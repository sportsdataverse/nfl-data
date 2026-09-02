# Two-Point Conversion (`two_pt_model`)


The two-point-conversion model estimates the probability a two-point
attempt **succeeds**, given game context. It powers the **go-for-2
vs. extra-point** branch of the [nfl4th decision](fourth_down.md): the
success probability times two points is compared against the extra-point
EV. It is a Python retrain of nfl4th’s 2-pt model, validated against the
converted nflverse artifact.

This document is compiled: the response-curve and season sections score
the bundled booster at render time and compare against the latest
published season’s empirical conversion rate.

## Model features

**9 features**; one row per two-point attempt (`yardline_100==2`,
2010–2025). The binary label is `two_point_conv_result=='success'`. A
**monotone constraint** `(0,0,0,0,0,0,1,0,1)` forces success probability
to rise with `posteam_spread` and `posteam_total`.

| Feature | Type | What it encodes |
|----|----|----|
| `era2` / `era3` / `era4` | one-hot | Rule era (2006–13 / 2014–17 / ≥2018). |
| `outdoors` / `retractable` / `dome` | binary | Stadium-type one-hots. |
| `posteam_spread` | numeric | Possession-team spread (team-strength proxy; **monotone ↑**). |
| `total_line` | numeric | Game total. |
| `posteam_total` | numeric | Possession-team implied total (offense quality; **monotone ↑**). |

## The model

**Algorithm.** XGBoost, `objective=binary:logistic`, **21 rounds**,
`eta=0.0576`, `max_depth=8`, with the monotone constraint above —
verbatim from the nfl4th R recipe. A deliberately shallow fit for a
small target.

**Evaluation.** Parity P(success) corr **0.8718** — **below** the 0.99
gate, and honestly so: the residual is **training-data vintage drift**,
not a recipe error.

> [!NOTE]
>
> ### Why parity is capped at ~0.87 (not a bug)
>
> The oracle was trained on the **2020-era nflfastR-data RDS** (726
> rows, 21 rounds); current nflverse PBP has since revised those same
> plays (spread/total backfills, a few changed 2-pt results). The recipe
> — features, params, monotone constraints, filters — is a **verified
> faithful match**; the residual is irreducible without the frozen
> training snapshot, analogous to the [`wpa` SNR ceiling](parity.md).

## The response curve, render time

<img src="two_pt_files/figure-commonmark/cell-3-output-1.png"
width="420" height="300"
alt="Model success probability vs possession-team spread (era4, outdoors, league-median totals) — monotone by constraint; the model is a context-adjusted base rate." />

<div id="mgiykuggng" style="padding-left:0px;padding-right:0px;padding-top:10px;padding-bottom:10px;overflow-x:auto;overflow-y:auto;width:auto;height:auto;">
<style>
#mgiykuggng table {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', 'Fira Sans', 'Droid Sans', Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
&#10;#mgiykuggng thead, tbody, tfoot, tr, td, th { border-style: none; }
 tr { background-color: transparent; }
