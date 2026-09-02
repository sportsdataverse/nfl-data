# nflfastR Parity


The headline validation for the NFL model suite is **parity with
nflfastR**: the models exist to *reproduce nflverse*, so the primary
gate is column-level agreement against nflfastR’s own published outputs,
not merely internal calibration.

## How parity is measured

Each model is validated against the **converted nflverse artifact as a
parity oracle**: the same plays are scored by this model and by
nflverse’s shipped model, and the public columns are correlated on the
**model domain** — kickoffs and PATs are **feature-substituted** exactly
as nflfastR does (touchback yardline 80 pre-2016 / 75 from 2016,
`down→1`, `ydstogo→10`), so the comparison is like-for-like. The parity
gate floors EP at Pearson-r 0.98 and caps WP Brier at 0.20.

## Play-level parity (lead-diff method, model domain)

| Column | Parity vs nflverse | Reading |
|----|----|----|
| `ep` | **r 0.996** | start-of-play expected points reproduces nflfastR |
| `epa` | **r 0.994** | first-difference of EP across the play |
| `wp` | **r 0.997** | spread-free in-game win probability |
| `vegas_wp` | **r 0.998** | spread-aware win probability — the tightest of the set |
| `cp` / `cpoe` | scale-correct | CPOE on the percentage-point scale `100·(complete_pass − cp)` |
| `wpa` | **r ≈ 0.89** | first-difference of WP — see ceiling note below |

## The committed LOSO metrics behind the cards

<div id="nwsgxwzpln" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#nwsgxwzpln table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#nwsgxwzpln thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#nwsgxwzpln p { margin: 0; padding: 0; }
 #nwsgxwzpln .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #nwsgxwzpln .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #nwsgxwzpln .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #nwsgxwzpln .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #nwsgxwzpln .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #nwsgxwzpln .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #nwsgxwzpln .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #nwsgxwzpln .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #nwsgxwzpln .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #nwsgxwzpln .gt_column_spanner_outer:first-child { padding-left: 0; }
 #nwsgxwzpln .gt_column_spanner_outer:last-child { padding-right: 0; }
 #nwsgxwzpln .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #nwsgxwzpln .gt_spanner_row { border-bottom-style: hidden; }
 #nwsgxwzpln .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #nwsgxwzpln .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #nwsgxwzpln .gt_from_md> :first-child { margin-top: 0; }
 #nwsgxwzpln .gt_from_md> :last-child { margin-bottom: 0; }
 #nwsgxwzpln .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #nwsgxwzpln .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #nwsgxwzpln .gt_indent_1 { text-indent: 5px; }
 #nwsgxwzpln .gt_indent_2 { text-indent: calc(5px * 2); }
 #nwsgxwzpln .gt_indent_3 { text-indent: calc(5px * 3); }
 #nwsgxwzpln .gt_indent_4 { text-indent: calc(5px * 4); }
 #nwsgxwzpln .gt_indent_5 { text-indent: calc(5px * 5); }
 #nwsgxwzpln .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #nwsgxwzpln .gt_row_group_first td { border-top-width: 2px; }
 #nwsgxwzpln .gt_row_group_first th { border-top-width: 2px; }
 #nwsgxwzpln .gt_striped { color: #333333; background-color: #F4F4F4; }
 #nwsgxwzpln .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #nwsgxwzpln .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #nwsgxwzpln .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #nwsgxwzpln .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #nwsgxwzpln .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #nwsgxwzpln .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #nwsgxwzpln .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #nwsgxwzpln .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #nwsgxwzpln .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #nwsgxwzpln .gt_left { text-align: left; }
 #nwsgxwzpln .gt_center { text-align: center; }
 #nwsgxwzpln .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #nwsgxwzpln .gt_font_normal { font-weight: normal; }
 #nwsgxwzpln .gt_font_bold { font-weight: bold; }
 #nwsgxwzpln .gt_font_italic { font-style: italic; }
 #nwsgxwzpln .gt_super { font-size: 65%; }
 #nwsgxwzpln .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #nwsgxwzpln .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #nwsgxwzpln .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #nwsgxwzpln .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #nwsgxwzpln .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #nwsgxwzpln .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| LOSO calibration metrics — read live from the committed training report |  |  |  |
