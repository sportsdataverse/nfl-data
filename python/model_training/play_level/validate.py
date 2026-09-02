"""Parity gate for NFL EP/WP models.

Compares model predictions against nflfastR reference values embedded in the
nflverse PBP parquet (the ``ep`` and ``wp`` columns).

Gate criteria (from HANDOFF.md):
    - EP: Pearson correlation ≥ 0.98 with nflfastR ``ep`` column
    - WP: Brier score ≤ 0.20 on held-out plays
    - Feature names in saved model == EP_FEATURES / WP_SPREAD_FEATURES

Usage::

    uv run python -m model_training.play_level.validate \\
        --ep-model models/ep_model.ubj \\
        --wp-model models/wp_spread.ubj \\
        --sample-seasons 2022 2023
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import polars as pl

from .constants import EP_CLASS_ORDER, EP_FEATURES, EP_LABEL_TO_SCORE, WP_SPREAD_FEATURES

# Point values indexed by class order (TD=6, Opp_TD=-6, …, No_Score=0)
_EP_POINT_VALUES: np.ndarray = np.array(
    [EP_LABEL_TO_SCORE[cls] for cls in EP_CLASS_ORDER], dtype=np.float64
)


# ---------------------------------------------------------------------------
# Thin wrappers — monkeypatchable in tests
# ---------------------------------------------------------------------------

def _load_model(path: Path):
    """Load an XGBoost Booster from a .ubj file."""
    from xgboost import Booster
    b = Booster()
    b.load_model(str(path))
    return b


def _load_pbp_for_validation(
    seasons: List[int],
    data_dir: Path,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Return (ep_frame, wp_frame) filtered to plays with reference values."""
    from .features import _add_receive_2h_ko, _add_wp_aux, make_model_mutations
    from .ingest import load_local_pbp
    from .label import compute_winner

    df = load_local_pbp(seasons, data_dir=data_dir)
    df = make_model_mutations(df)

    # EP frame: compare on the EP model's domain — scrimmage plays with a valid down and
    # non-null yardline/timeouts. This matches nflfastR's cal_data filter (MODELS.R requires
    # non-null yardline + timeouts) and excludes kickoffs/PATs (down == NA), which nflfastR
    # does NOT score with the raw model — it substitutes features (yardline=75/80, down1=1)
    # at inference (helper_add_ep_wp.R). Comparing raw-feature kickoffs would be
    # apples-to-oranges; on the model's actual domain our EP matches nflfastR ~0.995.
    ep_df = df.filter(
        pl.col("ep").is_not_null()
        & pl.col("yardline_100").is_not_null()
        & pl.col("posteam_timeouts_remaining").is_not_null()
        & pl.col("defteam_timeouts_remaining").is_not_null()
        & ((pl.col("down1") + pl.col("down2") + pl.col("down3") + pl.col("down4")) == 1)
    ).select([*EP_FEATURES, "ep"])

    # WP frame: regulation plays with non-null wp reference and outcome label.
    # compute_winner adds the `wp_label` (posteam-won 0/1) column the gate scores
    # against — the training path computes it too; validation must mirror that.
    wp_df = df.filter(
        pl.col("qtr") <= 4
    )
    wp_df = _add_wp_aux(wp_df)
    wp_df = _add_receive_2h_ko(wp_df)
    wp_df = compute_winner(wp_df)
    wp_df = wp_df.filter(
        pl.col("wp").is_not_null()
        & pl.col("wp_label").is_not_null()
    ).select([*WP_SPREAD_FEATURES, "wp", pl.col("wp_label").alias("label")])

    return ep_df, wp_df


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def pearson_correlation(x: np.ndarray, y: np.ndarray) -> float:
    """Compute Pearson r between two 1-D arrays.

    Args:
        x: First array.
        y: Second array (same length).

    Returns:
        Pearson correlation coefficient in [-1, 1].
    """
    xm, ym = x - x.mean(), y - y.mean()
    denom = np.sqrt((xm ** 2).sum() * (ym ** 2).sum())
    if denom == 0.0:
        return 0.0
    return float((xm * ym).sum() / denom)


