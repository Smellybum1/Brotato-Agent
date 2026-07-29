"""Analysis for the STUDENT vs CONTROL confinement screen.

Pre-registered in ``reports/wp2/student_bd_confinement_prereg.md``. The decision
rule is fixed there and is NOT re-derived here.

The one thing this script does differently from the label-based readouts: it
assigns each trial's arm from the **treatment readback** -- the fraction of that
run's wave-17 ``student_tick`` events with ``source == "student"`` -- and not
from the run label. A label records what was INTENDED. If the sidecar died, or
the config write did not land, the trial still carries the student label while
having run the teacher, and pooling on the label silently mixes the arms.

Validity counts are printed PER ARM before any outcome number, and every guard
is computed on the serving stream rather than on the result, so none of them can
reject by outcome.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# The PRIMARY endpoint is computed by the existing reference implementation, not
# reimplemented here. A local copy silently diverged on two details already: the
# reference bins with `int(x // cell)` and no centring offset, and it EXCLUDES
# sub-10 ms control_dt captures. Numbers that are not produced by the same code
# as the archived baseline are not comparable to it.
from wp2_confinement import (  # noqa: E402
    MIN_CONTROL_DT_MS,
    analyze_run,
    arena_of,
    dig,
    iter_captures,
    occupancy_concentration,
)

SERVE_BAR = 0.80          # prereg: a STUDENT trial serves >=80% of its wave-17 ticks
ARCHIVED_CONTROL_SD = 4.427
GO_BAR = 2.0 * ARCHIVED_CONTROL_SD          # +8.85 cells
NOGO_BAR = 0.5 * ARCHIVED_CONTROL_SD        # +2.21 cells


def runs_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "runs"


def serving_readback(run_id: str, wave: int):
    """Treatment readback for one run's wave-`wave`.

    Returns (frac_all, frac_conn, total, served, n_conn) where:

    * ``frac_all``  = served / all wave ticks.
    * ``frac_conn`` = served / ticks during which a connection existed, i.e.
      excluding ``not_connected`` and ``disconnect`` ticks.

    Neither is a FILTER (prereg 5c). The all-tick fraction falls purely because
    a trial is short -- the mod reconnects 2-3 times per run and each gap costs
    a roughly fixed ~61 ticks -- and short trials are deaths, so gating on it
    would reject by outcome. The connected-only fraction is invariant to trial
    length and to the number of reconnect gaps, and answers the question the
    guard was actually for: when a connection existed, did the student drive?
    """
    path = runs_dir() / run_id / "events.jsonl"
    if not path.is_file():
        return None
    seq = []
    for line in path.open(encoding="utf-8"):
        if '"student_tick"' not in line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("event") != "student_tick":
            continue
        p = ev.get("payload", {})
        if int(p.get("wave", -1)) != wave:
            continue
        seq.append((p.get("source"), p.get("cause")))

    total = len(seq)
    served = sum(1 for src, _ in seq if src == "student")
    GAP = {"not_connected", "disconnect"}
    connected = [(src, cause) for src, cause in seq if cause not in GAP]
    n_conn = len(connected)
    served_conn = sum(1 for src, _ in connected if src == "student")
    frac_all = served / total if total else 0.0
    frac_conn = served_conn / n_conn if n_conn else 0.0
    return frac_all, frac_conn, total, served, n_conn


def wave_positions(run_id: str, wave: int):
    """Wave-`wave` player positions, filtered exactly as `analyze_run` does."""
    kept = []
    for p in iter_captures(runs_dir() / run_id):
        if int(p.get("wave", 0) or 0) != wave:
            continue
        dt = p.get("control_dt_ms")
        if dt is not None:
            try:
                if float(dt) < MIN_CONTROL_DT_MS:
                    continue
            except (TypeError, ValueError):
                pass
        kept.append(p)
    w, h = arena_of(kept)
    positions = [(float(dig(p, "player", "x", default=0.0)),
                  float(dig(p, "player", "y", default=0.0))) for p in kept]
    return positions, w, h


def prefix_cells(run_id: str, wave: int, k: int):
    """PREREG ADDENDUM 5b: the primary recomputed on a COMMON capture budget, so
    both arms are measured at an identical sample size even when one arm dies
    earlier."""
    positions, w, h = wave_positions(run_id, wave)
    if len(positions) < k or k <= 0:
        return None
    return occupancy_concentration(positions[:k], w, h)["cells_50pct"]


def summarise(name, values):
    if not values:
        return f"  {name:<10} n=0"
    mean = statistics.mean(values)
    sd = statistics.stdev(values) if len(values) > 1 else float("nan")
    return (f"  {name:<10} n={len(values):<3} mean={mean:6.2f}  sd={sd:5.3f}  "
            f"raw={sorted(values)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", required=True)
    ap.add_argument("--wave", type=int, default=17)
    ap.add_argument("--exclude", nargs="*", default=[])
    args = ap.parse_args()

    rows = []
    for line in Path(args.trials).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    rows = [r for r in rows if r.get("run_id") not in set(args.exclude)]

    print(f"trials in file: {len(rows)}  (excluded: {args.exclude})\n")

    # ---- validity and ARM ASSIGNMENT FROM READBACK, before any outcome ----
    buckets = {"student": [], "control": [], "AMBIGUOUS": [], "invalid": []}
    for r in rows:
        rid = r.get("run_id")
        if not r.get("valid"):
            buckets["invalid"].append((rid, r.get("label"), r.get("invalid_reason")))
            continue
        got = serving_readback(rid, args.wave)
        if got is None:
            buckets["invalid"].append((rid, r.get("label"), "no events.jsonl"))
            continue
        frac_all, frac_conn, total, served, n_conn = got
        analysis = analyze_run(runs_dir() / rid, args.wave)
        rec = {
            "run_id": rid, "label": r.get("label"),
            "frac": frac_conn, "frac_all": frac_all, "n_conn": n_conn,
            "ticks": total, "served": served,
            "cells": analysis["concentration"]["cells_50pct"],
            "captures": analysis["captures_used"],
            "damage": r.get("damage_taken"),
            "result": analysis.get("result") or r.get("result"),
            "survived": analysis.get("survived"),
            "fixture": r.get("fixture_file", ""),
        }
        # prereg 5c: INTENTION TO TREAT. Neither condition can be moved by how
        # the trial turned out. No trial is dropped for serving less.
        if served > 0:
            buckets["student"].append(rec)
        elif total == 0:
            buckets["control"].append(rec)
        else:
            # student_enabled was on but the sidecar never served: an arming
            # failure, reported rather than silently pooled into either arm.
            buckets["AMBIGUOUS"].append(rec)

    print("=== VALIDITY / ARM ASSIGNMENT (from treatment readback, before outcomes) ===")
    for key in ("student", "control", "AMBIGUOUS", "invalid"):
        print(f"  {key:<10} {len(buckets[key])}")
    if buckets["AMBIGUOUS"]:
        print("\n  !! AMBIGUOUS trials (partial serving) -- EXCLUDED per prereg:")
        for r in buckets["AMBIGUOUS"]:
            print(f"     {r['run_id']} label={r['label']} served={r['served']}/{r['ticks']} "
                  f"({r['frac']:.3f})")
    if buckets["invalid"]:
        print("\n  invalid trials:")
        for rid, label, reason in buckets["invalid"]:
            print(f"     {rid} label={label} reason={reason}")

    mism = [r for r in buckets["student"] if not str(r["label"]).startswith("student")]
    mism += [r for r in buckets["control"] if not str(r["label"]).startswith("control")]
    if mism:
        print("\n  !! LABEL/READBACK DISAGREEMENT (readback wins):")
        for r in mism:
            print(f"     {r['run_id']} label={r['label']} serve_frac={r['frac']:.3f}")
    else:
        print("\n  label and readback agree on every valid trial")

    if buckets["student"]:
        fc = sorted(r["frac"] for r in buckets["student"])
        fa = sorted(r["frac_all"] for r in buckets["student"])
        print(f"\n  student serving fraction, CONNECTED-ONLY (reported, not a filter)")
        print(f"    min/median/max: {fc[0]:.3f} / {fc[len(fc)//2]:.3f} / {fc[-1]:.3f}")
        print(f"  student serving fraction, ALL TICKS")
        print(f"    min/median/max: {fa[0]:.3f} / {fa[len(fa)//2]:.3f} / {fa[-1]:.3f}")

        # Evidence for WHY the all-tick fraction is not usable as a gate: it
        # should track trial length, and trial length tracks survival.
        drop = [r for r in buckets["student"] if r["frac_all"] < SERVE_BAR]
        if drop:
            surv_drop = sum(1 for r in drop if r["survived"])
            keep = [r for r in buckets["student"] if r["frac_all"] >= SERVE_BAR]
            surv_keep = sum(1 for r in keep if r["survived"])
            print(f"\n  the ABANDONED all-tick gate would have dropped {len(drop)} "
                  f"student trials ({surv_drop}/{len(drop)} survived) and kept "
                  f"{len(keep)} ({surv_keep}/{len(keep)} survived)")
            print("    -> a survival-rate difference here is the outcome-selection "
                  "the gate was abandoned to avoid")

    # ---- outcomes, split by fixture ----
    included = buckets["student"] + buckets["control"]
    fixtures = sorted({Path(str(r["fixture"])).name for r in included if r["fixture"]})
    print(f"\nfixtures seen: {fixtures}")

    # ---- prereg 5b: common capture budget across ALL included trials ----
    cap_counts = [r["captures"] for r in included if r["captures"]]
    K = min(cap_counts) if cap_counts else 0
    print(f"\ncaptures_used per arm (duration confound check):")
    for nm in ("student", "control"):
        cs = sorted(r["captures"] for r in buckets[nm] if r["captures"])
        if cs:
            print(f"  {nm:<8} n={len(cs)} min={cs[0]} median={cs[len(cs)//2]} max={cs[-1]}")
    print(f"  common prefix budget K = {K} captures")
    for r in included:
        r["cells_K"] = prefix_cells(r["run_id"], args.wave, K)

    for fx in fixtures:
        s = [r for r in buckets["student"] if Path(str(r["fixture"])).name == fx]
        c = [r for r in buckets["control"] if Path(str(r["fixture"])).name == fx]
        sv = [r["cells"] for r in s if r["cells"] is not None]
        cv = [r["cells"] for r in c if r["cells"] is not None]
        print(f"\n=== FIXTURE {fx} ===")
        print("PRIMARY -- cells holding 50% of wave-17 captures")
        print(summarise("student", sv))
        print(summarise("control", cv))
        if sv and cv:
            d = statistics.mean(sv) - statistics.mean(cv)
            sd_c = statistics.stdev(cv) if len(cv) > 1 else float("nan")
            print(f"  effect d = {d:+.2f} cells")
            if not math.isnan(sd_c) and sd_c > 0:
                print(f"  control sd (this campaign) = {sd_c:.3f}  -> d = {d/sd_c:+.2f} control sd")
            print(f"  prereg bars: GO >= +{GO_BAR:.2f}   NO-GO <= +{NOGO_BAR:.2f}")
            verdict = ("GO" if d >= GO_BAR else
                       "NO-GO (close the line)" if d <= NOGO_BAR else "AMBIGUOUS")

            # prereg 5b: common-prefix sensitivity, binding only to downgrade.
            svk = [r["cells_K"] for r in s if r.get("cells_K") is not None]
            cvk = [r["cells_K"] for r in c if r.get("cells_K") is not None]
            print(f"\n  SENSITIVITY at common K captures (prereg 5b)")
            print(summarise("student", svk))
            print(summarise("control", cvk))
            if svk and cvk:
                dk = statistics.mean(svk) - statistics.mean(cvk)
                print(f"  effect d_K = {dk:+.2f} cells")
                if (d > 0) != (dk > 0) and abs(d) > 1e-9 and abs(dk) > 1e-9:
                    print("  !! full-length and common-prefix effects DISAGREE IN SIGN")
                    if verdict == "GO":
                        verdict = "AMBIGUOUS (GO downgraded by 5b sign disagreement)"
                    elif verdict == "AMBIGUOUS":
                        verdict = "AMBIGUOUS (sign disagreement)"
            # prereg 5c: PER-PROTOCOL sensitivity -- student trials that
            # actually served >=80% of their CONNECTED ticks.
            spp = [r["cells"] for r in s
                   if r.get("frac", 0) >= SERVE_BAR and r["cells"] is not None]
            print(f"\n  SENSITIVITY per-protocol, connected-fraction >= {SERVE_BAR} (prereg 5c)")
            print(summarise("student", spp))
            print(f"  {'control':<10} unchanged (control never serves)")
            if spp and cv:
                dpp = statistics.mean(spp) - statistics.mean(cv)
                print(f"  effect d_pp = {dpp:+.2f} cells  "
                      f"({len(spp)}/{len(sv)} student trials retained)")
                if (d > 0) != (dpp > 0) and abs(d) > 1e-9 and abs(dpp) > 1e-9:
                    print("  !! intention-to-treat and per-protocol DISAGREE IN SIGN")
                    if verdict.startswith("GO"):
                        verdict = "AMBIGUOUS (GO downgraded by 5c sign disagreement)"

            print(f"\n  >>> {verdict}")

        print("\nGUARDS (reported, not gating)")
        for nm, arm in (("student", s), ("control", c)):
            # `survived` comes from wp2_confinement's own reading of the run
            # (wave-18 captures present), not from a result string.
            wins = sum(1 for r in arm if r.get("survived"))
            dmg = [r["damage"] for r in arm if isinstance(r["damage"], (int, float))]
            dtxt = f"{statistics.median(dmg):.0f}" if dmg else "n/a"
            print(f"  {nm:<8} survived wave 17: {wins}/{len(arm)}   "
                  f"median gross damage {dtxt}")
        print("  (gross damage never subtracts healing -- reported component only)")

    print("\nBASELINES for reference (archived, mod 0.2.55, fixture A):")
    print("  agent control n=6: [7, 19, 13, 17, 10, 12] mean 13.00 sd 4.427")
    print("  human       n=6: mean 27.50 sd 1.871")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
