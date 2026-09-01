# Win Probability — naive (`wp`)


The naive Win Probability model answers *given only the game state, with
no betting-market information, how likely is the possession team to
win?* It is the spread model’s sibling — identical except it **drops
`spread_time`** — and is the nflfastR `wp` surface: the right choice
when a pregame spread is unavailable or when you explicitly want a
market-free WP.

This document is compiled: the naive-vs-spread divergence analysis below
is recomputed at render time from the latest published `nfl_model_pbp`
season, which carries both surfaces on every play.

## Model features

**11 features** — exactly the [spread model](wp_spread.md)’s set **minus
`spread_time`**: `receive_2h_ko`, `home`, `half_seconds_remaining`,
`game_seconds_remaining`, `Diff_Time_Ratio`, `score_differential`,
`down`, `ydstogo`, `yardline_100`, `posteam_timeouts_remaining`,
`defteam_timeouts_remaining`. Dropping the single market feature is the
*only* difference between the two WP heads, which is why they can be
compared head-to-head.

## The model

**Algorithm.** XGBoost, `objective=binary:logistic`, `eta=0.2`,
`max_depth=4` — the `fastrmodels` naive-WP recipe. Trained on the **full
1999–2025 history (1,268,220 plays)**, the same frame as the spread
model. The higher learning rate / shallower trees reflect that, without
the spread, there is less structured signal to fit.

**Evaluation.** nflfastR parity: `wp` correlates **r 0.997** against
nflverse (see [Parity](parity.md)). LOSO calibration uses the same
protocol as the spread model.

## Feature importance

<div id="ohdqghfujy" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#ohdqghfujy table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#ohdqghfujy thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#ohdqghfujy p { margin: 0; padding: 0; }
 #ohdqghfujy .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #ohdqghfujy .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #ohdqghfujy .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #ohdqghfujy .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #ohdqghfujy .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #ohdqghfujy .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #ohdqghfujy .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #ohdqghfujy .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #ohdqghfujy .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #ohdqghfujy .gt_column_spanner_outer:first-child { padding-left: 0; }
 #ohdqghfujy .gt_column_spanner_outer:last-child { padding-right: 0; }
 #ohdqghfujy .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #ohdqghfujy .gt_spanner_row { border-bottom-style: hidden; }
 #ohdqghfujy .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #ohdqghfujy .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #ohdqghfujy .gt_from_md> :first-child { margin-top: 0; }
 #ohdqghfujy .gt_from_md> :last-child { margin-bottom: 0; }
 #ohdqghfujy .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #ohdqghfujy .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #ohdqghfujy .gt_indent_1 { text-indent: 5px; }
 #ohdqghfujy .gt_indent_2 { text-indent: calc(5px * 2); }
 #ohdqghfujy .gt_indent_3 { text-indent: calc(5px * 3); }
 #ohdqghfujy .gt_indent_4 { text-indent: calc(5px * 4); }
 #ohdqghfujy .gt_indent_5 { text-indent: calc(5px * 5); }
 #ohdqghfujy .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #ohdqghfujy .gt_row_group_first td { border-top-width: 2px; }
 #ohdqghfujy .gt_row_group_first th { border-top-width: 2px; }
 #ohdqghfujy .gt_striped { color: #333333; background-color: #F4F4F4; }
 #ohdqghfujy .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #ohdqghfujy .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #ohdqghfujy .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #ohdqghfujy .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #ohdqghfujy .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #ohdqghfujy .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #ohdqghfujy .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #ohdqghfujy .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #ohdqghfujy .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #ohdqghfujy .gt_left { text-align: left; }
 #ohdqghfujy .gt_center { text-align: center; }
 #ohdqghfujy .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #ohdqghfujy .gt_font_normal { font-weight: normal; }
 #ohdqghfujy .gt_font_bold { font-weight: bold; }
 #ohdqghfujy .gt_font_italic { font-style: italic; }
 #ohdqghfujy .gt_super { font-size: 65%; }
 #ohdqghfujy .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #ohdqghfujy .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #ohdqghfujy .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #ohdqghfujy .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #ohdqghfujy .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #ohdqghfujy .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Features by gain — committed naive-WP booster |         |
|-----------------------------------------------|---------|
| feature                                       | gain    |
| score_differential                            | 3,206.4 |
| Diff_Time_Ratio                               | 2,884.8 |
| home                                          | 798.8   |
| yardline_100                                  | 225.3   |
| receive_2h_ko                                 | 179.8   |
| game_seconds_remaining                        | 169.8   |
| down                                          | 158.2   |
| posteam_timeouts_remaining                    | 99.3    |
| ydstogo                                       | 69.1    |
| half_seconds_remaining                        | 66.6    |
| defteam_timeouts_remaining                    | 50.8    |

&#10;</div>

Without the market prior, `score_differential`, `yardline_100` and the
clock terms carry the model from the opening kickoff — precisely why the
naive WP is least confident (closest to 0.5) early and diverges most
from the spread WP in the first quarter.

