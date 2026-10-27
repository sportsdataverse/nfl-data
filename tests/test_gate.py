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


def test_a_game_that_ends_on_a_try_checks_the_touchdown_before_it():
    """sdv-py scores the try on its own row: EPA = its points - 0.92, never -EP, so the try is not the last play."""
    ended_on_pat = _frame(
        **{"type.text": ["Rush", "Passing Touchdown", "Extra Point Good"]},
        scoring_play=[False, True, False],
        EPA=[0.3, 4.9, 0.08],
        EP_start=[1.0, 2.0, 0.92],
    )
    assert _checks(ended_on_pat, 2025)["last_play_epa_not_minus_ep"] == 0


def test_a_truncated_feed_is_not_held_to_end_of_half():
    """The processor's "partial" game (no row carries game_play_number) has no end; a real game still does."""
    partial = _frame(game_play_number=[None, None, None], end_of_half=[None, None, None])
    assert _checks(partial, 2003)["last_row_end_of_half_null"] == 0
    assert _checks(_frame(end_of_half=[False, False, None]), 2003)["last_row_end_of_half_null"] == 1


def test_a_reversal_into_a_touchdown_keeps_td_play():
    """311204002/0528: ESPN leaves it unscored, but the reversal made it a touchdown."""
    into_td = _frame(
        text=["run", "FUMBLES, Touchback. The play was REVERSED. FUMBLES, and recovers at TEN 0. TOUCHDOWN.", "TO"],
        td_play=[False, True, False],
    )
    assert _checks(into_td, 2011)["td_play_unscored_reversal"] == 0


def test_game_count_matches_the_raw_library():
    assert _checks(_frame(), 2005, expected=({1}, 251, 0))["games_vs_raw"] == 0
    assert _checks(_frame(), 2005, expected=({1, 2}, 251, 0))["games_vs_raw"] == 1  # a game the file lost
    assert _checks(_frame(), 2005, expected=(set(), 251, 0))["games_vs_raw"] == 1  # a game it should not hold


def test_a_library_that_lost_games_fails_even_when_the_file_matches_it():
    """The expected set comes from the raw library, so a library that lost games is caught by its own counts."""
    counts = _checks(_frame(), 2010, expected=({1}, 40, 0))  # 40 stub games in a season that had none
    assert counts["games_vs_raw"] == 0 and counts["stub_games_over_observed"] == 38
    assert _checks(_frame(), 2005, expected=({1}, 251, 0))["stub_games_over_observed"] == 0
    assert _checks(_frame(), 2010, expected=({1}, 0, 3))["raw_summaries_missing"] == 3


def test_truncated_games_are_capped_at_the_observed_count():
    """A parser bug that nulls game_play_number would exempt its games from the end-of-game checks: count them."""
    partial = _frame(game_play_number=[None, None, None], end_of_half=[None, None, None])
    assert _checks(partial, 2003)["partial_games_over_observed"] == 0  # 1 of the 12 measured
    assert _checks(partial, 2015)["partial_games_over_observed"] == 1  # none measured


def test_a_reversal_whose_touchdown_was_nullified_is_still_held_to_td_play():
    nullified = _frame(
        text=["run", "The play was REVERSED. ... TOUCHDOWN NULLIFIED by Penalty.", "TO"], td_play=[False, True, False]
    )
    assert _checks(nullified, 2011)["td_play_unscored_reversal"] == 1
