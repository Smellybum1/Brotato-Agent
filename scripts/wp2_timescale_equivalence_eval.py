#!/usr/bin/env python
"""Evaluator for the pre-registered time_scale equivalence protocols.

Implements exactly and only the decision rule in
reports/wp2/timescale_equivalence_protocol.md, including the AMENDMENT section
(A1-A6, ambiguities closed before any outcome data was read).

The same decision rule is re-used, per arm, by
reports/wp2/timescale_doseresponse_protocol.md (the 2x/4x dose-response
campaign). That protocol differs only in its structural-gate CONSTANTS -- a
per-arm G1 lower bound with NO upper bound, and 28/32 rather than 14/16 -- plus
a declared-in-advance achieved/nominal MECHANISM diagnostic. All of those are
CLI arguments whose defaults reproduce the 8x campaign exactly, so the original
invocation below still produces byte-identical output.

Usage:
  # original 8x equivalence campaign (defaults unchanged)
  python scripts/wp2_timescale_equivalence_eval.py \
      --slow .tmp/ts_equiv/slow.jsonl --fast .tmp/ts_equiv/fast.jsonl

  # dose-response campaign, 2.0x arm vs the contemporaneous 1.0x control
  python scripts/wp2_timescale_equivalence_eval.py \
      --slow .tmp/ts_dose/s1.jsonl --fast .tmp/ts_dose/s2.jsonl \
      --nominal-scale 2.0 --g1-min 1.5 --g1-max none \
      --min-valid 28 --min-pairs 28

Standard library only. Reporting tool, not a gate.

Exit codes:
  0 -- a verdict was reached. ANY verdict, including FAIL: a FAIL verdict is a
       legitimate analytical result and must not look like a crashed tool.
  2 -- NO ANALYSIS WAS PERFORMED. Currently only the A6 arm-identity abort. This
       is an operator error, not a verdict; a tool that exits 0 having analysed
       nothing is a silent pass.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import statistics
import sys
from collections import Counter, defaultdict

DELTA = 19.0                      # equivalence margin (damage)
# Defaults are the 8x equivalence protocol's. The dose-response protocol
# overrides them on the command line.
G1_RATIO_LO, G1_RATIO_HI = 6.5, 9.5
G2_MIN_VALID = 14
G2_DENOM = 16
G5_MIN_PAIRS = 14                 # A2: precision gate, INCONCLUSIVE not FAIL
# Dose-response mechanism-test bands (achieved / nominal), declared in advance
# in reports/wp2/timescale_doseresponse_protocol.md. Diagnostic, NOT a gate.
MECH_SATURATION_IMPLICATED = 0.95
MECH_ARM_SATURATED = 0.90
EXPECTED_MOD = "0.2.49-wp2-capture"
# The protocol wrote this as the bare version "0.1.129"; the field actually
# carries "teacher_v1-0.1.129-gun-wp1". Correcting the expected STRING, not the
# gate's intent -- the deployed policy is still required to be 0.1.129.
EXPECTED_POLICY = "teacher_v1-0.1.129-gun-wp1"
BOOTSTRAP_N = 10000
BOOTSTRAP_SEED = 20260727

LABEL_ROUND_RE = re.compile(r"r(\d+)\s*$")


# --------------------------------------------------------------------------
# Statistics (implemented here: no scipy/numpy)
# --------------------------------------------------------------------------
def _betacf(a: float, b: float, x: float) -> float:
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 3e-16:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbeta + b * math.log1p(-x) + a * math.log(x)) * _betacf(b, a, 1.0 - x) / b


def t_cdf(t: float, df: float) -> float:
    x = df / (df + t * t)
    p = 0.5 * betainc(df / 2.0, 0.5, x)
    return 1.0 - p if t > 0 else p


def t_ppf(p: float, df: float) -> float:
    """Inverse t CDF by bisection (accurate to ~1e-10)."""
    lo, hi = -1000.0, 1000.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------
def parse_round(label):
    if not isinstance(label, str):
        return None
    m = LABEL_ROUND_RE.search(label)
    return int(m.group(1)) if m else None


def load(path, arm):
    rows = []
    problems = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    problems.append("%s arm line %d: unparseable JSON (%s)" % (arm, lineno, exc))
                    continue
                row["_arm"] = arm
                row["_round"] = parse_round(row.get("label"))
                if row["_round"] is None:
                    problems.append(
                        "%s arm line %d: could not parse round from label %r"
                        % (arm, lineno, row.get("label"))
                    )
                rows.append(row)
    except OSError as exc:
        problems.append("%s arm: cannot read %s (%s)" % (arm, path, exc))
    return rows, problems


def is_valid(row):
    return bool(row.get("valid"))


def check_arm_labels(rows, arm, path):
    """A6 -- arm identity is cross-checked, not assumed.

    Returns a list of mismatch descriptions; empty means the file is the arm
    the flag claims it is.
    """
    prefix = "ts_%s" % arm
    bad = []
    for i, r in enumerate(rows, 1):
        label = r.get("label")
        if not isinstance(label, str) or not label.startswith(prefix):
            bad.append("row %d (run_id=%r): label=%r does not start with %r"
                       % (i, r.get("run_id"), label, prefix))
    return bad


# --------------------------------------------------------------------------
# Gates
# --------------------------------------------------------------------------
def gate_g1(slow_rows, fast_rows, out, lo_bound=G1_RATIO_LO, hi_bound=G1_RATIO_HI,
            nominal=None):
    """G1 -- acceleration actually took effect.

    `hi_bound` may be None or math.inf, meaning NO UPPER BOUND: the
    dose-response protocol deliberately drops it because an upper bound tests
    this machine's throughput, not whether acceleration took effect.

    `nominal`, when given, adds the pre-registered achieved/nominal MECHANISM
    diagnostic. It is a DIAGNOSTIC and never changes the gate's pass/fail.
    """

    def rate(rows):
        vals = []
        for r in rows:
            if not is_valid(r):
                continue
            n, d = r.get("n_captures"), r.get("duration_ms")
            if isinstance(n, (int, float)) and isinstance(d, (int, float)) and d:
                vals.append(n / d)
        return vals

    sv, fv = rate(slow_rows), rate(fast_rows)
    if not sv or not fv:
        out.append("G1  FAIL  insufficient data: slow n=%d fast n=%d valid trials with "
                   "n_captures and duration_ms" % (len(sv), len(fv)))
        return False
    ms, mf = statistics.median(sv), statistics.median(fv)
    ratio = mf / ms if ms else float("inf")
    unbounded = hi_bound is None or hi_bound == float("inf")
    # The dose-response protocol writes the lower bound STRICTLY ("> 1.5",
    # "> 2.5"); implement the text it claims to implement.
    ok = ratio > lo_bound and (unbounded or ratio <= hi_bound)
    req = ("> %.1f, NO UPPER BOUND APPLIED (an upper bound tests throughput, "
           "not effect)" % lo_bound) if unbounded else "[%.1f, %.1f]" % (lo_bound, hi_bound)
    out.append("G1  %s  median n_captures/duration_ms: slow %.6f (n=%d), fast %.6f (n=%d), "
               "ratio fast/slow = %.4f, required %s"
               % ("PASS" if ok else "FAIL", ms, len(sv), mf, len(fv), ratio, req))
    # Dose-response protocol, Reporting: "Achieved-ratio series printed per arm,
    # not just its median." A median can hide a bimodal or drifting series, and
    # here the series IS the mechanism evidence.
    for arm, vals in (("slow", sv), ("fast", fv)):
        series = ", ".join("%.2f" % (v * 1000.0) for v in vals)
        out.append("G1  SERIES  %s arm captures per real second, per trial (n=%d): [%s]"
                   % (arm, len(vals), series))
    out.append("G1  SERIES  the ratio above is median/median; the series are printed so a "
               "bimodal or drifting arm cannot hide behind its median.")
    if nominal:
        quot = ratio / nominal
        out.append("G1  DIAGNOSTIC (mechanism test, NOT a gate): achieved %.4f / nominal "
                   "%.2f = %.4f of nominal" % (ratio, nominal, quot))
        if quot >= MECH_SATURATION_IMPLICATED:
            out.append("G1  DIAGNOSTIC  band: >= %.2f of nominal -- if this arm comes back "
                       "EQUIVALENT, SATURATION IS IMPLICATED and the safe operating rule is "
                       "'any scale this machine sustains', headroom checked per machine. If "
                       "it STILL degrades, saturation is refuted, acceleration is unsafe in "
                       "principle, and the line closes permanently."
                       % MECH_SATURATION_IMPLICATED)
        elif quot < MECH_ARM_SATURATED:
            out.append("G1  DIAGNOSTIC  band: < %.2f of nominal -- THIS ARM WAS ITSELF "
                       "SATURATED. Its result reads as 'saturated at this scale', NOT 'this "
                       "scale is unsafe'; the honest conclusion is that this machine's "
                       "ceiling sits below it." % MECH_ARM_SATURATED)
        else:
            out.append("G1  DIAGNOSTIC  band: in [%.2f, %.2f) of nominal -- the protocol "
                       "declares no interpretation for this band; neither the saturation-"
                       "implicated nor the arm-saturated reading is licensed."
                       % (MECH_ARM_SATURATED, MECH_SATURATION_IMPLICATED))
    return ok


def gate_g2(slow_rows, fast_rows, out, min_valid=G2_MIN_VALID):
    ok = True
    for arm, rows in (("slow", slow_rows), ("fast", fast_rows)):
        valid = [r for r in rows if is_valid(r)]
        arm_ok = len(valid) >= min_valid
        # The 8x protocol's denominator is 16 (2 rounds); the dose-response
        # protocol's is 32 (4 rounds). Report the arm's own trial count when it
        # exceeds the default so the printed ratio is never "28 / 16".
        denom = max(G2_DENOM, len(rows))
        out.append("G2  %s  %s arm valid trials = %d / %d (rows present = %d), required >= %d"
                   % ("PASS" if arm_ok else "FAIL", arm, len(valid), denom, len(rows),
                      min_valid))
        ok = ok and arm_ok
        bad_waves = [r.get("run_id") for r in valid if r.get("waves") != [20]]
        bad_boss = [r.get("run_id") for r in valid if r.get("boss_entity") != "predator"]
        # boss_paths is a DICT {script_path: capture_count}, not a list. The
        # isinstance(..., list) test flagged all 32 rows and produced a spurious
        # G2 failure on clean data; a gate that cannot pass is worth nothing.
        bad_paths = [
            r.get("run_id") for r in valid
            if not isinstance(r.get("boss_paths"), dict) or len(r.get("boss_paths")) != 1
        ]
        for name, bad in (("waves != [20]", bad_waves),
                          ("boss_entity != predator", bad_boss),
                          ("boss_paths length != 1", bad_paths)):
            status = "PASS" if not bad else "FAIL"
            out.append("G2  %s  %s arm shape check %s: %d offending valid trials%s"
                       % (status, arm, name, len(bad),
                          "" if not bad else " -> " + ", ".join(str(b) for b in bad[:8])))
            ok = ok and not bad
    return ok


def gate_g3(slow_rows, fast_rows, out):
    ok = True
    allrows = slow_rows + fast_rows
    checks = (
        ("finale_pivot_projectiles", True),
        ("mod_version", EXPECTED_MOD),
        ("policy_version", EXPECTED_POLICY),
    )
    for field, expected in checks:
        seen = Counter(repr(r.get(field)) for r in allrows)
        distinct = sorted(seen.items(), key=lambda kv: (-kv[1], kv[0]))
        field_ok = len(seen) == 1 and next(iter(seen)) == repr(expected)
        ok = ok and field_ok
        out.append("G3  %s  %s distinct values over %d trials: %s (expected only %r)"
                   % ("PASS" if field_ok else "FAIL", field, len(allrows),
                      ", ".join("%s x%d" % (v, c) for v, c in distinct) or "<none>",
                      expected))
    return ok


def gate_g4(slow_rows, fast_rows, out):
    rounds = sorted({r["_round"] for r in slow_rows + fast_rows if r["_round"] is not None})
    ok = bool(rounds)
    if not rounds:
        out.append("G4  FAIL  no rounds could be parsed from any label")
        return False
    for rnd in rounds:
        s = sum(1 for r in slow_rows if r["_round"] == rnd and is_valid(r))
        f = sum(1 for r in fast_rows if r["_round"] == rnd and is_valid(r))
        rok = s >= 1 and f >= 1
        ok = ok and rok
        out.append("G4  %s  round %d: slow valid = %d, fast valid = %d, required >= 1 each"
                   % ("PASS" if rok else "FAIL", rnd, s, f))
    return ok


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def short(digest):
    return str(digest)[:12] if digest is not None else "<none>"


def parse_upper_bound(text):
    """G1's upper bound, which must be genuinely optional.

    Accepts a float, or any of none/off/inf/infinity/disabled meaning NO UPPER
    BOUND (the dose-response protocol deliberately specifies none).
    """
    if text is None:
        return None
    t = str(text).strip().lower()
    if t in ("none", "off", "no", "disabled", "inf", "+inf", "infinity", "float('inf')"):
        return float("inf")
    try:
        return float(t)
    except ValueError:
        raise argparse.ArgumentTypeError(
            "--g1-max must be a number, or one of none/off/inf to disable the upper bound")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--slow", required=True)
    ap.add_argument("--fast", required=True)
    ap.add_argument("--nominal-scale", type=float, default=None,
                    help="the treatment arm's REQUESTED time_scale (e.g. 2.0, 4.0, 8.0). "
                         "When given, G1 additionally prints the pre-registered "
                         "achieved/nominal mechanism diagnostic. Diagnostic only -- it "
                         "never changes the verdict.")
    ap.add_argument("--g1-min", type=float, default=G1_RATIO_LO,
                    help="G1 minimum achieved ratio (default %(default)s, the 8x "
                         "protocol's; dose-response uses 1.5 for the 2x arm and 2.5 "
                         "for the 4x arm)")
    ap.add_argument("--g1-max", type=parse_upper_bound, default=G1_RATIO_HI,
                    help="G1 maximum achieved ratio (default %s). Pass none/off/inf to "
                         "DISABLE the upper bound entirely, as the dose-response protocol "
                         "requires." % G1_RATIO_HI)
    ap.add_argument("--min-valid", type=int, default=G2_MIN_VALID,
                    help="G2 minimum valid trials per arm (default %(default)s; "
                         "dose-response uses 28)")
    ap.add_argument("--min-pairs", type=int, default=G5_MIN_PAIRS,
                    help="G5 minimum pairs formed (default %(default)s; dose-response "
                         "uses 28). Failure yields INCONCLUSIVE, never FAIL.")
    # The 8x protocol pre-registers exactly ONE escalation to 32 pairs. The
    # dose-response protocol pre-registers NONE ("No escalation is pre-registered
    # in any branch"), so an INCONCLUSIVE verdict there must not offer one.
    # Deliberately NOT inferred from --nominal-scale: an implicit coupling
    # between an unrelated flag and the wording of a verdict gets misread later.
    ap.add_argument("--escalation", dest="escalation", action="store_true", default=True,
                    help="one escalation to 32 pairs is pre-registered (default; the 8x "
                         "equivalence protocol)")
    ap.add_argument("--no-escalation", dest="escalation", action="store_false",
                    help="NO escalation is pre-registered in any branch (the "
                         "dose-response protocol); the campaign ends at the verdict")
    args = ap.parse_args()
    min_pairs = args.min_pairs
    esc = args.escalation
    # Verdict-text fragments. The escalation-granting forms are the originals,
    # byte for byte.
    ESC_G5 = ("-> eligible for the single pre-registered escalation." if esc else
              "-> NO ESCALATION IS PRE-REGISTERED IN ANY BRANCH; the campaign ends at "
              "this verdict.")
    ESC_R5 = ("-> the single pre-registered escalation to 32 pairs (64 trials, 2 further "
              "rounds) is permitted; same rules, same margin, no second extension." if esc
              else "-> NO ESCALATION IS PRE-REGISTERED IN ANY BRANCH; the campaign ends at "
              "this verdict, with the same margin and no extension of any kind.")

    slow_rows, p1 = load(args.slow, "slow")
    fast_rows, p2 = load(args.fast, "fast")
    load_problems = p1 + p2

    print("=" * 78)
    print("time_scale equivalence evaluator")
    print("protocol: reports/wp2/timescale_equivalence_protocol.md (frozen)")
    print("slow: %s  (%d rows)" % (args.slow, len(slow_rows)))
    print("fast: %s  (%d rows)" % (args.fast, len(fast_rows)))
    print("=" * 78)
    for p in load_problems:
        print("LOAD PROBLEM: " + p)
    if load_problems:
        print()

    # ---- A6: arm identity cross-check (abort loudly) -----------------------
    label_bad = ([("slow", args.slow, m) for m in check_arm_labels(slow_rows, "slow", args.slow)]
                 + [("fast", args.fast, m) for m in check_arm_labels(fast_rows, "fast", args.fast)])
    if label_bad:
        print("!" * 78)
        print("ABORT (protocol amendment A6): ARM IDENTITY CROSS-CHECK FAILED.")
        print("Every row in the --slow file must have a label starting 'ts_slow' and")
        print("every row in the --fast file a label starting 'ts_fast'. A file passed to")
        print("the wrong flag would invert the sign of the entire result silently.")
        print("%d mismatching rows:" % len(label_bad))
        for arm, path, msg in label_bad[:20]:
            print("  --%s file %s: %s" % (arm, path, msg))
        if len(label_bad) > 20:
            print("  ... and %d more" % (len(label_bad) - 20))
        print("NO ANALYSIS PERFORMED. Fix the arguments and re-run.")
        print("!" * 78)
        # Exit 2, not 0: no analysis was performed. Every verdict path below
        # returns 0, including FAIL -- a FAIL verdict is a real result.
        return 2

    # ---- index by pair key -------------------------------------------------
    def index(rows):
        idx = defaultdict(list)
        for r in rows:
            idx[(r.get("fixture_digest"), r["_round"])].append(r)
        return idx

    si, fi = index(slow_rows), index(fast_rows)
    keys = sorted(set(si) | set(fi), key=lambda k: (str(k[0]), -1 if k[1] is None else k[1]))

    print("--- 1. RAW PAIR TABLE (primary outcome = damage_taken, diff = fast - slow) ---")
    print("%-14s %6s %12s %12s %12s" % ("fixture", "round", "slow_dmg", "fast_dmg", "diff"))
    diffs = []
    dropped = []
    for key in keys:
        dig, rnd = key
        s_all, f_all = si.get(key, []), fi.get(key, [])
        s_ok = [r for r in s_all if is_valid(r) and isinstance(r.get("damage_taken"), (int, float))]
        f_ok = [r for r in f_all if is_valid(r) and isinstance(r.get("damage_taken"), (int, float))]
        if len(s_ok) == 1 and len(f_ok) == 1:
            sd, fd = s_ok[0]["damage_taken"], f_ok[0]["damage_taken"]
            d = fd - sd
            diffs.append((dig, rnd, sd, fd, d))
            print("%-14s %6s %12.1f %12.1f %+12.1f"
                  % (short(dig), rnd, sd, fd, d))
        else:
            reasons = []
            for arm, all_, ok_ in (("slow", s_all, s_ok), ("fast", f_all, f_ok)):
                if not all_:
                    reasons.append("%s missing" % arm)
                elif not ok_:
                    bad = all_[0]
                    reasons.append("%s invalid (invalid_reason=%r, valid=%r, damage_taken=%r)"
                                   % (arm, bad.get("invalid_reason"), bad.get("valid"),
                                      bad.get("damage_taken")))
                elif len(ok_) > 1:
                    reasons.append("%s has %d valid trials (expected 1)" % (arm, len(ok_)))
            dropped.append((dig, rnd, "; ".join(reasons)))
            print("%-14s %6s %12s %12s %12s   DROPPED"
                  % (short(dig), rnd, "-", "-", "-"))
    print()
    print("pairs formed : %d" % len(diffs))
    print("pairs dropped: %d" % len(dropped))
    for dig, rnd, why in dropped:
        print("  DROPPED %s round %s: %s" % (short(dig), rnd, why))
    print()

    # ---- 2. gates ----------------------------------------------------------
    print("--- 2. STRUCTURAL GATES ---")
    lines = []
    g1 = gate_g1(slow_rows, fast_rows, lines, lo_bound=args.g1_min,
                 hi_bound=args.g1_max, nominal=args.nominal_scale)
    g2 = gate_g2(slow_rows, fast_rows, lines, min_valid=args.min_valid)
    g3 = gate_g3(slow_rows, fast_rows, lines)
    g4 = gate_g4(slow_rows, fast_rows, lines)
    for line in lines:
        print(line)
    gates_pass = g1 and g2 and g3 and g4
    print("GATES OVERALL (FAIL gates G1-G4): %s  (G1=%s G2=%s G3=%s G4=%s)"
          % ("PASS" if gates_pass else "FAIL",
             "PASS" if g1 else "FAIL", "PASS" if g2 else "FAIL",
             "PASS" if g3 else "FAIL", "PASS" if g4 else "FAIL"))
    g5 = len(diffs) >= min_pairs
    print("G5  %s  pairs formed = %d, required >= %d  "
          "(A2 precision gate -- failure yields INCONCLUSIVE, NOT FAIL)"
          % ("PASS" if g5 else "FAIL", len(diffs), min_pairs))
    print()

    # ---- 3. primary --------------------------------------------------------
    print("--- 3. PRIMARY RESULT: damage_taken paired difference (fast - slow) ---")
    d = [x[4] for x in diffs]
    n = len(d)
    ci = None
    print("n pairs = %d" % n)
    if n >= 2:
        mean = statistics.fmean(d)
        sd = statistics.stdev(d)
        se = sd / math.sqrt(n)
        df = n - 1
        tcrit = t_ppf(0.975, df)
        lo, hi = mean - tcrit * se, mean + tcrit * se
        ci = (lo, hi)
        print("mean paired difference = %+.4f" % mean)
        print("SD of differences      = %.4f" % sd)
        print("standard error         = %.4f" % se)
        print("t critical value       = %.6f  (two-sided 95%%, df = n-1 = %d)" % (tcrit, df))
        print("paired-t 95%% CI        = [%+.4f, %+.4f]" % (lo, hi))

        rng = random.Random(BOOTSTRAP_SEED)
        means = []
        for _ in range(BOOTSTRAP_N):
            means.append(sum(d[rng.randrange(n)] for _ in range(n)) / n)
        means.sort()
        blo = means[int(math.floor(0.025 * (BOOTSTRAP_N - 1)))]
        bhi = means[int(math.ceil(0.975 * (BOOTSTRAP_N - 1)))]
        print("bootstrap percentile 95%% CI = [%+.4f, %+.4f]  (%d resamples, seed %d)"
              % (blo, bhi, BOOTSTRAP_N, BOOTSTRAP_SEED))
    else:
        print("CANNOT COMPUTE CI: fewer than 2 pairs.")

    for arm, rows in (("slow", slow_rows), ("fast", fast_rows)):
        dmg = [r["damage_taken"] for r in rows
               if is_valid(r) and isinstance(r.get("damage_taken"), (int, float))]
        if dmg:
            print("pooled %s arm damage: n=%d mean=%.4f median=%.4f"
                  % (arm, len(dmg), statistics.fmean(dmg), statistics.median(dmg)))
        else:
            print("pooled %s arm damage: no valid trials" % arm)
    print()

    # ---- 4. reported but not decisive -------------------------------------
    print("--- 4. REPORTED BUT NOT DECISIVE ---")
    losses = {}
    for arm, rows in (("slow", slow_rows), ("fast", fast_rows)):
        valid = [r for r in rows if is_valid(r)]
        wins = sum(1 for r in valid if str(r.get("result", "")).lower() in ("win", "victory"))
        losses[arm] = len(valid) - wins
        print("%s arm victories: %d / %d valid  (losses = %d); result values seen: %s"
              % (arm, wins, len(valid), losses[arm],
                 dict(Counter(str(r.get("result")) for r in valid))))
        wall = [r["trial_wall_sec"] for r in valid
                if isinstance(r.get("trial_wall_sec"), (int, float))]
        print("%s arm median trial_wall_sec: %s"
              % (arm, "%.2f" % statistics.median(wall) if wall else "n/a"))
    loss_gap = losses.get("fast", 0) - losses.get("slow", 0)
    mandatory_escalation = loss_gap >= 3
    print("loss gap (fast - slow) = %d; mandatory-escalation threshold >= 3 -> %s"
          % (loss_gap, "TRIGGERED" if mandatory_escalation else "not triggered"))
    print()

    # ---- 5. verdict --------------------------------------------------------
    print("--- 5. VERDICT (amendment A1 ordered rules; A2 G5; A5 loss clause) ---")
    if ci is None:
        if not gates_pass:
            print("VERDICT: FAIL  [rule 1] -- a structural gate failed (G1=%s G2=%s G3=%s "
                  "G4=%s); no CI computable (%d pairs)."
                  % ("PASS" if g1 else "FAIL", "PASS" if g2 else "FAIL",
                     "PASS" if g3 else "FAIL", "PASS" if g4 else "FAIL", len(diffs)))
        else:
            print("VERDICT: INCONCLUSIVE  [G5 (A2)] -- only %d pairs formed (< %d) and "
                  "no CI is computable below 2 pairs; a precision shortfall, not a "
                  "validity break." % (len(diffs), min_pairs))
    else:
        lo, hi = ci
        within = (lo >= -DELTA) and (hi <= DELTA)
        contains_zero = lo <= 0.0 <= hi
        wholly_outside = (lo > DELTA) or (hi < -DELTA)
        cis = "CI [%+.3f, %+.3f]" % (lo, hi)
        gate_str = ("G1=%s G2=%s G3=%s G4=%s"
                    % ("PASS" if g1 else "FAIL", "PASS" if g2 else "FAIL",
                       "PASS" if g3 else "FAIL", "PASS" if g4 else "FAIL"))
        verdict = None
        # A1 rule 1 / rule 2 are FAIL and are NOT overridden by the loss clause (A5).
        if not gates_pass:
            verdict = ("FAIL", "rule 1", "a structural gate failed (%s); any gate failure "
                       "is FAIL regardless of the damage CI. %s" % (gate_str, cis))
        elif wholly_outside:
            verdict = ("FAIL", "rule 2", "%s lies wholly outside [%+.0f, %+.0f]. "
                       "Acceleration stays a dev convenience; real campaigns run at 1.0x."
                       % (cis, -DELTA, DELTA))
        # A5: the loss clause outranks the damage CI, but not a structural FAIL.
        elif mandatory_escalation:
            verdict = ("INCONCLUSIVE", "A5 loss clause",
                       "the fast arm recorded %d more losses than the slow arm (>= 3), "
                       "which OUTRANKS the damage CI %s %s" % (
                           loss_gap, cis,
                           ("-> mandatory escalation to 32 pairs (64 trials, 2 further "
                            "rounds); same rules, same margin %.0f, no second extension."
                            % DELTA) if esc else
                           ("-> NO ESCALATION IS PRE-REGISTERED IN ANY BRANCH, so the "
                            "mandatory-escalation remedy is unavailable and the campaign "
                            "ends at this verdict (margin %.0f)." % DELTA)))
        # A2: precision shortfall, evaluated after the FAIL gates, before the CI rules.
        elif not g5:
            verdict = ("INCONCLUSIVE", "G5 (A2)",
                       "only %d pairs formed, fewer than the required %d; this is a "
                       "precision shortfall, not a validity break, so it is INCONCLUSIVE "
                       "and not FAIL. %s %s" % (len(diffs), min_pairs, cis, ESC_G5))
        elif within and contains_zero:
            verdict = ("EQUIVALENT", "rule 3",
                       "%s lies within [%+.0f, %+.0f] and contains 0, all structural "
                       "gates pass -> acceleration approved for campaigns."
                       % (cis, -DELTA, DELTA))
        elif within and not contains_zero:
            verdict = ("SMALL SHIFT", "rule 4",
                       "%s lies within [%+.0f, %+.0f] but does NOT contain 0, all gates "
                       "pass -> approved for paired same-scale campaigns only; never "
                       "pooled with 1.0x data or compared against archived 1x baselines."
                       % (cis, -DELTA, DELTA))
        else:
            verdict = ("INCONCLUSIVE", "rule 5",
                       "%s straddles a margin boundary of [%+.0f, %+.0f] (neither wholly "
                       "inside nor wholly outside) %s" % (cis, -DELTA, DELTA, ESC_R5))
        # The A1 rule set is exhaustive; this must never fire.
        assert verdict is not None, "A1 rule set failed to be exhaustive"
        print("VERDICT: %s  [%s] -- %s" % verdict)
    return 0


if __name__ == "__main__":
    sys.exit(main())
