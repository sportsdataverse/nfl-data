"""Receiver targets on 2003-2008 throws, whose Shield stats name no target (fixture README).

Real plays: Detroit's 2003 regular season, with nflverse's ``receiver_id`` for the same
plays as the oracle. Before the fill every Lions receiver's targets equal their catches
bar one; nflverse has them targeted on the incompletions too.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from nfl_team_summaries.input import fill_receiver_ids

FIX = Path(__file__).parent / "fixtures" / "receiver_targets" / "model_pbp_2003_det.parquet"
HAKIM, ROGERS = "00-0006627", "00-0022072"
THROWN = (pl.col("pass_attempt") == 1) & (pl.col("sack") == 0)


@pytest.fixture(scope="module")
def plays() -> pl.DataFrame:
    return pl.read_parquet(FIX)


def _line(df: pl.DataFrame, player: str) -> tuple[int, int]:
    rows = df.filter(THROWN & (pl.col("receiver_player_id") == player))
    return rows.height, int(rows["complete_pass"].sum())


def test_fixture_reproduces_the_bug(plays):
    thrown = plays.filter(THROWN)
    assert (thrown.height, thrown["receiver_player_id"].null_count()) == (590, 269)
    assert _line(plays, HAKIM) == (50, 49)
    assert _line(plays, ROGERS) == (22, 22)


def test_matches_nflverse_receiver_id(plays):
    thrown = fill_receiver_ids(plays).filter(THROWN)
    # same id on every throw, and null on the same 11 (throwaways, spikes, no "to X")
    assert thrown["receiver_player_id"].null_count() == 11
    assert (
        thrown.filter(
            pl.col("receiver_player_id").ne_missing(pl.col("nflverse_receiver_id"))
        ).height
        == 0
    )


def test_targets_hand_counted(plays):
    filled = fill_receiver_ids(plays)
    assert _line(filled, HAKIM) == (109, 49)
    assert _line(filled, ROGERS) == (52, 22)


def test_fills_nulls_only(plays):
    filled = fill_receiver_ids(plays)
    had = plays["receiver_player_id"].is_not_null()
    assert filled.filter(had)["receiver_player_id"].equals(plays.filter(had)["receiver_player_id"])
    # never names a target on a run or a sack
    assert filled.filter(~THROWN)["receiver_player_id"].equals(
        plays.filter(~THROWN)["receiver_player_id"]
    )
    assert filled.columns == plays.columns


def test_filled_rows_carry_the_stat_name(plays):
    # the parser stops "A.Randle El" at "A.Randle": a filled row takes a name the
    # stats give its id instead (the feed itself spells some ids two ways, "A. Hakim")
    stat = (
        plays.filter(pl.col("receiver_player_id").is_not_null())
        .select("receiver_player_id", "receiver_player_name")
        .unique()
    )
    filled = fill_receiver_ids(plays).filter(
        THROWN & plays["receiver_player_id"].is_null() & pl.col("receiver_player_id").is_not_null()
    )
    assert filled.height == 269 - 11
    assert (
        filled.join(stat, on=["receiver_player_id", "receiver_player_name"], how="anti").height == 0
    )
