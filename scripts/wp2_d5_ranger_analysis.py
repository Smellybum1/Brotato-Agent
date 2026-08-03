"""S29 -- first Danger 5 victory attempt on `character_ranger`. PRE-REGISTERED analysis.

Implements reports/wp2/d5_ranger_attempt_prereg.md, and NOTHING ELSE.
Authored BLIND, before any S29 run existed, so the statistics cannot be tuned
to the result.

Order of report is part of the design and is fixed here:

  STEP 1  (S29e / S29f)  VALIDITY AND COUNTS, printed BEFORE any outcome.
          Per-run character_observed / observed danger / mod_version /
          unlock_pool era stamp / opener from run_start.weapon, plus the
          DIRECTORY-vs-SUMMARY reconciliation and the supervisor-log greps.
  STEP 2  (S29g PRIMARY)    victory, binary. Era-independent.
  STEP 3  (S29g SECONDARY)  terminal wave, FULL RAW SERIES then descriptives.
  STEP 4  (S29g)            the mutant D5 0/16 context block, printed with its
          era mismatch adjacent and unmissable. NO statistic is computed there.

Deliberate non-features, because the pre-registration does not license them:
  - No p-value, no test, no effect size for ranger-vs-mutant. Different era
    (177/46/2286319327 vs 179/48/2018397571) => NOT POOLABLE.
  - No interim interpretation, no top-up logic, no extension rule (S29g).
  - No offense/landmark analysis, no correlation: that is S26, not S29.

Two traps this project has paid for, hard-coded here:
  - `character_ok` is CONSTANT True across all 276 era-stamped runs => VACUOUS
    as a filter. This script asserts the OBSERVED value and NEVER gates on the
    flag. Same for `danger_ok`: only its PRESENCE is informative.
  - The event key is e["event"], NOT e["type"] (`type` is None on every line,
    and using it yields a clean, wrong zero).

Every candidate-set size is printed BEFORE any count taken off it: a zero from
a vacuous filter is not a zero.

Output is ASCII-only (a prior script died of UnicodeEncodeError on cp1252
AFTER printing its verdict). Importing this module executes and prints NOTHING.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from math import sqrt
from pathlib import Path

EXPECT_CHARACTER = "character_ranger"
EXPECT_DANGER = 5
EXPECT_BUILD = "0.2.73-wp2-capture"
EXPECT_OPENER = "weapon_pistol_1"
EXPECT_ERA = (179, 48, "2018397571")
DESIGN_N = 16

# S29g context block only -- an era-confounded, INDICATIVE-ONLY reference.
MUTANT_D5_WINS = 0
MUTANT_D5_N = 16
MUTANT_D5_ERA = (177, 46, "2286319327")

CEILING_WAVE = 20          # S28g ceiling rule
CEILING_FRACTION = 0.50

SUPERVISOR_PATTERNS = ("Death screen stuck", "Telemetry stall", "Run timeout")

HEAD_LINES = 200           # how far into events.jsonl we look for run_start
TAIL_BYTES = 512 * 1024    # how much of the tail we read for last event / hp

Z95 = 1.959963984540054


# ---------------------------------------------------------------- statistics

def describe(vals: list[float]) -> dict:
    """n / mean / median / sd (sample, n-1) / min / max. No test, no inference."""
    n = len(vals)
    if n == 0:
        return {"n": 0, "mean": None, "median": None, "sd": None,
                "min": None, "max": None}
    mean = sum(vals) / n
    sv = sorted(vals)
    med = sv[n // 2] if n % 2 else (sv[n // 2 - 1] + sv[n // 2]) / 2.0
    sd = sqrt(sum((v - mean) ** 2 for v in vals) / (n - 1)) if n > 1 else 0.0
    return {"n": n, "mean": mean, "median": med, "sd": sd,
            "min": sv[0], "max": sv[-1]}


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float] | None:
    """Wilson score interval for a binomial proportion.

    DESCRIPTIVE uncertainty on the S29g PRIMARY count only. It is not a test
    and nothing in this script branches on it. Chosen over Wald because Wald
    collapses to the degenerate [0, 0] at k = 0, which would make the "no
    victory" case unreadable.
    """
    if n <= 0:
        return None
    if k < 0 or k > n:
        raise ValueError("wilson: k out of range")
    denom = n + z * z
    centre = (k + z * z / 2.0) / denom
    half = (z / denom) * sqrt(k * (n - k) / n + z * z / 4.0)
    return (max(0.0, centre - half), min(1.0, centre + half))


# ---------------------------------------------------------------------- I/O

def read_head_lines(path: Path, limit: int = HEAD_LINES) -> list[str]:
    """First `limit` lines only. events.jsonl reaches 100+ MB; an unbounded
    read once killed a supervisor with MemoryError."""
    out: list[str] = []
    if not path.exists():
        return out
    with path.open(encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            if i >= limit:
                break
            out.append(line)
    return out


def read_tail_lines(path: Path, nbytes: int = TAIL_BYTES) -> list[str]:
    """Last <= nbytes worth of complete-ish lines. Bounded, same reason."""
    if not path.exists():
        return []
    size = path.stat().st_size
    with path.open("rb") as fh:
        if size > nbytes:
            fh.seek(size - nbytes)
            fh.readline()  # drop the partial first line
        blob = fh.read()
    text = blob.decode("utf-8", errors="replace")
    return [ln for ln in text.splitlines() if ln.strip()]


def opener_from_events(events_path: Path) -> str | None:
    """S29e.4 -- the opener is certified BEHAVIOURALLY from run_start.weapon.
    A disk readback of weapon_prefixes proves nothing (S6 passed exactly that
    readback while nothing consumed the key)."""
    for line in read_head_lines(events_path):
        if '"run_start"' not in line:
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("event") != "run_start":   # e["event"], never e["type"]
            continue
        return (e.get("payload") or {}).get("weapon")
    return None


def tail_state(events_path: Path) -> dict:
    """Last event name and terminal HP, for runs that vanished without a
    summary (S29f). HP is scalar on combat_tick.payload.hp; combat_capture
    carries it under payload.player.hp on some builds, so both are tried."""
    last_event = None
    last_wave = None
    hp = None
    hp_source = None
    for line in read_tail_lines(events_path):
        try:
            e = json.loads(line)
        except Exception:
            continue
        ev = e.get("event")
        if ev is None:
            continue
        last_event = ev
        pay = e.get("payload") or {}
        if isinstance(pay.get("wave"), (int, float)):
            last_wave = pay["wave"]
        if isinstance(pay.get("hp"), (int, float)):
            hp, hp_source = pay["hp"], f"{ev}.payload.hp"
        else:
            pl = pay.get("player")
            if isinstance(pl, dict) and isinstance(pl.get("hp"), (int, float)):
                hp, hp_source = pl["hp"], f"{ev}.payload.player.hp"
    return {"last_event": last_event, "last_wave": last_wave,
            "hp": hp, "hp_source": hp_source}


def load_run(runs_dir: Path, rid: str) -> dict | None:
    sp = runs_dir / rid / "summary.json"
    if not sp.exists():
        return None
    s = json.loads(sp.read_text(encoding="utf-8-sig"))   # BOM once broke this
    pool = s.get("unlock_pool") or {}
    return {
        "run_id": rid,
        "wave": s.get("last_wave"),
        "result": str(s.get("result", "")).lower(),
        "victory": str(s.get("result", "")).lower() == "victory",
        "build": str(s.get("mod_version")),
        "character_observed": s.get("character_observed"),
        "requested_character": s.get("requested_character") or s.get("character"),
        "danger": s.get("danger"),
        "danger_ok_present": "danger_ok" in s,
        "estop_enabled": s.get("movement_estop_enabled"),
        "estop_suppressed": s.get("movement_estop_suppressed"),
        "telemetry_complete": s.get("telemetry_complete"),
        "era": (pool.get("items"), pool.get("weapons"), str(pool.get("items_hash"))),
        "opener_summary": s.get("weapon"),
        "opener_events": opener_from_events(runs_dir / rid / "events.jsonl"),
    }


def grep_supervisor_log(path: Path) -> dict:
    counts = {p: 0 for p in SUPERVISOR_PATTERNS}
    if not path.exists():
        return {"exists": False, "counts": counts, "lines": 0}
    lines = 0
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            lines += 1
            for p in SUPERVISOR_PATTERNS:
                if p in line:
                    counts[p] += 1
    return {"exists": True, "counts": counts, "lines": lines}


# ------------------------------------------------------------------ reporting

def analyse(state_file: Path, runs_dir: Path, supervisor_log: Path) -> int:
    bar = "=" * 78
    problems: list[str] = []

    if not state_file.exists():
        print(f"NO STATE FILE: {state_file}")
        return 2
    state = json.loads(state_file.read_text(encoding="utf-8-sig"))
    collected_ids = list(state.get("collected_run_ids") or [])
    baseline_ids = set(state.get("baseline_run_ids") or [])

    rows: list[dict] = []
    missing_summary: list[str] = []
    for rid in collected_ids:
        r = load_run(runs_dir, rid)
        if r is None:
            missing_summary.append(rid)
        else:
            rows.append(r)

    print(bar)
    print("STEP 1 -- VALIDITY AND COUNTS (S29e / S29f)")
    print("PRINTED BEFORE ANY OUTCOME STATISTIC. Nothing below step 1 is read")
    print("until every denominator above has been printed.")
    print(bar)
    print(f"  state file            {state_file}")
    print(f"  runs dir              {runs_dir}")
    print(f"  design n (S29d)       {DESIGN_N}, FIXED")
    print(f"  collected_run_ids     {len(collected_ids)}")
    print(f"  baseline_run_ids      {len(baseline_ids)}  (pre-campaign directories)")
    print(f"  summaries loaded      {len(rows)}")
    print(f"  summaries MISSING     {len(missing_summary)} {missing_summary if missing_summary else ''}")
    if missing_summary:
        problems.append(f"{len(missing_summary)} collected run(s) have no summary.json")

    n = len(rows)
    if n < DESIGN_N:
        print()
        print("  " + "!" * 70)
        print(f"  !! PARTIAL SET: {n} of {DESIGN_N} pre-registered runs are present.")
        print("  !! S29g forbids interim interpretation, extension and top-up-and-retest.")
        print("  !! S26's within-arm D5 sd is 1.590; n < 16 does not discriminate.")
        print("  !! Everything below is a PROGRESS READOUT, NOT the pre-registered result.")
        print("  " + "!" * 70)
    if n == 0:
        print("\n  No summaries to analyse. Stopping before any outcome statistic.")
        return 2

    # --- per-run validity table (S29e). Assert OBSERVED values, never the flags.
    print()
    print(f"  per-run validity, candidate set size = {n}")
    print("  (character_ok and danger_ok are CONSTANT True across all 276 era-stamped")
    print("   runs => VACUOUS as filters. The OBSERVED value is asserted instead; for")
    print("   danger_ok only its PRESENCE is reported.)")
    print()
    hdr = (f"    {'#':>2}  {'run_id':<24} {'char_observed':<18} {'dgr':>3} "
           f"{'dok?':>4}  {'build':<22} {'era':<22} {'opener':<18} {'wave':>4}")
    print(hdr)
    for i, r in enumerate(rows, 1):
        era = f"{r['era'][0]}/{r['era'][1]}/{r['era'][2]}"
        opener = str(r["opener_events"] or r["opener_summary"])
        print(f"    {i:>2}  {r['run_id']:<24} {str(r['character_observed']):<18} "
              f"{str(r['danger']):>3} {str(r['danger_ok_present']):>4}  "
              f"{r['build']:<22} {era:<22} {opener:<18} {str(r['wave']):>4}")

    def tally(name: str, pred, expect_desc: str) -> int:
        ok = sum(1 for r in rows if pred(r))
        flag = "" if ok == n else "   <-- PROBLEM"
        print(f"    {name:<28} {ok}/{n}  (expected {expect_desc}){flag}")
        if ok != n:
            problems.append(f"{name}: {n - ok}/{n} runs off expectation")
        return ok

    print()
    print(f"  aggregate gates, denominator = {n}")
    tally("character_observed", lambda r: r["character_observed"] == EXPECT_CHARACTER,
          EXPECT_CHARACTER)
    tally("observed danger", lambda r: r["danger"] == EXPECT_DANGER, str(EXPECT_DANGER))
    tally("danger_ok PRESENT", lambda r: r["danger_ok_present"], "present on every run")
    tally("mod_version", lambda r: r["build"] == EXPECT_BUILD, EXPECT_BUILD)
    tally("opener (run_start.weapon)",
          lambda r: (r["opener_events"] or r["opener_summary"]) == EXPECT_OPENER,
          EXPECT_OPENER)

    openers_ev = sorted({str(r["opener_events"]) for r in rows})
    openers_sm = sorted({str(r["opener_summary"]) for r in rows})
    print(f"    opener values from events   {openers_ev}")
    print(f"    opener values from summary  {openers_sm}")
    if openers_ev != openers_sm:
        print("      note: summary and events disagree on the opener; the BEHAVIOURAL")
        print("      value (run_start.weapon) is the certified one per S29d.")

    # --- era stamp per run (S29h). Drift is DISCLOSED, not fatal.
    eras = sorted({r["era"] for r in rows}, key=str)
    print()
    print(f"  era stamp (unlock_pool), denominator = {n}")
    for e in eras:
        cnt = sum(1 for r in rows if r["era"] == e)
        print(f"    {e[0]}/{e[1]}/{e[2]}   {cnt}/{n} runs")
    print(f"    expected {EXPECT_ERA[0]}/{EXPECT_ERA[1]}/{EXPECT_ERA[2]}")
    if len(eras) == 1:
        print("    era is CONSTANT across the arm.")
        if eras[0] != EXPECT_ERA:
            print("    <-- DRIFT: constant but NOT the expected stamp.")
            print("        DISCLOSED. This voids the arm's COMPARATIVE use.")
            print("        It does NOT affect the victory objective, which is era-independent.")
    else:
        print(f"    <-- DRIFT: the arm spans {len(eras)} eras.")
        print("        DISCLOSED per S29h. Voids the arm's COMPARATIVE use;")
        print("        the victory objective is era-independent and stands.")

    # --- S29f directory-vs-summary reconciliation. BOTH denominators printed.
    print()
    print("  S29f RECONCILIATION -- runs that VANISHED rather than were rejected")
    print("  The supervisor applies no validity filter at collection, so there is no")
    print("  reject-by-outcome path. The residual risk is a run killed BEFORE its")
    print("  summary was written: it produces no summary and is never collected.")
    print("  dead_stuck fires only on hp == 0, so the only runs it can silently drop")
    print("  are DEATHS -- outcome-selecting in the direction that flatters the arm.")
    if not runs_dir.exists():
        print(f"    RUNS DIR DOES NOT EXIST: {runs_dir} -- reconciliation NOT COMPUTED.")
        problems.append("runs dir missing; S29f reconciliation not computed")
    else:
        all_dirs = {p.name for p in runs_dir.iterdir() if p.is_dir()}
        collected_set = set(collected_ids)
        # ⛔ BUG FIXED 2026-08-03, found on the first real run. The window was
        # `all_dirs - baseline_ids`, but `baseline_run_ids` is built by the
        # supervisor from list_summaries() (overnight_supervisor.py:42-52), i.e.
        # from SUMMARIES, not directories. Every historical run that never wrote
        # a summary is therefore absent from the baseline and was misread as
        # campaign-window excess: it reported 293 window dirs and **277 "vanished
        # runs"** dating back to run_1784xxx, weeks before the campaign. A wrong
        # denominator manufacturing a large, alarming, entirely false positive.
        # Correct window: run ids embed their start epoch (run_<epoch>_<rand>),
        # so the campaign window is bounded below by the EARLIEST COLLECTED run.
        def _epoch(name: str):
            parts = name.split("_")
            return int(parts[1]) if len(parts) > 2 and parts[1].isdigit() else None
        floors = [e for e in (_epoch(r) for r in collected_ids) if e is not None]
        floor = min(floors) if floors else None
        if floor is None:
            print("    CANNOT DERIVE CAMPAIGN WINDOW from collected run ids -- "
                  "reconciliation NOT COMPUTED (not reported as zero).")
            problems.append("campaign window underivable; S29f reconciliation not computed")
            window_dirs = []
        else:
            window_dirs = sorted(
                d for d in all_dirs
                if (_epoch(d) is not None and _epoch(d) >= floor)
            )
        excess = sorted(set(window_dirs) - collected_set)
        print(f"    directories in runs dir, total           {len(all_dirs)}")
        print(f"    baseline_run_ids (SUMMARIES, not dirs)   {len(baseline_ids)}"
              f"   <- NOT used as the window; see comment")
        print(f"    campaign floor epoch (earliest collected run)  {floor}")
        print(f"    DENOMINATOR A: directories created in the campaign window "
              f"(run-id epoch >= floor)  {len(window_dirs)}")
        print(f"    DENOMINATOR B: len(collected_run_ids)                              "
              f"  {len(collected_ids)}")
        print(f"    excess (A not in B) = {len(excess)}")
        missing_from_dirs = sorted(collected_set - all_dirs)
        if missing_from_dirs:
            print(f"    collected ids with NO directory: {missing_from_dirs}")
            problems.append("collected run ids without a directory")
        if not excess:
            print("    A == B: no run vanished. (This zero is meaningful only because")
            print("     both denominators above were actually computed and printed.)")
        else:
            print("    <-- KNOWN UNMEASURED TRIALS, listed individually, never dropped:")
            for rid in excess:
                ts = tail_state(runs_dir / rid / "events.jsonl")
                print(f"      {rid}  last_event={ts['last_event']}  "
                      f"last_wave={ts['last_wave']}  terminal_hp={ts['hp']} "
                      f"({ts['hp_source']})")
            print("    NOTE: one of these may simply be the run in flight if the")
            print("    campaign is still running.")
            problems.append(f"{len(excess)} run(s) created but never collected")

    # --- supervisor log greps (S29f)
    print()
    log = grep_supervisor_log(supervisor_log)
    print(f"  supervisor log: {supervisor_log}")
    if not log["exists"]:
        print("    NOT FOUND -- grep counts NOT COMPUTED (a zero here would be vacuous).")
        problems.append("supervisor log not found; restart-path counts not computed")
    else:
        print(f"    lines scanned (denominator) = {log['lines']}")
        for p in SUPERVISOR_PATTERNS:
            print(f"      {p:<22} {log['counts'][p]}")

    print()
    print(f"  VALIDITY PROBLEMS: {len(problems)}")
    for p in problems:
        print(f"    - {p}")

    # ------------------------------------------------------------- STEP 2
    print()
    print(bar)
    print("STEP 2 -- PRIMARY ENDPOINT (S29g): VICTORY, BINARY. ERA-INDEPENDENT.")
    print(bar)
    print(f"  candidate set size (runs with a summary) = {n}")
    wins = [r for r in rows if r["victory"]]
    results = sorted({r["result"] for r in rows})
    print(f"  distinct result values observed: {results}")
    print(f"  VICTORIES: {len(wins)}/{n}")
    ci = wilson(len(wins), n)
    print(f"  rate {len(wins)/n:.4f}   Wilson 95% [{ci[0]:.4f}, {ci[1]:.4f}] "
          f"(descriptive only; not a test)")
    if wins:
        for r in wins:
            print(f"    VICTORY  run_id={r['run_id']}  terminal_wave={r['wave']}  "
                  f"era={r['era'][0]}/{r['era'][1]}/{r['era'][2]}")
        print("  => NORTH STAR 1 SATISFIED: a Danger 5 run was won.")
    else:
        print("    (no victorious run ids to list)")
        print("  S29c, declared before data: a ranger 0/16 at D5 is a FULLY EXPECTED")
        print("  outcome and does NOT falsify the selection. D0 competence is measured")
        print("  not to carry to D5 (mutant .3125 -> .000, p = 0.043). Ranger's .688 at")
        print("  D0 was a SCREENING signal, never a prediction.")

    # ------------------------------------------------------------- STEP 3
    print()
    print(bar)
    print("STEP 3 -- SECONDARY ENDPOINT (S29g): TERMINAL WAVE (characterisation)")
    print(bar)
    waves_raw = [r["wave"] for r in rows]
    usable = [float(w) for w in waves_raw if isinstance(w, (int, float))]
    print(f"  candidate set size = {n}; runs with a numeric last_wave = {len(usable)}")
    if len(usable) != n:
        bad = [r["run_id"] for r in rows if not isinstance(r["wave"], (int, float))]
        print(f"    non-numeric last_wave on: {bad}")
        problems.append("non-numeric last_wave present")
    if not usable:
        print("  no numeric terminal waves; nothing to describe.")
    else:
        print("  FULL RAW per-run terminal wave series (sorted) -- the raw series is")
        print("  required; a summary statistic alone is never sufficient:")
        print(f"    {[int(w) if float(w).is_integer() else w for w in sorted(usable)]}")
        print("  unsorted, paired to run_id:")
        for r in rows:
            print(f"    {r['run_id']:<24} wave={r['wave']}  result={r['result']}")
        d = describe(usable)
        print(f"  n={d['n']}  median={d['median']:.1f}  mean={d['mean']:.4f}  "
              f"sd={d['sd']:.4f}  min={d['min']:.0f}  max={d['max']:.0f}")
        at_ceiling = sum(1 for w in usable if w >= CEILING_WAVE)
        frac = at_ceiling / len(usable)
        print(f"  runs at wave >= {CEILING_WAVE}: {at_ceiling}/{len(usable)} = {frac:.4f}")
        if frac >= CEILING_FRACTION:
            print("  " + "!" * 70)
            print(f"  !! S28g CEILING RULE FIRES: >= {CEILING_FRACTION:.0%} of trials reach "
                  f"wave {CEILING_WAVE}.")
            print("  !! TERMINAL WAVE IS A FLOOR, NOT A POINT ESTIMATE.")
            print("  !! Any effect size computed off it is a BOUND. The mean and sd")
            print("  !! printed above UNDERSTATE the true values by an unknown amount.")
            print("  " + "!" * 70)

    # ------------------------------------------------------------- STEP 4
    print()
    print(bar)
    print("STEP 4 -- CONTEXT ONLY: mutant D5. NOT EVIDENCE. NO STATISTIC COMPUTED.")
    print(bar)
    print("  " + "!" * 70)
    print(f"  !! mutant D5 arm : {MUTANT_D5_WINS}/{MUTANT_D5_N} victories at era "
          f"{MUTANT_D5_ERA[0]}/{MUTANT_D5_ERA[1]}/{MUTANT_D5_ERA[2]}")
    ranger_era = f"{eras[0][0]}/{eras[0][1]}/{eras[0][2]}" if len(eras) == 1 else f"{len(eras)} eras (drifted)"
    print(f"  !! ranger D5 arm : {len(wins)}/{n} victories at era {ranger_era}")
    print("  !! DIFFERENT ERA => NOT POOLABLE => ERA-CONFOUNDED => INDICATIVE ONLY.")
    print("  !! S29g forbids reporting any ranger-vs-mutant comparison AS EVIDENCE.")
    print("  !! No p-value, no test, no effect size is computed here, by design.")
    print("  !! This was declared BEFORE data so it could not be decided afterwards.")
    print("  " + "!" * 70)
    print("  Also on record and NOT upgraded (S29b): the exact 4-group homogeneity")
    print("  test on S25's bare arm is p = 0.00606 (characters differ); bare ranger")
    print("  vs bare mutant at D0 is 5/8 vs 1/8, p = 0.119. Ranger being the top D0")
    print("  cell is best-of-N, i.e. outcome selection.")

    print()
    print(bar)
    if n < DESIGN_N:
        print(f"EXIT: PARTIAL ({n}/{DESIGN_N}). Not the pre-registered result.")
        return 2
    if problems:
        print(f"EXIT: {len(problems)} VALIDITY PROBLEM(S) -- resolve before quoting any number.")
        return 3
    print("EXIT: clean, n at design size.")
    return 0


# ---------------------------------------------------------------- self-test

def _write_run(runs_dir: Path, rid: str, *, wave, result: str,
               danger: int = EXPECT_DANGER,
               character: str = EXPECT_CHARACTER,
               era: tuple = EXPECT_ERA,
               build: str = EXPECT_BUILD,
               opener: str = EXPECT_OPENER,
               with_summary: bool = True,
               bom: bool = False,
               danger_ok_key: bool = True,
               ticks: list[tuple[int, int]] | None = None) -> None:
    d = runs_dir / rid
    d.mkdir(parents=True, exist_ok=True)
    if with_summary:
        s = {
            "run_id": rid, "last_wave": wave, "result": result, "danger": danger,
            "character": character, "character_observed": character,
            "character_ok": True, "mod_version": build, "weapon": opener,
            "movement_estop_enabled": False, "telemetry_complete": True,
            "unlock_pool": {"items": era[0], "weapons": era[1],
                            "items_hash": era[2], "weapons_hash": "1530875081"},
        }
        if danger_ok_key:
            s["danger_ok"] = True
        enc = "utf-8-sig" if bom else "utf-8"
        (d / "summary.json").write_text(json.dumps(s), encoding=enc)
    lines = [json.dumps({"event": "run_start", "type": None,
                         "payload": {"weapon": opener, "character": character}})]
    for w, hp in (ticks or [(1, 20)]):
        lines.append(json.dumps({"event": "combat_tick", "type": None,
                                 "payload": {"wave": w, "hp": hp}}))
    (d / "events.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_script(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(Path(__file__).resolve()), *args],
                          capture_output=True, text=True)


def self_test() -> int:
    fails: list[str] = []

    def check(name: str, ok: bool, extra: str = "") -> None:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {extra}" if extra else ""))
        if not ok:
            fails.append(name)

    print("Validating every statistic against a known closed form BEFORE the")
    print("script is allowed to decide anything.\n")

    # ---- (a) describe() against hand-computed closed forms, BOTH directions.
    d = describe([1.0, 2.0, 3.0, 4.0])
    # mean 2.5; median (2+3)/2 = 2.5; sample sd = sqrt(5/3) = 1.290994448735806
    check("(a1) describe: even n -> mean 2.5, median 2.5, sd sqrt(5/3)",
          abs(d["mean"] - 2.5) < 1e-12 and abs(d["median"] - 2.5) < 1e-12
          and abs(d["sd"] - sqrt(5.0 / 3.0)) < 1e-12,
          f"mean={d['mean']} med={d['median']} sd={d['sd']:.12f}")
    d2 = describe([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
    # textbook: mean 5, population sd 2, sample sd = sqrt(32/7) = 2.13808993529939
    check("(a2) describe: textbook set -> mean 5, sample sd sqrt(32/7)",
          abs(d2["mean"] - 5.0) < 1e-12 and abs(d2["sd"] - sqrt(32.0 / 7.0)) < 1e-12,
          f"mean={d2['mean']} sd={d2['sd']:.12f}")
    d3 = describe([7.0, 3.0, 5.0])
    check("(a3) describe: odd n -> median is the middle ORDER STATISTIC (5), "
          "not the middle input",
          d3["median"] == 5.0 and d3["min"] == 3.0 and d3["max"] == 7.0,
          f"med={d3['median']} min={d3['min']} max={d3['max']}")
    d4 = describe([9.0] * 5)
    check("(a4) describe: NULL case, a constant series has sd exactly 0",
          d4["sd"] == 0.0 and d4["mean"] == 9.0, f"sd={d4['sd']}")
    d5 = describe([1.0])
    check("(a5) describe: n=1 does not divide by zero", d5["sd"] == 0.0)

    # ---- (b) Wilson against published closed forms, POSITIVE and NULL branches.
    # Independent derivation: the Wilson bounds are the two roots of
    # (n + z^2) p^2 - (2k + z^2) p + k^2/n = 0, i.e. the p solving
    # |phat - p| = z*sqrt(p(1-p)/n). Recomputing them by the quadratic formula
    # is a genuinely different route to the same numbers, not a restatement of
    # the implementation.
    def wilson_by_quadratic(k: int, n: int, z: float = Z95) -> tuple[float, float]:
        a = n + z * z
        b = -(2.0 * k + z * z)
        c = k * k / n
        disc = b * b - 4 * a * c
        return ((-b - sqrt(disc)) / (2 * a), (-b + sqrt(disc)) / (2 * a))

    lo, hi = wilson(50, 100)
    qlo, qhi = wilson_by_quadratic(50, 100)
    check("(b1) Wilson 50/100 matches the quadratic-root derivation and the "
          "published (0.40383, 0.59617)",
          abs(lo - qlo) < 1e-12 and abs(hi - qhi) < 1e-12
          and abs(lo - 0.40383) < 1e-5 and abs(hi - 0.59617) < 1e-5,
          f"({lo:.7f}, {hi:.7f}) vs quadratic ({qlo:.7f}, {qhi:.7f})")
    lo7, hi7 = wilson(7, 20)
    q7lo, q7hi = wilson_by_quadratic(7, 20)
    check("(b1b) Wilson 7/20 matches the quadratic-root derivation "
          "(asymmetric case, so a symmetry bug could not hide)",
          abs(lo7 - q7lo) < 1e-12 and abs(hi7 - q7hi) < 1e-12
          and abs((lo7 + hi7) / 2 - 0.35) > 1e-3,
          f"({lo7:.7f}, {hi7:.7f})")
    lo0, hi0 = wilson(0, 10)
    # centre = (0+z^2/2)/(10+z^2) ; half = z/(10+z^2) * sqrt(0 + z^2/4) = centre
    zz = Z95 * Z95
    exp_hi = (zz / 2.0) / (10 + zz) + (Z95 / (10 + zz)) * sqrt(zz / 4.0)
    check("(b2) Wilson NULL branch 0/10: lower is EXACTLY 0, upper matches the "
          "closed form (a Wald interval would degenerate to [0,0])",
          lo0 == 0.0 and abs(hi0 - exp_hi) < 1e-12 and abs(hi0 - 0.2775327) < 1e-6,
          f"({lo0:.7f}, {hi0:.7f})")
    lo1, hi1 = wilson(10, 10)
    check("(b3) Wilson POSITIVE branch 10/10: upper is EXACTLY 1 and the lower "
          "bound EXCLUDES 0 (the interval can return the positive)",
          hi1 == 1.0 and lo1 > 0.6, f"({lo1:.7f}, {hi1:.7f})")
    lo2, hi2 = wilson(1, 16)
    check("(b4) Wilson 1/16 (a single victory in the design-size arm) is a "
          "proper subinterval of (0,1)",
          0.0 < lo2 < 1.0 / 16 < hi2 < 1.0, f"({lo2:.7f}, {hi2:.7f})")
    try:
        wilson(3, 2)
        bad = True
    except ValueError:
        bad = False
    check("(b5) Wilson rejects k > n rather than returning a number", not bad)
    check("(b6) Wilson n=0 returns None, not a spurious interval", wilson(0, 0) is None)

    # ---- (c) ceiling rule fires and does NOT fire, at the exact boundary.
    def ceil_frac(ws):
        return sum(1 for w in ws if w >= CEILING_WAVE) / len(ws)
    check("(c1) ceiling rule NULL branch: 7/16 at wave 20 is below 50%",
          ceil_frac([20] * 7 + [11] * 9) < CEILING_FRACTION,
          f"frac={ceil_frac([20]*7+[11]*9):.4f}")
    check("(c2) ceiling rule POSITIVE branch: 8/16 at wave 20 fires (>=, not >)",
          ceil_frac([20] * 8 + [11] * 8) >= CEILING_FRACTION,
          f"frac={ceil_frac([20]*8+[11]*8):.4f}")

    tmp = Path(tempfile.mkdtemp(prefix="d5ranger_selftest_"))
    runs = tmp / "runs"
    runs.mkdir(parents=True)

    # ---- (d) parsing: BOM, e["event"] not e["type"], bounded tail.
    _write_run(runs, "run_bom", wave=12, result="defeat", bom=True)
    r = load_run(runs, "run_bom")
    check("(d1) summary.json with a UTF-8 BOM parses (utf-8-sig)",
          r is not None and r["wave"] == 12)
    check("(d2) opener comes from run_start via e['event'] "
          "(e['type'] is None on every line and would yield a clean wrong zero)",
          r["opener_events"] == EXPECT_OPENER, f"opener={r['opener_events']}")
    _write_run(runs, "run_tail", wave=9, result="defeat",
               ticks=[(8, 15), (9, 7), (9, 0)])
    ts = tail_state(runs / "run_tail" / "events.jsonl")
    check("(d3) tail_state finds the LAST event, its wave and terminal hp=0",
          ts["last_event"] == "combat_tick" and ts["last_wave"] == 9
          and ts["hp"] == 0, f"{ts}")
    check("(d4) head/tail readers are bounded (no whole-file read)",
          len(read_head_lines(runs / "run_tail" / "events.jsonl", 2)) == 2)

    # ---- (e) end-to-end: clean 16-run arm, NO victory (the null outcome).
    # Run ids MUST be realistic `run_<epoch>_<rand>`: the S29f campaign window is
    # derived from the run-id epoch (see the reconciliation block). Fixtures that
    # used opaque names like "camp_null_run_00" made the window underivable, so
    # these checks silently exercised the NOT-COMPUTED branch instead of the real
    # one. Baseline sits BELOW the floor; extra_dirs sit ABOVE it, i.e. genuinely
    # inside the window, which is the only way (g1) can test what it claims to.
    BASE_EPOCH = 1700000000
    CAMP_EPOCH = 1700010000

    def build_campaign(dirname: str, waves, results, extra_dirs=(), baseline=("old",)):
        root = tmp / dirname
        rd = root / "runs"
        rd.mkdir(parents=True)
        for j, b in enumerate(baseline):
            _write_run(rd, f"run_{BASE_EPOCH + j}_{b}", wave=5, result="defeat")
        ids = []
        for i, (w, res) in enumerate(zip(waves, results)):
            rid = f"run_{CAMP_EPOCH + i * 100}_{i:02d}"
            _write_run(rd, rid, wave=w, result=res, ticks=[(w, 0)])
            ids.append(rid)
        for k, rid in enumerate(extra_dirs):
            _write_run(rd, f"run_{CAMP_EPOCH + 90000 + k}_{rid}", wave=None, result="",
                       with_summary=False, ticks=[(11, 3), (11, 0)])
        sf = root / "state.json"
        sf.write_text(json.dumps({"schema_version": 1,
                                  "baseline_run_ids": sorted(baseline),
                                  "collected_run_ids": ids}), encoding="utf-8")
        lg = root / "supervisor.log"
        lg.write_text("ok\nDeath screen stuck; relaunching\nTelemetry stall detected\n"
                      "ok\nRun timeout exceeded\nDeath screen stuck again\n",
                      encoding="utf-8")
        return sf, rd, lg

    waves_null = [9, 10, 11, 11, 12, 8, 13, 10, 9, 14, 11, 12, 10, 11, 9, 13]
    sf, rd, lg = build_campaign("camp_null", waves_null, ["defeat"] * 16)
    p = _run_script("--state-file", str(sf), "--runs-dir", str(rd),
                    "--supervisor-log", str(lg))
    out = p.stdout
    ordered = (out.index("STEP 1") < out.index("STEP 2") < out.index("STEP 3")
               < out.index("STEP 4"))
    check("(e1) NULL end-to-end: clean 16/16, 0 victories, exit 0, steps in order",
          p.returncode == 0 and "VICTORIES: 0/16" in out and ordered,
          f"exit={p.returncode}")
    check("(e2) validity is printed BEFORE the primary endpoint",
          out.index("VALIDITY AND COUNTS") < out.index("PRIMARY ENDPOINT"))
    check("(e3) both reconciliation denominators are printed, not just the difference",
          "DENOMINATOR A" in out and "DENOMINATOR B" in out and "excess (A not in B) = 0" in out)
    check("(e4) supervisor grep counts are reported with their denominator",
          all(f"{pat:<22} {cnt}" in out
              for pat, cnt in zip(SUPERVISOR_PATTERNS, (2, 1, 1)))
          and "lines scanned (denominator) = 6" in out)
    check("(e5) the raw per-run terminal-wave series is printed, not only a summary",
          str(sorted(waves_null)) in out and "FULL RAW" in out)
    check("(e6) STEP 4 prints the era mismatch and computes NO statistic",
          "NOT POOLABLE" in out and "ERA-CONFOUNDED" in out
          and "No p-value, no test, no effect size" in out)
    check("(e7) all output is ASCII-safe (a prior script died on cp1252)",
          all(ord(c) < 128 for c in out))
    if p.returncode != 0:
        print(out[-3000:]); print(p.stderr[-2000:])

    # ---- (f) POSITIVE end-to-end: a victory is detected and named.
    waves_win = [9, 10, 11, 11, 12, 8, 13, 10, 9, 14, 11, 12, 10, 11, 9, 20]
    res_win = ["defeat"] * 15 + ["victory"]
    sf2, rd2, lg2 = build_campaign("camp_win", waves_win, res_win)
    p2 = _run_script("--state-file", str(sf2), "--runs-dir", str(rd2),
                     "--supervisor-log", str(lg2))
    check("(f1) POSITIVE end-to-end: the victory is counted and its run_id printed",
          "VICTORIES: 1/16" in p2.stdout
          and f"run_{CAMP_EPOCH + 15 * 100}_15" in p2.stdout
          and "NORTH STAR 1 SATISFIED" in p2.stdout, f"exit={p2.returncode}")
    check("(f2) the victory branch is REACHABLE and distinct from the null branch",
          "VICTORIES: 0/16" not in p2.stdout)

    # ---- (g) the vanished-run path: an excess directory is listed individually.
    sf3, rd3, lg3 = build_campaign("camp_ghost", waves_null[:15], ["defeat"] * 15,
                                   extra_dirs=("camp_ghost_ghost",))
    p3 = _run_script("--state-file", str(sf3), "--runs-dir", str(rd3),
                     "--supervisor-log", str(lg3))
    check("(g1) a run directory with no summary is reported as a KNOWN UNMEASURED "
          "TRIAL, with its last event and terminal HP",
          "KNOWN UNMEASURED" in p3.stdout and "camp_ghost_ghost" in p3.stdout
          and "terminal_hp=0" in p3.stdout)
    check("(g2) a short campaign is announced LOUDLY and exits 2, not silently "
          "analysed as if complete",
          p3.returncode == 2 and "PARTIAL SET: 15 of 16" in p3.stdout,
          f"exit={p3.returncode}")

    # ---- (h) validity failures are caught on OBSERVED values, never on the
    #          vacuous character_ok / danger_ok flags.
    root4 = tmp / "camp_bad"
    rd4 = root4 / "runs"
    rd4.mkdir(parents=True)
    ids4 = []
    for i in range(16):
        rid = f"bad_{i:02d}"
        _write_run(rd4, rid, wave=10, result="defeat",
                   character="character_mutant" if i == 3 else EXPECT_CHARACTER,
                   danger=0 if i == 4 else EXPECT_DANGER,
                   opener="weapon_smg_1" if i == 5 else EXPECT_OPENER,
                   era=(177, 46, "2286319327") if i == 6 else EXPECT_ERA)
        ids4.append(rid)
    sf4 = root4 / "state.json"
    sf4.write_text(json.dumps({"schema_version": 1, "baseline_run_ids": [],
                               "collected_run_ids": ids4}), encoding="utf-8")
    p4 = _run_script("--state-file", str(sf4), "--runs-dir", str(rd4),
                     "--supervisor-log", str(root4 / "nope.log"))
    check("(h1) a wrong character_observed is caught even though character_ok is "
          "True on every run (the flag is VACUOUS and is never gated on)",
          "character_observed           15/16" in p4.stdout and p4.returncode == 3,
          f"exit={p4.returncode}")
    check("(h2) a wrong observed danger is caught (danger_ok is True throughout)",
          "observed danger              15/16" in p4.stdout)
    check("(h3) a wrong opener is caught behaviourally from run_start.weapon",
          "opener (run_start.weapon)    15/16" in p4.stdout)
    check("(h4) era DRIFT is DISCLOSED (arm spans 2 eras) and does not silently pass",
          "DRIFT: the arm spans 2 eras" in p4.stdout)
    check("(h5) a missing supervisor log is reported as NOT COMPUTED, never as a "
          "count of zero",
          "grep counts NOT COMPUTED" in p4.stdout)

    # ---- (i) importing the module must compute and print nothing.
    probe = tmp / "probe.py"
    probe.write_text(
        "import importlib.util, sys, io\n"
        "buf = io.StringIO(); old = sys.stdout; sys.stdout = buf\n"
        f"spec = importlib.util.spec_from_file_location('m', r'{Path(__file__).resolve()}')\n"
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        "sys.stdout = old\n"
        "print('PRINTED:' + repr(buf.getvalue()))\n", encoding="utf-8")
    p5 = subprocess.run([sys.executable, str(probe)], capture_output=True, text=True)
    check("(i) importing this module prints NOTHING and computes no verdict "
          "(a previous verification script imported an analysis module, which "
          "EXECUTED it and printed a verdict off a partially-written file)",
          "PRINTED:''" in p5.stdout, p5.stdout.strip()[:120])

    # ---- (j) missing state file
    p6 = _run_script("--state-file", str(tmp / "no_such_state.json"),
                     "--runs-dir", str(runs))
    check("(j) a missing state file exits non-zero instead of reporting 0 runs",
          p6.returncode == 2 and "NO STATE FILE" in p6.stdout, f"exit={p6.returncode}")

    print()
    if fails:
        print(f"SELF-TEST FAILED: {len(fails)} check(s) -- {fails}")
        return 1
    print("All self-tests passed.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="S29 ranger D5 pre-registered analysis")
    ap.add_argument("--state-file", default=r".tmp/d5_ranger/state.json")
    ap.add_argument("--runs-dir", default=None)
    ap.add_argument("--supervisor-log", default=None)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    state_file = Path(args.state_file).resolve()
    runs_dir = Path(args.runs_dir) if args.runs_dir else Path(
        os.path.expandvars(r"%APPDATA%\Brotato\brotato_agent\runs"))
    sup = Path(args.supervisor_log) if args.supervisor_log else \
        state_file.parent / "supervisor.log"
    return analyse(state_file, runs_dir, sup)


if __name__ == "__main__":
    raise SystemExit(main())
