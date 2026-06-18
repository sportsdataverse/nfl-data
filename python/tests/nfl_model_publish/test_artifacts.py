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


# ---------------------------------------------------------------------------
# pattern mode — flat glob, no card-sidecar pairing
# ---------------------------------------------------------------------------

def test_pattern_uploads_matching_glob(tmp_path):
    (tmp_path / "roster_2022.parquet").write_bytes(b"r22")
    (tmp_path / "roster_2023.parquet").write_bytes(b"r23")
    (tmp_path / "ep.ubj").write_bytes(b"ignored")  # not matched by pattern
    calls = []
    res = upload_artifacts(
        tmp_path,
        "nfl_rosters",
        "owner/repo",
        pattern="roster_*.parquet",
        dry_run=False,
        runner=lambda args: calls.append(args),
        exists_check=lambda tag, repo: True,  # skip create
    )
    names = {c[3].rsplit("\\", 1)[-1].rsplit("/", 1)[-1] for c in calls}
    assert names == {"roster_2022.parquet", "roster_2023.parquet"}
    assert res["uploaded"] == 2


def test_pattern_single_file(tmp_path):
    (tmp_path / "players.parquet").write_bytes(b"players")
    res = upload_artifacts(
        tmp_path,
        "nfl_players",
        "owner/repo",
        pattern="players.parquet",
        dry_run=True,
        runner=lambda args: None,
        exists_check=_boom,
    )
    assert len(res["files"]) == 1
    assert res["files"][0].endswith("players.parquet")


# ---------------------------------------------------------------------------
# _parse_seasons
# ---------------------------------------------------------------------------

def test_parse_seasons_range_and_single():
    from nfl_model_publish.cli import _parse_seasons

    assert _parse_seasons("2022:2024") == [2022, 2023, 2024]
    assert _parse_seasons("2023") == [2023]


def test_parse_seasons_rejects_inverted_and_malformed():
    import argparse

    import pytest

    from nfl_model_publish.cli import _parse_seasons

    with pytest.raises(argparse.ArgumentTypeError):
        _parse_seasons("2024:2022")
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_seasons("twenty:twentytwo")
