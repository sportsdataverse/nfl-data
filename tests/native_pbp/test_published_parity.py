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

    def fake_load(dataset, season, cache_dir, games=None, refresh=False):
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
    assert "0.2.0b1+abc.13" in text and "| epa | 4 |" in text  # 2 joined plays x 2 seasons
    summary = pl.read_csv(tmp_path / "out" / "model_pbp" / "summary.csv")
    assert summary["season"].to_list() == [2023, 2024] and summary["joined"].to_list() == [2, 2]
    assert pl.read_csv(tmp_path / "out" / "model_pbp" / "missing.csv")[
        "column"
    ].unique().to_list() == ["stadium"]


def test_model_column_refs_counts_files_that_name_a_column(tmp_path):
    (tmp_path / "a.py").write_text('cols = ["aborted_play", "down"]\n', encoding="utf-8")
    (tmp_path / "b.py").write_text("x = df['aborted_play']\n", encoding="utf-8")
    refs = model_column_refs(["aborted_play", "stadium"], roots=[tmp_path])
    assert refs == {"aborted_play": 2, "stadium": 0}
