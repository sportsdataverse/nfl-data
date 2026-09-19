"""Offline tests for the report-only QA stage (``nfl_espn_build.qa``).

Real inputs only: the vendored one-game fixture for the per-game gate, and two
real season frames cut from it for the drift gate. No network -- the published
comparison frame is passed in directly rather than downloaded.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest
from nfl_espn_build import build, process, qa
from nfl_espn_build.cli import main
from nfl_espn_build.config import REGISTRY, processing_version

FIX = Path(__file__).parent / "fixtures" / "espn_nfl"
EVENT = 401772510
FIXTURE_LINES = {"401772510": (8.5, 47.5), "2025_01_DAL_PHI": (8.5, 47.5)}


@pytest.fixture(scope="module")
def qa_built(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setattr(process, "schedule_lines", lambda season: FIXTURE_LINES if season == 2025 else {})
    mp.setattr(qa, "published_frame", lambda *a, **k: None)  # no release to diff against
    root = tmp_path_factory.mktemp("qa")
    cache, out = root / "cache", root / "out"
    rc = main(
        # pbp first: the drift gate reads the season pbp parquet
        [
            "--dataset",
            "pbp",
            "-s",
            "2025",
            "--raw-dir",
            str(FIX),
            "--cache-dir",
            str(cache),
            "--out",
            str(out),
            "--workers",
            "1",
        ]
    )
    assert rc == 0
    rc = main(
        [
            "--dataset",
            "qa",
            "-s",
            "2025",
            "--raw-dir",
            str(FIX),
            "--cache-dir",
            str(cache),
            "--out",
            str(out),
            "--workers",
            "1",
        ]
    )
    assert rc == 0
    yield cache, out
    mp.undo()


def test_qa_row_shape_and_identity(qa_built):
    _, out = qa_built
    df = pl.read_parquet(build.output_path(REGISTRY["qa"], 2025, out))
    assert df.height == 1
    assert set(qa.QA_SCHEMA) <= set(df.columns)
    assert {"week", "season_type", "nflverse_game_id"} <= set(df.columns)
    row = df.row(0, named=True)
    assert row["game_id"] == EVENT and row["season"] == 2025
    assert row["league"] == "nfl" and row["source"] == "espn"
    assert row["processing_version"] == processing_version()
    assert row["n_rows"] > 100
    assert row["ok"] == (row["n_errors"] == 0)
    # the id columns are flat strings so parquet / csv / rds share one schema
    assert df.schema["failed_rule_ids"] == pl.Utf8
    assert row["failed_rule_ids"].count(",") + 1 == row["n_errors"] or not row["n_errors"]


def test_qa_row_is_cached_in_the_final_not_recomputed(qa_built):
    cache, _ = qa_built
    final = process.read_final(process.final_path(cache, 2025, EVENT))
    assert final["qa"]["game_id"] == EVENT
    # a cached row is returned verbatim
    final["qa"]["n_errors"] = 999
    assert qa.game_qa_row(final, processing_version="x")["n_errors"] == 999


def test_qa_row_falls_back_for_a_final_that_predates_the_stage(qa_built):
    cache, _ = qa_built
    final = process.read_final(process.final_path(cache, 2025, EVENT))
    cached = dict(final["qa"])
    final.pop("qa")
    fresh = qa.game_qa_row(final, processing_version=processing_version())
    assert fresh["game_id"] == cached["game_id"]
    assert fresh["n_errors"] == cached["n_errors"]
    assert fresh["failed_rule_ids"] == cached["failed_rule_ids"]


def test_season_summary_sidecar(qa_built):
    _, out = qa_built
    path = qa.summary_path(build.output_path(REGISTRY["qa"], 2025, out))
    s = json.loads(path.read_text())
    assert s["games"] == 1 and s["season"] == 2025
    assert s["error_free_share"] in (0.0, 1.0)
    assert s["max_error_share"] == qa.MAX_ERROR_SHARE
    assert s["blocking"] is False, "V2 ships report-only"
    assert s["threshold_exceeded"] is (s["error_share"] > qa.MAX_ERROR_SHARE)
    assert isinstance(s["counts_by_rule"], dict) and s["drift"] == []


def test_drift_gate_reports_schema_null_constant_and_mean_shift(qa_built):
    _, out = qa_built
    new = pl.read_parquet(build.output_path(REGISTRY["pbp"], 2025, out))
    assert new.height > 100
    # a "previous release" built from the same real season: one column dropped,
    # one retyped, and a numeric column whose mean is half of this one's
    prev = (
        new.drop("period")
        .with_columns(
            pl.col("game_id").cast(pl.Utf8),
            (pl.col("EPA") * 0.5).alias("EPA"),
            pl.lit(None, dtype=pl.Utf8).alias("gone_constant"),
        )
        .with_columns(
            pl.Series("gone_constant", ["a", "b"] * (new.height // 2) + ["a"] * (new.height % 2))
        )
    )
    new = new.with_columns(pl.lit("only", dtype=pl.Utf8).alias("gone_constant"))
    found = qa.drift_findings(new, prev)
    by = {(f["check"], f["locator"].get("column")) for f in found}
    assert ("schema_contract", "period") in by  # new column vs the release
    assert ("schema_contract", "game_id") in by  # dtype change on a join key
    assert ("constant_column", "gone_constant") in by
    assert ("rate_anomaly", "EPA") in by
    assert all(f["severity"] in ("error", "warn") for f in found)
    assert qa.drift_findings(new, None) == []  # a first publish has nothing to drift from
