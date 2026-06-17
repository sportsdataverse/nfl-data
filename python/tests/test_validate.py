"""Tests for validate.py — EP/WP parity gate.

Uses deterministic synthetic data so no real models or nflverse data required.
"""
import math
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import polars as pl
import pytest

import model_training.track6_nfl_ep_wp.validate as val_mod
from model_training.track6_nfl_ep_wp.validate import (
    brier_score,
    pearson_correlation,
    validate_ep,
    validate_wp,
    run_parity_gate,
)
from model_training.track6_nfl_ep_wp.constants import EP_FEATURES, WP_SPREAD_FEATURES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ep_frame(n: int = 100) -> pl.DataFrame:
    rng = np.random.default_rng(42)
    data = {c: rng.uniform(0, 1, n).tolist() for c in EP_FEATURES}
    # nflfastR reference EP values in [-10, 10]
    data["ep"] = rng.uniform(-10, 10, n).tolist()
    return pl.DataFrame(data)


def _wp_frame(n: int = 100) -> pl.DataFrame:
    rng = np.random.default_rng(42)
    data = {c: rng.uniform(0, 1, n).tolist() for c in WP_SPREAD_FEATURES}
    data["wp"] = rng.uniform(0, 1, n).tolist()
    data["label"] = rng.integers(0, 2, n).astype(float).tolist()
    return pl.DataFrame(data)


def _mock_ep_model(predictions: np.ndarray):
    """Booster mock whose predict() returns a flat probability array."""
    m = MagicMock()
    # EP predict returns (N, 7) probabilities; we return a fixed array
    m.predict.return_value = predictions
    m.feature_names = list(EP_FEATURES)
    return m


def _mock_wp_model(predictions: np.ndarray):
    m = MagicMock()
    m.predict.return_value = predictions
    m.feature_names = list(WP_SPREAD_FEATURES)
    return m


# ---------------------------------------------------------------------------
# pearson_correlation
# ---------------------------------------------------------------------------

class TestPearsonCorrelation:
    def test_perfect_correlation(self):
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        assert abs(pearson_correlation(x, x) - 1.0) < 1e-9

    def test_perfect_negative_correlation(self):
        x = np.array([1.0, 2.0, 3.0])
        y = np.array([3.0, 2.0, 1.0])
        assert abs(pearson_correlation(x, y) - (-1.0)) < 1e-9

    def test_zero_correlation_returns_near_zero(self):
        rng = np.random.default_rng(0)
        x = rng.uniform(0, 1, 10_000)
        y = rng.uniform(0, 1, 10_000)
        assert abs(pearson_correlation(x, y)) < 0.05

    def test_returns_float_in_minus_one_to_one(self):
        rng = np.random.default_rng(1)
        x, y = rng.uniform(0, 1, 100), rng.uniform(0, 1, 100)
        r = pearson_correlation(x, y)
        assert -1.0 <= r <= 1.0


# ---------------------------------------------------------------------------
# brier_score
# ---------------------------------------------------------------------------

class TestBrierScore:
    def test_perfect_predictions_score_zero(self):
        y_true = np.array([1.0, 0.0, 1.0, 0.0])
        y_pred = np.array([1.0, 0.0, 1.0, 0.0])
        assert abs(brier_score(y_true, y_pred)) < 1e-9

    def test_worst_predictions_score_one(self):
        y_true = np.array([1.0, 0.0])
        y_pred = np.array([0.0, 1.0])
        assert abs(brier_score(y_true, y_pred) - 1.0) < 1e-9

    def test_all_half_predictions_score_quarter(self):
        y_true = np.array([1.0, 0.0, 1.0, 0.0])
        y_pred = np.full(4, 0.5)
        assert abs(brier_score(y_true, y_pred) - 0.25) < 1e-9

    def test_returns_value_in_zero_one(self):
        rng = np.random.default_rng(0)
        y_true = rng.integers(0, 2, 100).astype(float)
        y_pred = rng.uniform(0, 1, 100)
        bs = brier_score(y_true, y_pred)
        assert 0.0 <= bs <= 1.0


# ---------------------------------------------------------------------------
# validate_ep
# ---------------------------------------------------------------------------

