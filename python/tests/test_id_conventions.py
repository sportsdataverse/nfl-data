"""Regression tests for the ID-column-type + name-matching conventions.

Join keys (game_id / player_id / gsis_id / team) are only as correct as the dtype
agreement on both sides. These pin the bug classes that historically surfaced only
downstream (after a model rebuild or a join produced wrong/empty matches): the
``id -> Utf8`` "paper-over" cast on a float-origin id, join-key dtype disagreement,
and case-sensitive player-name matching.

Mirrors the sdv-py ``tests/test_id_conventions.py`` contract for the nfl-data model
pipeline (the EP/WP/CP port is polars-based). All offline; polars-gated so it skips
cleanly if polars isn't installed in this environment rather than erroring.
"""

from __future__ import annotations

import pytest

pl = pytest.importorskip("polars")


def test_float_origin_id_naive_utf8_is_the_trap() -> None:
    """A float-origin id stringifies as ``"123.0"`` — the documented foot-gun.

    JSON/parquet with nulls in an id column yields Float64; a naive ``cast(Utf8)``
    then produces ``"123.0"``, silently breaking a join against ``"123"``. The
    convention is to cast the *raw integer* first.
    """
    df = pl.DataFrame({"id": [123.0]})  # Float64 (e.g. a nullable id from JSON)
    naive = df.select(pl.col("id").cast(pl.Utf8)).to_series()[0]
    assert naive == "123.0"  # the trap

    safe = df.select(pl.col("id").cast(pl.Int64).cast(pl.Utf8)).to_series()[0]
    assert safe == "123"  # cast the raw integer, never the float


def test_join_key_dtype_must_agree() -> None:
    """An Int64-vs-Utf8 mismatch on the join key yields wrong/empty matches.

    Assert dtype agreement before joining; the convention is to pin one canonical
    dtype per id at the boundary and keep it consistent across the pipeline.
    """
    left = pl.DataFrame({"gsis_id": [1, 2, 3], "x": [10, 20, 30]})
    right_bad = pl.DataFrame({"gsis_id": ["1", "2", "3"], "y": [1.0, 2.0, 3.0]})
    assert left.schema["gsis_id"] != right_bad.schema["gsis_id"]

    right_ok = right_bad.with_columns(pl.col("gsis_id").cast(pl.Int64))
    assert left.schema["gsis_id"] == right_ok.schema["gsis_id"]
    joined = left.join(right_ok, on="gsis_id", how="inner")
    assert joined.height == 3  # all rows match once dtypes agree


def test_player_name_match_is_case_insensitive() -> None:
    """Name reconciliation folds case (polars/Rust regex inline ``(?i)`` toggle)."""
    df = pl.DataFrame({"name": ["Patrick Mahomes", "patrick mahomes", "P. MAHOMES"]})
    hits = df.filter(pl.col("name").str.contains(r"(?i)mahomes")).height
    assert hits == 3
