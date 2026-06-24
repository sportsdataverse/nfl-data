"""Publish path for the self-trained decision_models NFL model suite.

Mirrors :mod:`nfl_model_publish.artifacts` but routes the *Python-native*
decision_models artifacts to their correct destinations:

- **Uploaded to releases** (the repoint mechanism):
    - ``xpass_model.ubj`` -> ``nfl_model_artifacts``
    - ``fd_model.ubj`` + ``wp_model.ubj`` -> ``nfl_4th_down_models``
- **Copied out for the sdv-py bundle** (sdv-py commits these to
  ``sportsdataverse/nfl/models/``; not uploaded to any release):
    - ``two_pt_model.ubj``, ``fg_model.ubj``, ``punt_data.parquet``

The artifacts come from ``model_training.decision_models`` — either trained
fresh (``train-all``) or read from an existing ``out/`` directory. ``--dry-run``
plans the uploads + copies without touching the network or the bundle dir.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .artifacts import _gh_release_exists, _gh_runner, _RELEASE_BODY

__all__ = [
    "TRACK7_RELEASE_MAP",
    "TRACK7_BUNDLE_ARTIFACTS",
    "artifact_digest",
    "plan_decision_models_artifacts",
    "publish_decision_models_artifacts",
]

# Release-tagged artifacts: {filename: release tag}. xpass joins the EP/WP/CP
# model_artifacts release; fd + wp join the 4th-down models release (the same
# split nfl4th uses: dropback model with the core models, go/wp with 4th-down).
TRACK7_RELEASE_MAP: Dict[str, str] = {
    "xpass_model.ubj": "nfl_model_artifacts",
    "fd_model.ubj": "nfl_4th_down_models",
    "wp_model.ubj": "nfl_4th_down_models",
}

# Bundled-in-sdv-py artifacts: copied to the bundle dir, never uploaded. sdv-py
# ships these under ``sportsdataverse/nfl/models/`` (package-data) and commits
# them directly.
TRACK7_BUNDLE_ARTIFACTS: tuple[str, ...] = (
    "two_pt_model.ubj",
    "fg_model.ubj",
    "punt_data.parquet",
)

# Release-notes body for the 4th-down models release (artifacts.py owns the rest).
_TRACK7_RELEASE_BODY: Dict[str, str] = {
    "nfl_4th_down_models": (
        "NFL 4th-down decision models (go-for-it gain `fd_model` + win-probability "
        "`wp_model` .ubj; Python-native decision_models retrain)."
    ),
}


def artifact_digest(path: Path) -> Dict[str, object]:
    """Return ``{name, path, size_bytes, sha256}`` for an artifact file.

    Args:
        path: Path to the artifact.

    Returns:
        Dict with the file name, absolute path, byte size, and SHA-256 hex digest.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
    """
    p = Path(path)
    data = p.read_bytes()
    return {
        "name": p.name,
        "path": str(p.resolve()),
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _ensure_out_dir(
    out_dir: Path,
    *,
    train: bool,
    nrounds_override: Optional[int],
    source: str,
    wp_cal_data_path: Optional[str],
) -> None:
    """Train the suite into ``out_dir`` when ``train`` (else assume it exists)."""
    if not train:
        return
    from model_training.decision_models.pipeline import train_all

    train_all(
        out_dir=out_dir,
        nrounds_override=nrounds_override,
        source=source,
        wp_cal_data_path=wp_cal_data_path,
    )


def plan_decision_models_artifacts(out_dir) -> Dict[str, List[Dict[str, object]]]:
    """Classify the decision_models artifacts in ``out_dir`` into upload + bundle sets.

    Args:
        out_dir: Directory holding the trained decision_models ``.ubj`` / ``.parquet``.

    Returns:
        ``{"uploads": [{...release...}], "bundle": [{...}], "missing": [str]}``
        where each artifact entry carries its digest (name/path/size/sha256) plus
        — for uploads — the destination ``tag``.
    """
    out_dir = Path(out_dir)
    uploads: List[Dict[str, object]] = []
    bundle: List[Dict[str, object]] = []
    missing: List[str] = []

    for fname, tag in TRACK7_RELEASE_MAP.items():
        path = out_dir / fname
        if not path.exists():
            missing.append(fname)
            continue
        entry = artifact_digest(path)
        entry["tag"] = tag
        uploads.append(entry)

    for fname in TRACK7_BUNDLE_ARTIFACTS:
        path = out_dir / fname
        if not path.exists():
            missing.append(fname)
            continue
        bundle.append(artifact_digest(path))

    return {"uploads": uploads, "bundle": bundle, "missing": missing}


def publish_decision_models_artifacts(
    out_dir,
    repo: str,
    *,
    train: bool = False,
    nrounds_override: Optional[int] = None,
    source: str = "nflverse",
    wp_cal_data_path: Optional[str] = None,
    bundle_dir: Optional[str] = None,
    dry_run: bool = False,
    runner: Optional[Callable[[list], None]] = None,
    exists_check: Optional[Callable[[str, str], bool]] = None,
) -> Dict[str, object]:
    """Train (optionally) + route the decision_models artifacts to release + bundle.

    Release-tagged artifacts (``TRACK7_RELEASE_MAP``) are uploaded to their tag on
    ``repo`` (release auto-created if missing). Bundle artifacts
    (``TRACK7_BUNDLE_ARTIFACTS``) are copied to ``bundle_dir`` (when given) for
    sdv-py to commit. ``runner`` / ``exists_check`` are injectable for hermetic
    testing.

    Args:
        out_dir: Directory holding (or to receive) the trained artifacts.
        repo: GitHub repo slug for uploads.
        train: When True, run ``train_all`` into ``out_dir`` first.
        nrounds_override: Passed through to ``train_all`` (smoke runs).
        source: PBP source for ``train_all``.
        wp_cal_data_path: Override the WP ``cal_data.rds`` path.
        bundle_dir: Where to copy the sdv-py bundle artifacts (skipped if None).
        dry_run: Plan without uploading, creating releases, or copying.
        runner: ``gh`` sub-command executor (defaults to :func:`_gh_runner`).
        exists_check: Release-existence check (defaults to
            :func:`_gh_release_exists`).

    Returns:
        Dict with ``uploads`` (per-artifact digests + tag + uploaded flag),
        ``bundle`` (per-artifact digests + copied-to path), ``missing``,
        ``created_releases`` (list of tags), and ``dry_run``.

    Raises:
        FileNotFoundError: If ``train`` is False and required artifacts are absent.
    """
    out_dir = Path(out_dir)
    run = runner or _gh_runner
    exists = exists_check or _gh_release_exists

    _ensure_out_dir(
        out_dir,
        train=train,
        nrounds_override=nrounds_override,
        source=source,
        wp_cal_data_path=wp_cal_data_path,
    )

    plan = plan_decision_models_artifacts(out_dir)
    uploads = plan["uploads"]
    bundle = plan["bundle"]
    missing = plan["missing"]

    if not train and missing:
        raise FileNotFoundError(
            f"decision_models artifacts missing from {out_dir}: {missing}. "
            f"Pass train=True (--train) to build them first."
        )

    # Ensure each distinct release exists, then upload its artifacts.
    created_releases: List[str] = []
    tags = sorted({str(u["tag"]) for u in uploads})
    body_map = {**_RELEASE_BODY, **_TRACK7_RELEASE_BODY}
    if dry_run:
        for tag in tags:
            print(f"[dry-run] would ensure release {repo}:{tag} exists")
    else:
        for tag in tags:
            if not exists(tag, repo):
                body = body_map.get(tag, f"{tag} (auto-created by nfl_model_publish).")
                run(["release", "create", tag, "--repo", repo, "--title", tag, "--notes", body])
                created_releases.append(tag)

    for u in uploads:
        tag, path = str(u["tag"]), str(u["path"])
        if dry_run:
            print(f"[dry-run] would upload {u['name']} -> {repo}:{tag}")
            u["uploaded"] = False
            continue
        run(["release", "upload", tag, path, "--repo", repo, "--clobber"])
        u["uploaded"] = True

    # Copy the sdv-py bundle artifacts out (sdv-py commits them; never uploaded).
    for b in bundle:
        if bundle_dir is None:
            b["copied_to"] = None
            continue
        dest_dir = Path(bundle_dir)
        dest = dest_dir / str(b["name"])
        if dry_run:
            print(f"[dry-run] would copy {b['name']} -> {dest}")
            b["copied_to"] = str(dest)
            continue
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(b["path"]), str(dest))
        b["copied_to"] = str(dest.resolve())

    return {
        "uploads": uploads,
        "bundle": bundle,
        "missing": missing,
        "created_releases": created_releases,
        "dry_run": dry_run,
    }
