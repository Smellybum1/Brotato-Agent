#!/usr/bin/env bash
# §29 — first Danger 5 victory attempt, character = ranger.
#
#   usage: bash scripts/d5_ranger_campaign.sh
#
# Prereg: reports/wp2/d5_ranger_attempt_prereg.md
#
# Adapted from d5_pair_campaign.sh (§26), which is the proven full-run driver.
# Design rules this encodes, each earned:
#   * The config is read ONCE at _ready(), so the game must be KILLED before
#     arming or the run silently uses the previous arm.
#   * Any step that ARMS an experiment needs a READBACK and must ABORT on
#     mismatch — here BOTH character AND danger.
#   * weapon_pistol FIRST: all 16 ranger evidence runs opened weapon_pistol_1,
#     and _select_inventory_by_id_prefix is a SUBSTRING match tried IN ORDER.
#     Ranger HAS an smg, so an smg-first list opens ranger on the wrong weapon.
#     A disk readback does NOT prove this — certify from run_start.weapon.
#   * NO --stop-on-win (§22 + operator decision 2026-08-03): fixed n=16.
#   * --min-wins 0: not a win-rate gate, and the default 18 makes the early
#     abort fire instantly (GATE IMPOSSIBLE). With 0, max_losses=16 and the
#     abort is unreachable in a 16-run campaign — that is what keeps the
#     supervisor free of any reject-by-outcome path.
#   * --no-deploy: the build is FROZEN. deploy_mod.py would rewrite the arm
#     from a hardcoded dict (danger 0, and it DROPS movement_estop_enabled).
#     The supervisor still calls deploy_mod.py --repair-launch on every launch,
#     which clears ModLoader's mods-disabled latch without touching the arm.
#   * A block yielding 0 runs must ABORT, not continue.
set -u

cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
CHARACTER="ranger"
DANGER=5
RUNS=16
PY=".venv/Scripts/python.exe"
STATE=".tmp/d5_ranger/state.json"
mkdir -p .tmp/d5_ranger

kill_game() {
  MSYS_NO_PATHCONV=1 taskkill /IM Brotato.exe /F >/dev/null 2>&1 || true
  sleep 4
}

echo "=== §29 first D5 attempt  character=$CHARACTER  danger=$DANGER  runs=$RUNS ==="

# --- Preflight: the installed build must be the frozen one, port INERT. ---
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
    raise SystemExit("ABORT: the port is NOT inert — §29 requires it disarmed")
PY

# --- Preflight: record the era we are entering at (drift is disclosed, not fatal). ---
"$PY" - <<'PY'
import json, os
def djb2(s):
    h = 5381
    for c in s.encode("utf-8"): h = ((h * 33) + c) & 0xFFFFFFFF
    return h
save = json.load(open(os.path.join(os.environ["APPDATA"], "Brotato",
        "76561198030888875", "save_v3_0.json"), encoding="utf-8-sig"))
items, weps, chals = save["items_unlocked"], save["weapons_unlocked"], save["challenges_completed"]
# positive controls: these MUST be True, else the membership test is broken
ctrl = all(djb2(c) in items for c in
           ("item_potato", "item_padding", "item_night_goggles", "item_lens"))
print(f"  save era      : items={len(items)} weapons={len(weps)} challenges={len(chals)}")
print(f"  controls pass : {ctrl}")
if not ctrl:
    raise SystemExit("ABORT: unlock positive controls failed — the era check is broken")
# ranger era-safety: its reward is already unlocked, so a win grants nothing
safe = djb2("item_night_goggles") in items and djb2("chal_ranger") in chals
print(f"  ranger era-safe: {safe}  (reward item_night_goggles already unlocked)")
PY

# --- Arm, with an abort-on-mismatch readback. ---
echo ""
echo "--- arming  character=$CHARACTER  danger=$DANGER ---"
kill_game
"$PY" - "$CHARACTER" "$DANGER" <<'PY' || { echo "ABORT: arming failed"; exit 3; }
import json, os, sys
ch = "character_" + sys.argv[1]
danger = int(sys.argv[2])
cfg = os.path.expandvars(r"%APPDATA%\Brotato\brotato_agent\agent_config.json")
WANT = {"auto_start": True, "character": ch, "danger": danger,
        "movement_estop_enabled": False,
        # pistol FIRST — see the header. All ranger evidence runs opened pistol.
        "weapon_prefixes": ["weapon_pistol","weapon_smg","weapon_revolver","weapon_shredder",
                            "weapon_crossbow","weapon_laser_gun","weapon_"]}
open(cfg, "w", encoding="utf-8").write(json.dumps(WANT, indent=2))
back = json.loads(open(cfg, encoding="utf-8-sig").read())
bad = {k: (v, back.get(k)) for k, v in WANT.items() if back.get(k) != v}
if bad:
    print("  READBACK MISMATCH:", bad); raise SystemExit(1)
print(f"  ARMED and read back: {ch}  danger={danger}  pistol-first prefixes")
PY

echo "--- collecting $RUNS runs (fixed n, NO stop-on-win) ---"
"$PY" scripts/overnight_supervisor.py --runs "$RUNS" --min-wins 0 --no-deploy \
    --disarm-on-finish --state-file "$STATE" --report-prefix "d5_ranger" \
    > ".tmp/d5_ranger/supervisor.log" 2>&1
RC=$?

GOT=$("$PY" -c "import json,sys; print(len(json.load(open(sys.argv[1],encoding='utf-8-sig'))['collected_run_ids']))" "$STATE" 2>/dev/null || echo 0)
echo "--- finished rc=$RC collected=$GOT/$RUNS ---"
if [ "$GOT" -eq 0 ]; then
  echo "ABORT: ZERO runs collected — the experiment is dead, not unlucky."
  kill_game; exit 4
fi
if [ "$GOT" -lt "$RUNS" ]; then
  echo "WARN: short ($GOT/$RUNS) — re-run this script to top up before analysing."
fi

kill_game
echo ""
echo "=== §29 COMPLETE — game killed. ==="
"$PY" - <<'PY'
import json, os
cfg = os.path.expandvars(r"%APPDATA%\Brotato\brotato_agent\agent_config.json")
print("  final auto_start:", json.loads(open(cfg, encoding="utf-8-sig").read()).get("auto_start"))
PY
