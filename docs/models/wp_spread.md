# Win Probability — spread (`vegas_wp`)


The spread-aware Win Probability model estimates the probability that
the team in possession wins the game, given game state **and the pregame
point spread**. It produces the nflfastR `vegas_wp` surface;
consecutive-play differences define **Win Probability Added (WPA)**. It
is a faithful re-implementation of the nflfastR spread WP model
(nflverse `fastrmodels`, Ben Baldwin).

This document is compiled: the LOSO calibration re-plots from the
committed report artifact, and the SHAP/results sections score the
committed booster (`models/wp_spread.ubj`) over the latest published
`nfl_model_pbp` season at render time.

## Model features

**12 features**, all start-of-play. The binary label is
`label = (possession team == game winner)`. The signature feature is the
time-decayed spread.

| Feature | Type | What it encodes |
|----|----|----|
| `spread_time` | numeric | `pos_team_spread · exp(−4 · elapsed_share)` — the pregame spread decayed toward 0 as the clock runs; its influence vanishes by Q4. **The market signal.** |
| `receive_2h_ko` | binary | Possession team receives the second-half kickoff — a known WP edge. |
| `home` | binary | Home-field indicator for the possession team. |
| `half_seconds_remaining` | numeric | Seconds remaining in the half. |
| `game_seconds_remaining` | numeric | Seconds remaining in the game. |
| `Diff_Time_Ratio` | numeric | Score differential scaled by time — an urgency/leverage interaction. |
| `score_differential` | numeric | Possession-team score differential. |
| `down` | numeric | Current down. |
| `ydstogo` | numeric | Yards to go. |
| `yardline_100` | numeric | Field position. |
| `posteam_timeouts_remaining` | numeric | Possession-team timeouts left. |
| `defteam_timeouts_remaining` | numeric | Defense timeouts left. |

## The model

**Algorithm.** XGBoost, `objective=binary:logistic`,
`eval_metric=logloss`, `eta=0.05`, `max_depth=5` — the `fastrmodels`
spread-WP recipe. Trained on the **full 1999–2025 history (1,268,220
plays)**. The `spread_time` decay constant (−4) matches the shipped
derivation.

**Evaluation.** nflfastR parity is the headline gate — `vegas_wp`
correlates **r 0.998** against nflverse, the tightest agreement in the
suite (see [Parity](parity.md)). LOSO calibration below.

## Calibration Results

Leave-one-season-out, pooled out-of-fold, binned predicted WP vs
observed win rate. On the **1999–2025** LOSO pool (1,268,220 plays):
weighted calibration error **0.0026**, Brier **0.154**.

<img src="wp_spread_files/figure-commonmark/cell-3-output-1.png"
width="420" height="300"
alt="LOSO reliability — predicted WP bin vs observed win rate, from the committed report artifact." />

<div id="bzsvvzgmam" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#bzsvvzgmam table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#bzsvvzgmam thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#bzsvvzgmam p { margin: 0; padding: 0; }
 #bzsvvzgmam .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #bzsvvzgmam .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #bzsvvzgmam .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #bzsvvzgmam .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #bzsvvzgmam .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #bzsvvzgmam .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #bzsvvzgmam .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #bzsvvzgmam .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #bzsvvzgmam .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #bzsvvzgmam .gt_column_spanner_outer:first-child { padding-left: 0; }
 #bzsvvzgmam .gt_column_spanner_outer:last-child { padding-right: 0; }
 #bzsvvzgmam .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #bzsvvzgmam .gt_spanner_row { border-bottom-style: hidden; }
 #bzsvvzgmam .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #bzsvvzgmam .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #bzsvvzgmam .gt_from_md> :first-child { margin-top: 0; }
 #bzsvvzgmam .gt_from_md> :last-child { margin-bottom: 0; }
 #bzsvvzgmam .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #bzsvvzgmam .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #bzsvvzgmam .gt_indent_1 { text-indent: 5px; }
 #bzsvvzgmam .gt_indent_2 { text-indent: calc(5px * 2); }
 #bzsvvzgmam .gt_indent_3 { text-indent: calc(5px * 3); }
 #bzsvvzgmam .gt_indent_4 { text-indent: calc(5px * 4); }
 #bzsvvzgmam .gt_indent_5 { text-indent: calc(5px * 5); }
 #bzsvvzgmam .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #bzsvvzgmam .gt_row_group_first td { border-top-width: 2px; }
 #bzsvvzgmam .gt_row_group_first th { border-top-width: 2px; }
 #bzsvvzgmam .gt_striped { color: #333333; background-color: #F4F4F4; }
 #bzsvvzgmam .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #bzsvvzgmam .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #bzsvvzgmam .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #bzsvvzgmam .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #bzsvvzgmam .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #bzsvvzgmam .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #bzsvvzgmam .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #bzsvvzgmam .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #bzsvvzgmam .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #bzsvvzgmam .gt_left { text-align: left; }
 #bzsvvzgmam .gt_center { text-align: center; }
 #bzsvvzgmam .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #bzsvvzgmam .gt_font_normal { font-weight: normal; }
 #bzsvvzgmam .gt_font_bold { font-weight: bold; }
 #bzsvvzgmam .gt_font_italic { font-style: italic; }
 #bzsvvzgmam .gt_super { font-size: 65%; }
 #bzsvvzgmam .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #bzsvvzgmam .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #bzsvvzgmam .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #bzsvvzgmam .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #bzsvvzgmam .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #bzsvvzgmam .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Frozen LOSO metrics (training report) |                |
