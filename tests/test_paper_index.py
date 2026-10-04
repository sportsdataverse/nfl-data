"""Stage 09 (``nfl_paper_index_games``) and the luck columns on ``nfl_team_summaries``,
over real published 2022 rows.

Provenance and the hand numbers behind every literal here:
tests/fixtures/paper_index/README.md. Nothing in this module can reach the network
or a release: the pbp slice is read from a tmp dir, and ``requests.get``, the ``gh``
runner and the release sidecars are refused for every test. The CLI tests that pass
``--publish`` stub the upload seam.
"""

from __future__ import annotations

import logging
import math
import os
import shutil
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path

import polars as pl
import pytest
import sportsdataverse.paper_index as pi
import yaml
from nfl_model_publish import artifacts
from nfl_model_publish.artifacts import _RELEASE_BODY, PKG_FUNCTION
from nfl_team_summaries import paper_index as stage
from nfl_team_summaries.__main__ import SPLITS, TABLES
from nfl_team_summaries.build import _teams_lookup
from nfl_team_summaries.input import prepare_plays
from nfl_team_summaries.league_averages import CATEGORIES, metric_columns
from nfl_team_summaries.paper_index import (
    FLOOR,
    LUCK_COLUMNS,
    STEM,
    TAG,
    attach_luck,
    build_paper_index_games,
    main,
    paper_index_games_table,
    paper_index_span,
    season_games,
)
from polars.testing import assert_frame_equal

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "paper_index"
SEASON = 2022
NYG, TEN, GB, NE, JAX, WSH, NO, ATL, PHI, MIN = 19, 10, 9, 17, 30, 28, 18, 1, 21, 16  # ESPN ids
WEEK_1, WEEK_4, WEEK_7, TIE, WEEK_15, WEEK_18, WILD_CARD = (
    401437640,
    401437759,
    401437796,
    401437880,
    401437905,
    401437957,
    401438001,
)
#: the nflverse ids of the fixture's regular-season games: what stage 06's plays carry
REG_IDS = [
    "2022_01_NYG_TEN",
    "2022_04_NE_GB",
    "2022_07_NYG_JAX",
    "2022_13_WAS_NYG",  # the 20-20 tie
    "2022_15_ATL_NO",
    "2022_18_NYG_PHI",
]
PLAYOFF_ID = "2022_19_NYG_MIN"
#: the Giants' share in each of their three scored regular-season games (README)
NYG_SHARES = {
    WEEK_1: 0.3892217089209761,
    WEEK_7: 0.6659481674306241,
    WEEK_18: 0.2673060257282711,
}
#: fragments that mark an outcome-derived column, however it is later suffixed
OUTCOME_FRAGMENTS = ("deserved_wins", "luck_wins", "luck_z", "paper_index")


def _pbp() -> pl.DataFrame:
    return pl.read_parquet(FIX / "espn_nfl_pbp_2022_slice.parquet")


def _refuse(*args, **kwargs):
    raise AssertionError("a paper_index test reached the network or a release")


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setattr("requests.get", _refuse)  # load_espn_pbp's release fallback
    for name in ("_gh_runner", "_gh_release_exists", "upload_release_sidecars"):
        monkeypatch.setattr(artifacts, name, _refuse)


def _pbp_dir(root: Path, pbp: pl.DataFrame | None = None, season: int = SEASON) -> Path:
    """A ``--pbp-dir`` holding the slice (or ``pbp``) under the name the stage reads."""
    path = root / f"play_by_play_{season}.parquet"
    if pbp is None:
        shutil.copyfile(FIX / "espn_nfl_pbp_2022_slice.parquet", path)
    else:
        pbp.write_parquet(path)
    return root


def _teams(season: int = SEASON) -> pl.DataFrame:
    """The identity columns of a season's ``team_summaries``: the 32 real teams."""
    return _teams_lookup().with_columns(season=pl.lit(season, dtype=pl.Int64))


def _luck(root: Path, ids: list[str] = REG_IDS, pbp: pl.DataFrame | None = None) -> pl.DataFrame:
    """Stage 06's two calls, on the slice: cut by the plays' ids, then attach."""
    return attach_luck(_teams(), season_games(SEASON, pl.Series(ids), _pbp_dir(root, pbp)), SEASON)


def _row(df: pl.DataFrame, team: int) -> dict:
    return df.filter(pl.col("team_id") == team).row(0, named=True)


