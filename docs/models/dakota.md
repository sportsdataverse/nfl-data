# dakota (QB efficiency metric)


`dakota` is a **derived metric, not a trained model** — the nflfastR
quarterback-efficiency composite. It is a fixed **linear combination of
EPA per dropback and CPOE**, with coefficients chosen to best predict a
passer’s *next-season* adjusted EPA/play. Because it blends a stable
input (CPOE) with a noisier one (EPA), `dakota` is more **year-to-year
stable** than raw EPA/play — it is the closest thing in the suite to a
“true talent” passing number.

This document is compiled: the stability claim above is not repeated on
faith — it is **measured at render time** from the two most recent
published seasons, per input component.

## How it is computed

Per qualifying passer, over a sample of dropbacks:

1.  `passing_epa` — the sum of QB-credited EPA (`qb_epa`), matching
    nflfastR’s credited-EPA logic exactly;
2.  `cpoe` — mean completion % over expected from the [CP
    model](cpoe.md), on the percentage-point scale
    `100 · (complete_pass − cp)`;
3.  `dakota` — the fixed-coefficient linear blend of EPA/play and CPOE.

It is emitted as a column in the player-stats aggregation alongside the
other passing rates (`pacr`, `racr`, `wopr`).

## The stability claim, measured

<div id="cjnljxyiin" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#cjnljxyiin table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#cjnljxyiin thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#cjnljxyiin p { margin: 0; padding: 0; }
 #cjnljxyiin .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #cjnljxyiin .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #cjnljxyiin .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #cjnljxyiin .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #cjnljxyiin .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #cjnljxyiin .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #cjnljxyiin .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #cjnljxyiin .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #cjnljxyiin .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #cjnljxyiin .gt_column_spanner_outer:first-child { padding-left: 0; }
 #cjnljxyiin .gt_column_spanner_outer:last-child { padding-right: 0; }
 #cjnljxyiin .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #cjnljxyiin .gt_spanner_row { border-bottom-style: hidden; }
 #cjnljxyiin .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #cjnljxyiin .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #cjnljxyiin .gt_from_md> :first-child { margin-top: 0; }
 #cjnljxyiin .gt_from_md> :last-child { margin-bottom: 0; }
 #cjnljxyiin .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #cjnljxyiin .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #cjnljxyiin .gt_indent_1 { text-indent: 5px; }
 #cjnljxyiin .gt_indent_2 { text-indent: calc(5px * 2); }
 #cjnljxyiin .gt_indent_3 { text-indent: calc(5px * 3); }
 #cjnljxyiin .gt_indent_4 { text-indent: calc(5px * 4); }
 #cjnljxyiin .gt_indent_5 { text-indent: calc(5px * 5); }
 #cjnljxyiin .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #cjnljxyiin .gt_row_group_first td { border-top-width: 2px; }
 #cjnljxyiin .gt_row_group_first th { border-top-width: 2px; }
 #cjnljxyiin .gt_striped { color: #333333; background-color: #F4F4F4; }
 #cjnljxyiin .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #cjnljxyiin .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #cjnljxyiin .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #cjnljxyiin .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #cjnljxyiin .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #cjnljxyiin .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #cjnljxyiin .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #cjnljxyiin .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #cjnljxyiin .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #cjnljxyiin .gt_left { text-align: left; }
 #cjnljxyiin .gt_center { text-align: center; }
 #cjnljxyiin .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #cjnljxyiin .gt_font_normal { font-weight: normal; }
 #cjnljxyiin .gt_font_bold { font-weight: bold; }
 #cjnljxyiin .gt_font_italic { font-style: italic; }
 #cjnljxyiin .gt_super { font-size: 65%; }
 #cjnljxyiin .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #cjnljxyiin .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #cjnljxyiin .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #cjnljxyiin .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #cjnljxyiin .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #cjnljxyiin .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Year-over-year stability of dakota's inputs — 2024 → 2025 |  |  |
|----|----|----|
| same passer, min 200 dropbacks both seasons; CPOE's higher stability is why the blend beats raw EPA |  |  |
| input | returning_passers | yoy_pearson |
| epa_play | 28 | 0.200 |
| cpoe | 28 | 0.061 |

&#10;</div>

