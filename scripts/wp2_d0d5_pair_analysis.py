"""S26 -- matched D0-vs-D5 pair on character_mutant. PRE-REGISTERED analysis.

Implements reports/wp2/d0_d5_matched_pair_prereg.md.

  PRIMARY   (S26c) terminal-wave distribution per arm, full raw series, victory
            rate; comparison by permutation on the difference in MEAN terminal
            wave, TWO-SIDED. Exact enumeration when the assignment space is
            <= 2,000,000, otherwise a fixed-seed Monte Carlo of 200,000
            resamples. Which one ran is always printed.
  SECONDARY (S26d) offense at a landmark vs terminal wave, Spearman rho within
            each arm, difference between arms by permutation. The landmark
            problem is STRUCTURAL: the per-arm EXCLUSION COUNT is printed
            BEFORE every rho, and if k=5 (the pre-registered primary landmark)
            excludes anything in either arm the result is flagged CONTAMINATED.

Offense = sum(weapon.damage) over the CAPTURE's payload.weapons at the FIRST
combat_capture of the wave. NOT the save file's weapons[i].stats (same field
names, ~3.4x apart) and NOT sum(damage/cooldown).

Validity is printed BEFORE any outcome. The analysis REFUSES to run below
MIN_PER_ARM runs in either arm -- a partial verdict on a blind design is
optional stopping.

No scipy: Spearman is implemented here (rank transform with average ranks,
then Pearson). Output is deliberately ASCII-only -- the S25 script died of
UnicodeEncodeError on Windows cp1252 AFTER printing its verdict.

`--self-test` validates the machinery on synthetic data before it decides
anything. Importing this module executes nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import tempfile
from fractions import Fraction
from itertools import combinations
from math import comb, sqrt
from pathlib import Path

ARMS = ("D0", "D5")
ARM_DIR = {"D0": "d5pair_d0", "D5": "d5pair_d5"}
ARM_DANGER = {"D0": 0, "D5": 5}
MIN_PER_ARM = 16
LANDMARKS = [2, 3, 4, 5, 6, 8, 10]
PRIMARY_LANDMARK = 5
EXACT_LIMIT = 2_000_000
MC_RESAMPLES = 200_000
MC_SEED = 20260802


# ---------------------------------------------------------------- statistics

def ranks(xs: list[float]) -> list[float]:
    """Average ranks, 1-based, ties averaged."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    out = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            out[order[k]] = avg
        i = j + 1
    return out


def pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sxx = sum((a - mx) ** 2 for a in xs)
    syy = sum((b - my) ** 2 for b in ys)
    if sxx <= 0 or syy <= 0:
        return None  # a constant vector has no correlation, not a zero one
    return sxy / sqrt(sxx * syy)


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys):
        raise ValueError("spearman: length mismatch")
    if len(xs) < 2:
        return None
    return pearson(ranks(list(xs)), ranks(list(ys)))