@pytest.fixture()
def games() -> pl.DataFrame:
    return paper_index_games_table(_pbp(), SEASON)


@pytest.fixture()
def luck(tmp_path) -> pl.DataFrame:
    return _luck(tmp_path)


# --- the per-game table ---------------------------------------------------------------


def test_schema_is_t1_plus_the_span_with_int_ids(games):
    assert games.schema == pl.Schema(
        {
            "game_id": pl.Int64,
            "team_id": pl.Int64,
            **pi.GAMES_SCHEMA,
            "paper_index_span": pl.Utf8,
        }
    )
    assert games.height == 12  # six scored games, one row per team
    assert not games.select("game_id", "team_id").is_duplicated().any()
    assert games["paper_index_span"].unique().to_list() == ["holdout"]


def test_t1_rows_pass_through_unchanged(games):
    t1 = pi.paper_index_games(_pbp().select(pi.PBP_COLUMNS), "nfl")
    assert_frame_equal(games.drop("paper_index_span"), t1)


def test_each_games_two_shares_sum_to_one(games):
    per_game = games.group_by("game_id").agg(
        total=pl.col("paper_share").sum(), sides=pl.len(), winners=pl.col("won").sum()
    )
    assert per_game["sides"].unique().to_list() == [2]
    assert per_game["winners"].unique().to_list() == [1]
    assert all(math.isclose(t, 1.0, abs_tol=1e-12) for t in per_game["total"])
    # and each row's opp_share is the other row's paper_share
    assert all(
        math.isclose(a + b, 1.0, abs_tol=1e-12)
        for a, b in zip(games["paper_share"], games["opp_share"])
    )


@pytest.mark.parametrize(
    ("game_id", "home", "trainer_share", "gop_share"),
    [
        (WEEK_7, JAX, 0.3340565130289467, 0.334051832569376),
        (WEEK_15, NO, 0.47358853727444855, 0.47360223401106105),
        (WEEK_1, TEN, 0.6107839271392764, 0.6107782910790238),
        (WEEK_4, GB, 0.7496201860489962, 0.7496249078045325),
    ],
)
def test_oracle_parity_through_the_producer(tmp_path, game_id, home, trainer_share, gop_share):
    """sdv-py's four 2022 oracle games, computed by the stage builder from the pbp file."""
    built = build_paper_index_games(SEASON, _pbp_dir(tmp_path))
    share = built.filter((pl.col("game_id") == game_id) & (pl.col("team_id") == home))[
        "paper_share"
    ].item()
    # Game on Paper's own module on these rows (4-decimal weights, as shipped)
    assert share == pytest.approx(gop_share, abs=1e-9)
    # the trainer's full-precision share: GOP's oracle test holds 5e-4
    assert share == pytest.approx(trainer_share, abs=5e-4)


def test_a_tie_has_no_row_and_counts_nowhere(games, luck):
    """T1 drops a game without a winner: the 20-20 Washington-Giants game is neither a
    game, a win nor a loss -- not half a win."""
    assert TIE not in games["game_id"].to_list()
    assert TIE in _pbp()["game_id"].unique().to_list()  # it is in the pbp, and completed
    assert _row(luck, NYG)["paper_index_games_n"] == 3  # four regular-season games played
    wsh = _row(luck, WSH)  # Washington's only fixture game is the tie
    assert wsh["paper_index_games_n"] == 0
    assert wsh["deserved_wins"] is None and wsh["luck_wins"] is None and wsh["luck_z"] is None
    assert wsh["luck_wins_rank"] is None and wsh["luck_z_rank"] is None


