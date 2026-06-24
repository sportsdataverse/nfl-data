"""Tests for fetcher.py — NFL API raw JSON file library builder.

All tests use monkeypatching to avoid real network calls.
The NFL Shield API (api.nfl.com) requires a bearer token; these tests never
touch the network.
"""
import json
from pathlib import Path

import pytest

from model_training.play_level.fetcher import (
    build_raw_library,
    extract_game_ids_from_weekly,
    list_season_weeks,
)


# ---------------------------------------------------------------------------
# Helpers — synthetic API responses
# ---------------------------------------------------------------------------

def _weeks_payload(week_nums: list[int]) -> dict:
    """Synthetic nfl_weeks raw JSON: {weeks: [{week: N, ...}, ...]}."""
    return {"weeks": [{"week": n, "weekType": "REG", "season": 2024} for n in week_nums]}


def _weekly_details_payload(game_ids: list[str], week: int = 1) -> list:
    """Synthetic nfl_weekly_game_details raw JSON: bare list of game dicts."""
    return [{"id": gid, "week": week, "season": 2024, "homeTeam": {}, "awayTeam": {}} for gid in game_ids]


# ---------------------------------------------------------------------------
# list_season_weeks
# ---------------------------------------------------------------------------

class TestListSeasonWeeks:
    def test_returns_sorted_week_numbers(self, monkeypatch):
        import model_training.play_level.fetcher as mod
        monkeypatch.setattr(mod, "_list_weeks", lambda season, season_type, headers=None: _weeks_payload([3, 1, 2]))
        assert list_season_weeks(2024, "REG") == [1, 2, 3]

    def test_eighteen_regular_season_weeks(self, monkeypatch):
        import model_training.play_level.fetcher as mod
        monkeypatch.setattr(mod, "_list_weeks", lambda season, season_type, headers=None: _weeks_payload(list(range(1, 19))))
        weeks = list_season_weeks(2024, "REG")
        assert len(weeks) == 18
        assert weeks[0] == 1
        assert weeks[-1] == 18

    def test_postseason_weeks(self, monkeypatch):
        import model_training.play_level.fetcher as mod
        monkeypatch.setattr(mod, "_list_weeks", lambda season, season_type, headers=None: _weeks_payload([1, 2, 3, 4]))
        weeks = list_season_weeks(2024, "POST")
        assert weeks == [1, 2, 3, 4]

    def test_empty_weeks_returns_empty_list(self, monkeypatch):
        import model_training.play_level.fetcher as mod
        monkeypatch.setattr(mod, "_list_weeks", lambda season, season_type, headers=None: {"weeks": []})
        assert list_season_weeks(2024, "REG") == []

    def test_weeks_missing_key_returns_empty_list(self, monkeypatch):
        import model_training.play_level.fetcher as mod
        monkeypatch.setattr(mod, "_list_weeks", lambda season, season_type, headers=None: {})
        assert list_season_weeks(2024, "REG") == []

    def test_passes_season_and_type_to_underlying(self, monkeypatch):
        import model_training.play_level.fetcher as mod
        calls: list[tuple] = []
        def spy(season, season_type, headers=None):
            calls.append((season, season_type))
            return _weeks_payload([1])
        monkeypatch.setattr(mod, "_list_weeks", spy)
        list_season_weeks(2023, "POST")
        assert calls == [(2023, "POST")]


# ---------------------------------------------------------------------------
# extract_game_ids_from_weekly
# ---------------------------------------------------------------------------

class TestExtractGameIdsFromWeekly:
    def test_extracts_id_field(self):
        payload = [{"id": "abc-123"}, {"id": "def-456"}]
        assert extract_game_ids_from_weekly(payload) == ["abc-123", "def-456"]

    def test_extracts_nfl_id_field(self):
        payload = [{"nflId": "ghi-789"}]
        assert extract_game_ids_from_weekly(payload) == ["ghi-789"]

    def test_extracts_game_id_field(self):
        payload = [{"gameId": "jkl-012"}]
        assert extract_game_ids_from_weekly(payload) == ["jkl-012"]

    def test_id_takes_priority_over_nfl_id(self):
        payload = [{"id": "primary", "nflId": "secondary"}]
        assert extract_game_ids_from_weekly(payload) == ["primary"]

    def test_skips_games_with_no_id(self):
        payload = [{"homeTeam": "KC"}, {"id": "valid-id"}]
        assert extract_game_ids_from_weekly(payload) == ["valid-id"]

    def test_empty_list_returns_empty(self):
        assert extract_game_ids_from_weekly([]) == []

    def test_dict_payload_games_key(self):
        payload = {"games": [{"id": "g1"}, {"id": "g2"}]}
        assert extract_game_ids_from_weekly(payload) == ["g1", "g2"]

    def test_dict_payload_data_key_fallback(self):
        payload = {"data": [{"id": "g3"}]}
        assert extract_game_ids_from_weekly(payload) == ["g3"]

    def test_ids_are_strings(self):
        payload = [{"id": 12345}]
        result = extract_game_ids_from_weekly(payload)
        assert result == ["12345"]
        assert all(isinstance(gid, str) for gid in result)


