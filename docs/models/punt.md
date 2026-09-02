# Punt Outcome Distribution (`punt_data`)


The punt surface is an **empirical landing distribution** — *not* a
trained model — giving, for each pre-punt field position, the
distribution of resulting field positions (plus block / return-TD / muff
probabilities). It powers the **punt branch** of the [nfl4th
decision](fourth_down.md): the post-punt field position distribution is
mapped through the WP surface to value punting. It is a Python builder
reproducing nfl4th’s punt distribution, validated against the converted
nflverse distribution.

This document is compiled: the surface below is plotted from the bundled
`punt_data.parquet` artifact at render time, and the expected-net
section holds its implied net punt distance against the latest published
season’s actual punts.

## How it is built

From PBP punts: per punt,
`yardline_after = yardline_100 − kick_distance + return_yards` (end-zone
→ 20; blocked → `yardline_100`; capped to \[1, 100\]). Flags: `blocked`,
`return_td (= yardline_after == 100)`,
`muff (= fumble_lost, 0 if blocked)`. Then, **grouped by
`yardline_100`** (and filtered to `yardline_100 > 30`):

1.  coarse-bin the muffed / blocked / return-TD percentages;
2.  a 2-D KDE (`scipy.stats.gaussian_kde`) over
    `(yardline_100, yardline_after)` excluding blocked + return-TD rows,
    normalized per snap yardline;
3.  re-insert block (`yardline_after = 999 → yardline_100`) and TD
    (`= 100`) rows rescaled by `1 − (block + td)`;
4.  duplicate rows for `muff ∈ {0, 1}` weighted by the bin muff rate;
    renormalize.

Output columns: `yardline_100`, `yardline_after`, `pct`, `muff`.

## The surface

<img src="punt_files/figure-commonmark/cell-3-output-1.png" width="420"
height="300"
alt="The bundled punt landing distribution: P(resulting opponent field position | snap yardline)." />

<img src="punt_files/figure-commonmark/cell-4-output-1.png" width="420"
height="300"
alt="Expected net field-position change implied by the surface vs snap yardline, with the touchback shelf visible near midfield." />

## Evaluation

Distributional parity against the converted nflverse distribution via
**total-variation (TV) distance** per snap yardline (KDE bandwidth
causes small, expected divergence): **freq-weighted TV 0.0652** (gate
≤0.10), mean TV 0.0944, median 0.0599. See [Parity](parity.md).

A render-time reality check against the latest published season’s punts
— mean realized net (kick distance minus return) vs the surface’s
expectation over the same snap positions:

<div id="nofjqflqfo" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#nofjqflqfo table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#nofjqflqfo thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#nofjqflqfo p { margin: 0; padding: 0; }
 #nofjqflqfo .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #nofjqflqfo .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #nofjqflqfo .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #nofjqflqfo .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #nofjqflqfo .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #nofjqflqfo .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #nofjqflqfo .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #nofjqflqfo .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #nofjqflqfo .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #nofjqflqfo .gt_column_spanner_outer:first-child { padding-left: 0; }
 #nofjqflqfo .gt_column_spanner_outer:last-child { padding-right: 0; }
 #nofjqflqfo .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #nofjqflqfo .gt_spanner_row { border-bottom-style: hidden; }
 #nofjqflqfo .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #nofjqflqfo .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #nofjqflqfo .gt_from_md> :first-child { margin-top: 0; }
 #nofjqflqfo .gt_from_md> :last-child { margin-bottom: 0; }
 #nofjqflqfo .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #nofjqflqfo .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #nofjqflqfo .gt_indent_1 { text-indent: 5px; }
 #nofjqflqfo .gt_indent_2 { text-indent: calc(5px * 2); }
 #nofjqflqfo .gt_indent_3 { text-indent: calc(5px * 3); }
 #nofjqflqfo .gt_indent_4 { text-indent: calc(5px * 4); }
 #nofjqflqfo .gt_indent_5 { text-indent: calc(5px * 5); }
 #nofjqflqfo .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #nofjqflqfo .gt_row_group_first td { border-top-width: 2px; }
 #nofjqflqfo .gt_row_group_first th { border-top-width: 2px; }
 #nofjqflqfo .gt_striped { color: #333333; background-color: #F4F4F4; }
 #nofjqflqfo .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #nofjqflqfo .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #nofjqflqfo .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #nofjqflqfo .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #nofjqflqfo .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #nofjqflqfo .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #nofjqflqfo .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #nofjqflqfo .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #nofjqflqfo .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #nofjqflqfo .gt_left { text-align: left; }
 #nofjqflqfo .gt_center { text-align: center; }
 #nofjqflqfo .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #nofjqflqfo .gt_font_normal { font-weight: normal; }
 #nofjqflqfo .gt_font_bold { font-weight: bold; }
 #nofjqflqfo .gt_font_italic { font-style: italic; }
 #nofjqflqfo .gt_super { font-size: 65%; }
 #nofjqflqfo .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #nofjqflqfo .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #nofjqflqfo .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #nofjqflqfo .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #nofjqflqfo .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #nofjqflqfo .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Render-time punt-surface check — 2025 season snap mix |          |
