#!/usr/bin/env python3
"""Item outcome ledger -- offline, reusable evaluation of item effectiveness.

Targets items whose value is NOT captured by the DPS/EHP combat model
(pickup/collection, economy) using matched-wave KPI contrasts, and covers
offense stat items as a calibration control (their computed %DPS gain, from the
bit-exact replay mirror, is what the ledger's ranking is validated against).

Method
------
For every item bought across the campaign runs we record (item, run, wave, price,
run outcome). Items are classified data-driven from their offer-board tags and
effect keys into mechanism classes, each with a matched KPI:

  collection (pickup tag / pickup_range / instant_gold_attracting effect)
      -> ground-material cap-saturation fraction (primary) and mean ground
         material count (proxy) for waves AFTER acquisition, contrasted against
         the SAME waves' pooled baseline over runs NOT holding the item.
  defensive (stat_armor / stat_max_hp / stat_dodge / ...)
      -> player damage-taken per wave after acquisition vs matched baseline
         (lower is better).
  economy (economy tag / gold effects)
      -> gold entering subsequent shops vs matched baseline.
  offense (stat_ranged_damage / stat_percent_damage / stat_attack_speed / crit)
      -> computed %loadout-DPS gain at purchase from the wp2_offer_dps_replay
         mirror (calibration control; NOT a matched-wave contrast).

Matched-wave contrast unit
--------------------------
The statistical unit is a (run, item) *holding*: acquisition wave = the earliest
wave the run bought the item, so multiple buys of the same item in one run do not
multiply post-wave observations. For each post-acquisition wave w the treatment
value is contrasted against the mean KPI at the SAME wave w over every run that
does NOT hold the item by wave w (runs that never bought it, or bought it later).
Runs that died before w have no wave-w capture and are excluded on both sides, so
the contrast only ever compares runs alive at w.

Small-n honesty
---------------
Per item we report n_buys and n_runs. Any item bought in fewer than 3 runs is
marked INSUFFICIENT (numbers reported, no verdict). No retier recommendations --
evidence only, with a "tension with current tier" note where the ledger's
direction contradicts config.gd ROGUERANKER_ITEM_TIERS / WIKI_USEFUL_ITEM_TIERS.

Merge
-----
The JSON stores raw contrast sums (sum_delta, sum_effect, counts) plus the
per-holding rows, so ledgers from several campaigns pool exactly:

    python scripts/wp2_item_ledger.py --merge a.json b.json --out c.json

CLI (mirrors wp2_telemetry_stats.py)
------------------------------------
    python scripts/wp2_item_ledger.py --runs-dir <dir> \
        --from-audit reports/wp2/v122_exact20_safety_audit.json \
        --out reports/wp2/item_ledger_v122_campaign.json
    python scripts/wp2_item_ledger.py --runs-dir <dir> \
        --run-id <id> [--run-id ...] --out <json>

Read-only on run directories. No game, no deploy, no network.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from statistics import median

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# Reused, not reimplemented: per-wave baselines + shop purchases.
from wp2_telemetry_stats import compute_run_stats  # noqa: E402
# Reused, not reimplemented: offer-board harvest + bit-exact DPS replay mirror.
from wp2_offer_dps_replay import (  # noqa: E402
    read_shop_events,
    harvest_weapon_stats,
    replay,
)

ROOT = os.path.dirname(_HERE)
CONFIG_REL = "mod/mods-unpacked/Tom-BrotatoAgent/teacher/config.gd"

# --- classification vocab (data-driven from offer tags / effect keys) --------
COLLECTION_TAGS = frozenset({"pickup"})
COLLECTION_EFFECT_KEYS = frozenset({"pickup_range", "instant_gold_attracting"})
OFFENSE_STAT_KEYS = frozenset({
    "stat_ranged_damage", "stat_percent_damage", "stat_attack_speed",
    "stat_crit_chance", "stat_crit_damage",
})
DEFENSE_EFFECT_KEYS = frozenset({
    "stat_armor", "stat_max_hp", "stat_dodge", "stat_hp_regeneration",
    "stat_life_steal",
})
ECONOMY_TAGS = frozenset({"economy"})
ECONOMY_EFFECT_KEYS = frozenset({
    "chance_double_gold", "gold_drops", "gold", "free_rerolls",
    "stat_harvesting", "heal_when_pickup_gold",
})

# Priority order for the item's PRIMARY class (its matched KPI).
CLASS_PRIORITY = ("collection", "offense", "defensive", "economy", "other")

# KPI specifications. direction +1 => higher is better; -1 => lower is better.
# direction: sign multiplier turning a holder-minus-baseline delta into an
#   "effect" (only meaningful when value_direction is good_high/good_low).
# value_direction: how to READ the sign --
#   good_high  higher KPI is better    -> effect = +delta
#   good_low   lower KPI is better     -> effect = -delta
#   ambiguous  sign is not a value verdict (see note); reported descriptively.
KPI_SPECS = {
    "materials_saturation_frac": {
        "source": "per_wave", "path": ("materials", "saturation_frac"),
        "direction": 1, "value_direction": "ambiguous",
        "label": "ground-material cap-saturation fraction",
    },
    "materials_mean": {
        "source": "per_wave", "path": ("materials", "mean"),
        "direction": 1, "value_direction": "ambiguous",
        "label": "mean ground material count",
    },
    "damage_amount": {
        "source": "per_wave", "path": ("damage", "amount"),
        "direction": -1, "value_direction": "good_low",
        "label": "player damage taken per wave",
    },
    "gold_entering": {
        "source": "shops", "path": ("gold_entering",),
        "direction": 1, "value_direction": "good_high",
        "label": "gold entering shop",
    },
}
CLASS_KPIS = {
    "collection": ["materials_saturation_frac", "materials_mean"],
    "defensive": ["damage_amount"],
    "economy": ["gold_entering"],
    # offense handled separately (calibration control via DPS replay).
}
CONFOUND_NOTES = {
    "collection": ("Ground-material saturation is AMBIGUOUS as a value signal: "
                   "it is the fraction of captures where uncollected drops sit "
                   "near the 50 cap, so a working pickup item -- clearing the "
                   "ground faster -- pushes saturation DOWN, while a higher "
                   "kill/drop rate pushes it UP. A negative holder delta is "
                   "therefore consistent with the item collecting well, not "
                   "with a deficiency. Also confounded by selection (bought in "
                   "runs that already collect well / survive longer) and by "
                   "occupancy. Sign is reported descriptively, not as a "
                   "beats/below-baseline verdict."),
    "defensive": ("Damage taken per wave is dominated by wave difficulty and "
                  "positioning; the wave-matched baseline controls difficulty "
                  "but not build/skill selection into buying defense."),
    "economy": ("Gold entering later shops reflects total run economy (kills, "
                "wave reached, spend discipline), not just the item; matched on "
                "wave only."),
    "offense": ("Calibration control: %DPS gain is the exact combat-model math "
                "at purchase (waves 9-15 window, loadout-validated), not an "
                "outcome contrast."),
}

INSUFFICIENT_MIN_RUNS = 3
TIER_RANK = {"S": 5, "A": 4, "B": 3, "C": 2, "D": 1}


# --- classification ---------------------------------------------------------
def classify_item(tags, effect_keys):
    """Return (classes:list, primary:str) from offer tags + effect keys."""
    tags = set(tags or [])
    effect_keys = set(effect_keys or [])
    classes = []
    if tags & COLLECTION_TAGS or effect_keys & COLLECTION_EFFECT_KEYS:
        classes.append("collection")
    if effect_keys & OFFENSE_STAT_KEYS:
        classes.append("offense")
    if effect_keys & DEFENSE_EFFECT_KEYS:
        classes.append("defensive")
    if tags & ECONOMY_TAGS or effect_keys & ECONOMY_EFFECT_KEYS:
        classes.append("economy")
    if not classes:
        classes.append("other")
    primary = next(c for c in CLASS_PRIORITY if c in classes)
    return classes, primary


def build_item_catalog(run_ids, runs_dir):
    """item_id -> {tags, effect_keys} harvested from purchase_offer boards."""
    catalog = {}
    for rid in run_ids:
        path = os.path.join(runs_dir, rid, "events.jsonl")
        if not os.path.isfile(path):
            continue
        for e in read_shop_events(_as_path(path)):
            if e.get("event") != "purchase_offer":
                continue
            for it in e.get("payload", {}).get("items", []):
                iid = it.get("id")
                if it.get("category") != "item" or not iid or iid in catalog:
                    continue
                catalog[iid] = {
                    "tags": list(it.get("tags", [])),
                    "effect_keys": sorted({ef.get("key")
                                           for ef in it.get("effects", [])
                                           if ef.get("key")}),
                }
    return catalog


def _as_path(p):
    """read_shop_events wants a pathlib-like object with .open()."""
    from pathlib import Path
    return Path(p)


# --- KPI access -------------------------------------------------------------
def kpi_value(run_stats, wave, kpi):
    """Value of KPI at a wave for one run, or None if absent."""
    spec = KPI_SPECS[kpi]
    container = run_stats.get(spec["source"], {})
    node = container.get(str(wave))
    if node is None:
        return None
    for key in spec["path"]:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    if node is None:
        return None
    try:
        return float(node)
    except (TypeError, ValueError):
        return None


def kpi_waves(run_stats, kpi):
    spec = KPI_SPECS[kpi]
    return sorted(int(w) for w in run_stats.get(spec["source"], {}))


# --- purchases + holdings ---------------------------------------------------
def extract_purchases(run_stats):
    """List of {run, wave, item_id, price} for every item shop_buy in a run."""
    out = []
    rid = run_stats.get("run_id")
    for wave_str, shop in run_stats.get("shops", {}).items():
        for it in shop.get("items_bought", []):
            if it.get("category") != "item":
                continue
            out.append({
                "run": rid,
                "wave": int(wave_str),
                "item_id": it.get("id"),
                "price": it.get("price"),
            })
    return out


def earliest_buy_by_run(purchases, item_id):
    """run_id -> earliest wave the run bought item_id (only runs that did)."""
    out = {}
    for p in purchases:
        if p["item_id"] != item_id:
            continue
        w = p["wave"]
        if p["run"] not in out or w < out[p["run"]]:
            out[p["run"]] = w
    return out


# --- matched-wave contrast --------------------------------------------------
def matched_contrast(item_id, kpi, runs_by_id, earliest_buy):
    """Compute the matched-wave contrast for one item + KPI.

    Returns a raw-accumulator dict (poolable across campaigns) plus the
    per-holding rows. Derived fields are filled by finalize_contrast().
    """
    spec = KPI_SPECS[kpi]
    direction = spec["direction"]
    holders = {rid: w for rid, w in earliest_buy.items() if w is not None}

    sum_delta = 0.0
    sum_effect = 0.0
    n_obs = 0
    n_obs_positive = 0
    per_holding = []

    for rid, buy_wave in sorted(holders.items()):
        run_stats = runs_by_id.get(rid)
        if run_stats is None:
            continue
        h_delta = 0.0
        h_effect = 0.0
        h_n = 0
        h_pos = 0
        for w in kpi_waves(run_stats, kpi):
            if w <= buy_wave:
                continue
            tv = kpi_value(run_stats, w, kpi)
            if tv is None:
                continue
            # baseline: runs NOT holding item_id by wave w, alive at w.
            base = []
            for orid, orun in runs_by_id.items():
                eb = earliest_buy.get(orid)
                if eb is not None and eb <= w:
                    continue  # holder at w
                ov = kpi_value(orun, w, kpi)
                if ov is not None:
                    base.append(ov)
            if not base:
                continue
            baseline = sum(base) / len(base)
            delta = tv - baseline
            effect = delta * direction
            sum_delta += delta
            sum_effect += effect
            n_obs += 1
            n_obs_positive += int(effect > 0)
            h_delta += delta
            h_effect += effect
            h_n += 1
            h_pos += int(effect > 0)
        if h_n:
            per_holding.append({
                "run": rid,
                "acquired_wave": buy_wave,
                "n_postwaves": h_n,
                "mean_delta": h_delta / h_n,
                "mean_effect": h_effect / h_n,
                "obs_positive": h_pos,
            })

    return {
        "kpi": kpi,
        "label": spec["label"],
        "value_direction": spec["value_direction"],
        "direction": "higher_better" if direction > 0 else "lower_better",
        "sum_delta": sum_delta,
        "sum_effect": sum_effect,
        "n_obs": n_obs,
        "n_obs_positive": n_obs_positive,
        "n_holdings": len(per_holding),
        "n_holdings_positive": sum(1 for h in per_holding
                                   if h["mean_effect"] > 0),
        "per_holding": per_holding,
    }


def finalize_contrast(c):
    """Fill derived (mean / sign-consistency) fields from raw accumulators."""
    n = c["n_obs"]
    nh = c["n_holdings"]
    c["mean_delta"] = (c["sum_delta"] / n) if n else None
    c["mean_effect"] = (c["sum_effect"] / n) if n else None
    c["obs_sign_consistency"] = (c["n_obs_positive"] / n) if n else None
    c["holding_sign_consistency"] = (c["n_holdings_positive"] / nh) if nh else None
    return c


# --- offense calibration control (DPS replay reuse) -------------------------
def offense_calibration(run_ids, runs_dir, results):
    """item_id -> {values:[%dps gain per bought instance], per_buy:[...]}.

    Reuses wp2_offer_dps_replay.replay() (bit-exact combat-model mirror,
    waves 9-15). Only bought, %DPS-computable offense-stat offers are kept.
    """
    runs = {}
    for rid in run_ids:
        path = os.path.join(runs_dir, rid, "events.jsonl")
        if not os.path.isfile(path):
            continue
        runs[rid] = read_shop_events(_as_path(path))
    if not runs:
        return {}, {"records": 0, "computable": 0}
    wstats = harvest_weapon_stats(runs)
    records, _parity, _trust = replay(runs, results, wstats)
    by_item = defaultdict(lambda: {"values": [], "per_buy": []})
    n_records = 0
    n_comp = 0
    for r in records:
        if not r.get("bought"):
            continue
        n_records += 1
        if not r.get("computable") or r.get("dps_gain") is None:
            continue
        n_comp += 1
        by_item[r["item_id"]]["values"].append(r["dps_gain"])
        by_item[r["item_id"]]["per_buy"].append({
            "run": r["run"], "wave": r["wave"],
            "dps_gain": r["dps_gain"], "direct_gain": r.get("direct_gain"),
            "method": r.get("dps_method"), "result": r.get("result"),
        })
    return dict(by_item), {"bought_offense_offers": n_records,
                           "computable": n_comp,
                           "window": "waves 9-15 shops"}


def finalize_calibration(cal):
    vals = cal["values"]
    cal["n"] = len(vals)
    cal["sum"] = sum(vals) if vals else 0.0
    cal["mean"] = (sum(vals) / len(vals)) if vals else None
    cal["median"] = median(vals) if vals else None
    return cal


# --- tier tables (config.gd HEAD) -------------------------------------------
def _parse_gd_tier_block(text, const_name):
    m = re.search(const_name + r"\s*:=\s*\{", text)
    if not m:
        return {}
    i = m.end()
    depth = 1
    body_start = i
    while i < len(text) and depth:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    body = text[body_start:i - 1]
    out = {}
    for mm in re.finditer(r'"(item_[a-z0-9_]+)"\s*:\s*"([SABCD])"', body):
        out[mm.group(1)] = mm.group(2)
    return out


def load_item_tiers(config_text):
    rogue = _parse_gd_tier_block(config_text, "ROGUERANKER_ITEM_TIERS")
    wiki = _parse_gd_tier_block(config_text, "WIKI_USEFUL_ITEM_TIERS")
    tiers = {}
    for iid, t in rogue.items():
        tiers[iid] = {"tier": t, "source": "rogueranker"}
    for iid, t in wiki.items():
        tiers.setdefault(iid, {"tier": t, "source": "wiki"})
    return tiers


def read_config_text():
    """config.gd from HEAD (not the working tree the other agent may edit)."""
    import subprocess
    try:
        return subprocess.check_output(
            ["git", "show", "HEAD:" + CONFIG_REL], cwd=ROOT,
            encoding="utf-8", stderr=subprocess.DEVNULL)
    except Exception:
        path = os.path.join(ROOT, CONFIG_REL)
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()


def tier_tension(primary_class, contrast, tier, insufficient):
    """Short note where the ledger's KPI direction contradicts the item tier."""
    if insufficient or tier is None or contrast is None:
        return None
    # An ambiguous KPI (collection saturation) has no good/bad sign, so it
    # cannot contradict a tier -- no tension claim.
    if contrast.get("value_direction") == "ambiguous":
        return None
    eff = contrast.get("mean_effect")
    cons = contrast.get("holding_sign_consistency")
    if eff is None or cons is None:
        return None
    rank = TIER_RANK.get(tier, 0)
    helps = eff > 0 and cons >= 0.6
    hurts = eff < 0 and cons <= 0.4
    if helps and rank <= TIER_RANK["C"]:
        return ("ledger: helps %s (consistent) but tier %s -- possibly "
                "underrated on this axis" % (primary_class, tier))
    if hurts and rank >= TIER_RANK["A"]:
        return ("ledger: no %s benefit (consistent) but tier %s -- rating "
                "must rest on other axes" % (primary_class, tier))
    return None


