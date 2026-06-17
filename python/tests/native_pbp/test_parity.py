"""Parity gate: native reconstruction vs nflverse load_nfl_pbp.

Gated by NFL_PARITY_TESTS=1 (downloads a season of nflverse PBP). Run with:
    NFL_PARITY_TESTS=1 uv run pytest tests/native_pbp/test_parity.py -v
"""
from __future__ import annotations

import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("NFL_PARITY_TESTS") != "1",
        reason="set NFL_PARITY_TESTS=1 to run (downloads nflverse PBP)",
    ),
]

SAMPLE_GAMES = [
    "2024_01_BAL_KC",
    "2024_01_GB_PHI",
    "2024_05_NO_KC",
    "2024_22_KC_PHI",  # Super Bowl LIX
]

# Minimum acceptable per-column match rate across the sample.
THRESHOLDS = {
    "down": 1.0,
    "ydstogo": 1.0,
    "yardline_100": 1.0,
    "qtr": 1.0,
    "complete_pass": 1.0,
    "pass_attempt": 1.0,
    "rush_attempt": 1.0,
    "air_yards": 1.0,
    "posteam_timeouts_remaining": 0.99,
    "defteam_timeouts_remaining": 0.99,
    "score_differential": 0.99,  # per-play points stepping -> exact on the BAL_KC anchor
    "touchdown": 1.0,
}


def test_parity_sample_games():
    from native_pbp.parity import run_parity

    report = run_parity(2024, game_ids=SAMPLE_GAMES)
    assert report["games"], "no games compared — raw files or nflverse missing"

    agg = report["aggregate"]
    failures = []
    for col, floor in THRESHOLDS.items():
        rate = agg.get(col)
        if rate is None:
            failures.append(f"{col}: no comparable rows")
        elif rate < floor:
            failures.append(f"{col}: {rate:.3f} < {floor}")
    assert not failures, "parity below threshold:\n  " + "\n  ".join(failures)
