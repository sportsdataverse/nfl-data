# Expected Pass (`xpass_model`)


The expected-pass model estimates the probability that a scrimmage play
is a **dropback (pass)** given pre-snap game state — a measure of how
*predictable* an offense’s tendency is. It is the nflfastR xpass
surface, where **`pass_oe = 100 · (pass − xpass)`** is the pass-rate
over expected: positive when an offense passes more than
situation-average. A full-history (1999–2025) retrain following the
nflverse dropback recipe.

This document is compiled: the calibration and team-tendency sections
evaluate the published `xpass` / `pass_oe` columns on the latest
`nfl_model_pbp` season at render time.

## Model features

**19 features**, pre-snap; one row per scrimmage play (1999–2025). The
binary label is `pass` (dropback). Note it consumes the [WP
surfaces](wp_spread.md) (`wp`, `vegas_wp`) as features.

| Feature | What it encodes |
|----|----|
| `down`, `ydstogo`, `yardline_100`, `qtr` | Down/distance/field position/quarter — the tendency backbone. |
| `wp`, `vegas_wp` | In-game win probability (game-script urgency). |
| `score_differential`, `half_seconds_remaining` | Score/clock context. |
| `home` | Possession team is home. |
| `posteam_timeouts_remaining`, `defteam_timeouts_remaining` | Timeouts. |
| `era0`..`era4` | Rule-era one-hot (cuts 2001/2005/2013/2017) — era-aware across all of 1999–2025. |
| `outdoors`, `retractable`, `dome` | Stadium-type one-hots. |

## The model

**Algorithm.** XGBoost, `objective=binary:logistic`, **1,121 rounds**,
`eta=0.015`, `gamma=2`, `max_depth=7`, `min_child_weight=0.9`,
`subsample/colsample=0.8`, `base_score=mean(label)`, `seed=2013` —
verbatim from the nflverse dropback-model recipe. The predicted
probability is `xpass`; **`pass_oe = 100 · (pass − xpass)`** is the
actionable residual.

**Evaluation.** Full-history retrain on 892,122 plays.
Parity-vs-nflverse is **informational** (the nflverse oracle trains on
2006+): P(pass) corr **0.989** — see [Parity](parity.md).

## Feature importance

<div id="zxiiggpkas" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#zxiiggpkas table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#zxiiggpkas thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#zxiiggpkas p { margin: 0; padding: 0; }
 #zxiiggpkas .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #zxiiggpkas .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #zxiiggpkas .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #zxiiggpkas .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #zxiiggpkas .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #zxiiggpkas .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #zxiiggpkas .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #zxiiggpkas .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #zxiiggpkas .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #zxiiggpkas .gt_column_spanner_outer:first-child { padding-left: 0; }
 #zxiiggpkas .gt_column_spanner_outer:last-child { padding-right: 0; }
 #zxiiggpkas .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #zxiiggpkas .gt_spanner_row { border-bottom-style: hidden; }
 #zxiiggpkas .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #zxiiggpkas .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #zxiiggpkas .gt_from_md> :first-child { margin-top: 0; }
 #zxiiggpkas .gt_from_md> :last-child { margin-bottom: 0; }
 #zxiiggpkas .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #zxiiggpkas .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #zxiiggpkas .gt_indent_1 { text-indent: 5px; }
 #zxiiggpkas .gt_indent_2 { text-indent: calc(5px * 2); }
 #zxiiggpkas .gt_indent_3 { text-indent: calc(5px * 3); }
 #zxiiggpkas .gt_indent_4 { text-indent: calc(5px * 4); }
 #zxiiggpkas .gt_indent_5 { text-indent: calc(5px * 5); }
 #zxiiggpkas .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #zxiiggpkas .gt_row_group_first td { border-top-width: 2px; }
 #zxiiggpkas .gt_row_group_first th { border-top-width: 2px; }
 #zxiiggpkas .gt_striped { color: #333333; background-color: #F4F4F4; }
 #zxiiggpkas .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #zxiiggpkas .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #zxiiggpkas .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #zxiiggpkas .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #zxiiggpkas .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #zxiiggpkas .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #zxiiggpkas .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #zxiiggpkas .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #zxiiggpkas .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #zxiiggpkas .gt_left { text-align: left; }
 #zxiiggpkas .gt_center { text-align: center; }
 #zxiiggpkas .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #zxiiggpkas .gt_font_normal { font-weight: normal; }
 #zxiiggpkas .gt_font_bold { font-weight: bold; }
 #zxiiggpkas .gt_font_italic { font-style: italic; }
 #zxiiggpkas .gt_super { font-size: 65%; }
 #zxiiggpkas .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #zxiiggpkas .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #zxiiggpkas .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #zxiiggpkas .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #zxiiggpkas .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #zxiiggpkas .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Top 12 features by gain — bundled xpass booster |       |
