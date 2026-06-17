"""Training label computation for NFL EP/WP models.

EP label: ``Next_Score_Half`` — what is the next score in the same game half,
from the perspective of the current possession team (7-class).

WP label: ``Winner`` — did the possession team win the game (binary).

Both are computed from nflverse PBP columns; no external .rds files required.
"""
from __future__ import annotations

from typing import Literal, Optional

import polars as pl

from .constants import CP_FEATURES, EP_CLASS_ORDER, EP_FEATURES, WP_NAIVE_FEATURES, WP_SPREAD_FEATURES
from .features import make_model_mutations, prepare_cp_data, prepare_ep_data, prepare_wp_data

# ---------------------------------------------------------------------------
# Class index mapping (Touchdown=0 … No_Score=6)
# ---------------------------------------------------------------------------

SCORE_LABEL_TO_CLASS: dict[str, int] = {label: i for i, label in enumerate(EP_CLASS_ORDER)}


# ---------------------------------------------------------------------------
# EP label: Next_Score_Half
# ---------------------------------------------------------------------------

def _score_type_and_team(sp: int, touchdown: int, td_team: Optional[str],
                          field_goal_result: Optional[str], safety: int,
                          posteam: str, defteam: str) -> tuple[str | None, str | None]:
    """Return (score_label, scoring_team) for a scoring play, or (None, None)."""
    if not sp:
        return None, None
    if touchdown and td_team:
        label = "Touchdown" if td_team == posteam else "Opp_Touchdown"
        return label, td_team
    if field_goal_result == "made":
        return "Field_Goal", posteam
    if safety:
        # Safety: posteam conceded it → defteam scored → Opp_Safety from posteam view
        return "Opp_Safety", defteam
    return None, None


def compute_next_score_half(df: pl.DataFrame) -> pl.DataFrame:
    """Add ``next_score_half`` and ``next_score_class`` columns.

    For each play, determines the next scoring event in the same (game_id, game_half),
    expressed relative to the CURRENT play's possession team (posteam).

    Args:
        df: nflverse PBP DataFrame (raw or partially processed).

    Returns:
        Input DataFrame with two additional columns:
            - ``next_score_half`` (Utf8): score label string (one of 7 classes).
            - ``next_score_class`` (Int32): integer class index 0–6.
    """
    # 1. On each scoring play, record the ABSOLUTE score type + scoring team. Perspective
    #    is applied later, relative to each play's OWN posteam. (The previous version baked
    #    the scoring play's perspective into the label and propagated it unchanged, which
    #    flipped the sign on every possession-change play and never produced Opp_Field_Goal
    #    or Safety. See the row-wise spec in _score_type_and_team.)
    df = df.with_columns([
        pl.when((pl.col("sp") == 1) & (pl.col("touchdown") == 1) & pl.col("td_team").is_not_null())
        .then(pl.lit("TD"))
        .when((pl.col("sp") == 1) & (pl.col("field_goal_result") == "made"))
        .then(pl.lit("FG"))
        .when((pl.col("sp") == 1) & (pl.col("safety") == 1))
        .then(pl.lit("Safety"))
        .otherwise(pl.lit(None).cast(pl.Utf8))
        .alias("_score_type"),
        pl.when((pl.col("sp") == 1) & (pl.col("touchdown") == 1) & pl.col("td_team").is_not_null())
        .then(pl.col("td_team"))                       # TD: the team that scored (offense or defense)
        .when((pl.col("sp") == 1) & (pl.col("field_goal_result") == "made"))
        .then(pl.col("posteam"))                       # made FG: kicked by the possession team
        .when((pl.col("sp") == 1) & (pl.col("safety") == 1))
        .then(pl.col("defteam"))                       # safety: scored by the defense (posteam conceded)
        .otherwise(pl.lit(None).cast(pl.Utf8))
        .alias("_score_team"),
    ])

    # 2. Within each (game_id, game_half), propagate the NEXT scoring play's type + team to
    #    all earlier plays: sort DESCENDING by play_id, then forward_fill (which now walks
    #    earliest-last, so each play inherits the nearest *future* score). The scoring play
    #    keeps its own score.
    df = df.sort(["game_id", "game_half", "play_id"], descending=[False, False, True])
    df = df.with_columns([
        pl.col("_score_type").forward_fill().over(["game_id", "game_half"]).alias("_next_type"),
        pl.col("_score_team").forward_fill().over(["game_id", "game_half"]).alias("_next_team"),
    ])
    df = df.sort(["game_id", "game_half", "play_id"], descending=[False, False, False])

    # 3. Express the next score RELATIVE to each play's own posteam: same team -> the positive
    #    class, opponent -> the Opp_ class. No further score in the half -> No_Score.
    same = pl.col("_next_team") == pl.col("posteam")
    df = df.with_columns(
        pl.when(pl.col("_next_type").is_null()).then(pl.lit("No_Score"))
        .when(pl.col("_next_type") == "TD")
        .then(pl.when(same).then(pl.lit("Touchdown")).otherwise(pl.lit("Opp_Touchdown")))
        .when(pl.col("_next_type") == "FG")
        .then(pl.when(same).then(pl.lit("Field_Goal")).otherwise(pl.lit("Opp_Field_Goal")))
        .when(pl.col("_next_type") == "Safety")
        .then(pl.when(same).then(pl.lit("Safety")).otherwise(pl.lit("Opp_Safety")))
        .otherwise(pl.lit("No_Score"))
        .alias("next_score_half")
    )

    # 4. Map to the integer class index.
    no_score_class = SCORE_LABEL_TO_CLASS["No_Score"]
    df = df.with_columns(
        pl.col("next_score_half")
        .replace_strict(SCORE_LABEL_TO_CLASS, return_dtype=pl.Int32, default=no_score_class)
        .alias("next_score_class")
    )

    return df.drop(["_score_type", "_score_team", "_next_type", "_next_team"])


