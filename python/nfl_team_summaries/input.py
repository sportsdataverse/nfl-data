"""``nfl_model_pbp`` (nflfastR shape) -> the cfbfastR-schema frame the grid builder reads.

One boundary, one rename map. Everything downstream speaks the CFB builder's
names (``EPA``, ``pos_team_id``, ``yards_gained``, ``epa_success`` ...) so the
grid math is a transcription of the college producer, not a second definition.

nflfastR conventions kept on purpose (rbsdm.com uses the same ones):

* a DROPBACK (``pass`` here) is a pass attempt, a sack or a QB scramble;
* a RUSH is a rush attempt that is not a scramble;
* ``success`` is ``epa > 0``;
* kneels, spikes, no-plays (penalties), kickoffs, punts, FGs and conversions are
  not scrimmage plays. Fourth-down decisions and special teams are read from
  the raw frame separately (:mod:`nfl_team_summaries.rbsdm`).
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Callable, Iterable, Optional

import polars as pl

from .crosswalk import attach_team_ids

RELEASE_URL = (
    "https://github.com/sportsdataverse/sportsdataverse-data/releases/download/"
    "nfl_model_pbp/model_pbp_{season}.parquet"
)

#: the season types that make up a season's tables; POST is excluded because a
#: playoff team's extra games would inflate its per-game totals against the field
DEFAULT_SEASON_TYPES = ("REG",)

_SCRIMMAGE_PLAY_TYPES = ("pass", "run")


def load_model_pbp(season: int, source_dir: Optional[str | Path] = None) -> pl.DataFrame:
    """One season of ``nfl_model_pbp``: a local ``model_pbp_{season}.parquet`` if
    ``source_dir`` holds one, else the release asset."""
    if source_dir is not None:
        local = Path(source_dir) / f"model_pbp_{season}.parquet"
        if local.exists():
            return pl.read_parquet(local)
    import requests

    resp = requests.get(RELEASE_URL.format(season=season), timeout=300)
    resp.raise_for_status()
    return pl.read_parquet(io.BytesIO(resp.content))


def _flag(col: str) -> pl.Expr:
    return pl.col(col).fill_null(0).cast(pl.Int64)


def filter_season_types(pbp: pl.DataFrame, season_types: Iterable[str]) -> pl.DataFrame:
    return pbp.filter(pl.col("season_type").is_in(list(season_types)))


def prepare_plays(
    pbp: pl.DataFrame,
    season: int,
    *,
    season_types: Iterable[str] = DEFAULT_SEASON_TYPES,
    schedule_fn: Optional[Callable[..., pl.DataFrame]] = None,
) -> pl.DataFrame:
    """Scrimmage plays in the grid builder's schema.

    Args:
        pbp: a season of ``nfl_model_pbp``.
        season: the season (stamped as Int64 ``season``).
        season_types: which ``season_type`` values to keep.
        schedule_fn: injectable ``load_nfl_schedule``; supplies ``location`` for
            the neutral-site flag the opponent adjustment needs. ``None`` uses
            sdv-py's loader; a loader failure degrades to ``neutral_site=False``.
    """
    df = filter_season_types(pbp, season_types)
    if df.height == 0:
        return df

    # Drive context from the WHOLE frame (kickoffs/punts included) before the
    # scrimmage filter: a drive's start is its first snap from scrimmage, and
    # its yardage is what its scrimmage plays gained.
    df = df.with_columns(
        drive_id=pl.when(pl.col("fixed_drive").is_not_null())
        .then(pl.col("game_id") + "_" + pl.col("fixed_drive").cast(pl.Utf8))
        .otherwise(None)
    )
    is_scrim = pl.col("play_type").is_in(_SCRIMMAGE_PLAY_TYPES) & pl.col("down").is_not_null()
    df = df.sort(["game_id", "play_id"]).with_columns(
        drive_start_yards_to_goal=pl.when(is_scrim)
        .then(pl.col("yardline_100"))
        .otherwise(None)
        .drop_nulls()
        .first()
        .over("drive_id"),
        drive_yards=pl.when(is_scrim)
        .then(pl.col("yards_gained"))
        .otherwise(0)
        .sum()
        .over("drive_id"),
    )

    df = df.filter(is_scrim & pl.col("posteam").is_not_null() & pl.col("epa").is_not_null())

    dropback = (_flag("pass_attempt") == 1) | (_flag("sack") == 1) | (_flag("qb_scramble") == 1)
    rush = (_flag("rush_attempt") == 1) & (_flag("qb_scramble") == 0)
    df = df.with_columns(
        season=pl.lit(int(season), dtype=pl.Int64),
        game_id=pl.col("game_id").cast(pl.Utf8),
        game_play_number=pl.col("play_id"),
        pos_team=pl.col("posteam"),
        def_pos_team=pl.col("defteam"),
        home=pl.col("home_team"),
        away=pl.col("away_team"),
        EPA=pl.col("epa"),
        wpa=pl.col("wpa"),
        wp_before=pl.col("wp"),
        **{"pass": dropback.cast(pl.Float64), "rush": rush.cast(pl.Float64)},
        yards_gained=pl.col("yards_gained").cast(pl.Float64),
        distance=pl.col("ydstogo"),
        yards_to_goal=pl.col("yardline_100"),
        epa_success=(pl.col("epa") > 0).cast(pl.Float64),
        success=(pl.col("epa") > 0).cast(pl.Float64),
        sack_vec=_flag("sack").cast(pl.Float64),
        int=_flag("interception").cast(pl.Float64),
        fumble_vec=_flag("fumble").cast(pl.Float64),
        pass_breakup=pl.col("pass_defense_1_player_id").is_not_null(),
        # nflfastR's pass_attempt is 1 on sacks too; an ATTEMPT here is a ball
        # actually thrown (complete, incomplete or intercepted)
        pass_attempt=((_flag("pass_attempt") == 1) & (_flag("sack") == 0)).cast(pl.Float64),
        completion=_flag("complete_pass").cast(pl.Float64),
        pass_td=_flag("pass_touchdown").cast(pl.Float64),
        rush_td=_flag("rush_touchdown").cast(pl.Float64),
        yds_rushed=pl.when(rush)
        .then(pl.col("rushing_yards").fill_null(pl.col("yards_gained")))
        .otherwise(None)
        .cast(pl.Float64),
        yds_receiving=pl.when(_flag("complete_pass") == 1)
        .then(pl.col("receiving_yards").fill_null(pl.col("yards_gained")))
        .otherwise(None)
        .cast(pl.Float64),
        yds_passing=pl.when(_flag("complete_pass") == 1)
        .then(pl.col("passing_yards").fill_null(pl.col("yards_gained")))
        .otherwise(0.0)
        .cast(pl.Float64),
        yds_sacked=pl.when(_flag("sack") == 1)
        .then(pl.col("yards_gained"))
        .otherwise(None)
        .cast(pl.Float64),
    )
    df = df.with_columns(
        pos_EPA_pass=pl.when(pl.col("pass") == 1).then(pl.col("EPA")).otherwise(None),
        pos_EPA_rush=pl.when(pl.col("rush") == 1).then(pl.col("EPA")).otherwise(None),
    )

    df = attach_team_ids(df, "pos_team", "pos_team")
    df = attach_team_ids(df, "def_pos_team", "def_pos_team")
    df = attach_team_ids(df, "home", "home_team")
    df = attach_team_ids(df, "away", "away_team")

    df = df.with_columns(neutral_site=pl.lit(False))
    sched = _schedule(season, schedule_fn)
    if sched is not None and "location" in sched.columns:
        neutral = sched.select(
            pl.col("game_id").cast(pl.Utf8), (pl.col("location") == "Neutral").alias("__neutral")
        ).unique(subset=["game_id"])
        df = (
            df.join(neutral, on="game_id", how="left")
            .with_columns(neutral_site=pl.col("__neutral").fill_null(False))
            .drop("__neutral")
        )
    return df


def _schedule(season: int, schedule_fn) -> Optional[pl.DataFrame]:
    try:
        if schedule_fn is None:
            from sportsdataverse.nfl import load_nfl_schedule

            schedule_fn = load_nfl_schedule
        return schedule_fn(seasons=[season])
    except Exception as e:  # neutral-site is a refinement, never worth failing a build
        print(
            f"[nfl_team_summaries {season}] schedule unavailable ({e}); neutral_site=False",
            flush=True,
        )
        return None
