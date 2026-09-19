"""Run ``NFLPlayProcess`` over a stored game and cache the *final* payload.

``nfl-raw`` is scraping-only, so the processor runs here: the committed ESPN
summary feeds ``espn_nfl_pbp(summary=...)`` and the committed core play items
feed ``play_participants_from_items`` (names resolved from the summary's own
box score, no network). The result is the same shape ``cfbfastR-cfb-raw``
commits as ``cfb/json/final/{game_id}.json`` -- plays, ``advBoxScore``,
drives, box score, header, odds, win probability -- plus the NFL identity
(``season`` / ``season_type`` / ``week`` / ``nflverse_game_id`` /
``shield_game_id``) and the wide ``play_participants`` rows.

Finals are cached gzipped under ``{cache_dir}/{season}/{event_id}.json.gz``
stamped with :func:`nfl_espn_build.config.processing_version`; a stale stamp
(new sdv-py, new ``SCHEMA_REV``) or ``--reprocess`` rebuilds them. Only a
completed game (``status.type.state == "post"``) is cached: a pregame shell or
an in-progress capture would freeze the season's dataset at that state.
"""

from __future__ import annotations

import functools
import gzip
import json
import logging
import multiprocessing as mp
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from nfl_espn_build.config import processing_version
from nfl_espn_build.ingest import EspnStore
from nfl_espn_build.qa import qa_row

log = logging.getLogger(__name__)

#: summary keys carried into the final verbatim (media dropped)
_KEEP = (
    "plays",
    "advBoxScore",
    "drives",
    "boxscore",
    "header",
    "gameInfo",
    "teamInfo",
    "leaders",
    "standings",
    "scoringPlays",
    "pickcenter",
    "winprobability",
    "timeouts",
    "playByPlaySource",
    "homeTeamSpread",
    "gameSpread",
    "gameSpreadAvailable",
    "overUnder",
)


def status_state(summary: dict[str, Any]) -> str | None:
    try:
        return summary["header"]["competitions"][0]["status"]["type"]["state"]
    except (KeyError, IndexError, TypeError):
        return None


def _home_away_ids(summary: dict[str, Any]) -> tuple[int | None, int | None]:
    home = away = None
    try:
        comps = summary["header"]["competitions"][0]["competitors"]
    except (KeyError, IndexError, TypeError):
        return None, None
    for c in comps or []:
        tid = (c.get("team") or {}).get("id")
        if c.get("homeAway") == "home":
            home = int(tid) if tid is not None else None
        elif c.get("homeAway") == "away":
            away = int(tid) if tid is not None else None
    return home, away


@functools.lru_cache(maxsize=4)
def schedule_lines(season: int) -> dict[str, tuple[float | None, float | None]]:
    """``{espn_event_id | nflverse game_id: (spread_line, total_line)}`` from the nflverse schedule.

    ESPN's summary ``pickcenter`` is empty before ~2013 and again for most
    2023-2025 games, and the core odds feed has nothing before the mid-2010s;
    the nflverse schedule carries the closing line back to 1999 (and the ESPN
    event id since 2001). Cached per process (workers are spawned processes).
    ``{}`` when the schedule cannot be read, so a game falls back to its
    summary's pickcenter and then the processor defaults.
    """
    try:
        from sportsdataverse.nfl import load_nfl_schedule

        sched = load_nfl_schedule(seasons=[int(season)])
    except Exception as exc:  # noqa: BLE001 -- network / release availability
        log.warning("season %s: nflverse schedule unavailable (%r); no odds override", season, exc)
        return {}
    out: dict[str, tuple[float | None, float | None]] = {}
    cols = [c for c in ("game_id", "espn", "spread_line", "total_line") if c in sched.columns]
    if {"spread_line", "total_line"} - set(cols):
        return {}
    for row in sched.select(cols).iter_rows(named=True):
        val = (row.get("spread_line"), row.get("total_line"))
        for key in (row.get("game_id"), row.get("espn")):
            if key not in (None, ""):
                out[str(key)] = val
    return out


