# nfl4th Decision WP (`wp_model`)


The nfl4th decision WP is a **home-perspective** win-probability model
used to value 4th-down options: each candidate outcome
([go](fourth_down.md) / [FG](fg.md) / [punt](punt.md) /
[2-pt](two_pt.md)) is mapped to a resulting game state and scored by
this model, and the highest-WP action is recommended. It is a Python
retrain of the WP model nfl4th applies for 4th-down decisions, validated
against the converted nflverse artifact.

> [!IMPORTANT]
>
> ### This is **not** the core WP suite
>
> The [core WP models](wp_spread.md) are **possession-team** WP (the
> nflfastR `wp` / `vegas_wp` surface). This is nfl4th’s **home-team**
> 11-feature WP, whose contract comes from nfl4th’s decision-WP model.
> The home-perspective transforms are ported verbatim. The two serve
> different layers — don’t cross-wire them.

This document is compiled: the importance table reads the released
booster and the decision-impact section reads the published season’s
decision columns — the surfaces this model’s scores produce — at render
time.

## Model features

**11 features**, home perspective. The label is whether the home team
won.

| Feature | What it encodes |
|----|----|
| `home_receive_2h_ko` | Home team receives the second-half kickoff. |
| `spread_time` | `home_spread · exp(−4 · elapsed_share)` — time-decayed line. |
| `home_posteam` | Home team is on offense. |
| `half_seconds_remaining` / `game_seconds_remaining` | Clock. |
| `Diff_Time_Ratio` | Score differential scaled by time. |
| `home_score_differential` | Home score margin. |
| `home_ep` | Home-perspective expected points (links to the EP model). |
| `ydstogo` | Yards to go. |
| `home_yardline_100` | Home-perspective field position. |
| `home_timeouts_remaining` | Home timeouts left. |

## The model

**Algorithm.** XGBoost, `objective=binary:logistic`, `eta=0.025`,
`max_depth=5`, `gamma=1`, `subsample/colsample=0.8`, **500 rounds** (a
500–2000 sweep all clears 0.99; corr-vs-oracle peaks at 500). Trained
from nfl4th’s win-probability calibration frame (the frozen tuning frame
nfl4th + nflfastR read).

**Evaluation.** Parity P(win) corr **0.9947** (gate ≥0.99) — see
[Parity](parity.md).

## Feature importance

<div id="geyioikujm" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#geyioikujm table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#geyioikujm thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#geyioikujm p { margin: 0; padding: 0; }
 #geyioikujm .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #geyioikujm .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #geyioikujm .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #geyioikujm .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #geyioikujm .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #geyioikujm .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #geyioikujm .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #geyioikujm .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #geyioikujm .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #geyioikujm .gt_column_spanner_outer:first-child { padding-left: 0; }
 #geyioikujm .gt_column_spanner_outer:last-child { padding-right: 0; }
 #geyioikujm .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #geyioikujm .gt_spanner_row { border-bottom-style: hidden; }
 #geyioikujm .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #geyioikujm .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #geyioikujm .gt_from_md> :first-child { margin-top: 0; }
 #geyioikujm .gt_from_md> :last-child { margin-bottom: 0; }
 #geyioikujm .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #geyioikujm .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #geyioikujm .gt_indent_1 { text-indent: 5px; }
 #geyioikujm .gt_indent_2 { text-indent: calc(5px * 2); }
 #geyioikujm .gt_indent_3 { text-indent: calc(5px * 3); }
 #geyioikujm .gt_indent_4 { text-indent: calc(5px * 4); }
 #geyioikujm .gt_indent_5 { text-indent: calc(5px * 5); }
 #geyioikujm .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #geyioikujm .gt_row_group_first td { border-top-width: 2px; }
 #geyioikujm .gt_row_group_first th { border-top-width: 2px; }
 #geyioikujm .gt_striped { color: #333333; background-color: #F4F4F4; }
 #geyioikujm .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #geyioikujm .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #geyioikujm .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #geyioikujm .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #geyioikujm .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #geyioikujm .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #geyioikujm .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #geyioikujm .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #geyioikujm .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #geyioikujm .gt_left { text-align: left; }
 #geyioikujm .gt_center { text-align: center; }
 #geyioikujm .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #geyioikujm .gt_font_normal { font-weight: normal; }
 #geyioikujm .gt_font_bold { font-weight: bold; }
 #geyioikujm .gt_font_italic { font-style: italic; }
 #geyioikujm .gt_super { font-size: 65%; }
 #geyioikujm .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #geyioikujm .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #geyioikujm .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #geyioikujm .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #geyioikujm .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #geyioikujm .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Features by gain — released nfl4th decision-WP booster |         |
|--------------------------------------------------------|---------|
| feature                                                | gain    |
| home_score_differential                                | 1,050.3 |
| Diff_Time_Ratio                                        | 865.3   |
| spread_time                                            | 333.2   |
| home_posteam                                           | 168.4   |
| home_ep                                                | 117.7   |
| game_seconds_remaining                                 | 62.2    |
| home_yardline_100                                      | 43.2    |
| home_receive_2h_ko                                     | 35.5    |
| home_timeouts_remaining                                | 29.2    |
| half_seconds_remaining                                 | 21.4    |
| ydstogo                                                | 7.2     |

