"""S31 Gate 0 screen analysis -- body_clearance_scale dose ladder at Danger 5.

Order is fixed by reports/wp2/body_clearance_screen_prereg.md and is NOT
negotiable at analysis time:
  1. validity gates, per arm, BEFORE any outcome
  2. the DELIVERY check -- does the dose reach the FINAL command?  If it does
     not, the knob is inert and the primary endpoint is not interpretable.
  3. PRIMARY mediator: per-trial in-range fraction
  4. SAFETY VETO: low-HP exposure.  An arm that raises in-range fraction while
     ALSO raising low-HP exposure is REJECTED, not reported as a win.
  5. terminal wave -- CONTEXT ONLY at n=4, no outcome claim.
"""
import glob
import json
import math
import os
import statistics as st
from itertools import combinations

RUNS = os.path.join(os.environ["APPDATA"], "Brotato", "brotato_agent", "runs")
ARMS = [("0.5", "d05"), ("1.0", "d10"), ("2.0", "d20"), ("3.0", "d30")]
EXPECT = {"character": "character_ranger", "danger": 5, "build": "0.2.75-wp2-capture",
          "opener": "weapon_pistol_1"}


def perm_p(a, b, iters=200000):
    """Exact two-sided permutation on the difference of means when the split
    count is small enough to enumerate, else a deterministic full enumeration
    guard.  Self-tested in main()."""
    pooled = list(a) + list(b)
    n = len(a)
    obs = abs(st.mean(a) - st.mean(b))
    idx = range(len(pooled))
    total = hit = 0
    for combo in combinations(idx, n):
        s = set(combo)
        x = [pooled[i] for i in idx if i in s]
        y = [pooled[i] for i in idx if i not in s]
        total += 1
        if abs(st.mean(x) - st.mean(y)) >= obs - 1e-12:
            hit += 1
    return hit / total if total else 1.0


def load_arm(tag):
    sf = ".tmp/s31_bcs/%s/state.json" % tag
    if not os.path.exists(sf):
        return []
    return json.load(open(sf, encoding="utf-8-sig"))["collected_run_ids"]


def scan(rid):
    """One pass over a run.  Returns per-trial aggregates."""
    path = os.path.join(RUNS, rid, "events.jsonl")
    out = {"rid": rid, "dose": None, "character": None, "danger": None,
           "build": None, "opener": None, "last_wave": None,
           "caps": 0, "with_enemy": 0, "in_range_sum": 0.0,
           "bsa_true": 0, "bsa_seen": 0, "hp_low": 0, "hp_seen": 0,
           "deficit_sum": 0.0, "headings": [], "sel_clear": [], "inp_clear": []}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if '"run_start"' in line and out["dose"] is None:
                try:
                    p = json.loads(line).get("payload") or {}
                except Exception:
                    p = {}
                out["dose"] = p.get("body_clearance_scale")
                out["character"] = p.get("character") or p.get("requested_character")
                out["build"] = p.get("mod_version")
                out["opener"] = p.get("weapon")
                out["danger"] = p.get("danger")
                continue
            if '"combat_capture"' not in line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("event") != "combat_capture":   # key is 'event', NOT 'type'
                continue
            p = e.get("payload") or {}
            out["caps"] += 1
            if isinstance(p.get("wave"), int):
                out["last_wave"] = max(out["last_wave"] or 0, p["wave"])
            pl = p.get("player") or {}
            hp, mx = pl.get("hp"), pl.get("max_hp")
            if isinstance(hp, (int, float)) and isinstance(mx, (int, float)) and mx > 0:
                out["hp_seen"] += 1
                r = hp / mx
                if r < 0.70:
                    out["hp_low"] += 1
                out["deficit_sum"] += max(0.0, 1.0 - r)
            # The exact path, probed from the data. A first version searched
            # payload / teacher / teacher.debug and read seen=0 over 145,183
            # captures -- a VACUOUS filter, not a null. It is nested two levels
            # deeper, under teacher.contributions.finale_translation.
            tele = ((p.get("teacher") or {}).get("contributions") or {}).get(
                "finale_translation") or {}
            if "body_safety_active" in tele:
                out["bsa_seen"] += 1
                if tele["body_safety_active"]:
                    out["bsa_true"] += 1
            # The DIRECT dose readback: the clearance the arbiter actually
            # ACCEPTED. A more permissive dose should accept LOWER clearance.
            # Far stronger than a heading distribution.
            for key, acc in (("body_selected_clearance", "sel_clear"),
                             ("body_input_clearance", "inp_clear")):
                v = tele.get(key)
                if isinstance(v, (int, float)) and abs(v) < 1e17:  # INF sentinel guard
                    out[acc].append(float(v))
            # teacher.action is a DICT {x, y} -- NOT a list. The isinstance
            # check against (list, tuple) silently produced 0 headings.
            act = (p.get("teacher") or {}).get("action")
            if isinstance(act, dict):
                try:
                    ax, ay = float(act.get("x", 0.0)), float(act.get("y", 0.0))
                    if ax or ay:
                        out["headings"].append(math.degrees(math.atan2(ay, ax)) % 360.0)
                except Exception:
                    pass
            ents = p.get("entities") or {}
            enemies = ents.get("enemies") or []
            if not enemies:
                continue
            weps = p.get("weapons") or []
            rng = max([float(w.get("max_range", 0) or 0) for w in weps] or [0.0])
            if rng <= 0:
                continue
            px, py = pl.get("x"), pl.get("y")
            if px is None or py is None:
                continue
            inr = 0
            for en in enemies:
                ex, ey = en.get("x"), en.get("y")
                if ex is None or ey is None:
                    continue
                if math.hypot(ex - px, ey - py) <= rng:
                    inr += 1
            out["with_enemy"] += 1
            out["in_range_sum"] += inr / float(len(enemies))
    return out


