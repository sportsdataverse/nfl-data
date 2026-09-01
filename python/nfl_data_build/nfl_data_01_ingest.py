"""Stage 01 — raw per-game JSON ingest (HTTP read-through cache over nfl-raw).

Thin numbered entry over ``nfl_data_ingest``; args forward verbatim to its CLI.
The library package owns the logic; this file exists so the repo's lifecycle
is enumerable: ingest -> model_pbp -> pbp_publish -> rosters_players ->
ratings_weekly (models: see nfl_model_build). Single home: models/manifest.yaml.

Usage::

    python -m nfl_data_build.nfl_data_01_ingest --seasons 2025 --cache-dir _raw_cache
    scripts/nfl_data.sh 01
"""
from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    from nfl_data_ingest.cli import main as _main

    argv = list(argv) if argv is not None else sys.argv[1:]
    return _main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
