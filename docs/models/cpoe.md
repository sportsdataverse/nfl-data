# Completion Probability / CPOE


The Completion Probability (CP) model estimates the probability a given
pass attempt is completed (`cp`) from pre-throw game state and the throw
geometry. **CPOE** is the **percentage-point residual**
`100 · (complete_pass − cp)`: positive when a passer completes throws a
league-average passer would not. It is a faithful re-implementation of
the nflfastR CP/CPOE model (nflverse `fastrmodels`, Ben Baldwin).

This document is compiled: the LOSO calibration re-plots from the
committed report artifacts, and the SHAP and passer-leaderboard sections
score the committed booster and the published season at render time.

## Model features

**18 features**; the binary label is `complete_pass`. CP depends on
`air_yards` charting, reliable from **2006** onward, so only the 2006+
era one-hots (`era2..4`) are carried.

| Feature | Type | What it encodes |
|----|----|----|
| `air_yards` | numeric | Distance the ball travels in the air — the dominant completion driver. |
| `distance_to_sticks` | numeric | `air_yards − ydstogo`: how far past the first-down marker the throw targets. |
| `air_is_zero` | binary | Behind-LOS / screen indicator (`air_yards == 0`). |
| `pass_middle` | binary | Throw is over the middle of the field. |
| `qb_hit` | binary | QB was hit on the play (pressure proxy). |
| `yardline_100` | numeric | Field position (compresses depth near the goal line). |
| `ydstogo` | numeric | Yards to go. |
| `down1` … `down4` | one-hot | Current down (4 columns). |
| `home` | binary | Possession team is home. |
| `dome` / `retractable` / `outdoors` | binary | Stadium-type one-hots (wind/weather proxy). |
| `era2` … `era4` | one-hot | Rule era from 2006 (cuts 2013 / 2017). |

## The model

**Algorithm.** XGBoost, `objective=binary:logistic`, `eta=0.025`,
`max_depth=4` — the `fastrmodels` CP recipe. The predicted `cp` is the
completion probability; **CPOE = `100 · (complete_pass − cp)`** on a
percentage-point scale. Trained on **339,706 charted pass attempts**
(1999–2025 range; air-yards era 2006+).

> **Sign note.** `distance_to_sticks` is `air_yards − ydstogo` — a
> historically sign-flipped input that was corrected in the shipped CP
> feature builder; it is pinned here so the parity holds.

**Evaluation.** nflfastR parity: CPOE is **scale-correct** on the
percentage-point scale against nflverse (see [Parity](parity.md)).

## Calibration Results

Leave-one-season-out, binned predicted `cp` vs empirical completion
rate, **faceted by air-yards bucket** (the nflfastR CP signature —
completion probability is a strong, monotone function of throw depth).
On the **1999–2025** LOSO pool (339,706 throws): CP weighted calibration
error **0.0136**, Brier **0.192**.

<img src="cpoe_files/figure-commonmark/cell-3-output-1.png" width="420"
height="300"
alt="LOSO reliability by air-yards bucket, from the committed report artifact." />

<img src="cpoe_files/figure-commonmark/cell-4-output-1.png" width="420"
height="300"
alt="Completion rate vs air yards, 2025 season — the monotone depth curve the model must reproduce." />

## Feature importance & SHAP

