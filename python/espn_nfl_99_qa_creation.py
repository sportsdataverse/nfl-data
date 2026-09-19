"""Builder: ESPN NFL per-game validation QA (report-only).

One row per game -- ``sportsdataverse.validation.validate_game`` over the
processor's plays -- plus a season ``_summary.json`` sidecar carrying the
error-free share, the per-rule counts and the pre-publish drift gate against
the previously published ``espn_nfl_pbp`` asset.

Numbered 99, and twin of ``cfbfastR-cfb-data``'s
``python/espn_cfb_99_qa_creation.py``, because it is the LAST stage of a
season: the drift gate reads the season pbp parquet the earlier stages wrote.
Report-only in this revision -- ``nfl_espn_build.qa.BLOCKING`` is ``False`` and
nothing here fails a build.

Example:
    One season::

        uv run python python/espn_nfl_99_qa_creation.py -s 2025 -e 2025
"""

from __future__ import annotations

from _shim import run_dataset

DATASET = "qa"

if __name__ == "__main__":
    raise SystemExit(run_dataset(DATASET))
