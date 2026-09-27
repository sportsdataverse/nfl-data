# shield_thin fixture

Real inputs for the 1999-2002 thin-game backfill (`native_pbp.cli._backfill_thin_games`).

`raw/{season}/{game_id}.json.gz` are `sportsdataverse/nfl-raw` `nfl/raw` Shield payloads, gzipped
(the tests decompress them into a `{raw_dir}/{season}/{game_id}.json` library):

| game | Shield `driveChart.plays` | role |
|---|---|---|
| `2000_10_KC_OAK` | thin | 1999-2000 nflverse shape: markers carry only `desc` (one with a null `timeout`); two-minute warnings; OAK; a `""` posteam |
| `2000_03_SD_KC` | thin | absent from nflverse: no play data anywhere |
| `2000_06_BUF_MIA` | none (2 KB shell) | absent from nflverse: no play data anywhere |
| `2002_13_STL_PHI` | thin | 2001+ shape: markers are `play_type_nfl == "TIMEOUT"`, one comment-prefixed; STL |
| `2002_16_MIA_MIN` | full (154) | a full-length <= 2002 game, left untouched |
| `2003_09_CAR_HOU` | full (148) | the 2003 build schema |

`nflverse_pbp.parquet` holds the nflverse pbp rows of `2000_10_KC_OAK` and `2002_13_STL_PHI`
(`load_nfl_pbp([2000, 2002])`, 2026-09-27). It is trimmed to the columns the backfill can read:
the build frame's columns plus the marker-filter inputs. `_backfill_thin_games` selects by the
build schema, so it never reads the dropped columns.

Refresh (from the repo root, nfl-raw checked out as a sibling):

```sh
for g in 2000/2000_10_KC_OAK 2000/2000_03_SD_KC 2000/2000_06_BUF_MIA 2002/2002_13_STL_PHI \
         2002/2002_16_MIA_MIN 2003/2003_09_CAR_HOU; do
  gzip -9 -n -c ../nfl-raw/nfl/raw/$g.json > tests/fixtures/shield_thin/raw/$g.json.gz
done
cd python && SDV_PY_NFL_CACHE=off uv run --no-sync python - <<'EOF'
import gzip, json
import polars as pl
from native_pbp.build import build_pbp
from sportsdataverse.nfl import load_nfl_pbp
F = "../tests/fixtures/shield_thin"
game = json.load(gzip.open(f"{F}/raw/2003/2003_09_CAR_HOU.json.gz"))
keep = set(build_pbp(game, game_id="2003_09_CAR_HOU").columns) | {"desc", "play_type_nfl", "timeout", "play_type"}
nv = load_nfl_pbp([2000, 2002]).filter(pl.col("game_id").is_in(["2000_10_KC_OAK", "2002_13_STL_PHI"]))
nv.select([c for c in nv.columns if c in keep]).write_parquet(
    f"{F}/nflverse_pbp.parquet", compression="zstd", compression_level=22, statistics=False
)
EOF
```

nflverse_pbp.parquet is adapted from nflverse-data `pbp/play_by_play_{2000,2002}.parquet`
(https://github.com/nflverse/nflverse-data), © nflverse contributors, licensed CC BY 4.0
(https://creativecommons.org/licenses/by/4.0/). Changes: filtered to two games and trimmed to the
columns listed above.
