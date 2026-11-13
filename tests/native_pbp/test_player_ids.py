"""nfl_model_pbp's ``receiver`` / ``receiver_id`` against nflverse's, on real plays.

Fixtures (``tests/fixtures/receiver_targets/README.md``): Detroit's 2003 and Cleveland's 2004
offense, cut from ``nfl_model_pbp``, with nflverse's ``receiver_id`` for the same plays as the
oracle. 2003-2008 Shield stats name no target on an incompletion; 2004 CLE carries
"Andre' Davis", whose apostrophe stops the name parser.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from native_pbp.cli import _add_receiver_ids, build_season

FIX = Path(__file__).parent.parent / "fixtures" / "receiver_targets"
THROWN = (pl.col("pass_attempt") == 1) & (pl.col("sack") == 0)


@pytest.mark.parametrize(
    ("name", "season", "thrown_null_before"),
    [("model_pbp_2003_det", 2003, 269), ("model_pbp_2004_cle", 2004, 188)],
)
def test_receiver_id_matches_nflverse(name, season, thrown_null_before):
    plays = pl.read_parquet(FIX / f"{name}.parquet").with_columns(season=pl.lit(season, pl.Int64))
    assert plays.filter(THROWN)["receiver_player_id"].null_count() == thrown_null_before

    out = _add_receiver_ids(plays)

    assert out.filter(pl.col("receiver_id").ne_missing(pl.col("nflverse_receiver_id"))).height == 0
    # a target is named on all but a handful of throws (throwaways, spikes, no "to X")
    assert out.filter(THROWN)["receiver_id"].null_count() < 20
    # appended, nothing else touched
    assert out.columns == [*plays.columns, "receiver", "receiver_id"]
    assert out.drop("receiver", "receiver_id").equals(plays)


def test_receiver_on_every_receiver_id():
    plays = pl.read_parquet(FIX / "model_pbp_2003_det.parquet").with_columns(
        season=pl.lit(2003, pl.Int64)
    )
    out = _add_receiver_ids(plays)
    assert (
        out.filter(pl.col("receiver_id").is_not_null() & pl.col("receiver").is_null()).height == 0
    )


def test_empty_frame_gets_typed_columns():
    out = _add_receiver_ids(pl.DataFrame({"game_id": pl.Series([], dtype=pl.String)}))
    assert out.schema["receiver"] == pl.String
    assert out.schema["receiver_id"] == pl.String


def test_build_season_writes_receiver_columns(tmp_path):
    from tests.native_pbp.test_cli import _seed_raw_dir

    out = pl.read_parquet(
        build_season(2024, raw_dir=_seed_raw_dir(tmp_path / "raw"), out_dir=tmp_path / "out")
    )
    assert {"receiver", "receiver_id"} <= set(out.columns)
