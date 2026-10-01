"""Stage 07 (``nfl_metric_curves``) over the committed REAL 2024 ``nfl_model_pbp`` season.

``nfl/model_pbp/model_pbp_2024.parquet`` is copied once into a tmp dir (the CLI
reads it through ``--pbp-dir``); every oracle below is recomputed from that same
file, never pinned. The gsis -> espn map is sdv-py's real players master, loaded
once per module over the network. The offline CI checkout is sparse and carries
no ``nfl/`` tree, so this module skips there and gates locally.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import polars as pl
import pytest
from nfl_model_publish import artifacts
from nfl_model_publish.artifacts import _RELEASE_BODY, PKG_FUNCTION
from nfl_team_summaries.crosswalk import load_crosswalk
from nfl_team_summaries.curves import SCHEMA, STEM, TAG, build_metric_curves, gsis_to_espn, main
from sportsdataverse.metric_curves import BUCKET_EDGES

ROOT = Path(__file__).resolve().parents[1]
SEASON = 2024
PBP = ROOT / "nfl" / "model_pbp" / f"model_pbp_{SEASON}.parquet"
GSIS = r"^00-00\d{5}$"
INT = r"^\d+$"

pytestmark = pytest.mark.skipif(
    not PBP.is_file(), reason=f"{PBP.relative_to(ROOT)} absent (sparse CI checkout)"
)


@pytest.fixture(scope="module")
def pbp_dir(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("model_pbp")
    shutil.copyfile(PBP, d / PBP.name)
    return d


@pytest.fixture(scope="module")
def players() -> pl.DataFrame:
    return gsis_to_espn()


@pytest.fixture(scope="module")
def curves(pbp_dir, players) -> pl.DataFrame:
    return build_metric_curves(SEASON, pl.read_parquet(pbp_dir / PBP.name), players=players)


@pytest.fixture(scope="module")
def pbp(pbp_dir) -> pl.DataFrame:
    # regular season + postseason: the population the sdv-py adapter counts
    return pl.read_parquet(
        pbp_dir / PBP.name,
        columns=[
            "season_type",
            "field_goal_attempt",
            "field_goal_result",
            "kick_distance",
            "pass_attempt",
            "sack",
            "air_yards",
            "kicker_player_id",
            "passer_player_id",
        ],
    ).filter(pl.col("season_type").is_in(["REG", "POST"]))


def _in_span(df, metric, col):
    """The attempts sdv-py bins: an attempt outside the metric's fixed edges is dropped by design."""
    lo, hi = BUCKET_EDGES[metric][0], BUCKET_EDGES[metric][-1]
    return df.filter((pl.col(col) >= lo) & (pl.col(col) < hi))


def _league(curves, metric):
    return curves.filter((pl.col("metric") == metric) & (pl.col("entity_type") == "league"))


def test_league_fg_curve_sums_to_the_seasons_fg_attempts_and_makes(pbp, curves):
    fg = pbp.filter((pl.col("field_goal_attempt") == 1) & pl.col("kick_distance").is_not_null())
    assert (
        _in_span(fg, "fg_pct_by_distance", "kick_distance").height == fg.height
    )  # 15-80 covers 2024
    league = _league(curves, "fg_pct_by_distance")
    assert league["attempts"].sum() == fg.height > 0
    assert league["successes"].sum() == fg.filter(pl.col("field_goal_result") == "made").height
    assert (league["rate"] == league["successes"] / league["attempts"]).all()


def test_league_air_yards_curve_sums_to_the_thrown_passes_with_air_yards(pbp, curves):
    passes = pbp.filter(
        (pl.col("pass_attempt") == 1) & (pl.col("sack") == 0) & pl.col("air_yards").is_not_null()
    )
    binned = _in_span(passes, "cmp_pct_by_air_yards", "air_yards")
    assert 0 < passes.height - binned.height < 20  # a dozen throws outside [-10, 70) in 2024
    assert _league(curves, "cmp_pct_by_air_yards")["attempts"].sum() == binned.height > 0


def test_success_by_down_distance_has_exactly_20_league_rows(curves):
    league = _league(curves, "success_by_down_distance")
    assert league.height == 20
    assert sorted(league["down"].unique()) == [1, 2, 3, 4]
    assert league.group_by("down").len()["len"].to_list() == [5] * 4


