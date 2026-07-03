# nflfastR Parity Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining nflfastR parity gaps across nfl-data (`native_pbp`) and sdv-py (`sportsdataverse/nfl`): hardcoded game-repair layers, exact clock semantics, series/drive detail, the air/YAC EPA-WPA column family, `clean_pbp` canonicalization, player-level def/kicking stats, series conversion rates, standings, and a playstats dataset builder.

**Architecture:** Two independent tracks in two worktrees. Track A (nfl-data, Tasks 1–4, 9) extends the `native_pbp` reconstruction pipeline with the repair/mutation layers nflfastR applies between scrape and model-input, plus a playstats long-format builder. Track B (sdv-py, Tasks 5–8) extends the analysis surface: `ep_wp.py` gains the air/YAC EPA-WPA derivations (single-owner rule preserved), and new modules port `clean_pbp`, player def/kicking aggregation, series conversion rates, and standings. The two tracks share no files; cross-repo wiring (nfl-data consuming new sdv-py functions) is explicitly OUT of scope (nfl-data pins sdv-py from git@main; wiring lands after both PRs merge).

**Tech Stack:** Python 3.11+/3.9+ respectively, polars 1.x, uv, pytest. Oracle: nflfastR R source at `c:\Users\saiem\Documents\GitHub-Data\sdv-dev\nflverse-dev\nflfastR\R\`.

## Worktrees & Commands

| Track | Worktree root | Branch | Test command |
|---|---|---|---|
| A (nfl-data) | `c:\Users\saiem\Documents\GitHub-Data\sdv-dev\nflverse-dev\nfl-data\.claude\worktrees\nflfastr-parity` | `feat/nflfastr-parity-native` | `cd python && uv run pytest -q` |
| B (sdv-py) | `c:\Users\saiem\Documents\GitHub-Data\sdv-dev\sdv-py\.claude\worktrees\nflfastr-parity` | `feat/nflfastr-parity-surface` | `uv run pytest tests/nfl -q` |

**Reference doc (authoritative extract of all R source, line-anchored, verbatim data tables):**
`docs/superpowers/plans/2026-07-03-nflfastr-parity-reference.md` (in the Track A worktree). Every task below cites reference §s. When the plan and the reference disagree on a formula or a data table, the reference (i.e. the R source) governs — flag the discrepancy in your report.

## Global Constraints

- **polars 1.x modern API only**: `group_by`, `with_row_index`, `map_elements(..., return_dtype=)`, `pl.len()`, `how="full", coalesce=True`, `cum_sum`, `str.strip_chars`. Boolean masks explicit: `pl.col("c") == True`. No lookaround in regex — use `(?i)prefix(?-i: NAMES)` inline case toggle.
- **All window/cumulative ops in PBP derivations are `.over("game_id")`** (or `cum_sum().over("game_id")`) — frames are multi-game concatenations; a cross-game leak is a Critical defect.
- **New code fully typed** (params + returns). In sdv-py, append each new module path to the `[tool.mypy] files` ratchet in `pyproject.toml` and verify `uv run mypy sportsdataverse/nfl/<module>.py` passes.
- **sdv-py docstrings**: every public callable gets Google-style `Args:/Returns:/Raises:` + an `Example:` block in napoleon literal-block format (`Example:` heading, blank line, `::`-introduced 4-space-indented block; NO `>>>` doctest prompts). See `wbb/wbb_team_roster.py` for the canonical shape.
- **sdv-py single-owner rule**: EPA/WPA derivation logic lives ONLY in `sportsdataverse/nfl/ep_wp.py`. Construction modules never re-add it inline.
- **Empty/degenerate inputs return a zero-row frame carrying the documented schema**, never raise.
- **Output columns snake_case**; Float64 for model-derived floats (cast explicitly; never let numpy float32 leak into a public column).
- **ID dtype discipline**: one canonical dtype per id; assert `left.schema[k] == right.schema[k]` before joins; never paper over with float→Utf8 casts.
- **Conventional Commits; NEVER add AI co-author trailers** (no `Co-Authored-By: Claude ...`) — human is sole author.
- **Known pre-existing failure in Track A**: `tests/test_decision_models_trainer_smoke.py::TestFeatureBuilders::test_fg_label_and_roof_era` fails on origin/main (missing `era0` column, decision-models trainer area). It is not caused by, nor to be fixed by, any task here. Baseline: 241 passed, 1 failed, 1 skipped, 23 deselected. Track B baseline: `tests/nfl` 329 passed, 51 skipped.
- **Network-free tests by default.** Track A network tests use the `integration` marker (deselected by default). Track B live tests use `@skip_if_no_live`. All new task tests must run offline.
- **1-indexing gotcha**: R `play_id`/sequence comparisons are on GSIS play ids (not row positions); port comparisons by value, never by row index.
- Track A vendored data files live under `python/native_pbp/data/` and are read via `importlib.resources.files("native_pbp") / "data"` (or `Path(__file__).parent / "data"`, matching whichever pattern `native_pbp` already uses — check first).

---

## Track A — nfl-data `native_pbp`

### Task 1: Hardcoded game repairs (`fix_bad_games` + `fix_posteams`)

**Files:**
- Create: `python/native_pbp/repairs.py`
- Modify: `python/native_pbp/build.py` (apply repairs immediately after `parse_game`, before description/features/labels — the same pipeline position as nflfastR, which repairs the raw combined frame before mutations)
- Test: `python/tests/native_pbp/test_repairs.py`

**Interfaces:**
- Produces: `apply_game_repairs(df: pl.DataFrame) -> pl.DataFrame` (idempotent; keys off the frame's own `game_id` column — safe on multi-game frames) and `fix_posteams(df: pl.DataFrame) -> pl.DataFrame`. Task 2 adds more functions to this module.

**Requirements:** Port reference **§1** (`helper_scrape_nfl.R :: fix_bad_games` and `fix_posteams`) completely. `fix_bad_games` is a data-driven set of per-(game_id, play_id) corrections — wrong `posteam`, dropped/duplicated plays, bad `drive_play_count`s, etc. Transcribe every rule; each rule keys on the nflverse `game_id` string (e.g. `"2013_09_SEA_TB"`) — confirm against the reference whether nflfastR keys on old GSIS ids and, if so, map using the `game_id` format the native frame carries (it carries nflverse-style ids from the CLI schedule lookup; check `build.py`). If a rule's target column doesn't exist in the native frame yet at the repair stage, apply what exists and document the remainder in the module docstring.

- [ ] **Step 1: Write failing tests.** One test per repair *class* (not per game): e.g. a synthetic frame with the exact `game_id`/`play_id` of a known-bad game asserting the corrected value; plus a passthrough test:

```python
import polars as pl
from polars.testing import assert_frame_equal
from native_pbp.repairs import apply_game_repairs, fix_posteams

