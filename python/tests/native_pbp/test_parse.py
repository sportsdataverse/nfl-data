"""Tests for the core Shield driveChart -> base play frame parser."""
from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from native_pbp.parse import (
    _clock_to_seconds,
    _game_half,
    _seconds_remaining,
    _yardline_100,
    parse_game,
)

GAME = Path(__file__).resolve().parents[2] / "nfl" / "raw" / "2024" / "2024_01_BAL_KC.json"
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not GAME.exists(), reason="2024_01_BAL_KC raw game not present"),
]


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def test_clock_to_seconds():
    assert _clock_to_seconds("15:00") == 900
    assert _clock_to_seconds("14:19") == 859
    assert _clock_to_seconds("0:03") == 3
    assert _clock_to_seconds(None) is None
    assert _clock_to_seconds("bad") is None


def test_yardline_100():
    assert _yardline_100("50", "KC") == 50
    assert _yardline_100("BAL 32", "BAL") == 68   # own 32 -> 68 to score
    assert _yardline_100("BAL 32", "KC") == 32     # opponent's 32 -> 32 to score
    assert _yardline_100("BAL 1", "KC") == 1
    assert _yardline_100(None, "KC") is None
    assert _yardline_100("BAL 32", None) is None


def test_seconds_remaining_quarters():
    assert _seconds_remaining(1, 900) == (1800, 3600)   # start of game
    assert _seconds_remaining(2, 0) == (0, 1800)         # end of 1st half
    assert _seconds_remaining(4, 0) == (0, 0)            # end of regulation
    assert _game_half(1) == "Half1" and _game_half(3) == "Half2" and _game_half(5) == "Overtime"


# ---------------------------------------------------------------------------
# Real-game parse
# ---------------------------------------------------------------------------

def _df():
    return parse_game(json.loads(GAME.read_text(encoding="utf-8")))


def test_frame_shape_and_game_id():
    df = _df()
    assert df.height > 130          # ~150+ non-deleted plays
    assert df["game_id"].unique().to_list() == ["2024_01_BAL_KC"]
    assert set(df["home_team"].unique()) == {"KC"}
    assert set(df["away_team"].unique()) == {"BAL"}


def test_possession_resolves_and_alternates():
    df = _df()
    # The opening drive is BAL (away); possession should cover both teams.
    pos = df.filter(pl.col("posteam").is_not_null())["posteam"].unique().to_list()
    assert set(pos) == {"BAL", "KC"}
    # First scrimmage play with a down belongs to BAL's opening drive.
    first = df.filter(pl.col("down").is_not_null()).head(1)
    assert first["posteam"][0] == "BAL"
    assert first["defteam"][0] == "KC"


def test_field_and_clock_bounds():
    df = _df()
    yl = df.filter(pl.col("yardline_100").is_not_null())["yardline_100"]
    assert yl.min() >= 1 and yl.max() <= 99
    gsr = df.filter(pl.col("game_seconds_remaining").is_not_null())["game_seconds_remaining"]
    assert gsr.min() >= 0 and gsr.max() <= 3600
    downs = set(df.filter(pl.col("down").is_not_null())["down"].unique().to_list())
    assert downs <= {1, 2, 3, 4}


def test_play_type_distribution():
    df = _df()
    pt = dict(df.group_by("play_type").len().iter_rows())
    assert pt.get("pass", 0) > 40
    assert pt.get("run", 0) > 40
    assert pt.get("field_goal", 0) >= 1
    assert pt.get("punt", 0) >= 1


def test_known_completion_play():
    df = _df()
    # L.Jackson 12-yd completion exists; check a completed pass row is coherent.
    comp = df.filter((pl.col("complete_pass") == 1) & (pl.col("passer_player_name") == "L.Jackson")).head(1)
    assert comp.height == 1
    assert comp["play_type"][0] == "pass"
    assert comp["posteam"][0] == "BAL"
    assert comp["air_yards"][0] is not None
