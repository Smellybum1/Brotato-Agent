"""WP2 M3 validation ladder — rung 2: offline replay parity (architecture §4.2).

Streams the frozen ``combat_obs_v1`` validation-split capture payloads through a
*live* student sidecar socket (protocol v1, ``docs/IPC_PROTOCOL.md``) and compares
each returned action to a reference action computed independently via the exact
``bc_offline`` inference path on CPU. The reference is the frozen NPZ row forwarded
through the verified model; the sidecar action is the same tick re-encoded live
from the RAW ``events.jsonl`` payload matched by ``capture_seq``.

Gates (each reported PASS/FAIL):
  * ``max_abs_delta``      — max |Δaction| over all compared ticks ≤ 1e-6;
  * ``finite``             — zero NaN/Inf in any compared reference/sidecar action;
  * ``no_sidecar_error``   — zero ``error`` replies on compared ticks;
  * ``coverage``           — every valid&temporal val row matched to a raw payload.

Reference and sidecar share the same verified artifact chain (registry manifest ->
``best.pt`` sha256 -> CPU eval model -> hash-verified normalization manifest ->
observation schema -> ``bc_input_v1``). The frozen ``events.jsonl`` runs are
READ-ONLY; nothing is ever written there.

Exit codes: 0 all gates pass · 1 a gate failed · 2 setup/artifact error.

Usage:
    .venv/Scripts/python.exe scripts/wp2_student_replay_parity.py
    .venv/Scripts/python.exe scripts/wp2_student_replay_parity.py --smoke
"""
from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterator, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from trainer.bridge import protocol  # noqa: E402

DEFAULT_REGISTRY = REPO_ROOT / "models" / "registry" / "bc_v1_s1_full.json"
DEFAULT_SPLIT_CONFIG = REPO_ROOT / "configs" / "wp2" / "dataset_split_v1.yaml"
DEFAULT_SCHEMA = REPO_ROOT / "configs" / "wp2" / "observation_v1.yaml"
DEFAULT_DATASET_DIR = REPO_ROOT / "datasets" / "combat_obs_v1"
RUNS_ROOT = Path("C:/Users/moxhe/AppData/Roaming/Brotato/brotato_agent/runs")

REPORT_JSON = REPO_ROOT / "reports" / "wp2" / "student_replay_parity_v1.json"
REPORT_MD = REPO_ROOT / "reports" / "wp2" / "student_replay_parity_v1.md"
SIDECAR_LOG = REPO_ROOT / ".tmp" / "parity_sidecar_log.jsonl"

MAX_ABS_DELTA_GATE = 1e-6
SMOKE_ROWS_PER_RUN = 250
SMOKE_RUNS = 2
REFERENCE_CHUNK = 1  # batch-1 forward — matches the sidecar's per-tick serving exactly
                     # (isolates the encode+serve parity from batch-kernel rounding)
SIDECAR_START_TIMEOUT_SEC = 90.0
SOCKET_TIMEOUT_SEC = 60.0


class ParitySetupError(RuntimeError):
    """Raised on any artifact / data / sidecar setup failure (exit code 2)."""


