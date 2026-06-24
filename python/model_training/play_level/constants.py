"""Feature contracts and hyperparameters for NFL EP/WP/CP models.

Canonical source: fastrmodels/data-raw/MODELS.R (Ben Baldwin, nflverse/fastrmodels)
Feature derivations: nflfastR/R/helper_add_ep_wp.R + helper_add_cp_cpoe.R
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# EP — expected points (multi:softprob, 7 classes)
# ---------------------------------------------------------------------------

EP_FEATURES: list[str] = [
    "half_seconds_remaining",
    "yardline_100",
    "home",
    "retractable",
    "dome",
    "outdoors",
    "ydstogo",
    "era0",
    "era1",
    "era2",
    "era3",
    "era4",
    "down1",
    "down2",
    "down3",
    "down4",
    "posteam_timeouts_remaining",
    "defteam_timeouts_remaining",
]

EP_NUM_CLASSES: int = 7

EP_LABEL_TO_SCORE: dict[str, float] = {
    "Touchdown": 7.0,
    "Opp_Touchdown": -7.0,
    "Field_Goal": 3.0,
    "Opp_Field_Goal": -3.0,
    "Safety": 2.0,
    "Opp_Safety": -2.0,
    "No_Score": 0.0,
}

# Class index order mirrors fastrmodels: 0=TD, 1=Opp_TD, 2=FG, 3=Opp_FG, 4=Safety, 5=Opp_Safety, 6=No_Score
EP_CLASS_ORDER: list[str] = [
    "Touchdown",
    "Opp_Touchdown",
    "Field_Goal",
    "Opp_Field_Goal",
    "Safety",
    "Opp_Safety",
    "No_Score",
]

EP_HYPERPARAMS: dict = {
    "objective": "multi:softprob",
    "num_class": EP_NUM_CLASSES,
    "eval_metric": "mlogloss",
    "eta": 0.025,
    "gamma": 1.0,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "max_depth": 5,
    "min_child_weight": 1,
    "nrounds": 525,
    "seed": 2013,
}

# ---------------------------------------------------------------------------
# WP-spread — win probability with spread (binary:logistic)
# ---------------------------------------------------------------------------

WP_SPREAD_FEATURES: list[str] = [
    "receive_2h_ko",
    "spread_time",
    "home",
    "half_seconds_remaining",
    "game_seconds_remaining",
    "Diff_Time_Ratio",
    "score_differential",
    "down",
    "ydstogo",
    "yardline_100",
    "posteam_timeouts_remaining",
    "defteam_timeouts_remaining",
]

WP_SPREAD_MONOTONE_CONSTRAINTS: tuple[int, ...] = (0, 0, 0, 0, 0, 1, 1, -1, -1, -1, 1, -1)

WP_SPREAD_HYPERPARAMS: dict = {
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "eta": 0.05,
    "gamma": 0.79012017,
    "subsample": 0.9224245,
    "colsample_bytree": 5 / 12,
    "max_depth": 5,
    "min_child_weight": 7,
    "nrounds": 534,
    "monotone_constraints": WP_SPREAD_MONOTONE_CONSTRAINTS,
}

# ---------------------------------------------------------------------------
# WP-naive — win probability without spread (binary:logistic)
# ---------------------------------------------------------------------------

WP_NAIVE_FEATURES: list[str] = [f for f in WP_SPREAD_FEATURES if f != "spread_time"]

WP_NAIVE_HYPERPARAMS: dict = {
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "eta": 0.2,
    "gamma": 0.0,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "max_depth": 4,
    "min_child_weight": 1,
    "nrounds": 65,
}

# ---------------------------------------------------------------------------
# CP — completion probability (binary:logistic, Zach Feldman)
# ---------------------------------------------------------------------------

CP_FEATURES: list[str] = [
    "air_yards",
    "yardline_100",
    "ydstogo",
    "down1",
    "down2",
    "down3",
    "down4",
    "air_is_zero",
    "pass_middle",
    "era2",
    "era3",
    "era4",
    "qb_hit",
    "home",
    "outdoors",
    "retractable",
    "dome",
    "distance_to_sticks",
]

CP_HYPERPARAMS: dict = {
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "eta": 0.025,
    "gamma": 5.0,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "max_depth": 4,
    "min_child_weight": 6,
    "nrounds": 560,
}

# ---------------------------------------------------------------------------
# xYAC — expected yards after catch (multi:softprob, 76 classes)
# ---------------------------------------------------------------------------
# Canonical source: nflverse-pbp/models/train_xyac_model.R. Same feature family as
# CP (a completed pass at the catch point) plus ``distance_to_goal`` (= yardline_100 -
# air_yards, the yardline at the catch). The label is a 76-class multinomial over
# clamped YAC buckets: clamp(yards_after_catch, -5, 70) + 5 → integers 0..75. The
# model gives, for each completed pass, the full distribution of plausible YAC values,
# from which xYAC EP and other YAC-aware metrics are derived.

XYAC_FEATURES: list[str] = [
    "air_yards",
    "yardline_100",
    "ydstogo",
    "distance_to_goal",
    "down1",
    "down2",
    "down3",
    "down4",
    "air_is_zero",
    "pass_middle",
    "era2",
    "era3",
    "era4",
    "qb_hit",
    "home",
    "outdoors",
    "retractable",
    "dome",
    "distance_to_sticks",
]

# 76 YAC buckets: clamp(yards_after_catch, -5, 70) shifted by +5 → [0, 75].
XYAC_NUM_CLASSES: int = 76

XYAC_HYPERPARAMS: dict = {
    "objective": "multi:softprob",
    "num_class": XYAC_NUM_CLASSES,
    "eval_metric": "mlogloss",
    "eta": 0.025,
    "gamma": 2.0,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "max_depth": 4,
    "min_child_weight": 1,
    "nrounds": 500,
    "seed": 2013,
}
