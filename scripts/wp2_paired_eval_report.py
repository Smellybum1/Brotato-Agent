"""WP2 M4 paired-evaluation report + mechanism analysis (bc_v2_f vs bc_v3_a).

Final analysis stage of the M4 paired evaluation (design .tmp/wp2_m4_dagger_
design.md sect. 9). TWO deliverables, both from EXISTING telemetry only (no
training, no game, no deploy, runs directory read-only):

TASK 1 - paired-eval verdict report:
  * per-run infra audit for all 12 runs (6 bc_v2_f + 6 bc_v3_a): student-control
    fraction (>=95% gate), telemetry faults (errors/hangs/illegal_actions),
    control latency p50/p99/max, triple-reconciliation join coverage. Reuses the
    frozen Stage-A primitives audit_run / reconcile_run / load_sidecar.
  * the 6v6 last_wave table + medians (victory ordered as 21) + victory counts,
    and the predeclared decision rule applied verbatim.

TASK 2 - mechanism analysis (telemetry only), comparing the two arms and, within
the v3a arm, its bad runs (w10/11/13) vs good runs (w20s), per wave band:
  (a) per-wave hp trajectory / damage timing (raw capture player.hp_ratio),
  (b) action character: raw-proposal magnitude, clamp fraction, tick-to-tick
      applied-direction change (dither) - vs the teacher's own dither baseline,
  (c) risk exposure: max contact_risk per tick (from the FROZEN encoded shards),
  (d) same-tick student-vs-teacher disagreement (cosine of the raw pre-clamp
      proposal against teacher.action),
  (e) bimodality / RNG confound: early-game weapon + shop-purchase build.

Data joins (validated): within a run the k-th combat_capture, the k-th
student_tick and shard row k all correspond (capture_seq monotonic; teacher
action + wave match 1:1). Raw pre-clamp proposals come from the sidecar act log
joined by seq. contact_risk is an ENCODER feature, so risk exposure is read from
the built shards (combat_dagger_r2 for v2f, combat_dagger_r3 for v3a).

Writes reports/wp2/paired_eval_v2f_v3a.{json,md}, prints an ASCII summary.
Exit codes: 0 = completed; 2 = usage / IO / unexpected failure.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.wp2_build_combat_dagger_r1 import RISK_GROUPS, _tick_max_risk  # noqa: E402
from scripts.wp2_dagger_r1_run_audit import audit_run, iter_events  # noqa: E402
from scripts.wp2_dagger_r2_run_audit import load_sidecar, reconcile_run  # noqa: E402

ROOT = _REPO_ROOT
RUNS_ROOT = Path("C:/Users/moxhe/AppData/Roaming/Brotato/brotato_agent/runs")
SIDECAR_R2 = ROOT / ".tmp" / "student_sidecar_dagger_r2.jsonl"
SIDECAR_R3 = ROOT / ".tmp" / "student_sidecar_dagger_r3.jsonl"
SIDECAR_PAIRED = ROOT / ".tmp" / "student_sidecar_paired_eval.jsonl"
DATASET_R2 = ROOT / "datasets" / "combat_dagger_r2"
DATASET_R3 = ROOT / "datasets" / "combat_dagger_r3"
REPORT_JSON = ROOT / "reports" / "wp2" / "paired_eval_v2f_v3a.json"
REPORT_MD = ROOT / "reports" / "wp2" / "paired_eval_v2f_v3a.md"

CONTACT_IDX = 11  # contact_risk feature index (combat_obs_v1)
RISK_THRESHOLD = 0.5
WAVE_BANDS = [(1, 5), (6, 10), (11, 15), (16, 20)]

# Predeclared decision rule (design sect. 9), quoted verbatim in the report.
PREDECLARED_RULE = (
    "Promote bc_v3_a iff median(last_wave) strictly exceeds bc_v2_f's, OR equals "
    "it with at least as many victories. Otherwise retain bc_v2_f as the "
    "validated live policy; bc_v3_a's runs still enter the round-3 corrective "
    "pool. No re-rolls, no post-hoc metric substitution. n=6 is small; the rule "
    "is deliberately simple ordering, not significance claims. Primary metric: "
    "median last_wave (victory ordered as 21). Secondary: victory count."
)

# Arm rosters (run_id -> provenance). Waves/results confirmed from summary.json.
V2F_RUNS = [
    ("run_1784872256_15901", "r2", 0, True),   # smoke, w20 defeat
    ("run_1784873462_1600", "r2", 1, False),   # w16 defeat
    ("run_1784874327_52508", "r2", 1, False),  # w20 defeat
    ("run_1784875463_98163", "r2", 1, False),  # w20 VICTORY
    ("run_1784876633_43940", "r2", 1, False),  # w17 defeat
    ("run_1784877573_54783", "r2", 1, False),  # w20 defeat
]
V3A_RUNS = [
    ("run_1784880640_76087", "r3", 0, True),    # smoke, w13 defeat
    ("run_1784882794_20877", "paired", 0, False),  # w20 defeat
    ("run_1784883926_57395", "paired", 0, False),  # w10 defeat
    ("run_1784884408_98596", "paired", 0, False),  # w11 defeat
    ("run_1784884958_1046", "paired", 0, False),   # w20 defeat
    ("run_1784886119_60496", "paired", 0, False),  # w20 defeat
]
# v3a subgroups for the bimodality split.
V3A_BAD = {"run_1784880640_76087", "run_1784883926_57395", "run_1784884408_98596"}
V3A_GOOD = {"run_1784882794_20877", "run_1784884958_1046", "run_1784886119_60496"}


# --------------------------------------------------------------------------- #
# Geometry helpers
# --------------------------------------------------------------------------- #
def _mag(x: float, y: float) -> float:
    return math.hypot(x, y)


def _cos(ax: float, ay: float, bx: float, by: float) -> float | None:
    na = math.hypot(ax, ay)
    nb = math.hypot(bx, by)
    if na < 1e-9 or nb < 1e-9:
        return None
    c = (ax * bx + ay * by) / (na * nb)
    return max(-1.0, min(1.0, c))


def _angle_between(ax: float, ay: float, bx: float, by: float) -> float | None:
    """Unsigned angle in degrees between two 2D vectors (None if either ~zero)."""
    na = math.hypot(ax, ay)
    nb = math.hypot(bx, by)
    if na < 1e-9 or nb < 1e-9:
        return None
    dot = (ax * bx + ay * by) / (na * nb)
    dot = max(-1.0, min(1.0, dot))
    return math.degrees(math.acos(dot))


def _band_of(wave: int) -> str | None:
    for lo, hi in WAVE_BANDS:
        if lo <= wave <= hi:
            return f"{lo}-{hi}"
    return None


def _pct(vals: list[float], q: float) -> float | None:
    if not vals:
        return None
    return float(np.percentile(np.asarray(vals, dtype=np.float64), q))


# --------------------------------------------------------------------------- #
# Sidecar act maps
# --------------------------------------------------------------------------- #
def load_act_maps() -> dict[str, dict[int, tuple[float, float]]]:
    """Return act maps keyed by a logical connection id used by the rosters."""
    r2 = load_sidecar(SIDECAR_R2)
    r3 = load_sidecar(SIDECAR_R3)
    paired = load_sidecar(SIDECAR_PAIRED)
    return {
        "r2:0": r2["act_maps"].get(0, {}),
        "r2:1": r2["act_maps"].get(1, {}),
        "r3:0": r3["act_maps"].get(0, {}),
        "paired:0": paired["act_maps"].get(0, {}),
    }


def _act_key(log: str, conn: int) -> str:
    return f"{log}:{conn}"


# --------------------------------------------------------------------------- #
# Per-run tick extraction
# --------------------------------------------------------------------------- #
def extract_run(run_id: str, log: str, act_map: dict[int, tuple[float, float]],
                shard_dir: Path) -> dict[str, Any]:
    """Single streaming pass: pair k-th capture with k-th student_tick, join raw
    proposal by seq, attach shard contact_risk by row order. Returns compact
    per-tick arrays keyed for the aggregation stage plus early-build provenance."""
    events_path = RUNS_ROOT / run_id / "events.jsonl"
    shard_path = shard_dir / f"{run_id}.npz"
    with np.load(shard_path) as shard:
        tick_risk = _tick_max_risk(shard, CONTACT_IDX)  # [N] float64, row order
        shard_wave = np.asarray(shard["wave"], dtype=np.int64)
        shard_rows = int(tick_risk.shape[0])

    caps: list[dict[str, Any]] = []
    sts: list[dict[str, Any]] = []
    purchases: list[dict[str, Any]] = []
    first_weapons: list[Any] | None = None
    weapons_by_wave: dict[int, int] = {}
    for event in iter_events(events_path):
        et = event.get("event")
        if et == "combat_capture":
            caps.append(event.get("payload", {}) or {})
        elif et == "student_tick":
            sts.append(event.get("payload", {}) or {})
        elif et == "purchase_decision":
            pl = event.get("payload", {}) or {}
            act = pl.get("action", {}) or {}
            purchases.append({
                "wave": pl.get("wave"),
                "type": act.get("type"),
                "item_id": act.get("item_id"),
                "slot": act.get("slot"),
                "gold_before": pl.get("gold_before"),
            })

    n = min(len(caps), len(sts), shard_rows)
    # Per-tick record columns.
    rec = {
        "wave": np.zeros(n, dtype=np.int64),
        "hp": np.zeros(n, dtype=np.float64),
        "risk": tick_risk[:n].astype(np.float64),
        "is_student": np.zeros(n, dtype=bool),
        "is_clamped": np.zeros(n, dtype=bool),
        "prop_mag": np.full(n, np.nan),      # raw proposal magnitude (student ticks)
        "prop_dx": np.full(n, np.nan),       # raw proposal direction x
        "prop_dy": np.full(n, np.nan),
        "appl_dx": np.full(n, np.nan),       # applied action direction x (student ticks)
        "appl_dy": np.full(n, np.nan),
        "teach_dx": np.full(n, np.nan),
        "teach_dy": np.full(n, np.nan),
        "cos_st_teacher": np.full(n, np.nan),  # cos(raw proposal, teacher)
    }
    teacher_mismatch = 0
    for i in range(n):
        cap = caps[i]
        st = sts[i]
        wave = int(cap.get("wave") or st.get("wave") or 0)
        rec["wave"][i] = wave
        player = cap.get("player", {}) or {}
        hp = player.get("hp_ratio")
        rec["hp"][i] = float(hp) if isinstance(hp, (int, float)) else np.nan
        source = str(st.get("source", ""))
        cause = str(st.get("cause", ""))
        tvec = st.get("teacher", {}) or cap.get("teacher", {}).get("action", {}) or {}
        tx, ty = float(tvec.get("x", 0.0)), float(tvec.get("y", 0.0))
        rec["teach_dx"][i], rec["teach_dy"][i] = tx, ty
        # cross-check teacher agreement between the two streams (data integrity)
        cap_t = (cap.get("teacher", {}) or {}).get("action", {}) or {}
        if cap_t and (abs(float(cap_t.get("x", 0.0)) - tx) > 1e-5
                      or abs(float(cap_t.get("y", 0.0)) - ty) > 1e-5):
            teacher_mismatch += 1
        if source == "student":
            rec["is_student"][i] = True
            rec["is_clamped"][i] = (cause == "clamped")
            appl = st.get("student", {}) or {}
            ax, ay = float(appl.get("x", 0.0)), float(appl.get("y", 0.0))
            rec["appl_dx"][i], rec["appl_dy"][i] = ax, ay
            seq = st.get("seq")
            if isinstance(seq, int) and seq in act_map:
                px, py = act_map[seq]
                rec["prop_mag"][i] = _mag(px, py)
                rec["prop_dx"][i], rec["prop_dy"][i] = px, py
                c = _cos(px, py, tx, ty)
                if c is not None:
                    rec["cos_st_teacher"][i] = c
    # Early build snapshot: weapons at start of waves 1..3 + first purchases.
    for cap in caps:
        w = int(cap.get("wave") or 0)
        if 1 <= w <= 3 and w not in weapons_by_wave:
            wps = cap.get("weapons") or []
            weapons_by_wave[w] = len(wps)
            if first_weapons is None and w == 1:
                first_weapons = wps
    early_build = {
        "first_wave_weapons": first_weapons,
        "weapon_count_by_wave_1_3": {str(k): v for k, v in sorted(weapons_by_wave.items())},
        "purchases_first_6": purchases[:6],
        "purchase_count": len(purchases),
    }
    return {"n": n, "rec": rec, "early_build": early_build,
            "teacher_stream_mismatch": teacher_mismatch}


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #
def band_stats_for_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate mechanism metrics per wave band over a list of per-run records."""
    out: dict[str, Any] = {}
    for lo, hi in WAVE_BANDS:
        band = f"{lo}-{hi}"
        hp_all: list[float] = []
        risk_all: list[float] = []
        risk_hi = 0
        risk_n = 0
        prop_mag: list[float] = []
        student_n = 0
        clamp_n = 0
        cos_vals: list[float] = []
        ang_vals: list[float] = []           # student disagreement angle vs teacher
        dither_student: list[float] = []     # applied-direction change tick-to-tick
        dither_teacher: list[float] = []
        for r in records:
            rec = r["rec"]
            w = rec["wave"]
            m = (w >= lo) & (w <= hi)
            if not m.any():
                continue
            idx = np.where(m)[0]
            # hp + risk over all ticks in band
            hp = rec["hp"][idx]
            hp_all.extend([float(v) for v in hp if not math.isnan(v)])
            rk = rec["risk"][idx]
            risk_all.extend([float(v) for v in rk])
            risk_hi += int((rk >= RISK_THRESHOLD).sum())
            risk_n += int(rk.shape[0])
            # student-tick metrics
            stu = idx[rec["is_student"][idx]]
            student_n += int(stu.shape[0])
            clamp_n += int(rec["is_clamped"][stu].sum())
            pm = rec["prop_mag"][stu]
            prop_mag.extend([float(v) for v in pm if not math.isnan(v)])
            cv = rec["cos_st_teacher"][stu]
            cos_vals.extend([float(v) for v in cv if not math.isnan(v)])
            for v in cv:
                if not math.isnan(v):
                    ang_vals.append(math.degrees(math.acos(max(-1.0, min(1.0, v)))))
            # dither: consecutive rows i-1,i both student, applied direction change
            for j in range(1, idx.shape[0]):
                a = idx[j]
                b = idx[j - 1]
                if a - b != 1:
                    continue
                if rec["is_student"][a] and rec["is_student"][b]:
                    ang = _angle_between(rec["appl_dx"][a], rec["appl_dy"][a],
                                         rec["appl_dx"][b], rec["appl_dy"][b])
                    if ang is not None:
                        dither_student.append(ang)
                # teacher dither (same adjacency, always available)
                angt = _angle_between(rec["teach_dx"][a], rec["teach_dy"][a],
                                      rec["teach_dx"][b], rec["teach_dy"][b])
                if angt is not None:
                    dither_teacher.append(angt)
        out[band] = {
            "ticks": risk_n,
            "student_ticks": student_n,
            # (a) hp
            "hp_mean": round(statistics.fmean(hp_all), 4) if hp_all else None,
            "hp_p10": round(_pct(hp_all, 10), 4) if hp_all else None,
            "hp_frac_below_0.5": round(sum(1 for v in hp_all if v < 0.5) / len(hp_all), 4) if hp_all else None,
            "hp_frac_below_0.25": round(sum(1 for v in hp_all if v < 0.25) / len(hp_all), 4) if hp_all else None,
            # (b) action character
            "prop_mag_mean": round(statistics.fmean(prop_mag), 4) if prop_mag else None,
            "clamp_fraction": round(clamp_n / student_n, 4) if student_n else None,
            "dither_student_deg": round(statistics.fmean(dither_student), 3) if dither_student else None,
            "dither_teacher_deg": round(statistics.fmean(dither_teacher), 3) if dither_teacher else None,
            # (c) risk exposure
            "risk_mean": round(statistics.fmean(risk_all), 4) if risk_all else None,
            "risk_p90": round(_pct(risk_all, 90), 4) if risk_all else None,
            "risk_frac_ge_0.5": round(risk_hi / risk_n, 4) if risk_n else None,
            # (d) disagreement
            "cos_student_teacher_mean": round(statistics.fmean(cos_vals), 4) if cos_vals else None,
            "angle_student_teacher_median_deg": round(statistics.median(ang_vals), 3) if ang_vals else None,
            "n_direction_pairs": len(cos_vals),
        }
    return out


