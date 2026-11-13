"""nfl_model_pbp's clean_pbp player columns against nflverse's, on real plays.

Fixtures (``tests/fixtures/receiver_targets/README.md``) are cut from ``nfl_model_pbp`` with
nflverse's ids for the same plays as the oracle:

- Detroit 2003 and Cleveland 2004: 2003-2008 Shield stats name no target on an incompletion,
  and 2004 CLE carries "Andre' Davis", whose apostrophe stops the name parser.
- Arizona 2003: 46 charted scrambles. nflfastR #536 (2025-10-10) makes the scrambling QB the
  passer on 1999-2005 charted scrambles. nflverse's 2003 release (2025-04-30) predates it and
  still has him as the rusher, so those rows are the one intended difference.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from native_pbp.cli import _PLAYER_ID_COLUMNS, _add_player_ids, build_season

FIX = Path(__file__).parent.parent / "fixtures" / "receiver_targets"
THROWN = (pl.col("pass_attempt") == 1) & (pl.col("sack") == 0)


def _plays(name: str, season: int) -> pl.DataFrame:
    return pl.read_parquet(FIX / f"{name}.parquet").with_columns(season=pl.lit(season, pl.Int64))


@pytest.mark.parametrize(
    ("name", "season", "thrown_null_before"),
    [("model_pbp_2003_det", 2003, 269), ("model_pbp_2004_cle", 2004, 188)],
)
def test_receiver_id_matches_nflverse(name, season, thrown_null_before):
    plays = _plays(name, season)
    assert plays.filter(THROWN)["receiver_player_id"].null_count() == thrown_null_before

    out = _add_player_ids(plays)

    assert out.filter(pl.col("receiver_id").ne_missing(pl.col("nflverse_receiver_id"))).height == 0
    # a target is named on all but a handful of throws (throwaways, spikes, no "to X")
    assert out.filter(THROWN)["receiver_id"].null_count() < 20
    # appended, nothing else touched
    assert out.columns == [*plays.columns, *_PLAYER_ID_COLUMNS]
    assert out.drop(_PLAYER_ID_COLUMNS).equals(plays)


def test_passer_rusher_match_nflverse_but_for_charted_scrambles():
    plays = _plays("model_pbp_2003_ari", 2003)
    out = _add_player_ids(plays)
    scramble = pl.col("qb_scramble") == 1
    assert out.filter(scramble).height == 46

    rest = out.filter(~scramble)
    assert rest.filter(pl.col("passer_id").ne_missing(pl.col("nflverse_passer_id"))).height == 0
    assert rest.filter(pl.col("rusher_id").ne_missing(pl.col("nflverse_rusher_id"))).height == 0

    # nflfastR #536: the scrambling QB is the passer, and the play has no rusher
    scr = out.filter(scramble)
    assert scr["nflverse_rusher_id"].null_count() == 0
    assert scr.filter(pl.col("passer_id").ne_missing(pl.col("nflverse_rusher_id"))).height == 0
    assert scr["rusher_id"].null_count() == 46


def test_names_ride_with_ids():
    out = _add_player_ids(_plays("model_pbp_2003_det", 2003))
    for who in ("passer", "rusher", "receiver"):
        assert out.filter(pl.col(f"{who}_id").is_not_null() & pl.col(who).is_null()).height == 0


def test_empty_frame_gets_typed_columns():
    out = _add_player_ids(pl.DataFrame({"game_id": pl.Series([], dtype=pl.String)}))
    assert all(out.schema[c] == pl.String for c in _PLAYER_ID_COLUMNS)


def test_build_season_writes_player_columns(tmp_path):
    from tests.native_pbp.test_cli import _seed_raw_dir

    out = pl.read_parquet(
        build_season(2024, raw_dir=_seed_raw_dir(tmp_path / "raw"), out_dir=tmp_path / "out")
    )
    assert set(_PLAYER_ID_COLUMNS) <= set(out.columns)
