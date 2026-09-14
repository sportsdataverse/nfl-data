"""Read the ESPN game library ``nfl-raw`` commits under ``nfl/espn/``.

Two sources, one interface (:class:`EspnStore`):

* a local checkout of ``sportsdataverse/nfl-raw`` (the droplet; ``--raw-dir``
  or ``NFL_RAW_DIR``, default the sibling ``../nfl-raw``), or
* ``raw.githubusercontent.com`` (CI, which never checks out the multi-GB raw
  repo -- the same pattern as :mod:`nfl_data_ingest.fetch`).

Files are the gzipped JSON ``nfl-raw`` writes: ``raw/{season}/{event_id}.json.gz``
(the ESPN summary) and ``plays/{season}/{event_id}.json.gz`` (core play
participants). The crosswalk ``crosswalk/games.json`` is the season index --
every captured event with its nflverse ``game_id`` and Shield uuid -- so a
season enumerates identically over HTTP and on disk.
"""

from __future__ import annotations

import gzip
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)

RAW_BASE = "https://raw.githubusercontent.com/sportsdataverse/nfl-raw/main/nfl/espn"
_TIMEOUT = 60


def _session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=4,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def resolve_raw_root(raw_dir: str | os.PathLike | None = None) -> str:
    """The ``nfl/espn`` root to read: an explicit dir, ``$NFL_RAW_DIR``, the sibling checkout, else HTTP.

    A directory argument may be the nfl-raw repo root or its ``nfl/espn``
    subtree; both resolve to the subtree.
    """
    cand = raw_dir or os.environ.get("NFL_RAW_DIR")
    if cand is None:
        here = Path(__file__).resolve()
        cand = here.parents[2].parent / "nfl-raw"
        if not cand.exists():
            return RAW_BASE
    p = Path(cand)
    if (p / "nfl" / "espn").is_dir():
        return str(p / "nfl" / "espn")
    if p.is_dir():
        return str(p)
    if str(cand).startswith("http"):
        return str(cand).rstrip("/")
    raise FileNotFoundError(f"ESPN raw root not found: {cand}")


@dataclass(frozen=True)
class EspnStore:
    """Reader over ``nfl/espn`` at ``root`` (a directory or an ``https://`` prefix)."""

    root: str

    @property
    def is_http(self) -> bool:
        return self.root.startswith("http")

    def _read(self, rel: str) -> dict[str, Any] | list | None:
        """Parse ``{root}/{rel}`` (gzip-aware); ``None`` when the file is absent."""
        if self.is_http:
            r = _session().get(f"{self.root}/{rel}", timeout=_TIMEOUT)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            body = r.content
            if rel.endswith(".gz"):
                body = gzip.decompress(body)
            return json.loads(body.decode("utf-8"))
        p = Path(self.root) / rel
        if not p.exists():
            return None
        if rel.endswith(".gz"):
            with gzip.open(p, "rt", encoding="utf-8") as fh:
                return json.load(fh)
        return json.loads(p.read_text(encoding="utf-8"))

    def crosswalk_games(self) -> list[dict[str, Any]]:
        rows = self._read("crosswalk/games.json")
        return list(rows) if isinstance(rows, list) else []

    def season_events(self, season: int) -> list[dict[str, Any]]:
        """Every captured event of ``season`` from the crosswalk, oldest first.

        Falls back to listing the local ``raw/{season}`` directory when the
        crosswalk has no rows for the season (a capture not yet crosswalked).
        """
        rows = [g for g in self.crosswalk_games() if int(g.get("season") or 0) == int(season)]
        if not rows and not self.is_http:
            d = Path(self.root) / "raw" / str(season)
            rows = [
                {"espn_event_id": int(p.name.split(".")[0]), "season": int(season)}
                for p in sorted(d.glob("*.json.gz"))
            ]
        rows.sort(key=lambda g: (g.get("week") or 0, g.get("kickoff_utc") or "", g["espn_event_id"]))
        return rows

    def summary(self, season: int, event_id: int) -> dict[str, Any] | None:
        return self._read(f"raw/{season}/{event_id}.json.gz")  # type: ignore[return-value]

    def plays(self, season: int, event_id: int) -> list[dict[str, Any]]:
        body = self._read(f"plays/{season}/{event_id}.json.gz")
        return list((body or {}).get("items") or []) if isinstance(body, dict) else []