def perm_mean_diff(a: list[float], b: list[float],
                   exact_limit: int = EXACT_LIMIT,
                   resamples: int = MC_RESAMPLES,
                   seed: int = MC_SEED) -> dict:
    """Two-sided permutation test on mean(a) - mean(b).

    Returns dict with p, mode ('exact'/'monte-carlo'), space/resamples, and the
    exact Fraction when the enumeration was exhaustive.
    """
    na, nb = len(a), len(b)
    pooled = list(a) + list(b)
    obs = sum(a) / na - sum(b) / nb
    target = abs(obs) - 1e-12
    space = comb(na + nb, na)

    # EXACT even when the space is astronomically large. mean(a)-mean(b) is a
    # monotone function of sum(a), so the exact null distribution is the count
    # of na-subsets by sum -- a subset-sum DP costing O(n*na*total), not
    # C(n,na) enumerations. C(32,16) = 601,080,390 is hopeless to enumerate and
    # trivial this way. Requires integer values; terminal waves are integers.
    # The pre-registration (S26c) says EXACT, so this path is preferred and the
    # Monte Carlo below is only a last resort for non-integer data.
    if all(float(v).is_integer() for v in pooled):
        ints = [int(v) for v in pooled]
        total_i = sum(ints)
        # counts[k][s] = number of ways to choose k items summing to s
        counts = [[0] * (total_i + 1) for _ in range(na + 1)]
        counts[0][0] = 1
        for v in ints:
            for k in range(min(na, na), 0, -1):
                prev, cur = counts[k - 1], counts[k]
                for s in range(total_i - v, -1, -1):
                    c = prev[s]
                    if c:
                        cur[s + v] += c
        hits = 0
        for s, c in enumerate(counts[na]):
            if c and abs(s / na - (total_i - s) / nb) >= target:
                hits += c
        frac = Fraction(hits, space)
        return {"p": float(frac), "mode": "exact", "method": "subset-sum-dp",
                "space": space, "fraction": frac, "observed": obs}

    if space <= exact_limit:
        hits = 0
        total = sum(pooled)
        for idx in combinations(range(na + nb), na):
            sa = sum(pooled[i] for i in idx)
            d = sa / na - (total - sa) / nb
            if abs(d) >= target:
                hits += 1
        frac = Fraction(hits, space)
        return {"p": float(frac), "mode": "exact", "method": "enumeration",
                "space": space, "fraction": frac, "observed": obs}
    rng = random.Random(seed)
    hits = 0
    idxs = list(range(na + nb))
    total = sum(pooled)
    for _ in range(resamples):
        rng.shuffle(idxs)
        sa = sum(pooled[i] for i in idxs[:na])
        d = sa / na - (total - sa) / nb
        if abs(d) >= target:
            hits += 1
    p = (hits + 1) / (resamples + 1)
    return {"p": p, "mode": "monte-carlo", "space": space,
            "resamples": resamples, "seed": seed, "hits": hits,
            "floor": 1.0 / (resamples + 1), "observed": obs}


def perm_rho_diff(xa: list[float], ya: list[float],
                  xb: list[float], yb: list[float],
                  resamples: int = MC_RESAMPLES, seed: int = MC_SEED) -> dict | None:
    """Two-sided permutation on rho(arm A) - rho(arm B), shuffling arm labels."""
    ra, rb = spearman(xa, ya), spearman(xb, yb)
    if ra is None or rb is None:
        return None
    obs = ra - rb
    pairs = list(zip(xa, ya)) + list(zip(xb, yb))
    na = len(xa)
    rng = random.Random(seed)
    hits = 0
    for _ in range(resamples):
        rng.shuffle(pairs)
        pa, pb = pairs[:na], pairs[na:]
        sa = spearman([p[0] for p in pa], [p[1] for p in pa])
        sb = spearman([p[0] for p in pb], [p[1] for p in pb])
        if sa is None or sb is None:
            continue
        if abs(sa - sb) >= abs(obs) - 1e-12:
            hits += 1
    return {"rho_a": ra, "rho_b": rb, "diff": obs,
            "p": (hits + 1) / (resamples + 1), "resamples": resamples,
            "seed": seed, "floor": 1.0 / (resamples + 1)}


# ---------------------------------------------------------------------- I/O

def offense_by_landmark(events_path: Path, landmarks: list[int]) -> dict[int, float]:
    """sum(weapon.damage) at the FIRST combat_capture of each landmark wave."""
    want = set(landmarks)
    got: dict[int, float] = {}
    if not events_path.exists():
        return got
    with events_path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if '"combat_capture"' not in line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("event") != "combat_capture":
                continue
            pay = e.get("payload") or {}
            w = pay.get("wave")
            if w not in want or w in got:  # FIRST capture of the wave only
                continue
            tot = 0.0
            for wp in pay.get("weapons") or []:
                d = wp.get("damage")
                if isinstance(d, (int, float)):
                    tot += float(d)
            got[w] = tot
            if len(got) == len(want):
                break
    return got