def odds_override_for(
    season: int, event_id: int, nflverse_game_id: str | None = None
) -> dict[str, Any] | None:
    """The processor's ``odds_override`` for a game, or ``None`` when no line is known.

    nflverse ``spread_line`` is positive when the home team is favored;
    the processor takes the magnitude plus a ``homeFavorite`` flag.
    """
    lines = schedule_lines(int(season))
    hit = lines.get(str(event_id))
    if hit is None and nflverse_game_id:
        hit = lines.get(str(nflverse_game_id))
    if hit is None or hit[0] is None:
        return None
    spread, total = hit
    return {
        "gameSpread": abs(float(spread)),
        "overUnder": float(total) if total is not None else 55.5,
        "homeFavorite": float(spread) > 0,
        "gameSpreadAvailable": True,
    }


def build_final(
    summary: dict[str, Any],
    plays_items: list[dict[str, Any]] | None,
    event_id: int,
    *,
    nflverse_game_id: str | None = None,
    shield_game_id: str | None = None,
    odds_override: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Process one stored game; ``None`` when the game has not completed."""
    if status_state(summary) != "post":
        return None
    from sportsdataverse.football.play_participants import (
        athlete_lookup_from_summary,
        play_participants_from_items,
    )
    from sportsdataverse.nfl import NFLPlayProcess

    parts = play_participants_from_items(
        plays_items or [], event_id, athlete_lookup=athlete_lookup_from_summary(summary)
    )
    proc = NFLPlayProcess(
        gameId=event_id,
        participants=parts if parts.height else None,
        join_participants=False,
        odds_override=odds_override,
    )
    proc.espn_nfl_pbp(summary=summary)
    result = proc.run_processing_pipeline()

    season_block = result.get("season") or {}
    if not isinstance(season_block, dict):
        season_block = {"year": season_block}
    home_id, away_id = _home_away_ids(summary)
    final: dict[str, Any] = {k: result[k] for k in _KEEP if k in result}
    final.update(
        id=int(event_id),
        gameId=int(event_id),
        season=int(season_block.get("year") or summary["header"]["season"]["year"]),
        season_type=int(season_block.get("type") or summary["header"]["season"].get("type") or 2),
        week=result.get("week"),
        homeTeamId=home_id,
        awayTeamId=away_id,
        nflverse_game_id=nflverse_game_id,
        shield_game_id=shield_game_id,
        processing_version=processing_version(),
        odds_source=getattr(proc, "odds_source", None),
        count=len(result.get("plays") or []),
        play_participants=parts.to_dicts() if parts.height else [],
    )
    # the report-only QA verdict rides in the final, so every dataset cut --
    # including a `--no-process` rebuild -- reads it instead of re-validating
    final["qa"] = qa_row(
        proc.plays_frame,
        processing_version=processing_version(),
        summary=final,
        box=final.get("advBoxScore"),
        header=final.get("header"),
    )
    return final


def final_path(cache_dir: str | Path, season: int, event_id: int) -> Path:
    return Path(cache_dir) / str(season) / f"{event_id}.json.gz"


def write_final(path: Path, final: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=6) as fh:
        json.dump(final, fh, separators=(",", ":"), ensure_ascii=False, default=str)
    tmp.replace(path)


def read_final(path: Path) -> dict[str, Any] | None:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def final_is_current(path: Path) -> bool:
    """True when a cached final exists and carries the current processing version."""
    if not path.exists():
        return False
    final = read_final(path)
    return bool(final) and final.get("processing_version") == processing_version()


def summary_has_play_text(summary: dict[str, Any]) -> bool:
    """Whether any drive play carries ``text``: ESPN's oldest games ship stub plays without it.

    ``drives`` is a mapping with ``previous`` (and sometimes ``current``, a
    drive or a list of drives) or, in some captures, a bare list of drives.
    """
    drives = summary.get("drives") or {}
    if isinstance(drives, dict):
        groups: list[Any] = list(drives.get("previous") or [])
        current = drives.get("current")
        groups += current if isinstance(current, list) else ([current] if current else [])
    else:
        groups = list(drives)
    for drive in groups:
        if not isinstance(drive, dict):
            continue
        for play in drive.get("plays") or []:
            if isinstance(play, dict) and play.get("text"):
                return True
    return False


def _process_one(args: tuple[str, int, dict[str, Any], str]) -> tuple[int, str]:
    """Worker: read, process, cache one event. Returns ``(event_id, status)``.

    ``"stub"`` is a completed game whose plays carry no text (all of 2005, the
    2004 Pro Bowl, the 2008 AFC Championship): the processor cannot parse it and
    never will, so it is a warning, not a failure that would hold back the
    season's other games. Any final an older sdv-py left for it is removed so
    the game cannot ride into a cut.
    """
    root, season, ev, cache_dir = args
    store = EspnStore(root)
    event_id = int(ev["espn_event_id"])
    try:
        summary = store.summary(season, event_id)
        if summary is None:
            return event_id, "missing"
        if status_state(summary) == "post" and not summary_has_play_text(summary):
            log.warning("season %s event %s: stub plays (no text); skipped", season, event_id)
            final_path(cache_dir, season, event_id).unlink(missing_ok=True)
            return event_id, "stub"
        final = build_final(
            summary,
            store.plays(season, event_id),
            event_id,
            nflverse_game_id=ev.get("game_id"),
            shield_game_id=ev.get("shield_game_id"),
            odds_override=odds_override_for(season, event_id, ev.get("game_id")),
        )
        if final is None:
            return event_id, "not_final"
        write_final(final_path(cache_dir, season, event_id), final)
        return event_id, "processed"
    except Exception as exc:  # noqa: BLE001 -- one bad game must not sink the season
        log.error("season %s event %s failed: %r", season, event_id, exc)
        return event_id, "failed"


def process_season(
    store: EspnStore,
    season: int,
    cache_dir: str | Path,
    *,
    workers: int = 2,
    reprocess: bool = False,
) -> dict[str, int]:
    """Bring the season's cached finals up to date. Returns a status tally."""
    t0 = time.time()
    events = store.season_events(season)
    todo = [
        ev
        for ev in events
        if reprocess
        or not final_is_current(final_path(cache_dir, season, int(ev["espn_event_id"])))
    ]
    tally = {"listed": len(events), "cached": len(events) - len(todo)}
    if not todo:
        log.info("season %s: %d finals current, nothing to process", season, len(events))
        return tally
    log.info(
        "season %s: processing %d of %d events (workers=%d)",
        season,
        len(todo),
        len(events),
        workers,
    )
    jobs = [(store.root, season, ev, str(cache_dir)) for ev in todo]
    if workers <= 1:
        results = [_process_one(j) for j in jobs]
    else:
        # spawn, never fork: polars + a forked pool deadlocks at 0% CPU
        ctx = mp.get_context("spawn")
        results = []
        with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as pool:
            futs = [pool.submit(_process_one, j) for j in jobs]
            for i, fut in enumerate(as_completed(futs), 1):
                results.append(fut.result())
                if i % 25 == 0 or i == len(futs):
                    log.info(
                        "season %s: %d/%d processed (%.0fs)", season, i, len(futs), time.time() - t0
                    )
    for _, status in results:
        tally[status] = tally.get(status, 0) + 1
    log.info("season %s done in %.0fs: %s", season, time.time() - t0, tally)
    return tally


def load_season_finals(cache_dir: str | Path, season: int) -> list[dict[str, Any]]:
    """Every CURRENT-version cached final of ``season``, oldest event id first.

    A final left behind by an older sdv-py (a game whose reprocess failed) is
    skipped and counted, never mixed into a dataset cut.
    """
    d = Path(cache_dir) / str(season)
    out, stale = [], 0
    for p in sorted(d.glob("*.json.gz")):
        final = read_final(p)
        if not final:
            continue
        if final.get("processing_version") != processing_version():
            stale += 1
            continue
        out.append(final)
    if stale:
        log.warning("season %s: %d stale cached final(s) skipped (reprocess them)", season, stale)
    return out