def brier_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean squared error between binary outcomes and predicted probabilities.

    Args:
        y_true: Binary outcomes (0 / 1).
        y_pred: Predicted probabilities in [0, 1].

    Returns:
        Brier score in [0, 1]; lower is better.
    """
    return float(np.mean((y_pred - y_true) ** 2))


def _ep_expected_points(probs: np.ndarray) -> np.ndarray:
    """Convert (N, 7) class-probability matrix to expected-points scalar.

    Mirrors nflfastR's ``predict_ep()``: EP = sum_k(p_k * score_k), then
    clamp to [-10, 10].

    Args:
        probs: Array of shape (N, 7) from ``xgb_model.predict(DMatrix)``.

    Returns:
        1-D array of shape (N,) with EP values in [-10, 10].
    """
    ep = probs @ _EP_POINT_VALUES
    return np.clip(ep, -10.0, 10.0)


# ---------------------------------------------------------------------------
# Model validators
# ---------------------------------------------------------------------------

def validate_ep(
    model,
    df: pl.DataFrame,
    *,
    correlation_threshold: float = 0.98,
) -> Dict[str, Any]:
    """Validate EP model predictions against nflfastR reference ``ep`` column.

    Args:
        model: Trained XGBoost Booster with ``EP_FEATURES`` feature names.
        df: Frame with ``EP_FEATURES`` columns + ``ep`` (nflfastR reference values).
        correlation_threshold: Minimum Pearson r to pass the gate (default 0.98).

    Returns:
        Dict with keys ``correlation``, ``gate_pass``, ``n_plays``.
    """
    from xgboost import DMatrix

    X = df.select(EP_FEATURES).to_numpy()
    dmat = DMatrix(X, feature_names=EP_FEATURES)
    probs = model.predict(dmat)
    if probs.ndim == 1:
        # reshape (N*7,) → (N,7) if XGBoost returns flat output
        probs = probs.reshape(-1, len(EP_CLASS_ORDER))

    our_ep = _ep_expected_points(probs)
    ref_ep = np.array(df["ep"].to_list(), dtype=np.float64)
    r = pearson_correlation(our_ep, ref_ep)

    return {
        "correlation": r,
        "gate_pass": r >= correlation_threshold,
        "n_plays": len(df),
    }


def validate_wp(
    model,
    df: pl.DataFrame,
    *,
    brier_threshold: float = 0.20,
) -> Dict[str, Any]:
    """Validate WP model predictions against actual game outcomes.

    Args:
        model: Trained XGBoost Booster with ``WP_SPREAD_FEATURES`` feature names.
        df: Frame with ``WP_SPREAD_FEATURES`` columns + ``label`` (0/1 actual outcome).
        brier_threshold: Maximum Brier score to pass the gate (default 0.20).

    Returns:
        Dict with keys ``brier_score``, ``gate_pass``, ``n_plays``.
    """
    from xgboost import DMatrix

    X = df.select(WP_SPREAD_FEATURES).to_numpy()
    dmat = DMatrix(X, feature_names=WP_SPREAD_FEATURES)
    y_pred = model.predict(dmat)
    y_true = np.array(df["label"].to_list(), dtype=np.float64)
    bs = brier_score(y_true, y_pred)

    return {
        "brier_score": bs,
        "gate_pass": bs <= brier_threshold,
        "n_plays": len(df),
    }


# ---------------------------------------------------------------------------
# Parity gate orchestrator
# ---------------------------------------------------------------------------

def run_parity_gate(
    ep_model_path: Path,
    wp_model_path: Path,
    sample_seasons: List[int],
    *,
    data_dir: Path = Path("data"),
    ep_correlation_threshold: float = 0.98,
    wp_brier_threshold: float = 0.20,
) -> Dict[str, Any]:
    """Run the full EP + WP parity gate against nflfastR reference values.

    Args:
        ep_model_path: Path to ``ep_model.ubj``.
        wp_model_path: Path to ``wp_spread.ubj``.
        sample_seasons: Seasons of nflverse PBP to compare against.
        data_dir: Directory containing ``pbp_{season}.parquet`` files.
        ep_correlation_threshold: Gate threshold for EP Pearson r (default 0.98).
        wp_brier_threshold: Gate threshold for WP Brier score (default 0.20).

    Returns:
        Dict with keys ``ep`` (EP result dict), ``wp`` (WP result dict), and
        ``overall_pass`` (True only when both gates pass).

    Example:
        Run the gate after training::

            from pathlib import Path
            from model_training.play_level.validate import run_parity_gate

            result = run_parity_gate(
                ep_model_path=Path("models/ep_model.ubj"),
                wp_model_path=Path("models/wp_spread.ubj"),
                sample_seasons=[2022, 2023],
            )
            print("PASS" if result["overall_pass"] else "FAIL", result)
    """
    ep_model = _load_model(Path(ep_model_path))
    wp_model = _load_model(Path(wp_model_path))

    ep_df, wp_df = _load_pbp_for_validation(sample_seasons, Path(data_dir))

    print(f"[validate] EP: {len(ep_df):,} reference plays from {sample_seasons}")
    ep_result = validate_ep(
        ep_model, ep_df, correlation_threshold=ep_correlation_threshold
    )
    print(f"[validate] EP correlation = {ep_result['correlation']:.4f} "
          f"(threshold ≥ {ep_correlation_threshold}) → {'PASS' if ep_result['gate_pass'] else 'FAIL'}")

    print(f"[validate] WP: {len(wp_df):,} reference plays from {sample_seasons}")
    wp_result = validate_wp(
        wp_model, wp_df, brier_threshold=wp_brier_threshold
    )
    print(f"[validate] WP Brier = {wp_result['brier_score']:.4f} "
          f"(threshold ≤ {wp_brier_threshold}) → {'PASS' if wp_result['gate_pass'] else 'FAIL'}")

    overall = ep_result["gate_pass"] and wp_result["gate_pass"]
    print(f"[validate] Overall: {'PASS ✓' if overall else 'FAIL ✗'}")

    return {
        "ep": ep_result,
        "wp": wp_result,
        "overall_pass": overall,
    }
# ---------------------------------------------------------------------------
# dakota — the derived EPA/CPOE composite (no artifact; gate its premise)
# ---------------------------------------------------------------------------
#: sdv-py ships dakota as a fixed linear blend
#: (``sportsdataverse/nfl/nfl_stats.py``): 0.816*EPA/dropback + 0.184*CPOE.
DAKOTA_LINEAR_COEFFICIENTS: "tuple[float, float]" = (0.816, 0.184)
#: Dropback minimum for a qualifying passer-season. 200 keeps ~26 passers per
#: season -- roughly the set of full-time starters.
DAKOTA_MIN_DROPBACKS: int = 200
#: Floors for the blend's PREMISE, measured on model_pbp 2006-2025 (488 qualifying
#: passer-season pairs, 2026-09-01): CPOE year-over-year r = 0.7031 vs EPA/play's
#: 0.4508, and dakota itself carries 0.6820 -- i.e. blending in the stable input
#: buys +0.2312 of year-to-year stability. Floors sit below the observed values so
#: they detect a regression in an input model; never lower them to make a build
#: pass. CPOE is only defined from 2006 (air-yards charting), so pre-2006 pairs
#: cannot enter this gate at all.
DAKOTA_CPOE_STABILITY_FLOOR: float = 0.60
DAKOTA_STABILITY_FLOOR: float = 0.58
DAKOTA_STABILITY_MARGIN_FLOOR: float = 0.15
#: Floor for agreement between the shipped linear blend and the published
#: nflfastR GAM it approximates (observed r = 0.8542 pooled; worst season pair
#: 0.8348). This is the number that should move when either input model is
#: retrained -- see the recalibration-cadence row in models/REGISTRY.md.
DAKOTA_GAM_FIDELITY_FLOOR: float = 0.80
#: Minimum pairs before the correlations mean anything.
DAKOTA_MIN_PAIRS: int = 100

_ORACLE_DIR = Path(__file__).resolve().parents[3] / "models" / "oracles"


def dakota_gam_predict(cpoe: np.ndarray, epa_per_play: np.ndarray) -> np.ndarray:
    """Evaluate the published nflfastR dakota GAM from its committed term curves.

    The upstream model is ``mgcv::gam(target ~ s(cpoe) + s(epa_per_play))`` where
    ``target`` is NEXT season's adjusted EPA/play. Because it is purely additive,
    ``dakota = intercept + f_cpoe(cpoe) + f_epa(epa_per_play)`` and linear
    interpolation on the exported partial-effect curves reproduces
    ``mgcv::predict.gam`` to floating-point noise (pinned by
    ``models/oracles/dakota_gam_check.csv``; measured max error 8.0e-06).

    Args:
        cpoe: CPOE per passer-season, percentage-point scale.
        epa_per_play: EPA per dropback per passer-season.

    Returns:
        GAM dakota values, same shape as the inputs.

    Raises:
        FileNotFoundError: If the committed oracle fixtures are missing.
    """
    terms = pl.read_csv(_ORACLE_DIR / "dakota_gam_terms.csv")
    intercept = float((_ORACLE_DIR / "dakota_gam_intercept.txt").read_text().strip())
    cpoe_curve = terms.filter(pl.col("term") == "cpoe").sort("x")
    epa_curve = terms.filter(pl.col("term") == "epa_per_play").sort("x")
    return (
        intercept
        + np.interp(np.asarray(cpoe, float), cpoe_curve["x"].to_numpy(), cpoe_curve["f"].to_numpy())
        + np.interp(np.asarray(epa_per_play, float), epa_curve["x"].to_numpy(), epa_curve["f"].to_numpy())
    )


def dakota_passer_seasons(pbp: pl.DataFrame, *, min_dropbacks: int = DAKOTA_MIN_DROPBACKS) -> pl.DataFrame:
    """Aggregate PBP to qualifying passer-seasons carrying dakota's two inputs.

    Args:
        pbp: PBP with ``season``, ``passer_player_id``, ``qb_epa``, ``cpoe``.
        min_dropbacks: Qualifying threshold.

    Returns:
        One row per (passer, season) with ``dropbacks`` / ``epa_play`` / ``cpoe``.
        Passer-seasons with no CPOE (pre-2006) are dropped -- a null CPOE folded
        to 0 would silently read as league-average accuracy.
    """
    return (
        pbp.filter(pl.col("qb_epa").is_not_null() & pl.col("passer_player_id").is_not_null())
        .group_by(["passer_player_id", "season"])
        .agg(
            pl.col("passer_player_name").first().alias("passer"),
            pl.len().alias("dropbacks"),
            pl.col("qb_epa").mean().alias("epa_play"),
            pl.col("cpoe").drop_nulls().mean().alias("cpoe"),
        )
        .filter((pl.col("dropbacks") >= min_dropbacks) & pl.col("cpoe").is_not_null())
    )


def validate_dakota(
    pbp: pl.DataFrame,
    *,
    min_dropbacks: int = DAKOTA_MIN_DROPBACKS,
    cpoe_stability_floor: float = DAKOTA_CPOE_STABILITY_FLOOR,
    stability_floor: float = DAKOTA_STABILITY_FLOOR,
    stability_margin_floor: float = DAKOTA_STABILITY_MARGIN_FLOOR,
    gam_fidelity_floor: float = DAKOTA_GAM_FIDELITY_FLOOR,
    min_pairs: int = DAKOTA_MIN_PAIRS,
) -> "Dict[str, Any]":
    """Gate dakota, which has no artifact of its own to validate.

    dakota is a derived metric -- a fixed linear blend of EPA/dropback and CPOE --
    so there is nothing to score against a holdout. What CAN be checked is the
    thing the blend exists for, and that is what this gates:

    1. **The premise.** Blending is only worth doing because CPOE is the more
       year-to-year stable input. If ``cpoe_yoy`` stops exceeding ``epa_yoy``,
       the blend has lost its reason to exist.
    2. **The payoff.** dakota must actually inherit that stability
       (``dakota_yoy``, and its margin over ``epa_yoy``).
    3. **Fidelity to the published model.** The shipped linear coefficients
       approximate an nflfastR GAM; ``gam_fidelity`` is how well they still track
       it. This is the number to re-read when ``ep`` or ``cp`` is retrained --
       dakota consumes both, and neither retrain touches these coefficients.

    Reported but deliberately NOT gated: ``forecast_r`` /
    ``forecast_r_gam`` / ``epa_forecast_r`` -- how well each predicts NEXT
    season's EPA/play. Measured on model_pbp, the linear blend does not beat raw
    EPA/play at that (0.3007 vs 0.4508; the GAM manages 0.4257). That is a real
    result and it is reported honestly, but it is a different estimand from the
    one the GAM was fit on (weighted WEEKLY rows, 5-attempt minimum), so it is a
    caveat on how the metric is described, not evidence the coefficients are
    wrong. Gating it would be gating a comparison this data cannot settle.

    Args:
        pbp: Multi-season PBP (``season``, ``passer_player_id``, ``qb_epa``,
            ``cpoe``). Needs >= 2 consecutive seasons from 2006 on.
        min_dropbacks: Qualifying dropback threshold per passer-season.
        cpoe_stability_floor: Floor on CPOE's year-over-year correlation.
        stability_floor: Floor on dakota's year-over-year correlation.
        stability_margin_floor: Floor on ``dakota_yoy - epa_yoy``.
        gam_fidelity_floor: Floor on corr(linear blend, published GAM).
        min_pairs: Minimum passer-season pairs for the gate to be meaningful.

    Returns:
        Dict of the measured quantities plus ``gate_pass``. A sample below
        ``min_pairs`` returns ``gate_pass`` False rather than a vacuous pass.
    """
    a, b = DAKOTA_LINEAR_COEFFICIENTS
    seasons = dakota_passer_seasons(pbp, min_dropbacks=min_dropbacks)
    nxt = seasons.select(
        pl.col("passer_player_id"),
        (pl.col("season") - 1).alias("season"),
        pl.col("epa_play").alias("epa_play_next"),
        pl.col("cpoe").alias("cpoe_next"),
    )
    pairs = seasons.join(nxt, on=["passer_player_id", "season"], how="inner")

    if pairs.height < min_pairs:
        return {
            "n_pairs": pairs.height,
            "gate_pass": False,
            "reason": f"only {pairs.height} passer-season pairs (need {min_pairs})",
        }

    epa = pairs["epa_play"].to_numpy()
    cpoe = pairs["cpoe"].to_numpy()
    epa_next = pairs["epa_play_next"].to_numpy()
    cpoe_next = pairs["cpoe_next"].to_numpy()
    dakota = a * epa + b * cpoe
    dakota_next = a * epa_next + b * cpoe_next
    gam = dakota_gam_predict(cpoe, epa)

    epa_yoy = pearson_correlation(epa, epa_next)
    cpoe_yoy = pearson_correlation(cpoe, cpoe_next)
    dakota_yoy = pearson_correlation(dakota, dakota_next)
    fidelity = pearson_correlation(dakota, gam)
    margin = dakota_yoy - epa_yoy

    return {
        "n_pairs": pairs.height,
        "n_passer_seasons": seasons.height,
        "epa_yoy": epa_yoy,
        "cpoe_yoy": cpoe_yoy,
        "dakota_yoy": dakota_yoy,
        "stability_margin": margin,
        "gam_fidelity": fidelity,
        "gam_mean_abs_diff": float(np.mean(np.abs(dakota - gam))),
        # Reported, not gated -- see the docstring.
        "forecast_r": pearson_correlation(dakota, epa_next),
        "forecast_r_gam": pearson_correlation(gam, epa_next),
        "epa_forecast_r": pearson_correlation(epa, epa_next),
        "gate_pass": bool(
            cpoe_yoy >= cpoe_stability_floor
            and dakota_yoy >= stability_floor
            and margin >= stability_margin_floor
            and fidelity >= gam_fidelity_floor
        ),
    }
