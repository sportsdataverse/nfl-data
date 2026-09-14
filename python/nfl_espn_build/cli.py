"""CLI for ``nfl_espn_build`` -- ``-s/-e`` seasons, one or every dataset.

    python -m nfl_espn_build --dataset pbp -s 2025 -e 2025
    python -m nfl_espn_build --dataset all -s 2002 -e 2026 --workers 4
    python -m nfl_espn_build --dataset adv_box -s 2025 -e 2025 --publish

Processing (the slow step, ~8 s a game) runs once per game into the final
cache; every dataset is then cut from the cache. ``--no-process`` builds from
whatever is cached; ``--reprocess`` rebuilds every final regardless of its
stamp.
"""

from __future__ import annotations

import argparse
import logging
import sys

from nfl_espn_build.build import build_season
from nfl_espn_build.config import ADV_ORDER, ALL_ORDER, REGISTRY
from nfl_espn_build.ingest import EspnStore, resolve_raw_root
from nfl_espn_build.process import process_season
from nfl_espn_build.publish import DEFAULT_REPO, publish_files

GROUPS = {"all": ALL_ORDER, "adv_box": ADV_ORDER}


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="nfl_espn_build", description=__doc__.split("\n\n")[0])
    ap.add_argument("--dataset", required=True, choices=sorted(REGISTRY) + sorted(GROUPS))
    ap.add_argument("-s", "--start-year", type=int, required=True)
    ap.add_argument("-e", "--end-year", type=int, default=None)
    ap.add_argument(
        "--raw-dir",
        default=None,
        help="nfl-raw checkout (or its nfl/espn); default: sibling, else HTTP",
    )
    ap.add_argument("--cache-dir", default=".cache/nfl_espn_final", help="per-game final cache")
    ap.add_argument("--out", default="out/espn_nfl", help="parquet output root")
    ap.add_argument("--workers", type=int, default=2, help="processor workers (spawned processes)")
    ap.add_argument(
        "--reprocess", action="store_true", help="rebuild every final, ignoring the cache stamp"
    )
    ap.add_argument("--no-process", action="store_true", help="build from cached finals only")
    ap.add_argument(
        "--publish", action="store_true", help="upload each season parquet to its espn_nfl_* tag"
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="with --publish: plan uploads, send nothing"
    )
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--verbose", action="store_true")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="[%(asctime)s] %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    log = logging.getLogger("nfl_espn_build")
    datasets = GROUPS.get(args.dataset, [args.dataset])
    end = args.end_year if args.end_year is not None else args.start_year
    seasons = list(range(args.start_year, end + 1))
    store = EspnStore(resolve_raw_root(args.raw_dir))
    log.info(
        "raw root: %s | seasons %s-%s | datasets %s", store.root, seasons[0], seasons[-1], datasets
    )

    failed = 0
    for season in seasons:
        if not args.no_process:
            tally = process_season(
                store, season, args.cache_dir, workers=args.workers, reprocess=args.reprocess
            )
            failed += tally.get("failed", 0)
        written = build_season(datasets, season, cache_dir=args.cache_dir, out=args.out)
        if args.publish:
            for name, path in written.items():
                if path is None:
                    continue
                publish_files(REGISTRY[name].tag, [path], repo=args.repo, dry_run=args.dry_run)
    if failed:
        log.error("%d game(s) failed to process; see the log", failed)
    return 1 if failed else 0
