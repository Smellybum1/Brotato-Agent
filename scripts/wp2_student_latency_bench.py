"""WP2 M3 validation ladder — rung 3: latency benchmark (architecture §4.3, §9.2).

Drives a *live* student sidecar (protocol v1, ``docs/IPC_PROTOCOL.md``) over a
loopback socket with representative frozen ``combat_capture`` payloads and records
per-request model and end-to-end latency at 15/20/30 Hz request cadence.

Corpus bands (raw payloads from the frozen ``events.jsonl`` runs, READ-ONLY):
  * ``early`` — waves 1-5;
  * ``late``  — waves 16-19;
  * ``boss``  — wave 20;
  * ``peak``  — the top 5% of all sampled payloads by ``enemies + projectiles``
    entity count (the serialization / encode hot path).

Gates at 20 Hz (each reported PASS/FAIL; 15/30 Hz stats reported for the §9.2 record):
  * ``model_p99``   — model p99 ≤ 10 ms;
  * ``e2e_p99``     — end-to-end p99 ≤ 25 ms;
  * ``within_50ms`` — ≥ 99.9% of replies within 50 ms;
  * ``consec_miss`` — no run of > 2 consecutive misses of the 40 ms deadline.

The client is Python, so this measures Python-client -> loopback -> sidecar cost.
Godot-side JSON serialization is NOT included here and will be measured live via
the mod's ``student_tick`` ``latency_ms`` telemetry during the isolated smoke.

Exit codes: 0 all 20 Hz gates pass · 1 a gate failed · 2 setup/artifact error.

Usage:
    .venv/Scripts/python.exe scripts/wp2_student_latency_bench.py
    .venv/Scripts/python.exe scripts/wp2_student_latency_bench.py --smoke
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from trainer.bridge import protocol  # noqa: E402
from scripts.wp2_student_replay_parity import (  # noqa: E402
    ParitySetupError,
    SidecarClient,
    find_free_port,
    kill_sidecar,
    load_validation_runs,
)

DEFAULT_REGISTRY = REPO_ROOT / "models" / "registry" / "bc_v1_s1_full.json"
DEFAULT_ONNX_REGISTRY = REPO_ROOT / "models" / "registry" / "bc_v1_s1_full_onnx.json"
DEFAULT_SPLIT_CONFIG = REPO_ROOT / "configs" / "wp2" / "dataset_split_v1.yaml"
DEFAULT_SCHEMA = REPO_ROOT / "configs" / "wp2" / "observation_v1.yaml"
RUNS_ROOT = Path("C:/Users/moxhe/AppData/Roaming/Brotato/brotato_agent/runs")

REPORT_JSON = REPO_ROOT / "reports" / "wp2" / "student_latency_bench_v1.json"
REPORT_MD = REPO_ROOT / "reports" / "wp2" / "student_latency_bench_v1.md"
SIDECAR_LOG = REPO_ROOT / ".tmp" / "latency_sidecar_log.jsonl"


def _report_paths(backend: str) -> tuple[Path, Path]:
    """Backend-aware report paths so the qualified torch report is never overwritten."""
    if backend == "onnx":
        return (
            REPO_ROOT / "reports" / "wp2" / "student_latency_bench_onnx_v1.json",
            REPO_ROOT / "reports" / "wp2" / "student_latency_bench_onnx_v1.md",
        )
    return REPORT_JSON, REPORT_MD


def _spawn_sidecar_with_backend(
    registry: Path,
    port: int,
    log_path: Path,
    *,
    backend: str,
    onnx_registry: Path,
    idle_exit_sec: float = 3600.0,
):
    """Spawn ``run_student_sidecar.py`` with an explicit ``--backend`` (torch|onnx).

    A local spawn (rather than the imported torch-only ``spawn_sidecar``) keeps
    ``wp2_student_replay_parity.py`` unmodified while threading the backend
    selection through.
    """
    import subprocess

    log_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "run_student_sidecar.py"),
        "--registry", str(registry),
        "--host", "127.0.0.1",
        "--port", str(port),
        "--idle-exit-sec", str(idle_exit_sec),
        "--log-path", str(log_path),
        "--backend", backend,
    ]
    if backend == "onnx":
        cmd += ["--onnx-registry", str(onnx_registry)]
    return subprocess.Popen(
        cmd, cwd=str(REPO_ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )

# Bands: name -> inclusive wave range (peak is derived, not wave-gated).
WAVE_BANDS: dict[str, tuple[int, int]] = {
    "early": (1, 5),
    "late": (16, 19),
    "boss": (20, 20),
}
PEAK_BAND = "peak"
PEAK_FRACTION = 0.05

CADENCES_HZ = (15, 20, 30)
GATE_CADENCE_HZ = 20
DEADLINE_MS = 40.0
WITHIN_MS = 50.0
WARMUP_REQUESTS = 60  # > 50; first-call JIT (~26 ms) discarded

TARGET_PER_BAND = 2000
WARMUP_DISCARD = 50
SMOKE_TARGET_PER_BAND = 150
SMOKE_WARMUP = 55
SMOKE_CADENCES = (20,)

# Gates
MODEL_P99_MS = 10.0
E2E_P99_MS = 25.0
WITHIN_FRACTION = 0.999
MAX_CONSEC_MISS = 2


# ---------------------------------------------------------------------------
# Corpus assembly
# ---------------------------------------------------------------------------
def _iter_capture_payloads(events_path: Path) -> Iterator[dict[str, Any]]:
    with open(events_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            if event.get("event") == "combat_capture":
                yield event["payload"]


def _entity_load(payload: dict[str, Any]) -> int:
    ents = payload.get("entities") or {}
    return len(ents.get("enemies") or []) + len(ents.get("projectiles") or [])


def _band_for_wave(wave: int) -> str | None:
    for name, (lo, hi) in WAVE_BANDS.items():
        if lo <= wave <= hi:
            return name
    return None


def _run_reaches(run: dict[str, Any], lo: int) -> bool:
    """Whether a run reaches band lower-bound ``lo`` (last_wave unknown => assume yes)."""
    last_wave = run.get("last_wave")
    if last_wave is None:
        return True
    try:
        return int(last_wave) >= lo
    except (TypeError, ValueError):
        return True


def _round_robin(run_buckets: list[list[dict[str, Any]]], limit: int) -> list[dict[str, Any]]:
    """Interleave per-run lists one-at-a-time for even coverage, up to ``limit``."""
    out: list[dict[str, Any]] = []
    idx = 0
    while len(out) < limit:
        progressed = False
        for bucket in run_buckets:
            if idx < len(bucket):
                out.append(bucket[idx])
                progressed = True
                if len(out) >= limit:
                    break
        if not progressed:
            break
        idx += 1
    return out


def build_corpus(
    runs: list[dict[str, Any]],
    runs_root: Path,
    *,
    per_band: int,
    log: Any = print,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Sample raw payloads evenly across runs into wave bands + a peak-load subset.

    Each band's per-run intake cap is sized from how many runs actually reach the
    band (via the split's ``last_wave`` metadata), with 50% headroom, so a band
    reaches ``per_band`` when the data exists rather than being throttled by a flat
    cap. Per-run buckets are then round-robin-merged for even cross-run coverage and
    trimmed to ``per_band``. The peak band is the top ``PEAK_FRACTION`` of every
    sampled payload by enemies+projectiles count. events.jsonl is streamed once each
    (READ-ONLY).
    """
    # Per-band contributing-run count from last_wave (a run reaches band [lo,hi]
    # iff last_wave >= lo), used to size an even per-run intake cap with headroom.
    intake_cap: dict[str, int] = {}
    n_contrib: dict[str, int] = {}
    for name, (lo, _hi) in WAVE_BANDS.items():
        contrib = sum(1 for r in runs if _run_reaches(r, lo))
        n_contrib[name] = contrib
        base = per_band / max(1, contrib)
        intake_cap[name] = max(1, int(base * 1.5) + 1)

    # Per-run per-band buckets (round-robin-merged after collection).
    buckets: dict[str, list[list[dict[str, Any]]]] = {name: [] for name in WAVE_BANDS}
    loads: list[tuple[int, dict[str, Any]]] = []  # (entity_load, payload) for peak selection
    per_run_band_counts: dict[str, dict[str, int]] = {}

    for run in runs:
        run_id = run["run_id"]
        events_path = runs_root / run_id / "events.jsonl"
        if not events_path.is_file():
            log(f"[bench]   WARNING: events.jsonl missing for {run_id}; skipping")
            continue
        run_bucket = {name: [] for name in WAVE_BANDS}
        for payload in _iter_capture_payloads(events_path):
            band = _band_for_wave(int(payload.get("wave") or 0))
            if band is None or len(run_bucket[band]) >= intake_cap[band]:
                continue
            run_bucket[band].append(payload)
            loads.append((_entity_load(payload), payload))
            if all(len(run_bucket[b]) >= intake_cap[b] for b in WAVE_BANDS):
                break
        for name in WAVE_BANDS:
            if run_bucket[name]:
                buckets[name].append(run_bucket[name])
        per_run_band_counts[run_id] = {name: len(run_bucket[name]) for name in WAVE_BANDS}

    # Round-robin merge across per-run buckets (even coverage), trim to per_band.
    bands: dict[str, list[dict[str, Any]]] = {}
    for name in WAVE_BANDS:
        bands[name] = _round_robin(buckets[name], per_band)

    # Peak band: top PEAK_FRACTION by entity load across everything sampled.
    loads.sort(key=lambda t: t[0], reverse=True)
    n_peak = max(1, int(len(loads) * PEAK_FRACTION))
    peak = [p for _, p in loads[:n_peak]]

    corpus = dict(bands)
    corpus[PEAK_BAND] = peak

    meta = {
        "per_band_target": per_band,
        "per_band_intake_cap": intake_cap,
        "per_band_contributing_runs": n_contrib,
        "counts": {name: len(payloads) for name, payloads in corpus.items()},
        "peak_entity_load_min": int(loads[n_peak - 1][0]) if loads else 0,
        "peak_entity_load_max": int(loads[0][0]) if loads else 0,
        "per_run_band_counts": per_run_band_counts,
    }
    return corpus, meta


