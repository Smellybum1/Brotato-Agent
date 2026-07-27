#!/usr/bin/env bash
# DOSE-RESPONSE: is a LOWER time_scale safe when 8x is not?
#
# 8x is refuted (reports/wp2/timescale_equivalence_verdict.md): damage 22.1 ->
# 45.2, victories 32/32 -> 26/32, replicated. But the 8x arm was CPU-SATURATED --
# it requested 8x and achieved only 6.20x. If saturation is the mechanism, a
# scale the machine can actually sustain is clean and the failure is a CLIFF, not
# a slope. This tests 2x and 4x against a CONTEMPORANEOUS 1x control.
#
# All three arms run in every round on the same 8 fixtures, so the control is
# never stale relative to a treatment arm.
#
# Protocol: reports/wp2/timescale_doseresponse_protocol.md (committed first).
set -u

cd "$(dirname "$0")/.."
export APPDATA='C:\Users\moxhe\AppData\Roaming'
PY=./.venv/Scripts/python.exe
OUT=.tmp/ts_dose
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

# time_scale must NEVER be left accelerated: dataset collection reads
# control_dt_ms as a real-time student model input.
trap 'set_scale 1.0; echo "time_scale reset to 1.0 (trap)"' EXIT INT TERM

rows_of() { [ -f "$1" ] && wc -l < "$1" || echo 0; }
check() {
  local after; after=$(rows_of "$1")
  if [ "$after" -le "$2" ]; then
    echo "FATAL: $3 produced 0 trials. Stopping." >&2; exit 1
  fi
}

# arm -> (scale, file, label prefix). The evaluator cross-checks that a control
# file's labels start ts_slow and a treatment file's ts_fast (amendment A6), so
# each accelerated arm goes to its OWN file under the ts_fast label.
run_arm() {  # $1 scale  $2 file  $3 label  $4 round
  echo "=== round $4 : ${1}x -> $2 ==="
  set_scale "$1"
  local before; before=$(rows_of "$OUT/$2")
  "$PY" scripts/wp2_finale_loop.py --trials 8 --boss predator "${FIXARGS[@]}" \
    --label "${3}_r${4}" --out "$OUT/$2"
  check "$OUT/$2" "$before" "round $4 ${1}x"
}

ROUNDS="${ROUNDS:-1 2 3 4}"
for round in $ROUNDS; do
  run_arm 1.0 s1.jsonl ts_slow "$round"
  run_arm 2.0 s2.jsonl ts_fast "$round"
  run_arm 4.0 s4.jsonl ts_fast "$round"
done

set_scale 1.0
echo "=== complete (time_scale reset to 1.0) ==="
wc -l "$OUT"/s1.jsonl "$OUT"/s2.jsonl "$OUT"/s4.jsonl
