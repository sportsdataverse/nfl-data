"""Parity harness: diff the native reconstruction against nflverse load_nfl_pbp.

The correctness gate for the whole port. Joins on ``play_id`` (which aligns
exactly — native is a superset, since nflverse drops some admin/timeout rows)
and reports per-column match rates among rows where both sides are non-null.
``roof`` / ``spread_line`` for the native build are sourced from the nflverse
frame itself (the schedules data), closing the loop.

Live (downloads nflverse PBP): drive it from a gated test or a script.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import polars as pl

from native_pbp.build import build_pbp

# column -> comparison mode ("exact" | "tol"); tol uses |a-b| < 0.5 for floats.
DEFAULT_PARITY_COLUMNS: Dict[str, str] = {
    "down": "exact",
    "ydstogo": "exact",
    "yardline_100": "exact",
    "qtr": "exact",
    "half_seconds_remaining": "tol",
    "game_seconds_remaining": "tol",
    "score_differential": "exact",
    "posteam_timeouts_remaining": "exact",
    "defteam_timeouts_remaining": "exact",
    "pass_attempt": "exact",
    "rush_attempt": "exact",
    "complete_pass": "exact",
    "interception": "exact",
    "air_yards": "tol",
    "touchdown": "exact",
}


def compare_frames(
    native: pl.DataFrame,
    nflverse: pl.DataFrame,
    columns: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Per-column match rates between native and nflverse on the play_id join.

    Args:
        native: A native build frame (one or more games).
        nflverse: nflverse PBP filtered to the same game(s).
        columns: ``{column: "exact"|"tol"}`` map; defaults to
            :data:`DEFAULT_PARITY_COLUMNS`.

    Returns:
        ``{"joined": int, "columns": {col: {"matched","compared","rate"}}}``.
    """
    columns = columns or DEFAULT_PARITY_COLUMNS
    native = native.with_columns(pl.col("play_id").cast(pl.Int64))
    nflverse = nflverse.with_columns(pl.col("play_id").cast(pl.Int64))

    avail = [c for c in columns if c in native.columns and c in nflverse.columns]
    j = native.select(["play_id"] + avail).join(
        nflverse.select(["play_id"] + [pl.col(c).alias(f"nv_{c}") for c in avail]),
        on="play_id", how="inner",
    )
    report: Dict[str, Any] = {"joined": j.height, "columns": {}}
    for c in avail:
        sub = j.filter(pl.col(c).is_not_null() & pl.col(f"nv_{c}").is_not_null())
        compared = sub.height
        if compared == 0:
            report["columns"][c] = {"matched": 0, "compared": 0, "rate": None}
            continue
        if columns[c] == "tol":
            matched = sub.filter((pl.col(c).cast(pl.Float64) - pl.col(f"nv_{c}").cast(pl.Float64)).abs() < 0.5).height
        else:
            matched = sub.filter(pl.col(c).cast(pl.Float64) == pl.col(f"nv_{c}").cast(pl.Float64)).height
        report["columns"][c] = {"matched": matched, "compared": compared, "rate": matched / compared}
    return report


def _load_nflverse(season: int) -> pl.DataFrame:
    """Load one season of nflverse PBP as polars (cache off)."""
    from sportsdataverse.nfl import load_nfl_pbp, update_config

    update_config(cache_mode="off")
    nv = load_nfl_pbp(seasons=[season])
    if not isinstance(nv, pl.DataFrame):
        nv = pl.from_pandas(nv)
    return nv


def run_parity(
    season: int,
    game_ids: Optional[List[str]] = None,
    raw_dir: str = "nfl/raw",
    columns: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Build native PBP for the given games and diff vs nflverse for the season.

    roof / spread_line for each native build are read from the nflverse frame
    (its schedules-derived columns). Returns a per-game + aggregate report.

    Args:
        season: NFL season year.
        game_ids: Specific game_ids to check; all of the season's nflverse games
            when None.
        raw_dir: Root of the committed per-game library.
        columns: Override the comparison column map.

    Returns:
        ``{"season", "games": {gid: report}, "aggregate": {col: rate}}``.
    """
    import json
    from pathlib import Path

    nv_all = _load_nflverse(season)
    if game_ids is None:
        game_ids = nv_all["game_id"].unique().to_list()

    games: Dict[str, Any] = {}
    for gid in game_ids:
        raw_path = Path(raw_dir) / str(season) / f"{gid}.json"
        if not raw_path.exists():
            continue
        nv_g = nv_all.filter(pl.col("game_id") == gid)
        roof = nv_g["roof"][0] if "roof" in nv_g.columns and nv_g.height else None
        spread = nv_g["spread_line"][0] if "spread_line" in nv_g.columns and nv_g.height else None
        native = build_pbp(json.loads(raw_path.read_text(encoding="utf-8")),
                           roof=roof, spread_line=spread, game_id=gid)
        if native.height:
            games[gid] = compare_frames(native, nv_g, columns=columns)

    # Aggregate match rate per column across games.
    agg: Dict[str, Dict[str, int]] = {}
    for rep in games.values():
        for col, st in rep["columns"].items():
            a = agg.setdefault(col, {"matched": 0, "compared": 0})
            a["matched"] += st["matched"]
            a["compared"] += st["compared"]
    aggregate = {col: (a["matched"] / a["compared"] if a["compared"] else None) for col, a in agg.items()}
    return {"season": season, "games": games, "aggregate": aggregate}
