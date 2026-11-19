"""Pre-publish freshness gate: a built ``model_pbp`` season must hold every completed game.

The schedule is nflverse's games file (``sportsdataverse.nfl.load_nfl_schedule``, the same
source the build reads betting lines from); a game is completed when both scores are in.
A season fails when its newest built week is behind the newest completed week, or when a
completed game is missing from the build (which also catches a game count below the
completed count). On 2026-11-19 a reprocess published 2026 with weeks 1-4 while weeks
1-10 were played: the ingest had trusted pre-game shells cached a month earlier.

Calibrated on the 1999-2025 assets published 2026-11-19: every season passes, with game
ids and weeks (POST 18-22) agreeing between build and schedule; the weeks-1-4 2026 build
fails both checks.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

import polars as pl

# Completed in the schedule but with no play data anywhere (CLAUDE.md "Shield thin games").
KNOWN_ABSENT = frozenset({"2000_03_SD_KC", "2000_06_BUF_MIA"})


def season_problems(season: int, built: pl.DataFrame, schedule: pl.DataFrame) -> list[str]:
    """Why ``built`` (one season's model_pbp, ``game_id`` + ``week``) is stale; ``[]`` if fresh."""
    done = schedule.filter(
        (pl.col("season") == season)
        & pl.col("home_score").is_not_null()
        & pl.col("away_score").is_not_null()
        & ~pl.col("game_id").is_in(sorted(KNOWN_ABSENT))
    )
    if done.height == 0:
        return []
    built_week, done_week = built["week"].max(), done["week"].max()
    problems = []
    if built_week is None or built_week < done_week:
        problems.append(
            f"{season}: newest built week {built_week} is behind the newest completed "
            f"week {done_week}"
        )
    missing = sorted(set(done["game_id"].to_list()) - set(built["game_id"].to_list()))
    if missing:
        problems.append(
            f"{season}: built {built['game_id'].n_unique()} games, {len(missing)} of "
            f"{done.height} completed games missing: {', '.join(missing[:8])}"
            + (" ..." if len(missing) > 8 else "")
        )
    return problems


def check_dir(
    parquet_dir: str | Path, schedule_fn: Callable[..., pl.DataFrame] | None = None
) -> list[str]:
    """Gate every ``model_pbp_{season}.parquet`` in ``parquet_dir``; returns the problems."""
    files = sorted(Path(parquet_dir).glob("model_pbp_*.parquet"))
    if not files:
        return [f"no model_pbp_*.parquet in {parquet_dir}"]
    seasons = {int(re.search(r"(\d{4})", f.stem).group(1)): f for f in files}
    if schedule_fn is None:
        from sportsdataverse.nfl import load_nfl_schedule as schedule_fn
    schedule = schedule_fn(seasons=sorted(seasons))
    problems = []
    for season, f in seasons.items():
        problems += season_problems(
            season, pl.read_parquet(f, columns=["game_id", "week"]), schedule
        )
    return problems
