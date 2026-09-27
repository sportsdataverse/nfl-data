"""The 1999-2002 thin Shield game backfill in ``native_pbp.cli``, on REAL fixtures.

api.nfl.com serves ``driveChart.plays`` as GAME_START/END_GAME plus a stray play for every
2000-2001 game, 2002 weeks 1-15 and six late-1999 games; ``build_season`` swaps those stubs
for nflverse pbp rows conformed to the build schema. The fixtures are real nfl-raw Shield
payloads and those games' real nflverse rows (``tests/fixtures/shield_thin/README.md``);
``load_nfl_pbp`` is monkeypatched to serve the nflverse rows, so the tests stay offline.
"""

from __future__ import annotations

import gzip
from pathlib import Path

import polars as pl
import pytest
from native_pbp.build import build_season as build_season_frame
from native_pbp.cli import _INT64_YARDS, _backfill_thin_games, build_season
from polars.testing import assert_frame_equal

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "shield_thin"
NV = pl.read_parquet(FIX / "nflverse_pbp.parquet")

KC_OAK, SD_KC, BUF_MIA = "2000_10_KC_OAK", "2000_03_SD_KC", "2000_06_BUF_MIA"
STL_PHI, MIA_MIN, CAR_HOU = "2002_13_STL_PHI", "2002_16_MIA_MIN", "2003_09_CAR_HOU"


@pytest.fixture
def nflverse(monkeypatch):
    """Serve the fixture's real nflverse rows for the requested seasons; record the calls."""
    calls: list[list[int]] = []

    def _load(seasons):
        calls.append(list(seasons))
        return NV.filter(pl.col("season").is_in(list(seasons)))

    monkeypatch.setattr("sportsdataverse.nfl.load_nfl_pbp", _load)
    return calls


def _raw(tmp_path: Path, *game_ids: str) -> Path:
    """Lay the gzipped fixture payloads out as a ``{raw_dir}/{season}/{game_id}.json`` library."""
    for g in game_ids:
        d = tmp_path / "raw" / g[:4]
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{g}.json").write_bytes(
            gzip.decompress((FIX / "raw" / g[:4] / f"{g}.json.gz").read_bytes())
        )
    return tmp_path / "raw"


def _build(tmp_path: Path, season: int, *game_ids: str) -> pl.DataFrame:
    """Run the real CLI ``build_season`` (no enrich) and read back the written parquet."""
    raw = _raw(tmp_path, *game_ids)
    return pl.read_parquet(build_season(season, raw_dir=raw, out_dir=tmp_path / "out"))


def _nv_play_ids(game_id: str) -> set[int]:
    return set(NV.filter(pl.col("game_id") == game_id)["play_id"].cast(pl.Int64).to_list())


def _team_values(df: pl.DataFrame) -> set[str]:
    cols = [
        c
        for c, dt in df.schema.items()
        if dt == pl.String and (c in ("posteam", "defteam") or c.endswith("_team"))
    ]
    return {v for c in cols for v in df[c].drop_nulls().to_list()}


# --------------------------------------------------------------------------- 2001+ shape


def test_thin_2002_game_is_replaced_by_nflverse_rows_minus_markers(tmp_path, nflverse):
    raw = _raw(tmp_path / "stub", STL_PHI)
    assert build_season_frame(2002, raw_dir=raw).height < 100  # the Shield payload is a stub

    g = _build(tmp_path, 2002, STL_PHI, MIA_MIN).filter(pl.col("game_id") == STL_PHI)

    # nflverse has 181 rows; the 7 play_type_nfl == "TIMEOUT" markers go (the Shield build
    # drops its TIMEOUT rows) -- including play 1981, whose desc opens with a comment
    markers = {784, 840, 1981, 2520, 3142, 3846, 3884}
    assert g.height == 181 - len(markers)
    assert set(g["play_id"].to_list()) == _nv_play_ids(STL_PHI) - markers
    # kept: a real pass nflverse also flags timeout == 1, and the END QUARTER / END GAME rows
    # (null timeout) the Shield build keeps too
    assert {1763, 1083, 2143, 3067, 4083} <= set(g["play_id"].to_list())
    assert nflverse == [[2002]]