# ---------------------------------------------------------------------------
# Paced request loop
# ---------------------------------------------------------------------------
def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = pct / 100.0 * (len(ordered) - 1)
    import math

    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[int(low)]
    frac = rank - low
    return ordered[int(low)] * (1.0 - frac) + ordered[int(high)] * frac


def paced_run(
    client: SidecarClient,
    payloads: list[dict[str, Any]],
    hz: float,
    *,
    seq_base: int,
) -> dict[str, Any]:
    """Send ``payloads`` at a fixed ``hz`` cadence; record model + e2e latency.

    The schedule is absolute (target = t0 + i/hz): a late reply does not push the
    next send back, matching the mod's 20 Hz capture cadence. Reads block on the
    single FIFO socket, so each request's e2e is send -> reply receipt.
    """
    period = 1.0 / hz
    model_ms: list[float] = []
    e2e_ms: list[float] = []
    errors = 0
    t0 = time.perf_counter()
    for i, payload in enumerate(payloads):
        target = t0 + i * period
        now = time.perf_counter()
        if target > now:
            time.sleep(target - now)
        send_ts = time.perf_counter()
        wave = int(payload.get("wave") or 0)
        reply = client.act(seq=seq_base + i, wave=wave, payload=payload)
        recv_ts = time.perf_counter()
        if protocol.frame_type(reply) != protocol.MSG_ACTION:
            errors += 1
            continue
        e2e_ms.append((recv_ts - send_ts) * 1000.0)
        model_ms.append(float(reply.get("model_ms", 0.0)))

    # Deadline / within-window analysis on e2e.
    misses = [ms > DEADLINE_MS for ms in e2e_ms]
    miss_count = sum(misses)
    max_consec = 0
    cur = 0
    for m in misses:
        cur = cur + 1 if m else 0
        max_consec = max(max_consec, cur)
    within = sum(1 for ms in e2e_ms if ms <= WITHIN_MS)
    n = len(e2e_ms)
    within_frac = (within / n) if n else 0.0

    def stats(values: list[float]) -> dict[str, float]:
        return {
            "p50": _percentile(values, 50.0),
            "p95": _percentile(values, 95.0),
            "p99": _percentile(values, 99.0),
            "max": max(values) if values else 0.0,
            "mean": (sum(values) / len(values)) if values else 0.0,
        }

    return {
        "hz": hz,
        "n": n,
        "errors": errors,
        "model_ms": stats(model_ms),
        "e2e_ms": stats(e2e_ms),
        "deadline_ms": DEADLINE_MS,
        "miss_count": miss_count,
        "max_consecutive_misses": max_consec,
        "within_50ms": within,
        "within_50ms_fraction": within_frac,
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def run_benchmark(
    *,
    registry: Path,
    split_config: Path,
    schema_path: Path,
    runs_root: Path,
    smoke: bool,
    port: int | None,
    backend: str = "torch",
    onnx_registry: Path | None = None,
    log: Any = print,
) -> dict[str, Any]:
    import yaml

    schema = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    source_capture_schema_hash = str(schema["source_capture_schema_hash"]).upper()
    schema_id = str(schema["schema_id"])
    control_hz = int(schema.get("control_hz", 20))

    per_band = SMOKE_TARGET_PER_BAND if smoke else TARGET_PER_BAND
    warmup_n = SMOKE_WARMUP if smoke else WARMUP_REQUESTS
    cadences = SMOKE_CADENCES if smoke else CADENCES_HZ

    # Corpus draws from every split run (train + val) so boss/late bands have depth.
    val_runs = load_validation_runs(split_config)
    all_runs = _all_split_runs(split_config)
    if smoke:
        all_runs = val_runs[:2]

    log(f"[bench] building corpus (per_band={per_band}) from {len(all_runs)} runs ...")
    corpus, corpus_meta = build_corpus(all_runs, runs_root, per_band=per_band, log=log)
    for name, payloads in corpus.items():
        log(f"[bench]   band {name}: {len(payloads)} payloads")

    chosen_port = port or find_free_port()
    log(f"[bench] spawning sidecar on 127.0.0.1:{chosen_port} (backend={backend}) ...")
    proc = _spawn_sidecar_with_backend(
        registry,
        chosen_port,
        SIDECAR_LOG,
        backend=backend,
        onnx_registry=onnx_registry or DEFAULT_ONNX_REGISTRY,
    )
    client = SidecarClient(chosen_port)

    started = time.perf_counter()
    band_results: dict[str, dict[str, Any]] = {}
    hello_ack: dict[str, Any] | None = None
    try:
        client.connect(proc)
        hello_ack = client.handshake(
            capture_schema_id=schema_id,
            capture_schema_hash=source_capture_schema_hash,
            control_hz=control_hz,
            run_id="latency_bench_v1",
        )
        log(f"[bench] handshake ok - serving {hello_ack.get('registry_run_name')} "
            f"backend={hello_ack.get('backend')} pid={hello_ack.get('pid')}")

        # Warmup on the heaviest available payloads (discarded). Covers first-call JIT.
        warmup_pool = (corpus[PEAK_BAND] or corpus["early"] or [])
        warmup_payloads = _repeat_to(warmup_pool, warmup_n)
        log(f"[bench] warmup: {len(warmup_payloads)} requests (discarded) ...")
        for i, payload in enumerate(warmup_payloads):
            client.act(seq=1_000_000 + i, wave=int(payload.get("wave") or 0), payload=payload)

        seq_base = 1
        for name in list(WAVE_BANDS) + [PEAK_BAND]:
            payloads = corpus.get(name) or []
            if not payloads:
                log(f"[bench]   band {name}: EMPTY, skipping")
                continue
            by_cadence: dict[str, Any] = {}
            for hz in cadences:
                result = paced_run(client, payloads, hz, seq_base=seq_base)
                seq_base += len(payloads) + 1
                by_cadence[str(hz)] = result
                log(f"[bench]   {name} @ {hz}Hz: model p99={result['model_ms']['p99']:.2f}ms "
                    f"e2e p99={result['e2e_ms']['p99']:.2f}ms "
                    f"miss={result['miss_count']} maxconsec={result['max_consecutive_misses']}")
            band_results[name] = by_cadence
        client.bye()
    finally:
        client.close()
        kill_sidecar(proc)

    runtime_sec = time.perf_counter() - started

    # -- 20 Hz gates (worst band) -------------------------------------------
    gate_cadence = str(GATE_CADENCE_HZ)
    gated_bands = {
        name: by_cad[gate_cadence]
        for name, by_cad in band_results.items()
        if gate_cadence in by_cad
    }
    gates = _compute_gates(gated_bands)
    all_pass = all(g["status"] == "PASS" for g in gates.values())

    return {
        "report": "student_latency_bench_v1",
        "rung": 3,
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "smoke" if smoke else "full",
        "backend": backend,
        "runtime_sec": round(runtime_sec, 2),
        "gate_cadence_hz": GATE_CADENCE_HZ,
        "cadences_hz": list(cadences),
        "warmup_requests_discarded": warmup_n,
        "client_note": (
            "Latency is Python-client -> loopback -> sidecar. Godot-side JSON "
            "serialization is NOT included here; it is measured live via the mod's "
            "student_tick latency_ms telemetry during the isolated smoke."
        ),
        "environment": _environment(),
        "machine": _machine_context(),
        "registry": str(registry),
        "sidecar_identity": hello_ack,
        "corpus": corpus_meta,
        "gates": gates,
        "overall": "PASS" if all_pass else "FAIL",
        "bands": band_results,
    }


def _all_split_runs(split_config: Path) -> list[dict[str, Any]]:
    import yaml

    data = yaml.safe_load(split_config.read_text(encoding="utf-8"))
    runs: list[dict[str, Any]] = []
    for key in ("train", "validation"):
        for entry in data.get(key) or []:
            runs.append({"run_id": str(entry["run_id"]), "last_wave": entry.get("last_wave")})
    return runs


def _repeat_to(pool: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    if not pool:
        return []
    out: list[dict[str, Any]] = []
    while len(out) < n:
        out.extend(pool)
    return out[:n]


def _compute_gates(gated_bands: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """20 Hz gates evaluated against the WORST band (max p99 / min within-frac)."""
    if not gated_bands:
        return {
            "model_p99": {"status": "FAIL", "detail": "no 20 Hz data"},
            "e2e_p99": {"status": "FAIL", "detail": "no 20 Hz data"},
            "within_50ms": {"status": "FAIL", "detail": "no 20 Hz data"},
            "consec_miss": {"status": "FAIL", "detail": "no 20 Hz data"},
        }

    def worst_p99(key: str) -> tuple[str, float]:
        return max(((name, r[key]["p99"]) for name, r in gated_bands.items()), key=lambda t: t[1])

    model_band, model_p99 = worst_p99("model_ms")
    e2e_band, e2e_p99 = worst_p99("e2e_ms")
    within_band, within_frac = min(
        ((name, r["within_50ms_fraction"]) for name, r in gated_bands.items()), key=lambda t: t[1]
    )
    consec_band, consec = max(
        ((name, r["max_consecutive_misses"]) for name, r in gated_bands.items()), key=lambda t: t[1]
    )

    return {
        "model_p99": {
            "status": "PASS" if model_p99 <= MODEL_P99_MS else "FAIL",
            "value_ms": float(model_p99),
            "threshold_ms": MODEL_P99_MS,
            "worst_band": model_band,
        },
        "e2e_p99": {
            "status": "PASS" if e2e_p99 <= E2E_P99_MS else "FAIL",
            "value_ms": float(e2e_p99),
            "threshold_ms": E2E_P99_MS,
            "worst_band": e2e_band,
        },
        "within_50ms": {
            "status": "PASS" if within_frac >= WITHIN_FRACTION else "FAIL",
            "value_fraction": float(within_frac),
            "threshold_fraction": WITHIN_FRACTION,
            "worst_band": within_band,
        },
        "consec_miss": {
            "status": "PASS" if consec <= MAX_CONSEC_MISS else "FAIL",
            "value": int(consec),
            "threshold": MAX_CONSEC_MISS,
            "worst_band": consec_band,
        },
    }


def _environment() -> dict[str, Any]:
    import platform

    import numpy as np
    import torch

    return {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "numpy": np.__version__,
        "platform": platform.platform(),
    }


def _machine_context() -> dict[str, Any]:
    import platform
    import subprocess

    cpu = platform.processor()
    try:
        out = subprocess.run(
            ["wmic", "cpu", "get", "name"], capture_output=True, text=True, timeout=10
        )
        lines = [ln.strip() for ln in out.stdout.splitlines() if ln.strip() and ln.strip() != "Name"]
        if lines:
            cpu = lines[0]
    except Exception:
        pass
    return {
        "cpu": cpu,
        "logical_cores": _cpu_count(),
        "platform": platform.platform(),
        "plugged_in": "unknown",
    }


def _cpu_count() -> int:
    import os

    return os.cpu_count() or 0


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
def write_reports(payload: dict[str, Any]) -> tuple[Path, Path]:
    report_json, report_md = _report_paths(payload.get("backend", "torch"))
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_md.write_text(_render_md(payload), encoding="utf-8")
    return report_json, report_md


def _render_md(p: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Student latency benchmark — rung 3")
    lines.append("")
    lines.append(
        f"Generated {p['generated']} · mode **{p['mode']}** · backend **{p.get('backend', 'torch')}** · "
        f"runtime {p['runtime_sec']}s · gate cadence {p['gate_cadence_hz']} Hz · overall **{p['overall']}**."
    )
    lines.append("")
    lines.append(f"> {p['client_note']}")
    lines.append("")

    lines.append(f"## Gates (at {p['gate_cadence_hz']} Hz, worst band)")
    lines.append("")
    lines.append("| gate | status | value | threshold | worst band |")
    lines.append("|---|---|---|---|---|")
    g = p["gates"]
    lines.append(
        f"| model p99 | {g['model_p99']['status']} | {g['model_p99'].get('value_ms', float('nan')):.2f} ms "
        f"| ≤ {g['model_p99'].get('threshold_ms', MODEL_P99_MS)} ms | {g['model_p99'].get('worst_band', '-')} |"
    )
    lines.append(
        f"| end-to-end p99 | {g['e2e_p99']['status']} | {g['e2e_p99'].get('value_ms', float('nan')):.2f} ms "
        f"| ≤ {g['e2e_p99'].get('threshold_ms', E2E_P99_MS)} ms | {g['e2e_p99'].get('worst_band', '-')} |"
    )
    lines.append(
        f"| within 50 ms | {g['within_50ms']['status']} | "
        f"{g['within_50ms'].get('value_fraction', 0.0) * 100:.3f}% "
        f"| ≥ {g['within_50ms'].get('threshold_fraction', WITHIN_FRACTION) * 100:.1f}% "
        f"| {g['within_50ms'].get('worst_band', '-')} |"
    )
    lines.append(
        f"| ≤ 2 consecutive 40 ms-deadline misses | {g['consec_miss']['status']} | "
        f"{g['consec_miss'].get('value', '-')} | ≤ {g['consec_miss'].get('threshold', MAX_CONSEC_MISS)} "
        f"| {g['consec_miss'].get('worst_band', '-')} |"
    )
    lines.append("")

    lines.append("## Per-band x per-cadence")
    lines.append("")
    lines.append(
        "| band | Hz | n | model p50 | model p95 | model p99 | model max | "
        "e2e p50 | e2e p95 | e2e p99 | e2e max | miss | max consec | within 50ms |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for band, by_cad in p["bands"].items():
        for hz, r in by_cad.items():
            m, e = r["model_ms"], r["e2e_ms"]
            lines.append(
                f"| {band} | {hz} | {r['n']} | {m['p50']:.2f} | {m['p95']:.2f} | {m['p99']:.2f} | {m['max']:.2f} "
                f"| {e['p50']:.2f} | {e['p95']:.2f} | {e['p99']:.2f} | {e['max']:.2f} "
                f"| {r['miss_count']} | {r['max_consecutive_misses']} | {r['within_50ms_fraction'] * 100:.3f}% |"
            )
    lines.append("")

    c = p["corpus"]
    lines.append("## Corpus")
    lines.append("")
    lines.append(
        f"Per-band target {c['per_band_target']} · contributing runs {c['per_band_contributing_runs']} "
        f"· per-run intake cap {c['per_band_intake_cap']}. Peak band = top "
        f"{PEAK_FRACTION * 100:.0f}% by enemies+projectiles "
        f"(load range {c['peak_entity_load_min']}..{c['peak_entity_load_max']})."
    )
    lines.append("")
    lines.append("| band | payloads |")
    lines.append("|---|---|")
    for name, cnt in c["counts"].items():
        lines.append(f"| {name} | {cnt} |")
    lines.append("")

    lines.append("## Sidecar identity (`hello_ack`, verbatim)")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(p["sidecar_identity"], indent=2, sort_keys=True))
    lines.append("```")
    lines.append("")

    m = p["machine"]
    env = p["environment"]
    lines.append("## Machine + environment")
    lines.append("")
    lines.append(f"- CPU: {m['cpu']} ({m['logical_cores']} logical cores) · plugged-in: {m['plugged_in']}")
    lines.append(f"- torch `{env['torch']}` · numpy `{env['numpy']}` · python `{env['python']}`")
    lines.append(f"- {m['platform']}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rung 3 — student sidecar latency benchmark.")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--split-config", default=str(DEFAULT_SPLIT_CONFIG))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--runs-root", default=str(RUNS_ROOT))
    parser.add_argument("--port", type=int, default=None, help="sidecar port (default: OS-assigned free port)")
    parser.add_argument("--smoke", action="store_true", help="quick subset: 20 Hz only, ~150/band, 2 runs")
    parser.add_argument(
        "--backend",
        choices=("torch", "onnx"),
        default="torch",
        help="sidecar inference backend (default torch); onnx writes a separate report",
    )
    parser.add_argument("--onnx-registry", default=str(DEFAULT_ONNX_REGISTRY))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        payload = run_benchmark(
            registry=Path(args.registry),
            split_config=Path(args.split_config),
            schema_path=Path(args.schema),
            runs_root=Path(args.runs_root),
            smoke=args.smoke,
            port=args.port,
            backend=args.backend,
            onnx_registry=Path(args.onnx_registry),
        )
    except ParitySetupError as exc:
        print(f"setup error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - unexpected setup fault
        print(f"unexpected setup error: {exc}", file=sys.stderr)
        return 2

    report_json, report_md = write_reports(payload)
    g = payload["gates"]
    print(f"[bench] backend={payload.get('backend')} overall={payload['overall']} "
          f"model_p99={g['model_p99'].get('value_ms', float('nan')):.2f}ms "
          f"e2e_p99={g['e2e_p99'].get('value_ms', float('nan')):.2f}ms "
          f"within50={g['within_50ms'].get('value_fraction', 0.0) * 100:.3f}% "
          f"maxconsec={g['consec_miss'].get('value', '-')}")
    print(f"[bench] reports: {report_json} | {report_md}")
    return 0 if payload["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
