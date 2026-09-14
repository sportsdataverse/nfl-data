"""Shared entrypoint helper for the numbered ``espn_nfl_NN_*_creation.py`` shims.

Each shim states its dataset once and forwards the caller's season / output
args to ``nfl_espn_build.cli.main``; a caller-supplied ``--dataset`` is
refused rather than silently overridden (a run that quietly builds something
other than what was asked for is the failure mode these pipelines keep
getting bitten by). Mirrors ``cfbfastR-cfb-data/python/_shim.py``.
"""

from __future__ import annotations

import sys

from nfl_espn_build.cli import main

_FLAG = "--dataset"


def _reject_override(argv: list[str], dataset: str) -> None:
    for i, arg in enumerate(argv):
        if arg == _FLAG or arg.startswith(f"{_FLAG}="):
            given = (
                arg.split("=", 1)[1] if "=" in arg else (argv[i + 1] if i + 1 < len(argv) else "")
            )
            raise SystemExit(
                f"error: this entrypoint always builds {dataset!r}, so {_FLAG} {given!r} would be "
                f"ambiguous. Run the {given!r} shim instead, or: python -m nfl_espn_build {_FLAG} {given} ..."
            )


def run_dataset(dataset: str, argv: list[str] | None = None) -> int:
    """Build exactly ``dataset`` (or a group: ``all`` / ``adv_box``)."""
    argv = list(sys.argv[1:] if argv is None else argv)
    _reject_override(argv, dataset)
    return main([_FLAG, dataset, *argv])
