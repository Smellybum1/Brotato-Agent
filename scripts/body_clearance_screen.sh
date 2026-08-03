#!/usr/bin/env bash
# §31 Gate 0 screen — body_clearance_scale dose ladder at Danger 5, character ranger.
#
#   usage: bash scripts/body_clearance_screen.sh
#
# Prereg: reports/wp2/body_clearance_screen_prereg.md
#
# Design rules this encodes, each earned:
#   * The config is read ONCE at _ready(), so the game MUST be killed between
#     doses or the next arm silently runs the previous dose.
#   * Any step that ARMS an experiment needs a READBACK and must ABORT on
#     mismatch -- here character, danger AND body_clearance_scale.
#   * weapon_pistol FIRST: every ranger evidence run opened weapon_pistol_1,
#     and _select_inventory_by_id_prefix is a SUBSTRING match tried IN ORDER,
#     so an smg-first list opens ranger on the wrong weapon.
#   * NO --stop-on-win: this is a fixed-n screen (S22 optional stopping).
#   * --min-wins 0: not a win-rate gate; the default 18 makes the early abort
#     fire instantly at GATE IMPOSSIBLE.
#   * --no-deploy: the build is FROZEN for the screen's whole duration.
#   * A dose yielding 0 runs ABORTS -- dead is not the same as unlucky.
set -u

cd "C:/Codex/Brotato Agent" || exit 1
CHARACTER="ranger"
DANGER=5
RUNS=4
PY=".venv/Scripts/python.exe"

kill_game() {
  MSYS_NO_PATHCONV=1 taskkill /IM Brotato.exe /F >/dev/null 2>&1 || true
  sleep 4
}

echo "=== §31 body_clearance screen  char=$CHARACTER  danger=$DANGER  n=$RUNS/dose ==="

"$PY" - <<'PY' || exit 1
import zipfile
z = zipfile.ZipFile(r"C:\Games\Steam\steamapps\workshop\content\1942280\3737864106\Tom-BrotatoAgent.zip")
cfg = z.read("mods-unpacked/Tom-BrotatoAgent/teacher/config.gd").decode("utf-8", "replace")
ctl = z.read("mods-unpacked/Tom-BrotatoAgent/runtime/agent_controller.gd").decode("utf-8", "replace")
pf  = z.read("mods-unpacked/Tom-BrotatoAgent/teacher/potential_field.gd").decode("utf-8", "replace")
port = [l for l in cfg.splitlines() if "EXPERIMENT_PORT_WR_PROFILE_TO :=" in l][0].strip()
ver  = [l for l in ctl.splitlines() if "const MOD_VERSION" in l][0].strip()
print("  installed build:", ver)
print("  installed port :", port)
if ':=""' not in port.replace(" ", ""):
    raise SystemExit("ABORT: the port is NOT inert")
# The knob must exist in the INSTALLED zip, on body_slack and nowhere else.
uses = [l.strip() for l in pf.splitlines() if "body_clearance_scale" in l]
print("  knob sites in installed potential_field.gd:", len(uses))
for u in uses:
    print("    ", u)
if not any("body_clearance_slack(wave) * body_clearance_scale" in u for u in uses):
    raise SystemExit("ABORT: the dose is not applied to body_slack in the INSTALLED build")
if any("BOSS_FINALE_BODY_CRITICAL_CLEARANCE" in u and "*" in u for u in uses):
    raise SystemExit("ABORT: the hard contact floor is being scaled -- it must never be")
PY

for DOSE in 1.0 2.0 3.0 0.5; do
  TAG=$(echo "$DOSE" | tr -d '.')
  STATE=".tmp/s31_bcs/d${TAG}/state.json"
  mkdir -p ".tmp/s31_bcs/d${TAG}"

  if [ -f "$STATE" ]; then
    HAVE=$("$PY" -c "import json,sys; print(len(json.load(open(sys.argv[1],encoding='utf-8-sig'))['collected_run_ids']))" "$STATE" 2>/dev/null || echo 0)
    if [ "$HAVE" -ge "$RUNS" ]; then echo "--- dose $DOSE already complete ($HAVE/$RUNS) ---"; continue; fi
  fi

  echo ""
  echo "--- DOSE body_clearance_scale=$DOSE  arming ---"
  kill_game
  "$PY" - "$CHARACTER" "$DANGER" "$DOSE" <<'PY' || { echo "ABORT: arming failed"; exit 3; }
import json, os, sys
ch = "character_" + sys.argv[1]
danger = int(sys.argv[2])
dose = float(sys.argv[3])
cfg = os.path.expandvars(r"%APPDATA%\Brotato\brotato_agent\agent_config.json")
WANT = {"auto_start": True, "character": ch, "danger": danger,
        "movement_estop_enabled": False,
        "body_clearance_scale": dose,
        "weapon_prefixes": ["weapon_pistol","weapon_smg","weapon_revolver","weapon_shredder",
                            "weapon_crossbow","weapon_laser_gun","weapon_"]}
open(cfg, "w", encoding="utf-8").write(json.dumps(WANT, indent=2))
back = json.loads(open(cfg, encoding="utf-8-sig").read())
bad = {k: (v, back.get(k)) for k, v in WANT.items() if back.get(k) != v}
if bad:
    print("  READBACK MISMATCH:", bad); raise SystemExit(1)
print(f"  ARMED and read back: {ch}  danger={danger}  body_clearance_scale={dose}")
PY

  echo "--- collecting $RUNS runs at dose $DOSE ---"
  "$PY" scripts/overnight_supervisor.py --runs "$RUNS" --min-wins 0 --no-deploy \
      --disarm-on-finish --state-file "$STATE" --report-prefix "s31_d${TAG}" \
      > ".tmp/s31_bcs/d${TAG}/supervisor.log" 2>&1
  GOT=$("$PY" -c "import json,sys; print(len(json.load(open(sys.argv[1],encoding='utf-8-sig'))['collected_run_ids']))" "$STATE" 2>/dev/null || echo 0)
  echo "--- dose $DOSE done: $GOT/$RUNS ---"
  if [ "$GOT" -eq 0 ]; then
    echo "ABORT: dose $DOSE produced ZERO runs -- the experiment is dead, not unlucky."
    kill_game; exit 4
  fi
done

kill_game
echo ""
echo "=== §31 COMPLETE -- game killed. ==="
"$PY" - <<'PY'
import json, os
cfg = os.path.expandvars(r"%APPDATA%\Brotato\brotato_agent\agent_config.json")
d = json.loads(open(cfg, encoding="utf-8-sig").read())
print("  final auto_start:", d.get("auto_start"), " body_clearance_scale:", d.get("body_clearance_scale"))
PY
