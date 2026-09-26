"""The five season tables from a prepared scrimmage frame.

Structure and column names are transcribed from ``cfbfastR-cfb-data``'s
``cfb_data_build/team_summaries.py`` (itself a port of the R
``espn_cfb_15_team_summaries_creation.R``) so the two leagues publish one
contract. What is deliberately NOT carried over is that module's recovery of
ESPN's incomplete college sidecars (name->id maps for sacks and interceptions):
nflfastR-shape pbp carries ``passer_player_id`` on every sack and pick, so the
passer table is a plain aggregation here.

Ranks follow R's ``rank()`` (average ties, nulls trailing); percentiles are
Weibull positions among qualifiers with null metrics excluded from the
denominator -- see ``_rank`` / ``_pct``.
"""

from __future__ import annotations

import numpy as np
import polars as pl
from sportsdataverse.cfb import cfb_adjusted_epa

from .checks import assert_adjustment_is_real, assert_finite, assert_passer_identity
from .crosswalk import load_crosswalk
from .rbsdm import passer_extras, team_extras

# Explosive-play EPA thresholds (shared with the college grid).
_EXPLOSIVE_PASS_EPA = 2.4
_EXPLOSIVE_RUSH_EPA = 1.8
# GEI normalization constant (gameonpaper).
_GEI_NORM = 179.01777401608126

#: leaderboard qualifier gates, per team game. Pro-Football-Reference's
#: per-category minimums (https://www.pro-football-reference.com/about/minimums.htm),
#: the ones gameonpaper.com's leaderboards already advertise; the college grid
#: borrowed the same three.
QB_MIN_DROPBACKS_PER_GAME = 14.0
RB_MIN_RUSHES_PER_GAME = 6.25
WR_MIN_TARGETS_PER_GAME = 1.875

#: the 1..99 percentile ladder both percentile tables are cut on
_PCTILES: tuple[float, ...] = tuple(round(0.01 * i, 2) for i in range(1, 100))

#: the qualifier gate per player table, written once and reused by the rank /
#: percentile attach AND by the percentile-threshold table, so a threshold can
#: never be taken over a different population than the ``_pct`` it explains.
QB_QUALIFIES = pl.col("dropbacks") >= QB_MIN_DROPBACKS_PER_GAME * pl.col("team_games")
RB_QUALIFIES = pl.col("plays") >= RB_MIN_RUSHES_PER_GAME * pl.col("team_games")
WR_QUALIFIES = pl.col("plays") >= WR_MIN_TARGETS_PER_GAME * pl.col("team_games")

#: table -> (ranked metrics, the subset ranked LOW-is-good). Every entry gets a
#: ``{metric}_rank`` and a ``{metric}_pct`` on the player table and a threshold
#: column in ``player_percentiles``.
PLAYER_RANK_SPECS: dict[str, tuple[list[str], list[str]]] = {
    "passing": (
        [
            "TEPA",
            "EPAgame",
            "EPAplay",
            "success",
            "comppct",
            "yards",
            "yardsplay",
            "yardsgame",
            "sack_adj_yards",
            "yardsdropback",
            "detmer",
            "detmergame",
            "passing_td",
            "pass_int",
            "sacked",
            "cpoe",
            "qb_epa_play",
            "epa_cpoe_composite",
        ],
        ["pass_int", "sacked"],
    ),
    "rushing": (
        [
            "TEPA",
            "EPAgame",
            "EPAplay",
            "success",
            "plays",
            "yards",
            "rushing_td",
            "fumbles",
            "yardsplay",
            "yardsgame",
        ],
        ["fumbles"],
    ),
    "receiving": (
        [
            "TEPA",
            "EPAgame",
            "EPAplay",
            "success",
            "comp",
            "targets",
            "catchpct",
            "yards",
            "passing_td",
            "fumbles",
            "yardsplay",
            "yardsgame",
        ],
        ["fumbles"],
    ),
}

#: union of every ranked player metric, in first-seen order -- the column set of
#: the ``player_percentiles`` table (a metric another group does not rank is null
#: on that group's rows).
PLAYER_PERCENTILE_METRICS: list[str] = list(
    dict.fromkeys(c for cols, _ in PLAYER_RANK_SPECS.values() for c in cols)
)


def _rank(col: str, *, descending: bool) -> pl.Expr:
    """R ``rank()`` -- average ties, ``na.last=TRUE`` (nulls take the trailing ranks)."""
    c = pl.col(col)
    base = c.rank(method="average", descending=descending)
    n_nonnull = c.is_not_null().sum()
    null_trail = (n_nonnull + c.is_null().cum_sum()).cast(pl.Float64)
    return pl.when(c.is_null()).then(null_trail).otherwise(base)