|---------------------------------------|----------------|
| metric                                | value          |
| weighted calibration error            | 0.0026         |
| Brier                                 | 0.1536         |
| LOSO plays                            | 1,268,220.0000 |

&#10;</div>

## Feature importance & SHAP

<div id="tfaoklfpwh" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#tfaoklfpwh table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#tfaoklfpwh thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#tfaoklfpwh p { margin: 0; padding: 0; }
 #tfaoklfpwh .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #tfaoklfpwh .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #tfaoklfpwh .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #tfaoklfpwh .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #tfaoklfpwh .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #tfaoklfpwh .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #tfaoklfpwh .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #tfaoklfpwh .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #tfaoklfpwh .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #tfaoklfpwh .gt_column_spanner_outer:first-child { padding-left: 0; }
 #tfaoklfpwh .gt_column_spanner_outer:last-child { padding-right: 0; }
 #tfaoklfpwh .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #tfaoklfpwh .gt_spanner_row { border-bottom-style: hidden; }
 #tfaoklfpwh .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #tfaoklfpwh .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #tfaoklfpwh .gt_from_md> :first-child { margin-top: 0; }
 #tfaoklfpwh .gt_from_md> :last-child { margin-bottom: 0; }
 #tfaoklfpwh .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #tfaoklfpwh .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #tfaoklfpwh .gt_indent_1 { text-indent: 5px; }
 #tfaoklfpwh .gt_indent_2 { text-indent: calc(5px * 2); }
 #tfaoklfpwh .gt_indent_3 { text-indent: calc(5px * 3); }
 #tfaoklfpwh .gt_indent_4 { text-indent: calc(5px * 4); }
 #tfaoklfpwh .gt_indent_5 { text-indent: calc(5px * 5); }
 #tfaoklfpwh .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #tfaoklfpwh .gt_row_group_first td { border-top-width: 2px; }
 #tfaoklfpwh .gt_row_group_first th { border-top-width: 2px; }
 #tfaoklfpwh .gt_striped { color: #333333; background-color: #F4F4F4; }
 #tfaoklfpwh .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #tfaoklfpwh .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #tfaoklfpwh .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #tfaoklfpwh .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #tfaoklfpwh .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #tfaoklfpwh .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #tfaoklfpwh .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #tfaoklfpwh .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #tfaoklfpwh .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #tfaoklfpwh .gt_left { text-align: left; }
 #tfaoklfpwh .gt_center { text-align: center; }
 #tfaoklfpwh .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #tfaoklfpwh .gt_font_normal { font-weight: normal; }
 #tfaoklfpwh .gt_font_bold { font-weight: bold; }
 #tfaoklfpwh .gt_font_italic { font-style: italic; }
 #tfaoklfpwh .gt_super { font-size: 65%; }
 #tfaoklfpwh .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #tfaoklfpwh .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #tfaoklfpwh .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #tfaoklfpwh .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #tfaoklfpwh .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #tfaoklfpwh .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Features by gain — committed spread-WP booster |         |
|------------------------------------------------|---------|
| feature                                        | gain    |
| score_differential                             | 2,414.4 |
| Diff_Time_Ratio                                | 910.2   |
| spread_time                                    | 495.0   |
| home                                           | 244.9   |
| defteam_timeouts_remaining                     | 128.6   |
| yardline_100                                   | 90.7    |
| posteam_timeouts_remaining                     | 81.6    |
| down                                           | 63.6    |
| game_seconds_remaining                         | 61.1    |
| receive_2h_ko                                  | 50.6    |
| half_seconds_remaining                         | 26.3    |
| ydstogo                                        | 14.4    |

&#10;</div>

<img src="wp_spread_files/figure-commonmark/cell-6-output-1.png"
width="420" height="300"
alt="TreeSHAP per-play attributions (log-odds), 4,000-play sample from 2025 — spread_time’s influence is wide early and collapses late by construction." />

