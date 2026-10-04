# paper_index fixtures

Real released rows for `python/nfl_team_summaries/paper_index.py` (stage 09,
`nfl_paper_index_games`, and the luck columns on `nfl_team_summaries`), cut on
2026-10-04 from the published `espn_nfl_pbp` 2022 asset. That file is the one
sdv-py's own NFL Paper Index fixture was cut from and the one the NFL fit read (same
sha256 as `sportsdataverse-py/tests/fixtures/paper_index/README.md` records).

| fixture | rows | source | source sha256 |
| --- | --- | --- | --- |
| `espn_nfl_pbp_2022_slice.parquet` | 1,202 | `https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_nfl_pbp/play_by_play_2022.parquet` | `26459cef7f4186a7a63c3c1881ae4af2c480f527088353c8743554e9712c9376` |

## Selection

Every play of seven games, projected to `sportsdataverse.paper_index.PBP_COLUMNS` (23
columns) plus `nflverse_game_id`, sorted by `game_id, game_play_number`. Ids are as
released: `game_id`, `pos_team_id`, `homeTeamId`, `awayTeamId` all Int64;
`nflverse_game_id` is text.

| `game_id` | `nflverse_game_id` | type / week | game (ESPN team ids) | final | plays | why it is here |
| --- | --- | --- | --- | --- | --- | --- |
| 401437640 | `2022_01_NYG_TEN` | regular, 1 | Giants (19) at Titans (10) | 21-20 Giants | 162 | one of sdv-py's 12 oracle games; a Giants win |
| 401437759 | `2022_04_NE_GB` | regular, 4 | Patriots (17) at Packers (9) | 27-24 Packers | 175 | oracle game |
| 401437796 | `2022_07_NYG_JAX` | regular, 7 | Giants (19) at Jaguars (30) | 23-17 Giants | 179 | oracle game; a Giants win |
| 401437880 | `2022_13_WAS_NYG` | regular, 13 | Commanders (28) at Giants (19) | 20-20 | 194 | a TIE: sdv-py drops a game without a winner |
| 401437905 | `2022_15_ATL_NO` | regular, 15 | Falcons (1) at Saints (18) | 21-18 Saints | 158 | oracle game; the game the snap-floor test cuts short |
| 401437957 | `2022_18_NYG_PHI` | regular, 18 | Giants (19) at Eagles (21) | 22-16 Eagles | 177 | the last regular-season week; a Giants loss |
| 401438001 | `2022_19_NYG_MIN` | postseason, 1 | Giants (19) at Vikings (16), wild card | 31-24 Giants | 157 | a playoff game: ESPN numbers the postseason from week 1 again |

The Giants are the hand-computed team: three scored regular-season games (two wins, a
loss), a tie and a playoff win.

## The snap floor has no released NFL case

sdv-py scores a game only when both sides ran 20 or more scrimmage snaps. Measured on
every `espn_nfl_pbp` season 2002-2026 (2026-10-04): no completed, decided game with
computable inputs has a side under 20. The games the Paper Index does not score are
the ones level on their last play (real ties, and truncated 2002-2004 feeds that stop
at 0-0 or 7-7), the Pro Bowls (non-franchise sides) and the truncated 2002-2004 and
2007 feeds that carry no scrimmage rows at all. So the floor
test cuts a real game short instead: the first 52 plays of 401437905 (by
`game_play_number`) leave Atlanta 19 scrimmage snaps and New Orleans 24 at 14-3, and
the game is not scored; the first 56 give Atlanta 22 and it is.

## Hand numbers

Shares are `sportsdataverse.paper_index.paper_index_games` at sdv-py `769ea7fc` on the
fixture rows. The four oracle games are also Game on Paper's own module on the same
rows and the trainer's full-precision shares, both copied from sdv-py's
`tests/fixtures/paper_index/` (`gop_compute_nfl.json` `homeShare`,
`paper_index_oracle_nfl.json` `expectedHomeShare`):

| game | home | this producer | GOP module | trainer |
| --- | --- | --- | --- | --- |
| 401437796 | Jaguars | 0.3340518325693759 | 0.334051832569376 | 0.3340565130289467 |
| 401437905 | Saints | 0.4736022340110611 | 0.47360223401106105 | 0.47358853727444855 |
| 401437640 | Titans | 0.6107782910790239 | 0.6107782910790238 | 0.6107839271392764 |
| 401437759 | Packers | 0.7496249078045323 | 0.7496249078045325 | 0.7496201860489962 |

The shipped weights are rounded to 4 decimals, so the trainer's shares are held to
`5e-4` (GOP's own oracle tolerance) and GOP's module to `1e-9`.

| team | game | won | `paper_share` |
| --- | --- | --- | --- |
| Giants | 401437640 (week 1) | yes | 0.3892217089209761 |
| Giants | 401437796 (week 7) | yes | 0.6659481674306241 |
| Giants | 401437957 (week 18) | no | 0.2673060257282711 |
| Giants | 401438001 (wild card) | yes | 0.7246169632675805 |

Giants, regular season: `deserved_wins` = 0.3892217089209761 + 0.6659481674306241 +
0.2673060257282711 = 1.3224759020798713; wins = 2; `luck_wins` = 2 - 1.3224759020798713
= 0.6775240979201287; variance = 0.237728 + 0.222461 + 0.195854 = 0.656043, so `luck_z`
= 0.677524 / sqrt(0.656043) = 0.836486. `paper_index_games_n` = 3: the tie is not a
game, a win or a loss, and the wild-card game is in `nfl_paper_index_games` only.

The 2022 regular season over the eight teams of the five scored games, each metric in
its own order (rank 1 first):

| team | games | wins | `deserved_wins` | `luck_wins` | `luck_wins_rank` | `luck_z` | `luck_z_rank` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Giants | 3 | 2 | 1.322476 | 0.677524 | 1 | 0.836486 | 2 |
| Saints | 1 | 1 | 0.473602 | 0.526398 | 2 | 1.054266 | 1 |
| Eagles | 1 | 1 | 0.732694 | 0.267306 | 3 | 0.604009 | 3 |
| Packers | 1 | 1 | 0.749625 | 0.250375 | 4 | 0.577928 | 4 |
| Patriots | 1 | 0 | 0.250375 | -0.250375 | 5 | -0.577928 | 5 |
| Jaguars | 1 | 0 | 0.334052 | -0.334052 | 6 | -0.708250 | 6 |
| Falcons | 1 | 0 | 0.526398 | -0.526398 | 7 | -1.054266 | 7 |
| Titans | 1 | 0 | 0.610778 | -0.610778 | 8 | -1.252689 | 8 |

The deserved wins sum to 5, the scored games. The Saints' `luck_z` is
sqrt(0.526398 / 0.473602) = 1.054266: one win on a 0.47 share is fewer wins of luck
than the Giants' three games and more standard deviations. Washington (the tie only)
and Minnesota (the playoff game only) have `paper_index_games_n` = 0, null luck and no
rank, as do the 22 teams with no fixture game.
