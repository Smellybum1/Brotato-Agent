"""WP2 Stage F validation ladder — rung 2: residual-probe offline replay check.

Spawns the torch-free residual-probe sidecar (fixed seed, theta_max = 5 deg) and
streams frozen ``combat_capture`` payloads from the v122 exact-20 teacher campaign
``events.jsonl`` runs (READ-ONLY) through it over protocol v1. For every reply it
verifies, against the sidecar's own per-act log (joined by ``seq``):

  * ``rotation_match``   — reply == rotate(teacher.action, logged delta_deg) to 1e-6;
  * ``magnitude``        — |reply| == |teacher.action| to 1e-6 (rotation is norm-safe);
  * ``zero_passthrough`` — every zero teacher vector passes through unchanged with
                           a ``None`` logged delta (no random draw);
  * ``delta_uniform``    — the sampled deltas fill Uniform(-5, +5): all in range and
                           mean / variance / KS statistic within uniform tolerances.

The ``events.jsonl`` runs are READ-ONLY; nothing is written there. The probe needs
no torch and no registry — only the capture-schema hash from the observation schema.

Exit codes: 0 all gates pass · 1 a gate failed · 2 setup error.

Usage:
    .venv/Scripts/python.exe scripts/wp2_residual_probe_replay_check.py
    .venv/Scripts/python.exe scripts/wp2_residual_probe_replay_check.py --smoke
"""
from __future__ import annotations

import argparse
import json
import math
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

DEFAULT_SCHEMA = REPO_ROOT / "configs" / "wp2" / "observation_v1.yaml"
V122_COLLECTION_REPORT = REPO_ROOT / "reports" / "wp2" / "v122_exact20_teacher_collection_report.json"
RUNS_ROOT = Path("C:/Users/moxhe/AppData/Roaming/Brotato/brotato_agent/runs")

REPORT_JSON = REPO_ROOT / "reports" / "wp2" / "residual_probe_replay_check.json"
REPORT_MD = REPO_ROOT / "reports" / "wp2" / "residual_probe_replay_check.md"
PROBE_LOG = REPO_ROOT / ".tmp" / "residual_probe_replay_log.jsonl"

THETA_MAX_DEG = 5.0
PROBE_SEED = 20260724
FULL_TARGET_PAYLOADS = 2500      # >= the required 2000, with margin
SMOKE_TARGET_PAYLOADS = 400
MATCH_TOL = 1e-6
SIDECAR_START_TIMEOUT_SEC = 60.0
SOCKET_TIMEOUT_SEC = 60.0


class ReplaySetupError(RuntimeError):
    """Raised on any sidecar / data setup failure (exit code 2)."""


