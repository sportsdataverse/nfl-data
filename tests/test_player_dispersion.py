"""Per-game dispersion and the rushing tiers on the player tables (TFD-5d).

Real carries: the Giants' first five 2024 games, three rushers (fixture README). The
expected values below are worked by hand from the CSV, not by the code under test.
The wiring into the published tables is covered in ``test_team_summaries.py``.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from nfl_team_summaries.build import player_dispersion, rusher_tiers

FIX = Path(__file__).parent / "fixtures" / "player_dispersion" / "rushers_2024_nyg_wk01_05.csv"
KEYS = ["pos_team_id", "rusher_player_id"]
TRACY, GRAY, NABERS = "00-0039384", "00-0038396", "00-0039337"


@pytest.fixture(scope="module")
def carries() -> pl.DataFrame:
    return pl.read_csv(FIX, schema_overrides={"pos_team_id": pl.Utf8})


def _row(df: pl.DataFrame, player: str) -> dict:
    return df.filter(pl.col("rusher_player_id") == player).row(0, named=True)


def test_dispersion_hand_computed(carries):
    # Gray's EPA/carry by game: 2024_01_MIN_NYG -0.260433/2 = -0.130217,
    # 2024_03_NYG_CLE -0.880194 (1 carry), 2024_04_DAL_NYG -0.474639 (1),
    # 2024_05_NYG_SEA -13.088094/4 = -3.272023 (the fumble returned for a touchdown).
    # mean -1.189268; population sd 1.231430 -> boom above 0.042162 (no game), bust
    # below -2.420698 (the -3.272023 game). Sorted
    # [-3.272023, -0.880194, -0.474639, -0.130217]: p10 at position 0.3 =
    # -3.272023 + 0.3 * 2.391829 = -2.554475; p90 at 2.7 = -0.474639 + 0.7 * 0.344422
    # = -0.233543.
    gray = _row(player_dispersion(carries, KEYS), GRAY)
    assert gray["dispersion_games"] == 4
    assert gray["EPAplay_sd"] == pytest.approx(1.231430, abs=1e-6)
    assert gray["EPAplay_p10"] == pytest.approx(-2.554475, abs=1e-6)
    assert gray["EPAplay_p90"] == pytest.approx(-0.233543, abs=1e-6)
    assert (gray["boom_rate"], gray["bust_rate"]) == (0.0, 0.25)
    # Tracy's five games: -0.526805, -0.587769, -0.074185, -0.620294, 0.219279. mean
    # -0.317955, sd 0.333428: only 0.219279 clears 0.015473, none is below -0.651383
    tracy = _row(player_dispersion(carries, KEYS), TRACY)
    assert tracy["dispersion_games"] == 5
    assert tracy["EPAplay_sd"] == pytest.approx(0.333428, abs=1e-6)
    assert tracy["EPAplay_p10"] == pytest.approx(-0.607284, abs=1e-6)
    assert tracy["EPAplay_p90"] == pytest.approx(0.101893, abs=1e-6)
    assert (tracy["boom_rate"], tracy["bust_rate"]) == (0.2, 0.0)


def test_under_three_games_is_null(carries):
    nabers = _row(player_dispersion(carries, KEYS), NABERS)
    assert nabers["dispersion_games"] == 2
    for c in ("EPAplay_sd", "EPAplay_p10", "EPAplay_p90", "boom_rate", "bust_rate"):
        assert nabers[c] is None, c


def test_identical_games_are_neither_boom_nor_bust():
    # sd == 0: a non-strict threshold would make every game both a boom and a bust
    flat = pl.DataFrame(
        {
            "pos_team_id": ["19"] * 3,
            "rusher_player_id": ["x"] * 3,
            "game_id": ["a", "b", "c"],
            "EPA": [0.25] * 3,
        }
    )
    row = player_dispersion(flat, KEYS).row(0, named=True)
    assert row["EPAplay_sd"] == 0.0
    assert (row["boom_rate"], row["bust_rate"]) == (0.0, 0.0)


def test_dispersion_is_bit_stable_across_row_order(carries):
    # the per-game frame leaves its group_by in no fixed order and float sums are not
    # associative: reduced unsorted, the sd moves in the last bit between two builds
    want = player_dispersion(carries, KEYS).sort(KEYS)
    for seed in range(50):  # about a third of the shuffles move an unsorted sd
        got = player_dispersion(carries.sample(fraction=1.0, shuffle=True, seed=seed), KEYS)
        assert got.sort(KEYS).equals(want), seed


def test_tier_shares_and_stuff_rate_hand_counted(carries):
    tiers = rusher_tiers(carries, KEYS)
    # Tracy, 30 carries: 18 for <= 4 yards (incl. three 4s), 8 for 5-10 (incl. three
    # 5s), 4 for 11+ (11, 13, 25, 27); 3 for <= 0 (three 0s)
    t = _row(tiers, TRACY)
    assert (t["line_yards_share"], t["second_level_share"], t["open_field_share"]) == (
        18 / 30,
        8 / 30,
        4 / 30,
    )
    assert t["stuff_rate"] == 3 / 30
    # Gray, 8 carries: yards 0, 6, 0, 1, 2, 0, 0, 2
    g = _row(tiers, GRAY)
    assert (g["line_yards_share"], g["second_level_share"], g["open_field_share"]) == (
        7 / 8,
        1 / 8,
        0.0,
    )
    assert g["stuff_rate"] == 4 / 8
    # Nabers, 3 carries: 2, 2, -4. A loss is a line carry and a stuff; the tiers are
    # not held to the 3-game floor
    n = _row(tiers, NABERS)
    assert (n["line_yards_share"], n["stuff_rate"]) == (1.0, 1 / 3)


def test_tier_cut_points_sit_where_football_outsiders_put_them():
    # no back in the fixture has a 10-yard carry, so the cuts get one row each side:
    # -1, 0 and 4 are line yards (-1 and 0 stuffs), 5 and 10 second level, 11 open field
    edges = pl.DataFrame(
        {
            "pos_team_id": ["19"] * 6,
            "rusher_player_id": ["x"] * 6,
            "EPA": [0.0] * 6,
            "yds_rushed": [-1.0, 0.0, 4.0, 5.0, 10.0, 11.0],
            "pos_score_diff_start": [0] * 6,
        }
    )
    row = rusher_tiers(edges, KEYS).row(0, named=True)
    assert (row["line_yards_share"], row["second_level_share"], row["open_field_share"]) == (
        3 / 6,
        2 / 6,
        1 / 6,
    )
    assert row["stuff_rate"] == 2 / 6


def test_one_score_split(carries):
    tiers = rusher_tiers(carries, KEYS)
    # Tracy: the 4 carries with |score diff| > 8 at the snap are one at -18 in
    # 2024_01_MIN_NYG (-0.489554), one at +14 in 2024_03_NYG_CLE (-0.556025) and two
    # at +10 in 2024_05_NYG_SEA (0.018672, -0.122993). His two carries at -8 in
    # 2024_04_DAL_NYG are inside one score.
    t = _row(tiers, TRACY)
    assert (t["EPAplay_one_score_n"], t["EPAplay_not_one_score_n"]) == (26, 4)
    assert t["EPAplay_not_one_score"] == pytest.approx(-0.287475, abs=1e-6)
    assert t["EPAplay_one_score"] == pytest.approx(0.023209, abs=1e-6)
    # Nabers never carried outside one score: no rate, a count of 0
    n = _row(tiers, NABERS)
    assert n["EPAplay_not_one_score"] is None and n["EPAplay_not_one_score_n"] == 0
