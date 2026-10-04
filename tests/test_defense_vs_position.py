"""Stage 08 (``nfl_defense_vs_position``) over real published 2024 rows.

Provenance and the hand counts behind every literal here:
tests/fixtures/defense_vs_position/README.md. Nothing in this module can reach
the network or a release: the pbp slice is read from a tmp dir, the roster
loader is stubbed with the roster slice, and ``requests.get``, the ``gh``
runner and the release sidecars are refused for every test. The one CLI test
that passes ``--publish`` also passes ``--dry-run``.
"""

from __future__ import annotations

import logging
import shutil
from fnmatch import fnmatch
from pathlib import Path

import polars as pl
import pytest
from nfl_model_publish import artifacts
from nfl_model_publish.artifacts import _RELEASE_BODY, PKG_FUNCTION
from nfl_team_summaries import defense_vs_position as stage
from nfl_team_summaries.__main__ import SPLITS, TABLES
from nfl_team_summaries.build import MIN_COHORT_TEAMS
from nfl_team_summaries.defense_vs_position import (
    FLOOR,
    OUTPUT_SCHEMA,
    PCT_METRICS,
    STEM,
    TAG,
    build_defense_vs_position,
    defense_vs_position_table,
    main,
)
from nfl_team_summaries.league_averages import CATEGORIES
from polars.testing import assert_frame_equal
from sportsdataverse.defense_vs_position import OUTPUT_SCHEMA as T1_SCHEMA
from sportsdataverse.defense_vs_position import PBP_COLUMNS, defense_vs_position

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "defense_vs_position"
SEASON = 2024
PHI, DEN, BAL, KC, DET, PIT = 21, 7, 33, 12, 8, 23  # ESPN team ids, stage 06's key
QUALIFIERS = (PHI, DEN, BAL, KC, DET)  # three games each; Pittsburgh has two
PCT_COLS = [f"{m}_pct" for m in PCT_METRICS]


def _pbp() -> pl.DataFrame:
    return pl.read_parquet(FIX / "model_pbp_2024_slice.parquet")


def _rosters() -> pl.DataFrame:
    return pl.read_parquet(FIX / "nfl_rosters_2024_slice.parquet")


def _refuse(*args, **kwargs):
    raise AssertionError("a defense_vs_position test reached the network or a release")


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setattr("requests.get", _refuse)  # load_model_pbp's release fallback
    monkeypatch.setattr(stage, "load_rosters", lambda season: _rosters())
    for name in ("_gh_runner", "_gh_release_exists", "upload_release_sidecars"):
        monkeypatch.setattr(artifacts, name, _refuse)


def _pbp_dir(root: Path, pbp: pl.DataFrame | None = None, season: int = SEASON) -> Path:
    """A ``--pbp-dir`` holding the slice (or ``pbp``) under the name the stage reads."""
    path = root / f"model_pbp_{season}.parquet"
    if pbp is None:
        shutil.copyfile(FIX / "model_pbp_2024_slice.parquet", path)
    else:
        pbp.write_parquet(path)
    return root


@pytest.fixture()
def dvp(tmp_path) -> pl.DataFrame:
    return build_defense_vs_position(SEASON, _pbp_dir(tmp_path))


def _cell(df: pl.DataFrame, team: int, group: str) -> dict:
    rows = df.filter((pl.col("team_id") == team) & (pl.col("position_group") == group)).to_dicts()
    assert len(rows) == 1, rows
    return rows[0]


def test_schema_keys_and_int_team_id(dvp):
    assert dvp.schema == pl.Schema(OUTPUT_SCHEMA)
    assert dvp.schema["team_id"] == pl.Int64
    assert dvp.select("season", "team_id", "position_group").is_duplicated().sum() == 0
    assert set(dvp["team_id"]) == {PHI, DEN, BAL, KC, DET, PIT}
    assert set(dvp["position_group"]) == {"QB", "RB", "WR", "TE"}
    assert dvp.height == 6 * 4
    assert dvp["season"].unique().to_list() == [SEASON]


def test_t1_columns_pass_through_unchanged(dvp):
    t1 = defense_vs_position(_pbp().select(PBP_COLUMNS["nfl"]), _rosters(), "nfl").rename(
        {"team_id": "pos_team"}  # sdv-py keys the NFL rows on the nflverse abbreviation
    )
    cols = ["season", "pos_team", *[c for c in T1_SCHEMA if c not in ("season", "team_id")]]
    keys = ["pos_team", "position_group"]
    assert_frame_equal(dvp.select(cols).sort(keys), t1.select(cols).sort(keys))


def test_team_columns_are_the_summaries_names(dvp):
    phi = _cell(dvp, PHI, "QB")
    assert (phi["pos_team"], phi["team_name"], phi["division"], phi["conference"]) == (
        "PHI",
        "Philadelphia Eagles",
        "NFC East",
        "NFC",
    )
    den = _cell(dvp, DEN, "TE")
    assert (den["pos_team"], den["division"], den["conference"]) == ("DEN", "AFC West", "AFC")


