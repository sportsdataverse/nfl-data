"""nfl_data_ingest — fetch nfl-raw committed JSON into a local cache.

Usage:
    from nfl_data_ingest.fetch import fetch_game, ingest_season, enumerate_game_ids
"""
from nfl_data_ingest.fetch import (
    RAW_BASE,
    enumerate_game_ids,
    fetch_game,
    ingest_season,
    raw_url,
)

__all__ = [
    "RAW_BASE",
    "enumerate_game_ids",
    "fetch_game",
    "ingest_season",
    "raw_url",
]
