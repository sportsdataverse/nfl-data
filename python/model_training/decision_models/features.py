"""Feature engineering for the NFL model suite (decision_models).

Reuses play_level's :func:`make_model_mutations` (era buckets, roof one-hots, home,
down dummies) and adds the per-model filters / labels / spread-total features
that the nfl4th + nflverse-pbp R training scripts apply.

All functions accept and return polars DataFrames.
"""

from __future__ import annotations

import polars as pl

# Reuse the canonical mutation engine from play_level — DO NOT re-implement.
from model_training.play_level.features import make_model_mutations

from .constants import (
    XPASS_FEATURES,
    FD_FEATURES,
    TWO_PT_FEATURES,
    FG_FEATURES,
    WP_FEATURES,
)

__all__ = [
    "make_model_mutations",
    "add_spread_total_features",
    "prepare_xpass_data",
    "prepare_fd_data",
    "prepare_two_pt_data",
    "prepare_fg_data",
    "prepare_wp_data",
]


def add_spread_total_features(df: pl.DataFrame) -> pl.DataFrame:
    """Add posteam-perspective spread/total features used by fd + two_pt.

    Mirrors the R mutate block::

        home_total    = (spread_line + total_line) / 2
        away_total    = (total_line  - spread_line) / 2
        posteam_total = if home posteam then home_total else away_total
        posteam_spread = if home posteam then spread_line else -spread_line

    Requires ``home`` (from :func:`make_model_mutations`), ``spread_line``,
    ``total_line``.
    """
    return df.with_columns(
        ((pl.col("spread_line") + pl.col("total_line")) / 2.0).alias("home_total"),
        ((pl.col("total_line") - pl.col("spread_line")) / 2.0).alias("away_total"),
    ).with_columns(
        pl.when(pl.col("home") == 1.0)
        .then(pl.col("home_total"))
        .otherwise(pl.col("away_total"))
        .alias("posteam_total"),
        pl.when(pl.col("home") == 1.0)
        .then(pl.col("spread_line"))
        .otherwise(-1.0 * pl.col("spread_line"))
        .alias("posteam_spread"),
    )


# ---------------------------------------------------------------------------
# xpass
# ---------------------------------------------------------------------------
def prepare_xpass_data(df: pl.DataFrame) -> pl.DataFrame:
    """Build the xpass (dropback) training frame.

    Filter (train_dropback_model.R / _dropback_model_data.R): scrimmage plays
    (``rush==1 | pass==1``) with a valid down + non-null posteam / timeouts /
    yardline / score_differential, no kneels / aborted plays, week <= 17. The
    label is ``pass``.

    Args:
        df: Raw nflverse PBP (already passed through ``make_model_mutations``).

    Returns:
        Frame with ``XPASS_FEATURES`` columns + ``label`` (0/1).
    """
    out = df.filter(
        ((pl.col("rush") == 1) | (pl.col("pass") == 1))
        & (pl.col("qb_kneel") == 0)
        & pl.col("posteam").is_not_null()
        & pl.col("down").is_not_null()
        & pl.col("defteam_timeouts_remaining").is_not_null()
        & pl.col("posteam_timeouts_remaining").is_not_null()
        & pl.col("yardline_100").is_not_null()
        & pl.col("score_differential").is_not_null()
    )
    if "aborted_play" in out.columns:
        out = out.filter(pl.col("aborted_play").fill_null(0) == 0)
    if "week" in out.columns:
        out = out.filter(pl.col("week") <= 17)
    out = out.with_columns(pl.col("pass").cast(pl.Int32).alias("label"))
    return out.select([*XPASS_FEATURES, "label"])


