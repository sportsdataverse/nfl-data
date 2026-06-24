# nflfastR Parity

The headline validation for the NFL model suite is **parity with nflfastR**: the
models exist to *reproduce nflverse*, so the primary gate is column-level
agreement against nflfastR's own published outputs, not merely internal
calibration.

## How parity is measured

Each model is validated against the **converted nflverse artifact as a parity
oracle**: the same plays are scored by this model and by nflverse's shipped
model, and the public columns are correlated on the **model domain** — kickoffs
and PATs are **feature-substituted** exactly as nflfastR does (touchback yardline
80 pre-2016 / 75 from 2016, `down→1`, `ydstogo→10`), so the comparison is
like-for-like. The parity gate floors EP at Pearson-r 0.98 and caps WP Brier at
0.20.

## Play-level parity (lead-diff method, model domain)

| Column | Parity vs nflverse | Reading |
|---|---|---|
| `ep` | **r 0.996** | start-of-play expected points reproduces nflfastR |
| `epa` | **r 0.994** | first-difference of EP across the play |
| `wp` | **r 0.997** | spread-free in-game win probability |
| `vegas_wp` | **r 0.998** | spread-aware win probability — the tightest of the set |
| `cp` / `cpoe` | scale-correct | CPOE on the percentage-point scale `100·(complete_pass − cp)` |
| `wpa` | **r ≈ 0.89** | first-difference of WP — see ceiling note below |

## Fourth-down & tendency parity

The fourth-down / tendency models are **full-history (1999–2025) era-aware retrains**
(era0..era4 one-hot), so they no longer reproduce nfl4th's narrow-window oracles —
parity here is **informational** (how far the modern model sits from the frozen
oracle), not a reproduction gate. The decision WP is the exception: it trains on a
fixed calibration frame, so it still reproduces its oracle.

| Model | Metric | Parity | Basis |
|---|---|---|---|
| [Expected Pass](xpass.md) | P(pass) corr | **0.9895** | informational — era-aware, 1999–2025 |
| [Fourth-Down Yards](fourth_down.md) | mean-gain corr | **0.9856** | informational — era-aware, 1999–2025 |
| [Decision WP](nfl4th_wp.md) | P(win) corr | **0.9947** | reproduction — cal_data-bound (unchanged) |
| [Field Goal](fg.md) | attempted-cells corr | **0.971** (freq-wt 0.986) | informational — era-aware, 1999–2025 |
| [Two-Point](two_pt.md) | P(success) corr | **0.806** | informational — 2010–2025, vintage-drift |
| [Punt distribution](punt.md) | freq-weighted TV dist | **0.105** | informational — full-history |

## Two honest ceilings (not bugs)

**`wpa` ≈ 0.89.** `wpa` is the per-play first difference of `wp`. The derivation
is **exact** — fed nflverse's own `wp`, the reconstruction correlates **1.0**.
The ≈0.89 against nflverse's `wpa` is a **signal-to-noise ceiling**: tiny per-play
WP disagreements (the residual after r-0.997 `wp` agreement) are amplified by
first-differencing.

**Two-point ≈ 0.87.** The two-point oracle was trained on a frozen 2020-era
snapshot (726 rows) that current nflverse PBP has since revised. The recipe is a
verified faithful match; the residual is irreducible without the frozen training
data — the same kind of ceiling as `wpa`.

## Why parity *and* LOSO

Parity proves the models reproduce the reference implementation; **LOSO
calibration** (each model card) proves they are honestly calibrated out-of-sample
on held-out seasons. A model can be well-calibrated yet diverge from nflverse, or
match nflverse yet be miscalibrated — so both lenses are reported. The two share
one derivation engine, byte-identical between the live construction path and the
parity path.

## Lineage

- **EP / WP / CP** — nflfastR EP/WP/CP models · nflverse `fastrmodels`
  (Ben Baldwin).
- **Fourth-down / FG / two-point / punt** — the nfl4th decision models.
- **xPass** — the nflverse dropback model.
- **Artifacts** — published as `nfl_model_artifacts` (EP / WP / CP) and
  `nfl_4th_down_models`, bundled in `sportsdataverse`.