&#10;</div>

## What its scores decide — 2025 season

The published pbp carries the decision layer’s outputs — per-option WP
deltas scored by this model. Their distribution is the model’s footprint
on the season:

<img src="nfl4th_wp_files/figure-commonmark/cell-4-output-1.png"
width="420" height="300"
alt="Distribution of the go-vs-best-alternative WP delta on 2025 4th downs — mass near zero means most 4th downs are genuinely close calls." />

<div id="zliyrzunye" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#zliyrzunye table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#zliyrzunye thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#zliyrzunye p { margin: 0; padding: 0; }
 #zliyrzunye .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #zliyrzunye .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #zliyrzunye .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #zliyrzunye .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #zliyrzunye .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #zliyrzunye .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #zliyrzunye .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #zliyrzunye .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #zliyrzunye .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #zliyrzunye .gt_column_spanner_outer:first-child { padding-left: 0; }
 #zliyrzunye .gt_column_spanner_outer:last-child { padding-right: 0; }
 #zliyrzunye .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #zliyrzunye .gt_spanner_row { border-bottom-style: hidden; }
 #zliyrzunye .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #zliyrzunye .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #zliyrzunye .gt_from_md> :first-child { margin-top: 0; }
 #zliyrzunye .gt_from_md> :last-child { margin-bottom: 0; }
 #zliyrzunye .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #zliyrzunye .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #zliyrzunye .gt_indent_1 { text-indent: 5px; }
 #zliyrzunye .gt_indent_2 { text-indent: calc(5px * 2); }
 #zliyrzunye .gt_indent_3 { text-indent: calc(5px * 3); }
 #zliyrzunye .gt_indent_4 { text-indent: calc(5px * 4); }
 #zliyrzunye .gt_indent_5 { text-indent: calc(5px * 5); }
 #zliyrzunye .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #zliyrzunye .gt_row_group_first td { border-top-width: 2px; }
 #zliyrzunye .gt_row_group_first th { border-top-width: 2px; }
 #zliyrzunye .gt_striped { color: #333333; background-color: #F4F4F4; }
 #zliyrzunye .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #zliyrzunye .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #zliyrzunye .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #zliyrzunye .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #zliyrzunye .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #zliyrzunye .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #zliyrzunye .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #zliyrzunye .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #zliyrzunye .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #zliyrzunye .gt_left { text-align: left; }
 #zliyrzunye .gt_center { text-align: center; }
 #zliyrzunye .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #zliyrzunye .gt_font_normal { font-weight: normal; }
 #zliyrzunye .gt_font_bold { font-weight: bold; }
 #zliyrzunye .gt_font_italic { font-style: italic; }
 #zliyrzunye .gt_super { font-size: 65%; }
 #zliyrzunye .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #zliyrzunye .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #zliyrzunye .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #zliyrzunye .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #zliyrzunye .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #zliyrzunye .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| High-leverage GO situations — 2025 |  |
|----|----|
| the classic nfl4th finding: coaches still leave WP on the table in clear-go spots |  |
| check | value |
| 4th downs where GO is worth \> 3 pts of WP | 0.000 |
| of those, teams actually went | 0.000 |
| conversion rate when they went | <na> |

&#10;</div>

## Limitations

It is the **decision-layer** WP, tuned to reproduce nfl4th’s
recommendations, not a general-purpose live WP feed — for that use the
[core WP](wp_spread.md). It inherits the home-perspective framing and
the EP model’s drift through `home_ep`.

## Provenance

| field | value |
|----|----|
| `model_type` | wp (nfl4th home-perspective) |
| `objective` | binary:logistic |
| `features` | 11 (home perspective) |
| `label` | home team won |
| `hyperparameters` | eta=0.025, max_depth=5, nrounds=500 |
| `lineage` | nfl4th decision-WP model |
| `parity` | P(win) corr 0.9947 (gate ≥0.99) |
| `distribution` | `nfl_4th_down_models` release |
| `rebuild this doc` | `scripts/render_model_docs.sh` (Quarto → GFM; `uv sync --group docs`) |

## Avenues for improvement & open issues

- **Unify with the main WP family** — the nfl4th contract keeps a
  separate home-perspective model; folding it into the spread family
  would remove a dual-maintenance surface.
- **Resolved (2026-09-01, PR \#28) — the silent skip:** a missing
  `cal_data.rds` now fails the stage / `train-all` (rc 1) unless
  `--allow-skip` / `--allow-missing-cal-data`, which record
  `status: SKIPPED` with the reason in `models/ledger.jsonl` and
  report.md.
- **Known issue:** the training window (2001-2020) still lags the main
  models; extending it needs the calibration frame rebuilt from current
  `model_pbp` (with `ep` and `Winner`) and the P(win) parity floor
  re-derived — not lowered.