|----|----|----|----|
| figures/metrics.json, seasons 1999–2025, generated 2026-06-24 |  |  |  |
| model | cal_error | brier | n |
| EP (per-class weighted) | 0.0058 | <na> | 1,195,636 |
| WP (spread) | 0.0026 | 0.1536 | 1,268,220 |
| CP | 0.0136 | 0.1919 | 339,706 |

&#10;</div>

## Fourth-down & tendency parity

The fourth-down / tendency models are **full-history (1999–2025)
era-aware retrains** (era0..era4 one-hot), so they no longer reproduce
nfl4th’s narrow-window oracles — parity here is **informational** (how
far the modern model sits from the frozen oracle), not a reproduction
gate. The decision WP is the exception: it trains on a fixed calibration
frame, so it still reproduces its oracle.

| Model | Metric | Parity | Basis |
|----|----|----|----|
| [Expected Pass](xpass.md) | P(pass) corr | **0.9895** | informational — era-aware, 1999–2025 |
| [Fourth-Down Yards](fourth_down.md) | mean-gain corr | **0.9856** | informational — era-aware, 1999–2025 |
| [Decision WP](nfl4th_wp.md) | P(win) corr | **0.9947** | reproduction — cal_data-bound (unchanged) |
| [Field Goal](fg.md) | attempted-cells corr | **0.971** (freq-wt 0.986) | informational — era-aware, 1999–2025 |
| [Two-Point](two_pt.md) | P(success) corr | **0.806** | informational — 2010–2025, vintage-drift |
| [Punt distribution](punt.md) | freq-weighted TV dist | **0.105** | informational — full-history |
| [Punt distribution](punt.md) | freq-weighted KS **vs reality** | **0.147** (≤0.22) | gate — realized landings, last 3 seasons |

## Two honest ceilings (not bugs)

**`wpa` ≈ 0.89.** `wpa` is the per-play first difference of `wp`. The
derivation is **exact** — fed nflverse’s own `wp`, the reconstruction
correlates **1.0**. The ≈0.89 against nflverse’s `wpa` is a
**signal-to-noise ceiling**: tiny per-play WP disagreements (the
residual after r-0.997 `wp` agreement) are amplified by
first-differencing.

**Two-point ≈ 0.87.** The two-point oracle was trained on a frozen
2020-era snapshot (726 rows) that current nflverse PBP has since
revised. The recipe is a verified faithful match; the residual is
irreducible without the frozen training data — the same kind of ceiling
as `wpa`.

## Parity on the rare branches

The headline table above is the aggregate. The branches that actually
break models are rare by construction, so they contribute almost nothing
to a whole-season correlation and can be badly wrong while it stays at
0.99. This section scores the same 2025 columns **within** those
branches, against the nflverse published values, and reports the sample
size beside every number because most of these are small enough that the
sample size is the finding.

<div id="lpxtjhwimu" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#lpxtjhwimu table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#lpxtjhwimu thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#lpxtjhwimu p { margin: 0; padding: 0; }
 #lpxtjhwimu .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #lpxtjhwimu .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #lpxtjhwimu .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #lpxtjhwimu .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #lpxtjhwimu .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #lpxtjhwimu .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #lpxtjhwimu .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #lpxtjhwimu .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #lpxtjhwimu .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #lpxtjhwimu .gt_column_spanner_outer:first-child { padding-left: 0; }
 #lpxtjhwimu .gt_column_spanner_outer:last-child { padding-right: 0; }
 #lpxtjhwimu .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #lpxtjhwimu .gt_spanner_row { border-bottom-style: hidden; }
 #lpxtjhwimu .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #lpxtjhwimu .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #lpxtjhwimu .gt_from_md> :first-child { margin-top: 0; }
 #lpxtjhwimu .gt_from_md> :last-child { margin-bottom: 0; }
 #lpxtjhwimu .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #lpxtjhwimu .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #lpxtjhwimu .gt_indent_1 { text-indent: 5px; }
 #lpxtjhwimu .gt_indent_2 { text-indent: calc(5px * 2); }
 #lpxtjhwimu .gt_indent_3 { text-indent: calc(5px * 3); }
 #lpxtjhwimu .gt_indent_4 { text-indent: calc(5px * 4); }
 #lpxtjhwimu .gt_indent_5 { text-indent: calc(5px * 5); }
 #lpxtjhwimu .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #lpxtjhwimu .gt_row_group_first td { border-top-width: 2px; }
 #lpxtjhwimu .gt_row_group_first th { border-top-width: 2px; }
 #lpxtjhwimu .gt_striped { color: #333333; background-color: #F4F4F4; }
 #lpxtjhwimu .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #lpxtjhwimu .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #lpxtjhwimu .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #lpxtjhwimu .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #lpxtjhwimu .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #lpxtjhwimu .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #lpxtjhwimu .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #lpxtjhwimu .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #lpxtjhwimu .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #lpxtjhwimu .gt_left { text-align: left; }
 #lpxtjhwimu .gt_center { text-align: center; }
 #lpxtjhwimu .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #lpxtjhwimu .gt_font_normal { font-weight: normal; }
 #lpxtjhwimu .gt_font_bold { font-weight: bold; }
 #lpxtjhwimu .gt_font_italic { font-style: italic; }
 #lpxtjhwimu .gt_super { font-size: 65%; }
 #lpxtjhwimu .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #lpxtjhwimu .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #lpxtjhwimu .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #lpxtjhwimu .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #lpxtjhwimu .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #lpxtjhwimu .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Parity vs nflverse within rare branches — 2025 |  |  |  |  |  |  |  |  |  |  |