def _pct(col: str) -> pl.Expr:
    """Percentile (0-100) of ``{col}_rank`` among qualifiers that HAVE the metric.

    Weibull position ``(n + 1 - rank) / (n + 1)``: nobody sits at exactly 0 or
    100. A null metric yields a null percentile and leaves the denominator,
    so "unknown" never renders as "worst".
    """
    src = pl.col(col)
    rank = pl.col(f"{col}_rank")
    n = src.is_not_null().sum()
    return (
        pl.when(src.is_null()).then(None).otherwise(100 * (n + 1 - rank) / (n + 1)).cast(pl.Float64)
    )


def add_derived_metrics(plays: pl.DataFrame) -> pl.DataFrame:
    """Per-play situational columns the grid aggregates."""
    df = plays.with_columns(
        play_stuffed=pl.col("yards_gained") <= 0,
        red_zone=pl.col("yards_to_goal") <= 20,
    )
    df = df.with_columns(
        red_zone_success=pl.when(pl.col("red_zone")).then(pl.col("epa_success")).otherwise(None),
        third_down_success=pl.when(pl.col("down") == 3).then(pl.col("epa_success")).otherwise(None),
        late_down_success=pl.when(pl.col("down") >= 3).then(pl.col("epa_success")).otherwise(None),
        third_down_distance=pl.when(pl.col("down") == 3).then(pl.col("distance")).otherwise(None),
        early_down_EPA=pl.when(pl.col("down") <= 2).then(pl.col("EPA")).otherwise(None),
        early_down_success=pl.when(pl.col("down") <= 2).then(pl.col("epa_success")).otherwise(None),
        havoc=(
            (pl.col("sack_vec") == 1)
            | (pl.col("int") == 1)
            | (pl.col("fumble_vec") == 1)
            | (pl.col("pass_breakup") == True)  # noqa: E712
            | (pl.col("yards_gained") < 0)
        ),
        explosive=pl.when(pl.col("pass") == 1)
        .then(pl.col("EPA") >= _EXPLOSIVE_PASS_EPA)
        .when(pl.col("rush") == 1)
        .then(pl.col("EPA") >= _EXPLOSIVE_RUSH_EPA)
        .otherwise(False),
        opportunity_run=(pl.col("rush") == 1) & (pl.col("yds_rushed") >= 4),
    )
    rush = pl.col("rush") == 1
    yds = pl.col("yds_rushed")
    df = df.with_columns(
        adj_rush_yardage=pl.when(rush & (yds > 10))
        .then(pl.lit(10.0))
        .when(rush)
        .then(yds)
        .otherwise(None)
    )
    adj = pl.col("adj_rush_yardage")
    df = df.with_columns(
        line_yards=pl.when(rush & (yds < 0))
        .then(1.2 * adj)
        .when(rush & (yds >= 0) & (yds <= 4))
        .then(adj)
        .when(rush & (yds >= 5) & (yds <= 10))
        .then(0.5 * adj)
        .when(rush & (yds >= 11))
        .then(pl.lit(0.0))
        .otherwise(None),
        second_level_yards=pl.when(rush & (yds >= 5))
        .then(0.5 * (adj - 5))
        .when(rush)
        .then(pl.lit(0.0))
        .otherwise(None),
        open_field_yards=pl.when(rush & (yds > 10))
        .then(yds - adj)
        .when(rush)
        .then(pl.lit(0.0))
        .otherwise(None),
    )
    df = df.with_columns(highlight_yards=pl.col("second_level_yards") + pl.col("open_field_yards"))
    df = df.with_columns(
        nonExplosiveEpa=pl.when(pl.col("EPA").is_not_null() & (pl.col("explosive") == False))  # noqa: E712
        .then(pl.col("EPA"))
        .otherwise(None),
    )
    return df.sort(["game_id", "game_play_number"])


#: every MEAN-aggregated team metric -> the play-level column it averages; its
#: ``_n`` is that column's non-null count (the mean's actual denominator)
_TEAM_MEAN_SOURCES: dict[str, str] = {
    "passrate": "pass",
    "rushrate": "rush",
    "havoc": "havoc",
    "explosive": "explosive",
    "EPAplay": "EPA",
    "yardsplay": "yards_gained",
    "play_stuffed": "play_stuffed",
    "success": "epa_success",
    "red_zone_success": "red_zone_success",
    "third_down_success": "third_down_success",
    "third_down_distance": "third_down_distance",
    "late_down_success": "late_down_success",
    "early_down_EPA": "early_down_EPA",
    "start_position": "drive_start_yards_to_goal",
    "nonExplosiveEpaPerPlay": "nonExplosiveEpa",
    "line_yards": "line_yards",
    "opportunity_rate": "opportunity_run",
}
#: ratio metrics -> the count they divide by (read before n_games / n_drives are dropped)
_TEAM_RATIO_DENOMINATORS: dict[str, str] = {
    "playsgame": "n_games",
    "EPAgame": "n_games",
    "yardsgame": "n_games",
    "drivesgame": "n_games",
    "EPAdrive": "n_drives",
    "yardsdrive": "n_drives",
    "playsdrive": "n_drives",
}