def test_a_game_under_the_snap_floor_is_in_neither_table(tmp_path):
    """No released NFL game sits under T1's floor (README), so the case is a real game cut
    short: the first 52 plays of Atlanta at New Orleans leave Atlanta 19 scrimmage snaps."""
    pbp = _pbp()
    game = pbp.filter(pl.col("game_id") == WEEK_15).sort("game_play_number")
    rest = pbp.filter(pl.col("game_id") != WEEK_15)

    def snaps(cut: pl.DataFrame) -> dict[int, int]:
        return dict(
            cut.filter(pl.col("scrimmage_play") == True).group_by("pos_team_id").len().iter_rows()
        )

    short, enough = game.head(52), game.head(56)
    assert snaps(short) == {ATL: 19, NO: 24} and snaps(enough) == {ATL: 22, NO: 25}
    assert snaps(short)[ATL] < pi.MIN_PLAYS_PER_TEAM <= snaps(enough)[ATL]
    # decided at the cut (14-3), so it is the floor that drops it and not the tie rule
    assert short.tail(1).select("homeScore", "awayScore").row(0) == (14, 3)

    under = pl.concat([rest, short])
    assert WEEK_15 not in paper_index_games_table(under, SEASON)["game_id"].to_list()
    table = _luck(tmp_path, pbp=under)
    assert _row(table, ATL)["paper_index_games_n"] == 0 and _row(table, ATL)["luck_wins"] is None
    assert _row(table, NO)["paper_index_games_n"] == 0
    # four more plays put Atlanta over the floor and the game is scored
    over = _luck(tmp_path, pbp=pl.concat([rest, enough]))
    assert (
        _row(over, ATL)["paper_index_games_n"] == 1 and _row(over, NO)["paper_index_games_n"] == 1
    )


# --- the luck columns -----------------------------------------------------------------


def test_luck_columns_are_appended_in_order_with_their_dtypes(luck):
    assert luck.columns == [*_teams().columns, *LUCK_COLUMNS]
    assert [luck.schema[c] for c in LUCK_COLUMNS] == [
        pl.Float64,
        pl.Float64,
        pl.Float64,
        pl.Float64,
        pl.Float64,
        pl.Int64,
        pl.Utf8,
    ]
    assert luck.height == 32 and luck["team_id"].n_unique() == 32
    assert luck["paper_index_span"].unique().to_list() == ["holdout"]


def test_luck_wins_is_wins_minus_deserved_on_a_hand_computed_team(luck):
    """The Giants' three scored regular-season games: won weeks 1 and 7, lost week 18."""
    shares = list(NYG_SHARES.values())
    deserved = sum(shares)
    variance = sum(p * (1 - p) for p in shares)
    nyg = _row(luck, NYG)
    assert nyg["paper_index_games_n"] == 3
    assert nyg["deserved_wins"] == pytest.approx(1.3224759020798713, abs=1e-12)
    assert nyg["deserved_wins"] == pytest.approx(deserved, abs=1e-12)
    assert nyg["luck_wins"] == pytest.approx(2 - deserved, abs=1e-12)
    assert nyg["luck_wins"] + nyg["deserved_wins"] == pytest.approx(2.0, abs=1e-12)  # the wins
    assert nyg["luck_z"] == pytest.approx((2 - deserved) / math.sqrt(variance), abs=1e-12)
    assert nyg["luck_z"] == pytest.approx(0.8364859100276172, abs=1e-9)


def test_season_deserved_wins_sum_to_the_scored_games(luck):
    scored_reg_games = 5  # six regular-season games, one a tie
    assert luck["deserved_wins"].sum() == pytest.approx(scored_reg_games, abs=1e-9)
    assert luck["paper_index_games_n"].sum() == 2 * scored_reg_games
    assert luck["luck_wins"].sum() == pytest.approx(0.0, abs=1e-9)  # one win per scored game


def test_ranks_are_over_the_teams_with_a_value_and_differ_by_metric(luck):
    ranked = luck.filter(pl.col("luck_wins").is_not_null())
    assert ranked.height == 8  # the eight teams of the five scored games
    for col in ("luck_wins", "luck_z"):
        order = ranked.sort(col, descending=True)[f"{col}_rank"].to_list()
        assert order == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    assert luck.filter(pl.col("luck_wins").is_null())["luck_wins_rank"].null_count() == 24
    # the Giants have more wins of luck over three games, the Saints more deviations over one
    assert (_row(luck, NYG)["luck_wins_rank"], _row(luck, NO)["luck_wins_rank"]) == (1.0, 2.0)
    assert (_row(luck, NYG)["luck_z_rank"], _row(luck, NO)["luck_z_rank"]) == (2.0, 1.0)


