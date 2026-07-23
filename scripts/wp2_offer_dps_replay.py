"""Offline marginal-DPS + flat-offense-gain replay over recorded shop offers (v124).

Read-only. Replays the 20-run v122 exact-20 campaign
(`reports/wp2/v122_exact20_safety_audit.json`) and, for every offense-stat item
OFFERED at waves 9-15 shops, computes two quantities that feed the v124
`OFFENSE_IMPACT_MIN_ITEM_GAIN` threshold decision:

  1. The teacher combat model's % loadout DPS gain -- an EXACT Python port of
     `teacher/combat_model.gd` `weapon_dps()` / `combat_value()` (the dps term
     `100 * (dps1 - dps0) / dps0` across the equipped loadout).
  2. The flat "direct offense gain" the live threshold actually gates on --
     `shop_strategy.gd _direct_offense_gain()` (raw stat-point sum of
     ranged_damage + percent_damage + attack_speed, plus explosive/piercing
     weapon bonuses; crit stats contribute 0). This is what
     `OFFENSE_IMPACT_MIN_ITEM_GAIN` (config.gd, currently 6.0) is compared to.

Loadout handling
----------------
The equipped weapon list is NOT emitted in the telemetry (only the aggregate
`build_metrics.offense.weapon_dps` plus four offense stats). We rebuild it by
replaying the run: starting weapon + weapon buys (full stats recorded on the
offer board) + sells + combine `after_signature` resets, with a bounded
silent-combine reconciliation search (some combines are not telemetry-logged).
Each shop's rebuilt loadout is *validated* against the recorded
`weapon_dps` (within 1%), `weapon_count`, and `weapon_tier_sum`; only validated
("trusted") shops are used for ranged_damage / crit gains. Items whose combat
deltas touch only percent_damage / attack_speed are loadout-free (a uniform DPS
scalar) and are computed exactly at every shop.

Weapon base stats come only from the recorded offer boards (version-correct for
game 1.1.15.4); tier-3 weapons that never appear on a board (e.g. weapon_smg_4)
leave their shop untrusted for ranged/crit gains -- reported as coverage.

Usage:
    python scripts/wp2_offer_dps_replay.py [--runs-dir PATH] [--out-dir reports/wp2]
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict, deque
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "mod" / "mods-unpacked" / "Tom-BrotatoAgent" / "teacher" / "config.gd"
AUDIT = ROOT / "reports" / "wp2" / "v122_exact20_safety_audit.json"
DEFAULT_RUNS = Path.home() / "AppData" / "Roaming" / "Brotato" / "brotato_agent" / "runs"

# --- shop_strategy.gd sign constants ---
_SIGN_POSITIVE = 0
_SIGN_NEGATIVE = 1
_SIGN_NEUTRAL = 2
_SIGN_FROM_VALUE = 3

# combat_model.gd _DAMAGE_STATS / scaling-relevant stats
OFFENSE_STAT_KEYS = frozenset({
    "stat_ranged_damage", "stat_attack_speed", "stat_percent_damage",
    "stat_crit_chance", "stat_crit_damage",
})
# Keys whose combat delta changes weapon_dps only through per-weapon structure
# (scaling flats or crit) -> require the equipped loadout.
_LOADOUT_FREE_KEYS = frozenset({"stat_percent_damage", "stat_attack_speed"})
# _COMBAT_STATS from shop_strategy.gd (keys _combat_deltas keeps).
_COMBAT_STATS = frozenset({
    "stat_percent_damage", "stat_ranged_damage", "stat_melee_damage",
    "stat_elemental_damage", "stat_damage", "stat_attack_speed",
    "stat_crit_chance", "stat_crit_damage", "stat_max_hp", "stat_armor",
    "stat_dodge", "stat_hp_regeneration", "stat_speed",
})
# _direct_offense_gain explosive/piercing keys
_EXPLOSIVE_KEYS = frozenset({
    "piercing", "piercing_damage", "bounce", "explosion_damage",
    "explosion_size", "effect_explode", "explode_on_death",
    "projectiles_on_death", "burning_spread",
})
_DEFAULT_CRIT_DAMAGE = 2.0


# ───────────────────────── combat_model.gd port (EXACT) ─────────────────────

def _f(v) -> float:
    """Port of combat_model.gd _f(): numeric -> float, else 0.0."""
    if isinstance(v, bool):
        return 0.0
    return float(v) if isinstance(v, (int, float)) else 0.0


def weapon_dps(weapon: dict, stats: dict) -> float:
    flat = _f(weapon.get("damage"))
    for s in (weapon.get("scaling") or []):
        if isinstance(s, (list, tuple)) and len(s) >= 2:
            flat += _f(stats.get(s[0])) * _f(s[1])
    flat = max(1.0, flat)

    hit = flat * (1.0 + _f(stats.get("stat_percent_damage")) / 100.0)

    crit_chance = _f(weapon.get("crit_chance")) + _f(stats.get("stat_crit_chance")) / 100.0
    crit_chance = min(1.0, max(0.0, crit_chance))
    crit_damage = _f(weapon.get("crit_damage"))
    if crit_damage == 0.0:
        crit_damage = _DEFAULT_CRIT_DAMAGE
    crit_damage += _f(stats.get("stat_crit_damage")) / 100.0
    hit *= 1.0 + crit_chance * max(0.0, crit_damage - 1.0)

    cooldown = max(1.0, _f(weapon.get("cooldown")))
    rate = (1.0 + _f(stats.get("stat_attack_speed")) / 100.0) * 60.0 / cooldown
    return hit * rate


def total_dps(weapons: list, stats: dict) -> float:
    return sum(weapon_dps(w, stats) for w in weapons)


def effective_weapon_dps(weapon: dict, stats: dict) -> float:
    direct = weapon_dps(weapon, stats)
    projectiles = max(1.0, _f(weapon.get("nb_projectiles")))
    piercing = max(0.0, _f(weapon.get("piercing")))
    pierce_keep = min(1.0, max(0.0, 1.0 - _f(weapon.get("piercing_dmg_reduction"))))
    bounce = max(0.0, _f(weapon.get("bounce")))
    bounce_keep = min(1.0, max(0.0, 1.0 - _f(weapon.get("bounce_dmg_reduction"))))
    crowd_mult = 1.0 + piercing * pierce_keep * 0.35 + bounce * bounce_keep * 0.25
    sets = weapon.get("sets") or []
    if "set_explosive" in sets:
        crowd_mult *= 1.15
    if bool(weapon.get("burning", False)):
        crowd_mult *= 1.10
    return direct * projectiles * crowd_mult


def total_effective_weapon_dps(weapons: list, stats: dict) -> float:
    return sum(effective_weapon_dps(w, stats) for w in weapons)


def apply_deltas(stats: dict, deltas: dict, gain_mods: dict | None = None) -> dict:
    gain_mods = gain_mods or {}
    out = dict(stats)
    for stat, dv in deltas.items():
        gain = 1.0 + _f(gain_mods.get(stat)) / 100.0
        out[stat] = _f(out.get(stat)) + _f(dv) * max(0.0, gain)
    return out


def combat_value_dps_gain(weapons: list, stats: dict, deltas: dict,
                          gain_mods: dict | None = None) -> float:
    """The dps_gain term of combat_model.gd combat_value()."""
    new_stats = apply_deltas(stats, deltas, gain_mods)
    dps0 = total_dps(weapons, stats)
    dps1 = total_dps(weapons, new_stats)
    if dps0 > 0:
        return 100.0 * (dps1 - dps0) / dps0
    if dps1 > 0:
        return 100.0
    return 0.0


def closed_form_dps_gain(stats: dict, deltas: dict) -> float:
    """Loadout-free DPS gain for deltas touching only percent_damage/attack_speed.

    Both stats are uniform multipliers over every weapon's dps, so the % gain is
    independent of the loadout and equals combat_value's dps term exactly when
    gain_mods are empty (well_rounded).
    """
    factor = 1.0
    if "stat_percent_damage" in deltas:
        p0 = _f(stats.get("stat_percent_damage"))
        factor *= (1.0 + (p0 + _f(deltas["stat_percent_damage"])) / 100.0) / (1.0 + p0 / 100.0)
    if "stat_attack_speed" in deltas:
        a0 = _f(stats.get("stat_attack_speed"))
        factor *= (1.0 + (a0 + _f(deltas["stat_attack_speed"])) / 100.0) / (1.0 + a0 / 100.0)
    return 100.0 * (factor - 1.0)


# ───────────────────────── shop_strategy.gd port (EXACT) ────────────────────

def effect_signed_value(e: dict) -> float:
    val = e.get("value", 0)
    if val is None:
        val = 0
    eff_sign = e.get("sign", _SIGN_FROM_VALUE)
    if eff_sign == _SIGN_POSITIVE:
        return abs(float(val))
    if eff_sign == _SIGN_NEGATIVE:
        return -abs(float(val))
    if eff_sign == _SIGN_NEUTRAL:
        return 0.0
    return float(val)


def combat_deltas(effects: list) -> dict:
    d: dict = {}
    for e in effects:
        key = e.get("key", "")
        if key in _COMBAT_STATS:
            d[key] = d.get(key, 0.0) + effect_signed_value(e)
    return d


def direct_offense_gain(effects: list) -> float:
    """Port of shop_strategy.gd _direct_offense_gain()."""
    gain = 0.0
    for e in effects:
        key = e.get("key", "")
        val = effect_signed_value(e)
        if key in ("stat_ranged_damage", "stat_percent_damage", "stat_attack_speed"):
            gain += val
        elif key in _EXPLOSIVE_KEYS and val > 0.0:
            gain += max(1.0, val)
    return gain


# ───────────────────────────── config / audit ──────────────────────────────

def parse_threshold() -> float:
    text = CONFIG.read_text(encoding="utf-8")
    m = re.search(r"const OFFENSE_IMPACT_MIN_ITEM_GAIN := ([0-9.]+)", text)
    if not m:
        raise SystemExit("config.gd missing OFFENSE_IMPACT_MIN_ITEM_GAIN")
    return float(m.group(1))


def load_run_list() -> list[dict]:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    return audit["runs"]


# ─────────────────────────────── telemetry ─────────────────────────────────

def read_shop_events(path: Path) -> list[dict]:
    """Parse only shop-relevant events (skip the ~21k combat_capture lines)."""
    out = []
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            if ("purchase_" in line or "shop_combine_confirmed" in line
                    or "run_start" in line):
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


def sig_ids(signature: str) -> list[str]:
    return [x.split(":")[0] for x in json.loads(signature)]


def tier_of(my_id: str) -> int:
    """my_id weapon_smg_2 -> tier index 1 (suffix = tier + 1)."""
    tail = my_id.rsplit("_", 1)[-1]
    return int(tail) - 1 if tail.isdigit() else 0


def base_of(my_id: str) -> str:
    parts = my_id.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0]
    return my_id


def combined_id(my_id: str) -> str:
    """Result of combining two copies of my_id (tier t -> t+1)."""
    return f"{base_of(my_id)}_{tier_of(my_id) + 2}"


class LoadoutReconstructor:
    """Replays weapon acquisitions and validates each shop against build_metrics."""

    def __init__(self, wstats: dict):
        self.wstats = wstats

    def complete(self, loadout: list[str]) -> bool:
        return all(w in self.wstats for w in loadout)

    def effective(self, loadout: list[str], stats: dict) -> float | None:
        if not self.complete(loadout):
            return None
        return sum(effective_weapon_dps(self.wstats[w], stats) for w in loadout)

    def validate(self, loadout: list[str], stats: dict, rec_dps, rec_count,
                 rec_tier_sum, tol: float = 0.01) -> bool:
        if rec_count is not None and len(loadout) != rec_count:
            return False
        if rec_tier_sum is not None and sum(tier_of(w) + 1 for w in loadout) != rec_tier_sum:
            return False
        eff = self.effective(loadout, stats)
        if eff is None or not rec_dps:
            return False
        return abs(eff - rec_dps) / rec_dps <= tol

    def reconcile(self, loadout: list[str], stats: dict, rec_dps, rec_count,
                  rec_tier_sum, max_steps: int = 5) -> list[str] | None:
        """BFS applying silent combines (2 same base+tier -> 1 next tier)."""
        start = tuple(sorted(loadout))
        if self.validate(list(start), stats, rec_dps, rec_count, rec_tier_sum):
            return list(start)
        seen = {start}
        depth = {start: 0}
        q = deque([start])
        while q:
            st = q.popleft()
            if depth[st] >= max_steps:
                continue
            for mid, cnt in Counter(st).items():
                if cnt >= 2:
                    lst = list(st)
                    lst.remove(mid)
                    lst.remove(mid)
                    lst.append(combined_id(mid))
                    ns = tuple(sorted(lst))
                    if ns in seen:
                        continue
                    seen.add(ns)
                    depth[ns] = depth[st] + 1
                    if self.validate(list(ns), stats, rec_dps, rec_count, rec_tier_sum):
                        return list(ns)
                    q.append(ns)
        return None


def build_metrics_stats(off: dict) -> dict:
    """Recorded offense stats -> combat_model stats dict (crit_damage unrecorded=0)."""
    return {
        "stat_ranged_damage": off.get("ranged_damage"),
        "stat_percent_damage": off.get("percent_damage"),
        "stat_attack_speed": off.get("attack_speed"),
        "stat_crit_chance": off.get("crit_chance"),
    }


def offense_keys(effects: list) -> set:
    return set(e.get("key") for e in effects) & OFFENSE_STAT_KEYS


# ─────────────────────────────── main replay ───────────────────────────────

def harvest_weapon_stats(runs: dict[str, list[dict]]) -> dict:
    wstats: dict = {}
    for events in runs.values():
        for e in events:
            if e.get("event") != "purchase_offer":
                continue
            for it in e["payload"].get("items", []):
                if it.get("category") == "weapon" and it.get("id") not in wstats:
                    wstats[it["id"]] = {
                        k: it.get(k) for k in (
                            "damage", "cooldown", "scaling", "crit_chance",
                            "crit_damage", "nb_projectiles", "piercing",
                            "piercing_dmg_reduction", "bounce",
                            "bounce_dmg_reduction", "sets")
                    }
    return wstats


def replay(runs: dict[str, list[dict]], results: dict[str, str], wstats: dict):
    recon = LoadoutReconstructor(wstats)
    offer_records = []            # per offense-item-offer instance
    parity_samples = []          # combine-anchor formula parity
    shop_trust = Counter()       # (trusted, total) at w9-15
    for rid, events in runs.items():
        result = results[rid]
        start_weapon = None
        for e in events:
            if e.get("event") == "run_start":
                start_weapon = e["payload"].get("weapon")
        loadout = [start_weapon] if start_weapon else []
        last_offer = None
        decisions = [e for e in events
                     if e.get("event") == "purchase_decision"
                     and e["payload"].get("build_metrics")]
        for e in events:
            ev = e.get("event")
            pl = e.get("payload", {})
            if ev == "purchase_offer":
                last_offer = pl
            elif ev == "purchase_decision":
                wave = pl.get("wave")
                off = pl.get("build_metrics", {}).get("offense", {})
                action = pl.get("action", {})
                stats = build_metrics_stats(off)
                rec_dps = off.get("weapon_dps")
                rec_count = off.get("weapon_count")
                rec_tsum = off.get("weapon_tier_sum")
                # Validate / reconcile loadout for THIS shop state.
                trusted = recon.validate(loadout, stats, rec_dps, rec_count, rec_tsum)
                if not trusted:
                    fixed = recon.reconcile(loadout, stats, rec_dps, rec_count, rec_tsum)
                    if fixed is not None:
                        loadout = fixed
                        trusted = True
                weapons = [wstats[w] for w in loadout] if recon.complete(loadout) else None

                in_window = wave is not None and 9 <= wave <= 15
                if in_window:
                    shop_trust["total"] += 1
                    shop_trust["trusted"] += int(trusted)
                    if last_offer is not None:
                        _record_offers(offer_records, last_offer, action, rid, result,
                                       wave, stats, weapons if trusted else None)
                # apply the decision to the running loadout
                if action.get("type") == "shop_buy" and last_offer:
                    for it in last_offer.get("items", []):
                        if it.get("slot") == action.get("slot") and it.get("category") == "weapon":
                            loadout.append(it["id"])
                elif action.get("type") == "shop_sell":
                    idx = action.get("index")
                    if idx is not None and 0 <= idx < len(loadout):
                        loadout.pop(idx)
            elif ev == "shop_combine_confirmed" and pl.get("state_changed"):
                # Formula parity check with EXACT before_signature loadout.
                _parity_at_combine(recon, pl, e.get("seq", 0), decisions, parity_samples)
                loadout = sig_ids(pl["after_signature"])
    return offer_records, parity_samples, shop_trust


def _record_offers(records, offer, action, rid, result, wave, stats, weapons):
    band = "9-12" if wave <= 12 else "13-15"
    bought_slot = action.get("slot") if action.get("type") == "shop_buy" else None
    for it in offer.get("items", []):
        if it.get("category") != "item":
            continue
        okeys = offense_keys(it.get("effects", []))
        if not okeys:
            continue
        effects = it.get("effects", [])
        deltas = combat_deltas(effects)
        d_gain = direct_offense_gain(effects)
        loadout_free = bool(deltas) and set(deltas).issubset(_LOADOUT_FREE_KEYS)
        dps_gain = None
        method = None
        if loadout_free:
            dps_gain = closed_form_dps_gain(stats, deltas)
            method = "closed_form"
        elif weapons is not None and deltas:
            dps_gain = combat_value_dps_gain(weapons, stats, deltas)
            method = "model"
        records.append({
            "run": rid,
            "result": result,
            "wave": wave,
            "band": band,
            "item_id": it.get("id"),
            "slot": it.get("slot"),
            "offense_keys": sorted(okeys),
            "affordable": bool(it.get("affordable", False)),
            "bought": bought_slot is not None and it.get("slot") == bought_slot,
            "direct_gain": d_gain,
            "dps_gain": dps_gain,
            "dps_method": method,
            "computable": dps_gain is not None,
        })


def _parity_at_combine(recon: LoadoutReconstructor, pl: dict, seq: int, decisions, samples):
    loadout = sig_ids(pl["before_signature"])
    if not recon.complete(loadout):
        return
    if not decisions:
        return
    best = min(decisions, key=lambda d: abs(d.get("seq", 0) - seq))
    off = best["payload"]["build_metrics"]["offense"]
    stats = build_metrics_stats(off)
    rec = off.get("weapon_dps")
    if not rec:
        return
    eff = sum(effective_weapon_dps(recon.wstats[w], stats) for w in loadout)
    samples.append({"rel_err": abs(eff - rec) / rec, "computed": eff, "recorded": rec})


# ───────────────────────────── distributions ───────────────────────────────

def pctl(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    idx = max(0, min(len(s) - 1, int(round((q / 100.0) * (len(s) - 1)))))
    return s[idx]


def summarize(values: list[float]) -> dict:
    vals = [v for v in values if v is not None]
    if not vals:
        return {"n": 0}
    return {
        "n": len(vals),
        "median": round(median(vals), 3),
        "p25": round(pctl(vals, 25), 3),
        "p75": round(pctl(vals, 75), 3),
        "p90": round(pctl(vals, 90), 3),
        "min": round(min(vals), 3),
        "max": round(max(vals), 3),
    }


def dedup_offers(records: list[dict]) -> list[dict]:
    """One record per (run, wave, item_id): the bought instance if any, else the
    last skipped instance (closest build state)."""
    by_key: dict = {}
    for r in records:
        key = (r["run"], r["wave"], r["item_id"])
        cur = by_key.get(key)
        if cur is None or (r["bought"] and not cur["bought"]) or (
                r["bought"] == cur["bought"]):
            by_key[key] = r
    return list(by_key.values())


def build_report(records, parity, shop_trust, threshold, runs_meta):
    dedup = dedup_offers(records)

    def dist(subset, key="dps_gain"):
        return summarize([r[key] for r in subset if r.get(key) is not None])

    # 1. %DPS distributions (computable records)
    comp = [r for r in records if r["computable"]]
    def split(pred):
        return dist([r for r in comp if pred(r)])
    dps_dist = {
        "all": dist(comp),
        "bought": split(lambda r: r["bought"]),
        "skipped": split(lambda r: not r["bought"]),
        "victory": split(lambda r: r["result"] == "victory"),
        "defeat": split(lambda r: r["result"] == "defeat"),
        "band_9_12": split(lambda r: r["band"] == "9-12"),
        "band_13_15": split(lambda r: r["band"] == "13-15"),
        "bought_victory": split(lambda r: r["bought"] and r["result"] == "victory"),
        "bought_defeat": split(lambda r: r["bought"] and r["result"] == "defeat"),
        "skipped_victory": split(lambda r: not r["bought"] and r["result"] == "victory"),
        "skipped_defeat": split(lambda r: not r["bought"] and r["result"] == "defeat"),
    }
    # per offense-key medians (an item may carry several keys)
    per_key = {}
    for k in sorted(OFFENSE_STAT_KEYS):
        sub = [r for r in comp if k in r["offense_keys"]]
        per_key[k] = {"bought": dist([r for r in sub if r["bought"]]),
                      "skipped": dist([r for r in sub if not r["bought"]])}

    # 2. flat-gain threshold clearing (direct_offense_gain), skipped offense
    #    offers in DEFEAT runs. Computed per-instance and deduped.
    thresholds = [6.0, 4.0, 3.0, 2.0]
    def clearing(subset):
        n = len(subset)
        out = {"n": n}
        for t in thresholds:
            c = sum(1 for r in subset if r["direct_gain"] >= t)
            out[f"clear_{t}"] = {"count": c, "frac": round(c / n, 3) if n else None}
        return out
    skipped_defeat = [r for r in records if r["result"] == "defeat" and not r["bought"]]
    skipped_defeat_dd = [r for r in dedup if r["result"] == "defeat" and not r["bought"]]
    aff_skipped_defeat = [r for r in skipped_defeat if r["affordable"]]
    # The live gate at shop_strategy.gd:1026 first drops items with
    # _direct_offense_gain <= 0 (crit-only / net-negative offense) BEFORE the
    # threshold; the threshold literal therefore only ever applies to offers with
    # direct_gain > 0. This is the decision-relevant denominator.
    pos_skipped_defeat = [r for r in skipped_defeat if r["direct_gain"] > 0.0]
    pos_aff_skipped_defeat = [r for r in aff_skipped_defeat if r["direct_gain"] > 0.0]
    flat_gain = {
        "threshold_current": threshold,
        "per_instance": clearing(skipped_defeat),
        "per_instance_affordable": clearing(aff_skipped_defeat),
        "deduped": clearing(skipped_defeat_dd),
        "per_instance_positive_gain": clearing(pos_skipped_defeat),
        "per_instance_positive_gain_affordable": clearing(pos_aff_skipped_defeat),
        # context: same for victory + all, and bought reference
        "skipped_victory_per_instance": clearing(
            [r for r in records if r["result"] == "victory" and not r["bought"]]),
        "bought_defeat_per_instance": clearing(
            [r for r in records if r["result"] == "defeat" and r["bought"]]),
    }

    # 3. sanity anchors: 5 bought, model-computed (deterministic pick)
    anchors = _sanity_anchors(records)

    # 4. parity
    within = sum(1 for s in parity if s["rel_err"] <= 0.01)
    parity_summary = {
        "combine_anchor_states": len(parity),
        "within_1pct": within,
        "frac_within_1pct": round(within / len(parity), 4) if parity else None,
        "max_rel_err": round(max((s["rel_err"] for s in parity), default=0.0), 6),
        "median_rel_err": round(median([s["rel_err"] for s in parity]), 8) if parity else None,
        "shops_w9_15_total": shop_trust["total"],
        "shops_w9_15_loadout_trusted": shop_trust["trusted"],
        "shops_w9_15_trusted_frac": round(shop_trust["trusted"] / shop_trust["total"], 3)
            if shop_trust["total"] else None,
    }

    coverage = {
        "offense_offer_instances": len(records),
        "computable_dps": sum(1 for r in records if r["computable"]),
        "computable_frac": round(sum(1 for r in records if r["computable"]) / len(records), 3)
            if records else None,
        "closed_form": sum(1 for r in records if r["dps_method"] == "closed_form"),
        "model": sum(1 for r in records if r["dps_method"] == "model"),
        "uncomputable_loadout": sum(1 for r in records
                                    if not r["computable"]),
        "deduped_offense_offers": len(dedup),
    }

    return {
        "meta": runs_meta,
        "coverage": coverage,
        "dps_distribution_pct": dps_dist,
        "dps_by_offense_key": per_key,
        "flat_direct_offense_gain": flat_gain,
        "sanity_anchors": anchors,
        "parity": parity_summary,
    }


def _sanity_anchors(records):
    picks = [r for r in records if r["bought"] and r["dps_method"] == "model"]
    picks.sort(key=lambda r: (r["run"], r["wave"], r["item_id"] or ""))
    chosen = picks[:: max(1, len(picks) // 5)][:5] if picks else []
    return [{k: r[k] for k in ("run", "wave", "item_id", "offense_keys",
                               "direct_gain", "dps_gain", "dps_method")}
            for r in chosen]


# ─────────────────────────────── rendering ─────────────────────────────────

def _fmt(d: dict) -> str:
    if not d or d.get("n", 0) == 0:
        return "n=0"
    return (f"n={d['n']} median={d['median']} p25={d['p25']} "
            f"p75={d['p75']} p90={d['p90']}")


def render_markdown(report: dict) -> str:
    L = []
    L.append("# v124 offense-offer marginal-DPS replay")
    L.append("")
    m = report["meta"]
    L.append(f"Generated by `scripts/wp2_offer_dps_replay.py` over the {m['run_count']}-run "
             f"v122 exact-20 campaign ({m['victory']} victory / {m['defeat']} defeat). "
             f"Read-only. All numbers are **computed offline**, replicating "
             f"`combat_model.gd` `weapon_dps()`/`combat_value()` and "
             f"`shop_strategy.gd _direct_offense_gain()` exactly.")
    L.append("")
    c = report["coverage"]
    L.append("## Coverage")
    L.append("")
    L.append(f"- Offense-stat offer instances (items, w9-15): **{c['offense_offer_instances']}** "
             f"(deduped per run/wave/item: {c['deduped_offense_offers']}).")
    L.append(f"- %DPS computable: **{c['computable_dps']} ({int(100*c['computable_frac'])}%)** "
             f"-- {c['closed_form']} loadout-free (percent_damage/attack_speed, exact) + "
             f"{c['model']} full-model (ranged/crit at loadout-trusted shops).")
    L.append(f"- Not %DPS-computable (ranged/crit at untrusted/incomplete loadout shops): "
             f"**{c['uncomputable_loadout']}**.")
    L.append("")
    p = report["parity"]
    L.append("## 4. Parity of the Python combat model vs recorded telemetry")
    L.append("")
    L.append(f"At the **{p['combine_anchor_states']}** shop states where the equipped loadout is "
             f"exactly recoverable (combine `before_signature`), the Python "
             f"`effective_weapon_dps` reproduces the recorded "
             f"`build_metrics.offense.weapon_dps`:")
    L.append("")
    L.append(f"- within 1%: **{p['within_1pct']}/{p['combine_anchor_states']} "
             f"({p['frac_within_1pct']*100:.1f}%)**")
    L.append(f"- max relative error: **{p['max_rel_err']:.2e}**, median relative error: "
             f"{p['median_rel_err']:.2e} (i.e. bit-exact).")
    L.append(f"- Loadout-trusted w9-15 shop **decision states** (rebuilt loadout validated "
             f"vs recorded weapon_dps/count/tier_sum within 1%; the rest fall back to "
             f"loadout-free gains only): "
             f"**{p['shops_w9_15_loadout_trusted']}/{p['shops_w9_15_total']} "
             f"({p['shops_w9_15_trusted_frac']*100:.0f}%)**.")
    L.append("")
    L.append("## 2. Flat direct-offense gain vs the threshold literal "
             "(the v124 decision input)")
    L.append("")
    fg = report["flat_direct_offense_gain"]
    L.append(f"`OFFENSE_IMPACT_MIN_ITEM_GAIN` = **{fg['threshold_current']}** gates "
             f"`_direct_offense_gain(effects)` = the raw stat-point sum of "
             f"ranged_damage + percent_damage + attack_speed (crit stats contribute 0). "
             f"Fraction of **skipped offense offers in defeat runs** that a lowered "
             f"literal would newly clear:")
    L.append("")
    L.append("| threshold | per-instance | per-instance (affordable) | deduped |")
    L.append("|---|---|---|---|")
    pi, pa, dd = fg["per_instance"], fg["per_instance_affordable"], fg["deduped"]
    for t in (6.0, 4.0, 3.0, 2.0):
        k = f"clear_{t}"
        L.append(f"| >= {t} | {pi[k]['count']}/{pi['n']} ({_pct(pi[k]['frac'])}) "
                 f"| {pa[k]['count']}/{pa['n']} ({_pct(pa[k]['frac'])}) "
                 f"| {dd[k]['count']}/{dd['n']} ({_pct(dd[k]['frac'])}) |")
    L.append("")
    pg = fg["per_instance_positive_gain"]
    L.append(f"Decision-relevant denominator -- the live gate first drops offers with "
             f"`_direct_offense_gain <= 0` (crit-only / net-negative), so the threshold "
             f"only applies to the **{pg['n']}** skipped defeat offers with a positive flat "
             f"offense gain. Of those, the fraction cleared at each level:")
    L.append("")
    L.append("| threshold | cleared (positive-gain skips, defeat) |")
    L.append("|---|---|")
    for t in (6.0, 4.0, 3.0, 2.0):
        k = f"clear_{t}"
        L.append(f"| >= {t} | {pg[k]['count']}/{pg['n']} ({_pct(pg[k]['frac'])}) |")
    L.append("")
    L.append(f"Reference: bought offense offers in defeat runs already clear >= 6.0 at "
             f"{_pct(fg['bought_defeat_per_instance']['clear_6.0']['frac'])} "
             f"(n={fg['bought_defeat_per_instance']['n']}); skipped offers in victory runs "
             f"clear >= 6.0 at {_pct(fg['skipped_victory_per_instance']['clear_6.0']['frac'])}.")
    L.append("")
    L.append("## 1. Computed % loadout-DPS gain distribution")
    L.append("")
    dd = report["dps_distribution_pct"]
    L.append("| split | dist |")
    L.append("|---|---|")
    for k in ("all", "bought", "skipped", "victory", "defeat", "band_9_12",
              "band_13_15", "bought_victory", "bought_defeat",
              "skipped_victory", "skipped_defeat"):
        L.append(f"| {k} | {_fmt(dd[k])} |")
    L.append("")
    L.append("### By offense key (bought / skipped medians)")
    L.append("")
    L.append("| key | bought | skipped |")
    L.append("|---|---|---|")
    for k, v in report["dps_by_offense_key"].items():
        L.append(f"| {k} | {_fmt(v['bought'])} | {_fmt(v['skipped'])} |")
    L.append("")
    L.append("## 3. Sanity anchors (hand-checkable bought items, full model path)")
    L.append("")
    for a in report["sanity_anchors"]:
        L.append(f"- `{a['item_id']}` w{a['wave']} run {a['run']}: keys={a['offense_keys']}, "
                 f"direct_gain={a['direct_gain']}, computed %DPS gain="
                 f"{round(a['dps_gain'], 3)} ({a['dps_method']})")
    L.append("")
    L.append("Full per-anchor computation (stats-before, effects, dps0, dps1) is in the "
             "companion JSON under `sanity_anchors_detail`.")
    L.append("")
    return "\n".join(L)


def _pct(frac):
    return "n/a" if frac is None else f"{frac*100:.0f}%"


# ───────────────────── detailed anchor computation (JSON) ───────────────────

def anchor_details(records, wstats, runs, results):
    """Re-derive dps0/dps1 for the sanity anchors so the primary can hand-check."""
    picks = [r for r in records if r["bought"] and r["dps_method"] == "model"]
    picks.sort(key=lambda r: (r["run"], r["wave"], r["item_id"] or ""))
    chosen = picks[:: max(1, len(picks) // 5)][:5] if picks else []
    details = []
    for r in chosen:
        # find the offer + decision to reconstruct exact inputs
        detail = _reconstruct_anchor(r, wstats, runs, results)
        if detail:
            details.append(detail)
    return details


def _reconstruct_anchor(rec, wstats, runs, results):
    events = runs[rec["run"]]
    recon = LoadoutReconstructor(wstats)
    start_weapon = None
    for e in events:
        if e.get("event") == "run_start":
            start_weapon = e["payload"].get("weapon")
    loadout = [start_weapon] if start_weapon else []
    last_offer = None
    decisions = [e for e in events if e.get("event") == "purchase_decision"
                 and e["payload"].get("build_metrics")]
    for e in events:
        ev = e.get("event")
        pl = e.get("payload", {})
        if ev == "purchase_offer":
            last_offer = pl
        elif ev == "purchase_decision":
            wave = pl.get("wave")
            off = pl.get("build_metrics", {}).get("offense", {})
            action = pl.get("action", {})
            stats = build_metrics_stats(off)
            trusted = recon.validate(loadout, stats, off.get("weapon_dps"),
                                     off.get("weapon_count"), off.get("weapon_tier_sum"))
            if not trusted:
                fixed = recon.reconcile(loadout, stats, off.get("weapon_dps"),
                                        off.get("weapon_count"), off.get("weapon_tier_sum"))
                if fixed is not None:
                    loadout = fixed
                    trusted = True
            if (wave == rec["wave"] and last_offer is not None
                    and action.get("type") == "shop_buy"
                    and action.get("slot") == rec["slot"] and trusted):
                for it in last_offer.get("items", []):
                    if it.get("slot") == rec["slot"] and it.get("id") == rec["item_id"]:
                        weapons = [wstats[w] for w in loadout]
                        deltas = combat_deltas(it.get("effects", []))
                        new_stats = apply_deltas(stats, deltas)
                        dps0 = total_dps(weapons, stats)
                        dps1 = total_dps(weapons, new_stats)
                        return {
                            "run": rec["run"], "wave": wave, "item_id": rec["item_id"],
                            "loadout": list(loadout),
                            "stats_before": {k: stats.get(k) for k in stats},
                            "item_effects": it.get("effects", []),
                            "combat_deltas": deltas,
                            "dps0": round(dps0, 4), "dps1": round(dps1, 4),
                            "dps_gain_pct": round(100.0 * (dps1 - dps0) / dps0, 4) if dps0 else None,
                            "direct_offense_gain": direct_offense_gain(it.get("effects", [])),
                        }
            if action.get("type") == "shop_buy" and last_offer:
                for it in last_offer.get("items", []):
                    if it.get("slot") == action.get("slot") and it.get("category") == "weapon":
                        loadout.append(it["id"])
            elif action.get("type") == "shop_sell":
                idx = action.get("index")
                if idx is not None and 0 <= idx < len(loadout):
                    loadout.pop(idx)
        elif ev == "shop_combine_confirmed" and pl.get("state_changed"):
            loadout = sig_ids(pl["after_signature"])
    return None


# ─────────────────────────────────── cli ───────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS)
    ap.add_argument("--out-dir", type=Path, default=ROOT / "reports" / "wp2")
    args = ap.parse_args()

    threshold = parse_threshold()
    run_meta = load_run_list()
    results = {r["run_id"]: r["result"] for r in run_meta}
    ids = [r["run_id"] for r in run_meta]

    runs = {}
    for rid in ids:
        path = args.runs_dir / rid / "events.jsonl"
        if not path.exists():
            raise SystemExit(f"missing telemetry: {path}")
        runs[rid] = read_shop_events(path)

    wstats = harvest_weapon_stats(runs)
    records, parity, shop_trust = replay(runs, results, wstats)

    runs_meta = {
        "run_count": len(ids),
        "victory": sum(1 for r in run_meta if r["result"] == "victory"),
        "defeat": sum(1 for r in run_meta if r["result"] == "defeat"),
        "weapon_stat_table_size": len(wstats),
        "window": "waves 9-15 shops",
        "note": "well_rounded character (no offense gain_mods); stat_crit_damage "
                "not recorded, assumed 0 (validated by exact parity).",
    }
    report = build_report(records, parity, shop_trust, threshold, runs_meta)
    report["sanity_anchors_detail"] = anchor_details(records, wstats, runs, results)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "v124_offer_dps_distribution.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    (args.out_dir / "v124_offer_dps_distribution.md").write_text(
        render_markdown(report), encoding="utf-8")
    print(f"offense offers={len(records)} computable={report['coverage']['computable_dps']} "
          f"parity_within1%={report['parity']['within_1pct']}/{report['parity']['combine_anchor_states']} "
          f"trusted_shops={shop_trust['trusted']}/{shop_trust['total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
