"""Builder: ESPN NFL season tendencies per head coach (nflverse schedule attribution).

Thin entrypoint; the build lives in ``nfl_espn_build`` and this file exists so
the directory listing is the pipeline and each dataset is runnable on its own.
The head coach of each game comes from the nflverse schedule (``home_coach`` /
``away_coach``); a midseason change splits the season between both coaches.

Example:
    One season::

        uv run python python/espn_nfl_62_coach_tendencies_creation.py -s 2025 -e 2025
"""

from __future__ import annotations

from _shim import run_dataset

DATASET = "coach_tendencies"

if __name__ == "__main__":
    raise SystemExit(run_dataset(DATASET))