|-------------------------------------------------|-------|
| feature                                         | gain  |
| down                                            | 308.5 |
| ydstogo                                         | 210.9 |
| qtr                                             | 88.1  |
| wp                                              | 77.0  |
| half_seconds_remaining                          | 51.6  |
| posteam_timeouts_remaining                      | 26.7  |
| yardline_100                                    | 25.7  |
| score_differential                              | 24.8  |
| defteam_timeouts_remaining                      | 20.4  |
| vegas_wp                                        | 19.5  |
| era4                                            | 17.8  |
| home                                            | 12.3  |

&#10;</div>

## Calibration — render time, published surface

The published season carries `xpass` and `pass_oe` on every scrimmage
play, and the realized dropback indicator is recoverable exactly as
`pass = xpass + pass_oe/100`. Binned reliability of the applied surface:

<img src="xpass_files/figure-commonmark/cell-4-output-1.png" width="420"
height="300"
alt="Reliability of the published xpass surface, 2025 — predicted dropback probability vs realized dropback rate." />

<div id="viulbayhye" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#viulbayhye table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#viulbayhye thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#viulbayhye p { margin: 0; padding: 0; }
 #viulbayhye .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #viulbayhye .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #viulbayhye .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #viulbayhye .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #viulbayhye .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #viulbayhye .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #viulbayhye .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #viulbayhye .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #viulbayhye .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #viulbayhye .gt_column_spanner_outer:first-child { padding-left: 0; }
 #viulbayhye .gt_column_spanner_outer:last-child { padding-right: 0; }
 #viulbayhye .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #viulbayhye .gt_spanner_row { border-bottom-style: hidden; }
 #viulbayhye .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #viulbayhye .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #viulbayhye .gt_from_md> :first-child { margin-top: 0; }
 #viulbayhye .gt_from_md> :last-child { margin-bottom: 0; }
 #viulbayhye .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #viulbayhye .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #viulbayhye .gt_indent_1 { text-indent: 5px; }
 #viulbayhye .gt_indent_2 { text-indent: calc(5px * 2); }
 #viulbayhye .gt_indent_3 { text-indent: calc(5px * 3); }
 #viulbayhye .gt_indent_4 { text-indent: calc(5px * 4); }
 #viulbayhye .gt_indent_5 { text-indent: calc(5px * 5); }
 #viulbayhye .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #viulbayhye .gt_row_group_first td { border-top-width: 2px; }
 #viulbayhye .gt_row_group_first th { border-top-width: 2px; }
 #viulbayhye .gt_striped { color: #333333; background-color: #F4F4F4; }
 #viulbayhye .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #viulbayhye .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #viulbayhye .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #viulbayhye .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #viulbayhye .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #viulbayhye .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #viulbayhye .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #viulbayhye .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #viulbayhye .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #viulbayhye .gt_left { text-align: left; }
 #viulbayhye .gt_center { text-align: center; }
 #viulbayhye .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #viulbayhye .gt_font_normal { font-weight: normal; }
 #viulbayhye .gt_font_bold { font-weight: bold; }
 #viulbayhye .gt_font_italic { font-style: italic; }
 #viulbayhye .gt_super { font-size: 65%; }
 #viulbayhye .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #viulbayhye .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #viulbayhye .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #viulbayhye .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #viulbayhye .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #viulbayhye .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Render-time xpass evaluation — 2025 |             |
|-------------------------------------|-------------|
| metric                              | value       |
| plays                               | 34,504.0000 |
| realized dropback rate              | 0.5692      |
| Brier (xpass)                       | 0.1927      |
| baseline Brier (constant rate)      | 0.2452      |

&#10;</div>

## Results — team tendency, 2025

