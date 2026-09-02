"""CLI for the nfl_ratings_weekly vintage job.

Usage:
    python -m nfl_ratings_weekly --seasons 1999:2025 --out out/nfl_ratings_weekly
    python -m nfl_ratings_weekly --seasons 2025 --out out/nfl_ratings_weekly --publish
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from nfl_ratings_weekly.builder import build_season

TAG = "nfl_ratings_weekly"
REPO = "sportsdataverse/sportsdataverse-data"


def _parse_seasons(value: str) -> list[int]:
    if ":" in value:
        start, end = (int(p) for p in value.split(":", 1))
        if start > end:
            raise argparse.ArgumentTypeError(f"start {start} must be <= end {end}")
        return list(range(start, end + 1))
    return [int(value)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m nfl_ratings_weekly",
        description="Build (and optionally publish) per-week as-of NFL ratings vintages.",
    )
    parser.add_argument("--seasons", required=True, help="Single year (2024) or range (2009:2025).")
    parser.add_argument(
        "--out", default="out/nfl_ratings_weekly", help="Output directory for parquet files."
    )
    parser.add_argument(
        "--publish", action="store_true", help=f"Upload assets to the {TAG} release on {REPO}."
    )
    parser.add_argument("--verbose", action="store_true", help="Debug logging.")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s"
    )

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for season in _parse_seasons(args.seasons):
        frame = build_season(season)
        if frame.height == 0:
            logging.warning("season %s produced no vintages; nothing written", season)
            continue
        path = out / f"nfl_ratings_weekly_{season}.parquet"
        frame.write_parquet(path)
        logging.info(
            "wrote %s (%d rows, weeks %s-%s)",
            path,
            frame.height,
            frame["as_of_week"].min(),
            frame["as_of_week"].max(),
        )
        written.append(path)
    if args.publish:
        if not written:
            # Every requested season produced zero vintages -- the pre-kickoff
            # state (build_season already logged why). A real failure raises
            # before we get here, so an empty run is a no-op, not an error.
            logging.warning("nothing to publish yet")
            return 0
        from nfl_model_publish.artifacts import upload_artifacts

        result = upload_artifacts(out, TAG, REPO, pattern="nfl_ratings_weekly_*.parquet")
        logging.info("published %d asset(s) to %s@%s", result["uploaded"], REPO, TAG)
    return 0


if __name__ == "__main__":
    sys.exit(main())
