#!/usr/bin/env bash
# Reprocess the native nfl_model_pbp family after an sdv-py lock bump: one season at a time,
#   1. ingest + build model_pbp (--enrich, sdv-py enrich_nfl_pbp) and publish it (stage 01-03),
#   2. stages 06 (season summaries + percentiles), 07 (metric curves), 08 (defense vs position),
#      each built into its own per-season dir and published (stage 06 uploads its whole --out dir,
#      so a shared dir would re-upload every earlier season),
#   3. copy the season's tracked tables into nfl/<table>/ and commit + push them,
#      "chore(data): NFL season summaries + percentiles rebuild (Start: Y End: Y) [skip ci]".
# Then player-stats / team-stats are rebuilt over the whole published span, 1999 to the current season
# (each is one all-seasons asset aggregating the pbp release).
# Run AFTER scripts/reprocess_espn_nfl.sh: stage 06's Paper Index luck columns read espn_nfl_pbp.
#
#   bash scripts/reprocess_nfl_model_pbp.sh -s 1999 -e 2026
#   SEASONS="2011 2010" bash scripts/reprocess_nfl_model_pbp.sh
#   tail -f logs/reprocess_nfl_model_pbp_$(date -u +%Y%m%d).log
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

START=""; END=""
while getopts s:e: flag; do
  case "$flag" in s) START=$OPTARG;; e) END=$OPTARG;; *) echo "usage: $0 -s YYYY [-e YYYY]" >&2; exit 2;; esac
done
if [ -n "${SEASONS:-}" ]; then LIST=$SEASONS
elif [ -n "$START" ]; then LIST=$(seq "$START" "${END:-$START}")
else echo "usage: $0 -s YYYY [-e YYYY]  (or SEASONS=\"...\")" >&2; exit 2; fi

PY=$PWD/.venv/bin/python; RAW=.cache/nfl_raw; WORK=out/reprocess_model_pbp
mkdir -p logs; LOG="logs/reprocess_nfl_model_pbp_$(date -u +%Y%m%d).log"
export PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8
export GIT_CONFIG_PARAMETERS="'gc.auto=0'"
exec > >(tee -a "$LOG") 2>&1
ts() { date -u '+%F %T'; }
fail() { echo "[$(ts)Z] FAIL: $*"; echo "EXIT=1"; exit 1; }
py() { (cd python && "$PY" -m "$@"); }

echo "[$(ts)Z] reprocess_nfl_model_pbp start: seasons $(echo $LIST | tr '\n' ' ')"
for Y in $LIST; do
  W=$PWD/$WORK/$Y; rm -rf "${W:?}"; mkdir -p "$W"
  echo "[$(ts)Z] === $Y model_pbp"
  py nfl_data_01_ingest --seasons "$Y" --cache-dir "$PWD/$RAW" || fail "$Y ingest"
  py nfl_data_02_model_pbp build --enrich --seasons "$Y" --raw-dir "$PWD/$RAW" --out "$W/model_pbp" || fail "$Y build"
  ls "$W"/model_pbp/*.parquet >/dev/null 2>&1 || fail "$Y build wrote no parquet"
  py nfl_data_03_pbp_publish --parquet-dir "$W/model_pbp" --tag nfl_model_pbp \
    --repo sportsdataverse/sportsdataverse-data || fail "$Y model_pbp publish"

  echo "[$(ts)Z] === $Y stages 06-08"
  py nfl_data_06_team_summaries --seasons "$Y" --pbp-dir "$W/model_pbp" --out "$W/summaries" --publish \
    || fail "$Y stage 06"
  py nfl_data_07_metric_curves --seasons "$Y" --pbp-dir "$W/model_pbp" --out "$W/curves" --publish \
    || fail "$Y stage 07"
  py nfl_data_08_defense_vs_position --seasons "$Y" --pbp-dir "$W/model_pbp" --out "$W/dvp" --publish \
    || fail "$Y stage 08"

  echo "[$(ts)Z] === $Y commit"
  exec 9>/tmp/git_pull_sdv.lock
  flock -w 3600 9 || fail "$Y: git_pull sweep held its lock for 1h"
  for f in "$W"/summaries/nfl_*/*_"$Y".parquet; do       # nfl_passing/passing_Y -> nfl/passing/
    [ -f "$f" ] || continue
    d=nfl/$(basename "$(dirname "$f")" | sed 's/^nfl_//'); mkdir -p "$d"; cp "$f" "$d/"
  done
  # model_pbp is tracked for only some seasons: refresh those, add none
  t=nfl/model_pbp/model_pbp_$Y.parquet
  [ -n "$(git ls-files -- "$t")" ] && cp "$W/model_pbp/$(basename "$t")" "$t" 2>/dev/null
  git add -- nfl/*/*_"$Y".parquet ':!nfl/espn' 9>&-
  if git diff --cached --quiet 9>&-; then
    echo "[$(ts)Z] $Y: no tracked change"
  else
    git commit -q -m "chore(data): NFL season summaries + percentiles rebuild (Start: $Y End: $Y) [skip ci]" 9>&- \
      || fail "$Y commit"
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

# player_stats / team_stats are ONE all-seasons asset each: always rebuild the whole published span
# (1999 to the current season), never just the reprocessed seasons, or the upload drops the rest.
CUR=$(date -u +%Y); [ "$((10#$(date -u +%m)))" -lt 3 ] && CUR=$((CUR - 1))
echo "[$(ts)Z] === player-stats / team-stats 1999:$CUR"
py nfl_model_publish player-stats --seasons "1999:$CUR" --out "$PWD/$WORK/player_stats" || fail "player-stats"
py nfl_model_publish team-stats --seasons "1999:$CUR" --out "$PWD/$WORK/team_stats" || fail "team-stats"
echo "[$(ts)Z] chain done"
echo "EXIT=0"
