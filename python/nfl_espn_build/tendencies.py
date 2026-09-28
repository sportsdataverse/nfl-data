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
* both tendencies datasets carry the game-context splits (``games_{c}``,
  ``wins_{c}`` ...; ``c`` = ``home``, ``away``, ``neutral_site``,
  ``after_bye``, ``opener``, ``one_score_game``) from the same schedule row:
  a neutral site is both teams' and then neither is home or away; after a
  bye = the team's ``*_rest >= 13``; the opener = its first regular-season
  game; one score = final margin <= 8; a win = more points than the opponent
  (a tie is not). There is no NFL ``vs_ranked``.
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
#: ESPN ids of the 32 franchises (1-30, 33 Ravens, 34 Texans). The Pro Bowl is filed
#: under the postseason with non-franchise teams: AFC/NFC (31/32) most years, draft
#: squads such as Team Rice / Team Irvin (35/36) in 2013-2015.
FRANCHISE_TEAM_IDS = frozenset(range(1, 31)) | {33, 34}
TEAM_GROUP = ("season", "pos_team")
COACH_GROUP = ("season", "pos_team", "coach")
COACH_DEF_GROUP = ("season", "def_pos_team", "def_coach")
#: per-side game context, ``home_{c}`` / ``away_{c}`` in the schedule frame
SIDE_CONTEXT = ("after_bye", "opener", "win")
#: the game's own context, shared by both sides
GAME_CONTEXT = ("neutral_site", "one_score_game")
#: the schedule frame per ESPN event: sidelines + game context
COACH_SCHEMA = {
    "game_id": pl.Int64,
    "home_coach": pl.Utf8,
    "away_coach": pl.Utf8,
    **{c: pl.Boolean for c in GAME_CONTEXT},
    **{f"{s}_{c}": pl.Boolean for s in ("home", "away") for c in SIDE_CONTEXT},
}
#: the nflverse schedule columns the frame is built from
SCHEDULE_COLS = {
    "espn",
    "home_coach",
    "away_coach",
    "game_type",
    "week",
    "location",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
    "home_rest",
    "away_rest",
}


def season_plays(finals: list[dict[str, Any]]) -> pl.DataFrame:
    """The season's reshaped plays (the ``pbp`` cut, ids unresolved), regular + postseason only."""
    df = bind_games([RESHAPERS["pbp"](game) for game in finals])
    # the processor stamps `seasonType` on every play and reshape_pbp adds the
    # crosswalk's `season_type`; either one excludes preseason
    col = next((c for c in ("season_type", "seasonType") if c in df.columns), None)
    if df.height and col is not None:
        df = df.filter(pl.col(col).cast(pl.Int64, strict=False).is_in(COUNTED_SEASON_TYPES))
    return exclude_exhibitions(df)


def exclude_exhibitions(df: pl.DataFrame) -> pl.DataFrame:
    """Drop the Pro Bowl: any game with a side that is not one of the 32 franchises."""
    sides = [c for c in ("homeTeamId", "awayTeamId") if c in df.columns]
    if df.height == 0 or not sides:
        return df
    exhibition = pl.any_horizontal(
        [~pl.col(c).cast(pl.Int64, strict=False).is_in(list(FRANCHISE_TEAM_IDS)) for c in sides]
    )
    return df.filter(~exhibition.fill_null(False))


def coach_games(season: int) -> pl.DataFrame:
    """Sidelines and game context per ESPN event id from the nflverse schedule.

    Empty (with the schema) when the schedule cannot be read, so the coach
    datasets come out empty for the season and neither tendencies dataset
    carries context splits, rather than either being wrong.
    """
    try:
        from sportsdataverse.nfl import load_nfl_schedule

        sched = load_nfl_schedule(seasons=[int(season)])
    except Exception as exc:  # noqa: BLE001 -- network / release availability
        log.warning(
            "season %s: nflverse schedule unavailable (%r); no coach attribution or game context",
            season,
            exc,
        )
        return pl.DataFrame(schema=COACH_SCHEMA)
    missing = sorted(SCHEDULE_COLS - set(sched.columns))
    if missing:
        log.warning(
            "season %s: nflverse schedule lacks %s; no coach attribution or game context",
            season,
            missing,
        )
        return pl.DataFrame(schema=COACH_SCHEMA)
    return schedule_context(sched)


