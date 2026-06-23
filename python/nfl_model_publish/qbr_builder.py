"""Build SDV-native ESPN Total QBR datasets (season-level + week-level).

Mirrors nflverse's ``espn_data`` release files ``qbr_season_level.parquet`` /
``qbr_week_level.parquet`` (produced upstream by ``espnscrapeR``) by scraping
ESPN's ``fitt/v3`` QBR web endpoint and reshaping to the same tidy column schema.
The published ``nfl_espn_qbr`` release feeds ``load_nfl_espn_qbr(source="sdv")``
in sdv-py, so the column names / dtypes here MUST match the nflverse schema.

Provenance notes (verified live against the 2024 ESPN payloads + nflverse parquet):

* Endpoint: ``site.web.api.espn.com/apis/fitt/v3/sports/football/nfl/qbr``
  (the same source ``espnscrapeR`` uses -- the Core-v2 ``.../qbr/{split}`` route
  404s and is NOT used).
* ``categories[0].totals`` decodes 1:1 (confirmed against ``categories[0].names``)
  to ``[qbr_total, pts_added, qb_plays, epa_total, pass, run, exp_sack, penalty,
  qbr_raw, sack]``.
* ``season_type`` is ``"Regular"`` (seasontype 2) / ``"Playoffs"`` (seasontype 3).
* Season-level ``game_week`` is the constant ``"Season Total"``; week-level uses
  the integer week plus ``"Week N"`` text.
* ``team`` is the team nickname (``athlete.teamName``); ``opp_team`` is the full
  opponent display name and ``opp_name`` its nickname.
* ``rank`` is NOT ESPN's integer ``ranks[0]`` -- nflverse uses R's average-tie
  ``rank(desc(qbr_total))`` (e.g. a two-way tie for first is ``1.5``), computed
  over the qualified rows only. We recompute it here to match.
* Week-level is qualified-only; season-level keeps qualified + unqualified rows
  (unqualified carry ``rank = null``).
"""

from __future__ import annotations

import time
from typing import Any, Iterator

import polars as pl
import requests

_QBR_URL = "https://site.web.api.espn.com/apis/fitt/v3/sports/football/nfl/qbr"
_HEADERS = {"User-Agent": "Mozilla/5.0 (sportsdataverse nfl-data qbr builder)"}
_SEASON_TYPES = {2: "Regular", 3: "Playoffs"}

# totals[] position -> nflverse column name (order from the live `categories[0].names`).
_TOTAL_COLS = [
    "qbr_total", "pts_added", "qb_plays", "epa_total", "pass",
    "run", "exp_sack", "penalty", "qbr_raw", "sack",
]
_FLOAT_COLS = [*_TOTAL_COLS, "rank"]

# Final column order (== nflverse qbr_{season,week}_level.parquet).
_SEASON_ORDER = [
    "season", "season_type", "game_week", "team_abb", "player_id", "name_short",
    "rank", *_TOTAL_COLS,
    "name_first", "name_last", "name_display", "headshot_href", "team", "qualified",
]
_WEEK_ORDER = [
    "season", "season_type", "game_id", "game_week", "week_text", "team_abb",
    "player_id", "name_short", "rank", *_TOTAL_COLS,
    "name_first", "name_last", "name_display", "headshot_href", "team",
    "opp_id", "opp_abb", "opp_team", "opp_name", "week_num", "qualified",
]

_PAGE_CAP = 50  # hard backstop against runaway pagination


