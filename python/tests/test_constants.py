"""Failing tests for play_level.constants — run BEFORE implementing constants.py.

These tests lock the NFL EP/WP/CP feature contracts derived from:
  fastrmodels/data-raw/MODELS.R + nflfastR/R/helper_add_ep_wp.R + helper_add_cp_cpoe.R
"""
import pytest

from model_training.play_level.constants import (
    EP_FEATURES,
    EP_HYPERPARAMS,
    WP_SPREAD_FEATURES,
    WP_SPREAD_HYPERPARAMS,
    WP_SPREAD_MONOTONE_CONSTRAINTS,
    WP_NAIVE_FEATURES,
    WP_NAIVE_HYPERPARAMS,
    CP_FEATURES,
    CP_HYPERPARAMS,
    EP_NUM_CLASSES,
    EP_LABEL_TO_SCORE,
)


# ---------------------------------------------------------------------------
# EP contract
# ---------------------------------------------------------------------------

def test_ep_features_length():
    assert len(EP_FEATURES) == 18


def test_ep_features_exact_order():
    """Order matters — XGBoost stores feature names in DMatrix column order."""
    expected = [
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
    assert EP_FEATURES == expected


def test_ep_num_classes():
    assert EP_NUM_CLASSES == 7


def test_ep_label_to_score_keys():
    assert set(EP_LABEL_TO_SCORE.keys()) == {
        "Touchdown",
        "Opp_Touchdown",
        "Field_Goal",
        "Opp_Field_Goal",
        "Safety",
        "Opp_Safety",
        "No_Score",
    }


def test_ep_label_to_score_values():
    mapping = EP_LABEL_TO_SCORE
    assert mapping["Touchdown"] == 7.0
    assert mapping["Opp_Touchdown"] == -7.0
    assert mapping["Field_Goal"] == 3.0
    assert mapping["Opp_Field_Goal"] == -3.0
    assert mapping["Safety"] == 2.0
    assert mapping["Opp_Safety"] == -2.0
    assert mapping["No_Score"] == 0.0


def test_ep_hyperparams_keys():
    required = {
        "objective", "num_class", "eval_metric",
        "eta", "gamma", "subsample", "colsample_bytree",
        "max_depth", "min_child_weight", "nrounds", "seed",
    }
    assert required <= set(EP_HYPERPARAMS.keys())


def test_ep_hyperparams_values():
    p = EP_HYPERPARAMS
    assert p["objective"] == "multi:softprob"
    assert p["num_class"] == 7
    assert p["eta"] == pytest.approx(0.025)
    assert p["gamma"] == pytest.approx(1.0)
    assert p["subsample"] == pytest.approx(0.8)
    assert p["colsample_bytree"] == pytest.approx(0.8)
    assert p["max_depth"] == 5
    assert p["min_child_weight"] == 1
    assert p["nrounds"] == 525
    assert p["seed"] == 2013


# ---------------------------------------------------------------------------
# WP-spread contract
# ---------------------------------------------------------------------------

def test_wp_spread_features_length():
    assert len(WP_SPREAD_FEATURES) == 12


def test_wp_spread_features_exact_order():
    expected = [
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
    assert WP_SPREAD_FEATURES == expected


def test_wp_spread_monotone_constraints_length():
    """12 features → 12 constraint values."""
    assert len(WP_SPREAD_MONOTONE_CONSTRAINTS) == 12


def test_wp_spread_monotone_constraints_values():
    # (0,0,0,0,0,1,1,-1,-1,-1,1,-1)
    expected = (0, 0, 0, 0, 0, 1, 1, -1, -1, -1, 1, -1)
    assert tuple(WP_SPREAD_MONOTONE_CONSTRAINTS) == expected


def test_wp_spread_hyperparams_values():
    p = WP_SPREAD_HYPERPARAMS
    assert p["objective"] == "binary:logistic"
    assert p["eta"] == pytest.approx(0.05)
    assert p["gamma"] == pytest.approx(0.79012017)
    assert abs(p["subsample"] - 0.9224245) < 1e-6
    assert abs(p["colsample_bytree"] - 5 / 12) < 1e-9
    assert p["max_depth"] == 5
    assert p["min_child_weight"] == 7
    assert p["nrounds"] == 534


# ---------------------------------------------------------------------------
# WP-naive contract
# ---------------------------------------------------------------------------

def test_wp_naive_features_length():
    assert len(WP_NAIVE_FEATURES) == 11


def test_wp_naive_features_excludes_spread_time():
    assert "spread_time" not in WP_NAIVE_FEATURES


def test_wp_naive_features_subset_of_spread():
    # naive = spread minus spread_time
    assert set(WP_NAIVE_FEATURES) == set(WP_SPREAD_FEATURES) - {"spread_time"}


def test_wp_naive_hyperparams_values():
    p = WP_NAIVE_HYPERPARAMS
    assert p["objective"] == "binary:logistic"
    assert p["eta"] == pytest.approx(0.2)
    assert p["gamma"] == pytest.approx(0.0)
    assert p["subsample"] == pytest.approx(0.8)
    assert p["colsample_bytree"] == pytest.approx(0.8)
    assert p["max_depth"] == 4
    assert p["min_child_weight"] == 1
    assert p["nrounds"] == 65


# ---------------------------------------------------------------------------
# CP contract
# ---------------------------------------------------------------------------

def test_cp_features_length():
    # air_yards, yardline_100, ydstogo, down1-4, air_is_zero, pass_middle,
    # era2-4, qb_hit, home, outdoors, retractable, dome, distance_to_sticks = 18
    # (complete_pass is the label; valid_pass is the filter — neither is a feature)
    assert len(CP_FEATURES) == 18


def test_cp_features_contains_required():
    required = {
        "air_yards", "yardline_100", "ydstogo",
        "down1", "down2", "down3", "down4",
        "air_is_zero", "pass_middle",
        "era2", "era3", "era4",
        "qb_hit", "home",
        "outdoors", "retractable", "dome",
        "distance_to_sticks",
    }
    # distance_to_sticks is 18th — CP has 17 excluding valid_pass
    assert set(CP_FEATURES) == required - {"distance_to_sticks"} | {"distance_to_sticks"}


def test_cp_hyperparams_values():
    p = CP_HYPERPARAMS
    assert p["objective"] == "binary:logistic"
    assert p["eta"] == pytest.approx(0.025)
    assert p["gamma"] == pytest.approx(5.0)
    assert p["max_depth"] == 4
    assert p["min_child_weight"] == 6
    assert p["nrounds"] == 560