#mgiykuggng p { margin: 0; padding: 0; }
 #mgiykuggng .gt_table { display: table; border-collapse: collapse; line-height: normal; margin-left: auto; margin-right: auto; color: #333333; font-size: 16px; font-weight: normal; font-style: normal; background-color: #FFFFFF; width: auto; border-top-style: solid; border-top-width: 2px; border-top-color: #A8A8A8; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #A8A8A8; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; }
 #mgiykuggng .gt_caption { padding-top: 4px; padding-bottom: 4px; }
 #mgiykuggng .gt_title { color: #333333; font-size: 125%; font-weight: initial; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; border-bottom-color: #FFFFFF; border-bottom-width: 0; }
 #mgiykuggng .gt_subtitle { color: #333333; font-size: 85%; font-weight: initial; padding-top: 3px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; border-top-color: #FFFFFF; border-top-width: 0; }
 #mgiykuggng .gt_heading { background-color: #FFFFFF; text-align: center; border-bottom-color: #FFFFFF; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #mgiykuggng .gt_bottom_border { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #mgiykuggng .gt_col_headings { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; }
 #mgiykuggng .gt_col_heading { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; padding-left: 5px; padding-right: 5px; overflow-x: hidden; }
 #mgiykuggng .gt_column_spanner_outer { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: normal; text-transform: inherit; padding-top: 0; padding-bottom: 0; padding-left: 4px; padding-right: 4px; }
 #mgiykuggng .gt_column_spanner_outer:first-child { padding-left: 0; }
 #mgiykuggng .gt_column_spanner_outer:last-child { padding-right: 0; }
 #mgiykuggng .gt_column_spanner { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: bottom; padding-top: 5px; padding-bottom: 5px; overflow-x: hidden; display: inline-block; width: 100%; }
 #mgiykuggng .gt_spanner_row { border-bottom-style: hidden; }
 #mgiykuggng .gt_group_heading { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; text-align: left; }
 #mgiykuggng .gt_empty_group_heading { padding: 0.5px; color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; vertical-align: middle; }
 #mgiykuggng .gt_from_md> :first-child { margin-top: 0; }
 #mgiykuggng .gt_from_md> :last-child { margin-bottom: 0; }
 #mgiykuggng .gt_row { padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; margin: 10px; border-top-style: solid; border-top-width: 1px; border-top-color: #D3D3D3; border-left-style: none; border-left-width: 1px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 1px; border-right-color: #D3D3D3; vertical-align: middle; overflow-x: hidden; }
 #mgiykuggng .gt_stub { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; }
 #mgiykuggng .gt_indent_1 { text-indent: 5px; }
 #mgiykuggng .gt_indent_2 { text-indent: calc(5px * 2); }
 #mgiykuggng .gt_indent_3 { text-indent: calc(5px * 3); }
 #mgiykuggng .gt_indent_4 { text-indent: calc(5px * 4); }
 #mgiykuggng .gt_indent_5 { text-indent: calc(5px * 5); }
 #mgiykuggng .gt_stub_row_group { color: #333333; background-color: #FFFFFF; font-size: 100%; font-weight: initial; text-transform: inherit; border-right-style: solid; border-right-width: 2px; border-right-color: #D3D3D3; padding-left: 5px; padding-right: 5px; vertical-align: top; }
 #mgiykuggng .gt_row_group_first td { border-top-width: 2px; }
 #mgiykuggng .gt_row_group_first th { border-top-width: 2px; }
 #mgiykuggng .gt_striped { color: #333333; background-color: #F4F4F4; }
 #mgiykuggng .gt_table_body { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #mgiykuggng .gt_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #mgiykuggng .gt_first_summary_row { border-top-style: solid; border-top-width: 2px; border-top-color: #D3D3D3; }
 #mgiykuggng .gt_last_summary_row_top { border-bottom-style: solid; border-bottom-width: 2px; border-bottom-color: #D3D3D3; }
 #mgiykuggng .gt_grand_summary_row { color: #333333; background-color: #FFFFFF; text-transform: inherit; padding-top: 8px; padding-bottom: 8px; padding-left: 5px; padding-right: 5px; }
 #mgiykuggng .gt_first_grand_summary_row_bottom { border-top-style: double; border-top-width: 6px; border-top-color: #D3D3D3; }
 #mgiykuggng .gt_last_grand_summary_row_top { border-bottom-style: double; border-bottom-width: 6px; border-bottom-color: #D3D3D3; }
 #mgiykuggng .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #mgiykuggng .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #mgiykuggng .gt_left { text-align: left; }
 #mgiykuggng .gt_center { text-align: center; }
 #mgiykuggng .gt_right { text-align: right; font-variant-numeric: tabular-nums; }
 #mgiykuggng .gt_font_normal { font-weight: normal; }
 #mgiykuggng .gt_font_bold { font-weight: bold; }
 #mgiykuggng .gt_font_italic { font-style: italic; }
 #mgiykuggng .gt_super { font-size: 65%; }
 #mgiykuggng .gt_footnotes { color: font-color(#FFFFFF); background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #mgiykuggng .gt_footnote { margin: 0px; font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; }
 #mgiykuggng .gt_sourcenotes { color: #333333; background-color: #FFFFFF; border-bottom-style: none; border-bottom-width: 2px; border-bottom-color: #D3D3D3; border-left-style: none; border-left-width: 2px; border-left-color: #D3D3D3; border-right-style: none; border-right-width: 2px; border-right-color: #D3D3D3; }
 #mgiykuggng .gt_sourcenote { font-size: 90%; padding-top: 4px; padding-bottom: 4px; padding-left: 5px; padding-right: 5px; text-align: left; }
 #mgiykuggng .gt_footnote_marks { font-size: 75%; vertical-align: 0.4em; position: initial; }
 #mgiykuggng .gt_asterisk { font-size: 100%; vertical-align: 0; }
 &#10;</style>

| Render-time two-point evaluation — 2025 |  |
|----|----|
| the model's whole dynamic range is a few points around the base rate — by design for a 1,363-attempt target |  |
| check | value |
| 2025 two-point attempts | 130.0000 |
| empirical success rate | 0.4615 |
| model range over the spread grid (min) | 0.4534 |
| model range (max) | 0.4980 |

&#10;</div>

## Limitations

The sample is tiny, so the model is near-constant — treat it as a
slightly-context-adjusted base rate, not a sharp per-play estimate. No
play-call, personnel, or defensive context. The decision it feeds is
driven mostly by the ~48% success level against the empirical XP make
rate.

## Provenance

| field | value |
|----|----|
| `model_type` | two_pt |
| `objective` | binary:logistic (monotone spread/total ↑) |
| `features` | 9 (see above) |
| `label` | two_point_conv_result == success |
| `training_seasons` | 2010–2025 (1,363 attempts) |
| `hyperparameters` | eta=0.0576, max_depth=8, nrounds=21 |
| `lineage` | nfl4th two-point model |
| `parity` | P(success) corr 0.806 (informational; 2010–2025, vintage-drift) |
| `distribution` | bundled in sportsdataverse |
| `rebuild this doc` | `scripts/render_model_docs.sh` (Quarto → GFM; `uv sync --group docs`) |

## Avenues for improvement & open issues

- **Sparse-sample ceiling** — a documented soft gate (~0.87 parity)
  because the data vintage is thin; pooling college two-point data is a
  plausible transfer-learning experiment.
- **Resolved (2026-09-01, PR \#28):** `_stage.gate_status()` labels the
  soft gate `SOFT PASS` / `SOFT FAIL` in the console,
  `models/ledger.jsonl`, report.md and the train-all summary, so it can
  never read as a hard-gate `PASS`; the 0.99 floor is unchanged.