# ---------------------------------------------------------------------------
# fd_model (go-for-it gain distribution)
# ---------------------------------------------------------------------------
def prepare_fd_data(df: pl.DataFrame) -> pl.DataFrame:
    """Build the fd (go-for-it yards-gained) training frame.

    Filter (_go_for_it_and_2pt_models.R): ``down in {3,4}``, no kneels,
    ``rush==1 | pass==1``, non-null posteam / yardline / score_differential,
    week <= 17, then ``play_type_nfl in {RUSH,PASS,SACK} | first_down_penalty==1``.

    Label: ``yards_gained`` with defensive-first-down-penalty recoding, clamped
    to [-10, 65], then shifted by +10 → class index 0..75.

    Args:
        df: Raw nflverse PBP (already passed through ``make_model_mutations``).

    Returns:
        Frame with ``FD_FEATURES`` columns + ``label`` (Int32, 0..75).
    """
    out = df.filter(
        pl.col("down").is_in([3, 4])
        & (pl.col("qb_kneel") == 0)
        & ((pl.col("rush") == 1) | (pl.col("pass") == 1))
        & pl.col("posteam").is_not_null()
        & pl.col("yardline_100").is_not_null()
        & pl.col("score_differential").is_not_null()
        & (pl.col("week") <= 17)
    )
    out = add_spread_total_features(out)

    fdp = pl.col("first_down_penalty").fill_null(0)
    pen_yards = pl.col("penalty_yards").fill_null(0)
    ytg = pl.col("ydstogo")
    # defensive first-down-penalty recode then truncate to [-10, 65]
    yards = (
        pl.when((fdp == 1) & (pen_yards < ytg))
        .then(ytg)
        .when((fdp == 1) & (pen_yards >= ytg))
        .then(pen_yards)
        .otherwise(pl.col("yards_gained"))
    )
    yards = pl.when(yards < -10).then(pl.lit(-10)).otherwise(yards)
    yards = pl.when(yards > 65).then(pl.lit(65)).otherwise(yards)
    out = out.with_columns(yards.alias("_yards_gained"))

    out = out.filter(
        pl.col("play_type_nfl").is_in(["RUSH", "PASS", "SACK"]) | (pl.col("first_down_penalty").fill_null(0) == 1)
    )
    out = out.with_columns((pl.col("_yards_gained") + 10).cast(pl.Int32).alias("label"))
    return out.select([*FD_FEATURES, "label"])


# ---------------------------------------------------------------------------
# two_pt_model
# ---------------------------------------------------------------------------
def prepare_two_pt_data(df: pl.DataFrame) -> pl.DataFrame:
    """Build the 2-pt conversion training frame.

    Filter (_go_for_it_and_2pt_models.R): ``is.na(down)``,
    ``two_point_conv_result`` not-null, ``yardline_100 == 2``,
    ``rush==1 | pass==1``, non-null posteam / yardline / score_differential,
    week <= 17. Label = ``two_point_conv_result == "success"``.

    Args:
        df: Raw nflverse PBP (already passed through ``make_model_mutations``).

    Returns:
        Frame with ``TWO_PT_FEATURES`` columns + ``label`` (0/1).
    """
    out = df.filter(
        pl.col("down").is_null()
        & pl.col("two_point_conv_result").is_not_null()
        & (pl.col("yardline_100") == 2)
        & ((pl.col("rush") == 1) | (pl.col("pass") == 1))
        & pl.col("posteam").is_not_null()
        & pl.col("score_differential").is_not_null()
        & (pl.col("week") <= 17)
    )
    out = add_spread_total_features(out)
    out = out.with_columns((pl.col("two_point_conv_result") == "success").cast(pl.Int32).alias("label"))
    return out.select([*TWO_PT_FEATURES, "label"])


# ---------------------------------------------------------------------------
# fg_model (re-trained as XGBoost)
# ---------------------------------------------------------------------------
def prepare_fg_data(df: pl.DataFrame) -> pl.DataFrame:
    """Build the field-goal make-probability training frame.

    Filter (_punt_and_fg_models.R): ``play_type_nfl == "FIELD_GOAL"``.
    Features: ``yardline_100`` + ``fg_roof`` (roof == "outdoors") +
    ``fg_era`` (season >= 2020). Label = ``sp`` (field goal made), falling back
    to ``field_goal_result == "made"`` when ``sp`` is absent / null.

    Args:
        df: Raw nflverse PBP (no mutation prerequisite — fg uses its own roof/era).

    Returns:
        Frame with ``FG_FEATURES`` columns + ``label`` (0/1).
    """
    out = df.filter(pl.col("play_type_nfl") == "FIELD_GOAL")
    # era0..era4 come from make_model_mutations (applied upstream); fg builds only
    # its own roof flag. The binary fg_era is retired in favour of the full era
    # one-hot so the make-prob curve is era-aware across all kicking eras.
    out = out.with_columns(
        (pl.col("roof") == "outdoors").cast(pl.Int32).alias("fg_roof"),
    )
    # label: prefer sp, else field_goal_result == "made"
    if "sp" in out.columns:
        label = pl.when(pl.col("sp").is_not_null()).then(pl.col("sp"))
        if "field_goal_result" in out.columns:
            label = label.otherwise((pl.col("field_goal_result") == "made").cast(pl.Int32))
        else:
            label = label.otherwise(pl.lit(0))
    else:
        label = (pl.col("field_goal_result") == "made").cast(pl.Int32)
    out = out.with_columns(label.cast(pl.Int32).alias("label"))
    out = out.filter(pl.col("label").is_not_null())
    return out.select([*FG_FEATURES, "label"])


