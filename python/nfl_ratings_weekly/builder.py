"""Build per-week as-of vintages of the NFL ratings spine for one season."""

from __future__ import annotations

import datetime as dt
import logging
import urllib.error
from typing import Callable, Optional

import polars as pl
from sportsdataverse.errors import NoDataError

log = logging.getLogger(__name__)


def week_starts(schedule: pl.DataFrame) -> list[tuple[int, str]]:
    """``(week, first-kickoff-date)`` per week, ascending.

    All game types are included: NFL week numbering is monotone through the
    postseason (REG 1-18, then WC/DIV/CON/SB continue 19-22), so unlike the
    CFB twin there is no label collision to avoid.

    Args:
        schedule: One season's schedule frame (needs ``week``, ``gameday``).

    Returns:
        Ascending ``(week, YYYY-MM-DD)`` pairs; the date is the earliest
        kickoff of that week — the EXCLUSIVE as-of cutoff.
    """
    g = (
        schedule.select("week", "gameday")
        .drop_nulls()
        .group_by("week")
        .agg(pl.col("gameday").min().alias("cutoff"))
        .sort("week")
    )
    return [(int(w), str(c)[:10]) for w, c in zip(g["week"].to_list(), g["cutoff"].to_list())]


def build_season(
    season: int,
    *,
    ratings_fn: Optional[Callable[..., pl.DataFrame]] = None,
    schedule_fn: Optional[Callable[..., pl.DataFrame]] = None,
) -> pl.DataFrame:
    """Build the season's vintage table: one block per ``as_of_week``.

    For each week ``W`` (in kickoff order) the ratings spine is refit with
    ``as_of_date`` = week ``W``'s first kickoff date, so the emitted block
    contains ONLY information from games strictly before week ``W``
    (EXCLUSIVE — ``nfl_ratings`` filters ``gameday < as_of_date``). Week 1
    yields an empty fit and emits no rows; weeks that fail after retry are
    reported and skipped, never silently absent.

    Args:
        season: The season to build.
        ratings_fn: Injectable ``nfl_ratings`` (hermetic tests).
        schedule_fn: Injectable ``load_nfl_schedule`` (hermetic tests).

    Returns:
        Long frame: the ``nfl_ratings`` columns plus ``as_of_week`` (Int32).
        Empty frame if no week produced rows.
    """
    if ratings_fn is None or schedule_fn is None:
        from sportsdataverse.nfl import load_nfl_schedule, nfl_ratings

        ratings_fn = ratings_fn or nfl_ratings
        schedule_fn = schedule_fn or load_nfl_schedule
    schedule = schedule_fn(seasons=[season])
    frames: list[pl.DataFrame] = []
    built: list[int] = []
    for week, cutoff in week_starts(schedule):
        try:
            d = ratings_fn(season, as_of_date=dt.date.fromisoformat(cutoff))
        except NoDataError as e:
            # The season's pbp asset is not published yet (nflverse creates
            # play_by_play_<season>.parquet at kickoff; the Tuesday cron starts
            # Sep 1). Zero rows before kickoff is the answer, not a failure --
            # and no later week can succeed against the same absent asset.
            log.info("season %s: no published pbp yet (%s) -- skipped", season, e)
            break
        except urllib.error.HTTPError as e:
            # Same condition, different exception. The loader reads the release
            # asset straight into polars, so an absent one surfaces as a raw
            # urllib 404 and never becomes NoDataError -- which is how the first
            # scheduled run (2026-09-01) died on a case this function already
            # handled. The test raised NoDataError, so it passed while
            # production 404'd.
            #
            # ONLY 404/410. A 5xx or a rate-limit is transient, and treating one
            # as "no data" would silently publish an empty ratings week on a
            # green run.
            if e.code not in (404, 410):
                raise
            log.info("season %s: pbp asset absent (HTTP %s) -- skipped", season, e.code)
            break
        if d.height:
            # 1999-2000 pbp carries plays with an empty-string team that survives
            # nfl_ratings' null filter and emits a garbage "" team row — drop it
            d = d.filter(pl.col("team_id") != "")
        if d.height == 0:
            log.info("season %s as_of_week %s: no prior games (skipped)", season, week)
            continue
        frames.append(d.with_columns(as_of_week=pl.lit(week, dtype=pl.Int32)))
        built.append(week)
    log.info("season %s: built %d vintages (weeks %s)", season, len(built), built)
    if not frames:
        return pl.DataFrame()
    return pl.concat(frames, how="diagonal_relaxed")