# --- build ------------------------------------------------------------------
def build_ledger(run_stats_list, catalog, tiers, calibration, cal_meta,
                 campaign_label):
    runs_by_id = {rs["run_id"]: rs for rs in run_stats_list}
    results = {rs["run_id"]: rs.get("result") for rs in run_stats_list}

    all_purchases = []
    for rs in run_stats_list:
        all_purchases.extend(extract_purchases(rs))

    # per-item buy/run counts
    buys = defaultdict(int)
    runs_bought = defaultdict(set)
    for p in all_purchases:
        buys[p["item_id"]] += 1
        runs_bought[p["item_id"]].add(p["run"])

    items = {}
    for item_id in sorted(buys):
        cat = catalog.get(item_id, {"tags": [], "effect_keys": []})
        classes, primary = classify_item(cat["tags"], cat["effect_keys"])
        n_buys = buys[item_id]
        n_runs = len(runs_bought[item_id])
        insufficient = n_runs < INSUFFICIENT_MIN_RUNS
        tier_info = tiers.get(item_id)

        entry = {
            "item_id": item_id,
            "classes": classes,
            "primary_class": primary,
            "tags": cat["tags"],
            "effect_keys": cat["effect_keys"],
            "tier": tier_info["tier"] if tier_info else None,
            "tier_source": tier_info["source"] if tier_info else None,
            "n_buys": n_buys,
            "n_runs": n_runs,
            "insufficient": insufficient,
            "contrasts": {},
            "calibration": None,
            "tier_tension": None,
        }

        earliest = earliest_buy_by_run(all_purchases, item_id)
        for kpi in CLASS_KPIS.get(primary, []):
            c = finalize_contrast(
                matched_contrast(item_id, kpi, runs_by_id, earliest))
            entry["contrasts"][kpi] = c

        if item_id in calibration:
            entry["calibration"] = finalize_calibration(
                dict(calibration[item_id]))

        primary_kpis = CLASS_KPIS.get(primary, [])
        if primary_kpis:
            entry["tier_tension"] = tier_tension(
                primary, entry["contrasts"].get(primary_kpis[0]),
                entry["tier"], insufficient)

        items[item_id] = entry

    return {
        "tool": "wp2_item_ledger",
        "schema_version": 1,
        "campaigns": [campaign_label],
        "run_count": len(run_stats_list),
        "victory": sum(1 for r in results.values() if r == "victory"),
        "defeat": sum(1 for r in results.values() if r == "defeat"),
        "insufficient_min_runs": INSUFFICIENT_MIN_RUNS,
        "class_kpis": CLASS_KPIS,
        "kpi_specs": {k: {"direction": v["direction"], "label": v["label"]}
                      for k, v in KPI_SPECS.items()},
        "confound_notes": CONFOUND_NOTES,
        "calibration_meta": cal_meta,
        "items": items,
    }