def load_run(runs_dir: Path, rid: str) -> dict | None:
    sp = runs_dir / rid / "summary.json"
    if not sp.exists():
        return None
    s = json.loads(sp.read_text(encoding="utf-8-sig"))
    pool = s.get("unlock_pool") or {}
    row = {
        "run_id": rid,
        "wave": s.get("last_wave"),
        "victory": str(s.get("result", "")).lower() == "victory",
        "build": str(s.get("mod_version")),
        "char_ok": bool(s.get("character_ok")),
        "danger_ok": bool(s.get("danger_ok")),
        "danger": s.get("danger"),
        "requested_character": str(s.get("requested_character")),
        "estop_suppressed": s.get("movement_estop_suppressed"),
        "era": (pool.get("items"), pool.get("weapons"), str(pool.get("items_hash"))),
        "opener": s.get("weapon"),
        "offense": offense_by_landmark(runs_dir / rid / "events.jsonl", LANDMARKS),
    }
    if not row["opener"]:
        ev = runs_dir / rid / "events.jsonl"
        if ev.exists():
            with ev.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if '"run_start"' in line:
                        try:
                            row["opener"] = (json.loads(line).get("payload") or {}).get("weapon")
                        except Exception:
                            pass
                        break
    return row


def load_arm(root: Path, runs_dir: Path, arm: str) -> tuple[list[dict], list[str]]:
    problems: list[str] = []
    sf = root / ".tmp" / ARM_DIR[arm] / "state.json"
    if not sf.exists():
        return [], [f"{arm}: no state file {sf}"]
    ids = json.loads(sf.read_text(encoding="utf-8-sig")).get("collected_run_ids") or []
    rows = []
    for rid in ids:
        r = load_run(runs_dir, rid)
        if r is None:
            problems.append(f"{arm}: missing summary for {rid}")
            continue
        rows.append(r)
    return rows, problems


# ------------------------------------------------------------------ reporting

