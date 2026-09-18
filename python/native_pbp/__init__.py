"""Native NFL play-by-play reconstruction from the api.nfl.com Shield driveChart feed.

**The parser moved to** :mod:`sportsdataverse.nfl.shield_pbp` (sportsdataverse-py
#528). Every module listed below is now a re-export shim over its graduated twin;
nfl-data keeps the pipeline around it -- ``cli`` (the ``--enrich`` + parquet-writing
build) and ``parity`` (the nflverse diff). Fix a parser bug in sdv-py, not here.

Modules (build order, each a shim except ``cli`` / ``parity``):
    stat_ids    -- GSIS statType decode + per-play stats summation (sum_play_stats)
    parse       -- driveChart -> base play frame (down/dist/yardline/clock/posteam/...)
    players     -- passer/rusher/receiver resolution
    description -- play-text regex layer (pass_location, run_location, penalties)
    features    -- timeouts, score_differential, game_half, seconds, roof, era, spread join
    labels      -- EP/WP/CP label sources (sp/touchdown/td_team/field_goal_result/safety/result)
    drives      -- fixed_drive / fixed_drive_result + drive_* detail columns
    series      -- series / series_result / series_success
    parity      -- diff vs sportsdataverse.load_nfl_pbp for sample games
"""

from __future__ import annotations

__version__ = "0.1.0"
