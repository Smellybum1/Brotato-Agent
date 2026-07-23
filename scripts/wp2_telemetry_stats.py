#!/usr/bin/env python3
"""Reusable CPU-side telemetry statistics for WP2 Brotato campaign runs.

Streams each run's events.jsonl exactly once (line-by-line, constant memory
w.r.t. file size) and emits per-run + pooled statistics that consolidate the
methodology of the streaming-agent analyses:

  reports/wp2/v123_run5_calibration.md
  reports/wp2/v122_campaign_strength_drivers.md
  reports/wp2/v122_exact20_covariates.md

Metrics per run:
  1. Strength S per wave  = clamp(offense.weapon_dps / offense.dps_target, 0, 2)
     from combat_tick.build_metrics.offense (0.5 s cadence). median/p10/p90 per
     wave, plus tick-time-weighted tier fractions under the v123 hysteresis
     thresholds (strong enter >=1.25 / exit <=1.15, weak enter <=0.75 /
     exit >=0.85).
  2. Occupancy per wave from combat_capture player positions: two-wall corner
     (<280 of both a horizontal AND a vertical wall) and single-wall edge
     (<280 of any wall) fractions. Arena read from capture.arena.
  3. Economy per shop (grouped by purchase_decision.wave): gold entering,
     spend, end-of-shop idle gold, reroll count + cost, items bought
     (id, price, effect keys, offense flag). purchase_offer coverage and, if
     offers are recorded, bought-vs-offered offense items. The marginal-DPS
     gain of an offer is NOT recorded by the telemetry (verified); flagged.
  4. Dash episodes per wave from
     capture.teacher.contributions.finale_translation.loot_dash_active edges:
     count and mean length (in captures), plus active-capture fraction.
  5. Damage per wave (player_damage.amount, attributed to the wave of the most
     recent combat event) and ground-material cap saturation per wave
     (fraction of captures with len(entities.materials) >= threshold).
  result / last_wave / duration come from summary.json.

Handles both v122 captures (no strength keys) and v123+ captures (which add
finale_translation.build_strength / strength_tier); S is always recomputed from
build_metrics for consistency across versions.

CLI:
  python scripts/wp2_telemetry_stats.py --runs-dir <dir> \
      --run-id <id> [--run-id ...] --out <json>
  python scripts/wp2_telemetry_stats.py --runs-dir <dir> \
      --from-audit reports/wp2/v122_exact20_safety_audit.json --out <json>

Read-only on run directories. No game, no deploy, no network.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict

# --- constants (consolidated from the precedent analyses) -------------------
CORNER_MARGIN = 280.0            # LATE_CORNER_GUARD_MARGIN mirror
STRONG_ENTER, STRONG_EXIT = 1.25, 1.15
WEAK_ENTER, WEAK_EXIT = 0.75, 0.85
MATERIAL_CAP = 50                # observed field ceiling (dropped_counts=0)
MATERIAL_SATURATION_MIN = 48     # "near the 50 cap"
OFFENSE_STAT_KEYS = frozenset({
    "stat_ranged_damage",
    "stat_attack_speed",
    "stat_percent_damage",
    "stat_crit_chance",
})


# --- small numeric helpers --------------------------------------------------
def clamp(value, lo, hi):
    return lo if value < lo else hi if value > hi else value


def percentile(sorted_vals, pct):
    """Linear-interpolated percentile (numpy 'linear'/type-7). pct in [0,100].

    ``sorted_vals`` must already be sorted ascending and non-empty.
    """
    n = len(sorted_vals)
    if n == 1:
        return float(sorted_vals[0])
    rank = (pct / 100.0) * (n - 1)
    lo = int(rank)
    hi = min(lo + 1, n - 1)
    frac = rank - lo
    return float(sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac)


def summarize(values):
    """median/p10/p90/mean/n for a list of numbers (empty-safe)."""
    if not values:
        return {"n": 0, "median": None, "p10": None, "p90": None, "mean": None}
    sv = sorted(values)
    return {
        "n": len(sv),
        "median": percentile(sv, 50),
        "p10": percentile(sv, 10),
        "p90": percentile(sv, 90),
        "mean": sum(sv) / len(sv),
    }


def strength_tiers(series):
    """Tick-time-weighted tier fractions over an ordered S series using the v123
    hysteresis state machine. Returns dict of strong/neutral/weak fractions."""
    if not series:
        return {"strong": None, "neutral": None, "weak": None, "n": 0}
    state = "neutral"
    counts = {"strong": 0, "neutral": 0, "weak": 0}
    for s in series:
        if state == "strong":
            if s <= STRONG_EXIT:
                state = "weak" if s <= WEAK_ENTER else "neutral"
        elif state == "weak":
            if s >= WEAK_EXIT:
                state = "strong" if s >= STRONG_ENTER else "neutral"
        else:  # neutral
            if s >= STRONG_ENTER:
                state = "strong"
            elif s <= WEAK_ENTER:
                state = "weak"
        counts[state] += 1
    n = len(series)
    return {
        "strong": counts["strong"] / n,
        "neutral": counts["neutral"] / n,
        "weak": counts["weak"] / n,
        "n": n,
    }


def occupancy_flags(px, py, width, height, margin=CORNER_MARGIN):
    """(corner, edge) booleans for a player position in an arena.

    corner = within `margin` of one vertical AND one horizontal wall.
    edge   = within `margin` of any single wall.
    """
    near_vertical = px < margin or (width - px) < margin
    near_horizontal = py < margin or (height - py) < margin
    edge = near_vertical or near_horizontal
    corner = near_vertical and near_horizontal
    return corner, edge


# --- core streaming pass ----------------------------------------------------
def iter_events(events_path):
    with open(events_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def compute_run_stats(run_dir, run_id):
    """Single streaming pass over one run. Returns a per-run stats dict."""
    events_path = os.path.join(run_dir, "events.jsonl")
    summary_path = os.path.join(run_dir, "summary.json")

    summary = {}
    if os.path.isfile(summary_path):
        with open(summary_path, "r", encoding="utf-8") as fh:
            summary = json.load(fh)

    # per-wave accumulators
    s_by_wave = defaultdict(list)                 # wave -> [S values]
    s_series = []                                 # ordered S for hysteresis
    off_stat_by_wave = defaultdict(lambda: defaultdict(list))

    occ_by_wave = defaultdict(lambda: [0, 0, 0])  # wave -> [n, corner, edge]
    mat_by_wave = defaultdict(lambda: [0, 0])     # wave -> [n_caps, saturated]
    mat_counts_by_wave = defaultdict(list)        # wave -> [material counts]

    dmg_by_wave = defaultdict(lambda: [0.0, 0])   # wave -> [amount, events]

    # dash episode tracking (streaming edge detection over captures)
    dash_active_caps = defaultdict(int)           # wave -> active capture count
    dash_total_caps = defaultdict(int)            # wave -> total captures
    dash_episodes = defaultdict(list)             # wave -> [episode lengths]
    dash_prev = False
    dash_run_len = 0
    dash_run_wave = None

    # economy: group decisions per wave, matched to the latest offer board
    decisions_by_wave = defaultdict(list)
    last_offer = None
    offers_recorded = False
    offer_has_marginal = False  # whether any offer/decision records a DPS gain
    # offense items offered per wave: offer boards precede the decisions of the
    # same shop, so buffer each board and attribute it to the next decision's
    # wave (handles rerolls emitting several boards in one shop).
    offered_offense_by_wave = defaultdict(set)
    pending_offer_offense = []

    arena_w, arena_h = 2048.0, 1536.0
    current_wave = None
    strength_keys_present = False

    for e in iter_events(events_path):
        ev = e.get("event")
        p = e.get("payload", {})

        if ev == "combat_tick":
            w = p.get("wave")
            if w is not None:
                current_wave = w
            bm = p.get("build_metrics", {})
            off = bm.get("offense", {})
            dps_target = off.get("dps_target")
            wdps = off.get("weapon_dps")
            if dps_target:
                s = clamp(wdps / dps_target, 0.0, 2.0)
                s_by_wave[w].append(s)
                s_series.append(s)
                for k in OFFENSE_STAT_KEYS:
                    short = k[len("stat_"):]
                    if short in off:
                        off_stat_by_wave[w][short].append(off[short])

        elif ev == "combat_capture":
            w = p.get("wave")
            if w is not None:
                current_wave = w
            pl = p.get("player", {})
            arena = p.get("arena", {})
            arena_w = arena.get("width", arena_w)
            arena_h = arena.get("height", arena_h)
            px, py = pl.get("x"), pl.get("y")
            if px is not None and py is not None:
                corner, edge = occupancy_flags(px, py, arena_w, arena_h)
                acc = occ_by_wave[w]
                acc[0] += 1
                acc[1] += int(corner)
                acc[2] += int(edge)
            # ground materials
            mats = p.get("entities", {}).get("materials", [])
            mcount = len(mats)
            macc = mat_by_wave[w]
            macc[0] += 1
            macc[1] += int(mcount >= MATERIAL_SATURATION_MIN)
            mat_counts_by_wave[w].append(mcount)
            # dash edges
            ft = (p.get("teacher", {})
                    .get("contributions", {})
                    .get("finale_translation", {}))
            if "strength_tier" in ft or "build_strength" in ft:
                strength_keys_present = True
            active = bool(ft.get("loot_dash_active", False))
            dash_total_caps[w] += 1
            if active:
                dash_active_caps[w] += 1
            if active and not dash_prev:
                dash_run_len = 1
                dash_run_wave = w
            elif active and dash_prev:
                dash_run_len += 1
            elif (not active) and dash_prev:
                dash_episodes[dash_run_wave].append(dash_run_len)
                dash_run_len = 0
                dash_run_wave = None
            dash_prev = active

        elif ev == "player_damage":
            amt = p.get("amount", 0) or 0
            dmg_by_wave[current_wave][0] += amt
            dmg_by_wave[current_wave][1] += 1

        elif ev == "purchase_offer":
            offers_recorded = True
            last_offer = p
            for it in p.get("items", []):
                for mk in ("marginal_dps", "dps_gain", "delta_dps",
                           "combat_value", "marginal_value"):
                    if mk in it:
                        offer_has_marginal = True
                if (it.get("category") == "item"
                        and set(ef.get("key") for ef in it.get("effects", []))
                        & OFFENSE_STAT_KEYS):
                    pending_offer_offense.append(it.get("id"))

        elif ev == "purchase_decision":
            a = p.get("action", {})
            w = p.get("wave")
            if pending_offer_offense:
                offered_offense_by_wave[w].update(pending_offer_offense)
                pending_offer_offense = []
            slot = a.get("slot")
            matched = None
            if last_offer and slot is not None:
                for it in last_offer.get("items", []):
                    if it.get("slot") == slot:
                        matched = it
                        break
            decisions_by_wave[w].append((a, p, matched))
            sb = p.get("score_breakdown", {})
            if isinstance(sb, dict):
                for mk in ("marginal_dps", "dps_gain", "delta_dps"):
                    if mk in sb:
                        offer_has_marginal = True

    # close a dangling dash episode
    if dash_prev and dash_run_wave is not None:
        dash_episodes[dash_run_wave].append(dash_run_len)

    # ---- assemble per-wave stats ----
    waves = sorted(set(s_by_wave) | set(occ_by_wave) | set(mat_by_wave)
                   | set(decisions_by_wave) | set(dmg_by_wave))
    waves = [w for w in waves if w is not None]

    per_wave = {}
    for w in waves:
        s_stats = summarize(s_by_wave.get(w, []))
        occ = occ_by_wave.get(w, [0, 0, 0])
        occ_n = occ[0]
        macc = mat_by_wave.get(w, [0, 0])
        mat_stats = summarize(mat_counts_by_wave.get(w, []))
        dmg = dmg_by_wave.get(w, [0.0, 0])
        eps = dash_episodes.get(w, [])
        off_stats = {}
        for short, vals in off_stat_by_wave.get(w, {}).items():
            st = summarize(vals)
            off_stats[short] = st["median"]
        per_wave[str(w)] = {
            "S": s_stats,
            "offense_stats_median": off_stats,
            "occupancy": {
                "captures": occ_n,
                "corner_frac": (occ[1] / occ_n) if occ_n else None,
                "edge_frac": (occ[2] / occ_n) if occ_n else None,
            },
            "materials": {
                "captures": macc[0],
                "saturation_frac": (macc[1] / macc[0]) if macc[0] else None,
                "mean": mat_stats["mean"],
                "p90": mat_stats["p90"],
                "max": max(mat_counts_by_wave.get(w, [0])) if macc[0] else None,
            },
            "damage": {"amount": dmg[0], "events": dmg[1]},
            "dash": {
                "episodes": len(eps),
                "mean_len": (sum(eps) / len(eps)) if eps else None,
                "active_frac": (dash_active_caps.get(w, 0)
                                / dash_total_caps[w]) if dash_total_caps.get(w)
                else None,
            },
        }

    # ---- economy per shop ----
    shops = {}
    for w in sorted(decisions_by_wave):
        if w is None:
            continue
        decs = decisions_by_wave[w]
        gold_entering = decs[0][1].get("gold_before")
        idle_gold = None
        reroll_count = 0
        reroll_cost = 0
        spend = 0
        items_bought = []
        offense_bought = 0
        offense_offered = len(offered_offense_by_wave.get(w, set()))
        for a, pd_, matched in decs:
            atype = a.get("type")
            if atype == "shop_go":
                idle_gold = pd_.get("gold_before")
            elif atype == "shop_reroll":
                reroll_count += 1
                reroll_cost += pd_.get("reroll_price", 0) or 0
            elif atype == "shop_buy":
                price = matched.get("price") if matched else None
                effects = ([ef.get("key") for ef in matched.get("effects", [])]
                           if matched else [])
                is_offense = bool(set(effects) & OFFENSE_STAT_KEYS)
                category = matched.get("category") if matched else None
                if price:
                    spend += price
                if is_offense:
                    offense_bought += 1
                items_bought.append({
                    "id": a.get("item_id"),
                    "price": price,
                    "category": category,
                    "effect_keys": effects,
                    "offense_stat": is_offense,
                })
        if idle_gold is None:
            idle_gold = decs[-1][1].get("gold_before")
        shops[str(w)] = {
            "gold_entering": gold_entering,
            "spend": spend,
            "idle_gold": idle_gold,
            "reroll_count": reroll_count,
            "reroll_cost": reroll_cost,
            "items_bought": items_bought,
            "offense_stat_items_bought": offense_bought,
            "offense_stat_items_offered": offense_offered,
        }

    return {
        "run_id": run_id,
        "result": summary.get("result"),
        "last_wave": summary.get("last_wave"),
        "waves_completed": summary.get("waves_completed"),
        "policy_version": summary.get("policy_version"),
        "mod_version": summary.get("mod_version"),
        "duration_ms": summary.get("duration_ms"),
        "recoveries": summary.get("recoveries"),
        "strength_keys_present": strength_keys_present,
        "offers_recorded": offers_recorded,
        "offer_marginal_dps_recorded": offer_has_marginal,
        "strength_tiers": strength_tiers(s_series),
        "per_wave": per_wave,
        "shops": shops,
    }


# --- pooling ----------------------------------------------------------------
def pool_runs(run_stats):
    """Pool per-wave occupancy / materials / S / damage / dash across runs."""
    wave_occ = defaultdict(lambda: [0, 0, 0])       # wave -> [n, corner, edge]
    wave_mat = defaultdict(lambda: [0, 0])          # wave -> [n, saturated]
    wave_s_med = defaultdict(list)                   # wave -> [median S]
    wave_dmg = defaultdict(lambda: [0.0, 0])
    wave_dash = defaultdict(lambda: [0, 0, 0])       # wave -> [act, tot, epis]

    tiers = {"strong": [], "neutral": [], "weak": []}
    for rs in run_stats:
        t = rs["strength_tiers"]
        if t.get("n"):
            for k in tiers:
                tiers[k].append(t[k])
        for w, wd in rs["per_wave"].items():
            occ = wd["occupancy"]
            if occ["captures"]:
                acc = wave_occ[w]
                acc[0] += occ["captures"]
                acc[1] += round(occ["corner_frac"] * occ["captures"])
                acc[2] += round(occ["edge_frac"] * occ["captures"])
            mat = wd["materials"]
            if mat["captures"]:
                macc = wave_mat[w]
                macc[0] += mat["captures"]
                macc[1] += round(mat["saturation_frac"] * mat["captures"])
            if wd["S"]["median"] is not None:
                wave_s_med[w].append(wd["S"]["median"])
            wave_dmg[w][0] += wd["damage"]["amount"]
            wave_dmg[w][1] += wd["damage"]["events"]
            wave_dash[w][2] += wd["dash"]["episodes"]

    pooled = {}
    all_waves = sorted(set(wave_occ) | set(wave_mat) | set(wave_s_med),
                       key=lambda x: int(x))
    for w in all_waves:
        occ = wave_occ.get(w, [0, 0, 0])
        mat = wave_mat.get(w, [0, 0])
        pooled[w] = {
            "occupancy": {
                "captures": occ[0],
                "corner_frac": (occ[1] / occ[0]) if occ[0] else None,
                "edge_frac": (occ[2] / occ[0]) if occ[0] else None,
            },
            "materials": {
                "captures": mat[0],
                "saturation_frac": (mat[1] / mat[0]) if mat[0] else None,
            },
            "S_median": summarize(wave_s_med.get(w, [])),
            "damage": {
                "amount": wave_dmg[w][0],
                "events": wave_dmg[w][1],
                "runs": len(wave_s_med.get(w, [])) or None,
            },
            "dash_episodes_total": wave_dash[w][2],
        }
    pooled_tiers = {
        k: (sum(v) / len(v)) if v else None for k, v in tiers.items()
    }
    return {"per_wave": pooled, "strength_tiers_mean": pooled_tiers,
            "run_count": len(run_stats)}


# --- run-list resolution ----------------------------------------------------
def load_audit_run_ids(audit_path):
    with open(audit_path, "r", encoding="utf-8") as fh:
        audit = json.load(fh)
    runs = audit.get("runs", [])
    return [r["run_id"] for r in runs]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs-dir", required=True,
                    help="directory containing <run_id>/ subdirectories")
    ap.add_argument("--run-id", action="append", default=[],
                    help="run id (repeatable)")
    ap.add_argument("--from-audit",
                    help="safety-audit JSON to read the run list from")
    ap.add_argument("--out", required=True, help="output JSON path")
    args = ap.parse_args(argv)

    run_ids = list(args.run_id)
    if args.from_audit:
        run_ids += load_audit_run_ids(args.from_audit)
    # dedupe, preserve order
    seen = set()
    ordered = []
    for r in run_ids:
        if r not in seen:
            seen.add(r)
            ordered.append(r)
    if not ordered:
        ap.error("no run ids given (use --run-id or --from-audit)")

    run_stats = []
    for rid in ordered:
        run_dir = os.path.join(args.runs_dir, rid)
        if not os.path.isdir(run_dir):
            print("WARN: missing run dir %s" % run_dir)
            continue
        run_stats.append(compute_run_stats(run_dir, rid))

    out = {
        "tool": "wp2_telemetry_stats",
        "constants": {
            "corner_margin": CORNER_MARGIN,
            "strong_enter": STRONG_ENTER, "strong_exit": STRONG_EXIT,
            "weak_enter": WEAK_ENTER, "weak_exit": WEAK_EXIT,
            "material_cap": MATERIAL_CAP,
            "material_saturation_min": MATERIAL_SATURATION_MIN,
            "offense_stat_keys": sorted(OFFENSE_STAT_KEYS),
        },
        "runs_dir": args.runs_dir,
        "run_ids": ordered,
        "runs": run_stats,
        "pooled": pool_runs(run_stats),
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print("wrote %s (%d runs)" % (args.out, len(run_stats)))
    return out


if __name__ == "__main__":
    main()
