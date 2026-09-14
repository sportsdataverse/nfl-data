"""Release publishing for the ``espn_nfl_*`` tags.

One ``gh release upload <tag> <file> --clobber`` per file (never a multi-file
glob: multi-asset uploads silently drop large files), creating the release
when absent, through the same injectable ``gh`` runner
``nfl_model_publish.artifacts`` uses so tests never touch the network.
Requires ``GH_TOKEN`` = a PAT with ``Contents: write`` on the data repo.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from nfl_model_publish.artifacts import _gh_release_exists, _gh_runner

log = logging.getLogger(__name__)

DEFAULT_REPO = "sportsdataverse/sportsdataverse-data"

RELEASE_NOTES = (
    "ESPN NFL processed-game datasets built by sportsdataverse/nfl-data from the "
    "ESPN game library committed in sportsdataverse/nfl-raw (nfl/espn/), processed "
    "with sportsdataverse-py's NFLPlayProcess. One asset per season."
)


def publish_files(
    tag: str,
    files: list[Path],
    *,
    repo: str = DEFAULT_REPO,
    dry_run: bool = False,
    runner: Callable[[list], None] | None = None,
    exists_check: Callable[[str, str], bool] | None = None,
) -> list[Path]:
    """Upload ``files`` to the ``tag`` release on ``repo``; returns what was (or would be) sent."""
    runner = runner or _gh_runner
    exists_check = exists_check or _gh_release_exists
    files = [Path(f) for f in files if f is not None and Path(f).exists()]
    if not files:
        return []
    if dry_run:
        for f in files:
            log.info("[dry-run] would upload %s -> %s@%s", f, repo, tag)
        return files
    if not exists_check(tag, repo):
        runner(["release", "create", tag, "--repo", repo, "--title", tag, "--notes", RELEASE_NOTES])
    for f in files:
        runner(["release", "upload", tag, str(f), "--clobber", "--repo", repo])
        log.info("uploaded %s -> %s@%s", f.name, repo, tag)
    return files
