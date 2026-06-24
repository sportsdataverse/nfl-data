"""Feature contracts and hyperparameters for the NFL model suite (decision_models).

Faithful Python port of the R training scripts:

- xpass:   nflverse-pbp/models/train_dropback_model.R (+ _dropback_model_data.R)
- fd:      nfl4th/data-raw/_go_for_it_and_2pt_models.R (go-for-it gain model)
- two_pt:  nfl4th/data-raw/_go_for_it_and_2pt_models.R (2-pt conversion model)
- fg:      nfl4th/data-raw/_punt_and_fg_models.R (mgcv bam -> XGBoost re-train)
- punt:    nfl4th/data-raw/_punt_and_fg_models.R (empirical landing distribution)

All XGBoost hyperparameters below are verbatim from those scripts. The feature
orders mirror the R ``select(...)`` order, which is the column order R's
``model.matrix(~.+0, ...)`` produces (and therefore the order the booster
expects). Era cuts + roof one-hots come from ``features.make_model_mutations``.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# xpass — binary:logistic dropback model
# ---------------------------------------------------------------------------
# Source: train_dropback_model.R. Data >=2006, label = pass (dropback 0/1).
XPASS_FEATURES: list[str] = [
    "down",
    "ydstogo",
    "yardline_100",
    "qtr",
    "wp",
    "vegas_wp",
    "era0",
    "era1",
    "era2",
    "era3",
    "era4",
    "score_differential",
    "home",
    "half_seconds_remaining",
    "posteam_timeouts_remaining",
    "defteam_timeouts_remaining",
    "outdoors",
    "retractable",
    "dome",
]

XPASS_HYPERPARAMS: dict = {
    "booster": "gbtree",
    "objective": "binary:logistic",
    # XGBoost's Python API takes a single eval_metric or a list; nflfastR used both.
    "eval_metric": ["error", "logloss"],
    "eta": 0.015,
    "gamma": 2.0,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "max_depth": 7,
    "min_child_weight": 0.9,
    # base_score = mean(label) is set dynamically by the trainer.
    "nrounds": 1121,
    "seed": 2013,
}

# ---------------------------------------------------------------------------
# fd_model — multi:softprob, 76 classes (go-for-it gain distribution)
# ---------------------------------------------------------------------------
# Source: _go_for_it_and_2pt_models.R. Data 2014:2019, label = yards_gained + 10.
FD_NUM_CLASSES: int = 76

FD_FEATURES: list[str] = [
    "down",
    "ydstogo",
    "yardline_100",
    "era0",
    "era1",
    "era2",
    "era3",
    "era4",
    "outdoors",
    "retractable",
    "dome",
    "posteam_spread",
    "total_line",
    "posteam_total",
]

FD_HYPERPARAMS: dict = {
    "booster": "gbtree",
    "objective": "multi:softprob",
    "num_class": FD_NUM_CLASSES,
    "eval_metric": "mlogloss",
    "eta": 0.01,
    "gamma": 2.0,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "max_depth": 2,
    "min_child_weight": 0.8,
    "nrounds": 1124,
    "seed": 2013,
}

# ---------------------------------------------------------------------------
# two_pt_model — binary:logistic (2-pt conversion success)
# ---------------------------------------------------------------------------
# Source: _go_for_it_and_2pt_models.R. Data 2010:2019, yardline_100 == 2.
TWO_PT_FEATURES: list[str] = [
    "era2",
    "era3",
    "era4",
    "outdoors",
    "retractable",
    "dome",
    "posteam_spread",
    "total_line",
    "posteam_total",
]

# monotone over the 9 features (posteam_spread + posteam_total constrained +1)
TWO_PT_MONOTONE_CONSTRAINTS: tuple[int, ...] = (0, 0, 0, 0, 0, 0, 1, 0, 1)

TWO_PT_HYPERPARAMS: dict = {
    "booster": "gbtree",
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "eta": 0.0576,
    "gamma": 0.0006930406,
    "subsample": 0.395,
    "colsample_bytree": 0.444,
    "max_depth": 8,
    "min_child_weight": 2,
    "nrounds": 21,
    "monotone_constraints": TWO_PT_MONOTONE_CONSTRAINTS,
    "seed": 2013,
}

# ---------------------------------------------------------------------------
# fg_model — NEW: binary:logistic XGBoost (was an mgcv bam GAM)
# ---------------------------------------------------------------------------
# Source: _punt_and_fg_models.R. Data 2014:current, play_type_nfl == "FIELD_GOAL".
# label = sp (field goal made 0/1). fg_model_roof = paste0(fg_roof, fg_era) where
# fg_roof = (roof == "outdoors"), fg_era = (season >= 2020). We one-hot the four
# levels {"00","01","10","11"} as fg_roof_outdoors x fg_era_2020 dummies.
FG_FEATURES: list[str] = [
    "yardline_100",
    "fg_roof",  # 1 if roof == "outdoors"
    "era0",  # full era one-hot (cuts 2001/2005/2013/2017) replaces the binary
    "era1",  # fg_era — the full-history fg is era-aware across all kicking eras,
    "era2",  # and the PAT path (fg @ yardline_100=15) reads the modern era.
    "era3",
    "era4",
]

# The FG make-probability curve is a smooth monotone decline in distance; the
# oracle was an mgcv spline. To make a step-function booster track that spline we
# keep stumps (max_depth=2), a low eta with many rounds, and a monotone
# decreasing constraint on yardline_100 (the parity lever — without it the booster
# wiggles and corr-vs-GAM caps ~0.97; with it it reaches ~0.985 on the FG range).
FG_MONOTONE_CONSTRAINTS: tuple[int, ...] = (-1, 0, 0, 0, 0, 0, 0)  # yardline_100 ↓, fg_roof, era0..era4

FG_HYPERPARAMS: dict = {
    "booster": "gbtree",
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "eta": 0.03,
    "gamma": 0.0,
    "subsample": 0.8,
    "colsample_bytree": 1.0,
    "max_depth": 2,
    "min_child_weight": 2,
    "nrounds": 3000,
    "monotone_constraints": FG_MONOTONE_CONSTRAINTS,
    "seed": 2013,
}

# Roof/era grid the oracle GAM was exported over (yardline_100 1..99 x 4 levels).
FG_ROOF_LEVELS: tuple[str, ...] = ("00", "01", "10", "11")

# The GAM grid spans yardline 1..99, but FG attempts only occur ~17-63 yards; a
# booster cannot reproduce the spline's extrapolation into never-observed
# yardlines. The parity comparison is scoped to this realistic range.
FG_VALIDATION_YARDLINE_RANGE: tuple[int, int] = (10, 63)

# ---------------------------------------------------------------------------
# wp_model — win probability (home-perspective), binary:logistic
# ---------------------------------------------------------------------------
# The converted oracle `wp_model.ubj` (sdv-py-stats nfl4th_artifacts/official) is
# the model `nfl4th::wp_model()` applies for 4th-down decisions — a HOME-team
# win-probability XGBoost (11 features incl. `home_ep` + `spread_time`), NOT
# nflfastR MODELS.R's possession-team `wp_model` (those are play_level's WP models).
#
# The feature contract is `nfl4th` `R/apply_win_prob.R::wp_model_select()` —
# `as.matrix()` column order (the duplicate `home_timeouts_remaining` collapses
# to one column, so the booster is 11-wide):
#   home_receive_2h_ko, spread_time, home_posteam, half_seconds_remaining,
#   game_seconds_remaining, Diff_Time_Ratio, home_score_differential, home_ep,
#   ydstogo, home_yardline_100, home_timeouts_remaining
#
# Home-perspective transforms (apply_win_prob.R `calculate_win_probability`):
#   home_score_differential = posteam==home ? score_differential : -score_differential
#   home_yardline_100       = posteam==home ? yardline_100       : 100 - yardline_100
#   home_ep                 = posteam==home ? ep                 : -ep
#   home_posteam            = (home_team == posteam) ? 1 : 0
#   spread_time             = spread_line * exp(-4 * elapsed_share)   # spread_line is home-perspective
#   Diff_Time_Ratio         = home_score_differential / exp(-4 * elapsed_share)
#   home_receive_2h_ko      = qtr<=2 & home opened with a kickoff (== first defteam)
#   home_timeouts_remaining = posteam==home ? posteam_timeouts : defteam_timeouts
#   label                   = (home_team == Winner)
#
# (`elapsed_share` matches play_level `_add_wp_aux`: (3600 - game_sec) / 3600.)
WP_FEATURES: list[str] = [
    "home_receive_2h_ko",
    "spread_time",
    "home_posteam",
    "half_seconds_remaining",
    "game_seconds_remaining",
    "Diff_Time_Ratio",
    "home_score_differential",
    "home_ep",
    "ydstogo",
    "home_yardline_100",
    "home_timeouts_remaining",
]

# Params follow play_level's WP family (binary:logistic, eta 0.025, max_depth 5,
# gamma 1, subsample/colsample 0.8); the nfl4th oracle is unconstrained. nrounds
# 500 maximizes corr-vs-oracle on the held-out slice (sweep 500-2000 all >=0.99;
# parity peaks at 500 then drifts as the booster overfits the frozen cal_data).
WP_HYPERPARAMS: dict = {
    "booster": "gbtree",
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "eta": 0.025,
    "gamma": 1.0,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "max_depth": 5,
    "min_child_weight": 1,
    "nrounds": 500,
    "seed": 2013,
}

# Default calibration-data source (guga31bb/metrics wp_tuning/cal_data.rds, the
# frozen frame nflfastR data-raw/MODELS.R + nfl4th read). Local copy committed
# under nflverse-pbp/models. It carries `ep` / `Winner` / `play_type`, which are
# not derivable from raw PBP without re-running the full EP pipeline.
WP_CAL_DATA_RDS: str = (
    r"C:/Users/saiem/Documents/GitHub-Data/sdv-dev/nflverse-dev/"
    r"nflverse-pbp/models/cal_data.rds"
)

# ---------------------------------------------------------------------------
# punt_data — empirical landing distribution (NOT a model)
# ---------------------------------------------------------------------------
PUNT_SEASONS_DEFAULT: tuple[int, int] = (2010, 2019)
PUNT_OUTPUT_COLUMNS: tuple[str, ...] = ("yardline_100", "yardline_after", "pct", "muff")
