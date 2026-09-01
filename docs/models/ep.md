# Expected Points (EP)


The Expected Points (EP) model estimates the expected next-score value
for the team in possession at the **start of a play**, given game state.
It is the foundation of the NFL analytics stack: EP differences between
consecutive plays define **Expected Points Added (EPA)**. Every
play-by-play row carries an `ep` column plus the seven next-score class
probabilities. The model is a faithful re-implementation of the nflfastR
EP model (nflverse `fastrmodels`, Ben Baldwin).

This document is compiled: the calibration sections re-plot from the
committed LOSO report artifacts (`figures/*.parquet`, produced by the
training pipeline’s reporting stage over the full 1999–2025 corpus), and
the importance/SHAP and results sections score the committed booster
(`models/ep_model.ubj`) over the latest published `nfl_model_pbp` season
at render time.

## Model features

**18 features**, all known at the **start of the play** — no look-ahead.
Each row is one scrimmage play; the label is the *next scoring event* in
the same half (`next_score_class`).

| Feature | Type | What it encodes |
|----|----|----|
| `half_seconds_remaining` | numeric | Seconds left in the half — fewer expected possessions to score late. |
| `yardline_100` | numeric | Distance (1–99) to the opponent’s end zone — the strongest field-position signal. |
| `ydstogo` | numeric | Yards to go for a first down. |
| `down1` … `down4` | one-hot | Current down (4 columns). |
| `home` | binary | Possession team is home. |
| `dome` / `retractable` / `outdoors` | binary | Stadium-type one-hots (roof/exposure) — NFL EP carries a weather/venue proxy CFB does not. |
| `era0` … `era4` | one-hot | Rule era (cuts **2001 / 2005 / 2013 / 2017**) — captures scoring-environment drift across 27 seasons. |
| `posteam_timeouts_remaining` | numeric | Possession-team timeouts left. |
| `defteam_timeouts_remaining` | numeric | Defense timeouts left. |

## The model

**Algorithm.** XGBoost gradient-boosted trees,
`objective=multi:softprob` over `num_class=7`, `eval_metric=mlogloss`,
`eta=0.025`, `max_depth=5` — the `fastrmodels` EP recipe. The 7 class
probabilities are dotted with the nflfastR point map to produce a scalar
EP:

`{Touchdown:+7, Opp_Touchdown:−7, Field_Goal:+3, Opp_Field_Goal:−3, Safety:+2, Opp_Safety:−2, No_Score:0}`

(class order
`0=TD, 1=Opp_TD, 2=FG, 3=Opp_FG, 4=Safety, 5=Opp_Safety, 6=No_Score`).
Retrained on the **full 1999–2025 history (1,195,636 plays)** reshaped
from `nfl-raw` to nflfastR parity.

**Evaluation.** Two lenses — see [Parity](parity.md) for the
nflfastR-parity gate and the LOSO calibration below.

## Training data (LOSO report) and the render-time season

