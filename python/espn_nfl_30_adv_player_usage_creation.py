"""Builder: ESPN NFL usage box: player usage (explosive, first downs, shares, red zone, scoring opp, third down over expected).

Thin entrypoint; the build lives in ``nfl_espn_build`` and this file exists so
the directory listing is the pipeline and each dataset is runnable on its own.
The section is computed at build time from each final's plays and participants
(``sportsdataverse.football.usage_box``), so the installed sdv-py defines it.

Example:
    One season::

        uv run python python/espn_nfl_30_adv_player_usage_creation.py -s 2025 -e 2025
"""

from __future__ import annotations

from _shim import run_dataset

DATASET = "adv_player_usage"

if __name__ == "__main__":
    raise SystemExit(run_dataset(DATASET))
