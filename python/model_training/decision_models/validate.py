"""Parity gate for the NFL model suite (decision_models).

For each model, predict BOTH the freshly trained booster and the converted R
oracle on a held-out PBP slice and assert they agree:

    - xpass      Pearson corr >= 0.99 (per-play P(pass))
    - fd         Pearson corr >= 0.99 (mean predicted gain per play)
    - two_pt     Pearson corr >= 0.99 (per-play P(success))
    - fg         Pearson corr >= 0.98 vs the GAM grid FG% (report max abs diff)
    - punt       per-yardline total-variation distance small
    - wp         Pearson corr >= 0.99 (only if trained)

Also asserts each booster's ``feature_names == *_FEATURES``.

The oracles live under ``<sdv-py-stats>/dev/nfl4th_artifacts/``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import numpy as np
import polars as pl
from xgboost import Booster, DMatrix

from .constants import (
    FD_FEATURES,
    FD_NUM_CLASSES,
    FG_FEATURES,
    FG_VALIDATION_YARDLINE_RANGE,
    TWO_PT_FEATURES,
    WP_FEATURES,
    XPASS_FEATURES,
)

ORACLE_DIR = Path(r"C:/Users/saiem/Documents/GitHub-Data/sdv-dev/sdv-py-stats/dev/nfl4th_artifacts")

# The era-aware full-history xpass/fd add era0/era1(/era2) on top of the converted
# oracle's narrower contract. Predict the oracle on its OWN feature subset so the
# (now informational) corr-vs-oracle still computes despite the contract divergence.
_ORACLE_XPASS_FEATURES = [f for f in XPASS_FEATURES if f not in ("era0", "era1")]
_ORACLE_FD_FEATURES = [f for f in FD_FEATURES if f not in ("era0", "era1", "era2")]

__all__ = [
    "pearson_correlation",
    "load_oracle_booster",
    "validate_xpass",
    "validate_fd",
    "validate_two_pt",
    "validate_fg",
    "validate_wp",
    "validate_punt",
    "validate_punt_holdout",
    "realized_punt_landings",
]


def pearson_correlation(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    if a.size < 2 or b.size < 2:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def load_oracle_booster(path: Path, n_features: int) -> Booster:
    """Load a converted R oracle booster; it carries no feature names."""
    b = Booster()
    b.load_model(str(path))
    return b


def _predict(model: Booster, X: np.ndarray, feature_names: list[str] | None) -> np.ndarray:
    return model.predict(DMatrix(X, feature_names=feature_names))


# ---------------------------------------------------------------------------
# xpass
# ---------------------------------------------------------------------------
def validate_xpass(model: Booster, df: pl.DataFrame, *, threshold: float = 0.99) -> Dict[str, Any]:
    X = df.select(XPASS_FEATURES).to_numpy()
    ours = _predict(model, X, XPASS_FEATURES)
    oracle = load_oracle_booster(ORACLE_DIR / "xpass_model.ubj", len(_ORACLE_XPASS_FEATURES))
    ref = _predict(oracle, df.select(_ORACLE_XPASS_FEATURES).to_numpy(), None)
    r = pearson_correlation(ours, ref)
    return {
        "correlation": r,
        "gate_pass": r >= threshold,
        "n": len(df),
        "feature_names_ok": model.feature_names == XPASS_FEATURES,
    }


# ---------------------------------------------------------------------------
# fd — compare mean predicted gain per play
# ---------------------------------------------------------------------------
def _mean_gain(probs: np.ndarray) -> np.ndarray:
    if probs.ndim == 1:
        probs = probs.reshape(-1, FD_NUM_CLASSES)
    gains = np.arange(FD_NUM_CLASSES) - 10.0  # class 0 == -10 yards
    return probs @ gains


def validate_fd(model: Booster, df: pl.DataFrame, *, threshold: float = 0.99) -> Dict[str, Any]:
    X = df.select(FD_FEATURES).to_numpy()
    ours = _mean_gain(_predict(model, X, FD_FEATURES))
    oracle = load_oracle_booster(ORACLE_DIR / "fd_model.ubj", len(_ORACLE_FD_FEATURES))
    ref = _mean_gain(_predict(oracle, df.select(_ORACLE_FD_FEATURES).to_numpy(), None))
    r = pearson_correlation(ours, ref)
    return {
        "correlation": r,
        "gate_pass": r >= threshold,
        "n": len(df),
        "feature_names_ok": model.feature_names == FD_FEATURES,
    }


# ---------------------------------------------------------------------------
# two_pt
# ---------------------------------------------------------------------------
def validate_two_pt(model: Booster, df: pl.DataFrame, *, threshold: float = 0.99) -> Dict[str, Any]:
    X = df.select(TWO_PT_FEATURES).to_numpy()
    ours = _predict(model, X, TWO_PT_FEATURES)
    oracle = load_oracle_booster(ORACLE_DIR / "two_pt_model.ubj", len(TWO_PT_FEATURES))
    ref = _predict(oracle, X, None)
    r = pearson_correlation(ours, ref)
    return {
        "correlation": r,
        "gate_pass": r >= threshold,
        "n": len(df),
        "feature_names_ok": model.feature_names == TWO_PT_FEATURES,
    }


# ---------------------------------------------------------------------------
# wp — compare per-play P(posteam win) vs the naive wp_model oracle
# ---------------------------------------------------------------------------
def _wp_oracle_path() -> Path:
    """Locate the converted naive wp_model.ubj (root or official/ subdir)."""
    for cand in (ORACLE_DIR / "wp_model.ubj", ORACLE_DIR / "official" / "wp_model.ubj"):
        if cand.exists():
            return cand
    return ORACLE_DIR / "wp_model.ubj"


def validate_wp(model: Booster, df: pl.DataFrame, *, threshold: float = 0.99) -> Dict[str, Any]:
    """Compare our naive WP booster to the converted oracle (per-play P(win)).

    Args:
        model: Trained WP booster.
        df: Held-out ``prepare_wp_data`` frame (``WP_FEATURES`` + ``label``).
        threshold: Min Pearson corr to pass.
    """
    X = df.select(WP_FEATURES).to_numpy()
    ours = _predict(model, X, WP_FEATURES)
    oracle = load_oracle_booster(_wp_oracle_path(), len(WP_FEATURES))
    ref = _predict(oracle, X, None)
    r = pearson_correlation(ours, ref)
    return {
        "correlation": r,
        "gate_pass": r >= threshold,
        "n": len(df),
        "feature_names_ok": model.feature_names == WP_FEATURES,
    }


# ---------------------------------------------------------------------------
# fg — compare against the GAM grid (yardline x roof x era)
# ---------------------------------------------------------------------------
def validate_fg(
    model: Booster,
    *,
    threshold: float = 0.98,
    attempts: pl.DataFrame | None = None,
) -> Dict[str, Any]:
    """Predict over the GAM grid (yardline x roof x era) and compare FG%.

    The GAM grid spans every (yardline 1..99) x (4 roof/era) cell, but FG
    attempts only occur in a subset of those cells; the GAM extrapolates its
    per-combo spline into never-attempted cells (e.g. a 47-yd dome kick in a
    sparse roof/era combo) where it borrows strength across the spline and a
    step-function booster cannot follow. The GATE corr is therefore computed on
    the cells that carry >=1 real FG attempt (the model's actual operating
    domain); the full-grid corr + freq-weighted corr are reported alongside.

    Args:
        model: Trained FG booster.
        threshold: Min Pearson corr to pass.
        attempts: The FG training frame (``prepare_fg_data`` output) used to
            identify attempted (yardline, roof, era) cells. When None, falls
            back to the realistic yardline-range scoping.
    """
    grid = pl.read_parquet(ORACLE_DIR / "fg_model_grid.parquet")
    # fg_model_roof "RE": first digit = roof (1 outdoors), second = era (1 >=2020)
    grid = grid.with_columns(
        pl.col("fg_model_roof").str.slice(0, 1).cast(pl.Int32).alias("fg_roof"),
        pl.col("fg_model_roof").str.slice(1, 1).cast(pl.Int32).alias("fg_era"),
    )
    # The GAM grid carries the 2-level fg_era (>=2020); the era-aware fg uses the
    # 5-era one-hot. Map the grid's pre/post-2020 split onto the modern eras
    # (era4 = >=2018, era3 = 2014-2017) so the booster can be scored over the GAM
    # grid. INFORMATIONAL only — the full-history era-aware fg no longer reproduces
    # the narrow-window GAM oracle.
    grid = grid.with_columns(
        pl.lit(0).cast(pl.Int32).alias("era0"),
        pl.lit(0).cast(pl.Int32).alias("era1"),
        pl.lit(0).cast(pl.Int32).alias("era2"),
        (1 - pl.col("fg_era")).cast(pl.Int32).alias("era3"),
        pl.col("fg_era").cast(pl.Int32).alias("era4"),
    )

    full_r = pearson_correlation(
        _predict(model, grid.select(FG_FEATURES).to_numpy().astype(float), FG_FEATURES),
        grid["prob"].to_numpy(),
    )

    if attempts is not None and attempts.height:
        # Weight by attempted cells, keyed on era4 (the model's modern-era flag).
        cnt = (
            attempts.with_columns(
                pl.col("yardline_100").cast(pl.Int32),
                pl.col("fg_roof").cast(pl.Int32),
                pl.col("era4").cast(pl.Int32),
            )
            .group_by(["yardline_100", "fg_roof", "era4"])
            .agg(pl.len().alias("attempt_n"))
        )
        grid_keyed = grid.with_columns(
            pl.col("yardline_100").cast(pl.Int32),
            pl.col("fg_roof").cast(pl.Int32),
            pl.col("era4").cast(pl.Int32),
        )
        grid_obs = grid_keyed.join(cnt, on=["yardline_100", "fg_roof", "era4"], how="inner")
        weights = grid_obs["attempt_n"].to_numpy().astype(float)
        scope = "attempted-cells"
    else:
        lo, hi = FG_VALIDATION_YARDLINE_RANGE
        grid_obs = grid.filter((pl.col("yardline_100") >= lo) & (pl.col("yardline_100") <= hi))
        weights = np.ones(grid_obs.height)
        scope = f"yardline {FG_VALIDATION_YARDLINE_RANGE[0]}-{FG_VALIDATION_YARDLINE_RANGE[1]}"

    X = grid_obs.select(FG_FEATURES).to_numpy().astype(float)
    ours = _predict(model, X, FG_FEATURES)
    ref = grid_obs["prob"].to_numpy()
    r = pearson_correlation(ours, ref)
    max_abs = float(np.max(np.abs(ours - ref))) if grid_obs.height else float("nan")

    # frequency-weighted corr (how the model is actually exercised)
    mx, my = np.average(ours, weights=weights), np.average(ref, weights=weights)
    cov = np.average((ours - mx) * (ref - my), weights=weights)
    sx = np.sqrt(np.average((ours - mx) ** 2, weights=weights))
    sy = np.sqrt(np.average((ref - my) ** 2, weights=weights))
    wr = float(cov / (sx * sy)) if sx > 0 and sy > 0 else float("nan")

    return {
        "correlation": r,
        "weighted_correlation": wr,
        "max_abs_fg_pct_diff": max_abs,
        "full_grid_correlation": full_r,
        "gate_pass": r >= threshold,
        "n": grid_obs.height,
        "scope": scope,
        "feature_names_ok": model.feature_names == FG_FEATURES,
    }


# ---------------------------------------------------------------------------
# punt — total-variation distance of per-yardline landing distributions
# ---------------------------------------------------------------------------
def validate_punt(
    ours: pl.DataFrame,
    *,
    threshold: float = 0.10,
    punt_weights: dict[float, float] | None = None,
) -> Dict[str, Any]:
    """Compare per-yardline landing distributions vs the oracle punt_data.

    Marginalizes muff (sums pct over muff in {0,1}) into a P(yardline_after |
    yardline_100) distribution per yardline, then computes the total-variation
    distance per yardline. The GATE is the **frequency-weighted** mean TV (each
    yardline weighted by how often a punt actually occurs there) — the raw
    per-yardline mean is dominated by the rare 31-39 yardlines (punts almost
    never happen near FG range), where small-sample + KDE-bandwidth divergence is
    expected and the SPEC anticipates it. Raw mean / median / max are reported.

    Args:
        ours: Our ``build_punt_data`` output.
        threshold: Max freq-weighted mean TV to pass.
        punt_weights: Optional ``{yardline_100: punt_count}`` weights; when None,
            every yardline is weighted equally (raw mean == gate metric).
    """
    oracle = pl.read_parquet(ORACLE_DIR / "punt_data.parquet")

    def _marginal(df: pl.DataFrame) -> dict[float, dict[float, float]]:
        agg = df.group_by(["yardline_100", "yardline_after"]).agg(pl.col("pct").sum().alias("pct"))
        out: dict[float, dict[float, float]] = {}
        for row in agg.iter_rows(named=True):
            out.setdefault(float(row["yardline_100"]), {})[float(row["yardline_after"])] = float(row["pct"])
        return out

    o, r = _marginal(ours), _marginal(oracle)
    shared = sorted(set(o) & set(r))
    tvs, weights = [], []
    for yl in shared:
        keys = set(o[yl]) | set(r[yl])
        tv = 0.5 * sum(abs(o[yl].get(k, 0.0) - r[yl].get(k, 0.0)) for k in keys)
        tvs.append(tv)
        weights.append((punt_weights or {}).get(yl, 1.0))
    tv_arr = np.asarray(tvs, dtype=np.float64)
    w_arr = np.asarray(weights, dtype=np.float64)
    weighted = float(np.average(tv_arr, weights=w_arr)) if tv_arr.size and w_arr.sum() else float("nan")
    return {
        "weighted_mean_total_variation": weighted,
        "mean_total_variation": float(np.mean(tv_arr)) if tv_arr.size else float("nan"),
        "median_total_variation": float(np.median(tv_arr)) if tv_arr.size else float("nan"),
        "max_total_variation": float(np.max(tv_arr)) if tv_arr.size else float("nan"),
        "gate_pass": weighted <= threshold,
        "n_yardlines": len(shared),
    }
# ---------------------------------------------------------------------------
# punt — distribution gate against HELD-OUT seasons (not the R oracle)
# ---------------------------------------------------------------------------
#: Max freq-weighted per-yardline KS distance vs realized holdout landings.
#: Observed on the shipped surface (2026-09-01): 0.0874 on 2010-2014 (seasons
#: inside the classic training span), 0.1223 pooled 2020-2025, worst single
#: season 0.1881 (2024). The ceiling sits above the worst observed value so it
#: catches a regression without firing on the drift already documented in
#: docs/models/punt.md. Never raise it to make a build pass -- diagnose instead.
PUNT_HOLDOUT_KS_MAX: float = 0.22
#: Max |surface expected landing - realized mean landing| in yards on the holdout
#: snap mix. Observed 2026-09-01: 0.27 yd on 2010-2014, 2.12 yd pooled 2020-2025,
#: worst single season 2.58 (2024). Same never-lower rule.
PUNT_HOLDOUT_MEAN_YARDS_MAX: float = 3.5
#: A yardline needs this many real holdout punts before its empirical landing
#: distribution is worth comparing against. Below it the comparison measures
#: sampling noise, not the surface.
PUNT_HOLDOUT_MIN_PUNTS_PER_YARDLINE: int = 25


def realized_punt_landings(pbp: pl.DataFrame) -> pl.DataFrame:
    """Derive realized punt landing spots from PBP, mirroring ``build_punt_data``.

    Applies the same ``yardline_after`` construction the builder uses (end-zone
    NA->20, BLOCKED NA->yardline_100, cap 100, 0->1) so the comparison is
    like-for-like, then keeps ``yardline_100 > 30`` -- the builder's own domain.

    Punts are selected on ``play_type == "punt"``; the builder uses the nflverse
    ``play_type_nfl == "PUNT"``, which the published ``model_pbp`` corpus does
    not carry. Both select the same plays.

    Args:
        pbp: PBP carrying ``desc``, ``play_type``, ``yardline_100``,
            ``kick_distance``, ``return_yards``.

    Returns:
        One row per punt with ``yardline_100`` / ``yardline_after`` (Float64).
    """
    desc = pl.col("desc").fill_null("")
    ya = pl.col("yardline_100") - pl.col("kick_distance") + pl.col("return_yards").fill_null(0)
    ya = pl.when(desc.str.contains("end zone") & pl.col("kick_distance").is_null()).then(pl.lit(20.0)).otherwise(ya)
    ya = (
        pl.when(desc.str.contains("BLOCKED") & ya.is_null()).then(pl.col("yardline_100").cast(pl.Float64)).otherwise(ya)
    )
    ya = pl.when(ya > 100).then(pl.lit(100.0)).otherwise(ya)
    ya = pl.when(ya == 0).then(pl.lit(1.0)).otherwise(ya)
    return (
        pbp.filter(pl.col("play_type") == "punt")
        .select("desc", "yardline_100", "kick_distance", "return_yards")
        .with_columns(ya.alias("yardline_after"))
        .filter(pl.col("yardline_after").is_not_null() & (pl.col("yardline_100") > 30))
        .select(
            pl.col("yardline_100").cast(pl.Float64),
            pl.col("yardline_after").cast(pl.Float64).round(0),
        )
    )


def validate_punt_holdout(
    ours: pl.DataFrame,
    holdout_pbp: pl.DataFrame,
    *,
    ks_threshold: float = PUNT_HOLDOUT_KS_MAX,
    mean_yards_threshold: float = PUNT_HOLDOUT_MEAN_YARDS_MAX,
    min_punts_per_yardline: int = PUNT_HOLDOUT_MIN_PUNTS_PER_YARDLINE,
) -> Dict[str, Any]:
    """Gate the punt landing surface against REALITY on held-out seasons.

    ``validate_punt`` answers "does this reproduce the R oracle"; this answers
    "does this describe how punts actually land", which is the question the
    4th-down decision layer's punt branch depends on and the one an oracle-only
    gate cannot see. They are complementary: a surface can reproduce the oracle
    perfectly and still no longer match the modern game.

    **The gate statistic is KS, not total variation.** The surface is a smooth
    KDE over ~50 discrete landing spots per snap yardline, while a single season
    puts only ~45 punts on each yardline, so the empirical mass is spiky and TV
    -- a sum of pointwise differences -- is dominated by that discreteness (0.39
    per season vs 0.23 pooled, on a surface whose CDF tracks reality to 0.12).
    KS compares CDFs and is not fooled by where a sparse sample falls inside a
    bin. TV is still returned, as informational.

    Args:
        ours: ``build_punt_data`` output (or the shipped ``punt_data.parquet``).
        holdout_pbp: PBP for the seasons to check against. Pass seasons OUTSIDE
            the surface's training span for an honest read -- passing
            in-training seasons measures fit, not generalization.
        ks_threshold: Max freq-weighted KS distance.
        mean_yards_threshold: Max |expected - realized| mean landing, in yards.
        min_punts_per_yardline: Yardlines with fewer real punts are skipped.

    Returns:
        Dict with ``weighted_ks`` / ``max_ks`` / ``weighted_total_variation``,
        ``mean_landing_surface`` / ``_realized`` / ``mean_landing_diff``,
        ``n_punts``, ``n_yardlines``, and ``gate_pass`` (both criteria).
    """
    real = realized_punt_landings(holdout_pbp)
    surface = (
        ours.group_by(["yardline_100", "yardline_after"])
        .agg(pl.col("pct").sum().alias("pct"))
        .with_columns(
            pl.col("yardline_100").cast(pl.Float64),
            pl.col("yardline_after").cast(pl.Float64),
        )
    )

    counts = real.group_by(["yardline_100", "yardline_after"]).agg(pl.len().alias("n"))
    totals = counts.group_by("yardline_100").agg(pl.col("n").sum().alias("tot"))
    empirical = counts.join(totals, on="yardline_100", how="inner").with_columns(
        (pl.col("n") / pl.col("tot")).alias("p")
    )
    punts_at = {float(r["yardline_100"]): float(r["tot"]) for r in totals.iter_rows(named=True)}

    def _by_yardline(df: pl.DataFrame, value: str) -> "dict[float, dict[float, float]]":
        out: "dict[float, dict[float, float]]" = {}
        for row in df.iter_rows(named=True):
            out.setdefault(float(row["yardline_100"]), {})[float(row["yardline_after"])] = float(row[value])
        return out

    surf_by, emp_by = _by_yardline(surface, "pct"), _by_yardline(empirical, "p")
    ks_vals, tv_vals, weights = [], [], []
    for yardline in sorted(set(surf_by) & set(emp_by)):
        if punts_at.get(yardline, 0.0) < min_punts_per_yardline:
            continue
        s_row, e_row = surf_by[yardline], emp_by[yardline]
        cum_s = cum_e = ks = tv = 0.0
        for spot in sorted(set(s_row) | set(e_row)):
            s_p, e_p = s_row.get(spot, 0.0), e_row.get(spot, 0.0)
            tv += abs(s_p - e_p)
            cum_s += s_p
            cum_e += e_p
            ks = max(ks, abs(cum_s - cum_e))
        ks_vals.append(ks)
        tv_vals.append(0.5 * tv)
        weights.append(punts_at[yardline])

    ks_arr = np.asarray(ks_vals, dtype=np.float64)
    tv_arr = np.asarray(tv_vals, dtype=np.float64)
    w_arr = np.asarray(weights, dtype=np.float64)
    have = ks_arr.size > 0 and w_arr.sum() > 0
    weighted_ks = float(np.average(ks_arr, weights=w_arr)) if have else float("nan")

    expected = surface.group_by("yardline_100").agg(
        ((pl.col("yardline_after") * pl.col("pct")).sum() / pl.col("pct").sum()).alias("expected_after")
    )
    landed = (
        real.group_by("yardline_100")
        .agg(pl.col("yardline_after").mean().alias("realized_after"), pl.len().alias("n"))
        .join(expected, on="yardline_100", how="inner")
    )
    if landed.height:
        n_at = landed["n"].to_numpy().astype(float)
        mean_surface = float(np.average(landed["expected_after"].to_numpy(), weights=n_at))
        mean_realized = float(np.average(landed["realized_after"].to_numpy(), weights=n_at))
    else:
        mean_surface = mean_realized = float("nan")
    mean_diff = mean_surface - mean_realized

    return {
        "weighted_ks": weighted_ks,
        "max_ks": float(np.max(ks_arr)) if have else float("nan"),
        "weighted_total_variation": (float(np.average(tv_arr, weights=w_arr)) if have else float("nan")),
        "mean_landing_surface": mean_surface,
        "mean_landing_realized": mean_realized,
        "mean_landing_diff": mean_diff,
        "n_punts": real.height,
        "n_yardlines": int(ks_arr.size),
        "gate_pass": bool(have and weighted_ks <= ks_threshold and abs(mean_diff) <= mean_yards_threshold),
    }
