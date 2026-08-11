#!/usr/bin/env bash
# §27 acquisition block 1 — five gating characters, 8 runs each.
#
#   usage: bash scripts/acq_campaign.sh
#
# Prereg: reports/wp2/acquisition_block_prereg.md
#
# ⛔ DO NOT LAUNCH WHILE §26 IS RUNNING.
#
# Design rules this encodes, each earned:
#   * The config is read ONCE at _ready(), so the game must be KILLED between
#     characters or the next block silently runs the previous character.
#   * Arming needs a READBACK and must ABORT on mismatch.
#   * A block yielding 0 runs must ABORT, not continue.
#   * No --stop-on-win (§22/§20a): the unlock is granted at the win either way,
#     so running all 8 keeps the win-rate estimate uncensored for ~1 h.
#   * --min-wins 0: not a win-rate gate; the default 18 aborts instantly.
#   * --no-deploy: the build is FROZEN.
#
# NOTE, and it is the point of the campaign: the era WILL drift here. Every
# character has a LOCKED reward, so a win moves the shop pool. That is the
# objective, not a fault. Win rates from this campaign are NOT era-matched.
set -u

cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
CHARACTERS="soldier renegade cyborg hunter one_arm"
RUNS=8
PY=".venv/Scripts/python.exe"

kill_game() {
  MSYS_NO_PATHCONV=1 taskkill /IM Brotato.exe /F >/dev/null 2>&1 || true
  sleep 4
}

echo "=== §27 acquisition block 1  characters: $CHARACTERS  runs/character: $RUNS ==="
"$PY" - <<'PY' || exit 1
import zipfile
z = zipfile.ZipFile(r"C:\Games\Steam\steamapps\workshop\content\1942280\3737864106\Tom-BrotatoAgent.zip")
cfg = z.read("mods-unpacked/Tom-BrotatoAgent/teacher/config.gd").decode("utf-8", "replace")
ctl = z.read("mods-unpacked/Tom-BrotatoAgent/runtime/agent_controller.gd").decode("utf-8", "replace")
port = [l for l in cfg.splitlines() if "EXPERIMENT_PORT_WR_PROFILE_TO :=" in l][0].strip()
ver  = [l for l in ctl.splitlines() if "const MOD_VERSION" in l][0].strip()
print(f"  installed build: {ver}")
print(f"  installed port : {port}")
if ':=""' not in port.replace(' ', ''):
    raise SystemExit("ABORT: the port is NOT inert — this campaign requires it disarmed")
PY

# Refuse to run concurrently with the §26 driver — two campaigns cannot share
# the game, and the second would silently collect under the first one's arm.
#
# ⛔ THE PATTERN USES A BRACKET CLASS ON PURPOSE. A plain grep for the script
# name MATCHES ITS OWN COMMAND LINE (and every shell wrapper that mentions it):
# measured 10 matches where only 2 were the real driver, so a naive guard fires
# forever and blocks this campaign permanently. `d5_pair[_]campaign` does not
# occur literally in this query's own command line, and anchoring on
# `bash.exe" scripts/` excludes the `-c "source ..."` wrappers.
RUNNING=$(MSYS_NO_PATHCONV=1 wmic process get commandline 2>/dev/null | tr -d '\r' \
          | grep -cE 'bash\.exe" scripts/d5_pair[_]campaign\.sh' || true)
if [ "${RUNNING:-0}" -gt 0 ]; then
  echo "ABORT: §26 (the D0/D5 pair driver) is still running — $RUNNING process(es)."
  echo "       Two campaigns cannot share the game."
  exit 5
fi

for CH in $CHARACTERS; do
  STATE=".tmp/acq_${CH}/state.json"
  mkdir -p ".tmp/acq_${CH}"

  if [ -f "$STATE" ]; then
    HAVE=$("$PY" -c "import json,sys; print(len(json.load(open(sys.argv[1],encoding='utf-8-sig'))['collected_run_ids']))" "$STATE" 2>/dev/null || echo 0)
    if [ "$HAVE" -ge "$RUNS" ]; then
      echo "--- $CH already complete ($HAVE/$RUNS), skipping ---"
      continue
    fi
  fi

  echo ""
  echo "--- CHARACTER=$CH  arming ---"
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

  echo "--- CHARACTER=$CH  collecting $RUNS runs ---"
  "$PY" scripts/overnight_supervisor.py --runs "$RUNS" --min-wins 0 --no-deploy \
      --disarm-on-finish --state-file "$STATE" --report-prefix "acq_${CH}" \
      > ".tmp/acq_${CH}/supervisor.log" 2>&1
  RC=$?

  GOT=$("$PY" -c "import json,sys; print(len(json.load(open(sys.argv[1],encoding='utf-8-sig'))['collected_run_ids']))" "$STATE" 2>/dev/null || echo 0)
  echo "--- $CH finished rc=$RC collected=$GOT/$RUNS ---"
  if [ "$GOT" -eq 0 ]; then
    echo "ABORT: $CH produced ZERO runs — the experiment is dead, not unlucky."
    kill_game; exit 4
  fi
done

kill_game
echo ""
echo "=== §27 COMPLETE — game killed. Verify unlocks per prereg §27e (djb2 INTEGER hashes, positive controls). ==="
"$PY" - <<'PY'
import json, os
cfg = os.path.expandvars(r"%APPDATA%\Brotato\brotato_agent\agent_config.json")
print("  final auto_start:", json.loads(open(cfg, encoding="utf-8-sig").read()).get("auto_start"))
PY
