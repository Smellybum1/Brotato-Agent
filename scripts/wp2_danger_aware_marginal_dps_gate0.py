#!/usr/bin/env python3
"""§37 Gate 0: target-free danger-aware marginal-DPS buy override.

Implements reports/wp2/danger_aware_marginal_dps_prereg.md.  The analysis is
read-only.  It replays the 16 instrumented 0.2.79 D5 ranger runs, validates the
held loadout against recorded build metrics, prices every scored candidate on
trusted free-slot buy decisions, and applies the preregistered score doses.

Usage:
    python scripts/wp2_danger_aware_marginal_dps_gate0.py --runs-dir PATH
    python scripts/wp2_danger_aware_marginal_dps_gate0.py --self-test
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.wp2_offer_dps_replay import (
    LoadoutReconstructor,
    apply_deltas,
    build_metrics_stats,
    combined_id,
    combat_deltas,
    effective_weapon_dps,
    sig_ids,
    tier_of,
    total_effective_weapon_dps,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MOD = "0.2.79-wp2-capture"
CHARACTER = "character_ranger"
DANGER = 5
WAVE_MIN = 1
WAVE_MAX = 11
DOSES = (0.0, 0.5, 1.0, 2.0, 4.0)
EXPECTED_RUNS = 16
EXPECTED_UNLOCK = (179, 48, "2018397571", "1530875081")

JOIN_BAR = 0.99
TRUST_BAR = 0.95
PARITY_BAR = 0.99
REPRO_BAR = 0.99
SURFACE_BAR = 0.20
FLIP_BAR = 0.20
MEDIAN_GAIN_BAR = 5.0
POSITIVE_FLIP_BAR = 0.90
PER_RUN_UPPER_BAR = 0.33
TOL = 1e-9

# Ranger's character effect, source-noted in combat_model.gd:161.  Only the
# offense-relevant gain modifier is needed here.
RANGER_GAIN_MODS = {"stat_ranged_damage": 50.0}
KNOWN_CURRENT_STATS = frozenset({
    "stat_ranged_damage", "stat_percent_damage", "stat_attack_speed",
    "stat_crit_chance",
})
UNKNOWN_DPS_STATE = frozenset({"stat_crit_damage"})


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    vals = sorted(values)
    pos = (len(vals) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return vals[lo]
    return vals[lo] * (hi - pos) + vals[hi] * (pos - lo)


def _summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "min": min(values),
        "p25": _pct(values, 0.25),
        "median": statistics.median(values),
        "p75": _pct(values, 0.75),
        "max": max(values),
    }


def _unlock_stamp(summary: dict[str, Any]) -> tuple[Any, ...]:
    pool = summary.get("unlock_pool") or {}
    return (pool.get("items"), pool.get("weapons"),
            str(pool.get("items_hash")), str(pool.get("weapons_hash")))


def _read_relevant_events(path: Path) -> list[dict[str, Any]]:
    wanted = ('"run_start"', '"purchase_offer"', '"purchase_decision"',
              '"shop_combine_confirmed"', '"run_end"')
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for line in stream:
            if not any(token in line for token in wanted):
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _weapon_record(item: dict[str, Any]) -> dict[str, Any]:
    return {key: item.get(key) for key in (
        "damage", "cooldown", "scaling", "crit_chance", "crit_damage",
        "nb_projectiles", "piercing", "piercing_dmg_reduction", "bounce",
        "bounce_dmg_reduction", "sets", "burning",
    )}


def _harvest_catalog(runs: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    for events in runs.values():
        for event in events:
            if event.get("event") != "purchase_offer":
                continue
            for item in (event.get("payload") or {}).get("items", []) or []:
                if item.get("category") == "weapon" and item.get("id"):
                    record = _weapon_record(item)
                    old = catalog.get(str(item["id"]))
                    if old is not None and old != record:
                        raise RuntimeError(f"weapon catalog disagreement for {item['id']}")
                    catalog[str(item["id"])] = record
    return catalog


def _scored_rows(board_scores: Any) -> tuple[list[dict[str, Any]], bool]:
    if not isinstance(board_scores, list):
        return [], False
    truncated = any(isinstance(row, dict) and row.get("truncated") for row in board_scores)
    rows = [row for row in board_scores if isinstance(row, dict)
            and row.get("skipped") in (None, "") and _is_number(row.get("score"))]
    return rows, truncated


def _argmax(rows: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    if not rows:
        return None
    best = rows[0]
    for row in rows[1:]:
        if float(row[key]) > float(best[key]) + TOL:
            best = row
    return best


def _join_rows(rows: list[dict[str, Any]], offer: dict[str, Any] | None
               ) -> tuple[dict[tuple[int, str], dict[str, Any]], int]:
    if offer is None:
        return {}, len(rows)
    items = (offer.get("items") or []) if isinstance(offer, dict) else []
    by_key = {(int(item.get("slot", -1)), str(item.get("id", ""))): item
              for item in items if isinstance(item, dict)}
    joined: dict[tuple[int, str], dict[str, Any]] = {}
    missing = 0
    for row in rows:
        key = (int(row.get("slot", -1)), str(row.get("id", "")))
        if key not in by_key:
            missing += 1
        else:
            joined[key] = by_key[key]
    return joined, missing


def _item_gain(item: dict[str, Any], loadout: list[str], catalog: dict[str, dict[str, Any]],
               stats: dict[str, Any]) -> tuple[float | None, str]:
    effects = item.get("effects", []) or []
    deltas = combat_deltas(effects)
    if set(deltas) & UNKNOWN_DPS_STATE:
        return None, "unknown_current_stat"
    modeled = {key: value for key, value in deltas.items() if key in KNOWN_CURRENT_STATS}
    if not modeled:
        return 0.0, "no_modeled_weapon_dps_effect"
    if any(weapon_id not in catalog for weapon_id in loadout):
        return None, "catalog_incomplete"
    weapons = [catalog[weapon_id] for weapon_id in loadout]
    before = total_effective_weapon_dps(weapons, stats)
    after_stats = apply_deltas(stats, modeled, RANGER_GAIN_MODS)
    after = total_effective_weapon_dps(weapons, after_stats)
    return after - before, "item_stats"


def _weapon_gain(item: dict[str, Any], row: dict[str, Any], loadout: list[str],
                 catalog: dict[str, dict[str, Any]], stats: dict[str, Any]
                 ) -> tuple[float | None, str]:
    item_id = str(item.get("id", ""))
    if item_id not in catalog:
        return None, "catalog_incomplete"
    if bool(row.get("pairs_combine")):
        if item_id not in loadout:
            return None, "pair_not_in_loadout"
        next_id = combined_id(item_id)
        if next_id not in catalog:
            return None, "next_tier_missing"
        gain = (effective_weapon_dps(catalog[next_id], stats)
                - effective_weapon_dps(catalog[item_id], stats))
        return gain, "combine"
    return effective_weapon_dps(catalog[item_id], stats), "weapon_add"


def _price_rows(rows: list[dict[str, Any]], joined: dict[tuple[int, str], dict[str, Any]],
                loadout: list[str], catalog: dict[str, dict[str, Any]],
                stats: dict[str, Any], current_dps: float
                ) -> tuple[list[dict[str, Any]] | None, Counter,
                           list[tuple[float, float, str]]]:
    priced: list[dict[str, Any]] = []
    reasons: Counter = Counter()
    parity: list[tuple[float, float, str]] = []
    for row in rows:
        key = (int(row.get("slot", -1)), str(row.get("id", "")))
        item = joined.get(key)
        if item is None:
            reasons["join_missing"] += 1
            return None, reasons, parity
        if row.get("category") == "weapon":
            gain, method = _weapon_gain(item, row, loadout, catalog, stats)
            if method == "weapon_add" and _is_number(row.get("proj_dps_gain")) and gain is not None:
                parity.append((gain, float(row["proj_dps_gain"]), str(row.get("id", ""))))
        else:
            gain, method = _item_gain(item, loadout, catalog, stats)
        if gain is None:
            reasons[method] += 1
            return None, reasons, parity
        copy = dict(row)
        copy["gain"] = float(gain)
        copy["m"] = 100.0 * float(gain) / max(float(current_dps), 1.0)
        copy["gain_method"] = method
        priced.append(copy)
    return priced, reasons, parity


@dataclass
class Decision:
    run_id: str
    wave: int
    incumbent_id: str
    current_dps: float
    rows: list[dict[str, Any]]
    reachable: bool


@dataclass
class Analysis:
    run_ids: list[str] = field(default_factory=list)
    arm_errors: list[str] = field(default_factory=list)
    policy_by_run: Counter = field(default_factory=Counter)
    exclusions: Counter = field(default_factory=Counter)
    row_join_total: int = 0
    row_join_ok: int = 0
    otherwise_eligible: int = 0
    trusted_eligible: int = 0
    parity_total: int = 0
    parity_ok: int = 0
    parity_failures: list[dict[str, Any]] = field(default_factory=list)
    repro_total: int = 0
    repro_ok: int = 0
    gain_failures: Counter = field(default_factory=Counter)
    decisions: list[Decision] = field(default_factory=list)

    @property
    def policy_n(self) -> int:
        return sum(self.policy_by_run.values())


def _load_target_runs(runs_dir: Path) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    summaries: dict[str, dict[str, Any]] = {}
    for summary_path in runs_dir.glob("*/summary.json"):
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(summary.get("mod_version")) == MOD:
            summaries[summary_path.parent.name] = summary
    events = {run_id: _read_relevant_events(runs_dir / run_id / "events.jsonl")
              for run_id in summaries}
    return summaries, events


def analyse(runs_dir: Path) -> Analysis:
    summaries, runs = _load_target_runs(runs_dir)
    out = Analysis(run_ids=sorted(summaries))
    for run_id, summary in summaries.items():
        if summary.get("result") not in ("victory", "defeat"):
            out.arm_errors.append(f"{run_id}: nonterminal result {summary.get('result')!r}")
        if int(summary.get("danger", -1)) != DANGER or not bool(summary.get("danger_ok")):
            out.arm_errors.append(f"{run_id}: danger validity")
        if str(summary.get("character")) != CHARACTER or not bool(summary.get("character_ok")):
            out.arm_errors.append(f"{run_id}: character validity")
        if _unlock_stamp(summary) != EXPECTED_UNLOCK:
            out.arm_errors.append(f"{run_id}: unlock stamp {_unlock_stamp(summary)!r}")

    catalog = _harvest_catalog(runs)
    recon = LoadoutReconstructor(catalog)

    for run_id in sorted(runs):
        events = runs[run_id]
        start_weapon = next(((event.get("payload") or {}).get("weapon") for event in events
                             if event.get("event") == "run_start"), None)
        # Ranger's actual initial loadout is two copies of the selected pistol:
        # first-shop count/tier/DPS controls agree on all 16 source runs.  The
        # run_start field names the selected id once; §37j records the recovery.
        loadout: list[str] = ([str(start_weapon), str(start_weapon)]
                              if start_weapon else [])
        last_offer: dict[str, Any] | None = None

        for event in events:
            kind = event.get("event")
            payload = event.get("payload") or {}
            if kind == "purchase_offer":
                last_offer = payload
                continue
            if kind == "shop_combine_confirmed" and payload.get("state_changed"):
                loadout = sig_ids(payload.get("after_signature", "[]"))
                continue
            if kind != "purchase_decision":
                continue

            action = payload.get("action") or {}
            wave = int(payload.get("wave", -1))
            offense = ((payload.get("build_metrics") or {}).get("offense") or {})
            stats = build_metrics_stats(offense)
            trusted = recon.validate(loadout, stats, offense.get("weapon_dps"),
                                     offense.get("weapon_count"), offense.get("weapon_tier_sum"))
            if not trusted:
                fixed = recon.reconcile(loadout, stats, offense.get("weapon_dps"),
                                        offense.get("weapon_count"), offense.get("weapon_tier_sum"))
                if fixed is not None:
                    loadout = fixed
                    trusted = True

            is_policy_buy = action.get("type") == "shop_buy" and WAVE_MIN <= wave <= WAVE_MAX
            if is_policy_buy:
                out.policy_by_run[run_id] += 1
                board_meta = payload.get("board_meta") or {}
                rows, truncated = _scored_rows(payload.get("board_scores"))
                if bool(board_meta.get("slots_full")):
                    out.exclusions["slots_full"] += 1
                elif truncated:
                    out.exclusions["board_truncated"] += 1
                elif not rows:
                    out.exclusions["no_scored_rows"] += 1
                else:
                    out.otherwise_eligible += 1
                    joined, missing = _join_rows(rows, last_offer)
                    out.row_join_total += len(rows)
                    out.row_join_ok += len(rows) - missing
                    if missing:
                        out.exclusions["offer_join_failed"] += 1
                    elif not trusted:
                        out.exclusions["loadout_untrusted"] += 1
                    else:
                        out.trusted_eligible += 1
                        current_dps = float(offense.get("weapon_dps", 0.0))
                        priced, failures, parity = _price_rows(
                            rows, joined, loadout, catalog, stats, current_dps)
                        out.gain_failures.update(failures)
                        for computed, recorded, item_id in parity:
                            out.parity_total += 1
                            allowed = max(0.01, 0.01 * abs(recorded))
                            passed = abs(computed - recorded) <= allowed
                            out.parity_ok += int(passed)
                            if not passed and len(out.parity_failures) < 30:
                                out.parity_failures.append({
                                    "run_id": run_id, "wave": wave, "item_id": item_id,
                                    "computed": computed, "recorded": recorded,
                                    "abs_error": abs(computed - recorded),
                                })
                        if priced is None:
                            out.exclusions["gain_uncomputable"] += 1
                        else:
                            incumbent = _argmax(priced, "score")
                            out.repro_total += 1
                            action_id = str(action.get("item_id", ""))
                            matches = incumbent is not None and str(incumbent.get("id")) == action_id
                            out.repro_ok += int(matches)
                            if not matches:
                                out.exclusions["baseline_mismatch"] += 1
                            else:
                                incumbent_m = float(incumbent["m"])
                                reachable = any(float(row["m"]) > incumbent_m + TOL for row in priced)
                                out.decisions.append(Decision(
                                    run_id=run_id, wave=wave, incumbent_id=action_id,
                                    current_dps=current_dps, rows=priced, reachable=reachable))

            # Apply the actual action after measuring its pre-decision state.
            if action.get("type") == "shop_buy" and last_offer:
                chosen = next((item for item in last_offer.get("items", []) or []
                               if item.get("slot") == action.get("slot")), None)
                if chosen and chosen.get("category") == "weapon":
                    loadout.append(str(chosen.get("id")))
            elif action.get("type") == "shop_sell":
                index = action.get("index")
                if isinstance(index, int) and 0 <= index < len(loadout):
                    loadout.pop(index)
    return out


def dose_result(analysis: Analysis, dose: float) -> dict[str, Any]:
    flips: list[dict[str, Any]] = []
    per_run: Counter = Counter({run_id: 0.0 for run_id in analysis.run_ids})
    selected_m: list[float] = []
    for decision in analysis.decisions:
        dosed_rows = []
        for row in decision.rows:
            copy = dict(row)
            copy["dosed_score"] = float(row["score"]) + dose * float(row["m"])
            dosed_rows.append(copy)
        old = _argmax(dosed_rows, "score")
        new = _argmax(dosed_rows, "dosed_score")
        assert old is not None and new is not None
        selected_m.append(float(new["m"]))
        if str(new.get("id")) == str(old.get("id")):
            continue
        delta_m = float(new["m"]) - float(old["m"])
        per_run[decision.run_id] += delta_m / 100.0
        flips.append({
            "run_id": decision.run_id,
            "wave": decision.wave,
            "old_id": str(old.get("id")),
            "new_id": str(new.get("id")),
            "old_category": str(old.get("category")),
            "new_category": str(new.get("category")),
            "old_m": float(old["m"]),
            "new_m": float(new["m"]),
            "delta_m": delta_m,
            "score_sacrificed": float(old["score"]) - float(new["score"]),
            "new_method": str(new.get("gain_method")),
        })
    deltas = [row["delta_m"] for row in flips]
    upper = [per_run[run_id] for run_id in analysis.run_ids]
    return {
        "dose": dose,
        "policy_n": analysis.policy_n,
        "eligible_dosed_n": len(analysis.decisions),
        "flips": len(flips),
        "flip_rate_policy": len(flips) / max(analysis.policy_n, 1),
        "flip_rate_eligible": len(flips) / max(len(analysis.decisions), 1),
        "positive_flips": sum(delta > TOL for delta in deltas),
        "positive_flip_share": (sum(delta > TOL for delta in deltas) / len(deltas)
                                if deltas else None),
        "delta_m": _summary(deltas),
        "per_run_upper": _summary(upper),
        "flips_detail": flips,
        "selected_m": selected_m,
    }


def _controls(analysis: Analysis) -> tuple[dict[str, Any], list[str]]:
    join_rate = analysis.row_join_ok / max(analysis.row_join_total, 1)
    trust_rate = analysis.trusted_eligible / max(analysis.otherwise_eligible, 1)
    parity_rate = analysis.parity_ok / max(analysis.parity_total, 1)
    repro_rate = analysis.repro_ok / max(analysis.repro_total, 1)
    failures: list[str] = []
    if len(analysis.run_ids) != EXPECTED_RUNS:
        failures.append(f"run_count {len(analysis.run_ids)} != {EXPECTED_RUNS}")
    failures.extend(analysis.arm_errors)
    if join_rate < JOIN_BAR:
        failures.append(f"join_rate {join_rate:.4f} < {JOIN_BAR:.2f}")
    if trust_rate < TRUST_BAR:
        failures.append(f"trust_rate {trust_rate:.4f} < {TRUST_BAR:.2f}")
    if not analysis.parity_total or parity_rate < PARITY_BAR:
        failures.append(f"parity_rate {parity_rate:.4f} < {PARITY_BAR:.2f}")
    if repro_rate < REPRO_BAR:
        failures.append(f"repro_rate {repro_rate:.4f} < {REPRO_BAR:.2f}")
    null = dose_result(analysis, 0.0)
    if null["flips"] != 0:
        failures.append(f"null dose flipped {null['flips']}")
    return {
        "run_count": len(analysis.run_ids),
        "arm_errors": analysis.arm_errors,
        "policy_n": analysis.policy_n,
        "policy_by_run": dict(analysis.policy_by_run),
        "exclusions": dict(analysis.exclusions),
        "join": {"ok": analysis.row_join_ok, "total": analysis.row_join_total,
                 "rate": join_rate, "bar": JOIN_BAR},
        "loadout_trust": {"ok": analysis.trusted_eligible,
                          "total": analysis.otherwise_eligible,
                          "rate": trust_rate, "bar": TRUST_BAR},
        "weapon_gain_parity": {"ok": analysis.parity_ok, "total": analysis.parity_total,
                               "rate": parity_rate, "bar": PARITY_BAR,
                               "failures": analysis.parity_failures},
        "baseline_reproduction": {"ok": analysis.repro_ok, "total": analysis.repro_total,
                                  "rate": repro_rate, "bar": REPRO_BAR},
        "gain_failures": dict(analysis.gain_failures),
        "null_flips": null["flips"],
    }, failures


def build_result(analysis: Analysis) -> dict[str, Any]:
    controls, failures = _controls(analysis)
    if failures:
        return {"status": "VOID", "control_failures": failures, "controls": controls}

    reachable = sum(decision.reachable for decision in analysis.decisions)
    reachable_rate = reachable / max(analysis.policy_n, 1)
    dose_rows = [dose_result(analysis, dose) for dose in DOSES]

    monotone = True
    previous_flips = -1
    previous_selected: list[float] | None = None
    for row in dose_rows:
        if row["flips"] < previous_flips:
            monotone = False
        if previous_selected is not None:
            monotone &= all(cur + TOL >= prev
                            for cur, prev in zip(row["selected_m"], previous_selected))
        previous_flips = row["flips"]
        previous_selected = row["selected_m"]

    passing_doses: list[float] = []
    for row in dose_rows[1:]:
        median_gain = row["delta_m"].get("median")
        median_upper = row["per_run_upper"].get("median")
        if (row["flip_rate_policy"] >= FLIP_BAR
                and median_gain is not None and median_gain >= MEDIAN_GAIN_BAR
                and row["positive_flip_share"] is not None
                and row["positive_flip_share"] >= POSITIVE_FLIP_BAR
                and median_upper is not None and median_upper >= PER_RUN_UPPER_BAR):
            passing_doses.append(row["dose"])

    gate_a = reachable_rate >= SURFACE_BAR
    gate_b = bool(passing_doses) and monotone
    if not gate_a:
        reason = "surface_limited"
    elif not monotone:
        reason = "implementation_nonmonotone"
    elif not any(row["flip_rate_policy"] >= FLIP_BAR for row in dose_rows[1:]):
        reason = "score_margin_or_flip_limited"
    elif not any((row["delta_m"].get("median") or -math.inf) >= MEDIAN_GAIN_BAR
                 for row in dose_rows[1:]):
        reason = "magnitude_limited"
    elif not any((row["per_run_upper"].get("median") or -math.inf) >= PER_RUN_UPPER_BAR
                 for row in dose_rows[1:]):
        reason = "planning_deficit_limited"
    else:
        reason = "pass" if gate_b else "multi_bar_failure"

    for row in dose_rows:
        row.pop("selected_m", None)
    return {
        "status": "PASS" if gate_a and gate_b else "FAIL",
        "reason": reason,
        "controls": controls,
        "surface": {"reachable": reachable, "policy_n": analysis.policy_n,
                    "rate": reachable_rate, "bar": SURFACE_BAR, "pass": gate_a},
        "monotone": monotone,
        "passing_doses": passing_doses,
        "doses": dose_rows,
    }


def _print_controls(result: dict[str, Any]) -> None:
    controls = result["controls"]
    print("=" * 79)
    print("DENOMINATORS AND CONTROLS — BEFORE RESULTS")
    print("=" * 79)
    print(f"runs: {controls['run_count']} (required {EXPECTED_RUNS})")
    print(f"policy denominator — all D5 wave 1-11 shop_buy decisions: {controls['policy_n']}")
    for key, value in sorted(controls["exclusions"].items()):
        print(f"  unchanged/excluded {key:26s} {value}")
    for label, key in (("offer/row join", "join"), ("loadout trust", "loadout_trust"),
                       ("weapon-gain parity", "weapon_gain_parity"),
                       ("baseline reproduction", "baseline_reproduction")):
        row = controls[key]
        print(f"{label:24s}: {row['ok']}/{row['total']} = {row['rate']:.4f} "
              f"(bar {row['bar']:.2f})")
    print(f"null-dose flips: {controls['null_flips']} (required exactly 0)")
    print(f"positive control denominator — ordinary weapon parity rows: "
          f"{controls['weapon_gain_parity']['total']}")
    if controls["arm_errors"]:
        for error in controls["arm_errors"]:
            print(f"ARM ERROR: {error}")


def _print_results(result: dict[str, Any]) -> None:
    print("\n" + "=" * 79)
    print("PREREGISTERED RESULT")
    print("=" * 79)
    if result["status"] == "VOID":
        print("VERDICT: VOID — controls failed")
        for failure in result["control_failures"]:
            print(f"  - {failure}")
        return
    surface = result["surface"]
    print(f"Gate 0a reachable surface: {surface['reachable']}/{surface['policy_n']} = "
          f"{surface['rate']:.4f} (bar {surface['bar']:.2f}) => "
          f"{'PASS' if surface['pass'] else 'FAIL'}")
    print("\ndose  flips/policy  rate     median Δm  positive  median per-run upper")
    for row in result["doses"]:
        med = row["delta_m"].get("median")
        pos = row["positive_flip_share"]
        upper = row["per_run_upper"].get("median")
        print(f"{row['dose']:>4.1f}  {row['flips']:>4}/{row['policy_n']:<4}   "
              f"{row['flip_rate_policy']:.4f}  "
              f"{med if med is not None else 'n/a':>9}  "
              f"{pos if pos is not None else 'n/a':>8}  "
              f"{upper if upper is not None else 'n/a'}")
    print(f"\nmonotone: {result['monotone']}")
    print(f"passing doses: {result['passing_doses']}")
    print(f"VERDICT: {result['status']} — {result['reason']}")


def _self_test() -> int:
    # Higher-DPS alternative flips; incumbent-best does not.
    decision = Decision("r", 1, "a", 100.0, [
        {"id": "a", "category": "item", "score": 10.0, "m": 0.0,
         "gain_method": "no_modeled_weapon_dps_effect"},
        {"id": "b", "category": "weapon", "score": 5.0, "m": 10.0,
         "gain_method": "weapon_add"},
    ], True)
    analysis = Analysis(run_ids=["r"], policy_by_run=Counter({"r": 3}),
                        decisions=[decision])
    assert dose_result(analysis, 0.0)["flips"] == 0
    assert dose_result(analysis, 0.5)["flips"] == 0  # tie keeps recorded order
    assert dose_result(analysis, 1.0)["flips"] == 1
    already = Decision("r", 1, "b", 100.0, [
        {"id": "b", "category": "weapon", "score": 10.0, "m": 10.0,
         "gain_method": "weapon_add"},
        {"id": "a", "category": "item", "score": 9.0, "m": 0.0,
         "gain_method": "none"},
    ], False)
    analysis.decisions.append(already)
    assert dose_result(analysis, 4.0)["flips"] == 1

    # Item-stat gain is positive and Ranger's +50% ranged gain modifier engages.
    weapon = {"damage": 10, "cooldown": 60, "scaling": [["stat_ranged_damage", 1]],
              "crit_chance": 0.0, "crit_damage": 2.0, "nb_projectiles": 1,
              "piercing": 0, "piercing_dmg_reduction": 0.5, "bounce": 0,
              "bounce_dmg_reduction": 0.5, "sets": [], "burning": False}
    catalog = {"weapon_x_1": weapon,
               "weapon_x_2": {**weapon, "damage": 20}}
    gain, method = _item_gain(
        {"effects": [{"key": "stat_ranged_damage", "value": 2, "sign": 3}]},
        ["weapon_x_1"], catalog,
        {"stat_ranged_damage": 0, "stat_percent_damage": 0,
         "stat_attack_speed": 0, "stat_crit_chance": 0})
    assert method == "item_stats" and abs(float(gain) - 3.0) < 1e-9

    # Combine replaces one owned copy with the next tier.
    gain2, method2 = _weapon_gain(
        {"id": "weapon_x_1"}, {"pairs_combine": True}, ["weapon_x_1"], catalog,
        {"stat_ranged_damage": 0, "stat_percent_damage": 0,
         "stat_attack_speed": 0, "stat_crit_chance": 0})
    assert method2 == "combine" and abs(float(gain2) - 10.0) < 1e-9

    # Unknown decisions stay in the policy denominator but not the dosed set.
    assert analysis.policy_n == 3 and len(analysis.decisions) == 2
    print("self-test PASS (higher-DPS flip, incumbent-best no-flip, item gain, "
          "combine gain, unchanged policy denominator)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-dir", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return _self_test()
    if args.runs_dir is None:
        parser.error("--runs-dir is required unless --self-test")

    analysis = analyse(args.runs_dir)
    result = build_result(analysis)
    _print_controls(result)
    _print_results(result)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 1 if result["status"] == "VOID" else 0


if __name__ == "__main__":
    raise SystemExit(main())
