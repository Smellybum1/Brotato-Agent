"""Non-interactive entry point for the WP2 M3 student-inference sidecar.

Loads and verifies the frozen bc_v1 artifact chain from a registry manifest,
then serves it on a loopback TCP socket over protocol v1
(``docs/IPC_PROTOCOL.md``). Deploys never happen while the game runs — this is
launched by the primary per the standing procedure.

Exit codes:
    0  clean shutdown (bye / signal / idle-exit after disconnect)
    1  usage / unexpected error
    2  artifact load or hash-verification failure

Usage:
    .venv/Scripts/python.exe scripts/run_student_sidecar.py \
        --registry models/registry/bc_v1_s1_full.json --port 51888
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from trainer.bridge.sidecar import (  # noqa: E402
    DEFAULT_IDLE_EXIT_SEC,
    DEFAULT_LOG_PATH,
    DEFAULT_PORT,
    OnnxModelService,
    ResidualProbeService,
    SidecarConfig,
    SidecarStartupError,
    StudentSidecar,
    TorchModelService,
)

DEFAULT_REGISTRY = REPO_ROOT / "models" / "registry" / "bc_v1_s1_full.json"
DEFAULT_ONNX_REGISTRY = REPO_ROOT / "models" / "registry" / "bc_v1_s1_full_onnx.json"
DEFAULT_SCHEMA = REPO_ROOT / "configs" / "wp2" / "observation_v1.yaml"
DEFAULT_THETA_MAX_DEG = 5.0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the bc_v1 student policy over loopback TCP.")
    parser.add_argument(
        "--mode",
        choices=("student", "residual-probe"),
        default="student",
        help="serving mode: 'student' (verified bc_v1 model) or 'residual-probe' "
        "(torch-free bounded angular perturbation of the teacher action; design §2)",
    )
    parser.add_argument(
        "--theta-max-deg",
        type=float,
        default=DEFAULT_THETA_MAX_DEG,
        help=f"residual-probe: half-width of the uniform angular delta in degrees "
        f"(default {DEFAULT_THETA_MAX_DEG})",
    )
    parser.add_argument(
        "--probe-seed",
        type=int,
        default=None,
        help="residual-probe: REQUIRED integer seed for the per-run delta stream",
    )
    parser.add_argument(
        "--schema",
        default=str(DEFAULT_SCHEMA),
        help="residual-probe: observation schema yaml providing the capture schema "
        "hash to pin at handshake (default: configs/wp2/observation_v1.yaml)",
    )
    parser.add_argument(
        "--registry",
        default=str(DEFAULT_REGISTRY),
        help="registry manifest path (default: models/registry/bc_v1_s1_full.json)",
    )
    parser.add_argument("--checkpoint", choices=("best", "last"), default="best")
    parser.add_argument(
        "--backend",
        choices=("torch", "onnx"),
        default="torch",
        help="inference backend (default torch — the qualified live path)",
    )
    parser.add_argument(
        "--onnx-registry",
        default=str(DEFAULT_ONNX_REGISTRY),
        help="ONNX registry manifest (used only with --backend onnx)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="bind host (loopback only)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"bind port (default {DEFAULT_PORT})")
    parser.add_argument(
        "--idle-exit-sec",
        type=float,
        default=DEFAULT_IDLE_EXIT_SEC,
        help="exit this many seconds after client disconnect with no reconnect",
    )
    parser.add_argument("--log-path", default=str(DEFAULT_LOG_PATH), help="JSONL sidecar log path")
    return parser.parse_args(argv)


def _load_probe_capture_schema(schema_path: Path) -> dict:
    """Read the observation schema yaml for the probe's capture-schema pin.

    Torch-free by design (residual-probe mode requires no torch and no registry):
    only the ``source_capture_schema_hash`` / ``schema_id`` are needed so the
    handshake presents the hash the live mod pins.
    """
    import yaml

    try:
        data = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SidecarStartupError(f"schema unreadable: {exc}") from exc
    if not isinstance(data, dict) or "source_capture_schema_hash" not in data:
        raise SidecarStartupError(f"schema missing source_capture_schema_hash: {schema_path}")
    return data


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.host not in ("127.0.0.1", "localhost"):
        print(f"error: refusing non-loopback bind host {args.host!r}", file=sys.stderr)
        return 1

    if args.mode == "residual-probe":
        if args.probe_seed is None:
            print("error: --probe-seed is required in residual-probe mode", file=sys.stderr)
            return 1
        try:
            schema = _load_probe_capture_schema(Path(args.schema))
            service = ResidualProbeService(
                theta_max_deg=args.theta_max_deg,
                seed=args.probe_seed,
                capture_schema_hash=str(schema["source_capture_schema_hash"]),
                schema_id=str(schema.get("schema_id", "combat_obs_v1")),
            )
        except SidecarStartupError as exc:
            print(f"startup error: {exc}", file=sys.stderr)
            return 2
    else:
        try:
            if args.backend == "onnx":
                service = OnnxModelService.from_registry(args.onnx_registry, checkpoint=args.checkpoint)
            else:
                service = TorchModelService.from_registry(args.registry, checkpoint=args.checkpoint)
        except SidecarStartupError as exc:
            print(f"startup error: {exc}", file=sys.stderr)
            return 2

    identity = service.identity
    print(
        f"[sidecar] serving {identity.registry_run_name} "
        f"(model {identity.model_sha256[:12]}, schema {identity.observation_schema_hash[:12]}) "
        f"on {args.host}:{args.port} backend={identity.backend}",
        file=sys.stderr,
    )

    config = SidecarConfig(
        host="127.0.0.1",
        port=args.port,
        idle_exit_sec=args.idle_exit_sec,
        log_path=Path(args.log_path),
    )
    sidecar = StudentSidecar(service, config)
    try:
        return sidecar.serve()
    except KeyboardInterrupt:
        sidecar.request_stop()
        return 0
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
