"""Builder: ESPN NFL head-coach careers: every written coach season summed, rates recomputed.

Thin entrypoint; the build lives in ``nfl_espn_build`` and this file exists so
the directory listing is the pipeline and each dataset is runnable on its own.
Reads the ``coach_tendencies`` parquets already under the output root, so run
shim 62 for every season first; the file is season-less and rewritten each run.

Example:
    One season::

        uv run python python/espn_nfl_63_coach_careers_creation.py -s 2025 -e 2025
"""

from __future__ import annotations

from _shim import run_dataset

DATASET = "coach_careers"

if __name__ == "__main__":
    raise SystemExit(run_dataset(DATASET))
