"""The seven season tables from a prepared scrimmage frame.

Structure and column names are transcribed from ``cfbfastR-cfb-data``'s
``cfb_data_build/team_summaries.py`` (itself a port of the R
``espn_cfb_15_team_summaries_creation.R``) so the two leagues publish one
contract. What is deliberately NOT carried over is that module's recovery of
ESPN's incomplete college sidecars (name->id maps for sacks and interceptions):
nflfastR-shape pbp carries ``passer_player_id`` on every sack and pick, so the
passer table is a plain aggregation here.

Ranks follow R's ``rank()`` (average ties), except that a null metric and a
constant column are unranked (null). Percentiles are
Weibull positions among qualifiers with null metrics excluded from the
denominator -- see ``_rank`` / ``_pct``.
"""

from __future__ import annotations

import functools
from pathlib import Path

import numpy as np
import polars as pl
import sportsdataverse
from sportsdataverse.cfb import cfb_adjusted_epa

from .checks import assert_adjustment_is_real, assert_finite, assert_passer_identity
from .crosswalk import attach_team_ids, load_crosswalk
from .league_averages import build_league_averages
from .rbsdm import passer_extras, team_extras

# Explosive-play EPA thresholds (shared with the college grid).
_EXPLOSIVE_PASS_EPA = 2.4
_EXPLOSIVE_RUSH_EPA = 1.8
# GEI normalization constant (gameonpaper).
_GEI_NORM = 179.01777401608126
#: Connelly's average point value of a turnover, the scale GOP's glossary uses for
#: turnover luck (and cfbfastR-cfb-data's team_summaries). Measured on 2025 the mean
#: EPA of a giveaway is -4.71 here (-3.90 in college).
_POINTS_PER_TURNOVER = 5.0


@functools.cache
def _field_position_ep() -> pl.DataFrame:
    """Expected points of a drive start by own yardline (99 rows), bundled with sdv-py.

    The yardline-only table GOP's Paper Index reads, on purpose: the pbp's EP is a
    model with score differential and clock among its inputs, so a drive start priced
    by it carries the scoreboard.
    """
    path = Path(sportsdataverse.__file__).parent / "nfl" / "models" / "nfl_field_position_ep.parquet"
    return pl.read_parquet(path).select(
        pl.col("yardline_own").cast(pl.Int64), pl.col("ep").cast(pl.Float64)
    )

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

#: (gate, minimum per team game) per player table -- the league baselines read the
#: same gates the rank / percentile attach does
PLAYER_QUALIFIERS: dict[str, tuple[pl.Expr, float]] = {
    "passing": (QB_QUALIFIES, QB_MIN_DROPBACKS_PER_GAME),
    "rushing": (RB_QUALIFIES, RB_MIN_RUSHES_PER_GAME),
    "receiving": (WR_QUALIFIES, WR_MIN_TARGETS_PER_GAME),
}
#: one level in this league (the college grid splits fbs / p4 / g5)
LEVELS: dict[str, pl.Expr | None] = {"nfl": None}

#: the per-(game, team) metrics the percentile ladder is cut on
PERCENTILE_METRICS: list[str] = [
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

#: table -> (ranked metrics, the subset ranked LOW-is-good). Every entry gets a
#: ``{metric}_rank`` and a ``{metric}_pct`` on the player table and a threshold
#: column in ``player_percentiles``. Of the TFD-5d columns only ``boom_rate`` and
#: ``stuff_rate`` are leaderboard metrics; the sd, floor, ceiling, bust rate, tier
#: shares and one-score split are descriptive and stay unranked.
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
            "boom_rate",
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
            "boom_rate",
            "stuff_rate",
        ],
        ["fumbles", "stuff_rate"],
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
            "boom_rate",
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
    """R ``rank()`` with average ties, but a null metric stays UNRANKED (null), so "no
    sample" never renders as "worst"; and a constant column (two or more values, all
    equal, like ``passrate_off_pass``) ranks nobody -- a tie for everyone is not a
    placing. An all-null column (``line_yards_off_pass``) is then unranked too."""
    c = pl.col(col)
    constant = (c.count() > 1) & (c.drop_nulls().n_unique() == 1)
    return pl.when(~constant).then(c.rank(method="average", descending=descending))


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


def _mutate_summary_margins(df: pl.DataFrame, *, whole_team: bool = False) -> pl.DataFrame:
    out = df.with_columns(
        [(pl.col(f"{b}_off") - pl.col(f"{b}_def")).alias(f"{b}_margin") for b in _MARGIN_BASES]
    )
    out = out.with_columns(
        [_rank(f"{b}_margin", descending=True).alias(f"{b}_margin_rank") for b in _MARGIN_BASES]
    )
    if whole_team:  # the overall pair only; field position is per drive (_drives_table)
        out = out.with_columns(
            explosive_margin=pl.col("explosive_off") - pl.col("explosive_def"),
            # havoc rate created minus allowed (shares of plays): havoc is bad for an
            # offense, so def - off, positive is good
            havoc_margin=pl.col("havoc_def") - pl.col("havoc_off"),
        ).with_columns(
            explosive_margin_rank=_rank("explosive_margin", descending=True),
            havoc_margin_rank=_rank("havoc_margin", descending=True),
        )
    return out


