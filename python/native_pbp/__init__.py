"""Native NFL play-by-play reconstruction from the api.nfl.com Shield driveChart feed.

Ports nflfastR's play parser (R -> Python/polars) so Track 6 EP/WP/CP model training
can run off the committed ``nfl/raw/{season}/{game_id}.json`` library instead of
depending on nflverse pre-computed PBP.

Modules (build order):
    stat_ids    -- GSIS statType decode + per-play stats summation (sum_play_stats)
    parse       -- driveChart -> base play frame (down/dist/yardline/clock/posteam/...)
    players     -- passer/rusher/receiver resolution
    description -- play-text regex layer (pass_location, run_location, penalties)
    features    -- timeouts, score_differential, game_half, seconds, roof, era, spread join
    labels      -- EP/WP/CP label sources (sp/touchdown/td_team/field_goal_result/safety/result)
    parity      -- diff vs sportsdataverse.load_nfl_pbp for sample games
"""
from __future__ import annotations

__version__ = "0.1.0"