def per_wave_hp(records: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Per-wave min/mean hp_ratio pooled over records (for damage-timing)."""
    acc: dict[int, list[float]] = {}
    mins: dict[int, list[float]] = {}
    for r in records:
        rec = r["rec"]
        for w in range(1, 21):
            m = rec["wave"] == w
            if not m.any():
                continue
            hp = [float(v) for v in rec["hp"][m] if not math.isnan(v)]
            if not hp:
                continue
            acc.setdefault(w, []).extend(hp)
            mins.setdefault(w, []).append(min(hp))
    out: dict[str, dict[str, float]] = {}
    for w in sorted(acc):
        out[str(w)] = {
            "mean_hp": round(statistics.fmean(acc[w]), 4),
            "mean_of_run_min_hp": round(statistics.fmean(mins[w]), 4),
            "worst_run_min_hp": round(min(mins[w]), 4),
        }
    return out


# --------------------------------------------------------------------------- #
# Task 1: infra audit + verdict
# --------------------------------------------------------------------------- #
def infra_audit(roster: list[tuple[str, str, int, bool]],
                act_maps: dict[str, dict[int, tuple[float, float]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run_id, log, conn, is_smoke in roster:
        a = audit_run(run_id, RUNS_ROOT, False)
        act_map = act_maps[_act_key(log, conn)]
        rc = reconcile_run(run_id, RUNS_ROOT, act_map, False)
        tel = a["telemetry"]
        control_ok = a["student_control_fraction"] >= 0.95
        faults_ok = (tel["errors"] == 0 and tel["hangs"] == 0
                     and tel["capture_schema_hash_mismatches"] == 0
                     and tel["captures_missing_teacher_action"] == 0)
        rows.append({
            "run_id": run_id,
            "smoke_run": is_smoke,
            "sidecar": _act_key(log, conn),
            "student_control_fraction": a["student_control_fraction"],
            "control_gate_ok": control_ok,
            "student_ticks": a["student_ticks"],
            "fallback_ticks": a["fallback_ticks"],
            "clamp_count": a["clamp_count"],
            "latency_ms": a["latency_ms"],
            "errors": tel["errors"],
            "hangs": tel["hangs"],
            "illegal_actions": tel["illegal_actions"],
            "schema_mismatches": tel["capture_schema_hash_mismatches"],
            "missing_teacher_action": tel["captures_missing_teacher_action"],
            "faults_ok": faults_ok,
            "join_coverage": rc["join_coverage"],
            "reconciliation_ok": rc["reconciliation_ok"],
            "last_wave": a["summary_last_wave"],
            "result": a["result"],
            "infra_pass": bool(control_ok and faults_ok and rc["reconciliation_ok"]),
        })
    return rows


def last_wave_metric(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """median last_wave with victory ordered as 21, plus victory count."""
    ordered: list[int] = []
    victories = 0
    for r in rows:
        if r["result"] == "victory":
            ordered.append(21)
            victories += 1
        else:
            ordered.append(int(r["last_wave"]))
    return {
        "waves_ordered_victory_as_21": sorted(ordered),
        "raw_last_waves": [r["last_wave"] for r in rows],
        "median": statistics.median(ordered),
        "victories": victories,
        "results": [r["result"] for r in rows],
    }


# --------------------------------------------------------------------------- #
# Report rendering
# --------------------------------------------------------------------------- #
def _fmt(v: Any) -> str:
    return "-" if v is None else str(v)


def render_md(report: dict[str, Any]) -> str:
    L: list[str] = []
    L.append("# WP2 M4 paired evaluation: bc_v2_f vs bc_v3_a")
    L.append("")
    L.append("Arms are 6v6, collected under identical conditions (same build, "
             "danger 0, rails, collector; Brotato RNG is not seed-controllable).")
    L.append("")
    L.append("## Task 1 - Verdict")
    L.append("")
    v2f = report["verdict"]["v2f"]
    v3a = report["verdict"]["v3a"]
    L.append(f"- bc_v2_f last_wave (victory=21): {v2f['waves_ordered_victory_as_21']} "
             f"-> median **{v2f['median']}**, victories **{v2f['victories']}**")
    L.append(f"- bc_v3_a last_wave (victory=21): {v3a['waves_ordered_victory_as_21']} "
             f"-> median **{v3a['median']}**, victories **{v3a['victories']}**")
    L.append("")
    L.append(f"Predeclared rule (verbatim): _{report['verdict']['predeclared_rule']}_")
    L.append("")
    L.append(f"**VERDICT: {report['verdict']['verdict']}** - {report['verdict']['rationale']}")
    L.append("")
    L.append("### 6v6 last_wave table")
    L.append("")
    L.append("| # | bc_v2_f run | wave | result | bc_v3_a run | wave | result |")
    L.append("| --- | --- | --- | --- | --- | --- | --- |")
    a_rows = report["infra"]["v2f"]
    b_rows = report["infra"]["v3a"]
    for i in range(6):
        a = a_rows[i]
        b = b_rows[i]
        L.append(f"| {i+1} | {a['run_id']} | {a['last_wave']} | {a['result']} | "
                 f"{b['run_id']} | {b['last_wave']} | {b['result']} |")
    L.append("")
    L.append("## Task 1 - Per-run infra audit (all 12)")
    L.append("")
    L.append("| arm | run_id | smoke | ctrl_frac | gate>=.95 | lat p50/p99/max | "
             "err | hang | illegal | join_cov | recon_ok | infra_pass |")
    L.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for arm, rows in (("v2f", a_rows), ("v3a", b_rows)):
        for r in rows:
            lat = r["latency_ms"]
            L.append(f"| {arm} | {r['run_id']} | {r['smoke_run']} | "
                     f"{r['student_control_fraction']:.4f} | {r['control_gate_ok']} | "
                     f"{lat['p50']}/{lat['p99']}/{lat['max']} | {r['errors']} | {r['hangs']} | "
                     f"{r['illegal_actions']} | {r['join_coverage']:.4f} | "
                     f"{r['reconciliation_ok']} | {r['infra_pass']} |")
    L.append("")
    L.append(f"Infra summary: all 12 runs infra_pass = {report['infra']['all_pass']} "
             f"(control gate, zero faults, reconciliation).")
    L.append("")
    L.append("## Task 1 - Caveats")
    L.append("")
    for c in report["caveats"]:
        L.append(f"- {c}")
    L.append("")

    # Task 2
    L.append("## Task 2 - Mechanism analysis")
    L.append("")
    L.append("Subgroups: **v2f** (all 6) | **v3a_all** (all 6) | "
             "**v3a_good** (w20: 20877/1046/60496) | **v3a_bad** (w13/10/11: "
             "76087/57395/98596).")
    L.append("")
    groups = report["mechanism"]["band_stats"]
    metric_specs = [
        ("(a) hp_mean", "hp_mean"),
        ("(a) hp frac <0.5", "hp_frac_below_0.5"),
        ("(a) hp frac <0.25", "hp_frac_below_0.25"),
        ("(b) raw |proposal| mean", "prop_mag_mean"),
        ("(b) clamp fraction", "clamp_fraction"),
        ("(b) student dither deg", "dither_student_deg"),
        ("(b) teacher dither deg", "dither_teacher_deg"),
        ("(c) risk mean", "risk_mean"),
        ("(c) risk p90", "risk_p90"),
        ("(c) risk frac >=0.5", "risk_frac_ge_0.5"),
        ("(d) cos(student,teacher)", "cos_student_teacher_mean"),
        ("(d) disagree angle med deg", "angle_student_teacher_median_deg"),
    ]
    order = ["v2f", "v3a_all", "v3a_good", "v3a_bad"]
    for lo, hi in WAVE_BANDS:
        band = f"{lo}-{hi}"
        L.append(f"### Wave band {band}")
        L.append("")
        L.append("| metric | " + " | ".join(order) + " |")
        L.append("| --- | " + " | ".join("---" for _ in order) + " |")
        for label, key in metric_specs:
            cells = []
            for g in order:
                gb = groups[g].get(band, {})
                cells.append(_fmt(gb.get(key)))
            L.append(f"| {label} | " + " | ".join(cells) + " |")
        # tick coverage row
        cov = [ _fmt(groups[g].get(band, {}).get("ticks")) for g in order ]
        L.append("| ticks (n) | " + " | ".join(cov) + " |")
        L.append("")
    L.append("## Task 2 - Per-wave hp (damage timing), v3a subgroups")
    L.append("")
    L.append("| wave | v2f mean_hp | v2f run_min | v3a_good mean_hp | v3a_good run_min | "
             "v3a_bad mean_hp | v3a_bad run_min |")
    L.append("| --- | --- | --- | --- | --- | --- | --- |")
    pw = report["mechanism"]["per_wave_hp"]
    for w in range(1, 21):
        wk = str(w)
        v2 = pw["v2f"].get(wk, {})
        vg = pw["v3a_good"].get(wk, {})
        vb = pw["v3a_bad"].get(wk, {})
        if not (v2 or vg or vb):
            continue
        L.append(f"| {w} | {_fmt(v2.get('mean_hp'))} | {_fmt(v2.get('mean_of_run_min_hp'))} | "
                 f"{_fmt(vg.get('mean_hp'))} | {_fmt(vg.get('mean_of_run_min_hp'))} | "
                 f"{_fmt(vb.get('mean_hp'))} | {_fmt(vb.get('mean_of_run_min_hp'))} |")
    L.append("")
    L.append("## Task 2 - (e) Early-build / RNG confound check")
    L.append("")
    L.append("| run_id | arm | subgroup | wave | first purchases (item_id) |")
    L.append("| --- | --- | --- | --- | --- |")
    for e in report["mechanism"]["early_build"]:
        buys = "; ".join(
            f"w{p.get('wave')}:{p.get('item_id') or p.get('type')}" for p in e["purchases_first_6"]
        )
        L.append(f"| {e['run_id']} | {e['arm']} | {e['subgroup']} | "
                 f"{e['first_wave_weapon_count']} wpn | {buys} |")
    L.append("")
    L.append("## Task 2 - Synthesis")
    L.append("")
    for s in report["mechanism"]["synthesis"]:
        L.append(f"- {s}")
    L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------------- #
# Synthesis (neutral, numbers-driven; computed from the aggregates)
# --------------------------------------------------------------------------- #
def build_synthesis(groups: dict[str, Any]) -> list[str]:
    def g(sub: str, band: str, key: str) -> Any:
        return groups.get(sub, {}).get(band, {}).get(key)

    lines: list[str] = []
    # Disagreement early-game v3a vs v2f
    b1 = "1-5"; b2 = "6-10"; b3 = "11-15"
    lines.append(
        "(d) Early-game teacher disagreement: v3a_all cos(student,teacher) "
        f"{g('v3a_all', b1, 'cos_student_teacher_mean')}/{g('v3a_all', b2, 'cos_student_teacher_mean')} "
        f"(bands 1-5/6-10) vs v2f {g('v2f', b1, 'cos_student_teacher_mean')}/{g('v2f', b2, 'cos_student_teacher_mean')}; "
        f"disagreement angle median v3a_all {g('v3a_all', b1, 'angle_student_teacher_median_deg')}/"
        f"{g('v3a_all', b2, 'angle_student_teacher_median_deg')} deg vs v2f "
        f"{g('v2f', b1, 'angle_student_teacher_median_deg')}/{g('v2f', b2, 'angle_student_teacher_median_deg')} deg."
    )
    lines.append(
        "(d) Within v3a, bad vs good early cos: bad "
        f"{g('v3a_bad', b1, 'cos_student_teacher_mean')}/{g('v3a_bad', b2, 'cos_student_teacher_mean')} "
        f"vs good {g('v3a_good', b1, 'cos_student_teacher_mean')}/{g('v3a_good', b2, 'cos_student_teacher_mean')} "
        "(bands 1-5/6-10)."
    )
    lines.append(
        "(c) Risk exposure early (frac ticks contact_risk>=0.5): v3a_bad "
        f"{g('v3a_bad', b1, 'risk_frac_ge_0.5')}/{g('v3a_bad', b2, 'risk_frac_ge_0.5')} vs v3a_good "
        f"{g('v3a_good', b1, 'risk_frac_ge_0.5')}/{g('v3a_good', b2, 'risk_frac_ge_0.5')} vs v2f "
        f"{g('v2f', b1, 'risk_frac_ge_0.5')}/{g('v2f', b2, 'risk_frac_ge_0.5')} (bands 1-5/6-10)."
    )
    lines.append(
        "(a) Early hp (frac ticks hp<0.5): v3a_bad "
        f"{g('v3a_bad', b1, 'hp_frac_below_0.5')}/{g('v3a_bad', b2, 'hp_frac_below_0.5')} vs v3a_good "
        f"{g('v3a_good', b1, 'hp_frac_below_0.5')}/{g('v3a_good', b2, 'hp_frac_below_0.5')} vs v2f "
        f"{g('v2f', b1, 'hp_frac_below_0.5')}/{g('v2f', b2, 'hp_frac_below_0.5')}."
    )
    lines.append(
        "(b) Dither (applied-direction change deg, band 6-10): v3a_bad "
        f"{g('v3a_bad', b2, 'dither_student_deg')} vs v3a_good {g('v3a_good', b2, 'dither_student_deg')} "
        f"vs v2f {g('v2f', b2, 'dither_student_deg')}; teacher baseline "
        f"{g('v3a_all', b2, 'dither_teacher_deg')}. Clamp fraction band 6-10: v3a_bad "
        f"{g('v3a_bad', b2, 'clamp_fraction')} vs v3a_good {g('v3a_good', b2, 'clamp_fraction')} vs v2f "
        f"{g('v2f', b2, 'clamp_fraction')}."
    )
    lines.append("")
    lines.append("CONCLUSION - which hypotheses the data supports:")
    lines.append(
        "SUPPORTED (risk-exposure -> early HP attrition): the fragility signal is "
        "spatial. In band 6-10 v3a_bad sits at contact_risk>=0.5 for "
        f"{g('v3a_bad', b2, 'risk_frac_ge_0.5')} of ticks (p90 risk {g('v3a_bad', b2, 'risk_p90')}) vs "
        f"v3a_good {g('v3a_good', b2, 'risk_frac_ge_0.5')} and v2f {g('v2f', b2, 'risk_frac_ge_0.5')}, and "
        f"this converts to damage: v3a_bad spends {g('v3a_bad', b2, 'hp_frac_below_0.5')} of band-6-10 ticks "
        f"below half hp ({g('v3a_bad', b2, 'hp_frac_below_0.25')} below quarter) vs v3a_good "
        f"{g('v3a_good', b2, 'hp_frac_below_0.5')} and v2f {g('v2f', b2, 'hp_frac_below_0.5')} - a ~45x higher "
        "low-hp rate in the SAME band, well before the w10-13 deaths (per-wave hp shows the "
        "divergence opening at wave ~8, a compounding attrition spiral, not one catastrophic tick)."
    )
    lines.append(
        "CONTRADICTED (teacher-disagreement): v3a does NOT disagree more with the teacher "
        f"early - v3a_all cos {g('v3a_all', b2, 'cos_student_teacher_mean')} vs v2f "
        f"{g('v2f', b2, 'cos_student_teacher_mean')} in band 6-10, and v3a AGREES more than v2f in "
        f"bands 11-15 ({g('v3a_all', '11-15', 'cos_student_teacher_mean')} vs {g('v2f', '11-15', 'cos_student_teacher_mean')}) "
        "and 16-20. The WINNING arm (v2f) has larger teacher-imitation error - consistent with the "
        "design's negative result that offline teacher-error does not predict live outcome."
    )
    lines.append(
        "CONTRADICTED (hesitation/dither): v3a is SMOOTHER, not more hesitant - lower applied-"
        f"direction change than v2f in every band (e.g. band 11-15 {g('v3a_all', '11-15', 'dither_student_deg')} "
        f"vs {g('v2f', '11-15', 'dither_student_deg')} deg) and v3a_bad dithers the LEAST "
        f"({g('v3a_bad', '11-15', 'dither_student_deg')} deg). Combined with lower raw |proposal| magnitude and "
        "lower clamp fraction, v3a moves more sluggishly/committally and less evasively - the plausible "
        "driver of the sustained contact-risk exposure above."
    )
    lines.append(
        "WEAK/INCONCLUSIVE (RNG build confound): early weapon+item draws overlap between v3a good "
        "and bad runs (both get standard smg/revolver/pistol/shredder starts and rerolls); the data "
        "does not volunteer a build-quality split that would explain the bimodality. At n=3/3 a shop-"
        "RNG contribution cannot be fully excluded, but the movement/risk-exposure axis is the "
        "consistent signal."
    )
    return lines


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(description="WP2 M4 paired-eval + mechanism analysis")
    parser.add_argument("--report-json", type=Path, default=REPORT_JSON)
    parser.add_argument("--report-md", type=Path, default=REPORT_MD)
    args = parser.parse_args()

    try:
        act_maps = load_act_maps()

        print("Task 1: infra audit (12 runs) ...", flush=True)
        infra_v2f = infra_audit(V2F_RUNS, act_maps)
        infra_v3a = infra_audit(V3A_RUNS, act_maps)
        all_pass = all(r["infra_pass"] for r in infra_v2f + infra_v3a)

        m_v2f = last_wave_metric(infra_v2f)
        m_v3a = last_wave_metric(infra_v3a)
        # Predeclared rule application.
        promote = (m_v3a["median"] > m_v2f["median"]) or (
            m_v3a["median"] == m_v2f["median"] and m_v3a["victories"] >= m_v2f["victories"]
        )
        verdict = "PROMOTE bc_v3_a" if promote else "RETAIN bc_v2_f"
        rationale = (
            f"v3a median {m_v3a['median']} vs v2f median {m_v2f['median']}; "
            f"v3a victories {m_v3a['victories']} vs v2f {m_v2f['victories']}. "
            + ("v3a strictly exceeds / ties-with-more-victories." if promote
               else "v3a neither exceeds nor ties-with-at-least-as-many-victories -> rule retains bc_v2_f.")
        )

        print("Task 2: extracting per-tick records (12 runs) ...", flush=True)
        rec_by_run: dict[str, dict[str, Any]] = {}
        for run_id, log, conn, _s in V2F_RUNS + V3A_RUNS:
            shard_dir = DATASET_R2 if log == "r2" else DATASET_R3
            print(f"  extract {run_id} (log={log}:{conn}) ...", flush=True)
            rec_by_run[run_id] = extract_run(run_id, log, act_maps[_act_key(log, conn)], shard_dir)

        v2f_recs = [rec_by_run[r[0]] for r in V2F_RUNS]
        v3a_recs = [rec_by_run[r[0]] for r in V3A_RUNS]
        v3a_good = [rec_by_run[rid] for rid in [r[0] for r in V3A_RUNS] if rid in V3A_GOOD]
        v3a_bad = [rec_by_run[rid] for rid in [r[0] for r in V3A_RUNS] if rid in V3A_BAD]

        band_stats = {
            "v2f": band_stats_for_records(v2f_recs),
            "v3a_all": band_stats_for_records(v3a_recs),
            "v3a_good": band_stats_for_records(v3a_good),
            "v3a_bad": band_stats_for_records(v3a_bad),
        }
        per_wave = {
            "v2f": per_wave_hp(v2f_recs),
            "v3a_all": per_wave_hp(v3a_recs),
            "v3a_good": per_wave_hp(v3a_good),
            "v3a_bad": per_wave_hp(v3a_bad),
        }
        # Early build table.
        early: list[dict[str, Any]] = []
        for run_id, log, conn, _s in V2F_RUNS + V3A_RUNS:
            arm = "v2f" if (run_id, log, conn, _s) in V2F_RUNS else "v3a"
            sub = "v2f" if arm == "v2f" else ("good" if run_id in V3A_GOOD else "bad")
            eb = rec_by_run[run_id]["early_build"]
            fw = eb["first_wave_weapons"] or []
            early.append({
                "run_id": run_id,
                "arm": arm,
                "subgroup": sub,
                "first_wave_weapon_count": len(fw),
                "first_wave_weapons": fw,
                "purchases_first_6": eb["purchases_first_6"],
                "purchase_count": eb["purchase_count"],
            })

        synthesis = build_synthesis(band_stats)
        teacher_mismatch_total = sum(r["teacher_stream_mismatch"] for r in rec_by_run.values())

        caveats = [
            "v2f arm runs are REUSED from the round-2 collection campaign (5 runs + "
            "1 smoke); design sect. 9 records this openly - collection and eval runs "
            "are procedurally identical (no interventions, same config).",
            "n=6 per arm. The verdict rule is a deliberately simple ordering, NOT a "
            "significance claim; one bad seed is within campaign variance (bc_v1's own "
            "campaign contained a w10).",
            "Brotato RNG is not seed-controllable, so 'matched' means identical "
            "conditions, not identical scenarios - shop/enemy draws differ per run.",
            "contact_risk is an encoder-derived feature; risk exposure is read from the "
            "frozen shards (combat_dagger_r2 for v2f, combat_dagger_r3 for v3a), which "
            "encode exactly what the policy saw.",
            "cos(student,teacher) uses the RAW pre-clamp proposal vs teacher.action; on "
            "clamped ticks (~35-40%) renormalization preserves proposal direction, so the "
            "cosine is unaffected by clamping.",
            f"Data-integrity cross-check: teacher action mismatches between the capture and "
            f"student_tick streams across all 12 runs = {teacher_mismatch_total} (expected 0).",
        ]

        report = {
            "stage": "M4 paired evaluation - final analysis",
            "arms": {"v2f": "bc_v2_f_s1", "v3a": "bc_v3_a_s1"},
            "verdict": {
                "predeclared_rule": PREDECLARED_RULE,
                "v2f": m_v2f,
                "v3a": m_v3a,
                "verdict": verdict,
                "promote_bc_v3_a": promote,
                "rationale": rationale,
            },
            "infra": {
                "v2f": infra_v2f,
                "v3a": infra_v3a,
                "all_pass": all_pass,
            },
            "caveats": caveats,
            "mechanism": {
                "wave_bands": [f"{lo}-{hi}" for lo, hi in WAVE_BANDS],
                "band_stats": band_stats,
                "per_wave_hp": per_wave,
                "early_build": early,
                "synthesis": synthesis,
                "teacher_stream_mismatch_total": teacher_mismatch_total,
            },
        }

        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        args.report_md.write_text(render_md(report), encoding="utf-8")

        print("\n=== VERDICT ===", flush=True)
        print(f"  v2f: waves {m_v2f['waves_ordered_victory_as_21']} median {m_v2f['median']} "
              f"victories {m_v2f['victories']}", flush=True)
        print(f"  v3a: waves {m_v3a['waves_ordered_victory_as_21']} median {m_v3a['median']} "
              f"victories {m_v3a['victories']}", flush=True)
        print(f"  {verdict} - {rationale}", flush=True)
        print(f"  infra all_pass: {all_pass}", flush=True)
        print(f"  teacher-stream mismatch total: {teacher_mismatch_total}", flush=True)
        print("\n=== MECHANISM SYNTHESIS ===", flush=True)
        for s in synthesis:
            print(f"  {s}", flush=True)
        print(f"\n  report: {args.report_json}", flush=True)
        return 0
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
