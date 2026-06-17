"""Tests for the GSIS statType decode + sum_play_stats port."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from native_pbp.stat_ids import (
    FILL_GROUPS,
    STAT_ID_EFFECTS,
    _FILL_ID_SLOTS,
    sum_play_stats,
)

GAME = Path(__file__).resolve().parents[2] / "nfl" / "raw" / "2024" / "2024_01_BAL_KC.json"


# ---------------------------------------------------------------------------
# Unit semantics
# ---------------------------------------------------------------------------

def test_completion_sets_passer_yards():
    row = sum_play_stats([
        {"statType": 15, "yards": 12, "gsisPlayerId": "00-0034796", "gsisPlayerName": "L.Jackson", "teamId": "BAL"},
    ])
    assert row["pass_attempt"] == 1
    assert row["complete_pass"] == 1
    assert row["passer_player_id"] == "00-0034796"
    assert row["yards_gained"] == 12
    assert row["passing_yards"] == 12


def test_air_yards_complete_vs_incomplete():
    comp = sum_play_stats([{"statType": 111, "yards": 18, "gsisPlayerId": "p", "gsisPlayerName": "n", "teamId": "T"}])
    assert comp["air_yards"] == 18 and comp["complete_pass"] == 1
    incomp = sum_play_stats([{"statType": 112, "yards": 25, "gsisPlayerId": "p", "gsisPlayerName": "n", "teamId": "T"}])
    assert incomp["air_yards"] == 25 and "complete_pass" not in incomp  # 112 must NOT set complete_pass


def test_yac_ifna_receiver_does_not_overwrite():
    # stat 21 sets the receiver; a later stat 113 (YAC) must NOT overwrite it, but DOES set yac.
    row = sum_play_stats([
        {"statType": 21, "yards": 9, "gsisPlayerId": "REC1", "gsisPlayerName": "First", "teamId": "T"},
        {"statType": 113, "yards": 4, "gsisPlayerId": "REC2", "gsisPlayerName": "Second", "teamId": "T"},
    ])
    assert row["receiver_player_id"] == "REC1"          # IFNA guard preserved the first receiver
    assert row["yards_after_catch"] == 4


def test_penalty_fields():
    row = sum_play_stats([
        {"statType": 93, "yards": 5, "gsisPlayerId": "00-0032965", "gsisPlayerName": "R.Stanley", "teamId": "BAL"},
    ])
    assert row["penalty"] == 1
    assert row["penalty_yards"] == 5
    assert row["penalty_team"] == "BAL"


def test_qb_hit_fill_two_slots_with_dedup():
    row = sum_play_stats([
        {"statType": 110, "yards": 0, "gsisPlayerId": "A", "gsisPlayerName": "Aaa", "teamId": "T"},
        {"statType": 110, "yards": 0, "gsisPlayerId": "A", "gsisPlayerName": "Aaa", "teamId": "T"},  # dup -> skipped
        {"statType": 110, "yards": 0, "gsisPlayerId": "B", "gsisPlayerName": "Bbb", "teamId": "T"},
    ])
    assert row["qb_hit"] == 1
    assert row["qb_hit_1_player_id"] == "A"
    assert row["qb_hit_2_player_id"] == "B"  # second distinct player took slot 2; dup A did not


def test_rush_touchdown_sets_td_fields():
    row = sum_play_stats([
        {"statType": 11, "yards": 3, "gsisPlayerId": "RB", "gsisPlayerName": "R.Back", "teamId": "KC"},
    ])
    assert row["rush_touchdown"] == 1 and row["touchdown"] == 1
    assert row["td_team"] == "KC" and row["td_player_id"] == "RB"
    assert row["yards_gained"] == 3


def test_empty_and_unknown_statids_are_noops():
    assert sum_play_stats([]) == {}
    assert sum_play_stats([{"statType": 999, "yards": 1, "gsisPlayerId": "x", "gsisPlayerName": "y", "teamId": "z"}]) == {}
    assert sum_play_stats([{"statType": 63, "yards": 0, "gsisPlayerId": "x", "gsisPlayerName": "y", "teamId": "z"}]) == {}


# ---------------------------------------------------------------------------
# Mapping integrity
# ---------------------------------------------------------------------------

def test_fill_group_references_resolve():
    # Every *_FILL_* column used in STAT_ID_EFFECTS has a FILL_GROUPS entry...
    used = {col for effects in STAT_ID_EFFECTS.values() for col, _ in effects if "_FILL_" in col}
    assert used <= set(FILL_GROUPS), f"missing FILL_GROUPS for: {used - set(FILL_GROUPS)}"
    # ...and every FILL group prefix has a de-dup id-slot mapping.
    prefixes = {c.split("_FILL_", 1)[0] for c in FILL_GROUPS}
    assert prefixes <= set(_FILL_ID_SLOTS), f"missing _FILL_ID_SLOTS for: {prefixes - set(_FILL_ID_SLOTS)}"


def test_model_critical_codes_present():
    # Lower bound + the codes the EP/WP/CP models depend on must all be mapped.
    assert len(STAT_ID_EFFECTS) >= 100
    critical = {10, 11, 14, 15, 16, 19, 20, 21, 22, 68, 70, 89, 93, 110, 111, 112, 113}
    assert critical <= set(STAT_ID_EFFECTS), f"missing critical codes: {critical - set(STAT_ID_EFFECTS)}"


# ---------------------------------------------------------------------------
# Real-game smoke test (the parity anchor)
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.skipif(not GAME.exists(), reason="2024_01_BAL_KC raw game not present")
def test_real_game_runs_clean_and_has_signal():
    game = json.loads(GAME.read_text(encoding="utf-8"))
    plays = game["driveChart"]["plays"]
    rows = [sum_play_stats(p.get("stats") or []) for p in plays]

    # No exceptions, and the game produces meaningful aggregate signal.
    completions = sum(r.get("complete_pass", 0) for r in rows)
    rush_atts = sum(r.get("rush_attempt", 0) for r in rows)
    pass_atts = sum(r.get("pass_attempt", 0) for r in rows)
    air_yards_plays = sum(1 for r in rows if r.get("air_yards") is not None)
    touchdowns = sum(r.get("touchdown", 0) for r in rows)

    assert completions > 20, f"too few completions: {completions}"
    assert rush_atts > 20, f"too few rush attempts: {rush_atts}"
    assert pass_atts > completions, "pass attempts should exceed completions"
    assert air_yards_plays > 20, f"air_yards should populate on most pass plays: {air_yards_plays}"
    assert touchdowns >= 4, f"BAL@KC 2024 opener had multiple TDs: {touchdowns}"
