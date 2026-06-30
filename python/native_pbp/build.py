"""End-to-end native PBP build: Shield game payload -> nflverse-shape play frame.

Chains the module pipeline (parse -> description -> features -> labels) into a
single frame carrying the Track 6 ``REQUIRED_COLUMNS`` (and more), reconstructed
entirely from the committed ``nfl/raw`` Shield feed (plus game-level roof /
spread_line / total_line that come from a schedules join).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import polars as pl

from native_pbp.description import add_description_features
from native_pbp.features import add_game_state
from native_pbp.labels import add_labels
from native_pbp.parse import parse_game


def build_pbp(
    game: Dict[str, Any],
    *,
    roof: Optional[str] = None,
    spread_line: Optional[float] = None,
    total_line: Optional[float] = None,
    game_id: Optional[str] = None,
) -> pl.DataFrame:
    """Reconstruct one game's nflverse-shape play-by-play from a Shield payload.

    Args:
        game: A single Shield game object.
        roof: Game roof from a schedules join (the Shield feed omits it).
        spread_line: Closing spread (home-relative) from a schedules join.
        total_line: Game over/under from a schedules join (the Shield feed omits it).
        game_id: Override the nflverse game_id (computed from the payload if None).

    Returns:
        A polars DataFrame, one row per play, with the base nflverse columns
        Track 6 consumes. Empty payloads return a zero-row frame.
    """
    df = parse_game(game, game_id=game_id)
    if df.height == 0:
        return df
    df = add_description_features(df)
    df = add_game_state(df, roof=roof, spread_line=spread_line, total_line=total_line)
    df = add_labels(df, game)
    # Drop TIMEOUT rows (timeouts + two-minute warnings) to match nflverse's row
    # set — done AFTER add_game_state so the timeout cumsum already counted them.
    # fill_null keeps rows whose shield_play_type is null (null != "TIMEOUT" is null
    # in polars and would otherwise be filtered out).
    df = df.filter(pl.col("shield_play_type").fill_null("") != "TIMEOUT")
    return df.drop("_points_home", "_points_away")


def build_pbp_from_file(
    path: str | Path,
    *,
    roof: Optional[str] = None,
    spread_line: Optional[float] = None,
    total_line: Optional[float] = None,
) -> pl.DataFrame:
    """Load a ``nfl/raw/{season}/{game_id}.json`` file and build its PBP frame."""
    path = Path(path)
    game = json.loads(path.read_text(encoding="utf-8"))
    return build_pbp(
        game, roof=roof, spread_line=spread_line, total_line=total_line, game_id=path.stem
    )


def build_season(
    season: int,
    raw_dir: str | Path = "nfl/raw",
    *,
    schedule_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
    game_ids: Optional[List[str]] = None,
) -> pl.DataFrame:
    """Build every game in a season into one concatenated PBP frame.

    Args:
        season: NFL season year.
        raw_dir: Root of the committed per-game library.
        schedule_lookup: Optional ``{game_id: {"roof": ..., "spread_line": ...,
            "total_line": ...}}`` map (from a schedules join) supplying the
            game-level fields the Shield feed omits. Missing games fall back to
            ``roof=None``, ``spread_line=None``, ``total_line=None``.
        game_ids: Optional subset of game_ids to build (default: all in the season).

    Returns:
        Concatenated polars DataFrame across all games (diagonal_relaxed union).
    """
    season_dir = Path(raw_dir) / str(season)
    wanted = set(game_ids) if game_ids is not None else None
    frames: List[pl.DataFrame] = []
    for path in sorted(season_dir.glob(f"{season}_*.json")):
        if wanted is not None and path.stem not in wanted:
            continue
        meta = (schedule_lookup or {}).get(path.stem, {})
        df = build_pbp_from_file(
            path,
            roof=meta.get("roof"),
            spread_line=meta.get("spread_line"),
            total_line=meta.get("total_line"),
        )
        if df.height:
            frames.append(df)
    if not frames:
        return pl.DataFrame()
    return pl.concat(frames, how="diagonal_relaxed")
