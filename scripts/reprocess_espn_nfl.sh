#!/usr/bin/env bash
# Reprocess the espn_nfl family after an sdv-py lock bump: one season at a time, in order,
#   1. build every dataset at the installed sdv-py (a final whose stamp differs is reprocessed),
#   2. gate it with G-NFL-1 (python -m nfl_espn_build.gate); a failing season stops the chain,
#   3. publish that season from the cached finals (--no-process --publish) + paper_index_games,
#   4. commit + push that season's nfl/espn parquets, "chore(data): espn_nfl family rebuild
#      (Start: Y End: Y) [skip ci]", under the git_pull sweep lock.
# Ascending order matters: rolling_windows reads the WRITTEN pbp seasons 2002..Y. The season-less
# coach_careers table is published once, after the loop, from every rebuilt season.
#
#   bash scripts/reprocess_espn_nfl.sh -s 2002 -e 2026
#   SEASONS="2011 2010" bash scripts/reprocess_espn_nfl.sh      # rerun a list
#   tail -f logs/reprocess_espn_nfl_$(date -u +%Y%m%d).log
#
# Env: ESPN_NFL_WORKERS (processor processes, default 4), NFL_RAW_DIR (default ../nfl-raw).
# Ends with "chain done" and EXIT=<rc>; git children run with the lock fd closed (9>&-).
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

START=""; END=""
while getopts s:e: flag; do
  case "$flag" in s) START=$OPTARG;; e) END=$OPTARG;; *) echo "usage: $0 -s YYYY [-e YYYY]" >&2; exit 2;; esac
done
if [ -n "${SEASONS:-}" ]; then LIST=$SEASONS
elif [ -n "$START" ]; then LIST=$(seq "$START" "${END:-$START}")
else echo "usage: $0 -s YYYY [-e YYYY]  (or SEASONS=\"...\")" >&2; exit 2; fi

PY=.venv/bin/python; OUT=nfl/espn; CACHE=.cache/nfl_espn_final
RAW=${NFL_RAW_DIR:-../nfl-raw}; WORKERS=${ESPN_NFL_WORKERS:-4}
mkdir -p logs; LOG="logs/reprocess_espn_nfl_$(date -u +%Y%m%d).log"
export PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 PYTHONPATH=python
export GIT_CONFIG_PARAMETERS="'gc.auto=0'"
exec > >(tee -a "$LOG") 2>&1
ts() { date -u '+%F %T'; }
fail() { echo "[$(ts)Z] FAIL: $*"; echo "EXIT=1"; exit 1; }

stamp=$("$PY" -c 'from nfl_espn_build.config import processing_version; print(processing_version())') \
  || fail "cannot read processing_version"

# Data relies on raw being done: nfl-raw (the ESPN library + crosswalk/games.json this reads) must be on
# origin/main with no local changes, pulled under the sweep lock so no scrape is mid-commit.
exec 9>/tmp/git_pull_sdv.lock
flock -w 3600 9 || fail "git_pull sweep held its lock for 1h"
[ "$(git -C "$RAW" branch --show-current)" = main ] || fail "nfl-raw is not on main"
[ -z "$(git -C "$RAW" status --porcelain --untracked-files=no)" ] || fail "nfl-raw has local changes"
git -C "$RAW" pull -q --ff-only origin main 9>&- || fail "nfl-raw pull failed"
flock -u 9; exec 9>&-
echo "[$(ts)Z] nfl-raw at $(git -C "$RAW" log -1 --format='%h %s')"
echo "[$(ts)Z] reprocess_espn_nfl start: seasons $(echo $LIST | tr '\n' ' ') stamp=$stamp workers=$WORKERS"

for Y in $LIST; do
  echo "[$(ts)Z] === $Y build"
  "$PY" -m nfl_espn_build --dataset all -s "$Y" --raw-dir "$RAW" --cache-dir "$CACHE" --out "$OUT" \
    --workers "$WORKERS" --no-careers || fail "$Y build"
  "$PY" -m nfl_data_09_paper_index_games --seasons "$Y" --pbp-dir "$OUT/pbp" --out "$OUT/paper_index_games" \
    || fail "$Y paper_index_games build"

  echo "[$(ts)Z] === $Y gate"
  "$PY" -m nfl_espn_build.gate --pbp-dir "$OUT/pbp" -s "$Y" || fail "$Y G-NFL-1 gate (nothing published)"

  echo "[$(ts)Z] === $Y publish"
  "$PY" -m nfl_espn_build --dataset all -s "$Y" --no-process --cache-dir "$CACHE" --out "$OUT" --publish \
    --no-careers || fail "$Y publish"
  "$PY" -m nfl_data_09_paper_index_games --seasons "$Y" --pbp-dir "$OUT/pbp" --out "$OUT/paper_index_games" \
    --publish || fail "$Y paper_index_games publish"

  echo "[$(ts)Z] === $Y commit"
  exec 9>/tmp/git_pull_sdv.lock
  flock -w 3600 9 || fail "$Y: git_pull sweep held its lock for 1h"
  files=$(ls "$OUT"/*/*_"$Y".parquet 2>/dev/null)
  git add -- $files 9>&-
  if git diff --cached --quiet 9>&-; then
    echo "[$(ts)Z] $Y: no tracked change"
  else
    git commit -q -m "chore(data): espn_nfl family rebuild (Start: $Y End: $Y) [skip ci]" 9>&- || fail "$Y commit"
    pushed=0
    for _ in 1 2 3; do
      git pull -q --no-rebase --no-edit origin main 9>&- && git push -q origin HEAD 9>&- && { pushed=1; break; }
      sleep 20
    done
    [ "$pushed" = 1 ] || fail "$Y push rejected 3 times"
  fi
  flock -u 9; exec 9>&-
  echo "[$(ts)Z] $Y done"
done
# coach_careers sums every written coach season: publish it ONCE, from the full rebuilt span
LAST=$(echo $LIST | tr ' ' '\n' | sort -n | tail -1)
echo "[$(ts)Z] === coach_careers 2002-$LAST"
"$PY" -m nfl_espn_build --dataset coach_careers -s 2002 -e "$LAST" --no-process --cache-dir "$CACHE" --out "$OUT" \
  --publish || fail "coach_careers publish"
echo "[$(ts)Z] chain done"
echo "EXIT=0"