|----|----|----|----|----|----|----|----|----|----|----|
| Pearson r on the plays in each branch; read n first, then the r |  |  |  |  |  |  |  |  |  |  |
| Branch | Plays | ep | epa | wp | vegas_wp | wpa | wp bias | wp MAE | ep bias | ep MAE |
| all plays | 46,631 | 0.995 | 0.990 | 0.992 | 0.994 | 0.674 | −0.0011 | 0.0152 | 0.0329 | 0.1190 |
| onside kicks | 53 | 0.917 | 0.596 | 0.221 | 0.198 | −0.679 | −0.0825 | 0.0837 | 0.0809 | 0.1213 |
| all kickoffs | 2,918 | 0.939 | 0.907 | 0.986 | 0.987 | 0.706 | −0.0073 | 0.0149 | 0.0505 | 0.1059 |
| last 2 min of a half | 6,262 | 0.981 | 0.964 | 0.990 | 0.992 | 0.706 | −0.0006 | 0.0196 | −0.0333 | 0.1854 |
| last 30 s of a half | 1,973 | 0.980 | 0.962 | 0.986 | 0.991 | 0.608 | −0.0033 | 0.0240 | −0.0621 | 0.1792 |
| last 2 min, one score | 1,999 | 0.976 | 0.953 | 0.911 | 0.927 | 0.761 | −0.0180 | 0.0581 | −0.0491 | 0.2058 |
| overtime | 309 | 0.985 | 0.972 | 0.250 | 0.380 | 0.409 | −0.1049 | 0.2132 | 0.1021 | 0.1793 |
| PATs | 1,324 | 0.090 | 0.479 | 0.887 | 0.898 | 0.065 | 0.0027 | 0.0439 | 0.1677 | 0.2919 |
| two-point tries | 130 | <na> | 0.938 | 0.967 | 0.969 | 0.705 | 0.0425 | 0.0448 | 0.1074 | 0.2463 |
| safeties | 12 | 0.979 | 0.979 | 0.999 | 1.000 | 0.923 | 0.0027 | 0.0088 | −0.0314 | 0.0875 |
| 4th downs w/ a recommendation | 4,290 | 0.993 | 0.992 | 0.993 | 0.996 | 0.721 | −0.0022 | 0.0174 | 0.0246 | 0.1349 |
| field-goal attempts | 1,140 | 0.910 | 0.977 | 0.989 | 0.995 | 0.818 | −0.0081 | 0.0216 | 0.0100 | 0.2209 |
| penalties | 3,559 | 0.997 | 0.994 | 0.994 | 0.997 | 0.794 | −0.0002 | 0.0148 | 0.0352 | 0.1078 |

&#10;</div>

How to read this, because several of these numbers look alarming and are
not:

- **Onside kicks (n = 53) and overtime (n = 309) show low `wp`
  correlation (0.22, 0.25) for a reason that is not disagreement.** Both
  branches have almost no *variance* in the quantity being correlated —
  an onside kick happens when the game is nearly decided, so every play
  in the branch sits at a similar extreme WP. Pearson r divides by that
  variance, so a branch where both models agree “this is ~0.97 for the
  leading team” scores near zero. The correlation is the wrong statistic
  on a degenerate slice, and quoting the correlation as a parity failure
  would be a mistake. But the right check on such a slice is **agreement
  in level**, which correlation cannot see — and measuring it does not
  exonerate these branches:

  | branch       | `wp` bias | `wp` MAE |
  |--------------|-----------|----------|
  | all plays    | -0.0011   | 0.0152   |
  | onside kicks | -0.0825   | 0.0837   |
  | overtime     | -0.1049   | 0.2132   |

  Onside kicks carry a systematic ~8-point WP bias, and **overtime is
  materially divergent**: its MAE is roughly 14× the all-plays figure.
  Correlation hid that, and so would the aggregate — a branch-sized
  error is invisible in a 46,000-play average. Correlation hid it, and
  so would the aggregate.

  **The overtime divergence has since been traced and fixed — see the
  next section.** The numbers above still show it because they score the
  *published* `model_pbp_2025.parquet`, which was built before the fix;
  they will move on the next republish, which is the point of leaving
  them computed.

- **PATs and two-point tries are the same artefact, deliberately.** Both
  models feature-substitute these rows (down→1, ydstogo→10, fixed
  yardline), so predicted `ep` is near-constant across the branch by
  construction — on two-point tries it is constant enough that `r` is
  **undefined** (a zero-variance side makes it 0/0), which is why that
  cell is blank rather than small. The level agreement is what remains
  meaningful, and it is tight: `ep` MAE of 0.2463 on two-point tries and
  0.2919 on PATs. `epa` on two-point tries still correlates at 0.938
  because the *outcome* varies even when the pre-play state does not.

- **The branches with real spread agree.** Penalties (n = 3,559) sit at
  0.997 / 0.994, 4th downs carrying a recommendation (n = 4,290) at
  0.993 / 0.992, and the last two minutes of a half (n = 6,262) at 0.981
  / 0.964. These are the slices where a genuine construction bug would
  show, and they do not.

- **Safeties (n = 12) are reported and should not be gated on.** Twelve
  plays is an anecdote; it is in the table so the count is visible
  rather than implied.

`wpa` sits near 0.6–0.8 in every branch for the reason the aggregate
does — it is a first difference, so it inherits amplified noise. See the
ceiling note above.

## Distributional heads: is the *shape* right, not just the mean?

`xyac_model` and `fd_model` are 76-class multinomials, but every check
in this suite scores a scalar summary of them (`xyac_mean_yardage`, mean
predicted gain). A model can nail the mean of a distribution while
getting its shape badly wrong, and nothing above would notice. This
section scores the xYAC head’s full predictive distribution.

Two proper tools, neither needing a new dependency:

- **PIT (probability integral transform)** — where the realized YAC
  falls in the predicted CDF. If the distribution is honest, PIT values
  are uniform on \[0, 1\]; a hump in the middle means over-dispersion, a
  U-shape means over-confidence. YAC is discrete, so this uses the
  *randomized* PIT (`F(y−1) + U·p(y)`), which is uniform for a correctly
  specified discrete forecast.
- **CRPS** — the proper scoring rule for a whole predictive
  distribution, reported against a climatology baseline (the empirical
  marginal YAC distribution) so the number means something.

