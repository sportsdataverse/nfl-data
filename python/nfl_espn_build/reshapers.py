"""Bespoke per-game reshapers (the cfb-data ports, NFL final payload).

Each takes one final payload (see :mod:`nfl_espn_build.process`) and returns a
frame stamped with the game identity, or an empty frame when the block is
absent -- the generic ``flat_block_frame`` handles every other dataset.
"""

from __future__ import annotations

from typing import Any, Callable

import polars as pl

from nfl_espn_build.reshape import _norm_cell, stamp_identity


def _dig(node: Any, *keys: str) -> Any:
    for k in keys:
        if not isinstance(node, dict):
            return None
        node = node.get(k)
    return node


def _int(v: Any) -> int | None:
    try:
        return None if v is None else int(v)
    except (TypeError, ValueError):
        return None


def _chr(v: Any) -> str | None:
    return None if v is None else str(v)


# --- pbp ------------------------------------------------------------------
def reshape_pbp(game: dict[str, Any]) -> pl.DataFrame:
    """The processor's plays, one row per play, every column kept.

    ``NFLPlayProcess`` already emits the released column set (EPA/WP, series,
    box-score flags, dotted ``drive.*`` / ``start.*`` / ``end.*`` fields, player
    names + ids); this only normalizes cells and stamps identity. Nothing is
    recomputed, so a re-run of the processor is the only way values change.
    """
    plays = game.get("plays") or []
    rows = [{k: _norm_cell(v) for k, v in p.items()} for p in plays if isinstance(p, dict)]
    if not rows:
        return pl.DataFrame()
    return stamp_identity(pl.from_dicts(rows, infer_schema_length=None), game, week=True)


# --- team_box -------------------------------------------------------------
def reshape_team_box(game: dict[str, Any]) -> pl.DataFrame:
    """Pivot ``boxscore.teams[].statistics`` (name -> displayValue) per team."""
    teams = _dig(game, "boxscore", "teams")
    if not teams:
        return pl.DataFrame()
    rows: list[dict[str, Any]] = []
    for t in teams:
        row: dict[str, Any] = {}
        for s in t.get("statistics") or []:
            name = s.get("name") or s.get("label") or "stat"
            dv = s.get("displayValue")
            if dv is None:
                dv = s.get("value")
            row[name] = _chr(dv)
        row["team_id"] = _int(_dig(t, "team", "id"))
        row["team_abbreviation"] = _dig(t, "team", "abbreviation")
        row["team_name"] = _dig(t, "team", "displayName")
        row["home_away"] = t.get("homeAway")
        rows.append(row)
    return stamp_identity(pl.from_dicts(rows, infer_schema_length=None), game, week=True)


# --- player_box -----------------------------------------------------------
def reshape_player_box(game: dict[str, Any]) -> pl.DataFrame:
    """One row per athlete per stat category; the category ``keys`` become columns."""
    groups = _dig(game, "boxscore", "players")
    if not groups:
        return pl.DataFrame()
    rows: list[dict[str, Any]] = []
    for grp in groups:
        tid = _int(_dig(grp, "team", "id"))
        for cat in grp.get("statistics") or []:
            keys = cat.get("keys") or []
            cname = cat.get("name")
            for a in cat.get("athletes") or []:
                vals = [_chr(x) for x in (a.get("stats") or [])]
                if len(keys) == len(vals) and len(keys) > 0:
                    row: dict[str, Any] = dict(zip(keys, vals))
                elif len(vals) > 0:
                    row = {f"stat_{i + 1}": v for i, v in enumerate(vals)}
                else:
                    row = {}
                row["category"] = cname
                row["athlete_id"] = _int(_dig(a, "athlete", "id"))
                row["athlete_name"] = _dig(a, "athlete", "displayName")
                row["jersey"] = _dig(a, "athlete", "jersey")
                row["team_id"] = tid
                rows.append(row)
    if not rows:
        return pl.DataFrame()
    return stamp_identity(pl.from_dicts(rows, infer_schema_length=None), game, week=True)


# --- drives ---------------------------------------------------------------
def _drive_to_row(d: dict[str, Any]) -> dict[str, Any]:
    return {
        "drive_id": d.get("id"),
        "team_id": _int(_dig(d, "team", "id")),
        "result": d.get("result"),
        "display_result": d.get("displayResult"),
        "short_display_result": d.get("shortDisplayResult"),
        "description": d.get("description"),
        "yards": d.get("yards"),
        "offensive_plays": d.get("offensivePlays"),
        "is_score": d.get("isScore"),
        "start_period": _dig(d, "start", "period", "number"),
        "start_yard_line": _dig(d, "start", "yardLine"),
        "start_clock": _dig(d, "start", "clock", "displayValue"),
        "start_text": _dig(d, "start", "text"),
        "end_period": _dig(d, "end", "period", "number"),
        "end_yard_line": _dig(d, "end", "yardLine"),
        "end_clock": _dig(d, "end", "clock", "displayValue"),
        "time_elapsed": _dig(d, "timeElapsed", "displayValue"),
        "n_plays": len(d.get("plays") or []),
    }


def reshape_drives(game: dict[str, Any]) -> pl.DataFrame:
    """Unroll ``drives`` ({previous, current} or a bare list) to one row per drive."""
    dv = game.get("drives")
    if not dv:
        return pl.DataFrame()
    if isinstance(dv, dict) and ("previous" in dv or "current" in dv):
        all_drives = (dv.get("previous") or []) + (dv.get("current") or [])
    elif isinstance(dv, dict):
        all_drives = []
        for v in dv.values():
            all_drives.extend(v if isinstance(v, list) else [v])
    else:
        all_drives = []
        for v in dv:
            all_drives.extend(v if isinstance(v, list) else [v])
    all_drives = [d for d in all_drives if isinstance(d, dict) and d.get("id") is not None]
    if not all_drives:
        return pl.DataFrame()
    rows = [_drive_to_row(d) for d in all_drives]
    return stamp_identity(pl.from_dicts(rows, infer_schema_length=None), game, week=True)


RESHAPERS: dict[str, Callable[[dict[str, Any]], pl.DataFrame]] = {
    "pbp": reshape_pbp,
    "team_box": reshape_team_box,
    "player_box": reshape_player_box,
    "drives": reshape_drives,
}