<div id="xdedmfqcop" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#xdedmfqcop table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#xdedmfqcop thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#xdedmfqcop p { margin: 0; padding: 0; }
 #xdedmfqcop .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #xdedmfqcop .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #xdedmfqcop .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #xdedmfqcop .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #xdedmfqcop .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #xdedmfqcop .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #xdedmfqcop .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #xdedmfqcop .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #xdedmfqcop .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #xdedmfqcop .gt_column_spanner_outer:first-child { padding-left: 0; }
 #xdedmfqcop .gt_column_spanner_outer:last-child { padding-right: 0; }
 #xdedmfqcop .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #xdedmfqcop .gt_spanner_row { border-bottom-style: hidden; }
 #xdedmfqcop .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #xdedmfqcop .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #xdedmfqcop .gt_from_md> :first-child { margin-top: 0; }
 #xdedmfqcop .gt_from_md> :last-child { margin-bottom: 0; }
 #xdedmfqcop .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #xdedmfqcop .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #xdedmfqcop .gt_indent_1 { text-indent: 5px; }
 #xdedmfqcop .gt_indent_2 { text-indent: calc(5px * 2); }
 #xdedmfqcop .gt_indent_3 { text-indent: calc(5px * 3); }
 #xdedmfqcop .gt_indent_4 { text-indent: calc(5px * 4); }
 #xdedmfqcop .gt_indent_5 { text-indent: calc(5px * 5); }
 #xdedmfqcop .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #xdedmfqcop .gt_row_group_first td { border-top-width: 2px; }
 #xdedmfqcop .gt_row_group_first th { border-top-width: 2px; }
 #xdedmfqcop .gt_striped { color: #333333; background-color: #F4F4F4; }
 #xdedmfqcop .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #xdedmfqcop .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #xdedmfqcop .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #xdedmfqcop .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #xdedmfqcop .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #xdedmfqcop .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #xdedmfqcop .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #xdedmfqcop .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #xdedmfqcop .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #xdedmfqcop .gt_left { text-align: left; }
 #xdedmfqcop .gt_center { text-align: center; }
 #xdedmfqcop .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #xdedmfqcop .gt_font_normal { font-weight: normal; }
 #xdedmfqcop .gt_font_bold { font-weight: bold; }
 #xdedmfqcop .gt_font_italic { font-style: italic; }
 #xdedmfqcop .gt_super { font-size: 65%; }
 #xdedmfqcop .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #xdedmfqcop .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #xdedmfqcop .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #xdedmfqcop .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #xdedmfqcop .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #xdedmfqcop .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| EP evaluation corpora |  |  |
|----|----|----|
| the LOSO metrics are frozen training-report artifacts; the render-time season is live |  |  |
| corpus | plays | per_class_weighted_cal_error |
| LOSO pool (training report, 1999–2025) | 1,195,636 | 0.0058 |
| render-time season (2025, nfl_model_pbp) | 46,631 | <na> |

&#10;</div>

## Calibration

A 7-class softprob model is checked **per next-score class** — each
class probability binned against whether that class was the realized
next score (the nflfastR / cfbscrapR signature). This is a
**probability-scale** reliability check, directly comparable to the WP
and CP numbers. On the **1999–2025** leave-one-season-out pool the
**per-class weighted calibration error is 0.0058** — on par with WP
(0.0026) and better than CP (0.0136). The high-variance modal class
(`No_Score`, 0.012) carries most of the error; the rare scoring classes
(safeties, 0.003) are tight.

<img src="ep_files/figure-commonmark/cell-4-output-1.png" width="420"
height="300"
alt="Per-class LOSO reliability — predicted class probability (bin) vs realized frequency, from the committed report artifact." />

> [!NOTE]
>
> ### Why not a single points-scale number
>
> Binning the scalar `ep` against realized next-score *value* reads
> ≈0.07 **points**, but that is dominated by the absolute level of the
> next-score label — nflfastR’s own `ep` sits the same ~0.1 points above
> the realized-next-score mean — so it is **not** comparable to the
> probability-scale figures above, nor to WP/CP. The per-class
> reliability and the parity (`ep` r 0.996) are the honest, comparable
> signals; the model is not miscalibrated.

<img src="ep_files/figure-commonmark/cell-5-output-1.png" width="420"
height="300"
alt="EP by yardline, recomputed at render time on the 2025 season — the nflfastR signature curve." />

The EP-by-yardline curve rises smoothly from own-goal-line to a sharp
red-zone climb — the shape that makes EPA a meaningful per-play
currency.

## Feature importance & SHAP

