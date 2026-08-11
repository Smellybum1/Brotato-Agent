"""Pass 4 addendum: peak-vs-current and boundary diagnostics for the regression decision.

Run AFTER wp2_winrate_estimates.py. Writes .tmp/winrate/addendum.txt.
"""
from __future__ import annotations

import json
import math
import os
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L = [json.loads(l) for l in open(os.path.join(ROOT, ".tmp/winrate/ledger.jsonl"), encoding="utf-8")]
EST = json.load(open(os.path.join(ROOT, ".tmp/winrate/estimates.json"), encoding="utf-8"))
BUF = []


def P(*a):
    s = " ".join(str(x) for x in a)
    BUF.append(s)
    print(s)


def wilson(w, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = w / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    s = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - s) / d, (c + s) / d)


def fisher_2x2(a, b, c, d):
    """two-sided Fisher exact p for [[a,b],[c,d]]."""
    from math import comb
    n = a + b + c + d
    r1, c1 = a + b, a + c

    def pr(x):
        return comb(r1, x) * comb(n - r1, c1 - x) / comb(n, c1)
    p0 = pr(a)
    tot = 0.0
    for x in range(max(0, c1 - (n - r1)), min(r1, c1) + 1):
        p = pr(x)
        if p <= p0 * (1 + 1e-9):
            tot += p
    return min(1.0, tot)


P("=" * 100)
P("ADDENDUM — DIRECT COMPARISONS FOR THE 'DID IT REGRESS?' DECISION")
P("=" * 100)

CC = [x for x in L if x["summary_status"] == "present" and x["run_mode"] == "teacher"]


def wn(rows):
    return sum(1 for x in rows if x["win"]), len(rows)


P("")
P("A. BOUNDARY DIAGNOSTIC for the change-point segments")
P("   Cuts are at ATTEMPT index, so a version whose attempts straddle a cut appears in two")
P("   segments. Straddling versions and their split:")
segs = EST["changepoints"]["segments"]
CCs = sorted(CC, key=lambda x: (x["version_int"], x["attempt_id"]))
for s in segs:
    sub = CCs[s["i"]:s["j"]]
    P(f"   seg idx[{s['i']}:{s['j']}) versions present: {sorted(Counter(x['version_int'] for x in sub))}")
for k in range(len(segs) - 1):
    i = segs[k]["j"]
    P(f"   cut at idx{i}: version before={CCs[i-1]['version_int']} at/after={CCs[i]['version_int']}")

P("")
P("B. SEGMENT-TO-SEGMENT CONTRASTS (teacher complete-case, raw counts + Fisher exact)")
for k in range(len(segs)):
    for j in range(k + 1, len(segs)):
        a, b = segs[k]["wins"], segs[k]["n"] - segs[k]["wins"]
        c, d = segs[j]["wins"], segs[j]["n"] - segs[j]["wins"]
        p = fisher_2x2(a, b, c, d)
        P(f"   seg{k+1}(v{segs[k]['v_start']}-{segs[k]['v_end']}) {a}/{a+b}={a/(a+b):.3f}  vs  "
          f"seg{j+1}(v{segs[j]['v_start']}-{segs[j]['v_end']}) {c}/{c+d}={c/(c+d):.3f}   "
          f"diff={100*(c/(c+d)-a/(a+b)):+.1f}pp  fisher_p={p:.4g}")

P("")
P("C. PEAK-VERSION vs CURRENT-VERSION (the sharpest form of the regression claim)")
best = max(EST["per_version"], key=lambda r: (r["n_summary"] >= 10, r["cc_winrate"] if r["n_summary"] else -1))
P(f"   best version with n_summary>=10 by raw complete-case rate: v{best['version']} "
  f"{best['wins']}/{best['n_summary']}={best['cc_winrate']:.3f}")
cands = [r for r in EST["per_version"] if r["n_summary"] >= 10]
P("   all versions with n_summary>=10 (raw):")
for r in sorted(cands, key=lambda r: -r["cc_winrate"]):
    lo, hi = wilson(r["wins"], r["n_summary"])
    P(f"      v{r['version']:>3} {r['wins']:>3}/{r['n_summary']:<3} = {r['cc_winrate']:.3f} "
      f"wilson95=[{lo:.3f},{hi:.3f}]")

