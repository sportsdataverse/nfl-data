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

<div id="fjybtptdup" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#fjybtptdup table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#fjybtptdup thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#fjybtptdup p { margin: 0; padding: 0; }
 #fjybtptdup .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #fjybtptdup .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #fjybtptdup .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #fjybtptdup .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #fjybtptdup .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #fjybtptdup .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #fjybtptdup .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #fjybtptdup .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #fjybtptdup .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #fjybtptdup .gt_column_spanner_outer:first-child { padding-left: 0; }
 #fjybtptdup .gt_column_spanner_outer:last-child { padding-right: 0; }
 #fjybtptdup .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #fjybtptdup .gt_spanner_row { border-bottom-style: hidden; }
 #fjybtptdup .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #fjybtptdup .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #fjybtptdup .gt_from_md> :first-child { margin-top: 0; }
 #fjybtptdup .gt_from_md> :last-child { margin-bottom: 0; }
 #fjybtptdup .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #fjybtptdup .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #fjybtptdup .gt_indent_1 { text-indent: 5px; }
 #fjybtptdup .gt_indent_2 { text-indent: calc(5px * 2); }
 #fjybtptdup .gt_indent_3 { text-indent: calc(5px * 3); }
 #fjybtptdup .gt_indent_4 { text-indent: calc(5px * 4); }
 #fjybtptdup .gt_indent_5 { text-indent: calc(5px * 5); }
 #fjybtptdup .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #fjybtptdup .gt_row_group_first td { border-top-width: 2px; }
 #fjybtptdup .gt_row_group_first th { border-top-width: 2px; }
 #fjybtptdup .gt_striped { color: #333333; background-color: #F4F4F4; }
 #fjybtptdup .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #fjybtptdup .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #fjybtptdup .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #fjybtptdup .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #fjybtptdup .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #fjybtptdup .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #fjybtptdup .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #fjybtptdup .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #fjybtptdup .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #fjybtptdup .gt_left { text-align: left; }
 #fjybtptdup .gt_center { text-align: center; }
 #fjybtptdup .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #fjybtptdup .gt_font_normal { font-weight: normal; }
 #fjybtptdup .gt_font_bold { font-weight: bold; }
 #fjybtptdup .gt_font_italic { font-style: italic; }
 #fjybtptdup .gt_super { font-size: 65%; }
 #fjybtptdup .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #fjybtptdup .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #fjybtptdup .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #fjybtptdup .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #fjybtptdup .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #fjybtptdup .gt_asterisk { font-size: 100%; vertical-align: 0; }
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

<div id="rqlqqwucwq" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#rqlqqwucwq table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#rqlqqwucwq thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#rqlqqwucwq p { margin: 0; padding: 0; }
 #rqlqqwucwq .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #rqlqqwucwq .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #rqlqqwucwq .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #rqlqqwucwq .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #rqlqqwucwq .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #rqlqqwucwq .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #rqlqqwucwq .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #rqlqqwucwq .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #rqlqqwucwq .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #rqlqqwucwq .gt_column_spanner_outer:first-child { padding-left: 0; }
 #rqlqqwucwq .gt_column_spanner_outer:last-child { padding-right: 0; }
 #rqlqqwucwq .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #rqlqqwucwq .gt_spanner_row { border-bottom-style: hidden; }
 #rqlqqwucwq .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #rqlqqwucwq .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #rqlqqwucwq .gt_from_md> :first-child { margin-top: 0; }
 #rqlqqwucwq .gt_from_md> :last-child { margin-bottom: 0; }
 #rqlqqwucwq .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #rqlqqwucwq .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #rqlqqwucwq .gt_indent_1 { text-indent: 5px; }
 #rqlqqwucwq .gt_indent_2 { text-indent: calc(5px * 2); }
 #rqlqqwucwq .gt_indent_3 { text-indent: calc(5px * 3); }
 #rqlqqwucwq .gt_indent_4 { text-indent: calc(5px * 4); }
 #rqlqqwucwq .gt_indent_5 { text-indent: calc(5px * 5); }
 #rqlqqwucwq .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #rqlqqwucwq .gt_row_group_first td { border-top-width: 2px; }
 #rqlqqwucwq .gt_row_group_first th { border-top-width: 2px; }
 #rqlqqwucwq .gt_striped { color: #333333; background-color: #F4F4F4; }
 #rqlqqwucwq .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #rqlqqwucwq .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #rqlqqwucwq .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #rqlqqwucwq .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #rqlqqwucwq .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #rqlqqwucwq .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #rqlqqwucwq .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #rqlqqwucwq .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #rqlqqwucwq .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #rqlqqwucwq .gt_left { text-align: left; }
 #rqlqqwucwq .gt_center { text-align: center; }
 #rqlqqwucwq .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #rqlqqwucwq .gt_font_normal { font-weight: normal; }
 #rqlqqwucwq .gt_font_bold { font-weight: bold; }
 #rqlqqwucwq .gt_font_italic { font-style: italic; }
 #rqlqqwucwq .gt_super { font-size: 65%; }
 #rqlqqwucwq .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #rqlqqwucwq .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #rqlqqwucwq .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #rqlqqwucwq .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #rqlqqwucwq .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #rqlqqwucwq .gt_asterisk { font-size: 100%; vertical-align: 0; }
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

