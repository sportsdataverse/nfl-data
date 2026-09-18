"""``native_pbp.*`` is a re-export shim over ``sportsdataverse.nfl.shield_pbp``.

The parser graduated to the library (sportsdataverse-py #528) and these modules
stayed behind as compat shims. The rest of ``tests/native_pbp/`` already runs
every parser test through ``from native_pbp.X import ...``, so it is the shim's
real coverage; this file pins the identity -- one definition, in sdv-py -- so a
name that quietly stops being re-exported fails here instead of at 04:00 in the
cron.
"""

from __future__ import annotations

import importlib

import pytest

pytest.importorskip(
    "sportsdataverse.nfl.shield_pbp",
    reason="needs a sdv-py that ships shield_pbp (lock bump pending)",
)

#: module -> the names this repo imports from it (public via ``import *``,
#: private explicitly)
SHIMMED = {
    "build": ["build_pbp", "build_pbp_from_file", "build_season"],
    "description": ["add_description_features", "add_pass_rush", "add_qb_dropback"],
    "drives": ["add_drive_detail", "last_or_first_result", "swapped_posteam", "_OUTPUT_SCHEMA"],
    "features": ["add_game_state"],
    "labels": ["add_labels"],
    "parse": [
        "parse_game",
        "_clock_to_seconds",
        "_game_half",
        "_impute_clock",
        "_resolve_teams_and_game_id",
        "_yardline_100",
    ],
    "playstats": ["PLAYSTATS_SCHEMA", "build_playstats_frame", "build_playstats_season"],
    "repairs": [
        "apply_game_repairs",
        "fix_bad_games",
        "fix_posteams",
        "fix_scrambles",
        "fix_weird_pass_plays",
    ],
    "series": ["add_series_data", "_OUTPUT_SCHEMA"],
    "stat_ids": ["sum_play_stats"],
}


@pytest.mark.parametrize("mod", sorted(SHIMMED))
def test_shim_re_exports_the_graduated_object_itself(mod):
    shim = importlib.import_module(f"native_pbp.{mod}")
    real = importlib.import_module(f"sportsdataverse.nfl.shield_pbp.{mod}")
    for name in SHIMMED[mod]:
        assert hasattr(shim, name), f"native_pbp.{mod} no longer re-exports {name}"
        assert getattr(shim, name) is getattr(real, name), f"{mod}.{name} is a second definition"


def test_the_shim_carries_no_parser_code_of_its_own():
    """A shim is a docstring plus imports: a stray ``def`` here is a fork."""
    for mod in SHIMMED:
        src = importlib.import_module(f"native_pbp.{mod}").__file__
        with open(src, encoding="utf-8") as fh:
            body = fh.read()
        assert "\ndef " not in body and "\nclass " not in body, mod


def test_fetcher_re_exports_the_graduated_game_id_rule():
    from model_training.play_level import fetcher
    from sportsdataverse.nfl.shield_pbp import game_id as real

    for name in ("nflverse_game_id", "_team_abbr", "_nflverse_abbr", "_RELOCATIONS"):
        assert getattr(fetcher, name) is getattr(real, name), name
