"""Raw NFL API JSON file library builder.

Fetches per-week game detail payloads from ``api.nfl.com`` and stores them as
JSON files on disk, one file per week per season/type combination.

Storage layout::

    {output_dir}/{season}/{season_type}/wk{week:02d}.json

Each file contains the raw list (or dict) returned by the
``/football/v2/experience/weekly-game-details`` endpoint, exactly as received
from the NFL Shield API.  Downstream tools can read these files via
:func:`load_weekly_raw` without re-hitting the network.

Usage::

    from pathlib import Path
    from model_training.play_level.fetcher import build_raw_library

    paths = build_raw_library(
        seasons=list(range(2012, 2025)),
        output_dir=Path("data/raw"),
        season_types=["REG", "POST"],
        resume=True,
    )
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import List, Union


# ---------------------------------------------------------------------------
# Thin network wrappers — monkeypatched in tests
# ---------------------------------------------------------------------------

def _list_weeks(season: int, season_type: str, headers: dict | None = None) -> dict:
    """Return raw JSON from ``nfl_weeks`` (the NFL Shield week calendar)."""
    from sportsdataverse.nfl.nfl_api import nfl_weeks
    return nfl_weeks(season=season, season_type=season_type, return_parsed=False, headers=headers)


def _fetch_weekly_details(
    season: int,
    season_type: str,
    week: int,
    headers: dict | None = None,
) -> Union[list, dict]:
    """Return raw JSON from ``nfl_weekly_game_details`` (bare list or dict)."""
    from sportsdataverse.nfl.nfl_api import nfl_weekly_game_details
    return nfl_weekly_game_details(
        season=season,
        season_type=season_type,
        week=week,
        include_drive_chart=True,
        return_parsed=False,
        headers=headers,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_season_weeks(
    season: int,
    season_type: str = "REG",
    headers: dict | None = None,
) -> list[int]:
    """Return sorted week numbers for a season / type via the NFL API.

    Args:
        season: NFL season year (e.g. ``2024``).
        season_type: ``"REG"`` (regular season) or ``"POST"`` (postseason).
        headers: Pre-minted auth headers from ``nfl_headers_gen()``.
            A fresh token is minted automatically when ``None``.

    Returns:
        Sorted list of integer week numbers (e.g. ``[1, 2, ..., 18]``).
    """
    raw = _list_weeks(season, season_type, headers=headers)
    weeks_list = raw.get("weeks", []) or []
    week_nums: list[int] = []
    for wk in weeks_list:
        val = wk.get("week")
        if val is not None:
            try:
                week_nums.append(int(val))
            except (TypeError, ValueError):
                pass
    return sorted(week_nums)


def extract_game_ids_from_weekly(payload: Union[list, dict]) -> list[str]:
    """Extract game ID strings from a ``nfl_weekly_game_details`` raw payload.

    The endpoint returns either a bare ``list`` of game objects or a dict with a
    ``games``/``data`` key.  Each game object is checked for an ``id``,
    ``nflId``, or ``gameId`` field (in that priority order).

    Args:
        payload: Raw return value from ``nfl_weekly_game_details``.

    Returns:
        List of game ID strings; objects with no identifiable ID are skipped.
    """
    if isinstance(payload, list):
        games = payload
    else:
        games = payload.get("games", []) or payload.get("data", []) or []

    ids: list[str] = []
    for game in games:
        for field in ("id", "nflId", "gameId"):
            val = game.get(field)
            if val is not None:
                ids.append(str(val))
                break
    return ids


def build_raw_library(
    seasons: List[int],
    output_dir: Path = Path("data/raw"),
    *,
    season_types: List[str] = ("REG", "POST"),
    resume: bool = True,
    headers: dict | None = None,
    delay_s: float = 0.0,
) -> list[Path]:
    """Download and store weekly NFL game details JSON for the given seasons.

    For each (season, season_type, week) tuple, fetches the raw payload from
    ``api.nfl.com/football/v2/experience/weekly-game-details`` and writes it to
    ``{output_dir}/{season}/{season_type}/wk{week:02d}.json``.  When
    ``resume=True`` (default) an existing file is left untouched.

    Args:
        seasons: List of NFL season years to fetch (e.g. ``list(range(2012, 2025))``).
        output_dir: Root directory for the raw JSON library.
        season_types: Season type codes to fetch for each year.
            Defaults to ``("REG", "POST")``.
        resume: Skip weeks whose JSON file already exists on disk when ``True``.
        headers: Pre-minted auth headers to reuse across all requests.
            A fresh anonymous ``WEB_DESKTOP`` token is minted when ``None``.
        delay_s: Seconds to sleep after each network request (both the
            week-calendar lookup and each weekly-details fetch). Use a small
            positive value (e.g. ``2.0``) to throttle a sequential pull and stay
            polite to ``api.nfl.com``. A skipped (already-on-disk) week does not
            trigger a sleep, so resumed runs aren't penalized. Defaults to ``0.0``
            (no throttle).

    Returns:
        List of :class:`pathlib.Path` objects for each file written this run
        (already-present files skipped under ``resume=True`` are excluded).

    Example:
        Quick start (all regular-season weeks, 2020–2024)::

            from pathlib import Path
            from model_training.play_level.fetcher import build_raw_library

            paths = build_raw_library(
                seasons=list(range(2020, 2025)),
                output_dir=Path("data/raw"),
                season_types=["REG"],
            )
            print(f"Wrote {len(paths)} weekly files")

        Throttled sequential pull (2s between requests)::

            paths = build_raw_library(
                seasons=[2025],
                output_dir=Path("data/raw"),
                delay_s=2.0,
            )
    """
    output_dir = Path(output_dir)
    written: list[Path] = []

    for season in seasons:
        for stype in list(season_types):
            week_nums = list_season_weeks(season, stype, headers=headers)
            if delay_s > 0:
                time.sleep(delay_s)
            if not week_nums:
                continue
            season_dir = output_dir / str(season) / stype
            season_dir.mkdir(parents=True, exist_ok=True)

            for week in week_nums:
                out = season_dir / f"wk{week:02d}.json"
                if resume and out.exists():
                    continue
                payload = _fetch_weekly_details(season, stype, week, headers=headers)
                out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                print(f"[fetcher] {season}/{stype} wk{week:02d} -> {out}")
                written.append(out)
                if delay_s > 0:
                    time.sleep(delay_s)

    return written


# ---------------------------------------------------------------------------
# Read-back helpers
# ---------------------------------------------------------------------------

def load_weekly_raw(path: Path) -> Union[list, dict]:
    """Load a stored weekly JSON file from disk.

    Args:
        path: Path to a ``wk{NN}.json`` file written by :func:`build_raw_library`.

    Returns:
        The parsed JSON value (bare list or dict, matching what the API returned).

    Raises:
        FileNotFoundError: When ``path`` does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Weekly raw file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_library_files(
    season: int,
    season_type: str,
    data_dir: Path = Path("data/raw"),
) -> list[Path]:
    """List all stored weekly JSON files for a season/type, sorted by week.

    Args:
        season: NFL season year.
        season_type: ``"REG"`` or ``"POST"``.
        data_dir: Root directory of the raw JSON library.

    Returns:
        Sorted list of :class:`pathlib.Path` objects for each ``wk*.json`` file
        found.  Returns an empty list when the directory does not exist or
        contains no matching files.
    """
    week_dir = Path(data_dir) / str(season) / season_type
    if not week_dir.is_dir():
        return []
    return sorted(week_dir.glob("wk*.json"))


