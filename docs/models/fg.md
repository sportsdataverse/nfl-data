# Field Goal (`fg_model`)


The field-goal model estimates the probability a placekick is **made**,
given the kick distance and roof/era context. It powers the field-goal
branch of the [nfl4th 4th-down decision](fourth_down.md): the EV of
attempting a field goal is this make probability times three points. It
is a Python **XGBoost** retrain of nfl4th’s FG model — which was
originally an **mgcv GAM spline** — validated against the converted GAM
grid.

This document is compiled: the make-probability curve is scored from the
bundled booster at render time and overlaid on the latest published
season’s **empirical** make rates, and the kicker leaderboard scores
every 2025 attempt through the model to compute field goals over
expected.

## Model features

**7 features** (`yardline_100`, `fg_roof`, era0..era4); one row per FG
attempt (`play_type_nfl=='FIELD_GOAL'`, 1999–2025). The era one-hot
replaces the old binary `fg_era` so the make-prob curve is era-aware
across all kicking eras. The binary label is `sp` (field goal made).

| Feature | Type | What it encodes |
|----|----|----|
| `yardline_100` | numeric | Snap field position; kick distance is `yardline_100 + 17`. The dominant signal (**monotone ↓**). |
| `fg_roof` | binary | Outdoors (`roof=='outdoors'`) vs indoor/retractable. |
| `era0..4` | one-hot | Kicking era — the make curve has shifted outward era over era. |

## The model

**Algorithm.** XGBoost, `objective=binary:logistic`, shallow trees with
a high `min_child_weight` (the make curve is smooth), **monotone
constraint `−1` on `yardline_100`** (make probability must fall with
distance). Replaces the original mgcv GAM spline.

**Evaluation.** Because the booster step-approximates a spline, parity
is scoped to the **operating domain** (yardline×roof×era cells with ≥1
real attempt): **corr 0.9802** there (gate ≥0.98), **freq-weighted corr
0.9880**. Full-grid corr is lower by construction (0.9690) — the booster
cannot reproduce the spline’s extrapolation into never-attempted cells;
**max abs FG% diff 0.34**. See [Parity](parity.md).

## The make curve, against reality

<img src="fg_files/figure-commonmark/cell-4-output-1.png" width="420"
height="300"
alt="Model make probability vs empirical make rate by kick distance, 2025 attempts (era4, mixed roofs)." />

<div id="odpadfxeax" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#odpadfxeax table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#odpadfxeax thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#odpadfxeax p { margin: 0; padding: 0; }
 #odpadfxeax .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #odpadfxeax .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #odpadfxeax .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #odpadfxeax .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #odpadfxeax .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #odpadfxeax .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #odpadfxeax .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #odpadfxeax .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #odpadfxeax .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #odpadfxeax .gt_column_spanner_outer:first-child { padding-left: 0; }
 #odpadfxeax .gt_column_spanner_outer:last-child { padding-right: 0; }
 #odpadfxeax .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #odpadfxeax .gt_spanner_row { border-bottom-style: hidden; }
 #odpadfxeax .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #odpadfxeax .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #odpadfxeax .gt_from_md> :first-child { margin-top: 0; }
 #odpadfxeax .gt_from_md> :last-child { margin-bottom: 0; }
 #odpadfxeax .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #odpadfxeax .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #odpadfxeax .gt_indent_1 { text-indent: 5px; }
 #odpadfxeax .gt_indent_2 { text-indent: calc(5px * 2); }
 #odpadfxeax .gt_indent_3 { text-indent: calc(5px * 3); }
 #odpadfxeax .gt_indent_4 { text-indent: calc(5px * 4); }
 #odpadfxeax .gt_indent_5 { text-indent: calc(5px * 5); }
 #odpadfxeax .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #odpadfxeax .gt_row_group_first td { border-top-width: 2px; }
 #odpadfxeax .gt_row_group_first th { border-top-width: 2px; }
 #odpadfxeax .gt_striped { color: #333333; background-color: #F4F4F4; }
 #odpadfxeax .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #odpadfxeax .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #odpadfxeax .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #odpadfxeax .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #odpadfxeax .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #odpadfxeax .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #odpadfxeax .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #odpadfxeax .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #odpadfxeax .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #odpadfxeax .gt_left { text-align: left; }
 #odpadfxeax .gt_center { text-align: center; }
 #odpadfxeax .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #odpadfxeax .gt_font_normal { font-weight: normal; }
 #odpadfxeax .gt_font_bold { font-weight: bold; }
 #odpadfxeax .gt_font_italic { font-style: italic; }
 #odpadfxeax .gt_super { font-size: 65%; }
 #odpadfxeax .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #odpadfxeax .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #odpadfxeax .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #odpadfxeax .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #odpadfxeax .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #odpadfxeax .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Render-time FG evaluation — 2025 attempts scored by the bundled booster |  |
|----|----|
| scored with era4 + roof features; monotone-in-distance by constraint |  |
| metric | value |
| 2025 attempts | 1,140.0000 |
| make rate | 0.8561 |
| Brier (model) | 0.1117 |
| baseline Brier (constant) | 0.1232 |

&#10;</div>

## Results — field goals over expected, 2025

