#!/usr/bin/env python
"""Analysis for the §28 D5 scaling intervention campaign.

Pre-registration: reports/wp2/d5_scaling_intervention_prereg.md
Binding sections: §28e (endpoint/analysis), §28f (validity), §28g (stopping
rule / limits), §28i (corrections recorded 2026-08-03).

WHAT THIS SCRIPT IS ALLOWED TO DO, and in what order:

  1. §28i(ii) CENSORING RECOVERY. A row whose ``invalid_reason`` matches
     ``^timeout_`` is a CENSORED OBSERVATION, not an invalid trial. The driver
     skips its enrichment block on the timeout path, so the row arrives with
     ``valid=False, waves=[], last_wave=None``. We re-open that ``run_id``'s
     ``events.jsonl`` and recompute the wave series; censored terminal wave is
     ``max(waves)``. ``telemetry_stale_*`` and ``game_exited_before_summary``
     stay INVALID. A ``^timeout_`` row with a blank ``run_id`` is invalid and
     unrecoverable, and is reported separately.

  2. §28f(b)/§28g COUNTS BEFORE ANY OUTCOME. Per-arm n / valid / censored /
     invalid-by-reason / at-wave-20, printed before a single outcome statistic,
     followed by the §28g ceiling rule.

  3. §28i(i) DUAL PERMUTATION TEST. §28d and §28e contradict each other on
     paired vs unpaired. Both are computed with EQUAL STANDING, two-sided,
     alpha = 0.05, and printed side by side. Disagreement at alpha is itself a
     reported result: that arm is FRAGILE TO THE PAIRING CHOICE and is not
     reported as a significant finding.

  4. §28f(c) THE STATISTIC IS VERIFIED BEFORE IT DECIDES ANYTHING, in BOTH
     directions, against closed forms (``--self-test``). This project once
     shipped a hand-rolled Fisher exact that summed the wrong tail and whose
     positive branch was unreachable regardless of data.

  §28g STOPPING RULE, ENFORCED IN CODE: no outcome statistic is printed until
  the ladder holds the full pre-registered n. ``--allow-partial`` overrides,
  loudly, and is not a licensed analysis path.

Nothing runs on import (a verification script on this project once imported an
analysis module, executed it, and printed a verdict off a partially-written
file).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from collections import Counter
from itertools import combinations, product
from pathlib import Path
from typing import Any, Iterable, Sequence

ARMS = ("control", "H75", "H50", "D75", "D50")
TREATMENT_ARMS = ("H75", "H50", "D75", "D50")
CONTROL = "control"
ALPHA = 0.05
TARGET_WAVE_CEILING = 20
EXPECTED_TRIALS = 40

TIMEOUT_RE = re.compile(r"^timeout_")
FIXTURE_RE = re.compile(r"^(f\d+)_(control|H75|H50|D75|D50)\.json$")

# Exhaustive enumeration limits. Above these we fall back to Monte Carlo with a
# fixed seed and say so in the output. The pre-registered design (8 pairs;
# 8 v 8 unpaired) is far below both, so the real campaign is always EXACT.
MAX_EXACT_SIGNFLIP = 22          # 2**22
MAX_EXACT_UNPAIRED = 500_000     # C(n+m, n)
MC_RESAMPLES = 200_000
MC_SEED = 20260803


# ---------------------------------------------------------------------------
# events analysis -- REPLICATED from scripts/wp2_finale_loop.analyse_events
# ---------------------------------------------------------------------------
# Replicated rather than imported: wp2_finale_loop mutates sys.path at import
# and drags in the launcher module (subprocess, game control). Nothing there
# executes on import today, but an analysis pass must not depend on that
# staying true. `--self-test` asserts this copy is byte-identical in OUTPUT to
# the driver's own function on a synthetic events file, so the replication is
# checked rather than assumed.


def _boss_entity_from_path(script_path: Any) -> str:
    if not isinstance(script_path, str):
        return str(script_path)
    parts = [p for p in script_path.split("/") if p]
    if len(parts) >= 2 and parts[-1].endswith(".gd"):
        return parts[-2]
    return script_path


def analyse_events(events_path: Path) -> dict[str, Any]:
    """Waves / capture count / boss script paths from a run's events.jsonl."""
    waves: set[int] = set()
    n_captures = 0
    boss_paths: Counter[str] = Counter()
    try:
        handle = events_path.open("r", encoding="utf-8", errors="replace")
    except OSError:
        handle = None
    if handle is None:
        return {
            "waves": [], "n_captures": 0, "boss_paths": {},
            "boss_entity": "", "boss_capture_count": 0,
        }
    with handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("event") != "combat_capture":
                continue
            payload = event.get("payload") or {}
            n_captures += 1
            wave = payload.get("wave")
            if isinstance(wave, int):
                waves.add(wave)
            bosses = (payload.get("entities") or {}).get("bosses") or []
            for boss in bosses:
                if isinstance(boss, dict):
                    boss_paths[str(boss.get("script_path"))] += 1
    entities = sorted({_boss_entity_from_path(p) for p in boss_paths})
    return {
        "waves": sorted(waves),
        "n_captures": n_captures,
        "boss_paths": dict(boss_paths),
        "boss_entity": entities[0] if len(entities) == 1 else (";".join(entities) if entities else ""),
        "boss_capture_count": int(sum(boss_paths.values())),
    }