<div id="ptsjlcidck" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#ptsjlcidck table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#ptsjlcidck thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#ptsjlcidck p { margin: 0; padding: 0; }
 #ptsjlcidck .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #ptsjlcidck .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #ptsjlcidck .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #ptsjlcidck .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #ptsjlcidck .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #ptsjlcidck .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #ptsjlcidck .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #ptsjlcidck .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #ptsjlcidck .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #ptsjlcidck .gt_column_spanner_outer:first-child { padding-left: 0; }
 #ptsjlcidck .gt_column_spanner_outer:last-child { padding-right: 0; }
 #ptsjlcidck .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #ptsjlcidck .gt_spanner_row { border-bottom-style: hidden; }
 #ptsjlcidck .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #ptsjlcidck .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #ptsjlcidck .gt_from_md> :first-child { margin-top: 0; }
 #ptsjlcidck .gt_from_md> :last-child { margin-bottom: 0; }
 #ptsjlcidck .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #ptsjlcidck .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #ptsjlcidck .gt_indent_1 { text-indent: 5px; }
 #ptsjlcidck .gt_indent_2 { text-indent: calc(5px * 2); }
 #ptsjlcidck .gt_indent_3 { text-indent: calc(5px * 3); }
 #ptsjlcidck .gt_indent_4 { text-indent: calc(5px * 4); }
 #ptsjlcidck .gt_indent_5 { text-indent: calc(5px * 5); }
 #ptsjlcidck .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #ptsjlcidck .gt_row_group_first td { border-top-width: 2px; }
 #ptsjlcidck .gt_row_group_first th { border-top-width: 2px; }
 #ptsjlcidck .gt_striped { color: #333333; background-color: #F4F4F4; }
 #ptsjlcidck .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #ptsjlcidck .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #ptsjlcidck .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #ptsjlcidck .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #ptsjlcidck .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #ptsjlcidck .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #ptsjlcidck .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #ptsjlcidck .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #ptsjlcidck .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #ptsjlcidck .gt_left { text-align: left; }
 #ptsjlcidck .gt_center { text-align: center; }
 #ptsjlcidck .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #ptsjlcidck .gt_font_normal { font-weight: normal; }
 #ptsjlcidck .gt_font_bold { font-weight: bold; }
 #ptsjlcidck .gt_font_italic { font-style: italic; }
 #ptsjlcidck .gt_super { font-size: 65%; }
 #ptsjlcidck .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #ptsjlcidck .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #ptsjlcidck .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #ptsjlcidck .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #ptsjlcidck .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #ptsjlcidck .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Most pass-happy and most run-heavy over expectation — 2025 |  |  |  |  |
|----|----|----|----|----|
| pass_oe = percentage points of dropback rate over the situation-expected rate |  |  |  |  |
|  | Offense | Plays | Pass rate | PROE |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/la.png"
height="36" /> | LA | 1,261 | 58.8% | 2.37 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/cin.png"
height="36" /> | CIN | 1,044 | 64.5% | 1.08 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/ari.png"
height="36" /> | ARI | 1,070 | 66.1% | 0.55 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/kc.png"
height="36" /> | KC | 1,045 | 60.1% | −0.78 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/den.png"
height="36" /> | DEN | 1,197 | 59.7% | −1.40 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/car.png"
height="36" /> | CAR | 1,054 | 56.0% | −7.90 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/nyg.png"
height="36" /> | NYG | 1,075 | 53.3% | −8.93 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/was.png"
height="36" /> | WAS | 972 | 51.4% | −10.88 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/bal.png"
height="36" /> | BAL | 954 | 48.6% | −12.50 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/nyj.png"
height="36" /> | NYJ | 1,001 | 55.0% | −13.97 |

&#10;</div>

## Limitations

xpass is **pre-snap**: no personnel, formation, motion, or no-huddle
signal, so it captures the situation-explainable part of tendency only.
Two offenses in identical game state get the same xpass — the *team*
tendency lives in `pass_oe`, not in xpass itself.

## Provenance

| field | value |
|----|----|
| `model_type` | xpass |
| `objective` | binary:logistic |
| `features` | 19 (era0..4 + `wp` / `vegas_wp`) |
| `label` | pass (dropback) |
| `training_seasons` | 1999–2025 (892,122 plays) |
| `hyperparameters` | eta=0.015, max_depth=7, nrounds=1121 |
| `lineage` | nflverse dropback model |
| `parity` | P(pass) corr 0.989 (informational; full-history vs nflverse 2006+) |
| `distribution` | bundled in sportsdataverse |
| `rebuild this doc` | `scripts/render_model_docs.sh` (Quarto → GFM; `uv sync --group docs`) |

## Avenues for improvement & open issues

- **Motion/personnel data** — the known ceiling-lifter absent from
  public pbp.
- **Known issue:** era one-hots make the earliest seasons the reference
  class; a new era needs an explicit dummy, not silent absorption.
