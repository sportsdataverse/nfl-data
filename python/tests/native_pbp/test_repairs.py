"""Tests for the nflfastR hardcoded-game repair layer (fix_bad_games / fix_posteams).

Reference: ``docs/superpowers/plans/2026-07-03-nflfastr-parity-reference.md`` §1
(``helper_scrape_nfl.R :: fix_bad_games`` + ``fix_posteams``).
"""
from __future__ import annotations

import polars as pl
from polars.testing import assert_frame_equal

from native_pbp.repairs import apply_game_repairs, fix_bad_games, fix_posteams


# ---------------------------------------------------------------------------
# Passthrough — the common case (no bad_game condition, no legacy column)
# ---------------------------------------------------------------------------

def test_unaffected_game_passes_through_unchanged():
    df = pl.DataFrame(
        {
            "game_id": ["2023_01_BUF_NYJ"] * 3,
            "play_id": [1.0, 36.0, 55.0],
            "posteam": ["BUF", "BUF", "NYJ"],
        }
    )
    assert_frame_equal(apply_game_repairs(df), df)


def test_empty_frame_passes_through():
    df = pl.DataFrame(schema={"game_id": pl.Utf8, "posteam": pl.Utf8})
    assert_frame_equal(apply_game_repairs(df), df)


def test_normal_game_with_home_away_columns_untouched():
    # home_team != away_team -> bad_game condition never fires; repair columns
    # must be left exactly as-is even though they're present in the frame.
    df = pl.DataFrame(
        {
            "game_id": ["2023_01_BUF_NYJ"] * 2,
            "posteam": ["BUF", "NYJ"],
            "home_team": ["NYJ", "NYJ"],
            "away_team": ["BUF", "BUF"],
            "return_team": [None, "BUF"],
            "fumble_recovery_1_team": [None, None],
            "fumble_lost": [0, 0],
            "timeout_team": [None, None],
            "desc": ["(15:00) B.Allen pass", "(2:00) Timeout #1 by NYJ"],
        },
        # All-null columns would otherwise infer dtype=Null; pin Utf8 so the
        # comparison isn't sensitive to a polars all-null inference artifact
        # unrelated to what this test actually checks (values untouched).
        schema_overrides={"fumble_recovery_1_team": pl.Utf8, "timeout_team": pl.Utf8},
    )
    assert_frame_equal(apply_game_repairs(df), df)


# ---------------------------------------------------------------------------
# fix_bad_games — return_team rule
# ---------------------------------------------------------------------------

def test_fix_bad_games_return_team_home_has_ball():
    # posteam == home_team -> return_team should become away_team.
    df = pl.DataFrame(
        {
            "game_id": ["1999_01_FAKE_FAKE"] * 2,
            "posteam": ["NYJ", "NYJ"],
            "home_team": ["NYJ", "NYJ"],
            "away_team": ["NYJ", "NYJ"],  # bad_game: home == away in the raw feed
            "return_team": ["BUF", None],
        }
    )
    out = fix_bad_games(df)
    assert out["return_team"].to_list() == ["NYJ", None]


def test_fix_bad_games_return_team_away_has_ball():
    df = pl.DataFrame(
        {
            "game_id": ["1999_01_FAKE_FAKE"],
            "posteam": ["BUF"],
            "home_team": ["NYJ"],
            "away_team": ["NYJ"],
            "return_team": ["NYJ"],
        }
    )
    out = fix_bad_games(df)
    # posteam (BUF) != home_team (NYJ) -> return_team = home_team = NYJ
    assert out["return_team"].to_list() == ["NYJ"]


# ---------------------------------------------------------------------------
# fix_bad_games — fumble_recovery_1_team rule (4-branch case_when)
# ---------------------------------------------------------------------------