def _summarize_team(
    df: pl.DataFrame, group: str, *, ascending: bool, remove_cols: tuple[str, ...] = ()
) -> pl.DataFrame:
    """One side of the grid for one group key (offense or defense)."""
    g = df.group_by(group).agg(
        *[
            pl.col(src).is_not_null().sum().cast(pl.Int64).alias(f"{m}_n")
            for m, src in _TEAM_MEAN_SOURCES.items()
        ],
        plays=pl.len(),
        n_games=pl.col("game_id").n_unique(),
        # n_unique counts null as a value; a scrimmage play with no fixed_drive must not add a drive
        n_drives=pl.col("drive_id").drop_nulls().n_unique(),
        passrate=pl.col("pass").mean(),
        rushrate=pl.col("rush").mean(),
        havoc=pl.col("havoc").mean(),
        explosive=pl.col("explosive").mean(),
        TEPA=pl.col("EPA").sum(),
        EPAplay=pl.col("EPA").mean(),
        yards=pl.col("yards_gained").sum(),
        yardsplay=pl.col("yards_gained").mean(),
        play_stuffed=pl.col("play_stuffed").mean(),
        success=pl.col("epa_success").mean(),
        red_zone_success=pl.col("red_zone_success").mean(),
        third_down_success=pl.col("third_down_success").mean(),
        third_down_distance=pl.col("third_down_distance").mean(),
        late_down_success=pl.col("late_down_success").mean(),
        early_down_EPA=pl.col("early_down_EPA").mean(),
        start_position=pl.col("drive_start_yards_to_goal").mean(),
        nonExplosiveEpaPerPlay=pl.col("nonExplosiveEpa").mean(),
        line_yards=pl.col("line_yards").mean(),
        opportunity_rate=pl.col("opportunity_run").mean(),
    )
    g = g.with_columns(
        playsgame=pl.col("plays") / pl.col("n_games"),
        EPAdrive=pl.col("TEPA") / pl.col("n_drives"),
        EPAgame=pl.col("TEPA") / pl.col("n_games"),
        yardsgame=pl.col("yards") / pl.col("n_games"),
        drives=pl.col("n_drives"),
        drivesgame=pl.col("n_drives") / pl.col("n_games"),
        yardsdrive=pl.col("yards") / pl.col("n_drives"),
        playsdrive=pl.col("plays") / pl.col("n_drives"),
        *[pl.col(d).cast(pl.Int64).alias(f"{m}_n") for m, d in _TEAM_RATIO_DENOMINATORS.items()],
    ).drop("n_games", "n_drives")
    g = g.sort(group)
    d = ascending
    g = g.with_columns(
        playsgame_rank=_rank("playsgame", descending=not d),
        TEPA_rank=_rank("TEPA", descending=not d),
        EPAgame_rank=_rank("EPAgame", descending=not d),
        EPAplay_rank=_rank("EPAplay", descending=not d),
        EPAdrive_rank=_rank("EPAdrive", descending=not d),
        early_down_EPA_rank=_rank("early_down_EPA", descending=not d),
        success_rank=_rank("success", descending=not d),
        yards_rank=_rank("yards", descending=not d),
        yardsplay_rank=_rank("yardsplay", descending=not d),
        yardsgame_rank=_rank("yardsgame", descending=not d),
        drivesgame_rank=_rank("drivesgame", descending=not d),
        yardsdrive_rank=_rank("yardsdrive", descending=not d),
        playsdrive_rank=_rank("playsdrive", descending=not d),
        play_stuffed_rank=_rank("play_stuffed", descending=d),
        red_zone_success_rank=_rank("red_zone_success", descending=not d),
        third_down_success_rank=_rank("third_down_success", descending=not d),
        late_down_success_rank=_rank("late_down_success", descending=not d),
        third_down_distance_rank=_rank("third_down_distance", descending=d),
        start_position_rank=_rank("start_position", descending=d),
        havoc_rank=_rank("havoc", descending=d),
        explosive_rank=_rank("explosive", descending=not d),
        passrate_rank=_rank("passrate", descending=True),
        rushrate_rank=_rank("rushrate", descending=True),
        nonExplosiveEpaPerPlay_rank=_rank("nonExplosiveEpaPerPlay", descending=not d),
        line_yards_rank=_rank("line_yards", descending=not d),
        opportunity_rate_rank=_rank("opportunity_rate", descending=not d),
    )
    if remove_cols:
        g = g.drop([c for c in remove_cols if c in g.columns])
    return g


