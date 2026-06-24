"""Calibration tables + weighted calibration error for NFL EP/WP/CP models.

Mirrors the cfbfastR model-suite metric layer (cpoe/validate.py, rb_eval/validate.py):
a generic binned ``calibration_table`` + ``weighted_cal_error``, plus the EP-scalar
calibration (predicted expected points vs realized next-score points). These feed
``figures.py`` (calibration plots) and the ``report`` CLI.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import polars as pl

from .constants import EP_CLASS_ORDER, EP_LABEL_TO_SCORE

_EP_POINTS = np.array([EP_LABEL_TO_SCORE[c] for c in EP_CLASS_ORDER], dtype=np.float64)


def ep_expected_points(probs: np.ndarray) -> np.ndarray:
    """Convert an (N, 7) class-probability matrix to EP scalars, clamped to [-10, 10]."""
    if probs.ndim == 1:
        probs = probs.reshape(-1, len(EP_CLASS_ORDER))
    return np.clip(probs @ _EP_POINTS, -10.0, 10.0)


def brier_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean squared error between binary outcomes and predicted probabilities."""
    return float(np.mean((np.asarray(y_pred) - np.asarray(y_true)) ** 2))


def calibration_table(
    df: pl.DataFrame,
    pred_col: str,
    outcome_col: str,
    *,
    by: Optional[str] = None,
    bin_size: float = 0.05,
    min_plays: int = 10,
) -> pl.DataFrame:
    """Bin ``pred_col`` and compute the mean ``outcome_col`` per (``by``, bin).

    Generic over binary calibration (WP/CP: outcome 0/1, pred a probability) and
    value calibration (EP: outcome realized points, pred expected points with a
    larger ``bin_size``).

    Args:
        df: Frame with ``pred_col`` and ``outcome_col`` (and ``by`` if faceting).
        pred_col: Predicted probability / value column.
        outcome_col: Observed outcome column (averaged within each bin).
        by: Optional facet column (e.g. ``qtr`` for WP, an air-yards bucket for CP).
        bin_size: Bin width for ``pred_col`` (0.05 for probabilities, ~0.5 for EP).
        min_plays: Drop bins with fewer than this many rows.

    Returns:
        Frame with columns ``by``, ``bin``, ``n_plays``, ``actual`` — the exact
        shape :func:`figures.write_calibration` expects.
    """
    group = ([by] if by else []) + ["bin"]
    out = (
        df.drop_nulls([pred_col, outcome_col])
        .with_columns(bin=((pl.col(pred_col) / bin_size).round() * bin_size).round(4))
        .group_by(group)
        .agg(
            n_plays=pl.len(),
            actual=pl.col(outcome_col).cast(pl.Float64).mean(),
        )
        .filter(pl.col("n_plays") >= min_plays)
        .sort(group)
    )
    if by:
        out = out.rename({by: "by"}) if by != "by" else out
    else:
        out = out.with_columns(by=pl.lit("All"))
    return out.select(["by", "bin", "n_plays", "actual"])


def weighted_cal_error(table: pl.DataFrame) -> dict:
    """Per-facet + overall play-weighted mean |bin − actual| from a calibration table.

    Args:
        table: Output of :func:`calibration_table` (columns by/bin/n_plays/actual).

    Returns:
        ``{"per_group": [{by, wce, n}, ...], "overall": float}``.
    """
    t = table.with_columns(cal_diff=(pl.col("bin") - pl.col("actual")).abs())
    per = (
        t.group_by("by")
        .agg(
            wce=(pl.col("cal_diff") * pl.col("n_plays")).sum() / pl.col("n_plays").sum(),
            n=pl.col("n_plays").sum(),
        )
        .sort("by")
    )
    total = int(per["n"].sum())
    overall = float((per["wce"] * per["n"]).sum() / total) if total else float("nan")
    return {"per_group": per.to_dicts(), "overall": overall}


def pearson_correlation(x: np.ndarray, y: np.ndarray) -> float:
    """Pearson r between two 1-D arrays (0.0 when either is constant)."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    xm, ym = x - x.mean(), y - y.mean()
    denom = np.sqrt((xm ** 2).sum() * (ym ** 2).sum())
    return 0.0 if denom == 0.0 else float((xm * ym).sum() / denom)