## Where the 0.97 parity actually comes from

The FG model’s parity against the R oracle (attempted-cells corr ~0.97)
is the lowest of the boosters, so this section localizes it rather than
leaving it as a headline number. The oracle is the nfl4th `mgcv` GAM,
scored over its own grid and committed at
`models/oracles/fg_model_grid_nfl4th.csv` (provenance in that
directory’s README); the booster is scored over the same grid here.

<div id="rookglbhvw" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#rookglbhvw table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#rookglbhvw thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#rookglbhvw p { margin: 0; padding: 0; }
 #rookglbhvw .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #rookglbhvw .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #rookglbhvw .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #rookglbhvw .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #rookglbhvw .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #rookglbhvw .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #rookglbhvw .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #rookglbhvw .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #rookglbhvw .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #rookglbhvw .gt_column_spanner_outer:first-child { padding-left: 0; }
 #rookglbhvw .gt_column_spanner_outer:last-child { padding-right: 0; }
 #rookglbhvw .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #rookglbhvw .gt_spanner_row { border-bottom-style: hidden; }
 #rookglbhvw .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #rookglbhvw .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #rookglbhvw .gt_from_md> :first-child { margin-top: 0; }
 #rookglbhvw .gt_from_md> :last-child { margin-bottom: 0; }
 #rookglbhvw .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #rookglbhvw .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #rookglbhvw .gt_indent_1 { text-indent: 5px; }
 #rookglbhvw .gt_indent_2 { text-indent: calc(5px * 2); }
 #rookglbhvw .gt_indent_3 { text-indent: calc(5px * 3); }
 #rookglbhvw .gt_indent_4 { text-indent: calc(5px * 4); }
 #rookglbhvw .gt_indent_5 { text-indent: calc(5px * 5); }
 #rookglbhvw .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #rookglbhvw .gt_row_group_first td { border-top-width: 2px; }
 #rookglbhvw .gt_row_group_first th { border-top-width: 2px; }
 #rookglbhvw .gt_striped { color: #333333; background-color: #F4F4F4; }
 #rookglbhvw .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #rookglbhvw .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #rookglbhvw .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #rookglbhvw .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #rookglbhvw .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #rookglbhvw .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #rookglbhvw .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #rookglbhvw .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #rookglbhvw .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #rookglbhvw .gt_left { text-align: left; }
 #rookglbhvw .gt_center { text-align: center; }
 #rookglbhvw .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #rookglbhvw .gt_font_normal { font-weight: normal; }
 #rookglbhvw .gt_font_bold { font-weight: bold; }
 #rookglbhvw .gt_font_italic { font-style: italic; }
 #rookglbhvw .gt_super { font-size: 65%; }
 #rookglbhvw .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #rookglbhvw .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #rookglbhvw .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #rookglbhvw .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #rookglbhvw .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #rookglbhvw .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| FG parity vs the nfl4th GAM, by kick distance |  |  |  |  |  |
|----|----|----|----|----|----|
| attempted cells only; the disagreement is not spread across the range |  |  |  |  |  |
| Distance | Cells | Attempts | corr vs GAM | mean \|diff\| | max \|diff\| |
| under 30 | 48 | 3353 | 0.9610 | 0.0046 | 0.0113 |
| 30-39 | 40 | 3681 | 0.9503 | 0.0090 | 0.0282 |
| 40-49 | 40 | 3785 | 0.9541 | 0.0122 | 0.0407 |
| 50-59 | 40 | 1883 | 0.8637 | 0.0473 | 0.2947 |
| 60+ | 24 | 86 | 0.6793 | 0.1725 | 0.3466 |

&#10;</div>