# ---------------------------------------------------------------------------
# Per-game extraction (nflverse-style game_id naming)
# ---------------------------------------------------------------------------

# Data availability floors on api.nfl.com weekly-game-details:
#   * NFL_JSON_SCHEDULE_START -- schedule/game shells (teams, dates, scores) reach
#     back to the league's founding (1920). These carry no per-play detail
#     (``summary`` / ``driveChart`` are empty).
#   * NFL_JSON_DETAIL_START -- full play-by-play detail (``summary`` + ``driveChart``)
#     is reliably populated from 1999 onward (the nflverse / nflfastR era). 1997 is
#     spottily present; 1998 and earlier are shells only.
NFL_JSON_SCHEDULE_START = 1920
NFL_JSON_DETAIL_START = 1999

# NFL Shield club abbreviations that differ from the nflverse game_id convention.
# The Shield API exposes each club's abbreviation as the trailing path segment of
# its ``currentLogo`` URL (e.g. ``.../clubs/logos/PHI``). All 32 current clubs match
# nflverse except Arizona, which the league renders as ``AZ`` but nflverse spells
# ``ARI``. The Rams already render as ``LA`` (matching nflverse), not ``LAR``.
_NFLVERSE_ABBR_FIXUPS = {"AZ": "ARI"}

# ``currentLogo`` always yields a club's *present-day* abbreviation, so franchises
# that relocated inside the detail era need a season-aware fixup to match nflverse's
# historical game_ids. Map: modern abbr -> (last season under the OLD abbr, old abbr).
# A game in season <= cutoff uses the old abbr.
_RELOCATIONS = {
    "LA": (2015, "STL"),   # Rams: St. Louis through 2015, Los Angeles from 2016
    "LAC": (2016, "SD"),   # Chargers: San Diego through 2016, Los Angeles from 2017
    "LV": (2019, "OAK"),   # Raiders: Oakland through 2019, Las Vegas from 2020
}