def test_the_last_regular_week_is_in_and_the_playoff_game_is_not(tmp_path, games):
    """One id list -- the plays' -- cuts the shares: week 18 is the last regular-season
    week, and the wild-card game a week later is in the per-game table only."""
    playoff = games.filter(pl.col("game_id") == WILD_CARD)
    assert playoff["season_type"].unique().to_list() == [3] and playoff.height == 2
    assert _row(playoff, NYG)["won"] is True  # a win the regular-season luck must not count

    cut = season_games(SEASON, pl.Series(REG_IDS), _pbp_dir(tmp_path))
    assert cut.columns == games.columns
    assert WEEK_18 in cut["game_id"].to_list() and WILD_CARD not in cut["game_id"].to_list()
    assert cut["season_type"].unique().to_list() == [2]
    reg = _luck(tmp_path)
    assert _row(reg, NYG)["paper_index_games_n"] == 3
    assert _row(reg, MIN)["paper_index_games_n"] == 0  # Minnesota's only fixture game

    # the id list decides, not a season-type rule of this module: hand it the playoff id
    # (stage 06 run with --season-types REG,POST) and that game is summed too ...
    both = _luck(tmp_path, [*REG_IDS, PLAYOFF_ID])
    assert (
        _row(both, NYG)["paper_index_games_n"] == 4 and _row(both, MIN)["paper_index_games_n"] == 1
    )
    assert _row(both, NYG)["luck_wins"] == pytest.approx(
        3 - sum(NYG_SHARES.values()) - 0.7246169632675805, abs=1e-12
    )
    # ... and withhold week 18 and it is gone
    early = _luck(tmp_path, [i for i in REG_IDS if i != "2022_18_NYG_PHI"])
    assert (
        _row(early, NYG)["paper_index_games_n"] == 2
        and _row(early, PHI)["paper_index_games_n"] == 0
    )


def test_stage_06_still_writes_its_tables_when_the_luck_input_fails(tmp_path, monkeypatch, caplog):
    """espn_nfl_pbp is published by ANOTHER workflow. Its being absent (week 1 of a new
    season), late or broken must not take the seven play tables down with it: they are
    written with the luck columns null, and the run fails at the end so the cron is red,
    as it already does for the opponent splits."""
    from nfl_team_summaries import __main__ as cli

    from tests.test_team_summaries import _espn_game_ids, _fake_pbp, _roster, _schedule

    _fake_pbp().write_parquet(tmp_path / "model_pbp_2025.parquet")
    monkeypatch.setattr(
        cli,
        "prepare_plays",
        lambda pbp, season, season_types: prepare_plays(
            pbp, season, season_types=season_types, schedule_fn=_schedule
        ),
    )
    monkeypatch.setattr(cli, "load_rosters", lambda season: _roster())
    monkeypatch.setattr(cli, "load_espn_game_ids", _espn_game_ids)

    def no_asset(season, game_ids, pbp_dir):
        raise RuntimeError("404 Client Error: Not Found for url: .../play_by_play_2025.parquet")

    monkeypatch.setattr(cli, "season_games", no_asset)
    out = tmp_path / "out"
    with caplog.at_level(logging.ERROR):
        rc = cli.main(["--seasons", "2025", "--pbp-dir", str(tmp_path), "--out", str(out)])

    assert rc == 1  # red, not a silent null
    assert "luck" in caplog.text and "2025" in caplog.text
    for tag, stem in TABLES.values():  # every play table is still there
        assert (out / tag / f"{stem}_2025.parquet").exists(), tag
    written = pl.read_parquet(out / "nfl_team_summaries" / "team_summaries_2025.parquet")
    assert written.columns[-len(LUCK_COLUMNS) :] == list(LUCK_COLUMNS)  # the schema holds
    assert written["deserved_wins"].null_count() == written.height
    assert written["paper_index_games_n"].to_list() == [0] * written.height


