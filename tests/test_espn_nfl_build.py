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
from nfl_espn_build import tendencies as tendencies_mod
from nfl_espn_build.cli import main
from nfl_espn_build.config import ALL_ORDER, REGISTRY, processing_version
from nfl_espn_build.ingest import EspnStore, resolve_raw_root

FIX = Path(__file__).parent / "fixtures" / "espn_nfl"
EVENT = 401772510


#: what the nflverse schedule says for the fixture game (PHI favored by 8.5, total 47.5)
FIXTURE_LINES = {"401772510": (8.5, 47.5), "2025_01_DAL_PHI": (8.5, 47.5)}
#: and its sidelines (nflverse home_coach / away_coach)
FIXTURE_COACHES = pl.DataFrame(
    {"game_id": [EVENT], "home_coach": ["Nick Sirianni"], "away_coach": ["Brian Schottenheimer"]},
    schema={"game_id": pl.Int64, "home_coach": pl.Utf8, "away_coach": pl.Utf8},
)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    # offline: the schedule lookup is stubbed so the build never hits a release URL
    mp = pytest.MonkeyPatch()
    mp.setattr(process, "schedule_lines", lambda season: FIXTURE_LINES if season == 2025 else {})
    mp.setattr(
        tendencies_mod,
        "coach_games",
        lambda season: (
            FIXTURE_COACHES if season == 2025 else pl.DataFrame(schema=tendencies_mod.COACH_SCHEMA)
        ),
    )
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
    yield cache, out
    mp.undo()


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
        if name in ("adv_st_blocks", "usage_st_blocks") and not path.exists():
            continue  # no blocked kick in the fixture game: an empty cut is not written
        assert path.exists(), name
        df = pl.read_parquet(path)
        assert df.height > 0, name
        if spec.tendencies == "careers":  # one season-less file across every coach season
            assert "season" not in df.columns and df["seasons"].unique().to_list() == [1]
            continue
        if spec.aggregate or spec.tendencies:  # a season leaderboard has no game identity
            assert "game_id" not in df.columns and df["season"].unique().to_list() == [2025]
            continue
        assert {"game_id", "season", "week", "nflverse_game_id"} <= set(df.columns), name
        assert df["game_id"].unique().to_list() == [EVENT]
        assert df["nflverse_game_id"].unique().to_list() == ["2025_01_DAL_PHI"]
    assert set(REGISTRY) == set(ALL_ORDER)


def test_usage_datasets_and_leaderboards(built):
    _, out = built
    for name in ("adv_player_usage", "adv_tackles", "adv_team_usage", "adv_drive_scripting"):
        df = pl.read_parquet(build.output_path(REGISTRY[name], 2025, out))
        assert df.height > 0 and {"game_id", "season", "nflverse_game_id"} <= set(df.columns), name
    pu = pl.read_parquet(build.output_path(REGISTRY["adv_player_usage"], 2025, out))
    assert {
        "pos_team_id",
        "pos_team",
        "target_share",
        "fd_td_rate",
        "third_down_over_expected",
    } <= set(pu.columns)
    assert set(pu["pos_team"].drop_nulls().to_list()) == {"Philadelphia Eagles", "Dallas Cowboys"}
    tk = pl.read_parquet(build.output_path(REGISTRY["adv_tackles"], 2025, out))
    assert {"def_pos_team_id", "def_pos_team", "tackle_share", "position_group"} <= set(tk.columns)
    ds = pl.read_parquet(build.output_path(REGISTRY["adv_drive_scripting"], 2025, out))
    assert set(ds["script"].to_list()) == {"scripted", "non_scripted"}
    # season leaderboards: one row per identity, rates recomputed, no game_id
    lb = pl.read_parquet(build.output_path(REGISTRY["usage_players"], 2025, out))
    assert "game_id" not in lb.columns and (lb["games"] == 1).all() and lb.height == pu.height
    teams = pl.read_parquet(build.output_path(REGISTRY["usage_teams"], 2025, out))
    assert teams.height == 2 and "rz_points_per_trip" in teams.columns
    tk_lb = pl.read_parquet(build.output_path(REGISTRY["usage_tackles"], 2025, out))
    for team, g in tk_lb.group_by("def_pos_team_id"):
        assert abs(g["tackle_share"].sum() - 1.0) < 1e-9, team


