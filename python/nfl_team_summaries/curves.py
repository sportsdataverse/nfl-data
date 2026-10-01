"""Stage 07 -- ``nfl_metric_curves``: league / team / player rate curves along a continuous axis.

FG% by kick distance, completion% and EPA by air-yards bucket, 4th-down conversion
by yards to go and success by down x distance, each bucket with attempts,
successes, rate and EPA/attempt: ``sportsdataverse.metric_curves`` over ONE season
of ``nfl_model_pbp`` (regular season + postseason, the adapter's population). The
NFL twin of cfbfastR-cfb-data's stage 65; the span is the ``nfl_model_pbp`` span,
and a season whose pbp carries no air yards simply has no air-yards rows (an
empty bucket is absent, never zero).

Ids. Teams are keyed the way stage 06 keys them: ``entity_id`` on team rows and
``team_id`` on player rows are the ESPN team id as text via the vendored
crosswalk (``nfl_team_summaries/data/espn_team_ids.csv``); ``entity_name`` keeps
the nflverse abbreviation. Player rows leave the adapter on nflfastR gsis ids and
are re-keyed to the ESPN athlete id through sdv-py's players master
(``nfl_players_crosswalk``), with ``gsis_id`` kept as an added column. A gsis id
with no ESPN match keeps ``entity_id = gsis_id`` and ``id_source = "gsis"``: the
row is never dropped and its namespace is stated per row; every other row is
``espn``. Nothing is ever cast through float.

Publishing differs from stage 06 on purpose. Stage 06 uploads ``{stem}_*.parquet``,
EVERY season file in its output directory, so a per-season backfill loop over one
``--out`` re-uploads every earlier season on each pass (~3k uploads drained the
API quota on 2026-09-30). This stage uploads only the files it just wrote, one
exact file name per season.

Usage::

    python -m nfl_data_07_metric_curves --seasons 2024 --pbp-dir nfl/model_pbp --out out/nfl_metric_curves
    python -m nfl_data_07_metric_curves --seasons 1999:2025 --out out/nfl_metric_curves --publish
"""

from __future__ import annotations

import argparse
import logging
import sys
from functools import lru_cache
from pathlib import Path

import polars as pl
from sportsdataverse.metric_curves import (
    NFLFASTR_ATTEMPT_COLUMNS,
    OUTPUT_SCHEMA,
    metric_curves,
    nflfastr_attempts,
)

from nfl_team_summaries.__main__ import REPO, _parse_seasons
from nfl_team_summaries.crosswalk import attach_team_ids
from nfl_team_summaries.input import load_model_pbp

TAG = "nfl_metric_curves"
STEM = "metric_curves"
#: the sdv-py contract plus the nflfastR id a player row was re-keyed from
SCHEMA: dict[str, pl.DataType] = {**OUTPUT_SCHEMA, "gsis_id": pl.Utf8}
_SORT = ["metric", "entity_type", "entity_id", "season", "down", "x_lo"]


@lru_cache(maxsize=1)
def gsis_to_espn() -> pl.DataFrame:
    """``gsis_id`` -> ``espn_id`` (both Utf8, one row per gsis id) from sdv-py's players master.

    Loaded once per process (the season loop reuses it).

    Raises:
        ValueError: the master is empty (sdv-py degrades a failed load to an empty
            frame, which would silently publish a whole season on gsis ids) or an
            ``espn_id`` is not an integer string.
    """
    from sportsdataverse.nfl import nfl_players_crosswalk

    xw = (
        nfl_players_crosswalk()
        .select("gsis_id", "espn_id")
        .drop_nulls()
        .unique(subset=["gsis_id"], keep="first", maintain_order=True)
    )
    if xw.height == 0:
        raise ValueError("players master has no gsis_id -> espn_id rows (load failed?)")
    not_int = pl.col("espn_id").str.contains(r"^\d+$") == False  # noqa: E712 -- explicit mask, repo convention
    bad = xw.filter(not_int)["espn_id"].head(5).to_list()
    if bad:
        raise ValueError(f"players master espn_id is not an integer string: {bad}")
    return xw


