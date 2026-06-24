"""Failing tests for play_level.features — run BEFORE implementing features.py.

Tests verify that the Python translation of nflfastR's make_model_mutations() +
prepare_ep_data() / prepare_wp_data() / prepare_cp_data() produces correct columns
from a minimal synthetic play DataFrame.
"""
import math

import polars as pl
import pytest

from model_training.play_level.features import (
    make_model_mutations,
    prepare_ep_data,
    prepare_wp_data,
    prepare_cp_data,
    label_next_score_half,
)
from model_training.play_level.constants import EP_FEATURES, WP_SPREAD_FEATURES, WP_NAIVE_FEATURES


# ---------------------------------------------------------------------------
# Minimal synthetic play fixture
# ---------------------------------------------------------------------------

def _base_play(**overrides) -> dict:
    """One synthetic play with sensible defaults for feature derivation."""
    base = dict(
        game_id="2024_01_KC_BUF",
        qtr=1,
        down=1.0,
        yardline_100=75.0,
        ydstogo=10.0,
        score_differential=0.0,
        posteam_timeouts_remaining=3.0,
        defteam_timeouts_remaining=3.0,
        half_seconds_remaining=1800.0,
        game_seconds_remaining=3600.0,
        season=2024,
        roof="outdoors",
        posteam="KC",
        home_team="KC",
        defteam="BUF",
        spread_line=-3.0,
        # CP extras
        air_yards=10.0,
        pass_location="middle",
        complete_pass=1.0,
        incomplete_pass=0.0,
        interception=0.0,
        receiver_player_id="12345",
        receiver_player_name="T.Hill",
        qb_hit=0.0,
    )
    base.update(overrides)
    return base


def _make_df(**overrides) -> pl.DataFrame:
    return pl.DataFrame([_base_play(**overrides)])


# ---------------------------------------------------------------------------
# make_model_mutations
# ---------------------------------------------------------------------------

class TestMakeModelMutations:
    def test_adds_home_column_when_posteam_is_home(self):
        df = make_model_mutations(_make_df(posteam="KC", home_team="KC"))
        assert df["home"][0] == 1.0

    def test_adds_home_column_when_posteam_is_away(self):
        df = make_model_mutations(_make_df(posteam="BUF", home_team="KC"))
        assert df["home"][0] == 0.0

    def test_outdoors_flag_set_for_outdoors_roof(self):
        df = make_model_mutations(_make_df(roof="outdoors"))
        assert df["outdoors"][0] == 1.0
        assert df["dome"][0] == 0.0
        assert df["retractable"][0] == 0.0

    def test_dome_flag_set_for_dome_roof(self):
        df = make_model_mutations(_make_df(roof="dome"))
        assert df["dome"][0] == 1.0
        assert df["outdoors"][0] == 0.0
        assert df["retractable"][0] == 0.0

    def test_retractable_flag_set(self):
        df = make_model_mutations(_make_df(roof="retractable"))
        assert df["retractable"][0] == 1.0
        assert df["dome"][0] == 0.0
        assert df["outdoors"][0] == 0.0

    def test_closed_roof_counts_as_dome(self):
        """nflfastR treats 'closed' the same as 'dome'."""
        df = make_model_mutations(_make_df(roof="closed"))
        assert df["dome"][0] == 1.0

    def test_era_buckets_2024(self):
        df = make_model_mutations(_make_df(season=2024))
        assert df["era0"][0] == 0.0
        assert df["era1"][0] == 0.0
        assert df["era2"][0] == 0.0
        assert df["era3"][0] == 0.0
        assert df["era4"][0] == 1.0

    def test_era_buckets_2000(self):
        df = make_model_mutations(_make_df(season=2000))
        assert df["era0"][0] == 1.0
        assert df["era1"][0] == 0.0

    def test_era_buckets_2003(self):
        df = make_model_mutations(_make_df(season=2003))
        assert df["era0"][0] == 0.0
        assert df["era1"][0] == 1.0

    def test_era_buckets_2010(self):
        df = make_model_mutations(_make_df(season=2010))
        assert df["era2"][0] == 1.0

    def test_era_buckets_2016(self):
        df = make_model_mutations(_make_df(season=2016))
        assert df["era3"][0] == 1.0

    def test_down_one_hot_down1(self):
        df = make_model_mutations(_make_df(down=1.0))
        assert df["down1"][0] == 1.0
        assert df["down2"][0] == 0.0
        assert df["down3"][0] == 0.0
        assert df["down4"][0] == 0.0

    def test_down_one_hot_down3(self):
        df = make_model_mutations(_make_df(down=3.0))
        assert df["down3"][0] == 1.0
        assert df["down1"][0] == 0.0


# ---------------------------------------------------------------------------
# prepare_ep_data → must return exactly EP_FEATURES columns
# ---------------------------------------------------------------------------

class TestPrepareEpData:
    def test_returns_dataframe(self):
        df = make_model_mutations(_make_df())
        result = prepare_ep_data(df)
        assert isinstance(result, pl.DataFrame)

    def test_columns_match_ep_features(self):
        df = make_model_mutations(_make_df())
        result = prepare_ep_data(df)
        assert list(result.columns) == EP_FEATURES

    def test_no_nulls_in_result_for_complete_row(self):
        df = make_model_mutations(_make_df())
        result = prepare_ep_data(df)
        assert result.null_count().sum_horizontal()[0] == 0


