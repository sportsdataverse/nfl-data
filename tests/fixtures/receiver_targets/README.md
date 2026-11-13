# receiver_targets fixtures

Real 2003 and 2004 plays for `fill_receiver_ids` (`python/nfl_team_summaries/input.py`) and
`tests/test_receiver_targets.py`, cut on 2026-11-01.

| fixture | rows | source | source sha256 |
| --- | --- | --- | --- |
| `model_pbp_2003_det.parquet` | 1,304 x 11 | `model_pbp_2003.parquet` on the `nfl_model_pbp` release tag of `sportsdataverse/sportsdataverse-data` (44,962 rows x 327 columns) | `62da2363b0fe94bd5688d7a5d416ae428890a0744a50013f624d57a6d315bd17` |
| (oracle column `nflverse_receiver_id`) | | `play_by_play_2003.parquet` on the `pbp` release tag of `nflverse/nflverse-data`, its `receiver_id` joined on `game_id, play_id` | `a5bc20c69eee0c18364bea7fa1d3c2817941c8d9026058c694ab1ee73a2d279d` |
| `model_pbp_2004_cle.parquet` | 1,268 x 11 | `model_pbp_2004.parquet`, same tag (44,891 rows x 327 columns), with `play_by_play_2004.parquet`'s `receiver_id` from the same nflverse tag as the oracle column | `d31a2d5b633d116934bd36810ba1f2b4c4aaf65f2207e24edd83a5ea4d0d8889` (pbp), `94658bc15788eda63a8cdba0d8f1c8aa9253fb5baa9c0d07b9c2e35e75ae6a03` (nflverse) |
| `model_pbp_2003_ari.parquet` | 1,301 x 14 | `model_pbp_2003.parquet` (same file as the DET row), Arizona's regular-season offense, cut 2026-11-13, with `play_by_play_2003.parquet`'s `passer_id` / `rusher_id` (nflverse asset dated 2025-04-30) as the oracle columns `nflverse_passer_id` / `nflverse_rusher_id` | `62da2363b0fe94bd5688d7a5d416ae428890a0744a50013f624d57a6d315bd17` (pbp) |

Hashes are of the files as downloaded that day. nflverse data (c) nflverse contributors,
CC BY 4.0.

## Selection

Every play with `posteam == "DET"` (the 2003 Lions' offense, regular season only), sorted
by `game_id, play_id`. One whole team-season, because the fill's id lookup is the mode
over `(name, posteam)` for the season: a slice of a team's season would change it.
nflverse's `receiver_id` is null on its 693 non-pass rows.

The Cleveland 2004 offense (cut 2026-11-01, same selection, `posteam == "CLE"`) is the
unnamed-throw case: "Andre' Davis"'s apostrophe stops the name parser, so his catches carry an
id with no parsed name. 440 throws, 188 with no stat receiver; nflverse names a receiver on all
but 19, among them play 1406 ("J.Garcia pass incomplete to Andre' Davis (W.Peterson).").

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

The Cleveland 2004 file is the same recipe on the 2004 files with `posteam == "CLE"`,
written to `model_pbp_2004_cle.parquet`.

The Arizona 2003 file (`tests/native_pbp/test_player_ids.py`) keeps `posteam == "ARI"` and
`season_type == "REG"` with the columns `game_id, play_id, season_type, posteam, desc, qb_scramble,
{passer,rusher,fumbled_1}_player_{name,id}`, joined to nflverse's `passer_id` / `rusher_id`.

It holds 46 charted scrambles (`qb_scramble == 1`). On those, current nflfastR (#536,
2025-10-10) makes the scrambling QB the `passer` and leaves no `rusher`. nflverse's 2003 asset
predates that fix and still names him the `rusher`. Every other row's ids equal nflverse's.
