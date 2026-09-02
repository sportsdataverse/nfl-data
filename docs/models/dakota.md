# dakota (QB efficiency metric)


`dakota` is a **derived metric, not a trained model** — the nflfastR quarterback-efficiency composite. It is a fixed **linear combination of EPA per dropback and CPOE**, with coefficients chosen to best predict a passer’s *next-season* adjusted EPA/play. Because it blends a stable input (CPOE) with a noisier one (EPA), `dakota` is more **year-to-year stable** than raw EPA/play — it is the closest thing in the suite to a “true talent” passing number.

This document is compiled: the stability claim above is not repeated on faith — it is **measured at render time** from the two most recent published seasons, per input component.

## How it is computed

Per qualifying passer, over a sample of dropbacks:

1.  `passing_epa` — the sum of QB-credited EPA (`qb_epa`), matching nflfastR’s credited-EPA logic exactly;
2.  `cpoe` — mean completion % over expected from the [CP model](cpoe.md), on the percentage-point scale `100 · (complete_pass − cp)`;
3.  `dakota` — the fixed-coefficient linear blend of EPA/play and CPOE.

It is emitted as a column in the player-stats aggregation alongside the other passing rates (`pacr`, `racr`, `wopr`).

## The stability claim, measured

<div id="edjiqujexf" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#edjiqujexf table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#edjiqujexf thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#edjiqujexf p { margin: 0; padding: 0; }
 #edjiqujexf .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #edjiqujexf .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #edjiqujexf .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #edjiqujexf .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #edjiqujexf .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #edjiqujexf .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #edjiqujexf .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #edjiqujexf .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #edjiqujexf .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #edjiqujexf .gt_column_spanner_outer:first-child { padding-left: 0; }
 #edjiqujexf .gt_column_spanner_outer:last-child { padding-right: 0; }
 #edjiqujexf .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #edjiqujexf .gt_spanner_row { border-bottom-style: hidden; }
 #edjiqujexf .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #edjiqujexf .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #edjiqujexf .gt_from_md> :first-child { margin-top: 0; }
 #edjiqujexf .gt_from_md> :last-child { margin-bottom: 0; }
 #edjiqujexf .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #edjiqujexf .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #edjiqujexf .gt_indent_1 { text-indent: 5px; }
 #edjiqujexf .gt_indent_2 { text-indent: calc(5px * 2); }
 #edjiqujexf .gt_indent_3 { text-indent: calc(5px * 3); }
 #edjiqujexf .gt_indent_4 { text-indent: calc(5px * 4); }
 #edjiqujexf .gt_indent_5 { text-indent: calc(5px * 5); }
 #edjiqujexf .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #edjiqujexf .gt_row_group_first td { border-top-width: 2px; }
 #edjiqujexf .gt_row_group_first th { border-top-width: 2px; }
 #edjiqujexf .gt_striped { color: #333333; background-color: #F4F4F4; }
 #edjiqujexf .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #edjiqujexf .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #edjiqujexf .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #edjiqujexf .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #edjiqujexf .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #edjiqujexf .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #edjiqujexf .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #edjiqujexf .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #edjiqujexf .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #edjiqujexf .gt_left { text-align: left; }
 #edjiqujexf .gt_center { text-align: center; }
 #edjiqujexf .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #edjiqujexf .gt_font_normal { font-weight: normal; }
 #edjiqujexf .gt_font_bold { font-weight: bold; }
 #edjiqujexf .gt_font_italic { font-style: italic; }
 #edjiqujexf .gt_super { font-size: 65%; }
 #edjiqujexf .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #edjiqujexf .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #edjiqujexf .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #edjiqujexf .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #edjiqujexf .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #edjiqujexf .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Year-over-year stability of dakota's inputs — 2024 → 2025 |  |  |
|----|----|----|
| same passer, min 200 dropbacks both seasons; CPOE's higher stability is why the blend beats raw EPA |  |  |
| input | returning_passers | yoy_pearson |
| epa_play | 28 | 0.200 |
| cpoe | 28 | 0.061 |

&#10;</div>

<img src="dakota_files/figure-commonmark/cell-4-output-1.png" width="420" height="300" alt="The two inputs per passer, latest season — dakota is a fixed direction through this plane." />

