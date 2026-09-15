"""Builder: ESPN NFL advanced box score -- all ten sections.

Orchestrator, not a dataset: builds the ten ``adv_*`` datasets (20-29) from one
pass over the cached finals, the way ``cfbfastR-cfb-data``'s stage 04 does.

Example:
    One season, all ten::

        uv run python python/espn_nfl_04_adv_box_creation.py -s 2025 -e 2025
"""

from __future__ import annotations

from _shim import run_dataset

if __name__ == "__main__":
    raise SystemExit(run_dataset("adv_box"))
