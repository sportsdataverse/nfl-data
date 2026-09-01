# Fourth-Down Yards (`fd_model`)


The fourth-down yards model predicts the **distribution of yards
gained** on a go-for-it (or third-down) attempt — the core of the
**nfl4th** decision surface. From the 76-class gain distribution we
derive P(first down) for any distance-to-go, then combine it with the
EP/WP surfaces to compute the **go / punt / field-goal / two-point**
expected-value comparison. It is a faithful Python retrain of nfl4th’s
go-for-it model, validated against the converted nflverse artifact.

This document is compiled: the conversion-probability curve is derived
from the released booster at render time (summing class probabilities
over the distance-to-go), and compared with the latest published
season’s **empirical** 4th-down conversion rates.

## Model features

**14 features**; one row per 3rd/4th-down scrimmage play (1999–2025,
`qb_kneel==0`, `week<=17`). The label is `yards_gained` clamped to
**\[−10, 65\]** and shifted into **76 ordinal classes**
(`label = yards_gained + 10`).

| Feature | Type | What it encodes |
|----|----|----|
| `down` | numeric | Current down (3 or 4). |
| `ydstogo` | numeric | Yards to go — the conversion threshold. |
| `yardline_100` | numeric | Field position (compresses the gain distribution near the goal line). |
| `era0`..`era4` | one-hot | Rule-era one-hot (cuts 2001/2005/2013/2017) — era-aware across 1999–2025. |
| `outdoors` / `retractable` / `dome` | binary | Stadium-type one-hots. |
| `posteam_spread` | numeric | Possession-team spread (game-script context). |
| `total_line` | numeric | Game total (pace / offensive-environment proxy). |
| `posteam_total` | numeric | Possession-team implied total. |

## The model

**Algorithm.** XGBoost, `objective=multi:softprob` over **76 classes**,
**1,124 rounds**, `eta=0.01`, `max_depth=2`, `gamma=2`, `subsample=0.8`,
`colsample_bytree=0.8`, `min_child_weight=0.8` — verbatim from the
nfl4th R recipe. P(first down) for any distance-to-go is recovered by
summing class probabilities for gains ≥ the distance.

**Evaluation.** Parity against the converted nflverse artifact:
**mean-gain correlation 0.9856** (informational — era-aware full-history
retrain vs the nfl4th 2014–19 oracle) — see [Parity](parity.md).

## P(convert) vs reality, render time

<img src="fourth_down_files/figure-commonmark/cell-4-output-1.png"
width="420" height="300"
alt="Model P(convert) at midfield (neutral spread, era4) vs realized 2025 4th-down conversion rates — selection effects push the empirical curve above the unconditional model." />

Teams *choose* which 4th downs to attempt, so the realized curve
reflects selection (coaches go when they like the matchup) while the
model curve is the unconditional estimate at a fixed neutral state — the
gap between them is selection, not error. That distinction is the whole
reason the decision layer values options with a model rather than
empirical rates.

## The decision surface in use — 2025

The published pbp carries the nfl4th-style decision columns
(`go_wp_diff`, `fg_wp_diff`, `punt_wp_diff` — each option’s WP against
the best alternative), so the decision layer’s output is directly
observable:

