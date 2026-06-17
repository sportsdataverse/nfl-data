"""Gated end-to-end: train Track 6 models off the native nfl/raw library.

Offline (use_schedule=False -> no network), but builds a full season, so it is
gated by NFL_PARITY_TESTS=1 to keep the default suite fast. Run with:
    NFL_PARITY_TESTS=1 uv run pytest tests/native_pbp/test_native_training.py -v
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("NFL_PARITY_TESTS") != "1",
        reason="set NFL_PARITY_TESTS=1 to run (builds a full season + trains models)",
    ),
]


def test_native_training_produces_models(tmp_path):
    from model_training.track6_nfl_ep_wp.ingest import load_native_pbp
    from model_training.track6_nfl_ep_wp.label import (
        build_cp_training_set,
        build_ep_training_set,
        build_wp_training_set,
    )
    from model_training.track6_nfl_ep_wp.trainer import (
        train_cp,
        train_ep,
        train_wp_naive,
    )

    # Offline native build (roof/spread null without the schedule join).
    df = load_native_pbp([2023], use_schedule=False)
    assert df.height > 30000, f"unexpectedly small native season: {df.height}"

    ep_path = tmp_path / "ep.ubj"
    wp_path = tmp_path / "wp_naive.ubj"
    cp_path = tmp_path / "cp.ubj"

    train_ep(build_ep_training_set(df), output_path=ep_path)
    train_wp_naive(build_wp_training_set(df, variant="naive"), output_path=wp_path)
    train_cp(build_cp_training_set(df), output_path=cp_path)

    for p in (ep_path, wp_path, cp_path):
        assert Path(p).exists() and Path(p).stat().st_size > 0, f"missing/empty model: {p}"
