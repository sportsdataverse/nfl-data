"""Figures (plotnine-gated) + full report (heavy-gated) tests."""
from __future__ import annotations

import os

import polars as pl
import pytest


def test_figures_write_calibration_and_curves(tmp_path):
    pytest.importorskip("plotnine")
    from model_training.track6_nfl_ep_wp.figures import (
        plot_cp_by_air_yards,
        plot_ep_by_yardline,
        write_calibration,
    )

    cal = pl.DataFrame({"by": ["All"] * 5, "bin": [0.1, 0.3, 0.5, 0.7, 0.9],
                        "n_plays": [100, 200, 300, 200, 100], "actual": [0.12, 0.28, 0.51, 0.69, 0.93]})
    png, csv = write_calibration(cal, tmp_path / "wp_cal", "WP", "LOSO", 0.012)
    assert png.exists() and csv.exists() and (tmp_path / "wp_cal.parquet").exists()

    yl = list(range(1, 100)) * 4
    ep = pl.DataFrame({
        "yardline_100": yl,
        "ep": [6.0 - 0.05 * y for y in yl],            # gradient so loess can fit
        "down": [1] * 99 + [2] * 99 + [3] * 99 + [4] * 99,
    })
    p2, _ = plot_ep_by_yardline(ep, tmp_path / "ep_yl")
    assert p2.exists()

    ay = list(range(-5, 46)) * 2
    cp = pl.DataFrame({
        "air_yards": ay,
        "cp": [max(0.05, 0.9 - 0.012 * a) for a in ay],  # gradient
        "pass_middle": [1] * 51 + [0] * 51,
    })
    p3, _ = plot_cp_by_air_yards(cp, tmp_path / "cp_ay")
    assert p3.exists()


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("NFL_PARITY_TESTS") != "1",
                    reason="set NFL_PARITY_TESTS=1 (builds native seasons + LOSO trains)")
def test_run_report_end_to_end(tmp_path):
    import json

    from model_training.track6_nfl_ep_wp.report import run_report

    metrics = run_report([2023, 2024], source="native", out_dir=tmp_path,
                         nrounds=30, make_figures=False)
    assert (tmp_path / "metrics.json").exists()
    assert (tmp_path / "report.md").exists()
    saved = json.loads((tmp_path / "metrics.json").read_text())
    assert saved["source"] == "native" and saved["seasons"] == [2023, 2024]
    # Calibration errors are finite and WP Brier is in a sane range.
    assert metrics["ep"]["cal_error"] == metrics["ep"]["cal_error"]  # not NaN
    assert 0.0 <= metrics["wp"]["brier"] <= 0.30
