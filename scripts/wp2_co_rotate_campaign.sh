#!/usr/bin/env bash
# Pre-registered co-rotation campaign. Protocol: reports/wp2/co_rotate_eval_protocol.md
#
# 8 fixtures (one per SOURCE RUN, so they are 8 distinct builds) x 8 trials x 2 arms.
# Arms ALTERNATE in rounds of 8 rather than running one arm to completion, so that
# machine drift or thermal state cannot line up with an arm. Both arms carry
# --finale-pivot-projectiles; co-rotation is the only difference.
set -u

cd "$(dirname "$0")/.."
export APPDATA='C:\Users\moxhe\AppData\Roaming'
PY=./.venv/Scripts/python.exe
OUT=.tmp/co_rotate
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

for round in 1 2 3 4 5 6 7 8; do
  echo "=== round $round/8 : control (pivot only) ==="
  "$PY" scripts/wp2_finale_loop.py --trials 8 --boss predator \
    "${FIXARGS[@]}" \
    --label "corot_control_r${round}" --out "$OUT/control.jsonl" \
    --finale-pivot-projectiles

  echo "=== round $round/8 : treatment (pivot + co-rotate) ==="
  "$PY" scripts/wp2_finale_loop.py --trials 8 --boss predator \
    "${FIXARGS[@]}" \
    --label "corot_treat_r${round}" --out "$OUT/treatment.jsonl" \
    --finale-pivot-projectiles --finale-co-rotate
done

echo "=== campaign complete ==="
wc -l "$OUT"/control.jsonl "$OUT"/treatment.jsonl
