"""Upload NFL model artifacts (.ubj + model-card .json) to a GitHub release.

Card sidecar naming (from model_training.track6_nfl_ep_wp.model_card):
    ``write_model_card`` writes ``Path(model_path).with_suffix(".json")``,
    so a model file ``ep.ubj`` has its card at ``ep.json`` (same stem).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

GH_TIMEOUT_SECONDS = 300

# Release-notes body used when auto-creating a missing release.
_RELEASE_BODY = {
    "nfl_model_artifacts": (
        "NFL model artifacts (EP/WP-spread/WP-naive/CP .ubj) + model cards."
    ),
    "nfl_model_pbp": (
        "NFL compiled play-by-play (EP/WP/QBR enriched; Python-built)."
    ),
}


def plan_uploads(models_dir) -> list[Path]:
    """Discover model files + their card sidecars in *models_dir*.

    For each ``*.ubj`` found, pairs it with its sidecar card: a ``.json`` file
    sharing the same stem (e.g. ``ep.ubj`` + ``ep.json``).  The card is
    included only when it exists.

    Args:
        models_dir: Directory containing ``*.ubj`` model files (and optionally
            their ``.json`` card sidecars).

    Returns:
        De-duplicated list of :class:`pathlib.Path` objects in stable order
        (model first, then its card).
    """
    models_dir = Path(models_dir)
    seen: set[Path] = set()
    out: list[Path] = []

    for model_path in sorted(models_dir.glob("*.ubj")):
        if model_path not in seen:
            seen.add(model_path)
            out.append(model_path)
        # Card sidecar: same stem, .json extension
        card_path = model_path.with_suffix(".json")
        if card_path.exists() and card_path not in seen:
            seen.add(card_path)
            out.append(card_path)

    return out


def _gh_runner(args: list) -> None:
    subprocess.run(["gh", *args], check=True, timeout=GH_TIMEOUT_SECONDS)


def _gh_release_exists(tag: str, repo: str) -> bool:
    """Return True if a GitHub release for *tag* already exists on *repo*."""
    r = subprocess.run(
        ["gh", "release", "view", tag, "--repo", repo],
        capture_output=True,
        timeout=GH_TIMEOUT_SECONDS,
    )
    return r.returncode == 0


def upload_artifacts(
    models_dir,
    tag: str,
    repo: str,
    *,
    dry_run: bool = False,
    runner=None,
    exists_check=None,
) -> dict:
    """Upload each discovered model + card to the *tag* release on *repo*.

    The release is created if it does not already exist (``gh release upload``
    does not create one), so a single call is self-sufficient.  *runner* and
    *exists_check* are injectable for hermetic testing.

    Args:
        models_dir: Directory containing ``*.ubj`` model files.
        tag: GitHub release tag (e.g. ``"nfl_model_artifacts"``).
        repo: GitHub repository slug (e.g. ``"sportsdataverse/sportsdataverse-data"``).
        dry_run: When True, print what would be done without touching the network.
        runner: Callable ``(args: list) -> None`` that executes a ``gh`` sub-command
            (injectable for testing; defaults to :func:`_gh_runner`).
        exists_check: Callable ``(tag: str, repo: str) -> bool`` that checks whether
            the release already exists (injectable for testing; defaults to
            :func:`_gh_release_exists`).

    Returns:
        A dict with keys ``uploaded`` (int), ``files`` (list[str]),
        ``tag`` (str), and ``created_release`` (bool).
    """
    run = runner or _gh_runner
    exists = exists_check or _gh_release_exists
    files = plan_uploads(models_dir)
    created_release = False

    if dry_run:
        print(f"[dry-run] would ensure release {repo}:{tag} exists")
    elif not exists(tag, repo):
        body = _RELEASE_BODY.get(tag, f"{tag} (auto-created by nfl_model_publish).")
        run(["release", "create", tag, "--repo", repo, "--title", tag, "--notes", body])
        created_release = True

    uploaded = 0
    for f in files:
        if dry_run:
            print(f"[dry-run] would upload {f} -> {repo}:{tag}")
            continue
        run(["release", "upload", tag, str(f), "--repo", repo, "--clobber"])
        uploaded += 1

    return {
        "uploaded": uploaded,
        "files": [str(f) for f in files],
        "tag": tag,
        "created_release": created_release,
    }
