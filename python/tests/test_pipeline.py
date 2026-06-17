"""Tests for pipeline.py — training orchestrator.

All heavy work (download, label, train) is mocked so tests run instantly.
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import polars as pl
import pytest

import model_training.track6_nfl_ep_wp.pipeline as pipeline_mod
from model_training.track6_nfl_ep_wp.pipeline import (
    run_ep_pipeline,
    run_wp_pipeline,
    run_cp_pipeline,
    run_full_pipeline,
)
from model_training.track6_nfl_ep_wp.constants import (
    EP_FEATURES,
    WP_SPREAD_FEATURES,
    CP_FEATURES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ep_frame(n: int = 10) -> pl.DataFrame:
    """Minimal EP training frame with all EP_FEATURES + next_score_class."""
    import numpy as np
    rng = np.random.default_rng(0)
    data = {c: rng.uniform(0, 1, n).tolist() for c in EP_FEATURES}
    data["next_score_class"] = rng.integers(0, 7, n).tolist()
    return pl.DataFrame(data)


def _wp_frame(n: int = 10) -> pl.DataFrame:
    """Minimal WP training frame with WP_SPREAD_FEATURES + label."""
    import numpy as np
    rng = np.random.default_rng(0)
    data = {c: rng.uniform(0, 1, n).tolist() for c in WP_SPREAD_FEATURES}
    data["label"] = rng.integers(0, 2, n).astype(float).tolist()
    return pl.DataFrame(data)


def _cp_frame(n: int = 10) -> pl.DataFrame:
    """Minimal CP training frame with CP_FEATURES + complete_pass."""
    import numpy as np
    rng = np.random.default_rng(0)
    data = {c: rng.uniform(0, 1, n).tolist() for c in CP_FEATURES}
    data["complete_pass"] = rng.integers(0, 2, n).astype(float).tolist()
    return pl.DataFrame(data)


def _raw_pbp() -> pl.DataFrame:
    """Tiny synthetic raw PBP frame with all required columns."""
    from tests.test_ingest import _minimal_pbp
    return _minimal_pbp(n=20)


def _mock_booster():
    b = MagicMock()
    b.feature_names = EP_FEATURES
    return b


# ---------------------------------------------------------------------------
# run_ep_pipeline
# ---------------------------------------------------------------------------

class TestRunEpPipeline:
    def test_calls_load_local_pbp_when_no_download(self, tmp_path, monkeypatch):
        called = {}
        monkeypatch.setattr(pipeline_mod, "_load_pbp", lambda seasons, data_dir: (called.update({"seasons": seasons}) or _raw_pbp()))
        monkeypatch.setattr(pipeline_mod, "_build_ep", lambda df: _ep_frame())
        monkeypatch.setattr(pipeline_mod, "_train_ep", lambda df, output_path: _mock_booster())

        run_ep_pipeline([2024], data_dir=tmp_path, models_dir=tmp_path, download=False)
        assert called["seasons"] == [2024]

    def test_calls_download_when_download_true(self, tmp_path, monkeypatch):
        called = {}
        monkeypatch.setattr(pipeline_mod, "_download_pbp", lambda seasons, data_dir: called.update({"downloaded": True}) or [])
        monkeypatch.setattr(pipeline_mod, "_load_pbp", lambda seasons, data_dir: _raw_pbp())
        monkeypatch.setattr(pipeline_mod, "_build_ep", lambda df: _ep_frame())
        monkeypatch.setattr(pipeline_mod, "_train_ep", lambda df, output_path: _mock_booster())

        run_ep_pipeline([2024], data_dir=tmp_path, models_dir=tmp_path, download=True)
        assert called.get("downloaded")

    def test_model_saved_to_models_dir(self, tmp_path, monkeypatch):
        saved = {}
        def fake_train(df, output_path):
            saved["path"] = output_path
            return _mock_booster()

        monkeypatch.setattr(pipeline_mod, "_load_pbp", lambda seasons, data_dir: _raw_pbp())
        monkeypatch.setattr(pipeline_mod, "_build_ep", lambda df: _ep_frame())
        monkeypatch.setattr(pipeline_mod, "_train_ep", fake_train)

        run_ep_pipeline([2024], data_dir=tmp_path, models_dir=tmp_path, download=False)
        assert saved["path"] == tmp_path / "ep_model.ubj"

    def test_returns_booster_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pipeline_mod, "_load_pbp", lambda seasons, data_dir: _raw_pbp())
        monkeypatch.setattr(pipeline_mod, "_build_ep", lambda df: _ep_frame())
        monkeypatch.setattr(pipeline_mod, "_train_ep", lambda df, output_path: _mock_booster())

        result = run_ep_pipeline([2024], data_dir=tmp_path, models_dir=tmp_path, download=False)
        assert result == tmp_path / "ep_model.ubj"


# ---------------------------------------------------------------------------
# run_wp_pipeline
# ---------------------------------------------------------------------------

class TestRunWpPipeline:
    def test_spread_variant_saves_wp_spread_ubj(self, tmp_path, monkeypatch):
        saved = {}
        monkeypatch.setattr(pipeline_mod, "_load_pbp", lambda seasons, data_dir: _raw_pbp())
        monkeypatch.setattr(pipeline_mod, "_build_wp", lambda df, variant: _wp_frame())
        monkeypatch.setattr(pipeline_mod, "_train_wp_spread", lambda df, output_path: saved.update({"path": output_path}) or _mock_booster())
        monkeypatch.setattr(pipeline_mod, "_train_wp_naive", lambda df, output_path: _mock_booster())

        run_wp_pipeline([2024], variant="spread", data_dir=tmp_path, models_dir=tmp_path, download=False)
        assert saved["path"] == tmp_path / "wp_spread.ubj"

    def test_naive_variant_saves_wp_naive_ubj(self, tmp_path, monkeypatch):
        saved = {}
        monkeypatch.setattr(pipeline_mod, "_load_pbp", lambda seasons, data_dir: _raw_pbp())
        monkeypatch.setattr(pipeline_mod, "_build_wp", lambda df, variant: _wp_frame())
        monkeypatch.setattr(pipeline_mod, "_train_wp_spread", lambda df, output_path: _mock_booster())
        monkeypatch.setattr(pipeline_mod, "_train_wp_naive", lambda df, output_path: saved.update({"path": output_path}) or _mock_booster())

        run_wp_pipeline([2024], variant="naive", data_dir=tmp_path, models_dir=tmp_path, download=False)
        assert saved["path"] == tmp_path / "wp_naive.ubj"

    def test_returns_correct_path_for_each_variant(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pipeline_mod, "_load_pbp", lambda seasons, data_dir: _raw_pbp())
        monkeypatch.setattr(pipeline_mod, "_build_wp", lambda df, variant: _wp_frame())
        monkeypatch.setattr(pipeline_mod, "_train_wp_spread", lambda df, output_path: _mock_booster())
        monkeypatch.setattr(pipeline_mod, "_train_wp_naive", lambda df, output_path: _mock_booster())

        assert run_wp_pipeline([2024], variant="spread", data_dir=tmp_path, models_dir=tmp_path, download=False) == tmp_path / "wp_spread.ubj"
        assert run_wp_pipeline([2024], variant="naive", data_dir=tmp_path, models_dir=tmp_path, download=False) == tmp_path / "wp_naive.ubj"


# ---------------------------------------------------------------------------
# run_cp_pipeline
# ---------------------------------------------------------------------------

class TestRunCpPipeline:
    def test_saves_cp_model_ubj(self, tmp_path, monkeypatch):
        saved = {}
        monkeypatch.setattr(pipeline_mod, "_load_pbp", lambda seasons, data_dir: _raw_pbp())
        monkeypatch.setattr(pipeline_mod, "_build_cp", lambda df: _cp_frame())
        monkeypatch.setattr(pipeline_mod, "_train_cp", lambda df, output_path: saved.update({"path": output_path}) or _mock_booster())

        run_cp_pipeline([2024], data_dir=tmp_path, models_dir=tmp_path, download=False)
        assert saved["path"] == tmp_path / "cp_model.ubj"

    def test_returns_model_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pipeline_mod, "_load_pbp", lambda seasons, data_dir: _raw_pbp())
        monkeypatch.setattr(pipeline_mod, "_build_cp", lambda df: _cp_frame())
        monkeypatch.setattr(pipeline_mod, "_train_cp", lambda df, output_path: _mock_booster())

        result = run_cp_pipeline([2024], data_dir=tmp_path, models_dir=tmp_path, download=False)
        assert result == tmp_path / "cp_model.ubj"


# ---------------------------------------------------------------------------
# run_full_pipeline
# ---------------------------------------------------------------------------

class TestRunFullPipeline:
    def _patch_all(self, monkeypatch, tmp_path):
        monkeypatch.setattr(pipeline_mod, "_download_pbp", lambda seasons, data_dir: [])
        monkeypatch.setattr(pipeline_mod, "_load_pbp", lambda seasons, data_dir: _raw_pbp())
        monkeypatch.setattr(pipeline_mod, "_build_ep", lambda df: _ep_frame())
        monkeypatch.setattr(pipeline_mod, "_build_wp", lambda df, variant: _wp_frame())
        monkeypatch.setattr(pipeline_mod, "_build_cp", lambda df: _cp_frame())
        monkeypatch.setattr(pipeline_mod, "_train_ep", lambda df, output_path: _mock_booster())
        monkeypatch.setattr(pipeline_mod, "_train_wp_spread", lambda df, output_path: _mock_booster())
        monkeypatch.setattr(pipeline_mod, "_train_wp_naive", lambda df, output_path: _mock_booster())
        monkeypatch.setattr(pipeline_mod, "_train_cp", lambda df, output_path: _mock_booster())

    def test_returns_all_four_paths(self, tmp_path, monkeypatch):
        self._patch_all(monkeypatch, tmp_path)
        result = run_full_pipeline([2024], data_dir=tmp_path, models_dir=tmp_path)
        assert set(result.keys()) == {"ep", "wp_spread", "wp_naive", "cp"}

    def test_ep_path_points_to_models_dir(self, tmp_path, monkeypatch):
        self._patch_all(monkeypatch, tmp_path)
        result = run_full_pipeline([2024], data_dir=tmp_path, models_dir=tmp_path)
        assert result["ep"] == tmp_path / "ep_model.ubj"
        assert result["wp_spread"] == tmp_path / "wp_spread.ubj"
        assert result["wp_naive"] == tmp_path / "wp_naive.ubj"
        assert result["cp"] == tmp_path / "cp_model.ubj"

    def test_pbp_downloaded_once(self, tmp_path, monkeypatch):
        """PBP should be downloaded once and reused for all models."""
        download_calls = []
        monkeypatch.setattr(pipeline_mod, "_download_pbp", lambda seasons, data_dir: download_calls.append(seasons) or [])
        monkeypatch.setattr(pipeline_mod, "_load_pbp", lambda seasons, data_dir: _raw_pbp())
        monkeypatch.setattr(pipeline_mod, "_build_ep", lambda df: _ep_frame())
        monkeypatch.setattr(pipeline_mod, "_build_wp", lambda df, variant: _wp_frame())
        monkeypatch.setattr(pipeline_mod, "_build_cp", lambda df: _cp_frame())
        monkeypatch.setattr(pipeline_mod, "_train_ep", lambda df, output_path: _mock_booster())
        monkeypatch.setattr(pipeline_mod, "_train_wp_spread", lambda df, output_path: _mock_booster())
        monkeypatch.setattr(pipeline_mod, "_train_wp_naive", lambda df, output_path: _mock_booster())
        monkeypatch.setattr(pipeline_mod, "_train_cp", lambda df, output_path: _mock_booster())

        run_full_pipeline([2024], data_dir=tmp_path, models_dir=tmp_path, download=True)
        assert len(download_calls) == 1

    def test_models_dir_created_if_missing(self, tmp_path, monkeypatch):
        self._patch_all(monkeypatch, tmp_path)
        new_models = tmp_path / "new_models"
        run_full_pipeline([2024], data_dir=tmp_path, models_dir=new_models)
        assert new_models.is_dir()
