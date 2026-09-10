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
from nfl_team_summaries.build import _attach_leader_ranks, build_team_summaries
from nfl_team_summaries.crosswalk import attach_team_ids, load_crosswalk
from nfl_team_summaries.input import filter_season_types, prepare_plays

FIX = Path(__file__).parent / "fixtures"
TEAMS = ["KC", "BUF", "PHI", "DAL"]
GAMES = [
    ("2025_01_BUF_KC", "KC", "BUF"),
    ("2025_01_DAL_PHI", "PHI", "DAL"),
    ("2025_02_KC_PHI", "PHI", "KC"),
    ("2025_02_BUF_DAL", "DAL", "BUF"),
]


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
        "play_type": play_type,
        "down": down,
        "ydstogo": 10 if down in (1, None) else rng.randint(1, 9),
        "yardline_100": y100,
        "yards_gained": gain,
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
    assert sum(ts[c].null_count() for c in ts.columns if c.endswith("_rank")) == 0
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
