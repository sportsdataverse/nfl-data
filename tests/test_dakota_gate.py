"""Tests for the dakota gate.

dakota has no artifact, so the gate checks the blend's PREMISE (CPOE is the
stabler input), its PAYOFF (dakota inherits that stability) and its FIDELITY to
the published nflfastR GAM it approximates.

The floors come from real measurements on model_pbp 2006-2025 (recorded in the
constants' docstrings and in docs/models/dakota.md). These tests pin the
arithmetic on deterministic frames plus the one thing that must be exact: that
interpolating the committed GAM term curves reproduces ``mgcv::predict.gam``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
from model_training.play_level.validate import (
    DAKOTA_LINEAR_COEFFICIENTS,
    dakota_gam_predict,
    dakota_passer_seasons,
    validate_dakota,
)

# Resolved from THIS file, not the CWD: pytest may be invoked from python/.
ORACLE = Path(__file__).resolve().parents[1] / "models" / "oracles"


def test_gam_interpolation_reproduces_mgcv():
    """The committed curves must reproduce predict.gam, or every dakota number is wrong.

    If this fails the interpolation is broken, not the fixture -- the fixture is
    literally predict.gam's own output. Measured max error 8.0e-06.
    """
    chk = pl.read_csv(ORACLE / "dakota_gam_check.csv")
    got = dakota_gam_predict(chk["cpoe"].to_numpy(), chk["epa_per_play"].to_numpy())
    assert np.max(np.abs(got - chk["dakota"].to_numpy())) < 1e-4


def test_gam_is_additive_and_monotone_in_each_input():
    """Sanity on the reconstructed surface: more CPOE and more EPA are both better."""
    lo = dakota_gam_predict(np.array([-8.0]), np.array([-0.1]))[0]
    mid = dakota_gam_predict(np.array([0.0]), np.array([-0.1]))[0]
    hi = dakota_gam_predict(np.array([6.0]), np.array([-0.1]))[0]
    assert lo < mid < hi
    assert (
        dakota_gam_predict(np.array([0.0]), np.array([-0.2]))[0]
        < dakota_gam_predict(np.array([0.0]), np.array([0.2]))[0]
    )


def _pbp(
    n_passers: int,
    seasons: tuple[int, int],
    *,
    cpoe_stability: float,
    seed: int,
    correlated_inputs: bool = True,
) -> pl.DataFrame:
    """Synthetic two-season PBP with a tunable CPOE year-over-year signal.

    ``correlated_inputs`` mirrors reality: EPA/play and CPOE correlate at r ~ 0.55
    on model_pbp (accurate passers are efficient passers). Setting it False
    produces a joint distribution that does not occur in football and is used
    only by the fidelity test below.
    """
    rng = np.random.default_rng(seed)
    s0, s1 = seasons
    rows = {
        "season": [],
        "passer_player_id": [],
        "passer_player_name": [],
        "qb_epa": [],
        "cpoe": [],
    }
    for p in range(n_passers):
        true_cpoe = rng.normal(0.0, 4.0)
        slope = 0.015 if correlated_inputs else 0.0
        true_epa = 0.10 + slope * true_cpoe + rng.normal(0.0, 0.09)
        for season in (s0, s1):
            # cpoe_stability=1 -> the passer repeats his true CPOE exactly;
            # 0 -> this season's CPOE is unrelated to his own.
            cpoe = cpoe_stability * true_cpoe + (1 - cpoe_stability) * rng.normal(0.0, 4.0)
            epa = 0.6 * true_epa + 0.4 * rng.normal(0.10, 0.12)
            # 200 dropbacks whose MEANS are the season values above.
            rows["season"] += [season] * 200
            rows["passer_player_id"] += [f"00-{p:07d}"] * 200
            rows["passer_player_name"] += [f"Passer {p}"] * 200
            rows["qb_epa"] += (epa + rng.normal(0, 1e-9, 200)).tolist()
            rows["cpoe"] += (cpoe + rng.normal(0, 1e-9, 200)).tolist()
    return pl.DataFrame(rows)


def test_stable_cpoe_passes_the_gate():
    """The stability criteria are what synthetic data can legitimately settle.

    ``gam_fidelity`` is deliberately NOT floored here. It is a property of the
    real joint distribution of (EPA, CPOE) across passer-seasons, not of the
    coefficients alone, so no synthetic draw reproduces its real value; the real
    measurement is 0.8542 on model_pbp 2006-2025 and lives in the constants'
    docstrings, docs/models/dakota.md and the registry. Its floor is exercised by
    test_gam_fidelity_floor_bites below, which drives it low on purpose.
    """
    res = validate_dakota(
        _pbp(150, (2023, 2024), cpoe_stability=0.95, seed=7), gam_fidelity_floor=0.0
    )
    assert res["n_pairs"] == 150
    assert res["cpoe_yoy"] > res["epa_yoy"], "premise: CPOE is the stabler input"
    assert res["dakota_yoy"] > res["epa_yoy"], "payoff: dakota inherits the stability"
    assert res["stability_margin"] > 0
    assert np.isfinite(res["gam_fidelity"])
    assert res["gate_pass"] is True


def test_gam_fidelity_floor_bites():
    """A blend that stops tracking the published GAM must fail even if stable.

    Decorrelating the inputs makes the linear blend CPOE-dominated while the GAM
    stays EPA-dominated, which is exactly the failure the floor exists to catch:
    stability criteria all satisfied, agreement with the reference model gone.
    """
    frame = _pbp(150, (2023, 2024), cpoe_stability=0.95, seed=7, correlated_inputs=False)
    unfloored = validate_dakota(frame, gam_fidelity_floor=0.0)
    assert unfloored["gate_pass"] is True, "the stability criteria still hold"
    res = validate_dakota(frame)
    assert res["gam_fidelity"] < 0.80
    assert res["gate_pass"] is False, "the fidelity floor must be what fails it"


def test_unstable_cpoe_fails_the_gate():
    """If CPOE stops being the stable input, the blend has lost its reason to exist."""
    res = validate_dakota(_pbp(150, (2023, 2024), cpoe_stability=0.0, seed=11))
    assert res["cpoe_yoy"] < 0.60
    assert res["gate_pass"] is False


def test_small_sample_fails_rather_than_passing_vacuously():
    res = validate_dakota(_pbp(10, (2023, 2024), cpoe_stability=0.95, seed=3))
    assert res["n_pairs"] == 10
    assert res["gate_pass"] is False
    assert "reason" in res


def test_passer_seasons_drop_null_cpoe_instead_of_zero_filling():
    """A null CPOE folded to 0 would read as league-average accuracy (pre-2006)."""
    df = pl.DataFrame(
        {
            "season": [2005] * 200 + [2010] * 200,
            "passer_player_id": ["00-0000001"] * 200 + ["00-0000002"] * 200,
            "passer_player_name": ["Old Timer"] * 200 + ["Modern QB"] * 200,
            "qb_epa": [0.1] * 400,
            "cpoe": [None] * 200 + [2.5] * 200,
        }
    )
    out = dakota_passer_seasons(df)
    assert out.height == 1
    assert out["season"].to_list() == [2010]


def test_linear_coefficients_match_the_shipped_metric():
    """The gate must approximate what sdv-py actually publishes."""
    assert DAKOTA_LINEAR_COEFFICIENTS == (0.816, 0.184)
    assert abs(sum(DAKOTA_LINEAR_COEFFICIENTS) - 1.0) < 1e-9
