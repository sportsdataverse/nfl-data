"""CP trains from 2009: nflverse's pbp names no receiver on 2006-08 incompletions, so the valid-pass
filter kept only their completions and biased cp +0.085 on every 2006-13 pass."""
from __future__ import annotations

import polars as pl
from model_training.play_level.label import CP_FIRST_SEASON, build_cp_training_set


def test_cp_training_starts_at_2009():
    rows = {
        "air_yards": [8.0, 8.0], "yardline_100": [60.0, 60.0], "ydstogo": [10.0, 10.0], "down": [1.0, 1.0],
        "pass_location": ["left", "left"], "qb_hit": [0.0, 0.0], "posteam": ["NE", "NE"],
        "home_team": ["NE", "NE"], "roof": ["outdoors", "outdoors"], "complete_pass": [1.0, 0.0],
        "incomplete_pass": [0.0, 1.0], "interception": [0.0, 0.0],
        "receiver_player_id": ["00-1", "00-1"], "receiver_player_name": ["A.B", "A.B"],
        "season": [2008, 2009],
    }
    out = build_cp_training_set(pl.DataFrame(rows))
    assert CP_FIRST_SEASON == 2009
    assert out.height == 1 and out["complete_pass"].to_list() == [0.0]