<div id="jhnuftqkyr" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#jhnuftqkyr table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#jhnuftqkyr thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#jhnuftqkyr p { margin: 0; padding: 0; }
 #jhnuftqkyr .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #jhnuftqkyr .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #jhnuftqkyr .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #jhnuftqkyr .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #jhnuftqkyr .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #jhnuftqkyr .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #jhnuftqkyr .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #jhnuftqkyr .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #jhnuftqkyr .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #jhnuftqkyr .gt_column_spanner_outer:first-child { padding-left: 0; }
 #jhnuftqkyr .gt_column_spanner_outer:last-child { padding-right: 0; }
 #jhnuftqkyr .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #jhnuftqkyr .gt_spanner_row { border-bottom-style: hidden; }
 #jhnuftqkyr .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #jhnuftqkyr .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #jhnuftqkyr .gt_from_md> :first-child { margin-top: 0; }
 #jhnuftqkyr .gt_from_md> :last-child { margin-bottom: 0; }
 #jhnuftqkyr .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #jhnuftqkyr .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #jhnuftqkyr .gt_indent_1 { text-indent: 5px; }
 #jhnuftqkyr .gt_indent_2 { text-indent: calc(5px * 2); }
 #jhnuftqkyr .gt_indent_3 { text-indent: calc(5px * 3); }
 #jhnuftqkyr .gt_indent_4 { text-indent: calc(5px * 4); }
 #jhnuftqkyr .gt_indent_5 { text-indent: calc(5px * 5); }
 #jhnuftqkyr .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #jhnuftqkyr .gt_row_group_first td { border-top-width: 2px; }
 #jhnuftqkyr .gt_row_group_first th { border-top-width: 2px; }
 #jhnuftqkyr .gt_striped { color: #333333; background-color: #F4F4F4; }
 #jhnuftqkyr .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #jhnuftqkyr .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #jhnuftqkyr .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #jhnuftqkyr .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #jhnuftqkyr .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #jhnuftqkyr .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #jhnuftqkyr .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #jhnuftqkyr .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #jhnuftqkyr .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #jhnuftqkyr .gt_left { text-align: left; }
 #jhnuftqkyr .gt_center { text-align: center; }
 #jhnuftqkyr .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #jhnuftqkyr .gt_font_normal { font-weight: normal; }
 #jhnuftqkyr .gt_font_bold { font-weight: bold; }
 #jhnuftqkyr .gt_font_italic { font-style: italic; }
 #jhnuftqkyr .gt_super { font-size: 65%; }
 #jhnuftqkyr .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #jhnuftqkyr .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #jhnuftqkyr .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #jhnuftqkyr .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #jhnuftqkyr .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #jhnuftqkyr .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| xYAC distributional calibration — the 76-class head, not its mean |  |  |  |  |  |  |  |
|----|----|----|----|----|----|----|----|
| PIT uniformity and CRPS against a climatology baseline |  |  |  |  |  |  |  |
| Season | Completions | CRPS | CRPS (climatology) | Skill | PIT max decile dev | 50% cov | 90% cov |
| 2023 | 11,997 | 2.8269 | 3.1861 | 0.1127 | 0.0058 | 0.5053 | 0.9036 |
| 2024 | 11,644 | 2.8321 | 3.2379 | 0.1253 | 0.0068 | 0.5033 | 0.9060 |
| 2025 | 11,278 | 2.7629 | 3.1296 | 0.1172 | 0.0071 | 0.4965 | 0.9036 |

&#10;</div>

<img src="parity_files/figure-commonmark/cell-8-output-1.png"
width="420" height="300"
alt="PIT histograms by season. A correctly specified distributional forecast is uniform; the dashed line is the uniform target." />

**The 76-class head is well calibrated as a distribution, not just in
the mean.** No decile of the PIT deviates from its 10% target by more
than 0.7 points in any season; central coverage lands at 50.2% and 90.3%
against nominal 50% and 90%; and CRPS beats the climatology baseline by
11–13%. That last number is the honest ceiling statement — YAC is mostly
irreducible, so an 11–13% improvement over “predict the league-wide YAC
distribution every time” is what the geometry in the features is worth,
and it is why per-completion correlation on the mean looks unimpressive
while the model is nonetheless doing real work.

Calibration is not uniform across throw depth, so the slice the eye
should go to is computed rather than asserted:

