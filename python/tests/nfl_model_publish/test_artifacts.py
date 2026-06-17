"""Hermetic tests for nfl_model_publish.artifacts.

Network-free: every test injects runner/exists_check stubs so no gh calls are made.
"""
from __future__ import annotations

import json

from nfl_model_publish.artifacts import plan_uploads, upload_artifacts


# ---------------------------------------------------------------------------
# Fixture seeder
# ---------------------------------------------------------------------------

def _seed(tmp_path):
    """Create two .ubj models with their .json card sidecars."""
    (tmp_path / "ep.ubj").write_bytes(b"ep-model-bytes")
    (tmp_path / "ep.json").write_text(json.dumps({"model_type": "ep"}))
    (tmp_path / "wp_spread.ubj").write_bytes(b"wp-spread-model-bytes")
    (tmp_path / "wp_spread.json").write_text(json.dumps({"model_type": "wp_spread"}))
    return tmp_path


def _boom(*_a, **_k):
    raise AssertionError("should not be called in this test")


# ---------------------------------------------------------------------------
# plan_uploads
# ---------------------------------------------------------------------------

def test_plan_uploads_lists_models_and_cards(tmp_path):
    files = {p.name for p in plan_uploads(_seed(tmp_path))}
    assert files == {"ep.ubj", "ep.json", "wp_spread.ubj", "wp_spread.json"}


def test_plan_uploads_skips_missing_card(tmp_path):
    """A model without a sidecar card should still appear (just no card)."""
    (tmp_path / "cp.ubj").write_bytes(b"cp-bytes")
    # no cp.json
    files = {p.name for p in plan_uploads(tmp_path)}
    assert "cp.ubj" in files
    assert "cp.json" not in files


def test_plan_uploads_empty_dir(tmp_path):
    assert plan_uploads(tmp_path) == []


# ---------------------------------------------------------------------------
# dry_run — network-free, exists_check must NOT be called
# ---------------------------------------------------------------------------

def test_dry_run_uploads_nothing(tmp_path):
    calls = []
    res = upload_artifacts(
        _seed(tmp_path),
        "nfl_model_artifacts",
        "owner/repo",
        dry_run=True,
        runner=lambda args: calls.append(args),
        exists_check=_boom,  # must not be called
    )
    assert res["uploaded"] == 0
    assert len(res["files"]) == 4
    assert calls == []
    assert res["created_release"] is False


# ---------------------------------------------------------------------------
# create-when-missing — first runner call must be release create
# ---------------------------------------------------------------------------

def test_creates_release_when_missing(tmp_path):
    calls = []
    res = upload_artifacts(
        _seed(tmp_path),
        "nfl_model_artifacts",
        "owner/repo",
        dry_run=False,
        runner=lambda args: calls.append(args),
        exists_check=lambda tag, repo: False,
    )
    assert calls[0][:4] == ["release", "create", "nfl_model_artifacts", "--repo"]
    assert res["created_release"] is True
    # 1 create + 4 uploads
    assert len(calls) == 5
    assert res["uploaded"] == 4


# ---------------------------------------------------------------------------
# skip-when-present — no release create call
# ---------------------------------------------------------------------------

def test_skips_create_when_present(tmp_path):
    calls = []
    res = upload_artifacts(
        _seed(tmp_path),
        "nfl_model_artifacts",
        "owner/repo",
        dry_run=False,
        runner=lambda args: calls.append(args),
        exists_check=lambda tag, repo: True,
    )
    assert res["created_release"] is False
    assert all(c[:2] != ["release", "create"] for c in calls)
    assert res["uploaded"] == 4
    assert len(calls) == 4


# ---------------------------------------------------------------------------
# return dict contract
# ---------------------------------------------------------------------------

def test_upload_result_keys(tmp_path):
    res = upload_artifacts(
        _seed(tmp_path),
        "nfl_model_artifacts",
        "owner/repo",
        dry_run=True,
        runner=lambda args: None,
        exists_check=_boom,
    )
    assert set(res.keys()) == {"uploaded", "files", "tag", "created_release"}
    assert res["tag"] == "nfl_model_artifacts"