def test_stage_06_hands_the_shares_the_plays_own_game_ids(tmp_path, monkeypatch):
    """Through the stage-06 CLI: the ids that cut the shares are exactly the game ids of
    the plays the tables aggregate (a playoff game in the pbp is in neither), and the luck
    columns are attached after the build, so nothing inside it sees them."""
    from nfl_team_summaries import __main__ as cli

    from tests.test_team_summaries import GAMES, _espn_game_ids, _fake_pbp, _roster, _schedule

    pbp = _fake_pbp()
    playoff = pbp.filter(pl.col("game_id") == GAMES[0][0]).with_columns(
        game_id=pl.lit("2025_19_BUF_KC"), season_type=pl.lit("POST")
    )
    pl.concat([pbp, playoff]).write_parquet(tmp_path / "model_pbp_2025.parquet")
    monkeypatch.setattr(
        cli,
        "prepare_plays",
        lambda pbp, season, season_types: prepare_plays(
            pbp, season, season_types=season_types, schedule_fn=_schedule
        ),
    )
    monkeypatch.setattr(cli, "load_rosters", lambda season: _roster())
    monkeypatch.setattr(cli, "load_espn_game_ids", _espn_game_ids)
    seen: dict = {}

    def fake_season_games(season, game_ids, pbp_dir):
        seen["ids"] = sorted(game_ids.unique().to_list())
        seen["dir"] = pbp_dir
        return stage._NO_GAMES

    def fake_attach(team, shares, season):
        seen["built_columns"] = team.columns
        return attach_luck(team, shares, season)

    monkeypatch.setattr(cli, "season_games", fake_season_games)
    monkeypatch.setattr(cli, "attach_luck", fake_attach)
    out = tmp_path / "out"
    argv = ["--seasons", "2025", "--pbp-dir", str(tmp_path), "--out", str(out)]
    assert cli.main([*argv, "--espn-pbp-dir", "espn-dir"]) == 0

    assert seen["ids"] == sorted(g for g, _, _ in GAMES) and "2025_19_BUF_KC" not in seen["ids"]
    assert seen["dir"] == "espn-dir"
    # build_team_summaries knew none of them: no rank of theirs got a conference percentile
    assert not [c for c in seen["built_columns"] if any(f in c for f in OUTCOME_FRAGMENTS)]
    written = pl.read_parquet(out / "nfl_team_summaries" / "team_summaries_2025.parquet")
    assert written.columns == [*seen["built_columns"], *LUCK_COLUMNS]
    assert [c for c in written.columns if any(f in c for f in OUTCOME_FRAGMENTS)] == list(
        LUCK_COLUMNS
    )
    # 2025 is inside the fit's holdout; no ESPN rows were handed over, so nothing is summed
    assert written["paper_index_span"].unique().to_list() == ["holdout"]
    assert written["paper_index_games_n"].to_list() == [0, 0, 0, 0]
    averaged = pl.read_parquet(out / "nfl_league_averages" / "league_averages_2025.parquet")
    assert not [m for m in averaged["metric"].unique() if any(f in m for f in OUTCOME_FRAGMENTS)]


# --- the in-sample label --------------------------------------------------------------


def test_paper_index_span_reads_the_sdv_py_fit_spans(monkeypatch):
    (t0, t1), (h0, h1) = pi.TRAIN_SEASONS["nfl"], pi.HOLDOUT_SEASONS["nfl"]
    assert [paper_index_span(s) for s in (t0 - 1, t0, t1, h0, h1, h1 + 1)] == [
        "out_of_span",
        "train",
        "train",
        "holdout",
        "holdout",
        "out_of_span",
    ]
    # the NFL fit as sdv-py states it at the locked commit: train 2016-2021, holdout 2022-2025
    assert [paper_index_span(s) for s in (2015, 2016, 2021, 2022, 2025, 2026)] == [
        "out_of_span",
        "train",
        "train",
        "holdout",
        "holdout",
        "out_of_span",
    ]
    # read at call time, never copied: move the fit and the label moves with it
    monkeypatch.setitem(pi.TRAIN_SEASONS, "nfl", (2022, 2022))
    assert paper_index_span(2022) == "train" and paper_index_span(2021) == "out_of_span"
    assert paper_index_games_table(_pbp(), SEASON)["paper_index_span"].unique().to_list() == [
        "train"
    ]


def test_before_the_espn_floor_nothing_is_loaded_and_luck_is_null(monkeypatch):
    assert FLOOR == 2002
    monkeypatch.setattr(stage, "load_espn_pbp", _refuse)
    table = attach_luck(_teams(2001), season_games(2001, pl.Series(["2001_01_NYG_DEN"])), 2001)
    assert table["paper_index_games_n"].unique().to_list() == [0]
    assert table.select(pl.col("deserved_wins", "luck_wins", "luck_z").is_null().all()).row(0) == (
        True,
        True,
        True,
    )
    assert table["paper_index_span"].unique().to_list() == ["out_of_span"]


# --- an empty, foreign or broken input is refused, never written ----------------------