_MARGIN_BASES = ["TEPA", "EPAplay", "EPAdrive", "EPAgame", "success", "yardsplay"]


def _mutate_summary_margins(df: pl.DataFrame) -> pl.DataFrame:
    out = df.with_columns(
        [(pl.col(f"{b}_off") - pl.col(f"{b}_def")).alias(f"{b}_margin") for b in _MARGIN_BASES]
    )
    out = out.with_columns(
        [_rank(f"{b}_margin", descending=True).alias(f"{b}_margin_rank") for b in _MARGIN_BASES]
    )
    if "start_position_off" in df.columns:
        out = out.with_columns(
            start_position_margin=(100 - pl.col("start_position_off"))
            - (100 - pl.col("start_position_def"))
        ).with_columns(start_position_margin_rank=_rank("start_position_margin", descending=True))
    return out


def _suffix_nonkey(df: pl.DataFrame, key: str, suffix: str) -> pl.DataFrame:
    return df.rename({c: f"{c}{suffix}" for c in df.columns if c != key})


def _side_pair(frame: pl.DataFrame, *, remove_cols: tuple[str, ...] = ()) -> pl.DataFrame:
    off = _suffix_nonkey(
        _summarize_team(frame, "pos_team_id", ascending=False, remove_cols=remove_cols),
        "pos_team_id",
        "_off",
    )
    def_ = _suffix_nonkey(
        _summarize_team(frame, "def_pos_team_id", ascending=True, remove_cols=remove_cols),
        "def_pos_team_id",
        "_def",
    )
    return _mutate_summary_margins(
        off.join(def_, left_on="pos_team_id", right_on="def_pos_team_id", how="left")
    )


def _drives(plays: pl.DataFrame, group: str, ascending: bool) -> pl.DataFrame:
    per_drive = (
        plays.filter(pl.col("drive_id").is_not_null())
        .group_by([group, "drive_id"])
        .agg(
            total_available_yards=pl.col("drive_start_yards_to_goal").first(),
            total_gained_yards=pl.col("drive_yards").last(),
        )
    )
    agg = per_drive.group_by(group).agg(
        total_available_yards=pl.col("total_available_yards").sum(),
        total_gained_yards=pl.col("total_gained_yards").sum(),
    )
    agg = agg.with_columns(
        available_yards_pct=pl.col("total_gained_yards") / pl.col("total_available_yards")
    ).sort(group)
    return agg.with_columns(
        available_yards_pct_rank=_rank("available_yards_pct", descending=not ascending)
    )


def _drives_table(plays: pl.DataFrame) -> pl.DataFrame:
    off_dr = _suffix_nonkey(_drives(plays, "pos_team_id", False), "pos_team_id", "_off")
    def_dr = _suffix_nonkey(_drives(plays, "def_pos_team_id", True), "def_pos_team_id", "_def")
    return (
        off_dr.join(def_dr, left_on="pos_team_id", right_on="def_pos_team_id", how="left")
        .with_columns(
            total_available_yards_margin=pl.col("total_available_yards_off")
            - pl.col("total_available_yards_def"),
            total_gained_yards_margin=pl.col("total_gained_yards_off")
            - pl.col("total_gained_yards_def"),
            available_yards_pct_margin=pl.col("available_yards_pct_off")
            - pl.col("available_yards_pct_def"),
        )
        .with_columns(
            total_available_yards_margin_rank=_rank(
                "total_available_yards_margin", descending=True
            ),
            total_gained_yards_margin_rank=_rank("total_gained_yards_margin", descending=True),
            available_yards_pct_margin_rank=_rank("available_yards_pct_margin", descending=True),
        )
    )


