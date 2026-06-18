"""XGBoost trainers for NFL EP / WP-spread / WP-naive / CP models.

Each train_* function accepts a polars DataFrame that has already been feature-engineered
by features.py and returns a trained Booster. Pass ``nrounds`` to override the canonical
value from constants.py (useful for smoke tests with nrounds=5).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import polars as pl
from xgboost import Booster, DMatrix, train as xgb_train

from .constants import (
    EP_FEATURES,
    EP_HYPERPARAMS,
    EP_NUM_CLASSES,
    WP_SPREAD_FEATURES,
    WP_SPREAD_HYPERPARAMS,
    WP_NAIVE_FEATURES,
    WP_NAIVE_HYPERPARAMS,
    CP_FEATURES,
    CP_HYPERPARAMS,
    XYAC_FEATURES,
    XYAC_HYPERPARAMS,
)


def _to_dmatrix(
    df: pl.DataFrame,
    features: list[str],
    label_col: str,
    weight_col: Optional[str] = None,
) -> DMatrix:
    X = df.select(features).to_numpy()
    y = df[label_col].to_numpy()
    w = df[weight_col].to_numpy() if weight_col and weight_col in df.columns else None
    dmat = DMatrix(X, label=y, weight=w, feature_names=features)
    return dmat


def train_ep(
    df: pl.DataFrame,
    *,
    nrounds: Optional[int] = None,
    output_path: Optional[Path] = None,
) -> Booster:
    """Train NFL expected-points model.

    Args:
        df: Feature frame with ``EP_FEATURES`` columns + ``next_score_class`` (0–6)
            and optionally ``weight`` for sample weighting.
        nrounds: Override canonical nrounds (default: ``EP_HYPERPARAMS["nrounds"]``).
        output_path: If given, save the model as a UBJ file.

    Returns:
        Trained :class:`xgboost.Booster`.
    """
    rounds = nrounds if nrounds is not None else EP_HYPERPARAMS["nrounds"]
    params = {k: v for k, v in EP_HYPERPARAMS.items() if k != "nrounds"}
    dmat = _to_dmatrix(df, EP_FEATURES, "next_score_class", weight_col="weight")
    model = xgb_train(params, dmat, num_boost_round=rounds)
    if output_path is not None:
        model.save_model(str(output_path))
    return model


def train_wp_spread(
    df: pl.DataFrame,
    *,
    nrounds: Optional[int] = None,
    output_path: Optional[Path] = None,
) -> Booster:
    """Train NFL win-probability model with spread feature.

    Args:
        df: Feature frame with ``WP_SPREAD_FEATURES`` columns + ``label`` (0/1).
        nrounds: Override canonical nrounds (default: ``WP_SPREAD_HYPERPARAMS["nrounds"]``).
        output_path: If given, save the model as a UBJ file.

    Returns:
        Trained :class:`xgboost.Booster`.
    """
    rounds = nrounds if nrounds is not None else WP_SPREAD_HYPERPARAMS["nrounds"]
    params = {k: v for k, v in WP_SPREAD_HYPERPARAMS.items() if k not in ("nrounds", "monotone_constraints")}
    # XGBoost expects the monotone string as a param
    mc = WP_SPREAD_HYPERPARAMS["monotone_constraints"]
    params["monotone_constraints"] = "(" + ",".join(str(x) for x in mc) + ")"
    dmat = _to_dmatrix(df, WP_SPREAD_FEATURES, "label")
    model = xgb_train(params, dmat, num_boost_round=rounds)
    if output_path is not None:
        model.save_model(str(output_path))
    return model


def train_wp_naive(
    df: pl.DataFrame,
    *,
    nrounds: Optional[int] = None,
    output_path: Optional[Path] = None,
) -> Booster:
    """Train NFL win-probability model without spread feature.

    Args:
        df: Feature frame with ``WP_NAIVE_FEATURES`` columns + ``label`` (0/1).
        nrounds: Override canonical nrounds (default: ``WP_NAIVE_HYPERPARAMS["nrounds"]``).
        output_path: If given, save the model as a UBJ file.

    Returns:
        Trained :class:`xgboost.Booster`.
    """
    rounds = nrounds if nrounds is not None else WP_NAIVE_HYPERPARAMS["nrounds"]
    params = {k: v for k, v in WP_NAIVE_HYPERPARAMS.items() if k != "nrounds"}
    dmat = _to_dmatrix(df, WP_NAIVE_FEATURES, "label")
    model = xgb_train(params, dmat, num_boost_round=rounds)
    if output_path is not None:
        model.save_model(str(output_path))
    return model


def train_cp(
    df: pl.DataFrame,
    *,
    nrounds: Optional[int] = None,
    output_path: Optional[Path] = None,
) -> Booster:
    """Train NFL completion-probability model.

    Args:
        df: Feature frame from ``prepare_cp_data()`` filtered to ``valid_pass == 1``.
            Must have ``CP_FEATURES`` columns + ``complete_pass`` label.
        nrounds: Override canonical nrounds (default: ``CP_HYPERPARAMS["nrounds"]``).
        output_path: If given, save the model as a UBJ file.

    Returns:
        Trained :class:`xgboost.Booster`.
    """
    rounds = nrounds if nrounds is not None else CP_HYPERPARAMS["nrounds"]
    params = {k: v for k, v in CP_HYPERPARAMS.items() if k != "nrounds"}
    # base_score = mean completion rate (set dynamically)
    if "complete_pass" in df.columns:
        params["base_score"] = float(df["complete_pass"].mean())
    dmat = _to_dmatrix(df, CP_FEATURES, "complete_pass")
    model = xgb_train(params, dmat, num_boost_round=rounds)
    if output_path is not None:
        model.save_model(str(output_path))
    return model


def train_xyac(
    df: pl.DataFrame,
    *,
    nrounds: Optional[int] = None,
    output_path: Optional[Path] = None,
) -> Booster:
    """Train NFL expected-yards-after-catch (xYAC) model.

    Faithful port of ``nflverse-pbp/models/train_xyac_model.R``: a 76-class
    ``multi:softprob`` model over clamped YAC buckets, no sample weights.

    Args:
        df: Feature frame from ``build_xyac_training_set()`` — ``XYAC_FEATURES``
            columns + ``label`` (Int32, 0–75).
        nrounds: Override canonical nrounds (default: ``XYAC_HYPERPARAMS["nrounds"]``).
        output_path: If given, save the model as a UBJ file.

    Returns:
        Trained :class:`xgboost.Booster`.
    """
    rounds = nrounds if nrounds is not None else XYAC_HYPERPARAMS["nrounds"]
    params = {k: v for k, v in XYAC_HYPERPARAMS.items() if k != "nrounds"}
    dmat = _to_dmatrix(df, XYAC_FEATURES, "label")
    model = xgb_train(params, dmat, num_boost_round=rounds)
    if output_path is not None:
        model.save_model(str(output_path))
    return model
