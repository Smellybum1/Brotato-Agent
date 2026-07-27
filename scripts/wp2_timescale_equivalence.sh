#!/usr/bin/env bash
# Does acceleration change OUTCOMES?
#
# The internal checks already pass at every scale (captures per game-second
# 20.0, orbiter velocity scale-invariant, burst speed exactly 500). None of that
# proves the OUTCOME distribution is unchanged: game logic may have timing paths
# that run off _process rather than _physics_process.
#
# Same 8 fixtures, 4 trials each, at 1.0x and 8.0x, arms alternating per round.
# Primary comparator is DAMAGE TAKEN, not win rate: the shipped pivot fix pins
# win rate at the ceiling on these fixtures, so it cannot discriminate.
#
# This is an EQUIVALENCE question, so read the CI on the difference, not a
# p-value. "Not significantly different" at n=32 is weak; a tight interval
# around zero is the evidence worth having.
set -u

cd "$(dirname "$0")/.."
export APPDATA='C:\Users\moxhe\AppData\Roaming'
PY=./.venv/Scripts/python.exe
OUT=.tmp/ts_equiv
mkdir -p "$OUT"

FIX=(
  .tmp/snapshots/w19_boss_crab_20260726_134557_4ab34bffc43f89c3.json
  .tmp/snapshots/w19_predator_20260726_161821_fc24b6eb79072a4d.json
  .tmp/snapshots/w19_predator_20260726_165342_7149d1b7ab27f0a8.json
  .tmp/snapshots/w19_predator_20260726_182307_6c32fe3d950f8d6e.json
  .tmp/snapshots/w19_predator_20260726_184323_cab349ba80106a37.json
  .tmp/snapshots/w19_predator_20260726_191150_a00d393ad114f2cf.json
  .tmp/snapshots/w19_predator_20260726_193134_b02ffbeff221983d.json
  .tmp/snapshots/w19_predator_20260726_195023_56e65a951b357b1c.json
)
FIXARGS=()
for f in "${FIX[@]}"; do FIXARGS+=(--fixture "$f"); done

set_scale() {
  "$PY" -c "
import json,sys
from pathlib import Path
p=Path(r'C:\Users\moxhe\AppData\Roaming\Brotato\brotato_agent\agent_config.json')
cfg=json.loads(p.read_text(encoding='utf-8'))
cfg['time_scale']=float(sys.argv[1])
p.write_text(json.dumps(cfg,indent=2),encoding='utf-8')
" "$1"
}

rows_of() { [ -f "$1" ] && wc -l < "$1" || echo 0; }
check() {
  local after; after=$(rows_of "$1")
  if [ "$after" -le "$2" ]; then
    echo "FATAL: $3 produced 0 trials. Stopping." >&2; exit 1
  fi
}

for round in 1 2 3 4; do
  echo "=== round $round/4 : 1.0x ==="
  set_scale 1.0
  before=$(rows_of "$OUT/slow.jsonl")
  "$PY" scripts/wp2_finale_loop.py --trials 8 --boss predator "${FIXARGS[@]}" \
    --label "ts_slow_r${round}" --out "$OUT/slow.jsonl"
  check "$OUT/slow.jsonl" "$before" "round $round 1.0x"

  echo "=== round $round/4 : 8.0x ==="
  set_scale 8.0
  before=$(rows_of "$OUT/fast.jsonl")
  "$PY" scripts/wp2_finale_loop.py --trials 8 --boss predator "${FIXARGS[@]}" \
    --label "ts_fast_r${round}" --out "$OUT/fast.jsonl"
  check "$OUT/fast.jsonl" "$before" "round $round 8.0x"
done

set_scale 1.0
echo "=== complete (time_scale reset to 1.0) ==="
wc -l "$OUT"/slow.jsonl "$OUT"/fast.jsonl
