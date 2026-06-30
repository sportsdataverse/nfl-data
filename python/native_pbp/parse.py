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

from model_training.play_level.fetcher import _nflverse_abbr, _team_abbr, nflverse_game_id
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


# The feed's ``yardLine`` string uses NFL *gamebook* club abbreviations, which
# differ from nflverse's club abbreviation (used for ``posteam``) for four clubs.
# Without this normalization ``side == posteam`` is False for these clubs, the
# own-side flip (``100 - yd``) is skipped, and the club is mis-located to the
# opponent's red zone — corrupting ``yardline_100`` and every model that consumes
# it (ep/epa/wp). Enumerated across the 1999-2025 raw corpus:
#   JAC -> JAX (Jaguars, 1999-2019), LAR -> LA (Rams, 2016+),
#   BLT -> BAL / CLV -> CLE (2006). Each maps to exactly one nflverse abbr in
#   every era it appears, so the rename is season-independent.
_GAMEBOOK_TO_NFLVERSE: Dict[str, str] = {"JAC": "JAX", "LAR": "LA", "BLT": "BAL", "CLV": "CLE"}


def _yardline_100(yard_line: Optional[str], posteam: Optional[str]) -> Optional[int]:
    """Distance (yards) from the possession team to the opponent's goal line.

    ``"50"`` -> 50. ``"BAL 32"`` -> 68 if posteam is BAL (own 32), else 32. The
    parsed side abbreviation is normalized from the feed's gamebook scheme to
    nflverse (e.g. ``"LAR" -> "LA"``) before the own-side comparison, so the flip
    fires for clubs whose gamebook abbr differs from ``posteam``.
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
    side = _GAMEBOOK_TO_NFLVERSE.get(side, side)
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
    "pass_attempt",
    "complete_pass",
    "incomplete_pass",
    "interception",
    "rush_attempt",
    "sack",
    "touchdown",
    "pass_touchdown",
    "rush_touchdown",
    "return_touchdown",
    "field_goal_attempt",
    "field_goal_made",
    "field_goal_missed",
    "field_goal_blocked",
    "extra_point_attempt",
    "two_point_attempt",
    "punt_attempt",
    "kickoff_attempt",
    "penalty",
    "fumble",
    "fumble_lost",
    "qb_hit",
    "safety",
    "timeout",
    "first_down_rush",
    "first_down_pass",
    "first_down_penalty",
    # --- defensive / tackling indicators (team_stats enablement) ---
    "solo_tackle",
    "assist_tackle",
    "tackle_with_assist",
    "tackled_for_loss",
    "fumble_forced",
    "fumble_not_forced",
    "fumble_out_of_bounds",
    # --- special-teams return flags (exact punt_returns / kickoff_returns inputs;
    #     calculate_stats.R assigns statIds 37/38/39 + 49/50 to the receiving team) ---
    "punt_fair_catch",
    "punt_downed",
    "punt_out_of_bounds",
    "kickoff_fair_catch",
    "kickoff_out_of_bounds",
    # --- extra-point sub-results (drive extra_point_result) ---
    "extra_point_good",
    "extra_point_failed",
    "extra_point_blocked",
    "extra_point_safety",
    "extra_point_aborted",
    # --- two-point sub-results (drive two_point_conv_result) ---
    "two_point_rush_good",
    "two_point_rush_failed",
    "two_point_rush_safety",
    "two_point_pass_good",
    "two_point_pass_failed",
    "two_point_pass_safety",
    "two_point_pass_reception_good",
    "two_point_pass_reception_failed",
    "two_point_return",
]
_BASE_NUMERICS = [
    "yards_gained",
    "air_yards",
    "yards_after_catch",
    "passing_yards",
    "rushing_yards",
    "receiving_yards",
    "penalty_yards",
    "kick_distance",
    "return_yards",
    "lateral_rushing_yards",
    "lateral_receiving_yards",
]
# Exact per-play stat-id count / yards-sum accumulators (int, default 0) that close
# the team_stats parity gaps. Each maps 1:1 onto a nflfastR calculate_stats.R term:
#   def_tackles_for_loss        = sum(stat_id == 402)            (count of 402 credits)
#   def_tackles_for_loss_yards  = sum((stat_id == 402) * yards)
#   td_ids_touchdown            = count of td_ids() TD stats -> exact def_tds downstream
#   misc_yards                  = sum((stat_id %in% 63:64) * yards)
#   fumble_recovery_own_lateral_yards = sum((stat_id %in% 57:58) * yards)
#   fumble_recovery_opp_lateral_yards = sum((stat_id %in% 61:62) * yards)
_BASE_COUNTS = [
    "def_tackles_for_loss",
    "def_tackles_for_loss_yards",
    "td_ids_touchdown",
    "misc_yards",
    "fumble_recovery_own_lateral_yards",
    "fumble_recovery_opp_lateral_yards",
]
_BASE_PLAYERS = [
    "passer_player_id",
    "passer_player_name",
    "rusher_player_id",
    "rusher_player_name",
    "receiver_player_id",
    "receiver_player_name",
    "td_player_id",
    "td_player_name",
    "td_team",
    "penalty_team",
    "timeout_team",
    # --- kicking / punting / returns ---
    "kicker_player_id",
    "kicker_player_name",
    "punter_player_id",
    "punter_player_name",
    "punt_returner_player_id",
    "punt_returner_player_name",
    "kickoff_returner_player_id",
    "kickoff_returner_player_name",
    "return_team",
    # --- defensive single-writer slots ---
    "interception_player_id",
    "interception_player_name",
    "sack_player_id",
    "sack_player_name",
    "safety_player_id",
    "safety_player_name",
    "blocked_player_id",
    "blocked_player_name",
    "penalty_player_id",
    "penalty_player_name",
    # --- defensive FILL-group slots (de-duped multi-participant) ---
    "solo_tackle_1_player_id",
    "solo_tackle_1_player_name",
    "solo_tackle_1_team",
    "solo_tackle_2_player_id",
    "solo_tackle_2_player_name",
    "solo_tackle_2_team",
    "assist_tackle_1_player_id",
    "assist_tackle_1_player_name",
    "assist_tackle_1_team",
    "assist_tackle_2_player_id",
    "assist_tackle_2_player_name",
    "assist_tackle_2_team",
    "assist_tackle_3_player_id",
    "assist_tackle_3_player_name",
    "assist_tackle_3_team",
    "assist_tackle_4_player_id",
    "assist_tackle_4_player_name",
    "assist_tackle_4_team",
    "tackle_with_assist_1_player_id",
    "tackle_with_assist_1_player_name",
    "tackle_with_assist_1_team",
    "tackle_with_assist_2_player_id",
    "tackle_with_assist_2_player_name",
    "tackle_with_assist_2_team",
    "tackle_for_loss_1_player_id",
    "tackle_for_loss_1_player_name",
    "tackle_for_loss_2_player_id",
    "tackle_for_loss_2_player_name",
    "half_sack_1_player_id",
    "half_sack_1_player_name",
    "half_sack_2_player_id",
    "half_sack_2_player_name",
    "qb_hit_1_player_id",
    "qb_hit_1_player_name",
    "qb_hit_2_player_id",
    "qb_hit_2_player_name",
    "pass_defense_1_player_id",
    "pass_defense_1_player_name",
    "pass_defense_2_player_id",
    "pass_defense_2_player_name",
    "forced_fumble_player_1_player_id",
    "forced_fumble_player_1_player_name",
    "forced_fumble_player_1_team",
    "forced_fumble_player_2_player_id",
    "forced_fumble_player_2_player_name",
    "forced_fumble_player_2_team",
    "fumbled_1_player_id",
    "fumbled_1_player_name",
    "fumbled_1_team",
    "fumbled_2_player_id",
    "fumbled_2_player_name",
    "fumbled_2_team",
    "fumble_recovery_1_player_id",
    "fumble_recovery_1_player_name",
    "fumble_recovery_1_team",
    "fumble_recovery_1_yards",
    "fumble_recovery_2_player_id",
    "fumble_recovery_2_player_name",
    "fumble_recovery_2_team",
    "fumble_recovery_2_yards",
]

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
        # Resolve every teamId-valued stat column to an nflverse abbr. Covers the
        # scalar team cols (td/penalty/timeout/return) plus the FILL-group ``*_team``
        # slots (tackles, fumbles, forced fumbles, recoveries) used by team_stats.
        for tcol in stat_row:
            if tcol.endswith("_team") and stat_row.get(tcol) in team_by_id:
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
        for col in _BASE_COUNTS:
            # nflfastR sums these; the per-play value when no stat fires is 0 (not null).
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
    df = df.sort("play_seq")
    df = _add_special_teams_derivations(df)
    df = _add_fixed_drive(df)
    return df


# nflverse play_types that count as special teams (helper_additional_functions.R).
_SPECIAL_PLAY_TYPES = ("extra_point", "field_goal", "kickoff", "punt")


def _add_special_teams_derivations(df: pl.DataFrame) -> pl.DataFrame:
    """Derive ``two_point_conv_result``, ``extra_point_result`` and ``special``.

    Faithful port of nflfastR's mutations:

    * ``two_point_conv_result`` — from the two_point_*_good / _failed / _safety /
      _return sub-indicators when ``two_point_attempt == 1``
      (``helper_add_nflscrapr_mutations.R``).
    * ``extra_point_result`` — from the extra_point_good / _failed / _blocked /
      _safety / _aborted sub-indicators (``aggregate_game_stats_kicking.R``).
    * ``special`` — 1 when ``play_type`` is a special-teams type
      (``helper_additional_functions.R``).

    Args:
        df: The base play frame (post per-row stat merge), carrying the
            two_point_* / extra_point_* sub-indicator columns.

    Returns:
        The frame with ``two_point_conv_result`` (success/failure/safety/return/
        None), ``extra_point_result`` (good/failed/blocked/safety/aborted/None),
        and ``special`` (Int64 0/1) added.
    """
    two_pt = pl.col("two_point_attempt") == 1
    df = df.with_columns(
        two_point_conv_result=pl.when(
            two_pt
            & (
                (pl.col("two_point_rush_good") == 1)
                | (pl.col("two_point_pass_good") == 1)
                | (pl.col("two_point_pass_reception_good") == 1)
            )
        )
        .then(pl.lit("success"))
        .when(
            two_pt
            & (
                (pl.col("two_point_rush_failed") == 1)
                | (pl.col("two_point_pass_failed") == 1)
                | (pl.col("two_point_pass_reception_failed") == 1)
            )
        )
        .then(pl.lit("failure"))
        .when(two_pt & ((pl.col("two_point_rush_safety") == 1) | (pl.col("two_point_pass_safety") == 1)))
        .then(pl.lit("safety"))
        .when(two_pt & (pl.col("two_point_return") == 1))
        .then(pl.lit("return"))
        .otherwise(None),
        extra_point_result=pl.when(pl.col("extra_point_good") == 1)
        .then(pl.lit("good"))
        .when(pl.col("extra_point_failed") == 1)
        .then(pl.lit("failed"))
        .when(pl.col("extra_point_blocked") == 1)
        .then(pl.lit("blocked"))
        .when(pl.col("extra_point_safety") == 1)
        .then(pl.lit("safety"))
        .when(pl.col("extra_point_aborted") == 1)
        .then(pl.lit("aborted"))
        .otherwise(None),
        special=pl.col("play_type").is_in(_SPECIAL_PLAY_TYPES).fill_null(False).cast(pl.Int64),
    )
    return df


def _add_fixed_drive(df: pl.DataFrame) -> pl.DataFrame:
    """Add nflfastR's ``fixed_drive`` — a per-game ascending drive counter.

    Faithful polars port of the new_drive -> ``fixed_drive = cumsum(new_drive)``
    logic in ``helper_add_fixed_drives.R`` (Carl/Baldwin). ``fixed_drive`` starts
    at 1 and increments at each new possession; the number is shared across both
    teams (interleaved). A play inherits the same number through interstitial
    null-posteam plays (kickoffs / PATs / timeouts) via the look-back rules.

    ``new_drive`` is 1 when:

    * the possession team changes from the prior play (or from the play 2/3 back
      when the intervening play(s) have a null posteam — the kickoff/PAT gap), or
    * it is the first play of a half, or
    * the offense kept the ball after its own lost fumble on a punt/pass/run/FG
      (a new series), or it recovered an onside kick / muffed return, or
    * it is a kickoff immediately after a safety.

    It is forced back to 0 for a PAT/2pt that follows a *defensive* touchdown
    (the try is part of the scoring drive, not a new one).

    Args:
        df: The sorted (by ``play_seq``) base play frame, carrying ``game_id``,
            ``game_half``, ``posteam``, ``td_team``, ``touchdown``, ``fumble_lost``,
            ``safety``, ``kickoff_attempt``, ``own_kickoff_recovery``, ``play_type``.

    Returns:
        The frame with an Int64 ``fixed_drive`` column added.
    """
    if df.height == 0:
        return df.with_columns(fixed_drive=pl.lit(None, dtype=pl.Int64))

    own_ko = pl.col("own_kickoff_recovery") if "own_kickoff_recovery" in df.columns else pl.lit(0)
    g = ["game_id", "game_half"]
    pos = pl.col("posteam")

    # Base: possession change, with up to-3-play look-back across null posteams.
    change = (
        (pos != pos.shift(1).over(g))
        | ((pos != pos.shift(2).over(g)) & pos.shift(1).over(g).is_null())
        | ((pos != pos.shift(3).over(g)) & pos.shift(1).over(g).is_null() & pos.shift(2).over(g).is_null())
    )
    df = df.with_columns(_new_drive=change.cast(pl.Int64))

    # PAT/2pt after a defensive TD is NOT a new drive (the try belongs to the
    # scoring drive). Look back through up to two intervening timeout/TMW plays.
    prev_def_td = (
        (pl.col("touchdown").shift(1).over(g) == 1)
        & (pl.col("posteam").shift(1).over(g) != pl.col("td_team").shift(1).over(g))
        & pl.col("posteam").shift(1).over(g).is_not_null()
    )
    df = df.with_columns(_new_drive=pl.when(prev_def_td).then(pl.lit(0)).otherwise(pl.col("_new_drive")))

    # Same team retained the ball after its own lost fumble on a scrimmage/punt play
    # (and the play was not a TD) -> a new series/drive.
    retained_after_fumble = (
        (pos == pos.shift(1).over(g))
        & (pl.col("fumble_lost").shift(1).over(g) == 1)
        & pl.col("play_type").shift(1).over(g).is_in(["punt", "pass", "run", "field_goal"])
        & (pl.col("touchdown").shift(1).over(g) == 0)
    )
    df = df.with_columns(_new_drive=pl.when(retained_after_fumble).then(pl.lit(1)).otherwise(pl.col("_new_drive")))

    # Recovered onside kick / muffed return -> new drive.
    ko_recovery = (pl.col("play_type") == "kickoff") & ((own_ko == 1) | (pl.col("fumble_lost") == 1))
    # Kickoff right after a safety -> new drive.
    ko_after_safety = (pl.col("kickoff_attempt") == 1) & (pl.col("safety").shift(1).over(g) == 1)
    df = df.with_columns(
        _new_drive=pl.when(ko_recovery | ko_after_safety).then(pl.lit(1)).otherwise(pl.col("_new_drive"))
    )

    # First play of each half is always a new drive.
    df = df.with_columns(
        _row=pl.int_range(0, pl.len()).over(g),
    ).with_columns(_new_drive=pl.when(pl.col("_row") == 0).then(pl.lit(1)).otherwise(pl.col("_new_drive")))

    # Nulls (from shifts at boundaries) are not new drives.
    df = df.with_columns(_new_drive=pl.col("_new_drive").fill_null(0))
    # fixed_drive = cumulative count of new drives within the game.
    df = df.with_columns(fixed_drive=pl.col("_new_drive").cum_sum().over("game_id").cast(pl.Int64)).drop(
        "_new_drive", "_row"
    )
    return df
