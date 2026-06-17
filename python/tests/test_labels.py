"""Tests for label.py — EP Next_Score_Half + WP Winner computation.

All tests use deterministic synthetic plays — no real PBP required.
"""
import polars as pl
import pytest

from model_training.track6_nfl_ep_wp.label import (
    compute_next_score_half,
    compute_winner,
    build_ep_training_set,
    build_wp_training_set,
    SCORE_LABEL_TO_CLASS,
)
from model_training.track6_nfl_ep_wp.constants import EP_CLASS_ORDER


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _play(
    game_id="G1", play_id=1, game_half="Half1", qtr=1,
    sp=0, touchdown=0, td_team=None, field_goal_result=None, safety=0,
    posteam="KC", defteam="BUF", home_team="KC",
    result=7.0, home_score=7, away_score=0,
    **kwargs,
) -> dict:
    base = dict(
        game_id=game_id, play_id=play_id, game_half=game_half, qtr=qtr,
        sp=sp, touchdown=touchdown, td_team=td_team,
        field_goal_result=field_goal_result, safety=safety,
        posteam=posteam, defteam=defteam, home_team=home_team,
        result=result, home_score=home_score, away_score=away_score,
        season=2024, down=1.0, yardline_100=75.0, ydstogo=10.0,
        half_seconds_remaining=1800.0, game_seconds_remaining=3600.0,
        score_differential=0.0, spread_line=-3.0,
        posteam_timeouts_remaining=3.0, defteam_timeouts_remaining=3.0,
        roof="outdoors",
    )
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# SCORE_LABEL_TO_CLASS contract
# ---------------------------------------------------------------------------

class TestScoreLabelToClass:
    def test_all_seven_classes_mapped(self):
        assert set(SCORE_LABEL_TO_CLASS.keys()) == set(EP_CLASS_ORDER)

    def test_class_indices_zero_to_six(self):
        assert set(SCORE_LABEL_TO_CLASS.values()) == set(range(7))

    def test_touchdown_is_class_0(self):
        assert SCORE_LABEL_TO_CLASS["Touchdown"] == 0

    def test_no_score_is_class_6(self):
        assert SCORE_LABEL_TO_CLASS["No_Score"] == 6


# ---------------------------------------------------------------------------
# compute_next_score_half — basic EP label tests
# ---------------------------------------------------------------------------