def describe(vals: list[float]) -> dict:
    n = len(vals)
    mean = sum(vals) / n
    sv = sorted(vals)
    med = sv[n // 2] if n % 2 else (sv[n // 2 - 1] + sv[n // 2]) / 2.0
    sd = sqrt(sum((v - mean) ** 2 for v in vals) / (n - 1)) if n > 1 else 0.0
    return {"n": n, "mean": mean, "median": med, "sd": sd,
            "min": sv[0], "max": sv[-1]}


def analyse(root: Path, runs_dir: Path) -> int:
    arms: dict[str, list[dict]] = {}
    problems: list[str] = []
    for arm in ARMS:
        rows, probs = load_arm(root, runs_dir, arm)
        arms[arm] = rows
        problems += probs

    short = [a for a in ARMS if len(arms[a]) < MIN_PER_ARM]
    if short or problems:
        print("REFUSING TO RUN -- the pre-registered analysis is defined at "
              f"{MIN_PER_ARM} runs per arm, 2 arms (S26b).")
        for a in ARMS:
            print(f"  {a}: {len(arms[a])}/{MIN_PER_ARM} runs")
        for p in problems:
            print("  -", p)
        print("\nAnalysing a prefix and then collecting more is optional stopping.")
        return 2

    print("=" * 78)
    print("VALIDITY -- per arm, before any outcome (S26e)")
    print("=" * 78)
    clean = True
    eras_per_arm = {}
    for arm in ARMS:
        rows = arms[arm]
        n = len(rows)
        cok = sum(1 for r in rows if r["char_ok"])
        dok = sum(1 for r in rows if r["danger_ok"])
        eras = sorted({r["era"] for r in rows}, key=str)
        builds = sorted({r["build"] for r in rows})
        dangers = sorted({str(r["danger"]) for r in rows})
        openers = sorted({str(r["opener"]) for r in rows})
        estop = sorted({str(r["estop_suppressed"]) for r in rows})
        eras_per_arm[arm] = eras
        print(f"  {arm}  n={n}")
        print(f"      character_ok   {cok}/{n}" + ("" if cok == n else "   <-- PROBLEM"))
        print(f"      danger_ok      {dok}/{n}" + ("" if dok == n else "   <-- PROBLEM"))
        print(f"      era tuples     {eras}" + ("" if len(eras) == 1 else "   <-- PROBLEM"))
        print(f"      builds         {builds}" + ("" if len(builds) == 1 else "   <-- PROBLEM"))
        print(f"      danger observed{'':1} {dangers} (expected {ARM_DANGER[arm]})")
        print(f"      openers        {openers}")
        print(f"      estop_suppressed values {estop}")
        if cok != n:
            print(f"  FAIL: {arm} has {n - cok} runs with character_ok false")
            clean = False
        if dok != n:
            print(f"  FAIL: {arm} has {n - dok} runs with danger_ok false")
            clean = False
        if len(eras) != 1:
            print(f"  FAIL: {arm} spans {len(eras)} shop-pool eras")
            clean = False
        if len(builds) != 1:
            print(f"  FAIL: {arm} spans {len(builds)} builds")
            clean = False
        if dangers != [str(ARM_DANGER[arm])]:
            print(f"  FAIL: {arm} observed danger {dangers}, expected {ARM_DANGER[arm]}")
            clean = False
    if eras_per_arm["D0"] != eras_per_arm["D5"]:
        print("  FAIL: the two arms' era tuples DIFFER -- the pair is not poolable")
        clean = False
    print(f"\n  CLEAN: {clean}")

    print("\n" + "=" * 78)
    print("PRIMARY (S26c) -- terminal wave, descriptive, full raw series")
    print("=" * 78)
    waves = {}
    for arm in ARMS:
        w = sorted(int(r["wave"]) for r in arms[arm])
        waves[arm] = w
        d = describe([float(x) for x in w])
        v = sum(1 for r in arms[arm] if r["victory"])
        print(f"  {arm} raw terminal waves: {w}")
        print(f"      n={d['n']}  mean={d['mean']:.3f}  median={d['median']:.1f}  "
              f"sd={d['sd']:.3f}  min={d['min']:.0f}  max={d['max']:.0f}")
        print(f"      victories {v}/{d['n']} = {v/d['n']:.4f}")
    res = perm_mean_diff([float(x) for x in waves["D0"]],
                         [float(x) for x in waves["D5"]])
    print(f"\n  observed mean difference (D0 - D5): {res['observed']:+.4f}")
    print(f"  assignment space C({len(waves['D0'])+len(waves['D5'])},"
          f"{len(waves['D0'])}) = {res['space']:,}")
    if res["mode"] == "exact":
        f = res["fraction"]
        if res.get("method") == "subset-sum-dp":
            print(f"  mode: EXACT over all {res['space']:,} assignments, via a "
                  f"subset-sum DP (the statistic is monotone in sum(D0), so the "
                  f"null is counted, not enumerated)")
        else:
            print(f"  mode: EXACT enumeration of all {res['space']:,} assignments")
        print(f"  p (two-sided): {res['p']:.6g}   [{f.numerator}/{f.denominator}]")
    else:
        print(f"  mode: MONTE CARLO ({res['resamples']:,} resamples, seed {res['seed']}) "
              f"-- space exceeds the {EXACT_LIMIT:,} exact limit")
        print(f"  p (two-sided): {res['p']:.6g}   [({res['hits']}+1)/({res['resamples']}+1)"
              f", floor {res['floor']:.6g}]")
    print("  S26f: the D0/D5 terminal-wave gap is EXPECTED and is NOT a finding.")
    print("        The deliverable is the matched, poolable pair.")

    print("\n" + "=" * 78)
    print("SECONDARY (S26d) -- offense at landmark vs terminal wave, EXPLORATORY")
    print("=" * 78)
    print("  offense = sum(weapon.damage) at the FIRST combat_capture of wave k,")
    print("  from the CAPTURE payload (not the save's weapons[i].stats).")
    print("  Exclusion count is printed BEFORE every rho.")
    contaminated = False
    for k in LANDMARKS:
        tag = "  [PRE-REGISTERED PRIMARY LANDMARK]" if k == PRIMARY_LANDMARK else ""
        print(f"\n  --- wave {k}{tag}")
        per_arm = {}
        for arm in ARMS:
            rows = arms[arm]
            inc = [r for r in rows if k in r["offense"]]
            exc = len(rows) - len(inc)
            assert len(inc) + exc == len(rows), "exclusion accounting broken"
            xs = [r["offense"][k] for r in inc]
            ys = [float(r["wave"]) for r in inc]
            rho = spearman(xs, ys) if len(inc) >= 2 else None
            per_arm[arm] = (xs, ys, rho)
            print(f"      {arm}: n_arm={len(rows)}  n_EXCLUDED={exc} "
                  f"(never reached wave {k})  n_included={len(inc)}")
            print(f"          rho = {'n/a' if rho is None else f'{rho:+.4f}'}")
            if k == PRIMARY_LANDMARK and exc > 0:
                contaminated = True
        if k == PRIMARY_LANDMARK and contaminated:
            print("      CONTAMINATED: wave 5 excludes runs in at least one arm.")
            print("      Per prereg S26d this is selection on the outcome; the wave-5")
            print("      result is NOT the verdict -- it falls to the sensitivity set.")
        xa, ya, ra = per_arm["D0"]
        xb, yb, rb = per_arm["D5"]
        cmp_res = perm_rho_diff(xa, ya, xb, yb) if (ra is not None and rb is not None) else None
        if cmp_res is None:
            print("      between-arm comparison: n/a (an arm has no usable rho)")
        else:
            print(f"      between-arm: D0 n={len(xa)} rho={cmp_res['rho_a']:+.4f} | "
                  f"D5 n={len(xb)} rho={cmp_res['rho_b']:+.4f} | "
                  f"diff={cmp_res['diff']:+.4f}")
            print(f"      permutation on arm labels: p={cmp_res['p']:.6g} "
                  f"({cmp_res['resamples']:,} resamples, seed {cmp_res['seed']}, "
                  f"floor {cmp_res['floor']:.6g})")

    print("\n" + "=" * 78)
    print("S26f -- pre-declared interpretation")
    print("=" * 78)
    print("  A S26d null does NOT establish that D5 failure is survival-limited")
    print("  rather than offense-limited. An observational correlation on a")
    print("  compressed, censored endpoint has low power and the landmark")
    print("  constraint biases it. That needs an INTERVENTION (e.g. enemy_scaling,")
    print("  readback = max_hp by type), not a correlation.")
    print("  Do NOT pool these runs with the 35 archived D5 runs: different build,")
    print("  different character, and no era stamp at all.")
    if not clean:
        print("\n  VALIDITY PROBLEMS ABOVE -- resolve before quoting any number.")
        return 3
    return 0


# ---------------------------------------------------------------- self-test

def _write_run(runs_dir: Path, rid: str, *, wave: int, result: str,
               danger: int, captures: list[tuple[int, list[float]]],
               char_ok: bool = True, danger_ok: bool = True,
               build: str = "0.2.73-wp2-capture") -> None:
    d = runs_dir / rid
    d.mkdir(parents=True, exist_ok=True)
    (d / "summary.json").write_text(json.dumps({
        "last_wave": wave, "result": result, "danger": danger,
        "danger_ok": danger_ok, "character_ok": char_ok,
        "requested_character": "character_mutant", "mod_version": build,
        "movement_estop_suppressed": 0, "weapon": "weapon_smg_1",
        "unlock_pool": {"items": 177, "weapons": 46, "items_hash": "2286319327"},
    }), encoding="utf-8")
    lines = [json.dumps({"event": "run_start", "payload": {"weapon": "weapon_smg_1"}})]
    for w, dmgs in captures:
        lines.append(json.dumps({"event": "combat_capture", "payload": {
            "wave": w, "weapons": [{"damage": x, "cooldown": 4} for x in dmgs]}}))
    (d / "events.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def self_test() -> int:
    fails = []

    def check(name: str, ok: bool, extra: str = "") -> None:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {extra}" if extra else ""))
        if not ok:
            fails.append(name)

    print("Validating the machinery on synthetic data before it decides anything.\n")

    # (a) Spearman against closed forms and a textbook case.
    mono = spearman([1, 2, 3, 4, 5], [10, 20, 30, 40, 50])
    rev = spearman([1, 2, 3, 4, 5], [50, 40, 30, 20, 10])
    check("(a1) perfectly monotonic rho = +1", abs(mono - 1.0) < 1e-12, f"rho={mono:+.6f}")
    check("(a2) perfectly reversed rho = -1", abs(rev + 1.0) < 1e-12, f"rho={rev:+.6f}")
    # Textbook: n=5, d = [-1,1,1,-1,0] -> sum d^2 = 4 -> rho = 1 - 6*4/(5*24) = 0.8
    tb = spearman([1, 2, 3, 4, 5], [2, 1, 2.5, 4.5, 5])
    # ranks y = [2,1,3,4,5]; d^2 = 1+1+0+0+0 = 2 -> rho = 1 - 12/120 = 0.9
    check("(a3) textbook case rho = 0.9 (1 - 6*sum(d^2)/(n(n^2-1)))",
          abs(tb - 0.9) < 1e-12, f"rho={tb:+.6f}")
    # ties: average ranks
    ties = spearman([1, 1, 2, 2], [1, 1, 2, 2])
    check("(a4) tied but perfectly concordant rho = +1", ties is not None and abs(ties - 1.0) < 1e-12,
          f"rho={ties:+.6f}" if ties is not None else "None")

    # (b) THE TEST CAN RETURN THE POSITIVE -- fully separated arms hit the floor.
    a = [20.0] * 8
    b = [6.0] * 8
    r_exact = perm_mean_diff(a, b)
    floor_exact = Fraction(2, comb(16, 8))
    check("(b1) EXACT: full separation returns the two-sided floor 2/C(16,8)",
          r_exact["mode"] == "exact" and r_exact["fraction"] == floor_exact,
          f"p={r_exact['p']:.6g} [{r_exact['fraction']}]")
    # The MC fallback only runs on NON-INTEGER data now (integers take the exact
    # subset-sum DP), so it must be exercised with non-integer values -- feeding
    # it integers would silently test the DP again and report the MC path as
    # covered when it never executed.
    a16 = [20.5] * 16
    b16 = [6.5] * 16
    r_mc = perm_mean_diff(a16, b16, exact_limit=1000, resamples=20000, seed=1)
    check("(b2) MONTE CARLO fallback (non-integer data): full separation returns the MC floor",
          r_mc["mode"] == "monte-carlo" and abs(r_mc["p"] - r_mc["floor"]) < 1e-12,
          f"p={r_mc['p']:.6g} floor={r_mc['floor']:.6g}")
    # And the integer path must NOT silently fall back to Monte Carlo at the
    # real design size -- the pre-registration (S26c) says EXACT.
    r_real = perm_mean_diff([20] * 16, [6] * 16)
    check("(b2b) integer data at the REAL design size stays EXACT (no MC fallback)",
          r_real["mode"] == "exact" and r_real["method"] == "subset-sum-dp"
          and r_real["fraction"] == Fraction(2, comb(32, 16)),
          f"mode={r_real['mode']} method={r_real.get('method')} p={r_real['p']:.6g}")
    # A near-separation with realistic spread must still be small.
    r_near = perm_mean_diff([float(x) for x in [15, 16, 17, 18, 19, 20, 20, 20]],
                            [float(x) for x in [6, 7, 8, 9, 10, 11, 11, 12]])
    check("(b3) realistic separated arms give a small p", r_near["p"] < 0.001,
          f"p={r_near['p']:.6g}")

    # (c) THE NULL BOTH WAYS.
    ident = [1.0, 2.0, 3.0, 4.0]
    r_id = perm_mean_diff(ident, list(ident))
    check("(c1) identical arms give p = 1.0", abs(r_id["p"] - 1.0) < 1e-12,
          f"p={r_id['p']:.6g}")
    x = [float(v) for v in [3, 5, 9, 11, 14, 2]]
    y = [float(v) for v in [7, 8, 1, 12, 4, 6]]
    p_fwd = perm_mean_diff(x, y)
    p_rev = perm_mean_diff(y, x)
    check("(c2) two-sided symmetry: swapping the arms gives the same p",
          p_fwd["mode"] == "exact" and p_fwd["fraction"] == p_rev["fraction"],
          f"{p_fwd['p']:.6g} vs {p_rev['p']:.6g}")
    r_id_mc = perm_mean_diff([5.0] * 16, [5.0] * 16, exact_limit=1000,
                             resamples=5000, seed=3)
    check("(c3) MC null: identical arms give p = 1.0",
          abs(r_id_mc["p"] - 1.0) < 1e-12, f"p={r_id_mc['p']:.6g}")

    tmp = Path(tempfile.mkdtemp(prefix="d0d5_selftest_"))
    runs = tmp / "runs"
    runs.mkdir(parents=True)

    # (f) FIRST capture of the wave wins, not the last.
    _write_run(runs, "run_first", wave=9, result="defeat", danger=0,
               captures=[(5, [3.0, 4.0]), (5, [100.0, 100.0]), (6, [50.0])])
    off = offense_by_landmark(runs / "run_first" / "events.jsonl", LANDMARKS)
    check("(f) offense takes the FIRST capture of the wave (7.0, not 200.0)",
          off.get(5) == 7.0 and off.get(6) == 50.0, f"wave5={off.get(5)} wave6={off.get(6)}")

    # (d) Exclusion accounting.
    root = tmp / "root"
    (root / ".tmp" / ARM_DIR["D0"]).mkdir(parents=True)
    (root / ".tmp" / ARM_DIR["D5"]).mkdir(parents=True)
    d0_ids, d5_ids = [], []
    for i in range(MIN_PER_ARM):
        rid = f"run_d0_{i}"
        w = 12 + (i % 9)
        _write_run(runs, rid, wave=w, result="victory" if w >= 20 else "defeat",
                   danger=0, captures=[(k, [2.0 + i, 3.0]) for k in LANDMARKS if k <= w])
        d0_ids.append(rid)
    for i in range(MIN_PER_ARM):
        rid = f"run_d5_{i}"
        w = 3 + (i % 8)  # some runs die before wave 5 -> real exclusions
        _write_run(runs, rid, wave=w, result="defeat", danger=5,
                   captures=[(k, [1.0 + i, 2.0]) for k in LANDMARKS if k <= w])
        d5_ids.append(rid)
    (root / ".tmp" / ARM_DIR["D0"] / "state.json").write_text(
        json.dumps({"collected_run_ids": d0_ids}), encoding="utf-8")
    (root / ".tmp" / ARM_DIR["D5"] / "state.json").write_text(
        json.dumps({"collected_run_ids": d5_ids}), encoding="utf-8")

    rows_d5, _ = load_arm(root, runs, "D5")
    inc = [r for r in rows_d5 if 5 in r["offense"]]
    exc = [r for r in rows_d5 if 5 not in r["offense"]]
    expect_exc = sum(1 for r in rows_d5 if int(r["wave"]) < 5)
    check("(d) exclusion accounting: n_included + n_excluded == n_arm, and the "
          "excluded runs are exactly those that died before wave 5",
          len(inc) + len(exc) == len(rows_d5) and len(exc) == expect_exc and expect_exc > 0,
          f"n={len(rows_d5)} inc={len(inc)} exc={len(exc)} expected_exc={expect_exc}")

    # (e) The refusal gate fires -- as a real process exit code.
    short_root = tmp / "shortroot"
    for arm in ARMS:
        (short_root / ".tmp" / ARM_DIR[arm]).mkdir(parents=True)
        (short_root / ".tmp" / ARM_DIR[arm] / "state.json").write_text(
            json.dumps({"collected_run_ids": d0_ids[:3]}), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()),
         "--root", str(short_root), "--runs-dir", str(runs)],
        capture_output=True, text=True)
    check("(e) refusal gate: fewer than 16 runs per arm exits 2",
          proc.returncode == 2 and "REFUSING TO RUN" in proc.stdout,
          f"exit={proc.returncode}")

    # End-to-end smoke: the full analysis runs on the synthetic pair.
    proc2 = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()),
         "--root", str(root), "--runs-dir", str(runs)],
        capture_output=True, text=True)
    check("(g) end-to-end on a synthetic 16/16 pair exits 0 and prints validity "
          "before the primary",
          proc2.returncode == 0
          and proc2.stdout.index("VALIDITY") < proc2.stdout.index("PRIMARY")
          and proc2.stdout.index("PRIMARY") < proc2.stdout.index("SECONDARY"),
          f"exit={proc2.returncode}")
    check("(g2) all printed output is ASCII-safe",
          all(ord(c) < 128 for c in proc2.stdout))
    if proc2.returncode != 0:
        print(proc2.stdout[-2000:])
        print(proc2.stderr[-2000:])

    print()
    if fails:
        print(f"SELF-TEST FAILED: {len(fails)} check(s) -- {fails}")
        return 1
    print("All self-tests passed.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--runs-dir", default=None)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    root = Path(args.root).resolve()
    runs_dir = Path(args.runs_dir) if args.runs_dir else Path(
        os.path.expandvars(r"%APPDATA%\Brotato\brotato_agent\runs"))
    return analyse(root, runs_dir)


if __name__ == "__main__":
    raise SystemExit(main())
