# receiver_targets fixtures

Real 2003 plays for `fill_receiver_ids` (`python/nfl_team_summaries/input.py`) and
`tests/test_receiver_targets.py`, cut on 2026-11-01.

| fixture | rows | source | source sha256 |
| --- | --- | --- | --- |
| `model_pbp_2003_det.parquet` | 1,304 x 11 | `model_pbp_2003.parquet` on the `nfl_model_pbp` release tag of `sportsdataverse/sportsdataverse-data` (44,962 rows x 327 columns) | `62da2363b0fe94bd5688d7a5d416ae428890a0744a50013f624d57a6d315bd17` |
| (oracle column `nflverse_receiver_id`) | | `play_by_play_2003.parquet` on the `pbp` release tag of `nflverse/nflverse-data`, its `receiver_id` joined on `game_id, play_id` | `a5bc20c69eee0c18364bea7fa1d3c2817941c8d9026058c694ab1ee73a2d279d` |

Hashes are of the files as downloaded that day. nflverse data (c) nflverse contributors,
CC BY 4.0.

## Selection

Every play with `posteam == "DET"` (the 2003 Lions' offense, regular season only), sorted
by `game_id, play_id`. One whole team-season, because the fill's id lookup is the mode
over `(name, posteam)` for the season: a slice of a team's season would change it.
nflverse's `receiver_id` is null on its 693 non-pass rows.

## Hand-counted cells

Throws are `pass_attempt == 1 & sack == 0`: 590, 269 of them with no
`receiver_player_id` (the 2003 Shield feed has no pass-target stat). nflverse names a
receiver on all but 11 (throwaways, spikes, "pass incomplete (B.Berry)").

| receiver | id | targets / catches, raw | targets / catches, nflverse |
| --- | --- | --- | --- |
| A.Hakim | `00-0006627` | 50 / 49 | 109 / 49 |
| C.Rogers | `00-0022072` | 22 / 22 | 52 / 22 |

## Regenerate

```python
import polars as pl

m = pl.read_parquet(f"{SRC}/model_pbp_2003.parquet")
o = pl.read_parquet(f"{SRC}/play_by_play_2003.parquet").select(
    "game_id", pl.col("play_id").cast(pl.Int64), pl.col("receiver_id").alias("nflverse_receiver_id")
)
(
    m.filter(pl.col("posteam") == "DET")
    .select("game_id", "play_id", "season_type", "posteam", "desc", "pass_attempt", "sack",
            "complete_pass", "receiver_player_id", "receiver_player_name")
    .join(o, on=["game_id", "play_id"], how="left")
    .sort("game_id", "play_id")
    .write_parquet("tests/fixtures/receiver_targets/model_pbp_2003_det.parquet")
)
```