**The residual is the long-distance tail, and nothing else.** Inside 50
yards — where 10,819 of the 12,788 attempted-cell attempts live — the
two models agree to a mean absolute make-probability difference of
0.005–0.012. From 50 yards the agreement degrades (0.047), and past 60
it collapses (0.173 mean, 0.347 max) on **86 attempts across 27
seasons**. That is the whole story of the headline number: the cells
that carry the disagreement are the cells almost nobody kicks from,
which is also why the frequency-weighted correlation (0.988) is so much
higher than the unweighted one.

The mechanism is the one the model card already names, now measured: the
GAM is a smooth spline that keeps extrapolating a graceful decline past
the attempted domain, while the booster is a monotone step function with
a `min_child_weight` floor, so it flattens where it has no data. Neither
is “right” out there — the GAM’s long tail is an extrapolation too, not
evidence.

Two candidate explanations that the data rules **out**:

<div id="lxklzknezy" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#lxklzknezy table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#lxklzknezy thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#lxklzknezy p { margin: 0; padding: 0; }
 #lxklzknezy .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #lxklzknezy .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #lxklzknezy .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #lxklzknezy .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #lxklzknezy .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #lxklzknezy .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #lxklzknezy .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #lxklzknezy .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #lxklzknezy .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #lxklzknezy .gt_column_spanner_outer:first-child { padding-left: 0; }
 #lxklzknezy .gt_column_spanner_outer:last-child { padding-right: 0; }
 #lxklzknezy .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #lxklzknezy .gt_spanner_row { border-bottom-style: hidden; }
 #lxklzknezy .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #lxklzknezy .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #lxklzknezy .gt_from_md> :first-child { margin-top: 0; }
 #lxklzknezy .gt_from_md> :last-child { margin-bottom: 0; }
 #lxklzknezy .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #lxklzknezy .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #lxklzknezy .gt_indent_1 { text-indent: 5px; }
 #lxklzknezy .gt_indent_2 { text-indent: calc(5px * 2); }
 #lxklzknezy .gt_indent_3 { text-indent: calc(5px * 3); }
 #lxklzknezy .gt_indent_4 { text-indent: calc(5px * 4); }
 #lxklzknezy .gt_indent_5 { text-indent: calc(5px * 5); }
 #lxklzknezy .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #lxklzknezy .gt_row_group_first td { border-top-width: 2px; }
 #lxklzknezy .gt_row_group_first th { border-top-width: 2px; }
 #lxklzknezy .gt_striped { color: #333333; background-color: #F4F4F4; }
 #lxklzknezy .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #lxklzknezy .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #lxklzknezy .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #lxklzknezy .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #lxklzknezy .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #lxklzknezy .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #lxklzknezy .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #lxklzknezy .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #lxklzknezy .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #lxklzknezy .gt_left { text-align: left; }
 #lxklzknezy .gt_center { text-align: center; }
 #lxklzknezy .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #lxklzknezy .gt_font_normal { font-weight: normal; }
 #lxklzknezy .gt_font_bold { font-weight: bold; }
 #lxklzknezy .gt_font_italic { font-style: italic; }
 #lxklzknezy .gt_super { font-size: 65%; }
 #lxklzknezy .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #lxklzknezy .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #lxklzknezy .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #lxklzknezy .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #lxklzknezy .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #lxklzknezy .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| The same parity, sliced by era mapping and by roof |  |  |  |  |
|----|----|----|----|----|
| neither slice separates -- the era-cell mapping is not the cause |  |  |  |  |
| Slice | Cells | Attempts | corr vs GAM | mean \|diff\| |
| era3 (2014-17, grid fg_era=0) | 92 | 4171 | 0.9724 | 0.0447 |
| era4 (2018+, grid fg_era=1) | 100 | 8617 | 0.9731 | 0.0299 |
| indoor / retractable | 94 | 3903 | 0.9635 | 0.0438 |
| outdoors | 98 | 8885 | 0.9840 | 0.0305 |

&#10;</div>

The era-cell mapping (the grid’s two-level `fg_era` is projected onto
era3/era4) is a natural suspect and it is not the cause — both era
slices land at the same correlation. Roof is a weak effect in the same
direction as sample size.

**Against reality, rather than against the GAM, the booster is well
calibrated** — which is the reading that matters for a model in
production:

