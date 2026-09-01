"""Stage 05 — weekly NFL team ratings build (+ opt-in --publish).

Thin numbered entry over ``nfl_ratings_weekly``; args forward verbatim to its CLI.
The library package owns the logic; this file exists so the repo's lifecycle
is enumerable: ingest -> model_pbp -> pbp_publish -> rosters_players ->
ratings_weekly (models: see nfl_model_build). Single home: models/manifest.yaml.

Usage::

    python -m nfl_data_build.nfl_data_05_ratings_weekly --seasons 2025 --out ../out/nfl_ratings_weekly
    scripts/nfl_data.sh 05
"""
from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    from nfl_ratings_weekly.__main__ import main as _main

    argv = list(argv) if argv is not None else sys.argv[1:]
    return _main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