`spread_time` and the time/score-differential terms carry the model
early in games; as `spread_time` decays, `score_differential`,
`yardline_100` and the clock terms take over — the intended hand-off
from market prior to live game state, visible in the attribution spread
above.

## Results — the surface in use

<img src="wp_spread_files/figure-commonmark/cell-7-output-1.png"
width="420" height="300"
alt="The 2025 season’s wildest game by WP swing (published vegas_wp trace, possession-team perspective folded to home)." />

<div id="yozgsicvyc" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#yozgsicvyc table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#yozgsicvyc thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#yozgsicvyc p { margin: 0; padding: 0; }
 #yozgsicvyc .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #yozgsicvyc .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #yozgsicvyc .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #yozgsicvyc .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #yozgsicvyc .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #yozgsicvyc .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #yozgsicvyc .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #yozgsicvyc .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #yozgsicvyc .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #yozgsicvyc .gt_column_spanner_outer:first-child { padding-left: 0; }
 #yozgsicvyc .gt_column_spanner_outer:last-child { padding-right: 0; }
 #yozgsicvyc .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #yozgsicvyc .gt_spanner_row { border-bottom-style: hidden; }
 #yozgsicvyc .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #yozgsicvyc .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #yozgsicvyc .gt_from_md> :first-child { margin-top: 0; }
 #yozgsicvyc .gt_from_md> :last-child { margin-bottom: 0; }
 #yozgsicvyc .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #yozgsicvyc .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #yozgsicvyc .gt_indent_1 { text-indent: 5px; }
 #yozgsicvyc .gt_indent_2 { text-indent: calc(5px * 2); }
 #yozgsicvyc .gt_indent_3 { text-indent: calc(5px * 3); }
 #yozgsicvyc .gt_indent_4 { text-indent: calc(5px * 4); }
 #yozgsicvyc .gt_indent_5 { text-indent: calc(5px * 5); }
 #yozgsicvyc .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #yozgsicvyc .gt_row_group_first td { border-top-width: 2px; }
 #yozgsicvyc .gt_row_group_first th { border-top-width: 2px; }
 #yozgsicvyc .gt_striped { color: #333333; background-color: #F4F4F4; }
 #yozgsicvyc .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #yozgsicvyc .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #yozgsicvyc .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #yozgsicvyc .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #yozgsicvyc .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #yozgsicvyc .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #yozgsicvyc .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #yozgsicvyc .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #yozgsicvyc .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #yozgsicvyc .gt_left { text-align: left; }
 #yozgsicvyc .gt_center { text-align: center; }
 #yozgsicvyc .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #yozgsicvyc .gt_font_normal { font-weight: normal; }
 #yozgsicvyc .gt_font_bold { font-weight: bold; }
 #yozgsicvyc .gt_font_italic { font-style: italic; }
 #yozgsicvyc .gt_super { font-size: 65%; }
 #yozgsicvyc .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #yozgsicvyc .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #yozgsicvyc .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #yozgsicvyc .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #yozgsicvyc .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #yozgsicvyc .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Published-surface sanity — 2025        |            |
|----------------------------------------|------------|
| render-time check                      | value      |
| 2025 plays with vegas_wp               | 45,862.000 |
| mean vegas_wp (possession perspective) | 0.504      |

&#10;</div>

## Limitations

WPA — the first difference of WP — is intrinsically noisy: small
per-play WP movements are dominated by model variance, so single-play
WPA is a directional signal, not a precise quantity (the `wpa` parity
ceiling of ≈0.89 is exactly this — see [Parity](parity.md)). The spread
input is a pregame number; the model does not re-estimate a live spread.
Overtime and end-of-half edge cases are handled by the construction
pipeline upstream, not the model head.

## Provenance

| field | value |
|----|----|
| `model_type` | wp_spread |
| `objective` | binary:logistic |
| `features` | 12 (see above) |
| `label` | label (possession team wins) |
| `training_seasons` | 1999–2025 |
| `n_training_rows` | 1,268,220 |
| `hyperparameters` | eta=0.05, max_depth=5 |
| `lineage` | nflfastR spread-WP model · nflverse `fastrmodels` (Ben Baldwin) |
| `parity` | `vegas_wp` r 0.998 · `wpa` r ≈0.89 (SNR ceiling) |
| `artifact` | `models/wp_spread.ubj` (committed; also on `nfl_model_artifacts`) |
| `rebuild this doc` | `scripts/render_model_docs.sh` (Quarto → GFM; `uv sync --group docs`) |

## Avenues for improvement & open issues

- **Line movement** — the model sees a static spread; closing-line or
  in-week movement would sharpen early-game WP.
- **Known issue:** `spread_time`’s decay exponent (-4.0) is a fitted
  constant frozen in model_vars — it must travel with any retrain.
