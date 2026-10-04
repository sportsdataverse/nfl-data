# defense_vs_position fixtures

Real published 2024 rows for `python/nfl_team_summaries/defense_vs_position.py` (stage 08)
and `tests/test_defense_vs_position.py`, cut on 2026-10-04.

| fixture | rows | source | source sha256 |
| --- | --- | --- | --- |
| `model_pbp_2024_slice.parquet` | 1,349 x 21 | `model_pbp_2024.parquet` on the `nfl_model_pbp` release tag of `sportsdataverse/sportsdataverse-data` (47,366 rows x 326 columns) | `94a72afbcd45c4ae06e43d10fa4756eed0b0af124ce21e8fd96190650c4b1d6c` |
| `nfl_rosters_2024_slice.parquet` | 133 x 5 | `roster_2024.parquet` on the `rosters` release tag of `nflverse/nflverse-data` (3,216 rows x 36 columns), the file `sportsdataverse.nfl.load_nfl_rosters([2024])` reads | `bd38dbe785728c6b4ddc0b56b7d4fee69a8337595db3b631528d284253c04aaf` |

Both hashes are of the files as downloaded that day. The pbp asset is the one the
`player_dispersion` fixture beside this one was cut from (same hash).

## Selection

**pbp**: every play (special teams and penalties included) the six defenses below
defended in the listed regular-season games: the semi-join of the season pbp on those
`(defteam, game_id)` pairs, sorted by `game_id, play_id`. Columns:
`sportsdataverse.defense_vs_position.PBP_COLUMNS["nfl"]` plus `qb_scramble` (the stage
reads it) and `week`, `posteam`, `desc` for reading plays by hand.

| defense (`team_id`) | games (`game_id`) | why it is here |
| --- | --- | --- |
| Philadelphia (21) | `2024_01_GB_PHI`, `2024_02_ATL_PHI`, `2024_03_PHI_NO` | qualifier |
| Denver (7) | `2024_01_DEN_SEA`, `2024_02_PIT_DEN`, `2024_03_DEN_TB` | qualifier |
| Baltimore (33) | `2024_01_BAL_KC`, `2024_02_LV_BAL`, `2024_03_BAL_DAL` | qualifier |
| Kansas City (12) | `2024_01_BAL_KC`, `2024_02_CIN_KC`, `2024_03_KC_ATL` | qualifier |
| Detroit (8) | `2024_01_LA_DET`, `2024_02_TB_DET`, `2024_03_DET_ARI` | qualifier |
| Pittsburgh (23) | `2024_01_PIT_ATL`, `2024_02_PIT_DEN` | 2 games, so never `qualified` |

Each defense carries its first games of 2024 (weeks 1-3; Pittsburgh weeks 1-2). Five
qualifiers is exactly `MIN_COHORT_TEAMS`, the F5 cohort floor: one fewer and every
`_pct` is null.

**rosters**: `season`, `team`, `position`, `full_name`, `gsis_id` for every rusher and
receiver id in the pbp slice: 133 ids, 133 rows (12 QB, 37 RB, 55 WR, 28 TE, 1 OL).

## Hand-computed cells

Counted row by row in plain Python loops over the fixture files, not through the stage
or the sdv-py function. Population: `play_type` pass or run, `down` 1-4, `epa` not
null, `season_type` REG or POST. A dropback is `pass == 1`, a carry `rush == 1`, a
target a dropback that is not a sack and has a `receiver_player_id`.

**RB, EPA per play allowed** (carries by a roster RB, plus targets naming one). Lower
is the better defense, so the lowest ranks first.

| defense | plays | games | EPA sum | EPA/play | carries | rush yards | rank of 5 | `_pct` = 100 * (6 - rank) / 6 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Detroit | 55 | 3 | -9.881017645719112 | -0.179655 | 50 | 138 | 1 | 83.33 |
| Baltimore | 68 | 3 | -11.645739803803735 | -0.171261 | 45 | 117 (2.60 a carry, the lowest) | 2 | 66.67 |
| Denver | 91 | 3 | -7.373975946989958 | -0.081033 | 72 | 320 | 3 | 50.00 |
| Kansas City | 66 | 3 | -2.7571574459871044 | -0.041775 | 53 | 177 | 4 | 33.33 |
| Philadelphia | 88 | 3 | -3.1620409803072107 | -0.035932 | 70 | 366 | 5 | 16.67 |
| Pittsburgh | 48 | 2 | -1.7207644601585343 | -0.035849 | 36 | 128 | none (2 games) | null |