|-------------------------------------------------------|----------|
| check                                                 | value    |
| 2025 punts (snap \> 30)                               | 2,031.00 |
| surface-expected resulting yardline (2025 snap mix)   | 25.05    |

&#10;</div>

## The gate against reality

The TV comparison above answers “does this reproduce nfl4th”. It cannot
answer “does this still describe how punts land”, and the decision layer
depends on the second. As of 2026-09-01 the surface carries a second,
independent gate (`validate_punt_holdout`) that scores it against
realized landings:

<div id="zltcbwmbyc" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#zltcbwmbyc table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#zltcbwmbyc thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#zltcbwmbyc p { margin: 0; padding: 0; }
 #zltcbwmbyc .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #zltcbwmbyc .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #zltcbwmbyc .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #zltcbwmbyc .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #zltcbwmbyc .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #zltcbwmbyc .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #zltcbwmbyc .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #zltcbwmbyc .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #zltcbwmbyc .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #zltcbwmbyc .gt_column_spanner_outer:first-child { padding-left: 0; }
 #zltcbwmbyc .gt_column_spanner_outer:last-child { padding-right: 0; }
 #zltcbwmbyc .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #zltcbwmbyc .gt_spanner_row { border-bottom-style: hidden; }
 #zltcbwmbyc .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #zltcbwmbyc .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #zltcbwmbyc .gt_from_md> :first-child { margin-top: 0; }
 #zltcbwmbyc .gt_from_md> :last-child { margin-bottom: 0; }
 #zltcbwmbyc .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #zltcbwmbyc .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #zltcbwmbyc .gt_indent_1 { text-indent: 5px; }
 #zltcbwmbyc .gt_indent_2 { text-indent: calc(5px * 2); }
 #zltcbwmbyc .gt_indent_3 { text-indent: calc(5px * 3); }
 #zltcbwmbyc .gt_indent_4 { text-indent: calc(5px * 4); }
 #zltcbwmbyc .gt_indent_5 { text-indent: calc(5px * 5); }
 #zltcbwmbyc .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #zltcbwmbyc .gt_row_group_first td { border-top-width: 2px; }
 #zltcbwmbyc .gt_row_group_first th { border-top-width: 2px; }
 #zltcbwmbyc .gt_striped { color: #333333; background-color: #F4F4F4; }
 #zltcbwmbyc .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #zltcbwmbyc .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #zltcbwmbyc .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #zltcbwmbyc .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #zltcbwmbyc .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #zltcbwmbyc .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #zltcbwmbyc .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #zltcbwmbyc .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #zltcbwmbyc .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #zltcbwmbyc .gt_left { text-align: left; }
 #zltcbwmbyc .gt_center { text-align: center; }
 #zltcbwmbyc .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #zltcbwmbyc .gt_font_normal { font-weight: normal; }
 #zltcbwmbyc .gt_font_bold { font-weight: bold; }
 #zltcbwmbyc .gt_font_italic { font-style: italic; }
 #zltcbwmbyc .gt_super { font-size: 65%; }
 #zltcbwmbyc .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #zltcbwmbyc .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #zltcbwmbyc .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #zltcbwmbyc .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #zltcbwmbyc .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #zltcbwmbyc .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Punt surface vs realized landings |  |  |  |  |  |  |  |  |