class TestComputeNextScoreHalf:
    def test_td_by_posteam_labels_preceding_play(self):
        """Play 1 (no score) followed by Play 2 (TD, posteam=KC scored) → Touchdown."""
        plays = [
            _play(game_id="G1", play_id=1, sp=0, posteam="KC", defteam="BUF"),
            _play(game_id="G1", play_id=2, sp=1, touchdown=1, td_team="KC",
                  posteam="KC", defteam="BUF"),
        ]
        df = pl.DataFrame(plays)
        result = compute_next_score_half(df)
        row0 = result.filter(pl.col("play_id") == 1)
        assert row0["next_score_half"][0] == "Touchdown"
        assert row0["next_score_class"][0] == SCORE_LABEL_TO_CLASS["Touchdown"]

    def test_td_by_defteam_labels_preceding_play_as_opp_touchdown(self):
        """Interception returned for TD by defteam → Opp_Touchdown for prior posteam."""
        plays = [
            _play(game_id="G2", play_id=1, sp=0, posteam="KC", defteam="BUF"),
            _play(game_id="G2", play_id=2, sp=1, touchdown=1, td_team="BUF",
                  posteam="KC", defteam="BUF"),
        ]
        df = pl.DataFrame(plays)
        result = compute_next_score_half(df)
        row0 = result.filter(pl.col("play_id") == 1)
        assert row0["next_score_half"][0] == "Opp_Touchdown"

    def test_field_goal_made_labels_fg(self):
        plays = [
            _play(game_id="G3", play_id=1, sp=0, posteam="KC"),
            _play(game_id="G3", play_id=2, sp=1, field_goal_result="made", posteam="KC"),
        ]
        df = pl.DataFrame(plays)
        result = compute_next_score_half(df)
        assert result.filter(pl.col("play_id") == 1)["next_score_half"][0] == "Field_Goal"

    def test_field_goal_missed_not_a_scoring_play(self):
        """A missed FG is not a score; next play is No_Score if nothing follows."""
        plays = [
            _play(game_id="G4", play_id=1, sp=0, posteam="KC", game_half="Half1"),
            _play(game_id="G4", play_id=2, sp=1, field_goal_result="missed",
                  posteam="KC", game_half="Half1"),
        ]
        df = pl.DataFrame(plays)
        result = compute_next_score_half(df)
        # play 1 has no successful score after it
        assert result.filter(pl.col("play_id") == 1)["next_score_half"][0] == "No_Score"

    def test_safety_labels_opp_safety(self):
        """Safety: defteam scored (posteam conceded) → from posteam perspective = Opp_Safety."""
        plays = [
            _play(game_id="G5", play_id=1, sp=0, posteam="KC", defteam="BUF"),
            _play(game_id="G5", play_id=2, sp=1, safety=1, posteam="KC", defteam="BUF"),
        ]
        df = pl.DataFrame(plays)
        result = compute_next_score_half(df)
        assert result.filter(pl.col("play_id") == 1)["next_score_half"][0] == "Opp_Safety"

    def test_opp_field_goal_after_possession_change(self):
        """posteam=KC, then BUF gains possession and kicks a made FG → Opp_Field_Goal
        from KC's perspective. Regression: the old labeler propagated the scoring play's
        own perspective unchanged and never produced Opp_Field_Goal (every FG was
        Field_Goal)."""
        plays = [
            _play(game_id="P1", play_id=1, sp=0, posteam="KC", defteam="BUF"),
            _play(game_id="P1", play_id=2, sp=1, field_goal_result="made",
                  posteam="BUF", defteam="KC"),
        ]
        result = compute_next_score_half(pl.DataFrame(plays))
        assert result.filter(pl.col("play_id") == 1)["next_score_half"][0] == "Opp_Field_Goal"

    def test_posteam_safety_when_own_defense_scores(self):
        """posteam=KC, then BUF possesses and concedes a safety (KC's defense scores +2)
        → Safety from KC's perspective. Regression: the +2 Safety class was never
        produced (all safeties were Opp_Safety)."""
        plays = [
            _play(game_id="P2", play_id=1, sp=0, posteam="KC", defteam="BUF"),
            _play(game_id="P2", play_id=2, sp=1, safety=1, posteam="BUF", defteam="KC"),
        ]
        result = compute_next_score_half(pl.DataFrame(plays))
        assert result.filter(pl.col("play_id") == 1)["next_score_half"][0] == "Safety"

    def test_no_score_in_half_returns_no_score(self):
        """No scoring play in the half → No_Score."""
        plays = [_play(game_id="G6", play_id=i, sp=0, game_half="Half1") for i in range(5)]
        df = pl.DataFrame(plays)
        result = compute_next_score_half(df)
        assert (result["next_score_half"] == "No_Score").all()

    def test_scoring_play_itself_gets_its_own_label(self):
        """The scoring play gets the label for THAT score (not a future one)."""
        plays = [
            _play(game_id="G7", play_id=1, sp=1, touchdown=1, td_team="KC",
                  posteam="KC", defteam="BUF"),
            _play(game_id="G7", play_id=2, sp=0, posteam="BUF", defteam="KC"),
        ]
        df = pl.DataFrame(plays)
        result = compute_next_score_half(df)
        assert result.filter(pl.col("play_id") == 1)["next_score_half"][0] == "Touchdown"

    def test_scope_is_within_same_game_half(self):
        """Score in Half2 does not label plays in Half1."""
        plays = [
            _play(game_id="G8", play_id=1, sp=0, game_half="Half1", posteam="KC"),
            _play(game_id="G8", play_id=2, sp=1, touchdown=1, td_team="KC",
                  game_half="Half2", posteam="KC"),
        ]
        df = pl.DataFrame(plays)
        result = compute_next_score_half(df)
        assert result.filter(pl.col("play_id") == 1)["next_score_half"][0] == "No_Score"

    def test_scope_is_within_same_game_id(self):
        """Score in G2 does not label plays in G1."""
        plays = [
            _play(game_id="G1", play_id=1, sp=0, game_half="Half1", posteam="KC"),
            _play(game_id="G2", play_id=2, sp=1, touchdown=1, td_team="KC",
                  game_half="Half1", posteam="KC"),
        ]
        df = pl.DataFrame(plays)
        result = compute_next_score_half(df)
        assert result.filter(pl.col("game_id") == "G1")["next_score_half"][0] == "No_Score"

    def test_first_score_wins_when_multiple_in_half(self):
        """Only the NEXT (closest future) scoring play matters."""
        plays = [
            _play(game_id="G9", play_id=1, sp=0, posteam="KC"),
            _play(game_id="G9", play_id=2, sp=1, field_goal_result="made", posteam="KC"),
            _play(game_id="G9", play_id=3, sp=1, touchdown=1, td_team="KC", posteam="KC"),
        ]
        df = pl.DataFrame(plays)
        result = compute_next_score_half(df)
        assert result.filter(pl.col("play_id") == 1)["next_score_half"][0] == "Field_Goal"

    def test_returns_next_score_class_column(self):
        plays = [_play(game_id="GA", play_id=1, sp=0)]
        result = compute_next_score_half(pl.DataFrame(plays))
        assert "next_score_class" in result.columns
        assert result["next_score_class"].dtype == pl.Int32


