"""CLI entrypoint for nfl_model_publish.

Usage::

    python -m nfl_model_publish artifacts \\
        --models <dir> \\
        [--tag nfl_model_artifacts] \\
        [--repo sportsdataverse/sportsdataverse-data] \\
        [--dry-run]

    python -m nfl_model_publish rosters \\
        --seasons 2022:2024 \\
        --out <dir> \\
        [--tag nfl_rosters] \\
        [--repo sportsdataverse/sportsdataverse-data] \\
        [--dry-run]

    python -m nfl_model_publish players \\
        --out <dir> \\
        [--tag nfl_players] \\
        [--repo sportsdataverse/sportsdataverse-data] \\
        [--dry-run]
"""
from __future__ import annotations

import argparse

from .artifacts import upload_artifacts


def _parse_seasons(spec: str) -> list[int]:
    """Parse a ``"start:end"`` (inclusive) or single ``"year"`` season spec.

    Args:
        spec: Either ``"2022:2024"`` (inclusive range) or a single ``"2023"``.

    Returns:
        Ascending list of seasons.

    Raises:
        argparse.ArgumentTypeError: On malformed input or an inverted range.
    """
    try:
        if ":" in spec:
            lo_s, hi_s = spec.split(":", 1)
            lo, hi = int(lo_s), int(hi_s)
        else:
            lo = hi = int(spec)
    except ValueError as exc:  # noqa: BLE001 - re-raise as argparse error
        raise argparse.ArgumentTypeError(
            f"invalid --seasons {spec!r}: expected 'YYYY' or 'YYYY:YYYY'"
        ) from exc
    if hi < lo:
        raise argparse.ArgumentTypeError(
            f"invalid --seasons {spec!r}: end {hi} precedes start {lo}"
        )
    return list(range(lo, hi + 1))


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

    r = sub.add_parser("rosters", help="Build + upload SDV-native NFL season rosters.")
    r.add_argument(
        "--seasons",
        required=True,
        type=_parse_seasons,
        help="Season range 'YYYY:YYYY' (inclusive) or a single 'YYYY'.",
    )
    r.add_argument("--out", required=True, help="Output directory for roster_{season}.parquet files.")
    r.add_argument("--tag", default="nfl_rosters", help="GitHub release tag.")
    r.add_argument(
        "--repo",
        default="sportsdataverse/sportsdataverse-data",
        help="Target GitHub repository (owner/name).",
    )
    r.add_argument("--dry-run", action="store_true", help="Build but do not upload.")

    p = sub.add_parser("players", help="Build + upload the SDV-native NFL player index.")
    p.add_argument("--out", required=True, help="Output directory for players.parquet.")
    p.add_argument("--tag", default="nfl_players", help="GitHub release tag.")
    p.add_argument(
        "--repo",
        default="sportsdataverse/sportsdataverse-data",
        help="Target GitHub repository (owner/name).",
    )
    p.add_argument("--dry-run", action="store_true", help="Build but do not upload.")

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
    elif args.cmd == "rosters":
        from .builders import build_rosters

        built = build_rosters(args.seasons, args.out)
        total_rows = sum(b["rows"] for b in built)
        res = upload_artifacts(
            args.out,
            args.tag,
            args.repo,
            pattern="roster_*.parquet",
            dry_run=args.dry_run,
        )
        created = " (created release)" if res.get("created_release") else ""
        suffix = " (dry-run)" if args.dry_run else ""
        print(
            f"publish: seasons={len(built)} rows={total_rows} "
            f"uploaded={res['uploaded']} files={len(res['files'])} "
            f"-> {args.repo}:{res['tag']}{created}{suffix}"
        )
    elif args.cmd == "players":
        from .builders import build_players

        built = build_players(args.out)
        res = upload_artifacts(
            args.out,
            args.tag,
            args.repo,
            pattern="players.parquet",
            dry_run=args.dry_run,
        )
        created = " (created release)" if res.get("created_release") else ""
        suffix = " (dry-run)" if args.dry_run else ""
        print(
            f"publish: rows={built['rows']} "
            f"uploaded={res['uploaded']} files={len(res['files'])} "
            f"-> {args.repo}:{res['tag']}{created}{suffix}"
        )
    return 0