def _suffix_nonkey(df: pl.DataFrame, key: str, suffix: str) -> pl.DataFrame:
    return df.rename({c: f"{c}{suffix}" for c in df.columns if c != key})


def _side_pair(
    frame: pl.DataFrame, *, remove_cols: tuple[str, ...] = (), whole_team: bool = False
) -> pl.DataFrame:
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
        off.join(def_, left_on="pos_team_id", right_on="def_pos_team_id", how="left"),
        whole_team=whole_team,
    )


def _drives(plays: pl.DataFrame, group: str, ascending: bool) -> pl.DataFrame:
    per_drive = (
        plays.filter(pl.col("drive_id").is_not_null())
        .group_by([group, "drive_id"])
        .agg(
            total_available_yards=pl.col("drive_start_yards_to_goal").first(),
            total_gained_yards=pl.col("drive_yards").last(),
            # a scoring opportunity (sdv-py tendencies): a snap inside the opponent 40
            opp=(pl.col("yards_to_goal") <= 40).any(),
            points=pl.col("drive_points").first(),
        )
        .with_columns(
            _own_yardline=(100 - pl.col("total_available_yards")).round().cast(pl.Int64).clip(1, 99)
        )
        .join(_field_position_ep(), left_on="_own_yardline", right_on="yardline_own", how="left")
    )
    agg = per_drive.group_by(group).agg(
        total_available_yards=pl.col("total_available_yards").sum(),
        total_gained_yards=pl.col("total_gained_yards").sum(),
        pts_per_opp_n=pl.col("opp").sum().cast(pl.Int64),
        opp_points=pl.col("points").filter(pl.col("opp") == True).sum(),  # noqa: E712
        # sum() skips nulls: an asset without drive results would read as 0 points
        points_known=pl.col("points").is_not_null().all(),
        # field position is averaged per DRIVE, in yards and in points from the same
        # drives (until 2026-09-29 start_position was a mean over plays, so a long drive
        # counted once per snap)
        start_position=pl.col("total_available_yards").mean(),
        start_position_n=pl.col("total_available_yards").is_not_null().sum().cast(pl.Int64),
        drive_start_ep=pl.col("ep").mean(),
    )
    agg = (
        agg.with_columns(
            available_yards_pct=pl.col("total_gained_yards") / pl.col("total_available_yards"),
            pts_per_opp=pl.when((pl.col("pts_per_opp_n") > 0) & pl.col("points_known"))
            .then(pl.col("opp_points") / pl.col("pts_per_opp_n"))
            .otherwise(None),
        )
        .drop("opp_points", "points_known")
        .sort(group)
    )
    return agg.with_columns(
        available_yards_pct_rank=_rank("available_yards_pct", descending=not ascending),
        pts_per_opp_rank=_rank("pts_per_opp", descending=not ascending),
        # fewer yards to go ranks first on offense, more allowed on defense; the points
        # version the other way round
        start_position_rank=_rank("start_position", descending=ascending),
        drive_start_ep_rank=_rank("drive_start_ep", descending=not ascending),
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
            pts_per_opp_margin=pl.col("pts_per_opp_off") - pl.col("pts_per_opp_def"),
            # (100 - off) - (100 - def): positive when the team starts closer to goal
            start_position_margin=pl.col("start_position_def") - pl.col("start_position_off"),
            drive_start_ep_margin=pl.col("drive_start_ep_off") - pl.col("drive_start_ep_def"),
        )
        .with_columns(
            total_available_yards_margin_rank=_rank(
                "total_available_yards_margin", descending=True
            ),
            total_gained_yards_margin_rank=_rank("total_gained_yards_margin", descending=True),
            available_yards_pct_margin_rank=_rank("available_yards_pct_margin", descending=True),
            pts_per_opp_margin_rank=_rank("pts_per_opp_margin", descending=True),
            start_position_margin_rank=_rank("start_position_margin", descending=True),
            drive_start_ep_margin_rank=_rank("drive_start_ep_margin", descending=True),
        )
    )


