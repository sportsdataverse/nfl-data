"""Consistency gate for the "Model registry" table in ``CLAUDE.md``.

That table is prose: nothing enforces it stays true as files move. A row's
``fitting script`` cell names a real package under ``python/model_training/``
(or a function inside one) and its ``cadence`` cell names a real workflow under
``.github/workflows/`` (e.g. ``nfl_model_pipeline.yml``) -- unless the row is
explicitly marked ``TODO`` (the QBR-reconstruction row today: no trainer in
this repo yet). This test parses the live table out of CLAUDE.md and checks
every non-TODO reference actually resolves, so a rename/move that silently
strands a documented retrain path fails CI instead of rotting until someone
tries to run it a year later.

Offline; reads only CLAUDE.md + the filesystem, no imports of the (heavy,
xgboost-backed) trainer packages themselves.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
MODEL_TRAINING_DIR = REPO_ROOT / "python" / "model_training"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

TABLE_HEADER = "| model | artifact(s) | release tag |"


def _parse_registry_rows() -> list[list[str]]:
    """Return the model-registry table's data rows as lists of trimmed cells."""
    lines = CLAUDE_MD.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(TABLE_HEADER))
    rows = []
    for line in lines[start + 2 :]:  # +2 skips the header row and the --- separator
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(cells)
    return rows


REGISTRY_ROWS = _parse_registry_rows()


def test_registry_table_is_present_and_nonempty() -> None:
    # A parser bug or a deleted table must fail loudly, not pass vacuously.
    assert len(REGISTRY_ROWS) >= 10, "expected >=10 model-registry rows in CLAUDE.md"
    assert all(len(row) == 8 for row in REGISTRY_ROWS), (
        "model-registry row(s) don't have the expected 8 columns "
        "(model, artifact, release tag, training data, fitting script, "
        "gates, last retrain, cadence)"
    )


def _fitting_script_cell(row: list[str]) -> str:
    return row[4]


def _cadence_cell(row: list[str]) -> str:
    return row[7]


def test_every_non_todo_fitting_script_resolves() -> None:
    checked = 0
    for row in REGISTRY_ROWS:
        model, cell = row[0], _fitting_script_cell(row)
        if "TODO" in cell:
            # A TODO fitting script must not claim a real cadence either --
            # otherwise the table promises a retrain path that doesn't exist.
            assert "TODO" in _cadence_cell(row), (
                f"{model!r}: fitting script is TODO but cadence isn't -- "
                "table claims a schedule for a trainer that doesn't exist"
            )
            continue

        pkg = (
            "decision_models"
            if "decision_models" in cell
            else ("play_level" if "play_level" in cell else None)
        )
        assert pkg is not None, f"{model!r}: unrecognized fitting-script cell {cell!r}"
        pkg_dir = MODEL_TRAINING_DIR / pkg
        assert pkg_dir.is_dir(), f"{model!r}: {pkg_dir} does not exist"
        checked += 1

        func_match = re.search(r"`(\w+)`", cell)
        if func_match:
            func_name = func_match.group(1)
            sources = "\n".join(p.read_text(encoding="utf-8") for p in pkg_dir.glob("*.py"))
            assert re.search(rf"\bdef {re.escape(func_name)}\b", sources), (
                f"{model!r}: {pkg}.{func_name} not defined in any {pkg_dir} module"
            )

    assert checked >= 8, "expected most registry rows to name a real fitting script"


def test_every_referenced_workflow_file_exists() -> None:
    checked = 0
    for row in REGISTRY_ROWS:
        model, cell = row[0], _cadence_cell(row)
        for wf in re.findall(r"`([\w\-]+\.yml)`", cell):
            assert (WORKFLOWS_DIR / wf).is_file(), (
                f"{model!r}: cadence references {wf!r}, missing from {WORKFLOWS_DIR}"
            )
            checked += 1
    assert checked >= 8, "expected most registry rows to cite a real workflow file"