<div id="vovdtjmtul" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#vovdtjmtul table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#vovdtjmtul thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#vovdtjmtul p { margin: 0; padding: 0; }
 #vovdtjmtul .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #vovdtjmtul .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #vovdtjmtul .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #vovdtjmtul .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #vovdtjmtul .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #vovdtjmtul .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #vovdtjmtul .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #vovdtjmtul .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #vovdtjmtul .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #vovdtjmtul .gt_column_spanner_outer:first-child { padding-left: 0; }
 #vovdtjmtul .gt_column_spanner_outer:last-child { padding-right: 0; }
 #vovdtjmtul .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #vovdtjmtul .gt_spanner_row { border-bottom-style: hidden; }
 #vovdtjmtul .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #vovdtjmtul .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #vovdtjmtul .gt_from_md> :first-child { margin-top: 0; }
 #vovdtjmtul .gt_from_md> :last-child { margin-bottom: 0; }
 #vovdtjmtul .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #vovdtjmtul .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #vovdtjmtul .gt_indent_1 { text-indent: 5px; }
 #vovdtjmtul .gt_indent_2 { text-indent: calc(5px * 2); }
 #vovdtjmtul .gt_indent_3 { text-indent: calc(5px * 3); }
 #vovdtjmtul .gt_indent_4 { text-indent: calc(5px * 4); }
 #vovdtjmtul .gt_indent_5 { text-indent: calc(5px * 5); }
 #vovdtjmtul .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #vovdtjmtul .gt_row_group_first td { border-top-width: 2px; }
 #vovdtjmtul .gt_row_group_first th { border-top-width: 2px; }
 #vovdtjmtul .gt_striped { color: #333333; background-color: #F4F4F4; }
 #vovdtjmtul .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #vovdtjmtul .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #vovdtjmtul .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #vovdtjmtul .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #vovdtjmtul .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #vovdtjmtul .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #vovdtjmtul .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #vovdtjmtul .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #vovdtjmtul .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #vovdtjmtul .gt_left { text-align: left; }
 #vovdtjmtul .gt_center { text-align: center; }
 #vovdtjmtul .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #vovdtjmtul .gt_font_normal { font-weight: normal; }
 #vovdtjmtul .gt_font_bold { font-weight: bold; }
 #vovdtjmtul .gt_font_italic { font-style: italic; }
 #vovdtjmtul .gt_super { font-size: 65%; }
 #vovdtjmtul .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #vovdtjmtul .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #vovdtjmtul .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #vovdtjmtul .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #vovdtjmtul .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #vovdtjmtul .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| xYAC distributional calibration by throw depth |  |  |  |  |
|----|----|----|----|----|
| deep throws are the thinnest-sampled and the least well calibrated |  |  |  |  |
| Season | Air yards | Completions | CRPS | PIT max decile dev |
| 2023 | 0-4 | 3,529 | 2.6248 | 0.0116 |
| 2023 | 10-19 | 2,015 | 2.8407 | 0.0151 |
| 2023 | 5-9 | 2,911 | 2.1739 | 0.0134 |
| 2023 | deep (20+) | 739 | 3.9744 | 0.0229 |
| 2023 | screen (\< 0) | 2,803 | 3.4471 | 0.0147 |
| 2024 | 0-4 | 3,448 | 2.7094 | 0.0180 |
| 2024 | 10-19 | 1,989 | 2.6848 | 0.0121 |
| 2024 | 5-9 | 2,867 | 2.1394 | 0.0128 |
| 2024 | deep (20+) | 673 | 3.8442 | 0.0168 |
| 2024 | screen (\< 0) | 2,667 | 3.5896 | 0.0213 |
| 2025 | 0-4 | 3,437 | 2.5856 | 0.0094 |
| 2025 | 10-19 | 1,961 | 2.6239 | 0.0188 |
| 2025 | 5-9 | 2,706 | 2.3106 | 0.0131 |
| 2025 | deep (20+) | 702 | 3.2525 | 0.0268 |
| 2025 | screen (\< 0) | 2,472 | 3.4757 | 0.0134 |

&#10;</div>

Deep throws (air yards ≥ 20) are the worst slice on both measures: PIT
max decile deviation of 0.0168–0.0268 against at most 0.0213 everywhere
else, on only 673–739 completions a season, with CRPS rising to
3.25–3.97 as the YAC distribution there is both wider and
thinner-sampled. Still small in absolute terms — but it is the slice to
watch, not the headline.

**A monotone continuous head was not fitted** for the comparison the
xYAC card raises. The reason is that it is not cheap in the sense that
matters: a continuous head needs a distributional loss to be comparable
at all (scoring a point prediction against CRPS is not the same
question), and a fair comparison means a retrain plus a gate, not a
render-time fit. The result above also lowers the prior on it helping —
the classification head’s shape is already close to calibrated, so a
continuous reparameterisation would be buying smoothness in the tail,
not accuracy.

