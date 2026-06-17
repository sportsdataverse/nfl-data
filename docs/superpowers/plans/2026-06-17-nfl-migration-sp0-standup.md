# NFL Migration SP0 — Stand Up the Repos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (or execute inline). Steps use `- [ ]` checkboxes.

**Goal:** Create `sportsdataverse/nfl-data` (scaffolded, hermetic test green) and push the existing local `nfl-raw` to `sportsdataverse/nfl-raw`, so the producer==consumer URL-ingest seam (SP1) has both repos on GitHub.

**Architecture:** SP0 is infrastructure only — no modeling code moves yet (that's SP1). Stand up the empty `nfl-data` uv project mirroring cfb-data's structure (Python project under `python/`, hermetic `integration` marker, `R/` dir for the publish toolchain, `docs/`), and publish `nfl-raw` to GitHub.

**Tech Stack:** uv (PEP 621 + PEP 735), pytest, gh CLI, git.

## Global Constraints

- Org: **sportsdataverse**. Repos: `sportsdataverse/nfl-raw`, `sportsdataverse/nfl-data`. Publish target (later SPs): `sportsdataverse/sportsdataverse-data`.
- **No AI co-author/footer** on commits or PRs.
- **Path-scoped staging only** — `nfl-raw` has 3.1 GB of committed raw JSON; never `git add -A` carelessly, but its raw IS tracked (commit-to-repo pattern), so its push is expected.
- nfl-data `.gitignore` must exclude `python/.cache/`, `cfb/`-style data dirs, `__pycache__`, build artifacts, `*.egg-info`.

---

### Task 1: Create + push `sportsdataverse/nfl-raw`

**Files:** none (git/gh ops on the existing `nfl-raw` repo).

- [ ] **Step 1: Verify nfl-raw git state + size.**
  Run: `git -C <nfl-raw> status --short | head; git -C <nfl-raw> log --oneline -1; du -sh <nfl-raw>/.git`
  Expected: clean-ish tree, has commits, no remote.
- [ ] **Step 2: Create the GitHub repo (no push yet).**
  Run: `gh repo create sportsdataverse/nfl-raw --public --description "Raw + enriched NFL game JSON scraped from the NFL Shield API via sportsdataverse (sibling of nfl-data)." --disable-wiki`
  Expected: repo created, prints URL. Do NOT use `--source/--push` yet (the 3.1 GB push is a deliberate separate step).
- [ ] **Step 3: Add remote + push (the heavy step).**
  Run: `git -C <nfl-raw> remote add origin https://github.com/sportsdataverse/nfl-raw.git && git -C <nfl-raw> push -u origin HEAD`
  Expected: success. ⚠️ ~3.1 GB — slow; if it fails on pack size, fall back to pushing in history chunks (`git push origin <older-sha>:refs/heads/main` then advance). Run in background; verify with `gh repo view sportsdataverse/nfl-raw --json pushedAt,diskUsage`.
- [ ] **Step 4: Confirm raw JSON is reachable by URL (the SP1 seam).**
  Run: pick one game id and `curl -sI "https://raw.githubusercontent.com/sportsdataverse/nfl-raw/main/nfl/raw/<season>/<game_id>.json" | head -1`
  Expected: `HTTP/2 200`. This proves URL-ingest will work.

### Task 2: Scaffold `sportsdataverse/nfl-data`

**Files:**
- Create: `<nfl-data>/python/pyproject.toml`, `<nfl-data>/python/conftest.py`, `<nfl-data>/python/tests/test_skeleton.py`
- Create: `<nfl-data>/.gitignore`, `<nfl-data>/README.md`
- Create: `<nfl-data>/R/.gitkeep` (R toolchain lands in SP2)
- Move-in: `docs/` already holds the spec + this plan + the playbook (copy the playbook from nfl-raw if not present).

- [ ] **Step 1: `git init` + initial structure.**
  Run: `cd <nfl-data> && git init -b main`
  Create `python/`, `R/`, `docs/superpowers/{specs,plans}/` (specs/plan already written here).

- [ ] **Step 2: Write `python/pyproject.toml`** (mirror cfb-data; modeling dep-groups added in SP1):

```toml
[project]
name = "nfl-data-pipeline"
version = "0.1.0"
description = "Builds NFL compiled play-by-play datasets + trains EP/WP/CP models from sportsdataverse/nfl-raw committed JSON; publishes to sportsdataverse-data."
requires-python = ">=3.11"
dependencies = [
    "sportsdataverse>=0.0.65",
    "polars>=1.0,<2.0",
    "pyarrow>=15.0",
    "requests>=2.28",
    "tqdm>=4.66",
]

[dependency-groups]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
markers = ["integration: whole-corpus or network test requiring fetched/cached JSON (deselected by default)"]
testpaths = ["tests"]
pythonpath = ["."]
addopts = '-m "not integration"'
```

- [ ] **Step 3: Write the hermetic skeleton test** `python/tests/test_skeleton.py`:

```python
def test_skeleton_imports():
    """SP0 placeholder — proves the project + pytest config resolve. Replaced by real tests in SP1."""
    import polars as pl
    assert pl.DataFrame({"x": [1]}).height == 1
```

- [ ] **Step 4: Write `python/conftest.py`** (empty marker anchor, mirrors cfb-data):

```python
# pytest configuration anchor for the nfl-data Python project.
```

- [ ] **Step 5: Write `.gitignore`:**

```gitignore
__pycache__/
*.pyc
*.egg-info/
.venv/
python/.cache/
python/cfb/
python/nfl/
build/
dist/
.Rproj.user/
```

- [ ] **Step 6: Sync + run the hermetic suite.**
  Run: `cd <nfl-data>/python && uv sync && uv run pytest -q`
  Expected: `1 passed`.

- [ ] **Step 7: Create the GitHub repo + push.**
  Run: `gh repo create sportsdataverse/nfl-data --public --description "NFL compiled PBP datasets + EP/WP/CP models built from sportsdataverse/nfl-raw; published to sportsdataverse-data." --disable-wiki`
  Then: `git -C <nfl-data> add . && git -C <nfl-data> commit -m "chore: scaffold nfl-data (uv project + hermetic test marker + R toolchain dir) [SP0]" && git -C <nfl-data> remote add origin https://github.com/sportsdataverse/nfl-data.git && git -C <nfl-data> push -u origin main`
  Expected: pushed; `gh repo view sportsdataverse/nfl-data` succeeds.

### Task 3: SP0 acceptance

- [ ] Both repos exist on GitHub (`gh repo view` each).
- [ ] A `nfl-raw` raw JSON URL returns HTTP 200 (Task 1 Step 4).
- [ ] `nfl-data` hermetic suite is green (`1 passed`).
- [ ] The spec + this plan + the playbook are committed under `nfl-data/docs/`.
- [ ] No modeling code moved yet (that's SP1); `nfl-raw` working tree unchanged except the new remote.
