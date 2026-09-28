"""nfl_rolling_windows is cut from the written pbp seasons (fixture game 401772510, 2025)."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import polars as pl
import pytest
from nfl_espn_build import rolling
from nfl_espn_build.config import ALL_ORDER, REGISTRY
from nfl_espn_build.ingest import EspnStore, resolve_raw_root

from tests.test_espn_nfl_build import (  # noqa: F401  (module fixture: --dataset all -s 2025)
    FIX,
    built,
)


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    # history seasons come from the published tag; offline there is none
    monkeypatch.setattr(rolling, "fetch_history", lambda seasons, out: None)


def test_registered_last_in_the_full_run():
    assert REGISTRY["rolling_windows"].tag == "nfl_rolling_windows"
    assert REGISTRY["rolling_windows"].rolling
    assert ALL_ORDER[-1] == "rolling_windows"
    assert ALL_ORDER.index("pbp") < ALL_ORDER.index("rolling_windows")


def test_game_dates_are_the_eastern_calendar_day_of_the_crosswalk_kickoff():
    store = SimpleNamespace(
        crosswalk_games=lambda: [
            # Thursday night 8:30 pm EDT is 00:30Z on Friday
            {"espn_event_id": 1, "season": 2003, "kickoff_utc": "2003-09-05T00:30Z"},
            {"espn_event_id": 2, "season": 2003, "kickoff_utc": "2003-09-07T17:00Z"},
            # after DST ends (EST, UTC-5): 04:30Z Monday is still Sunday 11:30 pm
            {"espn_event_id": 3, "season": 2003, "kickoff_utc": "2003-12-01T04:30Z"},
        ]
    )
    df = rolling.game_dates(store)
    assert df.schema == pl.Schema({"game_id": pl.Int64, "game_date": pl.Date})
    assert dict(df.sort("game_id").iter_rows()) == {
        1: date(2003, 9, 4),
        2: date(2003, 9, 7),
        3: date(2003, 11, 30),
    }
    # the vendored crosswalk through the real reader: 2025-09-05T00:20Z is DAL-PHI on Sep 4
    fixture = rolling.game_dates(EspnStore(resolve_raw_root(FIX)))
    assert fixture.rows() == [(401772510, date(2025, 9, 4))]


def test_season_frame_windows_the_written_pbp(built, monkeypatch):  # noqa: F811
    monkeypatch.setattr(rolling, "PBP_FLOOR", 2025)
    _, out = built
    df = rolling.season_frame(2025, out, EspnStore(resolve_raw_root(FIX)))
    assert df["season"].unique().to_list() == [2025]
    assert df["as_of_date"].unique().to_list() == [date(2025, 9, 4)]
    drop = df.filter(
        (pl.col("window_unit") == "dropback")
        & (pl.col("window_n") == 50)
        & (pl.col("metric") == "epa")
    )
    assert drop.height >= 2  # both starting QBs
    assert drop["entity_id"].str.contains(r"^\d+$").all()  # ESPN athlete ids, text
    assert (drop["n"] <= 50).all() and drop["prev"].null_count() == drop.height  # one game: no prev
    assert set(df.filter(pl.col("entity_type") == "team")["entity_id"].unique()) == {"6", "21"}


def _write_2003_season(tmp_path):
    # 2002-2007 pbp carries passer / rusher ids as an all-null (Null-dtype) column
    path = rolling._pbp_path(2003, tmp_path)
    path.parent.mkdir(parents=True)
    ids = ("passer", "receiver", "rusher")
    pl.DataFrame(
        {
            "season": [2003],
            "seasonType": [2],
            "game_id": [1],
            "game_play_number": [1],
            "down": [1],
            "EPA": [0.5],
            "EPA_success": [True],
            "EPA_scrimmage": [0.5],
            "pass": [False],
            "rush": [True],
            "target": [False],
            **{f"{r}_player_{k}": [None] for r in ids for k in ("id", "name")},
            "pos_team_id": [6],
            "pos_team": ["Dallas Cowboys"],
            "homeTeamId": [21],
            "awayTeamId": [6],
        }
    ).write_parquet(path)
    return SimpleNamespace(
        crosswalk_games=lambda: [
            {"espn_event_id": 1, "season": 2003, "kickoff_utc": "2003-09-07T17:00Z"}
        ]
    )


def test_season_frame_reads_a_season_with_no_player_ids(tmp_path, monkeypatch):
    monkeypatch.setattr(rolling, "PBP_FLOOR", 2003)
    df = rolling.season_frame(2003, tmp_path, _write_2003_season(tmp_path))
    assert set(df["entity_type"]) == {"team"} and set(df["entity_id"]) == {"6"}


def test_missing_history_fails_instead_of_publishing_short_baselines(tmp_path, monkeypatch):
    # 2002 is absent after the (stubbed) download: a failed fetch, not a short career
    monkeypatch.setattr(rolling, "PBP_FLOOR", 2002)
    store = _write_2003_season(tmp_path)
    with pytest.raises(RuntimeError, match=r"history missing for \[2002\]"):
        rolling.season_frame(2003, tmp_path, store)


def test_a_rolling_only_run_replaces_the_current_season_pbp(tmp_path, monkeypatch):
    """Without pbp in the same run, the on-disk current season may be stale: it is re-fetched."""
    stale = rolling._pbp_path(2026, tmp_path)
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"stale")
    asked: list[list[int]] = []

    def fake_fetch(seasons, out):
        asked.append(list(seasons))
        assert not stale.exists(), "the stale file must be gone before the download"

    monkeypatch.setattr(rolling, "fetch_history", fake_fetch)
    monkeypatch.setattr(rolling, "PBP_FLOOR", 2025)
    # the download "failed" (fake_fetch wrote nothing): no current season, so nothing to publish
    assert rolling.season_frame(2026, tmp_path, pbp_cut=False).is_empty()
    assert asked == [[2025, 2026]]


def test_a_full_run_keeps_the_pbp_it_just_cut(tmp_path, monkeypatch):
    fresh = rolling._pbp_path(2026, tmp_path)
    fresh.parent.mkdir(parents=True)
    fresh.write_bytes(b"fresh")
    asked: list[list[int]] = []
    monkeypatch.setattr(rolling, "fetch_history", lambda seasons, out: asked.append(list(seasons)))
    monkeypatch.setattr(rolling, "PBP_FLOOR", 2025)
    with pytest.raises(RuntimeError, match="history missing"):  # 2025 absent offline
        rolling.season_frame(2026, tmp_path, pbp_cut=True)
    assert fresh.read_bytes() == b"fresh"
    assert asked == [[2025]]
