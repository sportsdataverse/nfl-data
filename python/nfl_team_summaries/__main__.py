"""CLI: build (and optionally publish) the NFL season summaries.

Usage:
    python -m nfl_team_summaries --seasons 2025 --out out/nfl_team_summaries
    python -m nfl_team_summaries --seasons 1999:2025 --out out/nfl_team_summaries --publish
    python -m nfl_team_summaries --seasons 2025 --pbp-dir out/model_pbp   # local parquet, no download

Each table publishes to its own release tag on sportsdataverse-data, one
parquet per season (``{stem}_{season}.parquet``), mirroring ``nfl_model_pbp``.

``team_opponent_splits`` is built after the seven :data:`TABLES` and isolated
from them: it also needs nfl-raw's ESPN crosswalk, and a crosswalk failure
must not hold back a week of the other tags. If it fails for any season its
tag is skipped, the seven still publish, and the run exits 1.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import polars as pl

from nfl_team_summaries.build import build_team_opponent_splits, build_team_summaries
from nfl_team_summaries.crosswalk import load_espn_game_ids
from nfl_team_summaries.input import (
    DEFAULT_SEASON_TYPES,
    filter_season_types,
    load_model_pbp,
    load_rosters,
    prepare_plays,
)
from nfl_team_summaries.paper_index import attach_luck, season_games

REPO = "sportsdataverse/sportsdataverse-data"
#: table key -> (release tag, file stem)
TABLES = {
    "team_summaries": ("nfl_team_summaries", "team_summaries"),
    "passing": ("nfl_passing", "passing"),
    "rushing": ("nfl_rushing", "rushing"),
    "receiving": ("nfl_receiving", "receiving"),
    "percentiles": ("nfl_percentiles", "percentiles"),
    # player-side twin of `percentiles`: its own tag, because the grain differs
    # (percentile x position group, not percentile x team-game) and the team
    # table is already a published contract the site reads.
    "player_percentiles": ("nfl_player_percentiles", "player_percentiles"),
    "league_averages": ("nfl_league_averages", "league_averages"),
}
#: one row per team-game (regular season): opponent, EPA/play, success, points
SPLITS = ("nfl_team_opponent_splits", "team_opponent_splits")


def _parse_seasons(value: str) -> list[int]:
    if ":" in value:
        start, end = (int(p) for p in value.split(":", 1))
        if start > end:
            raise argparse.ArgumentTypeError(f"start {start} must be <= end {end}")
        return list(range(start, end + 1))
    return [int(value)]


def _write(df: pl.DataFrame, out: Path, tag: str, stem: str, season: int) -> Path:
    d = out / tag
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{stem}_{season}.parquet"
    df.write_parquet(path)
    logging.info("wrote %s (%d rows x %d cols)", path, df.height, df.width)
    return path


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
        "--espn-pbp-dir",
        default=None,
        help="Directory holding espn_nfl_pbp's play_by_play_{season}.parquet (else the "
        "release asset): the input of team_summaries' Paper Index luck columns.",
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
    splits_written: list[Path] = []
    splits_failed: list[int] = []
    for season in _parse_seasons(args.seasons):
        pbp = load_model_pbp(season, args.pbp_dir)
        plays = prepare_plays(pbp, season, season_types=season_types)
        if plays.height == 0:
            logging.warning("season %s: no scrimmage plays; nothing written", season)
            continue
        raw = filter_season_types(pbp, season_types)
        tables = build_team_summaries(plays, raw, season, rosters=load_rosters(season))
        # Paper Index deserved wins and luck. Attached after the build, so the
        # conference percentiles and league_averages in there never see these
        # outcome-derived columns; and cut by the plays' own game ids, so they
        # cover the games the play metrics cover (no playoff game by default).
        tables["team_summaries"] = attach_luck(
            tables["team_summaries"],
            season_games(season, plays["game_id"], args.espn_pbp_dir),
            season,
        )
        for key, (tag, stem) in TABLES.items():
            written[key].append(_write(tables[key], out, tag, stem, season))
        try:
            splits = build_team_opponent_splits(plays, raw, season, load_espn_game_ids())
        except Exception:
            logging.exception(
                "season %s: team_opponent_splits failed; %s skipped", season, SPLITS[0]
            )
            splits_failed.append(season)
        else:
            splits_written.append(_write(splits, out, *SPLITS, season))

    if args.publish:
        from nfl_model_publish.artifacts import upload_artifacts

        publish = [(tag, stem) for key, (tag, stem) in TABLES.items() if written[key]]
        if splits_written and not splits_failed:
            publish.append(SPLITS)
        for tag, stem in publish:
            result = upload_artifacts(
                out / tag, tag, REPO, pattern=f"{stem}_*.parquet", dry_run=args.dry_run
            )
            logging.info("published %d asset(s) to %s@%s", result["uploaded"], REPO, tag)
    if splits_failed:
        logging.error("%s NOT built for season(s) %s (see above)", SPLITS[0], splits_failed)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
