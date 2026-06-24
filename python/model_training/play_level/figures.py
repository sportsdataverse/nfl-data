"""Model figures for NFL EP/WP/CP — cfbfastR-style calibration plots + nflfastR
signature curves.

Two families:
  * ``write_calibration`` — binned reliability plot in the bespoke cfbfastR garnet
    style (faceted by ``by``, sized points, smoother, y=x reference), emitting
    PNG + CSV + Parquet sidecars. Same contract as the cfbfastR suite's
    ``model_training.figures.write_calibration``.
  * ``plot_ep_by_yardline`` / ``plot_cp_by_air_yards`` — the two recognizable
    nflfastR README figures (EP by yardline × down; completion % by air yards ×
    pass direction), reproduced from the native models' predictions.

plotnine is imported lazily so the module loads without the ``figures`` dependency
group; the loess smoother falls back to ``lm`` when ``scikit-misc`` is absent.
"""
from __future__ import annotations

from pathlib import Path

import polars as pl

GARNET = "#500f1b"
GREY95 = "#f2f2f2"
GREY99 = "#fcfcfc"
FONT = ["Gill Sans MT", "DejaVu Sans", "sans-serif"]


def _smoother() -> str:
    try:
        import skmisc  # noqa: F401

        return "loess"
    except ModuleNotFoundError:
        return "lm"


def _save_with_fallback(build, png: Path) -> None:
    """Render a plot, falling back from the loess smoother to ``lm`` on failure.

    ``build(method)`` returns a fresh ggplot using the given smoother. loess can
    hit local-regression singularities on near-degenerate facets; ``lm`` is a safe
    fallback so a single bad facet never crashes report generation.
    """
    method = _smoother()
    try:
        build(method).save(png, width=6, height=4, dpi=200, verbose=False)
    except Exception:  # noqa: BLE001
        if method == "lm":
            raise
        build("lm").save(png, width=6, height=4, dpi=200, verbose=False)


def write_calibration(
    table: pl.DataFrame,
    stem: Path | str,
    title: str,
    subtitle: str,
    cal_error: float,
) -> tuple[Path, Path]:
    """Render a calibration/reliability plot + write CSV/Parquet sidecars.

    Args:
        table: Calibration frame with columns ``by``, ``bin``, ``n_plays``,
            ``actual`` (from :func:`metrics.calibration_table`).
        stem: Output path stem; ``<stem>.png/.csv/.parquet`` are written.
        title: Plot title.
        subtitle: Plot subtitle (e.g. ``"LOSO 2016-2024"``).
        cal_error: Overall weighted calibration error, shown in the caption.

    Returns:
        ``(png_path, csv_path)``.
    """
    from plotnine import (
        aes, element_rect, element_text, facet_wrap, geom_abline,
        geom_point, geom_smooth, ggplot, labs, theme, theme_bw,
    )

    stem = Path(stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    csv, png = stem.with_suffix(".csv"), stem.with_suffix(".png")
    table.write_csv(csv)
    table.write_parquet(stem.with_suffix(".parquet"))
    pdf = table.to_pandas()

    def _build(method):
        return (
            ggplot(pdf, aes("bin", "actual"))
            + geom_abline(slope=1, intercept=0, linetype="dashed", color="black")
            + geom_point(aes(size="n_plays"), color=GARNET)
            + geom_smooth(method=method, se=False, color=GARNET, size=0.5)
            + facet_wrap("~by")
            + labs(title=title, subtitle=subtitle,
                   caption=f"Overall weighted calibration error: {cal_error:.4f}",
                   x="Estimated probability", y="Observed probability", size="Plays")
            + theme_bw()
            + theme(text=element_text(family=FONT),
                    plot_background=element_rect(fill=GREY99, color="black"),
                    panel_background=element_rect(fill=GREY95),
                    legend_position="bottom")
        )

    _save_with_fallback(_build, png)
    return png, csv


def plot_ep_by_yardline(df: pl.DataFrame, stem: Path | str) -> tuple[Path, Path]:
    """nflfastR signature: Expected Points by yardline × down (smoothed curves).

    Args:
        df: Frame with ``yardline_100``, ``ep`` (model-predicted EP), and ``down``
            (1-4). Non-scrimmage rows (null down) are dropped.
        stem: Output stem; ``<stem>.png/.csv`` written.

    Returns:
        ``(png_path, csv_path)``.
    """
    from plotnine import (
        aes, element_rect, element_text, geom_smooth, ggplot, labs, scale_x_reverse,
        theme, theme_bw,
    )

    stem = Path(stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    csv, png = stem.with_suffix(".csv"), stem.with_suffix(".png")
    d = df.drop_nulls(["yardline_100", "ep", "down"]).filter(pl.col("down").is_in([1, 2, 3, 4]))
    d = d.with_columns(pl.col("down").cast(pl.Int64).cast(pl.Utf8).alias("Down"))
    pdf = d.select(["yardline_100", "ep", "Down"]).to_pandas()
    d.select(["yardline_100", "ep", "Down"]).write_csv(csv)

    def _build(method):
        return (
            ggplot(pdf, aes("yardline_100", "ep", color="Down"))
            + geom_smooth(method=method, se=False)
            + scale_x_reverse()
            + labs(title="Expected Points by Yardline and Down",
                   subtitle="Native nfl/raw EP model",
                   x="Yards from opponent end zone", y="Expected points", color="Down")
            + theme_bw()
            + theme(text=element_text(family=FONT),
                    plot_background=element_rect(fill=GREY99, color="black"),
                    panel_background=element_rect(fill=GREY95),
                    legend_position="bottom")
        )

    _save_with_fallback(_build, png)
    return png, csv


def plot_cp_by_air_yards(df: pl.DataFrame, stem: Path | str) -> tuple[Path, Path]:
    """nflfastR signature: Completion % by air yards × pass direction (smoothed).

    Args:
        df: Frame with ``air_yards``, ``cp`` (model-predicted completion prob), and
            ``pass_middle`` (1 = middle, 0 = outside). air_yards is clamped to
            [-5, 45] to match the nflfastR figure range.
        stem: Output stem; ``<stem>.png/.csv`` written.

    Returns:
        ``(png_path, csv_path)``.
    """
    from plotnine import (
        aes, element_rect, element_text, geom_smooth, ggplot, labs, theme, theme_bw,
    )

    stem = Path(stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    csv, png = stem.with_suffix(".csv"), stem.with_suffix(".png")
    d = (
        df.drop_nulls(["air_yards", "cp", "pass_middle"])
        .filter((pl.col("air_yards") >= -5) & (pl.col("air_yards") <= 45))
        .with_columns(
            pl.when(pl.col("pass_middle") == 1).then(pl.lit("Middle"))
            .otherwise(pl.lit("Outside")).alias("Pass direction")
        )
    )
    pdf = d.select(["air_yards", "cp", "Pass direction"]).to_pandas()
    d.select(["air_yards", "cp", "Pass direction"]).write_csv(csv)

    def _build(method):
        return (
            ggplot(pdf, aes("air_yards", "cp", color="Pass direction"))
            + geom_smooth(method=method, se=False)
            + labs(title="Expected Completion % by Air Yards and Pass Direction",
                   subtitle="Native nfl/raw CP model",
                   x="Air yards", y="Expected completion %", color="Pass direction")
            + theme_bw()
            + theme(text=element_text(family=FONT),
                    plot_background=element_rect(fill=GREY99, color="black"),
                    panel_background=element_rect(fill=GREY95),
                    legend_position="bottom")
        )

    _save_with_fallback(_build, png)
    return png, csv
