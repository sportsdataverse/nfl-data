"""Ingest nflverse play-by-play for the NFL model suite (decision_models).

The decision_models trainers need columns play_level's ``REQUIRED_COLUMNS`` superset does
not all carry (``two_point_conv_result``, ``sp`` / ``field_goal_result``,
``kick_distance``, ``return_yards``, ``first_down_penalty``, ``penalty_yards``,
``play_type_nfl``, ``desc``, …). The simplest faithful source is sdv-py's
``load_nfl_pbp(source="nflverse")``, which ships the full nflverse PBP schema
(spread_line / total_line / roof / wp / vegas_wp / kick_distance included).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import polars as pl

from .constants import WP_CAL_DATA_RDS

__all__ = ["load_training_pbp", "load_wp_cal_data"]


def load_training_pbp(seasons: List[int], *, source: str = "nflverse") -> pl.DataFrame:
    """Load training PBP for the decision_models models.

    Args:
        seasons: Seasons to load (e.g. ``list(range(2006, 2020))``).
        source: ``"nflverse"`` (default) → sdv-py ``load_nfl_pbp`` full schema.

    Returns:
        Concatenated polars DataFrame carrying the full nflverse PBP columns.

    Raises:
        ValueError: If ``source`` is unknown or no rows are returned.

    Example:
        Load the xpass training span::

            from model_training.decision_models.ingest import load_training_pbp
            df = load_training_pbp(list(range(2006, 2020)))
    """
    if source != "nflverse":
        raise ValueError(f"Unknown source {source!r}; decision_models supports 'nflverse'.")
    from sportsdataverse.nfl import load_nfl_pbp

    # Load per-season and concat with diagonal_relaxed: across a wide span (e.g.
    # 1999-2025) some nflverse columns drift dtype between seasons (``goal_to_go``
    # is Int32 in some years, Float64 in others), which a strict multi-season
    # vstack rejects. diagonal_relaxed unions columns and upcasts conflicting
    # dtypes to a common supertype, so the full-history span loads cleanly.
    frames: List[pl.DataFrame] = []
    for s in seasons:
        d = load_nfl_pbp(seasons=[s], source="nflverse")
        if not isinstance(d, pl.DataFrame):
            d = pl.from_pandas(d)
        if d.height:
            frames.append(d)
    if not frames:
        raise ValueError(f"No PBP returned for seasons {seasons}.")
    return pl.concat(frames, how="diagonal_relaxed")


def load_wp_cal_data(path: Optional[str] = None) -> pl.DataFrame:
    """Load the WP calibration frame (``cal_data.rds``) used by MODELS.R.

    The win-probability model is trained on ``guga31bb/metrics``
    ``wp_tuning/cal_data.rds`` — the frozen calibration frame nflfastR's
    ``data-raw/MODELS.R`` reads (it carries ``ep`` / ``Winner`` / ``play_type``,
    which are not derivable from raw PBP without re-running the full EP pipeline).
    Read directly via ``pyreadr`` (no Rscript round trip needed at runtime).

    Args:
        path: Path to ``cal_data.rds``. Defaults to ``WP_CAL_DATA_RDS`` (the
            local copy committed under ``nflverse-pbp/models``).

    Returns:
        Polars DataFrame with the cal_data columns (``game_id``, ``ep``,
        ``Winner``, ``posteam``, ``play_type``, ``spread_line``, …).

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If the RDS yields no rows.

    Example:
        Load + prepare the WP training frame::

            from model_training.decision_models.ingest import load_wp_cal_data
            from model_training.decision_models.features import (
                make_model_mutations, prepare_wp_data,
            )
            df = prepare_wp_data(make_model_mutations(load_wp_cal_data()))
    """
    import pyreadr

    rds_path = Path(path or WP_CAL_DATA_RDS)
    if not rds_path.exists():
        raise FileNotFoundError(
            f"cal_data.rds not found at {rds_path}. Override via load_wp_cal_data(path=...) or WP_CAL_DATA_RDS."
        )
    result = pyreadr.read_r(str(rds_path))
    pdf = next(iter(result.values()))  # single unnamed object in the RDS
    df = pl.from_pandas(pdf)
    if df.height == 0:
        raise ValueError(f"cal_data.rds at {rds_path} returned no rows.")
    return df