def test_an_empty_pbp_raises(tmp_path):
    empty = _pbp().head(0)
    with pytest.raises(ValueError, match="has no rows"):
        paper_index_games_table(empty, SEASON)
    with pytest.raises(ValueError, match="has no rows"):
        build_paper_index_games(SEASON, _pbp_dir(tmp_path, empty))
    with pytest.raises(ValueError, match="has no rows"):
        _luck(tmp_path, pbp=empty)


def test_a_pbp_of_another_season_raises(tmp_path):
    with pytest.raises(ValueError, match=r"holds season\(s\) \[2022\], expected 2023"):
        build_paper_index_games(2023, _pbp_dir(tmp_path, season=2023))
    with pytest.raises(ValueError, match="expected 2023"):
        season_games(2023, pl.Series(REG_IDS), _pbp_dir(tmp_path, season=2023))
    # and games of another season never reach a season's table
    with pytest.raises(ValueError, match=r"carry other seasons: \[2022\]"):
        attach_luck(_teams(2023), paper_index_games_table(_pbp(), SEASON), 2023)


@pytest.mark.parametrize("col", ["game_id", "pos_team_id", "homeTeamId", "awayTeamId"])
def test_a_float_or_text_id_raises(tmp_path, col):
    for bad in (pl.Float64, pl.Utf8):
        pbp = _pbp().with_columns(pl.col(col).cast(bad))
        with pytest.raises(TypeError, match=col):
            build_paper_index_games(SEASON, _pbp_dir(tmp_path, pbp))


@pytest.mark.parametrize("dtype", [pl.Float64, pl.Utf8, pl.Int32])
def test_team_ids_that_do_not_share_one_integer_type_raise(games, dtype):
    with pytest.raises(TypeError, match="team_id"):
        attach_luck(_teams().with_columns(pl.col("team_id").cast(dtype)), games, SEASON)
    with pytest.raises(TypeError, match="team_id"):
        attach_luck(_teams(), games.with_columns(pl.col("team_id").cast(dtype)), SEASON)


def test_text_game_ids_only(tmp_path):
    with pytest.raises(TypeError, match="nflverse game ids are text"):
        season_games(SEASON, pl.Series([401437640]), _pbp_dir(tmp_path))


def test_a_scored_team_without_a_summaries_row_raises(games):
    with pytest.raises(ValueError, match=rf"team\(s\) \[{NYG}\] have no team_summaries row"):
        attach_luck(_teams().filter(pl.col("team_id") != NYG), games, SEASON)


@pytest.mark.parametrize("how", ["null", "two"])
def test_a_scored_game_without_one_nflverse_id_raises(tmp_path, how):
    week_18 = pl.col("game_id") == WEEK_18
    if how == "null":
        bad = pl.when(week_18).then(None).otherwise(pl.col("nflverse_game_id"))
    else:  # the id changes part-way through the game's rows
        bad = (
            pl.when(week_18 & (pl.col("game_play_number") > 80))
            .then(pl.lit("2022_18_NYG_DAL"))
            .otherwise(pl.col("nflverse_game_id"))
        )
    pbp = _pbp().with_columns(nflverse_game_id=bad)
    with pytest.raises(ValueError, match=rf"scored game\(s\) \[{WEEK_18}\] carry no single"):
        _luck(tmp_path, pbp=pbp)


def test_ids_that_stopped_agreeing_raise_but_a_preseason_only_pbp_does_not(tmp_path, caplog):
    foreign = pl.Series(["2022_01_AAA_BBB", "2022_02_CCC_DDD"])
    with pytest.raises(ValueError, match="holds none of the 2 games"):
        season_games(SEASON, foreign, _pbp_dir(tmp_path))
    # August: the published pbp holds preseason games only and the plays are week 1.
    # Nothing to sum yet is not an error; the count says so and a warning names it.
    preseason = _pbp().with_columns(seasonType=pl.lit(1, dtype=pl.Int64))
    with caplog.at_level(logging.WARNING):
        table = attach_luck(
            _teams(), season_games(SEASON, foreign, _pbp_dir(tmp_path, preseason)), SEASON
        )
    assert table["paper_index_games_n"].unique().to_list() == [0]
    assert "lacks 2 of the 2 games" in caplog.text