def test_tendencies_per_team_coach_and_career(built):
    _, out = built
    team = pl.read_parquet(build.output_path(REGISTRY["team_tendencies"], 2025, out))
    assert team.height == 2 and "game_id" not in team.columns
    assert {
        "pos_team_id",
        "pos_team",
        "games",
        "plays",
        "sec_per_play_neutral",
        "pass_rate_neutral",
    } <= set(team.columns)
    assert {
        "go_rate",
        "fourth_agreement_rate",
        "rz_td_rate",
        "so_pts_per_trip",
        "def_epa_per_play",
    } <= set(team.columns)
    assert set(team["pos_team"].to_list()) == {"Philadelphia Eagles", "Dallas Cowboys"}
    assert (team["games"] == 1).all() and (team["plays"] > 40).all()
    coach = pl.read_parquet(build.output_path(REGISTRY["coach_tendencies"], 2025, out))
    assert coach.columns[:5] == ["season", "pos_team_id", "pos_team", "coach", "role"]
    assert set(coach["coach"].to_list()) == {"Nick Sirianni", "Brian Schottenheimer"}
    assert (coach["role"] == "HC").all()
    phi_team = team.filter(pl.col("pos_team") == "Philadelphia Eagles").row(0, named=True)
    phi_coach = coach.filter(pl.col("coach") == "Nick Sirianni").row(0, named=True)
    assert (
        phi_coach["plays"] == phi_team["plays"] and phi_coach["def_plays"] == phi_team["def_plays"]
    )
    assert abs(phi_coach["pass_rate"] - phi_team["pass_rate"]) < 1e-12
    careers = pl.read_parquet(build.output_path(REGISTRY["coach_careers"], 2025, out))
    assert build.output_path(REGISTRY["coach_careers"], 2025, out).name == "coach_careers.parquet"
    assert careers.columns[:6] == [
        "coach",
        "role",
        "teams",
        "seasons",
        "first_season",
        "last_season",
    ]
    row = careers.filter(pl.col("coach") == "Nick Sirianni").row(0, named=True)
    assert (
        row["teams"] == "Philadelphia Eagles"
        and row["seasons"] == 1
        and row["plays"] == phi_coach["plays"]
    )
    assert "pos_team_id" not in careers.columns


def test_season_plays_carry_home_team_and_exclude_preseason(built):
    cache, _ = built
    finals = process.load_season_finals(cache, 2025)
    plays = tendencies_mod.season_plays(finals)
    assert plays.height > 100 and {"homeTeamId", "seasonType", "season_type", "pos_team"} <= set(
        plays.columns
    )
    # a Pro Bowl (postseason, AFC/NFC as teams) never reaches the cached plays
    pro_bowl = [
        {**f, "plays": [{**p, "homeTeamId": 31, "awayTeamId": 32} for p in f["plays"]]}
        for f in finals
    ]
    assert tendencies_mod.season_plays(pro_bowl).height == 0
    for f in finals:
        f["plays"] = [{**p, "seasonType": 1} for p in f["plays"]]
        f["season_type"] = 1
    assert tendencies_mod.season_plays(finals).height == 0


def test_build_uses_the_stubbed_coach_lookup(built, monkeypatch):
    calls: list[int] = []

    def boom(season):
        calls.append(season)
        raise AssertionError("the build must resolve coach_games through the tendencies module")

    monkeypatch.setattr(tendencies_mod, "coach_games", boom)
    with pytest.raises(AssertionError):
        build.UsageCache("nfl").coaches(2025)
    assert calls == [2025]


def test_careers_are_cut_once_after_the_season_loop(built, monkeypatch):
    cache, out = built
    cuts: list[tuple[list[str], int]] = []
    real = build.build_season

    def spy(datasets, season, **kw):
        cuts.append((list(datasets), season))
        return real(datasets, season, **kw)

    monkeypatch.setattr("nfl_espn_build.cli.build_season", spy)
    rc = main(
        [
            "--dataset",
            "tendencies",
            "-s",
            "2024",
            "-e",
            "2025",
            "--no-process",
            "--raw-dir",
            str(FIX),
            "--cache-dir",
            str(cache),
            "--out",
            str(out),
        ]
    )
    assert rc == 0
    assert [c for c in cuts if "coach_careers" in c[0]] == [(["coach_careers"], 2025)]
    assert all("coach_careers" not in c[0] for c in cuts[:-1]) and len(cuts) == 3


def test_careers_are_skipped_when_a_season_failed(built, monkeypatch):
    cache, out = built
    cuts: list[list[str]] = []
    monkeypatch.setattr(
        "nfl_espn_build.cli.process_season", lambda *a, **k: {"listed": 1, "failed": 1}
    )
    monkeypatch.setattr(
        "nfl_espn_build.cli.build_season",
        lambda datasets, season, **kw: cuts.append(list(datasets)) or {},
    )
    rc = main(
        [
            "--dataset",
            "tendencies",
            "-s",
            "2025",
            "--raw-dir",
            str(FIX),
            "--cache-dir",
            str(cache),
            "--out",
            str(out),
        ]
    )
    assert rc == 1 and cuts == []