def _team_abbr(team: dict) -> str:
    """Return a club's *present-day* abbreviation from a Shield team object.

    Reads the trailing path segment of ``team["currentLogo"]`` (e.g.
    ``.../clubs/logos/PHI`` -> ``"PHI"``). This is the modern abbreviation; apply
    :func:`_nflverse_abbr` to normalize it to the nflverse convention for a season.

    Args:
        team: A Shield ``homeTeam`` / ``awayTeam`` object (must carry
            ``currentLogo``).

    Returns:
        The raw modern club abbreviation (e.g. ``"PHI"``, ``"AZ"``, ``"LA"``).

    Raises:
        ValueError: When no abbreviation can be derived (missing/empty
            ``currentLogo``).
    """
    raw = (team.get("currentLogo") or "").rstrip("/").rsplit("/", 1)[-1].strip()
    if not raw:
        raise ValueError(f"Cannot derive team abbreviation from team object: {team!r}")
    return raw


def _nflverse_abbr(raw: str, season: int) -> str:
    """Normalize a modern club abbreviation to nflverse's for a given season.

    Applies the season-independent rename (``AZ`` -> ``ARI``) and then the
    season-aware relocation fixup (e.g. the Rams are ``STL`` through 2015 and
    ``LA`` from 2016; Chargers ``SD`` <= 2016; Raiders ``OAK`` <= 2019).

    Args:
        raw: The present-day abbreviation from :func:`_team_abbr`.
        season: NFL season year (used to pick the era-correct abbreviation).

    Returns:
        The nflverse club abbreviation for that season.
    """
    abbr = _NFLVERSE_ABBR_FIXUPS.get(raw, raw)
    reloc = _RELOCATIONS.get(abbr)
    if reloc is not None and season <= reloc[0]:
        return reloc[1]
    return abbr


