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
    is_final_game,
    raw_url,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "nfl_raw"
# A played game's JSON carries a summary in a FINAL phase; nothing else is a cache hit.
_FINAL = {"summary": {"phase": "FINAL"}, "driveChart": {"plays": []}}
# nfl-raw's file for a game not played yet: no summary, no driveChart.
_SHELL = {"summary": None, "driveChart": None, "status": "SCHEDULED"}

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
        body = json.dumps(_FINAL).encode()
        session = _fake_session(body)

        result = fetch_game(2024, "2024_01_BAL_KC", cache_dir=tmp_path, session=session)

        assert result == tmp_path / "2024" / "2024_01_BAL_KC.json"
        assert result.exists()
        assert json.loads(result.read_bytes()) == _FINAL

    def test_session_called_once_on_first_fetch(self, tmp_path):
        body = json.dumps(_FINAL).encode()
        session = _fake_session(body)

        fetch_game(2024, "2024_01_BAL_KC", cache_dir=tmp_path, session=session)

        session.get.assert_called_once()

    def test_skip_on_second_call_if_file_exists(self, tmp_path):
        body = json.dumps(_FINAL).encode()
        session = _fake_session(body)

        # First call — fetches
        fetch_game(2024, "2024_01_BAL_KC", cache_dir=tmp_path, session=session)
        assert session.get.call_count == 1

        # Second call — file already present, should skip
        fetch_game(2024, "2024_01_BAL_KC", cache_dir=tmp_path, session=session)
        assert session.get.call_count == 1  # still 1, not 2

    def test_force_refetches_existing(self, tmp_path):
        body = json.dumps(_FINAL).encode()
        session = _fake_session(body)

        fetch_game(2024, "2024_01_BAL_KC", cache_dir=tmp_path, session=session)
        fetch_game(2024, "2024_01_BAL_KC", cache_dir=tmp_path, session=session, force=True)

        assert session.get.call_count == 2

    def test_creates_season_subdirectory(self, tmp_path):
        body = json.dumps(_FINAL).encode()
        session = _fake_session(body)

        fetch_game(2024, "2024_01_BAL_KC", cache_dir=tmp_path, session=session)

        assert (tmp_path / "2024").is_dir()

    def test_returns_path_object(self, tmp_path):
        body = json.dumps(_FINAL).encode()
        session = _fake_session(body)

        result = fetch_game(2024, "2024_01_BAL_KC", cache_dir=tmp_path, session=session)
        assert isinstance(result, Path)

    def test_url_contains_season_and_game(self, tmp_path):
        body = json.dumps(_FINAL).encode()
        session = _fake_session(body)

        fetch_game(2023, "2023_22_KC_PHI", cache_dir=tmp_path, session=session)

        call_url = session.get.call_args[0][0]
        assert "2023" in call_url
        assert "2023_22_KC_PHI" in call_url