def schedule_context(sched: pl.DataFrame) -> pl.DataFrame:
    """The :data:`COACH_SCHEMA` frame from nflverse schedule rows (see the module doc)."""
    reg = pl.col("game_type") == "REG"
    first_week = (
        sched.filter(reg)
        .select("week", team=pl.concat_list("home_team", "away_team"))
        .explode("team")
        .group_by("team")
        .agg(pl.col("week").min())
    )
    for side in ("home", "away"):
        sched = sched.join(
            first_week.rename({"team": f"{side}_team", "week": f"{side}_first_week"}),
            on=f"{side}_team",
            how="left",
        )
    home, away = pl.col("home_score"), pl.col("away_score")
    return (
        sched.select(
            pl.col("espn").cast(pl.Int64, strict=False).alias("game_id"),
            pl.col("home_coach").cast(pl.Utf8),
            pl.col("away_coach").cast(pl.Utf8),
            neutral_site=pl.col("location") == "Neutral",
            one_score_game=(home - away).abs() <= 8,
            **{f"{s}_after_bye": pl.col(f"{s}_rest") >= 13 for s in ("home", "away")},
            **{
                f"{s}_opener": reg & (pl.col("week") == pl.col(f"{s}_first_week"))
                for s in ("home", "away")
            },
            home_win=home > away,
            away_win=away > home,
        )
        .drop_nulls("game_id")
        .unique(subset=["game_id"], keep="first", maintain_order=True)
        .cast(COACH_SCHEMA)
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


def attach_context(plays: pl.DataFrame, games: pl.DataFrame) -> pl.DataFrame:
    """Boolean ``ctx_*`` (the offense's game context) and ``def_ctx_*`` (the defense's).

    ``games`` is :func:`coach_games`' frame. When it is empty (schedule
    unavailable) the plays come back without any ``ctx_*`` column, so
    ``tendencies`` emits no context split. A game missing from the schedule
    keeps its plays with null (never true) context.
    """
    if plays.height == 0 or games.height == 0:
        return plays
    ctx_cols = [*GAME_CONTEXT, *(f"{s}_{c}" for s in ("home", "away") for c in SIDE_CONTEXT)]
    # prefixed so a same-named pbp column can never shadow the schedule's
    g = games.select(pl.col("game_id").cast(pl.Int64), pl.col(ctx_cols).name.prefix("_sched_"))
    df = plays.with_columns(pl.col("game_id").cast(pl.Int64))
    assert df.schema["game_id"] == g.schema["game_id"]
    unmatched = df.join(g, on="game_id", how="anti")["game_id"].n_unique()
    if unmatched:
        log.warning("%d game(s) not in the nflverse schedule; no game context", unmatched)
    df = df.join(g, on="game_id", how="left")
    home = pl.col("pos_team").cast(pl.Int64, strict=False) == pl.col("homeTeamId").cast(
        pl.Int64, strict=False
    )
    neutral = pl.col("_sched_neutral_site")

    def side(prefix: str, is_home: pl.Expr) -> dict[str, pl.Expr]:
        return {
            f"{prefix}home": is_home & ~neutral,
            f"{prefix}away": ~is_home & ~neutral,
            **{f"{prefix}{c}": pl.col(f"_sched_{c}") for c in GAME_CONTEXT},
            **{
                f"{prefix}{c}": pl.when(is_home)
                .then(pl.col(f"_sched_home_{c}"))
                .otherwise(pl.col(f"_sched_away_{c}"))
                for c in SIDE_CONTEXT
            },
        }

    return df.with_columns(**side("ctx_", home), **side("def_ctx_", ~home)).drop(
        [f"_sched_{c}" for c in ctx_cols]
    )


def team_tendencies(plays: pl.DataFrame, games: pl.DataFrame) -> pl.DataFrame:
    """One row per (season, team); ``games`` is :func:`coach_games`' frame."""
    if plays.height == 0:
        return pl.DataFrame()
    from sportsdataverse.football.tendencies import tendencies

    return tendencies(attach_context(plays, games), league=LEAGUE, group_cols=TEAM_GROUP)


def coach_tendencies(plays: pl.DataFrame, coaches: pl.DataFrame) -> pl.DataFrame:
    """One row per (season, team, head coach), ``role`` = ``"HC"``."""
    df = attach_context(attach_coaches(plays, coaches), coaches)
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