# ---------------------------------------------------------------------------
# build_raw_library
# ---------------------------------------------------------------------------

class TestBuildRawLibrary:
    def _setup(self, monkeypatch, week_nums: list[int], game_ids: list[str]):
        import model_training.play_level.fetcher as mod
        monkeypatch.setattr(
            mod, "_list_weeks",
            lambda season, season_type, headers=None: _weeks_payload(week_nums),
        )
        monkeypatch.setattr(
            mod, "_fetch_weekly_details",
            lambda season, season_type, week, headers=None: _weekly_details_payload(game_ids, week),
        )

    def test_creates_output_directory(self, tmp_path, monkeypatch):
        self._setup(monkeypatch, [1], ["g1"])
        build_raw_library([2024], output_dir=tmp_path, season_types=["REG"])
        assert (tmp_path / "2024" / "REG").is_dir()

    def test_writes_one_file_per_week(self, tmp_path, monkeypatch):
        self._setup(monkeypatch, [1, 2, 3], ["g1"])
        paths = build_raw_library([2024], output_dir=tmp_path, season_types=["REG"])
        assert len(paths) == 3
        assert (tmp_path / "2024" / "REG" / "wk01.json").exists()
        assert (tmp_path / "2024" / "REG" / "wk03.json").exists()

    def test_file_contains_valid_json(self, tmp_path, monkeypatch):
        self._setup(monkeypatch, [1], ["game-abc"])
        build_raw_library([2024], output_dir=tmp_path, season_types=["REG"])
        text = (tmp_path / "2024" / "REG" / "wk01.json").read_text(encoding="utf-8")
        payload = json.loads(text)
        assert isinstance(payload, list)
        assert payload[0]["id"] == "game-abc"

    def test_file_named_with_two_digit_week(self, tmp_path, monkeypatch):
        self._setup(monkeypatch, [5, 14], ["g1"])
        build_raw_library([2024], output_dir=tmp_path, season_types=["REG"])
        assert (tmp_path / "2024" / "REG" / "wk05.json").exists()
        assert (tmp_path / "2024" / "REG" / "wk14.json").exists()

    def test_resume_skips_existing_files(self, tmp_path, monkeypatch):
        fetch_calls: list[tuple] = []
        import model_training.play_level.fetcher as mod
        monkeypatch.setattr(
            mod, "_list_weeks",
            lambda season, season_type, headers=None: _weeks_payload([1, 2]),
        )
        def tracking_fetch(season, season_type, week, headers=None):
            fetch_calls.append((season, season_type, week))
            return _weekly_details_payload(["g1"], week)
        monkeypatch.setattr(mod, "_fetch_weekly_details", tracking_fetch)

        # Pre-create wk01.json
        week_dir = tmp_path / "2024" / "REG"
        week_dir.mkdir(parents=True)
        (week_dir / "wk01.json").write_text("[]")

        build_raw_library([2024], output_dir=tmp_path, season_types=["REG"], resume=True)
        fetched_weeks = [c[2] for c in fetch_calls]
        assert 1 not in fetched_weeks  # skipped
        assert 2 in fetched_weeks  # fetched

    def test_no_resume_overwrites_existing(self, tmp_path, monkeypatch):
        import model_training.play_level.fetcher as mod
        monkeypatch.setattr(
            mod, "_list_weeks",
            lambda season, season_type, headers=None: _weeks_payload([1]),
        )
        monkeypatch.setattr(
            mod, "_fetch_weekly_details",
            lambda season, season_type, week, headers=None: [{"id": "new-game"}],
        )
        week_dir = tmp_path / "2024" / "REG"
        week_dir.mkdir(parents=True)
        (week_dir / "wk01.json").write_text('[{"id": "old-game"}]')

        build_raw_library([2024], output_dir=tmp_path, season_types=["REG"], resume=False)
        payload = json.loads((week_dir / "wk01.json").read_text())
        assert payload[0]["id"] == "new-game"

    def test_multiple_seasons_all_written(self, tmp_path, monkeypatch):
        self._setup(monkeypatch, [1], ["g1"])
        build_raw_library([2022, 2023, 2024], output_dir=tmp_path, season_types=["REG"])
        for year in [2022, 2023, 2024]:
            assert (tmp_path / str(year) / "REG" / "wk01.json").exists()

    def test_multiple_season_types(self, tmp_path, monkeypatch):
        self._setup(monkeypatch, [1], ["g1"])
        build_raw_library([2024], output_dir=tmp_path, season_types=["REG", "POST"])
        assert (tmp_path / "2024" / "REG" / "wk01.json").exists()
        assert (tmp_path / "2024" / "POST" / "wk01.json").exists()

    def test_returns_list_of_written_paths(self, tmp_path, monkeypatch):
        self._setup(monkeypatch, [1, 2], ["g1"])
        paths = build_raw_library([2024], output_dir=tmp_path, season_types=["REG"])
        assert all(isinstance(p, Path) for p in paths)
        assert all(p.exists() for p in paths)

    def test_empty_weeks_writes_nothing(self, tmp_path, monkeypatch):
        import model_training.play_level.fetcher as mod
        monkeypatch.setattr(
            mod, "_list_weeks",
            lambda season, season_type, headers=None: {"weeks": []},
        )
        paths = build_raw_library([2024], output_dir=tmp_path, season_types=["REG"])
        assert paths == []

    def test_default_output_dir_is_data_raw(self, tmp_path, monkeypatch):
        """Confirm the default output_dir keyword default is Path('data/raw')."""
        import model_training.play_level.fetcher as mod
        import inspect
        sig = inspect.signature(mod.build_raw_library)
        default = sig.parameters["output_dir"].default
        assert Path(default) == Path("data/raw")