def nflverse_game_id(game: dict, reg_weeks: int = 18) -> str:
    """Build the nflverse ``game_id`` (``{season}_{week:02d}_{away}_{home}``).

    Regular-season games keep their API week number. Postseason games continue
    the numbering past the regular season, matching nflverse: with ``reg_weeks=18``
    (the 2021+ schedule), Wild Card -> 19, Divisional -> 20, Conference -> 21,
    Super Bowl -> 22; with ``reg_weeks=17`` (1999-2020) those become 18-21.
    Team abbreviations are normalized to nflverse via :func:`_nflverse_abbr`,
    including season-aware relocation fixups (``LA`` -> ``STL`` for the pre-2016
    Rams, etc.).

    Args:
        game: A Shield game object (carrying ``season``, ``week``,
            ``seasonType``, ``homeTeam``, ``awayTeam``).
        reg_weeks: Number of regular-season weeks for the season, used as the
            postseason offset. ``17`` for 1999-2020, ``18`` for 2021+.

    Returns:
        The nflverse game_id string, e.g. ``"2025_01_DAL_PHI"``,
        ``"2025_19_LA_CAR"`` (Wild Card), or ``"2010_01_ARI_STL"`` (pre-relocation).
    """
    season = int(game["season"])
    api_week = int(game["week"])
    season_type = game.get("seasonType", "REG")
    week = api_week if season_type == "REG" else reg_weeks + api_week
    away = _nflverse_abbr(_team_abbr(game["awayTeam"]), season)
    home = _nflverse_abbr(_team_abbr(game["homeTeam"]), season)
    return f"{season}_{week:02d}_{away}_{home}"


def _detect_reg_weeks(season: int, data_dir: Path, season_types: List[str]) -> int:
    """Return the max REG week present on disk for a season (postseason offset).

    Falls back to ``18`` when no REG library files are found, so the modern
    (2021+) postseason offset is used by default.
    """
    if "REG" not in [s.upper() for s in season_types]:
        return 18
    weeks: list[int] = []
    for path in list_library_files(season, "REG", data_dir=data_dir):
        payload = load_weekly_raw(path)
        games = payload if isinstance(payload, list) else (
            payload.get("games") or payload.get("data") or []
        )
        for game in games:
            try:
                weeks.append(int(game["week"]))
            except (KeyError, TypeError, ValueError):
                pass
    return max(weeks) if weeks else 18


def extract_library_to_games(
    season: int,
    data_dir: Path = Path("data/raw"),
    output_dir: Path = Path("nfl/raw"),
    *,
    season_types: List[str] = ("REG", "POST"),
) -> list[Path]:
    """Split weekly library payloads into per-game nflverse-named JSON files.

    Reads every ``{data_dir}/{season}/{season_type}/wk*.json`` weekly payload,
    unpacks each game object, and writes it to
    ``{output_dir}/{season}/{nflverse_game_id}.json`` (one file per game). The
    postseason week offset is auto-detected from the regular-season payloads via
    :func:`_detect_reg_weeks`.

    Args:
        season: NFL season year (e.g. ``2025``).
        data_dir: Root of the weekly raw library (``build_raw_library`` output).
        output_dir: Root of the per-game library to write. Files land under
            ``{output_dir}/{season}/``.
        season_types: Season type codes to process. Defaults to
            ``("REG", "POST")``.

    Returns:
        Sorted list of :class:`pathlib.Path` objects for every per-game file
        written.

    Raises:
        ValueError: When two games resolve to the same nflverse game_id (should
            never happen for real NFL schedules — surfaces a data defect).

    Example:
        Extract a fetched season into the committed per-game library::

            from pathlib import Path
            from model_training.play_level.fetcher import (
                extract_library_to_games,
            )

            paths = extract_library_to_games(2025)
            print(f"Wrote {len(paths)} per-game files")
    """
    data_dir = Path(data_dir)
    season_dir = Path(output_dir) / str(season)
    season_dir.mkdir(parents=True, exist_ok=True)
    reg_weeks = _detect_reg_weeks(season, data_dir, list(season_types))

    written: dict[str, Path] = {}
    for season_type in list(season_types):
        for week_path in list_library_files(season, season_type, data_dir=data_dir):
            payload = load_weekly_raw(week_path)
            games = payload if isinstance(payload, list) else (
                payload.get("games") or payload.get("data") or []
            )
            for game in games:
                gid = nflverse_game_id(game, reg_weeks=reg_weeks)
                if gid in written:
                    raise ValueError(
                        f"Duplicate nflverse game_id {gid!r} "
                        f"(already wrote {written[gid]}); possible schedule defect."
                    )
                out = season_dir / f"{gid}.json"
                out.write_text(json.dumps(game, indent=2), encoding="utf-8")
                written[gid] = out

    return sorted(written.values())