# ---------------------------------------------------------------------------
# WP label: Winner
# ---------------------------------------------------------------------------

def compute_winner(df: pl.DataFrame) -> pl.DataFrame:
    """Add ``winner`` (team abbreviation or null for tie) and ``wp_label`` (0/1/null) columns.

    ``wp_label = 1.0`` when ``posteam == winner``; ``0.0`` when ``defteam == winner``;
    ``null`` for tied games (excluded from WP training per nflfastR convention).

    Args:
        df: nflverse PBP DataFrame containing ``home_score``, ``away_score``,
            ``home_team``, and ``posteam``.

    Returns:
        Input DataFrame with ``winner`` and ``wp_label`` columns added.
    """
    # Compute winner per game_id (home wins if home_score > away_score)
    game_results = (
        df.group_by("game_id")
        .agg([
            pl.col("home_score").last(),
            pl.col("away_score").last(),
            pl.col("home_team").first(),
            # away_team = defteam when posteam==home_team, but easier to derive
        ])
        .with_columns(
            pl.when(pl.col("home_score") > pl.col("away_score"))
            .then(pl.col("home_team"))
            .when(pl.col("away_score") > pl.col("home_score"))
            .then(pl.lit(None).cast(pl.Utf8))  # we'll fix away_team below
            .otherwise(pl.lit(None).cast(pl.Utf8))  # tie
            .alias("winner_home_or_tie"),
            (pl.col("home_score") > pl.col("away_score")).alias("home_wins"),
            (pl.col("away_score") > pl.col("home_score")).alias("away_wins"),
        )
    )

    # To identify the away winner we need the away team. Derive from PBP:
    # away_team = first posteam where posteam != home_team
    away_team_map = (
        df.filter(pl.col("posteam") != pl.col("home_team"))
        .group_by("game_id")
        .agg(pl.col("posteam").first().alias("away_team"))
    )

    game_results = game_results.join(away_team_map, on="game_id", how="left")
    game_results = game_results.with_columns(
        pl.when(pl.col("home_wins"))
        .then(pl.col("home_team"))
        .when(pl.col("away_wins"))
        .then(pl.col("away_team"))
        .otherwise(pl.lit(None).cast(pl.Utf8))
        .alias("winner")
    ).select(["game_id", "winner"])

    # Join winner back onto play-level frame
    df = df.join(game_results, on="game_id", how="left")

    # wp_label: 1.0 if posteam won, 0.0 if posteam lost, null if tie
    df = df.with_columns(
        pl.when(pl.col("winner").is_null())
        .then(pl.lit(None).cast(pl.Float64))
        .when(pl.col("posteam") == pl.col("winner"))
        .then(pl.lit(1.0))
        .otherwise(pl.lit(0.0))
        .alias("wp_label")
    )

    return df


