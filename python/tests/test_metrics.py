"""Offline unit tests for the model reporting metrics + model card."""
from __future__ import annotations

import json

import numpy as np
import polars as pl

from model_training.track6_nfl_ep_wp.metrics import (
    brier_score,
    calibration_table,
    ep_expected_points,
    pearson_correlation,
    weighted_cal_error,
)
from model_training.track6_nfl_ep_wp.model_card import write_model_card


def test_calibration_table_binary_single_panel():
    # Perfectly calibrated: actual rate == bin centre.
    df = pl.DataFrame({
        "p": [0.1] * 20 + [0.5] * 20 + [0.9] * 20,
        "y": [0] * 18 + [1] * 2 + [0] * 10 + [1] * 10 + [0] * 2 + [1] * 18,
    })
    tbl = calibration_table(df, "p", "y", bin_size=0.1, min_plays=5)
    assert set(tbl.columns) == {"by", "bin", "n_plays", "actual"}
    assert tbl["by"].unique().to_list() == ["All"]
    # bin 0.1 -> actual 0.1, bin 0.5 -> 0.5, bin 0.9 -> 0.9
    row = {b: a for b, a in zip(tbl["bin"], tbl["actual"])}
    assert abs(row[0.1] - 0.1) < 1e-9 and abs(row[0.5] - 0.5) < 1e-9 and abs(row[0.9] - 0.9) < 1e-9


def test_calibration_table_faceted_renames_by():
    df = pl.DataFrame({
        "p": [0.2] * 20 + [0.8] * 20,
        "y": [0, 1] * 10 + [1] * 18 + [0] * 2,
        "bucket": ["Short"] * 20 + ["Deep"] * 20,
    })
    tbl = calibration_table(df, "p", "y", by="bucket", bin_size=0.1, min_plays=5)
    assert "by" in tbl.columns and "bucket" not in tbl.columns
    assert set(tbl["by"].unique()) == {"Short", "Deep"}


def test_weighted_cal_error_perfect_is_zero():
    tbl = pl.DataFrame({"by": ["All"] * 3, "bin": [0.2, 0.5, 0.8],
                        "n_plays": [100, 100, 100], "actual": [0.2, 0.5, 0.8]})
    res = weighted_cal_error(tbl)
    assert abs(res["overall"]) < 1e-9


def test_weighted_cal_error_weights_by_plays():
    tbl = pl.DataFrame({"by": ["All"] * 2, "bin": [0.5, 0.5],
                        "n_plays": [900, 100], "actual": [0.5, 0.6]})
    # |0.5-0.5|*900 + |0.5-0.6|*100 = 10 ; /1000 = 0.01
    assert abs(weighted_cal_error(tbl)["overall"] - 0.01) < 1e-9


def test_brier_and_pearson():
    assert brier_score(np.array([1, 0, 1]), np.array([1.0, 0.0, 1.0])) == 0.0
    assert abs(pearson_correlation(np.array([1.0, 2, 3]), np.array([2.0, 4, 6])) - 1.0) < 1e-9
    assert pearson_correlation(np.array([1.0, 1, 1]), np.array([1.0, 2, 3])) == 0.0


def test_ep_expected_points_shape_and_clamp():
    # 7-class probs -> EP scalar in [-10, 10]
    probs = np.eye(7)  # each row puts all mass on one class
    ep = ep_expected_points(probs)
    assert ep.shape == (7,)
    assert ep.min() >= -10.0 and ep.max() <= 10.0


def test_write_model_card(tmp_path):
    card_path = write_model_card(
        tmp_path / "ep_model.ubj",
        model_type="ep", features=["a", "b", "c"], label="next_score_class",
        seasons=[2019, 2024, 2021], n_rows=12345,
        hyperparams={"objective": "multi:softprob", "eta": 0.025},
        source="native", metrics={"cal_error": 0.3},
    )
    assert card_path.name == "ep_model.json"
    card = json.loads(card_path.read_text())
    assert card["model_type"] == "ep"
    assert card["n_features"] == 3
    assert card["training_seasons"] == [2019, 2024]  # min/max
    assert card["n_training_rows"] == 12345
    assert card["source"] == "native"
    assert card["objective"] == "multi:softprob"
    assert card["metrics"] == {"cal_error": 0.3}
    assert "trained_date" in card