# ---------------------------------------------------------------------------
# Sidecar spawn + protocol client (reused by the latency benchmark)
# ---------------------------------------------------------------------------
def find_free_port() -> int:
    """Ask the OS for a free loopback TCP port and release it for the sidecar."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def spawn_sidecar(
    registry: Path, port: int, log_path: Path, *, idle_exit_sec: float = 3600.0
) -> subprocess.Popen:
    """Launch ``run_student_sidecar.py`` as a loopback subprocess on ``port``."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "run_student_sidecar.py"),
        "--registry", str(registry),
        "--host", "127.0.0.1",
        "--port", str(port),
        "--idle-exit-sec", str(idle_exit_sec),
        "--log-path", str(log_path),
    ]
    return subprocess.Popen(
        cmd,
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def kill_sidecar(proc: subprocess.Popen | None) -> None:
    """Terminate then hard-kill a spawned sidecar; never raises."""
    if proc is None or proc.poll() is not None:
        return
    try:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


class SidecarClient:
    """Minimal protocol-v1 client over a blocking loopback socket."""

    def __init__(self, port: int, host: str = "127.0.0.1") -> None:
        self._host = host
        self._port = port
        self._sock: socket.socket | None = None
        self._recv = None
        self.identity: dict[str, Any] | None = None

    def connect(self, proc: subprocess.Popen, timeout: float = SIDECAR_START_TIMEOUT_SEC) -> None:
        """Retry-connect until the sidecar accepts or ``timeout`` elapses."""
        deadline = time.monotonic() + timeout
        last_err: Exception | None = None
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                out = ""
                try:
                    out = proc.stdout.read() if proc.stdout else ""
                except Exception:
                    pass
                raise ParitySetupError(
                    f"sidecar exited early with code {proc.returncode}; output:\n{out}"
                )
            try:
                sock = socket.create_connection((self._host, self._port), timeout=5.0)
                sock.settimeout(SOCKET_TIMEOUT_SEC)
                self._sock = sock
                self._recv = protocol.socket_recv(sock)
                return
            except OSError as exc:  # not listening yet
                last_err = exc
                time.sleep(0.25)
        raise ParitySetupError(f"could not connect to sidecar on port {self._port}: {last_err}")

    def handshake(
        self, *, capture_schema_id: str, capture_schema_hash: str, control_hz: int, run_id: str
    ) -> dict[str, Any]:
        """Send ``hello`` and return the ``hello_ack`` identity block (raises on reject)."""
        self._send(
            protocol.build_hello(
                capture_schema_id=capture_schema_id,
                capture_schema_hash=capture_schema_hash,
                control_hz=control_hz,
                run_id=run_id,
            )
        )
        reply = protocol.read_frame(self._recv)
        if protocol.frame_type(reply) != protocol.MSG_HELLO_ACK:
            raise ParitySetupError(f"handshake rejected: {reply}")
        self.identity = reply
        return reply

    def act(self, *, seq: int, wave: int, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Send one ``act`` and return the matching ``action`` or ``error`` reply."""
        self._send(
            protocol.build_act(seq=seq, ts_ms=int(time.time() * 1000), wave=wave, payload=payload)
        )
        return protocol.read_frame(self._recv)

    def bye(self) -> None:
        if self._sock is None:
            return
        try:
            self._send(protocol.build_bye(reason="parity_done"))
        except Exception:
            pass

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def _send(self, message: Mapping[str, Any]) -> None:
        assert self._sock is not None
        self._sock.sendall(protocol.pack_frame(message))


# ---------------------------------------------------------------------------
# Reference (bc_offline path) + raw payload matching
# ---------------------------------------------------------------------------
def load_service(registry: Path):
    """Load + verify the artifact chain; returns the TorchModelService."""
    from trainer.bridge.sidecar import SidecarStartupError, TorchModelService

    try:
        return TorchModelService.from_registry(registry, checkpoint="best")
    except SidecarStartupError as exc:
        raise ParitySetupError(f"artifact chain failed to load/verify: {exc}") from exc


def reference_actions(service, npz, keep_idx, chunk: int = REFERENCE_CHUNK):
    """Forward the frozen NPZ rows through the verified model (bc_offline math).

    Standardizes the kept-40 globals with the run's manifest mean/std, passes the
    schema-ordered entity/mask tensors through unnormalized, applies the model, and
    returns the tanh action as ``[N, 2]`` f64. Forwarding batch-1 (``chunk=1``)
    reproduces the sidecar's per-tick serving exactly, so any residual difference is
    an encode/serve discrepancy rather than a batch-kernel rounding artifact.
    """
    import numpy as np
    import torch

    g48 = np.asarray(npz["global_features"], dtype=np.float32)[keep_idx]
    g40 = g48[:, service._kept_indices]
    standardized = ((g40 - service._mean) / service._std).astype(np.float32)
    entities = {
        name: np.asarray(npz[f"entities_{name}"], dtype=np.float32)[keep_idx]
        for name in service._group_names
    }
    masks = {
        name: np.asarray(npz[f"mask_{name}"], dtype=np.float32)[keep_idx]
        for name in service._group_names
    }

    n = standardized.shape[0]
    out = np.empty((n, 2), dtype=np.float64)
    model = service._model
    with torch.no_grad():
        for start in range(0, n, chunk):
            end = min(start + chunk, n)
            g_t = torch.from_numpy(standardized[start:end])
            e_t = {name: torch.from_numpy(entities[name][start:end]) for name in service._group_names}
            m_t = {name: torch.from_numpy(masks[name][start:end]) for name in service._group_names}
            out[start:end] = model(g_t, e_t, m_t).numpy()
    return out


def iter_capture_payloads(events_path: Path) -> Iterator[dict[str, Any]]:
    """Stream ``combat_capture`` payloads from a run's events.jsonl (READ-ONLY)."""
    with open(events_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            if event.get("event") == "combat_capture":
                yield event["payload"]


def collect_raw_payloads(events_path: Path, needed: set[int]) -> dict[int, dict[str, Any]]:
    """Return ``{capture_seq: raw payload}`` for every needed seq found in the run."""
    found: dict[int, dict[str, Any]] = {}
    for payload in iter_capture_payloads(events_path):
        cseq = payload.get("capture_seq")
        if cseq is None:
            continue
        cseq = int(cseq)
        if cseq in needed and cseq not in found:
            found[cseq] = payload
            if len(found) == len(needed):
                break
    return found


# ---------------------------------------------------------------------------
# Split config
# ---------------------------------------------------------------------------
def load_validation_runs(split_config: Path) -> list[dict[str, str]]:
    import yaml

    data = yaml.safe_load(split_config.read_text(encoding="utf-8"))
    entries = data.get("validation") or []
    runs = []
    for entry in entries:
        runs.append(
            {
                "run_id": str(entry["run_id"]),
                "shard_file": str(entry.get("shard_file", f"{entry['run_id']}.npz")),
                "outcome": str(entry.get("outcome", "")),
                "last_wave": entry.get("last_wave"),
            }
        )
    return runs


# ---------------------------------------------------------------------------
# Per-run parity
# ---------------------------------------------------------------------------
def parity_for_run(
    service,
    client: SidecarClient,
    run_meta: dict[str, Any],
    dataset_dir: Path,
    runs_root: Path,
    seq_base: int,
    *,
    smoke_rows: int | None,
) -> dict[str, Any]:
    import numpy as np

    run_id = run_meta["run_id"]
    shard_path = dataset_dir / run_meta["shard_file"]
    events_path = runs_root / run_id / "events.jsonl"
    if not shard_path.is_file():
        raise ParitySetupError(f"shard missing: {shard_path}")
    if not events_path.is_file():
        raise ParitySetupError(f"events.jsonl missing (READ-ONLY source): {events_path}")

    with np.load(shard_path) as npz:
        valid = np.asarray(npz["valid"], dtype=bool)
        temporal = np.asarray(npz["temporal_valid"], dtype=bool)
        keep = valid & temporal
        keep_idx = np.nonzero(keep)[0]
        capture_seq = np.asarray(npz["capture_seq"], dtype=np.int64)
        wave = np.asarray(npz["wave"], dtype=np.int64)

        if smoke_rows is not None and keep_idx.size > smoke_rows:
            pick = np.linspace(0, keep_idx.size - 1, smoke_rows).round().astype(np.intp)
            keep_idx = keep_idx[np.unique(pick)]

        ref = reference_actions(service, npz, keep_idx)

    row_seq = capture_seq[keep_idx]
    row_wave = wave[keep_idx]
    needed = {int(s) for s in row_seq}
    raw = collect_raw_payloads(events_path, needed)

    max_abs_delta = 0.0
    sum_abs_delta = 0.0
    n_compared = 0
    nonfinite = 0
    sidecar_errors: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    worst: dict[str, Any] | None = None

    for i in range(keep_idx.size):
        cseq = int(row_seq[i])
        payload = raw.get(cseq)
        if payload is None:
            unmatched.append({"capture_seq": cseq, "reason": "no_raw_payload_in_events"})
            continue
        rax, ray = float(ref[i, 0]), float(ref[i, 1])
        reply = client.act(seq=seq_base + i, wave=int(row_wave[i]), payload=payload)
        kind = protocol.frame_type(reply)
        if kind == protocol.MSG_ERROR:
            sidecar_errors.append({"capture_seq": cseq, "reason": reply.get("reason")})
            continue
        if kind != protocol.MSG_ACTION:
            sidecar_errors.append({"capture_seq": cseq, "reason": f"unexpected_reply:{kind}"})
            continue
        sax, say = float(reply["ax"]), float(reply["ay"])
        finite = all(np.isfinite(v) for v in (rax, ray, sax, say))
        if not finite:
            nonfinite += 1
            continue
        dax, day = abs(sax - rax), abs(say - ray)
        delta = max(dax, day)
        sum_abs_delta += (dax + day) / 2.0
        n_compared += 1
        if delta > max_abs_delta:
            max_abs_delta = delta
            worst = {
                "capture_seq": cseq,
                "wave": int(row_wave[i]),
                "reference": [rax, ray],
                "sidecar": [sax, say],
                "abs_delta": [dax, day],
            }

    return {
        "run_id": run_id,
        "outcome": run_meta.get("outcome"),
        "last_wave": run_meta.get("last_wave"),
        "rows_selected": int(keep_idx.size),
        "rows_compared": int(n_compared),
        "rows_unmatched": len(unmatched),
        "sidecar_error_count": len(sidecar_errors),
        "nonfinite_count": int(nonfinite),
        "max_abs_delta": float(max_abs_delta),
        "mean_abs_delta": float(sum_abs_delta / n_compared) if n_compared else 0.0,
        "worst_tick": worst,
        "unmatched": unmatched[:50],
        "sidecar_errors": sidecar_errors[:50],
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def run_parity(
    *,
    registry: Path,
    split_config: Path,
    schema_path: Path,
    dataset_dir: Path,
    runs_root: Path,
    smoke: bool,
    port: int | None,
    log: Any = print,
) -> dict[str, Any]:
    import torch
    import yaml

    torch.set_num_threads(1)

    schema = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    source_capture_schema_hash = str(schema["source_capture_schema_hash"]).upper()
    schema_id = str(schema["schema_id"])
    control_hz = int(schema.get("control_hz", 20))

    log(f"[parity] loading + verifying artifact chain from {registry.name} ...")
    service = load_service(registry)
    identity = service.identity

    val_runs = load_validation_runs(split_config)
    if smoke:
        val_runs = val_runs[:SMOKE_RUNS]
    smoke_rows = SMOKE_ROWS_PER_RUN if smoke else None

    chosen_port = port or find_free_port()
    log(f"[parity] spawning sidecar on 127.0.0.1:{chosen_port} ...")
    proc = spawn_sidecar(registry, chosen_port, SIDECAR_LOG)
    client = SidecarClient(chosen_port)

    started = time.perf_counter()
    per_run: list[dict[str, Any]] = []
    hello_ack: dict[str, Any] | None = None
    try:
        client.connect(proc)
        hello_ack = client.handshake(
            capture_schema_id=schema_id,
            capture_schema_hash=source_capture_schema_hash,
            control_hz=control_hz,
            run_id="replay_parity_v1",
        )
        log(f"[parity] handshake ok - serving {hello_ack.get('registry_run_name')} "
            f"backend={hello_ack.get('backend')} pid={hello_ack.get('pid')}")

        seq_base = 1
        for run_meta in val_runs:
            log(f"[parity] run {run_meta['run_id']} ({run_meta.get('outcome')}) ...")
            result = parity_for_run(
                service, client, run_meta, dataset_dir, runs_root, seq_base,
                smoke_rows=smoke_rows,
            )
            per_run.append(result)
            seq_base += result["rows_selected"] + 1
            log(f"[parity]   compared={result['rows_compared']} "
                f"max|d|={result['max_abs_delta']:.3e} "
                f"errors={result['sidecar_error_count']} unmatched={result['rows_unmatched']}")
        client.bye()
    finally:
        client.close()
        kill_sidecar(proc)

    runtime_sec = time.perf_counter() - started

    # -- aggregate gates -----------------------------------------------------
    agg_max = max((r["max_abs_delta"] for r in per_run), default=0.0)
    total_compared = sum(r["rows_compared"] for r in per_run)
    total_selected = sum(r["rows_selected"] for r in per_run)
    total_unmatched = sum(r["rows_unmatched"] for r in per_run)
    total_errors = sum(r["sidecar_error_count"] for r in per_run)
    total_nonfinite = sum(r["nonfinite_count"] for r in per_run)

    gate_max = agg_max <= MAX_ABS_DELTA_GATE and total_compared > 0
    gate_finite = total_nonfinite == 0
    gate_no_error = total_errors == 0
    gate_coverage = total_unmatched == 0 and total_compared == (total_selected - total_unmatched)
    all_pass = gate_max and gate_finite and gate_no_error and gate_coverage

    gates = {
        "max_abs_delta": {
            "status": "PASS" if gate_max else "FAIL",
            "value": float(agg_max),
            "threshold": MAX_ABS_DELTA_GATE,
        },
        "finite": {
            "status": "PASS" if gate_finite else "FAIL",
            "nonfinite_count": int(total_nonfinite),
        },
        "no_sidecar_error": {
            "status": "PASS" if gate_no_error else "FAIL",
            "error_count": int(total_errors),
        },
        "coverage": {
            "status": "PASS" if gate_coverage else "FAIL",
            "rows_selected": int(total_selected),
            "rows_compared": int(total_compared),
            "rows_unmatched": int(total_unmatched),
        },
    }

    return {
        "report": "student_replay_parity_v1",
        "rung": 2,
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "smoke" if smoke else "full",
        "runtime_sec": round(runtime_sec, 2),
        "environment": _environment(),
        "registry": str(registry),
        "sidecar_identity": hello_ack,  # verbatim hello_ack block
        "service_identity": identity.log_block(),
        "gates": gates,
        "overall": "PASS" if all_pass else "FAIL",
        "aggregate": {
            "rows_selected": int(total_selected),
            "rows_compared": int(total_compared),
            "rows_unmatched": int(total_unmatched),
            "sidecar_error_count": int(total_errors),
            "nonfinite_count": int(total_nonfinite),
            "max_abs_delta": float(agg_max),
        },
        "runs": per_run,
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
        "processor": platform.processor(),
        "torch_num_threads": torch.get_num_threads(),
    }


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
def write_reports(payload: dict[str, Any]) -> None:
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    REPORT_MD.write_text(_render_md(payload), encoding="utf-8")


def _render_md(p: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Student replay parity — rung 2")
    lines.append("")
    lines.append(
        f"Generated {p['generated']} · mode **{p['mode']}** · runtime {p['runtime_sec']}s · "
        f"overall **{p['overall']}**."
    )
    lines.append("")
    lines.append(
        "Reference actions are the frozen `combat_obs_v1` NPZ rows forwarded through the "
        "verified model via the exact `bc_offline` path (CPU, float32, hash-verified "
        "normalization manifest, batch-1 to match the sidecar's per-tick serving). "
        "Sidecar actions are the same ticks re-encoded live from the RAW `events.jsonl` "
        "payloads (READ-ONLY) matched by `capture_seq`, served over protocol v1 on loopback."
    )
    lines.append("")

    lines.append("## Gates")
    lines.append("")
    lines.append("| gate | status | detail |")
    lines.append("|---|---|---|")
    g = p["gates"]
    lines.append(
        f"| max &#124;Δaction&#124; ≤ {g['max_abs_delta']['threshold']:.0e} | "
        f"{g['max_abs_delta']['status']} | max = {g['max_abs_delta']['value']:.3e} |"
    )
    lines.append(
        f"| zero NaN/Inf | {g['finite']['status']} | nonfinite = {g['finite']['nonfinite_count']} |"
    )
    lines.append(
        f"| zero sidecar errors | {g['no_sidecar_error']['status']} | "
        f"errors = {g['no_sidecar_error']['error_count']} |"
    )
    cov = g["coverage"]
    lines.append(
        f"| coverage (all val rows matched) | {cov['status']} | "
        f"compared {cov['rows_compared']}/{cov['rows_selected']}, unmatched {cov['rows_unmatched']} |"
    )
    lines.append("")

    agg = p["aggregate"]
    lines.append(
        f"Aggregate: {agg['rows_compared']} ticks compared, max |Δ| = "
        f"{agg['max_abs_delta']:.3e}, mean over runs. Runtime {p['runtime_sec']}s."
    )
    lines.append("")

    lines.append("## Sidecar identity (`hello_ack`, verbatim)")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(p["sidecar_identity"], indent=2, sort_keys=True))
    lines.append("```")
    lines.append("")

    lines.append("## Per-run")
    lines.append("")
    lines.append(
        "| run_id | outcome | selected | compared | max &#124;Δ&#124; | mean &#124;Δ&#124; | "
        "errors | unmatched |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in p["runs"]:
        lines.append(
            f"| {r['run_id']} | {r.get('outcome', '-')} | {r['rows_selected']} | "
            f"{r['rows_compared']} | {r['max_abs_delta']:.3e} | {r['mean_abs_delta']:.3e} | "
            f"{r['sidecar_error_count']} | {r['rows_unmatched']} |"
        )
    lines.append("")

    worst = [r["worst_tick"] for r in p["runs"] if r.get("worst_tick")]
    if worst:
        lines.append("## Worst tick per run")
        lines.append("")
        lines.append("| run | capture_seq | wave | reference | sidecar | abs Δ |")
        lines.append("|---|---|---|---|---|---|")
        for r in p["runs"]:
            w = r.get("worst_tick")
            if not w:
                continue
            lines.append(
                f"| {r['run_id']} | {w['capture_seq']} | {w['wave']} | "
                f"[{w['reference'][0]:.6f}, {w['reference'][1]:.6f}] | "
                f"[{w['sidecar'][0]:.6f}, {w['sidecar'][1]:.6f}] | "
                f"[{w['abs_delta'][0]:.2e}, {w['abs_delta'][1]:.2e}] |"
            )
        lines.append("")

    env = p["environment"]
    lines.append("## Environment")
    lines.append("")
    lines.append(
        f"- torch `{env['torch']}` · numpy `{env['numpy']}` · python `{env['python']}` · "
        f"threads {env['torch_num_threads']}"
    )
    lines.append(f"- {env['platform']} · {env['processor']}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rung 2 — offline replay parity for the student sidecar.")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--split-config", default=str(DEFAULT_SPLIT_CONFIG))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--dataset-dir", default=str(DEFAULT_DATASET_DIR))
    parser.add_argument("--runs-root", default=str(RUNS_ROOT))
    parser.add_argument("--port", type=int, default=None, help="sidecar port (default: OS-assigned free port)")
    parser.add_argument("--smoke", action="store_true", help="quick subset: 2 runs, 250 rows each")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        payload = run_parity(
            registry=Path(args.registry),
            split_config=Path(args.split_config),
            schema_path=Path(args.schema),
            dataset_dir=Path(args.dataset_dir),
            runs_root=Path(args.runs_root),
            smoke=args.smoke,
            port=args.port,
        )
    except ParitySetupError as exc:
        print(f"setup error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - unexpected setup fault
        print(f"unexpected setup error: {exc}", file=sys.stderr)
        return 2

    write_reports(payload)
    print(f"[parity] overall={payload['overall']} "
          f"max|d|={payload['aggregate']['max_abs_delta']:.3e} "
          f"compared={payload['aggregate']['rows_compared']} "
          f"errors={payload['aggregate']['sidecar_error_count']} "
          f"unmatched={payload['aggregate']['rows_unmatched']}")
    print(f"[parity] reports: {REPORT_JSON} | {REPORT_MD}")
    return 0 if payload["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
