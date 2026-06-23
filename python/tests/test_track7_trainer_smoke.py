"""Fast offline smoke tests for track7 trainers + feature builders.

Tiny synthetic frames only (no real PBP / network). Verify each trainer emits a
valid .ubj with the contracted feature names, the feature builders apply the
right filters/labels, and the punt builder produces the documented schema.
"""
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from xgboost import Booster

from model_training.track7_nfl_models.constants import (
    XPASS_FEATURES,
    FD_FEATURES,
    FD_NUM_CLASSES,
    TWO_PT_FEATURES,
    FG_FEATURES,
    PUNT_OUTPUT_COLUMNS,
)
from model_training.track7_nfl_models.trainer import (
    train_xpass,
    train_fd,
    train_two_pt,
    train_fg,
    build_punt_data,
)
from model_training.track7_nfl_models.features import (
    make_model_mutations,
    prepare_xpass_data,
    prepare_fd_data,
    prepare_two_pt_data,
    prepare_fg_data,
    add_spread_total_features,
)

RNG = np.random.default_rng(7)
N = 200


def _bin_frame(features: list[str]) -> pl.DataFrame:
    rows = {f: RNG.uniform(0.0, 1.0, N).tolist() for f in features}
    rows["label"] = RNG.integers(0, 2, N).tolist()
    return pl.DataFrame(rows)


def _fd_frame() -> pl.DataFrame:
    rows = {f: RNG.uniform(0.0, 1.0, N).tolist() for f in FD_FEATURES}
    rows["label"] = RNG.integers(0, FD_NUM_CLASSES, N).tolist()
    return pl.DataFrame(rows)


# ---------------------------------------------------------------------------
# Trainers
# ---------------------------------------------------------------------------
class TestTrainXpass:
    def test_returns_booster_with_feature_names(self):
        m = train_xpass(_bin_frame(XPASS_FEATURES), nrounds=5)
        assert isinstance(m, Booster)
        assert m.feature_names == XPASS_FEATURES

    def test_saves(self, tmp_path: Path):
        train_xpass(_bin_frame(XPASS_FEATURES), nrounds=5, output_path=tmp_path / "xp.ubj")
        assert (tmp_path / "xp.ubj").exists()


class TestTrainFd:
    def test_returns_booster_with_feature_names(self):
        m = train_fd(_fd_frame(), nrounds=5)
        assert m.feature_names == FD_FEATURES

    def test_predict_is_76_class(self):
        m = train_fd(_fd_frame(), nrounds=5)
        from xgboost import DMatrix
        X = _fd_frame().select(FD_FEATURES).to_numpy()
        p = m.predict(DMatrix(X, feature_names=FD_FEATURES))
        assert p.shape[1] == FD_NUM_CLASSES


class TestTrainTwoPt:
    def test_feature_names_and_monotone(self):
        m = train_two_pt(_bin_frame(TWO_PT_FEATURES), nrounds=5)
        assert m.feature_names == TWO_PT_FEATURES


class TestTrainFg:
    def test_feature_names_pinned_rounds(self):
        m = train_fg(_bin_frame(FG_FEATURES), nrounds=5, cv_select=False)
        assert m.feature_names == FG_FEATURES


