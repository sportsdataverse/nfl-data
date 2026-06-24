"""Hermetic tests for nfl_model_publish.decision_models_artifacts.

Network-free: every test injects runner/exists_check stubs (no gh calls) and
seeds fake artifact files (no training). Verifies the release routing
(xpass->model_artifacts, fd+wp->4th_down_models), the sdv-py bundle copy
(two_pt/fg/punt), dry-run safety, and the digest reporting.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from nfl_model_publish.decision_models_artifacts import (
    TRACK7_BUNDLE_ARTIFACTS,
    TRACK7_RELEASE_MAP,
    artifact_digest,
    plan_decision_models_artifacts,
    publish_decision_models_artifacts,
)


def _seed(tmp_path: Path) -> Path:
    """Seed all six decision_models artifacts with distinct fake bytes."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "xpass_model.ubj").write_bytes(b"xpass-bytes")
    (tmp_path / "fd_model.ubj").write_bytes(b"fd-bytes")
    (tmp_path / "wp_model.ubj").write_bytes(b"wp-model-bytes")
    (tmp_path / "two_pt_model.ubj").write_bytes(b"two-pt-bytes")
    (tmp_path / "fg_model.ubj").write_bytes(b"fg-bytes")
    (tmp_path / "punt_data.parquet").write_bytes(b"punt-parquet-bytes")
    return tmp_path


def _boom(*_a, **_k):
    raise AssertionError("should not be called in this test")


# ---------------------------------------------------------------------------
# digest + plan
# ---------------------------------------------------------------------------
def test_artifact_digest(tmp_path: Path):
    p = tmp_path / "m.ubj"
    p.write_bytes(b"abc")
    d = artifact_digest(p)
    assert d["name"] == "m.ubj"
    assert d["size_bytes"] == 3
    # sha256("abc")
    assert d["sha256"] == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_plan_routes_uploads_and_bundle(tmp_path: Path):
    plan = plan_decision_models_artifacts(_seed(tmp_path))
    up = {u["name"]: u["tag"] for u in plan["uploads"]}
    assert up == {
        "xpass_model.ubj": "nfl_model_artifacts",
        "fd_model.ubj": "nfl_4th_down_models",
        "wp_model.ubj": "nfl_4th_down_models",
    }
    bundle = {b["name"] for b in plan["bundle"]}
    assert bundle == set(TRACK7_BUNDLE_ARTIFACTS)
    assert plan["missing"] == []


def test_plan_reports_missing(tmp_path: Path):
    (tmp_path / "xpass_model.ubj").write_bytes(b"x")
    plan = plan_decision_models_artifacts(tmp_path)
    assert {u["name"] for u in plan["uploads"]} == {"xpass_model.ubj"}
    # everything else is missing
    expected_missing = set(TRACK7_RELEASE_MAP) | set(TRACK7_BUNDLE_ARTIFACTS)
    expected_missing.discard("xpass_model.ubj")
    assert set(plan["missing"]) == expected_missing


# ---------------------------------------------------------------------------
# dry-run — network + filesystem safe
# ---------------------------------------------------------------------------
def test_dry_run_uploads_nothing_and_no_copy(tmp_path: Path):
    out = _seed(tmp_path / "out")
    bundle = tmp_path / "bundle"
    calls = []
    res = publish_decision_models_artifacts(
        out,
        "owner/repo",
        train=False,
        bundle_dir=str(bundle),
        dry_run=True,
        runner=lambda args: calls.append(args),
        exists_check=_boom,  # must not be called in dry-run
    )
    assert calls == []
    assert res["created_releases"] == []
    assert all(u["uploaded"] is False for u in res["uploads"])
    # dry-run plans the copy path but does not create the bundle dir
    assert not bundle.exists()


# ---------------------------------------------------------------------------
# real routing — release create + uploads + bundle copy
# ---------------------------------------------------------------------------
def test_uploads_route_to_correct_releases(tmp_path: Path):
    out = _seed(tmp_path / "out")
    calls = []
    res = publish_decision_models_artifacts(
        out,
        "owner/repo",
        train=False,
        bundle_dir=None,
        dry_run=False,
        runner=lambda args: calls.append(args),
        exists_check=lambda tag, repo: False,  # both releases missing
    )
    # two distinct releases created
    created = {c[2] for c in calls if c[:2] == ["release", "create"]}
    assert created == {"nfl_model_artifacts", "nfl_4th_down_models"}
    assert set(res["created_releases"]) == created
    # uploads target the mapped tag
    up_calls = [c for c in calls if c[:2] == ["release", "upload"]]
    by_name = {Path(c[3]).name: c[2] for c in up_calls}
    assert by_name == {
        "xpass_model.ubj": "nfl_model_artifacts",
        "fd_model.ubj": "nfl_4th_down_models",
        "wp_model.ubj": "nfl_4th_down_models",
    }
    assert all(u["uploaded"] for u in res["uploads"])


def test_skips_create_when_release_present(tmp_path: Path):
    out = _seed(tmp_path / "out")
    calls = []
    res = publish_decision_models_artifacts(
        out,
        "owner/repo",
        train=False,
        dry_run=False,
        runner=lambda args: calls.append(args),
        exists_check=lambda tag, repo: True,  # all exist
    )
    assert res["created_releases"] == []
    assert all(c[:2] != ["release", "create"] for c in calls)
    # 3 uploads, no creates
    assert len([c for c in calls if c[:2] == ["release", "upload"]]) == 3


def test_bundle_copied_out(tmp_path: Path):
    out = _seed(tmp_path / "out")
    bundle = tmp_path / "bundle"
    res = publish_decision_models_artifacts(
        out,
        "owner/repo",
        train=False,
        bundle_dir=str(bundle),
        dry_run=False,
        runner=lambda args: None,
        exists_check=lambda tag, repo: True,
    )
    copied = {Path(b["copied_to"]).name for b in res["bundle"]}
    assert copied == set(TRACK7_BUNDLE_ARTIFACTS)
    for fname in TRACK7_BUNDLE_ARTIFACTS:
        assert (bundle / fname).exists()


# ---------------------------------------------------------------------------
# missing artifacts without --train is an error
# ---------------------------------------------------------------------------
def test_missing_without_train_raises(tmp_path: Path):
    (tmp_path / "xpass_model.ubj").write_bytes(b"x")  # only one present
    with pytest.raises(FileNotFoundError):
        publish_decision_models_artifacts(
            tmp_path,
            "owner/repo",
            train=False,
            dry_run=True,
            runner=lambda args: None,
            exists_check=_boom,
        )