# --- merge ------------------------------------------------------------------
def merge_contrasts(a, b):
    out = {
        "kpi": a["kpi"],
        "label": a.get("label", b.get("label")),
        "value_direction": a.get("value_direction", b.get("value_direction")),
        "direction": a["direction"],
        "sum_delta": a["sum_delta"] + b["sum_delta"],
        "sum_effect": a["sum_effect"] + b["sum_effect"],
        "n_obs": a["n_obs"] + b["n_obs"],
        "n_obs_positive": a["n_obs_positive"] + b["n_obs_positive"],
        "n_holdings": a["n_holdings"] + b["n_holdings"],
        "n_holdings_positive": a["n_holdings_positive"] + b["n_holdings_positive"],
        "per_holding": list(a.get("per_holding", [])) + list(b.get("per_holding", [])),
    }
    return finalize_contrast(out)


def merge_calibration(a, b):
    if a is None:
        return dict(b) if b else None
    if b is None:
        return dict(a)
    out = {
        "values": list(a["values"]) + list(b["values"]),
        "per_buy": list(a.get("per_buy", [])) + list(b.get("per_buy", [])),
    }
    return finalize_calibration(out)


def merge_ledgers(ledgers):
    if not ledgers:
        raise ValueError("no ledgers to merge")
    merged = {
        "tool": "wp2_item_ledger",
        "schema_version": 1,
        "campaigns": [],
        "run_count": 0,
        "victory": 0,
        "defeat": 0,
        "insufficient_min_runs": INSUFFICIENT_MIN_RUNS,
        "class_kpis": CLASS_KPIS,
        "kpi_specs": ledgers[0].get("kpi_specs", {}),
        "confound_notes": CONFOUND_NOTES,
        "calibration_meta": {"merged": True},
        "items": {},
    }
    for led in ledgers:
        merged["campaigns"].extend(led.get("campaigns", []))
        merged["run_count"] += led.get("run_count", 0)
        merged["victory"] += led.get("victory", 0)
        merged["defeat"] += led.get("defeat", 0)
        for item_id, e in led.get("items", {}).items():
            if item_id not in merged["items"]:
                merged["items"][item_id] = {
                    "item_id": item_id,
                    "classes": list(e.get("classes", [])),
                    "primary_class": e.get("primary_class"),
                    "tags": e.get("tags", []),
                    "effect_keys": e.get("effect_keys", []),
                    "tier": e.get("tier"),
                    "tier_source": e.get("tier_source"),
                    "n_buys": 0,
                    "n_runs": 0,
                    "insufficient": True,
                    "contrasts": {},
                    "calibration": None,
                    "tier_tension": None,
                }
            m = merged["items"][item_id]
            m["n_buys"] += e.get("n_buys", 0)
            m["n_runs"] += e.get("n_runs", 0)
            for kpi, c in e.get("contrasts", {}).items():
                m["contrasts"][kpi] = (merge_contrasts(m["contrasts"][kpi], c)
                                       if kpi in m["contrasts"] else
                                       finalize_contrast(dict(
                                           c, per_holding=list(c.get("per_holding", [])))))
            m["calibration"] = merge_calibration(m["calibration"],
                                                 e.get("calibration"))
    # recompute insufficiency + tier tension on pooled counts
    for item_id, m in merged["items"].items():
        m["insufficient"] = m["n_runs"] < INSUFFICIENT_MIN_RUNS
        primary_kpis = CLASS_KPIS.get(m["primary_class"], [])
        if primary_kpis and primary_kpis[0] in m["contrasts"]:
            m["tier_tension"] = tier_tension(
                m["primary_class"], m["contrasts"][primary_kpis[0]],
                m["tier"], m["insufficient"])
    return merged