def test_pct_lower_allowed_is_the_better_defense(dvp):
    """RB EPA/play allowed, 5 qualifiers: Weibull 100 * (n + 1 - rank) / (n + 1)."""
    hand = {  # EPA sum / plays, lowest allowed first
        DET: -9.881017645719112 / 55,
        BAL: -11.645739803803735 / 68,
        DEN: -7.373975946989958 / 91,
        KC: -2.7571574459871044 / 66,
        PHI: -3.1620409803072107 / 88,
    }
    for rank, (team, epa) in enumerate(hand.items(), start=1):
        c = _cell(dvp, team, "RB")
        assert c["epa_per_play_allowed"] == pytest.approx(epa)
        assert c["epa_per_play_allowed_pct"] == pytest.approx(100 * (6 - rank) / 6)


def test_pct_sack_rate_is_the_reverse_direction(dvp):
    """QB sack rate: the defense that sacks MORE is better, so highest ranks first."""
    hand = {DEN: 11 / 94, BAL: 10 / 129, DET: 8 / 115, KC: 6 / 124, PHI: 4 / 95}
    for rank, (team, rate) in enumerate(hand.items(), start=1):
        c = _cell(dvp, team, "QB")
        assert c["sack_rate_allowed"] == pytest.approx(rate)
        assert c["sack_rate_allowed_pct"] == pytest.approx(100 * (6 - rank) / 6)


def test_non_qualifier_has_null_pct_and_counts_in_no_cohort(dvp):
    out = dvp.filter(pl.col("qualified") == False)
    assert set(out["team_id"]) == {PIT} and out.height == 4  # two games, every group
    assert out.select(pl.all_horizontal(pl.col(PCT_COLS).is_null()).all()).item()
    # Pittsburgh's sack rate (4 / 66) would rank 4th of 6 and push Kansas City to 5th
    assert _cell(dvp, PIT, "QB")["sack_rate_allowed"] == pytest.approx(4 / 66)
    assert _cell(dvp, KC, "QB")["sack_rate_allowed_pct"] == pytest.approx(200 / 6)
    # and its RB EPA/play (-0.0358) would make the cohort six: Detroit 600 / 7, not 500 / 6
    assert _cell(dvp, PIT, "RB")["epa_per_play_allowed"] == pytest.approx(-1.7207644601585343 / 48)
    assert _cell(dvp, DET, "RB")["epa_per_play_allowed_pct"] == pytest.approx(500 / 6)


def test_cohort_under_the_f5_floor_has_null_pct():
    """Detroit dropped: four qualifiers a group, under the floor of five."""
    out = defense_vs_position_table(_pbp().filter(pl.col("defteam") != "DET"), _rosters())
    assert out.filter(pl.col("qualified") == True)["team_id"].n_unique() == 4 < MIN_COHORT_TEAMS
    assert out.select(pl.all_horizontal(pl.col(PCT_COLS).is_null()).all()).item()


def test_extras_only_get_a_pct_on_their_own_group(dvp):
    q = dvp.filter(pl.col("team_id").is_in(QUALIFIERS))
    by_group = {g: q.filter(pl.col("position_group") == g) for g in ("QB", "RB", "WR", "TE")}
    own = {
        "sack_rate_allowed_pct": {"QB"},
        "rush_yards_per_carry_allowed_pct": {"RB"},
        "yards_per_target_allowed_pct": {"WR", "TE"},
    }
    for col, groups in own.items():
        for g, rows in by_group.items():
            assert rows[col].null_count() == (0 if g in groups else len(QUALIFIERS)), (col, g)
    # Baltimore 117 / 45 = 2.6 yards per carry, the lowest of the five
    assert _cell(dvp, BAL, "RB")["rush_yards_per_carry_allowed"] == pytest.approx(117 / 45)
    assert _cell(dvp, BAL, "RB")["rush_yards_per_carry_allowed_pct"] == pytest.approx(500 / 6)


def test_unattributed_target_share_on_a_hand_counted_game():
    """Pittsburgh at Denver: 39 dropbacks = 35 throws + 2 sacks + 2 scrambles; plays 1372
    and 4207 name no receiver."""
    game = pl.col("game_id") == "2024_02_PIT_DEN"
    out = defense_vs_position_table(_pbp().filter(game & (pl.col("defteam") == "PIT")), _rosters())
    assert _cell(out, PIT, "QB")["dropbacks"] == 39
    for group in ("WR", "TE"):
        assert _cell(out, PIT, group)["unattributed_target_share"] == pytest.approx(2 / 35)
    for group in ("QB", "RB"):
        assert _cell(out, PIT, group)["unattributed_target_share"] is None


