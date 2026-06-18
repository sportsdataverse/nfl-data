"""Build SDV-native NFL roster + player datasets and write them to parquet.

Thin orchestration over the ``sportsdataverse.nfl`` builders:

* :func:`build_rosters` -> one ``roster_{season}.parquet`` per season.
* :func:`build_players` -> a single ``players.parquet``.

The heavy lifting (ESPN scraping / crosswalking) lives in
``sportsdataverse.nfl.build_nfl_rosters`` / ``build_nfl_players``; this module
only sequences seasons, materializes frames to disk, and reports row counts so
the CLI can print a one-line summary.
"""
from __future__ import annotations

from pathlib import Path


def build_rosters(seasons: list[int], out_dir) -> list[dict]:
    """Build per-season NFL rosters and write ``roster_{season}.parquet`` files.

    Args:
        seasons: Seasons to build (one parquet per season).
        out_dir: Output directory (created if absent).

    Returns:
        List of ``{"season": int, "rows": int, "path": str}`` dicts, one per
        season, in input order.
    """
    from sportsdataverse.nfl import build_nfl_rosters

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    for season in seasons:
        df = build_nfl_rosters([season])
        path = out_dir / f"roster_{season}.parquet"
        df.write_parquet(path)
        results.append({"season": season, "rows": df.height, "path": str(path)})
        print(f"rosters: season={season} rows={df.height} -> {path}")
    return results


def build_players(out_dir) -> dict:
    """Build the SDV-native NFL player index and write ``players.parquet``.

    Note:
        ``build_nfl_players`` walks ~7,455 ESPN athlete ``$ref`` endpoints
        sequentially, so this is slow (several minutes) by design.

    Args:
        out_dir: Output directory (created if absent).

    Returns:
        ``{"rows": int, "path": str}``.
    """
    from sportsdataverse.nfl import build_nfl_players

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    df = build_nfl_players()
    path = out_dir / "players.parquet"
    df.write_parquet(path)
    print(f"players: rows={df.height} -> {path}")
    return {"rows": df.height, "path": str(path)}
