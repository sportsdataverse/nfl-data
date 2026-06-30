"""Hermetic tests for native_pbp.cli.build_season.

Uses a minimal synthetic game JSON that matches the Shield driveChart schema
just enough for parse_game to produce rows.  No real game files are needed.
"""
from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from native_pbp.cli import _parse_season_range, build_season, main


# ---------------------------------------------------------------------------
# Minimal synthetic Shield game payload
# ---------------------------------------------------------------------------

def _make_game(season: int = 2024, game_id: str = "2024_01_KC_BAL") -> dict:
    """Return a synthetic Shield game with 2 simple run plays.

    The homeTeam/awayTeam objects must carry a ``currentLogo`` URL whose trailing
    path segment is the club abbreviation (what _team_abbr() reads).
    """
    return {
        "season": season,
        "week": 1,
        "seasonType": "REG",
        "homeTeam": {
            "teamId": "home-uuid",
            "currentLogo": "https://static.nfl.com/clubs/logos/BAL",
        },
        "awayTeam": {
            "teamId": "away-uuid",
            "currentLogo": "https://static.nfl.com/clubs/logos/KC",
        },
        "summary": {
            "homeTeam": {"teamId": "home-uuid"},
            "awayTeam": {"teamId": "away-uuid"},
        },
        "driveChart": {
            "drives": [
                {
                    "teamId": "away-uuid",
                    "startedPlaySequenceNumber": 1,
                    "endedPlaySequenceNumber": 10,
                },
            ],
            "plays": [
                {
                    "playId": "p1",
                    "playSequenceNumber": 3,
                    "playType": "RUSH",
                    "quarter": 1,
                    "clockTime": "14:30",
                    "down": 1,
                    "yardsRemaining": 10,
                    "yardLine": "KC 35",
                    "yardsGained": 5,
                    "playIsGoalToGo": False,
                    "playDeleted": False,
                    "playScored": False,
                    "stats": [
                        {
                            "statType": 10,  # rush attempt
                            "yards": 5,
                            "gsisPlayerId": "00-0001234",
                            "gsisPlayerName": "Test Runner",
                            "teamId": "away-uuid",
                        }
                    ],
                },
                {
                    "playId": "p2",
                    "playSequenceNumber": 4,
                    "playType": "RUSH",
                    "quarter": 1,
                    "clockTime": "13:55",
                    "down": 2,
                    "yardsRemaining": 5,
                    "yardLine": "KC 30",
                    "yardsGained": 3,
                    "playIsGoalToGo": False,
                    "playDeleted": False,
                    "playScored": False,
                    "stats": [
                        {
                            "statType": 10,
                            "yards": 3,
                            "gsisPlayerId": "00-0001234",
                            "gsisPlayerName": "Test Runner",
                            "teamId": "away-uuid",
                        }
                    ],
                },
            ],
        },
    }


def _seed_raw_dir(tmp_path: Path, season: int = 2024) -> Path:
    """Write one synthetic game JSON into {tmp_path}/{season}/ and return raw_dir."""
    season_dir = tmp_path / str(season)
    season_dir.mkdir(parents=True)
    game = _make_game(season=season)
    (season_dir / f"{season}_01_KC_BAL.json").write_text(
        json.dumps(game), encoding="utf-8"
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_build_season_creates_parquet(tmp_path):
    raw_dir = _seed_raw_dir(tmp_path / "raw")
    out_dir = tmp_path / "out"

    out_path = build_season(2024, raw_dir=raw_dir, out_dir=out_dir)

    assert out_path.name == "model_pbp_2024.parquet"
    assert out_path.exists()
    df = pl.read_parquet(out_path)
    assert df.shape[0] > 0, "expected at least 1 play row"


def test_build_season_returns_path_with_correct_name(tmp_path):
    raw_dir = _seed_raw_dir(tmp_path / "raw", season=2023)
    out_dir = tmp_path / "out"
    out_path = build_season(2023, raw_dir=raw_dir, out_dir=out_dir)
    assert out_path.name == "model_pbp_2023.parquet"


def test_build_season_creates_out_dir_if_missing(tmp_path):
    raw_dir = _seed_raw_dir(tmp_path / "raw")
    out_dir = tmp_path / "nested" / "deep" / "out"
    assert not out_dir.exists()
    build_season(2024, raw_dir=raw_dir, out_dir=out_dir)
    assert out_dir.exists()


def test_build_season_empty_season_writes_empty_parquet(tmp_path):
    """Season dir with no games -> zero-row parquet (not an error)."""
    raw_dir = tmp_path / "raw"
    (raw_dir / "2024").mkdir(parents=True)
    out_dir = tmp_path / "out"
    out_path = build_season(2024, raw_dir=raw_dir, out_dir=out_dir)
    assert out_path.exists()
    df = pl.read_parquet(out_path)
    assert df.shape[0] == 0


def test_build_season_injects_schedule_lookup(tmp_path):
    """Betting lines from a schedule_lookup flow through to spread_line/total_line/roof.

    Guards the fix for the bug where the CLI never passed a schedule_lookup, leaving
    spread_line/total_line null and vegas_wp computed off a default spread.
    """
    raw_dir = _seed_raw_dir(tmp_path / "raw")
    out_dir = tmp_path / "out"
    lookup = {"2024_01_KC_BAL": {"roof": "dome", "spread_line": -3.5, "total_line": 44.5}}
    out_path = build_season(2024, raw_dir=raw_dir, out_dir=out_dir, schedule_lookup=lookup)
    df = pl.read_parquet(out_path)
    assert df["spread_line"].unique().to_list() == [-3.5]
    assert df["total_line"].unique().to_list() == [44.5]
    assert df["roof"].unique().to_list() == ["dome"]


def test_build_season_no_lookup_leaves_betting_lines_null(tmp_path):
    """Default (no schedule_lookup) leaves betting lines null — keeps unit tests hermetic."""
    raw_dir = _seed_raw_dir(tmp_path / "raw")
    out_dir = tmp_path / "out"
    out_path = build_season(2024, raw_dir=raw_dir, out_dir=out_dir)
    df = pl.read_parquet(out_path)
    assert df["spread_line"].null_count() == df.height
    assert df["total_line"].null_count() == df.height


def test_main_wires_schedule_lookup_into_build(tmp_path, monkeypatch):
    """main() builds the per-season schedule lookup and passes it to build_season."""
    raw_dir = _seed_raw_dir(tmp_path / "raw")
    out_dir = tmp_path / "out"
    sentinel = {"2024_01_KC_BAL": {"roof": "outdoors", "spread_line": 1.5, "total_line": 40.0}}
    monkeypatch.setattr("native_pbp.cli._build_schedule_lookup", lambda season: sentinel)
    captured = {}

    def _spy(season, *, raw_dir, out_dir, enrich=False, schedule_lookup=None):
        captured["schedule_lookup"] = schedule_lookup
        return Path(out_dir) / f"model_pbp_{season}.parquet"

    monkeypatch.setattr("native_pbp.cli.build_season", _spy)
    main(["build", "--seasons", "2024", "--raw-dir", str(raw_dir), "--out", str(out_dir)])
    assert captured["schedule_lookup"] is sentinel


def test_parse_season_range_single():
    assert _parse_season_range("2024") == [2024]


def test_parse_season_range_inclusive():
    assert _parse_season_range("2022:2024") == [2022, 2023, 2024]
