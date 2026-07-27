#!/usr/bin/env bash
# Pivot-fix qualification. Protocol: reports/wp2/pivot_fix_qualification_protocol.md
#
# control   = shipped default (NO flags)
# treatment = --finale-pivot-projectiles
#
# 8 fixtures x 4 trials x 2 arms = 64 trials, arms alternating per round.
# The installed build and the repo's identity constants must agree for the whole
# run: deploy first, then freeze the repo.
set -u

cd "$(dirname "$0")/.."
export APPDATA='C:\Users\moxhe\AppData\Roaming'
PY=./.venv/Scripts/python.exe
OUT=.tmp/pivot_qual
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
  local file="$1" before="$2" label="$3" after
  after=$(rows_of "$file")
  if [ "$after" -le "$before" ]; then
    echo "FATAL: $label produced 0 trials (rows $before -> $after)." >&2
    echo "The campaign is dead, not unlucky. Stopping so the machine is not wasted." >&2
    exit 1
  fi
}

for round in 1 2 3 4; do
  echo "=== round $round/4 : control (shipped default, no fix) ==="
  before=$(rows_of "$OUT/control.jsonl")
  # --no-... is REQUIRED here since mod 0.2.49 made the fix the shipped default
  # and the loop follows that default. Passing no flag would now run the
  # TREATMENT in both arms.
  "$PY" scripts/wp2_finale_loop.py --trials 8 --boss predator "${FIXARGS[@]}" \
    --label "pivotqual_control_r${round}" --out "$OUT/control.jsonl" \
    --no-finale-pivot-projectiles
  check_progress "$OUT/control.jsonl" "$before" "round $round control"

  echo "=== round $round/4 : treatment (pivot fix) ==="
  before=$(rows_of "$OUT/treatment.jsonl")
  "$PY" scripts/wp2_finale_loop.py --trials 8 --boss predator "${FIXARGS[@]}" \
    --label "pivotqual_treat_r${round}" --out "$OUT/treatment.jsonl" \
    --finale-pivot-projectiles
  check_progress "$OUT/treatment.jsonl" "$before" "round $round treatment"
done

echo "=== campaign complete ==="
wc -l "$OUT"/control.jsonl "$OUT"/treatment.jsonl
