"""Dose readback (manipulation check) for the section 28 D5 scaling campaign.

Prereg: reports/wp2/d5_scaling_intervention_prereg.md, section 28f block
"Dose readback -- the manipulation check, and it differs per dial". That block is
binding and the asymmetry it declares is the whole point of this module:

  HEALTH arms (H75, H50)
      Per-trial, deterministic. Per-entity `max_hp` in the CAPTURE STREAM against
      the arm's expected ratio (H75 -> 1/0.75 = 1.3333x, H50 -> 1/0.50 = 2.0000x
      relative to control at the SAME (wave, enemy type)). Read the LARGE-HP types
      only; small-HP types deviate by integer rounding alone and would manufacture
      false mismatches. A trial that does not match is EXCLUDED and REPORTED.

  DAMAGE arms (D75, D50)
      `max_hp` IS VACUOUS FOR THEM. Damage scaling does not change `max_hp` and the
      capture carries no enemy damage field (enemy keys measured here: armor,
      attack_path, category, health_ratio, hp, instance_id, is_boosted, max_hp,
      name, nx, ny, radius, script_path, speed, type_id, vx, vy, x, y). Applying the
      health readback to a D arm would be a check that CANNOT RETURN THE POSITIVE.
      Replacement: median player HP-DROP SIZE at MATCHED WAVES, aggregated PER ARM.
      Per-trial is impossible (a control run yields ~10 drop events in ~10,000
      captures). Gross `damage_taken` and drop COUNT are both invalid here -- the
      dial changes behaviour, and in the pilot the softer-hit arm took MORE gross
      damage per wave by accepting more, smaller hits. Drop SIZE is what resists
      that confound.

      TWO CHANNELS, because the prescribed one is lossy. Channel 1 differences
      player `hp` between consecutive captures WITHIN a wave. Measured defect: on
      run_1785675850_78197 it finds 4 drops where the game emitted 8
      `player_damage` events, and the 4 it misses are exactly the hits landing
      across a wave boundary (verified by seq-adjacent captures: 15->16, 17->18,
      18->19, 19->20). Cross-wave differencing cannot fix this -- HP and max_hp
      both change at the shop. Channel 2 therefore reads the game's own
      `player_damage.amount` and attributes the wave from the nearest PRECEDING
      capture; it is the PRIMARY, and channel 1 is corroboration. The two agree
      exactly on runs with no boundary hits (10 vs 10, 28 vs 28 measured). This
      matters: the loss is not random, it drops end-of-wave hits, and on that run
      3 of the 4 missed were SMALL (3, 5, 6) -- a bias in drop SIZE, in the
      direction of the hypothesis, from the channel the task prescribed.

      "MATCHED WAVES" is load-bearing: arms that survive longer reach
      harder waves where hits are bigger, so the comparison is restricted to waves
      reached by every arm being compared and the matched set is printed.

Arm certification (section 28f) is read from the CAPTURE STREAM / event log, never
from summary.json -- the feasibility gate caught `summary.observed_danger` reading
None while `danger_ok` read True, and they cannot both be right.

DISCIPLINE. Every check prints the SIZE OF THE CANDIDATE SET it searched before it
reports a zero or a "no mismatches". A zero out of a vacuous filter is not a zero.

The per-arm damage aggregate is a COMPLETION-TIME artifact. Section 28g forbids
interim interpretation, so it is OFF by default and requires --damage-aggregate.

Usage
    python scripts/wp2_d5_scaling_manipcheck.py --probe-run <run_id>
    python scripts/wp2_d5_scaling_manipcheck.py --health
    python scripts/wp2_d5_scaling_manipcheck.py --damage-aggregate   # completion only
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
from collections import Counter, defaultdict

# ---------------------------------------------------------------------------
# Constants fixed by the prereg
# ---------------------------------------------------------------------------

# arm -> enemy_scaling dial the driver wrote into the save
ARM_DIAL = {
    "control": {"health": 1.0, "damage": 1.0},
    "H75": {"health": 0.75, "damage": 1.0},
    "H50": {"health": 0.50, "damage": 1.0},
    "D75": {"health": 1.0, "damage": 0.75},
    "D50": {"health": 1.0, "damage": 0.50},
}
HEALTH_ARMS = ("H75", "H50")
DAMAGE_ARMS = ("D75", "D50")

# LARGE-HP types only. Small-HP types deviate by integer rounding alone.
LARGE_HP_TYPES = ("bruiser", "horned_bruiser", "healer")

# A cell is only read when the control baseline is large enough that integer
# rounding cannot move the ratio past the tolerance. At baseline 50 the worst
# rounding error is 0.5/25 = 2.0% for the H50 arm; the tolerance is 5%, and the
# arms are 33% apart, so this discriminates H75 from H50 with wide margin.
MIN_BASELINE_MAX_HP = 50
RATIO_TOL = 0.05

REQUIRED_OPENER = "weapon_smg_1"
REQUIRED_CHARACTER = "character_mutant"
REQUIRED_DANGER = 5

DEFAULT_LADDER = os.path.join(".tmp", "d5_scaling", "ladder.jsonl")


def default_runs_dir() -> str:
    appdata = os.environ.get("APPDATA", "")
    return os.path.join(appdata, "Brotato", "brotato_agent", "runs")


# ---------------------------------------------------------------------------
# Ladder / arm identification
# ---------------------------------------------------------------------------


def arm_of(fixture_file: str) -> str:
    """Arm is read from the trial row's fixture_file, e.g. f03_H50.json -> H50."""
    base = os.path.basename(str(fixture_file or ""))
    stem = base[:-5] if base.endswith(".json") else base
    if "_" not in stem:
        return ""
    fixture, _, arm = stem.partition("_")
    return arm if arm in ARM_DIAL else ""