<div id="uzdvomapnh" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#uzdvomapnh table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#uzdvomapnh thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#uzdvomapnh p { margin: 0; padding: 0; }
 #uzdvomapnh .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #uzdvomapnh .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #uzdvomapnh .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #uzdvomapnh .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #uzdvomapnh .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #uzdvomapnh .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #uzdvomapnh .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #uzdvomapnh .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #uzdvomapnh .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #uzdvomapnh .gt_column_spanner_outer:first-child { padding-left: 0; }
 #uzdvomapnh .gt_column_spanner_outer:last-child { padding-right: 0; }
 #uzdvomapnh .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #uzdvomapnh .gt_spanner_row { border-bottom-style: hidden; }
 #uzdvomapnh .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #uzdvomapnh .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #uzdvomapnh .gt_from_md> :first-child { margin-top: 0; }
 #uzdvomapnh .gt_from_md> :last-child { margin-bottom: 0; }
 #uzdvomapnh .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #uzdvomapnh .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #uzdvomapnh .gt_indent_1 { text-indent: 5px; }
 #uzdvomapnh .gt_indent_2 { text-indent: calc(5px * 2); }
 #uzdvomapnh .gt_indent_3 { text-indent: calc(5px * 3); }
 #uzdvomapnh .gt_indent_4 { text-indent: calc(5px * 4); }
 #uzdvomapnh .gt_indent_5 { text-indent: calc(5px * 5); }
 #uzdvomapnh .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #uzdvomapnh .gt_row_group_first td { border-top-width: 2px; }
 #uzdvomapnh .gt_row_group_first th { border-top-width: 2px; }
 #uzdvomapnh .gt_striped { color: #333333; background-color: #F4F4F4; }
 #uzdvomapnh .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #uzdvomapnh .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #uzdvomapnh .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #uzdvomapnh .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #uzdvomapnh .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #uzdvomapnh .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #uzdvomapnh .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #uzdvomapnh .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #uzdvomapnh .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #uzdvomapnh .gt_left { text-align: left; }
 #uzdvomapnh .gt_center { text-align: center; }
 #uzdvomapnh .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #uzdvomapnh .gt_font_normal { font-weight: normal; }
 #uzdvomapnh .gt_font_bold { font-weight: bold; }
 #uzdvomapnh .gt_font_italic { font-style: italic; }
 #uzdvomapnh .gt_super { font-size: 65%; }
 #uzdvomapnh .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #uzdvomapnh .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #uzdvomapnh .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #uzdvomapnh .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #uzdvomapnh .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #uzdvomapnh .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Top 12 features by gain — committed EP booster |       |
|------------------------------------------------|-------|
| feature                                        | gain  |
| half_seconds_remaining                         | 197.1 |
| down4                                          | 109.5 |
| yardline_100                                   | 108.7 |
| down1                                          | 91.6  |
| down2                                          | 77.8  |
| down3                                          | 65.0  |
| ydstogo                                        | 61.8  |
| defteam_timeouts_remaining                     | 56.5  |
| posteam_timeouts_remaining                     | 40.5  |
| home                                           | 14.9  |
| era4                                           | 12.3  |
| era0                                           | 10.2  |

&#10;</div>

<img src="ep_files/figure-commonmark/cell-7-output-1.png" width="420"
height="300"
alt="TreeSHAP (margin space), mean |contribution| per feature aggregated across the 7 class margins; 4,000-play sample from the 2025 season." />

`yardline_100` dominates (field position is the backbone of EP),
followed by `half_seconds_remaining` and the down one-hots; the era and
stadium one-hots apply level shifts rather than driving the surface —
matching the nflfastR EP post. Because EP is a softprob dot-product,
exact SHAP exists per class margin, not for the scalar `ep`; the chart
aggregates \|contribution\| across the seven margins and is labeled
accordingly.

## Results — the surface in use

