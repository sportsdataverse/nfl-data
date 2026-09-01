"""Shared runner for the numbered per-model stage scripts (``nfl_model_NN_*``).

Each stage script is a thin, individually-runnable pipeline for ONE model:
parse args -> fingerprint (skip when unchanged unless ``--force``) -> train via
the shared ``model_training`` package -> record fingerprint -> append a
``models/ledger.jsonl`` line -> fail the process on a hard gate failure.

The training logic stays in ``model_training`` (single implementation); this
layer owns per-model operability only. Run stages via
``python -m nfl_model_NN_<model>`` or ``scripts/nfl_models.sh``.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable, Optional

from model_training import fingerprint as fp

REPO_ROOT = Path(__file__).resolve().parents[2]
LEDGER = REPO_ROOT / "models" / "ledger.jsonl"
# nflverse pbp floor .. last completed season — matches decision_models
# FULL_HISTORY and the registry's "trained on 1999-present".
DEFAULT_SEASONS = ["1999", "2025"]


def parse_seasons(values: list[str]) -> list[int]:
    """1 value = single season; 2 = inclusive range; 3+ = explicit list."""
    seasons = [int(v) for v in values]
    if len(seasons) == 2:
        start, end = seasons
        return list(range(start, end + 1))
    return seasons


def play_level_parser(name: str, *, xyac: bool = False) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=f"python -m nfl_model_NN_{name}")
    p.add_argument("--seasons", nargs="+", default=DEFAULT_SEASONS, metavar="YEAR")
    p.add_argument("--data-dir", default="data", metavar="DIR")
    p.add_argument("--models-dir", default="models", metavar="DIR")
    p.add_argument("--download", action="store_true")
    p.add_argument(
        "--force", action="store_true", help="retrain even when the fingerprint is unchanged"
    )
    if xyac:
        p.add_argument("--source", choices=["nflverse", "native"], default="nflverse")
        p.add_argument("--xyac-model", default="models/xyac_model.ubj", metavar="PATH")
    return p


def decision_parser(name: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=f"python -m nfl_model_NN_{name}")
    p.add_argument("--out-dir", default="out", metavar="DIR")
    p.add_argument(
        "--nrounds",
        type=int,
        default=None,
        metavar="N",
        help="override nrounds (smoke runs; gates become informational)",
    )
    p.add_argument("--source", default="nflverse")
    p.add_argument(
        "--force", action="store_true", help="retrain even when the fingerprint is unchanged"
    )
    return p


def run_stage(
    *,
    name: str,
    suite: str,
    config: dict,
    artifacts: list[Path],
    train: Callable[[], Optional[dict]],
    force: bool = False,
    soft_gate: bool = False,
    smoke: bool = False,
) -> int:
    """Fingerprint-gated train run for one model; returns a process rc."""
    suite_dir = REPO_ROOT / "python" / "model_training" / suite
    store = artifacts[0].parent / fp.FINGERPRINT_STORE
    digest = fp.compute(suite_dir, config)
    if fp.should_skip(store, name, digest, artifacts, force):
        print(f"[{name}] fingerprint unchanged + artifacts present -> skip (--force to retrain)")
        return 0

    gates = train()  # None, or a validate_* result dict with gate_pass

    fp.record(store, name, digest)
    fp.append_ledger(
        LEDGER,
        {
            "suite": suite,
            "model": name,
            "fingerprint": digest,
            "config": config,
            "artifacts": [a.name for a in artifacts],
            "gates": gates,
            "delta_vs_champion": None,  # champion comparison happens at publish decision
            "in_published_data": False,  # flipped only when a reprocess ships the scores
        },
    )

    if gates is not None and gates.get("gate_pass") is False and not gates.get("skipped"):
        tag = "SOFT-FAIL" if soft_gate else ("FAIL (smoke run, tolerated)" if smoke else "FAIL")
        print(f"[{name}] parity gate: {tag}")
        if not soft_gate and not smoke:
            return 1
    missing = [a for a in artifacts if not a.is_file()]
    if missing:
        print(f"[{name}] ERROR: expected artifact(s) not written: {missing}")
        return 1
    print(f"[{name}] done -> {[str(a) for a in artifacts]}")
    return 0