|----|----|----|----|----|----|----|----|----|
| gate: freq-weighted KS \<= 0.22, \|mean landing gap\| \<= 3.5 yd |  |  |  |  |  |  |  |  |
| Window | Punts | Yardlines | KS (freq-wt) | TV (freq-wt) | Surface | Realized | Gap (yd) | Passes |
| 2010–2014 | 12,796 | 64 | 0.0874 | 0.2157 | 25.73 | 25.46 | 0.27 | True |
| 2020–2025 | 12,983 | 62 | 0.1223 | 0.2307 | 25.45 | 23.32 | 2.12 | True |
| 2023–2025 (gate window) | 6,511 | 55 | 0.1466 | 0.2824 | 24.86 | 22.39 | 2.48 | True |
| 2024 alone | 2,119 | 43 | 0.1881 | 0.4105 | 23.61 | 20.84 | 2.77 | True |

&#10;</div>

**Why KS and not TV.** The surface is a smooth KDE over ~50 discrete
landing spots per snap yardline, but a single season puts only ~45 punts
on each yardline, so the empirical mass is spiky. TV sums pointwise
differences and is therefore dominated by that discreteness — it reads
0.39 on one season against 0.23 pooled, on a surface whose *CDF* tracks
reality to 0.12. KS compares CDFs and is not fooled by where a sparse
sample falls inside a bin, so KS is the gate and TV is reported
alongside.

**The finding the gate exposes.** The surface is systematically
optimistic about where the returning team ends up, and the gap is
growing: 0.27 yards on 2010–2014, 2.12 pooled over 2020–2025, 2.77 in
2024 alone. Modern coverage pins returners deeper than a full-history
surface says. That is inside the band and is documented rather than
gated away — the ceiling was set above the worst observed value
precisely so it detects a *regression* rather than re-flagging drift
already described here. If the gap keeps widening, the honest response
is a recency-weighted rebuild, not a wider band.

## Limitations

It is a **league-average empirical surface** — no punter identity, hang
time, or coverage. KDE smoothing slightly blurs the per-yardline landing
spread (the TV residual). Snap positions inside the 30 are excluded
(where a punt is rarely the decision). Because the artifact is fitted on
the full history, the reality check above is a *recency* check rather
than out-of-sample generalization: the gate window’s seasons are inside
the training span, so it detects “the surface no longer describes recent
punting”, which is the failure that matters here.

## Provenance

| field | value |
|----|----|
| `model_type` | punt_data (empirical distribution, not a model) |
| `columns` | yardline_100, yardline_after, pct, muff |
| `build` | 2-D Gaussian KDE over punt landings, per snap yardline |
| `lineage` | nfl4th punt model |
| `parity` | freq-weighted TV 0.105 (informational; full-history vs nfl4th 2010–19) |
| `distribution` | bundled in sportsdataverse (`punt_data.parquet`) |
| `rebuild this doc` | `scripts/render_model_docs.sh` (Quarto → GFM; `uv sync --group docs`) |

## Avenues for improvement & open issues

- **Resolved (2026-09-01, PR \#29):** *it now has a gate of its own.*
  `validate_punt_holdout` scores the surface against realized landings
  (freq-weighted KS \<= 0.22, \|mean landing gap\| \<= 3.5 yd) and runs
  inside stage 11 alongside the oracle parity gate; both must pass.
  Errors no longer surface only through the 4th-down decision
  calibration.
- **The surface is 2.5 yards optimistic on recent seasons and drifting**
  (0.27 yd gap on 2010-2014 vs 2.77 in 2024). A recency-weighted or
  era-aware rebuild is the real fix; the gate exists to notice if it
  gets worse.
- **Returner identity and directional punting** are absent.
  `punt_returner_player_id` is in the pbp so a returner effect on the
  *return* component is tractable; direction is not published anywhere.
  This matters more than it looks – some of the drift above is plausibly
  returner/coverage era, and separating them would say whether the
  surface needs a rebuild or a covariate.
- **Known issue:** the gate window sits inside the training span (the
  artifact is full-history), so it is a recency check, not out-of-sample
  generalization.