# --- rendering --------------------------------------------------------------
def _fnum(v, nd=3):
    return "n/a" if v is None else ("%." + str(nd) + "f") % v


def _fpct(v):
    return "n/a" if v is None else "%.0f%%" % (100.0 * v)


def render_markdown(ledger):
    L = []
    camps = ", ".join(ledger.get("campaigns", []))
    L.append("# WP2 item outcome ledger -- %s" % camps)
    L.append("")
    L.append("Generated by `scripts/wp2_item_ledger.py` over %d runs (%d victory / "
             "%d defeat). Read-only; no game, no deploy. Matched-wave KPI "
             "contrasts for collection / defensive / economy items; offense "
             "items carry the bit-exact %%DPS-gain calibration control."
             % (ledger["run_count"], ledger.get("victory", 0),
                ledger.get("defeat", 0)))
    L.append("")
    L.append("- Contrast unit: a (run, item) holding; acquisition wave = earliest "
             "buy. Post-acquisition waves are contrasted against the same waves' "
             "mean over runs NOT holding the item (alive at that wave).")
    L.append("- INSUFFICIENT = bought in fewer than %d runs (numbers reported, no "
             "verdict). No retier recommendations in this pass."
             % ledger["insufficient_min_runs"])
    L.append("")

    items = ledger["items"]

    def by_class(cls):
        return sorted((e for e in items.values() if e["primary_class"] == cls),
                      key=lambda e: -e["n_buys"])

    # Collection (primary target)
    L.append("## Collection / pickup items (primary target)")
    L.append("")
    L.append(CONFOUND_NOTES["collection"])
    L.append("")
    L.append("KPI: ground-material cap-saturation fraction. Delta = holder minus "
             "matched non-holders at the same wave. Sign is AMBIGUOUS (see note): "
             "a pickup item clearing the ground faster LOWERS saturation, so a "
             "negative holder delta is consistent with the item working. "
             "'verdict' describes the sign only, not a value judgement.")
    L.append("")
    L.append("| item | tier | n_buys | n_runs | sat Δ (mean) | frac holders-higher "
             "(holdings / obs) | mat-mean Δ | sign |")
    L.append("|---|---|--:|--:|--:|---|--:|---|")
    for e in by_class("collection"):
        sat = e["contrasts"].get("materials_saturation_frac", {})
        mmean = e["contrasts"].get("materials_mean", {})
        verdict = ("INSUFFICIENT" if e["insufficient"]
                   else _verdict(sat))
        L.append("| %s | %s | %d | %d | %s | %s / %s | %s | %s |" % (
            e["item_id"].replace("item_", ""),
            e["tier"] or "-", e["n_buys"], e["n_runs"],
            _fnum(sat.get("mean_delta")),
            _fpct(sat.get("holding_sign_consistency")),
            _fpct(sat.get("obs_sign_consistency")),
            _fnum(mmean.get("mean_delta"), 2),
            verdict))
    L.append("")
    _tensions(L, by_class("collection"))

    # Offense calibration control
    L.append("## Offense stat items -- calibration control")
    L.append("")
    L.append(CONFOUND_NOTES["offense"])
    L.append("")
    L.append("If the ledger method is sound, ranking bought offense items by "
             "their computed %DPS gain reproduces the combat-model ordering.")
    L.append("")
    L.append("| item | tier | n_buys | computed %DPS gain (median) | mean | n_computable |")
    L.append("|---|---|--:|--:|--:|--:|")
    cal_items = sorted(
        (e for e in items.values() if e.get("calibration")),
        key=lambda e: -(e["calibration"].get("median") or -1e9))
    for e in cal_items:
        c = e["calibration"]
        L.append("| %s | %s | %d | %s | %s | %d |" % (
            e["item_id"].replace("item_", ""), e["tier"] or "-",
            e["n_buys"], _fnum(c.get("median")), _fnum(c.get("mean")),
            c.get("n", 0)))
    L.append("")

    # Defensive + economy
    for cls, title in (("defensive", "Defensive items"),
                       ("economy", "Economy items")):
        members = by_class(cls)
        L.append("## %s" % title)
        L.append("")
        L.append(CONFOUND_NOTES[cls])
        L.append("")
        if not members:
            L.append("_No item bought whose primary class is %s in this "
                     "campaign._" % cls)
            L.append("")
            continue
        kpi = CLASS_KPIS[cls][0]
        L.append("KPI: %s (%s better)." % (
            KPI_SPECS[kpi]["label"],
            "lower" if KPI_SPECS[kpi]["direction"] < 0 else "higher"))
        L.append("")
        L.append("| item | tier | n_buys | n_runs | Δ (mean) | sign-consist "
                 "(holdings) | verdict |")
        L.append("|---|---|--:|--:|--:|---|---|")
        for e in members:
            c = e["contrasts"].get(kpi, {})
            verdict = "INSUFFICIENT" if e["insufficient"] else _verdict(c)
            L.append("| %s | %s | %d | %d | %s | %s | %s |" % (
                e["item_id"].replace("item_", ""), e["tier"] or "-",
                e["n_buys"], e["n_runs"], _fnum(c.get("mean_delta")),
                _fpct(c.get("holding_sign_consistency")), verdict))
        L.append("")
        _tensions(L, members)

    return "\n".join(L)