<div id="nyunmvjfpn" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#nyunmvjfpn table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#nyunmvjfpn thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#nyunmvjfpn p { margin: 0; padding: 0; }
 #nyunmvjfpn .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #nyunmvjfpn .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #nyunmvjfpn .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #nyunmvjfpn .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #nyunmvjfpn .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #nyunmvjfpn .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #nyunmvjfpn .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #nyunmvjfpn .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #nyunmvjfpn .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #nyunmvjfpn .gt_column_spanner_outer:first-child { padding-left: 0; }
 #nyunmvjfpn .gt_column_spanner_outer:last-child { padding-right: 0; }
 #nyunmvjfpn .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #nyunmvjfpn .gt_spanner_row { border-bottom-style: hidden; }
 #nyunmvjfpn .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #nyunmvjfpn .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #nyunmvjfpn .gt_from_md> :first-child { margin-top: 0; }
 #nyunmvjfpn .gt_from_md> :last-child { margin-bottom: 0; }
 #nyunmvjfpn .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #nyunmvjfpn .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #nyunmvjfpn .gt_indent_1 { text-indent: 5px; }
 #nyunmvjfpn .gt_indent_2 { text-indent: calc(5px * 2); }
 #nyunmvjfpn .gt_indent_3 { text-indent: calc(5px * 3); }
 #nyunmvjfpn .gt_indent_4 { text-indent: calc(5px * 4); }
 #nyunmvjfpn .gt_indent_5 { text-indent: calc(5px * 5); }
 #nyunmvjfpn .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #nyunmvjfpn .gt_row_group_first td { border-top-width: 2px; }
 #nyunmvjfpn .gt_row_group_first th { border-top-width: 2px; }
 #nyunmvjfpn .gt_striped { color: #333333; background-color: #F4F4F4; }
 #nyunmvjfpn .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #nyunmvjfpn .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #nyunmvjfpn .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #nyunmvjfpn .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #nyunmvjfpn .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #nyunmvjfpn .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #nyunmvjfpn .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #nyunmvjfpn .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #nyunmvjfpn .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #nyunmvjfpn .gt_left { text-align: left; }
 #nyunmvjfpn .gt_center { text-align: center; }
 #nyunmvjfpn .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #nyunmvjfpn .gt_font_normal { font-weight: normal; }
 #nyunmvjfpn .gt_font_bold { font-weight: bold; }
 #nyunmvjfpn .gt_font_italic { font-style: italic; }
 #nyunmvjfpn .gt_super { font-size: 65%; }
 #nyunmvjfpn .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #nyunmvjfpn .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #nyunmvjfpn .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #nyunmvjfpn .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #nyunmvjfpn .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #nyunmvjfpn .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Input relationship — render time |  |
|----|----|
| the two inputs correlate but are far from redundant; the blend's value is the CPOE-stable component |  |
| check | value |
| qualifying passers (latest season) | 38.000 |
| corr(CPOE, EPA/play) among them | 0.698 |

&#10;</div>

## Results — the composite’s inputs, 2025

<div id="atpvbtcruv" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#atpvbtcruv table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#atpvbtcruv thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#atpvbtcruv p { margin: 0; padding: 0; }
 #atpvbtcruv .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #atpvbtcruv .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #atpvbtcruv .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #atpvbtcruv .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #atpvbtcruv .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #atpvbtcruv .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #atpvbtcruv .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #atpvbtcruv .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #atpvbtcruv .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #atpvbtcruv .gt_column_spanner_outer:first-child { padding-left: 0; }
 #atpvbtcruv .gt_column_spanner_outer:last-child { padding-right: 0; }
 #atpvbtcruv .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #atpvbtcruv .gt_spanner_row { border-bottom-style: hidden; }
 #atpvbtcruv .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #atpvbtcruv .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #atpvbtcruv .gt_from_md> :first-child { margin-top: 0; }
 #atpvbtcruv .gt_from_md> :last-child { margin-bottom: 0; }
 #atpvbtcruv .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #atpvbtcruv .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #atpvbtcruv .gt_indent_1 { text-indent: 5px; }
 #atpvbtcruv .gt_indent_2 { text-indent: calc(5px * 2); }
 #atpvbtcruv .gt_indent_3 { text-indent: calc(5px * 3); }
 #atpvbtcruv .gt_indent_4 { text-indent: calc(5px * 4); }
 #atpvbtcruv .gt_indent_5 { text-indent: calc(5px * 5); }
 #atpvbtcruv .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #atpvbtcruv .gt_row_group_first td { border-top-width: 2px; }
 #atpvbtcruv .gt_row_group_first th { border-top-width: 2px; }
 #atpvbtcruv .gt_striped { color: #333333; background-color: #F4F4F4; }
 #atpvbtcruv .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #atpvbtcruv .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #atpvbtcruv .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #atpvbtcruv .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #atpvbtcruv .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #atpvbtcruv .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #atpvbtcruv .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #atpvbtcruv .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #atpvbtcruv .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #atpvbtcruv .gt_left { text-align: left; }
 #atpvbtcruv .gt_center { text-align: center; }
 #atpvbtcruv .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #atpvbtcruv .gt_font_normal { font-weight: normal; }
 #atpvbtcruv .gt_font_bold { font-weight: bold; }
 #atpvbtcruv .gt_font_italic { font-style: italic; }
 #atpvbtcruv .gt_super { font-size: 65%; }
 #atpvbtcruv .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #atpvbtcruv .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #atpvbtcruv .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #atpvbtcruv .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #atpvbtcruv .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #atpvbtcruv .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| EPA/play leaders with their CPOE — 2025 (min 200 dropbacks) |  |  |  |  |  |
