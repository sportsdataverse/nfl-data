"""Feature engineering for NFL EP/WP/CP models.

Python translation of:
  nflfastR/R/helper_add_ep_wp.R  → make_model_mutations, prepare_wp_data, prepare_ep_data
  nflfastR/R/helper_add_cp_cpoe.R → prepare_cp_data

All functions accept and return polars DataFrames.
"""
from __future__ import annotations

import math

import polars as pl

from .constants import (
    EP_FEATURES,
    WP_SPREAD_FEATURES,
    WP_NAIVE_FEATURES,
    CP_FEATURES,
    EP_CLASS_ORDER,
    EP_LABEL_TO_SCORE,
)

# Era boundary years (left-inclusive, right-exclusive) matching nflfastR
_ERA_BOUNDS: list[tuple[int, int, str]] = [
    (0, 2001, "era0"),
    (2001, 2006, "era1"),
    (2006, 2014, "era2"),
    (2014, 2019, "era3"),
    (2019, 9999, "era4"),
]


def make_model_mutations(df: pl.DataFrame) -> pl.DataFrame:
    """Add all derived columns needed by EP, WP, and CP models.

    Mirrors nflfastR's ``make_model_mutations()`` + relevant parts of
    ``prepare_wp_data()`` for the columns computed at mutation time.

    Added columns (appended; existing columns unchanged):
        home, retractable, dome, outdoors,
        era0..era4, down1..down4
    """
    # home indicator
    df = df.with_columns(
        (pl.col("posteam") == pl.col("home_team")).cast(pl.Float64).alias("home")
    )

    # roof one-hot: 'closed' and 'dome' both map to dome=1
    df = df.with_columns(
        (pl.col("roof") == "retractable").cast(pl.Float64).alias("retractable"),
        pl.when(pl.col("roof").is_in(["dome", "closed"]))
        .then(pl.lit(1.0))
        .otherwise(pl.lit(0.0))
        .alias("dome"),
        pl.when(~pl.col("roof").is_in(["retractable", "dome", "closed"]))
        .then(pl.lit(1.0))
        .otherwise(pl.lit(0.0))
        .alias("outdoors"),
    )

    # era buckets from season
    era_exprs = [
        pl.when((pl.col("season") >= lo) & (pl.col("season") < hi))
        .then(pl.lit(1.0))
        .otherwise(pl.lit(0.0))
        .alias(name)
        for lo, hi, name in _ERA_BOUNDS
    ]
    df = df.with_columns(era_exprs)

    # down one-hot
    df = df.with_columns(
        (pl.col("down") == 1).cast(pl.Float64).alias("down1"),
        (pl.col("down") == 2).cast(pl.Float64).alias("down2"),
        (pl.col("down") == 3).cast(pl.Float64).alias("down3"),
        (pl.col("down") == 4).cast(pl.Float64).alias("down4"),
    )

    return df


def _add_wp_aux(df: pl.DataFrame) -> pl.DataFrame:
    """Add WP-specific derived columns: elapsed_share, spread_time, Diff_Time_Ratio."""
    df = df.with_columns(
        ((3600.0 - pl.col("game_seconds_remaining")) / 3600.0).alias("elapsed_share")
    )
    # posteam_spread: if home, use spread_line (negative = favoured); if away, negate
    df = df.with_columns(
        pl.when(pl.col("home") == 1.0)
        .then(pl.col("spread_line"))
        .otherwise(-pl.col("spread_line"))
        .alias("posteam_spread")
    )
    # spread_time = posteam_spread * exp(-4 * elapsed_share)
    df = df.with_columns(
        (pl.col("posteam_spread") * (pl.col("elapsed_share") * -4.0).exp()).alias("spread_time")
    )
    # Diff_Time_Ratio = score_differential / exp(-4 * elapsed_share)
    df = df.with_columns(
        (pl.col("score_differential") / (pl.col("elapsed_share") * -4.0).exp()).alias("Diff_Time_Ratio")
    )
    return df