<div id="kkciouswdh" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#kkciouswdh table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#kkciouswdh thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#kkciouswdh p { margin: 0; padding: 0; }
 #kkciouswdh .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #kkciouswdh .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #kkciouswdh .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #kkciouswdh .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #kkciouswdh .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #kkciouswdh .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #kkciouswdh .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #kkciouswdh .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #kkciouswdh .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #kkciouswdh .gt_column_spanner_outer:first-child { padding-left: 0; }
 #kkciouswdh .gt_column_spanner_outer:last-child { padding-right: 0; }
 #kkciouswdh .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #kkciouswdh .gt_spanner_row { border-bottom-style: hidden; }
 #kkciouswdh .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #kkciouswdh .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #kkciouswdh .gt_from_md> :first-child { margin-top: 0; }
 #kkciouswdh .gt_from_md> :last-child { margin-bottom: 0; }
 #kkciouswdh .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #kkciouswdh .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #kkciouswdh .gt_indent_1 { text-indent: 5px; }
 #kkciouswdh .gt_indent_2 { text-indent: calc(5px * 2); }
 #kkciouswdh .gt_indent_3 { text-indent: calc(5px * 3); }
 #kkciouswdh .gt_indent_4 { text-indent: calc(5px * 4); }
 #kkciouswdh .gt_indent_5 { text-indent: calc(5px * 5); }
 #kkciouswdh .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #kkciouswdh .gt_row_group_first td { border-top-width: 2px; }
 #kkciouswdh .gt_row_group_first th { border-top-width: 2px; }
 #kkciouswdh .gt_striped { color: #333333; background-color: #F4F4F4; }
 #kkciouswdh .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #kkciouswdh .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #kkciouswdh .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #kkciouswdh .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #kkciouswdh .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #kkciouswdh .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #kkciouswdh .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #kkciouswdh .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #kkciouswdh .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #kkciouswdh .gt_left { text-align: left; }
 #kkciouswdh .gt_center { text-align: center; }
 #kkciouswdh .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #kkciouswdh .gt_font_normal { font-weight: normal; }
 #kkciouswdh .gt_font_bold { font-weight: bold; }
 #kkciouswdh .gt_font_italic { font-style: italic; }
 #kkciouswdh .gt_super { font-size: 65%; }
 #kkciouswdh .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #kkciouswdh .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #kkciouswdh .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #kkciouswdh .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #kkciouswdh .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #kkciouswdh .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Model vs realized make rate by playing surface, 1999–2025 |  |  |  |  |
|----|----|----|----|----|
| surface is NOT a model feature; a large bias here would be a real gap |  |  |  |  |
| Surface | Attempts | Empirical | Model | Bias |
| grass | 13506 | 0.8250 | 0.8267 | 0.0017 |
| fieldturf | 6628 | 0.8435 | 0.8430 | −0.0006 |
| sportturf | 1325 | 0.8483 | 0.8455 | −0.0028 |
| astroturf | 1114 | 0.8214 | 0.8293 | 0.0080 |
| matrixturf | 869 | 0.8826 | 0.8581 | −0.0245 |
| astroplay | 426 | 0.8169 | 0.8284 | 0.0115 |
| a_turf | 390 | 0.8436 | 0.8508 | 0.0072 |
| grass | 337 | 0.8487 | 0.8428 | −0.0059 |
| dessograss | 201 | 0.8159 | 0.8339 | 0.0180 |

&#10;</div>

Every surface with a usable sample sits within 0.025 of its realized
make rate, and most within 0.01. Per-season bias behaves the same way
(mostly under 0.02). **So the honest verdict on the 0.97: it is a
disagreement between two functional forms in a region neither has data
for, not a defect in the shipped model.** It should not be “fixed” by
chasing the GAM into the extrapolated tail.

## Weather and altitude: measured, not modelled

The card lists weather as an absent feature. Here is what it is worth,
as a residual analysis on outdoor attempts (the schedule carries `temp`
and `wind`):

