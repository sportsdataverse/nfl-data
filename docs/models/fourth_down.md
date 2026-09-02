# Fourth-Down Yards (`fd_model`)


The fourth-down yards model predicts the **distribution of yards gained** on a go-for-it (or third-down) attempt — the core of the **nfl4th** decision surface. From the 76-class gain distribution we derive P(first down) for any distance-to-go, then combine it with the EP/WP surfaces to compute the **go / punt / field-goal / two-point** expected-value comparison. It is a faithful Python retrain of nfl4th’s go-for-it model, validated against the converted nflverse artifact.

This document is compiled: the conversion-probability curve is derived from the released booster at render time (summing class probabilities over the distance-to-go), and compared with the latest published season’s **empirical** 4th-down conversion rates.

## Model features

**14 features**; one row per 3rd/4th-down scrimmage play (1999–2025, `qb_kneel==0`, `week<=17`). The label is `yards_gained` clamped to **\[−10, 65\]** and shifted into **76 ordinal classes** (`label = yards_gained + 10`).

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

**Algorithm.** XGBoost, `objective=multi:softprob` over **76 classes**, **1,124 rounds**, `eta=0.01`, `max_depth=2`, `gamma=2`, `subsample=0.8`, `colsample_bytree=0.8`, `min_child_weight=0.8` — verbatim from the nfl4th R recipe. P(first down) for any distance-to-go is recovered by summing class probabilities for gains ≥ the distance.

**Evaluation.** Parity against the converted nflverse artifact: **mean-gain correlation 0.9856** (informational — era-aware full-history retrain vs the nfl4th 2014–19 oracle) — see [Parity](parity.md).

## P(convert) vs reality, render time

<img src="fourth_down_files/figure-commonmark/cell-4-output-1.png" width="420" height="300" alt="Model P(convert) at midfield (neutral spread, era4) vs realized 2025 4th-down conversion rates — selection effects push the empirical curve above the unconditional model." />

Teams *choose* which 4th downs to attempt, so the realized curve reflects selection (coaches go when they like the matchup) while the model curve is the unconditional estimate at a fixed neutral state — the gap between them is selection, not error. That distinction is the whole reason the decision layer values options with a model rather than empirical rates.

## The decision surface in use — 2025

The published pbp carries the nfl4th-style decision columns (`go_wp_diff`, `fg_wp_diff`, `punt_wp_diff`) plus `fourth_down_recommendation`.

**Read the `*_wp_diff` columns carefully**: each is that option’s WP *minus the best option’s*, so every one of them is `<= 0` and the recommended option is the one sitting at exactly `0`. A `go_wp_diff > 0` test is therefore always false — it is never satisfied on any play in any season — and a table built on it silently reports “the model never says go” plus an agreement rate that is really just the share of 4th downs teams did not go for. This document made that mistake until 2026-09-01. The unambiguous column is `fourth_down_recommendation`, which matches `go_wp_diff == 0` exactly (2025: 2,004 of 2,004; 2024: 1,860 of 1,860), so it is what the tables below use.

<div id="djrugxgwkg" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#djrugxgwkg table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#djrugxgwkg thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#djrugxgwkg p { margin: 0; padding: 0; }
 #djrugxgwkg .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #djrugxgwkg .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #djrugxgwkg .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #djrugxgwkg .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #djrugxgwkg .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #djrugxgwkg .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #djrugxgwkg .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #djrugxgwkg .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #djrugxgwkg .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #djrugxgwkg .gt_column_spanner_outer:first-child { padding-left: 0; }
 #djrugxgwkg .gt_column_spanner_outer:last-child { padding-right: 0; }
 #djrugxgwkg .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #djrugxgwkg .gt_spanner_row { border-bottom-style: hidden; }
 #djrugxgwkg .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #djrugxgwkg .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #djrugxgwkg .gt_from_md> :first-child { margin-top: 0; }
 #djrugxgwkg .gt_from_md> :last-child { margin-bottom: 0; }
 #djrugxgwkg .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #djrugxgwkg .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #djrugxgwkg .gt_indent_1 { text-indent: 5px; }
 #djrugxgwkg .gt_indent_2 { text-indent: calc(5px * 2); }
 #djrugxgwkg .gt_indent_3 { text-indent: calc(5px * 3); }
 #djrugxgwkg .gt_indent_4 { text-indent: calc(5px * 4); }
 #djrugxgwkg .gt_indent_5 { text-indent: calc(5px * 5); }
 #djrugxgwkg .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #djrugxgwkg .gt_row_group_first td { border-top-width: 2px; }
 #djrugxgwkg .gt_row_group_first th { border-top-width: 2px; }
 #djrugxgwkg .gt_striped { color: #333333; background-color: #F4F4F4; }
 #djrugxgwkg .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #djrugxgwkg .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #djrugxgwkg .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #djrugxgwkg .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #djrugxgwkg .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #djrugxgwkg .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #djrugxgwkg .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #djrugxgwkg .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #djrugxgwkg .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #djrugxgwkg .gt_left { text-align: left; }
 #djrugxgwkg .gt_center { text-align: center; }
 #djrugxgwkg .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #djrugxgwkg .gt_font_normal { font-weight: normal; }
 #djrugxgwkg .gt_font_bold { font-weight: bold; }
 #djrugxgwkg .gt_font_italic { font-style: italic; }
 #djrugxgwkg .gt_super { font-size: 65%; }
 #djrugxgwkg .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #djrugxgwkg .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #djrugxgwkg .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #djrugxgwkg .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #djrugxgwkg .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #djrugxgwkg .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Decision layer vs coaches — 2025 season |  |
