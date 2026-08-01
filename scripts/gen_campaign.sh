#!/usr/bin/env bash
# §25 port-generalisation campaign driver — one ARM, four characters, 8 runs each.
#
#   usage: bash scripts/gen_campaign.sh <bare|ported>
#
# The installed build defines the ARM (EXPERIMENT_PORT_WR_PROFILE_TO). This
# driver does NOT deploy and must never be run across a deploy: verify the
# installed build matches the arm you intend BEFORE starting it.
#
# Design rules this encodes, each earned:
#   * The config is read ONCE at _ready(), so the game must be KILLED between
#     characters or the next block silently runs the previous character.
#   * Any step that ARMS an experiment needs a READBACK, and the driver must
#     ABORT on mismatch — a scale/character that fails to apply produces a
#     campaign that looks healthy and measures nothing.
#   * A block yielding 0 runs must ABORT, not continue. A driver that cannot
#     tell "the experiment is dead" from "this round was unlucky" burns a night.
#   * No --stop-on-win anywhere (§22): stopping on the outcome biases the arm.
set -u

ARM="${1:-}"
if [ "$ARM" != "bare" ] && [ "$ARM" != "ported" ]; then
  echo "usage: bash scripts/gen_campaign.sh <bare|ported>" >&2; exit 64
fi

cd "C:/Codex/Brotato Agent" || exit 1
# Order drawn with secrets (§25b); cyborg->artificer and fisherman->ranger were
# substituted in place for ERA SAFETY (§25f): a win by a character whose reward
# is still locked unlocks an item, which moves the shop pool mid-campaign and
# invalidates pooling. All four here have their reward ALREADY unlocked.
CHARACTERS="artificer ranger mutant arms_dealer"
RUNS=8
PY=".venv/Scripts/python.exe"

kill_game() {
  MSYS_NO_PATHCONV=1 taskkill /IM Brotato.exe /F >/dev/null 2>&1 || true
  sleep 4
}

echo "=== §25 ARM=$ARM  characters: $CHARACTERS  runs/character: $RUNS ==="
"$PY" - <<'PY' || exit 1
import json, os, zipfile
z = zipfile.ZipFile(r"C:\Games\Steam\steamapps\workshop\content\1942280\3737864106\Tom-BrotatoAgent.zip")
cfg = z.read("mods-unpacked/Tom-BrotatoAgent/teacher/config.gd").decode("utf-8", "replace")
ctl = z.read("mods-unpacked/Tom-BrotatoAgent/runtime/agent_controller.gd").decode("utf-8", "replace")
port = [l for l in cfg.splitlines() if "EXPERIMENT_PORT_WR_PROFILE_TO :=" in l][0].strip()
ver  = [l for l in ctl.splitlines() if "const MOD_VERSION" in l][0].strip()
print(f"  installed build: {ver}")
print(f"  installed arm  : {port}")
PY

for CH in $CHARACTERS; do
  STATE=".tmp/gen_${ARM}_${CH}/state.json"
  mkdir -p ".tmp/gen_${ARM}_${CH}"

  if [ -f "$STATE" ]; then
    HAVE=$("$PY" -c "import json,sys; print(len(json.load(open(sys.argv[1],encoding='utf-8-sig'))['collected_run_ids']))" "$STATE" 2>/dev/null || echo 0)
    if [ "$HAVE" -ge "$RUNS" ]; then
      echo "--- $CH already complete ($HAVE/$RUNS), skipping ---"
      continue
    fi
  fi

  echo ""
  echo "--- ARM=$ARM  CHARACTER=$CH  arming ---"
  kill_game
  "$PY" - "$CH" <<'PY' || { echo "ABORT: arming failed for this character"; exit 3; }
import json, os, sys
ch = "character_" + sys.argv[1]
cfg = os.path.expandvars(r"%APPDATA%\Brotato\brotato_agent\agent_config.json")
WANT = {"auto_start": True, "character": ch, "danger": 0, "movement_estop_enabled": False,
        "weapon_prefixes": ["weapon_pistol","weapon_smg","weapon_revolver","weapon_shredder",
                            "weapon_crossbow","weapon_laser_gun","weapon_"]}
open(cfg, "w", encoding="utf-8").write(json.dumps(WANT, indent=2))
back = json.loads(open(cfg, encoding="utf-8-sig").read())
bad = {k: (v, back.get(k)) for k, v in WANT.items() if back.get(k) != v}
if bad:
    print("  READBACK MISMATCH:", bad); raise SystemExit(1)
print(f"  ARMED and read back: {ch}")
PY

  echo "--- ARM=$ARM  CHARACTER=$CH  collecting $RUNS runs ---"
  "$PY" scripts/overnight_supervisor.py --runs "$RUNS" --min-wins 0 --no-deploy \
      --disarm-on-finish --state-file "$STATE" --report-prefix "gen_${ARM}_${CH}" \
      > ".tmp/gen_${ARM}_${CH}/supervisor.log" 2>&1
  RC=$?

  GOT=$("$PY" -c "import json,sys; print(len(json.load(open(sys.argv[1],encoding='utf-8-sig'))['collected_run_ids']))" "$STATE" 2>/dev/null || echo 0)
  echo "--- $CH finished rc=$RC collected=$GOT/$RUNS ---"
  if [ "$GOT" -eq 0 ]; then
    echo "ABORT: $CH produced ZERO runs — the experiment is dead, not unlucky."
    kill_game; exit 4
  fi
  if [ "$GOT" -lt "$RUNS" ]; then
    echo "WARN: $CH short ($GOT/$RUNS) — re-run this script to top it up before analysing."
  fi
done

kill_game
echo ""
echo "=== ARM=$ARM COMPLETE — game killed. ==="
"$PY" - <<'PY'
import json, os
cfg = os.path.expandvars(r"%APPDATA%\Brotato\brotato_agent\agent_config.json")
print("  final auto_start:", json.loads(open(cfg, encoding="utf-8-sig").read()).get("auto_start"))
PY
