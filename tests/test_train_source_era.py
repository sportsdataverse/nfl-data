"""Track C plumbing: the ``source="sdv"`` training loader and the era-variant parameter.

The default (``era="nflfastr5"``, ``source="nflverse"``) must stay byte-for-byte what the
published models were trained on; the variants only add an ``era5`` break for comparison.
"""

from __future__ import annotations

import polars as pl
import pytest
from model_training.play_level import ingest
from model_training.play_level.constants import CP_FEATURES, EP_FEATURES, XYAC_FEATURES
from model_training.play_level.features import ERA_VARIANTS, era_features, make_model_mutations


def _frame(seasons):
    n = len(seasons)
    return pl.DataFrame(
        {
            "season": seasons,
            "posteam": ["A"] * n,
            "home_team": ["A"] * n,
            "roof": ["outdoors"] * n,
            "down": [1] * n,
        }
    )


def test_default_era_is_nflfastr5_and_has_no_era5():
    out = make_model_mutations(_frame([2001, 2002, 2006, 2014, 2018, 2025]))
    assert "era5" not in out.columns
    assert out["era4"].to_list() == [0, 0, 0, 0, 1, 1]
    assert out["era0"].to_list() == [1, 0, 0, 0, 0, 0]


@pytest.mark.parametrize("variant,first", [("era5_2023", 2023), ("era5_2024", 2024)])
def test_era5_variant_splits_era4_at_its_break(variant, first):
    out = make_model_mutations(_frame([2018, first - 1, first, 2025]), era=variant)
    assert out["era4"].to_list() == [1, 1, 0, 0]
    assert out["era5"].to_list() == [0, 0, 1, 1]
    # every row is in exactly one era
    eras = [c for c in out.columns if c.startswith("era")]
    assert out.select(pl.sum_horizontal(eras)).to_series().to_list() == [1, 1, 1, 1]


def test_unknown_era_variant_raises():
    with pytest.raises(ValueError, match="era"):
        make_model_mutations(_frame([2020]), era="era6")


def test_era_features_default_is_unchanged_and_variant_adds_era5_after_era4():
    assert era_features(EP_FEATURES) == EP_FEATURES
    for feats in (EP_FEATURES, CP_FEATURES, XYAC_FEATURES):
        v = era_features(feats, "era5_2024")
        assert v[v.index("era4") + 1] == "era5" and len(v) == len(feats) + 1
    assert set(ERA_VARIANTS) == {"nflfastr5", "era5_2023", "era5_2024"}


def test_load_sdv_pbp_reads_source_sdv_and_casts_to_nflverse_dtypes(monkeypatch):
    calls = []

    def fake(seasons, source="nflverse"):
        calls.append((tuple(seasons), source))
        return pl.DataFrame(
            {
                "game_id": ["g"],
                "play_id": pl.Series([40], dtype=pl.Int64),
                "down": pl.Series([1], dtype=pl.Int64),
                "season": pl.Series([seasons[0]], dtype=pl.Int64),
                "week": pl.Series([1], dtype=pl.Int64),
                "pass": pl.Series([True]),
                "yardline_100": [75.0],
            }
        )

    import sportsdataverse.nfl as sdv_nfl

    monkeypatch.setattr(sdv_nfl, "load_nfl_pbp", fake)
    out = ingest.load_sdv_pbp([2023, 2024], validate=False)
    assert calls == [((2023,), "sdv"), ((2024,), "sdv")]
    assert out.schema["play_id"] == pl.Float64 and out.schema["down"] == pl.Float64
    assert out.schema["pass"] == pl.Float64
    assert out.schema["season"] == pl.Int32 and out.schema["week"] == pl.Int32
    assert out["season"].to_list() == [2023, 2024]


def test_resolve_pbp_routes_sdv(monkeypatch, tmp_path):
    from model_training.play_level import pipeline

    monkeypatch.setattr(ingest, "load_sdv_pbp", lambda seasons: pl.DataFrame({"season": seasons}))
    assert pipeline._resolve_pbp([2024], tmp_path, False, "sdv")["season"].to_list() == [2024]
    with pytest.raises(ValueError, match="sdv"):
        pipeline._resolve_pbp([2024], tmp_path, False, "bogus")


def _cp_rows(seasons):
    n = len(seasons)
    return pl.DataFrame({
        "air_yards": [8.0] * n, "yardline_100": [60.0] * n, "ydstogo": [10.0] * n, "down": [1.0] * n,
        "pass_location": ["left"] * n, "qb_hit": [0.0] * n, "posteam": ["NE"] * n,
        "home_team": ["NE"] * n, "roof": ["outdoors"] * n,
        "complete_pass": [1.0, 0.0] * (n // 2) + [1.0] * (n % 2),
        "incomplete_pass": [0.0, 1.0] * (n // 2) + [0.0] * (n % 2), "interception": [0.0] * n,
        "receiver_player_id": ["00-1"] * n, "receiver_player_name": ["A.B"] * n, "season": seasons,
    })


def test_cp_training_set_carries_era5_only_for_a_variant():
    from model_training.play_level.label import build_cp_training_set

    df = _cp_rows([2023, 2024])
    assert build_cp_training_set(df).columns[: len(CP_FEATURES)] == CP_FEATURES
    v = build_cp_training_set(df, era="era5_2024")
    assert "era5" in v.columns and v["era5"].to_list() == [0.0, 1.0]


def test_loso_cp_fits_the_variant_features(monkeypatch):
    """A real (2-round) fit: the variant must reach the booster, not just the frame."""
    from model_training.play_level import loso, trainer

    seen = []
    real = trainer.train_cp

    def spy(df, **kw):
        model = real(df, **kw)
        seen.append(model.feature_names)
        return model

    monkeypatch.setattr(trainer, "train_cp", spy)
    df = _cp_rows([2023, 2023, 2024, 2024, 2025, 2025])
    out = loso.loso_cp(df, seasons=[2024], nrounds=2, era="era5_2024")
    assert out.height == 2 and seen and "era5" in seen[0]
    base = loso.loso_cp(df, seasons=[2024], nrounds=2)
    assert "era5" not in seen[-1] and base.height == 2