<div id="ybkeswqvsh" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#ybkeswqvsh table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#ybkeswqvsh thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#ybkeswqvsh p { margin: 0; padding: 0; }
 #ybkeswqvsh .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #ybkeswqvsh .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #ybkeswqvsh .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #ybkeswqvsh .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #ybkeswqvsh .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #ybkeswqvsh .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #ybkeswqvsh .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #ybkeswqvsh .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #ybkeswqvsh .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #ybkeswqvsh .gt_column_spanner_outer:first-child { padding-left: 0; }
 #ybkeswqvsh .gt_column_spanner_outer:last-child { padding-right: 0; }
 #ybkeswqvsh .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #ybkeswqvsh .gt_spanner_row { border-bottom-style: hidden; }
 #ybkeswqvsh .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #ybkeswqvsh .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #ybkeswqvsh .gt_from_md> :first-child { margin-top: 0; }
 #ybkeswqvsh .gt_from_md> :last-child { margin-bottom: 0; }
 #ybkeswqvsh .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #ybkeswqvsh .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #ybkeswqvsh .gt_indent_1 { text-indent: 5px; }
 #ybkeswqvsh .gt_indent_2 { text-indent: calc(5px * 2); }
 #ybkeswqvsh .gt_indent_3 { text-indent: calc(5px * 3); }
 #ybkeswqvsh .gt_indent_4 { text-indent: calc(5px * 4); }
 #ybkeswqvsh .gt_indent_5 { text-indent: calc(5px * 5); }
 #ybkeswqvsh .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #ybkeswqvsh .gt_row_group_first td { border-top-width: 2px; }
 #ybkeswqvsh .gt_row_group_first th { border-top-width: 2px; }
 #ybkeswqvsh .gt_striped { color: #333333; background-color: #F4F4F4; }
 #ybkeswqvsh .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #ybkeswqvsh .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #ybkeswqvsh .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #ybkeswqvsh .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #ybkeswqvsh .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #ybkeswqvsh .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #ybkeswqvsh .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #ybkeswqvsh .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #ybkeswqvsh .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #ybkeswqvsh .gt_left { text-align: left; }
 #ybkeswqvsh .gt_center { text-align: center; }
 #ybkeswqvsh .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #ybkeswqvsh .gt_font_normal { font-weight: normal; }
 #ybkeswqvsh .gt_font_bold { font-weight: bold; }
 #ybkeswqvsh .gt_font_italic { font-style: italic; }
 #ybkeswqvsh .gt_super { font-size: 65%; }
 #ybkeswqvsh .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #ybkeswqvsh .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #ybkeswqvsh .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #ybkeswqvsh .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #ybkeswqvsh .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #ybkeswqvsh .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Field goals over expected — 2025 (min 15 attempts) |  |  |  |  |  |  |
|----|----|----|----|----|----|----|
| made minus the model-expected makes on the same attempts; kicker identity is deliberately NOT a model feature, so this residual is the kicker |  |  |  |  |  |  |
|  | Kicker | Team | Att | Made | xMade | FGOE |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/l4rrfcuczjau7q02h2iz"
height="40" /> | E.Pineiro | SF | 32 | 31.0 | 26.0 | 5.0 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/r1g0mqxqc23tmqmgdbwm"
height="40" /> | W.Reichard | MIN | 35 | 33.0 | 28.7 | 4.3 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/qcfiv2cc7ky37yq9iklp"
height="40" /> | N.Folk | NYJ | 29 | 28.0 | 23.9 | 4.1 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/nbrs7doetqydf2rzhjjl"
height="40" /> | K.Fairbairn | HOU | 52 | 48.0 | 44.2 | 3.8 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/cpvujaqwscupzvbbx7oe"
height="40" /> | E.McPherson | CIN | 28 | 25.0 | 21.7 | 3.3 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/ynyyootbeabm5sx4ejgt"
height="40" /> | B.Aubrey | DAL | 42 | 36.0 | 33.0 | 3.0 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/gzvyb1u3dueikfy3otlq"
height="40" /> | R.Patterson | MIA | 29 | 27.0 | 24.2 | 2.8 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/vd4nd1hoax82j7fi2bx0"
height="40" /> | C.Dicker | LAC | 42 | 39.0 | 36.5 | 2.5 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/pfdod5cds77uznkotipk"
height="40" /> | C.Little | JAX | 36 | 31.0 | 28.5 | 2.5 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/rnw5znsm0hrekqvztiog"
height="40" /> | J.Myers | SEA | 56 | 49.0 | 46.7 | 2.3 |

&#10;</div>

## Limitations

Distance is everything plus a coarse roof/era shift — **no kicker
identity, wind, or weather**. The step-function booster does not
extrapolate the smooth GAM tail past the attempted domain, so very long
/ never-attempted cells should be read with caution (this is the
freq-weighted vs full-grid corr gap). The render-time scoring above pins
era4 for current-season attempts, which is exact for 2018+.

## Provenance

| field | value |
|----|----|
| `model_type` | fg |
| `objective` | binary:logistic (monotone yardline ↓) |
| `features` | yardline_100, fg_roof, era0..4 |
| `label` | sp (FG made) |
| `training_seasons` | 1999–2025 (23,919 attempts) |
| `lineage` | nfl4th field-goal model (was mgcv GAM) |
| `parity` | attempted-cells corr 0.971 · freq-weighted 0.986 (informational, era-aware full-history) |
| `distribution` | bundled in sportsdataverse |
| `rebuild this doc` | `scripts/render_model_docs.sh` (Quarto → GFM; `uv sync --group docs`) |

## Avenues for improvement & open issues

- **Weather/altitude/kicker aging** — none are features; kicker identity
  is the FGOE residual above, which is exactly the leaderboard’s point.
- **Known issue:** parity vs the R oracle sits at 0.971 — below the
  other boosters, documented, and worth a targeted divergence audit.
