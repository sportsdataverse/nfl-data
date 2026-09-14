"""Generic JSON-block -> tidy frame reshape (the cfb-data primitives, NFL identity).

Same cell rules as ``cfb_data_build.reshape`` so the two families' parquet
share one convention: ``null``/``[]`` -> null, a length-1 list unboxes, any
surviving list/dict is JSON-encoded to a string, scalars pass through.
Identity is stamped at the FRAME level after the row union: ``game_id`` (the
ESPN event id, matching the cfb family), ``season``, ``week``, and the NFL
extras ``season_type`` and ``nflverse_game_id`` when the final carries them.
"""

from __future__ import annotations

import json
from typing import Any

import polars as pl


def _norm_cell(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, list):
        if len(v) == 0:
            return None
        if len(v) == 1:
            v = v[0]
    if isinstance(v, (list, dict)):
        return json.dumps(v, separators=(",", ":"), ensure_ascii=False, default=str)
    return v


def stamp_identity(df: pl.DataFrame, game: dict[str, Any], *, week: bool = True) -> pl.DataFrame:
    """Overwrite/append the game identity columns; empty frames pass through."""
    if df.height == 0:
        return df
    cols: dict[str, pl.Expr] = {
        "game_id": pl.lit(int(game["id"]), dtype=pl.Int64),
        "season": pl.lit(int(game["season"]), dtype=pl.Int64),
    }
    if week and game.get("week") is not None:
        cols["week"] = pl.lit(int(game["week"]), dtype=pl.Int64)
    if game.get("season_type") is not None:
        cols["season_type"] = pl.lit(int(game["season_type"]), dtype=pl.Int64)
    if game.get("nflverse_game_id"):
        cols["nflverse_game_id"] = pl.lit(str(game["nflverse_game_id"]), dtype=pl.Utf8)
    return df.with_columns(**cols)


def flat_block_frame(block: list[dict[str, Any]] | None, game: dict[str, Any]) -> pl.DataFrame:
    """A list-of-flat-dicts block -> one row per element, stamped with identity."""
    if not block:
        return pl.DataFrame()
    rows = [{k: _norm_cell(v) for k, v in elem.items()} for elem in block if isinstance(elem, dict)]
    if not rows:
        return pl.DataFrame()
    return stamp_identity(pl.from_dicts(rows, infer_schema_length=None), game, week=True)


def bind_games(frames: list[pl.DataFrame | None]) -> pl.DataFrame:
    """Vertically union per-game frames by name, dropping empties, widening dtypes."""
    keep = [f for f in frames if f is not None and f.height > 0]
    if not keep:
        return pl.DataFrame()
    return pl.concat(keep, how="diagonal_relaxed")
