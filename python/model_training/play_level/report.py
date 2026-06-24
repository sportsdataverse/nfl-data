"""End-to-end model report: LOSO calibration + figures + metrics, written to disk.

Ties the reporting layer together (the cfbfastR-suite house style):
  LOSO (loso.py) -> calibration tables + weighted cal error (metrics.py)
  -> calibration plots + nflfastR signature curves (figures.py)
  -> a metrics JSON + a human-readable markdown report.

Figures require the ``figures`` dependency group (plotnine); when it is missing
the data tables + metrics still write and figure generation is skipped with a note.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import polars as pl

from .constants import EP_CLASS_ORDER
from .loso import loso_cp, loso_ep, loso_wp
from .metrics import brier_score, calibration_table, weighted_cal_error
from .pipeline import _resolve_pbp


def _ep_class_calibration(ep_cv: pl.DataFrame) -> pl.DataFrame:
    """Per next-score-class reliability table for the 7-class EP softprob.

    Unpivots the per-class predicted probabilities (``p_<class>``) to long form and
    bins each class's predicted probability against whether that class was the
    realized next score — the nflfastR/cfbscrapR 7-facet EP calibration. This is a
    probability-scale (0-1) check, so unlike the points-scale scalar EP calibration
    it is insensitive to the absolute level of the next-score label.
    """
    if ep_cv.is_empty():
        return ep_cv
    cls_to_idx = {c: i for i, c in enumerate(EP_CLASS_ORDER)}
    long = (
        ep_cv.unpivot(
            index=["actual_class"],
            on=[f"p_{c}" for c in EP_CLASS_ORDER],
            variable_name="class",
            value_name="pred_prob",
        )
        .with_columns(pl.col("class").str.replace("^p_", ""))
        .with_columns(
            is_actual=(
                pl.col("actual_class") == pl.col("class").replace_strict(cls_to_idx, return_dtype=pl.Int64)
            ).cast(pl.Int64)
        )
    )
    return calibration_table(long, "pred_prob", "is_actual", by="class", bin_size=0.05, min_plays=50)


def run_report(
    seasons: List[int],
    *,
    source: str = "native",
    out_dir: Path = Path("reports"),
    data_dir: Path = Path("data"),
    nrounds: Optional[int] = None,
    make_figures: bool = True,
) -> Dict[str, Any]:
    """Build the EP/WP/CP LOSO calibration report (tables + figures + metrics).

    Args:
        seasons: Seasons to evaluate (LOSO folds over these).
        source: ``native`` (nfl/raw) or ``nflverse``.
        out_dir: Directory for figures, calibration tables, metrics.json, report.md.
        data_dir: PBP parquet cache (nflverse source only).
        nrounds: Per-fold boosting rounds (pass a small value for a quick pass;
            None = canonical production counts).
        make_figures: Render PNGs (needs the ``figures`` group); tables/metrics
            always write.

    Returns:
        The metrics dict (also written to ``out_dir/metrics.json``).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    df = _resolve_pbp(seasons, Path(data_dir), download=False, source=source)
    lo, hi = min(seasons), max(seasons)
    span = f"{lo}-{hi}"

    # --- LOSO out-of-sample predictions ---
    ep_cv = loso_ep(df, seasons=seasons, nrounds=nrounds)
    wp_cv = loso_wp(df, seasons=seasons, nrounds=nrounds)
    cp_cv = loso_cp(df, seasons=seasons, nrounds=nrounds)

    # --- calibration tables + weighted cal error ---
    ep_cal = calibration_table(ep_cv, "pred_ep", "actual_points", bin_size=0.5, min_plays=50)
    wp_cal = calibration_table(wp_cv, "pred_wp", "wp_label", bin_size=0.05)
    cp_cal = calibration_table(cp_cv, "pred_cp", "complete_pass", by="air_yards_bucket", bin_size=0.05)
    ep_class_cal = _ep_class_calibration(ep_cv)
    ep_class_wce = weighted_cal_error(ep_class_cal) if ep_class_cal.height else {"overall": None, "per_group": []}

    metrics: Dict[str, Any] = {
        "source": source,
        "seasons": [lo, hi],
        "generated": date.today().isoformat(),
        "nrounds": nrounds,
        "ep": {
            "cal_error": weighted_cal_error(ep_cal)["overall"],
            "class_cal_error": ep_class_wce["overall"],
            "class_cal_per": ep_class_wce["per_group"],
            "n": ep_cv.height,
        },
        "wp": {
            "cal_error": weighted_cal_error(wp_cal)["overall"],
            "brier": brier_score(wp_cv["wp_label"].to_numpy(), wp_cv["pred_wp"].to_numpy()) if wp_cv.height else None,
            "n": wp_cv.height,
        },
        "cp": {
            "cal_error": weighted_cal_error(cp_cal),
            "brier": brier_score(cp_cv["complete_pass"].to_numpy(), cp_cv["pred_cp"].to_numpy())
            if cp_cv.height
            else None,
            "n": cp_cv.height,
        },
    }

    figs: Dict[str, str] = {}
    if make_figures:
        try:
            from .figures import plot_cp_by_air_yards, plot_ep_by_yardline, write_calibration

            write_calibration(
                ep_cal,
                out_dir / "ep_calibration",
                "EP calibration",
                f"LOSO {span} ({source})",
                metrics["ep"]["cal_error"],
            )
            if ep_class_cal.height:
                write_calibration(
                    ep_class_cal,
                    out_dir / "ep_class_calibration",
                    "Expected Points — calibration by next-score class",
                    f"LOSO {span} ({source}) · predicted class prob vs empirical rate",
                    ep_class_wce["overall"],
                )
            write_calibration(
                wp_cal,
                out_dir / "wp_calibration",
                "WP calibration",
                f"LOSO {span} ({source})",
                metrics["wp"]["cal_error"],
            )
            write_calibration(
                cp_cal,
                out_dir / "cp_calibration",
                "CP calibration by air-yards bucket",
                f"LOSO {span} ({source})",
                metrics["cp"]["cal_error"]["overall"],
            )
            plot_ep_by_yardline(ep_cv.rename({"pred_ep": "ep"}), out_dir / "ep_by_yardline")
            plot_cp_by_air_yards(cp_cv.rename({"pred_cp": "cp"}), out_dir / "cp_by_air_yards")
            figs = {
                "ep_calibration": "ep_calibration.png",
                "ep_class_calibration": "ep_class_calibration.png",
                "wp_calibration": "wp_calibration.png",
                "cp_calibration": "cp_calibration.png",
                "ep_by_yardline": "ep_by_yardline.png",
                "cp_by_air_yards": "cp_by_air_yards.png",
            }
        except ModuleNotFoundError:
            metrics["figures_skipped"] = "plotnine not installed (uv sync --group figures)"

    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (out_dir / "report.md").write_text(_render_markdown(metrics, figs, span, source), encoding="utf-8")
    return metrics