def _add_team_games(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(team_games=pl.col("game_id").n_unique().over("pos_team_id"))


def _per_game_rates(g: pl.DataFrame, yards_denom: str = "plays") -> pl.DataFrame:
    return g.with_columns(
        playsgame=pl.col("plays") / pl.col("games"),
        EPAgame=pl.col("TEPA") / pl.col("games"),
        yardsplay=pl.when(pl.col(yards_denom) > 0)
        .then(pl.col("yards") / pl.col(yards_denom))
        .otherwise(None),
        yardsgame=pl.col("yards") / pl.col("games"),
    )


def summarize_passer(df: pl.DataFrame) -> pl.DataFrame:
    """Per (team, passer) over DROPBACKS -- sacks and picks included from the start."""
    by = ["pos_team_id", "passer_player_id"]
    g = df.group_by(by).agg(
        passer_player_name=pl.col("passer_player_name").drop_nulls().first(),
        plays=pl.len(),
        games=pl.col("game_id").n_unique(),
        team_games=pl.col("team_games").last(),
        TEPA=pl.col("EPA").sum(),
        yards=pl.col("yds_passing").sum(),
        success=pl.col("success").mean(),
        comp=pl.col("completion").sum(),
        att=pl.col("pass_attempt").sum(),
        passing_td=pl.col("pass_td").sum(),
        sacked=pl.col("sack_vec").sum(),
        sack_yds=(-pl.col("yds_sacked")).sum(),
        pass_int=pl.col("int").sum(),
    )
    g = g.with_columns(
        dropbacks=pl.col("plays").cast(pl.Float64),
        comppct=pl.when(pl.col("att") > 0).then(pl.col("comp") / pl.col("att")).otherwise(None),
        sack_adj_yards=pl.col("yards") - pl.col("sack_yds"),
    )
    g = g.with_columns(
        EPAplay=pl.col("TEPA") / pl.col("dropbacks"),
        yardsdropback=pl.col("sack_adj_yards") / pl.col("dropbacks"),
        detmer=(pl.col("yards") / (400 * pl.col("games")))
        * (
            (pl.col("passing_td") + pl.col("pass_int"))
            / (1 + (pl.col("passing_td") - pl.col("pass_int")).abs())
        ),
        detmergame=(pl.col("yards") / pl.col("games") / 400)
        * (
            ((pl.col("passing_td") / pl.col("games")) + (pl.col("pass_int") / pl.col("games")))
            / (
                1
                + (
                    (pl.col("passing_td") / pl.col("games"))
                    - (pl.col("pass_int") / pl.col("games"))
                ).abs()
            )
        ),
    )
    return _per_game_rates(g, yards_denom="att")


def summarize_rusher(df: pl.DataFrame) -> pl.DataFrame:
    g = df.group_by(["pos_team_id", "rusher_player_id"]).agg(
        rusher_player_name=pl.col("rusher_player_name").drop_nulls().first(),
        plays=pl.len(),
        games=pl.col("game_id").n_unique(),
        team_games=pl.col("team_games").last(),
        TEPA=pl.col("EPA").sum(),
        EPAplay=pl.col("EPA").mean(),
        yards=pl.col("yds_rushed").sum(),
        success=pl.col("epa_success").mean(),
        rushing_td=pl.col("rush_td").sum(),
        fumbles=pl.col("fumble_vec").sum(),
    )
    return _per_game_rates(g)


def summarize_receiver(df: pl.DataFrame) -> pl.DataFrame:
    g = df.group_by(["pos_team_id", "receiver_player_id"]).agg(
        receiver_player_name=pl.col("receiver_player_name").drop_nulls().first(),
        plays=pl.len(),
        games=pl.col("game_id").n_unique(),
        team_games=pl.col("team_games").last(),
        TEPA=pl.col("EPA").sum(),
        EPAplay=pl.col("EPA").mean(),
        yards=pl.col("yds_receiving").sum(),
        success=pl.col("epa_success").mean(),
        comp=pl.col("completion").sum(),
        targets=pl.len(),
        passing_td=pl.col("pass_td").sum(),
        fumbles=pl.col("fumble_vec").sum(),
    )
    g = g.with_columns(catchpct=pl.col("comp") / pl.col("targets"))
    return _per_game_rates(g)


_PER_GAME_N = {m: pl.col("games") for m in ("EPAgame", "yardsgame", "playsgame")}
#: player rate -> the count it is a rate over (transcribed from summarize_* above)
PLAYER_SAMPLE_SIZES: dict[str, dict[str, pl.Expr]] = {
    "passing": {
        "EPAplay": pl.col("dropbacks"),
        "yardsdropback": pl.col("dropbacks"),
        "success": pl.col("plays"),  # plays == dropbacks here
        "comppct": pl.col("att"),
        "yardsplay": pl.col("att"),  # _per_game_rates(yards_denom="att")
        "detmer": pl.col("games"),
        "detmergame": pl.col("games"),
        **_PER_GAME_N,
    },
    "rushing": {
        "EPAplay": pl.col("plays"),
        "success": pl.col("plays"),
        "yardsplay": pl.col("plays"),
        **_PER_GAME_N,
    },
    "receiving": {
        "EPAplay": pl.col("plays"),
        "success": pl.col("plays"),
        "yardsplay": pl.col("plays"),
        "catchpct": pl.col("targets"),
        **_PER_GAME_N,
    },
}


def _attach_sample_sizes(df: pl.DataFrame, denominators: dict[str, pl.Expr]) -> pl.DataFrame:
    """Add ``{rate}_n`` beside every rate ``df`` carries: the count it is a rate over (0 when null)."""
    present = {m: e for m, e in denominators.items() if m in df.columns}
    return df.with_columns(
        *[e.fill_null(0).cast(pl.Int64).alias(f"{m}_n") for m, e in present.items()]
    )


def _attach_leader_ranks(
    data: pl.DataFrame,
    *,
    keys: list[str],
    min_expr: pl.Expr,
    spec: str | None = None,
    rank_cols: list[str] | None = None,
    asc_cols: list[str] | None = None,
) -> pl.DataFrame:
    """Ranks + percentiles AMONG QUALIFIERS, left-joined back onto every row.

    Pass ``spec`` (a :data:`PLAYER_RANK_SPECS` key) so the ranked set and its
    directions are read from the same place ``prepare_player_percentiles`` reads
    them; ``rank_cols``/``asc_cols`` stay for ad-hoc callers and tests.
    """
    if spec is not None:
        rank_cols, asc_cols = PLAYER_RANK_SPECS[spec]
    if not rank_cols:
        raise ValueError("pass either spec= or a non-empty rank_cols=")
    asc = set(asc_cols or [])
    stray = sorted(asc - set(rank_cols))
    if stray:
        raise ValueError(
            f"asc_cols entries missing from rank_cols: {stray}. They would be ranked high-is-good."
        )
    qual = data.filter(min_expr).with_columns(
        *[_rank(c, descending=(c not in asc)).alias(f"{c}_rank") for c in rank_cols]
    )
    qual = qual.with_columns(*[_pct(c).alias(f"{c}_pct") for c in rank_cols])
    out = qual.select(*keys, *[f"{c}_rank" for c in rank_cols], *[f"{c}_pct" for c in rank_cols])
    return data.join(out, on=keys, how="left")


def prepare_percentiles(df: pl.DataFrame) -> pl.DataFrame:
    """Per-(game, team) metrics -> the 1..99 quantile table."""
    per_game = df.group_by(["game_id", "pos_team"]).agg(
        GEI=pl.col("GEI").drop_nulls().first(),
        EPAplay=pl.col("EPA").mean(),
        pass_success=pl.col("epa_success").filter(pl.col("pass") == 1).mean(),
        rush_success=pl.col("epa_success").filter(pl.col("rush") == 1).mean(),
        early_down_success=pl.col("early_down_success").mean(),
        early_down_EPA=pl.col("early_down_EPA").mean(),
        late_down_success=pl.col("late_down_success").mean(),
        success=pl.col("epa_success").mean(),
        yardsplay=pl.col("yards_gained").mean(),
        dropbacks=pl.col("pass").sum(),
        rushes=pl.col("rush").sum(),
        sum_pos_EPA_pass=pl.col("pos_EPA_pass").sum(),
        sum_pos_EPA_rush=pl.col("pos_EPA_rush").sum(),
        sum_yds_receiving=pl.col("yds_receiving").sum(),
        sum_yds_sacked=pl.col("yds_sacked").sum(),
        pass_explosive=pl.col("explosive").filter(pl.col("pass") == 1).mean(),
        rush_explosive=pl.col("explosive").filter(pl.col("rush") == 1).mean(),
        explosive=pl.col("explosive").mean(),
        third_down_success=pl.col("third_down_success").mean(),
        red_zone_success=pl.col("red_zone_success").mean(),
        play_stuffed=pl.col("play_stuffed").mean(),
        nonExplosiveEpaPerPlay=pl.col("nonExplosiveEpa").mean(),
        havoc=pl.col("havoc").mean(),
        yardsrush=pl.col("yds_rushed").mean(),
        lineyards=pl.col("line_yards").mean(),
        opportunity_run=pl.col("opportunity_run").mean(),
        third_down_distance=pl.col("third_down_distance").mean(),
    )
    per_game = per_game.with_columns(
        EPAdropback=pl.when(pl.col("dropbacks") == 0)
        .then(0.0)
        .otherwise(pl.col("sum_pos_EPA_pass") / pl.col("dropbacks")),
        EPArush=pl.when(pl.col("rushes") == 0)
        .then(0.0)
        .otherwise(pl.col("sum_pos_EPA_rush") / pl.col("rushes")),
        yardsdropback=pl.when(pl.col("dropbacks") == 0)
        .then(0.0)
        .otherwise((pl.col("sum_yds_receiving") + pl.col("sum_yds_sacked")) / pl.col("dropbacks")),
    )
    metric_cols = [
        "GEI",
        "EPAplay",
        "pass_success",
        "rush_success",
        "early_down_success",
        "early_down_EPA",
        "late_down_success",
        "success",
        "yardsplay",
        "dropbacks",
        "rushes",
        "EPAdropback",
        "EPArush",
        "yardsdropback",
        "pass_explosive",
        "rush_explosive",
        "explosive",
        "third_down_success",
        "red_zone_success",
        "play_stuffed",
        "nonExplosiveEpaPerPlay",
        "havoc",
        "yardsrush",
        "lineyards",
        "opportunity_run",
        "third_down_distance",
    ]
    rows: dict[str, list[float]] = {"pctile": list(_PCTILES)}
    for c in metric_cols:
        vals = per_game[c].cast(pl.Float64).to_numpy().astype(float)
        rows[c] = [float(np.nanquantile(vals, p, method="linear")) for p in _PCTILES]
    return pl.DataFrame(rows)


def prepare_player_percentiles(qualifiers: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """Metric value at each percentile 1..99, per position group.

    The season twin of the team-level :func:`prepare_percentiles`, and the lookup
    side of the players' ``_pct`` columns: it answers "what EPA/play is a
    90th-percentile QB?" without shipping a roster. Shape mirrors the team table
    -- one row per percentile, one column per metric -- plus a ``position_group``
    discriminator. A metric a group does not rank is null on that group's rows.

    Two things keep it honest against the ``_pct`` a player carries:

    * it reads the SAME qualifier frames ``_attach_leader_ranks`` ranked, so the
      population behind a threshold is the population behind the percentile;
    * a LOW-is-good metric (interceptions, sacks taken, fumbles) is read from the
      opposite tail -- the 90th percentile of ``pass_int`` is a LOW pick count,
      the value a QB with ``pass_int_pct == 90`` actually has. Taking the plain
      90th quantile here would print the worst QBs' numbers against the best
      QBs' bar.
    """
    schema = {"position_group": pl.Utf8, "pctile": pl.Float64}
    schema.update({m: pl.Float64 for m in PLAYER_PERCENTILE_METRICS})
    frames = []
    for group, df in qualifiers.items():
        ranked, asc = PLAYER_RANK_SPECS[group]
        cols: dict[str, list] = {
            "position_group": [group] * len(_PCTILES),
            "pctile": list(_PCTILES),
        }
        for m in PLAYER_PERCENTILE_METRICS:
            if m not in ranked or df.height == 0:
                cols[m] = [None] * len(_PCTILES)
                continue
            vals = df[m].cast(pl.Float64).to_numpy().astype(float)
            if not np.isfinite(vals).any():
                cols[m] = [None] * len(_PCTILES)
                continue
            # low-is-good: the Nth percentile of GOODNESS is the (1-N)th of the value
            qs = [(1.0 - p) if m in asc else p for p in _PCTILES]
            cols[m] = [float(np.nanquantile(vals, q, method="linear")) for q in qs]
        frames.append(pl.DataFrame(cols, schema=schema))
    return pl.concat(frames, how="vertical")


def _clean_rank_columns(df: pl.DataFrame) -> pl.DataFrame:
    """``TEPA_rank_off`` -> ``TEPA_off_rank`` and ``EPAplay_n_off_pass`` -> ``EPAplay_off_pass_n``
    (the join suffixes land mid-name)."""
    rank_renames = {c: c.replace("_rank", "", 1) + "_rank" for c in df.columns if "_rank" in c}
    n_renames = {c: c.replace("_n_", "_", 1) + "_n" for c in df.columns if "_n_" in c}
    assert not (rank_renames.keys() & n_renames.keys()), (
        "a column needs both a _rank and a _n_ mid-name relocation -- "
        "the two rename dicts must stay disjoint"
    )
    renames = rank_renames | n_renames
    renames = {k: v for k, v in renames.items() if k != v}
    return df.rename(renames) if renames else df


def _teams_lookup() -> pl.DataFrame:
    xw = load_crosswalk()
    return xw.select(
        pl.col("espn_team_id").cast(pl.Int64).alias("team_id"),
        pl.col("nflverse_abbr").alias("pos_team"),
        pl.col("team_name"),
        pl.col("conference"),
        pl.col("division"),
    )


def _prepare_for_write(df: pl.DataFrame, yr: int) -> pl.DataFrame:
    """Rank suffixes to the end, identity columns first, season as Int64."""
    df = _clean_rank_columns(df)
    out = (
        df.with_columns(season=pl.lit(int(yr), dtype=pl.Int64))
        .rename({"pos_team_id": "team_id"})
        # bigint, like the college table in sdv-db (the site types team_id as a number)
        .with_columns(team_id=pl.col("team_id").cast(pl.Int64))
        .join(_teams_lookup(), on="team_id", how="left")
        # the college grid's classification column; one class in this league,
        # kept so a shared `fbs_class` filter never 400s
        .with_columns(fbs_class=pl.lit("NFL"))
    )
    lead = ["team_id", "pos_team", "team_name", "division", "conference", "season"]
    rest = [c for c in out.columns if c not in lead]
    return out.select(lead + rest)


def build_team_summaries(
    plays_input: pl.DataFrame, raw_pbp: pl.DataFrame, yr: int
) -> dict[str, pl.DataFrame]:
    """Build the five tables.

    Args:
        plays_input: :func:`nfl_team_summaries.input.prepare_plays` output.
        raw_pbp: the same season's ``model_pbp`` filtered to the same season
            types -- the fourth-down and special-teams extras need plays the
            scrimmage frame drops.
        yr: season.
    """
    plays = add_derived_metrics(plays_input)
    team_off = plays.filter(pl.col("EPA").is_not_null() & pl.col("epa_success").is_not_null())

    pctls = team_off.with_columns(
        GEI=(pl.col("wpa").abs().sum().over("game_id")) * (_GEI_NORM / pl.len().over("game_id"))
    )
    percentiles = prepare_percentiles(pctls).with_columns(season=pl.lit(int(yr), dtype=pl.Int64))

    rc = ("start_position", "start_position_rank", "start_position_n")
    overall = _side_pair(team_off)
    pass_data = _side_pair(team_off.filter(pl.col("pass") == 1), remove_cols=rc)
    rush_data = _side_pair(team_off.filter(pl.col("rush") == 1), remove_cols=rc)
    team_data = (
        overall.join(_drives_table(plays), on="pos_team_id", how="left", suffix="_drive")
        .join(pass_data, on="pos_team_id", how="left", suffix="_pass")
        .join(rush_data, on="pos_team_id", how="left", suffix="_rush")
    )

    # leaderboards
    qb = summarize_passer(
        team_off.filter((pl.col("pass") == 1) & pl.col("passer_player_id").is_not_null()).pipe(
            _add_team_games
        )
    )
    qb = passer_extras(qb, team_off, min_expr=QB_QUALIFIES)
    qb = _attach_leader_ranks(
        qb, keys=["pos_team_id", "passer_player_id"], min_expr=QB_QUALIFIES, spec="passing"
    )
    qb = _attach_sample_sizes(qb, PLAYER_SAMPLE_SIZES["passing"])
    rb = summarize_rusher(
        team_off.filter((pl.col("rush") == 1) & pl.col("rusher_player_id").is_not_null()).pipe(
            _add_team_games
        )
    )
    rb = _attach_leader_ranks(
        rb, keys=["pos_team_id", "rusher_player_id"], min_expr=RB_QUALIFIES, spec="rushing"
    )
    rb = _attach_sample_sizes(rb, PLAYER_SAMPLE_SIZES["rushing"])
    wr = summarize_receiver(
        team_off.filter(
            (pl.col("pass_attempt") == 1) & pl.col("receiver_player_id").is_not_null()
        ).pipe(_add_team_games)
    )
    wr = _attach_leader_ranks(
        wr, keys=["pos_team_id", "receiver_player_id"], min_expr=WR_QUALIFIES, spec="receiving"
    )
    wr = _attach_sample_sizes(wr, PLAYER_SAMPLE_SIZES["receiving"])
    # thresholds over exactly the frames that were ranked above
    player_percentiles = prepare_player_percentiles(
        {
            "passing": qb.filter(QB_QUALIFIES),
            "rushing": rb.filter(RB_QUALIFIES),
            "receiving": wr.filter(WR_QUALIFIES),
        }
    ).with_columns(season=pl.lit(int(yr), dtype=pl.Int64))

    # opponent-adjusted EPA: the shared sdv-py ridge (league-agnostic; keyed on
    # pos_team_id / def_pos_team_id / home / neutral_site / wp_before)
    adj = (
        cfb_adjusted_epa(plays)
        .drop("pos_team")
        .with_columns(team_id=pl.col("team_id").cast(pl.Int64))
    )
    team_out = _prepare_for_write(team_data, yr).join(adj, on="team_id", how="left")
    extras = team_extras(raw_pbp, plays).with_columns(team_id=pl.col("team_id").cast(pl.Int64))
    team_out = team_out.join(extras, on="team_id", how="left")
    assert_adjustment_is_real(team_out, label=f"team_summaries {yr}")
    assert_finite(
        team_out.drop([c for c in team_out.columns if c.endswith("_margin")]),
        label=f"team_summaries {yr}",
    )
    assert_passer_identity(qb, label=str(yr))

    return {
        "percentiles": percentiles,
        "player_percentiles": player_percentiles,
        "team_summaries": team_out,
        "passing": _prepare_for_write(qb, yr).rename({"passer_player_id": "player_id"}),
        "rushing": _prepare_for_write(rb, yr).rename({"rusher_player_id": "player_id"}),
        "receiving": _prepare_for_write(wr, yr).rename({"receiver_player_id": "player_id"}),
    }
