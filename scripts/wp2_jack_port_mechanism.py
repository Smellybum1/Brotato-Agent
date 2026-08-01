"""§24 profile-port — EXPLORATORY mechanism analysis. NOT the pre-registered test.

Written 2026-08-01 with block A2 at 12/16 and B2 unstarted, i.e. blind to half the
design, for the same reason the primary was: so the quantities are chosen before
they can be chosen to suit an answer.

STATUS, and it is not negotiable: **EXPLORATORY**. The confirmatory result is
`wp2_jack_power_analysis.py` (terminal wave, exact permutation, one-sided, a=0.05).
Nothing here may be substituted for it, and nothing here gets a verdict. If the
primary is null, a striking number in this file does NOT rescue it — that
substitution is the §18b failure this campaign exists to avoid.

WHY IT EXISTS: a positive primary says the port helps Jack. It does not say how,
and without a mechanism the result generalises to no other character. These are
the pre-specified candidate mechanisms, in the order they will be reported.

  M1 OFFENSE      sum weapon damage at wave-17 entry, and nominal dps.
                  The strongest existing finding on this project is that wave-17
                  deaths separate on OFFENSE (rank-biserial 0.188, doomed runs
                  entering with half the weapon damage) while defense does not
                  separate at all. If the port works by raising offense, these two
                  findings become one story.
  M2 CLEARANCE    standing enemies at waves 15/17, and enemy lifetime L/lambda.
                  Offense should show up downstream as a shorter enemy lifetime.
                  This is the mechanism's own readback: M1 without M2 means the
                  damage went somewhere that did not kill anything.
  M3 ECONOMY      materials collected, weapon buys, tier reached.
                  The rival explanation: the port buys differently rather than
                  fighting better.
  M4 SURVIVAL     HP-deficit exposure. Distinguishes "kills faster" from
                  "takes less damage", which M1-M3 cannot separate.

DISCIPLINE NOTES, each earned the hard way on this project:
  * Report DISTRIBUTIONS per arm, never a single pooled number. Wave population is
    bimodal by outcome; a pooled median describes whichever outcome is commoner.
  * `damage_taken` is a GROSS counter that never subtracts healing. It is reported
    as a component only and must not be read as harm.
  * Enemy lifetime is L/lambda and lambda comes from an EXTERNAL simulated spawn
    table (Brotato II session, marked INFERRED there). Flag it as such; it is not
    our measurement.
  * Terminal-wave differences make late-wave per-run statistics survivor-selected:
    a wave-17 quantity exists only for runs that REACHED wave 17. Report the
    denominator per arm every time.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics as st
from pathlib import Path

BLOCKS = {"A1": "PORTED", "A2": "PORTED", "B1": "BARE", "B2": "BARE"}
EXPECTED_PER_BLOCK = 16

# Simulated spawn flow, enemies/sec, danger 0. EXTERNAL and marked INFERRED by its
# source (decompiled wave composition, Brotato II session). Not our measurement.
SPAWN_FLOW_D0 = {15: 7.2, 17: 4.4, 19: 10.7, 20: 2.7}


def load_ids(root: Path) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for block in BLOCKS:
        p = root / ".tmp" / f"jack_power_{block}" / "state.json"
        if not p.exists():
            raise FileNotFoundError(f"block {block} has no state file: {p}")
        ids = json.loads(p.read_text(encoding="utf-8-sig"))["collected_run_ids"]
        if len(ids) != EXPECTED_PER_BLOCK:
            raise RuntimeError(f"block {block} holds {len(ids)}/{EXPECTED_PER_BLOCK} runs")
        out[block] = ids
    return out


def scan_run(runs_dir: Path, rid: str) -> dict:
    """One pass over a run: entry offense per wave, standing enemies, economy."""
    ev = runs_dir / rid / "events.jsonl"
    first_cap: dict[int, dict] = {}
    standing: dict[int, list[int]] = {}
    hp_ratio: list[float] = []
    weapon_buys = melee_buys = 0
    board: dict[str, str | None] = {}
    with ev.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            if '"combat_capture"' in line:
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                pay = e.get("payload") or {}
                w = pay.get("wave")
                if w is None:
                    continue
                ents = pay.get("entities") or {}
                standing.setdefault(w, []).append(len(ents.get("enemies") or []))
                if w not in first_cap:
                    first_cap[w] = pay
                pl = pay.get("player") or {}
                mx, hp = pl.get("max_hp"), pl.get("hp")
                if isinstance(mx, (int, float)) and mx > 0 and isinstance(hp, (int, float)):
                    hp_ratio.append(max(0.0, min(1.0, hp / mx)))
            elif '"purchase_' in line:
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                if e.get("event") == "purchase_offer":
                    board = {it.get("id"): it.get("weapon_type")
                             for it in (e.get("payload") or {}).get("items") or []}
                elif e.get("event") == "purchase_decision":
                    act = ((e.get("payload") or {}).get("action") or {})
                    if act.get("type") == "shop_buy":
                        wt = board.get(act.get("item_id"))
                        if wt is not None:
                            weapon_buys += 1
                            if wt == "melee":
                                melee_buys += 1

    def entry_damage(w: int):
        pay = first_cap.get(w)
        if not pay:
            return None
        ws = pay.get("weapons") or []
        tot = 0.0
        for wp in ws:
            d = wp.get("damage")
            if isinstance(d, (int, float)):
                tot += d
        return tot or None

    return {
        "run_id": rid,
        "reached": max(standing) if standing else 0,
        "entry_damage": {w: entry_damage(w) for w in (10, 15, 17)},
        "standing": {w: (st.median(v) if v else None) for w, v in standing.items()},
        "hp_deficit_auc": (1.0 - st.mean(hp_ratio)) if hp_ratio else None,
        "weapon_buys": weapon_buys,
        "melee_buys": melee_buys,
    }


def describe(name: str, vals: list[float], denom: int, total: int) -> str:
    vals = [v for v in vals if v is not None]
    if not vals:
        return f"    {name:<26} n=0/{total}  (no run produced this)"
    med = st.median(vals)
    lo, hi = min(vals), max(vals)
    return (f"    {name:<26} n={denom}/{total}  median {med:>9.3f}   range {lo:>8.3f}-{hi:<8.3f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--runs-dir", default=None)
    args = ap.parse_args()
    root = Path(args.root).resolve()
    runs_dir = Path(args.runs_dir) if args.runs_dir else Path(
        os.path.expandvars(r"%APPDATA%\Brotato\brotato_agent\runs"))

    try:
        ids = load_ids(root)
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"REFUSING TO RUN — {exc}")
        print("This is the EXPLORATORY mechanism analysis; it still waits for the full design,")
        print("because a mechanism read off a prefix is a story fitted to noise.")
        return 2

    print("=" * 74)
    print("§24 MECHANISM — EXPLORATORY. The confirmatory result is wp2_jack_power_analysis.py.")
    print("No verdict is issued here and nothing here may substitute for the primary.")
    print("=" * 74)

    arms: dict[str, list[dict]] = {"PORTED": [], "BARE": []}
    for block, run_ids in ids.items():
        for rid in run_ids:
            if not (runs_dir / rid / "events.jsonl").exists():
                continue
            arms[BLOCKS[block]].append(scan_run(runs_dir, rid))

    for arm, rows in arms.items():
        n = len(rows)
        print(f"\n{'='*74}\n{arm}  n={n}\n{'='*74}")
        reached = [r["reached"] for r in rows]
        print(f"  terminal wave reached: median {st.median(reached)}, range {min(reached)}-{max(reached)}")

        print("\n  M1 OFFENSE — summed weapon damage at wave entry")
        for w in (10, 15, 17):
            vals = [r["entry_damage"].get(w) for r in rows]
            got = sum(1 for v in vals if v is not None)
            print("  " + describe(f"entry damage w{w}", vals, got, n)
                  + ("   <-- SURVIVOR-SELECTED" if got < n else ""))

        print("\n  M2 CLEARANCE — standing enemies (median per run), and lifetime L/lambda")
        for w in (15, 17):
            vals = [r["standing"].get(w) for r in rows]
            got = sum(1 for v in vals if v is not None)
            print("  " + describe(f"standing enemies w{w}", vals, got, n)
                  + ("   <-- SURVIVOR-SELECTED" if got < n else ""))
            ok = [v for v in vals if v is not None]
            if ok and w in SPAWN_FLOW_D0:
                print(f"      -> mean enemy lifetime w{w} = {st.median(ok)/SPAWN_FLOW_D0[w]:.2f} s"
                      f"   [lambda={SPAWN_FLOW_D0[w]}/s EXTERNAL, simulated, not measured here]")

        print("\n  M3 ECONOMY — weapon purchasing")
        wb = sum(r["weapon_buys"] for r in rows)
        mb = sum(r["melee_buys"] for r in rows)
        print(f"    weapon buys (arm total)    {wb}")
        print(f"    melee buys  (arm total)    {mb}   share {mb/wb:.4f}" if wb else "    no weapon buys")

        print("\n  M4 SURVIVAL — HP-deficit exposure, mean(1 - hp/max_hp) over captures")
        print("  " + describe("hp deficit auc", [r["hp_deficit_auc"] for r in rows],
                              sum(1 for r in rows if r["hp_deficit_auc"] is not None), n))

    print("\n" + "=" * 74)
    print("Read M1 and M2 TOGETHER: offense without a shorter enemy lifetime means the")
    print("damage did not convert into clearance. Neither alone is a mechanism.")
    print("Late-wave rows marked SURVIVOR-SELECTED exist only for runs that got there;")
    print("if the arms differ in terminal wave, those rows are conditioned on the outcome.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
