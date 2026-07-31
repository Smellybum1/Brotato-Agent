"""Per-attempt ledger for a character-unlock campaign.

Implements reports/wp2/character_unlock_prereg.md section 4 (validity) and
section 5 (stopping rule). READ-ONLY: reads the campaign state file and the run
summaries, writes a .csv and a .md at --out. It never touches the game, the mod,
or agent_config.json.

Discipline notes baked in:
  * summary.danger is a hardcoded literal 0 and carries NO information; validity
    uses requested_danger + danger_ok only. config_id is likewise a hardcoded
    constant and is never grouped on.
  * character_observed == "(never-read)" means no combat tick ever ran: a
    TECHNICAL FAILURE, reported as its own category, never a defeat and never a
    silent pass.
  * technical failures are recorded and reported, never dropped and never
    excluded on the basis of their outcome.
  * every count is printed with its denominator.
  * the unlock_pool era stamp is reported per attempt and its drift is reported
    as DATA; no expected delta is asserted.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

NEVER_READ = "(never-read)"

# Weapon type is resolved from the GAME SOURCE, never from the weapon's name.
# weapon_type.gd: enum {MELEE, RANGED} -> MELEE = 0, RANGED = 1.
WEAPON_SOURCE_DIR = os.path.join(
    "third_party", "brotatoai", "src", "brotato_sources", "weapons"
)
MELEE, RANGED = 0, 1
_MY_ID_RE = re.compile(r'^my_id\s*=\s*"([^"]+)"', re.M)
_TYPE_RE = re.compile(r"^type\s*=\s*(\d+)", re.M)

FIELDS = [
    "attempt_n",
    "run_id",
    "result",
    "last_wave",
    "requested_character",
    "character_observed",
    "character_ok",
    "requested_danger",
    "danger_ok",
    "mod_version",
    "unlock_pool.items",
    "unlock_pool.weapons",
    "unlock_pool.items_hash",
    "starting_weapon",
    "arm",
    "valid",
    "invalid_reason",
]

# Positive controls for any unlock-id membership test (see godot_string_hash).
UNLOCK_POSITIVE_CONTROLS = [
    "item_potato",
    "item_padding",
    "item_night_goggles",
    "item_lens",
]


def godot_string_hash(s: str) -> int:
    """Godot String.hash(): djb2, h = h*33 + c, masked to 32 bits.

    items_unlocked / challenges_completed are list[int] of THESE values, so a
    raw string membership test is structurally incapable of returning True.
    """
    h = 5381
    for ch in s:
        h = (h * 33 + ord(ch)) & 0xFFFFFFFF
    return h


def build_weapon_type_map(repo_root: str) -> Dict[str, int]:
    """Map weapon my_id -> WeaponType int, parsed from the *_data.tres sources."""
    out: Dict[str, int] = {}
    root = os.path.join(repo_root, WEAPON_SOURCE_DIR)
    for path in glob.glob(os.path.join(root, "**", "*_data.tres"), recursive=True):
        try:
            with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        m_id = _MY_ID_RE.search(text)
        m_ty = _TYPE_RE.search(text)
        if m_id and m_ty:
            out[m_id.group(1)] = int(m_ty.group(1))
    return out


def read_run_start_weapon(runs_dir: str, run_id: str) -> str:
    """Read ONLY the first line of events.jsonl and return run_start.payload.weapon."""
    path = os.path.join(runs_dir, run_id, "events.jsonl")
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            first = fh.readline()
    except OSError:
        return ""
    if not first.strip():
        return ""
    try:
        ev = json.loads(first)
    except ValueError:
        return ""
    if ev.get("event") != "run_start":
        return ""
    return (ev.get("payload") or {}).get("weapon", "") or ""


def classify_arm(weapon_id: str, wtypes: Dict[str, int]) -> Tuple[str, str]:
    """Return (arm, note) for the observed starting weapon.

    The label DESCRIBES what was observed -- "<weapon_id> (MELEE|RANGED)" -- and
    carries no campaign-specific story. MELEE/RANGED comes from the source
    `type` field (weapon_type.gd: MELEE=0, RANGED=1); anything unresolvable is
    UNKNOWN, never guessed.
    """
    if not weapon_id:
        return "UNKNOWN", "no run_start weapon"
    t = wtypes.get(weapon_id)
    if t == MELEE:
        return "%s (MELEE)" % weapon_id, ""
    if t == RANGED:
        return "%s (RANGED)" % weapon_id, ""
    if t is None:
        return "UNKNOWN", "weapon type unresolved in source: %s" % weapon_id
    return "UNKNOWN", "%s has unrecognised source type %r" % (weapon_id, t)


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def read_summary(runs_dir: str, run_id: str) -> Optional[Dict[str, Any]]:
    path = os.path.join(runs_dir, run_id, "summary.json")
    if not os.path.isfile(path):
        return None
    try:
        return load_json(path)
    except (ValueError, OSError):
        return None


def evaluate(
    attempt_n: int,
    run_id: str,
    summary: Optional[Dict[str, Any]],
    character: str,
    mod_version: str,
    starting_weapon: str = "",
    arm: str = "UNKNOWN",
    arm_note: str = "",
) -> Dict[str, Any]:
    row: Dict[str, Any] = {f: "" for f in FIELDS}
    row["attempt_n"] = attempt_n
    row["run_id"] = run_id
    row["starting_weapon"] = starting_weapon
    row["arm"] = arm
    row["arm_note"] = arm_note

    if summary is None:
        row["result"] = "pending"
        row["valid"] = False
        row["invalid_reason"] = "no summary (run in progress or summary missing)"
        row["technical_failure"] = True
        row["pending"] = True
        return row

    pool = summary.get("unlock_pool") or {}
    row["result"] = summary.get("result", "")
    row["last_wave"] = summary.get("last_wave", "")
    row["requested_character"] = summary.get("requested_character", "")
    row["character_observed"] = summary.get("character_observed", "")
    row["character_ok"] = summary.get("character_ok", "")
    row["requested_danger"] = summary.get("requested_danger", "")
    row["danger_ok"] = summary.get("danger_ok", "")
    row["mod_version"] = summary.get("mod_version", "")
    row["unlock_pool.items"] = pool.get("items", -1)
    row["unlock_pool.weapons"] = pool.get("weapons", -1)
    row["unlock_pool.items_hash"] = pool.get("items_hash", "")
    row["pending"] = False

    reasons: List[str] = []
    never_read = row["character_observed"] == NEVER_READ
    if never_read:
        reasons.append(
            'character_observed == "(never-read)": no combat tick ever ran '
            "(TECHNICAL FAILURE, not a character mismatch)"
        )
    if row["requested_character"] != character:
        reasons.append(
            "requested_character %r != --character %r"
            % (row["requested_character"], character)
        )
    if not never_read and row["character_observed"] != row["requested_character"]:
        reasons.append(
            "character_observed %r != requested_character %r"
            % (row["character_observed"], row["requested_character"])
        )
    if row["character_ok"] is not True:
        reasons.append("character_ok is %r, not True" % (row["character_ok"],))
    if row["requested_danger"] != 0:
        reasons.append("requested_danger is %r, not 0" % (row["requested_danger"],))
    if row["danger_ok"] is not True:
        reasons.append("danger_ok is %r, not True" % (row["danger_ok"],))
    if row["mod_version"] != mod_version:
        reasons.append(
            "mod_version %r != pin %r" % (row["mod_version"], mod_version)
        )

    row["valid"] = not reasons
    row["invalid_reason"] = "; ".join(reasons)
    # A technical failure is a run that could not produce a usable attempt at
    # all -- no combat tick. Outcome plays no part in this classification.
    row["technical_failure"] = never_read
    return row


def render_table(rows: List[Dict[str, Any]]) -> str:
    cols = FIELDS
    data = [[str(r.get(c, "")) for c in cols] for r in rows]
    widths = [
        max(len(cols[i]), *(len(d[i]) for d in data)) if data else len(cols[i])
        for i in range(len(cols))
    ]
    out = [" | ".join(c.ljust(widths[i]) for i, c in enumerate(cols))]
    out.append("-+-".join("-" * w for w in widths))
    for d in data:
        out.append(" | ".join(d[i].ljust(widths[i]) for i in range(len(cols))))
    return "\n".join(out)


def build_report(
    rows: List[Dict[str, Any]],
    character: str,
    mod_version: str,
    state_file: str,
    runs_dir: str,
) -> str:
    n = len(rows)
    valid = [r for r in rows if r["valid"]]
    tech = [r for r in rows if r.get("technical_failure")]
    pending = [r for r in rows if r.get("pending")]
    invalid_not_tech = [r for r in rows if not r["valid"] and not r.get("technical_failure")]
    victories = [r for r in valid if r["result"] == "victory"]
    defeats = [r for r in valid if r["result"] == "defeat"]
    other = [r for r in valid if r["result"] not in ("victory", "defeat")]

    L: List[str] = []
    L.append("# Character-unlock attempt ledger — %s" % character)
    L.append("")
    L.append("Prereg: `reports/wp2/character_unlock_prereg.md` §4 (validity), §5 (stopping rule).")
    L.append("")
    L.append("- state file: `%s`" % state_file)
    L.append("- runs dir: `%s`" % runs_dir)
    L.append("- version pin: `%s`" % mod_version)
    L.append("")
    L.append("## Per-attempt ledger")
    L.append("")
    L.append("| " + " | ".join(FIELDS) + " |")
    L.append("|" + "|".join("---" for _ in FIELDS) + "|")
    for r in rows:
        L.append("| " + " | ".join(str(r.get(c, "")) for c in FIELDS) + " |")
    L.append("")
    L.append("## Counts (denominators printed)")
    L.append("")
    L.append("- attempts collected: **%d** (rows in `collected_run_ids`)" % n)
    L.append("- attempts valid: **%d / %d collected**" % (len(valid), n))
    L.append(
        "- technical failures (`character_observed == \"(never-read)\"`, no combat "
        "tick): **%d / %d collected** — recorded, never excluded on outcome"
        % (len(tech), n)
    )
    L.append(
        "- pending (no `summary.json` yet; campaign is live): **%d / %d collected**"
        % (len(pending), n)
    )
    L.append(
        "- invalid for other §4 reasons: **%d / %d collected**"
        % (len(invalid_not_tech), n)
    )
    L.append("")
    L.append("## Outcomes (valid attempts only, denominator = %d valid)" % len(valid))
    L.append("")
    L.append("| outcome | count | of valid |")
    L.append("|---|---|---|")
    L.append("| victory | %d | %d |" % (len(victories), len(valid)))
    L.append("| defeat | %d | %d |" % (len(defeats), len(valid)))
    L.append("| other/unknown | %d | %d |" % (len(other), len(valid)))
    L.append("")
    L.append(
        "Terminal waves, raw, in collection order (valid attempts): %s"
        % ([r["last_wave"] for r in valid] or "none")
    )
    L.append(
        "Terminal waves, raw, ALL collected rows incl. invalid/pending: %s"
        % ([r["last_wave"] for r in rows] or "none")
    )
    L.append("")
    arms_seen: List[str] = []
    for r in rows:
        if r["arm"] not in arms_seen:
            arms_seen.append(r["arm"])
    weapons_seen: List[str] = []
    for r in rows:
        w = r["starting_weapon"] or "(none)"
        if w not in weapons_seen:
            weapons_seen.append(w)
    multi_arm = len(weapons_seen) > 1

    L.append("## Starting weapon / arm")
    L.append("")
    L.append(
        "`arm` is derived from the run's `run_start` event `weapon` field, with "
        "MELEE/RANGED resolved from the game source "
        "(`weapons/**/*_data.tres` `type`, `weapon_type.gd` `{MELEE=0, RANGED=1}`). "
        "Unresolvable weapons are `UNKNOWN`, never guessed."
    )
    L.append("")
    if not multi_arm:
        only_a = arms_seen[0] if arms_seen else "UNKNOWN"
        L.append(
            "**Single arm throughout: `%s`, %d/%d attempts.** No per-arm split is "
            "reported: with one arm the comparison table would be meaningless."
            % (only_a, len(rows), len(rows))
        )
    if multi_arm:
        L.append(
            "### Outcomes BY ARM (prereg §8c — the starting weapon changed mid-campaign)"
        )
        L.append("")
        L.append(
            "⚠️ **This is NOT a controlled comparison.** The arms are sequential, not "
            "randomised; n is tiny; and the configuration change was made after "
            "observing two defeats. Attempts 1-2 are kept and counted in full — "
            "discarding known defeats would select on outcome. Read the split as "
            "bookkeeping, not as an experiment."
        )
        L.append("")
        L.append("| arm | attempts | valid | victories (of valid) | defeats (of valid) | terminal waves, raw, collection order |")
        L.append("|---|---|---|---|---|---|")
    for a in arms_seen if multi_arm else []:
        ar = [r for r in rows if r["arm"] == a]
        av = [r for r in ar if r["valid"]]
        L.append(
            "| %s | %d | %d / %d | %d / %d | %d / %d | %s |"
            % (
                a,
                len(ar),
                len(av),
                len(ar),
                len([r for r in av if r["result"] == "victory"]),
                len(av),
                len([r for r in av if r["result"] == "defeat"]),
                len(av),
                [r["last_wave"] for r in ar],
            )
        )
    if multi_arm:
        L.append(
            "| **POOLED** | %d | %d / %d | %d / %d | %d / %d | %s |"
            % (
                n,
                len(valid),
                n,
                len(victories),
                len(valid),
                len(defeats),
                len(valid),
                [r["last_wave"] for r in rows],
            )
        )
    L.append("")
    L.append("| attempt_n | run_id | starting_weapon | arm | note |")
    L.append("|---|---|---|---|---|")
    for r in rows:
        L.append(
            "| %s | %s | %s | %s | %s |"
            % (r["attempt_n"], r["run_id"], r["starting_weapon"] or "(none)", r["arm"], r.get("arm_note", ""))
        )
    L.append("")
    L.append("## `unlock_pool` era stamp per attempt")
    L.append("")
    L.append(
        "The pool drifts from ordinary play — `ChallengeService.unlock_reward` "
        "appends on challenge completion, which happens on defeats too. A change "
        "here is DATA, not a defect. No expected delta is asserted."
    )
    L.append("")
    L.append("| attempt_n | run_id | items | weapons | items_hash |")
    L.append("|---|---|---|---|---|")
    for r in rows:
        L.append(
            "| %s | %s | %s | %s | %s |"
            % (
                r["attempt_n"],
                r["run_id"],
                r["unlock_pool.items"],
                r["unlock_pool.weapons"],
                r["unlock_pool.items_hash"],
            )
        )
    stamps = [
        (r["unlock_pool.items"], r["unlock_pool.weapons"], r["unlock_pool.items_hash"])
        for r in rows
        if not r.get("pending")
    ]
    distinct = []
    for s in stamps:
        if s not in distinct:
            distinct.append(s)
    L.append("")
    L.append(
        "- distinct era stamps across %d attempts with a summary: **%d**"
        % (len(stamps), len(distinct))
    )
    if len(distinct) <= 1:
        L.append("- era CHANGED during the campaign: **no** (single stamp observed)")
    else:
        L.append("- era CHANGED during the campaign: **YES**")
        for s in distinct:
            L.append("  - items=%s weapons=%s items_hash=%s" % s)
        L.append(
            "  Runs from different stamps must not be pooled without era-matching."
        )
    L.append("")
    L.append("## §5 stopping rule")
    L.append("")
    if victories:
        L.append(
            "- **REACHED — first victory at attempt %s (`%s`).** Stop this "
            "character; the item is unlocked and further runs add nothing."
            % (victories[0]["attempt_n"], victories[0]["run_id"])
        )
    elif len(rows) >= 8:
        L.append(
            "- **REACHED — %d attempts collected (cap 8) with 0 victories among "
            "%d valid.** §5: stop and report rather than extending."
            % (len(rows), len(valid))
        )
    else:
        L.append(
            "- **NOT reached** — %d of 8 attempts collected, 0 victories among %d "
            "valid. %d attempts remain in this character's budget."
            % (len(rows), len(valid), 8 - len(rows))
        )
    L.append("")
    L.append("## Notes on fields deliberately NOT used")
    L.append("")
    L.append(
        "- `summary.danger` is a hardcoded literal `0` and carries no information; "
        "danger validity is evaluated from `requested_danger` and `danger_ok`."
    )
    L.append(
        "- `config_id` is a hardcoded string constant (1 distinct value across 299 "
        "runs); nothing is grouped or conditioned on it."
    )
    L.append(
        "- §4's \"capture stream parses to EOF\" is NOT evaluated here: only the "
        "FIRST line of `events.jsonl` is read (for `run_start.weapon`), never the "
        "whole capture stream. The `valid` column covers the identity and pin "
        "criteria only."
    )
    return "\n".join(L) + "\n"


def write_outputs(rows: List[Dict[str, Any]], out_prefix: str, md: str) -> None:
    parent = os.path.dirname(os.path.abspath(out_prefix))
    if parent:
        os.makedirs(parent, exist_ok=True)
    csv_path = out_prefix + ".csv"
    md_path = out_prefix + ".md"
    with open(csv_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(md)
    print("wrote %s" % csv_path)
    print("wrote %s" % md_path)


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state-file", required=True)
    p.add_argument(
        "--runs-dir",
        required=True,
        help=r"e.g. C:\Users\<user>\AppData\Roaming\Brotato\brotato_agent\runs",
    )
    p.add_argument("--character", required=True)
    p.add_argument("--mod-version", required=True)
    p.add_argument("--out", required=True, help="output prefix; .csv and .md are written")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    state = load_json(args.state_file)
    run_ids = list(state.get("collected_run_ids") or [])

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    wtypes = build_weapon_type_map(repo_root)
    print("weapon type entries parsed from source: %d" % len(wtypes))
    for ctl, expect in (("weapon_plank_1", MELEE), ("weapon_shredder_1", RANGED)):
        got = wtypes.get(ctl)
        print(
            "  source control %s: type=%r expected=%r %s"
            % (ctl, got, expect, "OK" if got == expect else "MISMATCH")
        )

    rows = []
    for i, rid in enumerate(run_ids, start=1):
        wpn = read_run_start_weapon(args.runs_dir, rid)
        arm, note = classify_arm(wpn, wtypes)
        rows.append(
            evaluate(
                i,
                rid,
                read_summary(args.runs_dir, rid),
                args.character,
                args.mod_version,
                wpn,
                arm,
                note,
            )
        )

    md = build_report(rows, args.character, args.mod_version, args.state_file, args.runs_dir)

    # Write the artifacts FIRST. A console encoding failure must never leave
    # stale output files behind while the command merely looks like it failed.
    write_outputs(rows, args.out, md)

    print("collected_run_ids: %d" % len(run_ids))
    print()
    print(render_table(rows))
    print()
    for r in rows:
        if r["invalid_reason"]:
            print("attempt %s (%s) INVALID: %s" % (r["attempt_n"], r["run_id"], r["invalid_reason"]))
    print()
    print(md)
    return 0


def _make_stdout_robust() -> None:
    """stdout must survive a cp1252 console; do not rely on PYTHONIOENCODING."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


if __name__ == "__main__":
    _make_stdout_robust()
    raise SystemExit(main())