**On explainability for these heads**: `pred_contribs=True` returns
`(n, 76, p+1)` for a multiclass booster — a per-class attribution
*tensor*, not the 2-D matrix the binary models return, so
`contribs[:, :-1]` and `contribs.sum(axis=1)` are both wrong for xYAC
and `fd_model`. Aggregate deliberately (mean \|SHAP\| over classes) or
pick a class. This is a recorded gotcha and it is why neither card ships
a per-play SHAP pass.

## Why parity *and* LOSO

Parity proves the models reproduce the reference implementation; **LOSO
calibration** (each model card) proves they are honestly calibrated
out-of-sample on held-out seasons. A model can be well-calibrated yet
diverge from nflverse, or match nflverse yet be miscalibrated — so both
lenses are reported. The two share one derivation engine, byte-identical
between the live construction path and the parity path.

## Lineage

- **EP / WP / CP** — nflfastR EP/WP/CP models · nflverse `fastrmodels`
  (Ben Baldwin).
- **Fourth-down / FG / two-point / punt** — the nfl4th decision models.
- **xPass** — the nflverse dropback model.
- **Artifacts** — published as `nfl_model_artifacts` (EP / WP / CP) and
  `nfl_4th_down_models`, bundled in `sportsdataverse`.

## Why overtime diverged

The overtime gap was not a calibration problem, an era problem, or a
low-variance artefact. **nflfastR does not run the win-probability
boosters on overtime at all.** `helper_add_ep_wp.R::add_wp_variables`
(L820-899) splits the frame before prediction: the models score
`qtr <= 4`, and `qtr > 4` gets a closed form built from the
expected-points class probabilities —

    Sudden_Death_WP = fg_prob + td_prob + safety_prob

with `vegas_wp` assigned the *same* value (the spread model is never
consulted in overtime). sdv-py scored overtime with the boosters,
i.e. asked them about a state upstream never asks them about.

Both signatures are checkable directly against nflverse’s own published
columns, with no model involved:

On the 324 published overtime plays of 2025, nflverse’s `wp` equals the
sudden-death closed form **exactly** (to 1e-9) on 80.6% of rows — the
remainder are the One-FG branch, which uses
`td_prob + fg_prob * Win_Back` on the first overtime drive — and
`vegas_wp` equals `wp` bit-for-bit on 96.6%. The control is decisive: in
regulation, across 48,162 plays, `vegas_wp` equals `wp` on 0.033%.

**We port the sudden-death form only, and that is a measured decision.**
The One-FG branch is selected upstream by `Drive_Diff`, computed off a
`First_Drive` that is a minimum over every overtime row in the frame
`add_wp_variables` was handed — and nflfastR calls it once on the whole
rbound multi-game batch, so it is close to dead in the published data
(only 19.4% of 2025’s overtime rows are not the sudden-death form, and
only 4 sit within 0.02 of the One-FG form). Every deterministic
reconstruction of it scores *worse* — overtime `wp` MAE vs nflverse for
2016 / 2022 / 2025: per overtime game 0.1609 / 0.1102 / 0.1431,
frame-global 0.0394 / 0.0503 / 0.0594 (best, but frame-dependent, and
`build_nfl_season` enriches per game, under which it collapses to the
first row), sudden death only 0.0513 / 0.0534 / 0.0599. The gap this
leaves is real and named rather than papered over: since 2012 a field
goal on the opening overtime drive no longer ends the game, so the
sudden-death form overstates the kicking team’s chances there — and
nflverse’s published values carry the same overstatement.