# --------------------------------------------------------------------------- 1999-2000 shape


def test_thin_2000_game_drops_timeouts_and_two_minute_warnings_only(tmp_path, nflverse):
    g = _build(tmp_path, 2000, KC_OAK, SD_KC, BUF_MIA).filter(pl.col("game_id") == KC_OAK)

    # 1999-2000 markers carry only the desc: "Timeout #2 by KC at 01:38." (null play_type),
    # "Timeout at 10:22. Injury timeout ..." and "Two-Minute Warning" (null timeout too)
    timeouts = {285, 2016, 3093, 3340, 3412, 3737, 4211}
    two_minute = {1936, 3991}
    assert g.height == 199 - len(timeouts) - len(two_minute)
    assert set(g["play_id"].to_list()) == _nv_play_ids(KC_OAK) - timeouts - two_minute
    # kept: a real run nflverse flags timeout == 1, a captains comment, END QUARTER/GAME
    assert {761, 17, 999, 2217, 3149, 4364} <= set(g["play_id"].to_list())


def test_all_null_stub_column_keeps_nflverse_values(tmp_path, nflverse):
    stub = build_season_frame(2000, raw_dir=_raw(tmp_path / "stub", KC_OAK, SD_KC, BUF_MIA))
    # a stub-only season: the column is all-null, so Null-typed
    assert stub.schema["qb_hit_1_player_id"] == pl.Null

    g = _build(tmp_path, 2000, KC_OAK, SD_KC, BUF_MIA)

    want = NV.filter(pl.col("game_id") == KC_OAK, pl.col("qb_hit_1_player_id").is_not_null())
    assert want.height == 4
    got = g.filter(pl.col("qb_hit_1_player_id").is_not_null())["qb_hit_1_player_id"]
    assert sorted(got.to_list()) == sorted(want["qb_hit_1_player_id"].to_list())


def test_team_codes_use_the_era_abbreviation(tmp_path, nflverse):
    # nflverse ships the modern LA / LV and, on some 1999-2000 non-play rows, "" for posteam
    nv_teams = {v for c in ("posteam", "timeout_team") for v in NV[c].drop_nulls().to_list()}
    assert {"LA", "LV", ""} <= nv_teams

    g00 = _build(tmp_path / "a", 2000, KC_OAK, SD_KC, BUF_MIA)
    g02 = _build(tmp_path / "b", 2002, STL_PHI, MIA_MIN)

    assert _team_values(g00) == {"KC", "OAK"}
    assert _team_values(g02) == {"STL", "PHI", "MIA", "MIN"}
    assert g00.filter(pl.col("play_id") == 761)["posteam"].to_list() == ["OAK"]  # was LV
    assert g00.filter(pl.col("play_id") == 17)["posteam"].to_list() == [None]  # was ""
    # `home` as the build emits it: Int64 1/0, never null -- 0 when posteam is null
    assert g00.schema["home"] == pl.Int64 and g00["home"].null_count() == 0
    home = dict(g00.filter(pl.col("play_id").is_in([761, 17])).select("play_id", "home").rows())
    assert home == {761: 1, 17: 0}  # OAK's ball at OAK; a no-posteam captains row


def test_drive_yard_lines_follow_the_build_not_nflverse_strings(tmp_path, nflverse):
    ref = build_season_frame(2003, raw_dir=_raw(tmp_path / "ref", CAR_HOU))
    g = _build(tmp_path, 2002, STL_PHI, MIA_MIN).filter(pl.col("game_id") == STL_PHI)

    for c in ("drive_start_yard_line", "drive_end_yard_line"):
        assert g.schema[c] == ref.schema[c] == pl.Int64
        assert g[c].is_not_null().mean() > 0.9
    first = (
        g.group_by("fixed_drive").agg(pl.col("drive_start_yard_line").first()).sort("fixed_drive")
    )
    by_drive = dict(zip(first["fixed_drive"].to_list(), first["drive_start_yard_line"].to_list()))
    # nflverse: drive 3 "PHI 20" (PHI's ball) -> 80 to go; drive 5 "LA 24" (PHI's ball) -> 24
    assert (by_drive[3], by_drive[5]) == (80, 24)