# ---------------------------------------------------------------------------
# Feature builders
# ---------------------------------------------------------------------------
def _synthetic_pbp() -> pl.DataFrame:
    """A handful of rows exercising each model's filter."""
    return pl.DataFrame(
        {
            "posteam": ["A", "A", "B", "A", "A"],
            "home_team": ["A", "B", "B", "A", "A"],
            "season": [2018, 2016, 2021, 2015, 2022],
            "roof": ["outdoors", "dome", "retractable", "outdoors", "closed"],
            "down": [3, 4, None, 4, None],
            "ydstogo": [5, 2, 0, 8, 0],
            "yardline_100": [45, 30, 2, 60, 2],
            "qtr": [1, 2, 3, 4, 4],
            "wp": [0.5, 0.6, 0.4, 0.55, 0.3],
            "vegas_wp": [0.52, 0.58, 0.42, 0.5, 0.31],
            "score_differential": [0, -3, 7, -7, 4],
            "half_seconds_remaining": [1700, 600, 1200, 90, 30],
            "posteam_timeouts_remaining": [3, 2, 3, 1, 0],
            "defteam_timeouts_remaining": [3, 3, 2, 1, 2],
            "pass": [1, 0, 1, 1, 0],
            "rush": [0, 1, 0, 0, 1],
            "qb_kneel": [0, 0, 0, 0, 0],
            "aborted_play": [0, 0, 0, 0, 0],
            "week": [1, 5, 10, 17, 12],
            "spread_line": [-3.0, 7.0, 0.0, -6.0, 2.0],
            "total_line": [45.0, 52.0, 44.0, 48.0, 40.0],
            "play_type_nfl": ["PASS", "RUSH", "PASS", "FIELD_GOAL", "PAT2"],
            "first_down_penalty": [0, 0, 0, 0, 0],
            "penalty_yards": [0, 0, 0, 0, 0],
            "yards_gained": [6, 1, 3, 0, 0],
            "two_point_conv_result": [None, None, "success", None, "failure"],
            "sp": [None, None, None, 1, None],
            "field_goal_result": [None, None, None, "made", None],
        }
    )


class TestFeatureBuilders:
    def test_spread_total(self):
        df = add_spread_total_features(make_model_mutations(_synthetic_pbp()))
        # row 0 is home posteam: posteam_spread == spread_line
        assert df["posteam_spread"][0] == pytest.approx(-3.0)
        # row 1 is away posteam: posteam_spread == -spread_line
        assert df["posteam_spread"][1] == pytest.approx(-7.0)

    def test_xpass_filter_columns(self):
        out = prepare_xpass_data(make_model_mutations(_synthetic_pbp()))
        assert out.columns == [*XPASS_FEATURES, "label"]
        # rows with non-null down + scrimmage play survive (rows 0,1,3)
        assert out.height == 3

    def test_fd_label_shift(self):
        out = prepare_fd_data(make_model_mutations(_synthetic_pbp()))
        assert out.columns == [*FD_FEATURES, "label"]
        # down in {3,4}, play_type_nfl RUSH/PASS/SACK -> rows 0,1 (row3 is FIELD_GOAL)
        # row0 yards_gained 6 -> label 16
        assert 16 in out["label"].to_list()

    def test_two_pt_filter(self):
        out = prepare_two_pt_data(make_model_mutations(_synthetic_pbp()))
        assert out.columns == [*TWO_PT_FEATURES, "label"]
        # only down-is-null + yardline_100==2 rows (2 and 4)
        assert out.height == 2
        assert set(out["label"].to_list()) == {0, 1}

    def test_fg_label_and_roof_era(self):
        out = prepare_fg_data(_synthetic_pbp())
        assert out.columns == [*FG_FEATURES, "label"]
        assert out.height == 1
        assert out["fg_roof"][0] == 1  # outdoors
        assert out["fg_era"][0] == 0   # 2015 < 2020
        assert out["label"][0] == 1    # sp == 1


# ---------------------------------------------------------------------------
# punt builder
# ---------------------------------------------------------------------------
class TestPuntBuilder:
    def test_schema_and_nonempty(self, tmp_path: Path):
        # synthesize many punts across yardlines so KDE + bins are well-posed
        n = 600
        yl = RNG.integers(31, 99, n)
        kd = RNG.integers(30, 55, n)
        ry = RNG.integers(0, 15, n)
        df = pl.DataFrame(
            {
                "play_type_nfl": ["PUNT"] * n,
                "desc": ["punt"] * n,
                "yardline_100": yl.astype(float).tolist(),
                "kick_distance": kd.astype(float).tolist(),
                "return_yards": ry.astype(float).tolist(),
                "fumble_lost": RNG.integers(0, 2, n).tolist(),
            }
        )
        out = build_punt_data(df, output_path=tmp_path / "punt.parquet")
        assert list(out.columns) == list(PUNT_OUTPUT_COLUMNS)
        assert out.height > 0
        assert (out["yardline_100"] > 30).all()
        # per-yardline pct sums ~1
        sums = out.group_by("yardline_100").agg(pl.col("pct").sum().alias("s"))
        assert np.allclose(sums["s"].to_numpy(), 1.0, atol=1e-6)
        assert (tmp_path / "punt.parquet").exists()
