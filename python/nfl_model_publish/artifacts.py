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


def plan_uploads(models_dir, pattern: str = "*.ubj") -> list[Path]:
    """Discover artifact files (and, for ``*.ubj``, their card sidecars).

    For the default ``*.ubj`` pattern each match is paired with its sidecar
    card — a ``.json`` file sharing the same stem (e.g. ``ep.ubj`` + ``ep.json``,
    included only when it exists).  For any other pattern (e.g.
    ``model_pbp_*.parquet``) the matched files are returned as-is with no
    sidecar pairing.

    Args:
        models_dir: Directory to scan for artifacts.
        pattern: Glob pattern for the primary artifacts (default ``"*.ubj"``).

    Returns:
        De-duplicated list of :class:`pathlib.Path` objects in stable order
        (model first, then its card when applicable).
    """
    models_dir = Path(models_dir)
    pair_cards = pattern == "*.ubj"
    seen: set[Path] = set()
    out: list[Path] = []

    for model_path in sorted(models_dir.glob(pattern)):
        if model_path not in seen:
            seen.add(model_path)
            out.append(model_path)
        if not pair_cards:
            continue
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
    pattern: str = "*.ubj",
    dry_run: bool = False,
    runner=None,
    exists_check=None,
) -> dict:
    """Upload each discovered artifact (+ card) to the *tag* release on *repo*.

    The release is created if it does not already exist (``gh release upload``
    does not create one), so a single call is self-sufficient.  *runner* and
    *exists_check* are injectable for hermetic testing.

    Args:
        models_dir: Directory to scan for artifacts.
        tag: GitHub release tag (e.g. ``"nfl_model_artifacts"``).
        repo: GitHub repository slug (e.g. ``"sportsdataverse/sportsdataverse-data"``).
        pattern: Glob pattern for the artifacts to upload (default ``"*.ubj"``;
            pass ``"model_pbp_*.parquet"`` for the compiled PBP dataset).
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
    files = plan_uploads(models_dir, pattern)
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