<div id="koghhxxtgc" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#koghhxxtgc table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#koghhxxtgc thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#koghhxxtgc p { margin: 0; padding: 0; }
 #koghhxxtgc .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #koghhxxtgc .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #koghhxxtgc .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #koghhxxtgc .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #koghhxxtgc .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #koghhxxtgc .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #koghhxxtgc .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #koghhxxtgc .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #koghhxxtgc .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #koghhxxtgc .gt_column_spanner_outer:first-child { padding-left: 0; }
 #koghhxxtgc .gt_column_spanner_outer:last-child { padding-right: 0; }
 #koghhxxtgc .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #koghhxxtgc .gt_spanner_row { border-bottom-style: hidden; }
 #koghhxxtgc .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #koghhxxtgc .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #koghhxxtgc .gt_from_md> :first-child { margin-top: 0; }
 #koghhxxtgc .gt_from_md> :last-child { margin-bottom: 0; }
 #koghhxxtgc .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #koghhxxtgc .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #koghhxxtgc .gt_indent_1 { text-indent: 5px; }
 #koghhxxtgc .gt_indent_2 { text-indent: calc(5px * 2); }
 #koghhxxtgc .gt_indent_3 { text-indent: calc(5px * 3); }
 #koghhxxtgc .gt_indent_4 { text-indent: calc(5px * 4); }
 #koghhxxtgc .gt_indent_5 { text-indent: calc(5px * 5); }
 #koghhxxtgc .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #koghhxxtgc .gt_row_group_first td { border-top-width: 2px; }
 #koghhxxtgc .gt_row_group_first th { border-top-width: 2px; }
 #koghhxxtgc .gt_striped { color: #333333; background-color: #F4F4F4; }
 #koghhxxtgc .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #koghhxxtgc .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #koghhxxtgc .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #koghhxxtgc .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #koghhxxtgc .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #koghhxxtgc .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #koghhxxtgc .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #koghhxxtgc .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #koghhxxtgc .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #koghhxxtgc .gt_left { text-align: left; }
 #koghhxxtgc .gt_center { text-align: center; }
 #koghhxxtgc .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #koghhxxtgc .gt_font_normal { font-weight: normal; }
 #koghhxxtgc .gt_font_bold { font-weight: bold; }
 #koghhxxtgc .gt_font_italic { font-style: italic; }
 #koghhxxtgc .gt_super { font-size: 65%; }
 #koghhxxtgc .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #koghhxxtgc .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #koghhxxtgc .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #koghhxxtgc .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #koghhxxtgc .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #koghhxxtgc .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| FG residual by wind and temperature — 17,445 outdoor attempts |  |  |  |  |  |
|----|----|----|----|----|----|
| residual = made - model; a monotone gradient is unmodelled signal |  |  |  |  |  |
| Variable | Bucket | Attempts | Empirical | Model | Mean residual |
| wind (mph) | \[-inf, 5) | 3663 | 0.8515 | 0.8266 | 0.0249 |
| wind (mph) | \[5, 10) | 7615 | 0.8263 | 0.8252 | 0.0011 |
| wind (mph) | \[10, 15) | 4001 | 0.8173 | 0.8276 | −0.0103 |
| wind (mph) | \[15, 20) | 1586 | 0.8083 | 0.8326 | −0.0243 |
| wind (mph) | \[20, inf) | 580 | 0.8155 | 0.8462 | −0.0307 |
| temp (F) | \[-inf, 32) | 1071 | 0.8058 | 0.8473 | −0.0415 |
| temp (F) | \[32, 50) | 4169 | 0.8249 | 0.8385 | −0.0136 |
| temp (F) | \[50, 70) | 7308 | 0.8307 | 0.8245 | 0.0063 |
| temp (F) | \[70, inf) | 4897 | 0.8297 | 0.8180 | 0.0117 |

&#10;</div>

Both gradients are monotone and material: kicks in under 5 mph beat the
model by **+2.5 points of make probability** and kicks in 20+ mph fall
short by **−3.1**, a 5.6-point spread the model currently attributes to
nothing. Temperature runs the same way (**−4.2** below freezing to
**+1.2** above 70°F), though wind and cold co-occur, so these are not
independent effects — a joint fit would split less signal between them
than the two tables suggest separately.

