#!/usr/bin/env python3
"""Monte-Carlo calibration of the champion/challenger sequential release gate.

Context. Every behavioural policy version from ~v84 to v128 shipped on ONE smoke
run plus internal audits. That procedure has no power against a 20-point win-rate
regression, and the agent's win rate fell ~20-25 points across ~45 versions without
anything firing. This script sizes the replacement.

The design is a Bayesian sequential test of a candidate against a frozen champion:

    reject   when P(p_cand <= p_champ - INDIFFERENCE) >= reject_threshold
    promote  when P(p_cand >= p_champ - TOLERANCE)    >= promote_threshold
    else continue, up to a hard cap; hitting the cap is INCONCLUSIVE = DO NOT SHIP.

The point most easily got wrong: the champion's rate is NOT known. It is estimated
from a finite champion bank, so p_champ carries its own posterior. Treating it as
known overstates the gate's power. Both modes are simulated here so the cost of
that uncertainty is explicit.

Outputs operating characteristics; nothing here touches the game or the policy.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict

import numpy as np


@dataclass
class GateSpec:
    indifference: float = 0.20   # a candidate this far below champion is unacceptable
    tolerance: float = 0.05      # promote only if candidate is plausibly within this
    reject_threshold: float = 0.90
    promote_threshold: float = 0.90
    cap: int = 30                # max candidate runs
    min_runs: int = 6            # no decision before this many
    prior_a: float = 1.0
    prior_b: float = 1.0


def simulate(spec: GateSpec, p_true: float, p_champ_true: float,
             champ_bank: int | None, rng: np.random.Generator,
             trials: int = 4000, grid: int = 400) -> dict:
    """Return operating characteristics for a candidate whose true rate is p_true.

    champ_bank=None models the champion rate as exactly known (optimistic);
    an integer models it as estimated from that many observed champion runs.
    """
    xs = np.linspace(1e-6, 1 - 1e-6, grid)
    outcomes = {"promote": 0, "reject": 0, "inconclusive": 0}
    stop_runs: list[int] = []

    for _ in range(trials):
        if champ_bank is None:
            champ_lo = champ_hi = p_champ_true
            champ_wins = None
        else:
            champ_wins = rng.binomial(champ_bank, p_champ_true)

        wins = 0
        decided = False
        for n in range(1, spec.cap + 1):
            wins += int(rng.random() < p_true)
            if n < spec.min_runs:
                continue

            # posterior over the candidate's rate
            a = spec.prior_a + wins
            b = spec.prior_b + (n - wins)
            cand_pdf = xs ** (a - 1) * (1 - xs) ** (b - 1)
            cand_pdf /= cand_pdf.sum()

            if champ_bank is None:
                # champion known: thresholds are fixed points
                p_below = cand_pdf[xs <= p_champ_true - spec.indifference].sum()
                p_within = cand_pdf[xs >= p_champ_true - spec.tolerance].sum()
            else:
                # champion uncertain: integrate over its posterior too
                ca = spec.prior_a + champ_wins
                cb = spec.prior_b + (champ_bank - champ_wins)
                champ_pdf = xs ** (ca - 1) * (1 - xs) ** (cb - 1)
                champ_pdf /= champ_pdf.sum()
                # P(cand <= champ - delta) over the joint (independent) posterior
                diff = xs[:, None] - xs[None, :]          # cand - champ
                joint = cand_pdf[:, None] * champ_pdf[None, :]
                p_below = joint[diff <= -spec.indifference].sum()
                p_within = joint[diff >= -spec.tolerance].sum()

            if p_below >= spec.reject_threshold:
                outcomes["reject"] += 1
                stop_runs.append(n)
                decided = True
                break
            if p_within >= spec.promote_threshold:
                outcomes["promote"] += 1
                stop_runs.append(n)
                decided = True
                break
        if not decided:
            outcomes["inconclusive"] += 1
            stop_runs.append(spec.cap)

    tot = float(trials)
    return {
        "p_true": p_true,
        "promote": outcomes["promote"] / tot,
        "reject": outcomes["reject"] / tot,
        "inconclusive": outcomes["inconclusive"] / tot,
        "mean_runs": float(np.mean(stop_runs)),
        "median_runs": float(np.median(stop_runs)),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--champion-rate", type=float, default=0.50,
                    help="true champion win rate to simulate against")
    ap.add_argument("--champ-bank", type=int, default=36,
                    help="champion control runs; 0 means treat champion as known")
    ap.add_argument("--trials", type=int, default=4000)
    ap.add_argument("--cap", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20260726)
    ap.add_argument("--json", type=str, default=None)
    args = ap.parse_args()

    spec = GateSpec(cap=args.cap)
    rng = np.random.default_rng(args.seed)
    bank = None if args.champ_bank == 0 else args.champ_bank
    pc = args.champion_rate

    # candidate truths worth knowing the behaviour at
    truths = [
        (pc + 0.10, "clearly better"),
        (pc,        "identical to champion"),
        (pc - 0.10, "mildly worse"),
        (pc - 0.20, "unacceptable (the indifference point)"),
        (pc - 0.30, "badly broken"),
    ]

    print(f"champion true rate = {pc:.2f}   champion bank = "
          f"{'KNOWN (infinite)' if bank is None else bank}   cap = {spec.cap}")
    print(f"gate: reject if P(cand <= champ-{spec.indifference:.2f}) >= {spec.reject_threshold}; "
          f"promote if P(cand >= champ-{spec.tolerance:.2f}) >= {spec.promote_threshold}; "
          f"min {spec.min_runs} runs")
    print()
    hdr = f"{'candidate truth':38s} {'promote':>8s} {'reject':>8s} {'inconcl':>8s} {'mean n':>7s} {'med n':>6s}"
    print(hdr)
    print("-" * len(hdr))
    rows = []
    for p, label in truths:
        p = min(max(p, 0.01), 0.99)
        r = simulate(spec, p, pc, bank, rng, trials=args.trials)
        r["label"] = label
        rows.append(r)
        print(f"{label + f'  (p={p:.2f})':38s} {r['promote']:8.3f} {r['reject']:8.3f} "
              f"{r['inconclusive']:8.3f} {r['mean_runs']:7.1f} {r['median_runs']:6.0f}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"spec": asdict(spec), "champion_rate": pc,
                       "champ_bank": args.champ_bank, "rows": rows}, fh, indent=2)
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