def _add_receive_2h_ko(df: pl.DataFrame) -> pl.DataFrame:
    """Add receive_2h_ko: 1 when posteam received the second-half kickoff.

    Logic mirrors nflfastR:
        grouped by game_id, find the first non-null defteam across all plays
        (this is the team that was defending on the opening play of the game —
        i.e. the team that kicked off → so they RECEIVE in the second half).
        receive_2h_ko = 1 iff (qtr <= 2) AND (posteam == first_defteam_in_game)
    """
    first_defteam = (
        df.filter(pl.col("defteam").is_not_null())
        .group_by("game_id")
        .agg(pl.col("defteam").first().alias("first_defteam"))
    )
    df = df.join(first_defteam, on="game_id", how="left")
    df = df.with_columns(
        pl.when((pl.col("qtr") <= 2) & (pl.col("posteam") == pl.col("first_defteam")))
        .then(pl.lit(1.0))
        .otherwise(pl.lit(0.0))
        .alias("receive_2h_ko")
    ).drop("first_defteam")
    return df


def prepare_ep_data(df: pl.DataFrame) -> pl.DataFrame:
    """Select and order columns for EP model inference / training.

    Args:
        df: DataFrame that has already been passed through ``make_model_mutations()``.

    Returns:
        DataFrame with exactly ``EP_FEATURES`` columns in canonical order.
    """
    return df.select(EP_FEATURES)


def prepare_wp_data(df: pl.DataFrame, *, variant: str = "spread") -> pl.DataFrame:
    """Select and order columns for WP model inference / training.

    Args:
        df: DataFrame that has already been passed through ``make_model_mutations()``.
        variant: ``"spread"`` (default) or ``"naive"``.

    Returns:
        DataFrame with exactly ``WP_SPREAD_FEATURES`` or ``WP_NAIVE_FEATURES`` columns.
        Plays with ``qtr > 4`` (overtime) are dropped — WP models are trained on
        regulation only.
    """
    df = df.filter(pl.col("qtr") <= 4)
    df = _add_wp_aux(df)
    df = _add_receive_2h_ko(df)
    feats = WP_SPREAD_FEATURES if variant == "spread" else WP_NAIVE_FEATURES
    return df.select(feats)


def prepare_cp_data(df: pl.DataFrame) -> pl.DataFrame:
    """Prepare CP model features + valid_pass flag.

    Args:
        df: DataFrame that has already been passed through ``make_model_mutations()``.

    Returns:
        DataFrame with ``CP_FEATURES`` columns + ``valid_pass`` (0.0 / 1.0).
        Callers should filter ``valid_pass == 1`` before training / inference.
    """
    df = df.with_columns(
        (pl.col("air_yards") == 0.0).cast(pl.Float64).alias("air_is_zero"),
        (pl.col("pass_location") == "middle").cast(pl.Float64).alias("pass_middle"),
        (pl.col("air_yards") - pl.col("ydstogo")).alias("distance_to_sticks"),
    )
    # valid_pass: complete|incomplete|interception AND air_yards in [-15, 70) AND has receiver + location
    df = df.with_columns(
        pl.when(
            ((pl.col("complete_pass") == 1) | (pl.col("incomplete_pass") == 1) | (pl.col("interception") == 1))
            & pl.col("air_yards").is_not_null()
            & (pl.col("air_yards") >= -15.0)
            & (pl.col("air_yards") < 70.0)
            & (pl.col("receiver_player_id").is_not_null() | pl.col("receiver_player_name").is_not_null())
            & pl.col("pass_location").is_not_null()
        )
        .then(pl.lit(1.0))
        .otherwise(pl.lit(0.0))
        .alias("valid_pass")
    )
    # Keep complete_pass (the CP label) when present so build_cp_training_set can
    # select it; absent at inference time, where only the features are needed.
    keep = [*CP_FEATURES, "valid_pass"]
    if "complete_pass" in df.columns:
        keep.append("complete_pass")
    return df.select(keep)


def label_next_score_half(df: pl.DataFrame) -> pl.DataFrame:
    """Pass through or validate a DataFrame that already has next_score_class column.

    During training, ``next_score_class`` (0–6) is computed from the nflverse PBP
    ``next_score_half`` / ``result`` columns by the ingest phase. This function is
    a thin validator that coerces the column to Int32 and confirms range.

    Args:
        df: DataFrame with a ``next_score_class`` column (0–6 integer or float).

    Returns:
        DataFrame with ``next_score_class`` as Int32, values clipped to [0, 6].
    """
    return df.with_columns(
        pl.col("next_score_class").cast(pl.Int32).clip(0, 6)
    )
