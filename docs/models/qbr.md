# QBR


The QBR model reconstructs an **ESPN-Total-QBR-style 0–100 quarterback
rating** from EPA components, so a QBR can be produced for any game in
the corpus without an ESPN QBR feed. It is a per-(quarterback, game)
regression onto ESPN’s published raw QBR, sitting one layer above the
[EP model](ep.md) — its inputs are EPA aggregates, and EPA is the first
difference of EP.

This document is compiled: the target-analysis sections below read
ESPN’s published QBR (the `nfl_espn_qbr` release this repo also
publishes) and the per-QB EPA aggregates from the published pbp at
render time — quantifying exactly how much of ESPN’s number the EPA
components can explain, which is the quantity the model reconstructs.

## Model features

**6 features**, one row per (quarterback, game). Each EPA component is
the per-game **win-probability-leverage-weighted** mean of that
component over the QB’s plays (high-leverage plays weighted up, garbage
time weighted down), and EPA is clamped to protect the regression from
blow-up plays (`EPA < −5 → −5`, fumble → −3.5).

| Feature | Type | What it encodes |
|----|----|----|
| `qbr_epa` | numeric | Total QBR-attributable (clamped, leverage-weighted) EPA — the dominant driver. |
| `pass_epa` | numeric | EPA on dropbacks. |
| `rush_epa` | numeric | EPA on QB rushes. |
| `sack_epa` | numeric | EPA lost on non-fumble sacks. |
| `pen_epa` | numeric | EPA from penalties on the QB’s plays. |
| `spread` | numeric | Possession-team pregame spread (garbage-time / leverage context). |

## The model

**Algorithm.** XGBoost regression (`objective=reg:squarederror`). The
target is ESPN’s *published raw QBR* for the quarterback-game; the EPA
components come from the [EP model](ep.md), so QBR composes on top of
EP/EPA. The leverage weighting mirrors ESPN’s clutch emphasis (plays in
0.1–0.2 / 0.8–0.9 home-WP bands carry 0.9× weight, beyond that 0.6×).

**Evaluation.** As a continuous bounded (0–100) target, QBR is checked
by predicted-vs-ESPN scatter rather than a probability-calibration plot.
The render-time analysis below measures the EPA-explainability ceiling
directly.

## The target, and its EPA-explainability

<div id="unqclejaky" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#unqclejaky table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#unqclejaky thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#unqclejaky p { margin: 0; padding: 0; }
 #unqclejaky .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #unqclejaky .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #unqclejaky .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #unqclejaky .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #unqclejaky .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #unqclejaky .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #unqclejaky .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #unqclejaky .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #unqclejaky .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #unqclejaky .gt_column_spanner_outer:first-child { padding-left: 0; }
 #unqclejaky .gt_column_spanner_outer:last-child { padding-right: 0; }
 #unqclejaky .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #unqclejaky .gt_spanner_row { border-bottom-style: hidden; }
 #unqclejaky .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #unqclejaky .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #unqclejaky .gt_from_md> :first-child { margin-top: 0; }
 #unqclejaky .gt_from_md> :last-child { margin-bottom: 0; }
 #unqclejaky .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #unqclejaky .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #unqclejaky .gt_indent_1 { text-indent: 5px; }
 #unqclejaky .gt_indent_2 { text-indent: calc(5px * 2); }
 #unqclejaky .gt_indent_3 { text-indent: calc(5px * 3); }
 #unqclejaky .gt_indent_4 { text-indent: calc(5px * 4); }
 #unqclejaky .gt_indent_5 { text-indent: calc(5px * 5); }
 #unqclejaky .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #unqclejaky .gt_row_group_first td { border-top-width: 2px; }
 #unqclejaky .gt_row_group_first th { border-top-width: 2px; }
 #unqclejaky .gt_striped { color: #333333; background-color: #F4F4F4; }
 #unqclejaky .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #unqclejaky .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #unqclejaky .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #unqclejaky .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #unqclejaky .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #unqclejaky .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #unqclejaky .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #unqclejaky .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #unqclejaky .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #unqclejaky .gt_left { text-align: left; }
 #unqclejaky .gt_center { text-align: center; }
 #unqclejaky .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #unqclejaky .gt_font_normal { font-weight: normal; }
 #unqclejaky .gt_font_bold { font-weight: bold; }
 #unqclejaky .gt_font_italic { font-style: italic; }
 #unqclejaky .gt_super { font-size: 65%; }
 #unqclejaky .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #unqclejaky .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #unqclejaky .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #unqclejaky .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #unqclejaky .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #unqclejaky .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| The published nfl_espn_qbr target — render time |           |
|-------------------------------------------------|-----------|
| check                                           | value     |
| ESPN QBR quarterback-weeks (release)            | 10,742.00 |
| latest season rows                              | 566.00    |
| mean QBR (latest season)                        | 52.57     |

&#10;</div>