# ---------------------------------------------------------------------------
# Sidecar spawn + minimal protocol client
# ---------------------------------------------------------------------------
def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def spawn_probe_sidecar(port: int, seed: int, log_path: Path) -> subprocess.Popen:
    """Launch ``run_student_sidecar.py --mode residual-probe`` on loopback."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "run_student_sidecar.py"),
        "--mode", "residual-probe",
        "--probe-seed", str(seed),
        "--theta-max-deg", str(THETA_MAX_DEG),
        "--schema", str(DEFAULT_SCHEMA),
        "--host", "127.0.0.1",
        "--port", str(port),
        "--idle-exit-sec", "3600",
        "--log-path", str(log_path),
    ]
    return subprocess.Popen(
        cmd, cwd=str(REPO_ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )


def kill_sidecar(proc: subprocess.Popen | None) -> None:
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


class ProbeClient:
    def __init__(self, port: int) -> None:
        self._port = port
        self._sock: socket.socket | None = None
        self._recv = None
        self.identity: dict[str, Any] | None = None

    def connect(self, proc: subprocess.Popen, timeout: float = SIDECAR_START_TIMEOUT_SEC) -> None:
        deadline = time.monotonic() + timeout
        last_err: Exception | None = None
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                out = proc.stdout.read() if proc.stdout else ""
                raise ReplaySetupError(f"sidecar exited early ({proc.returncode}); output:\n{out}")
            try:
                sock = socket.create_connection(("127.0.0.1", self._port), timeout=5.0)
                sock.settimeout(SOCKET_TIMEOUT_SEC)
                self._sock = sock
                self._recv = protocol.socket_recv(sock)
                return
            except OSError as exc:
                last_err = exc
                time.sleep(0.2)
        raise ReplaySetupError(f"could not connect to sidecar on {self._port}: {last_err}")

    def handshake(self, *, capture_schema_id: str, capture_schema_hash: str, control_hz: int) -> dict:
        self._send(protocol.build_hello(
            capture_schema_id=capture_schema_id, capture_schema_hash=capture_schema_hash,
            control_hz=control_hz, run_id="residual_probe_replay",
        ))
        reply = protocol.read_frame(self._recv)
        if protocol.frame_type(reply) != protocol.MSG_HELLO_ACK:
            raise ReplaySetupError(f"handshake rejected: {reply}")
        self.identity = reply
        return reply

    def act(self, *, seq: int, wave: int, payload: Mapping[str, Any]) -> dict:
        self._send(protocol.build_act(
            seq=seq, ts_ms=int(time.time() * 1000), wave=wave, payload=payload))
        return protocol.read_frame(self._recv)

    def bye(self) -> None:
        if self._sock is None:
            return
        try:
            self._send(protocol.build_bye(reason="replay_done"))
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
# Frozen payload source (READ-ONLY)
# ---------------------------------------------------------------------------
def load_v122_run_ids() -> list[str]:
    if not V122_COLLECTION_REPORT.is_file():
        raise ReplaySetupError(f"v122 collection report missing: {V122_COLLECTION_REPORT}")
    data = json.loads(V122_COLLECTION_REPORT.read_text(encoding="utf-8"))
    return [str(r["run_id"]) for r in data.get("results", [])]


def iter_capture_payloads(events_path: Path) -> Iterator[dict[str, Any]]:
    """Stream ``combat_capture`` payloads from a run's events.jsonl (READ-ONLY)."""
    with open(events_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or '"combat_capture"' not in line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("event") == "combat_capture":
                payload = event.get("payload")
                if isinstance(payload, dict):
                    yield payload


def iter_frozen_payloads(run_ids: list[str], target: int) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield up to ``target`` (run_id, payload) pairs across the frozen runs."""
    emitted = 0
    for run_id in run_ids:
        events_path = RUNS_ROOT / run_id / "events.jsonl"
        if not events_path.is_file():
            continue
        for payload in iter_capture_payloads(events_path):
            yield run_id, payload
            emitted += 1
            if emitted >= target:
                return


# ---------------------------------------------------------------------------
# Log join + verification
# ---------------------------------------------------------------------------
def read_probe_acts(log_path: Path) -> dict[int, dict[str, Any]]:
    """Return ``{seq: act log record}`` from the sidecar's per-act log."""
    acts: dict[int, dict[str, Any]] = {}
    if not log_path.is_file():
        return acts
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("event") == "act" and "seq" in rec:
            acts[int(rec["seq"])] = rec
    return acts


def _teacher_xy(payload: Mapping[str, Any]) -> tuple[float, float]:
    action = payload["teacher"]["action"]
    return float(action["x"]), float(action["y"])


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def run_check(*, smoke: bool, port: int | None, log: Any = print) -> dict[str, Any]:
    import numpy as np
    import yaml

    schema = yaml.safe_load(DEFAULT_SCHEMA.read_text(encoding="utf-8"))
    capture_schema_hash = str(schema["source_capture_schema_hash"]).upper()
    capture_schema_id = str(schema.get("source_capture_schema_id", "combat_capture_v2"))
    control_hz = int(schema.get("control_hz", 20))

    run_ids = load_v122_run_ids()
    target = SMOKE_TARGET_PAYLOADS if smoke else FULL_TARGET_PAYLOADS

    chosen_port = port or find_free_port()
    # Fresh log per invocation so the seq->delta join is unambiguous.
    if PROBE_LOG.exists():
        PROBE_LOG.unlink()
    log(f"[probe-replay] spawning residual-probe sidecar on 127.0.0.1:{chosen_port} "
        f"(seed={PROBE_SEED}, theta_max={THETA_MAX_DEG}) ...")
    proc = spawn_probe_sidecar(chosen_port, PROBE_SEED, PROBE_LOG)
    client = ProbeClient(chosen_port)

    started = time.perf_counter()
    replies: dict[int, dict[str, Any]] = {}   # seq -> {ax, ay, tx, ty, wave, run_id}
    sidecar_errors: list[dict[str, Any]] = []
    hello_ack: dict[str, Any] | None = None
    try:
        client.connect(proc)
        hello_ack = client.handshake(
            capture_schema_id=capture_schema_id,
            capture_schema_hash=capture_schema_hash,
            control_hz=control_hz,
        )
        log(f"[probe-replay] handshake ok - {hello_ack.get('registry_run_name')} "
            f"backend={hello_ack.get('backend')} model={hello_ack.get('model_sha256')}")

        seq = 0
        for run_id, payload in iter_frozen_payloads(run_ids, target):
            try:
                tx, ty = _teacher_xy(payload)
            except (KeyError, TypeError, ValueError):
                continue  # payload lacks a teacher.action; skip (not probe-eligible)
            seq += 1
            wave = int(payload.get("wave", 0) or 0)
            reply = client.act(seq=seq, wave=wave, payload=payload)
            kind = protocol.frame_type(reply)
            if kind != protocol.MSG_ACTION:
                sidecar_errors.append({"seq": seq, "reply": reply})
                continue
            replies[seq] = {
                "ax": float(reply["ax"]), "ay": float(reply["ay"]),
                "tx": tx, "ty": ty, "wave": wave, "run_id": run_id,
            }
        client.bye()
    finally:
        client.close()
        kill_sidecar(proc)

    runtime_sec = time.perf_counter() - started
    acts = read_probe_acts(PROBE_LOG)

    # -- verify every reply against the logged delta -------------------------
    max_rot_err = 0.0
    max_mag_err = 0.0
    worst_rot: dict[str, Any] | None = None
    deltas: list[float] = []
    zero_count = 0
    zero_passthrough_ok = True
    unmatched_log = 0
    n_verified = 0

    for seq, r in replies.items():
        rec = acts.get(seq)
        if rec is None:
            unmatched_log += 1
            continue
        tx, ty, ax, ay = r["tx"], r["ty"], r["ax"], r["ay"]
        n_verified += 1
        tmag = math.hypot(tx, ty)
        if tmag == 0.0:
            zero_count += 1
            # Passthrough: reply unchanged, logged delta None, no draw.
            if not (ax == tx and ay == ty and rec.get("delta_deg") is None):
                zero_passthrough_ok = False
            continue
        delta_deg = rec.get("delta_deg")
        if delta_deg is None:
            zero_passthrough_ok = False  # non-zero teacher must have a delta
            continue
        deltas.append(float(delta_deg))
        theta = math.radians(float(delta_deg))
        ex = tx * math.cos(theta) - ty * math.sin(theta)
        ey = tx * math.sin(theta) + ty * math.cos(theta)
        rot_err = max(abs(ax - ex), abs(ay - ey))
        mag_err = abs(math.hypot(ax, ay) - tmag)
        if rot_err > max_rot_err:
            max_rot_err = rot_err
            worst_rot = {
                "seq": seq, "wave": r["wave"], "delta_deg": float(delta_deg),
                "teacher": [tx, ty], "reply": [ax, ay], "expected": [ex, ey],
                "rot_err": rot_err,
            }
        if mag_err > max_mag_err:
            max_mag_err = mag_err

    # -- delta distribution (uniform on [-theta, +theta]) --------------------
    darr = np.asarray(deltas, dtype=np.float64)
    n_delta = int(darr.size)
    if n_delta:
        d_mean = float(darr.mean())
        d_var = float(darr.var())
        d_min = float(darr.min())
        d_max = float(darr.max())
        # KS statistic vs Uniform(-theta, +theta).
        s = np.sort(darr)
        cdf_emp = (np.arange(1, n_delta + 1)) / n_delta
        cdf_uni = (s + THETA_MAX_DEG) / (2.0 * THETA_MAX_DEG)
        ks = float(np.max(np.abs(cdf_emp - cdf_uni)))
    else:
        d_mean = d_var = d_min = d_max = ks = 0.0

    expected_var = (2.0 * THETA_MAX_DEG) ** 2 / 12.0  # = 8.3333 for theta=5
    # Tolerances scale with sample size; loose enough to avoid flakiness, tight
    # enough to catch a mis-parameterized or non-uniform generator.
    mean_tol = 0.35
    var_tol = 1.2
    ks_tol = 0.06 if n_delta >= 1000 else 0.12
    in_range = d_min >= -THETA_MAX_DEG - 1e-9 and d_max <= THETA_MAX_DEG + 1e-9
    dist_ok = bool(
        n_delta > 0 and in_range
        and abs(d_mean) <= mean_tol
        and abs(d_var - expected_var) <= var_tol
        and ks <= ks_tol
    )

    gate_rotation = n_verified > 0 and max_rot_err <= MATCH_TOL
    gate_magnitude = n_verified > 0 and max_mag_err <= MATCH_TOL
    gate_zero = zero_passthrough_ok
    gate_dist = dist_ok
    gate_errors = len(sidecar_errors) == 0 and unmatched_log == 0
    all_pass = gate_rotation and gate_magnitude and gate_zero and gate_dist and gate_errors

    gates = {
        "rotation_match": {
            "status": "PASS" if gate_rotation else "FAIL",
            "max_rot_err": max_rot_err, "threshold": MATCH_TOL,
        },
        "magnitude_preserved": {
            "status": "PASS" if gate_magnitude else "FAIL",
            "max_mag_err": max_mag_err, "threshold": MATCH_TOL,
        },
        "zero_passthrough": {
            "status": "PASS" if gate_zero else "FAIL",
            "zero_vector_count": zero_count,
        },
        "delta_uniform": {
            "status": "PASS" if gate_dist else "FAIL",
            "n": n_delta, "mean": d_mean, "var": d_var, "expected_var": expected_var,
            "min": d_min, "max": d_max, "ks": ks,
            "tolerances": {"mean": mean_tol, "var": var_tol, "ks": ks_tol},
        },
        "no_errors": {
            "status": "PASS" if gate_errors else "FAIL",
            "sidecar_error_count": len(sidecar_errors),
            "unmatched_log_count": unmatched_log,
        },
    }

    return {
        "report": "residual_probe_replay_check",
        "rung": 2,
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "smoke" if smoke else "full",
        "runtime_sec": round(runtime_sec, 2),
        "probe_seed": PROBE_SEED,
        "theta_max_deg": THETA_MAX_DEG,
        "sidecar_identity": hello_ack,
        "source": {
            "runs_root": str(RUNS_ROOT),
            "v122_run_ids": run_ids,
            "target_payloads": target,
        },
        "counts": {
            "verified": n_verified,
            "zero_vector": zero_count,
            "delta_samples": n_delta,
            "sidecar_errors": len(sidecar_errors),
            "unmatched_log": unmatched_log,
        },
        "worst_rotation_tick": worst_rot,
        "sidecar_errors": sidecar_errors[:20],
        "gates": gates,
        "overall": "PASS" if all_pass else "FAIL",
    }


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
def write_reports(payload: dict[str, Any]) -> None:
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    REPORT_MD.write_text(_render_md(payload), encoding="utf-8")


def _render_md(p: dict[str, Any]) -> str:
    g = p["gates"]
    c = p["counts"]
    lines = [
        "# Residual-probe replay check - rung 2",
        "",
        f"Generated {p['generated']} - mode **{p['mode']}** - runtime {p['runtime_sec']}s - "
        f"overall **{p['overall']}**.",
        "",
        f"Seed {p['probe_seed']}, theta_max {p['theta_max_deg']} deg. "
        f"{c['verified']} ticks verified ({c['delta_samples']} perturbed, "
        f"{c['zero_vector']} zero-vector passthrough) against the sidecar per-act log.",
        "",
        "Frozen `combat_capture` payloads from the v122 exact-20 teacher campaign "
        "`events.jsonl` runs (READ-ONLY) streamed through the torch-free residual-probe "
        "sidecar over protocol v1 on loopback.",
        "",
        "## Gates",
        "",
        "| gate | status | detail |",
        "|---|---|---|",
        f"| rotation match <= {g['rotation_match']['threshold']:.0e} | "
        f"{g['rotation_match']['status']} | max err = {g['rotation_match']['max_rot_err']:.3e} |",
        f"| magnitude preserved <= {g['magnitude_preserved']['threshold']:.0e} | "
        f"{g['magnitude_preserved']['status']} | max err = {g['magnitude_preserved']['max_mag_err']:.3e} |",
        f"| zero-vector passthrough | {g['zero_passthrough']['status']} | "
        f"count = {g['zero_passthrough']['zero_vector_count']} |",
        f"| delta ~ Uniform(-{p['theta_max_deg']:.0f}, +{p['theta_max_deg']:.0f}) | "
        f"{g['delta_uniform']['status']} | n={g['delta_uniform']['n']}, "
        f"mean={g['delta_uniform']['mean']:.4f}, var={g['delta_uniform']['var']:.4f} "
        f"(exp {g['delta_uniform']['expected_var']:.4f}), "
        f"range=[{g['delta_uniform']['min']:.4f}, {g['delta_uniform']['max']:.4f}], "
        f"KS={g['delta_uniform']['ks']:.4f} |",
        f"| no errors / all logged | {g['no_errors']['status']} | "
        f"errors={g['no_errors']['sidecar_error_count']}, "
        f"unmatched={g['no_errors']['unmatched_log_count']} |",
        "",
        "## Sidecar identity (`hello_ack`, verbatim)",
        "",
        "```json",
        json.dumps(p["sidecar_identity"], indent=2, sort_keys=True),
        "```",
        "",
    ]
    if p.get("worst_rotation_tick"):
        w = p["worst_rotation_tick"]
        lines += [
            "## Worst rotation tick",
            "",
            f"- seq {w['seq']} wave {w['wave']} delta {w['delta_deg']:.6f} deg",
            f"- teacher [{w['teacher'][0]:.6f}, {w['teacher'][1]:.6f}] -> "
            f"reply [{w['reply'][0]:.6f}, {w['reply'][1]:.6f}] "
            f"(expected [{w['expected'][0]:.6f}, {w['expected'][1]:.6f}], err {w['rot_err']:.3e})",
            "",
        ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rung 2 - residual-probe offline replay check.")
    parser.add_argument("--port", type=int, default=None, help="sidecar port (default: OS-assigned)")
    parser.add_argument("--smoke", action="store_true", help=f"quick subset: {SMOKE_TARGET_PAYLOADS} payloads")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        payload = run_check(smoke=args.smoke, port=args.port)
    except ReplaySetupError as exc:
        print(f"setup error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - unexpected setup fault
        print(f"unexpected setup error: {exc}", file=sys.stderr)
        return 2

    write_reports(payload)
    g = payload["gates"]
    print(f"[probe-replay] overall={payload['overall']} "
          f"rot_err={g['rotation_match']['max_rot_err']:.3e} "
          f"mag_err={g['magnitude_preserved']['max_mag_err']:.3e} "
          f"delta_n={g['delta_uniform']['n']} ks={g['delta_uniform']['ks']:.4f} "
          f"zero={g['zero_passthrough']['zero_vector_count']}")
    print(f"[probe-replay] reports: {REPORT_JSON} | {REPORT_MD}")
    return 0 if payload["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
