"""Builder: ESPN NFL advanced box: turnover.

Thin entrypoint; the build lives in ``nfl_espn_build`` and this file exists so
the directory listing is the pipeline and each dataset is runnable on its own.
Numbered like the cfb family (``cfbfastR-cfb-data/python/espn_cfb_25_*``) so the
two chains stay comparable by eye.

Example:
    One season::

        uv run python python/espn_nfl_25_adv_turnover_creation.py -s 2025 -e 2025
"""

from __future__ import annotations

from _shim import run_dataset

DATASET = "adv_turnover"

if __name__ == "__main__":
    raise SystemExit(run_dataset(DATASET))