def _turnovers(raw: pl.DataFrame) -> pl.DataFrame:
    """Giveaways / takeaways per game over EVERY play -- the official book's count.

    An interception is the passing team's giveaway; a lost fumble is the fumbling
    team's (``fumbled_1_team``: on a punt that is the RECEIVING team, not
    ``posteam``), and each is the other team's takeaway. Kick and punt muffs count,
    as they do in the official differential (2024: 30 of 32 teams match ESPN; the
    scrimmage-only count matched 9). ``turnover_margin`` = takeaways - giveaways.
    A team's games are those it appears in on EITHER side, so both rates share one
    denominator and the league margin sums to 0 even where the raw frame has gaps.

    Known limitation: ``fumble_lost`` is one flag per play and ``fumbled_1_team`` the
    FIRST fumbler, so a play with two lost fumbles keeps only the first. In 2024 that
    is ``2024_15_CIN_TEN`` play 3191 (TEN fumbles, CIN recovers, CIN fumbles out of
    the end zone for a touchback): CIN's giveaway and TEN's takeaway are missed --
    the two teams that miss ESPN by one. (``2024_13_PIT_CIN`` play 1857, where PIT
    recovers its own second fumble, is counted right.) The exact fix needs sdv-py
    to record the team per lost fumble (stat 106).
    """
    ints = raw.filter((pl.col("interception").fill_null(0) == 1) & pl.col("posteam").is_not_null())
    lost = raw.filter((pl.col("fumble_lost").fill_null(0) == 1) & pl.col("posteam").is_not_null())
    fumbler = pl.coalesce("fumbled_1_team", "posteam")
    other = (
        pl.when(fumbler == pl.col("posteam")).then(pl.col("defteam")).otherwise(pl.col("posteam"))
    )
    give = pl.concat([ints.select(team=pl.col("posteam")), lost.select(team=fumbler)])
    take = pl.concat([ints.select(team=pl.col("defteam")), lost.select(team=other)])
    games = (
        pl.concat(
            [
                raw.select(team=pl.col("posteam"), game_id=pl.col("game_id")),
                raw.select(team=pl.col("defteam"), game_id=pl.col("game_id")),
            ]
        )
        .drop_nulls()
        .unique()
        .group_by("team")
        .agg(games=pl.len())
    )
    out = (
        games.join(give.group_by("team").agg(giveaways=pl.len()), on="team", how="left")
        .join(take.group_by("team").agg(takeaways=pl.len()), on="team", how="left")
        .with_columns(
            turnovers_off=pl.col("giveaways").fill_null(0) / pl.col("games"),
            turnovers_def=pl.col("takeaways").fill_null(0) / pl.col("games"),
        )
        .with_columns(turnover_margin=pl.col("turnovers_def") - pl.col("turnovers_off"))
        .with_columns(
            turnovers_off_rank=_rank("turnovers_off", descending=False),
            turnovers_def_rank=_rank("turnovers_def", descending=True),
            turnover_margin_rank=_rank("turnover_margin", descending=True),
        )
    )
    return attach_team_ids(out, "team", "pos_team").drop("team", "games", "giveaways", "takeaways")