<div id="ugzrtbkvdz" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#ugzrtbkvdz table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#ugzrtbkvdz thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#ugzrtbkvdz p { margin: 0; padding: 0; }
 #ugzrtbkvdz .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #ugzrtbkvdz .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #ugzrtbkvdz .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #ugzrtbkvdz .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #ugzrtbkvdz .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #ugzrtbkvdz .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #ugzrtbkvdz .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #ugzrtbkvdz .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #ugzrtbkvdz .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #ugzrtbkvdz .gt_column_spanner_outer:first-child { padding-left: 0; }
 #ugzrtbkvdz .gt_column_spanner_outer:last-child { padding-right: 0; }
 #ugzrtbkvdz .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #ugzrtbkvdz .gt_spanner_row { border-bottom-style: hidden; }
 #ugzrtbkvdz .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #ugzrtbkvdz .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #ugzrtbkvdz .gt_from_md> :first-child { margin-top: 0; }
 #ugzrtbkvdz .gt_from_md> :last-child { margin-bottom: 0; }
 #ugzrtbkvdz .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #ugzrtbkvdz .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #ugzrtbkvdz .gt_indent_1 { text-indent: 5px; }
 #ugzrtbkvdz .gt_indent_2 { text-indent: calc(5px * 2); }
 #ugzrtbkvdz .gt_indent_3 { text-indent: calc(5px * 3); }
 #ugzrtbkvdz .gt_indent_4 { text-indent: calc(5px * 4); }
 #ugzrtbkvdz .gt_indent_5 { text-indent: calc(5px * 5); }
 #ugzrtbkvdz .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #ugzrtbkvdz .gt_row_group_first td { border-top-width: 2px; }
 #ugzrtbkvdz .gt_row_group_first th { border-top-width: 2px; }
 #ugzrtbkvdz .gt_striped { color: #333333; background-color: #F4F4F4; }
 #ugzrtbkvdz .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #ugzrtbkvdz .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #ugzrtbkvdz .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #ugzrtbkvdz .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #ugzrtbkvdz .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #ugzrtbkvdz .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #ugzrtbkvdz .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #ugzrtbkvdz .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #ugzrtbkvdz .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #ugzrtbkvdz .gt_left { text-align: left; }
 #ugzrtbkvdz .gt_center { text-align: center; }
 #ugzrtbkvdz .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #ugzrtbkvdz .gt_font_normal { font-weight: normal; }
 #ugzrtbkvdz .gt_font_bold { font-weight: bold; }
 #ugzrtbkvdz .gt_font_italic { font-style: italic; }
 #ugzrtbkvdz .gt_super { font-size: 65%; }
 #ugzrtbkvdz .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #ugzrtbkvdz .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #ugzrtbkvdz .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #ugzrtbkvdz .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #ugzrtbkvdz .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #ugzrtbkvdz .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Top 12 features by gain — committed CP booster |       |
|------------------------------------------------|-------|
| feature                                        | gain  |
| qb_hit                                         | 327.5 |
| distance_to_sticks                             | 287.8 |
| air_yards                                      | 269.1 |
| yardline_100                                   | 88.5  |
| era2                                           | 70.3  |
| pass_middle                                    | 54.5  |
| air_is_zero                                    | 50.2  |
| era3                                           | 49.3  |
| down3                                          | 35.2  |
| ydstogo                                        | 24.0  |
| outdoors                                       | 17.1  |
| down2                                          | 15.9  |

&#10;</div>

<img src="cpoe_files/figure-commonmark/cell-6-output-1.png" width="420"
height="300"
alt="TreeSHAP per-throw attributions (log-odds), top 8 features, 4,000-throw sample from 2025." />

`air_yards` and `distance_to_sticks` dominate (throw depth is everything
for completion), with `air_is_zero` / `pass_middle` / `qb_hit` refining
short and pressured throws; the stadium and era one-hots apply small
level shifts.

## Results — 2025 CPOE leaders

