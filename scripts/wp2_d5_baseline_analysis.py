#!/usr/bin/env python
"""Offline analysis of the Danger 5 baseline campaign.

Produces NUMBERS ONLY. This module deliberately prints no verdict and takes no
position on whether any hypothesis passed. Everything is guarded behind
``if __name__ == "__main__":`` so that importing it has no side effects.

Blocks:
  A  validity / arming identity (computed before any outcome is touched)
  B  primary outcome (victories, terminal-wave distribution, wave duration)
  C  per-wave economy (materials spawned / collected / left on ground / bank)
  D  reported components carrying no verdict (damage_taken, healing, rerolls, locks)
  E  field-variation audit (which fields actually vary; which are constant)

Groups are keyed by each run's own ``summary.json`` ``mod_version``. Different
mod builds are NEVER pooled.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from collections import Counter, OrderedDict
from typing import Any, Dict, List, Optional

# Runs excluded by identity, never by outcome.
HARD_EXCLUDED_RUN_IDS = {
    # pre-danger-latch build 0.2.58: cannot self-certify difficulty.
    "run_1785372250_76725",
}

# The game's own cap on simultaneous ground currency entities. A ground pile
# sitting at exactly this value is the GAME's cap, not truncation by our capture.
MAX_GOLDS = 50

# Threshold (seconds) for calling a drop in wave_time.elapsed_sec a RESET
# rather than jitter.
RESET_DROP_SEC = 1.0

# Lead time (seconds before the wave timer hits zero) for the sensitivity column.
LEAD_INSTANT_SEC = 1.0


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def runs_root() -> str:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise SystemExit("APPDATA is not set; cannot locate the live run archive.")
    return os.path.join(appdata, "Brotato", "brotato_agent", "runs")


def read_ids(path: str) -> List[str]:
    """Read run ids from a JSON state file (collected_run_ids) or a text list."""
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
    if isinstance(obj, dict):
        for key in ("collected_run_ids", "run_ids"):
            if isinstance(obj.get(key), list):
                return list(obj[key])
        raise SystemExit("%s: no collected_run_ids / run_ids list" % path)
    if isinstance(obj, list):
        return list(obj)
    raise SystemExit("%s: unrecognised shape" % path)


def desc(values: List[float]) -> Dict[str, Any]:
    """Descriptive stats with the denominator always attached."""
    vals = [v for v in values if v is not None]
    out: Dict[str, Any] = {"n": len(vals)}
    if not vals:
        out.update(median=None, mean=None, sd=None, min=None, max=None)
        return out
    out["median"] = statistics.median(vals)
    out["mean"] = statistics.fmean(vals)
    out["sd"] = statistics.stdev(vals) if len(vals) > 1 else None
    out["min"] = min(vals)
    out["max"] = max(vals)
    return out


# --------------------------------------------------------------------------
# per-run extraction
# --------------------------------------------------------------------------
class WaveAcc:
    """Accumulator for one wave of one run."""

    def __init__(self, wave: int) -> None:
        self.wave = wave
        self.captures = 0
        self.first_elapsed: Optional[float] = None
        self.last_elapsed: Optional[float] = None
        self.max_elapsed_before_reset: Optional[float] = None
        self.reset_detected = False
        self._reset_seen = False
        self.duration_sec: Optional[float] = None

        # material entity tracking (ground currency)
        self.ground_instances: Dict[int, float] = {}   # instance_id -> value
        self.ground_max_count = 0
        self.ground_at_cap_captures = 0
        self.dropped_materials_max = 0
        self.invalid_materials_max = 0

        # the two candidate measurement instants
        self.pre_zero_ground_value: Optional[float] = None    # AUTHORITATIVE
        self.pre_zero_ground_count: Optional[int] = None
        self.pre_zero_elapsed: Optional[float] = None
        self.pre_zero_seq: Optional[int] = None
        self.pre_zero_bank: Optional[int] = None

        # third instant: a fixed LEAD TIME before the timer hits zero. The
        # authoritative instant lands at remaining_sec ~= 0.05, which may already
        # be inside the game's end-of-wave vacuum; this column makes the
        # sensitivity of the figure to the instant visible instead of assumed.
        self.lead_ground_value: Optional[float] = None
        self.lead_ground_count: Optional[int] = None
        self.lead_remaining: Optional[float] = None

        self.last_capture_ground_value: Optional[float] = None  # AFTER the sweep
        self.last_capture_ground_count: Optional[int] = None
        self.last_capture_seq: Optional[int] = None
        self.last_capture_bank: Optional[int] = None

        self.post_zero_captures = 0

        # bank (player.materials) inside combat
        self.bank_first: Optional[int] = None
        self.bank_last: Optional[int] = None

        # hp / damage components
        self.hp_first: Optional[float] = None
        self.hp_last: Optional[float] = None
        self.hp_increase_total = 0.0
        self.player_damage_events = 0
        self.player_damage_amount = 0.0

        # shop outflow (attributed to the shop that FOLLOWS this wave)
        self.shop_buy_spend = 0
        self.shop_reroll_spend = 0
        self.shop_buys = 0
        self.shop_rerolls = 0
        self.shop_locks = 0
        self.shop_unlocks = 0
        self.shop_sells = 0
        self.shop_gold_before_first: Optional[int] = None
        self.shop_gold_before_last: Optional[int] = None

    def add_capture(self, seq: int, payload: Dict[str, Any]) -> None:
        self.captures += 1
        wt = payload.get("wave_time") or {}
        elapsed = wt.get("elapsed_sec")
        remaining = wt.get("remaining_sec")
        if self.duration_sec is None:
            self.duration_sec = wt.get("duration_sec")

        if isinstance(elapsed, (int, float)):
            if self.first_elapsed is None:
                self.first_elapsed = elapsed
            if (
                self.last_elapsed is not None
                and elapsed < self.last_elapsed - RESET_DROP_SEC
            ):
                self.reset_detected = True
                self._reset_seen = True
            self.last_elapsed = elapsed
            if not self._reset_seen:
                if (
                    self.max_elapsed_before_reset is None
                    or elapsed > self.max_elapsed_before_reset
                ):
                    self.max_elapsed_before_reset = elapsed

        player = payload.get("player") or {}
        bank = player.get("materials")
        if isinstance(bank, (int, float)):
            if self.bank_first is None:
                self.bank_first = bank
            self.bank_last = bank
        hp = player.get("hp")
        if isinstance(hp, (int, float)):
            if self.hp_first is None:
                self.hp_first = hp
            elif hp > self.hp_last:
                self.hp_increase_total += hp - self.hp_last
            self.hp_last = hp

        mats = ((payload.get("entities") or {}).get("materials")) or []
        total_value = 0.0
        for ent in mats:
            iid = ent.get("instance_id")
            val = ent.get("value")
            val = val if isinstance(val, (int, float)) else 0.0
            total_value += val
            if isinstance(iid, int):
                self.ground_instances[iid] = val
        if len(mats) > self.ground_max_count:
            self.ground_max_count = len(mats)
        if len(mats) >= MAX_GOLDS:
            self.ground_at_cap_captures += 1

        dropped = ((payload.get("dropped_counts") or {}).get("materials"))
        if isinstance(dropped, int) and dropped > self.dropped_materials_max:
            self.dropped_materials_max = dropped
        invalid = ((payload.get("invalid_counts") or {}).get("materials"))
        if isinstance(invalid, int) and invalid > self.invalid_materials_max:
            self.invalid_materials_max = invalid

        # --- the two instants ---------------------------------------------
        # AUTHORITATIVE: last capture with remaining_sec > 0. combat_capture
        # events continue for tens of ticks after the timer hits zero, and the
        # game's end-of-wave sweep happens INSIDE that window, so the final
        # capture reads ~0 left behind.
        if isinstance(remaining, (int, float)) and remaining > 0:
            self.pre_zero_ground_value = total_value
            self.pre_zero_ground_count = len(mats)
            self.pre_zero_elapsed = elapsed
            self.pre_zero_seq = seq
            self.pre_zero_bank = bank
        else:
            self.post_zero_captures += 1
        if isinstance(remaining, (int, float)) and remaining >= LEAD_INSTANT_SEC:
            self.lead_ground_value = total_value
            self.lead_ground_count = len(mats)
            self.lead_remaining = remaining

        self.last_capture_ground_value = total_value
        self.last_capture_ground_count = len(mats)
        self.last_capture_seq = seq
        self.last_capture_bank = bank

    # ----- derived -----------------------------------------------------
    def spawned_value(self) -> float:
        return float(sum(self.ground_instances.values()))

    def spawned_count(self) -> int:
        return len(self.ground_instances)

    def naive_duration_sec(self) -> Optional[float]:
        if self.first_elapsed is None or self.last_elapsed is None:
            return None
        return self.last_elapsed - self.first_elapsed

    def to_dict(self) -> Dict[str, Any]:
        left = self.pre_zero_ground_value
        spawned = self.spawned_value()
        collected_bank_delta = None
        if self.bank_first is not None and self.bank_last is not None:
            collected_bank_delta = self.bank_last - self.bank_first
        return OrderedDict(
            wave=self.wave,
            captures=self.captures,
            post_timer_zero_captures=self.post_zero_captures,
            wave_duration_sec_field=self.duration_sec,
            elapsed_first=self.first_elapsed,
            elapsed_last=self.last_elapsed,
            duration_naive_last_minus_first=self.naive_duration_sec(),
            duration_robust_max_before_reset=self.max_elapsed_before_reset,
            elapsed_reset_detected=self.reset_detected,
            # economy
            materials_spawned_value=spawned,
            materials_spawned_distinct_entities=self.spawned_count(),
            ground_value_AUTHORITATIVE_last_remaining_gt0=left,
            ground_count_AUTHORITATIVE_last_remaining_gt0=self.pre_zero_ground_count,
            authoritative_instant_elapsed=self.pre_zero_elapsed,
            authoritative_instant_seq=self.pre_zero_seq,
            ground_value_at_lead_1s=self.lead_ground_value,
            ground_count_at_lead_1s=self.lead_ground_count,
            lead_instant_remaining_sec=self.lead_remaining,
            ground_value_NON_AUTHORITATIVE_last_capture=self.last_capture_ground_value,
            ground_count_NON_AUTHORITATIVE_last_capture=self.last_capture_ground_count,
            non_authoritative_instant_seq=self.last_capture_seq,
            ground_instant_difference=(
                None
                if left is None or self.last_capture_ground_value is None
                else left - self.last_capture_ground_value
            ),
            ground_count_max_in_wave=self.ground_max_count,
            ground_count_captures_at_or_above_MAX_GOLDS=self.ground_at_cap_captures,
            dropped_materials_max=self.dropped_materials_max,
            invalid_materials_max=self.invalid_materials_max,
            materials_collected_bank_delta_in_combat=collected_bank_delta,
            bank_first_capture=self.bank_first,
            bank_last_capture=self.bank_last,
            bank_at_authoritative_instant=self.pre_zero_bank,
            # shop that follows this wave
            shop_spend_buys=self.shop_buy_spend,
            shop_spend_rerolls=self.shop_reroll_spend,
            shop_spend_total_outflow=self.shop_buy_spend + self.shop_reroll_spend,
            shop_buys=self.shop_buys,
            shop_rerolls=self.shop_rerolls,
            shop_locks=self.shop_locks,
            shop_unlocks=self.shop_unlocks,
            shop_sells=self.shop_sells,
            shop_gold_before_first_decision=self.shop_gold_before_first,
            shop_gold_before_last_decision=self.shop_gold_before_last,
            # components (block D, no verdict)
            hp_first=self.hp_first,
            hp_last=self.hp_last,
            hp_increase_total_component=self.hp_increase_total,
            player_damage_events=self.player_damage_events,
            player_damage_amount_sum=self.player_damage_amount,
        )


def analyse_run(run_dir: str, run_id: str) -> Dict[str, Any]:
    summary_path = os.path.join(run_dir, "summary.json")
    events_path = os.path.join(run_dir, "events.jsonl")

    out: Dict[str, Any] = OrderedDict(run_id=run_id)
    if not os.path.isfile(summary_path):
        out["load_error"] = "summary.json missing"
        return out
    with open(summary_path, "r", encoding="utf-8") as handle:
        summary = json.load(handle)

    # ---- Block A raw identity / arming fields -------------------------
    # NOTE: every field below is arming or identity data recorded before or
    # independent of the gameplay outcome. None of them can select on outcome.
    out["mod_version"] = summary.get("mod_version")
    out["policy_version"] = summary.get("policy_version")
    out["game_version"] = summary.get("game_version")
    out["config_id"] = summary.get("config_id")
    out["character"] = summary.get("character")
    out["requested_danger"] = summary.get("requested_danger")
    out["danger_observed"] = summary.get("danger")
    out["danger_ok"] = summary.get("danger_ok")
    out["human_movement"] = summary.get("human_movement")
    out["endless"] = summary.get("endless")
    out["wave_retry"] = summary.get("wave_retry")

    # ---- outcome fields (read, never used to filter) -------------------
    out["result"] = summary.get("result")
    out["last_wave"] = summary.get("last_wave")
    out["waves_completed"] = summary.get("waves_completed")
    out["duration_ms"] = summary.get("duration_ms")
    out["telemetry_complete"] = summary.get("telemetry_complete")
    out["errors"] = summary.get("errors")
    out["hangs"] = summary.get("hangs")
    out["recoveries"] = summary.get("recoveries")
    out["illegal_actions"] = summary.get("illegal_actions")
    out["nonfinite_fixed"] = summary.get("nonfinite_fixed")
    out["nonfinite_total"] = summary.get("nonfinite_total")

    # ---- Block D summary components -----------------------------------
    out["summary_damage_taken_GROSS"] = summary.get("damage_taken")
    out["summary_materials_spent"] = summary.get("materials_spent")
    out["summary_rerolls"] = summary.get("rerolls")
    out["summary_locks"] = summary.get("locks")
    out["summary_purchases_n"] = len(summary.get("purchases") or [])
    out["summary_level_ups_n"] = len(summary.get("level_ups") or [])
    out["summary_crates_n"] = len(summary.get("crates") or [])

    if not os.path.isfile(events_path):
        out["capture_parses_to_eof"] = False
        out["capture_parse_error"] = "events.jsonl missing"
        return out
    out["events_bytes"] = os.path.getsize(events_path)

    waves: "OrderedDict[int, WaveAcc]" = OrderedDict()
    readback: Optional[Dict[str, Any]] = None
    event_counts: Counter = Counter()
    parse_ok = True
    parse_error = None
    lines = 0
    bad_lines = 0
    last_seq = None
    stale_seq = 0
    field_const: Dict[str, set] = {}
    pending_offer: Optional[Dict[str, Any]] = None
    current_wave: Optional[int] = None
    run_end_seen = False

    def track(name: str, value: Any) -> None:
        bucket = field_const.setdefault(name, set())
        if len(bucket) <= 6:
            try:
                bucket.add(value if isinstance(value, (str, int, float, bool, type(None))) else repr(value))
            except TypeError:
                bucket.add("<unhashable>")

    with open(events_path, "r", encoding="utf-8", errors="strict") as handle:
        try:
            for raw in handle:
                lines += 1
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError as exc:
                    bad_lines += 1
                    parse_ok = False
                    parse_error = "line %d: %s" % (lines, exc)
                    break
                name = ev.get("event")
                event_counts[name] += 1
                seq = ev.get("seq")
                if isinstance(seq, int):
                    if last_seq is not None and seq == last_seq:
                        stale_seq += 1
                    last_seq = seq
                payload = ev.get("payload") or {}

                if name == "difficulty_readback":
                    readback = payload
                elif name == "run_end":
                    run_end_seen = True
                elif name == "combat_capture":
                    wave = payload.get("wave")
                    if not isinstance(wave, int):
                        continue
                    current_wave = wave
                    acc = waves.get(wave)
                    if acc is None:
                        acc = waves[wave] = WaveAcc(wave)
                    acc.add_capture(seq if isinstance(seq, int) else -1, payload)
                    track("capture.valid", payload.get("valid"))
                    track("capture.wave_time.valid", (payload.get("wave_time") or {}).get("valid"))
                    track("capture.teacher.action_fresh", (payload.get("teacher") or {}).get("action_fresh"))
                    track("capture.player.bonus_materials", (payload.get("player") or {}).get("bonus_materials"))
                    track("capture.capture_schema_id", payload.get("capture_schema_id"))
                elif name == "player_damage":
                    wave = current_wave
                    if wave is not None:
                        acc = waves.get(wave)
                        if acc is not None:
                            acc.player_damage_events += 1
                            amt = payload.get("amount")
                            if isinstance(amt, (int, float)):
                                acc.player_damage_amount += amt
                elif name == "purchase_offer":
                    pending_offer = payload
                elif name == "purchase_decision":
                    wave = payload.get("wave")
                    if not isinstance(wave, int):
                        wave = current_wave
                    acc = waves.get(wave)
                    if acc is None and wave is not None:
                        acc = waves[wave] = WaveAcc(wave)
                    action = payload.get("action") or {}
                    atype = action.get("type") if isinstance(action, dict) else action
                    gold_before = payload.get("gold_before")
                    if acc is not None:
                        if isinstance(gold_before, int):
                            if acc.shop_gold_before_first is None:
                                acc.shop_gold_before_first = gold_before
                            acc.shop_gold_before_last = gold_before
                        if atype == "shop_buy":
                            acc.shop_buys += 1
                            price = None
                            slot = action.get("slot")
                            for item in ((pending_offer or {}).get("items") or []):
                                if item.get("slot") == slot:
                                    price = item.get("price")
                                    break
                            if isinstance(price, (int, float)):
                                acc.shop_buy_spend += price
                            else:
                                acc.shop_buy_spend += 0
                        elif atype == "shop_reroll":
                            acc.shop_rerolls += 1
                            rp = payload.get("reroll_price")
                            if isinstance(rp, (int, float)):
                                acc.shop_reroll_spend += rp
                        elif atype == "shop_lock":
                            acc.shop_locks += 1
                        elif atype == "shop_unlock":
                            acc.shop_unlocks += 1
                        elif atype == "shop_sell":
                            acc.shop_sells += 1
                    pending_offer = None
        except (UnicodeDecodeError, OSError) as exc:  # pragma: no cover
            parse_ok = False
            parse_error = "%s: %s" % (type(exc).__name__, exc)

    out["capture_parses_to_eof"] = bool(parse_ok)
    out["capture_parse_error"] = parse_error
    out["events_lines"] = lines
    out["events_bad_lines"] = bad_lines
    out["run_end_event_present"] = run_end_seen
    out["event_counts"] = dict(event_counts)
    out["repeated_seq_count"] = stale_seq
    out["difficulty_readback"] = readback
    out["readback_observed_danger"] = (readback or {}).get("observed_danger")
    out["readback_danger_ok"] = (readback or {}).get("danger_ok")
    out["readback_rundata_current_difficulty"] = (readback or {}).get("rundata_current_difficulty")
    out["field_constancy"] = {k: sorted(map(str, v)) for k, v in field_const.items()}

    wave_rows = [waves[w].to_dict() for w in sorted(waves)]
    # cumulative economy columns
    cum_spawn = 0.0
    cum_left = 0.0
    cum_spend = 0.0
    for row in wave_rows:
        cum_spawn += row["materials_spawned_value"] or 0.0
        left = row["ground_value_AUTHORITATIVE_last_remaining_gt0"]
        cum_left += left or 0.0
        cum_spend += row["shop_spend_total_outflow"] or 0.0
        row["cumulative_materials_spawned_value"] = cum_spawn
        row["cumulative_ground_left_authoritative"] = cum_left
        row["cumulative_shop_spend"] = cum_spend
    out["waves"] = wave_rows
    out["waves_captured_span"] = (
        [wave_rows[0]["wave"], wave_rows[-1]["wave"]] if wave_rows else None
    )

    terminal = wave_rows[-1] if wave_rows else None
    out["terminal_wave_from_summary"] = summary.get("last_wave")
    out["terminal_wave_from_captures"] = terminal["wave"] if terminal else None
    out["terminal_wave_duration_robust_sec"] = (
        terminal["duration_robust_max_before_reset"] if terminal else None
    )
    out["terminal_wave_duration_naive_sec"] = (
        terminal["duration_naive_last_minus_first"] if terminal else None
    )
    out["terminal_wave_duration_field_sec"] = (
        terminal["wave_duration_sec_field"] if terminal else None
    )
    out["terminal_wave_elapsed_reset_detected"] = (
        terminal["elapsed_reset_detected"] if terminal else None
    )

    # Slot reserved for the primary agent's failure-channel / causal attribution
    # work. Deliberately NOT filled in here: the causal lag has to be re-derived
    # per context and player_damage events lag the true tick.
    out["failure_attribution"] = {
        "status": "not attempted (out of scope for this script)",
        "hp_drop_diff": None,
        "causal_lag": None,
        "channels": None,
    }
    return out


# --------------------------------------------------------------------------
# grouping + aggregation
# --------------------------------------------------------------------------
def validity(run: Dict[str, Any], group_mod: str) -> Dict[str, Any]:
    reasons = []
    if run.get("mod_version") != group_mod:
        reasons.append("mod_version != group (%r)" % run.get("mod_version"))
    if run.get("requested_danger") != 5:
        reasons.append("requested_danger != 5 (%r)" % run.get("requested_danger"))
    obs = run.get("danger_observed")
    if obs == -1:
        reasons.append("observed danger == -1 => NEVER READ (technical failure, NOT Danger 0)")
    elif obs != 5:
        reasons.append("observed danger != 5 (%r)" % obs)
    if run.get("danger_ok") is not True:
        reasons.append("danger_ok is not True (%r)" % run.get("danger_ok"))
    if not run.get("capture_parses_to_eof"):
        reasons.append("events.jsonl did not parse to EOF")
    technical = []
    if obs == -1:
        technical.append("danger never read")
    if not run.get("capture_parses_to_eof"):
        technical.append("capture parse failure")
    if not run.get("run_end_event_present"):
        technical.append("no run_end event (run may be incomplete/in-flight)")
    if run.get("errors"):
        technical.append("summary.errors=%s" % run.get("errors"))
    if run.get("hangs"):
        technical.append("summary.hangs=%s" % run.get("hangs"))
    return {
        "valid_gameplay_attempt": not reasons,
        "invalidity_reasons": reasons,
        "technical_failure_flags": technical,
        "selection_note": (
            "All fields used here are arming/identity or capture-integrity data. "
            "None of them is a function of the gameplay outcome, so this filter "
            "cannot select on outcome."
        ),
    }


def aggregate(runs: List[Dict[str, Any]], group_mod: str) -> Dict[str, Any]:
    for run in runs:
        run["validity"] = validity(run, group_mod)
    valid = [r for r in runs if r["validity"]["valid_gameplay_attempt"]]
    invalid = [r for r in runs if not r["validity"]["valid_gameplay_attempt"]]

    block_a = {
        "runs_considered": len(runs),
        "valid_gameplay_attempts": len(valid),
        "invalid_runs": len(invalid),
        "invalid_detail": [
            {"run_id": r["run_id"], "reasons": r["validity"]["invalidity_reasons"]}
            for r in invalid
        ],
        "technical_failures": [
            {"run_id": r["run_id"], "flags": r["validity"]["technical_failure_flags"]}
            for r in runs
            if r["validity"]["technical_failure_flags"]
        ],
        "note_minus_one": "danger == -1 means NEVER READ: a technical failure, not Danger 0.",
        "note_outcome": (
            "Technical failures are reported separately and no run is ever "
            "excluded because of its gameplay outcome."
        ),
    }

    results = Counter(r.get("result") for r in valid)
    victories = sum(1 for r in valid if r.get("result") == "victory")
    terminal_waves = [
        r.get("terminal_wave_from_summary")
        for r in valid
        if isinstance(r.get("terminal_wave_from_summary"), int)
    ]
    block_b = {
        "denominator_valid_attempts": len(valid),
        "victories": victories,
        "victory_rate": (victories / len(valid)) if valid else None,
        "victory_rate_denominator": len(valid),
        "result_counts": dict(results),
        "terminal_wave_values": terminal_waves,
        "terminal_wave_counts": dict(sorted(Counter(terminal_waves).items())),
        "terminal_wave_stats": desc([float(w) for w in terminal_waves]),
        "terminal_wave_range": (
            [min(terminal_waves), max(terminal_waves)] if terminal_waves else None
        ),
        "time_within_terminal_wave_robust_sec": desc(
            [
                r.get("terminal_wave_duration_robust_sec")
                for r in valid
                if isinstance(r.get("terminal_wave_duration_robust_sec"), (int, float))
            ]
        ),
        "time_within_terminal_wave_naive_sec": desc(
            [
                r.get("terminal_wave_duration_naive_sec")
                for r in valid
                if isinstance(r.get("terminal_wave_duration_naive_sec"), (int, float))
            ]
        ),
        "duration_method": (
            "wave_time.elapsed_sec RESETS on the final captures of a WON wave, so "
            "last-minus-first mixes two different quantities across outcomes. The "
            "robust figure is the MAXIMUM elapsed_sec observed before the first "
            "drop of more than %.1f s within the wave; the naive last-minus-first "
            "figure is printed alongside it for comparison." % RESET_DROP_SEC
        ),
    }

    # per-wave economy pooled within the group
    per_wave: Dict[int, Dict[str, List[float]]] = {}
    for run in valid:
        for row in run.get("waves") or []:
            slot = per_wave.setdefault(row["wave"], {})
            for key in (
                "materials_spawned_value",
                "ground_value_AUTHORITATIVE_last_remaining_gt0",
                "ground_value_at_lead_1s",
                "ground_value_NON_AUTHORITATIVE_last_capture",
                "materials_collected_bank_delta_in_combat",
                "shop_spend_total_outflow",
                "bank_last_capture",
                "ground_count_max_in_wave",
                "post_timer_zero_captures",
            ):
                val = row.get(key)
                if isinstance(val, (int, float)):
                    slot.setdefault(key, []).append(float(val))
    block_c = {
        "note_instant": (
            "combat_capture events continue for tens of ticks after "
            "wave_time.remaining_sec hits 0, and the game's end-of-wave sweep "
            "happens inside that window. The AUTHORITATIVE instant for "
            "'materials left on the ground at wave end' is the LAST CAPTURE WITH "
            "remaining_sec > 0. The last-capture figure is printed beside it and "
            "is NOT authoritative."
        ),
        "note_max_golds": (
            "MAX_GOLDS = %d is the GAME's cap on simultaneous ground currency "
            "entities, not truncation by this instrument: a ground pile sitting "
            "at exactly %d is the game's own limit."
            % (MAX_GOLDS, MAX_GOLDS)
        ),
        "note_spawned": (
            "materials_spawned_value is the sum of value over DISTINCT "
            "instance_ids observed on the ground during the wave. Captures are "
            "sampled, so a pickup between two captures is not counted: this is a "
            "LOWER BOUND on spawn, not a spawn ledger."
        ),
        "note_materials_spent": (
            "summary.materials_spent was fixed in 0.2.60 and means materials "
            "OUTFLOW (includes rerolls, excludes sells, resets per wave). It is "
            "reported as-is and not reinterpreted. shop_spend_total_outflow here "
            "is an independent reconstruction from purchase_offer prices plus "
            "reroll_price."
        ),
        "per_wave": {
            str(w): {k: desc(v) for k, v in sorted(cols.items())}
            for w, cols in sorted(per_wave.items())
        },
    }

    block_d = {
        "label": "COMPONENTS ONLY - none of these is an endpoint and none carries a verdict.",
        "damage_taken_note": (
            "summary.damage_taken is a GROSS counter that never subtracts "
            "healing; observed healing varied 15-171 across six earlier runs, so "
            "it is not a net damage figure."
        ),
        "healing_note": (
            "No dedicated healing field exists in this telemetry. "
            "hp_increase_total_component (sum of positive hp deltas between "
            "consecutive captures) is a crude proxy that also absorbs max_hp "
            "growth; treat it as a component, not a healing measurement."
        ),
        "damage_taken_GROSS": desc(
            [r.get("summary_damage_taken_GROSS") for r in valid
             if isinstance(r.get("summary_damage_taken_GROSS"), (int, float))]
        ),
        "materials_spent": desc(
            [r.get("summary_materials_spent") for r in valid
             if isinstance(r.get("summary_materials_spent"), (int, float))]
        ),
        "rerolls": desc(
            [r.get("summary_rerolls") for r in valid
             if isinstance(r.get("summary_rerolls"), (int, float))]
        ),
        "locks": desc(
            [r.get("summary_locks") for r in valid
             if isinstance(r.get("summary_locks"), (int, float))]
        ),
        "hp_increase_total_component": desc(
            [
                sum(
                    row.get("hp_increase_total_component") or 0.0
                    for row in (r.get("waves") or [])
                )
                for r in valid
            ]
        ),
    }

    # Block E: field-variation audit
    audit_fields = [
        "mod_version", "policy_version", "game_version", "config_id", "character",
        "requested_danger", "danger_observed", "danger_ok", "human_movement",
        "endless", "wave_retry", "telemetry_complete", "nonfinite_fixed",
        "nonfinite_total", "summary_rerolls", "summary_locks",
        "summary_materials_spent", "summary_damage_taken_GROSS",
        "readback_observed_danger", "readback_danger_ok",
        "readback_rundata_current_difficulty",
    ]
    audit: Dict[str, Any] = {}
    for field in audit_fields:
        vals = [r.get(field) for r in runs]
        uniq = sorted({str(v) for v in vals})
        audit[field] = {
            "distinct_values": uniq[:10],
            "n_distinct": len(uniq),
            "constant": len(uniq) <= 1,
        }
    capture_audit: Dict[str, Any] = {}
    for run in runs:
        for key, vals in (run.get("field_constancy") or {}).items():
            capture_audit.setdefault(key, set()).update(vals)
    block_e = {
        "summary_level_fields": audit,
        "capture_level_fields": {
            k: {"distinct_values": sorted(v)[:10], "n_distinct": len(v), "constant": len(v) <= 1}
            for k, v in sorted(capture_audit.items())
        },
        "note": (
            "New instruments default to -1; -1 is never read as a real zero. "
            "Fields flagged constant carry no information in this dataset."
        ),
    }

    return {
        "group_mod_version": group_mod,
        "block_a_validity": block_a,
        "block_b_primary": block_b,
        "block_c_economy": block_c,
        "block_d_components": block_d,
        "block_e_field_audit": block_e,
        "runs": runs,
    }


# --------------------------------------------------------------------------
# printing
# --------------------------------------------------------------------------
def fmt(val: Any, width: int = 0) -> str:
    if val is None:
        text = "-"
    elif isinstance(val, bool):
        text = "T" if val else "F"
    elif isinstance(val, float):
        text = "%.3f" % val
    else:
        text = str(val)
    return text.rjust(width) if width else text


def print_report(result: Dict[str, Any], label: str) -> None:
    print("=" * 100)
    print("DANGER 5 BASELINE ANALYSIS  label=%s" % label)
    print("NO VERDICT IS PRODUCED BY THIS SCRIPT. Numbers only.")
    print("=" * 100)
    for group in result["groups"]:
        mod = group["group_mod_version"]
        a = group["block_a_validity"]
        print()
        print("#" * 100)
        print("GROUP mod_version = %s   (groups are NEVER pooled)" % mod)
        print("#" * 100)

        print("\n--- BLOCK A: validity (arming/identity only; cannot select on outcome) ---")
        print("runs considered=%d  valid gameplay attempts=%d  invalid=%d"
              % (a["runs_considered"], a["valid_gameplay_attempts"], a["invalid_runs"]))
        print(a["note_minus_one"])
        print(a["note_outcome"])
        hdr = ("run_id", "req_d", "obs_d", "d_ok", "rb_obs", "rb_ok", "mod", "policy", "parse_eof", "valid")
        print("%-26s %5s %5s %4s %6s %5s %-20s %-32s %9s %5s" % hdr)
        for run in group["runs"]:
            print("%-26s %5s %5s %4s %6s %5s %-20s %-32s %9s %5s" % (
                run["run_id"], fmt(run.get("requested_danger")), fmt(run.get("danger_observed")),
                fmt(run.get("danger_ok")), fmt(run.get("readback_observed_danger")),
                fmt(run.get("readback_danger_ok")), str(run.get("mod_version")),
                str(run.get("policy_version")), fmt(run.get("capture_parses_to_eof")),
                fmt(run["validity"]["valid_gameplay_attempt"]),
            ))
        if a["invalid_detail"]:
            print("INVALID DETAIL:")
            for row in a["invalid_detail"]:
                print("  %s: %s" % (row["run_id"], "; ".join(row["reasons"])))
        if a["technical_failures"]:
            print("TECHNICAL FAILURES (reported separately, never outcome-excluded):")
            for row in a["technical_failures"]:
                print("  %s: %s" % (row["run_id"], "; ".join(row["flags"])))
        else:
            print("TECHNICAL FAILURES: none flagged (denominator %d runs)" % a["runs_considered"])

        b = group["block_b_primary"]
        print("\n--- BLOCK B: primary ---")
        print("victories = %s / %s valid attempts   rate = %s"
              % (b["victories"], b["denominator_valid_attempts"], fmt(b["victory_rate"])))
        print("result counts (denominator %d): %s" % (b["denominator_valid_attempts"], b["result_counts"]))
        print("terminal wave counts: %s" % b["terminal_wave_counts"])
        ts = b["terminal_wave_stats"]
        print("terminal wave  n=%s median=%s mean=%s sd=%s range=%s"
              % (ts["n"], fmt(ts["median"]), fmt(ts["mean"]), fmt(ts["sd"]), b["terminal_wave_range"]))
        print("\nRAW PER-RUN TABLE (block B):")
        print("%-26s %-9s %5s %5s %10s %10s %9s %6s" % (
            "run_id", "result", "lastW", "capW", "termDurRob", "termDurNaive",
            "waveDurFld", "reset"))
        for run in group["runs"]:
            print("%-26s %-9s %5s %5s %10s %10s %9s %6s" % (
                run["run_id"], str(run.get("result")), fmt(run.get("last_wave")),
                fmt(run.get("terminal_wave_from_captures")),
                fmt(run.get("terminal_wave_duration_robust_sec")),
                fmt(run.get("terminal_wave_duration_naive_sec")),
                fmt(run.get("terminal_wave_duration_field_sec")),
                fmt(run.get("terminal_wave_elapsed_reset_detected")),
            ))
        print("duration method: %s" % b["duration_method"])
        rob = b["time_within_terminal_wave_robust_sec"]
        nai = b["time_within_terminal_wave_naive_sec"]
        print("time-in-terminal-wave ROBUST  n=%s median=%s mean=%s sd=%s range=[%s, %s]"
              % (rob["n"], fmt(rob["median"]), fmt(rob["mean"]), fmt(rob["sd"]),
                 fmt(rob["min"]), fmt(rob["max"])))
        print("time-in-terminal-wave NAIVE   n=%s median=%s mean=%s sd=%s range=[%s, %s]"
              % (nai["n"], fmt(nai["median"]), fmt(nai["mean"]), fmt(nai["sd"]),
                 fmt(nai["min"]), fmt(nai["max"])))

        c = group["block_c_economy"]
        print("\n--- BLOCK C: economy, per wave (operator hypothesis; numbers only) ---")
        for key in ("note_instant", "note_max_golds", "note_spawned", "note_materials_spent"):
            print("NOTE: %s" % c[key])
        print("\nRAW PER-RUN PER-WAVE TABLE. 'leftAUTH' = last capture with remaining_sec>0 "
              "(AUTHORITATIVE). 'left@1s' = last capture with remaining_sec >= 1.0 s, an "
              "instant-sensitivity control. 'leftLAST' = final capture of the wave "
              "(AFTER the sweep; NOT authoritative).")
        print("%-26s %4s %8s %9s %8s %9s %6s %8s %8s %8s %9s %7s %7s %6s" % (
            "run_id", "wave", "spawnVal", "leftAUTH", "left@1s", "leftLAST", "diff",
            "collBank", "bankEnd", "shopOut", "cumSpawn", "gndMax", "capHits", "postT0"))
        for run in group["runs"]:
            for row in run.get("waves") or []:
                print("%-26s %4s %8s %9s %8s %9s %6s %8s %8s %8s %9s %7s %7s %6s" % (
                    run["run_id"], row["wave"],
                    fmt(row["materials_spawned_value"]),
                    fmt(row["ground_value_AUTHORITATIVE_last_remaining_gt0"]),
                    fmt(row["ground_value_at_lead_1s"]),
                    fmt(row["ground_value_NON_AUTHORITATIVE_last_capture"]),
                    fmt(row["ground_instant_difference"]),
                    fmt(row["materials_collected_bank_delta_in_combat"]),
                    fmt(row["bank_last_capture"]),
                    fmt(row["shop_spend_total_outflow"]),
                    fmt(row["cumulative_materials_spawned_value"]),
                    fmt(row["ground_count_max_in_wave"]),
                    fmt(row["ground_count_captures_at_or_above_MAX_GOLDS"]),
                    fmt(row["post_timer_zero_captures"]),
                ))
        print("\nPOOLED-WITHIN-GROUP per-wave medians (denominator = n per cell):")
        print("%5s %26s %6s %10s %10s" % ("wave", "field", "n", "median", "mean"))
        for wave, cols in sorted(c["per_wave"].items(), key=lambda kv: int(kv[0])):
            for field, stats in cols.items():
                print("%5s %26s %6s %10s %10s" % (
                    wave, field[:26], stats["n"], fmt(stats["median"]), fmt(stats["mean"])))

        d = group["block_d_components"]
        print("\n--- BLOCK D: components, NO verdict ---")
        print(d["label"])
        print("NOTE: %s" % d["damage_taken_note"])
        print("NOTE: %s" % d["healing_note"])
        print("%-26s %12s %14s %8s %6s %12s" % (
            "run_id", "dmgGROSS", "materials_spent", "rerolls", "locks", "hpIncrProxy"))
        for run in group["runs"]:
            hp_incr = sum(row.get("hp_increase_total_component") or 0.0
                          for row in (run.get("waves") or []))
            print("%-26s %12s %14s %8s %6s %12s" % (
                run["run_id"], fmt(run.get("summary_damage_taken_GROSS")),
                fmt(run.get("summary_materials_spent")), fmt(run.get("summary_rerolls")),
                fmt(run.get("summary_locks")), fmt(hp_incr)))
        for key in ("damage_taken_GROSS", "materials_spent", "rerolls", "locks",
                    "hp_increase_total_component"):
            stats = d[key]
            print("%-30s n=%s median=%s mean=%s sd=%s range=[%s, %s]" % (
                key, stats["n"], fmt(stats["median"]), fmt(stats["mean"]),
                fmt(stats["sd"]), fmt(stats["min"]), fmt(stats["max"])))

        e = group["block_e_field_audit"]
        print("\n--- BLOCK E: field-variation audit ---")
        print(e["note"])
        print("%-38s %4s %6s  %s" % ("field", "nDis", "const", "values(<=10)"))
        for field, info in e["summary_level_fields"].items():
            print("%-38s %4s %6s  %s" % (
                field, info["n_distinct"], "CONST" if info["constant"] else "varies",
                info["distinct_values"]))
        for field, info in e["capture_level_fields"].items():
            print("%-38s %4s %6s  %s" % (
                field, info["n_distinct"], "CONST" if info["constant"] else "varies",
                info["distinct_values"]))

        print("\nfailure-channel / causal attribution: NOT ATTEMPTED here "
              "(structure reserved at runs[].failure_attribution).")


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def build(run_ids: List[str], root: str) -> Dict[str, Any]:
    seen = []
    skipped = []
    for rid in run_ids:
        if rid in HARD_EXCLUDED_RUN_IDS:
            skipped.append({"run_id": rid, "reason": "hard-excluded by identity (pre-latch build)"})
            continue
        if rid in seen:
            continue
        seen.append(rid)

    analysed = []
    for rid in seen:
        run_dir = os.path.join(root, rid)
        if not os.path.isdir(run_dir):
            skipped.append({"run_id": rid, "reason": "run directory not found"})
            continue
        sys.stderr.write("reading %s\n" % rid)
        sys.stderr.flush()
        analysed.append(analyse_run(run_dir, rid))

    by_mod: "OrderedDict[str, List[Dict[str, Any]]]" = OrderedDict()
    for run in analysed:
        by_mod.setdefault(str(run.get("mod_version")), []).append(run)

    return {
        "schema": "wp2_d5_baseline_analysis/1",
        "runs_root": root,
        "run_ids_requested": list(run_ids),
        "skipped": skipped,
        "n_groups": len(by_mod),
        "groups": [aggregate(runs, mod) for mod, runs in by_mod.items()],
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline Danger 5 baseline analysis (numbers only, no verdict)."
    )
    parser.add_argument(
        "--run-ids-file", action="append", required=True,
        help="JSON state file with collected_run_ids, a JSON list, or a text file "
             "of run ids. Repeatable; runs are still grouped by their own mod_version.",
    )
    parser.add_argument("--out", required=True, help="Path to write the JSON result.")
    parser.add_argument("--label", default="d5_baseline", help="Label for the report header.")
    parser.add_argument("--runs-dir", default=None, help="Override the run archive root.")
    args = parser.parse_args(argv)

    root = args.runs_dir or runs_root()
    run_ids: List[str] = []
    for path in args.run_ids_file:
        run_ids.extend(read_ids(path))

    result = build(run_ids, root)
    result["label"] = args.label
    result["run_ids_files"] = list(args.run_ids_file)

    out_dir = os.path.dirname(os.path.abspath(args.out))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=1)

    print_report(result, args.label)
    print("\nJSON written to %s" % os.path.abspath(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