# ---------------------------------------------------------------------------
# Convenience builders
# ---------------------------------------------------------------------------

def build_ep_training_set(df: pl.DataFrame) -> pl.DataFrame:
    """Full EP training set pipeline from raw nflverse PBP.

    1. Compute ``Next_Score_Half`` label.
    2. Apply ``make_model_mutations()`` (era/roof/down one-hots, home indicator).
    3. Select ``EP_FEATURES + next_score_class``.

    Args:
        df: Raw nflverse PBP frame (multiple seasons).

    Returns:
        Training-ready DataFrame with EP_FEATURES columns + ``next_score_class``.
    """
    df = compute_next_score_half(df)
    df = make_model_mutations(df)
    return df.select([*EP_FEATURES, "next_score_class"])


def build_wp_training_set(
    df: pl.DataFrame,
    *,
    variant: Literal["spread", "naive"] = "spread",
) -> pl.DataFrame:
    """Full WP training set pipeline from raw nflverse PBP.

    1. Compute ``Winner`` label + ``wp_label``.
    2. Apply ``make_model_mutations()``.
    3. Inline WP feature engineering (spread_time, Diff_Time_Ratio, receive_2h_ko).
    4. Filter regulation plays (qtr <= 4) and drop tied games (``wp_label`` null).

    Args:
        df: Raw nflverse PBP frame.
        variant: ``"spread"`` or ``"naive"``.

    Returns:
        Training-ready DataFrame with WP feature columns + ``label`` (0.0/1.0).
    """
    from .features import _add_wp_aux, _add_receive_2h_ko

    df = compute_winner(df)
    df = make_model_mutations(df)
    df = df.filter(pl.col("qtr") <= 4)
    df = _add_wp_aux(df)
    df = _add_receive_2h_ko(df)
    # Drop tied games (wp_label null) before selecting final columns
    df = df.filter(pl.col("wp_label").is_not_null())
    feats = WP_SPREAD_FEATURES if variant == "spread" else WP_NAIVE_FEATURES
    return df.select([*feats, pl.col("wp_label").alias("label")])


def build_cp_training_set(df: pl.DataFrame) -> pl.DataFrame:
    """Full CP training set pipeline from raw nflverse PBP.

    1. Apply ``make_model_mutations()`` (era/roof/down one-hots, home indicator).
    2. Apply ``prepare_cp_data()`` (air_is_zero, pass_middle, distance_to_sticks, valid_pass).
    3. Filter to valid passes only (``valid_pass == 1``).
    4. Select ``CP_FEATURES + complete_pass``.

    Args:
        df: Raw nflverse PBP frame containing pass play columns.

    Returns:
        Training-ready DataFrame with ``CP_FEATURES`` columns + ``complete_pass`` label.
    """
    df = make_model_mutations(df)
    df = prepare_cp_data(df)
    df = df.filter(pl.col("valid_pass") == 1.0)
    return df.select([*CP_FEATURES, "complete_pass"])