<div id="pikziyosip" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#pikziyosip table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#pikziyosip thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#pikziyosip p { margin: 0; padding: 0; }
 #pikziyosip .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #pikziyosip .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #pikziyosip .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #pikziyosip .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #pikziyosip .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #pikziyosip .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #pikziyosip .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #pikziyosip .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #pikziyosip .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #pikziyosip .gt_column_spanner_outer:first-child { padding-left: 0; }
 #pikziyosip .gt_column_spanner_outer:last-child { padding-right: 0; }
 #pikziyosip .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #pikziyosip .gt_spanner_row { border-bottom-style: hidden; }
 #pikziyosip .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #pikziyosip .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #pikziyosip .gt_from_md> :first-child { margin-top: 0; }
 #pikziyosip .gt_from_md> :last-child { margin-bottom: 0; }
 #pikziyosip .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #pikziyosip .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #pikziyosip .gt_indent_1 { text-indent: 5px; }
 #pikziyosip .gt_indent_2 { text-indent: calc(5px * 2); }
 #pikziyosip .gt_indent_3 { text-indent: calc(5px * 3); }
 #pikziyosip .gt_indent_4 { text-indent: calc(5px * 4); }
 #pikziyosip .gt_indent_5 { text-indent: calc(5px * 5); }
 #pikziyosip .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #pikziyosip .gt_row_group_first td { border-top-width: 2px; }
 #pikziyosip .gt_row_group_first th { border-top-width: 2px; }
 #pikziyosip .gt_striped { color: #333333; background-color: #F4F4F4; }
 #pikziyosip .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #pikziyosip .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #pikziyosip .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #pikziyosip .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #pikziyosip .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #pikziyosip .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #pikziyosip .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #pikziyosip .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #pikziyosip .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #pikziyosip .gt_left { text-align: left; }
 #pikziyosip .gt_center { text-align: center; }
 #pikziyosip .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #pikziyosip .gt_font_normal { font-weight: normal; }
 #pikziyosip .gt_font_bold { font-weight: bold; }
 #pikziyosip .gt_font_italic { font-style: italic; }
 #pikziyosip .gt_super { font-size: 65%; }
 #pikziyosip .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #pikziyosip .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #pikziyosip .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #pikziyosip .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #pikziyosip .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #pikziyosip .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Altitude, by the crudest possible proxy: is the game in Denver? |  |  |  |
|----|----|----|----|
| Denver kicks beat the model despite being LONGER on average |  |  |  |
| Denver | Attempts | Mean residual | Mean distance (yd) |
| False | 17162 | −0.0006 | 36.2682 |
| True | 795 | 0.0298 | 37.5447 |

&#10;</div>

Denver attempts beat the model by **+3.1 points** while being **1.2
yards longer** on average — the sign and magnitude thin air predicts.
This is a proxy, not an altitude feature: a real one needs a
stadium-elevation table, which does not exist in the nflverse schedule.
**The source to use is the USGS Elevation Point Query Service**
(`https://epqs.nationalmap.gov/v1/json?x=<lon>&y=<lat>`; free, no key,
US-only, which covers every NFL venue except the international games)
keyed by stadium coordinates, committed as a ~40-row
`stadium_id -> elevation_m` lookup. That table is the missing input;
nothing else blocks the feature.

None of this is a retrain — it is a measurement of what a retrain would
have to gain. Adding `wind`, `temp` and elevation to a model whose only
real feature is distance is a materially different model, and it
inherits a new dependency (schedule weather is missing or wrong for some
older games), so it belongs in a gated retrain rather than in this
document.

## Limitations

Distance is everything plus a coarse roof/era shift — **no kicker
identity, wind, or weather**, and the section above quantifies what the
last two cost. The step-function booster does not extrapolate the smooth
GAM tail past the attempted domain, so very long / never-attempted cells
should be read with caution (this is the freq-weighted vs full-grid corr
gap). The render-time scoring above pins era4 for current-season
attempts, which is exact for 2018+.

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

- **Resolved (2026-09-01, PR \#29):** *the 0.97 parity audit.* The
  residual is the long-distance tail and nothing else: corr vs the GAM
  is 0.961 under 30 yards, 0.950 at 30-39, 0.954 at 40-49, 0.864 at
  50-59 and 0.679 at 60+ (86 attempts in 27 seasons). Era mapping and
  roof do not separate. Against reality the booster is well calibrated
  (per-surface bias \<= 0.025), so the number is a functional-form
  disagreement in a region neither model has data for – an honest
  residual, not a defect to chase.
- **Resolved (2026-09-01, PR \#29):** *weather measured.* Wind and
  temperature carry monotone, unmodelled residual gradients (+2.5 to
  -3.1 points of make probability across wind buckets; -4.2 to +1.2
  across temperature), and Denver kicks beat the model by 3.1 points
  while being 1.2 yards longer.
- **Altitude still needs a source**, named in the card: a
  stadium-elevation lookup from the USGS Elevation Point Query Service
  keyed by venue coordinates. Until that ~40-row table is committed,
  “altitude” is a Denver dummy.
- **Kicker aging** remains unexamined; kicker identity is deliberately
  the FGOE residual, which is the leaderboard’s point.
- **Known issue:** wind and cold co-occur, so the two weather tables
  above double-count shared signal – a joint fit would attribute less to
  each.
