"""Stage 02 — native model_pbp parquet build (+ EPA/WPA enrichment).

Thin numbered entry over ``native_pbp``; args forward verbatim to its CLI.
The library package owns the logic; this file exists so the repo's lifecycle
is enumerable: ingest -> model_pbp -> pbp_publish -> rosters_players ->
ratings_weekly (models: see nfl_model_build). Single home: models/manifest.yaml.

Usage::

    python -m nfl_data_build.nfl_data_02_model_pbp build --enrich --seasons 2025
    scripts/nfl_data.sh 02
"""
from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    from native_pbp.cli import main as _main

    argv = list(argv) if argv is not None else sys.argv[1:]
    return _main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
