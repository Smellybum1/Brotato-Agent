"""WP2 bc_v3 aggregate offline evaluation (round-2 DAgger: r1 + r2 corrective).

Evaluates the four models {bc_v1_s1_full, bc_v2_f_s1, bc_v3_a_s1, bc_v3_b_s1} on
THREE distributions, reusing the two unchanged eval pathways verbatim (no new
metric maths):

  (i)   teacher-val   -- frozen combat_obs_v1 val split via the unchanged
        ``bc_offline.evaluate_run`` path (independent reload; checkpoint sha256 +
        normalization-manifest hash verified; each model uses its OWN manifest).
  (ii)  r1 holdout     -- the deterministic 10% combat_dagger_r1 holdout
        (7,887 rows, seed 20260724), reproduced by ``load_composite_dataset``.
  (iii) r2 holdout     -- the deterministic 10% combat_dagger_r2 holdout
        (11,627 rows, seed 20260724), reproduced by ``load_composite_dataset``.

The r2 holdout is UNBIASED for all four models: bc_v1 and bc_v2_f never trained
on any r2 row (r2 was collected under the bc_v2_f student), and both bc_v3
candidates exclude the r2 holdout from training. It is therefore the primary
deployment-distribution comparison. Label on both holdouts = teacher.action.

Applies the design §8 REVISED gates (.tmp/wp2_m4_dagger_design.md §8, Decision 1a)
to bc_v3_a and bc_v3_b, with the deployment clauses evaluated on the R2 HOLDOUT
(per §8: fresh-run holdout under the candidate's predecessor bc_v2_f). Reports
copy_previous on the r2 holdout as the anti-copy-through baseline.

Findings only -- no promotion recommendation. Writes
``reports/wp2/bc_v3_eval.{json,md}``.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

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
from scripts.wp2_dagger_holdout_eval import _all_strata, _predict  # noqa: E402

REGISTRY_DIR = REPO_ROOT / "models" / "registry"
REPORTS_DIR = REPO_ROOT / "reports" / "wp2"

R1_DIR = REPO_ROOT / "datasets" / "combat_dagger_r1"
R2_DIR = REPO_ROOT / "datasets" / "combat_dagger_r2"
EXPECTED_R1_HOLDOUT_N = 7887
EXPECTED_R2_HOLDOUT_N = 11627

MODELS: tuple[str, ...] = ("bc_v1_s1_full", "bc_v2_f_s1", "bc_v3_a_s1", "bc_v3_b_s1")
GATE_MODELS: tuple[str, ...] = ("bc_v3_a_s1", "bc_v3_b_s1")

# §8 REVISED (Decision 1a) gate thresholds. Deployment clauses on the R2 holdout.
GATE_TV_MEDIAN_MAX = 9.0
GATE_TV_MAGERR_MAX = 0.09
GATE_HO_MEDIAN_MAX = 30.0
GATE_HO_RISK_MID_MEDIAN_MAX = 35.0   # risk 0.50-0.75
GATE_HO_RISK_HI_MEDIAN_MAX = 45.0    # risk 0.75-inf
GATE_ANTICOPY_MEDIAN_MAX = 37.3      # vs copy_previous 74.6 (>= 2x better)
RISK_MID = "0.50-0.75"
RISK_HI = "0.75-inf"

MAG_EPS = 0.01
BATCH_SIZE = 4096


def log(msg: str) -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# (i) teacher-val via the unchanged bc_offline path
# ---------------------------------------------------------------------------
def teacher_val_eval(device: str, models: tuple[str, ...]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in models:
        run_eval = evaluate_run(REGISTRY_DIR / f"{name}.json", checkpoint="best", device=device)
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
            f"[bc_v3:tv] {name}: median={o['median_angular_error_deg']:.3f}deg "
            f"mean={o['mean_angular_error_deg']:.3f}deg |mag|={o['mean_abs_magnitude_error']:.4f} "
            f"sat={o.get('saturation_fraction', 0.0):.5f}"
        )
    return out


# ---------------------------------------------------------------------------
# (ii)/(iii) holdout eval on a given corrective dir (r1 or r2)
# ---------------------------------------------------------------------------
def holdout_eval(
    device: torch.device,
    dagger_dir: Path,
    tag: str,
    expected_n: int,
    models: tuple[str, ...],
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    anomalies: list[str] = []

    rc = load_registry(REGISTRY_DIR / "bc_v2_a_s1.json")["resolved_config"]
    log(
        f"[bc_v3:{tag}] loading composite dataset for holdout "
        f"(dir={dagger_dir.name}, frac={DEFAULT_HOLDOUT_FRAC}, seed={DEFAULT_HOLDOUT_SEED})"
    )
    composite = load_composite_dataset(
        rc["dataset_dir"], dagger_dir, rc["split_config"], rc["input_config"], rc["schema"]
    )
    holdout = composite.aux_holdout
    n_holdout = holdout.size
    if n_holdout != expected_n:
        anomalies.append(f"{tag} holdout row count {n_holdout} != expected {expected_n}")

    feature_names = list(composite.global_feature_names)
    ref_policy_cfg = build_policy_config_from_registry(rc, feature_names)
    group_names = tuple(spec.name for spec in ref_policy_cfg.group_specs)
    prev_idx = ref_policy_cfg.prev_action_indices

    # Reference split (bc_v1 manifest) for strata bins + label target + copy_previous
    # baseline. prev_action / risk_bin / wave_band are normalization-independent.
    bc_v1_registry = load_registry(REGISTRY_DIR / "bc_v1_s1_full.json")
    bc_v1_ckpt = Path(bc_v1_registry["checkpoints"]["best"]["path"])
    bc_v1_norm = load_normalization_from_manifest(
        bc_v1_ckpt.parent / "normalization_manifest.json",
        bc_v1_registry["normalization_manifest_hash"], feature_names,
    )
    ref_split = _build_device_split(holdout, bc_v1_norm, group_names, prev_idx, device, pin=False)
    wave_band = ref_split.wave_band.to(device)
    risk_bin = ref_split.risk_bin.to(device)
    target = ref_split.actions.to(device)

    stratum_n = {
        "overall": int(target.shape[0]),
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
            f"[bc_v3:{tag}] {name}: median={o['median_angular_error_deg']:.3f}deg "
            f"cos={o['mean_cosine']:.4f} |mag|={o['mean_abs_magnitude_error']:.4f} "
            f"risk[{RISK_MID}]={res['by_risk_stratum'].get(RISK_MID, {}).get('median_angular_error_deg', float('nan')):.3f} "
            f"risk[{RISK_HI}]={res['by_risk_stratum'].get(RISK_HI, {}).get('median_angular_error_deg', float('nan')):.3f}"
        )

    # copy_previous baseline on the identical holdout rows.
    prev_pred = ref_split.prev_action.to(device)
    cp_res = _all_strata(prev_pred, target, wave_band, risk_bin)
    log(
        f"[bc_v3:{tag}] copy_previous: median={cp_res['overall']['median_angular_error_deg']:.3f}deg "
        f"mean={cp_res['overall']['mean_angular_error_deg']:.3f}deg"
    )

    meta = {
        "tag": tag,
        "dagger_dataset_dir": str(dagger_dir),
        "n": n_holdout,
        "expected_n": expected_n,
        "holdout_frac": DEFAULT_HOLDOUT_FRAC,
        "holdout_seed": DEFAULT_HOLDOUT_SEED,
        "dagger_manifest_hash": composite.dagger_manifest_hash,
        "base_manifest_hash": composite.base_manifest_hash,
        "stratum_n": stratum_n,
    }
    return {"models": results, "copy_previous": cp_res}, meta, anomalies


# ---------------------------------------------------------------------------
# §8 REVISED gate evaluation (deployment clauses on the R2 holdout)
# ---------------------------------------------------------------------------
def evaluate_gates(
    tv: dict[str, Any],
    r2: dict[str, Any],
    models: tuple[str, ...],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    r2_models = r2["models"]
    for name in models:
        to = tv[name]["overall"]
        tv_median = float(to["median_angular_error_deg"])
        tv_magerr = float(to["mean_abs_magnitude_error"])
        tv_sat = float(to.get("saturation_fraction", 0.0))

        hoall = r2_models[name]["overall"]
        ho_median = float(hoall["median_angular_error_deg"])
        ho_strata = r2_models[name]["by_risk_stratum"]

        cos_by_stratum: dict[str, float] = {}
        cos_all_pos = True
        for lab in RISK_BIN_LABELS:
            entry = ho_strata.get(lab, {})
            if entry.get("n", 0):
                c = float(entry["mean_cosine"])
                cos_by_stratum[lab] = c
                if not (c > 0.0):
                    cos_all_pos = False

        mid_entry = ho_strata.get(RISK_MID, {})
        risk_mid_med = float(mid_entry["median_angular_error_deg"]) if mid_entry.get("n", 0) else float("nan")
        hi_entry = ho_strata.get(RISK_HI, {})
        risk_hi_med = float(hi_entry["median_angular_error_deg"]) if hi_entry.get("n", 0) else float("nan")

        clauses = {
            "tv_median": {"value": tv_median, "threshold": f"<= {GATE_TV_MEDIAN_MAX}",
                          "pass": tv_median <= GATE_TV_MEDIAN_MAX},
            "tv_magerr": {"value": tv_magerr, "threshold": f"<= {GATE_TV_MAGERR_MAX}",
                          "pass": tv_magerr <= GATE_TV_MAGERR_MAX},
            "tv_sat": {"value": tv_sat, "threshold": "~ 0 (no regression)", "pass": tv_sat <= 1e-3},
            "ho_median_r2": {"value": ho_median, "threshold": f"<= {GATE_HO_MEDIAN_MAX}",
                             "pass": ho_median <= GATE_HO_MEDIAN_MAX},
            "ho_cos_pos_r2": {"value": cos_by_stratum, "threshold": "> 0 all risk strata",
                              "pass": cos_all_pos},
            "ho_risk_mid_r2": {"value": risk_mid_med, "threshold": f"<= {GATE_HO_RISK_MID_MEDIAN_MAX} (risk 0.50-0.75)",
                               "pass": (risk_mid_med <= GATE_HO_RISK_MID_MEDIAN_MAX) if risk_mid_med == risk_mid_med else False},
            "ho_risk_hi_r2": {"value": risk_hi_med, "threshold": f"<= {GATE_HO_RISK_HI_MEDIAN_MAX} (risk 0.75+)",
                              "pass": (risk_hi_med <= GATE_HO_RISK_HI_MEDIAN_MAX) if risk_hi_med == risk_hi_med else False},
            "anti_copy_r2": {"value": ho_median, "threshold": f"<= {GATE_ANTICOPY_MEDIAN_MAX} (2x copy_previous)",
                             "pass": ho_median <= GATE_ANTICOPY_MEDIAN_MAX},
        }
        out[name] = {"clauses": clauses, "qualifies": all(c["pass"] for c in clauses.values())}
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


def _med(strata: dict[str, Any], label: str) -> float:
    entry = strata.get(label, {})
    return float(entry.get("median_angular_error_deg", float("nan"))) if entry.get("n", 0) else float("nan")


def _cos(strata: dict[str, Any], label: str) -> float:
    entry = strata.get(label, {})
    return float(entry.get("mean_cosine", float("nan"))) if entry.get("n", 0) else float("nan")


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    tv = payload["teacher_val"]
    r1 = payload["r1_holdout"]
    r2 = payload["r2_holdout"]
    models = tuple(payload["models"])
    gates = payload["gates"]
    L: list[str] = []
    L.append("# WP2 bc_v3 aggregate offline evaluation (r1 + r2 corrective)")
    L.append("")
    L.append(
        f"Generated {payload['generated']} - device `{payload['device']}` - mag_eps "
        f"{payload['mag_eps']}. Findings only, no promotion recommendation."
    )
    L.append("")
    L.append(
        "Three distributions: (i) teacher-val = frozen `combat_obs_v1` val split via the "
        "unchanged `bc_offline.evaluate_run` path (each model's own normalization manifest); "
        f"(ii) r1 holdout = deterministic 10% `combat_dagger_r1` (n={r1['meta']['n']}); "
        f"(iii) r2 holdout = deterministic 10% `combat_dagger_r2` (n={r2['meta']['n']}, "
        f"seed {r2['meta']['holdout_seed']}). Label on both holdouts = teacher.action."
    )
    L.append("")
    L.append(
        "**The R2 holdout is the primary deployment-distribution comparison and is unbiased "
        "for ALL FOUR models**: bc_v1_s1_full and bc_v2_f_s1 never trained on any r2 row (r2 was "
        "collected under the bc_v2_f student), and both bc_v3 candidates exclude the r2 holdout "
        "from training."
    )
    L.append("")

    # -- 4-model x 3-distribution summary -----------------------------------
    L.append("## Summary: 4 models x 3 distributions (median / cosine / |mag err|)")
    L.append("")
    L.append(
        "| model | tv median | tv cos | tv |mag| | r1 median | r1 cos | r1 |mag| | "
        "r2 median | r2 cos | r2 |mag| |"
    )
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for name in models:
        t = tv[name]["overall"]
        h1 = r1["models"][name]["overall"]
        h2 = r2["models"][name]["overall"]
        L.append(
            f"| {name} | {_f(t['median_angular_error_deg'])} | {_f(t['mean_cosine'], '.4f')} "
            f"| {_f(t['mean_abs_magnitude_error'], '.4f')} "
            f"| {_f(h1['median_angular_error_deg'])} | {_f(h1['mean_cosine'], '.4f')} "
            f"| {_f(h1['mean_abs_magnitude_error'], '.4f')} "
            f"| {_f(h2['median_angular_error_deg'])} | {_f(h2['mean_cosine'], '.4f')} "
            f"| {_f(h2['mean_abs_magnitude_error'], '.4f')} |"
        )
    # copy_previous baselines on the two holdouts
    cp1 = r1["copy_previous"]["overall"]
    cp2 = r2["copy_previous"]["overall"]
    L.append(
        f"| copy_previous (baseline) | - | - | - "
        f"| {_f(cp1['median_angular_error_deg'])} | {_f(cp1['mean_cosine'], '.4f')} "
        f"| {_f(cp1['mean_abs_magnitude_error'], '.4f')} "
        f"| {_f(cp2['median_angular_error_deg'])} | {_f(cp2['mean_cosine'], '.4f')} "
        f"| {_f(cp2['mean_abs_magnitude_error'], '.4f')} |"
    )
    L.append("")

    # -- §8 gates (bc_v3 candidates only) -----------------------------------
    L.append("## §8 REVISED gates (deployment clauses on R2 holdout) -- PASS/FAIL per clause")
    L.append("")
    L.append(
        "Clauses (ALL must pass): `tv_median` <= 9.0deg; `tv_magerr` <= 0.09; `tv_sat` no "
        "saturation regression (~0); `ho_median_r2` <= 30deg; `ho_cos_pos_r2` cosine > 0 in "
        "every risk stratum; `ho_risk_mid_r2` risk 0.50-0.75 median <= 35deg; `ho_risk_hi_r2` "
        "risk 0.75+ median <= 45deg; `anti_copy_r2` r2 median <= 37.3deg (>= 2x better than "
        f"copy_previous {_f(cp2['median_angular_error_deg'])}deg)."
    )
    L.append("")
    L.append(
        "| model | tv_median | tv_magerr | tv_sat | ho_median_r2 | ho_cos_pos_r2 | "
        "ho_risk_mid_r2 | ho_risk_hi_r2 | anti_copy_r2 | QUALIFIES |"
    )
    L.append("|---|---|---|---|---|---|---|---|---|---|")

    def _mark(c: dict[str, Any], spec: str = ".3f") -> str:
        v = c["value"]
        tag = "PASS" if c["pass"] else "FAIL"
        if isinstance(v, dict):
            inner = ", ".join(f"{k}={_f(val, spec)}" for k, val in v.items())
            return f"{inner} [{tag}]"
        return f"{_f(v, spec)} [{tag}]"

    for name in GATE_MODELS:
        g = gates[name]
        cl = g["clauses"]
        L.append(
            f"| {name} | {_mark(cl['tv_median'])} | {_mark(cl['tv_magerr'], '.4f')} "
            f"| {_mark(cl['tv_sat'], '.5f')} | {_mark(cl['ho_median_r2'])} "
            f"| {_mark(cl['ho_cos_pos_r2'], '.4f')} | {_mark(cl['ho_risk_mid_r2'])} "
            f"| {_mark(cl['ho_risk_hi_r2'])} | {_mark(cl['anti_copy_r2'])} "
            f"| {'**PASS**' if g['qualifies'] else '**FAIL**'} |"
        )
    L.append("")

    # -- stratified tables (median deg) per distribution --------------------
    dists = (
        ("Teacher-val", {n: tv[n] for n in models}, None),
        ("R1 holdout", r1["models"], r1["copy_previous"]),
        ("R2 holdout", r2["models"], r2["copy_previous"]),
    )
    for dist_label, block, cp in dists:
        L.append(f"## {dist_label} -- by risk stratum (median deg / cosine)")
        L.append("")
        hdr = "| model | " + " | ".join(f"{lab} med" for lab in RISK_BIN_LABELS) + " | " + \
              " | ".join(f"{lab} cos" for lab in RISK_BIN_LABELS) + " |"
        L.append(hdr)
        L.append("|---|" + "---|" * (2 * len(RISK_BIN_LABELS)))
        rows = list(models)
        for name in rows:
            strata = block[name]["by_risk_stratum"]
            meds = " | ".join(_f(_med(strata, lab)) for lab in RISK_BIN_LABELS)
            coss = " | ".join(_f(_cos(strata, lab), ".4f") for lab in RISK_BIN_LABELS)
            L.append(f"| {name} | {meds} | {coss} |")
        if cp is not None:
            strata = cp["by_risk_stratum"]
            meds = " | ".join(_f(_med(strata, lab)) for lab in RISK_BIN_LABELS)
            coss = " | ".join(_f(_cos(strata, lab), ".4f") for lab in RISK_BIN_LABELS)
            L.append(f"| copy_previous | {meds} | {coss} |")
        L.append("")

    for dist_label, block, cp in dists:
        L.append(f"## {dist_label} -- by wave band (median deg)")
        L.append("")
        hdr = "| model | " + " | ".join(WAVE_BAND_LABELS) + " |"
        L.append(hdr)
        L.append("|---|" + "---|" * len(WAVE_BAND_LABELS))
        for name in models:
            bands = block[name]["by_wave_band"]
            cells = " | ".join(_f(_med(bands, lab)) for lab in WAVE_BAND_LABELS)
            L.append(f"| {name} | {cells} |")
        if cp is not None:
            bands = cp["by_wave_band"]
            cells = " | ".join(_f(_med(bands, lab)) for lab in WAVE_BAND_LABELS)
            L.append(f"| copy_previous | {cells} |")
        L.append("")

    # -- stratum n -----------------------------------------------------------
    L.append("## Holdout stratum counts")
    L.append("")
    L.append("| stratum | r1 n | r2 n |")
    L.append("|---|---|---|")
    L.append(f"| overall | {r1['meta']['stratum_n']['overall']} | {r2['meta']['stratum_n']['overall']} |")
    for lab in RISK_BIN_LABELS:
        L.append(
            f"| risk {lab} | {r1['meta']['stratum_n']['by_risk_stratum'][lab]} "
            f"| {r2['meta']['stratum_n']['by_risk_stratum'][lab]} |"
        )
    L.append("")

    # -- wall times ----------------------------------------------------------
    L.append("## Training wall times (from registries)")
    L.append("")
    L.append("| model | epochs_run | best_epoch | wall_time_sec |")
    L.append("|---|---|---|---|")
    for name in models:
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


def main(argv: list[str] | None = None) -> int:
    t0 = time.time()
    device = resolve_device("auto")
    log(f"[bc_v3] device={device} models={list(MODELS)}")

    log("[bc_v3] === (i) teacher-val via bc_offline.evaluate_run ===")
    tv = teacher_val_eval("auto", MODELS)

    log("[bc_v3] === (ii) r1 holdout ===")
    r1_res, r1_meta, r1_anom = holdout_eval(device, R1_DIR, "r1", EXPECTED_R1_HOLDOUT_N, MODELS)

    log("[bc_v3] === (iii) r2 holdout (primary deployment distribution) ===")
    r2_res, r2_meta, r2_anom = holdout_eval(device, R2_DIR, "r2", EXPECTED_R2_HOLDOUT_N, MODELS)

    log("[bc_v3] === §8 REVISED gates (deployment on R2 holdout) ===")
    gates = evaluate_gates(tv, r2_res, MODELS)
    for name in GATE_MODELS:
        g = gates[name]
        fails = [c for c, v in g["clauses"].items() if not v["pass"]]
        log(f"[bc_v3:gate] {name}: qualifies={g['qualifies']} " + (f"(FAIL: {', '.join(fails)})" if fails else "(all clauses pass)"))

    train_wall: dict[str, Any] = {}
    for name in MODELS:
        reg = load_registry(REGISTRY_DIR / f"{name}.json")
        train_wall[name] = {
            "epochs_run": reg.get("epochs_run"),
            "best_epoch": reg.get("best_epoch"),
            "wall_time_sec": reg.get("wall_time_sec"),
        }

    anomalies = r1_anom + r2_anom
    payload = {
        "report": "wp2_bc_v3_eval",
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "device": str(device),
        "mag_eps": MAG_EPS,
        "models": list(MODELS),
        "gate_models": list(GATE_MODELS),
        "teacher_val": tv,
        "r1_holdout": {"meta": r1_meta, "models": r1_res["models"], "copy_previous": r1_res["copy_previous"]},
        "r2_holdout": {"meta": r2_meta, "models": r2_res["models"], "copy_previous": r2_res["copy_previous"]},
        "gates": gates,
        "gate_thresholds": {
            "tv_median_max": GATE_TV_MEDIAN_MAX,
            "tv_magerr_max": GATE_TV_MAGERR_MAX,
            "ho_median_max": GATE_HO_MEDIAN_MAX,
            "ho_risk_mid_median_max": GATE_HO_RISK_MID_MEDIAN_MAX,
            "ho_risk_hi_median_max": GATE_HO_RISK_HI_MEDIAN_MAX,
            "anticopy_median_max": GATE_ANTICOPY_MEDIAN_MAX,
        },
        "train_wall": train_wall,
        "anomalies": anomalies,
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS_DIR / "bc_v3_eval.json"
    md_path = REPORTS_DIR / "bc_v3_eval.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(md_path, payload)
    log(f"[bc_v3] wrote {json_path}")
    log(f"[bc_v3] wrote {md_path}")
    if anomalies:
        log("[bc_v3] ANOMALIES:")
        for a in anomalies:
            log(f"  - {a}")
    else:
        log("[bc_v3] no anomalies")
    log(f"[bc_v3] done in {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
