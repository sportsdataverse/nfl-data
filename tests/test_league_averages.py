"""League baselines contract (``league_averages``) -- the pure module."""

from __future__ import annotations

import polars as pl
import pytest
from nfl_team_summaries.league_averages import SCHEMA, build_league_averages, summarize

QUALIFIERS = {"passing": (pl.col("dropbacks") >= 14.0 * pl.col("team_games"), 14.0)}


def test_summarize_counts_only_finite_metric_values():
    df = pl.DataFrame(
        {
            "season": [2025, 2025, 2025, 2025],
            "team_id": [1, 2, 3, 4],
            "EPAplay": [0.1, 0.2, 0.3, None],
            "yardsplay": [1.0, float("nan"), 3.0, 5.0],
            "EPAplay_rank": [3.0, 2.0, 1.0, 4.0],
            "EPAplay_pct": [25.0, 50.0, 75.0, None],
            "EPAplay_n": [10, 10, 10, 0],
            "conference": ["AFC", "AFC", "NFC", "NFC"],
        }
    )
    out = summarize(df, season=2025, level="nfl", entity="team", category="team_summaries")
    assert list(out.schema.items()) == list(SCHEMA.items())
    assert out["metric"].to_list() == ["EPAplay", "yardsplay"]
    epa = out.row(0, named=True)
    assert epa["mean"] == pytest.approx(0.2) and epa["sd"] == pytest.approx(0.1) and epa["n"] == 3


def test_players_are_gated_to_qualifiers():
    passing = pl.DataFrame(
        {
            "team_id": [1, 2, 3],
            "player_id": ["a", "b", "c"],
            "team_games": [17, 17, 17],
            "dropbacks": [300.0, 100.0, 500.0],
            "EPAplay": [0.2, 0.9, 0.1],
        }
    )
    out = build_league_averages(
        {"passing": passing}, 2025, levels={"nfl": None}, qualifiers=QUALIFIERS
    )
    ep = out.filter(pl.col("metric") == "EPAplay").row(0, named=True)
    assert (ep["level"], ep["n"], ep["qualifier_min"]) == ("nfl", 2, 14.0)
    assert ep["mean"] == pytest.approx(0.15)
