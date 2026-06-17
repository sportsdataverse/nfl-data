"""CLI entrypoint for nfl_model_publish.

Usage::

    python -m nfl_model_publish artifacts \\
        --models <dir> \\
        [--tag nfl_model_artifacts] \\
        [--repo sportsdataverse/sportsdataverse-data] \\
        [--dry-run]
"""
from __future__ import annotations

import argparse

from .artifacts import upload_artifacts


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="nfl_model_publish")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("artifacts", help="Upload NFL model artifacts (.ubj + cards) to a release.")
    a.add_argument("--models", required=True, help="Directory containing *.ubj model files.")
    a.add_argument("--tag", default="nfl_model_artifacts", help="GitHub release tag.")
    a.add_argument(
        "--repo",
        default="sportsdataverse/sportsdataverse-data",
        help="Target GitHub repository (owner/name).",
    )
    a.add_argument("--dry-run", action="store_true", help="Print actions without executing them.")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "artifacts":
        res = upload_artifacts(args.models, args.tag, args.repo, dry_run=args.dry_run)
        created = " (created release)" if res.get("created_release") else ""
        suffix = " (dry-run)" if args.dry_run else ""
        print(
            f"publish: uploaded={res['uploaded']} files={len(res['files'])} "
            f"-> {args.repo}:{res['tag']}{created}{suffix}"
        )
    return 0
