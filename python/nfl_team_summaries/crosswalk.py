"""nflverse team abbreviation <-> ESPN team id.

Vendored as a 32-row CSV rather than fetched: the site's URL space is keyed on
ESPN ids and a build must not depend on ESPN answering. Captured from
``site.api.espn.com/apis/site/v2/sports/football/nfl/teams`` on 2026-09-09;
the two abbreviations that differ are Washington (nflverse ``WAS``, ESPN
``WSH``) and the Rams (nflverse ``LA``, ESPN ``LAR``). Relocated franchises in
old seasons resolve to the current club, matching nflverse's own
``team_abbr_mapping``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import polars as pl

_CSV = Path(__file__).with_name("data") / "espn_team_ids.csv"

#: pbp of relocated seasons carries the old abbreviation; same franchise, same ESPN id
HISTORICAL_ABBR = {"OAK": "LV", "SD": "LAC", "STL": "LA"}


def load_crosswalk() -> pl.DataFrame:
    """The 32-row table: nflverse_abbr, espn_team_id (Int64), espn_abbr, team_name, conference, division."""
    return pl.read_csv(_CSV, schema_overrides={"espn_team_id": pl.Int64})


def canonical_abbr(col: str) -> pl.Expr:
    """Fold a relocated abbreviation onto the current franchise."""
    return pl.col(col).replace(HISTORICAL_ABBR)


def attach_team_ids(df: pl.DataFrame, abbr_col: str, prefix: str) -> pl.DataFrame:
    """Join ``{prefix}_id`` (ESPN id as Utf8, the site's key dtype) onto ``abbr_col``.

    Raises:
        ValueError: if any non-null abbreviation has no ESPN id -- a silent null
            here would drop that team from every table downstream.
    """
    xw = load_crosswalk().select(
        pl.col("nflverse_abbr").alias("__abbr"),
        pl.col("espn_team_id").cast(pl.Utf8).alias(f"{prefix}_id"),
    )
    out = df.with_columns(canonical_abbr(abbr_col).alias("__abbr")).join(
        xw, on="__abbr", how="left"
    )
    missing = (
        out.filter(pl.col("__abbr").is_not_null() & pl.col(f"{prefix}_id").is_null())["__abbr"]
        .unique()
        .to_list()
    )
    if missing:
        raise ValueError(
            f"no ESPN team id for abbreviation(s) {sorted(missing)} in column {abbr_col!r}"
        )
    return out.drop("__abbr")


@lru_cache(maxsize=None)
def load_espn_game_ids(raw_dir: str | None = None) -> pl.DataFrame:
    """nflverse ``game_id`` -> ESPN event id, from nfl-raw's ``crosswalk/games.json``.

    The same crosswalk the ``espn_nfl_*`` family keys on (a local nfl-raw checkout,
    ``$NFL_RAW_DIR``, else raw.githubusercontent.com -- see
    :func:`nfl_espn_build.ingest.resolve_raw_root`). ESPN's library starts in 2002,
    so earlier nflverse games have no row. Columns: ``nflverse_game_id`` (Utf8),
    ``game_id`` (Int64, the ESPN event id).
    """
    from nfl_espn_build.ingest import EspnStore, resolve_raw_root

    rows = EspnStore(resolve_raw_root(raw_dir)).crosswalk_games()
    return pl.DataFrame(
        [(r["game_id"], r["espn_event_id"]) for r in rows if r.get("game_id")],
        schema={"nflverse_game_id": pl.Utf8, "game_id": pl.Int64},
        orient="row",
    )