|----|----|
| the model recommends going on ~47% of 4th downs; teams go on ~21% |  |
| check | value |
| 4th downs with a recommendation | 4,290.000 |
| model says GO | 2,004.000 |
| teams actually went | 932.000 |
| went WHEN the model says go | 0.398 |
| went when the model says kick | 0.059 |
| coach–model agreement rate | 0.687 |

&#10;</div>

## Coach-indexed decision calibration, 2021–2025

League-wide agreement hides the thing the decision surface is actually used to argue about, which is that coaches differ. Indexing by the coach on the sideline (from the schedule’s `home_coach` / `away_coach`, assigned to whichever side had the ball) turns one number into a distribution:

<div id="tshutlxqxh" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#tshutlxqxh table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#tshutlxqxh thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#tshutlxqxh p { margin: 0; padding: 0; }
 #tshutlxqxh .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #tshutlxqxh .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #tshutlxqxh .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #tshutlxqxh .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #tshutlxqxh .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #tshutlxqxh .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #tshutlxqxh .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #tshutlxqxh .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #tshutlxqxh .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #tshutlxqxh .gt_column_spanner_outer:first-child { padding-left: 0; }
 #tshutlxqxh .gt_column_spanner_outer:last-child { padding-right: 0; }
 #tshutlxqxh .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #tshutlxqxh .gt_spanner_row { border-bottom-style: hidden; }
 #tshutlxqxh .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #tshutlxqxh .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #tshutlxqxh .gt_from_md> :first-child { margin-top: 0; }
 #tshutlxqxh .gt_from_md> :last-child { margin-bottom: 0; }
 #tshutlxqxh .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #tshutlxqxh .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #tshutlxqxh .gt_indent_1 { text-indent: 5px; }
 #tshutlxqxh .gt_indent_2 { text-indent: calc(5px * 2); }
 #tshutlxqxh .gt_indent_3 { text-indent: calc(5px * 3); }
 #tshutlxqxh .gt_indent_4 { text-indent: calc(5px * 4); }
 #tshutlxqxh .gt_indent_5 { text-indent: calc(5px * 5); }
 #tshutlxqxh .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #tshutlxqxh .gt_row_group_first td { border-top-width: 2px; }
 #tshutlxqxh .gt_row_group_first th { border-top-width: 2px; }
 #tshutlxqxh .gt_striped { color: #333333; background-color: #F4F4F4; }
 #tshutlxqxh .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #tshutlxqxh .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #tshutlxqxh .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #tshutlxqxh .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #tshutlxqxh .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #tshutlxqxh .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #tshutlxqxh .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #tshutlxqxh .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #tshutlxqxh .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #tshutlxqxh .gt_left { text-align: left; }
 #tshutlxqxh .gt_center { text-align: center; }
 #tshutlxqxh .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #tshutlxqxh .gt_font_normal { font-weight: normal; }
 #tshutlxqxh .gt_font_bold { font-weight: bold; }
 #tshutlxqxh .gt_font_italic { font-style: italic; }
 #tshutlxqxh .gt_super { font-size: 65%; }
 #tshutlxqxh .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #tshutlxqxh .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #tshutlxqxh .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #tshutlxqxh .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #tshutlxqxh .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #tshutlxqxh .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Aggressiveness on 4th down by head coach — 2021–2025 |  |  |  |  |  |  |  |