# ---------------------------------------------------------------------------
# permutation tests
# ---------------------------------------------------------------------------


def signflip_permutation_p(diffs: Sequence[float]) -> dict[str, Any]:
    """Two-sided exact sign-flip permutation on paired differences.

    Statistic: the mean of the differences. Under the null of exchangeability
    of sign, each of the 2**n sign assignments is equally likely. p is the
    proportion of assignments whose |statistic| is >= the observed |statistic|.

    The OBSERVED assignment is included in the count, so p is never 0 and the
    floor is 2 / 2**n (all-plus and all-minus), reached exactly when every
    difference shares a sign. That floor is a closed form and is asserted in
    the self-tests.
    """
    d = [float(x) for x in diffs]
    n = len(d)
    if n == 0:
        return {"p": float("nan"), "stat": float("nan"), "n": 0, "method": "empty"}
    obs = sum(d) / n
    target = abs(obs)
    tol = 1e-12
    if n <= MAX_EXACT_SIGNFLIP:
        hits = 0
        total = 0
        for signs in product((1.0, -1.0), repeat=n):
            total += 1
            stat = sum(s * v for s, v in zip(signs, d)) / n
            if abs(stat) >= target - tol:
                hits += 1
        return {"p": hits / total, "stat": obs, "n": n, "method": f"exact ({total} sign assignments)"}
    rng = _rng(MC_SEED)
    hits = 1
    for _ in range(MC_RESAMPLES):
        stat = sum((1.0 if rng() < 0.5 else -1.0) * v for v in d) / n
        if abs(stat) >= target - tol:
            hits += 1
    return {
        "p": hits / (MC_RESAMPLES + 1),
        "stat": obs,
        "n": n,
        "method": f"monte-carlo ({MC_RESAMPLES} resamples, seed {MC_SEED})",
    }


def unpaired_permutation_p(arm: Sequence[float], control: Sequence[float]) -> dict[str, Any]:
    """Two-sided permutation on the unpaired difference of means.

    Statistic: mean(arm) - mean(control). Under the null of exchangeability of
    labels, every way of splitting the pooled values into groups of size
    len(arm) and len(control) is equally likely. Exhaustive over C(n+m, n)
    splits when that is tractable.

    The observed split is one of the enumerated splits, so p is never 0. With
    complete separation and distinct values the floor is 2 / C(n+m, n) --
    a closed form, asserted in the self-tests.
    """
    a = [float(x) for x in arm]
    c = [float(x) for x in control]
    n, m = len(a), len(c)
    if n == 0 or m == 0:
        return {"p": float("nan"), "stat": float("nan"), "n": n, "m": m, "method": "empty"}
    pooled = a + c
    obs = sum(a) / n - sum(c) / m
    target = abs(obs)
    tol = 1e-12
    total_splits = math.comb(n + m, n)
    if total_splits <= MAX_EXACT_UNPAIRED:
        hits = 0
        total = 0
        idx = range(n + m)
        grand = sum(pooled)
        for pick in combinations(idx, n):
            total += 1
            s = sum(pooled[i] for i in pick)
            stat = s / n - (grand - s) / m
            if abs(stat) >= target - tol:
                hits += 1
        return {
            "p": hits / total, "stat": obs, "n": n, "m": m,
            "method": f"exact ({total} label splits)",
        }
    rng = _rng(MC_SEED)
    hits = 1
    grand = sum(pooled)
    for _ in range(MC_RESAMPLES):
        shuffled = _shuffled(pooled, rng)
        s = sum(shuffled[:n])
        stat = s / n - (grand - s) / m
        if abs(stat) >= target - tol:
            hits += 1
    return {
        "p": hits / (MC_RESAMPLES + 1), "stat": obs, "n": n, "m": m,
        "method": f"monte-carlo ({MC_RESAMPLES} resamples, seed {MC_SEED})",
    }


def _rng(seed: int):
    import random

    r = random.Random(seed)
    return r.random


