"""Offline tests for ``nfl_espn_build`` over the vendored one-game fixture.

The fixture (``tests/fixtures/espn_nfl``) is laid out like nfl-raw's
``nfl/espn/`` so the real CLI runs over it unchanged. Processing the one game
takes ~8 s, so the processed cache is module-scoped and shared.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import polars as pl
import pytest
from nfl_espn_build import build, process, publish
from nfl_espn_build.cli import main
from nfl_espn_build.config import ALL_ORDER, REGISTRY, processing_version
from nfl_espn_build.ingest import EspnStore, resolve_raw_root

FIX = Path(__file__).parent / "fixtures" / "espn_nfl"
EVENT = 401772510


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp("espn_nfl")
    cache, out = root / "cache", root / "out"
    rc = main(
        [
            "--dataset",
            "all",
            "-s",
            "2025",
            "--raw-dir",
            str(FIX),
            "--cache-dir",
            str(cache),
            "--out",
            str(out),
            "--workers",
            "1",
        ]
    )
    assert rc == 0
    return cache, out


def test_store_reads_fixture_like_the_raw_library():
    store = EspnStore(resolve_raw_root(FIX))
    events = store.season_events(2025)
    assert [e["espn_event_id"] for e in events] == [EVENT]
    assert events[0]["game_id"] == "2025_01_DAL_PHI"
    assert store.summary(2025, EVENT)["header"]["season"]["year"] == 2025
    assert len(store.plays(2025, EVENT)) > 100
    assert store.summary(2025, 1) is None and store.plays(2025, 1) == []


def test_every_registry_dataset_is_written(built):
    cache, out = built
    for name in ALL_ORDER:
        spec = REGISTRY[name]
        path = build.output_path(spec, 2025, out)
        assert path.exists(), name
        df = pl.read_parquet(path)
        assert df.height > 0 and {"game_id", "season", "week", "nflverse_game_id"} <= set(
            df.columns
        ), name
        assert df["game_id"].unique().to_list() == [EVENT]
        assert df["nflverse_game_id"].unique().to_list() == ["2025_01_DAL_PHI"]
    assert set(REGISTRY) == set(ALL_ORDER)


def test_pbp_carries_the_processor_columns(built):
    _, out = built
    df = pl.read_parquet(build.output_path(REGISTRY["pbp"], 2025, out))
    # the Paper Index / advanced-box inputs game-on-paper reads
    for col in (
        "EPA",
        "EPA_success",
        "EPA_explosive",
        "havoc",
        "scrimmage_play",
        "drive.id",
        "start.yardsToEndzone",
        "pos_score_pts",
        "scoring_opp",
        "passer_player_id",
        "rusher_player_name",
        "wp_before",
    ):
        assert col in df.columns, col
    assert df.filter(pl.col("scrimmage_play") == True).height > 100  # noqa: E712
    assert df["season_type"].unique().to_list() == [2]
    assert df.select(pl.col("EPA").is_null().mean()).item() < 0.2


def test_adv_and_box_shapes(built):
    _, out = built
    team = pl.read_parquet(build.output_path(REGISTRY["adv_team"], 2025, out))
    assert team.height == 2 and "pos_team" in team.columns
    box = pl.read_parquet(build.output_path(REGISTRY["team_box"], 2025, out))
    assert set(box["home_away"].to_list()) == {"home", "away"}
    players = pl.read_parquet(build.output_path(REGISTRY["player_box"], 2025, out))
    assert {"passing", "rushing", "receiving"} <= set(players["category"].to_list())
    drives = pl.read_parquet(build.output_path(REGISTRY["drives"], 2025, out))
    assert drives["drive_id"].n_unique() == drives.height
    parts = pl.read_parquet(build.output_path(REGISTRY["play_participants"], 2025, out))
    assert "passer_player_id" in parts.columns and parts["play_id"].n_unique() == parts.height


def test_cache_is_reused_and_stamped(built):
    cache, _ = built
    path = process.final_path(cache, 2025, EVENT)
    final = process.read_final(path)
    assert final["processing_version"] == processing_version()
    assert final["nflverse_game_id"] == "2025_01_DAL_PHI" and final["homeTeamId"] == 21
    assert process.final_is_current(path)
    store = EspnStore(str(FIX))
    tally = process.process_season(store, 2025, cache, workers=1)
    assert tally == {"listed": 1, "cached": 1}
    # a stale stamp is reprocessed on the next run
    final["processing_version"] = "0.0.0+0"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        json.dump(final, fh)
    assert not process.final_is_current(path)


def test_pregame_summary_is_not_cached():
    summary = json.load(gzip.open(FIX / "raw" / "2025" / f"{EVENT}.json.gz", "rt"))
    summary["header"]["competitions"][0]["status"]["type"]["state"] = "pre"
    assert process.build_final(summary, [], EVENT) is None


def test_publish_creates_release_once_and_uploads_per_file(tmp_path):
    a, b = tmp_path / "a.parquet", tmp_path / "b.parquet"
    a.write_bytes(b"x")
    b.write_bytes(b"y")
    calls: list[list] = []
    sent = publish.publish_files(
        "espn_nfl_pbp",
        [a, b, tmp_path / "missing.parquet"],
        repo="o/r",
        runner=calls.append,
        exists_check=lambda tag, repo: False,
    )
    assert sent == [a, b]
    assert calls[0][:3] == ["release", "create", "espn_nfl_pbp"]
    assert [c[2:4] for c in calls[1:]] == [["espn_nfl_pbp", str(a)], ["espn_nfl_pbp", str(b)]]
    assert all("--clobber" in c for c in calls[1:])
    assert publish.publish_files("t", [a], runner=calls.append, dry_run=True) == [a]
    assert len(calls) == 3


def test_shim_rejects_a_dataset_override():
    import _shim

    with pytest.raises(SystemExit, match="ambiguous"):
        _shim.run_dataset("pbp", ["--dataset", "drives", "-s", "2025"])