# ---------------------------------------------------------------------------
# compute_winner
# ---------------------------------------------------------------------------

class TestComputeWinner:
    def test_home_team_wins(self):
        plays = [_play(game_id="W1", home_score=21, away_score=14,
                       home_team="KC", posteam="KC")]
        result = compute_winner(pl.DataFrame(plays))
        row = result.filter(pl.col("game_id") == "W1")
        assert row["winner"][0] == "KC"  # home wins
        assert row["wp_label"][0] == 1.0   # KC is posteam, KC won

    def test_away_team_wins(self):
        plays = [_play(game_id="W2", home_score=14, away_score=21,
                       home_team="KC", posteam="BUF", defteam="KC")]
        result = compute_winner(pl.DataFrame(plays))
        row = result.filter(pl.col("game_id") == "W2")
        assert row["winner"][0] == "BUF"
        assert row["wp_label"][0] == 1.0  # BUF is posteam, BUF won

    def test_tie_gives_no_label(self):
        plays = [_play(game_id="W3", home_score=21, away_score=21,
                       home_team="KC", posteam="KC")]
        result = compute_winner(pl.DataFrame(plays))
        assert result.filter(pl.col("game_id") == "W3")["wp_label"][0] is None


# ---------------------------------------------------------------------------
# build_ep_training_set
# ---------------------------------------------------------------------------

class TestBuildEpTrainingSet:
    def test_contains_ep_features_and_label(self):
        from model_training.track6_nfl_ep_wp.constants import EP_FEATURES

        plays = [
            _play(game_id="T1", play_id=1, sp=0, posteam="KC"),
            _play(game_id="T1", play_id=2, sp=1, touchdown=1, td_team="KC", posteam="KC"),
        ]
        df = pl.DataFrame(plays)
        result = build_ep_training_set(df)
        for col in EP_FEATURES:
            assert col in result.columns, f"Missing EP feature column: {col}"
        assert "next_score_class" in result.columns

    def test_no_nulls_in_features_for_complete_plays(self):
        from model_training.track6_nfl_ep_wp.constants import EP_FEATURES

        plays = [_play(game_id="T2", play_id=i, sp=0, down=1.0) for i in range(5)]
        df = pl.DataFrame(plays)
        result = build_ep_training_set(df)
        for col in EP_FEATURES:
            nulls = result[col].null_count()
            assert nulls == 0, f"Unexpected nulls in {col}"


# ---------------------------------------------------------------------------
# build_wp_training_set
# ---------------------------------------------------------------------------

class TestBuildWpTrainingSet:
    def test_contains_wp_features_and_label(self):
        from model_training.track6_nfl_ep_wp.constants import WP_SPREAD_FEATURES

        plays = [_play(game_id="V1", play_id=i, qtr=min(i + 1, 4)) for i in range(4)]
        df = pl.DataFrame(plays)
        result = build_wp_training_set(df, variant="spread")
        for col in WP_SPREAD_FEATURES:
            assert col in result.columns, f"Missing WP feature: {col}"
        assert "label" in result.columns

    def test_overtime_plays_excluded(self):
        plays = [
            _play(game_id="V2", play_id=1, qtr=4),
            _play(game_id="V2", play_id=2, qtr=5),  # OT
        ]
        df = pl.DataFrame(plays)
        result = build_wp_training_set(df, variant="spread")
        assert result.height == 1

    def test_tied_games_excluded_from_wp(self):
        plays = [_play(game_id="V3", play_id=1, qtr=4, home_score=21, away_score=21)]
        df = pl.DataFrame(plays)
        result = build_wp_training_set(df, variant="spread")
        assert result.height == 0