def _shuffled(values: Sequence[float], rand) -> list[float]:
    out = list(values)
    for i in range(len(out) - 1, 0, -1):
        j = int(rand() * (i + 1))
        out[i], out[j] = out[j], out[i]
    return out


# ---------------------------------------------------------------------------
# ladder loading + §28i(ii) censoring recovery
# ---------------------------------------------------------------------------


class Trial:
    __slots__ = ("row", "fixture", "arm", "status", "reason", "terminal_wave", "waves", "recovery_note")

    def __init__(self, row: dict[str, Any]) -> None:
        self.row = row
        fixture_file = str(row.get("fixture_file") or "")
        match = FIXTURE_RE.match(fixture_file)
        self.fixture = match.group(1) if match else ""
        self.arm = match.group(2) if match else ""
        self.status = "unclassified"       # valid | censored | invalid | unrecoverable
        self.reason = str(row.get("invalid_reason") or "")
        self.terminal_wave: int | None = None
        self.waves: list[int] = list(row.get("waves") or [])
        self.recovery_note = ""

    @property
    def run_id(self) -> str:
        return str(self.row.get("run_id") or "").strip()


def load_ladder(path: Path) -> list[Trial]:
    trials: list[Trial] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            trials.append(Trial(json.loads(line)))
    return trials


def classify_and_recover(trials: Iterable[Trial], runs_dir: Path) -> None:
    """§28i(ii). Mutates each trial in place. Must run BEFORE any outcome."""
    for t in trials:
        if t.row.get("valid") is True:
            t.status = "valid"
            waves = [w for w in t.waves if isinstance(w, int)]
            t.terminal_wave = max(waves) if waves else t.row.get("last_wave")
            if t.terminal_wave is None:
                # A row flagged valid with no wave series is a contradiction, not
                # an outcome. Refuse to guess.
                t.status = "invalid"
                t.reason = "valid_row_without_wave_series"
            continue
        if TIMEOUT_RE.match(t.reason):
            if not t.run_id:
                t.status = "unrecoverable"
                t.recovery_note = "timeout row with blank run_id -- game never started"
                continue
            events = runs_dir / t.run_id / "events.jsonl"
            analysis = analyse_events(events)
            waves = [w for w in analysis["waves"] if isinstance(w, int)]
            if not waves:
                t.status = "unrecoverable"
                t.recovery_note = f"timeout row, no waves recoverable from {events}"
                continue
            t.status = "censored"
            t.waves = waves
            t.terminal_wave = max(waves)
            t.recovery_note = (
                f"recovered from {events.name}: waves {waves[0]}..{waves[-1]}, "
                f"{analysis['n_captures']} captures"
            )
            continue
        # telemetry_stale_* and game_exited_before_summary remain genuinely
        # invalid: the game stopped writing or died. That is a technical
        # failure, not an outcome. A timeout means the run was still GOING.
        t.status = "invalid"


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------


def per_arm(trials: Sequence[Trial]) -> dict[str, list[Trial]]:
    out: dict[str, list[Trial]] = {a: [] for a in ARMS}
    for t in trials:
        if t.arm in out:
            out[t.arm].append(t)
    return out


def usable(trials: Sequence[Trial]) -> list[Trial]:
    """Trials contributing an outcome: valid + censored (censored = FLOOR)."""
    return [t for t in trials if t.status in ("valid", "censored")]


