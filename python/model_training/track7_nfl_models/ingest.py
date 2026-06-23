"""Ingest nflverse play-by-play for the NFL model suite (track7).

The track7 trainers need columns track6's ``REQUIRED_COLUMNS`` superset does
not all carry (``two_point_conv_result``, ``sp`` / ``field_goal_result``,
``kick_distance``, ``return_yards``, ``first_down_penalty``, ``penalty_yards``,
``play_type_nfl``, ``desc``, …). The simplest faithful source is sdv-py's
``load_nfl_pbp(source="nflverse")``, which ships the full nflverse PBP schema
(spread_line / total_line / roof / wp / vegas_wp / kick_distance included).
"""
from __future__ import annotations

from typing import List

import polars as pl

__all__ = ["load_training_pbp"]


def load_training_pbp(seasons: List[int], *, source: str = "nflverse") -> pl.DataFrame:
    """Load training PBP for the track7 models.

    Args:
        seasons: Seasons to load (e.g. ``list(range(2006, 2020))``).
        source: ``"nflverse"`` (default) → sdv-py ``load_nfl_pbp`` full schema.

    Returns:
        Concatenated polars DataFrame carrying the full nflverse PBP columns.

    Raises:
        ValueError: If ``source`` is unknown or no rows are returned.

    Example:
        Load the xpass training span::

            from model_training.track7_nfl_models.ingest import load_training_pbp
            df = load_training_pbp(list(range(2006, 2020)))
    """
    if source != "nflverse":
        raise ValueError(f"Unknown source {source!r}; track7 supports 'nflverse'.")
    from sportsdataverse.nfl import load_nfl_pbp

    df = load_nfl_pbp(seasons=seasons, source="nflverse")
    if not isinstance(df, pl.DataFrame):
        df = pl.from_pandas(df)
    if df.height == 0:
        raise ValueError(f"No PBP returned for seasons {seasons}.")
    return df
