"""Stage 08 — NFL defense vs position (+ opt-in --publish).

Thin numbered entry over ``nfl_team_summaries.defense_vs_position``; args forward
verbatim to its CLI. Reads the released (or locally built) ``model_pbp`` season
parquet and that season's roster and publishes ``nfl_defense_vs_position`` --
what each defense allowed to QBs, RBs, WRs and TEs (EPA/play, success and
explosive rate, sack rate, yards per carry, yards per target), with a
percentile among qualifiers. Lifecycle: ingest -> model_pbp -> pbp_publish ->
rosters_players -> ratings_weekly -> team_summaries -> metric_curves ->
defense_vs_position.

Usage::

    python -m nfl_data_08_defense_vs_position --seasons 2025 --out ../out/nfl_defense_vs_position
    python -m nfl_data_08_defense_vs_position --seasons 2025 --pbp-dir out/model_pbp --publish
    scripts/nfl_data.sh 08
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    from nfl_team_summaries.defense_vs_position import main as _main

    argv = list(argv) if argv is not None else sys.argv[1:]
    return _main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