# ---------------------------------------------------------------------------
# prepare_wp_data → spread + naive variants
# ---------------------------------------------------------------------------

class TestPrepareWpData:
    def test_spread_columns_match(self):
        plays = pl.concat([_make_df() for _ in range(3)])
        df = make_model_mutations(plays)
        result = prepare_wp_data(df, variant="spread")
        assert list(result.columns) == WP_SPREAD_FEATURES

    def test_naive_columns_match(self):
        plays = pl.concat([_make_df() for _ in range(3)])
        df = make_model_mutations(plays)
        result = prepare_wp_data(df, variant="naive")
        assert list(result.columns) == WP_NAIVE_FEATURES

    def test_spread_time_derivation(self):
        """posteam is home (KC), spread_line=-3 → posteam_spread=-3
        elapsed_share = (3600-3600)/3600 = 0.0 → spread_time = -3 * exp(0) = -3.0
        (at kick-off, game_seconds_remaining=3600)"""
        df = make_model_mutations(_make_df(
            game_seconds_remaining=3600.0,
            spread_line=-3.0,
            posteam="KC", home_team="KC",
        ))
        result = prepare_wp_data(df, variant="spread")
        assert result["spread_time"][0] == pytest.approx(-3.0)

    def test_diff_time_ratio_at_kickoff(self):
        """elapsed_share=0 → exp(0)=1 → Diff_Time_Ratio = score_diff / 1."""
        df = make_model_mutations(_make_df(
            game_seconds_remaining=3600.0,
            score_differential=7.0,
        ))
        result = prepare_wp_data(df, variant="spread")
        assert result["Diff_Time_Ratio"][0] == pytest.approx(7.0)

    def test_receive_2h_ko_posteam_received_2h_kickoff(self):
        """receive_2h_ko=1 when posteam == first defteam in game (they got the 2H KO).
        Play in Q1 with KC as posteam, BUF was defteam first → BUF receives 2H KO → KC gets 0.
        If KC was defteam first → KC receives 2H KO → receive_2h_ko=1 when KC is posteam."""
        rows = [
            _base_play(qtr=1, posteam="KC", defteam="BUF", game_seconds_remaining=3500.0),
            _base_play(qtr=2, posteam="BUF", defteam="KC", game_seconds_remaining=1800.0),
        ]
        df = make_model_mutations(pl.DataFrame(rows))
        result = prepare_wp_data(df, variant="spread")
        # first defteam in game is BUF → BUF receives 2H ko → when posteam=="BUF" in Q1/Q2 → 1
        assert result["receive_2h_ko"][0] == 0.0   # KC is posteam, BUF is first defteam
        assert result["receive_2h_ko"][1] == 1.0   # BUF is posteam, BUF == first defteam

    def test_filters_overtime_plays(self):
        """WP model trained only on qtr<=4; prepare_wp_data should filter qtr>4."""
        rows = [
            _base_play(qtr=4),
            _base_play(qtr=5),  # overtime
        ]
        df = make_model_mutations(pl.DataFrame(rows))
        result = prepare_wp_data(df, variant="spread")
        assert result.height == 1


# ---------------------------------------------------------------------------
# prepare_cp_data
# ---------------------------------------------------------------------------

class TestPrepareCpData:
    def test_valid_pass_included_in_result(self):
        df = make_model_mutations(_make_df(
            air_yards=15.0, complete_pass=1.0, incomplete_pass=0.0, interception=0.0,
            pass_location="middle", receiver_player_id="X",
        ))
        result = prepare_cp_data(df)
        assert "valid_pass" in result.columns

    def test_invalid_pass_flagged(self):
        """Air yards < -15 → invalid."""
        df = make_model_mutations(_make_df(air_yards=-20.0, complete_pass=1.0,
                                           pass_location="middle", receiver_player_id="X"))
        result = prepare_cp_data(df)
        assert result["valid_pass"][0] == 0.0

    def test_air_is_zero_derived(self):
        df = make_model_mutations(_make_df(air_yards=0.0, complete_pass=1.0,
                                           pass_location="left", receiver_player_id="X"))
        result = prepare_cp_data(df)
        assert result["air_is_zero"][0] == 1.0

    def test_distance_to_sticks_derived(self):
        df = make_model_mutations(_make_df(air_yards=15.0, ydstogo=10.0, complete_pass=1.0,
                                           pass_location="right", receiver_player_id="X"))
        result = prepare_cp_data(df)
        assert result["distance_to_sticks"][0] == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# label_next_score_half (training-time EP label)
# ---------------------------------------------------------------------------

class TestLabelNextScoreHalf:
    def test_labels_added_and_class_index_0_to_6(self):
        """Synthetic 2-play game: TD scored at play 2 → play 1 gets Touchdown label."""
        rows = [
            _base_play(qtr=1, game_id="A", game_seconds_remaining=3500.0),
            _base_play(qtr=1, game_id="A", game_seconds_remaining=3400.0),
        ]
        df = pl.DataFrame(rows).with_columns(
            pl.lit("Touchdown").alias("next_score_type"),
            pl.lit(0).alias("next_score_class"),
        )
        result = label_next_score_half(df)
        assert "next_score_class" in result.columns
        assert result["next_score_class"].min() >= 0
        assert result["next_score_class"].max() <= 6