<img src="qbr_files/figure-commonmark/cell-4-output-1.png" width="420"
height="300"
alt="Per-QB-week: ESPN QBR vs simple (unweighted) EPA/play from the published pbp — the correlation is the floor the leverage-weighted model improves on." />

The unweighted EPA/play already explains most of QBR’s variance; the
model’s leverage weighting, clamping, and component split close much of
the remaining gap. What can never close is ESPN’s charting-based credit
assignment — inputs the public feed does not carry.

## Results — 2025 QBR leaders

<div id="zcxltijtvc" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#zcxltijtvc table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#zcxltijtvc thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#zcxltijtvc p { margin: 0; padding: 0; }
 #zcxltijtvc .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #zcxltijtvc .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #zcxltijtvc .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #zcxltijtvc .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #zcxltijtvc .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #zcxltijtvc .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #zcxltijtvc .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #zcxltijtvc .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #zcxltijtvc .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #zcxltijtvc .gt_column_spanner_outer:first-child { padding-left: 0; }
 #zcxltijtvc .gt_column_spanner_outer:last-child { padding-right: 0; }
 #zcxltijtvc .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #zcxltijtvc .gt_spanner_row { border-bottom-style: hidden; }
 #zcxltijtvc .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #zcxltijtvc .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #zcxltijtvc .gt_from_md> :first-child { margin-top: 0; }
 #zcxltijtvc .gt_from_md> :last-child { margin-bottom: 0; }
 #zcxltijtvc .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #zcxltijtvc .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #zcxltijtvc .gt_indent_1 { text-indent: 5px; }
 #zcxltijtvc .gt_indent_2 { text-indent: calc(5px * 2); }
 #zcxltijtvc .gt_indent_3 { text-indent: calc(5px * 3); }
 #zcxltijtvc .gt_indent_4 { text-indent: calc(5px * 4); }
 #zcxltijtvc .gt_indent_5 { text-indent: calc(5px * 5); }
 #zcxltijtvc .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #zcxltijtvc .gt_row_group_first td { border-top-width: 2px; }
 #zcxltijtvc .gt_row_group_first th { border-top-width: 2px; }
 #zcxltijtvc .gt_striped { color: #333333; background-color: #F4F4F4; }
 #zcxltijtvc .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #zcxltijtvc .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #zcxltijtvc .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #zcxltijtvc .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #zcxltijtvc .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #zcxltijtvc .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #zcxltijtvc .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #zcxltijtvc .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #zcxltijtvc .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #zcxltijtvc .gt_left { text-align: left; }
 #zcxltijtvc .gt_center { text-align: center; }
 #zcxltijtvc .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #zcxltijtvc .gt_font_normal { font-weight: normal; }
 #zcxltijtvc .gt_font_bold { font-weight: bold; }
 #zcxltijtvc .gt_font_italic { font-style: italic; }
 #zcxltijtvc .gt_super { font-size: 65%; }
 #zcxltijtvc .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #zcxltijtvc .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #zcxltijtvc .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #zcxltijtvc .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #zcxltijtvc .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #zcxltijtvc .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| ESPN Total QBR leaders — latest season (min 8 games)  |      |       |
|-------------------------------------------------------|------|-------|
| the published target the reconstruction is trained on |      |       |
| quarterback                                           | qbr  | games |
| J. Love                                               | 72.7 | 15    |
| D. Prescott                                           | 69.1 | 16    |
| D. Maye                                               | 68.1 | 21    |
| P. Mahomes                                            | 66.5 | 14    |
| M. Stafford                                           | 66.4 | 20    |
| B. Purdy                                              | 65.4 | 11    |
| D. Jones                                              | 64.4 | 12    |
| M. Jones                                              | 64.0 | 8     |
| J. Allen                                              | 62.3 | 18    |
| B. Mayfield                                           | 59.7 | 17    |

&#10;</div>

## Limitations

QBR is a **bounded 0–100** target, so the model cannot perfectly
reproduce ESPN’s proprietary formula (clutch weighting and charting
inputs we do not have). Treat the output as a faithful reconstruction of
the **EPA-explainable** part of QBR, not a byte-exact ESPN replica. It
inherits the EP model’s drift through the EPA components.

## Provenance

| field | value |
|----|----|
| `model_type` | qbr |
| `objective` | reg:squarederror |
| `features` | qbr_epa, pass_epa, rush_epa, sack_epa, pen_epa, spread |
| `target` | ESPN raw Total QBR (per quarterback-game; `nfl_espn_qbr` release) |
| `lineage` | ESPN Total QBR · EPA components from the EP model |
| `distribution` | bundled in sportsdataverse (`qbr_model.ubj`) |
| `rebuild this doc` | `scripts/render_model_docs.sh` (Quarto → GFM; `uv sync --group docs`) |

## Avenues for improvement & open issues

- **Opponent adjustment** — the QBR-style rating is unadjusted for
  defense faced.
- **Known issue:** the registry’s qbr row remains an external TODO
  (trainer not in `model_training/`) — this report documents the bundled
  artifact, not an in-repo recipe.