recent_teacher = [x for x in CC if x["version_int"] >= 122]
w, n = wn(recent_teacher)
lo, hi = wilson(w, n)
P("")
P(f"   RECENT TEACHER (version>=122, complete case): {w}/{n} = {w/n:.3f} wilson95=[{lo:.3f},{hi:.3f}]")
P("      per-version: " + " ".join(
    f"v{v}:{wn([x for x in recent_teacher if x['version_int']==v])[0]}/{wn([x for x in recent_teacher if x['version_int']==v])[1]}"
    for v in sorted({x["version_int"] for x in recent_teacher})))
peak = [x for x in CC if 60 <= x["version_int"] <= 79]
wp_, np_ = wn(peak)
lo2, hi2 = wilson(wp_, np_)
P(f"   PEAK ERA TEACHER (v60-79, complete case): {wp_}/{np_} = {wp_/np_:.3f} "
  f"wilson95=[{lo2:.3f},{hi2:.3f}]")
p = fisher_2x2(wp_, np_ - wp_, w, n - w)
P(f"   peak-era vs recent teacher: diff={100*(w/n - wp_/np_):+.1f}pp  fisher_p={p:.4g}")

P("")
P("D. MODE-MIXING CHECK IN THE RECENT BAND (v125 only)")
v125 = [x for x in L if x["version_int"] == 125]
for m in ("teacher", "residual", "student", "unknown"):
    sub = [x for x in v125 if x["run_mode"] == m and x["summary_status"] == "present"]
    if sub:
        ww, nn = wn(sub)
        lo3, hi3 = wilson(ww, nn)
        P(f"   v125 {m:<9} complete-case {ww}/{nn} = {ww/nn:.3f} wilson95=[{lo3:.3f},{hi3:.3f}]")
    else:
        P(f"   v125 {m:<9} complete-case 0/0 (no complete-case attempts)")
allv125 = [x for x in v125 if x["summary_status"] == "present"]
ww, nn = wn(allv125)
P(f"   v125 POOLED-ACROSS-MODES {ww}/{nn} = {ww/nn:.3f}  <-- reporting this as a teacher rate")
P("       would be WRONG: it mixes 3 modes.")

P("")
P("E. WHAT THE UNKNOWNS ARE, BY SEGMENT (they are NOT gameplay outcomes)")
for lo_v, hi_v, nm in ((0, 59, "v0-59"), (60, 83, "v60-83"), (84, 103, "v84-103"), (104, 128, "v104-128")):
    sub = [x for x in L if lo_v <= x["version_int"] <= hi_v]
    u = [x for x in sub if x["terminal_class"] == "UNKNOWN"]
    P(f"   {nm}: attempts={len(sub)} unknown={len(u)} ({100*len(u)/len(sub):.1f}%) "
      f"max_wave dist of unknowns={dict(sorted(Counter(x['final_wave'] for x in u).items(), key=lambda t:(t[0] is None, t[0])))}")

P("")
P("F. EQUIVALENT COMPARISON UNDER end_to_end_success (technical failures count as failures)")
for lo_v, hi_v, nm in ((0, 59, "v0-59"), (60, 83, "v60-83"), (84, 103, "v84-103"), (104, 128, "v104-128")):
    sub = [x for x in L if lo_v <= x["version_int"] <= hi_v and x["terminal_class"] != "EXTERNAL_ABORT"]
    ww = sum(1 for x in sub if x["win"])
    lo3, hi3 = wilson(ww, len(sub))
    P(f"   {nm}: e2e = {ww}/{len(sub)} = {ww/len(sub):.3f} wilson95=[{lo3:.3f},{hi3:.3f}]")

open(os.path.join(ROOT, ".tmp/winrate/addendum.txt"), "w", encoding="utf-8").write("\n".join(BUF) + "\n")
print("\nwrote .tmp/winrate/addendum.txt")