The overlay is ported as
`sportsdataverse.nfl.ep_wp._apply_ot_wp_overlay`, applied as step 3b of
`enrich_nfl_pbp` (sdv-py PR \#435). Rather than quote that PR’s numbers,
this card re-scores 2025’s overtime games through **whatever
`sportsdataverse` this repo currently pins** and reports the result, so
the paragraph below moves on its own when the dependency picks the
overlay up and cannot go stale the way a typed-in number would.

The `sportsdataverse` this repo resolves today does not carry the
overlay yet (this repo pins sportsdataverse at main and PR 435 has not
landed there), so these are still the broken-state numbers and this
paragraph rewrites itself on the next dependency bump. Re-scoring 2025’s
16 overtime games gives overtime `wp` MAE 0.1731, bias -0.1308, r 0.379
on 324 overtime plays, with `vegas_wp == wp` on 0.0% of them against
nflverse’s 96.6%.

Split by `down` — real overtime plays 0.1775 (n = 262) against 0.1547 (n
= 62) on `down`-null rows (PATs, two-point tries, markers) — which is
not yet meaningful: with the overlay off every overtime row is wrong for
the same reason, so the split carries no information.

What PR \#435 measured, gated, and this card will reproduce once the pin
moves: over ten seasons and 3,171 overtime plays, overtime `wp` MAE
falls from a 0.097-0.173 band to 0.014-0.052 and r rises from
0.379-0.885 to \>= 0.871, while the **all-plays** MAE *improves* (2025:
0.0145 -\> 0.0135) and regulation rows stay byte-identical. The residual
there concentrates on `down`-null rows because nflfastR’s PAT fix
carries no `qtr` guard and overwrites the overtime value on exactly
those rows with a spread-model number — that overlay is **not** ported,
and it is the open issue recorded below.

## Avenues for improvement & open issues

- **WPA parity ceiling (~0.89)** is an SNR limit of first-differencing
  WP — documented as exact-derivation-verified; do not chase it as a
  bug.
- **Resolved (2026-09-01, PR \#29):** parity now covers the rare
  branches (onside, kickoffs, end-of-half, overtime, PATs, two-point
  tries, safeties, field goals) with sample sizes reported beside every
  number. The honest finding is that **most of those branches cannot be
  judged by correlation at all** — onside kicks (n=53) and overtime
  (n=309) have almost no WP variance within the branch, so Pearson r
  collapses even where the two models agree, and PATs/two-point tries
  are feature-substituted to a near-constant `ep` by construction. The
  branches with real spread (penalties, 4th downs, end-of-half) agree at
  0.96–0.997.
- **Resolved (2026-09-01, PR \#29):** the distributional heads are now
  scored as distributions, not just means — xYAC PIT uniformity and CRPS
  vs climatology.
- **Resolved (2026-09-02, PR \#32):** the overtime divergence recorded
  here on 2026-09-02 is explained and fixed. It was a **missing port**,
  not a modelling gap: nflfastR never scores overtime with the WP
  boosters, and sdv-py did. See “Why overtime diverged” above for the
  two signatures that identify it from nflverse’s own columns. Fixed in
  sdv-py PR \#435 (`_apply_ot_wp_overlay`), gated on a committed
  five-era overtime fixture (MAE ceiling 0.035 / \|bias\| 0.030 / r
  floor 0.98, each set from the observed 0.0209 / -0.0149 / 0.9945 and
  each failing when the overlay is stubbed out). **The branch table
  above still shows the pre-fix numbers** because it scores the
  published `model_pbp_2025.parquet`, which predates the fix;
  republishing `nfl_model_pbp` moves them.
- **Open issue (found 2026-09-02, PR \#32): the PAT / kickoff WP
  overlays are still unported.** `add_wp_variables` applies two more
  post-prediction fixes sdv-py’s nflverse path does not: a PAT /
  two-point fix (L932-1041, no `qtr` guard) and a regulation-only
  kickoff-touchback re-score (L1043-1069). The overtime residual
  localises to exactly the rows the first one covers (2025 overtime: MAE
  0.024 on `down`-non-null rows vs 0.083 on `down`-null rows).
  Quantifying and porting them touches every PAT and kickoff in the
  dataset, so it is its own change with its own before/after —
  deliberately not folded into the overtime fix.
- **Avenue:** the same PIT/CRPS treatment for `fd_model`’s 76-class
  head. It is the same machinery, but the label is a
  *decision-conditioned* gain (teams choose which 4th downs to attempt),
  so the realized sample is selected and a naive PIT would read as
  miscalibration that is really selection.
- **Known issue:** these branch correlations are single-season (2025).
  Pooling seasons would tighten onside/safety counts, but the branch
  definitions drift with rule changes (the 2024 kickoff overhaul in
  particular), so pooling would trade sampling noise for era
  heterogeneity rather than removing uncertainty.
