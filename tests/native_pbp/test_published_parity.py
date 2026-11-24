"""Published-release parity (``native_pbp.parity`` published mode): ours vs nflverse.

Offline: hand-built frames that pin each rule the report relies on (the join key, NA counted
as a mismatch, the float tolerance, the ESPN id/team mapping). The real-data run is the CLI.
"""

from __future__ import annotations

import polars as pl
import pytest
from native_pbp.parity import compare_published, espn_to_nflverse, model_column_refs


def _nv(**cols):
    base = {
        "game_id": ["g1", "g1", "g1"],
        "play_id": [2.0, 3.0, 4.0],
        "play_type": ["pass", "run", "no_play"],
    }
    base.update(cols)
    return pl.DataFrame(base)


def _ours(**cols):
    base = {
        "game_id": ["g1", "g1", "g1"],
        "play_id": [1, 2, 3],
        "play_type": ["kickoff", "pass", "run"],
    }
    base.update(cols)
    return pl.DataFrame(base)


def test_coverage_counts_matched_and_each_side_only_by_play_type():
    rep = compare_published(_ours(), _nv())
    cov = {r["play_type"]: r for r in rep["coverage"].to_dicts()}
    assert cov["pass"]["matched"] == 1 and cov["run"]["matched"] == 1
    assert cov["kickoff"]["ours_only"] == 1  # play 1 is ours-only, typed by OUR play_type
    assert cov["no_play"]["nflverse_only"] == 1  # play 4 is nflverse-only, typed by nflverse's
    assert rep["joined"] == 2


def test_int64_vs_float64_key_joins_after_the_boundary_cast():
    rep = compare_published(_ours(), _nv())
    assert rep["joined"] == 2  # Int64 play_id (ours) vs Float64 (nflverse) still join


def test_column_match_counts_na_vs_value_as_mismatch_and_both_null_as_match():
    ours = _ours(down=[1, 2, None], air_yards=[None, 5.0, None])
    nv = _nv(down=[2.0, 3.0, None], air_yards=[5.00001, 9.0, None])
    # joined plays 2 and 3: down 2==2.0 match, None vs 3.0 mismatch
    # air_yards 5.0 vs 5.00001 within tol; None vs 9.0 mismatch
    rep = compare_published(ours, nv, float_tol=1e-4)
    cols = {r["column"]: r for r in rep["columns"].to_dicts()}
    assert (
        cols["down"]["compared"] == 2
        and cols["down"]["matched"] == 1
        and cols["down"]["na_mismatch"] == 1
    )
    assert cols["air_yards"]["matched"] == 1 and cols["air_yards"]["na_mismatch"] == 1
    both_null = compare_published(_ours(x=[None, None, None]), _nv(x=[None, None, None]))
    assert {r["column"]: r for r in both_null["columns"].to_dicts()}["x"]["rate"] == 1.0


def test_float_beyond_tolerance_is_a_mismatch():
    # joined plays 2 and 3: ours (1.0, 2.0) vs nflverse (1.5, 2.5) -> both off by 0.5
    rep = compare_published(_ours(ep=[0.0, 1.0, 2.0]), _nv(ep=[1.5, 2.5, 0.0]), float_tol=1e-4)
    assert {r["column"]: r for r in rep["columns"].to_dicts()}["ep"]["matched"] == 0


def test_metrics_report_mean_abs_diff_and_r_on_both_non_null_rows():
    ours = _ours(epa=[9.0, 1.0, 3.0])
    nv = _nv(epa=[1.5, 3.5, 7.0])  # joined (2,3): ours (1,3) vs nv (1.5,3.5): |d| = 0.5 each, r = 1
    rep = compare_published(ours, nv)
    m = rep["metrics"].filter(pl.col("metric") == "epa").to_dicts()[0]
    assert m["n"] == 2 and m["mean_abs_diff"] == pytest.approx(0.5) and m["r"] == pytest.approx(1.0)
    dev = rep["deviations"].filter(pl.col("metric") == "epa")
    assert dev.height == 2 and dev["abs_diff"].to_list() == pytest.approx([0.5, 0.5])


def test_missing_lists_nflverse_columns_we_lack():
    rep = compare_published(_ours(), _nv(aborted_play=[0.0, 0.0, 0.0], stadium=["a", "b", "c"]))
    assert set(rep["missing"]["column"].to_list()) == {"aborted_play", "stadium"}


