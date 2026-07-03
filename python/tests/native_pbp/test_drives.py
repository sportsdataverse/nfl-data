"""Tests for fixed_drive / fixed_drive_result / drive_* detail columns.

Reference: ``docs/superpowers/plans/2026-07-03-nflfastr-parity-reference.md`` §8
(``helper_add_fixed_drives.R :: add_drive_results``) -- the 9-rule ``new_drive``
cascade, ``fixed_drive_result`` end-of-half resolution, and the aggregate-from-
plays ``drive_*`` detail columns (see :mod:`native_pbp.drives`'s module
docstring for the documented divergence from nflfastR's raw-provider-sourced
drive detail fields).
"""
from __future__ import annotations

from typing import Any, Optional

import polars as pl
from polars.testing import assert_frame_equal

from native_pbp.drives import _OUTPUT_SCHEMA, add_drive_detail


def _row(
    *,
    play_seq: float,
    posteam: Optional[str],
    defteam: Optional[str],
    game_id: str = "2023_01_BUF_NYJ",
    game_half: str = "Half1",
    qtr: int = 1,
    down: Optional[int] = None,
    ydstogo: Optional[int] = None,
    yardline_100: Optional[int] = None,
    play_type: Optional[str] = None,
    desc: str = "",
    touchdown: int = 0,
    td_team: Optional[str] = None,
    fumble_lost: int = 0,
    safety: int = 0,
    kickoff_attempt: int = 0,
    own_kickoff_recovery: int = 0,
    field_goal_result: Optional[str] = None,
    punt_attempt: int = 0,
    interception: int = 0,
    first_down_rush: int = 0,
    first_down_pass: int = 0,
    first_down_penalty: int = 0,
    penalty_yards: int = 0,
    play_id: Optional[int] = None,
    quarter_seconds_remaining: Optional[int] = None,
    game_seconds_remaining: Optional[int] = None,
    yards_gained: int = 0,
) -> dict[str, Any]:
    return {
        "game_id": game_id,
        "game_half": game_half,
        "play_seq": play_seq,
        "posteam": posteam,
        "defteam": defteam,
        "qtr": qtr,
        "down": down,
        "ydstogo": ydstogo,
        "yardline_100": yardline_100,
        "play_type": play_type,
        "desc": desc,
        "touchdown": touchdown,
        "td_team": td_team,
        "fumble_lost": fumble_lost,
        "safety": safety,
        "kickoff_attempt": kickoff_attempt,
        "own_kickoff_recovery": own_kickoff_recovery,
        "field_goal_result": field_goal_result,
        "punt_attempt": punt_attempt,
        "interception": interception,
        "first_down_rush": first_down_rush,
        "first_down_pass": first_down_pass,
        "first_down_penalty": first_down_penalty,
        "penalty_yards": penalty_yards,
        "play_id": play_id if play_id is not None else int(play_seq),
        "quarter_seconds_remaining": quarter_seconds_remaining,
        "game_seconds_remaining": game_seconds_remaining,
        "yards_gained": yards_gained,
    }


def _frame(rows: list[dict[str, Any]]) -> pl.DataFrame:
    return pl.DataFrame(rows, infer_schema_length=None)


# ---------------------------------------------------------------------------
# Rule 1 + Rule 6: base possession change / first play of the half.
# ---------------------------------------------------------------------------


def test_first_play_of_half_is_new_drive():
    df = _frame([_row(play_seq=1, posteam="BUF", defteam="NYJ")])
    out = add_drive_detail(df)
    assert out["fixed_drive"].to_list() == [1]


def test_possession_change_increments_fixed_drive():
    df = _frame(
        [
            _row(play_seq=1, posteam="BUF", defteam="NYJ", play_type="run"),
            _row(play_seq=2, posteam="NYJ", defteam="BUF", play_type="punt", punt_attempt=1),
            _row(play_seq=3, posteam="NYJ", defteam="BUF", play_type="run"),
        ]
    )
    out = add_drive_detail(df)
    assert out["fixed_drive"].to_list() == [1, 2, 2]


# ---------------------------------------------------------------------------
# Rule 2: PAT after a defensive TD is NOT a new drive.
# ---------------------------------------------------------------------------


