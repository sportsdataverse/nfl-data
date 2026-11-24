"""Hermetic tests for native_pbp.cli.build_season.

Uses a minimal synthetic game JSON that matches the Shield driveChart schema
just enough for parse_game to produce rows.  No real game files are needed.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest
from native_pbp.build import build_season as build_season_frame
from native_pbp.cli import (
    _GAME_COLUMNS,
    _add_jersey_numbers,
    _build_jersey_lookup,
    _build_schedule_lookup,
    _parse_season_range,
    build_season,
    main,
)

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
    (season_dir / f"{season}_01_KC_BAL.json").write_text(json.dumps(game), encoding="utf-8")
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
    # the fixture fills no tackle-for-loss / assist columns: written typed, never as Null (_type_null_columns)
    nulls = [
        c
        for c, t in df.schema.items()
        if t == pl.Null and c.endswith(("_id", "_name", "_team", "_yards"))
    ]
    assert not nulls, nulls


def test_build_season_stamps_processing_version(tmp_path):
    """The nfl_model_pbp manifest reads its row from this stamp, never from the uploader's env."""
    from nfl_espn_build.config import processing_version

    out_path = build_season(2024, raw_dir=_seed_raw_dir(tmp_path / "raw"), out_dir=tmp_path / "out")

    meta = pl.read_parquet_metadata(out_path)
    assert meta["processing_version"] == processing_version()
    assert meta["season"] == "2024"


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
    jerseys = pl.DataFrame({"gsis_id": ["x"], "week": [None], "jersey_number": [1]})
    monkeypatch.setattr("native_pbp.cli._build_jersey_lookup", lambda season: jerseys)
    captured = {}

    def _spy(season, *, raw_dir, out_dir, enrich=False, schedule_lookup=None, jersey_lookup=None):
        captured["schedule_lookup"] = schedule_lookup
        captured["jersey_lookup"] = jersey_lookup
        return Path(out_dir) / f"model_pbp_{season}.parquet"

    monkeypatch.setattr("native_pbp.cli.build_season", _spy)
    main(["build", "--seasons", "2024", "--raw-dir", str(raw_dir), "--out", str(out_dir)])
    assert captured["schedule_lookup"] is sentinel
    assert captured["jersey_lookup"] is jerseys


def test_build_season_adds_the_game_columns(tmp_path):
    """Schedule fields by game_id (stadium -> game_stadium, gameday -> game_date) and the
    payload's id / venue / weather / kickoff, rendered like nflverse's start_time."""
    season_dir = tmp_path / "raw" / "2024"
    season_dir.mkdir(parents=True)
    game = _make_game()
    game["id"] = "7d3e8f84-shield"
    game["venue"] = {"name": "M&T Bank Stadium"}
    game["summary"].update(
        startTime="2024-09-06T00:44:42.957Z", weather="Temp: 67° F,  Wind:   mph"
    )
    (season_dir / "2024_01_KC_BAL.json").write_text(json.dumps(game), encoding="utf-8")
    lookup = {
        "2024_01_KC_BAL": {
            "roof": "outdoors",
            "old_game_id": "2024090500",
            "gameday": "2024-09-05",
            "location": "Home",
            "total": 47,
            "div_game": 0,
            "stadium": "M&T Bank",
            "stadium_id": "BAL00",
        }
    }
    df = pl.read_parquet(
        build_season(2024, tmp_path / "raw", tmp_path / "out", schedule_lookup=lookup)
    )
    assert df.columns[-20:-4] == list(_GAME_COLUMNS)
    row = df.select(_GAME_COLUMNS).row(0, named=True)
    assert row["nfl_api_id"] == "7d3e8f84-shield" and row["old_game_id"] == "2024090500"
    assert row["start_time"] == "9/5/24, 20:44:42"  # US Eastern, seconds truncated
    assert row["weather"] == "Temp: 67° F, Wind: mph"
    assert (row["stadium"], row["game_stadium"]) == ("M&T Bank Stadium", "M&T Bank")
    assert (row["game_date"], row["total"], row["temp"]) == ("2024-09-05", 47, None)
    assert df.schema["total"] == pl.Int64 and df.schema["temp"] == pl.Int64


