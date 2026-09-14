"""Per-season dataset build: cached finals -> reshape -> drift-safe union -> parquet.

Outputs land under ``{out}/{dataset}/{stem}_{season}.parquet`` (``out/`` is
git-ignored in this repo; the release tag is the distribution channel, as for
every other nfl-data dataset). A season is read from the cache ONCE and every
requested dataset is cut from it.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import polars as pl

from nfl_espn_build.config import REGISTRY, DatasetSpec
from nfl_espn_build.process import load_season_finals
from nfl_espn_build.reshape import bind_games, flat_block_frame
from nfl_espn_build.reshapers import RESHAPERS

log = logging.getLogger(__name__)


def _resolve_block(game: dict[str, Any], path: tuple[str, ...]) -> Any:
    node: Any = game
    for k in path:
        if not isinstance(node, dict):
            return None
        node = node.get(k)
    return node


def dataset_frame(spec: DatasetSpec, finals: list[dict[str, Any]]) -> pl.DataFrame:
    """Build one dataset over a list of finals (one season, typically)."""
    frames: list[pl.DataFrame] = []
    for game in finals:
        if spec.block is not None:
            frames.append(flat_block_frame(_resolve_block(game, spec.block), game))
        else:
            frames.append(RESHAPERS[spec.reshaper](game))  # type: ignore[index]
    df = bind_games(frames)
    if df.height and "game_id" in df.columns:
        sort_keys = [c for c in ("season", "week", "game_id") if c in df.columns]
        df = df.sort(sort_keys, maintain_order=True)
    return df


def output_path(spec: DatasetSpec, season: int, out: str | Path) -> Path:
    return Path(out) / spec.dataset / f"{spec.stem}_{season}.parquet"


def write_dataset(df: pl.DataFrame, spec: DatasetSpec, season: int, out: str | Path) -> Path | None:
    """Write the season parquet; ``None`` (and no file) for an empty frame."""
    if df is None or df.height == 0:
        return None
    path = output_path(spec, season, out)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".parquet.tmp")
    df.write_parquet(tmp)
    tmp.replace(path)
    return path


def build_season(
    datasets: list[str], season: int, *, cache_dir: str | Path, out: str | Path
) -> dict[str, Path | None]:
    """Cut every requested dataset for one season from its cached finals."""
    finals = load_season_finals(cache_dir, season)
    log.info("season %s: %d cached finals", season, len(finals))
    written: dict[str, Path | None] = {}
    for name in datasets:
        spec = REGISTRY[name]
        df = dataset_frame(spec, finals)
        path = write_dataset(df, spec, season, out)
        written[name] = path
        log.info(
            "season %s %s: %d rows x %d cols -> %s",
            season,
            name,
            df.height,
            df.width,
            path if path else "(empty, not written)",
        )
    return written
