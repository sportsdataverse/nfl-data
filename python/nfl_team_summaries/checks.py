"""Output-side gates: a transform that fails to transform must not pass.

Same discipline as ``cfbfastR-cfb-data``'s ``checks.py`` (the ridge no-op that
shipped green for two days). Thresholds here are NFL-scale: 32 teams, not 134.
"""

from __future__ import annotations

import numpy as np
import polars as pl

#: corr(adjusted, raw) above which the opponent adjustment did nothing.
#: 32 teams of near-parity schedules adjust LESS than college (measured 2025
#: build: adj_off_epa vs EPAplay_off corr 0.9x); the no-op is 0.999+, so the
#: bar sits just under it rather than at college's 0.95.
NOOP_CORR_THRESHOLD = 0.995
MIN_ROWS = 20

ADJUSTMENT_PAIRS = (("adj_off_epa", "EPAplay_off"), ("adj_def_epa", "EPAplay_def"))


def adjustment_report(df: pl.DataFrame) -> dict[str, float]:
    out: dict[str, float] = {}
    for adj, raw in ADJUSTMENT_PAIRS:
        if adj not in df.columns or raw not in df.columns:
            continue
        d = df.select(adj, raw).drop_nulls()
        if d.height < MIN_ROWS:
            continue
        x, y = d[adj].to_numpy(), d[raw].to_numpy()
        out[adj] = float("nan") if x.std() == 0 or y.std() == 0 else float(np.corrcoef(x, y)[0, 1])
    return out


def assert_adjustment_is_real(df: pl.DataFrame, *, label: str = "") -> dict[str, float]:
    rep = adjustment_report(df)
    bad = {k: v for k, v in rep.items() if v == v and v > NOOP_CORR_THRESHOLD}
    if bad:
        detail = ", ".join(f"{k} vs raw corr={v:.4f}" for k, v in bad.items())
        raise ValueError(
            f"opponent adjustment is a NO-OP in {label}: {detail} (threshold {NOOP_CORR_THRESHOLD})"
        )
    return rep


def assert_passer_identity(df: pl.DataFrame, *, label: str = "") -> None:
    """``TEPA == EPAplay * dropbacks`` for every passer, and no inf/NaN anywhere.

    The identity is what breaks when the numerator and the denominator span
    different play sets (cfbfastR-cfb-data#30). It costs nothing and it caught
    a 2.8x error there.
    """
    if df.height == 0:
        raise ValueError(f"passing {label} is EMPTY")
    off = df.with_columns(
        _resid=(pl.col("TEPA") - pl.col("EPAplay") * pl.col("dropbacks")).abs()
        - 1e-6 * (1 + pl.col("TEPA").abs())
    ).filter(pl.col("_resid") > 0)
    if off.height:
        w = off.sort("_resid", descending=True).row(0, named=True)
        raise ValueError(
            f"passing {label}: TEPA != EPAplay * dropbacks for {off.height} passer(s); worst "
            f"{w.get('passer_player_name')}: TEPA={w['TEPA']:.3f} vs {w['EPAplay'] * w['dropbacks']:.3f}"
        )
    assert_finite(df, label=f"passing {label}")


def assert_finite(df: pl.DataFrame, *, label: str = "") -> None:
    """No inf/NaN in any float column -- a zero denominator reached the output."""
    for col, dtype in df.schema.items():
        if dtype not in (pl.Float64, pl.Float32):
            continue
        s = df[col]
        n_bad = int((s.is_nan() | s.is_infinite()).sum())
        if n_bad:
            raise ValueError(f"{label}: {col} has {n_bad} inf/NaN value(s)")