## Naive vs spread — the divergence, measured

The published season carries both surfaces on every play, so the
documented claim — *the two diverge most early and converge as
`spread_time` decays* — is directly measurable:

<img src="wp_naive_files/figure-commonmark/cell-4-output-1.png"
width="420" height="300"
alt="Mean |wp − vegas_wp| by game quarter, 2025 season — the market prior’s influence decays exactly as designed." />

<div id="jqjjwiapdb" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#jqjjwiapdb table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#jqjjwiapdb thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#jqjjwiapdb p { margin: 0; padding: 0; }
 #jqjjwiapdb .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #jqjjwiapdb .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #jqjjwiapdb .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #jqjjwiapdb .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #jqjjwiapdb .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #jqjjwiapdb .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #jqjjwiapdb .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #jqjjwiapdb .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #jqjjwiapdb .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #jqjjwiapdb .gt_column_spanner_outer:first-child { padding-left: 0; }
 #jqjjwiapdb .gt_column_spanner_outer:last-child { padding-right: 0; }
 #jqjjwiapdb .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #jqjjwiapdb .gt_spanner_row { border-bottom-style: hidden; }
 #jqjjwiapdb .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #jqjjwiapdb .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #jqjjwiapdb .gt_from_md> :first-child { margin-top: 0; }
 #jqjjwiapdb .gt_from_md> :last-child { margin-bottom: 0; }
 #jqjjwiapdb .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #jqjjwiapdb .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #jqjjwiapdb .gt_indent_1 { text-indent: 5px; }
 #jqjjwiapdb .gt_indent_2 { text-indent: calc(5px * 2); }
 #jqjjwiapdb .gt_indent_3 { text-indent: calc(5px * 3); }
 #jqjjwiapdb .gt_indent_4 { text-indent: calc(5px * 4); }
 #jqjjwiapdb .gt_indent_5 { text-indent: calc(5px * 5); }
 #jqjjwiapdb .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #jqjjwiapdb .gt_row_group_first td { border-top-width: 2px; }
 #jqjjwiapdb .gt_row_group_first th { border-top-width: 2px; }
 #jqjjwiapdb .gt_striped { color: #333333; background-color: #F4F4F4; }
 #jqjjwiapdb .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #jqjjwiapdb .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #jqjjwiapdb .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #jqjjwiapdb .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #jqjjwiapdb .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #jqjjwiapdb .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #jqjjwiapdb .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #jqjjwiapdb .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #jqjjwiapdb .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #jqjjwiapdb .gt_left { text-align: left; }
 #jqjjwiapdb .gt_center { text-align: center; }
 #jqjjwiapdb .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #jqjjwiapdb .gt_font_normal { font-weight: normal; }
 #jqjjwiapdb .gt_font_bold { font-weight: bold; }
 #jqjjwiapdb .gt_font_italic { font-style: italic; }
 #jqjjwiapdb .gt_super { font-size: 65%; }
 #jqjjwiapdb .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #jqjjwiapdb .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #jqjjwiapdb .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #jqjjwiapdb .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #jqjjwiapdb .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #jqjjwiapdb .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Naive-vs-spread divergence — render-time, 2025 |        |
|------------------------------------------------|--------|
| check                                          | value  |
| Q1 mean \|naive − spread\|                     | 0.1431 |
| Q4 mean \|naive − spread\|                     | 0.0310 |
| corr(naive, spread), all plays                 | 0.9275 |

&#10;</div>

## Limitations

Because it ignores the market, the naive model is *less sharp* early in
games: strictly less information than the spread model, so its log-loss
and Brier are worse. Use it only when you want a spread-free WP or lack
a spread; for forecast accuracy when a spread exists, prefer the [spread
model](wp_spread.md). WPA carries the same per-play noise caveat.

## Provenance

| field | value |
|----|----|
| `model_type` | wp_naive |
| `objective` | binary:logistic |
| `features` | 11 (spread set minus `spread_time`) |
| `label` | label (possession team wins) |
| `training_seasons` | 1999–2025 |
| `n_training_rows` | 1,268,220 |
| `hyperparameters` | eta=0.2, max_depth=4 |
| `lineage` | nflfastR naive-WP model · nflverse `fastrmodels` (Ben Baldwin) |
| `parity` | `wp` r 0.997 |
| `artifact` | `models/wp_naive.ubj` (committed; also on `nfl_model_artifacts`) |
| `rebuild this doc` | `scripts/render_model_docs.sh` (Quarto → GFM; `uv sync --group docs`) |

## Avenues for improvement & open issues

- Primarily a fallback when no market prior exists; improvement effort
  belongs in the spread model. **Known issue:** naive WP is
  systematically miscalibrated for large early leads relative to the
  spread model — the quarter-divergence figure above is the standing
  measurement of that delta.
