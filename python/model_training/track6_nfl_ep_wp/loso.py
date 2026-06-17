"""Leave-one-season-out (LOSO) calibration for NFL EP/WP/CP models.

For each held-out season: train on the remaining seasons, predict on the held-out
season, and collect (prediction, outcome[, facet]) into a long-form frame suitable
for :func:`metrics.calibration_table`. This is the out-of-sample evaluation harness
the cfbfastR suite uses (cpoe/rb_eval), now matched for NFL.

LOSO trains one model per season, so pass a reduced ``nrounds`` for a quick
calibration pass; ``None`` uses the canonical (production) round counts.
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np
import polars as pl

from .constants import CP_FEATURES, EP_CLASS_ORDER, EP_FEATURES, WP_NAIVE_FEATURES
from .metrics import ep_expected_points

_EP_POINTS = ep_expected_points  # alias for readability


def _seasons(pbp: pl.DataFrame, seasons: Optional[List[int]]) -> List[int]:
    present = sorted(pbp.filter(pl.col("season").is_not_null())["season"].unique().to_list())
    return [s for s in (seasons or present) if s in present]


def loso_ep(pbp: pl.DataFrame, *, seasons: Optional[List[int]] = None,
            nrounds: Optional[int] = None) -> pl.DataFrame:
    """LOSO for EP — returns (season, pred_ep, actual_points) per play.

    ``actual_points`` is the realized next-score value (the class's point value),
    so a calibration table of pred_ep vs actual_points is a reliability check.
    """
    from xgboost import DMatrix

    from .label import build_ep_training_set
    from .trainer import train_ep

    pts = np.array([ {  # class index -> point value
        "Touchdown": 7, "Opp_Touchdown": -7, "Field_Goal": 3, "Opp_Field_Goal": -3,
        "Safety": 2, "Opp_Safety": -2, "No_Score": 0,
    }[c] for c in EP_CLASS_ORDER], dtype=np.float64)

    folds = []
    for held in _seasons(pbp, seasons):
        tr, te = pbp.filter(pl.col("season") != held), pbp.filter(pl.col("season") == held)
        if tr.is_empty() or te.is_empty():
            continue
        model = train_ep(build_ep_training_set(tr), nrounds=nrounds)
        ep_te = build_ep_training_set(te)
        probs = model.predict(DMatrix(ep_te.select(EP_FEATURES).to_numpy(), feature_names=EP_FEATURES))
        # Reconstruct down from the one-hot features for the EP-by-yardline curve.
        down = (ep_te["down1"] * 1 + ep_te["down2"] * 2 + ep_te["down3"] * 3 + ep_te["down4"] * 4)
        folds.append(pl.DataFrame({
            "pred_ep": ep_expected_points(probs).tolist(),
            "actual_points": pts[ep_te["next_score_class"].to_numpy()].tolist(),
            "yardline_100": ep_te["yardline_100"].to_list(),
            "down": down.cast(pl.Int64).to_list(),
        }).with_columns(season=pl.lit(held)))
    return pl.concat(folds, how="diagonal_relaxed") if folds else pl.DataFrame()


def loso_wp(pbp: pl.DataFrame, *, seasons: Optional[List[int]] = None,
            nrounds: Optional[int] = None) -> pl.DataFrame:
    """LOSO for WP-naive — returns (season, pred_wp, wp_label) per play."""
    from xgboost import DMatrix

    from .label import build_wp_training_set
    from .trainer import train_wp_naive

    folds = []
    for held in _seasons(pbp, seasons):
        tr, te = pbp.filter(pl.col("season") != held), pbp.filter(pl.col("season") == held)
        if tr.is_empty() or te.is_empty():
            continue
        model = train_wp_naive(build_wp_training_set(tr, variant="naive"), nrounds=nrounds)
        wp_te = build_wp_training_set(te, variant="naive")
        preds = model.predict(DMatrix(wp_te.select(WP_NAIVE_FEATURES).to_numpy(), feature_names=WP_NAIVE_FEATURES))
        folds.append(pl.DataFrame({
            "pred_wp": preds.tolist(),
            "wp_label": wp_te["label"].to_numpy().tolist(),
        }).with_columns(season=pl.lit(held)))
    return pl.concat(folds, how="diagonal_relaxed") if folds else pl.DataFrame()


def loso_cp(pbp: pl.DataFrame, *, seasons: Optional[List[int]] = None,
            nrounds: Optional[int] = None) -> pl.DataFrame:
    """LOSO for CP — returns (season, pred_cp, complete_pass, air_yards_bucket) per play."""
    from xgboost import DMatrix

    from .label import build_cp_training_set
    from .trainer import train_cp

    folds = []
    for held in _seasons(pbp, seasons):
        tr, te = pbp.filter(pl.col("season") != held), pbp.filter(pl.col("season") == held)
        if tr.is_empty() or te.is_empty():
            continue
        model = train_cp(build_cp_training_set(tr), nrounds=nrounds)
        cp_te = build_cp_training_set(te)
        preds = model.predict(DMatrix(cp_te.select(CP_FEATURES).to_numpy(), feature_names=CP_FEATURES))
        fold = cp_te.with_columns(
            pred_cp=pl.Series(preds.tolist(), dtype=pl.Float64),
        ).with_columns(
            air_yards_bucket=pl.when(pl.col("air_yards") <= 5).then(pl.lit("Short"))
            .when(pl.col("air_yards") <= 15).then(pl.lit("Intermediate"))
            .otherwise(pl.lit("Deep")),
            season=pl.lit(held),
        ).select(["season", "pred_cp", "complete_pass", "air_yards", "pass_middle", "air_yards_bucket"])
        folds.append(fold)
    return pl.concat(folds, how="diagonal_relaxed") if folds else pl.DataFrame()