# ---------------------------------------------------------------------------
# Manifest / load helpers
# ---------------------------------------------------------------------------

class TestLoadWeeklyRaw:
    """load_weekly_raw reads a stored JSON file back from disk."""

    def test_round_trip_list_payload(self, tmp_path):
        from model_training.play_level.fetcher import load_weekly_raw
        path = tmp_path / "wk01.json"
        original = [{"id": "g1", "week": 1}]
        path.write_text(json.dumps(original))
        loaded = load_weekly_raw(path)
        assert loaded == original

    def test_round_trip_dict_payload(self, tmp_path):
        from model_training.play_level.fetcher import load_weekly_raw
        path = tmp_path / "wk01.json"
        original = {"games": [{"id": "g1"}]}
        path.write_text(json.dumps(original))
        loaded = load_weekly_raw(path)
        assert loaded == original

    def test_raises_file_not_found(self, tmp_path):
        from model_training.play_level.fetcher import load_weekly_raw
        with pytest.raises(FileNotFoundError):
            load_weekly_raw(tmp_path / "does_not_exist.json")


class TestListLibraryFiles:
    """list_library_files enumerates stored week files for a season."""

    def test_finds_all_week_files(self, tmp_path):
        from model_training.play_level.fetcher import list_library_files
        d = tmp_path / "2024" / "REG"
        d.mkdir(parents=True)
        (d / "wk01.json").write_text("[]")
        (d / "wk02.json").write_text("[]")
        files = list_library_files(2024, "REG", data_dir=tmp_path)
        assert len(files) == 2

    def test_returns_sorted_paths(self, tmp_path):
        from model_training.play_level.fetcher import list_library_files
        d = tmp_path / "2023" / "POST"
        d.mkdir(parents=True)
        for w in [3, 1, 2]:
            (d / f"wk{w:02d}.json").write_text("[]")
        files = list_library_files(2023, "POST", data_dir=tmp_path)
        names = [f.name for f in files]
        assert names == ["wk01.json", "wk02.json", "wk03.json"]

    def test_empty_dir_returns_empty(self, tmp_path):
        from model_training.play_level.fetcher import list_library_files
        d = tmp_path / "2024" / "REG"
        d.mkdir(parents=True)
        assert list_library_files(2024, "REG", data_dir=tmp_path) == []

    def test_missing_dir_returns_empty(self, tmp_path):
        from model_training.play_level.fetcher import list_library_files
        assert list_library_files(2024, "REG", data_dir=tmp_path) == []