|----|----|----|----|----|----|----|----|
| top 8 and bottom 8 of 42 coaches with \>=150 decisions; league go-rate when the model says go is 36.4% |  |  |  |  |  |  |  |
|  | Coach | Dec | Model go% | Actual go% | Go when told | Go when told to kick | WP pts left / dec |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/ari.png" height="26" /> | Kliff Kingsbury | 270 | 44.4% | 26.7% | 50.0% | 8.0% | 0.296 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/chi.png" height="26" /> | Ben Johnson | 154 | 52.6% | 26.6% | 48.1% | 2.7% | 0.524 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/det.png" height="26" /> | Dan Campbell | 659 | 51.1% | 28.7% | 47.5% | 9.0% | 0.402 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/cle.png" height="26" /> | Kevin Stefanski | 765 | 39.2% | 23.5% | 46.3% | 8.8% | 0.285 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500-dark/car.png" height="26" /> | Dave Canales | 279 | 49.5% | 25.8% | 43.5% | 8.5% | 0.335 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/atl.png" height="26" /> | Raheem Morris | 261 | 43.7% | 22.6% | 43.0% | 6.8% | 0.396 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/ari.png" height="26" /> | Jonathan Gannon | 370 | 44.9% | 21.6% | 42.2% | 4.9% | 0.306 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/buf.png" height="26" /> | Sean McDermott | 591 | 46.0% | 21.7% | 41.9% | 4.4% | 0.373 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/sf.png" height="26" /> | Kyle Shanahan | 603 | 45.9% | 15.8% | 28.9% | 4.6% | 0.464 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/pit.png" height="26" /> | Mike Tomlin | 707 | 44.1% | 14.6% | 28.8% | 3.3% | 0.522 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/sea.png" height="26" /> | Mike Macdonald | 270 | 37.4% | 11.5% | 28.7% | 1.2% | 0.334 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/cin.png" height="26" /> | Zac Taylor | 649 | 46.1% | 14.6% | 28.4% | 2.9% | 0.522 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/ne.png" height="26" /> | Bill Belichick | 411 | 38.7% | 14.1% | 27.7% | 5.6% | 0.441 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/no.png" height="26" /> | Dennis Allen | 405 | 41.2% | 14.1% | 27.5% | 4.6% | 0.410 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/hou.png" height="26" /> | DeMeco Ryans | 477 | 36.5% | 13.4% | 27.0% | 5.6% | 0.346 |
| <img src="https://a.espncdn.com/i/teamlogos/nfl/500/lac.png" height="26" /> | Jim Harbaugh | 283 | 41.0% | 14.1% | 25.0% | 6.6% | 0.448 |

&#10;</div>

Three things this makes visible that the league-wide number cannot:

- **The spread is large and it is not noise.** Go-rate-when-the-model-says-go runs from 25% to 50% across coaches — the most aggressive coach in the sample goes twice as often as the most conservative *in the same recommended situations*.
- **Every coach is conservative relative to the model.** Even the top of the table converts only half of the model’s go recommendations. The gap is systematic, not a handful of outliers, which is the honest reading: either coaches price in things the model cannot see (personnel, weather, injury, job security) or the model’s go branch is optimistic. This document cannot separate those two.
- **`model_go_rate` differs by coach too**, which is a *situation* effect, not a tendency one — a coach whose team trails often faces more go-recommended 4th downs. Read `go_when_should` (a rate *within* recommended situations), not `actual_go_rate`, when comparing coaches.

The WP column is deliberately the *per-decision* average rather than a season total, so a coach with 659 decisions is not penalised against one with 154 for merely having coached more games.

## Decision surface

`fd_model` is one input to nfl4th’s 4th-down EV comparison; the others are [`fg_model`](fg.md), [`two_pt_model`](two_pt.md), the [punt distribution](punt.md), and the [nfl4th home-WP](nfl4th_wp.md). Each option’s EV is computed by mapping its outcome distribution through the WP surface and picking the highest-WP action.

## Limitations

The label is recorded `yards_gained`, which can disagree with the official result on penalty/lateral plays — label noise at the tails. The gain window is clipped to \[−10, 65\]. It predicts a *yardage distribution*, not the binary decision; the decision EV is computed downstream.

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

- **Resolved (2026-09-01, PR \#29):** *Coach-level tendencies* — decision calibration is now indexed by head coach (2021–2025, 42 coaches with \>=150 decisions). Go-rate within model-recommended situations spans 25%–50% against a 36% league rate, and every coach in the sample sits below the model.
- **Resolved (2026-09-01, PR \#29):** the decision table’s `go_wp_diff > 0` test was never satisfiable — the `*_wp_diff` columns are differences against the best option, so they are always `<= 0`. It now reads `fourth_down_recommendation`.
- **Whether the residual gap is coaches or the model** is not settled here. Every coach being conservative relative to the surface is equally consistent with coaches pricing in unobservables and with the go branch being optimistic; separating them needs a holdout on realized outcomes, not more slicing.
- **Known issue:** the 76-class yards head shares the xYAC machinery — the multiclass pred_contribs 3-D gotcha applies to any explainability pass.
