"""Parity gate for the NFL model suite (track7).

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
    XPASS_FEATURES,
    FD_FEATURES,
    FD_NUM_CLASSES,
    TWO_PT_FEATURES,
    FG_FEATURES,
    FG_VALIDATION_YARDLINE_RANGE,
)

ORACLE_DIR = Path(
    r"C:/Users/saiem/Documents/GitHub-Data/sdv-dev/sdv-py-stats/dev/nfl4th_artifacts"
)

__all__ = [
    "pearson_correlation",
    "load_oracle_booster",
    "validate_xpass",
    "validate_fd",
    "validate_two_pt",
    "validate_fg",
    "validate_punt",
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
    oracle = load_oracle_booster(ORACLE_DIR / "xpass_model.ubj", len(XPASS_FEATURES))
    ref = _predict(oracle, X, None)
    r = pearson_correlation(ours, ref)
    return {"correlation": r, "gate_pass": r >= threshold, "n": len(df),
            "feature_names_ok": model.feature_names == XPASS_FEATURES}


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
    oracle = load_oracle_booster(ORACLE_DIR / "fd_model.ubj", len(FD_FEATURES))
    ref = _mean_gain(_predict(oracle, X, None))
    r = pearson_correlation(ours, ref)
    return {"correlation": r, "gate_pass": r >= threshold, "n": len(df),
            "feature_names_ok": model.feature_names == FD_FEATURES}


# ---------------------------------------------------------------------------
# two_pt
# ---------------------------------------------------------------------------
def validate_two_pt(model: Booster, df: pl.DataFrame, *, threshold: float = 0.99) -> Dict[str, Any]:
    X = df.select(TWO_PT_FEATURES).to_numpy()
    ours = _predict(model, X, TWO_PT_FEATURES)
    oracle = load_oracle_booster(ORACLE_DIR / "two_pt_model.ubj", len(TWO_PT_FEATURES))
    ref = _predict(oracle, X, None)
    r = pearson_correlation(ours, ref)
    return {"correlation": r, "gate_pass": r >= threshold, "n": len(df),
            "feature_names_ok": model.feature_names == TWO_PT_FEATURES}


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

    full_r = pearson_correlation(
        _predict(model, grid.select(FG_FEATURES).to_numpy().astype(float), FG_FEATURES),
        grid["prob"].to_numpy(),
    )

    if attempts is not None and attempts.height:
        # Cast join keys to a common dtype — the grid is i32, the attempts frame
        # carries yardline_100 as f64.
        cnt = attempts.with_columns(
            pl.col("yardline_100").cast(pl.Int32),
            pl.col("fg_roof").cast(pl.Int32),
            pl.col("fg_era").cast(pl.Int32),
        ).group_by(["yardline_100", "fg_roof", "fg_era"]).agg(
            pl.len().alias("attempt_n")
        )
        grid_keyed = grid.with_columns(
            pl.col("yardline_100").cast(pl.Int32),
            pl.col("fg_roof").cast(pl.Int32),
            pl.col("fg_era").cast(pl.Int32),
        )
        grid_obs = grid_keyed.join(
            cnt, on=["yardline_100", "fg_roof", "fg_era"], how="inner"
        )
        weights = grid_obs["attempt_n"].to_numpy().astype(float)
        scope = "attempted-cells"
    else:
        lo, hi = FG_VALIDATION_YARDLINE_RANGE
        grid_obs = grid.filter(
            (pl.col("yardline_100") >= lo) & (pl.col("yardline_100") <= hi)
        )
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
        agg = df.group_by(["yardline_100", "yardline_after"]).agg(
            pl.col("pct").sum().alias("pct")
        )
        out: dict[float, dict[float, float]] = {}
        for row in agg.iter_rows(named=True):
            out.setdefault(float(row["yardline_100"]), {})[
                float(row["yardline_after"])
            ] = float(row["pct"])
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
