"""Builder: NFL rolling form windows: each player's and team's last N dropbacks / targets / carries / plays against the prior window, the season start and the career.

Thin entrypoint; the build lives in ``nfl_espn_build`` and this file exists so
the directory listing is the pipeline and each dataset is runnable on its own.
Cut at build time from the written ``espn_nfl_pbp`` seasons 2002..S
(``sportsdataverse.rolling_windows``), so the installed sdv-py defines every
window. Publishes to ``nfl_rolling_windows``.

Example:
    One season::

        uv run python python/espn_nfl_64_rolling_windows_creation.py -s 2025 -e 2025
"""

from __future__ import annotations

from _shim import run_dataset

DATASET = "rolling_windows"

if __name__ == "__main__":
    raise SystemExit(run_dataset(DATASET))
