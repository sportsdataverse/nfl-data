"""XGBoost trainers + punt-distribution builder for the NFL model suite (track7).

Each ``train_*`` accepts a feature-engineered polars DataFrame and returns a
trained Booster. Pass ``nrounds`` to override the canonical value (smoke tests
use ``nrounds=5``). ``build_punt_data`` is a non-model empirical-distribution
builder ported from ``_punt_and_fg_models.R``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import polars as pl
from xgboost import Booster, DMatrix, cv as xgb_cv, train as xgb_train

from .constants import (
    XPASS_FEATURES,
    XPASS_HYPERPARAMS,
    FD_FEATURES,
    FD_HYPERPARAMS,
    TWO_PT_FEATURES,
    TWO_PT_HYPERPARAMS,
    FG_FEATURES,
    FG_HYPERPARAMS,
)

__all__ = [
    "train_xpass",
    "train_fd",
    "train_two_pt",
    "train_fg",
    "build_punt_data",
]


def _to_dmatrix(df: pl.DataFrame, features: list[str], label_col: str) -> DMatrix:
    X = df.select(features).to_numpy()
    y = df[label_col].to_numpy()
    return DMatrix(X, label=y, feature_names=features)


def _strip(params: dict, *drop: str) -> dict:
    return {k: v for k, v in params.items() if k not in drop}


# ---------------------------------------------------------------------------
# xpass — binary:logistic
# ---------------------------------------------------------------------------
def train_xpass(
    df: pl.DataFrame,
    *,
    nrounds: Optional[int] = None,
    output_path: Optional[Path] = None,
) -> Booster:
    """Train the NFL xpass (dropback) model.

    Args:
        df: Frame from ``prepare_xpass_data`` — ``XPASS_FEATURES`` + ``label``.
        nrounds: Override canonical nrounds (default ``XPASS_HYPERPARAMS``).
        output_path: If given, save the model as a ``.ubj`` file.

    Returns:
        Trained :class:`xgboost.Booster`.

    Example:
        Smoke-train on a tiny frame::

            booster = train_xpass(frame, nrounds=5)
    """
    rounds = nrounds if nrounds is not None else XPASS_HYPERPARAMS["nrounds"]
    params = _strip(XPASS_HYPERPARAMS, "nrounds", "seed")
    params["base_score"] = float(df["label"].mean())
    params["seed"] = XPASS_HYPERPARAMS["seed"]
    dmat = _to_dmatrix(df, XPASS_FEATURES, "label")
    model = xgb_train(params, dmat, num_boost_round=rounds)
    if output_path is not None:
        model.save_model(str(output_path))
    return model


# ---------------------------------------------------------------------------
# fd_model — multi:softprob (76 classes)
# ---------------------------------------------------------------------------
def train_fd(
    df: pl.DataFrame,
    *,
    nrounds: Optional[int] = None,
    output_path: Optional[Path] = None,
) -> Booster:
    """Train the NFL fd (go-for-it gain distribution) model.

    Args:
        df: Frame from ``prepare_fd_data`` — ``FD_FEATURES`` + ``label`` (0..75).
        nrounds: Override canonical nrounds (default ``FD_HYPERPARAMS``).
        output_path: If given, save the model as a ``.ubj`` file.

    Returns:
        Trained :class:`xgboost.Booster`.
    """
    rounds = nrounds if nrounds is not None else FD_HYPERPARAMS["nrounds"]
    params = _strip(FD_HYPERPARAMS, "nrounds")
    dmat = _to_dmatrix(df, FD_FEATURES, "label")
    model = xgb_train(params, dmat, num_boost_round=rounds)
    if output_path is not None:
        model.save_model(str(output_path))
    return model


# ---------------------------------------------------------------------------
# two_pt_model — binary:logistic (monotone)
# ---------------------------------------------------------------------------
def train_two_pt(
    df: pl.DataFrame,
    *,
    nrounds: Optional[int] = None,
    output_path: Optional[Path] = None,
) -> Booster:
    """Train the NFL 2-pt conversion model.

    Args:
        df: Frame from ``prepare_two_pt_data`` — ``TWO_PT_FEATURES`` + ``label``.
        nrounds: Override canonical nrounds (default ``TWO_PT_HYPERPARAMS``).
        output_path: If given, save the model as a ``.ubj`` file.

    Returns:
        Trained :class:`xgboost.Booster`.
    """
    rounds = nrounds if nrounds is not None else TWO_PT_HYPERPARAMS["nrounds"]
    params = _strip(TWO_PT_HYPERPARAMS, "nrounds", "monotone_constraints")
    mc = TWO_PT_HYPERPARAMS["monotone_constraints"]
    params["monotone_constraints"] = "(" + ",".join(str(int(c)) for c in mc) + ")"
    dmat = _to_dmatrix(df, TWO_PT_FEATURES, "label")
    model = xgb_train(params, dmat, num_boost_round=rounds)
    if output_path is not None:
        model.save_model(str(output_path))
    return model


# ---------------------------------------------------------------------------
# fg_model — binary:logistic (re-train of the mgcv GAM)
# ---------------------------------------------------------------------------
def train_fg(
    df: pl.DataFrame,
    *,
    nrounds: Optional[int] = None,
    output_path: Optional[Path] = None,
    cv_select: bool = False,
) -> Booster:
    """Train the NFL field-goal make-probability model (XGBoost).

    The original was an ``mgcv::bam`` GAM. This re-trains it as a shallow,
    monotone (decreasing in distance) ``binary:logistic`` booster — the monotone
    constraint on ``yardline_100`` is what lets a step-function booster track the
    smooth spline closely. The canonical ``nrounds`` (3000 @ eta 0.03) was chosen
    by grid search to maximize corr-vs-GAM on the realistic FG range; 5-fold CV
    on logloss systematically under-fits this smooth target, so it is opt-in only.

    Args:
        df: Frame from ``prepare_fg_data`` — ``FG_FEATURES`` + ``label`` (0/1).
        nrounds: Pin the round count (default ``FG_HYPERPARAMS["nrounds"]``).
        output_path: If given, save the model as a ``.ubj`` file.
        cv_select: Select nrounds via 5-fold CV when True (under-fits — not used
            by the canonical pipeline).

    Returns:
        Trained :class:`xgboost.Booster`.
    """
    params = _strip(FG_HYPERPARAMS, "nrounds", "monotone_constraints")
    mc = FG_HYPERPARAMS["monotone_constraints"]
    params["monotone_constraints"] = "(" + ",".join(str(int(c)) for c in mc) + ")"
    dmat = _to_dmatrix(df, FG_FEATURES, "label")
    cap = FG_HYPERPARAMS["nrounds"]

    if nrounds is None and cv_select:
        cv_res = xgb_cv(
            params,
            dmat,
            num_boost_round=cap,
            nfold=5,
            metrics=("logloss",),
            early_stopping_rounds=50,
            seed=FG_HYPERPARAMS["seed"],
            verbose_eval=False,
        )
        rounds = int(cv_res.shape[0])
    else:
        rounds = nrounds if nrounds is not None else cap

    model = xgb_train(params, dmat, num_boost_round=rounds)
    if output_path is not None:
        model.save_model(str(output_path))
    return model


# ---------------------------------------------------------------------------
# punt_data — empirical landing distribution (NOT a model)
# ---------------------------------------------------------------------------
def _bandwidth_nrd(x: np.ndarray) -> float:
    """R ``MASS::bandwidth.nrd`` — the normal-reference bandwidth kde2d defaults to."""
    x = np.asarray(x, dtype=np.float64)
    n = len(x)
    q1, q3 = np.quantile(x, [0.25, 0.75])
    r = (q3 - q1) / 1.349
    sd = np.std(x, ddof=1)
    s = min(sd, r) if r > 0 else sd
    return 4.0 * 1.06 * s * n ** (-1.0 / 5.0)


def _kde2d_density(x: np.ndarray, y: np.ndarray, grid_n: int = 100) -> np.ndarray:
    """Per-point 2D KDE density, faithfully mirroring R ``MASS::kde2d``.

    kde2d uses an axis-aligned *product* of 1-D Gaussian kernels with per-axis
    bandwidth ``bandwidth.nrd`` (the kernel sd is ``h/4``), evaluated on a
    ``grid_n`` x ``grid_n`` grid; ``get_density`` then looks up the cell each
    point falls in via ``findInterval``. scipy's ``gaussian_kde`` uses a
    covariance-coupled kernel + Scott's rule and does NOT match — the product
    form here is what reproduces the punt landing distribution.
    """
    from scipy.stats import norm

    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    hx = _bandwidth_nrd(x) / 4.0
    hy = _bandwidth_nrd(y) / 4.0
    gx = np.linspace(x.min(), x.max(), grid_n)
    gy = np.linspace(y.min(), y.max(), grid_n)
    # z[i, j] = density at (gx[i], gy[j]) = mean_k Kx(gx[i]-x_k) * Ky(gy[j]-y_k)
    dx = norm.pdf((gx[:, None] - x[None, :]) / hx) / hx  # (grid_n, n)
    dy = norm.pdf((gy[:, None] - y[None, :]) / hy) / hy  # (grid_n, n)
    z = (dx @ dy.T) / len(x)  # (grid_n, grid_n), z[i, j] over gx[i], gy[j]
    # findInterval: index of grid edge below each value (R 1-based; clamp to grid).
    ix = np.clip(np.searchsorted(gx, x, side="right") - 1, 0, grid_n - 1)
    iy = np.clip(np.searchsorted(gy, y, side="right") - 1, 0, grid_n - 1)
    return z[ix, iy]


def build_punt_data(
    df: pl.DataFrame,
    *,
    output_path: Optional[Path] = None,
) -> pl.DataFrame:
    """Build the empirical punt landing distribution.

    Faithful port of ``_punt_and_fg_models.R``. For each punt computes
    ``yardline_after = yardline_100 - kick_distance + return_yards`` (end-zone
    NA→20; BLOCKED NA→yardline_100; cap 100; 0→1), flags blocked / return_td /
    muff, coarse-bins muffed/blocked/td pct by yardline, KDEs the non-blocked /
    non-td landings, re-injects block+td outlier rows, duplicates rows for
    ``muff in {0,1}`` weighted by the bin muffed pct, renormalizes per yardline,
    and keeps ``yardline_100 > 30``.

    Args:
        df: Raw nflverse PBP (punts are filtered internally).
        output_path: If given, write ``punt_data.parquet`` there.

    Returns:
        Frame with columns ``yardline_100, yardline_after, pct, muff``.
    """
    punts = df.filter(pl.col("play_type_nfl") == "PUNT").select(
        "desc", "yardline_100", "kick_distance", "return_yards", "fumble_lost"
    )

    desc = pl.col("desc").fill_null("")
    ya = pl.col("yardline_100") - pl.col("kick_distance") + pl.col("return_yards").fill_null(0)
    ya = (
        pl.when(desc.str.contains("end zone") & pl.col("kick_distance").is_null())
        .then(pl.lit(20.0))
        .otherwise(ya)
    )
    ya = (
        pl.when(desc.str.contains("BLOCKED") & ya.is_null())
        .then(pl.col("yardline_100").cast(pl.Float64))
        .otherwise(ya)
    )
    ya = pl.when(ya > 100).then(pl.lit(100.0)).otherwise(ya)
    ya = pl.when(ya == 0).then(pl.lit(1.0)).otherwise(ya)

    points = punts.with_columns(ya.alias("yardline_after")).with_columns(
        desc.str.contains("BLOCKED").cast(pl.Int32).alias("blocked"),
    )
    points = points.with_columns(
        (pl.col("yardline_after") == 100).cast(pl.Int32).alias("return_td"),
        pl.when(pl.col("blocked") == 1)
        .then(pl.lit(0))
        .otherwise(pl.col("fumble_lost").fill_null(0).cast(pl.Int32))
        .alias("fumble_lost"),
    ).filter(pl.col("yardline_after").is_not_null())
    points = points.with_columns(pl.col("yardline_100").cast(pl.Float64))

    # coarse bins to smooth rare blocked / td / muff rates
    bin_expr = (
        pl.when(pl.col("yardline_100") < 40).then(0)
        .when((pl.col("yardline_100") >= 40) & (pl.col("yardline_100") <= 49)).then(1)
        .when((pl.col("yardline_100") >= 50) & (pl.col("yardline_100") <= 59)).then(2)
        .when((pl.col("yardline_100") >= 60) & (pl.col("yardline_100") <= 69)).then(3)
        .when((pl.col("yardline_100") >= 70) & (pl.col("yardline_100") <= 79)).then(4)
        .when((pl.col("yardline_100") >= 80) & (pl.col("yardline_100") <= 89)).then(5)
        .otherwise(6)
    )
    per_yl = points.group_by("yardline_100").agg(
        pl.col("fumble_lost").sum().alias("muffed"),
        pl.col("blocked").sum().alias("blocked"),
        pl.col("return_td").sum().alias("return_td"),
        pl.len().alias("n"),
    ).with_columns(bin_expr.alias("bin"))
    per_bin = per_yl.group_by("bin").agg(
        pl.col("muffed").sum().alias("b_muffed"),
        pl.col("blocked").sum().alias("b_blocked"),
        pl.col("return_td").sum().alias("b_td"),
        pl.col("n").sum().alias("b_n"),
    ).with_columns(
        (pl.col("b_muffed") / pl.col("b_n")).alias("bin_muffed_pct"),
        (pl.col("b_blocked") / pl.col("b_n")).alias("bin_blocked_pct"),
        (pl.col("b_td") / pl.col("b_n")).alias("bin_td_pct"),
    )
    outliers = per_yl.join(per_bin, on="bin", how="left").select(
        "yardline_100", "bin_muffed_pct", "bin_blocked_pct", "bin_td_pct"
    )

    # NOTE: matches the R column swap exactly — return_tds carries bin_blocked_pct,
    # blocks carries bin_td_pct (the original script transposed these labels).
    return_tds = outliers.filter(pl.col("bin_blocked_pct") > 0).select(
        "yardline_100",
        pl.lit(100.0).alias("yardline_after"),
        pl.col("bin_blocked_pct").alias("density"),
    )
    blocks = outliers.filter(pl.col("bin_td_pct") > 0).select(
        "yardline_100",
        pl.lit(999.0).alias("yardline_after"),
        pl.col("bin_td_pct").alias("density"),
    )

    # KDE over non-blocked / non-td landings
    normal = points.filter((pl.col("blocked") == 0) & (pl.col("return_td") == 0)).select(
        "yardline_100", "yardline_after"
    )
    dens = _kde2d_density(
        normal["yardline_100"].to_numpy().astype(float),
        normal["yardline_after"].to_numpy().astype(float),
    )
    normal = normal.with_columns(pl.Series("density", dens))

    # Normalize the NORMAL landings to pct = density / sum(density) per yardline
    # (the R does this BEFORE binding the outlier rows). Outlier rows then carry
    # pct = their raw block/td density.
    normal_u = normal.unique(subset=["yardline_100", "yardline_after"], keep="first")
    tot = normal_u.group_by("yardline_100").agg(pl.col("density").sum().alias("tot"))
    normal_u = normal_u.join(tot, on="yardline_100", how="left").with_columns(
        (pl.col("density") / pl.col("tot")).alias("pct")
    ).drop("tot")

    outlier_rows = pl.concat(
        [
            return_tds.select("yardline_100", "yardline_after", "density"),
            blocks.select("yardline_100", "yardline_after", "density"),
        ],
        how="vertical",
    ).with_columns(pl.col("density").alias("pct"))  # outliers: pct = raw density

    dmap = pl.concat(
        [normal_u.select("yardline_100", "yardline_after", "density", "pct"), outlier_rows],
        how="vertical",
    )

    # outlier_pct per yardline = sum of raw densities of the 100 / 999 rows; rescale
    # the normal pct by (1 - outlier_pct). Outlier rows keep pct == density.
    out_pct = dmap.filter(pl.col("yardline_after").is_in([100.0, 999.0])).group_by(
        "yardline_100"
    ).agg(pl.col("density").sum().alias("outlier_pct"))
    dmap = dmap.join(out_pct, on="yardline_100", how="left").with_columns(
        pl.col("outlier_pct").fill_null(0.0)
    ).with_columns(
        pl.when(pl.col("yardline_after").is_in([100.0, 999.0]))
        .then(pl.col("pct"))
        .otherwise(pl.col("pct") * (1.0 - pl.col("outlier_pct")))
        .alias("pct")
    )
    # 999 -> yardline_100 (blocked punt: ball spotted at the LOS)
    dmap = dmap.with_columns(
        pl.when(pl.col("yardline_after") == 999.0)
        .then(pl.col("yardline_100"))
        .otherwise(pl.col("yardline_after"))
        .alias("yardline_after")
    )

    dmap = dmap.join(
        outliers.unique(subset=["yardline_100"]).select("yardline_100", "bin_muffed_pct"),
        on="yardline_100",
        how="left",
    ).select("yardline_100", "yardline_after", "pct", "bin_muffed_pct").filter(
        pl.col("yardline_100") > 30
    )

    # duplicate rows for muff in {0,1}: muff=1 only for non-block / non-td rows.
    muff0 = dmap.with_columns(pl.lit(0).alias("muff"))
    muff1 = dmap.filter(
        (pl.col("yardline_after") != 100.0)
        & (pl.col("yardline_100") != pl.col("yardline_after"))
    ).with_columns(pl.lit(1).alias("muff"))
    both = pl.concat([muff0, muff1], how="vertical")

    is_normal = (pl.col("yardline_after") != 100.0) & (
        pl.col("yardline_100") != pl.col("yardline_after")
    )
    bmp = pl.col("bin_muffed_pct").fill_null(0.0)
    both = both.with_columns(
        pl.when(pl.col("muff") == 1)
        .then(bmp * pl.col("pct"))
        .when((pl.col("muff") == 0) & is_normal)
        .then((1.0 - bmp) * pl.col("pct"))
        .otherwise(pl.col("pct"))
        .alias("pct")
    )

    # renormalize per yardline
    tot2 = both.group_by("yardline_100").agg(pl.col("pct").sum().alias("tot2"))
    both = both.join(tot2, on="yardline_100", how="left").with_columns(
        (pl.col("pct") / pl.col("tot2")).alias("pct")
    )

    out = both.select(
        "yardline_100",
        pl.col("yardline_after").cast(pl.Float64),
        pl.col("pct").cast(pl.Float64),
        pl.col("muff").cast(pl.Float64),
    ).sort(["yardline_100", "yardline_after", "muff"])

    if output_path is not None:
        out.write_parquet(str(output_path))
    return out
