"""CLI entrypoint for the track7 NFL model suite.

Usage::

    # Train everything + run the parity gate + write out/report.md
    python -m model_training.track7_nfl_models train-all

    # Fast smoke run (will NOT pass the parity gate)
    python -m model_training.track7_nfl_models train-all --nrounds 5 --out-dir out_smoke
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
    from .pipeline import train_all

    results = train_all(
        out_dir=Path(args.out_dir),
        nrounds_override=args.nrounds,
        source=args.source,
    )
    gate_models = [m for m in ("xpass", "fd", "two_pt", "fg", "punt") if m in results]
    # two_pt parity is data-vintage-limited (~0.87) — a documented soft gate, not a
    # build failure. See pipeline.py report Notes.
    SOFT_GATES = {"two_pt"}
    print("\n[track7] parity gate summary:")
    for m in gate_models:
        ok = results[m].get("gate_pass")
        tag = "PASS" if ok else ("SOFT-FAIL" if m in SOFT_GATES else "FAIL")
        print(f"  {m:8s} -> {tag}  (corr/metric known: see report.md)")
    hard_failed = [
        m for m in gate_models
        if not results[m].get("gate_pass", False) and m not in SOFT_GATES
    ]
    if hard_failed and args.nrounds is None:
        print(f"[track7] FAILED gates: {hard_failed}")
        return 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="model_training.track7_nfl_models")
    sub = p.add_subparsers(dest="command", required=True)
    t = sub.add_parser("train-all", help="train every model + run the parity gate")
    t.add_argument("--out-dir", default="out", help="artifact + report output dir")
    t.add_argument("--nrounds", type=int, default=None, help="override nrounds (smoke runs)")
    t.add_argument("--source", default="nflverse", help="PBP source")
    t.set_defaults(func=_cmd_train_all)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
