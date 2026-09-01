"""Stage 03 — publish model_pbp parquets to the nfl_model_pbp release tag.

Thin numbered entry over ``nfl_model_publish`` (injects the ``pbp`` subcommand); args forward verbatim to its CLI.
The library package owns the logic; this file exists so the repo's lifecycle
is enumerable: ingest -> model_pbp -> pbp_publish -> rosters_players ->
ratings_weekly (models: see nfl_model_build). Single home: models/manifest.yaml.

Usage::

    python -m nfl_data_build.nfl_data_03_pbp_publish --parquet-dir out/model_pbp --tag nfl_model_pbp
    scripts/nfl_data.sh 03
"""
from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    from nfl_model_publish.cli import main as _main

    argv = list(argv) if argv is not None else sys.argv[1:]
    return _main(["pbp", *argv])


if __name__ == "__main__":
    raise SystemExit(main())