def _to_float(x: Any) -> float | None:
    """Best-effort float; ESPN sends ``"-"`` for absent ranks/stats -> ``None``."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _common_fields(athlete: dict, season: int, season_type_label: str) -> dict:
    """Reshape the bio + ``categories[0].totals`` shared by season + week rows.

    Pure (no I/O): takes one ``athletes[]`` entry and returns the columns common
    to both grains. ``rank`` is left out here -- it is recomputed per group.
    """
    bio = athlete.get("athlete") or {}
    cats = athlete.get("categories") or [{}]
    totals = (cats[0] or {}).get("totals") or []
    pid = bio.get("id")
    row = {
        "season": season,
        "season_type": season_type_label,
        "team_abb": bio.get("teamShortName"),
        "player_id": str(pid) if pid is not None else None,
        "name_short": bio.get("shortName"),
        "name_first": bio.get("firstName"),
        "name_last": bio.get("lastName"),
        "name_display": bio.get("displayName"),
        "headshot_href": (bio.get("headshot") or {}).get("href"),
        "team": bio.get("teamName"),
    }
    for i, col in enumerate(_TOTAL_COLS):
        row[col] = _to_float(totals[i]) if i < len(totals) else None
    return row


def reshape_season_athlete(
    athlete: dict, season: int, season_type_label: str, qualified_ids: set[str]
) -> dict:
    """Pure reshape of one season-level ``athletes[]`` entry -> nflverse row."""
    row = _common_fields(athlete, season, season_type_label)
    row["game_week"] = "Season Total"
    row["qualified"] = row["player_id"] in qualified_ids
    return row


def reshape_week_athlete(athlete: dict, season: int, season_type_label: str) -> dict:
    """Pure reshape of one week-level ``athletes[]`` entry -> nflverse row.

    Week-level is qualified-only, so every emitted row is ``qualified=True``.
    """
    row = _common_fields(athlete, season, season_type_label)
    game = athlete.get("game") or {}
    opp = game.get("teamOpponent") or {}
    gid = game.get("id")
    opp_id = opp.get("id")
    row["game_id"] = str(gid) if gid is not None else None
    row["game_week"] = game.get("weekNumber")
    row["week_text"] = game.get("weekText")
    row["week_num"] = game.get("weekNumber")
    row["opp_id"] = str(opp_id) if opp_id is not None else None
    row["opp_abb"] = opp.get("abbreviation")
    row["opp_team"] = opp.get("displayName")
    row["opp_name"] = opp.get("nickname") or opp.get("name")
    row["qualified"] = True
    return row


def _fetch_athletes(
    qbr_type: str,
    season: int,
    seasontype: int,
    *,
    week: int | None = None,
    isqualified: bool = False,
    limit: int = 100,
    delay: float = 0.4,
) -> Iterator[dict]:
    """Yield every ``athletes[]`` entry across all pages for one query (I/O)."""
    page = 1
    while page <= _PAGE_CAP:
        params: dict[str, Any] = {
            "region": "us", "lang": "en", "qbrType": qbr_type,
            "seasontype": seasontype, "isqualified": str(isqualified).lower(),
            "limit": limit, "page": page, "season": season,
        }
        if week is not None:
            params["week"] = week
        resp = requests.get(_QBR_URL, params=params, headers=_HEADERS, timeout=30)
        if resp.status_code != 200:
            return
        payload = resp.json()
        for athlete in payload.get("athletes") or []:
            yield athlete
        pages = int((payload.get("pagination") or {}).get("pages", 1) or 1)
        if page >= pages:
            return
        page += 1
        time.sleep(delay)


def _qualified_ids(qbr_type: str, season: int, seasontype: int, week: int | None = None) -> set[str]:
    """Player-id set ESPN flags as qualified for one query (the ``isqualified=true`` list)."""
    out: set[str] = set()
    for athlete in _fetch_athletes(qbr_type, season, seasontype, week=week, isqualified=True):
        pid = (athlete.get("athlete") or {}).get("id")
        if pid is not None:
            out.add(str(pid))
    return out


def _finalize(rows: list[dict], order: list[str], rank_group: list[str]) -> pl.DataFrame:
    """Type-cast, recompute average-tie ``rank`` per group, and order columns.

    ``rank`` is computed over the *qualified rows only* (descending ``qbr_total``,
    average ties) to match nflverse; unqualified rows keep ``rank = null``. Note
    the ranking population must exclude unqualified rows -- unqualified passers can
    carry an inflated ``qbr_total`` (e.g. 100.0 on a single play), so ranking over
    the full group would corrupt the genuine leaders' ranks.
    """
    if not rows:
        return pl.DataFrame()
    df = pl.DataFrame(rows)
    cast_exprs = [pl.col(c).cast(pl.Float64) for c in _TOTAL_COLS if c in df.columns]
    cast_exprs.append(pl.col("season").cast(pl.Int32))
    if "week_num" in df.columns:
        cast_exprs.append(pl.col("week_num").cast(pl.Int32))
        if "game_week" in df.columns:  # week-level game_week is the integer week
            cast_exprs.append(pl.col("game_week").cast(pl.Int32))
    df = df.with_columns(cast_exprs)

    # Average-tie rank over the qualified subset only; unqualified rows -> null.
    qualified = df.filter(pl.col("qualified") == True).with_columns(  # noqa: E712
        pl.col("qbr_total")
        .rank(method="average", descending=True)
        .over(rank_group)
        .cast(pl.Float64)
        .alias("rank")
    )
    unqualified = df.filter(pl.col("qualified") == False).with_columns(  # noqa: E712
        pl.lit(None).cast(pl.Float64).alias("rank")
    )
    df = (
        pl.concat([qualified, unqualified], how="diagonal_relaxed")
        if unqualified.height
        else qualified
    )
    return df.select([c for c in order if c in df.columns])


def build_nfl_qbr_season(seasons: list[int], *, delay: float = 0.4) -> pl.DataFrame:
    """Build the season-level ESPN QBR frame (nflverse ``qbr_season_level`` shape)."""
    rows: list[dict] = []
    for season in seasons:
        for seasontype, label in _SEASON_TYPES.items():
            qualified = _qualified_ids("seasons", season, seasontype)
            for athlete in _fetch_athletes("seasons", season, seasontype, isqualified=False, delay=delay):
                rows.append(reshape_season_athlete(athlete, season, label, qualified))
    return _finalize(rows, _SEASON_ORDER, rank_group=["season", "season_type"])


def build_nfl_qbr_week(
    seasons: list[int],
    *,
    reg_weeks: range = range(1, 19),
    post_weeks: range = range(1, 6),
    delay: float = 0.4,
) -> pl.DataFrame:
    """Build the week-level ESPN QBR frame (nflverse ``qbr_week_level`` shape).

    Week-level is qualified-only, so only the ``isqualified=true`` list is
    fetched. A week that returns no athletes (e.g. a postseason round that did
    not occur) is simply skipped.
    """
    rows: list[dict] = []
    for season in seasons:
        for seasontype, label, weeks in ((2, "Regular", reg_weeks), (3, "Playoffs", post_weeks)):
            for week in weeks:
                for athlete in _fetch_athletes(
                    "weeks", season, seasontype, week=week, isqualified=True, delay=delay
                ):
                    rows.append(reshape_week_athlete(athlete, season, label))
    return _finalize(rows, _WEEK_ORDER, rank_group=["season", "season_type", "week_num"])
