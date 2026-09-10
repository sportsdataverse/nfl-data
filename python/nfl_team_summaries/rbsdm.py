"""The rbsdm.com team and QB measures the college grid does not carry.

Every column here is ranked with ``_rank`` like the rest of the grid so the
site's leaderboard machinery renders it unchanged. Directions:

* pass rate / xpass / pass-over-expected / neutral pass rate: ranked
  high-first -- there is no "good" direction, rank 1 is simply the most
  pass-happy offense;
* fourth-down go rate, go-over-expected and boost: high-first (aggressive =
  rank 1);
* luck: a team's own fumble recovery share and the share of opponent fumbles it
  recovered rank high-first; opponents' field-goal percentage ranks LOW-first
  (opponents missing is the lucky outcome).

* series conversion rate (rbsdm "Series Conv %"): the offense's share of
  series ending in a first down or touchdown ranks high-first; the defense's
  (series allowed) ranks LOW-first. Computed by sdv-py's port of nflfastR's
  ``calculate_series_conversion_rates`` from the ``series`` / ``series_success``
  / ``series_result`` columns ``nfl_model_pbp`` carries since the native_pbp
  parity build; an older asset without them gets the columns as nulls so the
  table schema never depends on the asset vintage.
"""

from __future__ import annotations

import polars as pl
from sportsdataverse.nfl import calculate_nfl_series_conversion_rates

from .crosswalk import attach_team_ids

#: rbsdm "neutral": early downs, competitive win probability, outside the
#: two-minute drill, before the fourth quarter
_NEUTRAL = (
    (pl.col("down") <= 2)
    & (pl.col("wp_before") >= 0.2)
    & (pl.col("wp_before") <= 0.8)
    & (pl.col("half_seconds_remaining") > 120)
    & (pl.col("qtr") <= 3)
)


def _rank(col: str, *, descending: bool) -> pl.Expr:
    c = pl.col(col)
    base = c.rank(method="average", descending=descending)
    n_nonnull = c.is_not_null().sum()
    # a column with no values at all (an older asset without the source
    # columns) ranks nobody: sequential ranks over nulls would look like data
    null_trail = (n_nonnull + c.is_null().cum_sum()).cast(pl.Float64)
    ranked = pl.when(c.is_null()).then(null_trail).otherwise(base)
    return pl.when(n_nonnull == 0).then(pl.lit(None, dtype=pl.Float64)).otherwise(ranked)


def _pass_tendencies(plays: pl.DataFrame) -> pl.DataFrame:
    """pass rate, expected pass rate and pass-over-expected, overall and in neutral situations."""
    has_x = plays.filter(pl.col("xpass").is_not_null())
    return has_x.group_by("pos_team_id").agg(
        pass_rate_off=pl.col("pass").mean(),
        xpass_rate_off=pl.col("xpass").mean(),
        # nflfastR pass_oe is in percentage points; the site shows both scales
        pass_oe_off=pl.col("pass_oe").mean(),
        neutral_pass_rate_off=pl.col("pass").filter(_NEUTRAL).mean(),
        neutral_xpass_rate_off=pl.col("xpass").filter(_NEUTRAL).mean(),
        neutral_pass_oe_off=pl.col("pass_oe").filter(_NEUTRAL).mean(),
    )


def _fourth_downs(raw: pl.DataFrame) -> pl.DataFrame:
    """Fourth-down decisions against sdv-py's recommendation (``fourth_down_recommendation`` / ``go_boost``).

    A decision is any fourth-down snap that resolved as a pass, run, punt or field
    goal (no penalties-only plays, no kneels). "Went for it" is a pass or a run.
    """
    d = raw.filter(
        (pl.col("down") == 4)
        & pl.col("play_type").is_in(["pass", "run", "punt", "field_goal"])
        & pl.col("fourth_down_recommendation").is_not_null()
        & pl.col("posteam").is_not_null()
    ).with_columns(
        went_for_it=pl.col("play_type").is_in(["pass", "run"]).cast(pl.Float64),
        rec_go=(pl.col("fourth_down_recommendation") == "go").cast(pl.Float64),
    )
    d = attach_team_ids(d, "posteam", "pos_team")
    return (
        d.group_by("pos_team_id")
        .agg(
            fourth_decisions_off=pl.len(),
            fourth_go_rate_off=pl.col("went_for_it").mean(),
            fourth_go_expected_off=pl.col("rec_go").mean(),
            # mean go_boost (WP gained by going, in points) across the decisions the
            # model says to go on: positive when a team takes its good go chances
            fourth_go_boost_off=pl.col("go_boost").filter(pl.col("rec_go") == 1).mean(),
            # share of model-recommended go spots the team actually went on
            fourth_go_when_recommended_off=pl.col("went_for_it")
            .filter(pl.col("rec_go") == 1)
            .mean(),
        )
        .with_columns(
            fourth_go_over_expected_off=pl.col("fourth_go_rate_off")
            - pl.col("fourth_go_expected_off")
        )
    )