def test_unaffected_game_passes_through_unchanged():
    df = pl.DataFrame({
        "game_id": ["2023_01_BUF_NYJ"] * 3,
        "play_id": [1.0, 36.0, 55.0],
        "posteam": ["BUF", "BUF", "NYJ"],
    })
    assert_frame_equal(apply_game_repairs(df), df)
```

  Plus, for each rule ported, a targeted test built from the reference §1 verbatim values (construct the minimal frame the rule matches; assert the mutated cells and that other cells are untouched).
- [ ] **Step 2: Run tests, verify failure** (`uv run pytest tests/native_pbp/test_repairs.py -q` → import error).
- [ ] **Step 3: Implement `repairs.py`** — repair table as module-level data (list of dicts or match expressions), one small applier; wire into `build.py`.
- [ ] **Step 4: Run full Track A suite** — only the known pre-existing failure remains.
- [ ] **Step 5: Commit** — `feat(native_pbp): port nflfastR fix_bad_games/fix_posteams repair tables`

### Task 2: `fix_weird_pass_plays` + `fix_scrambles`

**Files:**
- Modify: `python/native_pbp/repairs.py` (add both functions), `python/native_pbp/build.py` (call order per reference — `fix_scrambles` runs where nflfastR runs it relative to mutations; `fix_weird_pass_plays` where `clean_pbp`-era code runs it)
- Create: `python/native_pbp/data/scrambles_1999_2004.csv` (or the format the source ships) — vendored scramble play-id list per reference **§2** (document source URL + retrieval date in a `data/README.md`)
- Test: `python/tests/native_pbp/test_repairs.py` (extend)

**Interfaces:**
- Produces: `fix_weird_pass_plays(df: pl.DataFrame) -> pl.DataFrame`, `fix_scrambles(df: pl.DataFrame) -> pl.DataFrame` (reads the vendored list once, module-level cache).

**Requirements:** Reference **§2** (`fix_scrambles`, incl. the external scramble play-id list source and schema) and **§3** (`fix_weird_pass_plays` — pre-2006 garbled pass rows: air_yards sign/NA repair conditions). If the scramble list is fetched from a URL at nflfastR runtime, download it ONCE now and vendor it (this is the only permitted network action, done by you at build time, not at library runtime); record provenance. `qb_scramble` column: if the native frame lacks it before this task, `description.py` already extracts scramble — verify and reconcile (the fix backfills seasons where the feed doesn't mark scrambles).

- [ ] **Step 1: Failing tests** — scramble backfill (row whose `(game_id, play_id)` is in the vendored list gains `qb_scramble=1`), weird-pass repair (construct a row matching the reference §3 condition; assert repaired air_yards/flags), non-matching rows untouched.
- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement + vendor data file.**
- [ ] **Step 4: Full suite green (modulo known failure).**
- [ ] **Step 5: Commit** — `feat(native_pbp): port fix_weird_pass_plays + fix_scrambles with vendored scramble list`

### Task 3: Exact clock semantics + parity gate tightened

**Files:**
- Modify: `python/native_pbp/parse.py` (`_clock_to_seconds`, `_seconds_remaining`, and any end-of-quarter/null-clock handling), `python/native_pbp/parity.py` (`DEFAULT_PARITY_COLUMNS`: `half_seconds_remaining` and `game_seconds_remaining` flip `"tol"` → `"exact"`)
- Test: `python/tests/native_pbp/test_parse.py` (extend; a dedicated `TestClock` class)

**Interfaces:**
- Consumes: existing parse pipeline. Produces: identical function names; behavior change only.

**Requirements:** Reference **§4**: port `utils.R :: time_to_seconds` exactly (string formats, NA handling) AND every imputation nflfastR applies to `quarter_seconds_remaining` / `half_seconds_remaining` / `game_seconds_remaining` (null clocks, end-of-quarter rows, OT quarters — OT quarter length and `game_seconds_remaining` treatment in qtr 5+ must match nflfastR exactly, including its convention for `game_seconds_remaining` in OT).

- [ ] **Step 1: Failing table-driven tests** — cases: `"15:00"` q1 → half 1800/game 3600; `"0:00"` q2 → 0/1800; null clock mid-quarter (imputation per reference); `"12:34"` q5 (OT) per nflfastR convention; malformed string → the R behavior (NA).
- [ ] **Step 2: Verify failure** (at least the OT/null cases must fail against current code — if ALL pass already, the port is a no-op: report that instead of writing dead code, and still flip the parity gate).
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Full suite; flip parity-gate modes; run any offline parity tests.**
- [ ] **Step 5: Commit** — `feat(native_pbp): exact nflfastR clock semantics; parity gate half/game seconds exact`

### Task 4: `qb_dropback` + series data + drive detail columns

**Files:**
- Create: `python/native_pbp/series.py`, `python/native_pbp/drives.py`
- Modify: `python/native_pbp/description.py` (add `qb_dropback`), `python/native_pbp/build.py` (wire series + drives after features), `python/native_pbp/parse.py` only if `_add_fixed_drive` moves into `drives.py` (keep `fixed_drive` semantics identical)
- Test: `python/tests/native_pbp/test_series.py`, `python/tests/native_pbp/test_drives.py`

**Interfaces:**
- Produces: `add_series_data(df: pl.DataFrame) -> pl.DataFrame` → adds `series` (Int32, cumulative per game), `series_success` (Int32 0/1), `series_result` (Utf8: exact nflfastR category strings per reference §7); `add_drive_detail(df: pl.DataFrame) -> pl.DataFrame` → adds every `drive_*` column from reference **§8** with exact names; `qb_dropback = 1 when pass==1 or qb_scramble==1 else 0` (Int32, per reference §14's exact definition).

**Requirements:** Reference **§7** (`add_series_data` — the lag-based series increment rules incl. kickoff/penalty/possession-change edge cases) and **§8** (`add_drive_results` + fixed-drives detail: `drive_play_count`, `drive_time_of_possession`, `drive_first_downs`, `drive_inside20`, `drive_ended_with_score`, `drive_quarter_start`, `drive_quarter_end`, `drive_yards_penalized`, `drive_start_transition`, `drive_end_transition`, `drive_game_clock_start`, `drive_game_clock_end`, `drive_start_yard_line`, `drive_end_yard_line`, `drive_play_id_started`, `drive_play_id_ended` — exact list/formulas from the reference). All grouping `.over(["game_id", "fixed_drive"])` or group_by-join, never bare cumulative.

- [ ] **Step 1: Failing tests** — synthetic 2-drive game: first downs increment `series`; turnover ends series with `series_result="Turnover"`-class value (exact string from reference); drive aggregates (play_count, clock start/end) computed from the synthetic rows; `qb_dropback` truth table (pass=1/scramble=0 → 1; pass=0/scramble=1 → 1; both 0 → 0).
- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement `series.py` + `drives.py`, wire build order.**
- [ ] **Step 4: Full suite green.**
- [ ] **Step 5: Commit** — `feat(native_pbp): series data, drive detail columns, qb_dropback`

### Task 9: Playstats long-format builder

**Files:**
- Create: `python/native_pbp/playstats.py`
- Modify: `python/native_pbp/cli.py` (add `build-playstats` subcommand mirroring `build`'s season/raw-dir/out args)
- Test: `python/tests/native_pbp/test_playstats.py`

**Interfaces:**
- Consumes: raw Shield JSON games (same input as `parse_game`) and `stat_ids.py` decode tables.
- Produces: `build_playstats_frame(game: dict, game_id: str | None = None) -> pl.DataFrame` with schema per reference **§13** (`build_playstats` output: one row per (play, stat) — `game_id`, `season`, `week`, `play_id`, `stat_id`, `yards`, `team_abbr`, `player_name`, `gsis_player_id` — use the exact nflfastR/nflverse column names from the reference); `build_playstats_season(...)` iterating a season dir like `build.py::build_season` does.

**Requirements:** Reference **§13**. This is a reshape of the same `stats` arrays `sum_play_stats` consumes — long format instead of wide pivot. Reuse the existing raw-JSON iteration pattern from `build.py`; do NOT duplicate `stat_ids` decode logic — import it.

- [ ] **Step 1: Failing test** — feed the same in-repo fixture JSON the existing `test_parse.py`/`test_stat_ids.py` tests use (find it; do not fabricate a new fixture format); assert row count = total stats entries, exact schema, and a couple of known rows.
- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement + CLI subcommand.**
- [ ] **Step 4: Full suite green; `uv run python -m native_pbp build-playstats --help` exits 0.**
- [ ] **Step 5: Commit** — `feat(native_pbp): playstats long-format builder + CLI subcommand`

---

## Track B — sdv-py `sportsdataverse/nfl`

### Task 5: Air/YAC EPA-WPA column family (+ running totals, ESPN xyac unblock)

**Files:**
- Modify: `sportsdataverse/nfl/ep_wp.py`, `sportsdataverse/nfl/model_vars.py` (only if output-contract lists live there — check `NFLVERSE_FRAME_CONTRACT`)
- Test: `tests/nfl/test_ep_wp_air_yac.py` (new)

**Interfaces:**
- Consumes: `calculate_epa(df)`, `calculate_wpa(df)`, `_derive_epa`, `_derive_wpa` (existing, in `ep_wp.py`).
- Produces: `_derive_air_yac_epa(df: pl.DataFrame) -> pl.DataFrame` and `_derive_air_yac_wpa(df: pl.DataFrame) -> pl.DataFrame`, called from within `calculate_epa` / `calculate_wpa` respectively (so BOTH the nflverse lead_diff path and the ESPN construction path get them via the existing delegation — the single-owner rule). Output columns (exact set per reference **§5**; expected: `air_epa`, `yac_epa`, `comp_air_epa`, `comp_yac_epa`, `air_wpa`, `yac_wpa`, `comp_air_wpa`, `comp_yac_wpa`, and the running totals `total_home_epa`, `total_away_epa`, `total_home_rush_epa`, `total_away_rush_epa`, `total_home_pass_epa`, `total_away_pass_epa`, `total_home_comp_air_epa`, `total_away_comp_air_epa`, `total_home_comp_yac_epa`, `total_away_comp_yac_epa`, `total_home_raw_air_epa`, `total_away_raw_air_epa`, `total_home_raw_yac_epa`, `total_away_raw_yac_epa`, plus the WPA mirrors incl. `vegas_home_wpa` — the reference §5 list governs, use ITS names verbatim).

**Requirements:** Port reference **§5** faithfully: `air_epa`/`yac_epa` formulas incl. the touchdown/goal-line special cases and incompletion handling; `comp_*` = value-if-complete-else-0 semantics; every cumulative total is `cum_sum().over("game_id")` on the home/away-attributed values. `air_epa` already exists as an internal xyac input — reconcile: the public column must follow the reference formula; keep one computation (refactor the internal use to consume the new derivation, don't compute twice). ESPN xyac unblock: with `air_epa` now a real column from `calculate_epa`, remove the blocker that left ESPN-path xyac null — verify `calculate_xyac` runs on an ESPN-constructed frame (its `air_epa` prerequisite now satisfied); if a residual gap remains, document it precisely in your report rather than hacking around it. All new columns Float64.

- [ ] **Step 1: Failing tests** — synthetic one-game frame with hand-computed `ep`/`epa`/`wp` values on ~8 plays (complete pass, incomplete, TD pass, rush, interception): assert `yac_epa == epa - air_epa` on the completion; `comp_air_epa == 0` on the incompletion while `air_epa` is nonzero; totals are cumulative and, in a two-game concat, reset at the game boundary (leak test); all dtypes Float64.
- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement; wire into `calculate_epa`/`calculate_wpa`.**
- [ ] **Step 4:** `uv run pytest tests/nfl -q` green; `uv run mypy sportsdataverse/nfl/ep_wp.py` clean.
- [ ] **Step 5: Commit** — `feat(nfl): air/YAC EPA-WPA family + per-game running totals in ep_wp`

### Task 6: `clean_pbp` port (name/id canonicalization)

**Files:**
- Create: `sportsdataverse/nfl/nfl_clean.py`
- Modify: `sportsdataverse/nfl/__init__.py` (export `clean_nfl_pbp`), `pyproject.toml` (mypy ratchet)
- Test: `tests/nfl/test_nfl_clean.py`

**Interfaces:**
- Consumes: `sportsdataverse/nfl/datasets.py :: team_abbr_mapping` (relocation folding — already exists; do NOT re-hardcode the map).
- Produces: `clean_nfl_pbp(df: pl.DataFrame, *, return_as_pandas: bool = False) -> pl.DataFrame | pd.DataFrame` adding the reference **§6** column set (expected: cleaned `passer`/`rusher`/`receiver` short names, `name`/`id` (passer-else-rusher), `fantasy`/`fantasy_player_name`/`fantasy_player_id` (receiver-else-rusher), `aborted_play`, `play` flag, plus team-abbr normalization applied to every team column `team_name_fn` touches — the reference list governs).

**Requirements:** Reference **§6** verbatim behavior, including: the suffix-stripping/name-shortening regexes (mind the no-lookaround rule — rewrite with inline case toggles or two-pass extracts), the `maybe_valid`/`uniquify_ids` id handling ONLY if applicable to the id space our frames carry (native/nflverse frames carry GSIS `00-00xxxxx` ids already — if a §6 branch only exists for old GC ids, document-and-skip it in the module docstring rather than porting dead code), and `aborted_play` semantics. Public function: full docstring with `Example:` block per Global Constraints.

- [ ] **Step 1: Failing tests** — name cleaning (`"G.Minshew II"`-style suffix case per reference regexes), `name`/`id` fallback (pass row → passer, rush row → rusher), fantasy fallback (reception → receiver), team normalization (`"SD"` → `"LAC"`, `"OAK"` → `"LV"` on every touched column), `aborted_play` from a matching desc row, empty-frame schema stability.
- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4:** tests + mypy on the new module green; `uv run python tools/codegen/generate.py --check` still passes (no codegen surface touched — verify, don't assume).
- [ ] **Step 5: Commit** — `feat(nfl): clean_nfl_pbp — nflfastR clean_pbp port (names, ids, fantasy, team normalization)`

### Task 7: Player-level defense + kicking stats

**Files:**
- Modify: `sportsdataverse/nfl/nfl_stats.py` (follow the existing `build_nfl_player_stats` module patterns: `_i`/`_f` helpers, `_prepare_pbp`, empty-frame schema helpers), `sportsdataverse/nfl/__init__.py` (exports), `pyproject.toml` only if `nfl_stats.py` isn't already in the mypy ratchet
- Test: `tests/nfl/test_nfl_stats_def_kicking.py`

**Interfaces:**
- Consumes: the wide PBP columns produced by `sum_play_stats`-style frames (`solo_tackle_1_player_id`, `assist_tackle_*`, `pass_defense_*`, `qb_hit_*`, `fumble_recovery_*`, `kicker_player_id`, `field_goal_result`, `kick_distance`, ... — the same columns `load_nfl_pbp` serves).
- Produces: `build_nfl_player_stats_def(pbp: pl.DataFrame, *, weekly: bool = False, return_as_pandas: bool = False)` and `build_nfl_player_stats_kicking(pbp: pl.DataFrame, *, weekly: bool = False, return_as_pandas: bool = False)` with output columns exactly per reference **§9** / **§10** (def: `def_tackles_solo`, `def_tackles_with_assist`, `def_tackle_assists`, `def_tackles_for_loss`, `def_fumbles_forced`, `def_sacks`, `def_qb_hits`, `def_interceptions`, `def_pass_defended`, `def_tds`, `def_fumble_recovery_*`, `def_safety`, `def_penalty`, ... — reference list governs; kicking: `fg_made/att/missed/blocked`, distance buckets, `fg_long`, `fg_pct`, `pat_*`, `gwfg_*` — reference list governs).

**Requirements:** Reference **§9**/**§10**: every aggregation formula (which player-id slots feed which stat, half-sack = 0.5 weighting, tackle-with-assist vs assist distinction, made-distance buckets `fg_made_0_19`…`fg_made_60_`, game-winning FG detection). `weekly=False` collapses to season level exactly the way nflfastR does (recompute vs re-aggregate — follow the reference). Empty pbp → documented-schema zero-row frame.

- [ ] **Step 1: Failing tests** — synthetic pbp with: a split sack (two `half_sack_*` players → 0.5 each), solo+assist tackles, an INT-return TD, a 47-yard made FG + 52-yard miss + blocked PAT (assert bucket columns, `fg_long`, `fg_pct`), weekly vs season collapse, empty-frame schema.
- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4:** tests + mypy green.
- [ ] **Step 5: Commit** — `feat(nfl): player-level defense + kicking stat builders (nflfastR parity)`

### Task 8: Series conversion rates + standings calculators

**Files:**
- Create: `sportsdataverse/nfl/nfl_series.py`, `sportsdataverse/nfl/nfl_standings.py`
- Modify: `sportsdataverse/nfl/__init__.py` (exports), `pyproject.toml` (mypy ratchet, both modules)
- Test: `tests/nfl/test_nfl_series.py`, `tests/nfl/test_nfl_standings.py`

**Interfaces:**
- Consumes: `nfl_series` needs pbp with `series`, `series_success`, `series_result`, `posteam`/`defteam` (nflverse-loaded pbp has them today; Track A adds them natively — no cross-repo dependency for tests, use synthetic frames). `nfl_standings` consumes a games/schedules frame (`load_nfl_schedule` shape: `game_id, season, game_type, week, home_team, away_team, home_score, away_score`) plus division/conference mapping from `load_nfl_teams` (offline tests inject a small teams frame — the function takes `teams: pl.DataFrame | None = None` and only calls the loader when None).
- Produces: `calculate_nfl_series_conversion_rates(pbp: pl.DataFrame, *, weekly: bool = False, return_as_pandas: bool = False)` (output columns exactly per reference **§11**) and `calculate_nfl_standings(games: pl.DataFrame, *, teams: pl.DataFrame | None = None, tiebreaker_depth: int = 3, playoff_seeds: int | None = None, return_as_pandas: bool = False)` (columns + tiebreaker order per reference **§12**).

**Requirements:** Reference **§11** (offense + defense rate columns, weekly grain) and **§12** (win pct → h2h → division record → conference record tiebreakers to the documented depth; `div_rank`/`seed` outputs; ties = 0.5 wins). Do not implement tiebreaker levels beyond what nflfastR's `tiebreaker_depth` supports (YAGNI).

- [ ] **Step 1: Failing tests** — series rates: synthetic pbp with known series outcomes → exact rates; standings: a 4-team synthetic division schedule with a deliberate two-way tie broken by head-to-head, plus a tie game (0.5 win), assert `wins/losses/ties/win_pct/div_rank/seed`.
- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement both modules.**
- [ ] **Step 4:** tests + mypy green; `uv run pytest tests/nfl -q` fully green.
- [ ] **Step 5: Commit** — `feat(nfl): series conversion rates + standings calculators (nflfastR parity)`

---

## Out of scope (explicit)

- Wiring `clean_nfl_pbp`/new stats into nfl-data's `--enrich` cron path (needs sdv-py release/merge first; follow-up PR).
- `nfl_model_publish` release subcommand for playstats (builder + CLI land now; publisher wiring is a follow-up).
- Live/network parity validation runs (gated `integration`/`SDV_PY_LIVE_TESTS` runs are follow-up verification, not part of task DoD).
- Any change to model training, model artifacts, or the deprecated per-type NFL loaders.

## Execution order

Track A: 1 → 2 → 3 → 4 → 9. Track B: 5 → 6 → 7 → 8. Tracks are file-disjoint and may run concurrently (one implementer per track at a time). Ledger: `.superpowers/sdd/nflfastr-parity/progress.md` in the Track A worktree root.
