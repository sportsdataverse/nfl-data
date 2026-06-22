"""Build SDV-native NFL roster + player + player-stats datasets and write parquet.

Thin orchestration over the ``sportsdataverse.nfl`` builders:

* :func:`build_rosters` -> one ``roster_{season}.parquet`` per season.
* :func:`build_players` -> a single ``players.parquet``.
* :func:`build_player_stats` -> a single ``player_stats.parquet`` (all seasons
  stacked, week-level).

The heavy lifting (ESPN scraping / crosswalking / PBP aggregation) lives in
``sportsdataverse.nfl.build_nfl_rosters`` / ``build_nfl_players`` /
``build_nfl_player_stats``; this module only sequences seasons, materializes
frames to disk, and reports row counts so the CLI can print a one-line summary.
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


def build_player_stats(
    seasons: list[int],
    out_dir,
    *,
    season_type: str = "REG+POST",
) -> dict:
    """Build the SDV-native NFL player-stats table and write ``player_stats.parquet``.

    Mirrors nflverse ``player_stats`` (one combined week-level parquet covering
    all seasons, offense). Each season is aggregated independently with
    :func:`sportsdataverse.nfl.build_nfl_player_stats` (``summary_level="week"``)
    and the per-season week-level frames are stacked into one parquet.

    Aggregating per-season (rather than passing the full range in one call)
    avoids a raw play-by-play schema-drift edge: the SDV-native ``nfl_model_pbp``
    release has a one-column width difference across some seasons, which trips
    ``load_nfl_pbp``'s vertical concat when many seasons are read at once. The
    aggregated week-level output, by contrast, has a stable schema, so the
    per-season frames concat cleanly (``diagonal_relaxed`` tolerates any residual
    column-set drift across eras).

    Args:
        seasons: Seasons to aggregate (stacked into one parquet).
        out_dir: Output directory (created if absent).
        season_type: Passed through to ``build_nfl_player_stats``. Defaults to
            ``"REG+POST"`` to match nflverse week-level coverage.

    Returns:
        ``{"rows": int, "seasons": list[int], "path": str}``.
    """
    import polars as pl

    from sportsdataverse.nfl import build_nfl_player_stats

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    frames: list[pl.DataFrame] = []
    for season in seasons:
        sdf = build_nfl_player_stats(
            [season],
            summary_level="week",
            season_type=season_type,
        )
        print(f"player_stats: season={season} rows={sdf.height}")
        frames.append(sdf)
    df = pl.concat(frames, how="diagonal_relaxed")
    path = out_dir / "player_stats.parquet"
    df.write_parquet(path)
    print(
        f"player_stats: seasons={min(seasons)}-{max(seasons)} "
        f"rows={df.height} -> {path}"
    )
    return {"rows": df.height, "seasons": list(seasons), "path": str(path)}