def test_jersey_numbers_join_on_gsis_id_and_week_then_the_season_roster():
    df = pl.DataFrame(
        {
            "game_id": ["g"] * 3,
            "week": [1, 2, 2],
            "passer_id": ["qb", "qb", None],
            "rusher_id": [None, None, "rb"],
            "receiver_id": ["wr", None, None],
        }
    )
    jerseys = pl.DataFrame(
        {
            "gsis_id": ["qb", "qb", "qb", "rb", "wr"],
            "week": [1, 2, None, None, None],  # null week = season roster (the fallback)
            "jersey_number": [8, 13, 13, 22, 11],
        }
    )
    out = _add_jersey_numbers(df, jerseys)
    assert out["passer_jersey_number"].to_list() == [8, 13, None]  # traded mid-season
    assert out["rusher_jersey_number"].to_list() == [None, None, 22]
    assert out["receiver_jersey_number"].to_list() == [11, None, None]
    assert out["jersey_number"].to_list() == [8, 13, 22]  # passer, else rusher
    assert _add_jersey_numbers(df, None)["jersey_number"].null_count() == 3


def test_an_ambiguous_weekly_jersey_stays_null_and_never_falls_back(monkeypatch):
    """Two numbers for one (player, week) leave it null; only a week the roster lacks falls back."""
    import sportsdataverse.nfl as nfl

    weekly = pl.DataFrame({"gsis_id": ["qb", "qb"], "week": [2, 2], "jersey_number": [8, 13]})
    season = pl.DataFrame({"gsis_id": ["qb"], "jersey_number": [13]})
    monkeypatch.setattr(nfl, "load_nfl_weekly_rosters", lambda s: weekly, raising=True)
    monkeypatch.setattr(nfl, "load_nfl_rosters", lambda s: season, raising=True)
    jerseys = _build_jersey_lookup(2024)
    df = pl.DataFrame(
        {
            "game_id": ["g", "g"],
            "week": [2, 3],
            "passer_id": ["qb", "qb"],
            "rusher_id": pl.Series([None, None], dtype=pl.String),
            "receiver_id": pl.Series([None, None], dtype=pl.String),
        }
    )
    out = _add_jersey_numbers(df, jerseys)
    assert out["passer_jersey_number"].to_list() == [None, 13]


def test_build_schedule_lookup_degrades_on_load_failure(monkeypatch):
    """A schedule-load failure degrades to {} with a RuntimeWarning — never fails the build."""

    def _boom(seasons):
        raise RuntimeError("network down")

    monkeypatch.setattr("sportsdataverse.nfl.load_nfl_schedule", _boom)
    with pytest.warns(RuntimeWarning, match="schedule lookup failed"):
        assert _build_schedule_lookup(2024) == {}


def test_parse_season_range_single():
    assert _parse_season_range("2024") == [2024]


def test_parse_season_range_inclusive():
    assert _parse_season_range("2022:2024") == [2022, 2023, 2024]


def test_build_season_skips_preseason_games(tmp_path):
    # nflverse pbp is REG + POST only; preseason once shipped in model_pbp_2026.
    season_dir = tmp_path / "raw" / "2024"
    season_dir.mkdir(parents=True)
    (season_dir / "2024_01_KC_BAL.json").write_text(json.dumps(_make_game()), encoding="utf-8")
    pre = {**_make_game(game_id="2024_PRE1_KC_BAL"), "seasonType": "PRE"}
    (season_dir / "2024_PRE1_KC_BAL.json").write_text(json.dumps(pre), encoding="utf-8")

    df = build_season_frame(2024, raw_dir=tmp_path / "raw")

    assert df["game_id"].unique().to_list() == ["2024_01_KC_BAL"]