def test_pat_after_defensive_touchdown_stays_same_drive():
    df = _frame(
        [
            # BUF fumbles, NYJ returns it for a touchdown.
            _row(
                play_seq=1,
                posteam="BUF",
                defteam="NYJ",
                play_type="run",
                touchdown=1,
                td_team="NYJ",
                fumble_lost=1,
            ),
            # NYJ (the scoring team) attempts the PAT.
            _row(play_seq=2, posteam="NYJ", defteam="BUF", play_type="extra_point"),
        ]
    )
    out = add_drive_detail(df)
    assert out["fixed_drive"].to_list() == [1, 1]


# ---------------------------------------------------------------------------
# Rule 5: same team retains the ball after its own lost fumble -> new drive,
# even though ``posteam`` looks unchanged from the prior play.
# ---------------------------------------------------------------------------


def test_fumble_retained_by_same_team_starts_new_drive():
    df = _frame(
        [
            _row(play_seq=1, posteam="BUF", defteam="NYJ", play_type="run", fumble_lost=1, touchdown=0),
            _row(play_seq=2, posteam="BUF", defteam="NYJ", play_type="run"),
        ]
    )
    out = add_drive_detail(df)
    assert out["fixed_drive"].to_list() == [1, 2]


# ---------------------------------------------------------------------------
# Rule 7: recovered onside kick / muffed kickoff return -> new drive.
# ---------------------------------------------------------------------------


def test_own_kickoff_recovery_starts_new_drive():
    df = _frame(
        [
            _row(play_seq=1, posteam="BUF", defteam="NYJ", play_type="run"),
            _row(
                play_seq=2,
                posteam="BUF",
                defteam="NYJ",
                play_type="kickoff",
                kickoff_attempt=1,
                own_kickoff_recovery=1,
            ),
        ]
    )
    out = add_drive_detail(df)
    assert out["fixed_drive"].to_list() == [1, 2]


# ---------------------------------------------------------------------------
# Rule 8: kickoff immediately after a safety -> new drive.
# ---------------------------------------------------------------------------


def test_kickoff_after_safety_starts_new_drive():
    df = _frame(
        [
            _row(play_seq=1, posteam="BUF", defteam="NYJ", play_type="run", safety=1),
            _row(play_seq=2, posteam="BUF", defteam="NYJ", play_type="kickoff", kickoff_attempt=1),
        ]
    )
    out = add_drive_detail(df)
    assert out["fixed_drive"].to_list() == [1, 2]


# ---------------------------------------------------------------------------
# fixed_drive_result category strings.
# ---------------------------------------------------------------------------


def test_fixed_drive_result_touchdown():
    df = _frame(
        [
            _row(play_seq=1, posteam="BUF", defteam="NYJ", play_type="run"),
            _row(play_seq=2, posteam="BUF", defteam="NYJ", play_type="run", touchdown=1, td_team="BUF"),
        ]
    )
    out = add_drive_detail(df)
    assert out["fixed_drive_result"].to_list() == ["Touchdown", "Touchdown"]
    assert out["drive_ended_with_score"].to_list() == [1, 1]


def test_fixed_drive_result_turnover_and_punt_and_fg():
    df = _frame(
        [
            # Drive 1: turnover (lost fumble).
            _row(play_seq=1, posteam="BUF", defteam="NYJ", play_type="run", fumble_lost=1),
            # Drive 2 (NYJ, possession changed): punt.
            _row(play_seq=2, posteam="NYJ", defteam="BUF", play_type="punt", punt_attempt=1),
            # Drive 3 (BUF): made field goal.
            _row(play_seq=3, posteam="BUF", defteam="NYJ", play_type="field_goal", field_goal_result="made"),
        ]
    )
    out = add_drive_detail(df)
    assert out["fixed_drive"].to_list() == [1, 2, 3]
    assert out["fixed_drive_result"].to_list() == ["Turnover", "Punt", "Field goal"]
    assert out["drive_ended_with_score"].to_list() == [0, 0, 1]


def test_fixed_drive_result_missing_fg_and_turnover_on_downs():
    df = _frame(
        [
            _row(play_seq=1, posteam="BUF", defteam="NYJ", play_type="field_goal", field_goal_result="missed"),
            _row(
                play_seq=2,
                posteam="NYJ",
                defteam="BUF",
                play_type="run",
                down=4,
                ydstogo=5,
                yards_gained=1,
            ),
        ]
    )
    out = add_drive_detail(df)
    assert out["fixed_drive_result"].to_list() == ["Missed field goal", "Turnover on downs"]


