"""Stage 09 — NFL Paper Index per game (+ opt-in --publish).

Thin numbered entry over ``nfl_team_summaries.paper_index``; args forward verbatim
to its CLI. Reads the season's ``espn_nfl_pbp`` (the ESPN family's pbp, not
``model_pbp``: the Paper Index needs ESPN-shape columns) and publishes
``nfl_paper_index_games`` -- each team's deserved-win share in every scored game,
with ``paper_index_span`` saying whether the season was inside the fit. The season
sums are the ``deserved_wins`` / ``luck_*`` columns of ``nfl_team_summaries``
(stage 06). Runs after the ESPN family build (``scripts/espn_nfl_data.sh``), on
the pbp that run just wrote.

Usage::

    python -m nfl_data_09_paper_index_games --seasons 2025 --out ../out/nfl_paper_index_games
    python -m nfl_data_09_paper_index_games --seasons 2025 --pbp-dir out/espn_nfl/pbp --publish
    scripts/nfl_data.sh 09
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    from nfl_team_summaries.paper_index import main as _main

    argv = list(argv) if argv is not None else sys.argv[1:]
    return _main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
