"""Core play parser: Shield ``driveChart`` -> base nflverse-shape play frame.

Builds the play-level spine — one row per play with identifiers, possession,
down/distance/field-position, clock, play_type and per-play stat outcomes
(via :func:`native_pbp.stat_ids.sum_play_stats`). Downstream modules
(players/description/features/labels) enrich this frame; the parity harness
diffs it against ``sportsdataverse.nfl.load_nfl_pbp``.

Possession is resolved by assigning each play to the drive whose
``[startedPlaySequenceNumber, endedPlaySequenceNumber]`` range contains the
play's ``playSequenceNumber`` (the feed's ``driveSequence`` is unreliable).
Plays falling between drives (kickoffs / PATs / timeouts) get a null posteam.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import polars as pl

from model_training.track6_nfl_ep_wp.fetcher import _nflverse_abbr, _team_abbr, nflverse_game_id
from native_pbp.stat_ids import sum_play_stats


def _clock_to_seconds(clock: Optional[str]) -> Optional[int]:
    """Convert a ``"MM:SS"`` game clock to integer seconds remaining in the quarter."""
    if not clock or ":" not in clock:
        return None
    mm, ss = clock.split(":", 1)
    try:
        return int(mm) * 60 + int(ss)
    except ValueError:
        return None


def _yardline_100(yard_line: Optional[str], posteam: Optional[str]) -> Optional[int]:
    """Distance (yards) from the possession team to the opponent's goal line.

    ``"50"`` -> 50. ``"BAL 32"`` -> 68 if posteam is BAL (own 32), else 32.
    Returns None when the field position or possession is unknown.
    """
    if not yard_line or posteam is None:
        return None
    yard_line = yard_line.strip()
    if yard_line == "50":
        return 50
    parts = yard_line.rsplit(" ", 1)
    if len(parts) != 2:
        return None
    side, num = parts
    try:
        yd = int(num)
    except ValueError:
        return None
    return 100 - yd if side == posteam else yd


def _game_half(quarter: Optional[int]) -> Optional[str]:
    if quarter is None:
        return None
    if quarter in (1, 2):
        return "Half1"
    if quarter in (3, 4):
        return "Half2"
    return "Overtime"


def _seconds_remaining(quarter: Optional[int], qsr: Optional[int]) -> tuple[Optional[int], Optional[int]]:
    """(half_seconds_remaining, game_seconds_remaining) from quarter + quarter-seconds."""
    if quarter is None or qsr is None:
        return None, None
    if quarter in (1, 2):
        half = (2 - quarter) * 900 + qsr
        game = (4 - quarter) * 900 + qsr
    elif quarter in (3, 4):
        half = (4 - quarter) * 900 + qsr
        game = (4 - quarter) * 900 + qsr
    else:  # overtime — regulation exhausted
        half = qsr
        game = 0
    return half, game


def _play_type(row: Dict[str, Any], shield_play_type: Optional[str]) -> Optional[str]:
    """nflverse-style play_type from the summed stat outcomes + the feed's playType.

    qb_kneel / qb_spike are refined later from the description; this assigns the
    base class (pass/run/punt/field_goal/kickoff/extra_point/no_play).
    """
    has_pass = row.get("pass_attempt") == 1
    has_rush = row.get("rush_attempt") == 1
    penalty_only = (
        (shield_play_type == "PENALTY")
        and not has_pass
        and not has_rush
        and row.get("field_goal_attempt") != 1
        and row.get("punt_attempt") != 1
    )
    if penalty_only:
        return "no_play"
    if has_pass:
        return "pass"
    if has_rush:
        return "run"
    if row.get("field_goal_attempt") == 1:
        return "field_goal"
    if row.get("extra_point_attempt") == 1:
        return "extra_point"
    if row.get("punt_attempt") == 1:
        return "punt"
    if row.get("kickoff_attempt") == 1:
        return "kickoff"
    return None


def _drive_ranges(drives: List[Dict[str, Any]]) -> List[tuple[float, float, Optional[str]]]:
    """(startSeq, endSeq, teamId) per drive, for play->possession assignment."""
    out = []
    for d in drives or []:
        s = d.get("startedPlaySequenceNumber")
        e = d.get("endedPlaySequenceNumber")
        if s is None or e is None:
            continue
        out.append((float(s), float(e), d.get("teamId")))
    return out


def _posteam_for(seq: Optional[float], ranges: List[tuple[float, float, Optional[str]]]) -> Optional[str]:
    if seq is None:
        return None
    for start, end, team_id in ranges:
        if start <= seq <= end:
            return team_id
    return None


# A handful of stat columns are integer-ish indicators we want present (as 0) on
# every row so the frame schema is stable for downstream joins.
_BASE_INDICATORS = [
    "pass_attempt", "complete_pass", "incomplete_pass", "interception", "rush_attempt",
    "sack", "touchdown", "pass_touchdown", "rush_touchdown", "return_touchdown",
    "field_goal_attempt", "field_goal_made", "field_goal_missed", "field_goal_blocked",
    "extra_point_attempt", "two_point_attempt", "punt_attempt",
    "kickoff_attempt", "penalty", "fumble", "fumble_lost", "qb_hit", "safety", "timeout",
    "first_down_rush", "first_down_pass", "first_down_penalty",
]
_BASE_NUMERICS = ["yards_gained", "air_yards", "yards_after_catch", "passing_yards",
                  "rushing_yards", "receiving_yards", "penalty_yards", "kick_distance"]
_BASE_PLAYERS = ["passer_player_id", "passer_player_name", "rusher_player_id",
                 "rusher_player_name", "receiver_player_id", "receiver_player_name",
                 "td_player_id", "td_player_name", "td_team", "penalty_team", "timeout_team"]

# Points scored ON a play by its scoringPlayType (attributed to scoringTeamId).
# Drives the per-play running score, which steps correctly at each scoring play
# (TD +6 at the TD, PAT +1 at the PAT) — unlike a bundled TD+PAT summary step.
_SCORING_POINTS = {"TOUCHDOWN": 6, "PAT": 1, "PAT2": 2, "FIELD_GOAL": 3, "SAFETY": 2}


def parse_game(game: Dict[str, Any], game_id: Optional[str] = None) -> pl.DataFrame:
    """Parse one Shield game payload into a base play-level polars frame.

    Args:
        game: A single Shield game object (one ``nfl/raw/{season}/{game_id}.json``).
        game_id: Override the nflverse game_id; computed from the payload when None.

    Returns:
        A polars DataFrame, one row per play (sorted by play sequence), carrying
        identifiers, possession, down/distance/field-position, clock fields,
        play_type, and the summed per-play stat columns. Empty payloads return a
        zero-row frame.
    """
    season = int(game.get("season")) if game.get("season") is not None else None
    week = game.get("week")
    season_type = game.get("seasonType")
    summary = game.get("summary") or {}
    dc = game.get("driveChart") or {}
    plays = dc.get("plays") or []

    home_abbr = _nflverse_abbr(_team_abbr(game["homeTeam"]), season) if game.get("homeTeam") else None
    away_abbr = _nflverse_abbr(_team_abbr(game["awayTeam"]), season) if game.get("awayTeam") else None
    team_by_id: Dict[str, str] = {}
    for side, abbr in (("homeTeam", home_abbr), ("awayTeam", away_abbr)):
        tid = (summary.get(side) or {}).get("teamId")
        if tid is not None and abbr is not None:
            team_by_id[tid] = abbr

    if game_id is None:
        reg_weeks = 17 if (season is not None and season <= 2020) else 18
        game_id = nflverse_game_id(game, reg_weeks=reg_weeks) if game.get("homeTeam") else None

    ranges = _drive_ranges(dc.get("drives") or [])

    rows: List[Dict[str, Any]] = []
    for p in plays:
        if p.get("playDeleted"):
            continue
        seq = p.get("playSequenceNumber")
        pos_team_id = _posteam_for(float(seq) if seq is not None else None, ranges)
        posteam = team_by_id.get(pos_team_id) if pos_team_id else None
        defteam = None
        if posteam is not None:
            defteam = away_abbr if posteam == home_abbr else home_abbr

        stat_row = sum_play_stats(p.get("stats") or [])
        # Resolve teamId-valued stat columns to abbrs.
        for tcol in ("td_team", "penalty_team", "timeout_team", "return_team"):
            if stat_row.get(tcol) in team_by_id:
                stat_row[tcol] = team_by_id[stat_row[tcol]]

        quarter = p.get("quarter")
        qsr = _clock_to_seconds(p.get("clockTime"))
        half_sr, game_sr = _seconds_remaining(quarter, qsr)
        yards_gained = stat_row.get("yards_gained")
        if yards_gained is None:
            yards_gained = p.get("yardsGained")

        row: Dict[str, Any] = {
            "game_id": game_id,
            "season": season,
            "week": week,
            "season_type": season_type,
            "play_id": p.get("playId"),
            "play_seq": float(seq) if seq is not None else None,
            "posteam": posteam,
            "defteam": defteam,
            "home_team": home_abbr,
            "away_team": away_abbr,
            "home": 1 if (posteam is not None and posteam == home_abbr) else 0,
            "qtr": quarter,
            "game_half": _game_half(quarter),
            # Feed uses down=0 for non-scrimmage plays (kickoffs/PATs/timeouts);
            # nflverse leaves down null there.
            "down": (p.get("down") or None),
            "ydstogo": p.get("yardsRemaining"),
            "yardline_100": _yardline_100(p.get("yardLine"), posteam),
            "goal_to_go": 1 if p.get("playIsGoalToGo") else 0,
            "quarter_seconds_remaining": qsr,
            "half_seconds_remaining": half_sr,
            "game_seconds_remaining": game_sr,
            "play_type": _play_type(stat_row, p.get("playType")),
            "yards_gained": yards_gained,
            "desc": p.get("playDescription"),
            "shield_play_type": p.get("playType"),
            "special_teams_play_type": p.get("specialTeamsPlayType"),
            "sp": 1 if p.get("playScored") else 0,  # nflverse scoring-play indicator
        }
        # Merge the requested stable columns (default 0 / None when absent).
        for col in _BASE_INDICATORS:
            row[col] = int(stat_row.get(col) or 0)
        for col in _BASE_NUMERICS:
            row[col] = stat_row.get(col)
        for col in _BASE_PLAYERS:
            row[col] = stat_row.get(col)
        # Per-play points (for the running score), attributed to home/away.
        pts = _SCORING_POINTS.get(p.get("scoringPlayType"), 0) if p.get("playScored") else 0
        score_team = team_by_id.get(p.get("scoringTeamId"))
        row["_points_home"] = pts if score_team == home_abbr else 0
        row["_points_away"] = pts if score_team == away_abbr else 0
        rows.append(row)

    if not rows:
        return pl.DataFrame()

    # infer_schema_length=None scans all rows: sparse player/team columns are null
    # for the first 100+ plays in many games, which would otherwise be inferred as
    # Null dtype and then fail when a later string value appears.
    df = pl.DataFrame(rows, infer_schema_length=None)
    return df.sort("play_seq")
