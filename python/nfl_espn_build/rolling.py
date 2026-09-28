"""``nfl_rolling_windows``: last-N-events form (``sportsdataverse.rolling_windows``).

Cut from the WRITTEN ``espn_nfl_pbp`` seasons 2002..S (the career history the
baselines need). A scheduled run in CI has only the current season on disk, so
missing history is downloaded from the published tag first.

Game dates come from nfl-raw's ESPN crosswalk (``crosswalk/games.json``, read
through the build's :class:`~nfl_espn_build.ingest.EspnStore`): it indexes every
event the pbp was processed from, so every pbp game has a date. The nflverse
schedule's ``espn`` ids do not -- they miss 11 ESPN regular-season games
(2003-2010) and repeat 23 ids.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import polars as pl

from nfl_espn_build.config import REGISTRY
from nfl_espn_build.ingest import EspnStore, resolve_raw_root
from nfl_espn_build.publish import DEFAULT_REPO
from nfl_espn_build.tendencies import exclude_exhibitions

log = logging.getLogger(__name__)

PBP_FLOOR = 2002


def _pbp_path(season: int, out: str | Path) -> Path:
    spec = REGISTRY["pbp"]
    return Path(out) / spec.dataset / f"{spec.stem}_{season}.parquet"


def fetch_history(seasons: list[int], out: str | Path) -> None:
    """Download every missing season's pbp parquet from the published tag."""
    for s in seasons:
        path = _pbp_path(s, out)
        if path.is_file():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["gh", "release", "download", REGISTRY["pbp"].tag, "-R", DEFAULT_REPO,
             "-p", path.name, "-D", str(path.parent), "--skip-existing"],
            check=False,
        )  # fmt: skip


def game_dates(store: EspnStore) -> pl.DataFrame:
    """``(game_id, game_date)`` for every crosswalked ESPN event.

    ``kickoff_utc`` (``2002-09-06T00:30Z``) is a UTC instant and a night game
    kicks off after midnight UTC, so the date is the America/New_York calendar
    day, as the league lists it.
    """
    rows = store.crosswalk_games()
    return (
        pl.DataFrame(
            {
                "game_id": [r.get("espn_event_id") for r in rows],
                "kickoff_utc": [r.get("kickoff_utc") for r in rows],
            },
            schema={"game_id": pl.Int64, "kickoff_utc": pl.Utf8},
        )
        .select(
            "game_id",
            game_date=pl.col("kickoff_utc")
            .str.to_datetime("%Y-%m-%dT%H:%MZ", time_zone="UTC")
            .dt.convert_time_zone("America/New_York")
            .dt.date(),
        )
        # identical repeats collapse; a conflicting one is left for
        # football_events to refuse
        .unique(maintain_order=True)
    )


def season_frame(
    season: int, out: str | Path, store: EspnStore | None = None, *, pbp_cut: bool = True
) -> pl.DataFrame:
    """Rolling windows for ``season`` over every written pbp season up to it.

    ``store`` is the build's nfl-raw reader (default: the CLI's resolution --
    ``$NFL_RAW_DIR``, the sibling checkout, else HTTP). Empty when ``season``
    has no written pbp.

    ``pbp_cut`` says the same run just wrote ``season``'s pbp (``--dataset all``
    cuts pbp before rolling_windows). Without it the local current-season file
    may be days old -- a rolling-only run once published 2026 cut at a pbp from
    nine days earlier -- so it is replaced from the published tag; if that
    download fails the season is empty and nothing is published.
    """
    from sportsdataverse.rolling_windows import (
        FOOTBALL_PBP_COLUMNS,
        football_events,
        rolling_windows,
    )

    seasons = list(range(PBP_FLOOR, season + 1))
    if not pbp_cut:
        _pbp_path(season, out).unlink(missing_ok=True)
    fetch_history(seasons if not pbp_cut else seasons[:-1], out)
    present = [s for s in seasons if _pbp_path(s, out).is_file()]
    if season not in present:
        return pl.DataFrame()
    if len(present) < len(seasons):
        # every season 2002.. is on the tag, so a gap is a failed download; a
        # short history would publish wrong prev / career baselines
        raise RuntimeError(
            f"rolling_windows {season}: pbp history missing for "
            f"{sorted(set(seasons) - set(present))}; not publishing short baselines"
        )
    cols = [*FOOTBALL_PBP_COLUMNS, "homeTeamId", "awayTeamId"]
    frames = []
    for s in present:
        schema = pl.read_parquet_schema(_pbp_path(s, out))
        frames.append(pl.read_parquet(_pbp_path(s, out), columns=[c for c in cols if c in schema]))
    pbp = pl.concat(frames, how="diagonal_relaxed")
    # 2002-2007 have no passer / rusher ids: the all-null column is written as
    # the Null dtype, which football_events' id guard (int or text) refuses
    pbp = pbp.with_columns(
        pl.col(c).cast(pl.Utf8)
        for c, t in pbp.schema.items()
        if t == pl.Null and c.endswith(("_id", "_name"))
    )
    dates = game_dates(store or EspnStore(resolve_raw_root()))
    return rolling_windows(football_events(exclude_exhibitions(pbp), dates), season)
