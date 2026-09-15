"""Builder: ESPN NFL season tendencies per team: pace, run/pass by down and score state, efficiency, red-zone / scoring-opportunity and fourth-down decisions.

Thin entrypoint; the build lives in ``nfl_espn_build`` and this file exists so
the directory listing is the pipeline and each dataset is runnable on its own.
Computed at build time from the season's plays (``sportsdataverse.football.tendencies``),
so the installed sdv-py defines every metric.

Example:
    One season::

        uv run python python/espn_nfl_61_team_tendencies_creation.py -s 2025 -e 2025
"""

from __future__ import annotations

from _shim import run_dataset

DATASET = "team_tendencies"

if __name__ == "__main__":
    raise SystemExit(run_dataset(DATASET))
