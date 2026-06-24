"""End-to-end native PBP build tests + REQUIRED_COLUMNS contract check."""
from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from model_training.play_level.ingest import REQUIRED_COLUMNS
from native_pbp.build import build_pbp

GAME = Path(__file__).resolve().parents[2] / "nfl" / "raw" / "2024" / "2024_01_BAL_KC.json"
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not GAME.exists(), reason="2024_01_BAL_KC raw game not present"),
]


def _df():
    game = json.loads(GAME.read_text(encoding="utf-8"))
    return build_pbp(game, roof="outdoors", spread_line=-3.0)


def test_required_columns_present():
    df = _df()
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    assert not missing, f"native PBP missing REQUIRED_COLUMNS: {missing}"


def test_score_differential_progression():
    df = _df()
    # Pre-snap on the very first scrimmage play, score is 0-0.
    first = df.filter(pl.col("down").is_not_null()).head(1)
    assert first["score_differential"][0] == 0
    # Score differential takes on multiple values over the game.
    assert df["score_differential"].n_unique() > 3


def test_timeouts_in_range():
    df = _df()
    for col in ("posteam_timeouts_remaining", "defteam_timeouts_remaining"):
        vals = df.filter(pl.col(col).is_not_null())[col]
        assert vals.min() >= 0 and vals.max() <= 3


def test_final_scores_and_result():
    df = _df()
    # KC (home) beat BAL (away) 27-20 in the 2024 opener.
    assert df["home_score"].unique().to_list() == [27]
    assert df["away_score"].unique().to_list() == [20]
    assert df["result"].unique().to_list() == [7]


def test_field_goal_result_and_roof_spread():
    df = _df()
    fg = set(df.filter(pl.col("field_goal_result").is_not_null())["field_goal_result"].unique().to_list())
    assert "made" in fg
    assert df["roof"].unique().to_list() == ["outdoors"]
    assert df["spread_line"].unique().to_list() == [-3.0]


def test_pass_location_populated_on_completions():
    df = _df()
    comp = df.filter(pl.col("complete_pass") == 1)
    locs = set(comp.filter(pl.col("pass_location").is_not_null())["pass_location"].unique().to_list())
    assert locs <= {"left", "middle", "right"}
    assert len(locs) >= 2  # a real game has passes to multiple locations