def test_end_of_half_resolution_uses_first_non_null_result():
    # Same drive: an earlier play is a safety (non-null tmp_result), a later
    # play is the end-of-half marker (also non-null). The LAST non-null value
    # is "End of half" -> per §8's resolution rule, fall back to the FIRST
    # non-null value ("Safety") instead of reporting "End of half" itself.
    df = _frame(
        [
            _row(play_seq=1, posteam="BUF", defteam="NYJ", play_type="run", safety=1),
            _row(play_seq=2, posteam="BUF", defteam="NYJ", play_type="no_play", desc="(:00) END QUARTER 2"),
        ]
    )
    out = add_drive_detail(df)
    assert out["fixed_drive_result"].to_list() == ["Safety", "Safety"]


# ---------------------------------------------------------------------------
# drive_* aggregate columns.
# ---------------------------------------------------------------------------


def test_drive_summary_aggregates():
    df = _frame(
        [
            _row(
                play_seq=1,
                posteam="BUF",
                defteam="NYJ",
                play_type="run",
                qtr=1,
                yardline_100=75,
                penalty_yards=5,
                play_id=101,
                quarter_seconds_remaining=900,
                game_seconds_remaining=3600,
                first_down_rush=1,
            ),
            _row(
                play_seq=2,
                posteam="BUF",
                defteam="NYJ",
                play_type="pass",
                qtr=1,
                yardline_100=15,
                penalty_yards=0,
                play_id=102,
                quarter_seconds_remaining=840,
                game_seconds_remaining=3540,
            ),
            _row(
                play_seq=3,
                posteam="BUF",
                defteam="NYJ",
                play_type="run",
                qtr=1,
                yardline_100=1,
                touchdown=1,
                td_team="BUF",
                play_id=103,
                quarter_seconds_remaining=780,
                game_seconds_remaining=3480,
            ),
        ]
    )
    out = add_drive_detail(df)
    assert out["drive_play_count"].to_list() == [3, 3, 3]
    assert out["drive_first_downs"].to_list() == [1, 1, 1]
    assert out["drive_inside20"].to_list() == [1, 1, 1]  # yardline_100 hit 15/1 <= 20
    assert out["drive_quarter_start"].to_list() == [1, 1, 1]
    assert out["drive_quarter_end"].to_list() == [1, 1, 1]
    assert out["drive_yards_penalized"].to_list() == [5, 5, 5]
    assert out["drive_start_yard_line"].to_list() == [75, 75, 75]
    assert out["drive_end_yard_line"].to_list() == [1, 1, 1]
    assert out["drive_play_id_started"].to_list() == [101, 101, 101]
    assert out["drive_play_id_ended"].to_list() == [103, 103, 103]
    assert out["drive_game_clock_start"].to_list() == ["15:00", "15:00", "15:00"]
    assert out["drive_game_clock_end"].to_list() == ["13:00", "13:00", "13:00"]
    # 3600 - 3480 = 120s -> "2:00"
    assert out["drive_time_of_possession"].to_list() == ["2:00", "2:00", "2:00"]
    assert out["drive_end_transition"].to_list() == ["Touchdown", "Touchdown", "Touchdown"]


def test_drive_start_transition_is_previous_drives_end_transition():
    df = _frame(
        [
            _row(play_seq=1, posteam="BUF", defteam="NYJ", play_type="punt", punt_attempt=1),
            _row(play_seq=2, posteam="NYJ", defteam="BUF", play_type="run"),
        ]
    )
    out = add_drive_detail(df)
    assert out["drive_start_transition"].to_list() == [None, "Punt"]


# ---------------------------------------------------------------------------
# Degenerate input — never raise, stable schema.
# ---------------------------------------------------------------------------


def test_add_drive_detail_noop_shape_on_empty_frame():
    df = pl.DataFrame({"game_id": []}, schema={"game_id": pl.Utf8})
    out = add_drive_detail(df)
    for col, dtype in _OUTPUT_SCHEMA.items():
        assert col in out.columns
        assert out.schema[col] == dtype


def test_add_drive_detail_noop_without_required_columns():
    df = pl.DataFrame({"game_id": ["2023_01_BUF_NYJ"], "desc": ["some play"]})
    out = add_drive_detail(df)
    assert_frame_equal(out.select("game_id", "desc"), df)
    for col in _OUTPUT_SCHEMA:
        assert col in out.columns