def test_pro_bowl_is_excluded_from_tendencies():
    df = pl.DataFrame(
        {
            "game_id": [1, 1, 2, 2],
            "homeTeamId": [10, 10, 31, 31],
            "awayTeamId": [20, 20, 32, 32],
            "pos_team": [10, 20, 31, 32],
        }
    )
    kept = tendencies_mod.exclude_exhibitions(df)
    assert kept["game_id"].to_list() == [1, 1]
    assert tendencies_mod.exclude_exhibitions(df.head(0)).height == 0
    assert tendencies_mod.exclude_exhibitions(df.drop("homeTeamId", "awayTeamId")).height == 4


def test_attach_coaches_drops_unattributed_games():
    plays = pl.DataFrame(
        {
            "game_id": [1, 1, 2],
            "pos_team": [10, 20, 10],
            "homeTeamId": [10, 10, 30],
        }
    )
    coaches = pl.DataFrame(
        {"game_id": [1], "home_coach": ["Home HC"], "away_coach": ["Away HC"]},
        schema={"game_id": pl.Int64, "home_coach": pl.Utf8, "away_coach": pl.Utf8},
    )
    out = tendencies_mod.attach_coaches(plays, coaches)
    assert out["coach"].to_list() == ["Home HC", "Away HC"]
    assert out["def_coach"].to_list() == ["Away HC", "Home HC"]
    empty = tendencies_mod.attach_coaches(plays, pl.DataFrame(schema=tendencies_mod.COACH_SCHEMA))
    assert empty.height == 0 and {"coach", "def_coach"} <= set(empty.columns)
    assert tendencies_mod.coach_tendencies(plays.head(0), coaches).height == 0
    # a season with no finals reshapes to a frame with NO columns; still no rows
    bare = tendencies_mod.attach_coaches(pl.DataFrame(), coaches)
    assert bare.height == 0 and {"coach", "def_coach"} <= set(bare.columns)
    assert tendencies_mod.coach_tendencies(pl.DataFrame(), coaches).height == 0
    assert tendencies_mod.coach_careers([]).height == 0


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
    # ids surface as <col>_id and the name-shaped column carries the name (cfb convention)
    assert set(df["pos_team_id"].drop_nulls().to_list()) == {21, 6}
    assert set(df["pos_team"].drop_nulls().to_list()) == {"Philadelphia Eagles", "Dallas Cowboys"}
    assert df.columns.index("pos_team_id") + 1 == df.columns.index("pos_team")
    assert df.select(pl.col("EPA").is_null().mean()).item() < 0.2


def test_adv_and_box_shapes(built):
    _, out = built
    team = pl.read_parquet(build.output_path(REGISTRY["adv_team"], 2025, out))
    assert team.height == 2 and {"pos_team", "pos_team_id"} <= set(team.columns)
    assert sorted(team["pos_team_id"].to_list()) == [6, 21]
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
    assert final["odds_source"] == "injected"
    plays = final["plays"]
    assert (plays[0]["homeFavorite"], plays[0]["gameSpread"], plays[0]["overUnder"]) == (
        True,
        8.5,
        47.5,
    )
    assert process.final_is_current(path)
    store = EspnStore(str(FIX))
    tally = process.process_season(store, 2025, cache, workers=1)
    assert tally == {"listed": 1, "cached": 1}
    # a stale stamp is reprocessed on the next run (restored after: the cache is module-shared)
    current = final["processing_version"]
    final["processing_version"] = "0.0.0+0"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        json.dump(final, fh)
    assert not process.final_is_current(path)
    final["processing_version"] = current
    process.write_final(path, final)
    assert process.final_is_current(path)


def test_build_reads_the_current_crosswalk_not_the_cached_id(built, tmp_path):
    cache, _ = built
    fake = tmp_path / "raw"
    (fake / "crosswalk").mkdir(parents=True)
    rows = json.loads((FIX / "crosswalk" / "games.json").read_text())
    rows[0]["game_id"] = "2025_01_XXX_YYY"
    (fake / "crosswalk" / "games.json").write_text(json.dumps(rows))
    written = build.build_season(
        ["drives"], 2025, cache_dir=cache, out=tmp_path / "out", store=EspnStore(str(fake))
    )
    df = pl.read_parquet(written["drives"])
    assert df["nflverse_game_id"].unique().to_list() == ["2025_01_XXX_YYY"]
    # the cached final itself is untouched
    assert (
        process.read_final(process.final_path(cache, 2025, EVENT))["nflverse_game_id"]
        == "2025_01_DAL_PHI"
    )


