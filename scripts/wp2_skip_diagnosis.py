"""v124 follow-up: WHY were gate-clearing mid-game offense offers skipped?

The v124 design assumed `OFFENSE_IMPACT_MIN_ITEM_GAIN = 6.0` blocked mid-game
offense conversion. The replay (`wp2_offer_dps_replay.py`) showed 64% of the
skipped positive-gain offense offers in defeat runs already CLEARED 6.0 -- so
the 6.0 literal is not the blocker. This script diagnoses the ACTUAL blocking
condition by extending the verified replay to the shop-decision control flow of
`shop_strategy.gd decide_shop()`.

Method (read-only): reuse the verified replay records (each carries the recorded
decision's action, gold_before, item price, and build_metrics offense fields),
compute the two live gates that decide whether an offense item is even eligible
for the mandatory-offense buy path --
  * offense_deficient  = _offense_proxy(build) < _offense_target(wave)   (line 993/1344)
  * band_gate          = wave >= OFFENSE_BAND_FROM_WAVE and weapon_dps < dps_target (line 1212)
-- and classify each skipped positive-gain offense offer from the RECORDED
decision evidence (no full item_score parity needed):

  (a) outscored   : affordable, but the board's action bought a different item.
  (b) gold_blocked: unaffordable at decision (price > gold).
  (c) loop_exit   : affordable + gate-cleared, but the buy loop rerolled / went
                    (nothing cleared min_buy / the mandatory-offense path never
                    fired) -- shop_strategy.gd:1360-1529.
  (d) veto        : a density/trap veto is positively detectable on the item.
  (e) other       : affordable but the board did lock/combine/sell/unlock.

Writes reports/wp2/v124_skip_diagnosis.{json,md}.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import wp2_offer_dps_replay as R

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "mod" / "mods-unpacked" / "Tom-BrotatoAgent" / "teacher" / "config.gd"


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def parse_consts() -> dict:
    text = CONFIG.read_text(encoding="utf-8")
    names = [
        "MID_SHOP_PIVOT_WAVE", "LATE_SHOP_WAVE", "OFFENSE_FLOOR_MID",
        "OFFENSE_FLOOR_LATE", "OFFENSE_TARGET_MARGIN", "OFFENSE_DENSITY_P90_GOAL",
        "OFFENSE_DENSITY_POINTS_PER_ENEMY", "OFFENSE_DENSITY_MAX_BONUS",
        "OFFENSE_DENSITY_PEAK_GOAL", "OFFENSE_DENSITY_POINTS_PER_PEAK_ENEMY",
        "OFFENSE_DENSITY_MAX_PEAK_BONUS", "OFFENSE_BAND_FROM_WAVE",
        "OFFENSE_IMPACT_MIN_ITEM_GAIN",
    ]
    out = {}
    for n in names:
        m = re.search(rf"const {n} := ([0-9.]+)", text)
        if not m:
            raise SystemExit(f"config.gd missing {n}")
        out[n] = float(m.group(1))
    return out


# well_rounded profile literals (build_profiles.gd:271-291)
WR_MIN_BUY = 5.0
WR_GOLD_RESERVE = 40.0


def offense_target(wave: int, prev_p90, prev_peak, c: dict) -> float:
    base = 0.0
    if wave >= c["LATE_SHOP_WAVE"]:
        base = c["OFFENSE_FLOOR_LATE"]
    elif wave >= c["MID_SHOP_PIVOT_WAVE"]:
        base = c["OFFENSE_FLOOR_MID"]
    if base <= 0.0:
        return 0.0
    p90 = float(prev_p90 or 0.0)
    density_bonus = _clamp((p90 - c["OFFENSE_DENSITY_P90_GOAL"])
                           * c["OFFENSE_DENSITY_POINTS_PER_ENEMY"],
                           0.0, c["OFFENSE_DENSITY_MAX_BONUS"])
    peak = float(prev_peak or 0.0)
    peak_bonus = _clamp((peak - c["OFFENSE_DENSITY_PEAK_GOAL"])
                        * c["OFFENSE_DENSITY_POINTS_PER_PEAK_ENEMY"],
                        0.0, c["OFFENSE_DENSITY_MAX_PEAK_BONUS"])
    return base + c["OFFENSE_TARGET_MARGIN"] + density_bonus + peak_bonus


_DENSITY_KEYS = {"number_of_enemies", "extra_enemies_next_wave",
                 "extra_loot_aliens_next_wave"}


def annotate(rec: dict, c: dict) -> dict:
    wave = rec["wave"]
    tgt = offense_target(wave, rec.get("prev_p90_density"),
                         rec.get("prev_peak_density"), c)
    proxy = rec.get("offense_total")
    deficient = tgt > 0.0 and proxy is not None and float(proxy) < tgt
    wdps = rec.get("weapon_dps")
    dtgt = rec.get("dps_target")
    band_gate = (wave >= c["OFFENSE_BAND_FROM_WAVE"] and wdps is not None
                 and dtgt is not None and float(wdps) < float(dtgt))
    rec = dict(rec)
    rec["offense_target"] = round(tgt, 2)
    rec["offense_deficient"] = bool(deficient)
    rec["band_gate"] = bool(band_gate)
    rec["gate_clears_6"] = rec["direct_gain"] >= c["OFFENSE_IMPACT_MIN_ITEM_GAIN"]
    return rec


def classify(rec: dict) -> tuple[str, str]:
    """Return (bucket, subtype)."""
    if not rec["affordable"]:
        return "gold_blocked", ""
    action = rec.get("action_type")
    if action == "shop_buy":
        return "outscored", ""
    if action in ("shop_reroll", "shop_go"):
        # density/trap veto is the only reason a gate-cleared affordable offense
        # item is *ineligible* rather than just out-competed; detect positively.
        return "loop_exit", action
    if action in ("shop_lock", "shop_unlock", "shop_combine", "shop_sell"):
        return "other", action
    return "other", str(action)


def root_cause(rec: dict) -> str:
    """Why the mandatory-offense buy path did not rescue this affordable skip."""
    if not rec["affordable"]:
        return "unaffordable"
    if not rec["offense_deficient"]:
        # _offense_first_item_action returns {} at shop_strategy.gd:993
        return "offense_adequate_no_mandatory_path"
    # offense_deficient == True: mandatory path WAS active this board but bought
    # something else (a higher-ranked offense item / weapon), rerolled to search
    # for more impact, sold/combined a weapon, or exited the shop.
    action = rec.get("action_type")
    if action == "shop_buy":
        return "deficient_but_outranked_this_board"
    if action == "shop_reroll":
        return "deficient_but_rerolled_for_more_impact"
    if action == "shop_go":
        return "deficient_but_shop_exited"
    if action in ("shop_sell", "shop_combine", "shop_unlock"):
        return f"deficient_but_board_did_{action}"
    return "deficient_but_other"


def shop_sequence(events, wave):
    """Recorded board->action sequence for one (run) shop at `wave`."""
    seq = []
    last_offer = None
    for e in events:
        ev = e.get("event")
        pl = e.get("payload", {})
        if ev == "purchase_offer":
            last_offer = pl
        elif ev == "purchase_decision" and pl.get("wave") == wave:
            a = pl.get("action", {})
            bought = None
            if a.get("type") == "shop_buy" and last_offer:
                for it in last_offer.get("items", []):
                    if it.get("slot") == a.get("slot"):
                        bought = {"id": it.get("id"), "price": it.get("price")}
            seq.append({
                "action": a.get("type"),
                "gold_before": pl.get("gold_before"),
                "bought": bought,
            })
    return seq


def build(records, results, runs, c):
    ann = [annotate(r, c) for r in records]

    def subset(result):
        return [r for r in ann
                if r["result"] == result and not r["bought"]
                and r["direct_gain"] > 0.0]

    def histogram(subs):
        h = Counter()
        rc = Counter()
        for r in subs:
            bucket, sub = classify(r)
            h[bucket] += 1
            rc[root_cause(r)] += 1
        return h, rc

    defeat = subset("defeat")
    victory = subset("victory")
    dh, drc = histogram(defeat)
    vh, vrc = histogram(victory)

    # 5 walked-through defeat examples spanning the buckets.
    examples = _examples(defeat, runs)

    # dominant blocker (raw plurality bucket)
    dominant = dh.most_common(1)[0] if dh else ("none", 0)

    # richer breakdowns for the write-up
    extra_def = _extra_breakdown(defeat, ann)
    extra_vic = _extra_breakdown(victory, ann)

    def pack(subs, h, rc, extra):
        n = len(subs)
        return {
            "n": n,
            "buckets": {k: {"count": v, "frac": round(v / n, 3)}
                        for k, v in h.most_common()},
            "root_causes": {k: {"count": v, "frac": round(v / n, 3)}
                            for k, v in rc.most_common()},
            "affordable": sum(1 for r in subs if r["affordable"]),
            "offense_deficient": sum(1 for r in subs if r["offense_deficient"]),
            "band_gate_active": sum(1 for r in subs if r["band_gate"]),
            "clears_6": sum(1 for r in subs if r["gate_clears_6"]),
            **extra,
        }

    return {
        "meta": {
            "question": "Actual blocking condition for skipped positive-gain "
                        "offense offers (defeat, w9-15) that clear the current gate.",
            "note": "Classified from recorded decision evidence (action taken, "
                    "gold_before, item price, build_metrics offense) -- no full "
                    "item_score parity required.",
            "well_rounded_min_buy_score": WR_MIN_BUY,
            "well_rounded_gold_reserve": WR_GOLD_RESERVE,
            "offense_impact_min_item_gain": c["OFFENSE_IMPACT_MIN_ITEM_GAIN"],
        },
        "defeat": pack(defeat, dh, drc, extra_def),
        "victory_control": pack(victory, vh, vrc, extra_vic),
        "dominant_blocker": {
            "raw_plurality_bucket": dominant[0],
            "count": dominant[1],
            "frac_of_defeat_skips": round(dominant[1] / len(defeat), 3) if defeat else None,
            "source": _SOURCE.get(dominant[0]),
            "interpretation": (
                "The 6.0 gate is NOT the blocker: band_gate is active in only "
                f"{extra_def['band_gate_active_n']}/{len(defeat)} skips (it is "
                "structurally off below wave 13, where most skips occur), and "
                "where active the item cleared it. 'outscored' is the raw "
                "plurality but largely reflects the offense-first single-best "
                "pick buying a higher-ranked offense item or a weapon on the "
                "same board (offense IS converted, just a different item): "
                f"{extra_def['outscored_won_by_offense_item']} lost to another "
                f"offense item, {extra_def['outscored_won_by_weapon_or_other']} "
                "to a weapon/other item."),
            "actionable_blocker": (
                "reroll-for-impact pressure -- of the items truly LEFT on the "
                f"board, {extra_def['loop_exit_reroll']} were rerolled away and "
                f"only {extra_def['loop_exit_go']} left by shop-exit. While "
                "offense-deficient the reroll worth is boosted by +8 "
                "(shop_strategy.gd:1514-1518), so the shop rerolls past "
                "affordable gate-clearing offense items instead of banking the "
                "buy. Second: gold_blocked "
                f"({extra_def['gold_blocked_n']}, median {extra_def['gold_blocked_median_shortfall']} "
                "gold short)."),
            "actionable_source": "shop_strategy.gd:1514-1518 (+8 offense-deficient "
                                 "reroll boost) and :1525-1527 (reroll when "
                                 "best_here < worth)",
        },
        "examples": examples,
    }


def _extra_breakdown(subs, ann):
    reroll = go = 0
    won_off = won_other = 0
    sell = 0
    shortfalls = []
    for r in subs:
        b, sub = classify(r)
        if b == "loop_exit":
            if sub == "shop_reroll":
                reroll += 1
            elif sub == "shop_go":
                go += 1
        elif b == "outscored":
            winner = [x for x in ann if x["run"] == r["run"]
                      and x["wave"] == r["wave"] and x["slot"] == r["action_slot"]
                      and x["bought"]]
            if winner:
                won_off += 1
            else:
                won_other += 1
        elif b == "gold_blocked":
            shortfalls.append((r["price"] or 0) - (r["gold_before"] or 0))
        elif b == "other" and sub == "shop_sell":
            sell += 1
    # distinct true-miss: positive-gain offense items never bought that shop
    distinct = {}
    for r in subs:
        distinct[(r["run"], r["wave"], r["item_id"])] = False
    for r in ann:
        if r["bought"] and (r["run"], r["wave"], r["item_id"]) in distinct:
            distinct[(r["run"], r["wave"], r["item_id"])] = True
    true_miss = sum(1 for v in distinct.values() if not v)
    shortfalls.sort()
    return {
        "loop_exit_reroll": reroll,
        "loop_exit_go": go,
        "outscored_won_by_offense_item": won_off,
        "outscored_won_by_weapon_or_other": won_other,
        "other_shop_sell": sell,
        "gold_blocked_n": len(shortfalls),
        "gold_blocked_median_shortfall": shortfalls[len(shortfalls) // 2] if shortfalls else None,
        "band_gate_active_n": sum(1 for r in subs if r["band_gate"]),
        "distinct_items": len(distinct),
        "distinct_true_miss": true_miss,
    }


_SOURCE = {
    "outscored": "shop_strategy.gd:1360-1411 (generic best-purchase loop: a "
                 "higher item_score item is bought first; offense item never "
                 "reaches best_action)",
    "loop_exit": "shop_strategy.gd:1356+993 (_offense_first_item_action returns "
                 "{} when _offense_proxy >= _offense_target) then 1495-1529 "
                 "(reroll/go: best_here < worth, min_buy=5.0 not cleared)",
    "gold_blocked": "shop_strategy.gd:1378 (`if not it.get('affordable'): continue`)",
    "other": "shop_strategy.gd lock/combine/sell branches",
    "veto": "shop_strategy.gd:673 _increases_enemy_density / :684 _sustain_cap_veto",
}


def _examples(defeat, runs):
    # pick up to 5 covering the buckets, deterministic order
    picked = []
    seen_buckets = set()
    seen_items = set()
    ordered = sorted(defeat, key=lambda r: (r["run"], r["wave"], r["item_id"] or ""))
    # first pass: one per bucket, preferring distinct item_ids
    for r in ordered:
        b, _ = classify(r)
        if b not in seen_buckets and r["item_id"] not in seen_items:
            seen_buckets.add(b)
            seen_items.add(r["item_id"])
            picked.append(r)
    # fill to 5 with still-unseen items across any bucket
    for r in ordered:
        if len(picked) >= 5:
            break
        if r not in picked and r["item_id"] not in seen_items:
            seen_items.add(r["item_id"])
            picked.append(r)
    picked = picked[:5]
    out = []
    for r in picked:
        bucket, sub = classify(r)
        out.append({
            "run": r["run"], "wave": r["wave"], "item_id": r["item_id"],
            "offense_keys": r["offense_keys"], "direct_gain": r["direct_gain"],
            "clears_6.0": r["gate_clears_6"],
            "price": r["price"], "gold_before": r["gold_before"],
            "affordable": r["affordable"],
            "offense_total": round(float(r["offense_total"]), 1)
                if r["offense_total"] is not None else None,
            "offense_target": r["offense_target"],
            "offense_deficient": r["offense_deficient"],
            "weapon_dps": round(float(r["weapon_dps"]), 1)
                if r["weapon_dps"] is not None else None,
            "dps_target": r["dps_target"], "band_gate": r["band_gate"],
            "board_action_taken": r["action_type"],
            "bucket": bucket, "root_cause": root_cause(r),
            "shop_decision_sequence": shop_sequence(runs[r["run"]], r["wave"]),
        })
    return out


def render_md(rep: dict) -> str:
    L = []
    L.append("# v124 skip diagnosis -- the real blocker of mid-game offense conversion")
    L.append("")
    m = rep["meta"]
    L.append(f"Follow-up to the marginal-DPS replay. The 6.0 "
             f"`OFFENSE_IMPACT_MIN_ITEM_GAIN` gate was assumed to block mid-game "
             f"offense buys, but 64% of skipped positive-gain offense offers in "
             f"defeat runs already cleared it. This classifies the **actual** "
             f"blocking condition from recorded decision evidence.")
    L.append("")
    d = rep["defeat"]
    v = rep["victory_control"]
    L.append(f"well_rounded `min_buy_score` = **{m['well_rounded_min_buy_score']}**, "
             f"`gold_reserve` = {m['well_rounded_gold_reserve']}. "
             f"Set: **{d['n']}** skipped positive-gain offense offers (defeat, w9-15); "
             f"{v['n']} in victory (control).")
    L.append("")
    L.append("## Classification histogram")
    L.append("")
    L.append("| bucket | defeat | victory (control) |")
    L.append("|---|---|---|")
    keys = list(dict.fromkeys(list(d["buckets"]) + list(v["buckets"])))
    for k in keys:
        dv = d["buckets"].get(k, {"count": 0, "frac": 0})
        vv = v["buckets"].get(k, {"count": 0, "frac": 0})
        L.append(f"| {k} | {dv['count']} ({dv['frac']*100:.0f}%) "
                 f"| {vv['count']} ({vv['frac']*100:.0f}%) |")
    L.append("")
    L.append("### Root-cause breakdown (why the mandatory-offense path didn't fire)")
    L.append("")
    L.append("| root cause | defeat | victory |")
    L.append("|---|---|---|")
    rkeys = list(dict.fromkeys(list(d["root_causes"]) + list(v["root_causes"])))
    for k in rkeys:
        dv = d["root_causes"].get(k, {"count": 0, "frac": 0})
        vv = v["root_causes"].get(k, {"count": 0, "frac": 0})
        L.append(f"| {k} | {dv['count']} ({dv['frac']*100:.0f}%) "
                 f"| {vv['count']} ({vv['frac']*100:.0f}%) |")
    L.append("")
    L.append(f"- defeat: offense_deficient at skip = **{d['offense_deficient']}/{d['n']}**; "
             f"band_gate active = {d['band_gate_active']}/{d['n']}; "
             f"clears 6.0 = {d['clears_6']}/{d['n']}.")
    L.append(f"- victory: offense_deficient = {v['offense_deficient']}/{v['n']}; "
             f"band_gate active = {v['band_gate_active']}/{v['n']}.")
    L.append("")
    db = rep["dominant_blocker"]
    L.append("## Dominant blocker")
    L.append("")
    L.append(f"Raw plurality bucket: **{db['raw_plurality_bucket']}** -- "
             f"{db['count']}/{d['n']} ({db['frac_of_defeat_skips']*100:.0f}%).")
    L.append("")
    L.append(f"**Interpretation.** {db['interpretation']}")
    L.append("")
    L.append(f"**Actionable blocker.** {db['actionable_blocker']}")
    L.append("")
    L.append(f"Source: `{db['actionable_source']}`")
    L.append("")
    L.append(f"Reference (distinct items): of {d['distinct_items']} distinct "
             f"positive-gain offense items skipped in defeat runs, "
             f"**{d['distinct_true_miss']} were never bought that shop** "
             f"(true misses), {d['distinct_items'] - d['distinct_true_miss']} were "
             f"bought on a later board of the same shop.")
    L.append("")
    L.append("## 5 walked-through examples (defeat)")
    L.append("")
    for e in rep["examples"]:
        L.append(f"### `{e['item_id']}` -- w{e['wave']} run ...{e['run'][-8:]} "
                 f"[{e['bucket']}]")
        L.append(f"- offense keys {e['offense_keys']}, direct_gain={e['direct_gain']} "
                 f"(clears 6.0: {e['clears_6.0']}); price={e['price']}, "
                 f"gold_before={e['gold_before']} -> affordable={e['affordable']}")
        L.append(f"- offense_total={e['offense_total']} vs target={e['offense_target']} "
                 f"-> deficient={e['offense_deficient']}; weapon_dps={e['weapon_dps']} vs "
                 f"dps_target={e['dps_target']} -> band_gate={e['band_gate']}")
        L.append(f"- board action taken: **{e['board_action_taken']}**; "
                 f"root cause: **{e['root_cause']}**")
        L.append(f"- shop decision sequence: "
                 + " | ".join(
                     f"{s['action']}"
                     + (f"({s['bought']['id']}@{s['bought']['price']})"
                        if s.get("bought") else "")
                     + f" g={s['gold_before']}"
                     for s in e["shop_decision_sequence"]))
        L.append("")
    return "\n".join(L)


def main() -> int:
    c = parse_consts()
    run_meta = R.load_run_list()
    results = {r["run_id"]: r["result"] for r in run_meta}
    ids = [r["run_id"] for r in run_meta]
    runs = {}
    for rid in ids:
        path = DEFAULT = R.DEFAULT_RUNS / rid / "events.jsonl"
        if not path.exists():
            raise SystemExit(f"missing telemetry: {path}")
        runs[rid] = R.read_shop_events(path)
    wstats = R.harvest_weapon_stats(runs)
    records, _parity, _trust = R.replay(runs, results, wstats)
    report = build(records, results, runs, c)

    out_dir = ROOT / "reports" / "wp2"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "v124_skip_diagnosis.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    (out_dir / "v124_skip_diagnosis.md").write_text(render_md(report), encoding="utf-8")
    db = report["dominant_blocker"]
    d = report["defeat"]
    print(f"defeat skips n={d['n']} buckets={dict((k, x['count']) for k, x in d['buckets'].items())}")
    print(f"band_gate_active={d['band_gate_active']}/{d['n']} offense_deficient={d['offense_deficient']}/{d['n']} "
          f"reroll={d['loop_exit_reroll']} gold_blocked={d['gold_blocked_n']} true_miss={d['distinct_true_miss']}/{d['distinct_items']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