def _luck(raw: pl.DataFrame) -> pl.DataFrame:
    fum = raw.filter((pl.col("fumble").fill_null(0) == 1) & pl.col("posteam").is_not_null())
    fum = attach_team_ids(fum, "posteam", "pos_team")
    fum = attach_team_ids(fum, "defteam", "def_pos_team")
    own = fum.group_by("pos_team_id").agg(
        fumbles_off=pl.len(),
        luck_fumble_rec_pct_off=1 - pl.col("fumble_lost").fill_null(0).cast(pl.Float64).mean(),
    )
    opp = (
        fum.group_by("def_pos_team_id")
        .agg(
            fumbles_forced_def=pl.len(),
            luck_fumble_rec_pct_def=pl.col("fumble_lost").fill_null(0).cast(pl.Float64).mean(),
        )
        .rename({"def_pos_team_id": "pos_team_id"})
    )
    fg = raw.filter(
        (pl.col("field_goal_attempt").fill_null(0) == 1) & pl.col("defteam").is_not_null()
    )
    fg = attach_team_ids(fg, "defteam", "def_pos_team")
    opp_fg = (
        fg.group_by("def_pos_team_id")
        .agg(
            opp_fg_att_def=pl.len(),
            luck_opp_fg_pct_def=(pl.col("field_goal_result") == "made").cast(pl.Float64).mean(),
        )
        .rename({"def_pos_team_id": "pos_team_id"})
    )
    return own.join(opp, on="pos_team_id", how="full", coalesce=True).join(
        opp_fg, on="pos_team_id", how="full", coalesce=True
    )


_SERIES_INPUT = ("season", "week", "posteam", "defteam", "down", "series", "series_success", "series_result")


def _series(raw: pl.DataFrame) -> pl.DataFrame:
    """Offense / defense series conversion rate (nflfastR ``off_scr`` / ``def_scr``)."""
    if any(c not in raw.columns for c in _SERIES_INPUT):
        return pl.DataFrame(
            schema={"pos_team_id": pl.Utf8, "series_conv_off": pl.Float64, "series_conv_def": pl.Float64}
        )
    rates = calculate_nfl_series_conversion_rates(
        raw.filter(pl.col("posteam").is_not_null()).select(_SERIES_INPUT)
    )
    return attach_team_ids(rates, "team", "pos_team").select(
        pl.col("pos_team_id"),
        pl.col("off_scr").alias("series_conv_off"),
        pl.col("def_scr").alias("series_conv_def"),
    )


#: column -> ranked high-first?
_RANKED = {
    "pass_rate_off": True,
    "xpass_rate_off": True,
    "pass_oe_off": True,
    "neutral_pass_rate_off": True,
    "neutral_xpass_rate_off": True,
    "neutral_pass_oe_off": True,
    # the decision count ranks by volume: the site asks for a _rank beside every
    # column of a category (it had no rank -> "unknown select column" -> 400)
    "fourth_decisions_off": True,
    "fourth_go_rate_off": True,
    "fourth_go_expected_off": True,
    "fourth_go_over_expected_off": True,
    "fourth_go_boost_off": True,
    "fourth_go_when_recommended_off": True,
    "luck_fumble_rec_pct_off": True,
    "luck_fumble_rec_pct_def": True,
    "luck_opp_fg_pct_def": False,
    "series_conv_off": True,
    "series_conv_def": False,
}


def team_extras(raw: pl.DataFrame, plays: pl.DataFrame) -> pl.DataFrame:
    """One row per ``team_id`` (ESPN id, Utf8) with the rbsdm columns and their ranks."""
    out = (
        _pass_tendencies(plays)
        .join(_fourth_downs(raw), on="pos_team_id", how="full", coalesce=True)
        .join(_luck(raw), on="pos_team_id", how="full", coalesce=True)
        .join(_series(raw), on="pos_team_id", how="full", coalesce=True)
        .sort("pos_team_id")
    )
    out = out.with_columns(
        [
            _rank(c, descending=desc).alias(f"{c}_rank")
            for c, desc in _RANKED.items()
            if c in out.columns
        ]
    )
    return out.rename({"pos_team_id": "team_id"})


def passer_extras(qb: pl.DataFrame, team_off: pl.DataFrame, *, min_expr: pl.Expr) -> pl.DataFrame:
    """CPOE, EPA per dropback from ``qb_epa``, and rbsdm's EPA+CPOE composite.

    The composite is the mean of the two z-scores AMONG QUALIFIERS (rbsdm's
    "EPA + CPOE composite"), so it is null for a passer below the gate.
    """
    keys = ["pos_team_id", "passer_player_id"]
    extra = (
        team_off.filter((pl.col("pass") == 1) & pl.col("passer_player_id").is_not_null())
        .group_by(keys)
        .agg(
            cpoe=pl.col("cpoe").mean(),
            qb_epa_play=pl.col("qb_epa").mean()
            if "qb_epa" in team_off.columns
            else pl.col("EPA").mean(),
        )
    )
    qb = qb.join(extra, on=keys, how="left")
    qual = qb.filter(min_expr & pl.col("cpoe").is_not_null() & pl.col("EPAplay").is_not_null())
    if qual.height >= 2:
        z = qual.select(
            *keys,
            epa_cpoe_composite=(
                0.5 * (pl.col("EPAplay") - pl.col("EPAplay").mean()) / pl.col("EPAplay").std()
                + 0.5 * (pl.col("cpoe") - pl.col("cpoe").mean()) / pl.col("cpoe").std()
            ),
        )
        qb = qb.join(z, on=keys, how="left")
    else:
        qb = qb.with_columns(epa_cpoe_composite=pl.lit(None, dtype=pl.Float64))
    return qb