def test_espn_to_nflverse_strips_the_game_prefix_maps_teams_and_columns():
    espn = pl.DataFrame(
        {
            "id": [40167161740, 401671617106],
            "game_id": [401671617, 401671617],
            "nflverse_game_id": ["2024_01_ARI_BUF"] * 2,
            "type.text": ["Kickoff", "Pass Reception"],
            "pos_team_id": [22, 2],
            "def_pos_team_id": [2, 22],
            "start.down": [1, 3],
            "EPA": [0.1, -0.2],
            "completion": [False, True],
        }
    )
    games = [
        {
            "espn_event_id": 401671617,
            "home_espn_team_id": "2",
            "home_nflverse": "BUF",
            "away_espn_team_id": "22",
            "away_nflverse": "ARI",
        }
    ]
    out = espn_to_nflverse(espn, games)
    assert out["game_id"].to_list() == ["2024_01_ARI_BUF"] * 2
    assert out["play_id"].to_list() == [40, 106] and out.schema["play_id"] == pl.Int64
    assert out["posteam"].to_list() == ["ARI", "BUF"] and out["defteam"].to_list() == ["BUF", "ARI"]
    assert out["down"].to_list() == [1, 3] and out["epa"].to_list() == [0.1, -0.2]
    assert out["complete_pass"].to_list() == [0.0, 1.0]
    assert out["play_type"].to_list() == ["Kickoff", "Pass Reception"]


def test_run_published_parity_writes_readme_and_csvs_offline(tmp_path, monkeypatch):
    import native_pbp.parity as parity

    def fake_load(dataset, season, cache_dir, games=None, refresh=False, **kw):
        return (
            _ours(epa=[0.0, 1.0, 2.0]),
            _nv(epa=[0.0, 1.5, 2.0], stadium=["a", "b", "c"]),
            "0.2.0b1+abc.13",
        )

    monkeypatch.setattr(parity, "load_season", fake_load)
    readme = parity.run_published_parity(
        ["model_pbp"], [2023, 2024], tmp_path / "cache", tmp_path / "out"
    )
    text = readme.read_text(encoding="utf-8")
    assert "0.2.0b1+abc.13" in text and "| epa | all | 4 |" in text  # 2 joined plays x 2 seasons
    summary = pl.read_csv(tmp_path / "out" / "model_pbp" / "summary.csv")
    assert summary["season"].to_list() == [2023, 2024] and summary["joined"].to_list() == [2, 2]
    assert pl.read_csv(tmp_path / "out" / "model_pbp" / "missing.csv")[
        "column"
    ].unique().to_list() == ["stadium"]


def test_model_column_refs_counts_files_that_name_a_column(tmp_path):
    (tmp_path / "a.py").write_text('cols = ["aborted_play", "down"]\n', encoding="utf-8")
    (tmp_path / "b.py").write_text("x = df['aborted_play']\n", encoding="utf-8")
    (tmp_path / "c.py").write_text('# Removed "stadium"\nx = 1\n', encoding="utf-8")
    refs = model_column_refs(["aborted_play", "stadium"], roots=[tmp_path])
    assert refs == {"aborted_play": 2, "stadium": 0}  # a comment is not a reference


# --- review fixes (PR #98): inputs the report must refuse, not silently mis-count ---


def test_fractional_play_id_is_refused():
    with pytest.raises(ValueError, match="fractional play_id"):
        compare_published(_ours(), _nv(play_id=[2.0, 2.5, 4.0]))


def test_duplicate_keys_are_refused():
    dup = pl.DataFrame({"game_id": ["g1", "g1"], "play_id": [2, 2], "play_type": ["pass", "pass"]})
    with pytest.raises(ValueError, match="duplicate"):
        compare_published(dup, _nv())


def test_coverage_counts_every_row_when_play_type_is_absent():
    rep = compare_published(_ours().drop("play_type"), _nv().drop("play_type"))
    cov = rep["coverage"]
    assert cov["matched"].sum() == rep["joined"] == 2 and cov["play_type"].to_list() == ["(null)"]