def _verdict(contrast):
    if not contrast or contrast.get("n_obs", 0) == 0:
        return "no data"
    cons = contrast.get("holding_sign_consistency")
    if cons is None:
        return "no data"
    if contrast.get("value_direction") == "ambiguous":
        # Describe the raw delta sign only (no good/bad claim).
        delta = contrast.get("mean_delta")
        if delta is None:
            return "no data"
        if delta > 0 and cons >= 0.6:
            return "holders higher"
        if delta < 0 and cons <= 0.4:
            return "holders lower"
        return "mixed"
    eff = contrast.get("mean_effect")
    if eff is None:
        return "no data"
    if eff > 0 and cons >= 0.6:
        return "beats baseline"
    if eff < 0 and cons <= 0.4:
        return "below baseline"
    return "mixed / null"


def _tensions(L, entries):
    notes = [(e["item_id"].replace("item_", ""), e["tier_tension"])
             for e in entries if e.get("tier_tension")]
    if notes:
        L.append("Tier tensions:")
        L.append("")
        for name, note in notes:
            L.append("- **%s**: %s" % (name, note))
        L.append("")


# --- run-list resolution (mirrors wp2_telemetry_stats) ----------------------
def load_audit_run_ids(audit_path):
    with open(audit_path, "r", encoding="utf-8") as fh:
        audit = json.load(fh)
    return [r["run_id"] for r in audit.get("runs", [])]