def _render_markdown(metrics: Dict[str, Any], figs: Dict[str, str], span: str, source: str) -> str:
    cp_buckets = "\n".join(f"  - {b['by']}: {b['wce']:.4f} (n={b['n']:,})" for b in weighted_cal_error_rows(metrics))
    lines = [
        f"# NFL EP/WP/CP model report — {span} ({source})",
        "",
        f"Generated {metrics['generated']} · LOSO cross-validation · "
        f"per-fold nrounds={metrics['nrounds'] or 'canonical'}",
        "",
        "## Calibration (leave-one-season-out)",
        "",
        "| Model | Weighted cal error | Brier | Plays |",
        "|---|---|---|---|",
        f"| EP | {metrics['ep']['cal_error']:.4f} | — | {metrics['ep']['n']:,} |",
        f"| WP | {metrics['wp']['cal_error']:.4f} | {metrics['wp']['brier']:.4f} | {metrics['wp']['n']:,} |",
        f"| CP | {metrics['cp']['cal_error']['overall']:.4f} | {metrics['cp']['brier']:.4f} | {metrics['cp']['n']:,} |",
        "",
        "CP weighted cal error by air-yards bucket:",
        cp_buckets or "  (n/a)",
        "",
    ]
    if figs:
        lines += ["## Figures", ""]
        lines += [f"- ![{k}]({v})" for k, v in figs.items()]
    else:
        lines += ["_Figures skipped (install the `figures` dependency group)._"]
    return "\n".join(lines) + "\n"


def weighted_cal_error_rows(metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
    return metrics["cp"]["cal_error"].get("per_group", [])