def main():
    # --- self-test the statistic before it decides anything -------------
    assert abs(perm_p([1, 1, 1], [1, 1, 1]) - 1.0) < 1e-9, "identical arms must give p=1"
    sep = perm_p([10, 11, 12], [1, 2, 3])
    assert sep <= 0.10, "perfect separation must be able to return a small p, got %r" % sep
    print("SELF-TEST perm_p: identical arms -> 1.0 ; separated arms -> %.4f  (both branches reachable)"
          % sep)
    print()

    data = {}
    for label, tag in ARMS:
        ids = load_arm(tag)
        data[label] = [scan(r) for r in ids]

    # ---------------- 1. VALIDITY, BEFORE ANY OUTCOME -------------------
    print("=" * 78)
    print("STEP 1 -- VALIDITY GATES, PER ARM, BEFORE ANY OUTCOME (S31f)")
    print("=" * 78)
    problems = []
    for label, _ in ARMS:
        rows = data[label]
        n = len(rows)
        dose_ok = sum(1 for r in rows if r["dose"] is not None
                      and abs(float(r["dose"]) - float(label)) < 1e-9)
        ch_ok = sum(1 for r in rows if r["character"] == EXPECT["character"])
        op_ok = sum(1 for r in rows if r["opener"] == EXPECT["opener"])
        bd_ok = sum(1 for r in rows if r["build"] == EXPECT["build"])
        print("  dose %-4s n=%d | dose readback %d/%d | character %d/%d | opener %d/%d | build %d/%d"
              % (label, n, dose_ok, n, ch_ok, n, op_ok, n, bd_ok, n))
        if n and not (dose_ok == ch_ok == op_ok == bd_ok == n):
            problems.append("arm %s failed a validity gate" % label)
    print("  (character_ok is CONSTANT True archive-wide => VACUOUS as a filter;")
    print("   the OBSERVED value and the per-trial dose readback are asserted instead)")
    print()

    # ---------------- 2. DELIVERY CHECK ---------------------------------
    print("=" * 78)
    print("STEP 2 -- DELIVERY: DOES THE DOSE REACH THE FINAL COMMAND? (S31d)")
    print("Not assumed. calm_threat_mult once self-reported fine and moved the")
    print("command 0.003. If the dosed arms match control here, the knob is")
    print("INERT and the primary endpoint below is NOT interpretable.")
    print("=" * 78)
    for label, _ in ARMS:
        rows = data[label]
        bsa_seen = sum(r["bsa_seen"] for r in rows)
        bsa_true = sum(r["bsa_true"] for r in rows)
        heads = [h for r in rows for h in r["headings"]]
        frac = (bsa_true / bsa_seen) if bsa_seen else None
        sel = [v for r in rows for v in r["sel_clear"]]
        inp = [v for r in rows for v in r["inp_clear"]]
        print("  dose %-4s captures=%-7d  bsa seen=%-7d active=%s  headings=%d"
              % (label, sum(r["caps"] for r in rows), bsa_seen,
                 ("%.4f" % frac) if frac is not None else "FIELD ABSENT", len(heads)))
        if sel:
            print("           body_selected_clearance  n=%-7d median=%8.2f  mean=%8.2f"
                  % (len(sel), st.median(sel), st.mean(sel)))
        if inp:
            print("           body_input_clearance     n=%-7d median=%8.2f  mean=%8.2f"
                  % (len(inp), st.median(inp), st.mean(inp)))
    print("  ^ denominators printed first: a field that is ABSENT is reported as")
    print("    absent, never as a rate of zero.")
    print()

    # ---------------- 3. PRIMARY MEDIATOR -------------------------------
    print("=" * 78)
    print("STEP 3 -- PRIMARY MEDIATOR: per-trial IN-RANGE FRACTION")
    print("human 0.4417 +- 0.0187 ; agent 0.2801 +- 0.0535 (d=4.03) -- the band to move toward")
    print("=" * 78)
    series = {}
    for label, _ in ARMS:
        rows = data[label]
        vals = [r["in_range_sum"] / r["with_enemy"] for r in rows if r["with_enemy"] > 0]
        series[label] = vals
        cov = sum(r["with_enemy"] for r in rows)
        print("  dose %-4s n=%d  captures-with-an-enemy=%-7d  raw: %s"
              % (label, len(vals), cov, [round(v, 4) for v in vals]))
        if vals:
            print("           mean=%.4f  sd=%s  median=%.4f"
                  % (st.mean(vals),
                     ("%.4f" % st.stdev(vals)) if len(vals) > 1 else "n/a",
                     st.median(vals)))
    print()
    ctrl = series.get("1.0") or []
    if ctrl:
        for label, _ in ARMS:
            if label == "1.0" or not series[label]:
                continue
            d = st.mean(series[label]) - st.mean(ctrl)
            print("  dose %-4s vs control: delta=%+.4f  exact perm p=%.4f"
                  % (label, d, perm_p(series[label], ctrl)))
    print()

    # ---------------- 4. SAFETY VETO ------------------------------------
    print("=" * 78)
    print("STEP 4 -- SAFETY VETO (pre-declared): low-HP exposure")
    print("An arm that raises in-range fraction while ALSO raising low-HP")
    print("exposure is REJECTED, not reported as a win.")
    print("=" * 78)
    for label, _ in ARMS:
        rows = data[label]
        low = [r["hp_low"] / r["hp_seen"] for r in rows if r["hp_seen"]]
        auc = [r["deficit_sum"] / r["hp_seen"] for r in rows if r["hp_seen"]]
        if low:
            print("  dose %-4s frac captures below 70%% HP: mean=%.4f  raw=%s"
                  % (label, st.mean(low), [round(v, 4) for v in low]))
            print("           HP-deficit AUC: mean=%.4f  raw=%s"
                  % (st.mean(auc), [round(v, 4) for v in auc]))
    print()

    # ---------------- 5. CONTEXT ONLY -----------------------------------
    print("=" * 78)
    print("STEP 5 -- TERMINAL WAVE: CONTEXT ONLY (S31a). n=4/arm cannot resolve")
    print("it; D5 within-arm sd is 1.59-2.63. NO outcome claim may be made here.")
    print("=" * 78)
    for label, _ in ARMS:
        w = sorted(r["last_wave"] for r in data[label] if r["last_wave"])
        print("  dose %-4s terminal waves %s" % (label, w))
    print()
    if problems:
        print("VALIDITY PROBLEMS:", problems)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
