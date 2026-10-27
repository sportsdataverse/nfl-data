"""G-NFL-1 gate: each check counts what it should, on a hand-built two-game frame."""

from __future__ import annotations

import polars as pl
from nfl_espn_build.gate import _checks


def _frame(**over) -> pl.DataFrame:
    base = {
        "game_id": [1, 1, 1],
        "game_play_number": [1, 2, 3],
        "type.text": ["Rush", "Rush", "Timeout"],  # a trailing timeout is not the last play
        "text": ["run", "run", "Timeout #1"],
        "rush": [True, True, False],
        "yds_rushed": [7, 2, None],
        "opportunity_run": [True, False, None],
        "line_yards": [5.5, 2.0, None],
        "second_level_yards": [1.5, 0.0, None],
        "open_field_yards": [0.0, 0.0, None],
        "end_of_half": [False, True, False],
        "scoring_play": [False, False, False],
        "EP_start": [1.0, 2.0, 0.5],
        "EPA": [0.3, -2.0, 0.0],
        "td_play": [False, False, False],
        "penalty_1st_conv": [True, False, False],
    }
    return pl.DataFrame(base | over)


def test_clean_frame_passes():
    assert not any(_checks(_frame(), 2025).values())


def test_each_defect_is_counted():
    bad = _frame(
        opportunity_run=[False, False, None],  # 7-yard carry not flagged
        line_yards=[3.5, 2.0, None],  # old band: parts no longer sum to 7
        EPA=[0.3, 0.1, 0.0],  # last real play is not -EP
        text=["run", "TOUCHDOWN, REVERSED", "Timeout #1"],
        td_play=[False, True, False],  # unscored reversal kept td_play
    )
    counts = _checks(bad, 2025)
    for key in ("opportunity_run", "line_yards_parts", "last_play_epa_not_minus_ep", "td_play_unscored_reversal"):
        assert counts[key] == 1, key


def test_null_values_on_a_rush_are_failures():
    """A null comparison must count, not drop the row (a null opportunity_run passed silently)."""
    bad = _frame(opportunity_run=[None, False, None], second_level_yards=[None, 0.0, None])
    counts = _checks(bad, 2025)
    assert counts["opportunity_run"] == 1
    assert counts["line_yards_parts"] == 1
