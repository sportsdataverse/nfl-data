# Expected Yards After Catch (xYAC)


The xYAC model predicts the **distribution of yards gained after the
catch** on a completed pass, given the throw geometry and game state at
the moment of the catch. It is a faithful re-implementation of the
nflfastR `add_xyac` model — a **76-class multinomial** over post-catch
gain — and feeds the expected-YAC surface (`xyac_epa`,
`xyac_mean_yardage`) used to decompose a completion into its air vs
after-catch contributions.

This document is compiled: the evaluation below holds the published
`xyac_mean_yardage` column against **realized** yards after catch on the
latest published season — a live predicted-vs-realized check of the
applied model.

## Model features

**19 features** — the [CP](cpoe.md) feature set plus `distance_to_goal`.
The label is the post-catch yardage bucketed into 76 ordinal classes.
Like CP, xYAC depends on `air_yards` charting (2006+), so only `era2..4`
are carried.

| Feature | Type | What it encodes |
|----|----|----|
| `air_yards` | numeric | Air distance to the catch point — sets where YAC starts. |
| `distance_to_goal` | numeric | Yards from the catch point to the end zone — **caps** achievable YAC near the goal line. |
| `distance_to_sticks` | numeric | `air_yards − ydstogo`. |
| `yardline_100` / `ydstogo` | numeric | Field position and yards to go at the snap. |
| `air_is_zero` / `pass_middle` / `qb_hit` | binary | Screen/behind-LOS, over-the-middle, pressure indicators. |
| `down1` … `down4` | one-hot | Current down. |
| `home` | binary | Possession team is home. |
| `dome` / `retractable` / `outdoors` | binary | Stadium-type one-hots. |
| `era2` … `era4` | one-hot | Rule era from 2006. |

## The model

**Algorithm.** XGBoost, `objective=multi:softprob` over
**`num_class=76`**, `eta=0.025`, `max_depth=4` — the nflfastR `add_xyac`
recipe. The 76-class distribution over post-catch gain is the model
output; expected YAC and `xyac_epa` are recovered by combining the class
distribution with the EP surface at each resulting yard line. Trained on
**222,020 completed passes (2006–2025)**.

**Evaluation.** Faithful port of nflfastR `add_xyac` — the 76-class
multinomial reproduces the nflverse YAC distribution. xYAC is a
**download-on-demand** model in `sportsdataverse` (the ~34 MB artifact
is fetched and cached rather than bundled); the artifact is committed
here at `models/xyac_model.ubj`.

## Feature importance

<div id="uxshqtqqyu" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#uxshqtqqyu table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#uxshqtqqyu thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#uxshqtqqyu p { margin: 0; padding: 0; }
 #uxshqtqqyu .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #uxshqtqqyu .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #uxshqtqqyu .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #uxshqtqqyu .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #uxshqtqqyu .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #uxshqtqqyu .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #uxshqtqqyu .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #uxshqtqqyu .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #uxshqtqqyu .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #uxshqtqqyu .gt_column_spanner_outer:first-child { padding-left: 0; }
 #uxshqtqqyu .gt_column_spanner_outer:last-child { padding-right: 0; }
 #uxshqtqqyu .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #uxshqtqqyu .gt_spanner_row { border-bottom-style: hidden; }
 #uxshqtqqyu .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #uxshqtqqyu .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #uxshqtqqyu .gt_from_md> :first-child { margin-top: 0; }
 #uxshqtqqyu .gt_from_md> :last-child { margin-bottom: 0; }
 #uxshqtqqyu .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #uxshqtqqyu .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #uxshqtqqyu .gt_indent_1 { text-indent: 5px; }
 #uxshqtqqyu .gt_indent_2 { text-indent: calc(5px * 2); }
 #uxshqtqqyu .gt_indent_3 { text-indent: calc(5px * 3); }
 #uxshqtqqyu .gt_indent_4 { text-indent: calc(5px * 4); }
 #uxshqtqqyu .gt_indent_5 { text-indent: calc(5px * 5); }
 #uxshqtqqyu .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #uxshqtqqyu .gt_row_group_first td { border-top-width: 2px; }
 #uxshqtqqyu .gt_row_group_first th { border-top-width: 2px; }
 #uxshqtqqyu .gt_striped { color: #333333; background-color: #F4F4F4; }
 #uxshqtqqyu .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #uxshqtqqyu .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #uxshqtqqyu .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #uxshqtqqyu .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #uxshqtqqyu .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #uxshqtqqyu .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #uxshqtqqyu .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #uxshqtqqyu .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #uxshqtqqyu .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #uxshqtqqyu .gt_left { text-align: left; }
 #uxshqtqqyu .gt_center { text-align: center; }
 #uxshqtqqyu .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #uxshqtqqyu .gt_font_normal { font-weight: normal; }
 #uxshqtqqyu .gt_font_bold { font-weight: bold; }
 #uxshqtqqyu .gt_font_italic { font-style: italic; }
 #uxshqtqqyu .gt_super { font-size: 65%; }
 #uxshqtqqyu .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #uxshqtqqyu .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #uxshqtqqyu .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #uxshqtqqyu .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #uxshqtqqyu .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #uxshqtqqyu .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Top 12 features by gain — committed xYAC booster |      |
