"""Smoke tests for trainer.py — verify train functions produce valid .ubj artifacts.

These run with tiny synthetic data (no real PBP required). They are fast (<5s) and
serve as regression tests ensuring the XGBoost API contract stays stable.
"""
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from xgboost import Booster

from model_training.track6_nfl_ep_wp.constants import (
    EP_FEATURES,
    WP_SPREAD_FEATURES,
    WP_NAIVE_FEATURES,
    EP_NUM_CLASSES,
)
from model_training.track6_nfl_ep_wp.trainer import (
    train_ep,
    train_wp_spread,
    train_wp_naive,
)


RNG = np.random.default_rng(42)
N = 200  # small enough to be fast


def _ep_data() -> pl.DataFrame:
    """Random synthetic EP training frame."""
    rows = {feat: RNG.uniform(0.0, 1.0, N).tolist() for feat in EP_FEATURES}
    rows["next_score_class"] = RNG.integers(0, EP_NUM_CLASSES, N).tolist()
    rows["weight"] = RNG.uniform(0.5, 2.0, N).tolist()
    return pl.DataFrame(rows)


def _wp_data(include_spread: bool = True) -> pl.DataFrame:
    feats = WP_SPREAD_FEATURES if include_spread else WP_NAIVE_FEATURES
    rows = {feat: RNG.uniform(0.0, 1.0, N).tolist() for feat in feats}
    rows["label"] = RNG.integers(0, 2, N).tolist()
    return pl.DataFrame(rows)


# ---------------------------------------------------------------------------
# EP
# ---------------------------------------------------------------------------

class TestTrainEp:
    def test_returns_booster(self):
        model = train_ep(_ep_data(), nrounds=5)
        assert isinstance(model, Booster)

    def test_feature_names_match_contract(self):
        model = train_ep(_ep_data(), nrounds=5)
        assert model.feature_names == EP_FEATURES

    def test_saves_to_disk(self, tmp_path: Path):
        model = train_ep(_ep_data(), nrounds=5, output_path=tmp_path / "ep_model.ubj")
        assert (tmp_path / "ep_model.ubj").exists()

    def test_saved_model_loads_and_predicts(self, tmp_path: Path):
        train_ep(_ep_data(), nrounds=5, output_path=tmp_path / "ep_model.ubj")
        loaded = Booster()
        loaded.load_model(str(tmp_path / "ep_model.ubj"))
        assert loaded.feature_names == EP_FEATURES


# ---------------------------------------------------------------------------
# WP-spread
# ---------------------------------------------------------------------------

class TestTrainWpSpread:
    def test_returns_booster(self):
        model = train_wp_spread(_wp_data(include_spread=True), nrounds=5)
        assert isinstance(model, Booster)

    def test_feature_names_match_contract(self):
        model = train_wp_spread(_wp_data(include_spread=True), nrounds=5)
        assert model.feature_names == WP_SPREAD_FEATURES

    def test_saves_to_disk(self, tmp_path: Path):
        train_wp_spread(_wp_data(True), nrounds=5, output_path=tmp_path / "wp_spread.ubj")
        assert (tmp_path / "wp_spread.ubj").exists()


# ---------------------------------------------------------------------------
# WP-naive
# ---------------------------------------------------------------------------

class TestTrainWpNaive:
    def test_returns_booster(self):
        model = train_wp_naive(_wp_data(include_spread=False), nrounds=5)
        assert isinstance(model, Booster)

    def test_feature_names_match_contract(self):
        model = train_wp_naive(_wp_data(include_spread=False), nrounds=5)
        assert model.feature_names == WP_NAIVE_FEATURES

    def test_saves_to_disk(self, tmp_path: Path):
        train_wp_naive(_wp_data(False), nrounds=5, output_path=tmp_path / "wp_naive.ubj")
        assert (tmp_path / "wp_naive.ubj").exists()