def print_counts(groups: dict[str, list[Trial]], trials: Sequence[Trial],
                 mask_outcome_counts: bool = False) -> dict[str, bool]:
    """§28f(b)/§28g: counts BEFORE any outcome statistic. Returns ceiling flags.

    ``mask_outcome_counts`` withholds the wave-20 column and the ceiling rule on
    an INCOMPLETE campaign. The validity counts (valid / censored / invalid) are
    technical and §28f(b) wants them early; the wave-20 count is derived from the
    OUTCOME and §28g forbids looking at it mid-campaign.
    """
    print("=" * 78)
    print("§28f(b)/§28g  COUNTS FIRST -- reported before any outcome statistic")
    print("=" * 78)
    unknown = [t for t in trials if t.arm not in ARMS]
    if unknown:
        print(f"!! {len(unknown)} row(s) with unparseable fixture_file -- EXCLUDED, listed below")
        for t in unknown:
            print(f"     fixture_file={t.row.get('fixture_file')!r} run_id={t.run_id!r}")
    hdr = f"{'arm':<8}{'n':>4}{'valid':>7}{'censored':>10}{'invalid':>9}{'unrecov':>9}{'@w20':>6}"
    print(hdr)
    print("-" * len(hdr))
    ceiling: dict[str, bool] = {}
    for arm in ARMS:
        rows = groups[arm]
        n_valid = sum(1 for t in rows if t.status == "valid")
        n_cens = sum(1 for t in rows if t.status == "censored")
        n_inv = sum(1 for t in rows if t.status == "invalid")
        n_unrec = sum(1 for t in rows if t.status == "unrecoverable")
        n_w20 = sum(1 for t in rows if t.terminal_wave is not None and t.terminal_wave >= TARGET_WAVE_CEILING)
        w20_cell = "--" if mask_outcome_counts else str(n_w20)
        print(f"{arm:<8}{len(rows):>4}{n_valid:>7}{n_cens:>10}{n_inv:>9}{n_unrec:>9}{w20_cell:>6}")
        ceiling[arm] = bool(rows) and (n_w20 / len(rows)) >= 0.5
    print()
    print("invalid reasons (excluded from all outcome statistics):")
    reasons = Counter(t.reason or "(blank)" for t in trials if t.status in ("invalid", "unrecoverable"))
    if not reasons:
        print("  none")
    for reason, count in sorted(reasons.items()):
        print(f"  {count:>3}  {reason}")
    notes = [t for t in trials if t.recovery_note]
    print()
    print(f"§28i(ii) censoring recovery: {sum(1 for t in trials if t.status == 'censored')} recovered, "
          f"{sum(1 for t in trials if t.status == 'unrecoverable')} unrecoverable")
    for t in notes:
        print(f"  [{t.status:<13}] {t.arm:<8} {t.fixture:<5} {t.run_id:<22} {t.recovery_note}")
    print()
    if mask_outcome_counts:
        print("@w20 column and the §28g ceiling rule are WITHHELD: the campaign is")
        print("incomplete and the wave-20 count is an OUTCOME. §28g forbids the look.")
        print()
        return ceiling
    print("§28g CEILING RULE (>=50% of an arm's trials at wave 20 -> effect is a BOUND):")
    any_ceiling = False
    for arm in ARMS:
        if ceiling[arm]:
            any_ceiling = True
            print(f"  !! {arm}: CEILINGED. Terminal wave is a FLOOR for this arm. Its effect is "
                  f"reported as a BOUND, not a point estimate.")
    if not any_ceiling:
        print("  no arm is ceilinged; effects may be reported as point estimates")
    print()
    return ceiling


def print_series(groups: dict[str, list[Trial]]) -> None:
    """§28e: the raw per-fixture series, printed per arm."""
    print("=" * 78)
    print("§28e  RAW PER-FIXTURE SERIES (censored values marked '+' = FLOOR)")
    print("=" * 78)
    fixtures = sorted({t.fixture for rows in groups.values() for t in rows if t.fixture})
    hdr = f"{'arm':<8}" + "".join(f"{f:>8}" for f in fixtures)
    print(hdr)
    print("-" * len(hdr))
    for arm in ARMS:
        by_fix = {t.fixture: t for t in groups[arm]}
        cells = []
        for f in fixtures:
            t = by_fix.get(f)
            if t is None:
                cells.append("--")
            elif t.status == "valid":
                cells.append(str(t.terminal_wave))
            elif t.status == "censored":
                cells.append(f"{t.terminal_wave}+")
            else:
                cells.append(f"X:{t.status[:3]}")
        print(f"{arm:<8}" + "".join(f"{c:>8}" for c in cells))
    print()