<div id="pivuqblwui" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#pivuqblwui table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#pivuqblwui thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#pivuqblwui p { margin: 0; padding: 0; }
 #pivuqblwui .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #pivuqblwui .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #pivuqblwui .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #pivuqblwui .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #pivuqblwui .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #pivuqblwui .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #pivuqblwui .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #pivuqblwui .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #pivuqblwui .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #pivuqblwui .gt_column_spanner_outer:first-child { padding-left: 0; }
 #pivuqblwui .gt_column_spanner_outer:last-child { padding-right: 0; }
 #pivuqblwui .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #pivuqblwui .gt_spanner_row { border-bottom-style: hidden; }
 #pivuqblwui .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #pivuqblwui .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #pivuqblwui .gt_from_md> :first-child { margin-top: 0; }
 #pivuqblwui .gt_from_md> :last-child { margin-bottom: 0; }
 #pivuqblwui .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #pivuqblwui .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #pivuqblwui .gt_indent_1 { text-indent: 5px; }
 #pivuqblwui .gt_indent_2 { text-indent: calc(5px * 2); }
 #pivuqblwui .gt_indent_3 { text-indent: calc(5px * 3); }
 #pivuqblwui .gt_indent_4 { text-indent: calc(5px * 4); }
 #pivuqblwui .gt_indent_5 { text-indent: calc(5px * 5); }
 #pivuqblwui .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #pivuqblwui .gt_row_group_first td { border-top-width: 2px; }
 #pivuqblwui .gt_row_group_first th { border-top-width: 2px; }
 #pivuqblwui .gt_striped { color: #333333; background-color: #F4F4F4; }
 #pivuqblwui .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #pivuqblwui .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #pivuqblwui .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #pivuqblwui .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #pivuqblwui .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #pivuqblwui .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #pivuqblwui .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #pivuqblwui .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #pivuqblwui .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #pivuqblwui .gt_left { text-align: left; }
 #pivuqblwui .gt_center { text-align: center; }
 #pivuqblwui .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #pivuqblwui .gt_font_normal { font-weight: normal; }
 #pivuqblwui .gt_font_bold { font-weight: bold; }
 #pivuqblwui .gt_font_italic { font-style: italic; }
 #pivuqblwui .gt_super { font-size: 65%; }
 #pivuqblwui .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #pivuqblwui .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #pivuqblwui .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #pivuqblwui .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #pivuqblwui .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #pivuqblwui .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| CPOE leaders — 2025 (min 150 charted attempts) |  |  |  |  |  |
|----|----|----|----|----|----|
| percentage points of completion over the geometry-expected rate |  |  |  |  |  |
|  | Passer | Team | Att | Comp% | CPOE |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/oyap81gtzcvnfmripis1"
height="40" /> | D.Maye | NE | 612 | 69.3% | 4.42 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/mjwbioajzldkq1vzoz2d"
height="40" /> | J.Allen | BUF | 534 | 69.7% | 1.60 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/xykdxnvxpf9pobxvkjfj"
height="40" /> | B.Purdy | SF | 342 | 67.3% | 1.40 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/gnnvcgui1cijybukk2w7"
height="40" /> | J.Burrow | CIN | 259 | 66.8% | 1.23 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/v5sg1z9qvdpjeapblndz"
height="40" /> | M.Jones | SF | 293 | 69.3% | 0.66 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/blixemm3s9sa4gmqk5yn"
height="40" /> | D.Prescott | DAL | 600 | 67.3% | 0.49 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/s5t8m6bhedjwwtfw3ild"
height="40" /> | S.Darnold | SEA | 568 | 66.7% | 0.39 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/nhuiypfjzpkisxllinyv"
height="40" /> | D.Jones | IND | 384 | 68.0% | 0.34 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/uridusydmg6brwrmpmq6"
height="40" /> | S.Rattler | NO | 257 | 67.7% | 0.04 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/s1oelyaroiaalgilbeqk"
height="40" /> | J.Herbert | LAC | 543 | 66.1% | −0.07 |

&#10;</div>

## Limitations

CP is blind to receiver separation and coverage we do not chart, so CPOE
captures the *geometry-and-state-explainable* part of completion only.
Air-yards charting is unreliable before 2006, so CP is an air-yards-era
surface. CPOE is a per-throw residual; aggregate it over a meaningful
sample before reading it as passer skill.

## Provenance

| field | value |
|----|----|
| `model_type` | cp |
| `objective` | binary:logistic |
| `features` | 18 (see above) |
| `label` | complete_pass |
| `training_seasons` | 1999–2025 (air-yards era 2006+) |
| `n_training_rows` | 339,706 |
| `hyperparameters` | eta=0.025, max_depth=4 |
| `lineage` | nflfastR CP/CPOE model · nflverse `fastrmodels` (Ben Baldwin) |
| `parity` | `cpoe` scale-correct (percentage points) |
| `artifact` | `models/cp_model.ubj` (committed; also on `nfl_model_artifacts`) |
| `rebuild this doc` | `scripts/render_model_docs.sh` (Quarto → GFM; `uv sync --group docs`) |

## Avenues for improvement & open issues

- **Separation/coverage features** — public pbp lacks them; NGS-derived
  aggregates are the plausible lever.
- **Known issue:** CPOE is percentage-point scaled (100x) by convention
  — consumers routinely mis-scale it; the column doc must stay loud.
