# espn_nfl fixture

One real game from `sportsdataverse/nfl-raw` `nfl/espn/` -- ESPN event
401772510 (2025 week 1, DAL @ PHI): the summary (`raw/`), the slimmed core play
participants (`plays/`) and its crosswalk row -- laid out exactly like the raw
library so `nfl_espn_build` runs over it unchanged (`--raw-dir tests/fixtures/espn_nfl`).

Refresh:

    cp ../nfl-raw/nfl/espn/raw/2025/401772510.json.gz tests/fixtures/espn_nfl/raw/2025/
    cp ../nfl-raw/nfl/espn/plays/2025/401772510.json.gz tests/fixtures/espn_nfl/plays/2025/