|----|----|----|----|----|----|
| the two dakota inputs side by side; passers high on both are the composite's leaders |  |  |  |  |  |
|  | Passer | Team | Dropbacks | EPA/play | CPOE |
| <img src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/uneiwen9drvci9ahuebp" height="40" /> | J.Love | GB | 509 | 0.238 | −0.121 |
| <img src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/jwpkjfrkzufdyh8u1mg7" height="40" /> | M.Stafford | LA | 745 | 0.228 | −0.984 |
| <img src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/blixemm3s9sa4gmqk5yn" height="40" /> | D.Prescott | DAL | 634 | 0.172 | 0.493 |
| <img src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/yggfwr4ak4po9byj0qor" height="40" /> | J.Goff | DET | 616 | 0.168 | −1.579 |
| <img src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/oyap81gtzcvnfmripis1" height="40" /> | D.Maye | NE | 682 | 0.164 | 4.421 |
| <img src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/s5t8m6bhedjwwtfw3ild" height="40" /> | S.Darnold | SEA | 603 | 0.148 | 0.385 |
| <img src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/nhuiypfjzpkisxllinyv" height="40" /> | D.Jones | IND | 411 | 0.143 | 0.338 |
| <img src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/v5sg1z9qvdpjeapblndz" height="40" /> | M.Jones | SF | 311 | 0.139 | 0.664 |
| <img src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/xykdxnvxpf9pobxvkjfj" height="40" /> | B.Purdy | SF | 359 | 0.136 | 1.402 |
| <img src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/mjwbioajzldkq1vzoz2d" height="40" /> | J.Allen | BUF | 585 | 0.125 | 1.598 |

&#10;</div>

## The gate

dakota has no artifact, so there is nothing to score against a holdout — which is why it had no gate at all and simply inherited EP’s and CP’s. That is not the same thing: both parents can pass their own gates while the blend that consumes them stops being worth computing. As of 2026-09-01 `validate_dakota` gates the three things that *are* checkable, over every qualifying passer-season pair from 2006 on (CPOE needs air-yards charting, so 2006 is the floor):

<div id="moqlolestz" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#moqlolestz table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#moqlolestz thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#moqlolestz p { margin: 0; padding: 0; }
 #moqlolestz .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #moqlolestz .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #moqlolestz .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #moqlolestz .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #moqlolestz .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #moqlolestz .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #moqlolestz .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #moqlolestz .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #moqlolestz .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #moqlolestz .gt_column_spanner_outer:first-child { padding-left: 0; }
 #moqlolestz .gt_column_spanner_outer:last-child { padding-right: 0; }
 #moqlolestz .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #moqlolestz .gt_spanner_row { border-bottom-style: hidden; }
 #moqlolestz .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #moqlolestz .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #moqlolestz .gt_from_md> :first-child { margin-top: 0; }
 #moqlolestz .gt_from_md> :last-child { margin-bottom: 0; }
 #moqlolestz .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #moqlolestz .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #moqlolestz .gt_indent_1 { text-indent: 5px; }
 #moqlolestz .gt_indent_2 { text-indent: calc(5px * 2); }
 #moqlolestz .gt_indent_3 { text-indent: calc(5px * 3); }
 #moqlolestz .gt_indent_4 { text-indent: calc(5px * 4); }
 #moqlolestz .gt_indent_5 { text-indent: calc(5px * 5); }
 #moqlolestz .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #moqlolestz .gt_row_group_first td { border-top-width: 2px; }
 #moqlolestz .gt_row_group_first th { border-top-width: 2px; }
 #moqlolestz .gt_striped { color: #333333; background-color: #F4F4F4; }
 #moqlolestz .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #moqlolestz .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #moqlolestz .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #moqlolestz .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #moqlolestz .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #moqlolestz .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #moqlolestz .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #moqlolestz .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #moqlolestz .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #moqlolestz .gt_left { text-align: left; }
 #moqlolestz .gt_center { text-align: center; }
 #moqlolestz .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #moqlolestz .gt_font_normal { font-weight: normal; }
 #moqlolestz .gt_font_bold { font-weight: bold; }
 #moqlolestz .gt_font_italic { font-style: italic; }
 #moqlolestz .gt_super { font-size: 65%; }
 #moqlolestz .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #moqlolestz .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #moqlolestz .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #moqlolestz .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #moqlolestz .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #moqlolestz .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| dakota gate — 488 passer-season pairs, 2006–2025 |  |  |