def test_a_pbp_behind_the_plays_warns_with_the_count(tmp_path, caplog):
    """espn_nfl_pbp is published by another workflow: when it trails nfl_model_pbp the
    games it lacks are not summed, the count says so, and the log names how many."""
    ids = [*REG_IDS, "2022_18_DAL_WAS", "2022_18_KC_LV"]
    with caplog.at_level(logging.WARNING):
        table = _luck(tmp_path, ids)
    assert "espn_nfl_pbp lacks 2 of the 8 games" in caplog.text
    assert _row(table, NYG)["paper_index_games_n"] == 3
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        _luck(tmp_path)
    assert "lacks" not in caplog.text  # the tie is in the pbp: unscored is not missing


def test_keep_floor_warning_fails_stage_09_and_only_warns_in_stage_06(tmp_path):
    """sdv-py warns when inputs are computable for under 98% of the decided games. Stage
    09 would publish a season with games missing, so it fails; stage 06 keeps its seven
    tables and sums what was scored."""
    # week 4 with no drive ids: the feed defect behind the 2002 truncated games
    broken = _pbp().with_columns(
        pl.when(pl.col("game_id") == WEEK_4)
        .then(None)
        .otherwise(pl.col("drive.id"))
        .alias("drive.id")
    )
    with pytest.warns(UserWarning, match=stage._KEEP_FLOOR_WARNING):  # the real upstream text
        pi.paper_index_games(broken.select(pi.PBP_COLUMNS), "nfl")
    with pytest.raises(ValueError, match="paper_index_games 2022: .*computable for 5 of 6"):
        build_paper_index_games(SEASON, _pbp_dir(tmp_path, broken))
    with pytest.warns(UserWarning, match="computable for 5 of 6"):
        table = _luck(tmp_path, pbp=broken)
    assert (
        _row(table, GB)["paper_index_games_n"] == 0 and _row(table, NYG)["paper_index_games_n"] == 3
    )


# --- the stage CLI and its registration -----------------------------------------------


def test_cli_writes_the_season_and_publishes_only_what_it_wrote(games, tmp_path, monkeypatch):
    out = tmp_path / TAG
    out.mkdir()
    (out / f"{STEM}_2021.parquet").write_bytes(b"stale")  # a leftover season must not re-upload
    calls: list[tuple[Path, str, str, bool]] = []
    monkeypatch.setattr(
        artifacts,
        "upload_artifacts",
        lambda d, tag, repo, *, pattern, dry_run: (
            calls.append((Path(d), tag, pattern, dry_run)),
            {"uploaded": 0},
        )[1],
    )
    pbp_dir = _pbp_dir(tmp_path)
    argv = ["--seasons", str(SEASON), "--pbp-dir", str(pbp_dir), "--out", str(out)]
    assert main([*argv, "--publish", "--dry-run"]) == 0
    assert_frame_equal(pl.read_parquet(out / f"{STEM}_{SEASON}.parquet"), games)
    assert calls == [(out, TAG, f"{STEM}_{SEASON}.parquet", True)]
    calls.clear()
    assert main(argv) == 0 and calls == []  # without --publish the upload seam is untouched

    # an empty season file stops the run before anything is written or uploaded
    _pbp_dir(tmp_path, _pbp().head(0), season=2023)
    dest = tmp_path / "second"
    with pytest.raises(ValueError, match="espn_nfl_pbp 2023 has no rows"):
        main(["--seasons", "2022:2023", "--pbp-dir", str(pbp_dir), "--out", str(dest), "--publish"])
    assert calls == [] and [p.name for p in dest.iterdir()] == [f"{STEM}_{SEASON}.parquet"]


