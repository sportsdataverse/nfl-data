"""Stage 07 — NFL metric curves (+ opt-in --publish).

Thin numbered entry over ``nfl_team_summaries.curves``; args forward verbatim to
its CLI. Reads the released (or locally built) ``model_pbp`` season parquet and
publishes ``nfl_metric_curves`` -- league / team / player rate curves along a
continuous axis (FG% by distance, completion% and EPA by air yards, 4th-down
conversion by yards to go, success by down x distance). Lifecycle: ingest ->
model_pbp -> pbp_publish -> rosters_players -> ratings_weekly -> team_summaries
-> metric_curves.

Usage::

    python -m nfl_data_07_metric_curves --seasons 2025 --out ../out/nfl_metric_curves
    python -m nfl_data_07_metric_curves --seasons 2025 --pbp-dir out/model_pbp --publish
    scripts/nfl_data.sh 07
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    from nfl_team_summaries.curves import main as _main

    argv = list(argv) if argv is not None else sys.argv[1:]
    return _main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