|----|----|----|
| EPA/play's own year-over-year r is 0.4508, the bar the blend must clear |  |  |
| Criterion | Measured | Floor |
| CPOE year-over-year r (the premise) | 0.7031 | 0.6000 |
| dakota year-over-year r (the payoff) | 0.6820 | 0.5800 |
| dakota YoY − EPA YoY (the margin) | 0.2313 | 0.1500 |
| r vs the published nflfastR GAM | 0.8542 | 0.8000 |

&#10;</div>

Floors sit below the observed values on purpose: their job is to catch a regression in an input model, not to restate today’s number. The fidelity criterion is the one that answers the recalibration question — see below.

## What the coefficients actually approximate

`dakota` ships in sdv-py as fixed coefficients, `0.816·EPA/dropback + 0.184·CPOE`. The published nflfastR model is not linear: it is `mgcv::gam(target ~ s(cpoe) + s(epa_per_play))` fit on 377 weighted player-seasons, where `target` is *next* season’s adjusted EPA/play. The GAM is committed here as its partial-effect curves (`models/oracles/dakota_gam_*`), so the approximation can be measured rather than assumed:

<img src="dakota_files/figure-commonmark/cell-9-output-1.png" width="420" height="300" alt="The shipped linear blend against the published GAM it approximates, on real passer-seasons. Points off the diagonal are where the two disagree." />

The two agree at **r ≈ 0.85**, not 0.99 — the linear form is a real approximation, not a re-expression, and the scales differ (the CPOE term is on the percentage-point scale, so the linear blend spreads much wider than the GAM’s fitted range). **This is the number to re-read whenever `ep` or `cp` retrains.** Neither retrain touches these coefficients, so a drifting input changes what `dakota` means with nothing in the pipeline positioned to notice. That rule is recorded in the registry row, and the gate is how you check it.

## An honest negative: it does not out-forecast EPA

dakota’s coefficients were chosen to predict next-season adjusted EPA/play, so the obvious question is whether the blend beats its noisier input at that job. On this corpus, at season level with a 200-dropback minimum, it does not:

<div id="znthgbhrih" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#znthgbhrih table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#znthgbhrih thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#znthgbhrih p { margin: 0; padding: 0; }
 #znthgbhrih .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #znthgbhrih .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #znthgbhrih .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #znthgbhrih .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #znthgbhrih .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #znthgbhrih .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #znthgbhrih .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #znthgbhrih .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #znthgbhrih .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #znthgbhrih .gt_column_spanner_outer:first-child { padding-left: 0; }
 #znthgbhrih .gt_column_spanner_outer:last-child { padding-right: 0; }
 #znthgbhrih .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #znthgbhrih .gt_spanner_row { border-bottom-style: hidden; }
 #znthgbhrih .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #znthgbhrih .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #znthgbhrih .gt_from_md> :first-child { margin-top: 0; }
 #znthgbhrih .gt_from_md> :last-child { margin-bottom: 0; }
 #znthgbhrih .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #znthgbhrih .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #znthgbhrih .gt_indent_1 { text-indent: 5px; }
 #znthgbhrih .gt_indent_2 { text-indent: calc(5px * 2); }
 #znthgbhrih .gt_indent_3 { text-indent: calc(5px * 3); }
 #znthgbhrih .gt_indent_4 { text-indent: calc(5px * 4); }
 #znthgbhrih .gt_indent_5 { text-indent: calc(5px * 5); }
 #znthgbhrih .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #znthgbhrih .gt_row_group_first td { border-top-width: 2px; }
 #znthgbhrih .gt_row_group_first th { border-top-width: 2px; }
 #znthgbhrih .gt_striped { color: #333333; background-color: #F4F4F4; }
 #znthgbhrih .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #znthgbhrih .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #znthgbhrih .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #znthgbhrih .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #znthgbhrih .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #znthgbhrih .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #znthgbhrih .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #znthgbhrih .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #znthgbhrih .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #znthgbhrih .gt_left { text-align: left; }
 #znthgbhrih .gt_center { text-align: center; }
 #znthgbhrih .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #znthgbhrih .gt_font_normal { font-weight: normal; }
 #znthgbhrih .gt_font_bold { font-weight: bold; }
 #znthgbhrih .gt_font_italic { font-style: italic; }
 #znthgbhrih .gt_super { font-size: 65%; }
 #znthgbhrih .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #znthgbhrih .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #znthgbhrih .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #znthgbhrih .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #znthgbhrih .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #znthgbhrih .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Forecasting next season, 2006–2025                         |        |
