"""WP2 Stage G — ONNX vs PyTorch parity harness (packet §14.1).

Feeds >= 10,000 batch-1 input-tensor fixtures identically to the PyTorch model
(CPU, 1 thread) and the exported ONNX graph (ONNX Runtime, CPU, intra_op 1) and
compares the 2-D ``action`` output. Fixtures are drawn WITHOUT training-split
contamination — only from the frozen validation split — in four categories:

  (a) stratified real rows (by wave band x risk bin);
  (b) empty-group rows (each group's mask+entities zeroed one-at-a-time and
      all-at-once);
  (c) capacity-overflow rows (every mask forced all-ones);
  (d) edge-normalization rows (standardized globals at +/-6 sigma and entity
      features at their per-feature validation-pool bounds).

Categories (b)-(d) are synthetic INPUT-tensor fixtures fed identically to both
backends (they intentionally bypass ``encode_capture`` — parity is a property of
the model function, not the encoder).

Gates: zero NaN/Inf from either backend on every fixture; max |Δaction| over all
fixtures <= 1e-4. Mean and p99 |Δ| are reported. The fixture recipe (seed,
per-category counts, stratum allocation, base-row indices, per-category max diff)
is recorded in the JSON report, and the report's parity block is written back
into the ONNX registry manifest.

Exit codes: 0 all gates pass · 1 a gate failed · 2 setup/artifact error.

Usage:
    .venv/Scripts/python.exe scripts/wp2_onnx_parity.py
    .venv/Scripts/python.exe scripts/wp2_onnx_parity.py --smoke
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_REGISTRY = REPO_ROOT / "models" / "registry" / "bc_v1_s1_full.json"
DEFAULT_ONNX_REGISTRY = REPO_ROOT / "models" / "registry" / "bc_v1_s1_full_onnx.json"

REPORT_JSON = REPO_ROOT / "reports" / "wp2" / "onnx_parity_v1.json"
REPORT_MD = REPO_ROOT / "reports" / "wp2" / "onnx_parity_v1.md"
DEFAULT_LATENCY_JSON = REPO_ROOT / "reports" / "wp2" / "student_latency_bench_onnx_v1.json"

MAX_ABS_DIFF_GATE = 1e-4
SEED = 20260724
GLOBAL_EDGE_SIGMA = 6.0

# Full-run fixture composition (>= 10,000 total).
FULL_COUNTS = {"stratified": 8000, "empty_group": 1000, "capacity_overflow": 500, "edge_norm": 500}
# Smoke fixture composition (quick correctness check, not a qualifying run).
SMOKE_COUNTS = {"stratified": 400, "empty_group": 120, "capacity_overflow": 40, "edge_norm": 40}


class OnnxParitySetupError(RuntimeError):
    """Raised on any artifact / data / session setup failure (exit code 2)."""


# ---------------------------------------------------------------------------
# Artifact loading
# ---------------------------------------------------------------------------
def _load_torch_service(registry: Path):
    from trainer.bridge.sidecar import SidecarStartupError, TorchModelService

    try:
        return TorchModelService.from_registry(registry, checkpoint="best")
    except SidecarStartupError as exc:
        raise OnnxParitySetupError(f"torch artifact chain failed to load/verify: {exc}") from exc


def _load_onnx_session(onnx_registry: Path):
    """Load + sha-verify the ONNX graph and build a 1-thread CPU ORT session."""
    import onnxruntime as ort

    from trainer.imitation.bc_training import _sha256_file

    try:
        manifest = json.loads(onnx_registry.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise OnnxParitySetupError(f"onnx registry unreadable: {exc}") from exc

    onnx_path = Path(manifest["onnx_path"])
    if not onnx_path.is_file():
        raise OnnxParitySetupError(f"onnx file missing: {onnx_path}")
    onnx_sha = _sha256_file(onnx_path)
    if onnx_sha != str(manifest["onnx_sha256"]).upper():
        raise OnnxParitySetupError(
            f"onnx sha256 mismatch: file {onnx_sha} != manifest {manifest['onnx_sha256']}"
        )

    so = ort.SessionOptions()
    so.intra_op_num_threads = 1
    so.inter_op_num_threads = 1
    try:
        session = ort.InferenceSession(
            str(onnx_path), sess_options=so, providers=["CPUExecutionProvider"]
        )
    except Exception as exc:
        raise OnnxParitySetupError(f"onnxruntime could not load {onnx_path}: {exc}") from exc

    input_names = [str(n) for n in manifest["input_names"]]
    output_name = str(manifest["output_name"])
    return session, manifest, input_names, output_name, onnx_sha


def _load_validation_split(registry: Path):
    """Load the frozen validation split (no training rows) with standardized globals.

    Globals are standardized with the run's train-only normalization (identical
    to what the model expects); entity/mask tensors pass through unnormalized.
    """
    import numpy as np

    from trainer.data.bc_dataset import load_bc_dataset
    from trainer.evaluation.bc_offline import load_registry

    parent_registry = load_registry(registry)
    resolved = parent_registry["resolved_config"]
    dataset = load_bc_dataset(
        resolved["dataset_dir"], resolved["split_config"],
        resolved["input_config"], resolved["schema"],
    )
    val = dataset.val
    std_globals = dataset.normalization.apply(val.globals).astype(np.float32)
    return val, std_globals


# ---------------------------------------------------------------------------
# Fixture construction (validation split only; deterministic)
# ---------------------------------------------------------------------------
def _entity_bounds(val, group_names):
    """Per-feature (lo, hi) over present entity rows across all groups -> [15],[15]."""
    import numpy as np

    feat_dim = val.entities[group_names[0]].shape[2]
    lo = np.full(feat_dim, np.inf, dtype=np.float64)
    hi = np.full(feat_dim, -np.inf, dtype=np.float64)
    for name in group_names:
        ent = val.entities[name]  # [N, cap, F]
        mask = val.masks[name] > 0  # [N, cap]
        if not mask.any():
            continue
        present = ent[mask]  # [P, F]
        lo = np.minimum(lo, present.min(axis=0))
        hi = np.maximum(hi, present.max(axis=0))
    lo = np.where(np.isfinite(lo), lo, 0.0).astype(np.float32)
    hi = np.where(np.isfinite(hi), hi, 0.0).astype(np.float32)
    return lo, hi


def _row_fixture(val, std_globals, group_names, i):
    """Materialize one real validation row as a fixture dict of float32 arrays."""
    import numpy as np

    fx: dict[str, np.ndarray] = {"globals": np.array(std_globals[i], dtype=np.float32)}
    for name in group_names:
        fx[f"ent_{name}"] = np.array(val.entities[name][i], dtype=np.float32)
        fx[f"mask_{name}"] = np.array(val.masks[name][i], dtype=np.float32)
    return fx


def build_fixtures(val, std_globals, group_names, counts, *, log=print):
    """Build the deterministic fixture set. Returns (fixtures, recipe).

    ``fixtures`` is a list of ``(category, fixture_dict)``. ``recipe`` records the
    seed, per-category counts, stratum allocation, and base-row indices so the
    exact set is reproducible.
    """
    import numpy as np

    from trainer.imitation.bc_training import (
        compute_risk_stratum,
        risk_bin_indices,
        wave_band_indices,
    )

    rng = np.random.default_rng(SEED)
    n = int(val.globals.shape[0])
    fixtures: list[tuple[str, dict]] = []
    recipe: dict[str, Any] = {"seed": SEED, "n_val_rows": n, "counts": {}}

    # -- (a) stratified by wave band x risk bin -----------------------------
    wave_band = wave_band_indices(val.wave)
    risk = compute_risk_stratum(val.entities, val.masks)
    risk_bin = risk_bin_indices(risk)
    strata_key = wave_band.astype(np.int64) * 100 + risk_bin.astype(np.int64)
    uniq = np.unique(strata_key)
    want_a = counts["stratified"]
    alloc: dict[str, int] = {}
    picked_a: list[int] = []
    # Proportional allocation, largest-remainder rounded to hit want_a exactly.
    sizes = {int(k): int((strata_key == k).sum()) for k in uniq}
    raw = {k: want_a * s / n for k, s in sizes.items()}
    floor = {k: int(math.floor(v)) for k, v in raw.items()}
    remainder = want_a - sum(floor.values())
    order = sorted(raw, key=lambda k: raw[k] - floor[k], reverse=True)
    for k in order[:remainder]:
        floor[k] += 1
    for k in sorted(sizes):
        take = min(floor[k], sizes[k])
        idx = np.nonzero(strata_key == k)[0]
        chosen = rng.choice(idx, size=take, replace=False) if take > 0 else np.array([], dtype=np.intp)
        picked_a.extend(int(x) for x in chosen)
        wb, rb = divmod(k, 100)
        alloc[f"wb{wb}_rb{rb}"] = int(take)
    for i in picked_a:
        fixtures.append(("stratified", _row_fixture(val, std_globals, group_names, i)))
    recipe["stratified_allocation"] = alloc
    recipe["stratified_indices_sha256"] = hashlib.sha256(
        np.asarray(sorted(picked_a), dtype=np.int64).tobytes()
    ).hexdigest().upper()

    # -- (b) empty-group: zero each group one-at-a-time + all-at-once -------
    want_b = counts["empty_group"]
    variants = len(group_names) + 1  # per group + all
    n_base_b = max(1, want_b // variants)
    base_b = rng.choice(n, size=min(n_base_b, n), replace=False)
    made_b = 0
    for i in base_b:
        base = _row_fixture(val, std_globals, group_names, int(i))
        for gi, gname in enumerate(group_names):
            if made_b >= want_b:
                break
            fx = {k: np.array(v, dtype=np.float32) for k, v in base.items()}
            fx[f"mask_{gname}"][:] = 0.0
            fx[f"ent_{gname}"][:] = 0.0
            fixtures.append(("empty_group", fx))
            made_b += 1
        if made_b < want_b:
            fx = {k: np.array(v, dtype=np.float32) for k, v in base.items()}
            for gname in group_names:
                fx[f"mask_{gname}"][:] = 0.0
                fx[f"ent_{gname}"][:] = 0.0
            fixtures.append(("empty_group", fx))
            made_b += 1
        if made_b >= want_b:
            break
    recipe["empty_group_base_indices"] = [int(x) for x in base_b]

    # -- (c) capacity-overflow: every mask forced all-ones ------------------
    want_c = counts["capacity_overflow"]
    base_c = rng.choice(n, size=min(want_c, n), replace=False)
    for i in base_c:
        fx = _row_fixture(val, std_globals, group_names, int(i))
        for gname in group_names:
            fx[f"mask_{gname}"][:] = 1.0
        fixtures.append(("capacity_overflow", fx))
    recipe["capacity_overflow_base_indices"] = [int(x) for x in base_c]

    # -- (d) edge normalization: +/-6 sigma globals + entity bounds ---------
    want_d = counts["edge_norm"]
    ent_lo, ent_hi = _entity_bounds(val, group_names)
    n_base_d = max(1, want_d // 2)
    base_d = rng.choice(n, size=min(n_base_d, n), replace=False)
    made_d = 0
    for i in base_d:
        if made_d >= want_d:
            break
        # Variant A: globals at +6 sigma, present entity features at upper bound.
        fx_hi = _row_fixture(val, std_globals, group_names, int(i))
        fx_hi["globals"][:] = GLOBAL_EDGE_SIGMA
        for gname in group_names:
            present = fx_hi[f"mask_{gname}"] > 0
            fx_hi[f"ent_{gname}"][present] = ent_hi
        fixtures.append(("edge_norm", fx_hi))
        made_d += 1
        if made_d >= want_d:
            break
        # Variant B: globals at -6 sigma, present entity features at lower bound.
        fx_lo = _row_fixture(val, std_globals, group_names, int(i))
        fx_lo["globals"][:] = -GLOBAL_EDGE_SIGMA
        for gname in group_names:
            present = fx_lo[f"mask_{gname}"] > 0
            fx_lo[f"ent_{gname}"][present] = ent_lo
        fixtures.append(("edge_norm", fx_lo))
        made_d += 1
    recipe["edge_norm_base_indices"] = [int(x) for x in base_d]
    recipe["edge_norm_global_sigma"] = GLOBAL_EDGE_SIGMA
    recipe["entity_bounds"] = {"lo": [float(v) for v in ent_lo], "hi": [float(v) for v in ent_hi]}

    for cat in ("stratified", "empty_group", "capacity_overflow", "edge_norm"):
        recipe["counts"][cat] = sum(1 for c, _ in fixtures if c == cat)
    log(f"[parity] built {len(fixtures)} fixtures: {recipe['counts']}")
    return fixtures, recipe


# ---------------------------------------------------------------------------
# Dual-backend evaluation
# ---------------------------------------------------------------------------
def _torch_predict(model, fx, group_names):
    import torch

    globals_t = torch.from_numpy(fx["globals"]).unsqueeze(0)
    entities = {g: torch.from_numpy(fx[f"ent_{g}"]).unsqueeze(0) for g in group_names}
    masks = {g: torch.from_numpy(fx[f"mask_{g}"]).unsqueeze(0) for g in group_names}
    with torch.no_grad():
        out = model(globals_t, entities, masks)
    return float(out[0, 0].item()), float(out[0, 1].item())


def _onnx_predict(session, fx, input_names, output_name, group_names):
    import numpy as np

    ort_inputs = {"globals": np.ascontiguousarray(fx["globals"][None, :], dtype=np.float32)}
    for g in group_names:
        ort_inputs[f"ent_{g}"] = np.ascontiguousarray(fx[f"ent_{g}"][None, ...], dtype=np.float32)
        ort_inputs[f"mask_{g}"] = np.ascontiguousarray(fx[f"mask_{g}"][None, :], dtype=np.float32)
    out = session.run([output_name], ort_inputs)[0]
    return float(out[0, 0]), float(out[0, 1])


def _percentile(values, pct):
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = pct / 100.0 * (len(ordered) - 1)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[int(low)]
    frac = rank - low
    return ordered[int(low)] * (1.0 - frac) + ordered[int(high)] * frac


def evaluate_parity(service, session, input_names, output_name, fixtures, *, log=print):
    import numpy as np

    model = service._model
    group_names = service._group_names

    per_cat: dict[str, dict[str, Any]] = {}
    all_diffs: list[float] = []
    torch_nonfinite = 0
    onnx_nonfinite = 0
    worst = {"diff": -1.0, "category": None, "torch": None, "onnx": None}

    for idx, (cat, fx) in enumerate(fixtures):
        tax, tay = _torch_predict(model, fx, group_names)
        oax, oay = _onnx_predict(session, fx, input_names, output_name, group_names)
        t_fin = math.isfinite(tax) and math.isfinite(tay)
        o_fin = math.isfinite(oax) and math.isfinite(oay)
        if not t_fin:
            torch_nonfinite += 1
        if not o_fin:
            onnx_nonfinite += 1
        cat_rec = per_cat.setdefault(cat, {"n": 0, "diffs": [], "max_diff": 0.0, "nonfinite": 0})
        cat_rec["n"] += 1
        if not (t_fin and o_fin):
            cat_rec["nonfinite"] += 1
            continue
        diff = max(abs(tax - oax), abs(tay - oay))
        cat_rec["diffs"].append(diff)
        cat_rec["max_diff"] = max(cat_rec["max_diff"], diff)
        all_diffs.append(diff)
        if diff > worst["diff"]:
            worst = {"diff": diff, "category": cat, "torch": [tax, tay], "onnx": [oax, oay]}
        if (idx + 1) % 2000 == 0:
            log(f"[parity]   {idx + 1}/{len(fixtures)} fixtures compared "
                f"(running max |d| = {max(all_diffs):.3e})")

    category_stats = {}
    for cat, rec in per_cat.items():
        diffs = rec["diffs"]
        category_stats[cat] = {
            "n": rec["n"],
            "compared": len(diffs),
            "nonfinite": rec["nonfinite"],
            "max_diff": float(rec["max_diff"]),
            "mean_diff": float(np.mean(diffs)) if diffs else 0.0,
            "p99_diff": float(_percentile(diffs, 99.0)),
        }

    overall = {
        "n_fixtures": len(fixtures),
        "compared": len(all_diffs),
        "max_diff": float(max(all_diffs)) if all_diffs else 0.0,
        "mean_diff": float(np.mean(all_diffs)) if all_diffs else 0.0,
        "p99_diff": float(_percentile(all_diffs, 99.0)),
        "torch_nonfinite": torch_nonfinite,
        "onnx_nonfinite": onnx_nonfinite,
        "worst": worst if worst["category"] else None,
    }
    return overall, category_stats


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def run_parity(*, registry: Path, onnx_registry: Path, smoke: bool,
               latency_json: Path | None, log=print) -> dict[str, Any]:
    import torch

    torch.set_num_threads(1)

    log(f"[parity] loading torch chain from {registry.name} ...")
    service = _load_torch_service(registry)
    log(f"[parity] loading + verifying ONNX from {onnx_registry.name} ...")
    session, onnx_manifest, input_names, output_name, onnx_sha = _load_onnx_session(onnx_registry)

    log("[parity] loading frozen validation split (no training rows) ...")
    val, std_globals = _load_validation_split(registry)

    counts = SMOKE_COUNTS if smoke else FULL_COUNTS
    fixtures, recipe = build_fixtures(val, std_globals, service._group_names, counts, log=log)

    started = time.perf_counter()
    overall, category_stats = evaluate_parity(
        service, session, input_names, output_name, fixtures, log=log
    )
    runtime_sec = time.perf_counter() - started

    gate_finite = overall["torch_nonfinite"] == 0 and overall["onnx_nonfinite"] == 0
    gate_max = overall["max_diff"] <= MAX_ABS_DIFF_GATE and overall["compared"] > 0
    all_pass = gate_finite and gate_max

    gates = {
        "finite": {
            "status": "PASS" if gate_finite else "FAIL",
            "torch_nonfinite": overall["torch_nonfinite"],
            "onnx_nonfinite": overall["onnx_nonfinite"],
        },
        "max_abs_diff": {
            "status": "PASS" if gate_max else "FAIL",
            "value": overall["max_diff"],
            "threshold": MAX_ABS_DIFF_GATE,
        },
    }
    verdict = "PASS" if all_pass else "FAIL"

    latency = _load_latency(latency_json) if latency_json else None

    payload = {
        "report": "onnx_parity_v1",
        "stage": "G",
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "smoke" if smoke else "full",
        "runtime_sec": round(runtime_sec, 2),
        "environment": _environment(),
        "registry": str(registry),
        "onnx_registry": str(onnx_registry),
        "onnx_identity": {
            "onnx_sha256": onnx_sha,
            "parent_model_sha256": onnx_manifest.get("parent_model_sha256"),
            "opset": onnx_manifest.get("opset"),
            "exporter": onnx_manifest.get("exporter"),
            "torch_version": onnx_manifest.get("torch_version"),
            "onnx_version": onnx_manifest.get("onnx_version"),
            "onnxruntime_version": onnx_manifest.get("onnxruntime_version"),
            "input_names": input_names,
            "output_name": output_name,
        },
        "service_identity": service.identity.log_block(),
        "gates": gates,
        "overall": overall,
        "by_category": category_stats,
        "fixture_recipe": recipe,
        "latency_secondary": latency,
        "verdict": verdict,
    }
    return payload


def _load_latency(latency_json: Path) -> dict[str, Any] | None:
    if not latency_json or not Path(latency_json).is_file():
        return None
    try:
        data = json.loads(Path(latency_json).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return {
        "source": str(latency_json),
        "backend": data.get("backend"),
        "mode": data.get("mode"),
        "gate_cadence_hz": data.get("gate_cadence_hz"),
        "gates": data.get("gates"),
        "bands": {
            name: {hz: {"model_p99": r["model_ms"]["p99"], "e2e_p99": r["e2e_ms"]["p99"]}
                   for hz, r in by_cad.items()}
            for name, by_cad in (data.get("bands") or {}).items()
        },
    }


def _environment() -> dict[str, Any]:
    import platform

    import numpy as np
    import onnx
    import onnxruntime as ort
    import torch

    return {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "numpy": np.__version__,
        "onnx": onnx.__version__,
        "onnxruntime": ort.__version__,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "torch_num_threads": torch.get_num_threads(),
    }


def _update_onnx_manifest(onnx_registry: Path, payload: dict[str, Any], log=print) -> None:
    """Write the parity block back into the tracked ONNX registry manifest."""
    manifest = json.loads(onnx_registry.read_text(encoding="utf-8"))
    manifest["parity"] = {
        "report": "reports/wp2/onnx_parity_v1.json",
        "max_abs_diff": payload["overall"]["max_diff"],
        "n_fixtures": payload["overall"]["n_fixtures"],
        "verdict": payload["verdict"],
    }
    onnx_registry.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    log(f"[parity] updated manifest parity block -> {onnx_registry}")


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
def write_reports(payload: dict[str, Any]) -> None:
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    REPORT_MD.write_text(_render_md(payload), encoding="utf-8")


def _render_md(p: dict[str, Any]) -> str:
    o = p["overall"]
    g = p["gates"]
    lines: list[str] = []
    lines.append("# ONNX parity — WP2 Stage G")
    lines.append("")
    lines.append(
        f"Generated {p['generated']} · mode **{p['mode']}** · runtime {p['runtime_sec']}s · "
        f"verdict **{p['verdict']}**."
    )
    lines.append("")
    lines.append(
        "PyTorch (CPU, 1 thread) vs exported ONNX graph (ONNX Runtime, CPU, intra_op 1), "
        "batch-1, on validation-split fixtures only (no training-split contamination)."
    )
    lines.append("")

    lines.append("## Gates")
    lines.append("")
    lines.append("| gate | status | value | threshold |")
    lines.append("|---|---|---|---|")
    lines.append(
        f"| max &#124;Δaction&#124; | {g['max_abs_diff']['status']} | "
        f"{g['max_abs_diff']['value']:.3e} | <= {g['max_abs_diff']['threshold']:.0e} |"
    )
    lines.append(
        f"| zero NaN/Inf (both backends) | {g['finite']['status']} | "
        f"torch={g['finite']['torch_nonfinite']}, onnx={g['finite']['onnx_nonfinite']} | 0 |"
    )
    lines.append("")
    lines.append(
        f"Overall: {o['compared']}/{o['n_fixtures']} fixtures compared · "
        f"max |Δ| = {o['max_diff']:.3e} · mean |Δ| = {o['mean_diff']:.3e} · "
        f"p99 |Δ| = {o['p99_diff']:.3e}."
    )
    lines.append("")

    lines.append("## Per-category")
    lines.append("")
    lines.append("| category | n | compared | nonfinite | max &#124;Δ&#124; | mean &#124;Δ&#124; | p99 &#124;Δ&#124; |")
    lines.append("|---|---|---|---|---|---|---|")
    for cat in ("stratified", "empty_group", "capacity_overflow", "edge_norm"):
        c = p["by_category"].get(cat)
        if not c:
            continue
        lines.append(
            f"| {cat} | {c['n']} | {c['compared']} | {c['nonfinite']} | "
            f"{c['max_diff']:.3e} | {c['mean_diff']:.3e} | {c['p99_diff']:.3e} |"
        )
    lines.append("")

    if o.get("worst"):
        w = o["worst"]
        lines.append(
            f"Worst fixture: category **{w['category']}**, |Δ| = {w['diff']:.3e}, "
            f"torch = [{w['torch'][0]:.6f}, {w['torch'][1]:.6f}], "
            f"onnx = [{w['onnx'][0]:.6f}, {w['onnx'][1]:.6f}]."
        )
        lines.append("")

    r = p["fixture_recipe"]
    lines.append("## Fixture recipe")
    lines.append("")
    lines.append(
        f"Seed {r['seed']} · {r['n_val_rows']} validation rows available · counts {r['counts']}."
    )
    lines.append("")
    lines.append(
        "- (a) stratified: proportional over wave-band x risk-bin strata; "
        f"indices sha256 `{r.get('stratified_indices_sha256', '-')[:16]}...`."
    )
    lines.append(
        "- (b) empty-group: each group's mask+entities zeroed one-at-a-time and all-at-once "
        f"from {len(r.get('empty_group_base_indices', []))} base rows."
    )
    lines.append(
        "- (c) capacity-overflow: every mask forced all-ones from "
        f"{len(r.get('capacity_overflow_base_indices', []))} base rows."
    )
    lines.append(
        f"- (d) edge-normalization: standardized globals at +/-{r.get('edge_norm_global_sigma')} sigma "
        f"and present entity features at per-feature validation bounds, from "
        f"{len(r.get('edge_norm_base_indices', []))} base rows (2 variants each)."
    )
    lines.append("")

    oi = p["onnx_identity"]
    lines.append("## ONNX identity")
    lines.append("")
    lines.append(f"- onnx sha256 `{oi['onnx_sha256']}`")
    lines.append(f"- parent best.pt sha256 `{oi['parent_model_sha256']}`")
    lines.append(
        f"- opset {oi['opset']} · exporter {oi['exporter']} · torch {oi['torch_version']} · "
        f"onnx {oi['onnx_version']} · onnxruntime {oi['onnxruntime_version']}"
    )
    lines.append("")

    lat = p.get("latency_secondary")
    lines.append("## Latency (secondary — ONNX backend sidecar)")
    lines.append("")
    if lat:
        lg = lat.get("gates") or {}
        mp = lg.get("model_p99", {})
        ep = lg.get("e2e_p99", {})
        lines.append(
            f"Source `{Path(lat['source']).name}` · backend {lat.get('backend')} · "
            f"mode {lat.get('mode')} · gate cadence {lat.get('gate_cadence_hz')} Hz."
        )
        lines.append("")
        lines.append("| gate | status | value | threshold |")
        lines.append("|---|---|---|---|")
        lines.append(
            f"| model p99 | {mp.get('status', '-')} | {mp.get('value_ms', float('nan')):.2f} ms | "
            f"<= {mp.get('threshold_ms', 10.0)} ms |"
        )
        lines.append(
            f"| end-to-end p99 | {ep.get('status', '-')} | {ep.get('value_ms', float('nan')):.2f} ms | "
            f"<= {ep.get('threshold_ms', 25.0)} ms |"
        )
        lines.append("")
    else:
        lines.append(
            "Run `scripts/wp2_student_latency_bench.py --smoke --backend onnx` to populate "
            "this table (writes `reports/wp2/student_latency_bench_onnx_v1.json`)."
        )
        lines.append("")

    env = p["environment"]
    lines.append("## Environment")
    lines.append("")
    lines.append(
        f"- torch `{env['torch']}` · onnx `{env['onnx']}` · onnxruntime `{env['onnxruntime']}` · "
        f"numpy `{env['numpy']}` · python `{env['python']}` · threads {env['torch_num_threads']}"
    )
    lines.append(f"- {env['platform']} · {env['processor']}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WP2 Stage G — ONNX vs PyTorch parity harness.")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--onnx-registry", default=str(DEFAULT_ONNX_REGISTRY))
    parser.add_argument("--latency-json", default=str(DEFAULT_LATENCY_JSON),
                        help="optional ONNX latency-bench JSON to embed as a secondary table")
    parser.add_argument("--smoke", action="store_true", help="quick subset (~600 fixtures, not qualifying)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        payload = run_parity(
            registry=Path(args.registry),
            onnx_registry=Path(args.onnx_registry),
            smoke=args.smoke,
            latency_json=Path(args.latency_json) if args.latency_json else None,
        )
    except OnnxParitySetupError as exc:
        print(f"setup error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - unexpected setup fault
        print(f"unexpected setup error: {exc}", file=sys.stderr)
        return 2

    write_reports(payload)
    try:
        _update_onnx_manifest(Path(args.onnx_registry), payload)
    except Exception as exc:  # manifest update is best-effort; report already written
        print(f"warning: could not update onnx manifest: {exc}", file=sys.stderr)

    o = payload["overall"]
    print(f"[parity] verdict={payload['verdict']} "
          f"max|d|={o['max_diff']:.3e} p99|d|={o['p99_diff']:.3e} "
          f"compared={o['compared']}/{o['n_fixtures']} "
          f"nonfinite(torch={o['torch_nonfinite']},onnx={o['onnx_nonfinite']})")
    print(f"[parity] reports: {REPORT_JSON} | {REPORT_MD}")
    return 0 if payload["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
