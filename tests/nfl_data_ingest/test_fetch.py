"""Hermetic unit tests for nfl_data_ingest.fetch.

Uses a fake requests.Session so no real network calls are made.
Integration tests (live round-trip) are marked @pytest.mark.integration.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nfl_data_ingest.fetch import (
    RAW_BASE,
    enumerate_game_ids,
    fetch_game,
    ingest_season,
    raw_url,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_session(body: bytes | str, status: int = 200) -> MagicMock:
    """Return a mock requests.Session whose get() returns a fixed response."""
    resp = MagicMock()
    resp.status_code = status
    resp.raise_for_status = MagicMock()
    if isinstance(body, str):
        body = body.encode()
    resp.content = body
    resp.json.return_value = json.loads(body)
    session = MagicMock()
    session.get.return_value = resp
    return session


def _github_contents_payload(filenames: list[str]) -> bytes:
    """Synthetic GitHub Contents API response listing .json files."""
    entries = [{"name": fn, "type": "file"} for fn in filenames]
    return json.dumps(entries).encode()


# ---------------------------------------------------------------------------
# raw_url
# ---------------------------------------------------------------------------

class TestRawUrl:
    def test_scheme_and_host(self):
        url = raw_url(2024, "2024_01_BAL_KC")
        assert url.startswith("https://raw.githubusercontent.com/")

    def test_contains_season_and_game_id(self):
        url = raw_url(2024, "2024_01_BAL_KC")
        assert "/2024/" in url
        assert "2024_01_BAL_KC.json" in url

    def test_uses_raw_base(self):
        url = raw_url(2024, "2024_01_BAL_KC")
        assert url.startswith(RAW_BASE)

    def test_path_structure(self):
        url = raw_url(2023, "2023_22_KC_PHI")
        assert url == f"{RAW_BASE}/raw/2023/2023_22_KC_PHI.json"


# ---------------------------------------------------------------------------
# fetch_game
# ---------------------------------------------------------------------------

class TestFetchGame:
    def test_writes_json_to_cache(self, tmp_path):
        body = json.dumps({"driveChart": {"plays": []}}).encode()
        session = _fake_session(body)

        result = fetch_game(2024, "2024_01_BAL_KC", cache_dir=tmp_path, session=session)

        assert result == tmp_path / "2024" / "2024_01_BAL_KC.json"
        assert result.exists()
        assert json.loads(result.read_bytes()) == {"driveChart": {"plays": []}}

    def test_session_called_once_on_first_fetch(self, tmp_path):
        body = json.dumps({"game": "data"}).encode()
        session = _fake_session(body)

        fetch_game(2024, "2024_01_BAL_KC", cache_dir=tmp_path, session=session)

        session.get.assert_called_once()

    def test_skip_on_second_call_if_file_exists(self, tmp_path):
        body = json.dumps({"game": "data"}).encode()
        session = _fake_session(body)

        # First call — fetches
        fetch_game(2024, "2024_01_BAL_KC", cache_dir=tmp_path, session=session)
        assert session.get.call_count == 1

        # Second call — file already present, should skip
        fetch_game(2024, "2024_01_BAL_KC", cache_dir=tmp_path, session=session)
        assert session.get.call_count == 1  # still 1, not 2

    def test_force_refetches_existing(self, tmp_path):
        body = json.dumps({"game": "data"}).encode()
        session = _fake_session(body)

        fetch_game(2024, "2024_01_BAL_KC", cache_dir=tmp_path, session=session)
        fetch_game(2024, "2024_01_BAL_KC", cache_dir=tmp_path, session=session, force=True)

        assert session.get.call_count == 2

    def test_creates_season_subdirectory(self, tmp_path):
        body = json.dumps({}).encode()
        session = _fake_session(body)

        fetch_game(2024, "2024_01_BAL_KC", cache_dir=tmp_path, session=session)

        assert (tmp_path / "2024").is_dir()

    def test_returns_path_object(self, tmp_path):
        body = json.dumps({}).encode()
        session = _fake_session(body)

        result = fetch_game(2024, "2024_01_BAL_KC", cache_dir=tmp_path, session=session)
        assert isinstance(result, Path)

    def test_url_contains_season_and_game(self, tmp_path):
        body = json.dumps({}).encode()
        session = _fake_session(body)

        fetch_game(2023, "2023_22_KC_PHI", cache_dir=tmp_path, session=session)

        call_url = session.get.call_args[0][0]
        assert "2023" in call_url
        assert "2023_22_KC_PHI" in call_url


# ---------------------------------------------------------------------------
# enumerate_game_ids
# ---------------------------------------------------------------------------

class TestEnumerateGameIds:
    def test_strips_json_extension(self, tmp_path):
        payload = _github_contents_payload([
            "2024_01_BAL_KC.json",
            "2024_01_GB_PHI.json",
        ])
        session = _fake_session(payload)

        ids = enumerate_game_ids(2024, session=session)
        assert "2024_01_BAL_KC" in ids
        assert "2024_01_GB_PHI" in ids
        assert all(not gid.endswith(".json") for gid in ids)

    def test_filters_non_json_entries(self, tmp_path):
        payload = _github_contents_payload([
            "2024_01_BAL_KC.json",
            "README.md",
            "subdir",
        ])
        session = _fake_session(payload)

        ids = enumerate_game_ids(2024, session=session)
        assert len(ids) == 1
        assert ids[0] == "2024_01_BAL_KC"

    def test_explicit_id_list_bypasses_api(self):
        ids = enumerate_game_ids(2024, game_ids=["2024_01_BAL_KC", "2024_01_GB_PHI"])
        assert ids == ["2024_01_BAL_KC", "2024_01_GB_PHI"]

    def test_explicit_id_list_needs_no_session(self):
        # No session needed when game_ids is provided
        ids = enumerate_game_ids(2024, game_ids=["abc"])
        assert ids == ["abc"]

    def test_hits_github_contents_api(self):
        payload = _github_contents_payload(["2024_01_BAL_KC.json"])
        session = _fake_session(payload)

        enumerate_game_ids(2024, session=session)

        url = session.get.call_args[0][0]
        assert "api.github.com" in url
        assert "nfl-raw" in url
        assert "2024" in url

    def test_returns_list_of_strings(self):
        payload = _github_contents_payload(["2024_01_BAL_KC.json"])
        session = _fake_session(payload)

        ids = enumerate_game_ids(2024, session=session)
        assert isinstance(ids, list)
        assert all(isinstance(i, str) for i in ids)


# ---------------------------------------------------------------------------
# ingest_season
# ---------------------------------------------------------------------------

class TestIngestSeason:
    def test_fetches_all_enumerated_games(self, tmp_path):
        game_body = json.dumps({"driveChart": {"plays": []}}).encode()
        session = _fake_session(game_body)

        with patch("nfl_data_ingest.fetch.enumerate_game_ids",
                   return_value=["2024_01_BAL_KC", "2024_01_GB_PHI"]):
            ingest_season(2024, cache_dir=tmp_path, session=session)

        assert (tmp_path / "2024" / "2024_01_BAL_KC.json").exists()
        assert (tmp_path / "2024" / "2024_01_GB_PHI.json").exists()

    def test_returns_cache_root(self, tmp_path):
        game_body = json.dumps({}).encode()
        session = _fake_session(game_body)

        with patch("nfl_data_ingest.fetch.enumerate_game_ids",
                   return_value=["2024_01_BAL_KC"]):
            result = ingest_season(2024, cache_dir=tmp_path, session=session)

        assert result == tmp_path

    def test_default_cache_dir_is_dotcache(self):
        """Confirm default cache_dir keyword is .cache/nfl_raw."""
        import inspect
        from nfl_data_ingest.fetch import ingest_season as fn
        sig = inspect.signature(fn)
        default = sig.parameters["cache_dir"].default
        assert Path(default) == Path(".cache/nfl_raw")


# ---------------------------------------------------------------------------
# Live round-trip (integration only)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_live_fetch_single_game(tmp_path):
    """Fetch one real game from GitHub and verify JSON parses."""
    result = fetch_game(2024, "2024_01_BAL_KC", cache_dir=tmp_path)
    assert result.exists()
    data = json.loads(result.read_bytes())
    assert "driveChart" in data or isinstance(data, dict)


@pytest.mark.integration
def test_live_enumerate_game_ids_2024():
    """Enumerate 2024 season game IDs from the GitHub Contents API."""
    ids = enumerate_game_ids(2024)
    assert len(ids) > 100
    assert all(isinstance(i, str) for i in ids)
    assert "2024_01_BAL_KC" in ids