def _havoc_and_expected_turnovers(team_off: pl.DataFrame) -> pl.DataFrame:
    """Whole-team havoc EPA per game and Connelly's expected turnover margin per game.

    * ``havoc_EPAgame_off``: EPA per game on the team's own havoc snaps (the cost,
      negative); ``_def``: the same on its opponents' snaps it made havoc on;
      ``_margin`` = off - def, positive when its havoc costs opponents more.
    * ``expected_turnover_margin``: half of every scrimmage fumble recovered by each
      side, and interceptions at the season's measured share of passes defensed
      (INT + PBU). ``turnover_margin`` counts every play (a muffed punt included) and
      this cannot, so a muff reads as luck.

    Counts are cast to Float64 before any subtraction: polars sums booleans as
    UInt32, and takeaways - giveaways would wrap to ~4.3e9 when it goes negative.
    """
    defended = (pl.col("int") == 1) | (pl.col("pass_breakup") == True)  # noqa: E712
    on_pass = pl.col("pass") == 1
    int_share = team_off.select(
        (pl.col("int") == 1).sum().cast(pl.Float64)
        / defended.filter(on_pass).sum().cast(pl.Float64)
    ).item()

    def side(group: str, suffix: str) -> pl.DataFrame:
        return (
            team_off.group_by(group)
            .agg(
                games=pl.col("game_id").n_unique().cast(pl.Float64),
                havoc_epa=pl.col("EPA").filter(pl.col("havoc") == True).sum(),  # noqa: E712
                fumbles=(pl.col("fumble_vec") == 1).sum().cast(pl.Float64),
                defended=defended.filter(on_pass).sum().cast(pl.Float64),
            )
            .rename({group: "pos_team_id"})
            .rename(lambda c: c if c == "pos_team_id" else f"{c}{suffix}")
        )

    def per_game(col: str, side_: str) -> pl.Expr:
        return pl.col(f"{col}_{side_}") / pl.col(f"games_{side_}")

    off, de = side("pos_team_id", "_off"), side("def_pos_team_id", "_def")
    return (
        off.join(de, on="pos_team_id", how="left")
        .with_columns(
            havoc_EPAgame_off=per_game("havoc_epa", "off"),
            havoc_EPAgame_def=per_game("havoc_epa", "def"),
            # expected giveaways (off) and takeaways (def) per game: half of each
            # scrimmage fumble, INTs at the season's share of passes defensed
            expected_turnovers_off=0.5 * per_game("fumbles", "off")
            + int_share * per_game("defended", "off"),
            expected_turnovers_def=0.5 * per_game("fumbles", "def")
            + int_share * per_game("defended", "def"),
        )
        .with_columns(
            havoc_EPAgame_margin=pl.col("havoc_EPAgame_off") - pl.col("havoc_EPAgame_def"),
            expected_turnover_margin=pl.col("expected_turnovers_def")
            - pl.col("expected_turnovers_off"),
        )
        .select(
            "pos_team_id",
            "havoc_EPAgame_off",
            "havoc_EPAgame_def",
            "havoc_EPAgame_margin",
            "expected_turnovers_off",
            "expected_turnovers_def",
            "expected_turnover_margin",
        )
        .sort("pos_team_id")
        .with_columns(
            # less EPA lost to havoc is better on offense; more inflicted on defense
            havoc_EPAgame_off_rank=_rank("havoc_EPAgame_off", descending=True),
            havoc_EPAgame_def_rank=_rank("havoc_EPAgame_def", descending=False),
            havoc_EPAgame_margin_rank=_rank("havoc_EPAgame_margin", descending=True),
            # fewer expected giveaways rank first on offense, more takeaways on defense
            expected_turnovers_off_rank=_rank("expected_turnovers_off", descending=False),
            expected_turnovers_def_rank=_rank("expected_turnovers_def", descending=True),
            expected_turnover_margin_rank=_rank("expected_turnover_margin", descending=True),
        )
    )


