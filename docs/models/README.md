# NFL model cards (Quarto site)

Per-model methodology cards for the SportsDataverse / nflverse NFL models, in the
cfbfastR-suite house style. Lineage: **nflfastR** + **nflverse `fastrmodels`**
(Ben Baldwin) for the play-level models, and **nfl4th** for the fourth-down
decision suite.

## Pages

| Page | Model / metric |
|---|---|
| `index.qmd` | Landing page + model tables + regeneration |
| `parity.md` | nflfastR-parity validation (the headline gate) |
| `ep.md` | Expected Points (7-class softprob) |
| `wp_spread.md` / `wp_naive.md` | Win Probability — spread (`vegas_wp`) / naive (`wp`) |
| `cpoe.md` | Completion Probability / CPOE |
| `xyac.md` | Expected Yards After Catch (76-class) |
| `fourth_down.md` | Fourth-down go-for-it yards (76-class) |
| `fg.md` / `two_pt.md` / `punt.md` | Field goal / two-point / punt distribution |
| `nfl4th_wp.md` | Home-perspective decision WP |
| `xpass.md` | Expected pass (`pass_oe`) |
| `qbr.md` / `dakota.md` | QBR reconstruction / dakota efficiency metric |

## Build

```sh
cd docs/models && quarto render   # -> _site/
```

The calibration figures under `figures/` are produced by the NFL model-report
tool (leave-one-season-out → `ep/wp/cp_calibration.png`,
`ep_by_yardline.png`, `cp_by_air_yards.png`, `metrics.json`). The model cards
reference those filenames. Commit the source (`.qmd`/`.md`/`.css`) and the
generated `figures/*.png` so the published cards carry their calibration plots;
`_site/` is a build artifact.