def test_odds_override_from_schedule_lines(monkeypatch):
    monkeypatch.setattr(
        process,
        "schedule_lines",
        lambda season: {"1": (-3.0, 41.0), "2": (None, 44.0), "g3": (6.5, None)},
    )
    assert process.odds_override_for(2025, 1) == {
        "gameSpread": 3.0,
        "overUnder": 41.0,
        "homeFavorite": False,
        "gameSpreadAvailable": True,
    }
    assert process.odds_override_for(2025, 2) is None  # no line known
    assert process.odds_override_for(2025, 9, "g3")["overUnder"] == 55.5  # nflverse id fallback
    assert process.odds_override_for(2025, 9) is None


def test_stub_plays_are_skipped_not_failed(tmp_path):
    """A completed game whose plays carry no text is a warning, never a season failure."""
    root = tmp_path / "raw"
    for sub in ("raw", "plays"):
        (root / sub / "2025").mkdir(parents=True)
    with gzip.open(FIX / "raw" / "2025" / f"{EVENT}.json.gz", "rt", encoding="utf-8") as fh:
        summary = json.load(fh)
    for drive in summary["drives"]["previous"]:
        for play in drive["plays"]:
            play.pop("text", None)
    with gzip.open(root / "raw" / "2025" / f"{EVENT}.json.gz", "wt", encoding="utf-8") as fh:
        json.dump(summary, fh)
    with gzip.open(root / "plays" / "2025" / f"{EVENT}.json.gz", "wt", encoding="utf-8") as fh:
        json.dump({"items": []}, fh)
    (root / "crosswalk").mkdir()
    (root / "crosswalk" / "games.json").write_text((FIX / "crosswalk" / "games.json").read_text())
    assert not process.summary_has_play_text(summary)
    assert not process.summary_has_play_text({"drives": [{"plays": [{"id": 1}]}]})
    assert process.summary_has_play_text(
        {"drives": {"current": [{"plays": [{"text": "Kickoff"}]}]}}
    )
    # a final an older sdv-py left behind for the stub game is removed, not re-cut
    stale = process.final_path(tmp_path / "cache", 2025, EVENT)
    stale.parent.mkdir(parents=True)
    stale.write_text("{}")
    event_id, status = process._process_one(
        (str(root), 2025, {"espn_event_id": EVENT}, str(tmp_path / "cache"))
    )
    assert (event_id, status) == (EVENT, "stub")
    assert not stale.exists() and process.load_season_finals(tmp_path / "cache", 2025) == []
    tally = process.process_season(EspnStore(str(root)), 2025, tmp_path / "cache", workers=1)
    assert tally.get("stub") == 1 and not tally.get("failed")


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


def test_stale_finals_are_skipped_and_empty_cuts_remove_old_output(tmp_path):
    cache = tmp_path / "cache"
    (cache / "2025").mkdir(parents=True)
    process.write_final(cache / "2025" / "1.json.gz", {"id": 1, "processing_version": "0.0.0+0"})
    assert process.load_season_finals(cache, 2025) == []
    out = tmp_path / "out"
    stale = build.output_path(REGISTRY["drives"], 2025, out)
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"old")
    assert build.build_season(["drives"], 2025, cache_dir=cache, out=out) == {"drives": None}
    assert not stale.exists()


def test_resolve_team_names_keeps_the_shape_with_an_empty_lookup():
    df = pl.DataFrame({"x": [1], "pos_team": [21], "def_pos_team": [6]})
    empty = pl.DataFrame(schema={"team_id": pl.Int64, "team_name": pl.Utf8})
    out = build.resolve_team_names(df, empty)
    assert out.columns == ["x", "pos_team_id", "pos_team", "def_pos_team_id", "def_pos_team"]
    assert out.row(0) == (1, 21, None, 6, None)


def test_cli_rejects_a_bad_season_range_and_abbreviations():
    with pytest.raises(SystemExit):
        main(["--dataset", "drives", "-s", "2025", "-e", "2024"])
    with pytest.raises(SystemExit):
        main(["--dat", "drives", "-s", "2025"])


def test_shim_rejects_a_dataset_override():
    import _shim

    with pytest.raises(SystemExit, match="ambiguous"):
        _shim.run_dataset("pbp", ["--dataset", "drives", "-s", "2025"])