class TestCacheTrustsOnlyFinals:
    """A cached file is a hit only for a played game (the 2026-11-19 weeks-1-4 publish)."""

    def _cache(self, tmp_path, game: dict) -> Path:
        dest = tmp_path / "2026" / "2026_05_KC_JAX.json"
        dest.parent.mkdir(parents=True)
        dest.write_text(json.dumps(game))
        return dest

    def test_cached_shell_is_refetched_and_replaced(self, tmp_path):
        dest = self._cache(tmp_path, _SHELL)
        session = _fake_session(json.dumps(_FINAL))

        result = fetch_game(2026, "2026_05_KC_JAX", cache_dir=tmp_path, session=session)

        session.get.assert_called_once()
        assert result == dest
        assert json.loads(dest.read_text()) == _FINAL

    @pytest.mark.parametrize("phase", ["PREGAME", "INGAME", "HALFTIME"])
    def test_cached_unfinished_game_is_refetched(self, tmp_path, phase):
        self._cache(tmp_path, {"summary": {"phase": phase}, "driveChart": {"plays": []}})
        session = _fake_session(json.dumps(_FINAL))

        fetch_game(2026, "2026_05_KC_JAX", cache_dir=tmp_path, session=session)

        session.get.assert_called_once()

    def test_corrupt_cache_file_is_refetched(self, tmp_path):
        dest = self._cache(tmp_path, _FINAL)
        dest.write_text('{"summary": {"pha')
        session = _fake_session(json.dumps(_FINAL))

        fetch_game(2026, "2026_05_KC_JAX", cache_dir=tmp_path, session=session)

        session.get.assert_called_once()

    @pytest.mark.parametrize("phase", ["FINAL", "FINAL_OVERTIME"])
    def test_cached_final_is_a_hit(self, tmp_path, phase):
        dest = self._cache(tmp_path, {"summary": {"phase": phase}})
        session = _fake_session(json.dumps(_FINAL))

        assert fetch_game(2026, "2026_05_KC_JAX", cache_dir=tmp_path, session=session) == dest
        session.get.assert_not_called()

    def test_fetched_shell_is_not_cached(self, tmp_path):
        session = _fake_session(json.dumps(_SHELL))

        result = fetch_game(2026, "2026_15_KC_JAX", cache_dir=tmp_path, session=session)

        assert result is None
        assert not (tmp_path / "2026" / "2026_15_KC_JAX.json").exists()

    def test_fetched_shell_removes_a_stale_cached_shell(self, tmp_path):
        dest = self._cache(tmp_path, _SHELL)
        session = _fake_session(json.dumps(_SHELL))

        assert fetch_game(2026, "2026_05_KC_JAX", cache_dir=tmp_path, session=session) is None
        assert not dest.exists()

    def test_pregame_with_a_summary_is_still_written(self, tmp_path):
        # not final, so never a hit, but a summary with plays is game data the build reads
        # (the 2022_17_BUF_CIN no-contest is PREGAME with 30 plays)
        game = {"summary": {"phase": "PREGAME"}, "driveChart": {"plays": [{"playId": 1}]}}
        session = _fake_session(json.dumps(game))

        result = fetch_game(2026, "2026_11_IND_HOU", cache_dir=tmp_path, session=session)

        assert result is not None and json.loads(result.read_text()) == game

    def test_ingest_skips_shells_and_keeps_finals(self, tmp_path):
        final = json.dumps(_FINAL).encode()
        shell = json.dumps(_SHELL).encode()
        session = MagicMock()
        session.get.side_effect = lambda url, **kw: MagicMock(
            content=shell if "_15_" in url else final, raise_for_status=MagicMock()
        )
        with patch("nfl_data_ingest.fetch.enumerate_game_ids",
                   return_value=["2026_05_KC_JAX", "2026_15_KC_JAX"]):
            ingest_season(2026, cache_dir=tmp_path, session=session)

        assert sorted(p.name for p in (tmp_path / "2026").iterdir()) == ["2026_05_KC_JAX.json"]


class TestIsFinalGameOnRealFiles:
    """Real nfl-raw files (nfl/raw/2026/, nfl-raw 2d7b9d4f): a played final (ARI_LAC, its
    driveChart lists cut to two entries), the 2026-11-19 TNF before kickoff (IND_HOU:
    summary phase PREGAME, a lone GAME_START play) and a week-18 shell (TB_NO). All
    three have top-level status "SCHEDULED"."""

    @pytest.mark.parametrize(
        ("name", "final"),
        [("2026_01_ARI_LAC", True), ("2026_11_IND_HOU", False), ("2026_18_TB_NO", False)],
    )
    def test_signal(self, name, final):
        game = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
        assert game["status"] == "SCHEDULED"
        assert is_final_game(game) is final

    def test_shell_has_no_summary_or_drive_chart(self):
        game = json.loads((FIXTURES / "2026_18_TB_NO.json").read_text(encoding="utf-8"))
        assert game["summary"] is None and not game.get("driveChart")


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

    def test_sends_token_when_set(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "t0k")
        session = _fake_session(_github_contents_payload(["2024_01_BAL_KC.json"]))

        enumerate_game_ids(2024, session=session)

        assert session.get.call_args.kwargs["headers"] == {"Authorization": "Bearer t0k"}

    def test_anonymous_without_token(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        session = _fake_session(_github_contents_payload(["2024_01_BAL_KC.json"]))

        enumerate_game_ids(2024, session=session)

        assert session.get.call_args.kwargs["headers"] == {}

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
        game_body = json.dumps(_FINAL).encode()
        session = _fake_session(game_body)

        with patch("nfl_data_ingest.fetch.enumerate_game_ids",
                   return_value=["2024_01_BAL_KC", "2024_01_GB_PHI"]):
            ingest_season(2024, cache_dir=tmp_path, session=session)

        assert (tmp_path / "2024" / "2024_01_BAL_KC.json").exists()
        assert (tmp_path / "2024" / "2024_01_GB_PHI.json").exists()

    def test_returns_cache_root(self, tmp_path):
        game_body = json.dumps(_FINAL).encode()
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