def fixture_of(fixture_file: str) -> str:
    base = os.path.basename(str(fixture_file or ""))
    stem = base[:-5] if base.endswith(".json") else base
    return stem.partition("_")[0]


def load_ladder(path: str) -> list:
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            row["_lineno"] = lineno
            row["_arm"] = arm_of(row.get("fixture_file", ""))
            row["_fixture"] = fixture_of(row.get("fixture_file", ""))
            rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Capture-stream extraction
# ---------------------------------------------------------------------------


def enemy_type(type_id: str) -> str:
    """res://entities/units/enemies/bruiser/bruiser_stats.tres -> bruiser"""
    parts = str(type_id or "").rstrip("/").split("/")
    return parts[-2] if len(parts) >= 2 else str(type_id or "")


def iter_events(events_path: str):
    with open(events_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except ValueError:
                continue


def extract_run(events_path: str) -> dict:
    """One pass over events.jsonl. Returns the raw material for both checks plus
    the candidate-set sizes that make a zero interpretable."""
    out = {
        "events": 0,
        "captures": 0,
        "captures_invalid": 0,
        "enemy_rows": 0,
        "enemy_rows_boosted": 0,
        "enemy_rows_large": 0,
        "waves": set(),
        # (wave, type) -> Counter of max_hp, non-boosted large-HP types only.
        # is_boosted entities are EXCLUDED: an elite carries its own hp multiplier
        # and would contaminate the ratio.
        "maxhp": defaultdict(Counter),
        "maxhp_cells": 0,
        # wave -> list of player HP-drop SIZES, capture-differenced (channel 1)
        "drops": defaultdict(list),
        "drop_events": 0,
        # wave -> list of player HP-drop SIZES from the game's own player_damage
        # event (channel 2), wave attributed from the nearest PRECEDING capture
        "drops_pd": defaultdict(list),
        "player_damage_events": 0,
        "player_damage_amounts": [],
        "player_damage_no_wave": 0,
        # certification, all read from the stream
        "run_start": None,
        "difficulty_readbacks": [],
        "run_end_result": None,
    }
    prev_hp = None
    prev_wave = None
    for e in iter_events(events_path):
        out["events"] += 1
        ev = e.get("event")
        payload = e.get("payload") or {}
        if ev == "run_start":
            out["run_start"] = payload
        elif ev == "difficulty_readback":
            out["difficulty_readbacks"].append(payload)
        elif ev == "player_damage":
            out["player_damage_events"] += 1
            amount = payload.get("amount")
            out["player_damage_amounts"].append(amount)
            if prev_wave is None:
                out["player_damage_no_wave"] += 1
            elif amount is not None and amount > 0:
                out["drops_pd"][prev_wave].append(amount)
        elif ev == "run_end":
            out["run_end_result"] = payload.get("result")
        elif ev == "combat_capture":
            out["captures"] += 1
            if payload.get("valid") is False:
                out["captures_invalid"] += 1
            wave = payload.get("wave")
            out["waves"].add(wave)
            for en in (payload.get("entities") or {}).get("enemies") or []:
                out["enemy_rows"] += 1
                if en.get("is_boosted"):
                    out["enemy_rows_boosted"] += 1
                    continue
                ty = enemy_type(en.get("type_id"))
                if ty in LARGE_HP_TYPES:
                    out["enemy_rows_large"] += 1
                    out["maxhp"][(wave, ty)][en.get("max_hp")] += 1
            # player HP-drop SIZE, within-wave consecutive captures only.
            # Crossing a wave boundary is excluded: HP changes at the shop and a
            # cross-boundary difference is not a hit.
            hp = (payload.get("player") or {}).get("hp")
            if hp is not None and prev_hp is not None and prev_wave == wave and hp < prev_hp:
                out["drops"][wave].append(prev_hp - hp)
                out["drop_events"] += 1
            prev_hp = hp
            prev_wave = wave
    out["maxhp_cells"] = len(out["maxhp"])
    out["waves"].discard(None)
    return out


def modal_maxhp(extract: dict) -> dict:
    """(wave, type) -> (modal max_hp, n observations, n distinct values)."""
    table = {}
    for key, counter in extract["maxhp"].items():
        if not counter:
            continue
        value, n = counter.most_common(1)[0]
        table[key] = (value, n, len(counter))
    return table


# ---------------------------------------------------------------------------
# Arm certification (section 28f) -- from the capture stream, not the summary
# ---------------------------------------------------------------------------


def certify(extract: dict) -> dict:
    rs = extract["run_start"] or {}
    observed_char = rs.get("character")
    requested_char = rs.get("requested_character")
    # Mirrors the mod's own rule: an empty requested value is a MISMATCH, never a pass.
    character_ok = bool(requested_char) and observed_char == requested_char
    dr = extract["difficulty_readbacks"]
    observed_danger = dr[0].get("observed_danger") if dr else None
    danger_ok = observed_danger == REQUIRED_DANGER
    dials = [d.get("rundata_current_run_accessibility_settings") for d in dr]
    return {
        "character_observed": observed_char,
        "character_requested": requested_char,
        "character_ok": character_ok,
        "character_is_expected": observed_char == REQUIRED_CHARACTER,
        "observed_danger": observed_danger,
        "danger_ok": danger_ok,
        "n_difficulty_readbacks": len(dr),
        "opener": rs.get("weapon"),
        "opener_ok": rs.get("weapon") == REQUIRED_OPENER,
        "dial_readback": dials[0] if dials else None,
        "mod_version": rs.get("mod_version"),
        "unlock_pool": rs.get("unlock_pool"),
    }


def dial_matches_arm(dial, arm: str):
    """Confirms the SET value of the save dial, which is delivery, not effect.
    Returns None when the readback is absent -- absent is never a pass."""
    if not isinstance(dial, dict):
        return None
    want = ARM_DIAL.get(arm)
    if want is None:
        return None
    for key, value in want.items():
        got = dial.get(key)
        if got is None or abs(float(got) - value) > 1e-9:
            return False
    return True


# ---------------------------------------------------------------------------
# CHECK A -- health arms, per trial, deterministic
# ---------------------------------------------------------------------------


def build_control_reference(control_extracts: dict) -> dict:
    """(wave, type) -> {value, n_trials, values_seen}. Pooled over control trials.

    The reference is pooled rather than taken from the same fixture's control
    because a rescued arm reaches waves its paired control never saw. Cross-trial
    disagreement inside the reference is REPORTED, not averaged away."""
    agg = defaultdict(Counter)
    for run_id, ex in control_extracts.items():
        for key, (value, _n, _d) in modal_maxhp(ex).items():
            agg[key][value] += 1
    ref = {}
    for key, counter in agg.items():
        value, n_trials = counter.most_common(1)[0]
        ref[key] = {"value": value, "n_trials": n_trials, "values_seen": dict(counter)}
    return ref


def health_readback(extract: dict, arm: str, reference: dict) -> dict:
    """Expected ratio control_max_hp / arm_max_hp == 1 / health_dial."""
    expected = 1.0 / ARM_DIAL[arm]["health"]
    cells = []
    trial_table = modal_maxhp(extract)
    n_candidate_cells = len(trial_table)
    n_after_type = 0
    n_after_baseline = 0
    for (wave, ty), (value, n_obs, n_distinct) in sorted(trial_table.items()):
        if ty not in LARGE_HP_TYPES:
            continue
        n_after_type += 1
        ref = reference.get((wave, ty))
        if ref is None:
            continue
        if ref["value"] < MIN_BASELINE_MAX_HP:
            continue
        n_after_baseline += 1
        ratio = ref["value"] / float(value) if value else float("nan")
        cells.append(
            {
                "wave": wave,
                "type": ty,
                "control_max_hp": ref["value"],
                "trial_max_hp": value,
                "ratio": ratio,
                "expected": expected,
                "ok": abs(ratio - expected) <= RATIO_TOL * expected,
                "n_obs": n_obs,
                "n_distinct_values_in_cell": n_distinct,
                "ref_n_control_trials": ref["n_trials"],
                "ref_values_seen": ref["values_seen"],
            }
        )
    n_ok = sum(1 for c in cells if c["ok"])
    return {
        "arm": arm,
        "expected_ratio": expected,
        "n_candidate_cells": n_candidate_cells,
        "n_cells_large_hp_types": n_after_type,
        "n_cells_matched_to_reference": len(cells),
        "n_cells_after_baseline_floor": n_after_baseline,
        "n_cells_ok": n_ok,
        "n_cells_mismatch": len(cells) - n_ok,
        # VACUOUS is not PASS. Zero comparable cells is its own verdict.
        "verdict": "VACUOUS-NO-CELLS" if not cells else ("PASS" if n_ok == len(cells) else "MISMATCH"),
        "cells": cells,
    }


# ---------------------------------------------------------------------------
# CHECK B -- damage arms, per ARM, matched waves. Completion-time artifact.
# ---------------------------------------------------------------------------


def damage_aggregate(arm_to_extracts: dict, arms: list, channel: str = "drops_pd") -> dict:
    """Median player HP-drop SIZE at MATCHED WAVES, aggregated per arm.

    Matched waves = waves REACHED (present in the capture stream) by every arm in
    `arms`. Reached, not merely "has a drop": conditioning the wave set on whether
    a drop occurred would let the dial select its own comparison waves."""
    reached = {}
    for arm in arms:
        waves = set()
        for ex in arm_to_extracts.get(arm, {}).values():
            waves |= set(ex["waves"])
        reached[arm] = waves
    matched = set.intersection(*[reached[a] for a in arms]) if arms else set()

    per_arm = {}
    for arm in arms:
        sizes = []
        per_wave = defaultdict(list)
        n_drops_all_waves = 0
        for ex in arm_to_extracts.get(arm, {}).values():
            for wave, values in ex[channel].items():
                n_drops_all_waves += len(values)
                if wave in matched:
                    sizes.extend(values)
                    per_wave[wave].extend(values)
        per_arm[arm] = {
            "n_trials": len(arm_to_extracts.get(arm, {})),
            "waves_reached": sorted(reached[arm]),
            "n_drops_all_waves": n_drops_all_waves,
            "n_drops_matched": len(sizes),
            "median_drop_size": statistics.median(sizes) if sizes else None,
            "mean_drop_size": (sum(sizes) / len(sizes)) if sizes else None,
            "min_drop": min(sizes) if sizes else None,
            "max_drop": max(sizes) if sizes else None,
            "per_wave_median": {
                w: statistics.median(v) for w, v in sorted(per_wave.items())
            },
            "per_wave_n": {w: len(v) for w, v in sorted(per_wave.items())},
        }
    return {"arms": arms, "channel": channel, "matched_waves": sorted(matched),
            "per_arm": per_arm}


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def probe_run(run_id: str, runs_dir: str) -> None:
    """Candidate-set sizes for ONE run, so the checks can be seen to be non-vacuous."""
    path = os.path.join(runs_dir, run_id, "events.jsonl")
    ex = extract_run(path)
    cert = certify(ex)
    print("== probe run %s" % run_id)
    print("   events                    %d" % ex["events"])
    print("   combat_capture rows       %d  (invalid %d)" % (ex["captures"], ex["captures_invalid"]))
    print("   waves in capture stream   %s" % sorted(ex["waves"]))
    print("   enemy entity rows         %d  (is_boosted, excluded: %d)"
          % (ex["enemy_rows"], ex["enemy_rows_boosted"]))
    print("   enemy rows of LARGE-HP types %s: %d" % (list(LARGE_HP_TYPES), ex["enemy_rows_large"]))
    print("   (wave,type) max_hp cells  %d" % ex["maxhp_cells"])
    table = modal_maxhp(ex)
    for key in sorted(table):
        value, n, distinct = table[key]
        print("      w%-3s %-16s modal max_hp %-6s n=%-6d distinct_values=%d"
              % (key[0], key[1], value, n, distinct))
    print("   ch1 capture-differenced drops  %d  over %d captures"
          % (ex["drop_events"], ex["captures"]))
    for wave in sorted(ex["drops"]):
        print("      w%-3s drops %s" % (wave, ex["drops"][wave]))
    print("   ch2 player_damage events       %d  (no wave attributable: %d)"
          % (ex["player_damage_events"], ex["player_damage_no_wave"]))
    for wave in sorted(ex["drops_pd"]):
        print("      w%-3s drops %s" % (wave, ex["drops_pd"][wave]))
    agree = ex["drop_events"] == ex["player_damage_events"]
    print("   ch1 vs ch2 count  %d vs %d  %s"
          % (ex["drop_events"], ex["player_damage_events"], "AGREE" if agree else "DISAGREE"))
    if not agree:
        c1 = sorted(v for vs in ex["drops"].values() for v in vs)
        c2 = sorted(v for vs in ex["drops_pd"].values() for v in vs)
        missed = list(c2)
        for v in c1:
            if v in missed:
                missed.remove(v)
        print("      ch1 misses %s -- these are hits landing ACROSS a wave boundary, "
              "which ch1's within-wave rule excludes by construction" % missed)
    print("   certification (capture stream):")
    for key in ("character_observed", "character_requested", "character_ok",
                "observed_danger", "danger_ok", "n_difficulty_readbacks",
                "opener", "opener_ok", "dial_readback", "mod_version"):
        print("      %-24s %s" % (key, cert[key]))


def report_field_variation(rows: list, extracts: dict) -> None:
    """Confirms every field FILTERED on actually varies. A filter on a constant or
    on an always-null field is how a vacuous zero gets reported as a result."""
    print("== filter-field variation (a filter on a constant field is a vacuous filter)")
    arms = Counter(r["_arm"] for r in rows)
    print("   ladder arm (from fixture_file)  distinct=%d  %s" % (len(arms), dict(arms)))
    fixtures = Counter(r["_fixture"] for r in rows)
    print("   ladder fixture                  distinct=%d  %s" % (len(fixtures), dict(fixtures)))
    dials = Counter(
        json.dumps(certify(ex)["dial_readback"], sort_keys=True) for ex in extracts.values()
    )
    print("   capture-stream dial readback    distinct=%d" % len(dials))
    for key, n in dials.most_common():
        print("      %-44s n=%d" % (key, n))
    types = Counter()
    waves = Counter()
    boosted = Counter()
    for ex in extracts.values():
        for (wave, ty) in ex["maxhp"]:
            types[ty] += 1
            waves[wave] += 1
        boosted["boosted" if ex["enemy_rows_boosted"] else "none"] += 1
    print("   is_boosted (excluded from max_hp) present in %d/%d runs"
          % (boosted["boosted"], len(extracts)))
    print("   large-HP types seen             %s" % dict(types))
    print("   waves carrying max_hp cells     distinct=%d  %s" % (len(waves), sorted(waves)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ladder", default=DEFAULT_LADDER)
    ap.add_argument("--runs-dir", default=default_runs_dir())
    ap.add_argument("--probe-run", default=None,
                    help="print candidate-set sizes for ONE run and exit")
    ap.add_argument("--health", action="store_true",
                    help="per-trial health-arm dose readback")
    ap.add_argument("--damage-aggregate", action="store_true",
                    help="COMPLETION-TIME ONLY: per-arm matched-wave drop-size table. "
                         "Section 28g forbids interim interpretation.")
    ap.add_argument("--arms", default="control,D75,D50",
                    help="arms for the damage aggregate, comma separated")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    if args.probe_run:
        probe_run(args.probe_run, args.runs_dir)
        return 0

    rows = load_ladder(args.ladder)
    print("== ladder %s" % args.ladder)
    print("   trial rows                %d" % len(rows))
    usable = [r for r in rows if r.get("run_id")]
    print("   rows with a run_id        %d" % len(usable))
    print("   rows with a known arm     %d" % sum(1 for r in usable if r["_arm"]))

    extracts = {}
    missing = []
    for row in usable:
        path = os.path.join(args.runs_dir, row["run_id"], "events.jsonl")
        if not os.path.isfile(path):
            missing.append(row["run_id"])
            continue
        extracts[row["run_id"]] = extract_run(path)
    print("   telemetry found           %d   missing %d %s"
          % (len(extracts), len(missing), missing if missing else ""))
    if not extracts:
        print("   NOTHING TO CHECK -- candidate set is empty, this is not a pass")
        return 1

    # ---- certification, every trial -------------------------------------
    print("\n== arm certification (capture stream, never summary.json)")
    print("   candidate set: %d trials" % len(extracts))
    cert_fail = []
    for row in usable:
        ex = extracts.get(row["run_id"])
        if ex is None:
            continue
        c = certify(ex)
        problems = []
        if not c["character_ok"]:
            problems.append("character_ok=%s (observed %s vs requested %s)"
                            % (c["character_ok"], c["character_observed"], c["character_requested"]))
        if not c["character_is_expected"]:
            problems.append("character %s != %s" % (c["character_observed"], REQUIRED_CHARACTER))
        if not c["danger_ok"]:
            problems.append("observed_danger=%r != %d" % (c["observed_danger"], REQUIRED_DANGER))
        if not c["opener_ok"]:
            problems.append("opener=%r != %s" % (c["opener"], REQUIRED_OPENER))
        dm = dial_matches_arm(c["dial_readback"], row["_arm"])
        if dm is not True:
            problems.append("dial readback %r does not confirm arm %s (match=%r)"
                            % (c["dial_readback"], row["_arm"], dm))
        if problems:
            cert_fail.append((row["run_id"], row["_arm"], problems))
    print("   trials failing certification: %d of %d" % (len(cert_fail), len(extracts)))
    for run_id, arm, problems in cert_fail:
        print("      %s [%s] %s" % (run_id, arm, "; ".join(problems)))

    report_field_variation([r for r in usable if r["run_id"] in extracts], extracts)

    by_arm = defaultdict(dict)
    for row in usable:
        if row["run_id"] in extracts:
            by_arm[row["_arm"]][row["run_id"]] = extracts[row["run_id"]]

    result = {"certification_failures": [(r, a, p) for r, a, p in cert_fail]}

    # ---- CHECK A ---------------------------------------------------------
    if args.health:
        reference = build_control_reference(by_arm.get("control", {}))
        print("\n== CHECK A: health-arm dose readback (per trial, deterministic)")
        print("   control reference built from %d control trials, %d (wave,type) cells"
              % (len(by_arm.get("control", {})), len(reference)))
        disagreeing = {k: v for k, v in reference.items() if len(v["values_seen"]) > 1}
        print("   reference cells where control trials DISAGREE: %d %s"
              % (len(disagreeing), sorted(disagreeing) if disagreeing else ""))
        usable_ref = {k: v for k, v in reference.items() if v["value"] >= MIN_BASELINE_MAX_HP}
        print("   reference cells at or above the baseline floor (max_hp >= %d): %d"
              % (MIN_BASELINE_MAX_HP, len(usable_ref)))
        health_out = {}
        for arm in HEALTH_ARMS:
            trials = by_arm.get(arm, {})
            print("   -- arm %s  expected ratio %.4f  trials %d" %
                  (arm, 1.0 / ARM_DIAL[arm]["health"], len(trials)))
            for run_id, ex in trials.items():
                res = health_readback(ex, arm, reference)
                health_out[run_id] = res
                print("      %s  cells: candidate %d -> large-HP %d -> matched+floor %d | "
                      "ok %d mismatch %d | %s"
                      % (run_id, res["n_candidate_cells"], res["n_cells_large_hp_types"],
                         res["n_cells_matched_to_reference"], res["n_cells_ok"],
                         res["n_cells_mismatch"], res["verdict"]))
                for c in res["cells"]:
                    print("          w%-3s %-16s ctl %-5s trial %-5s ratio %.4f  %s (n=%d)"
                          % (c["wave"], c["type"], c["control_max_hp"], c["trial_max_hp"],
                             c["ratio"], "ok" if c["ok"] else "MISMATCH -> EXCLUDE TRIAL",
                             c["n_obs"]))
        excluded = [r for r, v in health_out.items() if v["verdict"] != "PASS"]
        print("   TRIALS EXCLUDED OR UNVERIFIED: %d %s" % (len(excluded), excluded))
        # Self-consistency: control trials against themselves must read 1.0.
        print("   positive control -- control arm read against the same reference "
              "(expected ratio 1.0):")
        for run_id, ex in by_arm.get("control", {}).items():
            table = modal_maxhp(ex)
            cells = [(k, reference[k]["value"] / float(v[0]))
                     for k, v in table.items()
                     if k in reference and reference[k]["value"] >= MIN_BASELINE_MAX_HP and v[0]]
            bad = [(k, r) for k, r in cells if abs(r - 1.0) > RATIO_TOL]
            print("      %s cells %d  off-unity %d %s" % (run_id, len(cells), len(bad), bad))
        result["health"] = health_out

    # ---- CHECK B ---------------------------------------------------------
    if args.damage_aggregate:
        arms = [a.strip() for a in args.arms.split(",") if a.strip()]
        print("\n== CHECK B: damage-arm dose readback "
              "(median player HP-DROP SIZE, MATCHED WAVES, per arm)")
        print("   COMPLETION-TIME ARTIFACT. Section 28g forbids interim interpretation.")
        result["damage"] = {}
        for channel, label in (("drops_pd", "ch2 player_damage amounts (PRIMARY)"),
                               ("drops", "ch1 capture-differenced (corroboration)")):
            agg = damage_aggregate(by_arm, arms, channel)
            print("   -- channel %s: %s" % (channel, label))
            print("      arms compared      %s" % agg["arms"])
            print("      matched waves      %s   (waves REACHED by every arm compared)"
                  % agg["matched_waves"])
            for arm in arms:
                a = agg["per_arm"][arm]
                print("      %-8s trials %d | drops all-waves %d -> matched %d | "
                      "median %s mean %s range %s..%s"
                      % (arm, a["n_trials"], a["n_drops_all_waves"], a["n_drops_matched"],
                         a["median_drop_size"],
                         None if a["mean_drop_size"] is None else round(a["mean_drop_size"], 3),
                         a["min_drop"], a["max_drop"]))
                print("         per-wave n       %s" % a["per_wave_n"])
                print("         per-wave median  %s" % a["per_wave_median"])
            result["damage"][channel] = agg

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, default=str)
        print("\nwrote %s" % args.json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
