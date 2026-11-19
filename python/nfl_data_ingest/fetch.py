"""URL-ingest layer: fetch nfl-raw committed JSON from GitHub into a local cache.

RAW_BASE points at the sportsdataverse/nfl-raw repo's committed per-game JSON.
Only a FINAL game's JSON is immutable, so only a cached final (``summary.phase``
``FINAL`` / ``FINAL_OVERTIME``) is a cache hit; anything else is re-fetched. nfl-raw
commits a file for every scheduled game, and an unplayed one is a pre-game shell
(``summary`` null, no ``driveChart``) that is never written to the cache. The
top-level ``status`` reads ``"SCHEDULED"`` on finals too, so it is not a signal.
On 2026-11-19 a reprocess trusted 207 shells cached on 2026-10-09 and published
2026 with weeks 1-4 only.

HTTP is handled by a pooled requests.Session with exponential-backoff retry so
callers never need to manage connection pooling themselves.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RAW_BASE: str = "https://raw.githubusercontent.com/sportsdataverse/nfl-raw/main/nfl"
_GITHUB_API_BASE: str = "https://api.github.com/repos/sportsdataverse/nfl-raw/contents/nfl"
_DEFAULT_TIMEOUT: int = 30
_MAX_RETRIES: int = 3
_BACKOFF_FACTOR: float = 1.0


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

def _make_session() -> requests.Session:
    """Return a pooled Session with exponential-backoff retry."""
    session = requests.Session()
    retry = Retry(
        total=_MAX_RETRIES,
        backoff_factor=_BACKOFF_FACTOR,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _api_headers() -> dict[str, str]:
    """Auth header for the GitHub REST API (an anonymous runner gets 60 requests/h per IP)."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


def is_final_game(game: object) -> bool:
    """True for a played game's JSON: ``summary.phase`` is ``FINAL`` or ``FINAL_OVERTIME``."""
    summary = game.get("summary") if isinstance(game, dict) else None
    return isinstance(summary, dict) and str(summary.get("phase") or "").startswith("FINAL")


def _cached_final(path: Path) -> bool:
    try:
        return is_final_game(json.loads(path.read_bytes()))
    except ValueError:  # truncated / corrupt cache file
        return False


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def raw_url(season: int, game_id: str) -> str:
    """Return the raw-content URL for a single game JSON file.

    Args:
        season: NFL season year (e.g. 2024).
        game_id: Canonical game identifier (e.g. ``"2024_01_BAL_KC"``).

    Returns:
        Full URL string pointing at the committed JSON on GitHub.
    """
    return f"{RAW_BASE}/raw/{season}/{game_id}.json"


# ---------------------------------------------------------------------------
# fetch_game
# ---------------------------------------------------------------------------

def fetch_game(
    season: int,
    game_id: str,
    cache_dir: Path | str = ".cache/nfl_raw",
    *,
    session: Optional[requests.Session] = None,
    force: bool = False,
) -> Optional[Path]:
    """Fetch a single game's JSON from nfl-raw and write it to the cache.

    A cached FINAL game is returned immediately unless *force* is ``True``; any other
    cached file (a pre-game shell, an in-progress game) is re-fetched. A pre-game shell
    (no ``summary``) is not written, and a stale cached copy of it is removed.

    Args:
        season: NFL season year.
        game_id: Canonical game identifier (e.g. ``"2024_01_BAL_KC"``).
        cache_dir: Root cache directory.  Season sub-directories are created
            automatically.
        session: Optional pre-built ``requests.Session``.  A default pooled
            session with retry is created when omitted.
        force: When ``True``, re-fetch even if the cached file already exists.

    Returns:
        :class:`pathlib.Path` to the written (or existing) cache file, or ``None``
        for a game not played yet.
    """
    cache_dir = Path(cache_dir)
    dest = cache_dir / str(season) / f"{game_id}.json"

    if dest.exists() and not force:
        if _cached_final(dest):
            logger.debug("cache hit: %s", dest)
            return dest
        logger.debug("cached %s is not a final game, re-fetching", dest)

    _session = session or _make_session()
    url = raw_url(season, game_id)
    logger.debug("fetching %s", url)

    resp = _session.get(url, timeout=_DEFAULT_TIMEOUT)
    resp.raise_for_status()
    game = json.loads(resp.content)
    if not (isinstance(game, dict) and game.get("summary")):
        # an unplayed game's shell: nothing to build, and caching it hid every later week
        dest.unlink(missing_ok=True)
        logger.debug("not played yet, not cached: %s", game_id)
        return None

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    logger.debug("written %s (%d bytes)", dest, len(resp.content))
    return dest


# ---------------------------------------------------------------------------
# enumerate_game_ids
# ---------------------------------------------------------------------------

def enumerate_game_ids(
    season: int,
    *,
    session: Optional[requests.Session] = None,
    game_ids: Optional[list[str]] = None,
) -> list[str]:
    """Return the list of game IDs available for *season*.

    Queries the GitHub Contents API to list ``nfl/raw/{season}/`` and strips
    the ``.json`` extension from each file name.  When *game_ids* is provided
    the API call is skipped and the supplied list is returned as-is (useful for
    tests and targeted re-ingests).

    Args:
        season: NFL season year.
        session: Optional ``requests.Session``.
        game_ids: Explicit list of game IDs to use instead of querying GitHub.

    Returns:
        Sorted list of game-ID strings (no ``.json`` extension).
    """
    if game_ids is not None:
        return list(game_ids)

    _session = session or _make_session()
    url = f"{_GITHUB_API_BASE}/raw/{season}"
    logger.debug("listing season %d from %s", season, url)

    resp = _session.get(url, timeout=_DEFAULT_TIMEOUT, headers=_api_headers())
    resp.raise_for_status()

    entries: list[dict] = resp.json()
    ids = sorted(
        e["name"][:-5]  # strip ".json"
        for e in entries
        if isinstance(e, dict)
        and e.get("type") == "file"
        and e.get("name", "").endswith(".json")
    )
    return ids


# ---------------------------------------------------------------------------
# ingest_season
# ---------------------------------------------------------------------------

def ingest_season(
    season: int,
    cache_dir: Path | str = ".cache/nfl_raw",
    *,
    session: Optional[requests.Session] = None,
    game_ids: Optional[list[str]] = None,
    force: bool = False,
) -> Path:
    """Fetch all games for *season* into the local cache.

    Enumerates game IDs via :func:`enumerate_game_ids` (or uses the supplied
    *game_ids* list), then fetches each one with :func:`fetch_game`.  Already-
    cached files are skipped unless *force* is ``True``.

    Args:
        season: NFL season year.
        cache_dir: Root cache directory.
        session: Optional ``requests.Session`` shared across all fetches.
        game_ids: Explicit list of game IDs; bypasses the GitHub API listing.
        force: Re-fetch even if cached files exist.

    Returns:
        :class:`pathlib.Path` to the cache root so callers can pass it directly
        to ``native_pbp.build.build_season(raw_dir=<cache>)``.
    """
    cache_dir = Path(cache_dir)
    _session = session or _make_session()

    ids = enumerate_game_ids(season, session=_session, game_ids=game_ids)
    logger.info("ingesting %d games for season %d", len(ids), season)

    unplayed = sum(
        fetch_game(season, gid, cache_dir=cache_dir, session=_session, force=force) is None
        for gid in ids
    )
    if unplayed:
        logger.info("season %d: %d game(s) not played yet, not cached", season, unplayed)

    return cache_dir
