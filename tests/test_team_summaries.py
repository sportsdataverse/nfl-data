"""Hermetic tests for nfl_team_summaries (no network, no release assets).

The synthetic frame is nflfastR-shaped (the columns ``nfl_model_pbp`` ships)
and small: four teams, four games, a few drives each, with every play kind the
producer branches on -- completions, incompletions, sacks, scrambles, rushes, a
pick, a lost fumble, kneels, spikes, penalties, kickoffs, and fourth-down
decisions of all three kinds. The column CONTRACT is asserted against the
site's own TypeScript interfaces, vendored under tests/fixtures.
"""

from __future__ import annotations

import random
from pathlib import Path

import polars as pl
import pytest
from nfl_team_summaries import checks
from nfl_team_summaries.build import (
    PLAYER_PERCENTILE_METRICS,
    PLAYER_RANK_SPECS,
    QB_MIN_DROPBACKS_PER_GAME,
    QB_QUALIFIES,
    RB_QUALIFIES,
    WR_QUALIFIES,
    _attach_leader_ranks,
    _drives_table,
    _prepare_for_write,
    _side_pair,
    _turnovers,
    add_derived_metrics,
    build_team_opponent_splits,
    build_team_summaries,
    prepare_player_percentiles,
)
from nfl_team_summaries.crosswalk import attach_team_ids, load_crosswalk
from nfl_team_summaries.input import filter_season_types, prepare_plays
from nfl_team_summaries.rbsdm import _RANKED as RBSDM_RANKED

FIX = Path(__file__).parent / "fixtures"
TEAMS = ["KC", "BUF", "PHI", "DAL"]
GAMES = [
    ("2025_01_BUF_KC", "KC", "BUF"),
    ("2025_01_DAL_PHI", "PHI", "DAL"),
    ("2025_02_KC_PHI", "PHI", "KC"),
    ("2025_02_BUF_DAL", "DAL", "BUF"),
]
#: final (home, away) score per game -- distinct, so a for/against swap shows
SCORES = {
    "2025_01_BUF_KC": (27, 20),
    "2025_01_DAL_PHI": (31, 17),
    "2025_02_KC_PHI": (13, 23),
    "2025_02_BUF_DAL": (10, 16),
}
#: nflverse game_id -> ESPN event id (stands in for nfl-raw's crosswalk)
ESPN_EVENTS = {g: 401772500 + i for i, (g, _, _) in enumerate(GAMES)}


def _espn_game_ids() -> pl.DataFrame:
    return pl.DataFrame(
        {"nflverse_game_id": list(ESPN_EVENTS), "game_id": list(ESPN_EVENTS.values())},
        schema={"nflverse_game_id": pl.Utf8, "game_id": pl.Int64},
    )


def _contract(name: str) -> list[str]:
    return [
        line.strip()
        for line in (FIX / f"sdv_{name}_columns.txt").read_text().splitlines()
        if line.strip()
    ]