|--------------------------------------------------|------|
| feature                                          | gain |
| air_yards                                        | 27.7 |
| distance_to_goal                                 | 15.9 |
| distance_to_sticks                               | 13.7 |
| pass_middle                                      | 12.3 |
| air_is_zero                                      | 6.2  |
| yardline_100                                     | 4.7  |
| down3                                            | 4.7  |
| ydstogo                                          | 4.6  |
| era4                                             | 4.1  |
| outdoors                                         | 4.0  |
| down1                                            | 3.9  |
| qb_hit                                           | 3.8  |

&#10;</div>

`air_yards` and `distance_to_goal` dominate — air depth sets the YAC
starting point and the goal line caps it — with `air_is_zero` /
`pass_middle` separating screens and crossers (high-YAC archetypes) from
contested downfield throws. (A per-play SHAP pass is deliberately
omitted: multiclass `pred_contribs` on a 76-class head is a 3-D
`(n, 76, 20)` tensor — the recorded gotcha — and the mean-YAC
attribution it would aggregate to is already what the gain table and the
depth curves below show.)

## Calibration — predicted vs realized YAC, render time

<img src="xyac_files/figure-commonmark/cell-4-output-1.png" width="420"
height="300"
alt="Mean predicted xYAC vs mean realized YAC by air-yards bucket, 2025 completions — the applied surface against reality." />

