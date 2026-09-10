"""CLI: build (and optionally publish) the NFL season summaries.

Usage:
    python -m nfl_team_summaries --seasons 2025 --out out/nfl_team_summaries
    python -m nfl_team_summaries --seasons 1999:2025 --out out/nfl_team_summaries --publish
    python -m nfl_team_summaries --seasons 2025 --pbp-dir out/model_pbp   # local parquet, no download

Each table publishes to its own release tag on sportsdataverse-data, one
parquet per season (``{stem}_{season}.parquet``), mirroring ``nfl_model_pbp``.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import polars as pl

from nfl_team_summaries.build import build_team_summaries
from nfl_team_summaries.input import (
    DEFAULT_SEASON_TYPES,
    filter_season_types,
    load_model_pbp,
    prepare_plays,
)

REPO = "sportsdataverse/sportsdataverse-data"
#: table key -> (release tag, file stem)
TABLES = {
    "team_summaries": ("nfl_team_summaries", "team_summaries"),
    "passing": ("nfl_passing", "passing"),
    "rushing": ("nfl_rushing", "rushing"),
    "receiving": ("nfl_receiving", "receiving"),
    "percentiles": ("nfl_percentiles", "percentiles"),
}


def _parse_seasons(value: str) -> list[int]:
    if ":" in value:
        start, end = (int(p) for p in value.split(":", 1))
        if start > end:
            raise argparse.ArgumentTypeError(f"start {start} must be <= end {end}")
        return list(range(start, end + 1))
    return [int(value)]


def build_season(
    season: int, *, pbp_dir: str | None, season_types=DEFAULT_SEASON_TYPES
) -> dict[str, pl.DataFrame]:
    pbp = load_model_pbp(season, pbp_dir)
    plays = prepare_plays(pbp, season, season_types=season_types)
    if plays.height == 0:
        return {}
    return build_team_summaries(plays, filter_season_types(pbp, season_types), season)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m nfl_team_summaries", description=__doc__.split("\n\n")[0]
    )
    parser.add_argument("--seasons", required=True, help="Single year (2025) or range (1999:2025).")
    parser.add_argument(
        "--out", default="out/nfl_team_summaries", help="Output root; one subdir per table."
    )
    parser.add_argument(
        "--pbp-dir",
        default=None,
        help="Directory holding model_pbp_{season}.parquet (else the release asset).",
    )
    parser.add_argument(
        "--season-types",
        default=",".join(DEFAULT_SEASON_TYPES),
        help="Comma list of season_type values to include (default REG).",
    )
    parser.add_argument(
        "--publish", action="store_true", help=f"Upload each table to its release tag on {REPO}."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="With --publish: print what would upload."
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s"
    )

    out = Path(args.out)
    season_types = tuple(s.strip() for s in args.season_types.split(",") if s.strip())
    written: dict[str, list[Path]] = {k: [] for k in TABLES}
    for season in _parse_seasons(args.seasons):
        tables = build_season(season, pbp_dir=args.pbp_dir, season_types=season_types)
        if not tables:
            logging.warning("season %s: no scrimmage plays; nothing written", season)
            continue
        for key, (tag, stem) in TABLES.items():
            df = tables[key]
            d = out / tag
            d.mkdir(parents=True, exist_ok=True)
            path = d / f"{stem}_{season}.parquet"
            df.write_parquet(path)
            written[key].append(path)
            logging.info("wrote %s (%d rows x %d cols)", path, df.height, df.width)

    if args.publish:
        from nfl_model_publish.artifacts import upload_artifacts

        for key, (tag, stem) in TABLES.items():
            if not written[key]:
                continue
            result = upload_artifacts(
                out / tag, tag, REPO, pattern=f"{stem}_*.parquet", dry_run=args.dry_run
            )
            logging.info("published %d asset(s) to %s@%s", result["uploaded"], REPO, tag)
    return 0


if __name__ == "__main__":
    sys.exit(main())