def test_contract_and_the_id_rule(pbp, curves):
    assert curves.schema == SCHEMA
    assert curves["season"].unique().to_list() == [SEASON]
    assert set(curves["entity_type"]) == {"league", "team", "player"}
    # ids are text, never a stringified float
    for col in ("entity_id", "team_id", "gsis_id"):
        assert not curves[col].drop_nulls().str.contains(r"\.").any()

    league = curves.filter(pl.col("entity_type") == "league")
    assert league["entity_id"].null_count() == league.height
    assert league["gsis_id"].null_count() == league.height

    # teams: stage 06's key, the ESPN team id, for every team in the pbp
    espn_teams = set(load_crosswalk()["espn_team_id"].cast(pl.Utf8))
    team = curves.filter(pl.col("entity_type") == "team")
    assert set(team["entity_id"]) <= espn_teams and team["entity_id"].n_unique() == 32
    assert set(team["id_source"]) == {"espn"}

    # players: ESPN athlete id + the gsis id it came from; an unmatched gsis id keeps its own
    player = curves.filter(pl.col("entity_type") == "player")
    assert player["gsis_id"].str.contains(GSIS).all()
    assert set(player["team_id"]) <= espn_teams
    espn = player.filter(pl.col("id_source") == "espn")
    assert espn["entity_id"].str.contains(INT).all()
    gsis = player.filter(pl.col("id_source") == "gsis")
    assert (gsis["entity_id"] == gsis["gsis_id"]).all()
    assert set(player["id_source"]) <= {"espn", "gsis"}
    matched = espn["gsis_id"].n_unique() / player["gsis_id"].n_unique()
    assert matched > 0.95, f"gsis -> espn match rate {matched:.3f}"
    # every binned kicker and passer is a player row, under one id or the other
    fg = pbp.filter((pl.col("field_goal_attempt") == 1) & pl.col("kick_distance").is_not_null())
    passes = pbp.filter(
        (pl.col("pass_attempt") == 1) & (pl.col("sack") == 0) & pl.col("air_yards").is_not_null()
    )
    credited = set(_in_span(fg, "fg_pct_by_distance", "kick_distance")["kicker_player_id"]) | set(
        _in_span(passes, "cmp_pct_by_air_yards", "air_yards")["passer_player_id"]
    )
    assert set(player["gsis_id"]) == credited - {None}


def test_empty_pbp_is_the_empty_contract_frame(pbp_dir, players):
    df = build_metric_curves(SEASON, pl.read_parquet(pbp_dir / PBP.name).head(0), players=players)
    assert df.height == 0
    assert df.schema == SCHEMA


def test_cli_writes_the_season_and_publishes_only_what_it_wrote(
    pbp_dir, curves, tmp_path, monkeypatch
):
    out = tmp_path / "nfl_metric_curves"
    out.mkdir()
    (out / f"{STEM}_2023.parquet").write_bytes(b"stale")  # a leftover season must not re-upload
    calls: list[tuple[Path, str, str]] = []
    monkeypatch.setattr(
        artifacts,
        "upload_artifacts",
        lambda d, tag, repo, *, pattern, dry_run: (
            calls.append((Path(d), tag, pattern)),
            {"uploaded": 1},
        )[1],
    )
    rc = main(["--seasons", str(SEASON), "--pbp-dir", str(pbp_dir), "--out", str(out), "--publish"])
    assert rc == 0
    written = pl.read_parquet(out / f"{STEM}_{SEASON}.parquet")
    assert written.schema == SCHEMA and written.equals(curves)
    assert calls == [(out, TAG, f"{STEM}_{SEASON}.parquet")]


def test_registered_with_its_tag_and_wired_after_stage_06():
    assert PKG_FUNCTION[TAG].endswith("nfl_data_07_metric_curves.py")
    assert "gsis_id" in _RELEASE_BODY[TAG]
    cron = (ROOT / ".github" / "workflows" / "nfl_pbp_cron.yml").read_text()
    assert cron.index("nfl_data_06_team_summaries") < cron.index("nfl_data_07_metric_curves")