def test_below_floor_season_writes_nothing_and_says_why(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(stage, "load_espn_pbp", _refuse)
    dest = tmp_path / "out"
    with caplog.at_level(logging.WARNING):
        assert main(["--seasons", "2000:2001", "--out", str(dest), "--publish", "--dry-run"]) == 0
    assert list(dest.iterdir()) == []
    assert "2001" in caplog.text and "2002" in caplog.text


def test_registered_with_its_tag_and_run_after_the_espn_family_build():
    assert PKG_FUNCTION[TAG].endswith("nfl_data_09_paper_index_games.py")
    notes = _RELEASE_BODY[TAG]
    assert "train = that season's games were part of the fit" in notes and str(FLOOR) in notes
    # the fit years are sdv-py's to state: none is copied into the note
    assert not [
        y for y in (*pi.TRAIN_SEASONS["nfl"], *pi.HOLDOUT_SEASONS["nfl"]) if str(y) in notes
    ]
    manifest = yaml.safe_load((ROOT / "models" / "manifest.yaml").read_text(encoding="utf-8"))
    entry = manifest["data_pipelines"]["paper_index_games"]
    assert entry["release_tag"] == TAG and entry["workflow"] == "espn_nfl_cron.yml"
    # the workflow runs scripts/espn_nfl_data.sh, which cuts the stage from the pbp it wrote
    cron = (ROOT / ".github" / "workflows" / entry["workflow"]).read_text(encoding="utf-8")
    driver = (ROOT / "scripts" / "espn_nfl_data.sh").read_text(encoding="utf-8")
    assert "scripts/espn_nfl_data.sh" in cron
    assert driver.index("-m nfl_espn_build") < driver.index("-m nfl_data_09_paper_index_games")
    assert '--pbp-dir "${OUT}/pbp"' in driver


def test_stays_out_of_stage_06s_globs_and_league_averages():
    stage_06 = [*TABLES.values(), SPLITS]
    assert TAG not in {tag for tag, _ in stage_06}
    assert not any(fnmatch(f"{STEM}_{SEASON}.parquet", f"{stem}_*.parquet") for _, stem in stage_06)
    assert STEM not in CATEGORIES and STEM not in TABLES


# --- leakage: the outcome-derived columns reach no metric list and no model -----------


def test_league_averages_never_averages_the_luck_columns(luck):
    """``metric_columns`` builds its list by dtype and suffix. Stage 06 attaches the luck
    columns after ``league_averages`` is built; this is the guard if that order moves."""
    with_metric = luck.with_columns(EPAplay_off=pl.lit(0.1))
    assert metric_columns(with_metric) == ["EPAplay_off"]
    # even re-expressed as a percentile or a cohort column they are not metrics
    derived = with_metric.with_columns(
        luck_z_conf_pct=pl.lit(50.0),
        deserved_wins_pct=pl.lit(50.0),
        luck_wins_rank_conf_pct=pl.lit(1.0),
    )
    assert metric_columns(derived) == ["EPAplay_off"]


def test_no_model_or_feature_set_reads_the_summaries_tables():
    """The trainers, the weekly ratings and the pinned feature sets read play-by-play.
    None names a summaries table or an outcome column, so the new columns cannot become
    a feature by name pattern; this fails the day one of them starts to."""
    sources = [
        *sorted((ROOT / "python" / "model_training").rglob("*.py")),
        *sorted((ROOT / "python" / "nfl_ratings_weekly").rglob("*.py")),
        *sorted((ROOT / "python" / "native_pbp").rglob("*.py")),
        *sorted((ROOT / "python").glob("nfl_model_[0-9][0-9]_*.py")),
        *sorted((ROOT / "features").glob("*.yaml")),
    ]
    assert len(sources) > 40 and len(list((ROOT / "features").glob("*.yaml"))) == 10
    needles = ("team_summaries", "league_averages", *OUTCOME_FRAGMENTS)
    hits = [
        (str(p.relative_to(ROOT)), n)
        for p in sources
        for n in needles
        if n in p.read_text(encoding="utf-8")
    ]
    assert hits == []


# --- a venv older than the sdv-py port ------------------------------------------------


def test_stages_import_on_an_sdv_py_without_paper_index():
    """A checkout whose venv was not synced after the lock moved has no
    ``sportsdataverse.paper_index``. Stage 06's CLI imports this module and stages 07 and
    08 import stage 06's CLI: all of them must still import there, and only a call that
    needs the Paper Index may fail. A fresh interpreter, so no module is already loaded."""
    code = "\n".join(
        [
            "import sys",
            # the locked sdv-py imports paper_index in its own __init__, so the package
            # is loaded first and the submodule taken away after: an older sdv-py
            "import sportsdataverse",
            "sys.modules['sportsdataverse.paper_index'] = None  # import -> ImportError",
            "import nfl_team_summaries.__main__, nfl_team_summaries.curves",
            "import nfl_model_publish.artifacts, nfl_espn_build.cli",
            "from nfl_team_summaries import paper_index",
            "try:",
            "    paper_index.paper_index_span(2022)",
            "except ImportError:",
            "    print('only the call fails')",
        ]
    )
    done = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=300,
        env={**os.environ, "PYTHONPATH": str(ROOT / "python")},
    )
    assert done.returncode == 0, done.stderr[-2000:]
    assert done.stdout.strip() == "only the call fails"
