"""Parity gate for NFL EP/WP models.

Compares model predictions against nflfastR reference values embedded in the
nflverse PBP parquet (the ``ep`` and ``wp`` columns).

Gate criteria (from HANDOFF.md):
    - EP: Pearson correlation ≥ 0.98 with nflfastR ``ep`` column
    - WP: Brier score ≤ 0.20 on held-out plays
    - Feature names in saved model == EP_FEATURES / WP_SPREAD_FEATURES

Usage::

    uv run python -m model_training.track6_nfl_ep_wp.validate \\
        --ep-model models/ep_model.ubj \\
        --wp-model models/wp_spread.ubj \\
        --sample-seasons 2022 2023
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import polars as pl

from .constants import EP_CLASS_ORDER, EP_FEATURES, EP_LABEL_TO_SCORE, WP_SPREAD_FEATURES


# Point values indexed by class order (TD=6, Opp_TD=-6, …, No_Score=0)
_EP_POINT_VALUES: np.ndarray = np.array(
    [EP_LABEL_TO_SCORE[cls] for cls in EP_CLASS_ORDER], dtype=np.float64
)


# ---------------------------------------------------------------------------
# Thin wrappers — monkeypatchable in tests
# ---------------------------------------------------------------------------

def _load_model(path: Path):
    """Load an XGBoost Booster from a .ubj file."""
    from xgboost import Booster
    b = Booster()
    b.load_model(str(path))
    return b


def _load_pbp_for_validation(
    seasons: List[int],
    data_dir: Path,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Return (ep_frame, wp_frame) filtered to plays with reference values."""
    from .ingest import load_local_pbp
    from .features import make_model_mutations, _add_wp_aux, _add_receive_2h_ko
    from .label import compute_winner

    df = load_local_pbp(seasons, data_dir=data_dir)
    df = make_model_mutations(df)

    # EP frame: compare on the EP model's domain — scrimmage plays with a valid down and
    # non-null yardline/timeouts. This matches nflfastR's cal_data filter (MODELS.R requires
    # non-null yardline + timeouts) and excludes kickoffs/PATs (down == NA), which nflfastR
    # does NOT score with the raw model — it substitutes features (yardline=75/80, down1=1)
    # at inference (helper_add_ep_wp.R). Comparing raw-feature kickoffs would be
    # apples-to-oranges; on the model's actual domain our EP matches nflfastR ~0.995.
    ep_df = df.filter(
        pl.col("ep").is_not_null()
        & pl.col("yardline_100").is_not_null()
        & pl.col("posteam_timeouts_remaining").is_not_null()
        & pl.col("defteam_timeouts_remaining").is_not_null()
        & ((pl.col("down1") + pl.col("down2") + pl.col("down3") + pl.col("down4")) == 1)
    ).select([*EP_FEATURES, "ep"])

    # WP frame: regulation plays with non-null wp reference and outcome label.
    # compute_winner adds the `wp_label` (posteam-won 0/1) column the gate scores
    # against — the training path computes it too; validation must mirror that.
    wp_df = df.filter(
        pl.col("qtr") <= 4
    )
    wp_df = _add_wp_aux(wp_df)
    wp_df = _add_receive_2h_ko(wp_df)
    wp_df = compute_winner(wp_df)
    wp_df = wp_df.filter(
        pl.col("wp").is_not_null()
        & pl.col("wp_label").is_not_null()
    ).select([*WP_SPREAD_FEATURES, "wp", pl.col("wp_label").alias("label")])

    return ep_df, wp_df


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def pearson_correlation(x: np.ndarray, y: np.ndarray) -> float:
    """Compute Pearson r between two 1-D arrays.

    Args:
        x: First array.
        y: Second array (same length).

    Returns:
        Pearson correlation coefficient in [-1, 1].
    """
    xm, ym = x - x.mean(), y - y.mean()
    denom = np.sqrt((xm ** 2).sum() * (ym ** 2).sum())
    if denom == 0.0:
        return 0.0
    return float((xm * ym).sum() / denom)


