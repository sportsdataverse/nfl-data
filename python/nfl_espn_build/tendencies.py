"""Season tendencies per team and per head coach (``sportsdataverse.football.tendencies``).

Three datasets, all computed at BUILD time from the season's reshaped plays so
the installed sdv-py defines every metric:

* ``team_tendencies`` -- one row per (season, team): pace, run/pass splits by
  down and score state, situation-neutral rates, explosive / success / EPA,
  third downs over expected, red-zone and scoring-opportunity efficiency,
  scripted vs non-scripted drives, fourth-down decisions against the bundled
  model, plus the ``def_*`` twin (what the team's defense allowed).
* ``coach_tendencies`` -- the same row per (season, team, head coach). The
  head coach of each game comes from the nflverse schedule
  (``home_coach`` / ``away_coach``, complete since 1999, keyed by ESPN event
  id), so a midseason change splits the season between the two coaches and
  an interim coach gets their own row.
* ``coach_careers`` -- every ``coach_tendencies`` season present in the output
  root summed per coach with the rates recomputed (one season-less file).

Preseason snaps are excluded everywhere: they describe a depth chart, not a
coach. Coordinators are not attributed -- no public source names the OC / DC
per game -- so ``role`` is always ``"HC"`` for now and exists so a
coordinator row can be added without a schema change.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import polars as pl

from nfl_espn_build.reshape import bind_games
from nfl_espn_build.reshapers import RESHAPERS

log = logging.getLogger(__name__)

LEAGUE = "nfl"
#: ESPN season types that count: regular season (2) and postseason (3)
COUNTED_SEASON_TYPES = (2, 3)
TEAM_GROUP = ("season", "pos_team")
COACH_GROUP = ("season", "pos_team", "coach")
COACH_DEF_GROUP = ("season", "def_pos_team", "def_coach")
COACH_SCHEMA = {"game_id": pl.Int64, "home_coach": pl.Utf8, "away_coach": pl.Utf8}


def season_plays(finals: list[dict[str, Any]]) -> pl.DataFrame:
    """The season's reshaped plays (the ``pbp`` cut, ids unresolved), regular + postseason only."""
    df = bind_games([RESHAPERS["pbp"](game) for game in finals])
    # the processor stamps `seasonType` on every play and reshape_pbp adds the
    # crosswalk's `season_type`; either one excludes preseason
    col = next((c for c in ("season_type", "seasonType") if c in df.columns), None)
    if df.height and col is not None:
        df = df.filter(pl.col(col).cast(pl.Int64, strict=False).is_in(COUNTED_SEASON_TYPES))
    return df


def coach_games(season: int) -> pl.DataFrame:
    """``(game_id, home_coach, away_coach)`` per ESPN event id from the nflverse schedule.

    Empty (with the schema) when the schedule cannot be read, so the coach
    datasets come out empty for the season rather than wrong.
    """
    try:
        from sportsdataverse.nfl import load_nfl_schedule

        sched = load_nfl_schedule(seasons=[int(season)])
    except Exception as exc:  # noqa: BLE001 -- network / release availability
        log.warning(
            "season %s: nflverse schedule unavailable (%r); no coach attribution", season, exc
        )
        return pl.DataFrame(schema=COACH_SCHEMA)
    if not {"espn", "home_coach", "away_coach"} <= set(sched.columns):
        log.warning(
            "season %s: nflverse schedule has no coach columns; no coach attribution", season
        )
        return pl.DataFrame(schema=COACH_SCHEMA)
    return (
        sched.select(
            pl.col("espn").cast(pl.Int64, strict=False).alias("game_id"),
            pl.col("home_coach").cast(pl.Utf8),
            pl.col("away_coach").cast(pl.Utf8),
        )
        .drop_nulls("game_id")
        .unique(subset=["game_id"], keep="first")
    )


def attach_coaches(plays: pl.DataFrame, coaches: pl.DataFrame) -> pl.DataFrame:
    """``coach`` / ``def_coach`` on every play from its game's sidelines.

    Plays whose game has no known coach on either side are dropped: an
    unattributed snap would otherwise land on a null coach row.
    """
    if plays.height == 0 or coaches.height == 0:
        # built from a schema, not with_columns(lit): a literal on a frame with
        # no columns broadcasts to ONE row, which would then be a "play"
        return pl.DataFrame(schema={**plays.schema, "coach": pl.Utf8, "def_coach": pl.Utf8})
    coaches = coaches.select(
        pl.col("game_id").cast(pl.Int64),
        pl.col("home_coach").cast(pl.Utf8),
        pl.col("away_coach").cast(pl.Utf8),
    )
    df = plays.with_columns(pl.col("game_id").cast(pl.Int64))
    assert df.schema["game_id"] == coaches.schema["game_id"]
    df = df.join(coaches, on="game_id", how="left")
    home = pl.col("pos_team").cast(pl.Int64, strict=False) == pl.col("homeTeamId").cast(
        pl.Int64, strict=False
    )
    df = df.with_columns(
        coach=pl.when(home).then(pl.col("home_coach")).otherwise(pl.col("away_coach")),
        def_coach=pl.when(home).then(pl.col("away_coach")).otherwise(pl.col("home_coach")),
    ).drop("home_coach", "away_coach")
    return df.filter(pl.col("coach").is_not_null() & pl.col("def_coach").is_not_null())


def team_tendencies(plays: pl.DataFrame) -> pl.DataFrame:
    """One row per (season, team)."""
    if plays.height == 0:
        return pl.DataFrame()
    from sportsdataverse.football.tendencies import tendencies

    return tendencies(plays, league=LEAGUE, group_cols=TEAM_GROUP)


def coach_tendencies(plays: pl.DataFrame, coaches: pl.DataFrame) -> pl.DataFrame:
    """One row per (season, team, head coach), ``role`` = ``"HC"``."""
    df = attach_coaches(plays, coaches)
    if df.height == 0:
        return pl.DataFrame()
    from sportsdataverse.football.tendencies import tendencies

    out = tendencies(df, league=LEAGUE, group_cols=COACH_GROUP, def_group_cols=COACH_DEF_GROUP)
    return out.with_columns(role=pl.lit("HC")).select(
        "season", "pos_team", "coach", "role", pl.exclude("season", "pos_team", "coach", "role")
    )


def coach_careers(season_files: list[Path]) -> pl.DataFrame:
    """Sum every written ``coach_tendencies`` season per coach; rates recomputed.

    ``teams`` lists the franchises coached (first to last season). Careers only
    cover the seasons present on disk, so a partial output root yields partial
    careers -- the build logs which seasons went in.
    """
    frames = [pl.read_parquet(p) for p in season_files]
    frames = [f for f in frames if f.height]
    if not frames:
        return pl.DataFrame()
    from sportsdataverse.football.tendencies import aggregate_tendencies

    careers = aggregate_tendencies(frames, keys=("coach",))
    teams = (
        pl.concat(frames, how="diagonal_relaxed")
        .sort(["season", "pos_team"])
        .group_by("coach", maintain_order=True)
        .agg(
            pl.col("pos_team")
            .drop_nulls()
            .unique(maintain_order=True)
            .str.join(", ")
            .alias("teams")
        )
    )
    careers = careers.join(teams, on="coach", how="left").with_columns(role=pl.lit("HC"))
    front = ["coach", "role", "teams", "seasons", "first_season", "last_season"]
    return careers.select(*front, pl.exclude(front)).sort("plays", descending=True)
