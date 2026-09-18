"""``fixed_drive`` / ``fixed_drive_result`` + the ``drive_*`` detail columns.

**Moved.** This module graduated to
:mod:`sportsdataverse.nfl.shield_pbp.drives` (sportsdataverse-py #528): the same
parser now serves live Shield games as well as this repo's ``nfl_model_pbp``
build, so it lives in the library and nfl-data keeps only its pipeline. Edit it
there -- this file is a compat shim so every ``from native_pbp.drives import
...`` in this repo (the CLI, ``model_training``, ``parity``, the tests) keeps
resolving to one definition.

Same pattern as ``ncaa-mfb-football-raw``'s
``ncaa_mfb_raw_scrape/mfb_cfbfastr.py``.
"""

from __future__ import annotations

from sportsdataverse.nfl.shield_pbp.drives import *  # noqa: F401,F403
from sportsdataverse.nfl.shield_pbp.drives import (  # noqa: F401
    _OUTPUT_SCHEMA,
)