def _fake_pbp(seed: int = 7) -> pl.DataFrame:
    rng = random.Random(seed)
    rows: list[dict] = []
    for gid, home, away in GAMES:
        play_id = 0
        drive = 0
        for half in (1, 2):
            for posteam in (away, home):
                defteam = home if posteam == away else away
                drive += 1
                play_id += 1
                # kickoff opens the drive: not a scrimmage play, must be ignored
                rows.append(
                    _play(
                        gid,
                        play_id,
                        drive,
                        "kickoff",
                        posteam,
                        defteam,
                        home,
                        away,
                        down=None,
                        y100=65,
                        gain=0,
                        rng=rng,
                        qtr=1 if half == 1 else 3,
                    )
                )
                y100 = 75
                # ~10 dropbacks per drive x 2 drives clears the 14/game QB gate
                kinds = [
                    "pass",
                    "pass",
                    "pass",
                    "run",
                    "pass",
                    "sack",
                    "scramble",
                    "pass",
                    "run",
                    "pass",
                    "pass",
                    "run",
                    "pass",
                    "fourth",
                ]
                for i, kind in enumerate(kinds):
                    play_id += 1
                    down = 1 + (i % 3) if kind != "fourth" else 4
                    qtr = 1 if half == 1 else 3
                    if kind == "fourth":
                        rec = ["go", "punt", "field_goal"][(play_id // 3) % 3]
                        actual = (
                            {"go": "run", "punt": "punt", "field_goal": "field_goal"}[rec]
                            if rng.random() < 0.6
                            else "punt"
                        )
                        rows.append(
                            _play(
                                gid,
                                play_id,
                                drive,
                                actual,
                                posteam,
                                defteam,
                                home,
                                away,
                                down=4,
                                y100=max(y100, 30),
                                gain=3 if actual == "run" else 0,
                                rng=rng,
                                qtr=qtr,
                                fourth=rec,
                            )
                        )
                        break
                    gain = rng.randint(-3, 18) if kind != "sack" else -rng.randint(2, 9)
                    rows.append(
                        _play(
                            gid,
                            play_id,
                            drive,
                            kind,
                            posteam,
                            defteam,
                            home,
                            away,
                            down=down,
                            y100=y100,
                            gain=gain,
                            rng=rng,
                            qtr=qtr,
                        )
                    )
                    y100 = max(1, y100 - gain)
                # noise plays every drive: a no_play penalty, a kneel and a spike
                for pt in ("no_play", "qb_kneel", "qb_spike"):
                    play_id += 1
                    rows.append(
                        _play(
                            gid,
                            play_id,
                            drive,
                            pt,
                            posteam,
                            defteam,
                            home,
                            away,
                            down=1,
                            y100=50,
                            gain=0,
                            rng=rng,
                            qtr=1 if half == 1 else 3,
                        )
                    )
    df = pl.DataFrame(rows)
    # one interception and one lost fumble, so the pick/luck branches see data
    df = df.with_columns(
        interception=pl.when((pl.col("play_type") == "pass") & (pl.col("play_id") == 4))
        .then(1)
        .otherwise(pl.col("interception")),
        fumble=pl.when((pl.col("play_type") == "run") & (pl.col("play_id") == 6))
        .then(1)
        .otherwise(pl.col("fumble")),
        fumble_lost=pl.when((pl.col("play_type") == "run") & (pl.col("play_id") == 6))
        .then(1)
        .otherwise(pl.col("fumble_lost")),
        fumbled_1_team=pl.when((pl.col("play_type") == "run") & (pl.col("play_id") == 6))
        .then(pl.col("posteam"))
        .otherwise(pl.col("fumbled_1_team")),
        # nflfastR carries the FINAL score on every row of the game
        home_score=pl.col("game_id").replace_strict({g: h for g, (h, _) in SCORES.items()}),
        away_score=pl.col("game_id").replace_strict({g: a for g, (_, a) in SCORES.items()}),
    )
    return df


def _play(
    gid,
    play_id,
    drive,
    kind,
    posteam,
    defteam,
    home,
    away,
    *,
    down,
    y100,
    gain,
    rng,
    qtr,
    fourth=None,
) -> dict:
    is_pass = kind in ("pass", "sack", "scramble")
    is_run = kind in ("run", "scramble")
    complete = 1 if kind == "pass" and rng.random() < 0.65 else 0
    qb = f"{posteam}-QB1"
    rb = f"{posteam}-RB1" if rng.random() < 0.7 else f"{posteam}-RB2"
    wr = f"{posteam}-WR1" if rng.random() < 0.6 else f"{posteam}-WR2"
    epa = round(
        rng.uniform(-1.5, 2.5)
        if kind not in ("kickoff", "no_play", "qb_kneel", "qb_spike", "punt", "field_goal")
        else rng.uniform(-0.5, 0.5),
        3,
    )
    play_type = {"pass": "pass", "sack": "pass", "scramble": "run", "run": "run"}.get(kind, kind)
    return {
        "season_type": "REG",
        "season": 2025,
        "game_id": gid,
        "play_id": play_id,
        "fixed_drive": drive,
        # one series per drive; every third drive fails to convert
        "series": drive,
        "series_success": 0 if drive % 3 == 0 else 1,
        "series_result": "Punt" if drive % 3 == 0 else "First down",
        "fixed_drive_result": ("Punt", "Touchdown", "Field goal")[drive % 3],
        "play_type": play_type,
        "down": down,
        "ydstogo": 10 if down in (1, None) else rng.randint(1, 9),
        "yardline_100": y100,
        # nflfastR carries NULL, not 0, on an incompletion or a pick
        "yards_gained": None if (kind == "pass" and not complete) else gain,
        "posteam": posteam,
        "defteam": defteam,
        "home_team": home,
        "away_team": away,
        "week": 1 if "_01_" in gid else 2,
        "epa": epa,
        "wpa": round(epa / 20, 4),
        "wp": round(rng.uniform(0.25, 0.75), 3),
        "qtr": qtr,
        "half_seconds_remaining": rng.randint(200, 1700),
        "pass_attempt": 1 if kind in ("pass", "sack") else 0,
        "sack": 1 if kind == "sack" else 0,
        "qb_scramble": 1 if kind == "scramble" else 0,
        "rush_attempt": 1 if is_run else 0,
        "complete_pass": complete,
        "incomplete_pass": 1 if kind == "pass" and not complete else 0,
        "interception": 0,
        "fumble": 0,
        "fumble_lost": 0,
        "fumbled_1_team": None,
        "fumble_forced": 0,
        "pass_defense_1_player_id": f"{defteam}-CB1"
        if kind == "pass" and not complete and rng.random() < 0.5
        else None,
        "pass_touchdown": 1 if kind == "pass" and complete and gain >= 15 else 0,
        "rush_touchdown": 1 if kind == "run" and gain >= 15 else 0,
        "passing_yards": gain if complete else None,
        "receiving_yards": gain if complete else None,
        "rushing_yards": gain if is_run else None,
        "passer_player_id": qb if is_pass else None,
        "passer_player_name": f"Q.{posteam}" if is_pass else None,
        "rusher_player_id": (qb if kind == "scramble" else rb) if is_run else None,
        "rusher_player_name": (f"Q.{posteam}" if kind == "scramble" else f"R.{rb[-3:]}")
        if is_run
        else None,
        "receiver_player_id": wr if kind == "pass" else None,
        "receiver_player_name": f"W.{wr[-3:]}" if kind == "pass" else None,
        "xpass": round(rng.uniform(0.3, 0.8), 3)
        if kind in ("pass", "sack", "scramble", "run")
        else None,
        "pass_oe": round(rng.uniform(-40, 40), 2)
        if kind in ("pass", "sack", "scramble", "run")
        else None,
        "cpoe": round(rng.uniform(-20, 20), 2) if kind == "pass" else None,
        "qb_epa": epa if is_pass else None,
        "fourth_down_recommendation": fourth,
        "go_boost": round(rng.uniform(-3, 4), 2) if fourth else None,
        "field_goal_attempt": 1 if kind == "field_goal" else 0,
        "field_goal_result": ("made" if rng.random() < 0.85 else "missed")
        if kind == "field_goal"
        else None,
        "qb_kneel": 1 if kind == "qb_kneel" else 0,
        "qb_spike": 1 if kind == "qb_spike" else 0,
    }


def _schedule(seasons):
    return pl.DataFrame(
        {"game_id": [g for g, _, _ in GAMES], "location": ["Home", "Home", "Neutral", "Home"]}
    )


@pytest.fixture(scope="module")
def tables():
    pbp = _fake_pbp()
    plays = prepare_plays(pbp, 2025, schedule_fn=_schedule)
    return plays, build_team_summaries(plays, filter_season_types(pbp, ("REG",)), 2025)


@pytest.fixture(scope="module")
def splits(tables):
    plays, _ = tables
    raw = filter_season_types(_fake_pbp(), ("REG",))
    return build_team_opponent_splits(plays, raw, 2025, _espn_game_ids())


# --- crosswalk -----------------------------------------------------------------


def test_crosswalk_is_complete_and_unique():
    xw = load_crosswalk()
    assert xw.height == 32
    assert xw["espn_team_id"].n_unique() == 32
    assert xw["nflverse_abbr"].n_unique() == 32
    assert xw.filter(pl.col("nflverse_abbr") == "WAS")["espn_abbr"][0] == "WSH"
    assert xw.filter(pl.col("nflverse_abbr") == "LA")["espn_abbr"][0] == "LAR"


def test_attach_team_ids_folds_relocations_and_refuses_unknowns():
    df = pl.DataFrame({"t": ["OAK", "SD", "STL", "DEN"]})
    out = attach_team_ids(df, "t", "team")
    assert out["team_id"].to_list() == ["13", "24", "14", "7"]
    assert out.schema["team_id"] == pl.Utf8
    with pytest.raises(ValueError, match="no ESPN team id"):
        attach_team_ids(pl.DataFrame({"t": ["XYZ"]}), "t", "team")


# --- input adapter --------------------------------------------------------------


def test_prepare_plays_flags_and_filters(tables):
    plays, _ = tables
    assert set(plays["play_type"].unique().to_list()) <= {"pass", "run"}
    # a dropback is a throw, a sack or a scramble; a rush excludes scrambles
    sacks = plays.filter(pl.col("sack_vec") == 1)
    assert sacks.height > 0 and (sacks["pass"] == 1).all() and (sacks["pass_attempt"] == 0).all()
    scr = plays.filter(
        pl.col("passer_player_id").is_not_null()
        & (pl.col("pass_attempt") == 0)
        & (pl.col("sack_vec") == 0)
    )
    assert scr.height > 0 and (scr["pass"] == 1).all() and (scr["rush"] == 0).all()
    assert (plays["pos_team_id"].cast(pl.Int64) > 0).all()
    assert plays.schema["pos_team_id"] == pl.Utf8
    assert plays.schema["season"] == pl.Int64
    # neutral site came from the injected schedule
    assert plays.filter(pl.col("game_id") == "2025_02_KC_PHI")["neutral_site"].all()
    assert not plays.filter(pl.col("game_id") == "2025_01_BUF_KC")["neutral_site"].any()


def test_prepare_plays_drive_context_from_the_whole_frame(tables):
    plays, _ = tables
    d = plays.filter(pl.col("drive_id") == "2025_01_BUF_KC_1")
    # the kickoff (yardline 65) is NOT the drive start; the first snap is
    assert d["drive_start_yards_to_goal"][0] == 75
    assert d["drive_yards"][0] == d["yards_gained"].sum()


def test_yardsplay_shares_its_denominator_with_plays(tables):
    """Yards/Play is yards_*/plays_*, as it is in the CFB producer.

    An incompletion is a play that gained nothing, not a play that did not
    happen: if ``yards_gained`` reached the grid as NULL, ``mean()`` would
    quietly drop it and Yards/Play would not reconcile with Plays on the
    same row. Same denominator for the rates that read yards_gained.
    """
    plays, grid = tables
    assert plays["yards_gained"].null_count() == 0
    for row in grid["team_summaries"].iter_rows(named=True):
        for side in ("off", "def"):
            for split in ("", "_pass", "_rush"):
                n = row[f"plays_{side}{split}"]
                if not n:
                    continue
                assert row[f"yardsplay_{side}{split}"] == pytest.approx(
                    row[f"yards_{side}{split}"] / n
                ), f"yardsplay_{side}{split}"
        assert row["yardsplay_margin"] == pytest.approx(row["yardsplay_off"] - row["yardsplay_def"])


def test_prepare_plays_respects_season_types():
    pbp = _fake_pbp().with_columns(season_type=pl.lit("POST"))
    assert prepare_plays(pbp, 2025, schedule_fn=_schedule).height == 0
    assert prepare_plays(pbp, 2025, season_types=("REG", "POST"), schedule_fn=_schedule).height > 0


# --- the five tables -----------------------------------------------------------------


@pytest.mark.parametrize(
    "table,contract",
    [
        ("team_summaries", "SDVTeamSummary"),
        ("passing", "SDVPassingSummary"),
        ("rushing", "SDVRushingSummary"),
        ("receiving", "SDVReceivingSummary"),
        ("percentiles", "SDVSeasonPercentile"),
    ],
)
def test_tables_cover_the_site_contract(tables, table, contract):
    _, out = tables
    missing = [c for c in _contract(contract) if c not in out[table].columns]
    assert not missing, f"{table} is missing {missing}"


def test_identity_columns(tables):
    _, out = tables
    ts = out["team_summaries"]
    assert ts.height == 4
    assert ts.schema["team_id"] == pl.Int64 and ts.schema["season"] == pl.Int64
    assert set(ts["team_id"].to_list()) == {12, 2, 21, 6}  # KC, BUF, PHI, DAL on ESPN
    assert set(ts["pos_team"].to_list()) == set(TEAMS)
    assert ts["team_name"].null_count() == 0 and ts["conference"].is_in(["AFC", "NFC"]).all()
    assert (ts["fbs_class"] == "NFL").all()
    assert ts.columns[:6] == [
        "team_id",
        "pos_team",
        "team_name",
        "division",
        "conference",
        "season",
    ]


def test_every_rank_has_its_metric_and_every_player_rank_its_percentile(tables):
    _, out = tables
    for name, df in out.items():
        for c in df.columns:
            if c.endswith("_rank"):
                assert c[: -len("_rank")] in df.columns, f"{name}.{c} has no metric column"
    for name in ("passing", "rushing", "receiving"):
        df = out[name]
        for c in df.columns:
            if c.endswith("_rank"):
                assert c[: -len("_rank")] + "_pct" in df.columns, f"{name}.{c} has no _pct"


def test_ranks_have_no_nulls_and_percentiles_stay_off_the_ends(tables):
    _, out = tables
    ts = out["team_summaries"]
    # the grid ranks everything (the cfb port's contract); an rbsdm extra is the
    # exception: its rank is null exactly where the metric is null for EVERY team
    # (an extra the synthetic season never produces), never anywhere else
    for c in (c for c in ts.columns if c.endswith("_rank")):
        metric = c[: -len("_rank")]
        if metric in RBSDM_RANKED and ts[metric].null_count() == ts.height:
            assert ts[c].null_count() == ts.height, c
        else:
            assert ts[c].null_count() == 0, c
    qb = out["passing"].filter(pl.col("TEPA_pct").is_not_null())
    assert qb.height > 0
    assert (qb["TEPA_pct"] > 0).all() and (qb["TEPA_pct"] < 100).all()


def test_passing_counts_attempts_sacks_and_dropbacks_separately(tables):
    _, out = tables
    qb = out["passing"]
    assert (qb["dropbacks"] >= qb["att"] + qb["sacked"]).all()
    assert (qb["sacked"] > 0).any()
    assert qb["pass_int"].sum() == len(GAMES)  # one doctored pick per game (play 4)
    assert qb["epa_cpoe_composite"].null_count() < qb.height  # some qualifiers
    # a scramble is a dropback but never an attempt
    assert (qb["dropbacks"] > qb["att"] + qb["sacked"]).any()


def test_rbsdm_extras_present_and_ranked(tables):
    _, out = tables
    ts = out["team_summaries"]
    for c in (
        "pass_rate_off",
        "xpass_rate_off",
        "pass_oe_off",
        "neutral_pass_rate_off",
        "fourth_decisions_off",
        "fourth_go_rate_off",
        "fourth_go_expected_off",
        "fourth_go_over_expected_off",
        "fourth_go_boost_off",
        "luck_fumble_rec_pct_off",
        "luck_opp_fg_pct_def",
        "series_conv_off",
        "series_conv_def",
    ):
        assert c in ts.columns and f"{c}_rank" in ts.columns, c
    assert ts["fourth_decisions_off"].sum() > 0
    # every third drive is a failed series: rates are real shares, and not all 1.0
    assert ts["series_conv_off"].is_between(0.0, 1.0).all()
    assert (ts["series_conv_off"] < 1.0).any()
    # a defense allowing FEWER conversions is better: the LOWEST allowed rate ranks 1
    d = ts.filter(pl.col("series_conv_def").is_not_null()).sort("series_conv_def")
    if d.height > 1:
        ranks = d["series_conv_def_rank"]
        assert ranks[0] == ranks.min() and ranks[0] <= ranks[-1]
    # opponents missing kicks is the lucky outcome: the LOWEST opp FG% ranks 1
    r = ts.filter(pl.col("luck_opp_fg_pct_def").is_not_null()).sort("luck_opp_fg_pct_def")
    if r.height > 1:
        ranks = r["luck_opp_fg_pct_def_rank"]
        assert ranks[0] == ranks.min() and ranks[0] <= ranks[-1]


def test_series_columns_survive_an_asset_without_series():
    # a model_pbp built before native_pbp's series port: the columns exist (null),
    # so the published table schema does not depend on the asset vintage
    pbp = _fake_pbp().drop("series", "series_success", "series_result")
    plays = prepare_plays(pbp, 2025, schedule_fn=_schedule)
    ts = build_team_summaries(plays, filter_season_types(pbp, ("REG",)), 2025)["team_summaries"]
    assert "series_conv_off" in ts.columns and "series_conv_def_rank" in ts.columns
    assert ts["series_conv_off"].is_null().all()
    # and nobody is ranked on a metric nobody has (sequential ranks over nulls would look like data)
    assert ts["series_conv_off_rank"].is_null().all() and ts["series_conv_def_rank"].is_null().all()


def test_percentiles_shape(tables):
    _, out = tables
    pc = out["percentiles"]
    assert pc.height == 99 and pc["pctile"][0] == 0.01 and pc["pctile"][-1] == 0.99
    assert (pc["season"] == 2025).all()


def test_tables_registry_matches_the_build_output(tables):
    from nfl_team_summaries.__main__ import TABLES

    _, out = tables
    assert set(TABLES) == set(out)
    assert TABLES["league_averages"] == ("nfl_league_averages", "league_averages")


# --- guards ------------------------------------------------------------------------


def test_asc_col_absent_from_rank_cols_is_rejected():
    df = pl.DataFrame({"k": ["a", "b"], "x": [1.0, 2.0], "team_games": [1, 1]})
    with pytest.raises(ValueError, match="asc_cols entries missing"):
        _attach_leader_ranks(df, keys=["k"], min_expr=pl.lit(True), rank_cols=["x"], asc_cols=["y"])


def test_passer_identity_gate_fires():
    bad = pl.DataFrame(
        {"passer_player_name": ["A"], "TEPA": [10.0], "EPAplay": [0.1], "dropbacks": [50.0]}
    )
    with pytest.raises(ValueError, match="TEPA != EPAplay"):
        checks.assert_passer_identity(bad, label="t")


def test_adjustment_noop_gate_fires():
    x = [float(i) for i in range(32)]
    same = pl.DataFrame({"adj_off_epa": x, "EPAplay_off": x, "adj_def_epa": x, "EPAplay_def": x})
    with pytest.raises(ValueError, match="NO-OP"):
        checks.assert_adjustment_is_real(same, label="t")


# --- percentiles ---------------------------------------------------------------------


@pytest.mark.parametrize("table", ["passing", "rushing", "receiving"])
def test_pct_is_monotone_with_its_metric_within_its_group(tables, table):
    """The validation-map gate: a better metric never gets a worse percentile.

    "Better" is the direction ``_rank`` already encodes -- descending for
    everything except the ``asc_cols`` (picks, sacks taken, fumbles), where a
    lower count is better. Ties may share a percentile; nothing may invert.
    """
    _, out = tables
    df = out[table]
    ranked, asc = PLAYER_RANK_SPECS[table]
    for metric in ranked:
        q = df.filter(pl.col(metric).is_not_null() & pl.col(f"{metric}_pct").is_not_null())
        if q.height < 2:
            continue
        q = q.sort(metric, descending=metric in asc)
        pct = q[f"{metric}_pct"].to_list()
        assert pct == sorted(pct), f"{table}.{metric}_pct inverts against its metric"


@pytest.mark.parametrize(
    "table,gate",
    [("passing", QB_QUALIFIES), ("rushing", RB_QUALIFIES), ("receiving", WR_QUALIFIES)],
)
def test_qualification_is_applied_identically_to_rank_and_pct(tables, table, gate):
    """Same population for both, and a null metric costs the percentile only.

    ``_rank`` reproduces R's ``na.last=TRUE`` and hands a null metric a trailing
    rank; ``_pct`` must not, or "unknown" renders as "worst".
    """
    _, out = tables
    df = out[table]
    ranked, _ = PLAYER_RANK_SPECS[table]
    qualified = df.filter(gate)
    if qualified.height == 0:
        # no back clears 6.25 carries per team-game in the four-game synthetic
        # season; the table must then carry no ranks at all (the gate firing on
        # a real population is covered by the unit test below and the 2025 fixture)
        assert all(df[f"{m}_rank"].null_count() == df.height for m in ranked)
        return
    for metric in ranked:
        rank, pct = pl.col(f"{metric}_rank"), pl.col(f"{metric}_pct")
        # non-qualifiers carry neither
        assert df.filter(~gate).filter(rank.is_not_null() | pct.is_not_null()).height == 0, metric
        # qualifiers all carry a rank; the percentile is dropped exactly where the metric is
        assert qualified.filter(rank.is_null()).height == 0, metric
        assert (
            qualified.filter(pct.is_null()).height
            == qualified.filter(pl.col(metric).is_null()).height
        ), metric
        good = qualified.filter(pct.is_not_null())
        n = good.height
        assert (good[f"{metric}_pct"] == 100 * (n + 1 - good[f"{metric}_rank"]) / (n + 1)).all()


def test_player_percentiles_shape_and_direction(tables):
    _, out = tables
    pp = out["player_percentiles"]
    assert pp.columns[:2] == ["position_group", "pctile"]
    assert pp.height == 99 * 3
    assert set(pp["position_group"].unique()) == {"passing", "rushing", "receiving"}
    assert (pp["season"] == 2025).all()
    for m in PLAYER_PERCENTILE_METRICS:
        assert pp.schema[m] == pl.Float64, m  # never a polars Null column
    for group, (ranked, asc) in PLAYER_RANK_SPECS.items():
        g = pp.filter(pl.col("position_group") == group).sort("pctile")
        assert g.height == 99 and g["pctile"][0] == 0.01 and g["pctile"][-1] == 0.99
        for m in PLAYER_PERCENTILE_METRICS:
            if m not in ranked:
                assert g[m].null_count() == 99, f"{group}.{m} is not a ranked metric there"
                continue
            vals = g.filter(pl.col(m).is_not_null())[m].to_list()
            if len(vals) < 2:
                continue
            # ascending from the 1st to the 99th percentile of GOODNESS, which for
            # a low-is-good metric means a falling raw value
            assert vals == (sorted(vals, reverse=True) if m in asc else sorted(vals)), (
                f"{group}.{m}"
            )


def test_player_percentile_thresholds_agree_with_the_players_pct(tables):
    """A threshold recomputes from the same qualifiers the ``_pct`` came from.

    Median check: the value at pctile 0.50 is the qualifiers' median, and the
    player nearest 50 on the ``_pct`` scale sits next to it.
    """
    _, out = tables
    pp = out["player_percentiles"]
    for table, gate in (
        ("passing", QB_QUALIFIES),
        ("rushing", RB_QUALIFIES),
        ("receiving", WR_QUALIFIES),
    ):
        qual = out[table].filter(gate)
        row = pp.filter((pl.col("position_group") == table) & (pl.col("pctile") == 0.5))
        for metric in PLAYER_RANK_SPECS[table][0]:
            vals = qual[metric].drop_nulls()
            if vals.len() == 0:
                continue
            assert row[metric][0] == pytest.approx(vals.median()), f"{table}.{metric}"


def test_player_percentiles_survive_a_group_with_no_qualifiers():
    pp = prepare_player_percentiles(
        {"passing": pl.DataFrame(schema={"TEPA": pl.Float64}), "rushing": pl.DataFrame()}
    )
    assert pp.height == 198
    assert pp["TEPA"].null_count() == 198 and pp.schema["TEPA"] == pl.Float64


# --- real 2025 output ------------------------------------------------------------------


def test_real_2025_passing_percentiles(  # noqa: D103
):
    """Invariants re-checked on a slice of the REAL 2025 nfl_passing build.

    Synthetic pbp cannot catch a qualification or direction regression that only
    shows up at league scale (34 qualified passers over 17 team games, with real
    ties -- two QBs share ``pass_int_rank`` 18.5). Provenance: the 2025 rows of
    ``nfl_passing`` built from the released ``model_pbp_2025`` by
    ``python -m nfl_team_summaries --seasons 2025``, qualifiers only, six columns.
    """
    df = pl.read_csv(FIX / "nfl_passing_2025_pct_sample.csv")
    assert df.height > 30
    # every sampled row qualified: PFR's 14 dropbacks per team-game
    assert (df["dropbacks"] >= 14.0 * df["team_games"]).all()
    n = df.height
    for metric, ascending in (("EPAplay", False), ("pass_int", True)):
        assert (df[f"{metric}_pct"] == 100 * (n + 1 - df[f"{metric}_rank"]) / (n + 1)).all(), metric
        assert (df[f"{metric}_pct"] > 0).all() and (df[f"{metric}_pct"] < 100).all()
        s = df.sort(metric, descending=ascending)
        assert s[f"{metric}_pct"].to_list() == sorted(s[f"{metric}_pct"].to_list()), metric


def test_attach_leader_ranks_gates_rank_and_pct_on_the_same_rows():
    """The gate is one filter: a non-qualifier gets neither a rank nor a percentile."""
    df = pl.DataFrame(
        {
            "k": list("abcdef"),
            "plays": [20.0, 18.0, 16.0, 14.0, 2.0, 1.0],  # e, f miss 6.25/game x 2
            "team_games": [2] * 6,
            "TEPA": [5.0, 4.0, 3.0, 2.0, 9.0, 8.0],
            "EPAgame": [1.0, 2.0, 3.0, None, 5.0, 6.0],
            "EPAplay": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
            "success": [0.5] * 6,
            "yards": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            "rushing_td": [1.0] * 6,
            "fumbles": [0.0, 1.0, 2.0, 3.0, 4.0, 5.0],
            "yardsplay": [1.0] * 6,
            "yardsgame": [1.0] * 6,
        }
    )
    out = _attach_leader_ranks(df, keys=["k"], min_expr=RB_QUALIFIES, spec="rushing")
    miss = out.filter(pl.col("k").is_in(["e", "f"]))
    assert miss["TEPA_rank"].null_count() == 2 and miss["TEPA_pct"].null_count() == 2
    hit = out.filter(~pl.col("k").is_in(["e", "f"])).sort("k")
    assert hit["TEPA_rank"].to_list() == [1.0, 2.0, 3.0, 4.0]
    assert hit["TEPA_pct"].to_list() == [80.0, 60.0, 40.0, 20.0]
    # a null metric keeps its trailing rank but loses the percentile
    assert hit.filter(pl.col("EPAgame").is_null())["EPAgame_rank"][0] == 4.0
    assert hit.filter(pl.col("EPAgame").is_null())["EPAgame_pct"][0] is None
    # fumbles rank low-is-good: the cleanest back tops the percentile
    assert hit.sort("fumbles")["fumbles_pct"].to_list() == [80.0, 60.0, 40.0, 20.0]


# --- sample sizes -----------------------------------------------------------------


@pytest.mark.parametrize("table", ["passing", "rushing", "receiving", "team_summaries"])
def test_every_n_column_is_int_suffixed_and_has_its_rate(tables, table):
    _, out = tables
    df = out[table]
    ns = [c for c in df.columns if c.endswith("_n")]
    assert ns, table
    assert [c for c in df.columns if "_n_" in c] == []
    assert [c for c in ns if c[:-2] not in df.columns] == []
    assert all(df.schema[c] == pl.Int64 for c in ns)


def test_rates_carry_their_real_denominators(tables):
    _, out = tables
    qb, wr, ts = out["passing"], out["receiving"], out["team_summaries"]
    assert (qb["EPAplay_n"] == qb["dropbacks"].cast(pl.Int64)).all()
    assert (qb["comppct_n"] == qb["att"].cast(pl.Int64)).all()
    assert (qb["yardsplay_n"] == qb["att"].cast(pl.Int64)).all()  # yards_denom="att" in this league
    assert (wr["catchpct_n"] == wr["targets"].cast(pl.Int64)).all()
    assert (ts["EPAplay_off_n"] == ts["plays_off"].cast(pl.Int64)).all()
    assert (
        ts["EPAplay_off_pass_n"].fill_null(0) == ts["plays_off_pass"].fill_null(0).cast(pl.Int64)
    ).all()


def test_every_rbsdm_rate_has_its_sample_size(tables):
    _, out = tables
    ts = out["team_summaries"]
    rates = [c for c in RBSDM_RANKED if c != "fourth_decisions_off" and c in ts.columns]
    assert [c for c in rates if f"{c}_n" not in ts.columns] == []
    assert (
        ts["fourth_go_rate_off_n"].fill_null(0)
        == ts["fourth_decisions_off"].fill_null(0).cast(pl.Int64)
    ).all()


# --- league baselines --------------------------------------------------------------


def test_league_averages_describe_the_qualified_population(tables):
    _, out = tables
    la = out["league_averages"]
    assert set(la["level"].unique()) == {"nfl"}
    rows = la.filter((pl.col("category") == "passing") & (pl.col("metric") == "EPAplay"))
    qual = out["passing"].filter(QB_QUALIFIES & pl.col("EPAplay").is_finite())
    assert qual.height > 0
    row = rows.row(0, named=True)
    assert row["n"] == qual.height and row["qualifier_min"] == QB_MIN_DROPBACKS_PER_GAME
    assert row["mean"] == pytest.approx(qual["EPAplay"].mean())


def test_team_game_median_matches_the_percentiles_table(tables):
    _, out = tables
    tg = out["league_averages"].filter(pl.col("category") == "team_game")
    mid = out["percentiles"].filter((pl.col("pctile") - 0.5).abs() < 1e-9).row(0, named=True)
    assert tg.height > 0
    for r in tg.iter_rows(named=True):
        assert r["median"] == pytest.approx(mid[r["metric"]], abs=1e-9), r["metric"]


# --- Five Factors ------------------------------------------------------------------

#: the seven Five Factors columns -> ranked high-first? (fewer giveaways and fewer
#: points allowed per opponent trip are the good directions)
FIVE_FACTORS = {
    "explosive_margin": True,
    "pts_per_opp_off": True,
    "pts_per_opp_def": False,
    "pts_per_opp_margin": True,
    "turnovers_off": False,
    "turnovers_def": True,
    "turnover_margin": True,
}


def test_five_factor_columns_and_ranks_exist(tables):
    _, out = tables
    ts = out["team_summaries"]
    for c in FIVE_FACTORS:
        assert c in ts.columns and f"{c}_rank" in ts.columns, c
        assert ts.schema[c] == pl.Float64, c
        assert ts.schema[f"{c}_rank"] == pl.Float64, c
    for c in ("pts_per_opp_off_n", "pts_per_opp_def_n"):
        assert ts.schema[c] == pl.Int64, c


def test_turnover_margin_sums_to_zero_across_the_league(tables):
    # every game of the synthetic season is in the fixture: each giveaway is
    # somebody's takeaway, and every team played the same number of games
    _, out = tables
    ts = out["team_summaries"]
    assert ts["turnovers_off"].sum() > 0  # the doctored picks reached the grid
    assert abs(ts["turnover_margin"].sum()) <= 1e-9 * len(GAMES)
    assert ts["turnover_margin"].to_list() == pytest.approx(
        (ts["turnovers_def"] - ts["turnovers_off"]).to_list()
    )


def test_five_factor_ranks_run_one_to_n_without_gaps(tables):
    """Average-tie ranks over the league: they sum to n(n+1)/2 and sit in [1, n]."""
    _, out = tables
    ts = out["team_summaries"]
    for c in FIVE_FACTORS:
        r = ts[f"{c}_rank"].drop_nulls()
        n = ts[c].drop_nulls().len()
        assert r.len() == n, c
        assert r.sum() == pytest.approx(n * (n + 1) / 2), c
        assert r.min() >= 1 and r.max() <= n, c


def test_five_factor_ranks_point_the_right_way(tables):
    _, out = tables
    ts = out["team_summaries"]
    for c, high_first in FIVE_FACTORS.items():
        s = ts.filter(pl.col(c).is_not_null()).sort(c, descending=high_first)
        ranks = s[f"{c}_rank"].to_list()
        assert ranks == sorted(ranks), c


def test_explosive_margin_is_offense_minus_defense(tables):
    _, out = tables
    ts = out["team_summaries"]
    assert ts["explosive_margin"].to_list() == pytest.approx(
        (ts["explosive_off"] - ts["explosive_def"]).to_list()
    )


_FF_G1 = ("2025_01_BUF_KC", "KC", "BUF")  # KC home
_FF_G2 = ("2025_02_KC_BUF", "BUF", "KC")  # BUF home


def _five_factor_pbp() -> pl.DataFrame:
    """Two teams, two games, every drive hand-placed (KC is team A, BUF team B).

    KC: a TD drive that snaps at the 35; a FG drive whose deepest snap is
    exactly the 40; a punt drive that stalls at the 41 (and fumbles, but KC
    recovers); an interception; a lost fumble. BUF: two interceptions (uneven
    on purpose, so charging picks to the wrong side shows), the second of which
    the KC defender fumbles back to BUF -- one giveaway and one takeaway for EACH
    side on one play; and a punt KC muffs and BUF recovers -- a special-teams
    giveaway charged to the RECEIVING team, which is not ``posteam`` on a punt.
    """
    rng = random.Random(0)
    # (game, fixed_drive, offense, fixed_drive_result, [(yardline_100, kind, overrides)])
    drives = [
        (_FF_G1, 1, "KC", "Touchdown", [(75, "pass", {}), (50, "run", {}), (35, "pass", {})]),
        (_FF_G1, 2, "BUF", "Turnover", [(75, "run", {}), (65, "pass", {"interception": 1})]),
        (
            _FF_G1,
            3,
            "KC",
            "Field goal",
            [(60, "run", {}), (45, "pass", {}), (40, "run", {}), (40, "field_goal", {})],
        ),
        (
            _FF_G1,
            4,
            "BUF",
            "Punt",
            [
                (
                    70,
                    "pass",
                    {
                        "interception": 1,
                        "fumble": 1,
                        "fumble_lost": 1,
                        "fumbled_1_team": "KC",
                    },
                )
            ],
        ),
        (
            _FF_G2,
            1,
            "KC",
            "Punt",
            [
                (80, "run", {}),
                (55, "pass", {}),
                (41, "run", {"fumble": 1, "fumbled_1_team": "KC"}),
                (41, "punt", {}),
            ],
        ),
        (
            _FF_G2,
            2,
            "BUF",
            "Punt",
            [
                (70, "run", {}),
                (50, "pass", {}),
                (50, "punt", {"fumble": 1, "fumble_lost": 1, "fumbled_1_team": "KC"}),
            ],
        ),
        (_FF_G2, 3, "KC", "Turnover", [(75, "pass", {"interception": 1})]),
        (
            _FF_G2,
            4,
            "KC",
            "Turnover",
            [(70, "run", {"fumble": 1, "fumble_lost": 1, "fumbled_1_team": "KC"})],
        ),
    ]
    rows = []
    play_id = {g[0]: 0 for g in (_FF_G1, _FF_G2)}
    for (gid, home, away), drive, off, result, snaps in drives:
        defteam = away if off == home else home
        for down, (y100, kind, overrides) in enumerate(snaps, start=1):
            play_id[gid] += 1
            special = kind in ("punt", "field_goal")
            row = _play(
                gid,
                play_id[gid],
                drive,
                kind,
                off,
                defteam,
                home,
                away,
                down=4 if special else min(down, 3),
                y100=y100,
                gain=0 if special else 5,
                rng=rng,
                qtr=1,
            )
            rows.append(row | {"fixed_drive_result": result} | overrides)
    return pl.DataFrame(rows)


def _five_factor_rows() -> dict[str, dict]:
    pbp = _five_factor_pbp()
    assert (pbp["interception"] == 1).sum() == 3  # BUF throws two, KC one: uneven on purpose
    plays = add_derived_metrics(prepare_plays(pbp, 2025, schedule_fn=_schedule))
    team = _prepare_for_write(
        _side_pair(plays)
        .join(_drives_table(plays), on="pos_team_id", how="left")
        .join(_turnovers(pbp), on="pos_team_id", how="left"),
        2025,
    )
    return {r["pos_team"]: r for r in team.iter_rows(named=True)}


def test_points_per_scoring_opportunity_by_hand():
    rows = _five_factor_rows()
    kc, buf = rows["KC"], rows["BUF"]
    # (7 + 3) / 2: the 35 and the 40 are inside the opponent 40, the 41 is not
    assert kc["pts_per_opp_off"] == pytest.approx(5.0)
    assert kc["pts_per_opp_off_n"] == 2
    # BUF's defense faced exactly KC's offense
    assert buf["pts_per_opp_def"] == pytest.approx(kc["pts_per_opp_off"])
    assert buf["pts_per_opp_def_n"] == 2
    # BUF never got inside the 40: no rate, and UNRANKED rather than ranked last
    assert buf["pts_per_opp_off"] is None and buf["pts_per_opp_off_n"] == 0
    assert buf["pts_per_opp_off_rank"] is None
    assert kc["pts_per_opp_def"] is None and kc["pts_per_opp_def_rank"] is None
    assert kc["pts_per_opp_off_rank"] == 1.0 and buf["pts_per_opp_def_rank"] == 1.0
    assert kc["pts_per_opp_margin"] is None and kc["pts_per_opp_margin_rank"] is None


def test_turnovers_per_game_by_hand():
    rows = _five_factor_rows()
    kc, buf = rows["KC"], rows["BUF"]
    # KC gives it away 4 times -- a pick, a LOST fumble, a muffed punt and the
    # fumble its defender lost after intercepting BUF (the fumble KC recovered is
    # no giveaway) -- and takes it away twice: BUF's two picks. Over two games.
    # Every play counts, as in the official differential: the muff and the
    # fumble-back are KC's giveaways although BUF had the ball.
    assert kc["turnovers_off"] == pytest.approx(2.0)
    assert kc["turnovers_def"] == pytest.approx(1.0)
    assert kc["turnover_margin"] == pytest.approx(-1.0)
    assert buf["turnovers_off"] == pytest.approx(1.0)
    assert buf["turnovers_def"] == pytest.approx(2.0)
    assert buf["turnover_margin"] == pytest.approx(1.0)
    # fewer giveaways, more takeaways and the better margin each rank 1
    assert (buf["turnovers_off_rank"], kc["turnovers_off_rank"]) == (1.0, 2.0)
    assert (buf["turnovers_def_rank"], kc["turnovers_def_rank"]) == (1.0, 2.0)
    assert (buf["turnover_margin_rank"], kc["turnover_margin_rank"]) == (1.0, 2.0)


def test_turnover_games_count_either_side_of_the_ball():
    """A game where the raw frame never gives a team the ball still counts for it.

    Drop BUF's only possession of game 2 (its punt, and KC's muff with it): BUF
    still played two games, so both of its rates divide by 2 and the league
    margin stays 0. Counting games from ``posteam`` alone would divide BUF's
    rates by 1.
    """
    pbp = _five_factor_pbp().filter(
        ~((pl.col("game_id") == _FF_G2[0]) & (pl.col("posteam") == "BUF"))
    )
    t = _turnovers(pbp)
    assert abs(t["turnover_margin"].sum()) <= 1e-9
    buf = t.filter(pl.col("pos_team_id") == "2").row(0, named=True)  # BUF on ESPN
    assert buf["turnovers_off"] == pytest.approx(1.0)  # its two picks, / 2
    assert buf["turnovers_def"] == pytest.approx(1.5)  # KC's pick, lost fumble, fumble-back, / 2


def test_no_drive_results_means_no_points_per_trip():
    """1999-2001 ``model_pbp`` carry no ``fixed_drive_result``.

    The season must still build. Its points per trip are UNKNOWN -- null and
    unranked, never 0.0 (which ``sum()`` over null points would produce) -- while
    the trip counts and the other Five Factors columns stand.
    """
    pbp = _fake_pbp().drop("fixed_drive_result")
    plays = prepare_plays(pbp, 2025, schedule_fn=_schedule)
    ts = build_team_summaries(plays, filter_season_types(pbp, ("REG",)), 2025)["team_summaries"]
    for c in ("pts_per_opp_off", "pts_per_opp_def", "pts_per_opp_margin"):
        assert ts[c].is_null().all(), c
        assert ts[f"{c}_rank"].is_null().all(), c
    assert (ts["pts_per_opp_off_n"] > 0).all() and (ts["pts_per_opp_def_n"] > 0).all()
    for c in ("explosive_margin", "turnovers_off", "turnovers_def", "turnover_margin"):
        assert ts[c].null_count() == 0 and ts[f"{c}_rank"].null_count() == 0, c


# --- team_opponent_splits (F7) --------------------------------------------------------

#: the published contract (plan F7 "Interfaces"); nflverse_game_id rides along
#: because the ESPN event id is null before 2002
SPLITS_SCHEMA = {
    "season": pl.Int64,
    "team_id": pl.Int64,
    "opponent_id": pl.Int64,
    "game_id": pl.Int64,
    "epa_per_play": pl.Float64,
    "success_rate": pl.Float64,
    "points_for": pl.Int64,
    "points_against": pl.Int64,
    "plays": pl.Int64,
    "is_home": pl.Boolean,
    "week": pl.Int64,
    "season_type": pl.Int64,
    "nflverse_game_id": pl.Utf8,
}


def test_opponent_splits_carry_espn_int64_ids(splits):
    s = splits
    assert dict(s.schema) == SPLITS_SCHEMA
    assert set(s["team_id"]) == set(s["opponent_id"]) == {12, 2, 21, 6}  # KC, BUF, PHI, DAL
    assert dict(zip(s["nflverse_game_id"], s["game_id"])) == ESPN_EVENTS
    assert (s["season"] == 2025).all() and (s["season_type"] == 2).all()
    assert set(s["week"]) == {1, 2}


def test_opponent_splits_two_rows_per_game(splits):
    # grouped on the nflverse id: the ESPN game_id is null before 2002
    per_game = splits.group_by("nflverse_game_id").agg(
        n=pl.len(), teams=pl.col("team_id").n_unique(), home=pl.col("is_home").sum()
    )
    assert per_game.height == len(GAMES)
    assert (per_game["n"] == 2).all() and (per_game["teams"] == 2).all()
    assert (per_game["home"] == 1).all()
    assert (splits["team_id"] != splits["opponent_id"]).all()


def test_opponent_splits_points_mirror_across_the_game(splits):
    """Side A's points_for is side B's points_against -- anchored to the final
    score, so a for/against swap made on both sides at once still fails."""
    s = splits
    pair = s.join(
        s,
        left_on=["nflverse_game_id", "team_id"],
        right_on=["nflverse_game_id", "opponent_id"],
        suffix="_b",
    )
    assert pair.height == s.height
    assert (pair["points_for"] == pair["points_against_b"]).all()
    assert (pair["points_against"] == pair["points_for_b"]).all()
    home = s.filter(pl.col("is_home") == True)  # noqa: E712
    got = {
        g: (pf, pa)
        for g, pf, pa in home.select("nflverse_game_id", "points_for", "points_against").iter_rows()
    }
    assert got == SCORES


def test_opponent_splits_reconcile_with_season_epa(tables, splits):
    """Plays-weighted EPA/play over a team's games IS its season EPAplay_off."""
    ts = tables[1]["team_summaries"].select("team_id", "EPAplay_off", "plays_off")
    w = splits.group_by("team_id").agg(
        epa=(pl.col("epa_per_play") * pl.col("plays")).sum() / pl.col("plays").sum(),
        plays=pl.col("plays").sum(),
    )
    assert w.schema["team_id"] == ts.schema["team_id"]
    j = ts.join(w, on="team_id", how="inner")
    assert j.height == 4
    for r in j.iter_rows(named=True):
        assert abs(r["epa"] - r["EPAplay_off"]) <= 1e-9, r
        assert r["plays"] == r["plays_off"], r


def _splits_with(raw_extra: pl.DataFrame | None = None, ids=None, yr: int = 2025):
    pbp = _fake_pbp()
    plays = prepare_plays(pbp, 2025, schedule_fn=_schedule)
    raw = filter_season_types(pbp, ("REG",))
    if raw_extra is not None:
        raw = pl.concat([raw, raw_extra], how="diagonal_relaxed")
    return build_team_opponent_splits(plays, raw, yr, _espn_game_ids() if ids is None else ids)


def test_a_game_with_no_scrimmage_play_is_dropped():
    """The 2022 BUF-CIN no-contest: two placeholder rows (GAME, "cancelled")
    and a 7-3 score, but not one snap. It is not a game either team played."""
    gid = "2025_03_KC_DAL"
    no_contest = pl.DataFrame(
        {
            "season_type": ["REG", "REG"],
            "season": [2025, 2025],
            "game_id": [gid, gid],
            "play_id": [1, 653],
            "week": [3, 3],
            "home_team": ["DAL", "DAL"],
            "away_team": ["KC", "KC"],
            "home_score": [7, 7],
            "away_score": [3, 3],
            "posteam": [None, None],
            "play_type": [None, None],
        }
    )
    ids = pl.concat([_espn_game_ids(), pl.DataFrame({"nflverse_game_id": [gid], "game_id": [1]})])
    s = _splits_with(no_contest, ids)
    assert gid not in s["nflverse_game_id"].to_list()
    assert s.height == 2 * len(GAMES)
    assert (s["plays"] > 0).all()


def test_an_unmatched_game_keeps_its_row_before_the_espn_library():
    """Before 2002 ESPN has no library: the game_id is null and the row stays."""
    ids = _espn_game_ids().filter(pl.col("nflverse_game_id") != "2025_01_BUF_KC")
    s = _splits_with(ids=ids, yr=1999)
    assert s.height == 2 * len(GAMES)
    miss = s.filter(pl.col("nflverse_game_id") == "2025_01_BUF_KC")
    assert miss.height == 2 and miss["game_id"].is_null().all()
    assert s.filter(pl.col("nflverse_game_id") != "2025_01_BUF_KC")["game_id"].null_count() == 0


def test_an_unmatched_played_game_raises_in_the_espn_era():
    ids = _espn_game_ids().filter(pl.col("nflverse_game_id") != "2025_01_BUF_KC")
    with pytest.raises(ValueError, match="no ESPN event id"):
        _splits_with(ids=ids, yr=2025)


def test_a_duplicated_crosswalk_row_raises():
    ids = _espn_game_ids()
    ids = pl.concat([ids, ids.head(1).with_columns(game_id=pl.lit(999, dtype=pl.Int64))])
    with pytest.raises(pl.exceptions.ComputeError, match="m:1"):
        _splits_with(ids=ids)


def _write_crosswalk(root: Path, body: str | None) -> str:
    d = root / "crosswalk"
    d.mkdir()
    if body is not None:
        (d / "games.json").write_text(body)
    return str(root)


def test_load_espn_game_ids_reads_the_nfl_raw_crosswalk(tmp_path):
    from nfl_team_summaries.crosswalk import load_espn_game_ids

    root = _write_crosswalk(
        tmp_path,
        '[{"espn_event_id": 401772500, "game_id": "2025_01_BUF_KC"},'
        ' {"espn_event_id": 401772999, "game_id": null}]',
    )
    ids = load_espn_game_ids(root)
    assert dict(ids.schema) == {"nflverse_game_id": pl.Utf8, "game_id": pl.Int64}
    assert ids.rows() == [("2025_01_BUF_KC", 401772500)]


@pytest.mark.parametrize(
    "body",
    [
        None,  # file absent
        '{"games": [{"espn_event_id": 401772500, "game_id": "2025_01_BUF_KC"}]}',  # wrapped
        "[]",  # empty
    ],
    ids=["missing", "wrapped", "empty"],
)
def test_load_espn_game_ids_refuses_an_unusable_crosswalk(tmp_path, body):
    from nfl_team_summaries.crosswalk import load_espn_game_ids

    with pytest.raises(ValueError, match="crosswalk/games.json"):
        load_espn_game_ids(_write_crosswalk(tmp_path, body))


@pytest.mark.parametrize("crosswalk_ok", [True, False], ids=["crosswalk_ok", "crosswalk_down"])
def test_cli_publishes_the_seven_even_when_the_splits_fail(tmp_path, monkeypatch, crosswalk_ok):
    """A crosswalk failure skips ONE tag and fails the run; the seven still publish."""
    import nfl_model_publish.artifacts as artifacts
    from nfl_team_summaries import __main__ as cli

    _fake_pbp().write_parquet(tmp_path / "model_pbp_2025.parquet")
    monkeypatch.setattr(
        cli,
        "prepare_plays",
        lambda pbp, season, season_types: prepare_plays(
            pbp, season, season_types=season_types, schedule_fn=_schedule
        ),
    )

    def crosswalk():
        if not crosswalk_ok:
            raise ValueError("crosswalk/games.json is missing")
        return _espn_game_ids()

    monkeypatch.setattr(cli, "load_espn_game_ids", crosswalk)
    uploaded: list[str] = []
    monkeypatch.setattr(
        artifacts,
        "upload_artifacts",
        lambda d, tag, repo, pattern, dry_run: uploaded.append(tag) or {"uploaded": 1},
    )
    out = tmp_path / "out"
    rc = cli.main(["--seasons", "2025", "--pbp-dir", str(tmp_path), "--out", str(out), "--publish"])

    seven = [tag for tag, _ in cli.TABLES.values()]
    splits_file = out / cli.SPLITS[0] / f"{cli.SPLITS[1]}_2025.parquet"
    for tag, stem in cli.TABLES.values():
        assert (out / tag / f"{stem}_2025.parquet").exists(), tag
    if crosswalk_ok:
        assert rc == 0 and uploaded == [*seven, cli.SPLITS[0]] and splits_file.exists()
    else:
        assert rc == 1 and uploaded == seven and not splits_file.exists()
