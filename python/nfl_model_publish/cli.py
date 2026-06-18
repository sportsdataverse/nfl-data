"""CLI entrypoint for nfl_model_publish.

Usage::

    python -m nfl_model_publish artifacts \\
        --models <dir> \\
        [--tag nfl_model_artifacts] \\
        [--repo sportsdataverse/sportsdataverse-data] \\
        [--dry-run]

    python -m nfl_model_publish pbp \\
        --parquet-dir <dir> \\
        [--tag nfl_model_pbp] \\
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

    p = sub.add_parser("pbp", help="Upload compiled model-PBP parquet files to a release.")
    p.add_argument(
        "--parquet-dir",
        required=True,
        help="Directory containing model_pbp_*.parquet files.",
    )
    p.add_argument("--tag", default="nfl_model_pbp", help="GitHub release tag.")
    p.add_argument(
        "--repo",
        default="sportsdataverse/sportsdataverse-data",
        help="Target GitHub repository (owner/name).",
    )
    p.add_argument("--dry-run", action="store_true", help="Print actions without executing them.")
    return ap


def _print_result(res: dict, repo: str, dry_run: bool) -> None:
    created = " (created release)" if res.get("created_release") else ""
    suffix = " (dry-run)" if dry_run else ""
    print(
        f"publish: uploaded={res['uploaded']} files={len(res['files'])} "
        f"-> {repo}:{res['tag']}{created}{suffix}"
    )


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "artifacts":
        res = upload_artifacts(args.models, args.tag, args.repo, dry_run=args.dry_run)
        _print_result(res, args.repo, args.dry_run)
    elif args.cmd == "pbp":
        res = upload_artifacts(
            args.parquet_dir,
            args.tag,
            args.repo,
            pattern="model_pbp_*.parquet",
            dry_run=args.dry_run,
        )
        _print_result(res, args.repo, args.dry_run)
    return 0
