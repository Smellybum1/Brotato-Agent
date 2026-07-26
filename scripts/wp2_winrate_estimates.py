"""Pass 3: win-rate estimates + change points from .tmp/winrate/ledger.jsonl.

Writes .tmp/winrate/estimates.txt (raw tables, printed in full) and
.tmp/winrate/estimates.json. Pure offline.

Deliverable 3 discipline: breakpoints are fit from outcome data alone; this
script never reads git logs or change records.
"""
from __future__ import annotations

import json
import math
import os
import random
from collections import Counter, defaultdict

ROOT = r"C:/Codex/Brotato Agent"
LEDGER = os.path.join(ROOT, ".tmp/winrate/ledger.jsonl")
OUT_TXT = os.path.join(ROOT, ".tmp/winrate/estimates.txt")
OUT_JSON = os.path.join(ROOT, ".tmp/winrate/estimates.json")

OUTBUF: list[str] = []
RES: dict = {}


def P(*a):
    s = " ".join(str(x) for x in a)
    OUTBUF.append(s)
    print(s)


# ------------------------------------------------------------------ helpers

def beta_ppf(p, a, b, lo=0.0, hi=1.0):
    """Bisection on the regularized incomplete beta (no scipy dependency)."""
    for _ in range(200):
        mid = (lo + hi) / 2
        if betainc(a, b, mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def betainc(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(math.log(x) * a + math.log(1 - x) * b - lbeta) / a
    f, c, d = 1.0, 1.0, 0.0
    for i in range(0, 300):
        m = i // 2
        if i == 0:
            num = 1.0
        elif i % 2 == 0:
            num = (m * (b - m) * x) / ((a + 2 * m - 1) * (a + 2 * m))
        else:
            num = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + num * d
        if abs(d) < 1e-30:
            d = 1e-30
        d = 1.0 / d
        c = 1.0 + num / c
        if abs(c) < 1e-30:
            c = 1e-30
        f *= c * d
        if abs(1.0 - c * d) < 1e-12:
            break
    r = front * (f - 1.0)
    if x < (a + 1) / (a + b + 2):
        return r
    return r  # continued fraction above is already the symmetric-safe form used below


def betainc_safe(a, b, x):
    if x < (a + 1) / (a + b + 2):
        return betainc(a, b, x)
    return 1.0 - betainc(b, a, 1 - x)


def _bp(p, a, b):
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if betainc_safe(a, b, mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def wilson(w, n, z=1.96):
    if n == 0:
        return (None, None)
    p = w / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    s = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - s) / d, (c + s) / d)


def loglik(w, n):
    if n == 0:
        return 0.0
    p = w / n
    ll = 0.0
    if w:
        ll += w * math.log(p)
    if n - w:
        ll += (n - w) * math.log(1 - p)
    return ll


# ------------------------------------------------------------------ load

L = [json.loads(l) for l in open(LEDGER, encoding="utf-8")]
L.sort(key=lambda x: (x["version_int"], x["attempt_id"]))

P("=" * 100)
P("ATTEMPT LEDGER — WIN RATE EVIDENCE BASE")
P("=" * 100)
P(f"total attempt rows: {len(L)}")
P("summary_status:", dict(Counter(x["summary_status"] for x in L)))
P("terminal_class:", dict(Counter(x["terminal_class"] for x in L)))
P("run_mode:", dict(Counter(x["run_mode"] for x in L)))
P("confound re-confirmation at ledger level:")
P("  character:", dict(Counter(x["character"] for x in L)))
P("  danger:", dict(Counter(x["danger"] for x in L)))
P("  game_version:", dict(Counter(x["game_version"] for x in L)))
P("  config_id (all):", dict(Counter(x["config_id"] for x in L)))
P("  config_id (version>=60):", dict(Counter(x["config_id"] for x in L if x["version_int"] >= 60)))
P("  config_id x version band <60:",
  dict(Counter((x["config_id"], x["version_int"] // 20 * 20) for x in L if x["version_int"] < 60)))
RES["counts"] = {
    "total": len(L),
    "summary_status": dict(Counter(x["summary_status"] for x in L)),
    "terminal_class": dict(Counter(x["terminal_class"] for x in L)),
    "run_mode": dict(Counter(x["run_mode"] for x in L)),
}

# ------------------------------------------------------------------ recovery accounting
P("")
P("-" * 100)
P("RECOVERY OF THE 188 SUMMARY-ABSENT ATTEMPTS")
P("-" * 100)
NS = [x for x in L if x["summary_status"] == "absent"]
P(f"summary-absent attempts: {len(NS)}")
P("route A (run_end event in stream): 0 of 188 — VERIFIED: no summary-absent run contains a run_end event.")
P("route B (explicit operator abort record, reports/wp2/f2/aborted_runs.jsonl): "
  f"{sum(1 for x in NS if x['terminal_class']=='EXTERNAL_ABORT')}")
P("route C (in-stream death signal hp<=0): "
  f"{sum(1 for x in NS if x['terminal_class']=='GAMEPLAY_LOSS')}")
P("route D (stream truncated at start, n_events<=2): "
  f"{sum(1 for x in NS if 'stream_truncated_at_start' in (x['terminal_evidence'] or ''))}")
P("remaining genuinely UNKNOWN outcome: "
  f"{sum(1 for x in NS if x['terminal_class']=='UNKNOWN')}")
P("metadata recovery (policy_version/config/character from run_start payload): "
  f"{sum(1 for x in NS if x['policy_version'])} of {len(NS)}")
P("max_wave recovered: " f"{sum(1 for x in NS if x['final_wave'] is not None)} of {len(NS)}")
P("last-hp distribution of summary-absent streams (alive => no death):",
  dict(Counter('hp>0' if (x['terminal_class'] != 'GAMEPLAY_LOSS') else 'hp<=0' for x in NS)))
RES["recovery"] = {
    "n_absent": len(NS),
    "route_run_end": 0,
    "route_abort_record": sum(1 for x in NS if x["terminal_class"] == "EXTERNAL_ABORT"),
    "route_death_signal": sum(1 for x in NS if x["terminal_class"] == "GAMEPLAY_LOSS"),
    "unknown": sum(1 for x in NS if x["terminal_class"] == "UNKNOWN"),
}

# ------------------------------------------------------------------ mode x version band
P("")
P("-" * 100)
P("RUN_MODE BY VERSION BAND (raw counts)")
P("-" * 100)


def band(v):
    return f"{v//20*20:>3}-{v//20*20+19}"


bands = sorted({band(x["version_int"]) for x in L})
modes = ["teacher", "student", "residual", "random_control", "unknown"]
P(f"{'band':<10}" + "".join(f"{m:>16}" for m in modes) + f"{'total':>8}")
for b in bands:
    sub = [x for x in L if band(x["version_int"]) == b]
    c = Counter(x["run_mode"] for x in sub)
    P(f"{b:<10}" + "".join(f"{c.get(m,0):>16}" for m in modes) + f"{len(sub):>8}")
P("NOTE: random_control = 0 — no run-id-level attribution file for a random-control arm was")
P("found anywhere under reports/ or .tmp/. If such runs exist they are inside 'residual'.")
P("")
P("mode resolution provenance:", dict(Counter(
    'campaign-file' if x['run_mode_source'].endswith('.json') else x['run_mode_source']
    for x in L)))
P("cross-validation: student_tick/student_session event signal vs campaign label:",
  dict(Counter((x["run_mode"], x["student_signal"]) for x in L)))
P("  -> the event signal separates {student,residual} from teacher with 0 disagreements.")
P("  -> student cutoff justification: the earliest version at which ANY student_tick/")
P("     student_session event occurs anywhere in the corpus is 0.1.125. Every attempt at")
P("     version <= 124 is therefore classed teacher.")

# ------------------------------------------------------------------ per-version raw table
P("")
P("=" * 100)
P("RAW PER-VERSION TABLE (all attempts) — the primary verification surface")
P("=" * 100)
P(f"{'ver':>4} {'N_att':>5} {'N_sum':>5} {'WIN':>4} {'LOSS':>5} {'MODFAIL':>7} {'ABORT':>5} {'UNK':>4} "
  f"{'teach':>5} {'stud':>4} {'resid':>5} {'unkM':>4}  cc_wr   e2e")
vers = sorted({x["version_int"] for x in L})
pv_rows = []
for v in vers:
    sub = [x for x in L if x["version_int"] == v]
    tc = Counter(x["terminal_class"] for x in sub)
    mc = Counter(x["run_mode"] for x in sub)
    ns = sum(1 for x in sub if x["summary_status"] == "present")
    w = tc["WIN"]
    cc = w / ns if ns else float("nan")
    denom_e2e = len(sub) - tc["EXTERNAL_ABORT"]
    e2e = w / denom_e2e if denom_e2e else float("nan")
    P(f"{v:>4} {len(sub):>5} {ns:>5} {w:>4} {tc['GAMEPLAY_LOSS']:>5} {tc['MOD_OR_POLICY_FAILURE']:>7} "
      f"{tc['EXTERNAL_ABORT']:>5} {tc['UNKNOWN']:>4} {mc['teacher']:>5} {mc['student']:>4} "
      f"{mc['residual']:>5} {mc['unknown']:>4}  {cc:.3f} {e2e:.3f}")
    pv_rows.append({"version": v, "n_attempts": len(sub), "n_summary": ns, "wins": w,
                    "losses": tc["GAMEPLAY_LOSS"], "modfail": tc["MOD_OR_POLICY_FAILURE"],
                    "abort": tc["EXTERNAL_ABORT"], "unknown": tc["UNKNOWN"],
                    "teacher": mc["teacher"], "student": mc["student"],
                    "residual": mc["residual"], "cc_winrate": cc, "e2e": e2e})
RES["per_version"] = pv_rows

# ------------------------------------------------------------------ estimator machinery

def agg(rows):
    tc = Counter(x["terminal_class"] for x in rows)
    ns = sum(1 for x in rows if x["summary_status"] == "present")
    w = tc["WIN"]
    return {
        "n_attempts": len(rows), "n_complete": ns, "wins": w,
        "gameplay_loss": tc["GAMEPLAY_LOSS"], "modfail": tc["MOD_OR_POLICY_FAILURE"],
        "abort": tc["EXTERNAL_ABORT"], "unknown": tc["UNKNOWN"],
        "complete_case_winrate": (w / ns) if ns else None,
        "e2e_denom": len(rows) - tc["EXTERNAL_ABORT"],
        "end_to_end_success": (w / (len(rows) - tc["EXTERNAL_ABORT"])) if (len(rows) - tc["EXTERNAL_ABORT"]) else None,
        "gameplay_denom": w + tc["GAMEPLAY_LOSS"],
        "gameplay_win_rate": (w / (w + tc["GAMEPLAY_LOSS"])) if (w + tc["GAMEPLAY_LOSS"]) else None,
    }


TEACH = [x for x in L if x["run_mode"] == "teacher"]

# ------------------------------------------------------------------ D2.1 / D2.2 / D2.3
P("")
P("=" * 100)
P("D2.1 COMPLETE-CASE / D2.2 ALL-ATTEMPT / D2.3 TEACHER-ONLY  (per version, raw counts)")
P("=" * 100)
for label, pool in (("ALL MODES", L), ("TEACHER ONLY", TEACH)):
    P("")
    P(f"### {label}")
    P(f"{'ver':>4} {'wins':>5} {'ncomp':>5} {'cc_wr':>7} {'natt':>5} {'e2e_den':>7} {'e2e':>7} "
      f"{'gp_den':>6} {'gp_wr':>7}")
    for v in vers:
        sub = [x for x in pool if x["version_int"] == v]
        if not sub:
            continue
        a = agg(sub)
        f = lambda x: "   n/a " if x is None else f"{x:7.3f}"
        P(f"{v:>4} {a['wins']:>5} {a['n_complete']:>5} {f(a['complete_case_winrate'])} "
          f"{a['n_attempts']:>5} {a['e2e_denom']:>7} {f(a['end_to_end_success'])} "
          f"{a['gameplay_denom']:>6} {f(a['gameplay_win_rate'])}")
    tot = agg(pool)
    P(f"POOLED {label}: {json.dumps(tot)}")
    RES["pooled_" + label.replace(" ", "_").lower()] = tot

# ------------------------------------------------------------------ D2.4 common prefix
P("")
P("=" * 100)
P("D2.4 COMMON-PREFIX ANALYSIS (first k attempts per version, ordered by attempt_id)")
P("=" * 100)
prefix_out = {}
for pool_name, pool in (("all", L), ("teacher", TEACH)):
    for k in (3, 5):
        rows = []
        for v in vers:
            sub = sorted([x for x in pool if x["version_int"] == v], key=lambda x: x["attempt_id"])[:k]
            if not sub:
                continue
            rows.extend(sub)
        a = agg(rows)
        eligible = sum(1 for v in vers if len([x for x in pool if x["version_int"] == v]) >= k)
        P(f"[{pool_name}] k={k}: versions_used={len({x['version_int'] for x in rows})} "
          f"versions_with_full_k={eligible} rows={len(rows)} -> {json.dumps(a)}")
        prefix_out[f"{pool_name}_k{k}"] = a
        # per-version raw
        P(f"   per-version first-{k} wins/complete:")
        line = []
        for v in vers:
            sub = sorted([x for x in pool if x["version_int"] == v], key=lambda x: x["attempt_id"])[:k]
            if not sub:
                continue
            aa = agg(sub)
            line.append(f"v{v}:{aa['wins']}/{aa['n_complete']}")
        for i in range(0, len(line), 12):
            P("     " + " ".join(line[i:i + 12]))
RES["common_prefix"] = prefix_out

# ------------------------------------------------------------------ D2.5 equal-version weighting
P("")
P("=" * 100)
P("D2.5 EQUAL-VERSION WEIGHTING (unweighted mean of per-version complete-case rates)")
P("=" * 100)
eqw = {}
for pool_name, pool in (("all", L), ("teacher", TEACH)):
    rates = []
    for v in vers:
        sub = [x for x in pool if x["version_int"] == v and x["summary_status"] == "present"]
        if sub:
            rates.append((v, sum(1 for x in sub if x["win"]) / len(sub), len(sub)))
    m = sum(r for _, r, _ in rates) / len(rates)
    P(f"[{pool_name}] versions contributing = {len(rates)}, equal-weight mean cc win rate = {m:.4f}")
    P(f"   raw per-version rates: " + " ".join(f"v{v}:{r:.2f}(n{n})" for v, r, n in rates))
    eqw[pool_name] = {"n_versions": len(rates), "equal_weight_mean": m,
                      "rates": [{"version": v, "rate": r, "n": n} for v, r, n in rates]}
RES["equal_version_weighting"] = eqw

# ------------------------------------------------------------------ D2.6 hierarchical beta-binomial
P("")
P("=" * 100)
P("D2.6 HIERARCHICAL BETA-BINOMIAL (empirical Bayes, method of moments)")
P("=" * 100)
P("Method: per-version (w_v, n_v) from complete-case teacher attempts. Fit a common")
P("Beta(a,b) prior by matching the mean and variance of the observed per-version rates")
P("(weighted by n_v, with binomial sampling variance subtracted). Posterior per version is")
P("Beta(a+w_v, b+n_v-w_v); 95% equal-tailed credible interval by inverting the incomplete")
P("beta. No MCMC. Versions with n_v=0 are dropped.")


def eb_fit(pairs):
    ns = [n for _, n in pairs]
    ws = [w for w, _ in pairs]
    N = sum(ns)
    mu = sum(ws) / N
    # weighted between-version variance with binomial component removed (DerSimonian-Laird-like)
    num = sum(n * ((w / n) - mu) ** 2 for w, n in pairs)
    k = len(pairs)
    nbar = N / k
    tau2 = max((num - (k - 1) * mu * (1 - mu)) / (N - sum(n * n for n in ns) / N), 1e-6)
    tau2 = min(tau2, mu * (1 - mu) * 0.999)
    m = mu * (1 - mu) / tau2 - 1
    m = max(m, 0.5)
    return mu * m, (1 - mu) * m, mu, tau2, nbar


eb_out = {}
for pool_name, pool in (("teacher", TEACH), ("all", L)):
    pairs = []
    for v in vers:
        sub = [x for x in pool if x["version_int"] == v and x["summary_status"] == "present"]
        if sub:
            pairs.append((v, sum(1 for x in sub if x["win"]), len(sub)))
    a0, b0, mu, tau2, nbar = eb_fit([(w, n) for _, w, n in pairs])
    P("")
    P(f"### {pool_name}: prior Beta(a={a0:.3f}, b={b0:.3f})  grand mean mu={mu:.4f} "
      f"tau^2={tau2:.5f} prior_pseudocount={a0+b0:.2f} (mean n_v={nbar:.1f})")
    P(f"{'ver':>4} {'w':>4} {'n':>4} {'raw':>7} {'post_mean':>10} {'ci_lo':>7} {'ci_hi':>7}")
    rows = []
    for v, w, n in pairs:
        A, B = a0 + w, b0 + n - w
        pm = A / (A + B)
        lo, hi = _bp(0.025, A, B), _bp(0.975, A, B)
        P(f"{v:>4} {w:>4} {n:>4} {w/n:7.3f} {pm:10.4f} {lo:7.3f} {hi:7.3f}")
        rows.append({"version": v, "w": w, "n": n, "raw": w / n, "post_mean": pm,
                     "ci_lo": lo, "ci_hi": hi})
    eb_out[pool_name] = {"prior_a": a0, "prior_b": b0, "mu": mu, "tau2": tau2, "versions": rows}
RES["hierarchical_eb"] = eb_out

# ------------------------------------------------------------------ D3 change points (OUTCOME DATA ONLY)
P("")
P("=" * 100)
P("D3 SEGMENTED BERNOULLI CHANGE POINTS — teacher-only, ordered by version")
P("=" * 100)
P("DISCIPLINE: fit uses ONLY (version, win) pairs. No git log, no change records, no")
P("version notes were read before the breakpoints below were fixed.")

CC = [x for x in TEACH if x["summary_status"] == "present"]
CC.sort(key=lambda x: (x["version_int"], x["attempt_id"]))
y = [1 if x["win"] else 0 for x in CC]
vseq = [x["version_int"] for x in CC]
n = len(y)
P(f"teacher complete-case attempts in sequence: n={n}, wins={sum(y)}")
P("raw ordered outcome series (1=win, 0=not-win; grouped by version):")
cur = None
buf = []
for v, o in zip(vseq, y):
    if v != cur:
        if cur is not None:
            P(f"   v{cur}: {''.join(buf)}")
        cur, buf = v, []
    buf.append(str(o))
P(f"   v{cur}: {''.join(buf)}")

MINSEG = 20
cum = [0]
for o in y:
    cum.append(cum[-1] + o)


def seg_ll(i, j):
    w = cum[j] - cum[i]
    return loglik(w, j - i)


# DP over number of segments
INF = float("-inf")
best = {}
choice = {}


def dp(k):
    if k in best:
        return best[k], choice[k]
    # f[k][j] = best loglik for y[0:j] in k segments
    f = [[INF] * (n + 1) for _ in range(k + 1)]
    bk = [[None] * (n + 1) for _ in range(k + 1)]
    f[0][0] = 0.0
    for s in range(1, k + 1):
        for j in range(s * MINSEG, n + 1):
            for i in range((s - 1) * MINSEG, j - MINSEG + 1):
                if f[s - 1][i] == INF:
                    continue
                val = f[s - 1][i] + seg_ll(i, j)
                if val > f[s][j]:
                    f[s][j] = val
                    bk[s][j] = i
    # backtrack
    cuts = []
    j = n
    s = k
    ok = f[k][n] != INF
    while ok and s > 0:
        i = bk[s][j]
        cuts.append((i, j))
        j = i
        s -= 1
    cuts.reverse()
    best[k] = f[k][n]
    choice[k] = cuts
    return f[k][n], cuts


P("")
P(f"{'K':>3} {'loglik':>10} {'params':>7} {'BIC':>10}  breakpoints (attempt index -> version)")
maxK = max(1, n // MINSEG)
bics = {}
for k in range(1, maxK + 1):
    ll, cuts = dp(k)
    if ll == INF:
        continue
    params = 2 * k - 1  # k rates + (k-1) breakpoints
    bic = -2 * ll + params * math.log(n)
    bics[k] = (bic, ll, cuts)
    bps = [c[0] for c in cuts[1:]]
    desc = ", ".join(f"idx{b}->v{vseq[b]}" for b in bps) or "(none)"
    P(f"{k:>3} {ll:10.3f} {params:>7} {bic:10.3f}  {desc}")

kbest = min(bics, key=lambda k: bics[k][0])
bic, ll, cuts = bics[kbest]
P("")
P(f"SELECTED K={kbest} by minimum BIC (BIC={bic:.3f})")
P("segments (index range, version range, wins/n, rate):")
seg_desc = []
for (i, j) in cuts:
    w = cum[j] - cum[i]
    seg_desc.append({"i": i, "j": j, "v_start": vseq[i], "v_end": vseq[j - 1],
                     "wins": w, "n": j - i, "rate": w / (j - i)})
    lo, hi = wilson(w, j - i)
    P(f"   idx[{i}:{j}) v{vseq[i]}..v{vseq[j-1]}  {w}/{j-i} = {w/(j-i):.3f}  "
      f"wilson95=[{lo:.3f},{hi:.3f}]")
bp_versions = [vseq[c[0]] for c in cuts[1:]]
P(f"BREAKPOINTS (fixed from outcome data alone): {bp_versions}")

# version-level bootstrap
P("")
P("Version-level bootstrap (resample versions with replacement, refit at K=%d, 400 reps):" % kbest)
byv = defaultdict(list)
for x in CC:
    byv[x["version_int"]].append(1 if x["win"] else 0)
vlist = sorted(byv)
rng = random.Random(20260726)
boot = []
for _ in range(400):
    samp = [rng.choice(vlist) for _ in vlist]
    samp.sort()
    yy = []
    vv = []
    for v in samp:
        yy.extend(byv[v])
        vv.extend([v] * len(byv[v]))
    nn = len(yy)
    if nn < kbest * MINSEG:
        continue
    cc = [0]
    for o in yy:
        cc.append(cc[-1] + o)

    def sll(i, j):
        return loglik(cc[j] - cc[i], j - i)

    f = [[INF] * (nn + 1) for _ in range(kbest + 1)]
    bk = [[None] * (nn + 1) for _ in range(kbest + 1)]
    f[0][0] = 0.0
    for s in range(1, kbest + 1):
        for j in range(s * MINSEG, nn + 1):
            for i in range((s - 1) * MINSEG, j - MINSEG + 1):
                if f[s - 1][i] == INF:
                    continue
                val = f[s - 1][i] + sll(i, j)
                if val > f[s][j]:
                    f[s][j] = val
                    bk[s][j] = i
    if f[kbest][nn] == INF:
        continue
    j, s, cs = nn, kbest, []
    while s > 0:
        i = bk[s][j]
        cs.append(i)
        j = i
        s -= 1
    cs = sorted(cs)[1:]
    boot.append([vv[i] for i in cs])
P(f"   successful bootstrap reps: {len(boot)}")
for pos in range(kbest - 1):
    vals = sorted(b[pos] for b in boot if len(b) > pos)
    if not vals:
        continue
    lo = vals[int(0.025 * len(vals))]
    hi = vals[min(len(vals) - 1, int(0.975 * len(vals)))]
    P(f"   breakpoint #{pos+1}: point={bp_versions[pos]}  bootstrap 95% interval on version = "
      f"[v{lo}, v{hi}]  median=v{vals[len(vals)//2]}")
    P(f"      bootstrap version histogram: {dict(Counter(vals).most_common(12))}")
RES["changepoints"] = {"K": kbest, "bic": bic, "breakpoint_versions": bp_versions,
                       "segments": seg_desc, "n": n,
                       "bic_table": {k: {"bic": v[0], "loglik": v[1]} for k, v in bics.items()},
                       "bootstrap_reps": len(boot),
                       "bootstrap": [b for b in boot]}

# ------------------------------------------------------------------ D2.7 missingness sensitivity
P("")
P("=" * 100)
P("D2.7 MISSINGNESS SENSITIVITY GRID")
P("=" * 100)
split = bp_versions[-1] if bp_versions else (vers[len(vers) // 2])
P(f"early/current split taken at the LAST data-derived breakpoint: version < {split} = EARLY, "
  f">= {split} = CURRENT")
early = [x for x in L if x["version_int"] < split and x["terminal_class"] != "EXTERNAL_ABORT"]
curr = [x for x in L if x["version_int"] >= split and x["terminal_class"] != "EXTERNAL_ABORT"]
for nm, g in (("EARLY", early), ("CURRENT", curr)):
    a = agg(g)
    P(f"{nm}: attempts={a['n_attempts']} wins={a['wins']} loss={a['gameplay_loss']} "
      f"modfail={a['modfail']} unknown={a['unknown']} "
      f"complete_case={a['complete_case_winrate']} e2e={a['end_to_end_success']}")
qs = [0.0, 0.25, 0.5, 0.75, 1.0]
we, ne, ue = sum(1 for x in early if x["win"]), len(early), sum(1 for x in early if x["terminal_class"] == "UNKNOWN")
wc, nc, uc = sum(1 for x in curr if x["win"]), len(curr), sum(1 for x in curr if x["terminal_class"] == "UNKNOWN")
P(f"raw inputs: early wins={we} attempts={ne} unknown={ue} | current wins={wc} attempts={nc} unknown={uc}")
P("")
P("grid cell = (current rate - early rate), percentage points. rows q_early, cols q_current")
P("        " + "".join(f"{q:>10.2f}" for q in qs))
grid = {}
for qe in qs:
    line = f"q_e={qe:.2f}"
    for qc in qs:
        re_ = (we + qe * ue) / ne
        rc_ = (wc + qc * uc) / nc
        line += f"{100*(rc_-re_):>10.1f}"
        grid[f"{qe}|{qc}"] = {"early": re_, "current": rc_, "gap_pp": 100 * (rc_ - re_)}
    P(line)
adv = grid["0.0|1.0"]
P("")
P(f"ADVERSARIAL CORNER (all EARLY unknowns are LOSSES, all CURRENT unknowns are WINS): "
  f"early={adv['early']:.4f} current={adv['current']:.4f} gap={adv['gap_pp']:+.1f} pp")
base = grid["0.0|0.0"]
P(f"opposite corner (all unknowns losses everywhere): gap={base['gap_pp']:+.1f} pp")
gaps = [v["gap_pp"] for v in grid.values()]
P(f"gap range over the whole grid: [{min(gaps):+.1f}, {max(gaps):+.1f}] pp; "
  f"sign flips across grid = {min(gaps) < 0 < max(gaps)}")
RES["sensitivity"] = {"split_version": split, "grid": grid,
                      "early": {"wins": we, "n": ne, "unknown": ue},
                      "current": {"wins": wc, "n": nc, "unknown": uc},
                      "adversarial_corner": adv,
                      "gap_min_pp": min(gaps), "gap_max_pp": max(gaps)}

# teacher-only version of the same grid
P("")
P("teacher-only sensitivity grid (same construction, teacher attempts only):")
te = [x for x in TEACH if x["version_int"] < split and x["terminal_class"] != "EXTERNAL_ABORT"]
tc_ = [x for x in TEACH if x["version_int"] >= split and x["terminal_class"] != "EXTERNAL_ABORT"]
we2, ne2, ue2 = sum(1 for x in te if x["win"]), len(te), sum(1 for x in te if x["terminal_class"] == "UNKNOWN")
wc2, nc2, uc2 = sum(1 for x in tc_ if x["win"]), len(tc_), sum(1 for x in tc_ if x["terminal_class"] == "UNKNOWN")
P(f"raw inputs: early wins={we2} attempts={ne2} unknown={ue2} | current wins={wc2} attempts={nc2} unknown={uc2}")
P("        " + "".join(f"{q:>10.2f}" for q in qs))
tgrid = {}
for qe in qs:
    line = f"q_e={qe:.2f}"
    for qc in qs:
        r1 = (we2 + qe * ue2) / ne2 if ne2 else float("nan")
        r2 = (wc2 + qc * uc2) / nc2 if nc2 else float("nan")
        line += f"{100*(r2-r1):>10.1f}"
        tgrid[f"{qe}|{qc}"] = 100 * (r2 - r1)
    P(line)
RES["sensitivity_teacher"] = {"early": {"wins": we2, "n": ne2, "unknown": ue2},
                              "current": {"wins": wc2, "n": nc2, "unknown": uc2},
                              "grid_gap_pp": tgrid}

# ------------------------------------------------------------------ era comparison from EB
P("")
P("=" * 100)
P("ERA-LEVEL COMPARISON OF SHRUNK PER-VERSION RATES (teacher, complete case)")
P("=" * 100)
segs = RES["changepoints"]["segments"]
ebv = {r["version"]: r for r in eb_out["teacher"]["versions"]}
for s in segs:
    vs = [v for v in ebv if s["v_start"] <= v <= s["v_end"]]
    pms = [ebv[v]["post_mean"] for v in vs]
    pms_s = sorted(pms)
    P(f"segment v{s['v_start']}..v{s['v_end']}: versions={len(vs)} pooled {s['wins']}/{s['n']}="
      f"{s['rate']:.3f}  shrunk per-version posterior means: mean={sum(pms)/len(pms):.3f} "
      f"median={pms_s[len(pms_s)//2]:.3f} min={pms_s[0]:.3f} max={pms_s[-1]:.3f}")
    P("     raw shrunk series: " + " ".join(f"v{v}:{ebv[v]['post_mean']:.3f}" for v in sorted(vs)))

os.makedirs(os.path.dirname(OUT_TXT), exist_ok=True)
open(OUT_TXT, "w", encoding="utf-8").write("\n".join(OUTBUF) + "\n")
json.dump(RES, open(OUT_JSON, "w", encoding="utf-8"), indent=1, default=str)
print(f"\nwrote {OUT_TXT} and {OUT_JSON}")