def _write_outputs(ledger, out_path):
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, indent=1)
    md_path = (out_path[:-5] + ".md") if out_path.endswith(".json") \
        else out_path + ".md"
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(ledger))
    return md_path


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs-dir", help="directory of <run_id>/ subdirectories")
    ap.add_argument("--run-id", action="append", default=[],
                    help="run id (repeatable)")
    ap.add_argument("--from-audit",
                    help="safety-audit JSON to read the run list from")
    ap.add_argument("--campaign-label", default=None,
                    help="label for this campaign in the merge-able JSON")
    ap.add_argument("--merge", nargs="+", metavar="LEDGER",
                    help="merge these ledger JSONs (pool counts + contrasts)")
    ap.add_argument("--out", required=True, help="output JSON path")
    args = ap.parse_args(argv)

    if args.merge:
        ledgers = []
        for path in args.merge:
            with open(path, "r", encoding="utf-8") as fh:
                ledgers.append(json.load(fh))
        merged = merge_ledgers(ledgers)
        md_path = _write_outputs(merged, args.out)
        print("merged %d ledgers -> %s (+ %s); %d items, %d runs"
              % (len(ledgers), args.out, os.path.basename(md_path),
                 len(merged["items"]), merged["run_count"]))
        return merged

    if not args.runs_dir:
        ap.error("--runs-dir required for build mode")
    run_ids = list(args.run_id)
    if args.from_audit:
        run_ids += load_audit_run_ids(args.from_audit)
    seen = set()
    ordered = [r for r in run_ids if not (r in seen or seen.add(r))]
    if not ordered:
        ap.error("no run ids (use --run-id or --from-audit)")

    label = args.campaign_label
    if label is None and args.from_audit:
        base = os.path.basename(args.from_audit)
        label = base.replace("_safety_audit.json", "").replace(".json", "")
    if label is None:
        label = "campaign"

    run_stats_list = []
    for rid in ordered:
        run_dir = os.path.join(args.runs_dir, rid)
        if not os.path.isdir(run_dir):
            print("WARN: missing run dir %s" % run_dir)
            continue
        run_stats_list.append(compute_run_stats(run_dir, rid))

    results = {rs["run_id"]: rs.get("result") for rs in run_stats_list}
    present_ids = [rs["run_id"] for rs in run_stats_list]
    catalog = build_item_catalog(present_ids, args.runs_dir)
    tiers = load_item_tiers(read_config_text())
    calibration, cal_meta = offense_calibration(present_ids, args.runs_dir,
                                                 results)

    ledger = build_ledger(run_stats_list, catalog, tiers, calibration,
                          cal_meta, label)
    md_path = _write_outputs(ledger, args.out)
    print("wrote %s (+ %s); %d items over %d runs"
          % (args.out, os.path.basename(md_path), len(ledger["items"]),
             ledger["run_count"]))
    return ledger


if __name__ == "__main__":
    main()
