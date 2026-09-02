"""Tests for the punt landing-distribution holdout gate.

The gate's THRESHOLDS come from real measurements against the shipped surface
(recorded in validate.py's constant docstrings and in docs/models/punt.md); these
tests pin the gate's *arithmetic* on deterministic frames, so they need no
network and no model artifact. A test that only asserted "gate_pass is True" on
a surface built from the same rows would pass no matter what the statistic did --
each case below is constructed so that a broken statistic flips the verdict.
"""

from __future__ import annotations

import polars as pl
from model_training.decision_models.validate import (
    PUNT_HOLDOUT_KS_MAX,
    realized_punt_landings,
    validate_punt_holdout,
)


def _pbp(landings: dict[float, list[float]]) -> pl.DataFrame:
    """Synthetic punt PBP: {snap yardline: [resulting yardline, ...]}.

    Encoded as a straight kick with no return so ``yardline_after`` is exactly
    ``yardline_100 - kick_distance``.
    """
    rows = []
    for yl, afters in landings.items():
        for after in afters:
            rows.append(
                {
                    "desc": "P.Unter punts 40 yards to the 20.",
                    "play_type": "punt",
                    "yardline_100": float(yl),
                    "kick_distance": float(yl - after),
                    "return_yards": 0.0,
                }
            )
    return pl.DataFrame(rows)


def _surface(mass: dict[float, dict[float, float]]) -> pl.DataFrame:
    rows = [
        {"yardline_100": yl, "yardline_after": after, "pct": pct, "muff": 0}
        for yl, spots in mass.items()
        for after, pct in spots.items()
    ]
    return pl.DataFrame(rows)


def _uniform_landings(yl: float, spots: list[float], per_spot: int) -> dict[float, list[float]]:
    return {yl: [s for s in spots for _ in range(per_spot)]}


def test_realized_landings_mirrors_the_builder_construction():
    pbp = pl.DataFrame(
        {
            "desc": ["punt to the end zone", "punt BLOCKED", "normal punt", "short field punt"],
            "play_type": ["punt", "punt", "punt", "punt"],
            "yardline_100": [70.0, 60.0, 80.0, 25.0],
            "kick_distance": [None, None, 45.0, 10.0],
            "return_yards": [None, None, 5.0, 0.0],
        }
    )
    out = realized_punt_landings(pbp)
    got = dict(zip(out["yardline_100"].to_list(), out["yardline_after"].to_list()))
    assert got[70.0] == 20.0, "end-zone punt with a null kick_distance must land at 20"
    assert got[60.0] == 60.0, "blocked punt with a null landing must stay at the snap"
    assert got[80.0] == 40.0, "80 - 45 + 5"
    assert 25.0 not in got, "snaps inside the 30 are outside the surface's domain"


def test_surface_matching_reality_passes():
    spots = [20.0, 21.0, 22.0, 23.0]
    pbp = _pbp(_uniform_landings(60.0, spots, per_spot=25))
    surface = _surface({60.0: {s: 0.25 for s in spots}})
    res = validate_punt_holdout(surface, pbp)
    assert res["n_punts"] == 100
    assert res["n_yardlines"] == 1
    assert res["weighted_ks"] < 1e-9
    assert abs(res["mean_landing_diff"]) < 1e-9
    assert res["gate_pass"] is True


def test_surface_shifted_downfield_fails_the_gate():
    """A 10-yard shift is a real regression; both criteria must catch it."""
    spots = [20.0, 21.0, 22.0, 23.0]
    pbp = _pbp(_uniform_landings(60.0, spots, per_spot=25))
    surface = _surface({60.0: {s + 10.0: 0.25 for s in spots}})
    res = validate_punt_holdout(surface, pbp)
    assert res["weighted_ks"] > PUNT_HOLDOUT_KS_MAX
    assert abs(res["mean_landing_diff"]) > 3.5
    assert res["gate_pass"] is False


def test_mean_yards_criterion_bites_when_ks_alone_would_pass():
    """Moving a little mass a long way barely moves KS but must still fail.

    KS caps at the displaced mass (0.1 here, under the 0.22 ceiling), so a
    KS-only gate would wave this through; the mean-landing band is what catches
    a surface whose tail is in the wrong place.
    """
    spots = [20.0] * 90 + [21.0] * 10
    pbp = _pbp({60.0: spots})
    surface = _surface({60.0: {20.0: 0.9, 60.0: 0.1}})
    res = validate_punt_holdout(surface, pbp)
    assert res["weighted_ks"] <= PUNT_HOLDOUT_KS_MAX, "KS alone would pass this"
    assert abs(res["mean_landing_diff"]) > 3.5
    assert res["gate_pass"] is False


def test_thin_yardlines_are_excluded_not_silently_scored():
    """A yardline with too few real punts must drop out, not contribute noise."""
    pbp = _pbp({60.0: [20.0] * 30, 75.0: [30.0] * 5})
    surface = _surface({60.0: {20.0: 1.0}, 75.0: {99.0: 1.0}})
    res = validate_punt_holdout(surface, pbp)
    assert res["n_yardlines"] == 1, "the 5-punt yardline must be excluded from KS"
    assert res["weighted_ks"] < 1e-9
    # ...but it is still counted in n_punts, so the exclusion is visible.
    assert res["n_punts"] == 35


def test_empty_holdout_reports_nan_and_does_not_pass():
    """No comparable data must never read as a pass."""
    pbp = _pbp({60.0: [20.0] * 30}).head(0)
    surface = _surface({60.0: {20.0: 1.0}})
    res = validate_punt_holdout(surface, pbp)
    assert res["n_yardlines"] == 0
    assert res["gate_pass"] is False
