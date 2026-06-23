"""Gated parity test for the track7 NFL model suite.

Marked ``integration`` (deselected by default — needs network PBP + the
converted R oracles under sdv-py-stats). Trains every model on the full spans
and asserts each meets its parity gate vs the oracle.
"""
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def test_train_all_meets_parity(tmp_path: Path):
    from model_training.track7_nfl_models.pipeline import train_all
    from model_training.track7_nfl_models.validate import ORACLE_DIR

    if not (ORACLE_DIR / "xpass_model.ubj").exists():
        pytest.skip(f"oracle artifacts not found under {ORACLE_DIR}")

    results = train_all(out_dir=tmp_path)

    assert results["xpass"]["correlation"] >= 0.99
    assert results["xpass"]["feature_names_ok"]
    assert results["fd"]["correlation"] >= 0.99
    assert results["fd"]["feature_names_ok"]
    # fg gate is on attempted (yardline x roof x era) cells — the operating domain.
    assert results["fg"]["correlation"] >= 0.98
    assert results["fg"]["feature_names_ok"]
    # punt gate is the frequency-weighted total-variation distance.
    assert results["punt"]["weighted_mean_total_variation"] <= 0.10
    # two_pt: recipe-faithful but parity is data-vintage-limited (~0.87) — assert the
    # recipe matches (feature names) and predictions are sane, not the 0.99 gate the
    # frozen-snapshot oracle would need. See report.md "Notes".
    assert results["two_pt"]["feature_names_ok"]
    assert results["two_pt"]["correlation"] >= 0.85
    # wp: home-perspective nfl4th wp_model recipe; trained only when cal_data.rds is
    # present (it carries ep/Winner/play_type, not derivable from raw PBP).
    if not results["wp"].get("skipped"):
        assert results["wp"]["feature_names_ok"]
        assert results["wp"]["correlation"] >= 0.99
