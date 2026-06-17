"""Training orchestrator for NFL EP/WP/CP models.

Chains ingest → label → train in a single call.  Each stage is a thin
module-level wrapper so tests can monkeypatch without touching the library.

Usage::

    from pathlib import Path
    from model_training.track6_nfl_ep_wp.pipeline import run_full_pipeline

    paths = run_full_pipeline(
        seasons=list(range(2012, 2025)),
        data_dir=Path("data"),
        models_dir=Path("models"),
        download=True,
    )
    # paths == {"ep": ..., "wp_spread": ..., "wp_naive": ..., "cp": ...}

CLI::

    uv run python -m model_training.track6_nfl_ep_wp --help
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import polars as pl


# ---------------------------------------------------------------------------
# Thin wrappers — monkeypatchable in tests
# ---------------------------------------------------------------------------

def _download_pbp(seasons: List[int], data_dir: Path) -> List[Path]:
    from .ingest import download_pbp
    return download_pbp(seasons, output_dir=data_dir)


def _load_pbp(seasons: List[int], data_dir: Path) -> pl.DataFrame:
    from .ingest import load_local_pbp
    return load_local_pbp(seasons, data_dir=data_dir)


def _load_native(seasons: List[int]) -> pl.DataFrame:
    """Reconstruct PBP from the committed nfl/raw Shield library (no nflverse dep)."""
    from .ingest import load_native_pbp
    return load_native_pbp(seasons)


def _resolve_pbp(seasons: List[int], data_dir: Path, download: bool, source: str) -> pl.DataFrame:
    """Load the training PBP frame from the chosen source.

    ``source="nflverse"`` (default) downloads (optional) + reads local parquet;
    ``source="native"`` reconstructs from the committed nfl/raw Shield library.
    """
    if source == "native":
        return _load_native(seasons)
    if source != "nflverse":
        raise ValueError(f"Unknown source {source!r}; expected 'nflverse' or 'native'.")
    if download:
        _download_pbp(seasons, data_dir)
    return _load_pbp(seasons, data_dir)


def _build_ep(df: pl.DataFrame) -> pl.DataFrame:
    from .label import build_ep_training_set
    return build_ep_training_set(df)


def _build_wp(df: pl.DataFrame, variant: str) -> pl.DataFrame:
    from .label import build_wp_training_set
    return build_wp_training_set(df, variant=variant)  # type: ignore[arg-type]


def _build_cp(df: pl.DataFrame) -> pl.DataFrame:
    from .label import build_cp_training_set
    return build_cp_training_set(df)


def _train_ep(df: pl.DataFrame, output_path: Path):
    from .trainer import train_ep
    return train_ep(df, output_path=output_path)


def _train_wp_spread(df: pl.DataFrame, output_path: Path):
    from .trainer import train_wp_spread
    return train_wp_spread(df, output_path=output_path)


def _train_wp_naive(df: pl.DataFrame, output_path: Path):
    from .trainer import train_wp_naive
    return train_wp_naive(df, output_path=output_path)


def _train_cp(df: pl.DataFrame, output_path: Path):
    from .trainer import train_cp
    return train_cp(df, output_path=output_path)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_ep_pipeline(
    seasons: List[int],
    *,
    data_dir: Path = Path("data"),
    models_dir: Path = Path("models"),
    download: bool = False,
) -> Path:
    """Download PBP (optional), build EP training set, train, save model.

    Args:
        seasons: NFL seasons to use for training.
        data_dir: Directory containing (or to receive) ``pbp_{season}.parquet`` files.
        models_dir: Directory where ``ep_model.ubj`` is written.
        download: When ``True``, download PBP from nflverse before training.

    Returns:
        Path to the saved ``ep_model.ubj`` file.
    """
    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)

    if download:
        _download_pbp(seasons, Path(data_dir))
    df = _load_pbp(seasons, Path(data_dir))
    ep_df = _build_ep(df)
    output_path = models_dir / "ep_model.ubj"
    _train_ep(ep_df, output_path)
    return output_path


def run_wp_pipeline(
    seasons: List[int],
    *,
    variant: str = "spread",
    data_dir: Path = Path("data"),
    models_dir: Path = Path("models"),
    download: bool = False,
) -> Path:
    """Download PBP (optional), build WP training set, train, save model.

    Args:
        seasons: NFL seasons to use for training.
        variant: ``"spread"`` or ``"naive"``.
        data_dir: Directory containing PBP parquet files.
        models_dir: Directory where the model file is written.
        download: When ``True``, download PBP from nflverse before training.

    Returns:
        Path to the saved ``wp_spread.ubj`` or ``wp_naive.ubj`` file.
    """
    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)

    if download:
        _download_pbp(seasons, Path(data_dir))
    df = _load_pbp(seasons, Path(data_dir))
    wp_df = _build_wp(df, variant)
    filename = "wp_spread.ubj" if variant == "spread" else "wp_naive.ubj"
    output_path = models_dir / filename
    if variant == "spread":
        _train_wp_spread(wp_df, output_path)
    else:
        _train_wp_naive(wp_df, output_path)
    return output_path


def run_cp_pipeline(
    seasons: List[int],
    *,
    data_dir: Path = Path("data"),
    models_dir: Path = Path("models"),
    download: bool = False,
) -> Path:
    """Download PBP (optional), build CP training set, train, save model.

    Args:
        seasons: NFL seasons to use for training.
        data_dir: Directory containing PBP parquet files.
        models_dir: Directory where ``cp_model.ubj`` is written.
        download: When ``True``, download PBP from nflverse before training.

    Returns:
        Path to the saved ``cp_model.ubj`` file.
    """
    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)

    if download:
        _download_pbp(seasons, Path(data_dir))
    df = _load_pbp(seasons, Path(data_dir))
    cp_df = _build_cp(df)
    output_path = models_dir / "cp_model.ubj"
    _train_cp(cp_df, output_path)
    return output_path


def run_full_pipeline(
    seasons: List[int],
    *,
    data_dir: Path = Path("data"),
    models_dir: Path = Path("models"),
    download: bool = True,
    source: str = "nflverse",
    write_cards: bool = True,
) -> dict[str, Path]:
    """Train all four models (EP, WP-spread, WP-naive, CP) in one shot.

    Downloads PBP once (when ``download=True``), loads it once, then builds and
    trains each model from the same in-memory frame.

    Args:
        seasons: NFL seasons to use (e.g. ``list(range(2012, 2025))``).
        data_dir: Directory for PBP parquet cache.
        models_dir: Directory where ``.ubj`` model files are written.
        download: Download PBP from nflverse before training (default ``True``).

    Returns:
        Dict mapping model keys to their saved paths::

            {
                "ep":       Path("models/ep_model.ubj"),
                "wp_spread": Path("models/wp_spread.ubj"),
                "wp_naive":  Path("models/wp_naive.ubj"),
                "cp":        Path("models/cp_model.ubj"),
            }

    Example:
        Full 2012–2024 training run::

            from pathlib import Path
            from model_training.track6_nfl_ep_wp.pipeline import run_full_pipeline

            paths = run_full_pipeline(
                seasons=list(range(2012, 2025)),
                models_dir=Path("models"),
            )
    """
    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)
    data_dir = Path(data_dir)

    print(f"[pipeline] loading {len(seasons)} season(s) of PBP (source={source})...")
    df = _resolve_pbp(seasons, data_dir, download, source)
    print(f"[pipeline] loaded {df.height:,} plays")

    from .constants import (
        CP_FEATURES, CP_HYPERPARAMS, EP_FEATURES, EP_HYPERPARAMS,
        WP_NAIVE_FEATURES, WP_NAIVE_HYPERPARAMS, WP_SPREAD_FEATURES, WP_SPREAD_HYPERPARAMS,
    )
    from .model_card import write_model_card

    def _card(path, mtype, feats, label, hp, n_rows):
        if write_cards:
            write_model_card(path, model_type=mtype, features=feats, label=label,
                             seasons=seasons, n_rows=n_rows, hyperparams=hp, source=source)

    print("[pipeline] building EP training set...")
    ep_df = _build_ep(df)
    print(f"[pipeline] EP: {ep_df.height:,} plays → training")
    ep_path = models_dir / "ep_model.ubj"
    _train_ep(ep_df, ep_path)
    _card(ep_path, "ep", EP_FEATURES, "next_score_class", EP_HYPERPARAMS, ep_df.height)
    print(f"[pipeline] EP model saved → {ep_path}")

    print("[pipeline] building WP-spread training set...")
    wp_spread_df = _build_wp(df, "spread")
    print(f"[pipeline] WP-spread: {wp_spread_df.height:,} plays → training")
    wp_spread_path = models_dir / "wp_spread.ubj"
    _train_wp_spread(wp_spread_df, wp_spread_path)
    _card(wp_spread_path, "wp_spread", WP_SPREAD_FEATURES, "label", WP_SPREAD_HYPERPARAMS, wp_spread_df.height)
    print(f"[pipeline] WP-spread model saved → {wp_spread_path}")

    print("[pipeline] building WP-naive training set...")
    wp_naive_df = _build_wp(df, "naive")
    print(f"[pipeline] WP-naive: {wp_naive_df.height:,} plays → training")
    wp_naive_path = models_dir / "wp_naive.ubj"
    _train_wp_naive(wp_naive_df, wp_naive_path)
    _card(wp_naive_path, "wp_naive", WP_NAIVE_FEATURES, "label", WP_NAIVE_HYPERPARAMS, wp_naive_df.height)
    print(f"[pipeline] WP-naive model saved → {wp_naive_path}")

    print("[pipeline] building CP training set...")
    cp_df = _build_cp(df)
    print(f"[pipeline] CP: {cp_df.height:,} valid passes → training")
    cp_path = models_dir / "cp_model.ubj"
    _train_cp(cp_df, cp_path)
    _card(cp_path, "cp", CP_FEATURES, "complete_pass", CP_HYPERPARAMS, cp_df.height)
    print(f"[pipeline] CP model saved → {cp_path}")

    return {
        "ep": ep_path,
        "wp_spread": wp_spread_path,
        "wp_naive": wp_naive_path,
        "cp": cp_path,
    }
