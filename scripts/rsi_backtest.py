"""Backtest the v81 Run Strength Index against historical run telemetry.

Read-only: replays build_metrics-carrying runs (v76+) and computes per-wave
RSI using the SAME constants and target curves as the mod, parsed directly
from teacher/config.gd so the two implementations cannot drift.

Usage:
    python scripts/rsi_backtest.py [--runs-dir PATH] [--min-wave 13] [--max-wave 19]

Outputs a per-run table (RSI at wave 15, run RSI over the window, band
deficit, result) and a win/loss separation summary.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "mod" / "mods-unpacked" / "Tom-BrotatoAgent" / "teacher" / "config.gd"
DEFAULT_RUNS = Path(os.environ.get("APPDATA", "")) / "Brotato" / "brotato_agent" / "runs"


def parse_config() -> dict:
    text = CONFIG.read_text(encoding="utf-8")

    def const(name: str) -> float:
        match = re.search(rf"const {name} := ([0-9.]+)", text)
        if match is None:
            raise SystemExit(f"config.gd is missing const {name}")
        return float(match.group(1))

    def curve(name: str) -> list[float]:
        match = re.search(rf"const {name} := \[(.*?)\]", text, re.DOTALL)
        if match is None:
            raise SystemExit(f"config.gd is missing const {name}")
        values = [float(v) for v in re.findall(r"[0-9]+\.[0-9]+", match.group(1))]
        if len(values) != 20:
            raise SystemExit(f"{name} must have 20 entries, found {len(values)}")
        return values

    return {
        "w_power": const("RSI_WEIGHT_POWER"),
        "w_control": const("RSI_WEIGHT_CONTROL"),
        "w_durability": const("RSI_WEIGHT_DURABILITY"),
        "w_conversion": const("RSI_WEIGHT_CONVERSION"),
        "power_cap": const("RSI_POWER_CAP"),
        "p90_ref": const("RSI_CONTROL_P90_REF"),
        "band_from": int(const("OFFENSE_BAND_FROM_WAVE")),
        "gold_reserve": const("SHOP_MED_GOLD_RESERVE"),
        "dps_targets": curve("OFFENSE_DPS_TARGETS_BY_WAVE"),
        "ehp_targets": curve("DEFENSE_EHP_TARGETS_BY_WAVE"),
        "enemy_hit_base": const("ENEMY_HIT_BASE"),
        "enemy_hit_per_wave": const("ENEMY_HIT_PER_WAVE"),
        "min_taken_frac": const("MIN_DAMAGE_TAKEN_FRAC"),
        "dodge_cap": const("DODGE_CAP_DEFAULT"),
        "regen_window": const("REGEN_WINDOW"),
        "lifesteal_weight": const("LIFESTEAL_EHP_WEIGHT"),
    }


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def ehp_index(defense: dict, wave: int, cfg: dict) -> float:
    max_hp = max(1.0, float(defense.get("max_hp") or 0.0))
    armor = float(defense.get("armor") or 0.0)
    dodge = clamp(float(defense.get("dodge") or 0.0), 0.0, cfg["dodge_cap"]) / 100.0
    enemy_hit = cfg["enemy_hit_base"] + cfg["enemy_hit_per_wave"] * max(0, wave)
    taken = max(enemy_hit * cfg["min_taken_frac"], max(enemy_hit - armor, 1.0))
    ehp = max_hp * (enemy_hit / taken) / (1.0 - dodge)
    ehp += float(defense.get("hp_regeneration") or 0.0) * cfg["regen_window"]
    ehp += float(defense.get("lifesteal") or 0.0) * cfg["lifesteal_weight"]
    return ehp


def rsi(dps: float, dps_target: float, ehp: float, ehp_target: float,
        p90: float, conversion: float, cfg: dict) -> dict:
    power = clamp(dps / max(dps_target, 1.0), 0.0, cfg["power_cap"])
    control = clamp(cfg["p90_ref"] / max(p90, cfg["p90_ref"]), 0.0, 1.0)
    durability = clamp(ehp / max(ehp_target, 1.0), 0.0, 1.0)
    conv = clamp(conversion, 0.0, 1.0)
    total = 100.0 * (cfg["w_power"] * power + cfg["w_control"] * control
                     + cfg["w_durability"] * durability + cfg["w_conversion"] * conv)
    return {"power": power, "control": control, "durability": durability,
            "conversion": conv, "total": total}


def analyze_run(events_path: Path, cfg: dict) -> dict | None:
    result = None
    per_wave_metrics: dict[int, dict] = {}
    density: dict[int, list[float]] = {}
    shop_entry_gold: dict[int, float] = {}
    shop_exit_gold: dict[int, float] = {}
    with events_path.open("r", encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = event.get("event", "")
            payload = event.get("payload", {}) or {}
            if kind == "run_end":
                result = str(payload.get("result", ""))
            metrics = payload.get("build_metrics")
            if isinstance(metrics, dict):
                wave = int(metrics.get("wave", 0) or 0)
                if wave > 0:
                    per_wave_metrics[wave] = metrics
            if kind == "combat_tick":
                wave = int(payload.get("wave", 0) or 0)
                debug = payload.get("debug", {}) or {}
                density.setdefault(wave, []).append(float(debug.get("enemies", 0) or 0))
            elif kind == "purchase_decision":
                wave = int(payload.get("wave", 0) or 0)
                gold = float(payload.get("gold_before", 0) or 0)
                shop_entry_gold.setdefault(wave, gold)
                action = payload.get("action", {}) or {}
                if str(action.get("type", "")) == "shop_go":
                    shop_exit_gold[wave] = gold
    if not per_wave_metrics:
        return None

    def p90_of(wave: int) -> float:
        samples = sorted(density.get(wave, []))
        if not samples:
            return 0.0
        idx = max(0, min(len(samples) - 1, int(-(-0.9 * len(samples) // 1)) - 1))
        return samples[idx]

    per_wave_rsi: dict[int, dict] = {}
    for wave, metrics in sorted(per_wave_metrics.items()):
        offense = metrics.get("offense", {}) or {}
        defense = metrics.get("defense", {}) or {}
        dps = float(offense.get("weapon_dps", 0) or 0)
        idx = min(max(wave, 1), 20) - 1
        dps_target = cfg["dps_targets"][idx]
        ehp_target = cfg["ehp_targets"][idx]
        ehp = ehp_index(defense, wave, cfg)
        conversion = 1.0
        if wave >= cfg["band_from"] and dps < dps_target and wave in shop_exit_gold:
            entry = max(shop_entry_gold.get(wave, 1.0), 1.0)
            leftover = max(0.0, shop_exit_gold[wave] - cfg["gold_reserve"])
            conversion = clamp(1.0 - leftover / entry, 0.0, 1.0)
        per_wave_rsi[wave] = rsi(dps, dps_target, ehp, ehp_target, p90_of(wave),
                                 conversion, cfg)
    return {"result": result, "per_wave": per_wave_rsi}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--min-wave", type=int, default=13)
    parser.add_argument("--max-wave", type=int, default=19)
    args = parser.parse_args()

    cfg = parse_config()
    rows = []
    for events_path in sorted(args.runs_dir.glob("*/events.jsonl")):
        analysis = analyze_run(events_path, cfg)
        if analysis is None or analysis["result"] not in ("victory", "defeat"):
            continue
        per_wave = analysis["per_wave"]
        window = [per_wave[w]["total"] for w in per_wave
                  if args.min_wave <= w <= args.max_wave]
        if not window:
            continue
        deficit = sum(max(0.0, 1.0 - per_wave[w]["power"]) for w in per_wave
                      if args.min_wave <= w <= args.max_wave)
        rows.append({
            "run": events_path.parent.name,
            "result": analysis["result"],
            "rsi_w15": per_wave.get(15, {}).get("total"),
            "run_rsi": sum(window) / len(window),
            "band_deficit": deficit,
        })

    if not rows:
        print("No scored build_metrics runs found.")
        return 1

    print(f"{'run':<26} {'result':<8} {'RSI@15':>7} {'runRSI':>7} {'deficit':>8}")
    for row in rows:
        w15 = "-" if row["rsi_w15"] is None else f"{row['rsi_w15']:.0f}"
        print(f"{row['run']:<26} {row['result']:<8} {w15:>7} "
              f"{row['run_rsi']:>7.1f} {row['band_deficit']:>8.2f}")

    wins = [r["run_rsi"] for r in rows if r["result"] == "victory"]
    losses = [r["run_rsi"] for r in rows if r["result"] == "defeat"]
    if wins and losses:
        print(f"\nwins  : n={len(wins)}  min runRSI={min(wins):.1f}  median~{sorted(wins)[len(wins)//2]:.1f}")
        print(f"losses: n={len(losses)}  max runRSI={max(losses):.1f}  median~{sorted(losses)[len(losses)//2]:.1f}")
        separated = min(wins) > max(losses)
        print(f"separation (min win > max loss): {'YES' if separated else 'NO'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
