"""Integration: native build satisfies Track 6's ingest contract (validate_pbp)."""
from __future__ import annotations

from pathlib import Path

import pytest

from model_training.play_level.ingest import REQUIRED_COLUMNS, validate_pbp
from native_pbp.build import build_season

RAW = Path(__file__).resolve().parents[2] / "nfl" / "raw" / "2024"
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not RAW.exists(), reason="2024 raw library not present"),
]

SAMPLE = ["2024_01_BAL_KC", "2024_01_GB_PHI"]


def test_build_season_subset_passes_validate_pbp():
    df = build_season(2024, game_ids=SAMPLE)
    assert df.height > 250          # two games' worth of plays
    assert set(df["game_id"].unique()) == set(SAMPLE)
    # The native frame must satisfy Track 6's REQUIRED_COLUMNS contract.
    validate_pbp(df)                # raises on any missing column / empty frame
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    assert not missing


def test_native_frame_dtypes_join_ready():
    # play_id must be castable to the int join key the parity harness uses.
    df = build_season(2024, game_ids=["2024_01_BAL_KC"])
    import polars as pl

    assert df.with_columns(pl.col("play_id").cast(pl.Int64)).height == df.height