def print_tests(groups: dict[str, list[Trial]], ceiling: dict[str, bool]) -> None:
    print("=" * 78)
    print("§28i(i)  DUAL PERMUTATION TEST -- paired and unpaired, EQUAL STANDING")
    print("=" * 78)
    print("§28d says unpaired, §28e says paired. Both are pre-registered and they")
    print("contradict. Neither is privileged. Two-sided, alpha = 0.05.")
    print()
    print("CENSORING HANDLING, stated explicitly (§28i(ii)4): a censored observation")
    print("enters BOTH tests at its recovered max(waves), i.e. at its FLOOR. This is")
    print("CONSERVATIVE for an arm that censors (its true terminal wave is >= the value")
    print("used, so a rescuing arm's effect is UNDER-stated, never over-stated) and")
    print("ANTI-conservative in the opposite direction only if the CONTROL censors.")
    print("Censored counts per arm are in the counts table above; read them first.")
    print("No survival model is fitted -- the prereg licenses no such analysis.")
    print()

    ctrl_rows = usable(groups[CONTROL])
    ctrl_by_fix = {t.fixture: t for t in ctrl_rows}
    ctrl_vals = [float(t.terminal_wave) for t in ctrl_rows]

    hdr = (f"{'arm':<8}{'n_pair':>7}{'mean_d':>9}{'p_paired':>11}"
           f"{'n_arm':>7}{'mean_diff':>11}{'p_unpaired':>12}  verdict")
    print(hdr)
    print("-" * len(hdr))
    verdicts: list[str] = []
    for arm in TREATMENT_ARMS:
        rows = usable(groups[arm])
        arm_vals = [float(t.terminal_wave) for t in rows]
        diffs = [
            float(t.terminal_wave) - float(ctrl_by_fix[t.fixture].terminal_wave)
            for t in rows
            if t.fixture in ctrl_by_fix
        ]
        paired = signflip_permutation_p(diffs)
        unpaired = unpaired_permutation_p(arm_vals, ctrl_vals)
        sig_p = paired["p"] == paired["p"] and paired["p"] < ALPHA
        sig_u = unpaired["p"] == unpaired["p"] and unpaired["p"] < ALPHA
        if not diffs or not arm_vals or not ctrl_vals:
            verdict = "INSUFFICIENT DATA"
        elif sig_p != sig_u:
            verdict = "FRAGILE TO PAIRING CHOICE -- not a significant finding"
        elif sig_p:
            verdict = "significant (both forms)" + (" -- BOUND ONLY (§28g ceiling)" if ceiling[arm] else "")
        else:
            verdict = "not significant (both forms)"
        verdicts.append(f"{arm}: {verdict}")
        print(f"{arm:<8}{paired['n']:>7}{paired['stat']:>9.3f}{paired['p']:>11.5f}"
              f"{unpaired['n']:>7}{unpaired['stat']:>11.3f}{unpaired['p']:>12.5f}  {verdict}")
        print(f"{'':<8}paired: {paired['method']}   unpaired: {unpaired['method']}")
    print()
    print("VERDICTS")
    for v in verdicts:
        print(f"  {v}")
    print()
    print("§28c inference table is FIXED and is not re-read here. §28g: the dials are")
    print("NOT unit-commensurable -- only qualitative (flat vs steep) comparisons are")
    print("licensed. No 'clearance matters Nx more than survival' claim is permitted.")
    print()


# ---------------------------------------------------------------------------
# §28f(c) SELF-TESTS -- the statistic is verified before it decides anything
# ---------------------------------------------------------------------------


def _approx(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) <= tol


