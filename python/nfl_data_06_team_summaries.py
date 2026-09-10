"""Stage 06 — NFL season team + player summaries (+ opt-in --publish).

Thin numbered entry over ``nfl_team_summaries``; args forward verbatim to its CLI.
Reads the released (or locally built) ``model_pbp`` season parquet and publishes
``nfl_team_summaries``, ``nfl_passing``, ``nfl_rushing``, ``nfl_receiving`` and
``nfl_percentiles`` -- the tables gameonpaper.com's NFL leaderboards, team pages
and trends read through sdv-db. Lifecycle: ingest -> model_pbp -> pbp_publish ->
rosters_players -> ratings_weekly -> team_summaries.

Usage::

    python -m nfl_data_06_team_summaries --seasons 2025 --out ../out/nfl_team_summaries
    python -m nfl_data_06_team_summaries --seasons 2025 --pbp-dir out/model_pbp --publish
    scripts/nfl_data.sh 06
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    from nfl_team_summaries.__main__ import main as _main

    argv = list(argv) if argv is not None else sys.argv[1:]
    return _main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