<img src="dakota_files/figure-commonmark/cell-4-output-1.png"
width="420" height="300"
alt="The two inputs per passer, latest season — dakota is a fixed direction through this plane." />

<div id="xpgfqfduul" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#xpgfqfduul table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#xpgfqfduul thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#xpgfqfduul p { margin: 0; padding: 0; }
 #xpgfqfduul .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #xpgfqfduul .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #xpgfqfduul .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #xpgfqfduul .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #xpgfqfduul .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #xpgfqfduul .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #xpgfqfduul .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #xpgfqfduul .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #xpgfqfduul .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #xpgfqfduul .gt_column_spanner_outer:first-child { padding-left: 0; }
 #xpgfqfduul .gt_column_spanner_outer:last-child { padding-right: 0; }
 #xpgfqfduul .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #xpgfqfduul .gt_spanner_row { border-bottom-style: hidden; }
 #xpgfqfduul .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #xpgfqfduul .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #xpgfqfduul .gt_from_md> :first-child { margin-top: 0; }
 #xpgfqfduul .gt_from_md> :last-child { margin-bottom: 0; }
 #xpgfqfduul .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #xpgfqfduul .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #xpgfqfduul .gt_indent_1 { text-indent: 5px; }
 #xpgfqfduul .gt_indent_2 { text-indent: calc(5px * 2); }
 #xpgfqfduul .gt_indent_3 { text-indent: calc(5px * 3); }
 #xpgfqfduul .gt_indent_4 { text-indent: calc(5px * 4); }
 #xpgfqfduul .gt_indent_5 { text-indent: calc(5px * 5); }
 #xpgfqfduul .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #xpgfqfduul .gt_row_group_first td { border-top-width: 2px; }
 #xpgfqfduul .gt_row_group_first th { border-top-width: 2px; }
 #xpgfqfduul .gt_striped { color: #333333; background-color: #F4F4F4; }
 #xpgfqfduul .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #xpgfqfduul .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #xpgfqfduul .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #xpgfqfduul .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #xpgfqfduul .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #xpgfqfduul .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #xpgfqfduul .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #xpgfqfduul .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #xpgfqfduul .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #xpgfqfduul .gt_left { text-align: left; }
 #xpgfqfduul .gt_center { text-align: center; }
 #xpgfqfduul .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #xpgfqfduul .gt_font_normal { font-weight: normal; }
 #xpgfqfduul .gt_font_bold { font-weight: bold; }
 #xpgfqfduul .gt_font_italic { font-style: italic; }
 #xpgfqfduul .gt_super { font-size: 65%; }
 #xpgfqfduul .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #xpgfqfduul .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #xpgfqfduul .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #xpgfqfduul .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #xpgfqfduul .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #xpgfqfduul .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Input relationship — render time |  |
|----|----|
| the two inputs correlate but are far from redundant; the blend's value is the CPOE-stable component |  |
| check | value |
| qualifying passers (latest season) | 38.000 |
| corr(CPOE, EPA/play) among them | 0.698 |

&#10;</div>

## Results — the composite’s inputs, 2025

