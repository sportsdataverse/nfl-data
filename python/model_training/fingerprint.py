"""Stage fingerprints + retrain ledger (Track C steps 3 + 5).

A fingerprint is ``hash(code subtree, config)`` where config carries the
training inputs that matter (seasons, source, nrounds override). Each train
entrypoint computes it, skips when unchanged (unless ``--force``), and records
it beside its outputs in ``.fingerprints.json``. Feature lists and
hyperparameters live in the code subtree (``constants.py``), so they are part
of the code digest by construction.

The ledger (``models/ledger.jsonl``, committed) appends one line per trained
model per run. ``in_published_data`` starts ``false`` and is flipped only when
a pbp reprocess actually ships scores from the new model — never at train time.
CI runs append on the runner only (the workflow has ``contents: read``); those
lines travel in the uploaded run artifact, and local/manual retrains commit
theirs.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

FINGERPRINT_STORE = ".fingerprints.json"


def code_digest(subtree: Path) -> str:
    """sha256 over every .py file in the subtree (path + bytes, sorted)."""
    h = hashlib.sha256()
    for p in sorted(subtree.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        h.update(p.relative_to(subtree).as_posix().encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def compute(subtree: Path, config: dict) -> str:
    """Fingerprint = hash(code subtree, canonical-JSON config). 16 hex chars."""
    h = hashlib.sha256()
    h.update(code_digest(subtree).encode())
    h.update(json.dumps(config, sort_keys=True, default=str).encode())
    return h.hexdigest()[:16]


def _load(store_path: Path) -> dict:
    try:
        return json.loads(store_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def should_skip(
    store_path: Path, key: str, fp: str, artifacts: list[Path], force: bool = False
) -> bool:
    """True iff the stored fingerprint matches AND every artifact exists."""
    if force:
        return False
    if _load(store_path).get(key) != fp:
        return False
    return bool(artifacts) and all(Path(a).is_file() for a in artifacts)


def record(store_path: Path, key: str, fp: str) -> None:
    store = _load(store_path)
    store[key] = fp
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text(json.dumps(store, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_ledger(ledger_path: Path, entry: dict) -> None:
    """Append one JSON line; stamps ``ts`` (UTC ISO) if absent."""
    entry = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **entry}
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True, default=str) + "\n")