<div id="cxgecxytaj" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#cxgecxytaj table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#cxgecxytaj thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#cxgecxytaj p { margin: 0; padding: 0; }
 #cxgecxytaj .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #cxgecxytaj .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #cxgecxytaj .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #cxgecxytaj .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #cxgecxytaj .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #cxgecxytaj .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #cxgecxytaj .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #cxgecxytaj .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #cxgecxytaj .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #cxgecxytaj .gt_column_spanner_outer:first-child { padding-left: 0; }
 #cxgecxytaj .gt_column_spanner_outer:last-child { padding-right: 0; }
 #cxgecxytaj .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #cxgecxytaj .gt_spanner_row { border-bottom-style: hidden; }
 #cxgecxytaj .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #cxgecxytaj .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #cxgecxytaj .gt_from_md> :first-child { margin-top: 0; }
 #cxgecxytaj .gt_from_md> :last-child { margin-bottom: 0; }
 #cxgecxytaj .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #cxgecxytaj .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #cxgecxytaj .gt_indent_1 { text-indent: 5px; }
 #cxgecxytaj .gt_indent_2 { text-indent: calc(5px * 2); }
 #cxgecxytaj .gt_indent_3 { text-indent: calc(5px * 3); }
 #cxgecxytaj .gt_indent_4 { text-indent: calc(5px * 4); }
 #cxgecxytaj .gt_indent_5 { text-indent: calc(5px * 5); }
 #cxgecxytaj .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #cxgecxytaj .gt_row_group_first td { border-top-width: 2px; }
 #cxgecxytaj .gt_row_group_first th { border-top-width: 2px; }
 #cxgecxytaj .gt_striped { color: #333333; background-color: #F4F4F4; }
 #cxgecxytaj .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #cxgecxytaj .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #cxgecxytaj .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #cxgecxytaj .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #cxgecxytaj .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #cxgecxytaj .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #cxgecxytaj .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #cxgecxytaj .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #cxgecxytaj .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #cxgecxytaj .gt_left { text-align: left; }
 #cxgecxytaj .gt_center { text-align: center; }
 #cxgecxytaj .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #cxgecxytaj .gt_font_normal { font-weight: normal; }
 #cxgecxytaj .gt_font_bold { font-weight: bold; }
 #cxgecxytaj .gt_font_italic { font-style: italic; }
 #cxgecxytaj .gt_super { font-size: 65%; }
 #cxgecxytaj .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #cxgecxytaj .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #cxgecxytaj .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #cxgecxytaj .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #cxgecxytaj .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #cxgecxytaj .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Decision layer vs coaches — 2025 season |  |
|----|----|
| go_wp_diff \> 0 means going for it maximizes WP among the four options |  |
| check | value |
| 4th downs with decision columns | 4,290.000 |
| model says GO (go_wp_diff \> 0) | 0.000 |
| teams actually went | 932.000 |
| coach–model agreement rate | 0.777 |

&#10;</div>

## Decision surface

`fd_model` is one input to nfl4th’s 4th-down EV comparison; the others
are [`fg_model`](fg.md), [`two_pt_model`](two_pt.md), the [punt
distribution](punt.md), and the [nfl4th home-WP](nfl4th_wp.md). Each
option’s EV is computed by mapping its outcome distribution through the
WP surface and picking the highest-WP action.

## Limitations

The label is recorded `yards_gained`, which can disagree with the
official result on penalty/lateral plays — label noise at the tails. The
gain window is clipped to \[−10, 65\]. It predicts a *yardage
distribution*, not the binary decision; the decision EV is computed
downstream.

## Provenance

| field | value |
|----|----|
| `model_type` | fd (fourth-down yards) |
| `objective` | multi:softprob (num_class=76) |
| `features` | 14 (era0..4 + see above) |
| `label` | yards_gained + 10 (clamped −10..65) |
| `training_seasons` | 1999–2025 (182,138 plays) |
| `hyperparameters` | eta=0.01, max_depth=2, nrounds=1124 |
| `lineage` | nfl4th go-for-it model |
| `parity` | mean-gain corr 0.986 (informational; full-history vs nfl4th 2014–19) |
| `distribution` | `nfl_4th_down_models` release (download-on-demand; 76-class model) |
| `rebuild this doc` | `scripts/render_model_docs.sh` (Quarto → GFM; `uv sync --group docs`) |

## Avenues for improvement & open issues

- **Coach-level tendencies** — decision calibration is league-wide; a
  coach-indexed layer would localize it.
- **Known issue:** the 76-class yards head shares the xYAC machinery —
  the multiclass pred_contribs 3-D gotcha applies to any explainability
  pass.