def _add_turnover_luck(team_data: pl.DataFrame) -> pl.DataFrame:
    """Turnover luck in points per game, per side and overall, with ranks.

    Positive = lucky on both sides: fewer giveaways than expected (``_off``), more
    takeaways than expected (``_def``); the two sum to ``turnover_luck`` =
    ``_POINTS_PER_TURNOVER`` x (``turnover_margin`` - ``expected_turnover_margin``).
    """
    return team_data.with_columns(
        turnover_luck_off=_POINTS_PER_TURNOVER
        * (pl.col("expected_turnovers_off") - pl.col("turnovers_off")),
        turnover_luck_def=_POINTS_PER_TURNOVER
        * (pl.col("turnovers_def") - pl.col("expected_turnovers_def")),
        turnover_luck=_POINTS_PER_TURNOVER
        * (pl.col("turnover_margin") - pl.col("expected_turnover_margin")),
    ).with_columns(
        turnover_luck_off_rank=_rank("turnover_luck_off", descending=True),
        turnover_luck_def_rank=_rank("turnover_luck_def", descending=True),
        turnover_luck_rank=_rank("turnover_luck", descending=True),
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


#: below this many games with a play, every dispersion column is null: a spread, a
#: floor and a ceiling over one or two games describe those games, not the player
DISPERSION_MIN_GAMES = 3
_DISPERSION_COLS = ("EPAplay_sd", "EPAplay_p10", "EPAplay_p90", "boom_rate", "bust_rate")


def player_dispersion(rows: pl.DataFrame, keys: list[str]) -> pl.DataFrame:
    """Spread of a player's per-game EPA/play, one row per ``keys`` (the college twin's).

    ``rows`` is one row per play the player's table credits him with (the table's
    own play filter), carrying ``keys``, ``game_id`` and ``EPA``. A game's EPA/play
    is ``sum(EPA) / plays``, the form of the published ``EPAplay``, taken over every
    game with at least one such play (``dispersion_games``). Over those games:

    * ``EPAplay_sd``: population sd (ddof=0);
    * ``EPAplay_p10`` / ``EPAplay_p90``: floor and ceiling, linear interpolation
      (R type 7, the method :func:`_quantiles` uses);
    * ``boom_rate`` / ``bust_rate``: the share of games MORE than one sd above /
      below the player's own per-game mean. That mean is the unweighted mean of
      the games, the centre the sd is taken around, not the play-weighted
      ``EPAplay``. Strict, so a player whose games are all equal (sd 0) is neither
      rather than both.

    All five are null when ``dispersion_games < DISPERSION_MIN_GAMES``.

    The games are SORTED before they are reduced (as ``league_averages.summarize``
    does): the per-game frame leaves its group_by in no fixed order and float sums
    are not associative, so an unsorted mean / sd moves the last bit between two
    identical builds (every rerun of the 2025 rushers did).
    """
    x = pl.col("game_epa").sort()
    mean, sd = x.mean(), x.std(ddof=0)
    out = (
        rows.group_by([*keys, "game_id"])
        .agg(game_epa=pl.col("EPA").sum() / pl.len())
        .group_by(keys)
        .agg(
            dispersion_games=pl.len().cast(pl.Int64),
            EPAplay_sd=sd,
            EPAplay_p10=x.quantile(0.1, interpolation="linear"),
            EPAplay_p90=x.quantile(0.9, interpolation="linear"),
            boom_rate=(x > mean + sd).mean(),
            bust_rate=(x < mean - sd).mean(),
        )
    )
    enough = pl.col("dispersion_games") >= DISPERSION_MIN_GAMES
    return out.with_columns([pl.when(enough).then(pl.col(c)).alias(c) for c in _DISPERSION_COLS])


#: Football Outsiders' cut-points on a carry's own yards (``yds_rushed``): the line
#: takes 4 or fewer, losses included; the second level 5-10; the open field 11 or
#: more. The same cuts ``line_yards`` / ``second_level_yards`` / ``open_field_yards``
#: split on in add_derived_metrics.
_LINE_MAX_YARDS = 4
_SECOND_LEVEL_MAX_YARDS = 10
#: a one-score margin: a touchdown and a two-point try (the college twin's constant,
#: and the ``one_score_game`` margin in nfl_espn_build.tendencies)
ONE_SCORE_MARGIN = 8


def rusher_tiers(rows: pl.DataFrame, keys: list[str]) -> pl.DataFrame:
    """Per-rusher yardage tiers, stuff rate and one-score split, one row per ``keys``.

    The three tier shares and ``stuff_rate`` (carries for 0 or fewer yards) are over
    carries with a ``yds_rushed`` (a missing value is not a 0; every carry had one in
    1999, 2001, 2024 and 2025), so the shares sum to 1. ``EPAplay_one_score`` is EPA
    per carry with the score within ``ONE_SCORE_MARGIN`` at the snap
    (``pos_score_diff_start``, the offense's margin before the play) and
    ``EPAplay_not_one_score`` the rest. Each has its ``_n`` carries; with none the
    rate is null.
    """
    y = pl.col("yds_rushed")
    close = pl.col("pos_score_diff_start").abs() <= ONE_SCORE_MARGIN
    epa = pl.col("EPA")
    return rows.group_by(keys).agg(
        line_yards_share=(y <= _LINE_MAX_YARDS).mean(),
        second_level_share=((y > _LINE_MAX_YARDS) & (y <= _SECOND_LEVEL_MAX_YARDS)).mean(),
        open_field_share=(y > _SECOND_LEVEL_MAX_YARDS).mean(),
        stuff_rate=(y <= 0).mean(),
        EPAplay_one_score=epa.filter(close).mean(),
        EPAplay_one_score_n=close.sum().cast(pl.Int64),
        EPAplay_not_one_score=epa.filter(~close).mean(),
        EPAplay_not_one_score_n=(~close).sum().cast(pl.Int64),
    )


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


#: Cohort floors, as in the college twin (owner decision D-F5, 2026-09-26): a
#: conference or position group with fewer rows that have the metric gets a null
#: cohort percentile, not a percentile of two.
MIN_COHORT_TEAMS = 5
MIN_COHORT_PLAYERS = 10

#: roster ``position`` -> ``position_group``; any other listed position is ``other``
_POSITION_GROUPS = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE"}


def _attach_cohort_percentiles(
    df: pl.DataFrame, *, cohort: str, rank_cols: list[str], suffix: str, min_cohort: int
) -> pl.DataFrame:
    """Add ``<m>{suffix}``, the Weibull percentile of each ``<m>_rank`` within ``cohort``.

    The college twin's formula. The cohort rank ``r`` is the rank of ``<m>_rank``
    ascending within the cohort, over the rows whose ``<m>`` and ``<m>_rank`` are
    both non-null (a null ``_rank`` is a non-qualifier, a null metric or a column
    ``_rank`` leaves unranked).
    ``_rank`` already encodes direction, so ascending is best-first. Ties take
    ``_rank``'s own ``average`` method. The value is ``100 * (n + 1 - r) / (n + 1)``
    with ``n`` those rows in the cohort, and null when ``<m>`` or the cohort key is
    null or ``n < min_cohort``.
    """
    exprs = []
    for rc in rank_cols:
        m = rc.removesuffix("_rank")
        has = pl.col(m).is_not_null() & pl.col(rc).is_not_null() & pl.col(cohort).is_not_null()
        n = has.sum().over(cohort)
        r = pl.when(has).then(pl.col(rc)).rank(method="average").over(cohort)
        exprs.append(
            pl.when(has & (n >= min_cohort))
            .then(100 * (n + 1 - r) / (n + 1))
            .cast(pl.Float64)
            .alias(f"{m}{suffix}")
        )
    return df.with_columns(exprs)


def _attach_position_cohorts(df: pl.DataFrame, rosters: pl.DataFrame | None) -> pl.DataFrame:
    """Join the roster ``position_group`` onto a player table, then its ``_pos_pct``.

    ``rosters`` is the season's ``load_nfl_rosters`` frame (``gsis_id``,
    ``position``); None or empty leaves ``position_group`` null. A player listed
    twice under one group counts once; one listed under two different groups is
    ambiguous and stays null. ``gsis_id`` is pinned to the leaderboard ``player_id``
    dtype by an integer or string parse; a float on either side raises rather than
    joining through ``"123.0"``.
    """
    key = df.schema["player_id"]
    if rosters is None or rosters.is_empty():
        df = df.with_columns(position_group=pl.lit(None, dtype=pl.Utf8))
    else:
        src = rosters.schema["gsis_id"]
        if not all(d.is_integer() or d == pl.Utf8 for d in (src, key)):
            raise TypeError(
                f"roster gsis_id is {src}, leaderboard player_id is {key}: "
                "ids join through an integer or string parse, never a float"
            )
        pos = pl.col("position")
        groups = (
            rosters.select(
                player_id=pl.col("gsis_id").cast(key),
                position_group=pl.when(pos.is_not_null()).then(
                    pos.replace_strict(_POSITION_GROUPS, default="other")
                ),
            )
            .drop_nulls()
            .unique()
            .filter(pl.col("player_id").is_unique())
        )
        assert df.schema["player_id"] == groups.schema["player_id"], (
            f"player_id {df.schema['player_id']} != roster {groups.schema['player_id']}"
        )
        df = df.join(groups, on="player_id", how="left", validate="m:1")
    return _attach_cohort_percentiles(
        df,
        cohort="position_group",
        rank_cols=[c for c in df.columns if c.endswith("_rank")],
        suffix="_pos_pct",
        min_cohort=MIN_COHORT_PLAYERS,
    )


def per_game_metrics(df: pl.DataFrame) -> pl.DataFrame:
    """One row per (game_id, pos_team): the team-game metrics both the percentile
    ladder and the ``team_game`` league baselines are cut over.
    """
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
    # the select drops the sum_* helper columns, which would otherwise become
    # "metrics" for the league baselines cut over this same frame
    return per_game.select("game_id", "pos_team", *PERCENTILE_METRICS)


def _quantiles(per_game: pl.DataFrame) -> pl.DataFrame:
    """The 1..99 ladder over :func:`per_game_metrics`."""
    rows: dict[str, list[float]] = {"pctile": list(_PCTILES)}
    for c in PERCENTILE_METRICS:
        vals = per_game[c].cast(pl.Float64).to_numpy().astype(float)
        rows[c] = [float(np.nanquantile(vals, p, method="linear")) for p in _PCTILES]
    return pl.DataFrame(rows)


def prepare_player_percentiles(qualifiers: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """Metric value at each percentile 1..99, per position group.

    The season twin of the team-level :func:`_quantiles`, and the lookup
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


#: nflverse season_type -> ESPN's code, the one espn_nfl_* and the college table carry
_SEASON_TYPE_CODE = {"PRE": 1, "REG": 2, "POST": 3}
#: first season of ESPN's NFL library (nfl-raw ``nfl/espn/``): from here on every
#: played game must carry an ESPN event id
ESPN_FIRST_SEASON = 2002
#: team_opponent_splits column order: the F7 contract, then the nflverse key
SPLITS_COLUMNS = [
    "season",
    "team_id",
    "opponent_id",
    "game_id",
    "epa_per_play",
    "success_rate",
    "points_for",
    "points_against",
    "plays",
    "is_home",
    "week",
    "season_type",
    "nflverse_game_id",
]


def _team_off(plays: pl.DataFrame) -> pl.DataFrame:
    """The scrimmage frame every offensive rate aggregates (EPA and success both known)."""
    return plays.filter(pl.col("EPA").is_not_null() & pl.col("epa_success").is_not_null())


def build_team_opponent_splits(
    plays: pl.DataFrame, raw_pbp: pl.DataFrame, yr: int, espn_game_ids: pl.DataFrame
) -> pl.DataFrame:
    """One row per team-game: the opponent, EPA/play, success rate and final points.

    ``epa_per_play`` / ``success_rate`` / ``plays`` aggregate the SAME scrimmage
    frame the grid's ``EPAplay_off`` does (:func:`_team_off`), per ``(game_id,
    pos_team_id, def_pos_team_id)``, so a team's plays-weighted mean over its games
    is its season ``EPAplay_off``. Points are the final ``home_score`` /
    ``away_score`` nflfastR carries on every row of a game. A side with no
    scrimmage play is dropped, which removes a game that was never played
    (``2022_17_BUF_CIN``, the no-contest, carries only two placeholder rows and a
    7-3 "score"). ``team_id`` / ``opponent_id`` are ESPN ids; ``game_id`` is the
    ESPN event id from nfl-raw's crosswalk, with ``nflverse_game_id`` alongside.

    Args:
        plays: :func:`nfl_team_summaries.input.prepare_plays` output.
        raw_pbp: the same season's ``model_pbp``, filtered to the same season types.
        yr: season.
        espn_game_ids: :func:`nfl_team_summaries.crosswalk.load_espn_game_ids`.

    Raises:
        ValueError: if a game's context is not unique, or if, from
            :data:`ESPN_FIRST_SEASON` on, a played game has no ESPN event id --
            a missing or stale crosswalk must fail, not publish null ids.
            Earlier seasons have no ESPN library: their ``game_id`` is null.
    """
    games = raw_pbp.select(
        "game_id", "week", "season_type", "home_team", "away_team", "home_score", "away_score"
    ).unique()
    dup = games.filter(pl.col("game_id").is_duplicated())["game_id"].unique().to_list()
    if dup:
        raise ValueError(f"team_opponent_splits {yr}: game context not unique for {dup[:5]}")

    def side(us: str, them: str, is_home: bool) -> pl.DataFrame:
        return games.select(
            pl.col("game_id").alias("nflverse_game_id"),
            "week",
            "season_type",
            pl.col(f"{us}_team").alias("team"),
            pl.col(f"{them}_team").alias("opponent"),
            pl.col(f"{us}_score").cast(pl.Int64).alias("points_for"),
            pl.col(f"{them}_score").cast(pl.Int64).alias("points_against"),
            is_home=pl.lit(is_home),
        )

    sides = pl.concat([side("home", "away", True), side("away", "home", False)])
    sides = attach_team_ids(attach_team_ids(sides, "team", "team"), "opponent", "opponent")
    sides = sides.with_columns(pl.col("team_id", "opponent_id").cast(pl.Int64))
    per_game = (
        _team_off(plays)
        .group_by("game_id", "pos_team_id", "def_pos_team_id")
        .agg(
            epa_per_play=pl.col("EPA").mean(),
            success_rate=pl.col("epa_success").mean(),
            plays=pl.len().cast(pl.Int64),
        )
        .select(
            pl.col("game_id").alias("nflverse_game_id"),
            pl.col("pos_team_id").cast(pl.Int64).alias("team_id"),
            pl.col("def_pos_team_id").cast(pl.Int64).alias("opponent_id"),
            "epa_per_play",
            "success_rate",
            "plays",
        )
    )
    keys = ["nflverse_game_id", "team_id", "opponent_id"]
    for k in keys:
        assert sides.schema[k] == per_game.schema[k], (k, sides.schema[k], per_game.schema[k])
    assert sides.schema["nflverse_game_id"] == espn_game_ids.schema["nflverse_game_id"]
    # inner: a side that never took a snap is not a game played
    out = sides.join(per_game, on=keys, how="inner", validate="1:1").join(
        espn_game_ids, on="nflverse_game_id", how="left", validate="m:1"
    )
    unmatched = sorted(out.filter(pl.col("game_id").is_null())["nflverse_game_id"].unique())
    if unmatched and yr >= ESPN_FIRST_SEASON:
        raise ValueError(
            f"team_opponent_splits {yr}: {len(unmatched)} played game(s) have no ESPN event id "
            f"in nfl-raw's crosswalk (missing or stale?): {unmatched[:5]}"
        )
    return (
        out.with_columns(
            season=pl.lit(int(yr), dtype=pl.Int64),
            week=pl.col("week").cast(pl.Int64),
            season_type=pl.col("season_type").replace_strict(
                _SEASON_TYPE_CODE, return_dtype=pl.Int64
            ),
        )
        .select(SPLITS_COLUMNS)
        .sort("week", "nflverse_game_id", "is_home")
    )


def build_team_summaries(
    plays_input: pl.DataFrame,
    raw_pbp: pl.DataFrame,
    yr: int,
    *,
    rosters: pl.DataFrame | None = None,
) -> dict[str, pl.DataFrame]:
    """Build the seven tables (``team_opponent_splits`` is built on its own, see
    :func:`build_team_opponent_splits`).

    Args:
        plays_input: :func:`nfl_team_summaries.input.prepare_plays` output.
        raw_pbp: the same season's ``model_pbp`` filtered to the same season
            types -- the fourth-down and special-teams extras need plays the
            scrimmage frame drops.
        yr: season.
        rosters: the season's ``load_nfl_rosters`` frame the player tables'
            ``position_group`` comes from (``None`` leaves it and ``_pos_pct`` null).
    """
    plays = add_derived_metrics(plays_input)
    team_off = _team_off(plays)

    pctls = team_off.with_columns(
        GEI=(pl.col("wpa").abs().sum().over("game_id")) * (_GEI_NORM / pl.len().over("game_id"))
    )
    per_game = per_game_metrics(pctls)
    percentiles = _quantiles(per_game).with_columns(season=pl.lit(int(yr), dtype=pl.Int64))

    overall = _side_pair(team_off, whole_team=True)
    pass_data = _side_pair(team_off.filter(pl.col("pass") == 1))
    rush_data = _side_pair(team_off.filter(pl.col("rush") == 1))
    team_data = (
        overall.join(_drives_table(plays), on="pos_team_id", how="left", suffix="_drive")
        .join(pass_data, on="pos_team_id", how="left", suffix="_pass")
        .join(rush_data, on="pos_team_id", how="left", suffix="_rush")
        .join(_turnovers(raw_pbp), on="pos_team_id", how="left")
        .join(_havoc_and_expected_turnovers(team_off), on="pos_team_id", how="left")
        .pipe(_add_turnover_luck)
    )

    # leaderboards. Each table's per-game dispersion is cut over the rows its summary
    # reads: the passer's dropbacks (throws and sacks, the plays TEPA sums), carries,
    # targets
    qb_keys = ["pos_team_id", "passer_player_id"]
    qb_rows = team_off.filter(
        (pl.col("pass") == 1) & pl.col("passer_player_id").is_not_null()
    ).pipe(_add_team_games)
    qb = passer_extras(summarize_passer(qb_rows), team_off, min_expr=QB_QUALIFIES)
    qb = qb.join(player_dispersion(qb_rows, qb_keys), on=qb_keys, how="left", validate="1:1")
    qb = _attach_leader_ranks(qb, keys=qb_keys, min_expr=QB_QUALIFIES, spec="passing")
    qb = _attach_sample_sizes(qb, PLAYER_SAMPLE_SIZES["passing"])
    rb_keys = ["pos_team_id", "rusher_player_id"]
    rb_rows = team_off.filter(
        (pl.col("rush") == 1) & pl.col("rusher_player_id").is_not_null()
    ).pipe(_add_team_games)
    rb = (
        summarize_rusher(rb_rows)
        .join(player_dispersion(rb_rows, rb_keys), on=rb_keys, how="left", validate="1:1")
        .join(rusher_tiers(rb_rows, rb_keys), on=rb_keys, how="left", validate="1:1")
    )
    rb = _attach_leader_ranks(rb, keys=rb_keys, min_expr=RB_QUALIFIES, spec="rushing")
    rb = _attach_sample_sizes(rb, PLAYER_SAMPLE_SIZES["rushing"])
    wr_keys = ["pos_team_id", "receiver_player_id"]
    wr_rows = team_off.filter(
        (pl.col("pass_attempt") == 1) & pl.col("receiver_player_id").is_not_null()
    ).pipe(_add_team_games)
    wr = summarize_receiver(wr_rows).join(
        player_dispersion(wr_rows, wr_keys), on=wr_keys, how="left", validate="1:1"
    )
    wr = _attach_leader_ranks(wr, keys=wr_keys, min_expr=WR_QUALIFIES, spec="receiving")
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
    # pos_team_id / def_pos_team_id / home / neutral_site / wp_before). NFL keeps
    # the pre-#598 method: #598's refit was validated on CFB only and needs
    # wp_before_naive, which this build doesn't create (owner decision 2026-09-27).
    adj = (
        cfb_adjusted_epa(plays, method="pre598")
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
    # grid + rbsdm ranks alike, cohort AFC / NFC
    team_out = _attach_cohort_percentiles(
        team_out,
        cohort="conference",
        rank_cols=[c for c in team_out.columns if c.endswith("_rank")],
        suffix="_conf_pct",
        min_cohort=MIN_COHORT_TEAMS,
    )
    players = {
        name: _attach_position_cohorts(
            _prepare_for_write(df, yr).rename({id_col: "player_id"}), rosters
        )
        for name, df, id_col in (
            ("passing", qb, "passer_player_id"),
            ("rushing", rb, "rusher_player_id"),
            ("receiving", wr, "receiver_player_id"),
        )
    }

    tables = {
        "percentiles": percentiles,
        "player_percentiles": player_percentiles,
        "team_summaries": team_out,
        **players,
    }
    tables["league_averages"] = build_league_averages(
        {**tables, "team_game": per_game}, yr, levels=LEVELS, qualifiers=PLAYER_QUALIFIERS
    )
    return tables
