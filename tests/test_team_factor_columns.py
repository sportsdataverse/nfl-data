"""Team-factor columns on the NFL ``team_summaries``: field position per drive, havoc EPA,
expected turnovers. The NFL twin of cfbfastR-cfb-data's test_factor_extension_columns.py;
every expected value is worked by hand.
"""

from __future__ import annotations

import polars as pl
import pytest
from nfl_team_summaries.build import (
    _drives_table,
    _field_position_ep,
    _havoc_and_expected_turnovers,
    _mutate_summary_margins,
)


def _ep(own_yardline: int) -> float:
    return _field_position_ep().filter(pl.col("yardline_own") == own_yardline)["ep"].item()


def test_field_position_ep_is_the_nfl_yardline_only_table():
    t = _field_position_ep()
    assert t.height == 99 and t["yardline_own"].to_list() == list(range(1, 100))
    assert t["ep"].is_sorted()


# (offense, defense, drive, yards_to_goal); a drive's first snap is its start. KC's first
# drive has THREE snaps and its second ONE, so a per-play mean would weight the 25 thrice.
_SNAPS = [
    ("KC", "BUF", "d1", 75),
    ("KC", "BUF", "d1", 60),
    ("KC", "BUF", "d1", 45),
    ("KC", "BUF", "d2", 40),
    ("BUF", "KC", "d3", 80),
]


def test_field_position_averages_drives_not_plays():
    plays = pl.DataFrame(
        _SNAPS, schema=["pos_team_id", "def_pos_team_id", "drive_id", "yards_to_goal"], orient="row"
    ).with_columns(
        drive_start_yards_to_goal=pl.col("yards_to_goal").first().over("drive_id"),
        drive_yards=pl.lit(10),
        drive_points=pl.lit(0.0),
    )
    out = _drives_table(plays).sort("pos_team_id")
    buf, kc = out.row(0, named=True), out.row(1, named=True)
    # yards: (75 + 40) / 2, not the per-play (3 * 75 + 40) / 4 = 66.25
    assert kc["start_position_off"] == pytest.approx(57.5)
    assert kc["start_position_n_off"] == 2
    assert kc["start_position_def"] == pytest.approx(80.0)
    assert kc["start_position_margin"] == pytest.approx(80.0 - 57.5)
    # points, from the same drives
    per_drive = (_ep(25) + _ep(60)) / 2
    assert kc["drive_start_ep_off"] == pytest.approx(per_drive)
    assert kc["drive_start_ep_off"] != pytest.approx((3 * _ep(25) + _ep(60)) / 4)
    assert buf["drive_start_ep_off"] == pytest.approx(_ep(20))
    assert kc["drive_start_ep_margin"] == pytest.approx(per_drive - _ep(20))
    # fewer yards to go / more EP ranks first on offense; the opposite allowed on defense
    assert (kc["start_position_rank_off"], buf["start_position_rank_off"]) == (1.0, 2.0)
    assert (kc["start_position_rank_def"], buf["start_position_rank_def"]) == (1.0, 2.0)
    assert (kc["drive_start_ep_rank_off"], buf["drive_start_ep_rank_off"]) == (1.0, 2.0)
    assert kc["start_position_margin_rank"] == 1.0 and kc["drive_start_ep_margin_rank"] == 1.0


def test_explosive_margin_is_whole_team_only():
    # before 2026-09-29 the whole-team margins keyed off start_position_off, which the
    # splits dropped; field position left the per-play grid, so the flag is explicit now
    df = pl.DataFrame(
        {
            f"{b}_{s}": [0.5]
            for b in ("TEPA", "EPAplay", "EPAdrive", "EPAgame", "success", "yardsplay", "explosive")
            for s in ("off", "def")
        }
    )
    assert "explosive_margin" in _mutate_summary_margins(df, whole_team=True).columns
    assert "explosive_margin" not in _mutate_summary_margins(df).columns


# scrimmage snaps: (game, offense, defense, EPA, havoc, int, pass, pass breakup, fumble)
_HAVOC = [
    ("g1", "A", "B", -3.0, True, 1.0, 1.0, False, 0.0),  # A intercepted
    ("g1", "A", "B", -0.5, True, 0.0, 1.0, True, 0.0),  # A's pass broken up
    ("g1", "A", "B", -2.0, True, 0.0, 0.0, False, 1.0),  # A fumbles a run
    ("g2", "A", "B", 0.5, False, 0.0, 0.0, False, 0.0),
    ("g1", "B", "A", 1.0, False, 0.0, 1.0, False, 0.0),
    ("g2", "B", "A", -0.4, True, 0.0, 1.0, True, 0.0),  # B's pass broken up
    ("g2", "B", "A", -1.5, True, 0.0, 0.0, False, 1.0),  # B fumbles a run
]


def test_havoc_epa_per_game_and_expected_turnover_margin():
    team_off = pl.DataFrame(
        _HAVOC,
        schema=[
            "game_id",
            "pos_team_id",
            "def_pos_team_id",
            "EPA",
            "havoc",
            "int",
            "pass",
            "pass_breakup",
            "fumble_vec",
        ],
        orient="row",
    )
    out = _havoc_and_expected_turnovers(team_off).sort("pos_team_id")
    a, b = out.row(0, named=True), out.row(1, named=True)
    assert a["havoc_EPAgame_off"] == pytest.approx(-2.75)  # (-3.0 - 0.5 - 2.0) / 2
    assert b["havoc_EPAgame_off"] == pytest.approx(-0.95)  # (-0.4 - 1.5) / 2
    assert a["havoc_EPAgame_def"] == pytest.approx(-0.95)
    assert a["havoc_EPAgame_margin"] == pytest.approx(-1.8)
    # INT share 1/3; fumbles cancel; A's passes defended twice in 2 games, B's once
    assert a["expected_turnover_margin"] == pytest.approx(-1 / 6)
    assert b["expected_turnover_margin"] == pytest.approx(1 / 6)
    assert (b["havoc_EPAgame_off_rank"], a["havoc_EPAgame_off_rank"]) == (1.0, 2.0)
    assert (b["havoc_EPAgame_def_rank"], a["havoc_EPAgame_def_rank"]) == (1.0, 2.0)
    assert (b["expected_turnover_margin_rank"], a["expected_turnover_margin_rank"]) == (1.0, 2.0)
