"""CLI entry point for nfl_data_ingest.

Usage:
    python -m nfl_data_ingest --seasons 2024:2024 --cache-dir .cache/nfl_raw
    python -m nfl_data_ingest --seasons 2020:2024 --cache-dir /data/nfl_cache
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from nfl_data_ingest.fetch import ingest_season


def _parse_seasons(value: str) -> list[int]:
    """Parse ``START:END`` or a single year into a list of season ints."""
    if ":" in value:
        parts = value.split(":", 1)
        start, end = int(parts[0]), int(parts[1])
        if start > end:
            raise argparse.ArgumentTypeError(
                f"Season range start {start} must be <= end {end}"
            )
        return list(range(start, end + 1))
    return [int(value)]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m nfl_data_ingest",
        description="Fetch nfl-raw committed per-game JSON into a local cache.",
    )
    parser.add_argument(
        "--seasons",
        required=True,
        help="Season(s) to ingest.  Single year (e.g. 2024) or range (e.g. 2020:2024).",
    )
    parser.add_argument(
        "--cache-dir",
        default=".cache/nfl_raw",
        help="Root cache directory (default: .cache/nfl_raw).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Re-fetch games that are already cached.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable debug logging.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    try:
        seasons = _parse_seasons(args.seasons)
    except (ValueError, argparse.ArgumentTypeError) as exc:
        print(f"error: invalid --seasons value: {exc}", file=sys.stderr)
        return 1

    cache_dir = Path(args.cache_dir)
    for season in seasons:
        print(f"Ingesting season {season} -> {cache_dir / str(season)}")
        ingest_season(season, cache_dir=cache_dir, force=args.force)
        print(f"  season {season} done.")

    return 0