<div id="nqlwdxapjc" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#nqlwdxapjc table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#nqlwdxapjc thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#nqlwdxapjc p { margin: 0; padding: 0; }
 #nqlwdxapjc .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #nqlwdxapjc .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #nqlwdxapjc .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #nqlwdxapjc .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #nqlwdxapjc .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #nqlwdxapjc .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #nqlwdxapjc .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #nqlwdxapjc .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #nqlwdxapjc .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #nqlwdxapjc .gt_column_spanner_outer:first-child { padding-left: 0; }
 #nqlwdxapjc .gt_column_spanner_outer:last-child { padding-right: 0; }
 #nqlwdxapjc .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #nqlwdxapjc .gt_spanner_row { border-bottom-style: hidden; }
 #nqlwdxapjc .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #nqlwdxapjc .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #nqlwdxapjc .gt_from_md> :first-child { margin-top: 0; }
 #nqlwdxapjc .gt_from_md> :last-child { margin-bottom: 0; }
 #nqlwdxapjc .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #nqlwdxapjc .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #nqlwdxapjc .gt_indent_1 { text-indent: 5px; }
 #nqlwdxapjc .gt_indent_2 { text-indent: calc(5px * 2); }
 #nqlwdxapjc .gt_indent_3 { text-indent: calc(5px * 3); }
 #nqlwdxapjc .gt_indent_4 { text-indent: calc(5px * 4); }
 #nqlwdxapjc .gt_indent_5 { text-indent: calc(5px * 5); }
 #nqlwdxapjc .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #nqlwdxapjc .gt_row_group_first td { border-top-width: 2px; }
 #nqlwdxapjc .gt_row_group_first th { border-top-width: 2px; }
 #nqlwdxapjc .gt_striped { color: #333333; background-color: #F4F4F4; }
 #nqlwdxapjc .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #nqlwdxapjc .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #nqlwdxapjc .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #nqlwdxapjc .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #nqlwdxapjc .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #nqlwdxapjc .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #nqlwdxapjc .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #nqlwdxapjc .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #nqlwdxapjc .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #nqlwdxapjc .gt_left { text-align: left; }
 #nqlwdxapjc .gt_center { text-align: center; }
 #nqlwdxapjc .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #nqlwdxapjc .gt_font_normal { font-weight: normal; }
 #nqlwdxapjc .gt_font_bold { font-weight: bold; }
 #nqlwdxapjc .gt_font_italic { font-style: italic; }
 #nqlwdxapjc .gt_super { font-size: 65%; }
 #nqlwdxapjc .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #nqlwdxapjc .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #nqlwdxapjc .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #nqlwdxapjc .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #nqlwdxapjc .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #nqlwdxapjc .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| EPA/play leaders with their CPOE — 2025 (min 200 dropbacks) |  |  |  |  |  |
|----|----|----|----|----|----|
| the two dakota inputs side by side; passers high on both are the composite's leaders |  |  |  |  |  |
|  | Passer | Team | Dropbacks | EPA/play | CPOE |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/uneiwen9drvci9ahuebp"
height="40" /> | J.Love | GB | 509 | 0.238 | −0.121 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/jwpkjfrkzufdyh8u1mg7"
height="40" /> | M.Stafford | LA | 745 | 0.228 | −0.984 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/blixemm3s9sa4gmqk5yn"
height="40" /> | D.Prescott | DAL | 634 | 0.172 | 0.493 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/yggfwr4ak4po9byj0qor"
height="40" /> | J.Goff | DET | 616 | 0.168 | −1.579 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/oyap81gtzcvnfmripis1"
height="40" /> | D.Maye | NE | 682 | 0.164 | 4.421 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/s5t8m6bhedjwwtfw3ild"
height="40" /> | S.Darnold | SEA | 603 | 0.148 | 0.385 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/nhuiypfjzpkisxllinyv"
height="40" /> | D.Jones | IND | 411 | 0.143 | 0.338 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/v5sg1z9qvdpjeapblndz"
height="40" /> | M.Jones | SF | 311 | 0.139 | 0.664 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/xykdxnvxpf9pobxvkjfj"
height="40" /> | B.Purdy | SF | 359 | 0.136 | 1.402 |
| <img
src="https://static.www.nfl.com/image/upload/%7BformatInstructions%7D/league/mjwbioajzldkq1vzoz2d"
height="40" /> | J.Allen | BUF | 585 | 0.125 | 1.598 |

&#10;</div>

## Lineage and caveats

`dakota` sits on top of two models: it inherits the [EP model](ep.md)
through `passing_epa` (so it carries the same intrinsic EP-model drift,
~0.99 parity against nflverse) and the [CP model](cpoe.md) through
`cpoe`. The blend coefficients are the published nflfastR values —
`dakota` is a **reproduction of the nflfastR metric**, not a re-fit.

## Limitations

It is a single composite number: it cannot separate scheme, receiver, or
pressure effects, and it is only meaningful over a **reasonable dropback
sample** (small samples are dominated by the EPA term’s noise). It is
descriptive of the *EPA-and-completion-explainable* part of QB play, the
same blind spots as its two parent models.

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

- **Recalibration cadence** — dakota blends EPA/CPOE; its coefficients
  should be re-examined whenever either input model is retrained.
- **Known issue:** no dedicated gate — it inherits its inputs’
  validation; the YoY table above is the standing empirical check on the
  blend’s premise.