def self_test() -> int:
    """Verify the permutation implementations against closed forms, BOTH ways.

    A p-value that is small when it should be large is as broken as the
    reverse, so every closed-form case is asserted as an EQUALITY, and the
    null / large-effect pair is asserted in both directions.
    """
    failures: list[str] = []

    def check(name: str, got: float, want: float, tol: float = 1e-9) -> None:
        ok = _approx(got, want, tol)
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: got {got!r}, expected {want!r}")
        if not ok:
            failures.append(name)

    def check_cmp(name: str, got: float, op: str, bound: float) -> None:
        ok = (got < bound) if op == "<" else (got > bound)
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: got {got!r}, required {op} {bound}")
        if not ok:
            failures.append(name)

    print("=" * 78)
    print("§28f(c) SELF-TESTS -- closed-form verification of the test statistic")
    print("=" * 78)

    print("\nA. sign-flip permutation, hand-enumerable cases")
    # d = [1, 2]: 4 assignments, means 1.5, -0.5, 0.5, -1.5.
    # |stat| >= 1.5 for exactly 2 of 4  ->  p = 0.5
    check("A1 d=[1,2] (2/4 by hand)", signflip_permutation_p([1, 2])["p"], 0.5)
    # d = [1, 2, 3]: sums +-1+-2+-3 = 6,4,2,0,0,-2,-4,-6.
    # |sum| >= 6 for exactly 2 of 8  ->  p = 0.25
    check("A2 d=[1,2,3] (2/8 by hand)", signflip_permutation_p([1, 2, 3])["p"], 0.25)
    # d = [1, 2, 3, 4]: |sum| >= 10 only for all-plus and all-minus -> 2/16
    check("A3 d=[1,2,3,4] (2/16 by hand)", signflip_permutation_p([1, 2, 3, 4])["p"], 2 / 16)
    # d = [3, -1]: means 1.0, 2.0, -2.0, -1.0. |stat| >= 1.0 for 4 of 4 -> p = 1
    check("A4 d=[3,-1] (4/4 by hand)", signflip_permutation_p([3, -1])["p"], 1.0)

    print("\nB. sign-flip closed form: all differences same sign -> p = 2 / 2**n")
    for n in (5, 6, 8):
        check(f"B{n} d=[1..{n}] all-positive", signflip_permutation_p(list(range(1, n + 1)))["p"], 2 / 2 ** n)
    # ... and the SAME magnitude with a flipped sign must give the SAME p.
    check("B-sign-symmetry d=[-1..-8]",
          signflip_permutation_p([-x for x in range(1, 9)])["p"],
          signflip_permutation_p(list(range(1, 9)))["p"])

    print("\nC. sign-flip BOTH DIRECTIONS -- large effect small p, null large p")
    big = [4, 5, 4, 6, 5, 4, 5, 6]        # every pair rescued by ~5 waves
    check("C1 large paired effect == 2/256", signflip_permutation_p(big)["p"], 2 / 256)
    check_cmp("C2 large paired effect is SIGNIFICANT", signflip_permutation_p(big)["p"], "<", ALPHA)
    null = [0, 0, 0, 0, 0, 0, 0, 0]
    check("C3 all-zero differences -> p = 1", signflip_permutation_p(null)["p"], 1.0)
    noisy = [1, -1, 2, -2, 0, 1, -1, 0]   # mean 0, no effect
    check_cmp("C4 zero-mean noise is NOT significant", signflip_permutation_p(noisy)["p"], ">", ALPHA)
    tiny = [1, -1, 1, -1, 1, -1, 1, 2]    # mean 0.375, small vs spread
    check_cmp("C5 small effect is NOT significant", signflip_permutation_p(tiny)["p"], ">", ALPHA)

    print("\nD. unpaired permutation, closed form 2 / C(n+m, n) under full separation")
    # arm strictly above control with distinct values: only the observed split
    # and its mirror reach |stat| >= observed.
    check("D1 3 v 3 fully separated == 2/20",
          unpaired_permutation_p([10, 11, 12], [1, 2, 3])["p"], 2 / math.comb(6, 3))
    check("D2 4 v 4 fully separated == 2/70",
          unpaired_permutation_p([20, 21, 22, 23], [1, 2, 3, 4])["p"], 2 / math.comb(8, 4))
    check("D3 8 v 8 fully separated == 2/12870",
          unpaired_permutation_p(list(range(20, 28)), list(range(1, 9)))["p"], 2 / math.comb(16, 8))
    check("D4 label symmetry (arm/control swapped)",
          unpaired_permutation_p([1, 2, 3], [10, 11, 12])["p"],
          unpaired_permutation_p([10, 11, 12], [1, 2, 3])["p"])

    print("\nE. unpaired BOTH DIRECTIONS -- and identical groups must give p = 1")
    check("E1 identical groups -> p = 1",
          unpaired_permutation_p([11, 12, 13, 11], [11, 12, 13, 11])["p"], 1.0)
    check_cmp("E2 8 v 8 fully separated is SIGNIFICANT",
              unpaired_permutation_p(list(range(20, 28)), list(range(1, 9)))["p"], "<", ALPHA)
    check_cmp("E3 overlapping groups are NOT significant",
              unpaired_permutation_p([10, 11, 12, 13, 9, 11, 12, 10],
                                     [11, 10, 13, 12, 10, 12, 11, 9])["p"], ">", ALPHA)
    # 2 v 2 CANNOT reach alpha = 0.05: floor is 2/C(4,2) = 1/3. A test that
    # returns significance here would be returning a positive it cannot have.
    check("E4 2v2 floor is 1/3, unreachable at alpha",
          unpaired_permutation_p([50, 51], [1, 2])["p"], 2 / math.comb(4, 2))

    print("\nF. independent brute-force reimplementation must agree exactly")
    def brute_unpaired(a: list[float], c: list[float]) -> float:
        pooled = a + c
        n = len(a)
        obs = sum(a) / len(a) - sum(c) / len(c)
        hits = tot = 0
        for pick in combinations(range(len(pooled)), n):
            rest = [pooled[i] for i in range(len(pooled)) if i not in set(pick)]
            grp = [pooled[i] for i in pick]
            stat = sum(grp) / len(grp) - sum(rest) / len(rest)
            tot += 1
            if abs(stat) >= abs(obs) - 1e-12:
                hits += 1
        return hits / tot

    for a, c in ([[12, 9, 14, 11], [8, 10, 9, 7]], [[11, 11, 12], [11, 12, 20]]):
        check(f"F {a} vs {c}", unpaired_permutation_p(a, c)["p"], brute_unpaired(a, c))

    def brute_signflip(d: list[float]) -> float:
        obs = sum(d) / len(d)
        hits = tot = 0
        for signs in product((1, -1), repeat=len(d)):
            tot += 1
            if abs(sum(s * v for s, v in zip(signs, d)) / len(d)) >= abs(obs) - 1e-12:
                hits += 1
        return hits / tot

    for d in ([2, -1, 3, 0, 1], [1, 1, 1, -5]):
        check(f"F signflip {d}", signflip_permutation_p(d)["p"], brute_signflip(d))

    print("\nG. analyse_events replication vs the driver's own function")
    print(f"  {_test_analyse_events(failures)}")

    print("\nH. end-to-end on SYNTHETIC data (no real campaign rows touched)")
    _test_pipeline(check, check_cmp)

    print()
    if failures:
        print(f"SELF-TEST FAILED: {len(failures)} check(s): {failures}")
        return 1
    print("SELF-TEST PASSED: every closed form matched, in both directions.")
    return 0


