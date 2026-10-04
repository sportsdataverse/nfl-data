# player_dispersion fixture

`rushers_2024_nyg_wk01_05.csv`: 41 real carries, cut from the published 2024
`nfl_model_pbp`, for `test_player_dispersion.py`.

- **Source:** `model_pbp_2024.parquet` on the `nfl_model_pbp` release tag of
  `sportsdataverse/sportsdataverse-data`, downloaded 2026-10-04 (47,366 rows x 326
  columns, sha256 `94a72afbcd45c4ae06e43d10fa4756eed0b0af124ce21e8fd96190650c4b1d6c`),
  passed through `input.prepare_plays` (regular season) and `build.add_derived_metrics`,
  then the rushing table's own filter (`_team_off`, `rush == 1`, `rusher_player_id` not
  null).
- **Cut:** the Giants (`pos_team_id == "19"`, the ESPN team id), their first five games
  of 2024 (weeks 1-5: `2024_01_MIN_NYG`, `2024_02_NYG_WAS`, `2024_03_NYG_CLE`,
  `2024_04_DAL_NYG`, `2024_05_NYG_SEA`), three rushers:
  - Tyrone Tracy (`00-0039384`): 30 carries over 5 games;
  - Eric Gray (`00-0038396`): 8 carries over 4 games;
  - Malik Nabers (`00-0039337`): 3 carries over 2 games, under the 3-game dispersion
    floor.
- **Columns:** the ones the helpers read (`game_id`, `pos_team_id`, `rusher_player_id`,
  `EPA`, `yds_rushed`, `pos_score_diff_start`) plus `week`, `game_play_number` and
  `rusher_player_name` for reading. Values are written unrounded.

The boundary carries the tests depend on are real: Tracy has three 4-yard, three 5-yard
and an 11-yard carry, which sit on the tier cut-points, two carries trailing by exactly
8 (inside one score) and two leading by 10 (outside); Nabers has a 4-yard loss. No back
in the cut has a 10-yard carry, so that one edge is a synthetic row in the test.

Gray's -11.47 EPA carry is real too: play 613 of `2024_05_NYG_SEA`, fourth-and-goal
from the 1, a fumble Seattle returned 102 yards for a touchdown. It is why his week-5
game is his one bust.

Regenerate (from the repo root, with `model_pbp_2024.parquet` in `PBP_DIR`):

```python
import polars as pl
from nfl_team_summaries.build import _team_off, add_derived_metrics
from nfl_team_summaries.input import load_model_pbp, prepare_plays

# the neutral-site flag is not read here, so no schedule download
no_schedule = lambda seasons: pl.DataFrame(schema={"game_id": pl.Utf8, "location": pl.Utf8})
plays = add_derived_metrics(
    prepare_plays(load_model_pbp(2024, PBP_DIR), 2024, schedule_fn=no_schedule)
)
games = [
    "2024_01_MIN_NYG", "2024_02_NYG_WAS", "2024_03_NYG_CLE", "2024_04_DAL_NYG",
    "2024_05_NYG_SEA",
]
(
    _team_off(plays)
    .filter(
        (pl.col("rush") == 1)
        & (pl.col("pos_team_id") == "19")
        & pl.col("game_id").is_in(games)
        & pl.col("rusher_player_id").is_in(["00-0039384", "00-0038396", "00-0039337"])
    )
    .sort("game_id", "game_play_number")
    .select(
        "game_id", "week", "game_play_number", "pos_team_id", "rusher_player_id",
        "rusher_player_name", "EPA", "yds_rushed", "pos_score_diff_start",
    )
    .write_csv("tests/fixtures/player_dispersion/rushers_2024_nyg_wk01_05.csv")
)
```
