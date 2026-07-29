"""Phase A parity gate: offline port of the live level-up scorer.

Read-only. Replays every recorded `level_up_decision` event and re-scores the
FULL option set with a Python port of:

  * `teacher/combat_model.gd`  combat_value()  (dps + ehp + speed + flat_damage)
  * `teacher/combat_model.gd`  effective_hp()
  * `teacher/shop_strategy.gd` _utility_score() / _effects_value()
  * `teacher/shop_strategy.gd` _late_shop_pivot_bonus() / _saturated_defense_only()
  * `teacher/shop_strategy.gd` decide_levelup()  (BOTH paths)

The numeric core (weapon_dps / effective_weapon_dps / apply_deltas /
combat_value_dps_gain / effect_signed_value / combat_deltas /
direct_offense_gain / LoadoutReconstructor) is IMPORTED from
`scripts/wp2_offer_dps_replay.py`, where it is already bit-exact verified.

Two parity measures are reported SEPARATELY:
  ARGMAX parity -- port's chosen index vs logged `action.index`
  SCORE  parity -- port's score for the LOGGED chosen index vs `action.score`

Usage:
    python scripts/wp2_levelup_scorer_parity.py [--runs-dir PATH] [--ablate ...]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from wp2_offer_dps_replay import (  # noqa: E402
    LoadoutReconstructor,
    _f,
    apply_deltas,
    combat_deltas,
    direct_offense_gain,
    effect_signed_value,
    total_dps,
    tier_of,
    sig_ids,
)

DEFAULT_RUNS = Path("C:/Users/moxhe/AppData/Roaming/Brotato/brotato_agent/runs")

# ───────────────────────── config.gd constants ──────────────────────────────
DPS_PRIORITY = 1.0
DEF_PRIORITY = 0.55
SPEED_VALUE = 0.6
ENEMY_HIT_BASE = 8.0
ENEMY_HIT_PER_WAVE = 2.5
MIN_DAMAGE_TAKEN_FRAC = 0.25
REGEN_WINDOW = 6.0
DODGE_CAP_DEFAULT = 70.0
EHP_REF = 50.0
UNKNOWN_EFFECT_WEIGHT = 0.3
MID_SHOP_PIVOT_WAVE = 9
SUSTAIN_CAP_WAVE = 8
LATE_SHOP_WAVE = 15
FINAL_SHOP_WAVE = 19
HARVESTING_DEADLINE_WAVE = 14.0
OFFENSE_FLOOR_MID = 70.0
OFFENSE_FLOOR_LATE = 120.0
DEFENSE_ADEQUATE_MID_MAX_HP = 45.0
DEFENSE_ADEQUATE_MID_ARMOR = 5.0
DEFENSE_ADEQUATE_MID_SUSTAIN = 8.0
DEFENSE_ADEQUATE_MAX_HP = 60.0
DEFENSE_ADEQUATE_ARMOR = 8.0
DEFENSE_ADEQUATE_SUSTAIN = 10.0
OFFENSE_TARGET_MARGIN = 25.0
OFFENSE_DENSITY_P90_GOAL = 15.0
OFFENSE_DENSITY_POINTS_PER_ENEMY = 7.0
OFFENSE_DENSITY_MAX_BONUS = 90.0
OFFENSE_DENSITY_PEAK_GOAL = 25.0
OFFENSE_DENSITY_POINTS_PER_PEAK_ENEMY = 2.0
OFFENSE_DENSITY_MAX_PEAK_BONUS = 30.0


def offense_target(wave: int, p90: float, peak: float) -> float:
    """shop_strategy.gd _offense_target(). NOTE: this is NOT build_metrics
    .offense.target, which comes from agent_controller _metric_targets()."""
    if wave >= LATE_SHOP_WAVE:
        base = OFFENSE_FLOOR_LATE
    elif wave >= MID_SHOP_PIVOT_WAVE:
        base = OFFENSE_FLOOR_MID
    else:
        return 0.0
    db = min(OFFENSE_DENSITY_MAX_BONUS, max(0.0,
             (p90 - OFFENSE_DENSITY_P90_GOAL) * OFFENSE_DENSITY_POINTS_PER_ENEMY))
    pb = min(OFFENSE_DENSITY_MAX_PEAK_BONUS, max(0.0,
             (peak - OFFENSE_DENSITY_PEAK_GOAL) * OFFENSE_DENSITY_POINTS_PER_PEAK_ENEMY))
    return base + OFFENSE_TARGET_MARGIN + db + pb

UTILITY_WEIGHTS = {
    "stat_lifesteal": 1.0, "stat_range": 0.25, "stat_harvesting": 0.85,
    "stat_engineering": 0.4, "stat_luck": 0.9, "stat_accuracy": 0.2,
    "piercing": 5.0, "piercing_damage": 0.3, "bounce": 1.5,
    "damage_against_bosses": 0.25, "giant_crit_damage": 0.2,
    "explosion_damage": 0.2, "explosion_size": 1.2, "effect_explode": 2.0,
    "explode_on_death": 1.0, "explode_on_consumable": 0.5,
    "projectiles_on_death": 1.0,
    "effect_burning": 2.0, "burn_chance": 0.4, "burning_spread": 0.5,
    "burning_cooldown_reduction": 0.3,
    "hit_protection": 3.0, "jellyshield_count": 2.0, "consumable_heal": 0.4,
    "hp_regen_bonus": 0.8, "heal_on_crit_kill": 0.5,
    "heal_when_pickup_gold": 0.3, "hp_start_next_wave": 0.2,
    "hp_start_wave": 0.2, "hp_cap": 0.2,
    "xp_gain": 0.15, "free_rerolls": 2.0, "items_price": 0.5,
    "recycling_gains": 0.2, "gold_drops": 0.3, "chance_double_gold": 0.2,
    "gold_on_crit_kill": 0.2, "gain_pct_gold_start_wave": 0.2,
    "instant_gold_attracting": 0.05, "pickup_range": 0.1,
    "harvesting_growth": 0.3, "knockback": 0.0,
    "gain_random_primary_stats_on_go_to_next_wave": 3.0, "wandering_bot": 3.0,
    "tree_turrets": 2.0, "trees": 1.5, "one_shot_trees": 1.0,
    "alien_eyes": 1.0, "item_hourglass": 1.0, "item_box_gold": 1.0,
    "lose_hp_per_second": 3.0, "enemy_damage": 0.6, "enemy_health": 0.5,
    "enemy_speed": 0.55, "enemy_fruit_drops": 0.2, "number_of_enemies": 1.2,
    "extra_enemies_next_wave": 1.6, "extra_elite_next_wave_chance": 0.4,
    "extra_loot_aliens_next_wave": 0.5, "fog_visibility": 0.3,
    "remove_speed": 0.5, "speed_cap": 0.3, "dodge_cap": 0.3,
}

# character_well_rounded profile (build_profiles.gd L271+ / build_profile.gd defaults)
WR = {
    "name": "well_rounded",
    "dps_gain_weight": 1.45,
    "ehp_value_multiplier": 1.45,
    "flat_damage_value": 0.55,
    "speed_value_multiplier": 1.15,
    "forbidden_stats": [],
    "utility_overrides": {
        "stat_harvesting": 2.8, "harvesting_growth": 2.2, "stat_luck": 2.2,
        "stat_lifesteal": 3.8, "number_of_enemies": 2.4,
        "extra_enemies_next_wave": 2.8, "extra_loot_aliens_next_wave": 1.2,
        "gold_drops": 1.4, "chance_double_gold": 1.2, "free_rerolls": 3.0,
        "items_price": 1.2, "recycling_gains": 1.8, "piercing": 7.0,
        "trees": 2.5,
    },
}

_COMBAT_STATS = frozenset({
    "stat_percent_damage", "stat_ranged_damage", "stat_melee_damage",
    "stat_elemental_damage", "stat_damage", "stat_attack_speed",
    "stat_crit_chance", "stat_crit_damage", "stat_max_hp", "stat_armor",
    "stat_dodge", "stat_hp_regeneration", "stat_speed",
})
_DAMAGE_STATS = ["stat_percent_damage", "stat_ranged_damage",
                 "stat_melee_damage", "stat_elemental_damage", "stat_damage"]
# Deltas that can move total_dps at all.
_DPS_RELEVANT = frozenset({
    "stat_percent_damage", "stat_attack_speed", "stat_crit_chance",
    "stat_crit_damage", "stat_ranged_damage", "stat_melee_damage",
    "stat_elemental_damage", "stat_damage",
})
# Deltas that move total_dps by a uniform scalar (loadout-independent).
_LOADOUT_FREE = frozenset({"stat_percent_damage", "stat_attack_speed"})


# ───────────────────────── combat_model.gd port ─────────────────────────────

def effective_hp(stats: dict, wave: int, caps: dict | None = None) -> float:
    caps = caps or {}
    max_hp = max(1.0, _f(stats.get("stat_max_hp")))
    armor = _f(stats.get("stat_armor"))
    dodge = _f(stats.get("stat_dodge")) / 100.0
    dodge_cap_raw = _f(caps.get("stat_dodge"))
    if dodge_cap_raw == 0.0:
        dodge_cap_raw = DODGE_CAP_DEFAULT
    dodge_cap = dodge_cap_raw / 100.0
    dodge = min(dodge_cap, max(0.0, dodge))
    enemy_hit = ENEMY_HIT_BASE + ENEMY_HIT_PER_WAVE * max(0, wave)
    taken = max(enemy_hit * MIN_DAMAGE_TAKEN_FRAC, max(enemy_hit - armor, 1.0))
    ehp = max_hp * (enemy_hit / taken) / (1.0 - dodge)
    ehp += _f(stats.get("stat_hp_regeneration")) * REGEN_WINDOW
    return ehp


def closed_form_dps_gain(stats: dict, deltas: dict) -> float:
    """Loadout-free % DPS gain: percent_damage / attack_speed are uniform scalars."""
    factor = 1.0
    if "stat_percent_damage" in deltas:
        p0 = _f(stats.get("stat_percent_damage"))
        factor *= (1.0 + (p0 + _f(deltas["stat_percent_damage"])) / 100.0) / (1.0 + p0 / 100.0)
    if "stat_attack_speed" in deltas:
        a0 = _f(stats.get("stat_attack_speed"))
        factor *= (1.0 + (a0 + _f(deltas["stat_attack_speed"])) / 100.0) / (1.0 + a0 / 100.0)
    return 100.0 * (factor - 1.0)


def combat_value(build: dict, deltas: dict, wave: int, ablate=()) -> float:
    weapons = build.get("weapons") or []
    stats = build.get("stats") or {}
    gain_mods = build.get("gain_mods") or {}
    caps = build.get("caps") or {}

    new_stats = apply_deltas(stats, deltas, gain_mods)

    dps0 = total_dps(weapons, stats)
    dps1 = total_dps(weapons, new_stats)
    ehp0 = effective_hp(stats, wave, caps)
    ehp1 = effective_hp(new_stats, wave, caps)

    dkeys = set(deltas) & _DPS_RELEVANT
    if not weapons:
        # No trusted loadout. Legal ONLY when the gain is loadout-independent.
        if not dkeys:
            dps_gain = 0.0
        elif dkeys.issubset(_LOADOUT_FREE):
            dps_gain = closed_form_dps_gain(stats, deltas)
        else:
            raise RuntimeError("combat_value needs a loadout for deltas %r" % sorted(dkeys))
    elif dps0 > 0:
        dps_gain = 100.0 * (dps1 - dps0) / dps0
    elif dps1 > 0:
        dps_gain = 100.0
    else:
        dps_gain = 0.0
    ehp_gain = 100.0 * (ehp1 - ehp0) / max(ehp0, EHP_REF)
    speed_gain = (_f(new_stats.get("stat_speed"))
                  - _f(stats.get("stat_speed"))) * SPEED_VALUE

    dps_weight = WR["dps_gain_weight"]
    flat_dmg_w = WR["flat_damage_value"]
    speed_w = WR["speed_value_multiplier"]
    ehp_w = WR["ehp_value_multiplier"]
    if wave >= LATE_SHOP_WAVE:  # profile.name == "well_rounded"
        dps_weight *= 1.50
        ehp_w *= 1.35
        flat_dmg_w = max(flat_dmg_w, 0.85)

    if "dps" in ablate:
        dps_gain = 0.0
    if "ehp" in ablate:
        ehp_gain = 0.0
    if "speed" in ablate:
        speed_gain = 0.0
    if "flat" in ablate:
        flat_dmg_w = 0.0

    score = (DPS_PRIORITY * dps_gain * dps_weight
             + DEF_PRIORITY * ehp_gain * ehp_w
             + speed_gain * speed_w)
    if flat_dmg_w != 0.0:
        for s in _DAMAGE_STATS:
            v = _f(deltas.get(s))
            if v != 0.0:
                gain = 1.0 + _f(gain_mods.get(s)) / 100.0
                score += v * max(0.0, gain) * flat_dmg_w
    return score


# ───────────────────────── shop_strategy.gd port ────────────────────────────

def utility_score(effects: list, wave: int) -> float:
    overrides = WR["utility_overrides"]
    score = 0.0
    for e in effects:
        key = e.get("key", "")
        if key in _COMBAT_STATS and key not in overrides:
            continue
        if key in overrides:
            w = overrides[key]
        elif key in UTILITY_WEIGHTS:
            w = UTILITY_WEIGHTS[key]
        else:
            w = UNKNOWN_EFFECT_WEIGHT
        if key in ("stat_harvesting", "harvesting_growth"):
            if wave >= LATE_SHOP_WAVE:
                w *= 0.10
            elif wave >= MID_SHOP_PIVOT_WAVE:
                w *= 0.40
            else:
                w *= max(0.35, (HARVESTING_DEADLINE_WAVE - wave) / HARVESTING_DEADLINE_WAVE)
        elif key == "stat_lifesteal":
            if wave >= LATE_SHOP_WAVE:
                w *= 2.35
            elif wave >= MID_SHOP_PIVOT_WAVE:
                w *= 1.90
            elif wave <= 14:
                w *= 1.75
            else:
                w *= 1.25
        elif key == "stat_luck":
            if wave >= LATE_SHOP_WAVE:
                w *= 0.20
            elif wave >= MID_SHOP_PIVOT_WAVE:
                w *= 0.55
            elif wave <= 12:
                w *= 1.35
        elif key in ("number_of_enemies", "extra_enemies_next_wave",
                     "extra_loot_aliens_next_wave", "gold_drops",
                     "chance_double_gold"):
            if wave >= LATE_SHOP_WAVE:
                w *= 0.15
            elif wave >= MID_SHOP_PIVOT_WAVE:
                w *= 0.50
        elif key in ("piercing", "piercing_damage", "bounce"):
            if wave >= LATE_SHOP_WAVE:
                w *= 1.90
            elif wave >= MID_SHOP_PIVOT_WAVE:
                w *= 1.40
        elif key in ("explosion_damage", "explosion_size", "effect_explode",
                     "explode_on_death", "projectiles_on_death", "burning_spread"):
            if wave >= LATE_SHOP_WAVE:
                w *= 2.25
            elif wave >= MID_SHOP_PIVOT_WAVE:
                w *= 1.55
        elif key == "damage_against_bosses":
            if wave >= FINAL_SHOP_WAVE:
                w *= 2.2
            elif wave >= LATE_SHOP_WAVE:
                w *= 0.25
            elif wave >= MID_SHOP_PIVOT_WAVE:
                w *= 0.60
        elif key in ("stat_max_hp", "stat_armor", "stat_dodge"):
            if wave >= LATE_SHOP_WAVE:
                w *= 1.45
            elif wave >= MID_SHOP_PIVOT_WAVE:
                w *= 1.25
        elif key in ("stat_ranged_damage", "stat_attack_speed"):
            if wave >= LATE_SHOP_WAVE:
                w *= 1.55
            elif wave >= MID_SHOP_PIVOT_WAVE:
                w *= 1.30
        score += w * effect_signed_value(e)
    return score


def saturated_defense_only(effects: list, build: dict, wave: int) -> bool:
    if wave < SUSTAIN_CAP_WAVE:
        return False
    st = build.get("stats") or {}
    late = wave >= LATE_SHOP_WAVE
    hp_floor = DEFENSE_ADEQUATE_MAX_HP if late else DEFENSE_ADEQUATE_MID_MAX_HP
    armor_floor = DEFENSE_ADEQUATE_ARMOR if late else DEFENSE_ADEQUATE_MID_ARMOR
    sustain_floor = DEFENSE_ADEQUATE_SUSTAIN if late else DEFENSE_ADEQUATE_MID_SUSTAIN
    hp = _f(st.get("stat_max_hp"))
    armor = _f(st.get("stat_armor"))
    sustain = _f(st.get("stat_hp_regeneration")) + _f(st.get("stat_lifesteal"))
    hp_gain = armor_gain = sustain_gain = 0.0
    for e in effects:
        val = effect_signed_value(e)
        if val <= 0.0:
            continue
        key = e.get("key", "")
        if key == "stat_max_hp":
            hp_gain += val
        elif key == "stat_armor":
            armor_gain += val
        elif key in ("stat_hp_regeneration", "stat_lifesteal"):
            sustain_gain += val
    if sustain_gain > 0.0 and sustain + sustain_gain >= sustain_floor:
        return True
    if direct_offense_gain(effects) > 0.0:
        return False
    return ((hp_gain > 0.0 and hp + hp_gain >= hp_floor)
            or (armor_gain > 0.0 and armor + armor_gain >= armor_floor)
            or (sustain_gain > 0.0 and sustain + sustain_gain >= sustain_floor))


def late_shop_pivot_bonus(effects: list, build: dict, wave: int,
                          offense: float, ablate=()) -> float:
    if "pivot" in ablate:
        return 0.0
    if saturated_defense_only(effects, build, wave):
        return -1e9
    st = build.get("stats") or {}
    max_hp = _f(st.get("stat_max_hp"))
    armor = _f(st.get("stat_armor"))
    dodge = _f(st.get("stat_dodge"))
    lifesteal = _f(st.get("stat_lifesteal"))
    sustain = _f(st.get("stat_hp_regeneration")) + _f(st.get("stat_lifesteal"))

    offense_starved_late = wave >= LATE_SHOP_WAVE and offense < OFFENSE_FLOOR_LATE
    hp_saturated = offense_starved_late and max_hp >= DEFENSE_ADEQUATE_MAX_HP
    armor_saturated = offense_starved_late and armor >= DEFENSE_ADEQUATE_ARMOR
    sustain_saturated = offense_starved_late and sustain >= DEFENSE_ADEQUATE_SUSTAIN
    defense_layers_adequate = ((hp_saturated and armor_saturated)
                               or (hp_saturated and sustain_saturated)
                               or (armor_saturated and sustain_saturated))
    late = wave >= LATE_SHOP_WAVE
    mid = wave >= MID_SHOP_PIVOT_WAVE
    bonus = 0.0
    for e in effects:
        key = e.get("key", "")
        val = effect_signed_value(e)
        if val == 0.0:
            continue
        if late:
            if key in ("stat_harvesting", "harvesting_growth", "stat_luck",
                       "number_of_enemies", "extra_enemies_next_wave",
                       "extra_loot_aliens_next_wave", "gold_drops"):
                if val > 0.0:
                    bonus -= val * 1.45
                continue
            if key == "stat_ranged_damage" and val > 0.0:
                bonus += val * (2.75 if offense < OFFENSE_FLOOR_LATE else 1.75)
            elif key == "stat_attack_speed" and val > 0.0:
                bonus += val * (2.40 if offense < OFFENSE_FLOOR_LATE else 1.50)
            elif key == "stat_percent_damage" and val > 0.0:
                bonus += val * (2.10 if offense < OFFENSE_FLOOR_LATE else 1.30)
            elif key == "stat_crit_chance" and val > 0.0:
                bonus += val * 0.75
            elif key == "stat_crit_damage" and val > 0.0:
                bonus += val * 0.50
            elif key in ("piercing", "piercing_damage", "bounce") and val > 0.0:
                bonus += val * (3.50 if offense < OFFENSE_FLOOR_LATE else 2.40)
            elif key in ("explosion_damage", "explosion_size", "effect_explode",
                         "explode_on_death", "projectiles_on_death",
                         "burning_spread") and val > 0.0:
                bonus += val * (2.00 if offense < OFFENSE_FLOOR_LATE else 1.10)
            elif key == "damage_against_bosses" and val > 0.0:
                bonus += val * (2.70 if wave >= FINAL_SHOP_WAVE else 0.10)
            elif key == "stat_max_hp" and val > 0.0:
                bonus += val * (-4.00 if hp_saturated else (0.85 if max_hp < 110.0 else 0.50))
            elif key == "stat_armor" and val > 0.0:
                bonus += val * (-12.00 if armor_saturated else (1.00 if armor < 14.0 else 0.55))
            elif key == "stat_dodge" and val > 0.0 and dodge < 60.0:
                bonus += val * (-4.00 if defense_layers_adequate else 1.65)
            elif key == "stat_lifesteal" and val > 0.0:
                bonus += val * (1.20 if lifesteal < 15.0 else 0.80)
            elif key == "stat_hp_regeneration" and val > 0.0:
                bonus += val * (-8.00 if sustain_saturated else 0.35)
            elif key == "jellyshield_count" and val > 0.0 and defense_layers_adequate:
                bonus -= val * 40.0
            elif key == "wandering_bot" and val > 0.0 and defense_layers_adequate:
                bonus -= val * 30.0
        elif mid:
            if val <= 0.0:
                continue
            if key in ("stat_harvesting", "harvesting_growth", "stat_luck"):
                bonus -= val * 1.10
            elif key in ("number_of_enemies", "extra_enemies_next_wave"):
                bonus -= val * 0.40
            elif key == "stat_ranged_damage":
                bonus += val * (2.40 if offense < OFFENSE_FLOOR_MID else 0.95)
            elif key == "stat_attack_speed":
                bonus += val * (2.10 if offense < OFFENSE_FLOOR_MID else 0.85)
            elif key == "stat_percent_damage":
                bonus += val * (1.85 if offense < OFFENSE_FLOOR_MID else 0.70)
            elif key in ("piercing", "piercing_damage", "bounce"):
                bonus += val * (3.20 if offense < OFFENSE_FLOOR_MID else 1.40)
            elif key in ("explosion_damage", "explosion_size", "effect_explode",
                         "explode_on_death", "projectiles_on_death", "burning_spread"):
                bonus += val * (1.85 if offense < OFFENSE_FLOOR_MID else 1.10)
            elif key == "stat_max_hp":
                bonus += val * (0.45 if offense < OFFENSE_FLOOR_MID else 1.00)
            elif key == "stat_armor":
                bonus += val * (0.35 if offense < OFFENSE_FLOOR_MID else 0.75)
            elif key == "stat_dodge" and dodge < 60.0:
                bonus += val * (0.35 if offense < OFFENSE_FLOOR_MID else 0.90)
            elif key == "stat_lifesteal":
                bonus += val * (0.75 if offense < OFFENSE_FLOOR_MID else 1.00)
        else:
            if val <= 0.0:
                continue
            if key == "stat_max_hp":
                if wave <= 11 and max_hp < 55.0:
                    bonus += val * 1.15
            elif key == "stat_armor":
                if wave >= 8 and armor < 10.0:
                    bonus += val * 0.70
            elif key == "stat_dodge":
                if wave >= 10 and dodge < 60.0:
                    bonus += val * 0.85
            elif key in ("stat_ranged_damage", "stat_attack_speed"):
                if wave >= 8:
                    bonus += val * 0.45
    return bonus


def effects_value(effects: list, build: dict, wave: int, ablate=()) -> float:
    if not effects:
        return 0.0
    return (combat_value(build, combat_deltas(effects), wave, ablate)
            + (0.0 if "utility" in ablate else utility_score(effects, wave)))


def option_score(effects: list, build: dict, wave: int, offense: float,
                 ablate=()) -> float:
    return (effects_value(effects, build, wave, ablate)
            + late_shop_pivot_bonus(effects, build, wave, offense, ablate))


def decide_levelup(options: list, build: dict, wave: int, offense: float,
                   target: float, ablate=()) -> dict:
    """Port of shop_strategy.gd decide_levelup(). forbidden_stats is [] for WR."""
    scores = {o["index"]: option_score(o.get("effects") or [], build, wave,
                                       offense, ablate) for o in options}
    if target > 0.0 and offense < target:
        best = None
        best_rank = -1e30
        best_score = -1e30
        for o in options:
            eff = o.get("effects") or []
            gain0 = direct_offense_gain(eff)
            if gain0 <= 0.0:
                continue
            s0 = scores[o["index"]]
            if s0 <= 0.0:
                continue
            rank0 = s0 + gain0 * 6.0
            if rank0 > best_rank:
                best, best_rank, best_score = o, rank0, s0
        if best is not None:
            return {"index": best["index"], "score": best_score,
                    "offense_first": True, "scores": scores}
    best = None
    best_score = -1e30
    for o in options:
        s = scores[o["index"]]
        if s > best_score:
            best_score, best = s, o
    return {"index": best["index"] if best else None, "score": best_score,
            "offense_first": False, "scores": scores}


# ───────────────────────────── telemetry replay ─────────────────────────────

_WANTED = ("run_start", "purchase_offer", "purchase_decision",
           "shop_combine_confirmed", "level_up_decision")


def read_events(path: Path) -> list:
    out = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not any(w in line for w in _WANTED):
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("event") in _WANTED:
                out.append(e)
    return out


def stats_from_metrics(bm: dict) -> dict:
    off = bm.get("offense") or {}
    dfn = bm.get("defense") or {}
    hp = dfn.get("max_hp_policy_stat")
    if hp is None:
        hp = dfn.get("max_hp")
    return {
        "stat_ranged_damage": off.get("ranged_damage"),
        "stat_percent_damage": off.get("percent_damage"),
        "stat_attack_speed": off.get("attack_speed"),
        "stat_crit_chance": off.get("crit_chance"),
        "stat_max_hp": hp,
        "stat_armor": dfn.get("armor"),
        "stat_dodge": dfn.get("dodge"),
        "stat_hp_regeneration": dfn.get("hp_regeneration"),
        "stat_lifesteal": dfn.get("lifesteal"),
    }


def needs_loadout(options: list) -> bool:
    for o in options:
        d = combat_deltas(o.get("effects") or [])
        keys = set(d) & _DPS_RELEVANT
        if keys and not keys.issubset(_LOADOUT_FREE):
            return True
    return False


def harvest_weapon_stats(run_events: dict) -> dict:
    wstats: dict = {}
    for events in run_events.values():
        for e in events:
            if e.get("event") != "purchase_offer":
                continue
            for it in e["payload"].get("items", []):
                if it.get("category") == "weapon" and it.get("id") not in wstats:
                    wstats[it["id"]] = {k: it.get(k) for k in (
                        "damage", "cooldown", "scaling", "crit_chance",
                        "crit_damage", "nb_projectiles", "piercing",
                        "piercing_dmg_reduction", "bounce",
                        "bounce_dmg_reduction", "sets")}
    return wstats


def dedup_key(pl: dict) -> tuple:
    bm = pl.get("build_metrics") or {}
    alts = json.dumps(pl.get("legal_alternatives"), sort_keys=True)
    act = pl.get("action") or {}
    return (bm.get("wave"), alts, act.get("index"), act.get("type"))


def collect(runs_dir: Path, cohort: str | None):
    """Returns (decisions, counters). cohort filters on (mod_version, policy_version)."""
    run_events = {}
    meta = {}
    for d in sorted(runs_dir.iterdir()):
        f = d / "events.jsonl"
        if not f.is_file():
            continue
        try:
            evs = read_events(f)
        except OSError:
            continue
        if not any(e.get("event") == "level_up_decision" for e in evs):
            continue
        rs = next((e["payload"] for e in evs if e.get("event") == "run_start"), {})
        run_events[d.name] = evs
        meta[d.name] = rs
    return run_events, meta


def replay(run_events: dict, meta: dict, wstats: dict, ablate=()):
    recon = LoadoutReconstructor(wstats)
    c = Counter()
    rows = []
    for rid, events in run_events.items():
        c["runs"] += 1
        rs = meta.get(rid, {})
        loadout = [rs["weapon"]] if rs.get("weapon") else []
        last_offer = None
        seen = set()
        for e in events:
            ev = e.get("event")
            pl = e.get("payload", {})
            if ev == "purchase_offer":
                last_offer = pl
            elif ev == "purchase_decision":
                bm = pl.get("build_metrics") or {}
                off = bm.get("offense") or {}
                st = stats_from_metrics(bm)
                fixed = recon.reconcile(loadout, st, off.get("weapon_dps"),
                                        off.get("weapon_count"),
                                        off.get("weapon_tier_sum"))
                if fixed is not None:
                    loadout = fixed
                action = pl.get("action") or {}
                if action.get("type") == "shop_buy" and last_offer:
                    for it in last_offer.get("items", []):
                        if (it.get("slot") == action.get("slot")
                                and it.get("category") == "weapon"):
                            loadout.append(it["id"])
                elif action.get("type") == "shop_sell":
                    idx = action.get("index")
                    if idx is not None and 0 <= idx < len(loadout):
                        loadout.pop(idx)
            elif ev == "shop_combine_confirmed" and pl.get("state_changed"):
                loadout = sig_ids(pl["after_signature"])
            elif ev == "level_up_decision":
                c["lud_raw"] += 1
                k = (rid,) + dedup_key(pl)
                if k in seen:
                    c["lud_dup"] += 1
                    continue
                seen.add(k)
                c["lud_distinct"] += 1
                action = pl.get("action") or {}
                if action.get("type") != "levelup_choose":
                    c["lud_not_choose_" + str(action.get("type"))] += 1
                    continue
                opts = pl.get("legal_alternatives") or []
                bm = pl.get("build_metrics") or {}
                if not opts or not bm:
                    c["lud_no_options_or_metrics"] += 1
                    continue
                c["lud_eligible"] += 1
                off = bm.get("offense") or {}
                wave = int(bm.get("wave") or 1)
                st = stats_from_metrics(bm)
                rec_dps = off.get("weapon_dps")
                need = needs_loadout(opts)
                fixed = recon.reconcile(loadout, st, rec_dps,
                                        off.get("weapon_count"),
                                        off.get("weapon_tier_sum"))
                trusted = fixed is not None
                if trusted:
                    loadout = fixed
                weapons = ([wstats[w] for w in loadout]
                           if recon.complete(loadout) else [])
                if need and not trusted:
                    c["excluded_recon_fail"] += 1
                    rows.append({"run": rid, "wave": wave, "excluded": True,
                                 "reason": "recon_fail",
                                 "loadout": list(loadout),
                                 "missing": [w for w in loadout if w not in wstats],
                                 "rec_count": off.get("weapon_count"),
                                 "rec_tier_sum": off.get("weapon_tier_sum")})
                    continue
                if not need:
                    c["loadout_free_decision"] += 1
                c["scored"] += 1
                build = {"weapons": weapons if trusted else [], "stats": st,
                         "gain_mods": {}, "caps": {}}
                if not need and not trusted:
                    # DPS term is identically 0 for every option; weapons unused.
                    build["weapons"] = []
                res = decide_levelup(opts, build, wave,
                                     float(off.get("total") or 0.0),
                                     offense_target(
                                         wave,
                                         float(off.get("previous_wave_p90_density") or 0.0),
                                         float(off.get("previous_wave_peak_density") or 0.0)),
                                     ablate)
                logged_i = action.get("index")
                logged_s = float(action.get("score") or 0.0)
                mine_s = res["scores"].get(logged_i)
                rows.append({
                    "run": rid, "wave": wave, "excluded": False,
                    "trusted": trusted, "needs_loadout": need,
                    "n_options": len(opts),
                    "logged_index": logged_i, "port_index": res["index"],
                    "argmax_ok": res["index"] == logged_i,
                    "logged_offense_first": bool(action.get("offense_first")),
                    "port_offense_first": res["offense_first"],
                    "logged_score": logged_s, "port_score": mine_s,
                    "abs_err": None if mine_s is None else abs(mine_s - logged_s),
                    "rel_err": None if mine_s is None else (
                        abs(mine_s - logged_s) / max(abs(logged_s), 1e-9)),
                    "keys": sorted({x.get("key") for o in opts
                                    for x in (o.get("effects") or [])}),
                    "chosen_keys": sorted({
                        x.get("key")
                        for o in opts if o.get("index") == logged_i
                        for x in (o.get("effects") or [])}),
                })
    return rows, c


# ───────────────────────────────── reporting ────────────────────────────────

def pctl(vals, q):
    if not vals:
        return None
    s = sorted(vals)
    return s[max(0, min(len(s) - 1, int(round(q / 100.0 * (len(s) - 1)))))]


def dist(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return {"n": 0}
    return {"n": len(vals), "min": min(vals), "p50": median(vals),
            "p90": pctl(vals, 90), "p99": pctl(vals, 99), "max": max(vals)}


def report(label, rows, c, tol=1e-4):
    scored = [r for r in rows if not r["excluded"]]
    print(f"\n===== {label} =====")
    print("counters:", dict(sorted(c.items())))
    n = len(scored)
    if n == 0:
        print("NO SCORED DECISIONS (denominator = 0)")
        return
    argmax_ok = sum(r["argmax_ok"] for r in scored)
    print(f"scored decisions: {n}")
    print(f"ARGMAX parity: {argmax_ok}/{n} = {argmax_ok/n:.4f}")
    ok_path = sum(r["logged_offense_first"] == r["port_offense_first"] for r in scored)
    print(f"path (offense_first) agreement: {ok_path}/{n} = {ok_path/n:.4f}")
    abs_e = [r["abs_err"] for r in scored]
    rel_e = [r["rel_err"] for r in scored]
    print("abs_err:", {k: (round(v, 6) if isinstance(v, float) else v)
                       for k, v in dist(abs_e).items()})
    print("rel_err:", {k: (round(v, 6) if isinstance(v, float) else v)
                       for k, v in dist(rel_e).items()})
    exact = sum(1 for v in abs_e if v is not None and v <= tol)
    near = sum(1 for v in rel_e if v is not None and v <= 1e-3)
    print(f"SCORE parity abs<={tol}: {exact}/{n} = {exact/n:.4f}"
          f" | rel<=1e-3: {near}/{n} = {near/n:.4f}")
    bad = [r for r in scored if r["rel_err"] is not None and r["rel_err"] > 1e-3]
    if bad:
        kc = Counter(tuple(r["chosen_keys"]) for r in bad)
        print("worst score mismatches by chosen effect keys (top 12):")
        for k, v in kc.most_common(12):
            print("   ", v, k)
        wc = Counter(r["wave"] for r in bad)
        print("mismatch by wave:", dict(sorted(wc.items())))
    bada = [r for r in scored if not r["argmax_ok"]]
    if bada:
        print("argmax mismatch by wave:", dict(sorted(Counter(r["wave"] for r in bada).items())))
        print("argmax mismatch by logged path:",
              dict(Counter(r["logged_offense_first"] for r in bada)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS)
    ap.add_argument("--ablate", default="",
                    help="comma list of dps,ehp,speed,flat,utility,pivot")
    args = ap.parse_args()
    ablate = tuple(x for x in args.ablate.split(",") if x)

    run_events, meta = collect(args.runs_dir, None)
    print(f"runs with level_up_decision: {len(run_events)}")

    cohort = Counter((meta[r].get("mod_version"), meta[r].get("policy_version"))
                     for r in run_events)
    print("\n--- cohort by (mod_version, policy_version), top 15 ---")
    for k, v in cohort.most_common(15):
        print(f"  {v:4d} runs  {k}")
    print(f"  ... {len(cohort)} distinct version pairs total")
    print("characters:", dict(Counter(meta[r].get("character") for r in run_events)))

    wstats = harvest_weapon_stats(run_events)
    print(f"weapon stat library harvested from offer boards: {len(wstats)} weapons")

    CUR = ("0.2.49-wp2-capture", "teacher_v1-0.1.129-gun-wp1")
    cur_runs = {r: e for r, e in run_events.items()
                if (meta[r].get("mod_version"), meta[r].get("policy_version")) == CUR}
    print(f"\ncurrent-era runs ({CUR}): {len(cur_runs)}")

    rows_cur, c_cur = replay(cur_runs, meta, wstats, ablate)
    report(f"CURRENT ERA {CUR} ablate={ablate}", rows_cur, c_cur)

    rows_all, c_all = replay(run_events, meta, wstats, ablate)
    report(f"ALL ERAS ablate={ablate}", rows_all, c_all)

    return rows_cur, rows_all


if __name__ == "__main__":
    main()
