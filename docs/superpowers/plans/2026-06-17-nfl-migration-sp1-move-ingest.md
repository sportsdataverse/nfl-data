# NFL Migration SP1 — Lift-and-Shift + URL Ingest — Implementation Plan

> REQUIRED SUB-SKILL: subagent-driven-development. Steps use `- [ ]` checkboxes.

**Goal:** Move the NFL compiled-PBP builder (`native_pbp`) and the EP/WP/CP training+reporting suite
(`model_training/play_level`) from `nfl-raw` into `nfl-data`, add a `nfl_data_ingest` layer that
fetches `nfl-raw`'s committed JSON by URL into a local cache, and prove the moved code builds compiled
PBP + the hermetic test suite passes in nfl-data. (nfl-raw is NOT modified here — that's SP3.)

**Architecture:** Reuse the moved code unchanged by having `nfl_data_ingest` download
`nfl/raw/{season}/{game_id}.json` from `RAW_BASE` into a cache dir, then call the existing
`native_pbp.build.build_season(raw_dir=<cache>)` / `play_level.ingest.load_native_pbp(raw_dir=<cache>)`.

## Global Constraints

- Repos: source `nfl-raw` (read-only this SP), target `sportsdataverse/nfl-data`.
- `RAW_BASE = "https://raw.githubusercontent.com/sportsdataverse/nfl-raw/main/nfl"` (raw files at `RAW_BASE/raw/{season}/{game_id}.json`).
- **Import layout:** nfl-data is `python/`-rooted (`pythonpath=["."]`). Rewrite `from python.native_pbp` → `from native_pbp`, `from python.model_training` → `from model_training` (and `import python.X` likewise) across moved code AND tests. Relative imports (`.ingest`, `.label`) are unchanged.
- HTTP via a pooled `requests.Session` with retry/backoff (mirror `sportsdataverse.dl_utils.download` conventions); final-game JSON is immutable → cache-forever.
- No AI co-author/footer. Path-scoped staging.

---

### Task 1: Move `native_pbp` + `model_training` into nfl-data
**Files:** copy `nfl-raw/python/native_pbp/` → `nfl-data/python/native_pbp/`; copy
`nfl-raw/python/model_training/` (contains only `play_level/`) → `nfl-data/python/model_training/`.

- [ ] **Step 1:** Copy both package dirs (exclude `__pycache__`). 
- [ ] **Step 2:** Rewrite absolute imports: in every `.py` under the two moved dirs, `from python.native_pbp` → `from native_pbp`, `from python.model_training` → `from model_training` (sed; verify no `python\.` prefix remains: `git grep -n "python\.native_pbp\|python\.model_training" python/` → empty).
- [ ] **Step 3:** Confirm packages import: `cd python && uv run python -c "import native_pbp.build, model_training.play_level.pipeline; print('ok')"` (after Task 3 deps).

### Task 2: Move the tests
**Files:** copy `nfl-raw/tests/{__init__.py, test_*.py, native_pbp/}` → `nfl-data/python/tests/`.

- [ ] **Step 1:** Copy the test files + `tests/native_pbp/` subdir (+ any fixtures they reference). Keep the SP0 `test_skeleton.py` for now (remove once real tests pass).
- [ ] **Step 2:** Rewrite the same `python.` import prefixes in the tests.
- [ ] **Step 3:** Mark any whole-corpus/network tests with `@pytest.mark.integration` so the default suite stays hermetic (the existing smoke/unit tests should run on fixtures — verify they don't read the full `nfl/raw`).

### Task 3: Carry modeling deps into nfl-data pyproject
**Files:** `nfl-data/python/pyproject.toml`.

- [ ] **Step 1:** Add to `[project].dependencies`: `xgboost>=2.0`, `numpy>=1.24`. Add `[dependency-groups] figures = ["plotnine>=0.13", "scikit-misc>=0.3"]`. Keep `sportsdataverse>=0.0.65`, polars, pyarrow, requests, tqdm.
- [ ] **Step 2:** `uv sync --group figures` → resolves; `uv run pytest -q` → hermetic suite green.

### Task 4: `nfl_data_ingest` — URL ingest into a cache
**Files:** create `nfl-data/python/nfl_data_ingest/{__init__.py, fetch.py, cli.py, __main__.py}`; test `python/tests/nfl_data_ingest/test_fetch.py`.

- [ ] **Step 1 (test first):** write `test_fetch.py` — given a fake session returning a known JSON body, `fetch_game(season, game_id, cache_dir, session=fake)` writes `cache_dir/{season}/{game_id}.json` and is a no-op (HEAD-skip) on the second call. Assert the cache file content + that the session is hit once.
- [ ] **Step 2:** implement `fetch.py`:
  - `RAW_BASE` constant; `raw_url(season, game_id) -> f"{RAW_BASE}/raw/{season}/{game_id}.json"`.
  - `fetch_game(season, game_id, cache_dir, *, session=None, force=False) -> Path` — pooled session, retry/backoff, write to cache, skip if present (final games immutable).
  - `enumerate_game_ids(season, *, session=None) -> list[str]` — list `nfl/raw/{season}/` via the GitHub contents API (`api.github.com/repos/sportsdataverse/nfl-raw/contents/nfl/raw/{season}`), stripping `.json`. (Fallback: accept an explicit id list.)
  - `ingest_season(season, cache_dir=".cache/nfl_raw", *, session=None) -> Path` — enumerate + fetch all; returns the cache root so `build_season(raw_dir=cache_root)` consumes it.
- [ ] **Step 3:** `cli.py` — `python -m nfl_data_ingest --seasons A:B --cache-dir .cache/nfl_raw`; mark a live round-trip test `@pytest.mark.integration`.
- [ ] **Step 4:** `uv run pytest -q` green (hermetic).

### Task 5: End-to-end wire + acceptance
- [ ] **Step 1 (integration, gated):** `python -m nfl_data_ingest --seasons 2024:2024` then `build_season(2024, raw_dir=.cache/nfl_raw)` produces a non-empty PBP frame; spot-check `native_pbp.parity` on a sample game (nflfastR parity). Mark `@pytest.mark.integration`.
- [ ] **Step 2:** Hermetic suite green; `import native_pbp.build, model_training.play_level.pipeline, nfl_data_ingest.fetch` all succeed.
- [ ] **Step 3:** Commit to a branch + PR into nfl-data `main`. Remove `test_skeleton.py` once the real suite is green.

## Acceptance
- nfl-data has `native_pbp/`, `model_training/play_level/`, `nfl_data_ingest/` + their tests; no `python.` import prefix remains.
- Hermetic `uv run pytest` green; gated integration test ingests 2024 by URL → builds parity-checked PBP.
- nfl-raw untouched (SP3 decommissions it).
