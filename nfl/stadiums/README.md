# `nfl/stadiums/` — NFL stadium reference

`stadiums.csv` is a verbatim copy of nfelo's stadium table: one row per NFL stadium used since 1999, keyed by the
Pro-Football-Reference stadium id (`stadium_id`, e.g. `KAN00`), with coordinates (`lat`, `lon`, `altitude`), field
`heading`, the first and last game dates there, `surface_type`, `roof_type`, address, time zone, capacity and history.

| | |
|---|---|
| source | [greerreNFL/Stadiums](https://github.com/greerreNFL/Stadiums) `data/stadiums.csv` (nfelo; read by `nfelodcm`) |
| upstream commit | `3e97318781f198973e1414189d6324249657f562` (2026-10-20) |
| fetched | 2026-10-27, `https://raw.githubusercontent.com/greerreNFL/Stadiums/3e97318781f198973e1414189d6324249657f562/data/stadiums.csv` |
| size | 51,180 bytes, 67 stadiums |
| sha256 | `c73bc82fdcb5abe9018227a61bfe91a562d7bf1f10214ee34f1a480d5bcd519c` |
| licence | none declared upstream (the repository has no LICENSE); credit nfelo / greerreNFL wherever it is shown |

`stadium_id` is the same key as nflverse's `games.stadium_id`, so a game joins to its venue directly.

The file is not edited here: to refresh it, fetch the upstream file at a newer commit and update the commit, date,
size and sha256 above in the same commit.