def _test_analyse_events(failures: list[str]) -> str:
    import tempfile

    rows = [
        {"event": "combat_capture", "payload": {"wave": 2, "entities": {"bosses": []}}},
        {"event": "combat_capture", "payload": {"wave": 3, "entities": {
            "bosses": [{"script_path": "res://entities/units/enemies/monk/monk.gd"}]}}},
        {"event": "other", "payload": {"wave": 99}},
        {"event": "combat_capture", "payload": {"wave": 3}},
        {"event": "combat_capture", "payload": {"wave": 7, "entities": {
            "bosses": [{"script_path": "res://entities/units/enemies/monk/monk.gd"}]}}},
        "{not json",
    ]
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "events.jsonl"
        with p.open("w", encoding="utf-8") as fh:
            for r in rows:
                fh.write((r if isinstance(r, str) else json.dumps(r)) + "\n")
        mine = analyse_events(p)
        if mine["waves"] != [2, 3, 7] or mine["n_captures"] != 4 or mine["boss_entity"] != "monk":
            failures.append("analyse_events hand-check")
            return f"[FAIL] hand-check: {mine}"
        try:
            import importlib
            import sys

            repo_root = str(Path(__file__).resolve().parents[1])
            if repo_root not in sys.path:
                sys.path.insert(0, repo_root)
            driver = importlib.import_module("scripts.wp2_finale_loop")
            theirs = driver.analyse_events(p)
        except Exception as exc:  # noqa: BLE001
            return f"[PASS] hand-check ok ({mine['waves']}); driver import unavailable ({exc.__class__.__name__}), equivalence NOT checked"
        if theirs != mine:
            failures.append("analyse_events equivalence")
            return f"[FAIL] equivalence: mine={mine} theirs={theirs}"
        return f"[PASS] hand-check ok and OUTPUT-IDENTICAL to wp2_finale_loop.analyse_events ({mine['waves']})"