<div id="hrclhoqnnb" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#hrclhoqnnb table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#hrclhoqnnb thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#hrclhoqnnb p { margin: 0; padding: 0; }
 #hrclhoqnnb .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #hrclhoqnnb .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #hrclhoqnnb .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #hrclhoqnnb .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #hrclhoqnnb .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #hrclhoqnnb .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #hrclhoqnnb .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #hrclhoqnnb .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #hrclhoqnnb .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #hrclhoqnnb .gt_column_spanner_outer:first-child { padding-left: 0; }
 #hrclhoqnnb .gt_column_spanner_outer:last-child { padding-right: 0; }
 #hrclhoqnnb .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #hrclhoqnnb .gt_spanner_row { border-bottom-style: hidden; }
 #hrclhoqnnb .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #hrclhoqnnb .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #hrclhoqnnb .gt_from_md> :first-child { margin-top: 0; }
 #hrclhoqnnb .gt_from_md> :last-child { margin-bottom: 0; }
 #hrclhoqnnb .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #hrclhoqnnb .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #hrclhoqnnb .gt_indent_1 { text-indent: 5px; }
 #hrclhoqnnb .gt_indent_2 { text-indent: calc(5px * 2); }
 #hrclhoqnnb .gt_indent_3 { text-indent: calc(5px * 3); }
 #hrclhoqnnb .gt_indent_4 { text-indent: calc(5px * 4); }
 #hrclhoqnnb .gt_indent_5 { text-indent: calc(5px * 5); }
 #hrclhoqnnb .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #hrclhoqnnb .gt_row_group_first td { border-top-width: 2px; }
 #hrclhoqnnb .gt_row_group_first th { border-top-width: 2px; }
 #hrclhoqnnb .gt_striped { color: #333333; background-color: #F4F4F4; }
 #hrclhoqnnb .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #hrclhoqnnb .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #hrclhoqnnb .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #hrclhoqnnb .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #hrclhoqnnb .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #hrclhoqnnb .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #hrclhoqnnb .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #hrclhoqnnb .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #hrclhoqnnb .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #hrclhoqnnb .gt_left { text-align: left; }
 #hrclhoqnnb .gt_center { text-align: center; }
 #hrclhoqnnb .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #hrclhoqnnb .gt_font_normal { font-weight: normal; }
 #hrclhoqnnb .gt_font_bold { font-weight: bold; }
 #hrclhoqnnb .gt_font_italic { font-style: italic; }
 #hrclhoqnnb .gt_super { font-size: 65%; }
 #hrclhoqnnb .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #hrclhoqnnb .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #hrclhoqnnb .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #hrclhoqnnb .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #hrclhoqnnb .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #hrclhoqnnb .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Render-time xYAC evaluation — 2025 season |  |
|----|----|
| per-completion correlation is bounded by irreducible YAC variance; the aggregate bias is the honest calibration number |  |
| check | value |
| completions evaluated | 11,278.000 |
| mean predicted xYAC | 5.443 |
| mean realized YAC | 5.357 |
| mean error (pred − real) | 0.085 |
| corr(pred, real) per completion | 0.375 |

&#10;</div>

The screen-depth region (negative/zero air yards) carries the highest
YAC and the tightest predicted-realized agreement; deep throws carry
little YAC and more relative noise — exactly the structure the 76-class
head is built around.

## Results — YAC over expected, 2025

<div id="athqrqcpnn" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#athqrqcpnn table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#athqrqcpnn thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#athqrqcpnn p { margin: 0; padding: 0; }
 #athqrqcpnn .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #athqrqcpnn .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #athqrqcpnn .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #athqrqcpnn .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #athqrqcpnn .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #athqrqcpnn .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #athqrqcpnn .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #athqrqcpnn .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #athqrqcpnn .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #athqrqcpnn .gt_column_spanner_outer:first-child { padding-left: 0; }
 #athqrqcpnn .gt_column_spanner_outer:last-child { padding-right: 0; }
 #athqrqcpnn .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #athqrqcpnn .gt_spanner_row { border-bottom-style: hidden; }
 #athqrqcpnn .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #athqrqcpnn .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #athqrqcpnn .gt_from_md> :first-child { margin-top: 0; }
 #athqrqcpnn .gt_from_md> :last-child { margin-bottom: 0; }
 #athqrqcpnn .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #athqrqcpnn .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #athqrqcpnn .gt_indent_1 { text-indent: 5px; }
 #athqrqcpnn .gt_indent_2 { text-indent: calc(5px * 2); }
 #athqrqcpnn .gt_indent_3 { text-indent: calc(5px * 3); }
 #athqrqcpnn .gt_indent_4 { text-indent: calc(5px * 4); }
 #athqrqcpnn .gt_indent_5 { text-indent: calc(5px * 5); }
 #athqrqcpnn .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #athqrqcpnn .gt_row_group_first td { border-top-width: 2px; }
 #athqrqcpnn .gt_row_group_first th { border-top-width: 2px; }
 #athqrqcpnn .gt_striped { color: #333333; background-color: #F4F4F4; }
 #athqrqcpnn .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #athqrqcpnn .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #athqrqcpnn .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #athqrqcpnn .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #athqrqcpnn .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #athqrqcpnn .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #athqrqcpnn .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #athqrqcpnn .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #athqrqcpnn .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #athqrqcpnn .gt_left { text-align: left; }
 #athqrqcpnn .gt_center { text-align: center; }
 #athqrqcpnn .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #athqrqcpnn .gt_font_normal { font-weight: normal; }
 #athqrqcpnn .gt_font_bold { font-weight: bold; }
 #athqrqcpnn .gt_font_italic { font-style: italic; }
 #athqrqcpnn .gt_super { font-size: 65%; }
 #athqrqcpnn .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #athqrqcpnn .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #athqrqcpnn .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #athqrqcpnn .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #athqrqcpnn .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #athqrqcpnn .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| YAC over expected — 2025 (min 40 catches) |  |  |  |  |  |  |
