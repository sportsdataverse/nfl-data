"""The release sidecars R's sportsdataverse_save() attaches to every tag.

The Python publisher never wrote them, so every nfl_* tag on sportsdataverse-data
carries no timestamp at all -- a consumer has no way to tell whether the assets
moved since they last downloaded.
"""

from __future__ import annotations

import json
from pathlib import Path

from nfl_model_publish.artifacts import PKG_FUNCTION, upload_artifacts

SIDECAR_NAMES = [
    "timestamp.txt",
    "timestamp.json",
    "package_function.txt",
    "package_function.json",
]
TAG = "nfl_model_artifacts"


def _seed(tmp_path):
    (tmp_path / "ep.ubj").write_bytes(b"ep")
    return tmp_path


def test_upload_stamps_the_tag_last(tmp_path):
    calls: list[list[str]] = []

    upload_artifacts(
        _seed(tmp_path),
        TAG,
        "owner/repo",
        dry_run=False,
        runner=lambda args: calls.append(args),
        exists_check=lambda tag, repo: True,
    )

    names = [Path(c[3]).name for c in calls if c[:2] == ["release", "upload"]]
    assert names == ["ep.ubj", *SIDECAR_NAMES]
    assert all(c[2] == TAG and c[-1] == "--clobber" for c in calls)


def test_nothing_uploaded_means_no_stamp(tmp_path):
    """A run that published nothing must not move the timestamp."""
    calls: list[list[str]] = []

    upload_artifacts(
        tmp_path,
        TAG,
        "owner/repo",
        dry_run=False,
        runner=lambda args: calls.append(args),
        exists_check=lambda tag, repo: True,
    )

    assert not any(c[:2] == ["release", "upload"] for c in calls)


def test_dry_run_stamps_nothing(tmp_path):
    calls: list[list[str]] = []

    upload_artifacts(
        _seed(tmp_path),
        TAG,
        "owner/repo",
        dry_run=True,
        runner=lambda args: calls.append(args),
        exists_check=lambda tag, repo: True,
    )

    assert not any(c[:2] == ["release", "upload"] for c in calls)


def test_sidecars_carry_the_producer_and_a_timestamp(tmp_path):
    seen: dict[str, str] = {}

    def _runner(argv: list[str]) -> None:
        # read inside the runner: the temp dir is cleaned up behind the upload
        path = Path(argv[3])
        if path.name.startswith(("timestamp.", "package_function.")):
            seen[path.name] = path.read_text()

    upload_artifacts(
        _seed(tmp_path),
        TAG,
        "owner/repo",
        dry_run=False,
        runner=_runner,
        exists_check=lambda tag, repo: True,
    )

    assert seen["package_function.txt"].strip() == PKG_FUNCTION[TAG]
    assert json.loads(seen["package_function.json"])["package_function"] == PKG_FUNCTION[TAG]
    assert json.loads(seen["timestamp.json"])["last_updated"].strip()


def test_loader_named_tags_point_at_a_real_loader():
    """The SDV-native release tags name the sdv-py loader that reads them."""
    assert PKG_FUNCTION["nfl_model_pbp"] == 'sportsdataverse.nfl.load_nfl_pbp(source="sdv")'
    assert PKG_FUNCTION["nfl_espn_qbr"] == "sportsdataverse.nfl.load_nfl_espn_qbr()"
    # artifact tags have no loader -- they name their producer instead
    assert PKG_FUNCTION[TAG].endswith("artifacts.py")
