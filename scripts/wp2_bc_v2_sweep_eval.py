"""WP2 bc_v2 round-2 sweep evaluation (frontier over corrective-mass x dropout).

Evaluates every bc_v2 sweep variant (C/D/E/F) alongside the round-1 references
(bc_v1_s1_full, bc_v2_a_s1, bc_v2_b_s1) on BOTH distributions, reusing the two
unchanged eval pathways verbatim -- no new metric maths:

  (a) teacher-val  -- the frozen combat_obs_v1 val split, via
      ``trainer.evaluation.bc_offline.evaluate_run`` (independent reload,
      checkpoint sha256 + normalization-manifest hash verified). Each model uses
      its OWN normalization manifest.

  (b) dagger-holdout -- the deterministic 10% combat_dagger_r1 holdout
      (seed 20260724, frac 0.10), EXCLUDED from training of every bc_v2
      candidate, reproduced by importing ``load_composite_dataset`` (not
      reimplemented). Label = teacher.action. Reuses the prediction/stratum
      helpers from ``scripts.wp2_dagger_holdout_eval``.

Findings only -- no promotion recommendation. Writes
``reports/wp2/bc_v2_sweep_report.{json,md}``.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from trainer.data.bc_v2_dataset import (  # noqa: E402
    DEFAULT_HOLDOUT_FRAC,
    DEFAULT_HOLDOUT_SEED,
    load_composite_dataset,
)
from trainer.evaluation.bc_offline import (  # noqa: E402
    build_policy_config_from_registry,
    evaluate_run,
    load_normalization_from_manifest,
    load_registry,
    verify_sha256,
)
from trainer.imitation.bc_training import (  # noqa: E402
    RISK_BIN_LABELS,
    WAVE_BAND_LABELS,
    _build_device_split,
    load_checkpoint,
    resolve_device,
)
from trainer.models.bc_policy_v1 import BCPolicyV1  # noqa: E402
from scripts.wp2_dagger_holdout_eval import (  # noqa: E402
    EXPECTED_HOLDOUT_N,
    _all_strata,
    _predict,
)

REGISTRY_DIR = REPO_ROOT / "models" / "registry"
REPORTS_DIR = REPO_ROOT / "reports" / "wp2"

# Round-1 references first, then the round-2 sweep variants. Order preserved in
# every table.
MODELS: tuple[str, ...] = (
    "bc_v1_s1_full",
    "bc_v2_a_s1",
    "bc_v2_b_s1",
    "bc_v2_c_s1",
    "bc_v2_d_s1",
    "bc_v2_e_s1",
    "bc_v2_f_s1",
)

# Sweep-knob provenance for the report (round-1 refs carry their trained values).
KNOBS: dict[str, dict[str, Any]] = {
    "bc_v1_s1_full": {"corrective_mass": None, "prev_action_dropout": 0.1, "lambda_mag": 0.5, "note": "no dagger data (teacher-only bc_v1)"},
    "bc_v2_a_s1": {"corrective_mass": 0.25, "prev_action_dropout": 0.1, "lambda_mag": 0.5, "note": "round-1 candidate A"},
    "bc_v2_b_s1": {"corrective_mass": 0.25, "prev_action_dropout": 0.1, "lambda_mag": 0.5, "note": "round-1 candidate B (aux heads, base export)"},
    "bc_v2_c_s1": {"corrective_mass": 0.10, "prev_action_dropout": 0.1, "lambda_mag": 0.5, "note": "round-2 C"},
    "bc_v2_d_s1": {"corrective_mass": 0.25, "prev_action_dropout": 0.4, "lambda_mag": 0.5, "note": "round-2 D"},
    "bc_v2_e_s1": {"corrective_mass": 0.10, "prev_action_dropout": 0.4, "lambda_mag": 0.5, "note": "round-2 E"},
    "bc_v2_f_s1": {"corrective_mass": 0.15, "prev_action_dropout": 0.4, "lambda_mag": 1.0, "note": "round-2 F (magnitude-repair probe)"},
    "bc_v2_g_s1": {"corrective_mass": 0.15, "prev_action_dropout": 0.4, "lambda_mag": 1.0, "note": "round-2b G (curriculum fine-tune from bc_v1, LR 3e-5, patience 3)"},
    "bc_v2_h_s1": {"corrective_mass": 0.05, "prev_action_dropout": 0.4, "lambda_mag": 1.0, "note": "round-2b H (fresh joint, low mass 0.05)"},
}

# §8 dual-distribution gate thresholds (.tmp/wp2_m4_dagger_design.md §8).
GATE_TV_MEDIAN_MAX = 6.5
GATE_TV_MAGERR_MAX = 0.06
GATE_HO_MEDIAN_MAX = 30.0
GATE_HO_RISK_HI_MEDIAN_MAX = 35.0
RISK_HI_STRATA = ("0.50-0.75", "0.75-inf")

MAG_EPS = 0.01
BATCH_SIZE = 4096
RISK_MID = "0.50-0.75"


def log(msg: str) -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# (a) teacher-val via the unchanged bc_offline path
# ---------------------------------------------------------------------------
def teacher_val_eval(device: str, models: tuple[str, ...] = MODELS) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in models:
        reg_path = REGISTRY_DIR / f"{name}.json"
        run_eval = evaluate_run(reg_path, checkpoint="best", device=device)
        s = run_eval.summary
        out[name] = {
            "overall": s["overall"],
            "by_risk_stratum": s["by_risk_stratum"],
            "by_wave_band": s["by_wave_band"],
            "checkpoint_sha256": s["checkpoint_sha256"],
            "checkpoint_epoch": s["checkpoint_epoch"],
        }
        o = s["overall"]
        log(
            f"[sweep:teacher-val] {name}: median={o['median_angular_error_deg']:.3f}deg "
            f"mean={o['mean_angular_error_deg']:.3f}deg |mag|={o['mean_abs_magnitude_error']:.4f} "
            f"risk[{RISK_MID}]={s['by_risk_stratum'].get(RISK_MID, {}).get('median_angular_error_deg', float('nan')):.3f}"
        )
    return out


# ---------------------------------------------------------------------------
# (b) dagger-holdout via the wp2_dagger_holdout_eval pathway (imported helpers)
# ---------------------------------------------------------------------------
def holdout_eval(
    device: torch.device, models: tuple[str, ...] = MODELS
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    anomalies: list[str] = []

    # Reproduce the training-stage holdout split by IMPORTING the loader. Pull
    # the shared dataset/config paths from the bc_v2_a registry (identical across
    # all bc_v2 registries; base dataset + split/input/schema are shared).
    ref_registry = load_registry(REGISTRY_DIR / "bc_v2_a_s1.json")
    rc = ref_registry["resolved_config"]
    dagger_dir = Path(ref_registry["bc_v2_provenance"]["dagger_dataset_dir"])

    log(
        f"[sweep:holdout] loading composite dataset (holdout_frac={DEFAULT_HOLDOUT_FRAC}, "
        f"holdout_seed={DEFAULT_HOLDOUT_SEED})"
    )
    composite = load_composite_dataset(
        rc["dataset_dir"], dagger_dir, rc["split_config"], rc["input_config"], rc["schema"],
    )
    holdout = composite.aux_holdout
    n_holdout = holdout.size
    if n_holdout != EXPECTED_HOLDOUT_N:
        anomalies.append(f"holdout row count {n_holdout} != expected {EXPECTED_HOLDOUT_N}")

    # Split-reproduction guard: holdout aux base rates must match the registry
    # (computed over this identical row set at training time).
    hd_mask = composite.holdout_aux_damage_mask.astype(bool)
    hm_mask = composite.holdout_aux_margin_mask.astype(bool)
    holdout_damage_rate = float(composite.holdout_aux_damage[hd_mask].mean()) if hd_mask.any() else float("nan")
    holdout_margin_mean = float(composite.holdout_aux_margin[hm_mask].mean()) if hm_mask.any() else float("nan")
    reg_rates = ref_registry["bc_v2_provenance"]["aux_base_rates"]
    if abs(holdout_damage_rate - float(reg_rates["holdout_aux_damage_base_rate"])) > 1e-6:
        anomalies.append("holdout aux_damage base rate != registry (split may not reproduce training)")
    if abs(holdout_margin_mean - float(reg_rates["holdout_aux_margin_mean"])) > 1e-6:
        anomalies.append("holdout aux_margin mean != registry (split may not reproduce training)")

    feature_names = list(composite.global_feature_names)
    ref_policy_cfg = build_policy_config_from_registry(rc, feature_names)
    group_names = tuple(spec.name for spec in ref_policy_cfg.group_specs)
    prev_idx = ref_policy_cfg.prev_action_indices

    # Reference split (bc_v1 manifest) for strata bins + label target; the
    # prev_action / risk_bin / wave_band fields do not depend on standardization.
    bc_v1_registry = load_registry(REGISTRY_DIR / "bc_v1_s1_full.json")
    bc_v1_ckpt = Path(bc_v1_registry["checkpoints"]["best"]["path"])
    bc_v1_norm = load_normalization_from_manifest(
        bc_v1_ckpt.parent / "normalization_manifest.json",
        bc_v1_registry["normalization_manifest_hash"], feature_names,
    )
    ref_split = _build_device_split(holdout, bc_v1_norm, group_names, prev_idx, device, pin=False)
    wave_band = ref_split.wave_band.to(device)
    risk_bin = ref_split.risk_bin.to(device)

    stratum_n = {
        "overall": int(ref_split.actions.shape[0]),
        "by_risk_stratum": {
            RISK_BIN_LABELS[b]: int((risk_bin == b).sum().item()) for b in range(len(RISK_BIN_LABELS))
        },
        "by_wave_band": {
            WAVE_BAND_LABELS[b]: int((wave_band == b).sum().item()) for b in range(len(WAVE_BAND_LABELS))
        },
    }

    results: dict[str, Any] = {}
    for name in models:
        registry = load_registry(REGISTRY_DIR / f"{name}.json")
        ckpt_entry = registry["checkpoints"]["best"]
        ckpt_path = Path(ckpt_entry["path"])
        sha = verify_sha256(ckpt_path, ckpt_entry["sha256"], f"{name}:best checkpoint")

        norm_path = ckpt_path.parent / "normalization_manifest.json"
        normalization = load_normalization_from_manifest(
            norm_path, registry["normalization_manifest_hash"], feature_names
        )
        policy_config = build_policy_config_from_registry(registry["resolved_config"], feature_names)
        model = BCPolicyV1(policy_config)
        load_checkpoint(ckpt_path, model)
        model.to(device).eval()

        dsplit = _build_device_split(holdout, normalization, group_names, prev_idx, device, pin=False)
        pred = _predict(model, dsplit, group_names, BATCH_SIZE)
        tgt = dsplit.actions.to(pred.device)
        res = _all_strata(pred, tgt, dsplit.wave_band.to(pred.device), dsplit.risk_bin.to(pred.device))
        res["checkpoint_sha256"] = sha
        results[name] = res
        o = res["overall"]
        log(
            f"[sweep:holdout] {name}: median={o['median_angular_error_deg']:.3f}deg "
            f"cos={o['mean_cosine']:.4f} |mag|={o['mean_abs_magnitude_error']:.4f} "
            f"risk[{RISK_MID}]={res['by_risk_stratum'].get(RISK_MID, {}).get('median_angular_error_deg', float('nan')):.3f}"
        )

    holdout_meta = {
        "n": n_holdout,
        "expected_n": EXPECTED_HOLDOUT_N,
        "holdout_frac": DEFAULT_HOLDOUT_FRAC,
        "holdout_seed": DEFAULT_HOLDOUT_SEED,
        "dagger_dataset_dir": str(dagger_dir),
        "dagger_manifest_hash": composite.dagger_manifest_hash,
        "base_manifest_hash": composite.base_manifest_hash,
        "stratum_n": stratum_n,
        "split_reproduction_check": {
            "holdout_aux_damage_base_rate": holdout_damage_rate,
            "registry_holdout_aux_damage_base_rate": float(reg_rates["holdout_aux_damage_base_rate"]),
            "holdout_aux_margin_mean": holdout_margin_mean,
            "registry_holdout_aux_margin_mean": float(reg_rates["holdout_aux_margin_mean"]),
            "reproduces_training_split": len(anomalies) == 0,
        },
    }
    return results, holdout_meta, anomalies


# ---------------------------------------------------------------------------
# §8 dual-distribution gate evaluation (PASS/FAIL per clause)
# ---------------------------------------------------------------------------
def evaluate_gates(
    tv: dict[str, Any], ho: dict[str, Any], models: tuple[str, ...]
) -> dict[str, Any]:
    """Evaluate the §8 dual-distribution gate clauses per model.

    Clauses (ALL must pass to qualify):
      tv_median   : teacher-val overall median <= 6.5 deg
      tv_magerr   : teacher-val mean |magnitude error| <= 0.06
      tv_sat      : teacher-val saturation fraction ~ 0 (no saturation regression)
      ho_median   : holdout overall median <= 30 deg
      ho_cos_pos  : holdout mean cosine > 0 in EVERY risk stratum
      ho_risk_hi  : holdout risk>=0.5 stratum medians <= 35 deg
    """
    out: dict[str, Any] = {}
    for name in models:
        to = tv[name]["overall"]
        tv_median = float(to["median_angular_error_deg"])
        tv_magerr = float(to["mean_abs_magnitude_error"])
        tv_sat = float(to.get("saturation_fraction", 0.0))

        hoall = ho[name]["overall"]
        ho_median = float(hoall["median_angular_error_deg"])
        ho_strata = ho[name]["by_risk_stratum"]

        # cosine > 0 in every populated risk stratum
        cos_by_stratum = {}
        cos_all_pos = True
        for lab in RISK_BIN_LABELS:
            entry = ho_strata.get(lab, {})
            if entry.get("n", 0):
                c = float(entry["mean_cosine"])
                cos_by_stratum[lab] = c
                if not (c > 0.0):
                    cos_all_pos = False
        # risk>=0.5 stratum medians <= 35
        risk_hi_meds = {}
        risk_hi_ok = True
        for lab in RISK_HI_STRATA:
            entry = ho_strata.get(lab, {})
            if entry.get("n", 0):
                m = float(entry["median_angular_error_deg"])
                risk_hi_meds[lab] = m
                if not (m <= GATE_HO_RISK_HI_MEDIAN_MAX):
                    risk_hi_ok = False

        clauses = {
            "tv_median": {"value": tv_median, "threshold": f"<= {GATE_TV_MEDIAN_MAX}", "pass": tv_median <= GATE_TV_MEDIAN_MAX},
            "tv_magerr": {"value": tv_magerr, "threshold": f"<= {GATE_TV_MAGERR_MAX}", "pass": tv_magerr <= GATE_TV_MAGERR_MAX},
            "tv_sat": {"value": tv_sat, "threshold": "~ 0 (no regression)", "pass": tv_sat <= 1e-3},
            "ho_median": {"value": ho_median, "threshold": f"<= {GATE_HO_MEDIAN_MAX}", "pass": ho_median <= GATE_HO_MEDIAN_MAX},
            "ho_cos_pos": {"value": cos_by_stratum, "threshold": "> 0 all strata", "pass": cos_all_pos},
            "ho_risk_hi": {"value": risk_hi_meds, "threshold": f"<= {GATE_HO_RISK_HI_MEDIAN_MAX} (risk>=0.5)", "pass": risk_hi_ok},
        }
        out[name] = {
            "clauses": clauses,
            "qualifies": all(c["pass"] for c in clauses.values()),
        }
    return out


# ---------------------------------------------------------------------------
# Report writers
# ---------------------------------------------------------------------------
def _f(v: Any, spec: str = ".3f") -> str:
    if v is None:
        return "-"
    if isinstance(v, float) and v != v:
        return "nan"
    try:
        return format(float(v), spec)
    except (TypeError, ValueError):
        return str(v)


def _risk_med(strata: dict[str, Any], label: str) -> float:
    entry = strata.get(label, {})
    return float(entry.get("median_angular_error_deg", float("nan"))) if entry.get("n", 0) else float("nan")


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    tv = payload["teacher_val"]
    ho = payload["holdout"]["models"]
    models_list = tuple(payload["models"])
    gates = payload.get("gates", {})
    L: list[str] = []
    L.append(f"# {payload.get('report_title', 'WP2 bc_v2 round-2 sweep -- offline evaluation (frontier)')}")
    L.append("")
    L.append(
        f"Generated {payload['generated']} - device `{payload['device']}` - mag_eps "
        f"{payload['mag_eps']}. Findings only, no promotion recommendation."
    )
    L.append("")
    L.append(
        "Two distributions: (a) teacher-val = frozen `combat_obs_v1` val split "
        f"({tv['bc_v1_s1_full']['overall']['n']} rows) via the unchanged "
        "`bc_offline.evaluate_run` path (each model's own normalization manifest); "
        f"(b) dagger-holdout = the deterministic 10% `combat_dagger_r1` holdout "
        f"(n={payload['holdout']['meta']['n']}, seed {payload['holdout']['meta']['holdout_seed']}), "
        "excluded from all bc_v2 training, label = teacher.action."
    )
    L.append("")
    src = payload["holdout"]["meta"]["split_reproduction_check"]
    L.append(
        f"Split reproduction: holdout aux_damage base rate {_f(src['holdout_aux_damage_base_rate'], '.9f')} "
        f"(registry {_f(src['registry_holdout_aux_damage_base_rate'], '.9f')}), aux_margin mean "
        f"{_f(src['holdout_aux_margin_mean'], '.9f')} (registry {_f(src['registry_holdout_aux_margin_mean'], '.9f')}) "
        f"-> reproduces training split: {src['reproduces_training_split']}."
    )
    L.append("")

    # -- knob provenance -----------------------------------------------------
    L.append("## Sweep configuration")
    L.append("")
    L.append("| variant | corrective mass | prev-action dropout | lambda_mag | note |")
    L.append("|---|---|---|---|---|")
    for name in models_list:
        k = payload["knobs"][name]
        cm = "-" if k["corrective_mass"] is None else _f(k["corrective_mass"], ".2f")
        L.append(f"| {name} | {cm} | {_f(k['prev_action_dropout'], '.1f')} | {_f(k['lambda_mag'], '.1f')} | {k['note']} |")
    L.append("")

    # -- the requested frontier table ---------------------------------------
    L.append("## Frontier table (requested)")
    L.append("")
    L.append(
        "| variant | tv median deg | tv \\|mag err\\| | tv risk 0.50-0.75 median | "
        "holdout median deg | holdout cosine | holdout \\|mag err\\| | holdout risk 0.50-0.75 median |"
    )
    L.append("|---|---|---|---|---|---|---|---|")
    for name in models_list:
        t = tv[name]
        h = ho[name]
        to = t["overall"]
        hoall = h["overall"]
        L.append(
            f"| {name} | {_f(to['median_angular_error_deg'])} | {_f(to['mean_abs_magnitude_error'], '.4f')} "
            f"| {_f(_risk_med(t['by_risk_stratum'], RISK_MID))} "
            f"| {_f(hoall['median_angular_error_deg'])} | {_f(hoall['mean_cosine'], '.4f')} "
            f"| {_f(hoall['mean_abs_magnitude_error'], '.4f')} "
            f"| {_f(_risk_med(h['by_risk_stratum'], RISK_MID))} |"
        )
    L.append("")

    # -- §8 gate-clause table (PASS/FAIL per clause) ------------------------
    if gates:
        L.append("## §8 dual-distribution gates (PASS/FAIL per clause)")
        L.append("")
        L.append(
            "Clauses (ALL must pass): `tv_median` teacher-val median <= 6.5deg; "
            "`tv_magerr` teacher-val mean |mag err| <= 0.06; `tv_sat` no saturation "
            "regression (~0); `ho_median` holdout median <= 30deg; `ho_cos_pos` holdout "
            "cosine > 0 in every risk stratum; `ho_risk_hi` holdout risk>=0.5 medians <= 35deg."
        )
        L.append("")
        L.append(
            "| variant | tv_median | tv_magerr | tv_sat | ho_median | ho_cos_pos | ho_risk_hi | QUALIFIES |"
        )
        L.append("|---|---|---|---|---|---|---|---|")

        def _mark(c: dict[str, Any], spec: str = ".3f") -> str:
            v = c["value"]
            tag = "PASS" if c["pass"] else "FAIL"
            if isinstance(v, dict):
                inner = ", ".join(f"{k}={_f(val, spec)}" for k, val in v.items())
                return f"{inner} [{tag}]"
            return f"{_f(v, spec)} [{tag}]"

        for name in models_list:
            g = gates[name]
            cl = g["clauses"]
            L.append(
                f"| {name} | {_mark(cl['tv_median'])} | {_mark(cl['tv_magerr'], '.4f')} "
                f"| {_mark(cl['tv_sat'], '.4f')} | {_mark(cl['ho_median'])} "
                f"| {_mark(cl['ho_cos_pos'], '.4f')} | {_mark(cl['ho_risk_hi'])} "
                f"| {'**PASS**' if g['qualifies'] else '**FAIL**'} |"
            )
        L.append("")

    # -- teacher-val full overall -------------------------------------------
    L.append("## Teacher-val overall (frozen combat_obs_v1 val split)")
    L.append("")
    L.append("| variant | n | val_loss | median deg | mean deg | cosine | \\|mag err\\| | sat frac |")
    L.append("|---|---|---|---|---|---|---|---|")
    for name in models_list:
        o = tv[name]["overall"]
        L.append(
            f"| {name} | {o.get('n', '-')} | {_f(o.get('val_loss'), '.4f')} "
            f"| {_f(o['median_angular_error_deg'])} | {_f(o['mean_angular_error_deg'])} "
            f"| {_f(o['mean_cosine'], '.4f')} | {_f(o['mean_abs_magnitude_error'], '.4f')} "
            f"| {_f(o['saturation_fraction'], '.4f')} |"
        )
    L.append("")

    # -- holdout full overall -----------------------------------------------
    L.append("## Dagger-holdout overall (student-visited distribution)")
    L.append("")
    L.append("| variant | n | median deg | mean deg | cosine | \\|mag err\\| |")
    L.append("|---|---|---|---|---|---|")
    for name in models_list:
        o = ho[name]["overall"]
        L.append(
            f"| {name} | {o.get('n', '-')} | {_f(o['median_angular_error_deg'])} "
            f"| {_f(o['mean_angular_error_deg'])} | {_f(o['mean_cosine'], '.4f')} "
            f"| {_f(o['mean_abs_magnitude_error'], '.4f')} |"
        )
    L.append("")

    # -- risk strata (both distributions, median deg) -----------------------
    for dist_label, block in (("Teacher-val", tv), ("Dagger-holdout", ho)):
        L.append(f"## {dist_label} by risk stratum (median deg)")
        L.append("")
        header = "| variant | " + " | ".join(RISK_BIN_LABELS) + " |"
        L.append(header)
        L.append("|---|" + "---|" * len(RISK_BIN_LABELS))
        for name in models_list:
            strata = block[name]["by_risk_stratum"]
            cells = " | ".join(_f(_risk_med(strata, lab)) for lab in RISK_BIN_LABELS)
            L.append(f"| {name} | {cells} |")
        L.append("")

    # -- wave bands (both distributions, median deg) ------------------------
    for dist_label, block in (("Teacher-val", tv), ("Dagger-holdout", ho)):
        L.append(f"## {dist_label} by wave band (median deg)")
        L.append("")
        header = "| variant | " + " | ".join(WAVE_BAND_LABELS) + " |"
        L.append(header)
        L.append("|---|" + "---|" * len(WAVE_BAND_LABELS))
        for name in models_list:
            bands = block[name]["by_wave_band"]
            cells = " | ".join(_f(_risk_med(bands, lab)) for lab in WAVE_BAND_LABELS)
            L.append(f"| {name} | {cells} |")
        L.append("")

    # -- wall times ----------------------------------------------------------
    L.append("## Training wall times (from registries)")
    L.append("")
    L.append("| variant | epochs_run | best_epoch | wall_time_sec |")
    L.append("|---|---|---|---|")
    for name in models_list:
        w = payload["train_wall"][name]
        L.append(f"| {name} | {w.get('epochs_run', '-')} | {w.get('best_epoch', '-')} | {_f(w.get('wall_time_sec'), '.1f')} |")
    L.append("")

    if payload["anomalies"]:
        L.append("## Anomalies")
        L.append("")
        for a in payload["anomalies"]:
            L.append(f"- {a}")
        L.append("")
    else:
        L.append("No anomalies.")
        L.append("")

    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def _parse_args(argv: list[str] | None) -> Any:
    import argparse

    p = argparse.ArgumentParser(description="WP2 bc_v2 sweep offline evaluation (dual-distribution + §8 gates).")
    p.add_argument(
        "--models",
        default=None,
        help="comma-separated variant names to evaluate (default: the round-1 sweep set).",
    )
    p.add_argument(
        "--report-stem",
        default="bc_v2_sweep_report",
        help="output stem under reports/wp2 (default bc_v2_sweep_report).",
    )
    p.add_argument(
        "--report-title",
        default=None,
        help="markdown H1 title (default depends on the report stem).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.models:
        models = tuple(m.strip() for m in args.models.split(",") if m.strip())
    else:
        models = MODELS
    report_title = args.report_title or (
        "WP2 bc_v2 round-2 sweep -- offline evaluation (frontier)"
        if args.report_stem == "bc_v2_sweep_report"
        else "WP2 bc_v2 round-2b -- curriculum vs joint-low-mass (dual-distribution + §8 gates)"
    )

    t0 = time.time()
    device = resolve_device("auto")
    log(f"[sweep] device={device} models={list(models)}")

    log("[sweep] === (a) teacher-val via bc_offline.evaluate_run ===")
    tv = teacher_val_eval("auto", models)

    log("[sweep] === (b) dagger-holdout via wp2_dagger_holdout_eval pathway ===")
    ho_models, ho_meta, anomalies = holdout_eval(device, models)

    log("[sweep] === §8 gate evaluation ===")
    gates = evaluate_gates(tv, ho_models, models)
    for name in models:
        g = gates[name]
        fails = [c for c, v in g["clauses"].items() if not v["pass"]]
        log(f"[sweep:gate] {name}: qualifies={g['qualifies']} " + (f"(FAIL: {', '.join(fails)})" if fails else "(all clauses pass)"))

    # Training wall times from the registries (for the report).
    train_wall: dict[str, Any] = {}
    for name in models:
        reg = load_registry(REGISTRY_DIR / f"{name}.json")
        train_wall[name] = {
            "epochs_run": reg.get("epochs_run"),
            "best_epoch": reg.get("best_epoch"),
            "wall_time_sec": reg.get("wall_time_sec"),
            "init_checkpoint": reg.get("init_checkpoint"),
        }

    payload = {
        "report": "wp2_bc_v2_sweep_eval",
        "report_title": report_title,
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "device": str(device),
        "mag_eps": MAG_EPS,
        "models": list(models),
        "knobs": {name: KNOBS[name] for name in models if name in KNOBS},
        "teacher_val": tv,
        "holdout": {"meta": ho_meta, "models": ho_models},
        "gates": gates,
        "train_wall": train_wall,
        "anomalies": anomalies,
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS_DIR / f"{args.report_stem}.json"
    md_path = REPORTS_DIR / f"{args.report_stem}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(md_path, payload)
    log(f"[sweep] wrote {json_path}")
    log(f"[sweep] wrote {md_path}")
    if anomalies:
        log("[sweep] ANOMALIES:")
        for a in anomalies:
            log(f"  - {a}")
    else:
        log("[sweep] no anomalies")
    log(f"[sweep] done in {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
