"""An all-null column is published with its real dtype, never polars' Null (``_type_null_columns``)."""

from __future__ import annotations

import polars as pl
from native_pbp.cli import _type_null_columns


def test_all_null_columns_take_their_published_dtype():
    # the 2003 shapes: no play fills these, so the build types them Null
    df = pl.DataFrame(
        {
            "play_id": [1, 2],
            "tackle_with_assist_2_player_id": [None, None],
            "tackle_with_assist_2_player_name": [None, None],
            "tackle_with_assist_2_team": [None, None],
            "air_yards": [None, None],
            "yards_after_catch": [None, None],
        }
    )
    assert df.schema["air_yards"] == pl.Null
    out = _type_null_columns(df)
    assert out.schema == pl.Schema(
        {
            "play_id": pl.Int64,
            "tackle_with_assist_2_player_id": pl.String,
            "tackle_with_assist_2_player_name": pl.String,
            "tackle_with_assist_2_team": pl.String,
            "air_yards": pl.Int64,
            "yards_after_catch": pl.Int64,
        }
    )
    assert out.height == 2 and out["air_yards"].null_count() == 2


def test_other_all_null_columns_are_left_alone():
    df = pl.DataFrame({"play_id": [1], "roof": [None]})
    assert _type_null_columns(df).schema["roof"] == pl.Null
