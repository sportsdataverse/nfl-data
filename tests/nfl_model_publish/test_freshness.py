"""The pre-publish freshness gate (``nfl_model_publish freshness``) and its wiring.

``nfl_schedule_2026_scores_20261119.csv`` is nflverse's 2026 schedule as
``load_nfl_schedule([2026])`` served it on 2026-11-19 (weeks 1-10 scored, 150 games).
The stale build it must refuse is the one published that day: weeks 1-4 only.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
import yaml
from nfl_model_publish import cli
from nfl_model_publish.freshness import check_dir, season_problems

ROOT = Path(__file__).resolve().parents[2]
SCHEDULE = pl.read_csv(ROOT / "tests" / "fixtures" / "nfl_schedule_2026_scores_20261119.csv")
DONE = SCHEDULE.filter(pl.col("home_score").is_not_null())


def _built(through_week: int) -> pl.DataFrame:
    # two plays a game, as the gate only reads game_id + week
    games = DONE.filter(pl.col("week") <= through_week).select("game_id", "week")
    return pl.concat([games, games])


def test_build_through_the_newest_completed_week_passes():
    assert season_problems(2026, _built(10), SCHEDULE) == []


def test_the_2026_11_19_weeks_1_to_4_build_is_refused():
    problems = season_problems(2026, _built(4), SCHEDULE)
    assert len(problems) == 2
    assert "newest built week 4 is behind the newest completed week 10" in problems[0]
    assert "86 of 150 completed games missing" in problems[1]


def test_one_missing_game_in_a_current_week_is_refused():
    built = _built(10).filter(pl.col("game_id") != "2026_10_KC_ATL")
    assert DONE["game_id"].to_list().count("2026_10_KC_ATL") == 1
    (problem,) = season_problems(2026, built, SCHEDULE)
    assert "1 of 150 completed games missing: 2026_10_KC_ATL" in problem


def test_unplayed_and_extra_built_games_are_fine():
    # a pregame/in-progress game in the build (2026_11_IND_HOU) is not a problem
    extra = pl.DataFrame({"game_id": ["2026_11_IND_HOU"], "week": [11]})
    assert season_problems(2026, pl.concat([_built(10), extra]), SCHEDULE) == []


def test_known_absent_2000_games_are_not_required():
    schedule = pl.DataFrame(
        {
            "game_id": ["2000_03_SD_KC", "2000_06_BUF_MIA", "2000_06_NE_IND"],
            "season": [2000] * 3,
            "week": [3, 6, 6],
            "home_score": [42, 13, 24],
            "away_score": [10, 20, 16],
        }
    )
    built = pl.DataFrame({"game_id": ["2000_06_NE_IND"], "week": [6]})
    assert season_problems(2000, built, schedule) == []


def _write(tmp_path: Path, built: pl.DataFrame) -> Path:
    built.write_parquet(tmp_path / "model_pbp_2026.parquet")
    return tmp_path


def test_check_dir_reads_each_season_file(tmp_path):
    seen = {}

    def schedule_fn(seasons):
        seen["seasons"] = seasons
        return SCHEDULE

    assert check_dir(_write(tmp_path, _built(10)), schedule_fn) == []
    assert seen["seasons"] == [2026]
    assert len(check_dir(_write(tmp_path, _built(4)), schedule_fn)) == 2


def test_check_dir_with_no_parquet_fails(tmp_path):
    assert check_dir(tmp_path, lambda seasons: SCHEDULE) == [
        f"no model_pbp_*.parquet in {tmp_path}"
    ]


@pytest.mark.parametrize(("week", "rc"), [(10, 0), (4, 1)])
def test_cli_exit_code(tmp_path, monkeypatch, capsys, week, rc):
    import sportsdataverse.nfl

    monkeypatch.setattr(sportsdataverse.nfl, "load_nfl_schedule", lambda seasons: SCHEDULE)
    assert cli.main(["freshness", "--parquet-dir", str(_write(tmp_path, _built(week)))]) == rc
    assert ("refusing to publish" in capsys.readouterr().out) is bool(rc)


def test_cron_gates_the_build_before_publishing_and_lists_with_a_token():
    text = (ROOT / ".github" / "workflows" / "nfl_pbp_cron.yml").read_text(encoding="utf-8")
    build = text.index("nfl_data_02_model_pbp build")
    gate = text.index("nfl_model_publish freshness")
    assert build < gate < text.index("nfl_data_03_pbp_publish")
    steps = yaml.safe_load(text)["jobs"]["build-and-publish"]["steps"]
    (step,) = [s for s in steps if s.get("id") == "model_pbp"]
    # the gate sits IN the build step: stages 07/08 key on its outcome, so a stale build skips them
    assert "nfl_model_publish freshness" in step["run"]
    assert step["env"]["GITHUB_TOKEN"] == "${{ github.token }}"


def test_reprocess_gates_each_season_before_publishing():
    text = (ROOT / "scripts" / "reprocess_nfl_model_pbp.sh").read_text(encoding="utf-8")
    gate = text.index("py nfl_model_publish freshness")
    assert (
        text.index("py nfl_data_02_model_pbp build")
        < gate
        < text.index("py nfl_data_03_pbp_publish")
    )