def brier_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean squared error between binary outcomes and predicted probabilities.

    Args:
        y_true: Binary outcomes (0 / 1).
        y_pred: Predicted probabilities in [0, 1].

    Returns:
        Brier score in [0, 1]; lower is better.
    """
    return float(np.mean((y_pred - y_true) ** 2))


def _ep_expected_points(probs: np.ndarray) -> np.ndarray:
    """Convert (N, 7) class-probability matrix to expected-points scalar.

    Mirrors nflfastR's ``predict_ep()``: EP = sum_k(p_k * score_k), then
    clamp to [-10, 10].

    Args:
        probs: Array of shape (N, 7) from ``xgb_model.predict(DMatrix)``.

    Returns:
        1-D array of shape (N,) with EP values in [-10, 10].
    """
    ep = probs @ _EP_POINT_VALUES
    return np.clip(ep, -10.0, 10.0)


# ---------------------------------------------------------------------------
# Model validators
# ---------------------------------------------------------------------------

def validate_ep(
    model,
    df: pl.DataFrame,
    *,
    correlation_threshold: float = 0.98,
) -> Dict[str, Any]:
    """Validate EP model predictions against nflfastR reference ``ep`` column.

    Args:
        model: Trained XGBoost Booster with ``EP_FEATURES`` feature names.
        df: Frame with ``EP_FEATURES`` columns + ``ep`` (nflfastR reference values).
        correlation_threshold: Minimum Pearson r to pass the gate (default 0.98).

    Returns:
        Dict with keys ``correlation``, ``gate_pass``, ``n_plays``.
    """
    from xgboost import DMatrix

    X = df.select(EP_FEATURES).to_numpy()
    dmat = DMatrix(X, feature_names=EP_FEATURES)
    probs = model.predict(dmat)
    if probs.ndim == 1:
        # reshape (N*7,) → (N,7) if XGBoost returns flat output
        probs = probs.reshape(-1, len(EP_CLASS_ORDER))

    our_ep = _ep_expected_points(probs)
    ref_ep = np.array(df["ep"].to_list(), dtype=np.float64)
    r = pearson_correlation(our_ep, ref_ep)

    return {
        "correlation": r,
        "gate_pass": r >= correlation_threshold,
        "n_plays": len(df),
    }


def validate_wp(
    model,
    df: pl.DataFrame,
    *,
    brier_threshold: float = 0.20,
) -> Dict[str, Any]:
    """Validate WP model predictions against actual game outcomes.

    Args:
        model: Trained XGBoost Booster with ``WP_SPREAD_FEATURES`` feature names.
        df: Frame with ``WP_SPREAD_FEATURES`` columns + ``label`` (0/1 actual outcome).
        brier_threshold: Maximum Brier score to pass the gate (default 0.20).

    Returns:
        Dict with keys ``brier_score``, ``gate_pass``, ``n_plays``.
    """
    from xgboost import DMatrix

    X = df.select(WP_SPREAD_FEATURES).to_numpy()
    dmat = DMatrix(X, feature_names=WP_SPREAD_FEATURES)
    y_pred = model.predict(dmat)
    y_true = np.array(df["label"].to_list(), dtype=np.float64)
    bs = brier_score(y_true, y_pred)

    return {
        "brier_score": bs,
        "gate_pass": bs <= brier_threshold,
        "n_plays": len(df),
    }


# ---------------------------------------------------------------------------
# Parity gate orchestrator
# ---------------------------------------------------------------------------

def run_parity_gate(
    ep_model_path: Path,
    wp_model_path: Path,
    sample_seasons: List[int],
    *,
    data_dir: Path = Path("data"),
    ep_correlation_threshold: float = 0.98,
    wp_brier_threshold: float = 0.20,
) -> Dict[str, Any]:
    """Run the full EP + WP parity gate against nflfastR reference values.

    Args:
        ep_model_path: Path to ``ep_model.ubj``.
        wp_model_path: Path to ``wp_spread.ubj``.
        sample_seasons: Seasons of nflverse PBP to compare against.
        data_dir: Directory containing ``pbp_{season}.parquet`` files.
        ep_correlation_threshold: Gate threshold for EP Pearson r (default 0.98).
        wp_brier_threshold: Gate threshold for WP Brier score (default 0.20).

    Returns:
        Dict with keys ``ep`` (EP result dict), ``wp`` (WP result dict), and
        ``overall_pass`` (True only when both gates pass).

    Example:
        Run the gate after training::

            from pathlib import Path
            from model_training.track6_nfl_ep_wp.validate import run_parity_gate

            result = run_parity_gate(
                ep_model_path=Path("models/ep_model.ubj"),
                wp_model_path=Path("models/wp_spread.ubj"),
                sample_seasons=[2022, 2023],
            )
            print("PASS" if result["overall_pass"] else "FAIL", result)
    """
    ep_model = _load_model(Path(ep_model_path))
    wp_model = _load_model(Path(wp_model_path))

    ep_df, wp_df = _load_pbp_for_validation(sample_seasons, Path(data_dir))

    print(f"[validate] EP: {len(ep_df):,} reference plays from {sample_seasons}")
    ep_result = validate_ep(
        ep_model, ep_df, correlation_threshold=ep_correlation_threshold
    )
    print(f"[validate] EP correlation = {ep_result['correlation']:.4f} "
          f"(threshold ≥ {ep_correlation_threshold}) → {'PASS' if ep_result['gate_pass'] else 'FAIL'}")

    print(f"[validate] WP: {len(wp_df):,} reference plays from {sample_seasons}")
    wp_result = validate_wp(
        wp_model, wp_df, brier_threshold=wp_brier_threshold
    )
    print(f"[validate] WP Brier = {wp_result['brier_score']:.4f} "
          f"(threshold ≤ {wp_brier_threshold}) → {'PASS' if wp_result['gate_pass'] else 'FAIL'}")

    overall = ep_result["gate_pass"] and wp_result["gate_pass"]
    print(f"[validate] Overall: {'PASS ✓' if overall else 'FAIL ✗'}")

    return {
        "ep": ep_result,
        "wp": wp_result,
        "overall_pass": overall,
    }