class TestValidateEp:
    def test_returns_correlation_key(self, monkeypatch):
        df = _ep_frame()
        rng = np.random.default_rng(0)
        # Return perfect predictions (prob matrix N×7, argmax gives class)
        preds = np.zeros((len(df), 7))
        preds[:, 3] = 1.0  # all predict Field_Goal
        model = _mock_ep_model(preds)
        monkeypatch.setattr(val_mod, "_ep_expected_points", lambda probs: np.zeros(len(df)))
        result = validate_ep(model, df)
        assert "correlation" in result
        assert "n_plays" in result
        assert result["n_plays"] == len(df)

    def test_correlation_near_one_for_matching_predictions(self, monkeypatch):
        """When our EP matches nflfastR ep, correlation should be ~1."""
        df = _ep_frame(n=500)
        ref_ep = np.array(df["ep"].to_list())
        model = _mock_ep_model(np.zeros((len(df), 7)))  # raw probs (unused, we mock _ep_expected_points)
        monkeypatch.setattr(val_mod, "_ep_expected_points", lambda probs: ref_ep)

        result = validate_ep(model, df)
        assert result["correlation"] > 0.999

    def test_gate_pass_when_correlation_above_threshold(self, monkeypatch):
        df = _ep_frame(n=200)
        ref_ep = np.array(df["ep"].to_list())
        model = _mock_ep_model(np.zeros((len(df), 7)))
        monkeypatch.setattr(val_mod, "_ep_expected_points", lambda probs: ref_ep)

        result = validate_ep(model, df, correlation_threshold=0.98)
        assert result["gate_pass"] is True

    def test_gate_fail_when_correlation_below_threshold(self, monkeypatch):
        df = _ep_frame(n=200)
        rng = np.random.default_rng(99)
        model = _mock_ep_model(np.zeros((len(df), 7)))
        monkeypatch.setattr(val_mod, "_ep_expected_points", lambda probs: rng.uniform(-5, 5, len(df)))

        result = validate_ep(model, df, correlation_threshold=0.98)
        assert result["gate_pass"] is False


# ---------------------------------------------------------------------------
# validate_wp
# ---------------------------------------------------------------------------

class TestValidateWp:
    def test_returns_brier_and_gate(self):
        df = _wp_frame(n=200)
        rng = np.random.default_rng(0)
        y_true = np.array(df["label"].to_list())
        y_pred = y_true + rng.normal(0, 0.05, len(y_true))
        y_pred = np.clip(y_pred, 0, 1)
        model = _mock_wp_model(y_pred)
        result = validate_wp(model, df)
        assert "brier_score" in result
        assert "gate_pass" in result
        assert "n_plays" in result
        assert 0.0 <= result["brier_score"] <= 1.0

    def test_gate_pass_when_brier_below_threshold(self):
        df = _wp_frame(n=200)
        y_true = np.array(df["label"].to_list())
        # Near-perfect predictions → low Brier
        model = _mock_wp_model(y_true)
        result = validate_wp(model, df, brier_threshold=0.20)
        assert result["gate_pass"] is True

    def test_gate_fail_when_brier_above_threshold(self):
        df = _wp_frame(n=200)
        rng = np.random.default_rng(7)
        # Random predictions → Brier ~0.25
        model = _mock_wp_model(rng.uniform(0, 1, len(df)))
        result = validate_wp(model, df, brier_threshold=0.20)
        assert result["gate_pass"] is False


# ---------------------------------------------------------------------------
# run_parity_gate
# ---------------------------------------------------------------------------

class TestRunParityGate:
    def _setup(self, monkeypatch, ep_corr: float = 0.99, wp_brier: float = 0.15):
        monkeypatch.setattr(val_mod, "_load_model", lambda path: MagicMock())
        monkeypatch.setattr(val_mod, "_load_pbp_for_validation", lambda seasons, data_dir: (_ep_frame(), _wp_frame()))
        monkeypatch.setattr(val_mod, "validate_ep", lambda model, df, **kw: {"correlation": ep_corr, "gate_pass": ep_corr >= 0.98, "n_plays": 100})
        monkeypatch.setattr(val_mod, "validate_wp", lambda model, df, **kw: {"brier_score": wp_brier, "gate_pass": wp_brier <= 0.20, "n_plays": 100})

    def test_returns_overall_pass_when_both_gates_pass(self, tmp_path, monkeypatch):
        self._setup(monkeypatch, ep_corr=0.99, wp_brier=0.15)
        result = run_parity_gate(
            ep_model_path=tmp_path / "ep.ubj",
            wp_model_path=tmp_path / "wp.ubj",
            sample_seasons=[2022, 2023],
        )
        assert result["overall_pass"] is True

    def test_returns_overall_fail_when_ep_gate_fails(self, tmp_path, monkeypatch):
        self._setup(monkeypatch, ep_corr=0.95, wp_brier=0.15)
        result = run_parity_gate(
            ep_model_path=tmp_path / "ep.ubj",
            wp_model_path=tmp_path / "wp.ubj",
            sample_seasons=[2022, 2023],
        )
        assert result["overall_pass"] is False
        assert result["ep"]["gate_pass"] is False

    def test_returns_overall_fail_when_wp_gate_fails(self, tmp_path, monkeypatch):
        self._setup(monkeypatch, ep_corr=0.99, wp_brier=0.25)
        result = run_parity_gate(
            ep_model_path=tmp_path / "ep.ubj",
            wp_model_path=tmp_path / "wp.ubj",
            sample_seasons=[2022, 2023],
        )
        assert result["overall_pass"] is False
        assert result["wp"]["gate_pass"] is False

    def test_result_has_ep_and_wp_keys(self, tmp_path, monkeypatch):
        self._setup(monkeypatch)
        result = run_parity_gate(
            ep_model_path=tmp_path / "ep.ubj",
            wp_model_path=tmp_path / "wp.ubj",
            sample_seasons=[2023],
        )
        assert "ep" in result and "wp" in result
