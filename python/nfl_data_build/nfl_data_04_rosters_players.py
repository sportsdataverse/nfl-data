"""Stage 04 — rosters / players / player-stats / team-stats / qbr datasets (build + publish fused).

Thin numbered entry over ``nfl_model_publish``; args forward verbatim to its CLI.
The library package owns the logic; this file exists so the repo's lifecycle
is enumerable: ingest -> model_pbp -> pbp_publish -> rosters_players ->
ratings_weekly (models: see nfl_model_build). Single home: models/manifest.yaml.

Usage::

    python -m nfl_data_build.nfl_data_04_rosters_players rosters --seasons 2025 --out out/rosters
    scripts/nfl_data.sh 04
"""
from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    from nfl_model_publish.cli import main as _main

    argv = list(argv) if argv is not None else sys.argv[1:]
    return _main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
