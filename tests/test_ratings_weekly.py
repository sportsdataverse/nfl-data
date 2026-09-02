"""Hermetic tests for the nfl_ratings_weekly builder (no network)."""

import datetime as dt

import polars as pl
from nfl_ratings_weekly.builder import build_season, week_starts


def _schedule() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "week": [1, 1, 2, 2, 3],
            "gameday": ["2024-09-05", "2024-09-08", "2024-09-12", "2024-09-15", "2024-09-19"],
        }
    )


def test_week_starts_uses_first_kickoff():
    assert week_starts(_schedule()) == [(1, "2024-09-05"), (2, "2024-09-12"), (3, "2024-09-19")]


def test_build_season_exclusive_cutoffs_and_labels():
    """The as-of cutoff for week W is week W's FIRST kickoff (EXCLUSIVE)."""
    calls: list[dt.date] = []

    def fake_ratings(season, *, as_of_date):
        calls.append(as_of_date)
        if as_of_date <= dt.date(2024, 9, 5):
            return pl.DataFrame()  # week 1: nothing knowable yet
        return pl.DataFrame({"team_id": ["A", "B"], "adj_net": [1.0, -1.0]})

    out = build_season(2024, ratings_fn=fake_ratings, schedule_fn=lambda seasons: _schedule())
    assert calls == [dt.date(2024, 9, 5), dt.date(2024, 9, 12), dt.date(2024, 9, 19)]
    # week 1 emitted nothing; weeks 2-3 labeled with their as_of_week
    assert out["as_of_week"].unique().sort().to_list() == [2, 3]
    assert out.schema["as_of_week"] == pl.Int32
    assert out.height == 4


def test_build_season_drops_empty_team_rows():
    """The 1999-2000 pbp '' team artifact must not reach the vintages."""

    def fake_ratings(season, *, as_of_date):
        return pl.DataFrame({"team_id": ["A", "", "B"], "adj_net": [1.0, 0.0, -1.0]})

    out = build_season(2024, ratings_fn=fake_ratings, schedule_fn=lambda seasons: _schedule())
    assert out.filter(pl.col("team_id") == "").height == 0
    assert set(out["team_id"].unique().to_list()) == {"A", "B"}


def test_build_season_empty_when_no_weeks():
    out = build_season(
        2024,
        ratings_fn=lambda s, *, as_of_date: pl.DataFrame(),
        schedule_fn=lambda seasons: _schedule(),
    )
    assert out.height == 0


def test_build_season_skips_unpublished_pbp_season():
    """Before kickoff the season's pbp asset is absent (NoDataError), which the
    Tuesday cron hit on its first in-season fire (2026-09-01). That is zero rows,
    not a failure -- and the builder must not raise or retry every week."""
    from sportsdataverse.errors import NoDataError

    calls: list[dt.date] = []

    def absent(season, *, as_of_date):
        calls.append(as_of_date)
        raise NoDataError("play_by_play_2026.parquet: 404")

    out = build_season(2026, ratings_fn=absent, schedule_fn=lambda seasons: _schedule())
    assert out.height == 0
    assert len(calls) == 1


def test_cli_publish_exits_zero_when_no_season_has_vintages_yet(monkeypatch, tmp_path):
    """--publish with nothing built is the pre-kickoff state, not an error: the
    scheduled Tuesday run must go green and simply publish nothing (Sourcery on
    nfl-data #27)."""
    import nfl_ratings_weekly.__main__ as cli

    monkeypatch.setattr(cli, "build_season", lambda season: pl.DataFrame())
    rc = cli.main(["--seasons", "2026", "--out", str(tmp_path), "--publish"])
    assert rc == 0
    assert list(tmp_path.glob("*.parquet")) == []