# --------------------------------------------------------------------------- schema + scope


def test_backfilled_seasons_carry_the_2003_column_set(tmp_path, nflverse):
    ref = build_season_frame(2003, raw_dir=_raw(tmp_path / "ref", CAR_HOU))
    g00 = _build(tmp_path / "a", 2000, KC_OAK, SD_KC, BUF_MIA)
    g02 = _build(tmp_path / "b", 2002, STL_PHI, MIA_MIN)
    assert set(g00.columns) == set(ref.columns) == set(g02.columns)
    # Null-typed in the stubs, nflverse Float64: cast to the published assets' Int64
    for c in _INT64_YARDS:
        assert NV.schema[c] == pl.Float64
        assert g00.schema[c] == g02.schema[c] == pl.Int64, c


def test_full_length_2002_game_is_untouched(tmp_path, nflverse):
    raw = _raw(tmp_path / "stub", STL_PHI, MIA_MIN)
    before = build_season_frame(2002, raw_dir=raw).filter(pl.col("game_id") == MIA_MIN)
    assert before.height >= 100

    after = _build(tmp_path, 2002, STL_PHI, MIA_MIN).filter(pl.col("game_id") == MIA_MIN)

    # dtypes may widen where every game was null (Null -> the backfill's dtype); values may not move
    assert_frame_equal(after, before, check_dtypes=False)


def test_2003_game_is_untouched_even_when_thin(tmp_path, nflverse):
    raw = _raw(tmp_path, CAR_HOU)
    # a real 2003 game, cut below the threshold
    thin = build_season_frame(2003, raw_dir=raw).head(40)

    assert _backfill_thin_games(thin, 2003, raw) is thin
    assert nflverse == []  # no nflverse fetch for a Shield-complete season


def test_games_with_no_data_anywhere_are_dropped_and_logged(tmp_path, nflverse, capsys):
    g = _build(tmp_path, 2000, KC_OAK, SD_KC, BUF_MIA)

    assert g["game_id"].unique().to_list() == [KC_OAK]  # the SD_KC stub rows do not survive
    out = capsys.readouterr().out
    assert "model_pbp 2000: backfilled 1 thin Shield game(s) from nflverse" in out
    assert f"no play data anywhere: ['{SD_KC}', '{BUF_MIA}']" in out


def test_partial_raw_library_backfills_only_its_own_games(tmp_path, nflverse, capsys):
    # nflverse has KC_OAK, but it is missing from this raw library: never pulled in or counted
    g = _build(tmp_path, 2000, SD_KC, BUF_MIA)

    assert KC_OAK not in g["game_id"].to_list()
    out = capsys.readouterr().out
    assert "model_pbp 2000: backfilled 0 thin Shield game(s) from nflverse" in out
    assert f"no play data anywhere: ['{SD_KC}', '{BUF_MIA}']" in out


def test_fractional_value_bound_for_an_int64_column_fails_loudly(tmp_path, monkeypatch):
    # polars' strict Float64 -> Int64 cast would truncate 1.5 to 1 silently
    bump = pl.when(pl.col("play_id") == 761).then(1.5).otherwise(pl.col("yards_after_catch"))
    nv = NV.with_columns(yards_after_catch=bump)
    monkeypatch.setattr(
        "sportsdataverse.nfl.load_nfl_pbp",
        lambda seasons: nv.filter(pl.col("season").is_in(list(seasons))),
    )
    with pytest.raises(ValueError, match="fractional nflverse values.*yards_after_catch"):
        _build(tmp_path, 2000, KC_OAK)
