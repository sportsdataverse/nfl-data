"""CLI entrypoint for the decision_models NFL model suite.

Usage::

    # Train everything + run the parity gate + write out/report.md
    python -m model_training.decision_models train-all

    # Fast smoke run (will NOT pass the parity gate)
    python -m model_training.decision_models train-all --nrounds 5 --out-dir out_smoke
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

# Windows consoles default to cp1252, which cannot encode the Unicode symbols in
# our progress output -> UnicodeEncodeError mid-run. Force UTF-8 at entry.
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def _cmd_train_all(args: argparse.Namespace) -> int:
    from model_training._stage import gate_status

    from .pipeline import SOFT_GATES, train_all

    results = train_all(
        out_dir=Path(args.out_dir),
        nrounds_override=args.nrounds,
        source=args.source,
        allow_missing_wp_cal_data=args.allow_missing_cal_data,
    )
    smoke = args.nrounds is not None
    gate_models = [m for m in ("xpass", "fd", "two_pt", "fg", "wp", "punt") if m in results]
    print("\n[decision_models] parity gate summary:")
    statuses = {}
    for m in gate_models:
        status = gate_status(results[m], soft_gate=m in SOFT_GATES, smoke=smoke)
        statuses[m] = status
        note = ""
        if m in SOFT_GATES:
            # two_pt parity is data-vintage-limited (~0.87) — a documented soft gate,
            # tolerated on failure and labelled SOFT in both directions so it is never
            # read as a hard-gate PASS. See pipeline.py report Notes.
            note = "  (soft gate: tolerated on failure, never a hard-gate pass)"
        elif status == "SKIPPED":
            note = f"  ({results[m].get('reason', 'no reason given')})"
        print(f"  {m:8s} -> {status}{note}  (corr/metric: see report.md)")
    hard_failed = [m for m, s in statuses.items() if s == "FAIL"]
    if hard_failed:
        print(f"[decision_models] FAILED gates: {hard_failed}")
        return 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="model_training.decision_models")
    sub = p.add_subparsers(dest="command", required=True)
    t = sub.add_parser("train-all", help="train every model + run the parity gate")
    t.add_argument("--out-dir", default="out", help="artifact + report output dir")
    t.add_argument("--nrounds", type=int, default=None, help="override nrounds (smoke runs)")
    t.add_argument("--source", default="nflverse", help="PBP source")
    t.add_argument(
        "--allow-missing-cal-data",
        action="store_true",
        help=(
            "record the nfl4th WP model as SKIPPED (report.md + summary) when cal_data.rds is "
            "absent instead of failing the run"
        ),
    )
    t.set_defaults(func=_cmd_train_all)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