def _test_pipeline(check, check_cmp) -> None:
    """Classification + recovery on synthetic rows, incl. every reason class."""
    import tempfile

    def row(fx: str, arm: str, **kw: Any) -> dict[str, Any]:
        base = {
            "fixture_file": f"{fx}_{arm}.json", "run_id": "", "result": "defeat",
            "last_wave": None, "waves": [], "valid": False, "invalid_reason": "",
            "n_captures": 0, "trial_wall_sec": 0.0,
        }
        base.update(kw)
        return base

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        runs = root / "runs"
        (runs / "run_censored_1").mkdir(parents=True)
        with (runs / "run_censored_1" / "events.jsonl").open("w", encoding="utf-8") as fh:
            for w in range(2, 19):
                fh.write(json.dumps({"event": "combat_capture", "payload": {"wave": w}}) + "\n")
        rows = [
            row("f01", "control", valid=True, waves=[2, 3, 4], last_wave=4),
            row("f01", "H50", invalid_reason="timeout_2400s", run_id="run_censored_1"),
            row("f02", "control", invalid_reason="telemetry_stale_60s"),
            row("f02", "H50", invalid_reason="timeout_2400s", run_id=""),
            row("f03", "control", invalid_reason="game_exited_before_summary"),
            row("f03", "D75", valid=True, waves=[2, 3], last_wave=3),
        ]
        ladder = root / "ladder.jsonl"
        with ladder.open("w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        trials = load_ladder(ladder)
        classify_and_recover(trials, runs)
        statuses = [t.status for t in trials]
        check("H1 statuses", float(statuses == [
            "valid", "censored", "invalid", "unrecoverable", "invalid", "valid"]), 1.0)
        check("H2 censored terminal wave = max(waves) = 18", float(trials[1].terminal_wave), 18.0)
        check("H3 telemetry_stale stays invalid", float(trials[2].status == "invalid"), 1.0)
        check("H4 blank run_id timeout is unrecoverable", float(trials[3].status == "unrecoverable"), 1.0)
        check("H5 game_exited stays invalid", float(trials[4].status == "invalid"), 1.0)
        check("H6 arm parsed from suffix", float(trials[1].arm == "H50" and trials[1].fixture == "f01"), 1.0)

    # ceiling rule, on synthetic arms
    fake = [Trial({"fixture_file": f"f0{i}_H50.json"}) for i in range(1, 5)]
    for t, w in zip(fake, [20, 20, 20, 12]):
        t.status, t.terminal_wave = "valid", w
    n_w20 = sum(1 for t in fake if t.terminal_wave >= TARGET_WAVE_CEILING)
    check("H7 ceiling rule fires at 3/4 >= 50%", float(n_w20 / len(fake) >= 0.5), 1.0)
    fake2 = list(fake)
    for t, w in zip(fake2, [20, 12, 12, 12]):
        t.terminal_wave = w
    n2 = sum(1 for t in fake2 if t.terminal_wave >= TARGET_WAVE_CEILING)
    check("H8 ceiling rule does NOT fire at 1/4", float(n2 / len(fake2) >= 0.5), 0.0)

    # a synthetic arm where the two forms DISAGREE must be labelled fragile.
    ctrl = [11, 10, 12, 11, 10, 12, 11, 10]
    armv = [13, 12, 14, 13, 12, 14, 13, 12]          # +2 on every fixture
    p_paired = signflip_permutation_p([a - c for a, c in zip(armv, ctrl)])["p"]
    p_unpaired = unpaired_permutation_p(armv, ctrl)["p"]
    check("H9 uniform +2 shift: paired == 2/256", p_paired, 2 / 256)
    check_cmp("H10 uniform +2 shift: unpaired also significant", p_unpaired, "<", ALPHA)
    # ... and a case built so paired sees a consistent shift the unpaired
    # comparison cannot resolve through between-fixture spread.
    ctrl_b = [4, 8, 12, 16, 6, 10, 14, 18]
    arm_b = [c + 1 for c in ctrl_b]
    pb = signflip_permutation_p([a - c for a, c in zip(arm_b, ctrl_b)])["p"]
    ub = unpaired_permutation_p(arm_b, ctrl_b)["p"]
    check_cmp("H11 pairing-sensitive case: paired significant", pb, "<", ALPHA)
    check_cmp("H12 pairing-sensitive case: unpaired NOT significant", ub, ">", ALPHA)
    print("       -> H11/H12 is a genuine paired/unpaired DISAGREEMENT; on real data "
          "that arm is labelled FRAGILE TO PAIRING CHOICE.")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="§28 D5 scaling campaign analysis")
    ap.add_argument("--ladder", default=".tmp/d5_scaling/ladder.jsonl")
    ap.add_argument("--runs-dir", default=None,
                    help="runs archive (default %%APPDATA%%/Brotato/brotato_agent/runs)")
    ap.add_argument("--expected-trials", type=int, default=EXPECTED_TRIALS)
    ap.add_argument("--allow-partial", action="store_true",
                    help="§28g VIOLATION: compute outcomes on an incomplete campaign")
    ap.add_argument("--self-test", action="store_true",
                    help="run the §28f(c) closed-form verification and exit")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    # §28f(c): the statistic is verified BEFORE it decides anything. Not a
    # separate opt-in step -- an unverified statistic never sees the data.
    print("Verifying the test statistic before it decides anything (§28f(c))...")
    if self_test() != 0:
        print("\nABORT: the permutation implementation failed its closed-form checks. "
              "No analysis is printed.")
        return 1
    print()

    runs_dir = Path(args.runs_dir) if args.runs_dir else (
        Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "runs")
    ladder = Path(args.ladder)
    trials = load_ladder(ladder)
    classify_and_recover(trials, runs_dir)
    groups = per_arm(trials)

    print(f"ladder: {ladder}  rows: {len(trials)}   runs archive: {runs_dir}")
    print()
    incomplete = len(trials) < args.expected_trials
    ceiling = print_counts(groups, trials, mask_outcome_counts=incomplete and not args.allow_partial)

    if incomplete and not args.allow_partial:
        print("=" * 78)
        print(f"STOP. §28g: fixed n, all {args.expected_trials} runs collected regardless of")
        print(f"interim results. The ladder holds {len(trials)}. NO outcome statistic, and no")
        print("per-fixture series, is printed on a partial campaign -- interim interpretation")
        print("is exactly what the stopping rule forbids. Re-run at completion.")
        print("(--allow-partial exists to make the violation explicit, not to license it.)")
        print("=" * 78)
        return 0
    if incomplete:
        print("!" * 78)
        print(f"!! --allow-partial: {len(trials)}/{args.expected_trials} rows. This is an INTERIM")
        print("!! look and is NOT a pre-registered analysis. §28g forbids acting on it.")
        print("!" * 78)
        print()

    print_series(groups)
    print_tests(groups, ceiling)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