def build_metric_curves(
    season: int, pbp: pl.DataFrame, *, players: pl.DataFrame | None = None
) -> pl.DataFrame:
    """One season's ``nfl_metric_curves`` rows (:data:`SCHEMA`) from its ``nfl_model_pbp``.

    Args:
        season: the season (logging only; the rows carry the pbp's ``season``).
        pbp: the season's ``nfl_model_pbp`` frame (any extra columns are ignored).
        players: injectable ``gsis_id`` / ``espn_id`` map (Utf8); ``None`` loads
            :func:`gsis_to_espn`.

    Returns:
        pl.DataFrame: league, team and player rows; the empty contract frame when
        the pbp yields no attempt.
    """
    curves = metric_curves(
        # the model_pbp schema is uniform across seasons; a missing column fails here, at the boundary
        nflfastr_attempts(pbp.select(NFLFASTR_ATTEMPT_COLUMNS)),
        "nfl",
    )
    if curves.height == 0:
        return pl.DataFrame(schema=SCHEMA)

    team = pl.col("entity_type") == "team"
    player = pl.col("entity_type") == "player"
    # teams: the adapter emits nflverse abbreviations; stage 06's crosswalk raises on an unknown one
    curves = attach_team_ids(
        curves.with_columns(
            __abbr=pl.when(team).then(pl.col("entity_id")).when(player).then(pl.col("team_id"))
        ),
        "__abbr",
        "__espn",
    )
    xw = players if players is not None else gsis_to_espn()
    xw = xw.select("gsis_id", pl.col("espn_id").alias("__player"))
    assert curves.schema["entity_id"] == xw.schema["gsis_id"] == pl.Utf8
    assert xw["gsis_id"].n_unique() == xw.height
    out = curves.with_columns(__gsis=pl.when(player).then(pl.col("entity_id"))).join(
        xw, left_on="__gsis", right_on="gsis_id", how="left"
    )
    assert out.height == curves.height
    unmatched = out.filter(player & pl.col("__player").is_null())["entity_id"].unique().sort()
    n_players = out.filter(player)["entity_id"].n_unique()
    logging.info(
        "season %s: %d/%d player ids re-keyed gsis -> espn (%.1f%%); unmatched: %s",
        season,
        n_players - unmatched.len(),
        n_players,
        100.0 * (n_players - unmatched.len()) / max(n_players, 1),
        unmatched.head(5).to_list(),
    )
    out = out.with_columns(
        gsis_id=pl.when(player).then(pl.col("entity_id")),
        entity_id=pl.when(team)
        .then(pl.col("__espn_id"))
        .when(player & pl.col("__player").is_not_null())
        .then(pl.col("__player"))
        .otherwise(pl.col("entity_id")),
        team_id=pl.when(player).then(pl.col("__espn_id")).otherwise(pl.col("team_id")),
        id_source=pl.when(player & pl.col("__player").is_null())
        .then(pl.lit("gsis"))
        .otherwise(pl.lit("espn")),
    )
    return out.select(list(SCHEMA)).cast(SCHEMA).sort(_SORT, nulls_last=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m nfl_data_07_metric_curves", description=__doc__.split("\n\n")[0]
    )
    parser.add_argument("--seasons", required=True, help="Single year (2025) or range (1999:2025).")
    parser.add_argument(
        "--out", default="out/nfl_metric_curves", help=f"Output dir: {STEM}_{{season}}.parquet."
    )
    parser.add_argument(
        "--pbp-dir",
        default=None,
        help="Directory holding model_pbp_{season}.parquet (else the release asset).",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help=f"Upload each season file written by THIS run to {TAG} on {REPO}.",
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
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for season in _parse_seasons(args.seasons):
        curves = build_metric_curves(season, load_model_pbp(season, args.pbp_dir))
        if curves.height == 0:
            logging.warning("season %s: no attempts; nothing written", season)
            continue
        path = out / f"{STEM}_{season}.parquet"
        curves.write_parquet(path)
        logging.info("wrote %s (%d rows x %d cols)", path, curves.height, curves.width)
        written.append(path)

    if args.publish:
        from nfl_model_publish.artifacts import upload_artifacts

        # one exact file per call: a stale season sitting in --out is never re-uploaded
        for path in written:
            result = upload_artifacts(
                path.parent, TAG, REPO, pattern=path.name, dry_run=args.dry_run
            )
            logging.info("published %d asset(s) to %s@%s", result["uploaded"], REPO, TAG)
    return 0


if __name__ == "__main__":
    sys.exit(main())
