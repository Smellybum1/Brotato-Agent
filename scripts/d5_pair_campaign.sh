#!/usr/bin/env bash
# §26 matched D0-vs-D5 pair — one character, two danger tiers.
#
#   usage: bash scripts/d5_pair_campaign.sh
#
# Prereg: reports/wp2/d0_d5_matched_pair_prereg.md
#
# Design rules this encodes, each earned:
#   * The config is read ONCE at _ready(), so the game must be KILLED between
#     arms or the next block silently runs the previous danger tier.
#   * Any step that ARMS an experiment needs a READBACK and must ABORT on
#     mismatch — here that means BOTH character AND danger.
#   * A block yielding 0 runs must ABORT, not continue.
#   * No --stop-on-win anywhere (§22): stopping on the outcome biases the arm.
#   * --min-wins 0: this is not a win-rate gate, and the default 18 aborts
#     instantly at GATE IMPOSSIBLE on resume.
#   * --no-deploy: the build is FROZEN for the campaign's whole duration.
set -u

cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
CHARACTER="mutant"
RUNS=16
PY=".venv/Scripts/python.exe"

kill_game() {
  MSYS_NO_PATHCONV=1 taskkill /IM Brotato.exe /F >/dev/null 2>&1 || true
  sleep 4
}

echo "=== §26 matched pair  character=$CHARACTER  runs/arm=$RUNS ==="
"$PY" - <<'PY' || exit 1
import zipfile
z = zipfile.ZipFile(r"C:\Games\Steam\steamapps\workshop\content\1942280\3737864106\Tom-BrotatoAgent.zip")
cfg = z.read("mods-unpacked/Tom-BrotatoAgent/teacher/config.gd").decode("utf-8", "replace")
ctl = z.read("mods-unpacked/Tom-BrotatoAgent/runtime/agent_controller.gd").decode("utf-8", "replace")
port = [l for l in cfg.splitlines() if "EXPERIMENT_PORT_WR_PROFILE_TO :=" in l][0].strip()
ver  = [l for l in ctl.splitlines() if "const MOD_VERSION" in l][0].strip()
print(f"  installed build: {ver}")
print(f"  installed port : {port}")
if '":= ""' not in port.replace(' ', '') and ':=""' not in port.replace(' ', ''):
    raise SystemExit("ABORT: the port is NOT inert — this campaign requires it disarmed")
PY

for DANGER in 0 5; do
  STATE=".tmp/d5pair_d${DANGER}/state.json"
  mkdir -p ".tmp/d5pair_d${DANGER}"

  if [ -f "$STATE" ]; then
    HAVE=$("$PY" -c "import json,sys; print(len(json.load(open(sys.argv[1],encoding='utf-8-sig'))['collected_run_ids']))" "$STATE" 2>/dev/null || echo 0)
    if [ "$HAVE" -ge "$RUNS" ]; then
      echo "--- danger $DANGER already complete ($HAVE/$RUNS), skipping ---"
      continue
    fi
  fi

  echo ""
  echo "--- DANGER=$DANGER  arming ---"
  kill_game
  "$PY" - "$CHARACTER" "$DANGER" <<'PY' || { echo "ABORT: arming failed"; exit 3; }
import json, os, sys
ch = "character_" + sys.argv[1]
danger = int(sys.argv[2])
cfg = os.path.expandvars(r"%APPDATA%\Brotato\brotato_agent\agent_config.json")
WANT = {"auto_start": True, "character": ch, "danger": danger,
        "movement_estop_enabled": False,
        "weapon_prefixes": ["weapon_pistol","weapon_smg","weapon_revolver","weapon_shredder",
                            "weapon_crossbow","weapon_laser_gun","weapon_"]}
open(cfg, "w", encoding="utf-8").write(json.dumps(WANT, indent=2))
back = json.loads(open(cfg, encoding="utf-8-sig").read())
bad = {k: (v, back.get(k)) for k, v in WANT.items() if back.get(k) != v}
if bad:
    print("  READBACK MISMATCH:", bad); raise SystemExit(1)
print(f"  ARMED and read back: {ch}  danger={danger}")
PY

  echo "--- DANGER=$DANGER  collecting $RUNS runs ---"
  "$PY" scripts/overnight_supervisor.py --runs "$RUNS" --min-wins 0 --no-deploy \
      --disarm-on-finish --state-file "$STATE" --report-prefix "d5pair_d${DANGER}" \
      > ".tmp/d5pair_d${DANGER}/supervisor.log" 2>&1
  RC=$?

  GOT=$("$PY" -c "import json,sys; print(len(json.load(open(sys.argv[1],encoding='utf-8-sig'))['collected_run_ids']))" "$STATE" 2>/dev/null || echo 0)
  echo "--- danger $DANGER finished rc=$RC collected=$GOT/$RUNS ---"
  if [ "$GOT" -eq 0 ]; then
    echo "ABORT: danger $DANGER produced ZERO runs — the experiment is dead, not unlucky."
    kill_game; exit 4
  fi
  if [ "$GOT" -lt "$RUNS" ]; then
    echo "WARN: danger $DANGER short ($GOT/$RUNS) — re-run this script to top it up before analysing."
  fi
done

kill_game
echo ""
echo "=== §26 COMPLETE — game killed. ==="
"$PY" - <<'PY'
import json, os
cfg = os.path.expandvars(r"%APPDATA%\Brotato\brotato_agent\agent_config.json")
print("  final auto_start:", json.loads(open(cfg, encoding="utf-8-sig").read()).get("auto_start"))
PY