Pittsburgh would be the sixth row of the cohort if it leaked in, which moves every
value above (Detroit to 600 / 7).

**QB, sack rate** (sacks per dropback). The one reversed column: more sacks is the
better defense, so the highest ranks first.

| defense | dropbacks | sacks | sack rate | rank of 5 | `_pct` |
| --- | --- | --- | --- | --- | --- |
| Denver | 94 | 11 | 0.117021 | 1 | 83.33 |
| Baltimore | 129 | 10 | 0.077519 | 2 | 66.67 |
| Detroit | 115 | 8 | 0.069565 | 3 | 50.00 |
| Kansas City | 124 | 6 | 0.048387 | 4 | 33.33 |
| Philadelphia | 95 | 4 | 0.042105 | 5 | 16.67 |
| Pittsburgh | 66 | 4 | 0.060606 | none (2 games) | null |

Pittsburgh would rank 4th of 6 if it leaked in, pushing Kansas City to 5th.

**`unattributed_target_share`** (throws = dropbacks that are neither sacks nor
scrambles; unattributed = no `receiver_player_id`).

- Pittsburgh at Denver, `2024_02_PIT_DEN`, Pittsburgh's defense: 39 dropbacks = 35
  throws + 2 sacks + 2 scrambles (plays 2655 and 3838, both "B.Nix scrambles"). Two
  throws name no receiver: play 1372 ("B.Nix pass incomplete short right.", a
  throwaway) and play 4207 (the D.Kazee interception on the last play). 2 / 35 =
  0.057143. Counting the scrambles as throws would give 4 / 37.
- Per defense over its games: Pittsburgh 4 of 60, Philadelphia 5 of 89, Detroit 1 of
  102, Kansas City 5 of 106, Baltimore 4 of 117, Denver 3 of 78.

## Regenerate

From the repo root, with the two source files downloaded to `SRC`:

```python
import polars as pl
from sportsdataverse.defense_vs_position import PBP_COLUMNS

games = {
    "PHI": ["2024_01_GB_PHI", "2024_02_ATL_PHI", "2024_03_PHI_NO"],
    "DEN": ["2024_01_DEN_SEA", "2024_02_PIT_DEN", "2024_03_DEN_TB"],
    "BAL": ["2024_01_BAL_KC", "2024_02_LV_BAL", "2024_03_BAL_DAL"],
    "KC": ["2024_01_BAL_KC", "2024_02_CIN_KC", "2024_03_KC_ATL"],
    "DET": ["2024_01_LA_DET", "2024_02_TB_DET", "2024_03_DET_ARI"],
    "PIT": ["2024_01_PIT_ATL", "2024_02_PIT_DEN"],
}
pairs = pl.DataFrame(
    [(t, g) for t, gs in games.items() for g in gs], schema=["defteam", "game_id"], orient="row"
)
out = "tests/fixtures/defense_vs_position"
pbp = (
    pl.read_parquet(f"{SRC}/model_pbp_2024.parquet")
    .select(*PBP_COLUMNS["nfl"], "qb_scramble", "week", "posteam", "desc")
    .join(pairs, on=["defteam", "game_id"], how="semi")
    .sort("game_id", "play_id")
)
pbp.write_parquet(f"{out}/model_pbp_2024_slice.parquet")
ids = set(pbp["rusher_player_id"].drop_nulls()) | set(pbp["receiver_player_id"].drop_nulls())
(
    pl.read_parquet(f"{SRC}/roster_2024.parquet")
    .filter(pl.col("gsis_id").is_in(list(ids)))
    .select("season", "team", "position", "full_name", "gsis_id")
    .sort("gsis_id")
    .write_parquet(f"{out}/nfl_rosters_2024_slice.parquet")
)
```

Both upstream assets can be republished in place, so a later download can differ from
the hashes above; the hand counts hold for the committed slices.
