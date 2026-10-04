"""League baselines contract (``league_averages``) -- the pure module."""

from __future__ import annotations

import polars as pl
import pytest
from nfl_team_summaries.league_averages import (
    SCHEMA,
    build_league_averages,
    metric_columns,
    summarize,
)
from polars.testing import assert_frame_equal

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


def test_dispersion_games_is_a_count_not_a_metric():
    # TFD-5d: the n behind the dispersion columns is context, like games; the split's
    # carries end in _n; the rates themselves are metrics
    df = pl.DataFrame(
        {
            "team_id": [1],
            "games": [17],
            "dispersion_games": [17],
            "boom_rate": [0.2],
            "boom_rate_pos_pct": [50.0],
            "EPAplay_one_score": [0.1],
            "EPAplay_one_score_n": [80],
        }
    )
    assert metric_columns(df) == ["boom_rate", "EPAplay_one_score"]


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


def test_summarize_is_bit_stable_across_row_order():
    """mean/sd must not depend on the unordered group_by feed's row order.

    ``1e16 + -1e16`` cancels exactly, but ``1e16 + 0.1`` loses the 0.1 to
    float64 precision -- so summing this set in a different order lands on a
    different total (0.0 vs 0.6) unless the values are sorted before the
    reduction. That is a real bug class, not a manufactured edge case: polars'
    parallel group_by does not guarantee a row order, so an unsorted mean/std
    churns the published parquet byte-for-byte between identical rebuilds.
    """
    values = [0.1, 0.2, 0.3, 1e16, -1e16]
    order_a = pl.DataFrame({"team_id": list(range(len(values))), "v": values})
    order_b = pl.DataFrame(
        {
            "team_id": list(range(len(values))),
            "v": [1e16, -1e16, 0.1, 0.2, 0.3],
        }
    )
    kwargs = dict(season=2025, level="nfl", entity="team", category="team_summaries")
    out_a = summarize(order_a, **kwargs)
    out_b = summarize(order_b, **kwargs)
    assert_frame_equal(out_a, out_b, check_exact=True)


def test_summarize_empty_frame_keeps_the_schema():
    empty = pl.DataFrame({"team_id": pl.Series([], dtype=pl.Int64)})
    out = summarize(empty, season=2025, level="nfl", entity="team", category="team_summaries")
    assert out.height == 0 and list(out.schema.items()) == list(SCHEMA.items())