def test_unattributed_target_share_is_per_defense_season(dvp):
    for team, share in ((PIT, 4 / 60), (PHI, 5 / 89), (DET, 1 / 102)):
        for group in ("WR", "TE"):
            assert _cell(dvp, team, group)["unattributed_target_share"] == pytest.approx(share)


def test_below_floor_season_is_the_empty_schema_and_says_why(tmp_path, monkeypatch, caplog):
    assert FLOOR == 1999
    monkeypatch.setattr(stage, "load_model_pbp", _refuse)  # nothing is loaded below the floor
    monkeypatch.setattr(stage, "load_rosters", _refuse)
    with caplog.at_level(logging.WARNING):
        out = build_defense_vs_position(1998, tmp_path)
    assert out.height == 0
    assert out.schema == pl.Schema(OUTPUT_SCHEMA)
    assert "1998" in caplog.text and "1999" in caplog.text
    # and the stage writes no asset for it
    dest = tmp_path / "out"
    assert main(["--seasons", "1997:1998", "--out", str(dest), "--publish", "--dry-run"]) == 0
    assert list(dest.iterdir()) == []


def test_empty_pbp_is_the_empty_schema():
    out = defense_vs_position_table(_pbp().head(0), _rosters())
    assert out.height == 0
    assert out.schema == pl.Schema(OUTPUT_SCHEMA)


def test_pbp_of_another_season_raises(tmp_path):
    with pytest.raises(ValueError, match="2024"):
        build_defense_vs_position(2023, _pbp_dir(tmp_path, season=2023))


@pytest.mark.parametrize(
    ("frame", "col"),
    [("pbp", "rusher_player_id"), ("pbp", "receiver_player_id"), ("rosters", "gsis_id")],
)
def test_float_id_raises(tmp_path, monkeypatch, frame, col):
    """A gsis id read as a number (``00-0039384`` -> 39384.0) never reaches the roster join."""
    as_float = pl.col(col).str.slice(3).cast(pl.Float64)
    pbp, rosters = _pbp(), _rosters()
    if frame == "pbp":
        pbp = pbp.with_columns(as_float)
    else:
        rosters = rosters.with_columns(as_float)
    monkeypatch.setattr(stage, "load_rosters", lambda season: rosters)
    with pytest.raises(TypeError, match=col):
        build_defense_vs_position(SEASON, _pbp_dir(tmp_path, pbp))


def test_unknown_defense_abbreviation_raises():
    renamed = _pbp().with_columns(pl.col("defteam").replace({"PIT": "XXX"}))
    with pytest.raises(ValueError, match="XXX"):
        defense_vs_position_table(renamed, _rosters())


def test_cli_writes_the_season_and_publishes_only_what_it_wrote(dvp, tmp_path, monkeypatch):
    out = tmp_path / "nfl_defense_vs_position"
    out.mkdir()
    (out / f"{STEM}_2023.parquet").write_bytes(b"stale")  # a leftover season must not re-upload
    calls: list[tuple[Path, str, str, bool]] = []
    monkeypatch.setattr(
        artifacts,
        "upload_artifacts",
        lambda d, tag, repo, *, pattern, dry_run: (
            calls.append((Path(d), tag, pattern, dry_run)),
            {"uploaded": 0},
        )[1],
    )
    argv = ["--seasons", str(SEASON), "--pbp-dir", str(tmp_path), "--out", str(out)]
    assert main([*argv, "--publish", "--dry-run"]) == 0
    written = pl.read_parquet(out / f"{STEM}_{SEASON}.parquet")
    assert written.schema == pl.Schema(OUTPUT_SCHEMA)
    assert_frame_equal(written, dvp)
    assert calls == [(out, TAG, f"{STEM}_{SEASON}.parquet", True)]
    # without --publish the upload seam is never touched
    calls.clear()
    assert main(argv) == 0 and calls == []


def test_registered_with_its_tag_and_wired_after_stage_07():
    assert PKG_FUNCTION[TAG].endswith("nfl_data_08_defense_vs_position.py")
    notes = _RELEASE_BODY[TAG]
    assert "naming a receiver" in notes and "2003-2008" in notes and str(FLOOR) in notes
    cron = (ROOT / ".github" / "workflows" / "nfl_pbp_cron.yml").read_text()
    assert cron.index("nfl_data_07_metric_curves") < cron.index("nfl_data_08_defense_vs_position")


def test_stays_out_of_stage_06_and_league_averages():
    """Stage 06 publishes whole directories by glob and ``league_averages`` derives its
    metric list by column pattern: this dataset must be in neither."""
    stage_06 = [*TABLES.values(), SPLITS]
    assert TAG not in {tag for tag, _ in stage_06}
    assert not any(fnmatch(f"{STEM}_{SEASON}.parquet", f"{stem}_*.parquet") for _, stem in stage_06)
    assert STEM not in CATEGORIES and STEM not in TABLES
