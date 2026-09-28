"""Hermetic tests for the nfl_ratings_weekly builder (no network)."""

import datetime as dt
from pathlib import Path

import polars as pl
import pytest
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


#: The real 2026 schedule, weeks 1-5 (``load_nfl_schedule``: game_id/week/gameday).
#: Week 3 ends with Monday night on 09-28; week 4 kicks off Thursday 10-01.
SCHEDULE_2026 = pl.read_csv(
    Path(__file__).parent / "fixtures" / "nfl_schedule_2026_wk1_5.csv",
    schema_overrides={"gameday": pl.Utf8},
)


def _vintages(today: dt.date | None) -> tuple[list[dt.date], list[int]]:
    """Build 2026 against the fixture; return (as_of_dates fit, as_of_weeks emitted)."""
    calls: list[dt.date] = []

    def fake_ratings(season, *, as_of_date):
        calls.append(as_of_date)
        if as_of_date <= dt.date(2026, 9, 9):
            return pl.DataFrame()  # week 1: no prior games
        return pl.DataFrame({"team_id": ["A"], "adj_net": [1.0]})

    out = build_season(
        2026, ratings_fn=fake_ratings, schedule_fn=lambda seasons: SCHEDULE_2026, today=today
    )
    return calls, out["as_of_week"].to_list()


def test_future_vintages_are_not_built():
    """The schedule lists every week before it is played. A vintage with an
    unplayed game before its cutoff refit the games already played and shipped
    them relabelled: 2026 as_of_week 4-18 were identical (review of 2026-09-28).
    On 09-28 Monday night is still to come, so as_of_week 4 is not final yet.
    """
    calls, weeks = _vintages(dt.date(2026, 9, 28))

    assert weeks == [2, 3]
    assert calls == [dt.date(2026, 9, 9), dt.date(2026, 9, 17), dt.date(2026, 9, 24)]


@pytest.mark.parametrize(
    "today, weeks",
    [
        (dt.date(2026, 9, 28), [2, 3]),  # Monday night (week 3) is dated today
        (dt.date(2026, 9, 29), [2, 3, 4]),  # Tuesday cron: week 3 is final
        (dt.date(2026, 10, 1), [2, 3, 4]),  # as_of_week 4's own cutoff day
        (dt.date(2026, 10, 6), [2, 3, 4, 5]),
    ],
)
def test_vintage_is_built_once_every_game_before_its_cutoff_is_over(today, weeks):
    """Boundary: as_of_week W's cutoff is week W's FIRST kickoff, so W is final
    once the last game before it is over -- the Tuesday after week W-1, which is
    when the cron runs. A game dated today is not over yet. Waiting for the
    cutoff itself would publish the pre-week-W vintage only after week W.
    """
    assert _vintages(today)[1] == weeks


def test_completed_season_keeps_every_vintage():
    """Every game is in the past: the same vintages as before."""
    calls, weeks = _vintages(dt.date(2027, 3, 1))

    assert weeks == [2, 3, 4, 5]
    assert calls == [dt.date.fromisoformat(c) for _, c in week_starts(SCHEDULE_2026)]
