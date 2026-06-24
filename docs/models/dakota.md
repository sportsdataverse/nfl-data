# dakota (QB efficiency metric)

## Overview

`dakota` is a **derived metric, not a trained model** — the nflfastR
quarterback-efficiency composite. It is a fixed **linear combination of EPA per
dropback and CPOE**, with coefficients chosen to best predict a passer's
*next-season* adjusted EPA/play. Because it blends a stable input (CPOE) with a
noisier one (EPA), `dakota` is more **year-to-year stable** than raw EPA/play —
it is the closest thing in the suite to a "true talent" passing number.

## How it is computed

Per qualifying passer, over a sample of dropbacks:

1. `passing_epa` — the sum of QB-credited EPA (`qb_epa`), matching nflfastR's
   credited-EPA logic exactly;
2. `cpoe` — mean completion % over expected from the [CP model](cpoe.md), on the
   percentage-point scale `100 · (complete_pass − cp)`;
3. `dakota` — the fixed-coefficient linear blend of EPA/play and CPOE.

It is emitted as a column in the player-stats aggregation alongside the other
passing rates (`pacr`, `racr`, `wopr`).

## Lineage and caveats

`dakota` sits on top of two models: it inherits the [EP model](ep.md) through
`passing_epa` (so it carries the same intrinsic EP-model drift, ~0.99 parity
against nflverse) and the [CP model](cpoe.md) through `cpoe`. The blend
coefficients are the published nflfastR values — `dakota` is a **reproduction of
the nflfastR metric**, not a re-fit.

## Limitations

It is a single composite number: it cannot separate scheme, receiver, or
pressure effects, and it is only meaningful over a **reasonable dropback sample**
(small samples are dominated by the EPA term's noise). It is descriptive of the
*EPA-and-completion-explainable* part of QB play, the same blind spots as its two
parent models.

## Provenance

| field | value |
|---|---|
| `type` | derived metric (fixed-coefficient linear blend) |
| `inputs` | EPA/dropback (`qb_epa`) + CPOE |
| `parents` | EP model · CP model |
| `lineage` | nflfastR `dakota` (adjusted EPA + CPOE composite) |
| `surface` | player-stats aggregation (per passer) |
