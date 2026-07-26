#!/usr/bin/env python3
"""Champion/challenger release gate — the decision tool, not the calibration.

Replaces "one smoke run + audits report zero violations", which allowed a
47-percentage-point win-rate collapse (69.7% -> 22.6%, Fisher p=8.9e-09) to persist
across roughly twenty policy versions undetected. That procedure had no power against
a win-rate change at all: it tested internal rule compliance on a single run.

Reads a frozen champion bank and a candidate's runs so far, and returns one of
PROMOTE / REJECT / CONTINUE / INCONCLUSIVE.

The decision rule, over independent Beta posteriors for champion and candidate:

    REJECT   when P(p_cand <= p_champ - INDIFFERENCE) >= reject_threshold
    PROMOTE  when P(p_cand >= p_champ - TOLERANCE)    >= promote_threshold
    CONTINUE otherwise, until the cap
    INCONCLUSIVE at the cap -- WHICH MEANS DO NOT SHIP.

That last line is the whole design. Calibration (scripts/wp2_gate_calibration.py,
champion 50%, 36-run bank, cap 30) shows this gate promotes a truly 20-point-worse
candidate only ~5.7% of the time, but promotes a genuinely good one just 40-65% of
the time. It is SAFE rather than POWERFUL, and treating "inconclusive" as a block is
what converts that low power into conservatism instead of risk. The cost is shipping
velocity, which is the correct place to pay: this project lost its win rate by
shipping freely, not by shipping slowly.

Two consequences worth stating because they are easy to get wrong:
  - The champion's rate is NOT known. It is estimated from a finite bank, and that
    uncertainty is integrated over here. Treating it as known overstates power
    (a known champion promotes a clearly-better candidate 81.5% of the time vs
    64.7% off a 36-run bank).
  - Because a single gate can cost up to ~30 runs and often ends inconclusive, you
    cannot gate two behavioural versions a week. Batch behavioural changes into one
    challenger.

This tool decides ONE of three independent gates. It does not replace:
  Gate 1 EXECUTABILITY AND DETERMINISM -- parse/load, schema, action legality, identity
  Gate 2 MECHANISTIC CONSTRAINTS      -- intended feature activates, no hard-rule breach
  Gate 3 OUTCOME                      -- this file
Gate 2 can never substitute for Gate 3 again.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

INDIFFERENCE = 0.20   # a candidate this far below champion is unacceptable
TOLERANCE = 0.05      # promote only if candidate is plausibly within this of champion
REJECT_THRESHOLD = 0.90
PROMOTE_THRESHOLD = 0.90
DEFAULT_CAP = 30
MIN_RUNS = 6
GRID = 600


def _posterior(wins: int, n: int, xs: np.ndarray) -> np.ndarray:
    a, b = 1.0 + wins, 1.0 + (n - wins)
    pdf = xs ** (a - 1) * (1 - xs) ** (b - 1)
    return pdf / pdf.sum()


def decide(champ_wins: int, champ_n: int, cand_wins: int, cand_n: int,
           cap: int = DEFAULT_CAP) -> dict:
    xs = np.linspace(1e-6, 1 - 1e-6, GRID)
    champ = _posterior(champ_wins, champ_n, xs)
    cand = _posterior(cand_wins, cand_n, xs)

    diff = xs[:, None] - xs[None, :]          # candidate - champion
    joint = cand[:, None] * champ[None, :]
    p_below = float(joint[diff <= -INDIFFERENCE].sum())
    p_within = float(joint[diff >= -TOLERANCE].sum())

    if cand_n < MIN_RUNS:
        verdict = "CONTINUE"
        reason = f"only {cand_n} candidate runs; minimum is {MIN_RUNS}"
    elif p_below >= REJECT_THRESHOLD:
        verdict = "REJECT"
        reason = (f"P(candidate <= champion-{INDIFFERENCE:.2f}) = {p_below:.3f} "
                  f">= {REJECT_THRESHOLD}")
    elif p_within >= PROMOTE_THRESHOLD:
        verdict = "PROMOTE"
        reason = (f"P(candidate >= champion-{TOLERANCE:.2f}) = {p_within:.3f} "
                  f">= {PROMOTE_THRESHOLD}")
    elif cand_n >= cap:
        verdict = "INCONCLUSIVE"
        reason = (f"reached cap of {cap} runs without a decision -- DO NOT SHIP. "
                  f"P(worse)={p_below:.3f}, P(acceptable)={p_within:.3f}")
    else:
        verdict = "CONTINUE"
        reason = (f"undecided at {cand_n}/{cap} runs. "
                  f"P(worse)={p_below:.3f}, P(acceptable)={p_within:.3f}")

    return {
        "verdict": verdict,
        "reason": reason,
        "champion": {"wins": champ_wins, "n": champ_n,
                     "rate": champ_wins / champ_n if champ_n else None},
        "candidate": {"wins": cand_wins, "n": cand_n,
                      "rate": cand_wins / cand_n if cand_n else None},
        "p_candidate_materially_worse": p_below,
        "p_candidate_acceptable": p_within,
        "runs_remaining": max(0, cap - cand_n),
    }


def _count_from_report(path: Path) -> tuple[int, int]:
    """Count wins/total from a collector report file's results[] block."""
    data = json.loads(path.read_text(encoding="utf-8"))
    results = data.get("results", [])
    scored = [r for r in results if r.get("result") in ("victory", "defeat")]
    wins = sum(1 for r in scored if r.get("result") == "victory")
    return wins, len(scored)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--champion-report", type=Path,
                    help="collector report JSON for the frozen champion bank")
    ap.add_argument("--candidate-report", type=Path,
                    help="collector report JSON for the candidate so far")
    ap.add_argument("--champion", type=str, help="override as WINS/N, e.g. 19/36")
    ap.add_argument("--candidate", type=str, help="override as WINS/N")
    ap.add_argument("--cap", type=int, default=DEFAULT_CAP)
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args()

    def parse(spec: str) -> tuple[int, int]:
        w, n = spec.split("/")
        return int(w), int(n)

    if args.champion:
        cw, cn = parse(args.champion)
    elif args.champion_report:
        cw, cn = _count_from_report(args.champion_report)
    else:
        ap.error("need --champion or --champion-report")

    if args.candidate:
        dw, dn = parse(args.candidate)
    elif args.candidate_report:
        dw, dn = _count_from_report(args.candidate_report)
    else:
        dw, dn = 0, 0

    if cn < 20:
        print(f"WARNING: champion bank is only {cn} runs. Calibration assumed ~36; "
              f"a thinner bank materially reduces the gate's power.\n")

    out = decide(cw, cn, dw, dn, cap=args.cap)
    print(f"champion  : {cw}/{cn}" + (f" = {100*cw/cn:.1f}%" if cn else ""))
    print(f"candidate : {dw}/{dn}" + (f" = {100*dw/dn:.1f}%" if dn else ""))
    print(f"\nVERDICT   : {out['verdict']}")
    print(f"reason    : {out['reason']}")
    if out["verdict"] == "INCONCLUSIVE":
        print("\nINCONCLUSIVE IS A BLOCK, NOT A PASS. Do not ship on green audits.")

    if args.json:
        args.json.write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
