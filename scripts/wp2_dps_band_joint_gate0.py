"""§36 Gate 0: does the JOINT DPS-band lever (gate wave W x target scale k) flip shop decisions?

Implements reports/wp2/dps_band_joint_prereg.md exactly, including the §36c
amendment (Gate 0 required an instrument; 0.2.79 ships it).

THE CLAIM IS AN INTERACTION, NOT A MAIN EFFECT:
  (i)  the detector `_dps_below_band` returns false below OFFENSE_BAND_FROM_WAVE
       (=13) and D5 dies at median wave 11, so it never runs; and
  (ii) the target it would enforce, OFFENSE_DPS_TARGETS_BY_WAVE, was calibrated
       on 41 DANGER-0 victories -- the agent sits a median 1.314x ABOVE it and
       dies anyway.
Each fix alone is predicted inert. This tests whether together they do more than
the sum of their parts.

COUNTERFACTUAL. At (W, k):
    band_gate'(wave) = (wave >= W) and (weapon_dps < k * dps_target)
and when true a WEAPON candidate is dropped from the ranking loop iff
    slots_full and not pairs_combine and proj_dps_gain < band_impact_floor
exactly as shop_strategy.gd:1637-1641. All five operands are recorded by 0.2.79:
`board_meta.{band_gate,slots_full,band_impact_floor_uncond}` and the per-row
`proj_dps_gain` / `pairs_combine`.

⛔ `band_impact_floor` is 0.05 * weapon_dps and does NOT scale with k -- scaling
the TARGET does not move the IMPACT FLOOR. The recorded `band_impact_floor`
field is 0.0 whenever the gate is closed (i.e. every D5 decision), which is why
`band_impact_floor_uncond` exists and is the one used here.

⛔ Dropping candidates can only REMOVE options, so a decision flips exactly when
the current winner is the one dropped.

⛔ NO GATE 0b, BY DESIGN (prereg §36d): whether a changed purchase raises the
weapon_dps TRAJECTORY is closed-loop and cannot be simulated from one decision.
A pass licenses a live SCREEN, never a ship.

Usage:
    python scripts/wp2_dps_band_joint_gate0.py --runs-dir <dir>
    python scripts/wp2_dps_band_joint_gate0.py --self-test
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MOD = "0.2.79-wp2-capture"
WAVE_MAX = 11
BAND_FROM_ACTUAL = 13
FLIP_BAR = 0.20            # carried verbatim from §32/§33/§35
INTERACTION_MARGIN = 0.10  # fixed in the prereg before any flip was computed
K_JOINT = [1.25, 1.50, 1.75]
W_SENS = [1, 6, 9]


def scored_rows(bs):
    return [c for c in bs
            if c.get("skipped") in (None, "") and isinstance(c.get("score"), (int, float))]


def band_gate_at(wave, weapon_dps, dps_target, W, k):
    if wave < W:
        return False
    if not isinstance(weapon_dps, (int, float)) or not isinstance(dps_target, (int, float)):
        return None
    return weapon_dps < k * dps_target


def dropped(cand, gate_on, slots_full, floor):
    """shop_strategy.gd:1637-1641, verbatim."""
    if not gate_on or not slots_full:
        return False
    if str(cand.get("category")) != "weapon":
        return False
    pc = cand.get("pairs_combine")
    pg = cand.get("proj_dps_gain")
    if not isinstance(pg, (int, float)) or not isinstance(pc, bool):
        return False        # operands N/A (sold_family/unusable): never reached the gate
    return (not pc) and pg < floor


def winner(rows):
    return max(rows, key=lambda c: float(c["score"])) if rows else None


def flips_at(caps, W, k):
    """Returns (n, n_flip, n_emptied, per-cell counters)."""
    n = nf = ne = 0
    cellflip = Counter()
    for c in caps:
        gate = band_gate_at(c["wave"], c["dps"], c["tgt"], W, k)
        if gate is None:
            continue
        n += 1
        base = c["base"]
        keep = [r for r in c["rows"]
                if not dropped(r, gate, c["slots_full"], c["floor"])]
        new = winner(keep)
        if new is None:
            ne += 1
            nf += 1
            cellflip[c["cell"]] += 1
        elif (str(new.get("id")), new.get("slot")) != (str(base.get("id")), base.get("slot")):
            nf += 1
            cellflip[c["cell"]] += 1
    return n, nf, ne, cellflip


def collect(runs_dir):
    ids = []
    for d in sorted(os.listdir(runs_dir)):
        sp = os.path.join(runs_dir, d, "summary.json")
        if not os.path.isfile(sp):
            continue
        try:
            s = json.load(open(sp, encoding="utf-8-sig"))
        except ValueError:
            continue
        if str(s.get("mod_version")) == MOD:
            ids.append(d)
    caps, skip = [], Counter()
    repro = Counter()
    for rid in ids:
        p = os.path.join(runs_dir, rid, "events.jsonl")
        if not os.path.exists(p):
            skip["missing_events"] += 1
            continue
        for ln in open(p, encoding="utf-8", errors="replace"):
            if '"purchase_decision"' not in ln:
                continue
            try:
                ev = json.loads(ln)
            except ValueError:
                skip["unparseable"] += 1
                continue
            pl = ev.get("payload") or {}
            act = pl.get("action") or {}
            if str(act.get("type")) != "shop_buy":
                skip["not_shop_buy"] += 1
                continue
            bs = pl.get("board_scores")
            bm = pl.get("board_meta")
            if not bs or not isinstance(bm, dict) or not bm:
                skip["no_board_scores_or_meta"] += 1
                continue
            w = pl.get("wave")
            w = int(w) if isinstance(w, (int, float)) else -1
            if not (1 <= w <= WAVE_MAX):
                skip["wave_outside_1_11"] += 1
                continue
            rows = scored_rows(bs)
            if not rows:
                skip["no_scored_candidates"] += 1
                continue
            off = ((pl.get("build_metrics") or {}).get("offense") or {})
            floor = bm.get("band_impact_floor_uncond")
            if not isinstance(floor, (int, float)):
                skip["no_uncond_floor"] += 1
                continue
            base = winner(rows)
            topw = str(base.get("id", "")).startswith("weapon_")
            full = bool(bm.get("slots_full"))
            ok = act.get("item_id") is not None and str(base.get("id")) == str(act.get("item_id"))
            repro[(full, topw, ok)] += 1
            caps.append(dict(wave=w, rows=rows, base=base, slots_full=full,
                             floor=float(floor), dps=off.get("weapon_dps"),
                             tgt=off.get("dps_target"), cell=(full, topw),
                             repro_ok=ok))
    return ids, caps, skip, repro


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return _self_test()
    if not a.runs_dir:
        ap.error("--runs-dir required unless --self-test")

    ids, caps, skip, repro = collect(a.runs_dir)
    print("=" * 78)
    print("DENOMINATORS (before any result)")
    print("=" * 78)
    print(f"  runs at {MOD}: {len(ids)}")
    print(f"  ANALYSIS SET (shop_buy, waves 1-{WAVE_MAX}, scored, meta): {len(caps)}")
    for k, v in skip.most_common():
        print(f"    excluded {k:28s} {v}")
    if not caps:
        print("  !! EMPTY. STOP.")
        return 1

    print("\n" + "=" * 78)
    print("CONTROL 1 -- cell-wise reproduction of the EMITTED action")
    print("=" * 78)
    tot_ok = tot = 0
    for full in (False, True):
        for topw in (False, True):
            o, m = repro[(full, topw, True)], repro[(full, topw, False)]
            if o + m:
                tot_ok += o; tot += o + m
                print(f"  slots_full={str(full):5s} top_weapon={str(topw):5s} : "
                      f"{o}/{o+m} = {o/(o+m):.4f}")
    print(f"  pooled: {tot_ok}/{tot} = {tot_ok/max(tot,1):.4f}")
    print("  ⚠️ the slots_full=True/top_weapon=True cell is owned by a sell-or-defer")
    print("     branch. Per prereg it is NOT excluded (the lever acts there);")
    print("     results are reported BOTH ways and their agreement is the result.")

    print("\n" + "=" * 78)
    print("CONTROL 2 -- ARM A baseline (W=13, k=1.00) must flip EXACTLY 0")
    print("=" * 78)
    nA, fA, eA, _ = flips_at(caps, BAND_FROM_ACTUAL, 1.00)
    print(f"  n={nA} flips={fA} emptied={eA}")
    if fA != 0:
        print("  ⛔ BASELINE FLIPS. The model does not reproduce the shipped policy. VOID.")
        return 1
    print("  ✅ 0 flips — the counterfactual reduces to the shipped behaviour.")

    print("\n" + "=" * 78)
    print("CONTROL 3 -- ARM C target-only (W=13, k=1.75) must flip EXACTLY 0")
    print("=" * 78)
    print("  Structural: if the wave gate really blocks the detector below 13,")
    print("  raising the target with W=13 cannot flip anything at waves <= 11.")
    nC, fC, eC, _ = flips_at(caps, BAND_FROM_ACTUAL, 1.75)
    print(f"  n={nC} flips={fC} emptied={eC}")
    if fC != 0:
        print("  ⛔ ARM C FLIPPED. The source reading is FALSIFIED. Analysis VOID.")
        return 1
    print("  ✅ 0 flips — the source reading survives its own falsification test.")

    print("\n" + "=" * 78)
    print("ARM B -- gate-only (W, k=1.00): predicted small")
    print("=" * 78)
    flipB = {}
    for W in W_SENS:
        n, f, e, _ = flips_at(caps, W, 1.00)
        flipB[W] = f / max(n, 1)
        print(f"  W={W:<2} n={n} flips={f} ({f/max(n,1):.4f}) emptied={e}")

    print("\n" + "=" * 78)
    print("ARM D -- JOINT (W, k). GATE 0a-i flip>=0.20; 0a-ii joint > B+C+0.10")
    print("=" * 78)
    print(f"  {'W':>3} {'k':>6} {'n':>5} {'flips':>6} {'rate':>8} {'emptied':>8}"
          f" {'excl-cell rate':>15} {'0a-ii need':>11} {'0a-ii':>6}")
    a_pass = inter_pass = False
    per_w = {}
    for W in W_SENS:
        rates = []
        for k in K_JOINT:
            n, f, e, cf = flips_at(caps, W, k)
            rate = f / max(n, 1)
            rates.append(rate)
            sub = [c for c in caps if c["cell"] != (True, True)]
            n2, f2, _, _ = flips_at(sub, W, k)
            r2 = f2 / max(n2, 1)
            need = flipB[W] + 0.0 + INTERACTION_MARGIN     # flip(C) is 0 by control 3
            ii = rate > need
            print(f"  {W:>3} {k:>6.2f} {n:>5} {f:>6} {rate:>8.4f} {e:>8}"
                  f" {r2:>15.4f} {need:>11.4f} {str(ii):>6}")
            if rate >= FLIP_BAR:
                a_pass = True
            if ii and rate >= FLIP_BAR:
                inter_pass = True
        per_w[W] = rates
        mono = all(rates[i] <= rates[i + 1] + 1e-12 for i in range(len(rates) - 1))
        distinct = len(set(round(r, 12) for r in rates)) > 1
        print(f"      monotone in k: {mono}"
              + ("" if distinct else "   ⚠️ VACUOUS (all doses identical)"))

    print("\n" + "=" * 78)
    print("VERDICT")
    print("=" * 78)
    print(f"  GATE 0a-i  (flip >= {FLIP_BAR:.2f})              : {'PASS' if a_pass else 'FAIL'}")
    print(f"  GATE 0a-ii (joint > B + C + {INTERACTION_MARGIN:.2f}) : "
          f"{'PASS' if inter_pass else 'FAIL'}")
    print(f"  => {'SCREEN IT' if (a_pass and inter_pass) else 'DO NOT IMPLEMENT'}")
    print("\n  ⛔ No Gate 0b exists by design: the DPS consequence is closed-loop.")
    print("     A pass licenses a live SCREEN whose primary is the realised")
    print("     weapon_dps trajectory at waves <= 11. It is not a survival claim.")
    return 0


def _self_test():
    ok = True

    def chk(name, cond):
        nonlocal ok
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        ok = ok and cond

    chk("gate closed below W", band_gate_at(5, 10.0, 100.0, 13, 1.0) is False)
    chk("gate open at/above W when below target",
        band_gate_at(13, 10.0, 100.0, 13, 1.0) is True)
    chk("gate closed when at/above target",
        band_gate_at(13, 200.0, 100.0, 13, 1.0) is False)
    chk("k raises the bar => can open a gate that was shut",
        band_gate_at(13, 120.0, 100.0, 13, 1.0) is False
        and band_gate_at(13, 120.0, 100.0, 13, 1.75) is True)
    chk("missing metrics return None, not a silent False",
        band_gate_at(13, None, 100.0, 13, 1.0) is None)

    w = {"category": "weapon", "pairs_combine": False, "proj_dps_gain": 1.0}
    chk("dropped when gate on, slots full, no pair, gain below floor",
        dropped(w, True, True, 5.0) is True)
    chk("NOT dropped when slots not full", dropped(w, True, False, 5.0) is False)
    chk("NOT dropped when gate off", dropped(w, False, True, 5.0) is False)
    chk("NOT dropped when it pairs for combine",
        dropped({**w, "pairs_combine": True}, True, True, 5.0) is False)
    chk("NOT dropped when gain clears the floor",
        dropped({**w, "proj_dps_gain": 9.0}, True, True, 5.0) is False)
    chk("non-weapon never dropped",
        dropped({**w, "category": "item"}, True, True, 5.0) is False)
    chk("operands ABSENT => never dropped (sold_family/unusable path)",
        dropped({"category": "weapon"}, True, True, 5.0) is False)

    # The flip statistic must be able to return BOTH zero and non-zero.
    rows = [{"category": "weapon", "id": "weapon_a", "slot": 0, "score": 10.0,
             "pairs_combine": False, "proj_dps_gain": 1.0},
            {"category": "item", "id": "item_b", "slot": 1, "score": 5.0}]
    cap = dict(wave=9, rows=rows, base=rows[0], slots_full=True, floor=5.0,
               dps=10.0, tgt=100.0, cell=(True, True), repro_ok=True)
    n, f, e, _ = flips_at([cap], 13, 1.0)
    chk("no flip when the gate is shut by W", (n, f) == (1, 0))
    n, f, e, _ = flips_at([cap], 1, 1.0)
    chk("flip when the gate opens and the winner is dropped", (n, f) == (1, 1))
    cap2 = dict(cap, rows=[rows[0]], base=rows[0])
    n, f, e, _ = flips_at([cap2], 1, 1.0)
    chk("emptied board counts as a flip and is reported", (n, f, e) == (1, 1, 1))
    print("\nSELF-TEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