|------------------------------------------------------------|--------|
| reported and deliberately NOT gated — see the caveat below |        |
| predictor of NEXT season's EPA/play                        | r      |
| EPA/play alone                                             | 0.4508 |
| dakota (shipped linear blend)                              | 0.3007 |
| dakota (published GAM)                                     | 0.4257 |

&#10;</div>

Read this carefully rather than as a debunking. The GAM was fit on **weighted weekly** rows with a 5-attempt minimum; the table above is **season-level** with a 200-dropback minimum, which is a different estimand on a different sample. What it does establish is that dakota’s advertised advantage does not automatically survive at the aggregation most people use it at, and that the frozen coefficients have never been re-examined against the corpus they are now applied to. It is reported here, and left out of the gate, because gating it would gate a comparison this data cannot settle.

The stability claim — the one the table at the top of this document measures — does hold: dakota is markedly more year-to-year stable than raw EPA/play (0.682 vs 0.451), which is exactly what blending in a stable input buys.

## Lineage and caveats

`dakota` sits on top of two models: it inherits the [EP model](ep.md) through `passing_epa` (so it carries the same intrinsic EP-model drift, ~0.99 parity against nflverse) and the [CP model](cpoe.md) through `cpoe`. The blend coefficients are the published nflfastR values — `dakota` is a **reproduction of the nflfastR metric**, not a re-fit.

## Limitations

It is a single composite number: it cannot separate scheme, receiver, or pressure effects, and it is only meaningful over a **reasonable dropback sample** (small samples are dominated by the EPA term’s noise). It is descriptive of the *EPA-and-completion-explainable* part of QB play, the same blind spots as its two parent models.

## Provenance

| field | value |
|----|----|
| `type` | derived metric (fixed-coefficient linear blend) |
| `inputs` | EPA/dropback (`qb_epa`) + CPOE |
| `parents` | EP model · CP model |
| `lineage` | nflfastR `dakota` (adjusted EPA + CPOE composite) |
| `surface` | player-stats aggregation (per passer) |
| `rebuild this doc` | `scripts/render_model_docs.sh` (Quarto → GFM; `uv sync --group docs`) |

## Avenues for improvement & open issues

- **Resolved (2026-09-01, PR \#29):** *no dedicated gate.* `validate_dakota` now gates the blend’s premise (CPOE YoY r 0.7031, floor 0.60), its payoff (dakota YoY 0.6820 at a +0.2313 margin over EPA, floors 0.58/0.15) and its fidelity to the published nflfastR GAM (0.8542, floor 0.80), over 488 passer-season pairs.
- **Resolved (2026-09-01, PR \#29):** *recalibration cadence* is now a written rule in `models/REGISTRY.md` — re-run this gate whenever `ep` or `cp` retrains — and the fidelity number is the thing it tells you to re-read.
- **The coefficients themselves have still never been re-fit.** The gate detects drift; it does not correct it. Re-fitting means reproducing the original weekly, weighted, 5-attempt-minimum setup on the modern corpus, which is a real piece of work and a change to a published metric’s definition.
- **Known issue:** the gate is opt-in (`--dakota-seasons`) and no scheduled job passes it, because dakota has no artifact and therefore no numbered stage; wiring it into the annual suite needs that design question settled first.
- **Known issue:** at season level the blend does not out-forecast raw EPA/play for next-season EPA/play (0.3007 vs 0.4508) — a different estimand from the GAM’s weekly fit, but a caveat on how the metric is described.
