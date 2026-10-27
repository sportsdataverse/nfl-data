"""R843-3: team summaries use sdv-py's standard per-yard adjusted-line-yards band."""

from __future__ import annotations

import polars as pl
import pytest
from nfl_team_summaries.build import _rush_yardage_bands

# yds_rushed -> (line, second_level, open_field), the band sdv-py's processors write
EXPECTED = {
    -3: (-3.6, 0.0, 0.0),
    0: (0.0, 0.0, 0.0),
    4: (4.0, 0.0, 0.0),
    7: (5.5, 1.5, 0.0),  # the old band read 3.5 line yards here
    10: (7.0, 3.0, 0.0),
    25: (7.0, 3.0, 15.0),  # the old band read 0 line yards here
}


@pytest.mark.parametrize("yds", sorted(EXPECTED))
def test_band_matches_sdv_py(yds):
    out = _rush_yardage_bands(pl.DataFrame({"rush": [1], "yds_rushed": [yds]})).row(0, named=True)
    line, second, open_field = EXPECTED[yds]
    assert out["line_yards"] == pytest.approx(line)
    assert out["second_level_yards"] == pytest.approx(second)
    assert out["open_field_yards"] == pytest.approx(open_field)


def test_parts_sum_to_every_gain():
    df = _rush_yardage_bands(pl.DataFrame({"rush": [1] * 100, "yds_rushed": list(range(100))}))
    total = df["line_yards"] + df["second_level_yards"] + df["open_field_yards"]
    assert (total - df["yds_rushed"]).abs().max() < 1e-9


def test_non_rushes_stay_null():
    out = _rush_yardage_bands(pl.DataFrame({"rush": [0], "yds_rushed": [8]})).row(0, named=True)
    assert out["line_yards"] is None and out["second_level_yards"] is None and out["open_field_yards"] is None