def test_fix_bad_games_fumble_recovery_all_branches():
    df = pl.DataFrame(
        {
            "game_id": ["1999_01_FAKE_FAKE"] * 5,
            "posteam": ["NYJ", "BUF", "NYJ", "BUF", "NYJ"],
            "home_team": ["NYJ"] * 5,
            "away_team": ["BUF"] * 5,
            "fumble_lost": [1, 1, 0, 0, 0],
            "fumble_recovery_1_team": ["X", "X", "X", "X", None],
        }
    )
    out = fix_bad_games(df)
    # row0: fumble_lost=1, posteam==home -> away_team (BUF)
    # row1: fumble_lost=1, posteam==away -> home_team (NYJ)
    # row2: fumble_lost=0, posteam==home -> home_team (NYJ)
    # row3: fumble_lost=0, posteam==away -> away_team (BUF)
    # row4: fumble_recovery_1_team originally null -> untouched (None)
    assert out["fumble_recovery_1_team"].to_list() == ["BUF", "NYJ", "NYJ", "BUF", None]


# ---------------------------------------------------------------------------
# fix_bad_games — timeout_team rule (regex re-extraction from desc)
# ---------------------------------------------------------------------------

def test_fix_bad_games_timeout_team_extracted_from_desc():
    df = pl.DataFrame(
        {
            "game_id": ["1999_01_FAKE_FAKE"] * 3,
            "posteam": ["NYJ", "NYJ", "NYJ"],
            "home_team": ["NYJ"] * 3,
            "away_team": ["NYJ"] * 3,
            "timeout_team": ["WRONG", None, "WRONG"],
            "desc": [
                "Timeout #1 by BUF at 05:00.",
                "(11:23) B.Allen pass short",
                "Timeout #3 by NYJ at 00:41.",
            ],
        }
    )
    out = fix_bad_games(df)
    assert out["timeout_team"].to_list() == ["BUF", None, "NYJ"]


def test_fix_bad_games_leaves_missing_columns_alone():
    # None of the repair target columns are present -> passthrough, no KeyError.
    df = pl.DataFrame(
        {
            "game_id": ["1999_01_FAKE_FAKE"],
            "posteam": ["NYJ"],
            "home_team": ["NYJ"],
            "away_team": ["NYJ"],
        }
    )
    assert_frame_equal(fix_bad_games(df), df)


# ---------------------------------------------------------------------------
# apply_game_repairs — end-to-end gating (only bad-game rows are touched;
# safe on multi-game frames since the gate is derived per-row from that
# row's own home_team/away_team)
# ---------------------------------------------------------------------------

def test_apply_game_repairs_only_touches_bad_game_rows():
    df = pl.DataFrame(
        {
            "game_id": ["1999_01_FAKE_FAKE", "1999_01_FAKE_FAKE", "2023_01_BUF_NYJ"],
            "posteam": ["NYJ", "BUF", "BUF"],
            "home_team": ["NYJ", "NYJ", "NYJ"],
            "away_team": ["NYJ", "NYJ", "BUF"],  # row2: normal game, home != away
            "return_team": ["BUF", "NYJ", "NYJ"],
        }
    )
    out = apply_game_repairs(df)
    # bad-game rows (0, 1) get corrected; the normal-game row (2) is untouched.
    assert out["return_team"].to_list() == ["NYJ", "NYJ", "NYJ"]


# ---------------------------------------------------------------------------
# fix_posteams — defensive no-op gate (the native Shield pipeline never emits
# a pre_play_by_play column; see module docstring for the deferred branch)
# ---------------------------------------------------------------------------

def test_fix_posteams_noop_without_pre_play_by_play():
    df = pl.DataFrame(
        {
            "game_id": ["2023_01_BUF_NYJ"],
            "posteam": ["BUF"],
        }
    )
    assert_frame_equal(fix_posteams(df), df)


def test_fix_posteams_noop_even_when_column_present():
    # The regex-based re-derivation branch is intentionally unimplemented
    # (deferred; see module docstring) — presence of pre_play_by_play must not
    # raise, and posteam must be left unchanged.
    df = pl.DataFrame(
        {
            "game_id": ["2023_01_BUF_NYJ"],
            "posteam": ["BUF"],
            "pre_play_by_play": ["BUF  1-10  NYJ 40"],
        }
    )
    out = fix_posteams(df)
    assert out["posteam"].to_list() == ["BUF"]