# ---------------------------------------------------------------------------
# wp_model (home-perspective win probability — the nfl4th wp_model contract)
# ---------------------------------------------------------------------------
def prepare_wp_data(df: pl.DataFrame) -> pl.DataFrame:
    """Build the wp (home-perspective win-probability) training frame.

    Faithful port of ``nfl4th`` ``R/apply_win_prob.R`` (the recipe that produces
    the converted ``wp_model.ubj`` oracle). Filters ties + nulls, applies the
    home-perspective feature transforms, and labels by ``home_team == Winner``::

        filter(Winner != "TIE", qtr <= 4, !is.na(ep/score_differential/
               play_type/yardline_100))
        home_score_differential = posteam==home ? score_differential : -score_differential
        home_yardline_100       = posteam==home ? yardline_100       : 100 - yardline_100
        home_ep                 = posteam==home ? ep                 : -ep
        home_posteam            = (home_team == posteam)
        spread_time             = spread_line * exp(-4 * elapsed_share)
        Diff_Time_Ratio         = home_score_differential / exp(-4 * elapsed_share)
        home_receive_2h_ko      = qtr<=2 & home opened with a kickoff (first defteam)
        home_timeouts_remaining = posteam==home ? posteam_timeouts : defteam_timeouts
        label                   = (home_team == Winner)

    Output features are the 11 ``WP_FEATURES`` in the oracle's
    ``as.matrix(wp_model_select(...))`` column order.

    Args:
        df: ``cal_data.rds`` rows. Must carry ``Winner``, ``ep``, ``play_type``,
            ``game_id``, ``defteam``, ``home_team``, ``posteam``, ``spread_line``.

    Returns:
        Frame with ``WP_FEATURES`` columns + ``label`` (0/1).
    """
    is_home = pl.col("posteam") == pl.col("home_team")
    out = df.filter(
        (pl.col("Winner") != "TIE")
        & (pl.col("qtr") <= 4)
        & pl.col("ep").is_not_null()
        & pl.col("score_differential").is_not_null()
        & pl.col("play_type").is_not_null()
        & pl.col("yardline_100").is_not_null()
    )
    # home-perspective transforms + elapsed_share (matches play_level _add_wp_aux)
    out = out.with_columns(
        is_home.cast(pl.Int32).alias("home_posteam"),
        ((3600.0 - pl.col("game_seconds_remaining")) / 3600.0).alias("elapsed_share"),
        pl.when(is_home)
        .then(pl.col("score_differential"))
        .otherwise(-pl.col("score_differential"))
        .alias("home_score_differential"),
        pl.when(is_home)
        .then(pl.col("yardline_100"))
        .otherwise(100.0 - pl.col("yardline_100"))
        .alias("home_yardline_100"),
        pl.when(is_home).then(pl.col("ep")).otherwise(-pl.col("ep")).alias("home_ep"),
        pl.when(is_home)
        .then(pl.col("posteam_timeouts_remaining"))
        .otherwise(pl.col("defteam_timeouts_remaining"))
        .alias("home_timeouts_remaining"),
    )
    out = out.with_columns(
        # spread_line is already home-perspective in nflfastR (negative = home favored)
        (pl.col("spread_line") * (pl.col("elapsed_share") * -4.0).exp()).alias("spread_time"),
        (pl.col("home_score_differential") / (pl.col("elapsed_share") * -4.0).exp()).alias("Diff_Time_Ratio"),
    )
    # home_receive_2h_ko: home opened the game on defense (i.e. kicked off) -> they
    # receive the 2nd-half kickoff. First non-null defteam in the game == kicking team.
    first_defteam = (
        out.filter(pl.col("defteam").is_not_null())
        .group_by("game_id")
        .agg(pl.col("defteam").first().alias("_first_defteam"))
    )
    out = out.join(first_defteam, on="game_id", how="left")
    out = out.with_columns(
        pl.when((pl.col("qtr") <= 2) & (pl.col("home_team") == pl.col("_first_defteam")))
        .then(pl.lit(1))
        .otherwise(pl.lit(0))
        .alias("home_receive_2h_ko")
    )
    out = out.with_columns((pl.col("home_team") == pl.col("Winner")).cast(pl.Int32).alias("label"))
    return out.select([*WP_FEATURES, "label"])
