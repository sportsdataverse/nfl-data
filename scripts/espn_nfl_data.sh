#!/usr/bin/env bash
# espn_nfl_* processed-game datasets: process nfl-raw's ESPN library through
# NFLPlayProcess (cached per game) and cut every registry dataset per season.
#
#   bash scripts/espn_nfl_data.sh                 # current season, all datasets
#   bash scripts/espn_nfl_data.sh -s 2002 -e 2026 # backfill (resumable: cached finals are skipped)
#   PUBLISH=1 bash scripts/espn_nfl_data.sh -s 2025
#
# Watch:  tail -f logs/espn_nfl_data_$(date -u +%Y%m%d).log
# Knobs (env): NFL_RAW_DIR (nfl-raw checkout; default sibling, else HTTP),
#   ESPN_NFL_WORKERS (processor processes, default 2), ESPN_NFL_CACHE
#   (default .cache/nfl_espn_final), ESPN_NFL_OUT (default out/espn_nfl),
#   PUBLISH=1 to upload each season parquet to its espn_nfl_* release tag
#   (needs GH_TOKEN = a PAT with Contents: write on sportsdataverse-data).
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PY="${NFL_DATA_PYTHON:-}"
if [ -z "${PY}" ]; then
  for cand in .venv/Scripts/python.exe .venv/bin/python; do
    if [ -x "${cand}" ]; then PY="${cand}"; break; fi
  done
fi
if [ -z "${PY}" ]; then
  echo "FATAL: no venv python found (uv sync first, or set NFL_DATA_PYTHON)" >&2
  exit 1
fi
default_season() {
  local m y
  m=$(date -u +%m); y=$(date -u +%Y)
  if [ "$((10#$m))" -ge 3 ]; then echo "$y"; else echo "$((y - 1))"; fi
}
START_YEAR=""; END_YEAR=""; DATASET="all"
while getopts s:e:d: flag; do
  case "${flag}" in
    s) START_YEAR=${OPTARG};;
    e) END_YEAR=${OPTARG};;
    d) DATASET=${OPTARG};;
    *) echo "usage: $0 [-s YYYY] [-e YYYY] [-d dataset|all|adv_box]" >&2; exit 2;;
  esac
done
START_YEAR=${START_YEAR:-$(default_season)}
END_YEAR=${END_YEAR:-$START_YEAR}
mkdir -p logs
LOG="logs/espn_nfl_data_$(date -u +%Y%m%d).log"
export PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8
ARGS=(--dataset "$DATASET" -s "$START_YEAR" -e "$END_YEAR"
      --workers "${ESPN_NFL_WORKERS:-2}"
      --cache-dir "${ESPN_NFL_CACHE:-.cache/nfl_espn_final}"
      --out "${ESPN_NFL_OUT:-out/espn_nfl}")
[ -n "${NFL_RAW_DIR:-}" ] && ARGS+=(--raw-dir "$NFL_RAW_DIR")
[ "${PUBLISH:-0}" = "1" ] && ARGS+=(--publish)
{
  echo "[$(date -u '+%F %T')Z] espn_nfl_data start: ${START_YEAR}-${END_YEAR} dataset=${DATASET} publish=${PUBLISH:-0}"
  PYTHONPATH=python "$PY" -m nfl_espn_build "${ARGS[@]}"
  rc=$?
  echo "[$(date -u '+%F %T')Z] espn_nfl_data done rc=$rc"
  echo "EXIT=$rc"
  exit "$rc"
} 2>&1 | tee -a "$LOG"
exit "${PIPESTATUS[0]}"