<div id="iufkploovh" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#iufkploovh table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#iufkploovh thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#iufkploovh p { margin: 0; padding: 0; }
 #iufkploovh .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #iufkploovh .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #iufkploovh .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #iufkploovh .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #iufkploovh .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #iufkploovh .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #iufkploovh .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #iufkploovh .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #iufkploovh .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #iufkploovh .gt_column_spanner_outer:first-child { padding-left: 0; }
 #iufkploovh .gt_column_spanner_outer:last-child { padding-right: 0; }
 #iufkploovh .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #iufkploovh .gt_spanner_row { border-bottom-style: hidden; }
 #iufkploovh .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #iufkploovh .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #iufkploovh .gt_from_md> :first-child { margin-top: 0; }
 #iufkploovh .gt_from_md> :last-child { margin-bottom: 0; }
 #iufkploovh .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #iufkploovh .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #iufkploovh .gt_indent_1 { text-indent: 5px; }
 #iufkploovh .gt_indent_2 { text-indent: calc(5px * 2); }
 #iufkploovh .gt_indent_3 { text-indent: calc(5px * 3); }
 #iufkploovh .gt_indent_4 { text-indent: calc(5px * 4); }
 #iufkploovh .gt_indent_5 { text-indent: calc(5px * 5); }
 #iufkploovh .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #iufkploovh .gt_row_group_first td { border-top-width: 2px; }
 #iufkploovh .gt_row_group_first th { border-top-width: 2px; }
 #iufkploovh .gt_striped { color: #333333; background-color: #F4F4F4; }
 #iufkploovh .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #iufkploovh .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #iufkploovh .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #iufkploovh .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #iufkploovh .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #iufkploovh .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #iufkploovh .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #iufkploovh .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #iufkploovh .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #iufkploovh .gt_left { text-align: left; }
 #iufkploovh .gt_center { text-align: center; }
 #iufkploovh .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #iufkploovh .gt_font_normal { font-weight: normal; }
 #iufkploovh .gt_font_bold { font-weight: bold; }
 #iufkploovh .gt_font_italic { font-style: italic; }
 #iufkploovh .gt_super { font-size: 65%; }
 #iufkploovh .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #iufkploovh .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #iufkploovh .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #iufkploovh .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #iufkploovh .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #iufkploovh .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Top 10 offenses by EPA/play — 2025 season |  |  |  |
|----|----|----|----|
| EPA is the first difference of this model's EP surface |  |  |  |
|  | Offense | Plays | EPA/play |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/la.png"
height="36" /> | LA | 1,261 | 0.144 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/buf.png"
height="36" /> | BUF | 1,203 | 0.125 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/gb.png"
height="36" /> | GB | 1,063 | 0.113 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/dal.png"
height="36" /> | DAL | 1,104 | 0.098 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/det.png"
height="36" /> | DET | 1,051 | 0.084 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/ne.png"
height="36" /> | NE | 1,268 | 0.077 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/ind.png"
height="36" /> | IND | 1,011 | 0.069 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/chi.png"
height="36" /> | CHI | 1,255 | 0.065 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/sf.png"
height="36" /> | SF | 1,180 | 0.054 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/sea.png"
height="36" /> | SEA | 1,184 | 0.038 |

&#10;</div>

## Limitations

EP is a **start-of-play** quantity; it does not know the result of the
current play (that is what EPA captures). Top-1 class accuracy is
inherently capped by irreducible next-score noise, not miscalibration —
the model is well-calibrated in aggregate even where individual outcomes
are unpredictable. The 7-class point map is fixed, and the model is
blind to personnel and in-play participants by design.

## Provenance

| field | value |
|----|----|
| `model_type` | ep |
| `objective` | multi:softprob (num_class=7) |
| `features` | 18 (see above) |
| `label` | next_score_class |
| `training_seasons` | 1999–2025 |
| `n_training_rows` | 1,195,636 |
| `hyperparameters` | eta=0.025, max_depth=5 |
| `lineage` | nflfastR EP model · nflverse `fastrmodels` (Ben Baldwin) |
| `parity` | `ep` r 0.996 · `epa` r 0.994 |
| `artifact` | `models/ep_model.ubj` (committed; also on `nfl_model_artifacts`) |
| `rebuild this doc` | `scripts/render_model_docs.sh` (Quarto → GFM; `uv sync --group docs`) |

## Avenues for improvement & open issues

- **Era interactions** — era dummies were evaluated and rejected on
  calibration; richer era x feature interactions (kickoff rules, OT
  format) remain unexplored.
- **Known issue:** kickoff/PAT rows depend on the feature-substitution
  convention (touchback yardline, down/ydstogo resets) — any rule change
  (e.g. dynamic kickoff) requires revisiting those constants before
  retrain.
