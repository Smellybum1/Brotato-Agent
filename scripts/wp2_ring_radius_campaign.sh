#!/usr/bin/env bash
# Pre-registered ring-radius campaign. Protocol: reports/wp2/ring_radius_eval_protocol.md
#
# control   = pivot fix only
# treatment = pivot fix + co-rotate + ring-radius  (outrunning REQUIRES rotating,
#             so the mechanism is both terms together; the co-rotation campaign
#             supplies the direction-only decomposition)
#
# Same 8 fixtures, same alternating rounds, same decision rule as co-rotation so
# the two campaigns are directly comparable.
#
# BEFORE RUNNING: the installed build and the repo's identity constants must
# agree, and must STAY agreed for the whole campaign. Deploy first, then freeze
# the repo -- no MOD_VERSION / manifest / telemetry-default / collector-constant
# edits until it finishes. A repo-only version bump during the first co-rotation
# campaign tripped the loop's identity gate and silently killed 87% of it.
set -u

cd "$(dirname "$0")/.."
export APPDATA='C:\Users\moxhe\AppData\Roaming'
PY=./.venv/Scripts/python.exe
OUT=.tmp/ring_radius
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

rows_of() { [ -f "$1" ] && wc -l < "$1" || echo 0; }
check_progress() {
  local file="$1" before="$2" label="$3"
  local after
  after=$(rows_of "$file")
  if [ "$after" -le "$before" ]; then
    echo "FATAL: $label produced 0 trials (rows $before -> $after)." >&2
    echo "The campaign is dead, not unlucky. Stopping so the machine is not wasted." >&2
    exit 1
  fi
}

for round in 1 2 3 4 5 6 7 8; do
  echo "=== round $round/8 : control (pivot only) ==="
  before=$(rows_of "$OUT/control.jsonl")
  "$PY" scripts/wp2_finale_loop.py --trials 8 --boss predator \
    "${FIXARGS[@]}" \
    --label "ring_control_r${round}" --out "$OUT/control.jsonl" \
    --finale-pivot-projectiles
  check_progress "$OUT/control.jsonl" "$before" "round $round control"

  echo "=== round $round/8 : treatment (pivot + co-rotate + ring-radius) ==="
  before=$(rows_of "$OUT/treatment.jsonl")
  "$PY" scripts/wp2_finale_loop.py --trials 8 --boss predator \
    "${FIXARGS[@]}" \
    --label "ring_treat_r${round}" --out "$OUT/treatment.jsonl" \
    --finale-pivot-projectiles --finale-co-rotate --finale-ring-radius
  check_progress "$OUT/treatment.jsonl" "$before" "round $round treatment"
done

echo "=== campaign complete ==="
wc -l "$OUT"/control.jsonl "$OUT"/treatment.jsonl