def test_nan_against_a_null_typed_column_is_both_null():
    ours = _ours(cp=pl.Series([None, None, None], dtype=pl.Null))
    nv = _nv(cp=[float("nan"), float("nan"), 0.5])
    col = {r["column"]: r for r in compare_published(ours, nv)["columns"].to_dicts()}["cp"]
    assert (
        col["both_null"] == 2 and col["na_mismatch"] == 0
    )  # joined plays 2, 3 are NaN on nflverse


def test_espn_null_id_is_refused():
    espn = pl.DataFrame(
        {
            "id": [40167161740, None],
            "game_id": [401671617, 401671617],
            "nflverse_game_id": ["g"] * 2,
            "type.text": ["Kickoff"] * 2,
            "pos_team_id": [22, 22],
            "def_pos_team_id": [2, 2],
        }
    )
    with pytest.raises(ValueError, match="game_id"):
        espn_to_nflverse(espn, [])


def test_runner_refuses_a_non_empty_out_dir_and_an_empty_selection(tmp_path):
    import native_pbp.parity as parity

    with pytest.raises(ValueError, match="no season"):
        parity.run_published_parity(["model_pbp"], [], tmp_path / "c", tmp_path / "o1")
    (tmp_path / "o2").mkdir()
    (tmp_path / "o2" / "README.md").write_text("old", encoding="utf-8")
    with pytest.raises(ValueError, match="not empty"):
        parity.run_published_parity(["model_pbp"], [2024], tmp_path / "c", tmp_path / "o2")


@pytest.mark.parametrize("args", [["--float-tol", "-1"], ["--float-tol", "nan"], ["--top-n", "-1"]])
def test_cli_rejects_bad_tolerance_and_top_n(args):
    from native_pbp.cli import build_parser

    with pytest.raises(SystemExit):
        build_parser().parse_args(["parity", "--seasons", "2024", "--out", "x", *args])


def test_espn_pbp_skips_pre_2006_by_default_and_takes_an_explicit_first_season(
    tmp_path, monkeypatch
):
    # before 2006 the ESPN play id does not embed the GSIS play_id: the join is coincidental
    import native_pbp.parity as parity
    from native_pbp.cli import build_parser

    asked = []

    def fake_load(dataset, season, cache_dir, games=None, refresh=False, **kw):
        asked.append(season)
        return _ours(), _nv(stadium=["a", "b", "c"]), "stamp"

    monkeypatch.setattr(parity, "load_season", fake_load)
    (tmp_path / "raw" / "nfl" / "espn" / "crosswalk").mkdir(parents=True)
    (tmp_path / "raw" / "nfl" / "espn" / "crosswalk" / "games.json").write_text("[]")
    seasons = [2004, 2005, 2006, 2007]
    run = parity.run_published_parity
    run(["espn_pbp"], seasons, tmp_path / "c", tmp_path / "o1", raw_dir=tmp_path / "raw")
    assert asked == [2006, 2007]
    asked.clear()
    run(
        ["espn_pbp"],
        seasons,
        tmp_path / "c",
        tmp_path / "o2",
        raw_dir=tmp_path / "raw",
        first_seasons={"espn_pbp": 2005},
    )
    assert asked == [2005, 2006, 2007]
    args = build_parser().parse_args(
        ["parity", "--seasons", "2004", "--out", "x", "--espn-first-season", "2002"]
    )
    assert args.espn_first_season == 2002


def test_metrics_split_tries_from_other_plays_by_the_nflverse_try_flags():
    # 2003-04 nflverse types every PAT try "no_play" but still sets extra_point_attempt
    ours = _ours(ep=[0.0, 1.0, 0.9])
    nv = _nv(ep=[1.0, 4.9, 0.0], extra_point_attempt=[0.0, 1.0, 0.0], two_point_attempt=[0, 0, 0])
    rep = compare_published(ours, nv)  # joined: play 2 (1.0 vs 1.0), play 3 a try (0.9 vs 4.9)
    m = {r["plays"]: r for r in rep["metrics"].filter(pl.col("metric") == "ep").to_dicts()}
    assert m["all"]["n"] == 2 and m["try"]["n"] == 1 and m["non_try"]["n"] == 1
    assert m["try"]["mean_abs_diff"] == pytest.approx(4.0)
    assert m["non_try"]["mean_abs_diff"] == pytest.approx(0.0)
