"""Play-description regex layer (ported from nflfastR helper_add_nflscrapr_mutations.R).

Adds the text-derived columns the models / nflverse schema expect — chiefly
``pass_location`` (CP feature) plus ``pass_length``, ``run_location``,
``run_gap``, and the qb_kneel / qb_spike / qb_scramble / shotgun / no_huddle
indicators — and refines ``play_type`` to ``qb_kneel`` / ``qb_spike``.

``air_yards`` is NOT parsed here — it comes from the stats feed (statType
111/112) in :mod:`native_pbp.stat_ids`.
"""
from __future__ import annotations

import polars as pl


def add_description_features(df: pl.DataFrame) -> pl.DataFrame:
    """Add description-derived columns + refine play_type. Expects a ``desc`` column.

    Args:
        df: A base play frame from :func:`native_pbp.parse.parse_game`.

    Returns:
        The frame with ``pass_length``, ``pass_location``, ``run_location``,
        ``run_gap``, ``qb_kneel``, ``qb_spike``, ``qb_scramble``, ``shotgun``,
        ``no_huddle`` added and ``play_type`` refined for kneels/spikes.
    """
    if df.height == 0:
        return df
    d = pl.col("desc").fill_null("")
    df = df.with_columns(
        pass_length=d.str.extract(r"pass (?:incomplete )?(short|deep)", 1),
        pass_location=d.str.extract(r"(?:short|deep) (left|middle|right)", 1),
        run_location_raw=d.str.extract(r" (left|middle|right)[ .]", 1),
        run_gap_raw=d.str.extract(r" (guard|tackle|end)\b", 1),
        qb_kneel=d.str.contains(" kneels").cast(pl.Int64),
        qb_spike=d.str.contains(" spiked").cast(pl.Int64),
        qb_scramble=d.str.contains(" scrambles").cast(pl.Int64),
        shotgun=d.str.contains("Shotgun").cast(pl.Int64),
        no_huddle=d.str.contains("No Huddle").cast(pl.Int64),
    )
    # run_location / run_gap only meaningful on runs.
    df = df.with_columns(
        run_location=pl.when(pl.col("play_type") == "run").then(pl.col("run_location_raw")).otherwise(None),
        run_gap=pl.when(pl.col("play_type") == "run").then(pl.col("run_gap_raw")).otherwise(None),
    ).drop("run_location_raw", "run_gap_raw")
    # Refine play_type: kneels/spikes override the rush/pass base class.
    df = df.with_columns(
        play_type=pl.when(pl.col("qb_kneel") == 1).then(pl.lit("qb_kneel"))
        .when(pl.col("qb_spike") == 1).then(pl.lit("qb_spike"))
        .otherwise(pl.col("play_type"))
    )
    return df