|----|----|----|----|----|----|----|
| realized YAC minus the geometry-expected YAC; the broken-tackle/athleticism residual the model is deliberately blind to |  |  |  |  |  |  |
|  | Receiver | Team | Rec | YAC | xYAC | YAC−xYAC |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/rjaf9auhx3lrktzgwpfb"
height="40" /> | B.Robinson | ATL | 78 | 857.0 | 580.5 | 276.5 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/resjdwihunsqckohcorj"
height="40" /> | C.McCaffrey | SF | 108 | 766.0 | 621.1 | 144.9 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/tknefloqsleltfmslj2y"
height="40" /> | D.Metcalf | PIT | 57 | 443.0 | 299.1 | 143.9 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/cbpyykoguf7rsxezqzvk"
height="40" /> | G.Pickens | DAL | 87 | 479.0 | 341.3 | 137.7 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/mnzsnemdzbey5hbahdhk"
height="40" /> | K.Walker | SEA | 40 | 441.0 | 313.5 | 127.5 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/gpjarmglg1jhwq5wr1uu"
height="40" /> | J.Williams | DET | 64 | 433.0 | 310.1 | 122.9 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/qsyrgtfjj06wryahnxc9"
height="40" /> | C.Parkinson | LA | 48 | 368.0 | 247.7 | 120.3 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/ed09migntlyy8ntgvcu1"
height="40" /> | R.Stevenson | NE | 43 | 403.0 | 289.0 | 114.0 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/f3txbqdarbabqtq4sx98"
height="40" /> | J.Warren | PIT | 41 | 439.0 | 338.9 | 100.1 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/iy0uidp9wokc6a7u8lwq"
height="40" /> | R.Rice | KC | 51 | 414.0 | 318.2 | 95.8 |

&#10;</div>

## Limitations

xYAC is blind to the broken-tackle / open-field athleticism that drives
the YAC tail, so it captures the *situation-and-geometry-explainable*
mean, not a specific receiver’s elusiveness — which is precisely what
makes YAC-over-expected a meaningful receiver skill residual. The
76-class window clips extreme returns. Because it depends on
`air_yards`, it is a 2006+ surface.

## Provenance

| field | value |
|----|----|
| `model_type` | xyac |
| `objective` | multi:softprob (num_class=76) |
| `features` | 19 (CP set + `distance_to_goal`) |
| `label` | post-catch yardage (76 ordinal classes) |
| `training_seasons` | 2006–2025 |
| `n_training_rows` | 222,020 |
| `hyperparameters` | eta=0.025, max_depth=4 |
| `lineage` | nflfastR `add_xyac` |
| `artifact` | `models/xyac_model.ubj` (committed; download-on-demand in sportsdataverse) |
| `rebuild this doc` | `scripts/render_model_docs.sh` (Quarto → GFM; `uv sync --group docs`) |

## Avenues for improvement & open issues

- **Continuous target** — the 76-class distribution could be compared
  against a monotone continuous head; distributional calibration beyond
  the mean is unevaluated (the render-time check above evaluates the
  mean only).
- **Known issue:** `distance_to_sticks` sign conventions bit once
  already (recorded gotcha) — any feature change must re-verify it.
