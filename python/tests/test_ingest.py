"""Tests for ingest.py — offline unit tests only (no real network calls).

The download_pbp function is tested via a monkeypatched load_nfl_pbp that returns
a small synthetic DataFrame, so these tests never hit the network.
"""
from pathlib import Path

import polars as pl
import pytest

from model_training.play_level.ingest import (
    validate_pbp,
    REQUIRED_COLUMNS,
)


def _minimal_pbp(n: int = 50) -> pl.DataFrame:
    """Return a synthetic PBP frame with all REQUIRED_COLUMNS present."""
    import numpy as np

    rng = np.random.default_rng(0)
    teams = ["KC", "BUF", "SF", "PHI"]
    roofs = ["outdoors", "dome", "retractable", "closed"]
    return pl.DataFrame(
        {
            "game_id": [f"2024_01_A_B_{i % 5}" for i in range(n)],
            "play_id": list(range(n)),
            "qtr": rng.integers(1, 5, n).tolist(),
            "down": rng.choice([1.0, 2.0, 3.0, 4.0, None], n).tolist(),
            "yardline_100": rng.uniform(1, 99, n).tolist(),
            "ydstogo": rng.uniform(1, 30, n).tolist(),
            "half_seconds_remaining": rng.uniform(0, 1800, n).tolist(),
            "game_seconds_remaining": rng.uniform(0, 3600, n).tolist(),
            "score_differential": rng.uniform(-28, 28, n).tolist(),
            "posteam_timeouts_remaining": rng.choice([0.0, 1.0, 2.0, 3.0], n).tolist(),
            "defteam_timeouts_remaining": rng.choice([0.0, 1.0, 2.0, 3.0], n).tolist(),
            "posteam": rng.choice(teams, n).tolist(),
            "defteam": rng.choice(teams, n).tolist(),
            "home_team": rng.choice(teams, n).tolist(),
            "season": [2024] * n,
            "roof": rng.choice(roofs, n).tolist(),
            "spread_line": rng.uniform(-14, 14, n).tolist(),
            "game_half": rng.choice(["Half1", "Half2"], n).tolist(),
            # scoring columns
            "sp": rng.integers(0, 2, n).tolist(),
            "touchdown": rng.integers(0, 2, n).tolist(),
            "td_team": rng.choice(teams, n).tolist(),
            "field_goal_result": rng.choice(["made", "missed", None], n).tolist(),
            "safety": rng.integers(0, 2, n).tolist(),
            "result": rng.choice([-10.0, 0.0, 7.0, 14.0], n).tolist(),
            "home_score": rng.integers(0, 50, n).tolist(),
            "away_score": rng.integers(0, 50, n).tolist(),
            # CP columns
            "air_yards": rng.uniform(-5, 50, n).tolist(),
            "pass_location": rng.choice(["left", "middle", "right", None], n).tolist(),
            "complete_pass": rng.integers(0, 2, n).tolist(),
            "incomplete_pass": rng.integers(0, 2, n).tolist(),
            "interception": rng.integers(0, 2, n).tolist(),
            "receiver_player_id": [f"id_{i}" for i in range(n)],
            "receiver_player_name": [f"P.Name{i}" for i in range(n)],
            "qb_hit": rng.integers(0, 2, n).tolist(),
        }
    )


class TestValidatePbp:
    def test_passes_on_complete_frame(self):
        validate_pbp(_minimal_pbp())  # should not raise

    def test_raises_on_missing_required_column(self):
        df = _minimal_pbp().drop("yardline_100")
        with pytest.raises(ValueError, match="yardline_100"):
            validate_pbp(df)

    def test_raises_on_zero_rows(self):
        df = _minimal_pbp().clear()
        with pytest.raises(ValueError, match="empty"):
            validate_pbp(df)

    def test_required_columns_covers_ep_source(self):
        ep_needed = {
            "yardline_100", "ydstogo", "down",
            "posteam_timeouts_remaining", "defteam_timeouts_remaining",
            "season", "roof", "posteam", "home_team",
            "half_seconds_remaining", "game_seconds_remaining",
        }
        assert ep_needed <= set(REQUIRED_COLUMNS)

    def test_required_columns_covers_wp_source(self):
        wp_needed = {"spread_line", "score_differential", "qtr", "game_half", "defteam", "game_id"}
        assert wp_needed <= set(REQUIRED_COLUMNS)

    def test_required_columns_covers_label_source(self):
        label_needed = {"sp", "touchdown", "td_team", "field_goal_result", "safety",
                        "result", "home_score", "away_score", "play_id"}
        assert label_needed <= set(REQUIRED_COLUMNS)


class TestDownloadPbpMocked:
    def test_download_saves_parquet(self, tmp_path: Path, monkeypatch):
        import model_training.play_level.ingest as ingest_mod

        monkeypatch.setattr(ingest_mod, "_load_nfl_pbp", lambda seasons, **kw: _minimal_pbp())
        from model_training.play_level.ingest import download_pbp

        download_pbp([2024], output_dir=tmp_path)
        assert (tmp_path / "pbp_2024.parquet").exists()

    def test_download_validates_on_load(self, tmp_path: Path, monkeypatch):
        import model_training.play_level.ingest as ingest_mod

        # Return a frame missing a required column
        bad = _minimal_pbp().drop("game_id")
        monkeypatch.setattr(ingest_mod, "_load_nfl_pbp", lambda seasons, **kw: bad)
        from model_training.play_level.ingest import download_pbp

        with pytest.raises(ValueError, match="game_id"):
            download_pbp([2024], output_dir=tmp_path)
