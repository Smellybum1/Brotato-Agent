"""Single-client loopback sidecar serving the frozen bc_v1 student policy.

The server (architecture note §3.3) binds ``127.0.0.1`` only, accepts one client
at a time, verifies the peer is loopback, performs the protocol-v1 handshake, and
answers ``act`` requests strictly FIFO through an injectable
:class:`ModelService`. The real service — :class:`TorchModelService` — wires the
verified artifact chain (registry manifest -> ``best.pt`` sha256 -> CPU eval
model -> hash-verified normalization manifest -> observation schema ->
``bc_input_v1``) and reproduces the ``bc_offline`` inference math exactly:

    encode_capture(payload) -> select kept-40 globals by name -> (x-mean)/std
    -> [1, cap, 15] / [1, cap] entity+mask tensors in group order -> forward
    -> tanh action in [-1, 1].

None of the normalization / masking / encoding logic is duplicated: it is reused
verbatim from :mod:`trainer.evaluation.bc_offline`,
:mod:`trainer.observation.encoder_v1`, and :mod:`trainer.data.bc_dataset`.

The service is injectable behind the :class:`ModelService` interface so the
serving loop can be unit-tested with a fake predictor and no torch artifacts.
"""
from __future__ import annotations

import abc
import json
import math
import os
import signal
import socket
import threading
import time
from collections import deque
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from trainer.bridge import protocol
from trainer.bridge.protocol import (
    ConnectionClosed,
    PROTOCOL_VERSION,
    ProtocolError,
    frame_type,
)

LOOPBACK_HOSTS = frozenset({"127.0.0.1"})
#: Backend identity string for the ONNX Runtime CPU serving path (packet §14.2).
BACKEND_ONNX_CPU = "onnxruntime-cpu"
DEFAULT_PORT = 51888
DEFAULT_IDLE_EXIT_SEC = 120.0
DEFAULT_LOG_PATH = Path(".tmp") / "student_sidecar_log.jsonl"
DEFAULT_STATS_WINDOW = 512
DEFAULT_ACCEPT_TIMEOUT = 1.0
DEFAULT_STATS_LOG_INTERVAL_SEC = 30.0


class SidecarStartupError(RuntimeError):
    """Raised when the artifact chain cannot be loaded/verified (exit code 2)."""


# ---------------------------------------------------------------------------
# Identity + model service interface
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ServiceIdentity:
    """Everything the sidecar must expose about the artifacts it is serving.

    The first block is echoed into ``hello_ack``; ``source_capture_schema_hash``
    and ``model_sha256`` additionally gate the handshake against the mod's pins.
    """

    schema_id: str
    observation_schema_hash: str
    input_config_sha256: str
    model_sha256: str
    normalization_sha256: str
    registry_run_name: str
    source_capture_schema_hash: str
    backend: str = protocol.BACKEND_TORCH_CPU

    def hello_ack(self, pid: int) -> dict[str, Any]:
        return protocol.build_hello_ack(
            schema_id=self.schema_id,
            observation_schema_hash=self.observation_schema_hash,
            input_config_sha256=self.input_config_sha256,
            model_sha256=self.model_sha256,
            normalization_sha256=self.normalization_sha256,
            registry_run_name=self.registry_run_name,
            pid=pid,
            backend=self.backend,
        )

    def log_block(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "observation_schema_hash": self.observation_schema_hash,
            "input_config_sha256": self.input_config_sha256,
            "model_sha256": self.model_sha256,
            "normalization_sha256": self.normalization_sha256,
            "registry_run_name": self.registry_run_name,
            "source_capture_schema_hash": self.source_capture_schema_hash,
            "backend": self.backend,
        }


class ModelService(abc.ABC):
    """The inference interface the serving loop depends on.

    Implementations must expose a static :attr:`identity` and a pure
    :meth:`predict` that returns ``(ax, ay, model_ms)`` or raises on any encode /
    inference fault (the loop converts the exception into an ``error`` reply).
    """

    @property
    @abc.abstractmethod
    def identity(self) -> ServiceIdentity:
        ...

    @abc.abstractmethod
    def predict(self, payload: Mapping[str, Any]) -> tuple[float, float, float]:
        """Return ``(ax, ay, model_ms)`` for one raw capture payload."""


# ---------------------------------------------------------------------------
# Shared preprocessing (encode -> kept-40 -> standardize -> entity/mask arrays)
# ---------------------------------------------------------------------------
def _encode_inputs(
    payload: Mapping[str, Any],
    schema: dict[str, Any],
    kept_indices: Any,
    mean: Any,
    std: Any,
    group_names: tuple[str, ...],
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    """Encode one raw capture payload into model-ready numpy inputs.

    Reproduces the ``bc_offline`` inference preprocessing exactly and is the
    SINGLE source of that math for both serving backends:

        encode_capture -> 48 globals -> select kept-40 by index -> (x-mean)/std
        (globals only) -> per-group entity ``[cap, 15]`` + mask ``[cap]`` f32.

    Returns ``(standardized_globals [40] f32, entities{name->[cap,15] f32},
    masks{name->[cap] f32})``. Entities/masks pass through unnormalized — they
    are bounded by construction and standardizing padded rows would break their
    provable inertness.
    """
    import numpy as np

    from trainer.observation import encoder_v1

    obs = encoder_v1.encode_capture(dict(payload), schema)

    globals48 = np.asarray(obs.global_features, dtype=np.float32)
    globals40 = globals48[kept_indices]
    standardized = ((globals40 - mean) / std).astype(np.float32)
    entities = {
        name: np.asarray(obs.entities[name], dtype=np.float32) for name in group_names
    }
    masks = {
        name: np.asarray(obs.masks[name], dtype=np.float32) for name in group_names
    }
    return standardized, entities, masks


# ---------------------------------------------------------------------------
# Real torch-CPU service (verified artifact chain)
# ---------------------------------------------------------------------------
class TorchModelService(ModelService):
    """Serves ``best.pt`` on CPU, reproducing the ``bc_offline`` inference math."""

    def __init__(
        self,
        *,
        model: Any,
        schema: dict[str, Any],
        kept_indices: Any,
        mean: Any,
        std: Any,
        group_names: tuple[str, ...],
        identity: ServiceIdentity,
    ) -> None:
        self._model = model
        self._schema = schema
        self._kept_indices = kept_indices
        self._mean = mean
        self._std = std
        self._group_names = group_names
        self._identity = identity

    @property
    def identity(self) -> ServiceIdentity:
        return self._identity

    @classmethod
    def from_registry(
        cls, registry_path: str | Path, *, checkpoint: str = "best"
    ) -> "TorchModelService":
        """Load + verify the full artifact chain. Any mismatch => SidecarStartupError."""
        # Torch/numpy imports are deferred so the pure serving loop and its unit
        # tests never pay the import cost or require the artifacts.
        import numpy as np
        import torch
        import yaml

        from trainer.data.bc_dataset import _resolve_indices
        from trainer.evaluation.bc_offline import (
            BCOfflineEvalError,
            build_policy_config_from_registry,
            load_normalization_from_manifest,
            load_registry,
            verify_sha256,
        )
        from trainer.imitation.bc_training import _sha256_file, load_checkpoint
        from trainer.models.bc_policy_v1 import BCPolicyV1
        from trainer.observation import encoder_v1
        from trainer.observation.encoder_v1 import ObservationError

        try:
            registry = load_registry(registry_path)
            resolved = registry["resolved_config"]

            # 1. checkpoint sha256 (verified before any torch.load).
            ckpt_entry = registry["checkpoints"].get(checkpoint)
            if not isinstance(ckpt_entry, dict) or "path" not in ckpt_entry or "sha256" not in ckpt_entry:
                raise SidecarStartupError(f"registry has no {checkpoint!r} checkpoint entry")
            ckpt_path = Path(ckpt_entry["path"])
            model_sha = verify_sha256(ckpt_path, ckpt_entry["sha256"], f"{checkpoint} checkpoint")

            # 2. observation schema; file hash must equal registry schema_hash.
            schema = encoder_v1.load_schema(Path(resolved["schema"]))
            schema_hash = str(schema["_schema_hash"]).upper()
            if schema_hash != str(registry["schema_hash"]).upper():
                raise SidecarStartupError(
                    f"schema hash mismatch: file {schema_hash} != registry {registry['schema_hash']}"
                )

            # 3. input config -> kept-40 indices by name; sha256 for hello_ack.
            input_config_path = Path(resolved["input_config"])
            input_config = yaml.safe_load(input_config_path.read_text(encoding="utf-8"))
            if not isinstance(input_config, dict):
                raise SidecarStartupError(f"input config is not a mapping: {input_config_path}")
            names48 = [str(name) for name in schema["global_features"]]
            excluded = [str(n) for n in input_config.get("excluded_global_features", [])]
            labels = [str(n) for n in input_config.get("label_features", [])]
            kept_indices, kept_names, _ = _resolve_indices(names48, excluded, labels)
            input_config_sha256 = _sha256_file(input_config_path)

            # 4. model reconstruction + checkpoint load (CPU, eval, 1 thread).
            policy_config = build_policy_config_from_registry(resolved, kept_names)
            model = BCPolicyV1(policy_config)
            load_checkpoint(ckpt_path, model)
            model.to("cpu").eval()
            torch.set_num_threads(1)

            # 5. normalization manifest from the checkpoint dir; hash-verified.
            norm_manifest_path = ckpt_path.parent / "normalization_manifest.json"
            normalization = load_normalization_from_manifest(
                norm_manifest_path, registry["normalization_manifest_hash"], kept_names
            )

            group_names = tuple(spec.name for spec in policy_config.group_specs)
            kept_arr = np.asarray(kept_indices, dtype=np.intp)
            mean = np.asarray(normalization.mean, dtype=np.float32)
            std = np.asarray(normalization.std, dtype=np.float32)
        except (BCOfflineEvalError, ObservationError, KeyError, OSError, ValueError) as exc:
            raise SidecarStartupError(str(exc)) from exc

        identity = ServiceIdentity(
            schema_id=str(schema["schema_id"]),
            observation_schema_hash=schema_hash,
            input_config_sha256=input_config_sha256,
            model_sha256=model_sha,
            normalization_sha256=str(registry["normalization_manifest_hash"]).upper(),
            registry_run_name=str(registry["run_name"]),
            source_capture_schema_hash=str(schema["source_capture_schema_hash"]).upper()
            if schema.get("source_capture_schema_hash")
            else str(schema.get("source_capture_schema_hash")),
        )
        return cls(
            model=model,
            schema=schema,
            kept_indices=kept_arr,
            mean=mean,
            std=std,
            group_names=group_names,
            identity=identity,
        )

    def predict(self, payload: Mapping[str, Any]) -> tuple[float, float, float]:
        import torch

        standardized, ent_arrays, mask_arrays = _encode_inputs(
            payload, self._schema, self._kept_indices, self._mean, self._std, self._group_names
        )

        globals_t = torch.from_numpy(standardized).unsqueeze(0)  # [1, 40]
        entities = {
            name: torch.from_numpy(ent_arrays[name]).unsqueeze(0)
            for name in self._group_names
        }
        masks = {
            name: torch.from_numpy(mask_arrays[name]).unsqueeze(0)
            for name in self._group_names
        }

        start = time.perf_counter()
        with torch.no_grad():
            out = self._model(globals_t, entities, masks)
        model_ms = (time.perf_counter() - start) * 1000.0
        return float(out[0, 0].item()), float(out[0, 1].item()), model_ms


# ---------------------------------------------------------------------------
# ONNX Runtime CPU service (verified onnx manifest + parent linkage)
# ---------------------------------------------------------------------------
class OnnxModelService(ModelService):
    """Serves the exported ONNX graph via ONNX Runtime (CPU), sharing the exact
    ``_encode_inputs`` preprocessing with :class:`TorchModelService`.

    The parent torch artifact chain is loaded + verified to obtain the identical
    schema / kept-index / normalization / group-order preprocessing and to prove
    the ONNX manifest's ``parent_model_sha256`` matches the parent registry's
    verified ``best.pt`` sha256 (the ONNX graph was exported from that exact
    checkpoint). ``identity.model_sha256`` is the ONNX file hash and the backend
    string is ``onnxruntime-cpu``.
    """

    def __init__(
        self,
        *,
        session: Any,
        schema: dict[str, Any],
        kept_indices: Any,
        mean: Any,
        std: Any,
        group_names: tuple[str, ...],
        input_names: list[str],
        output_name: str,
        identity: ServiceIdentity,
    ) -> None:
        self._session = session
        self._schema = schema
        self._kept_indices = kept_indices
        self._mean = mean
        self._std = std
        self._group_names = group_names
        self._input_names = input_names
        self._output_name = output_name
        self._identity = identity

    @property
    def identity(self) -> ServiceIdentity:
        return self._identity

    @classmethod
    def from_registry(
        cls, onnx_registry_path: str | Path, *, checkpoint: str = "best"
    ) -> "OnnxModelService":
        """Load + verify the ONNX manifest, parent linkage, and build an ORT session."""
        import numpy as np
        import onnxruntime as ort

        from trainer.export.onnx_export import input_names_for
        from trainer.imitation.bc_training import _sha256_file

        onnx_registry_path = Path(onnx_registry_path)
        try:
            manifest = json.loads(onnx_registry_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise SidecarStartupError(f"onnx registry unreadable: {exc}") from exc
        if not isinstance(manifest, dict):
            raise SidecarStartupError("onnx registry is not a JSON object")

        for key in ("onnx_path", "onnx_sha256", "parent_registry", "parent_model_sha256"):
            if key not in manifest:
                raise SidecarStartupError(f"onnx registry missing required key {key!r}")

        onnx_path = Path(manifest["onnx_path"])
        if not onnx_path.is_file():
            raise SidecarStartupError(f"onnx file missing: {onnx_path}")
        onnx_sha = _sha256_file(onnx_path)
        if onnx_sha != str(manifest["onnx_sha256"]).upper():
            raise SidecarStartupError(
                f"onnx sha256 mismatch: file {onnx_sha} != manifest {manifest['onnx_sha256']}"
            )

        # Parent linkage: load + verify the parent torch chain (verifies best.pt
        # sha256) and require the manifest's parent_model_sha256 to equal it.
        parent_registry = Path(manifest["parent_registry"])
        if not parent_registry.is_absolute() and not parent_registry.is_file():
            parent_registry = onnx_registry_path.parent / manifest["parent_registry"]
        parent = TorchModelService.from_registry(parent_registry, checkpoint=checkpoint)
        parent_sha = parent.identity.model_sha256
        if str(manifest["parent_model_sha256"]).upper() != str(parent_sha).upper():
            raise SidecarStartupError(
                f"onnx parent_model_sha256 {manifest['parent_model_sha256']} != "
                f"parent registry best.pt sha {parent_sha}"
            )

        group_names = parent._group_names
        expected_inputs = input_names_for(group_names)
        input_names = [str(n) for n in manifest.get("input_names", expected_inputs)]
        output_name = str(manifest.get("output_name", "action"))

        try:
            so = ort.SessionOptions()
            so.intra_op_num_threads = 1
            so.inter_op_num_threads = 1
            session = ort.InferenceSession(
                str(onnx_path), sess_options=so, providers=["CPUExecutionProvider"]
            )
        except Exception as exc:
            raise SidecarStartupError(f"onnxruntime could not load {onnx_path}: {exc}") from exc

        session_inputs = [i.name for i in session.get_inputs()]
        if session_inputs != input_names or input_names != expected_inputs:
            raise SidecarStartupError(
                f"onnx input names {session_inputs} disagree with manifest {input_names} "
                f"or expected {expected_inputs}"
            )
        session_outputs = [o.name for o in session.get_outputs()]
        if session_outputs != [output_name]:
            raise SidecarStartupError(
                f"onnx output names {session_outputs} != expected [{output_name!r}]"
            )

        identity = replace(parent.identity, model_sha256=onnx_sha, backend=BACKEND_ONNX_CPU)
        return cls(
            session=session,
            schema=parent._schema,
            kept_indices=np.asarray(parent._kept_indices, dtype=np.intp),
            mean=np.asarray(parent._mean, dtype=np.float32),
            std=np.asarray(parent._std, dtype=np.float32),
            group_names=group_names,
            input_names=input_names,
            output_name=output_name,
            identity=identity,
        )

    def predict(self, payload: Mapping[str, Any]) -> tuple[float, float, float]:
        import numpy as np

        standardized, ent_arrays, mask_arrays = _encode_inputs(
            payload, self._schema, self._kept_indices, self._mean, self._std, self._group_names
        )

        ort_inputs: dict[str, Any] = {
            "globals": np.ascontiguousarray(standardized[None, :], dtype=np.float32)
        }
        for name in self._group_names:
            ort_inputs[f"ent_{name}"] = np.ascontiguousarray(
                ent_arrays[name][None, ...], dtype=np.float32
            )
            ort_inputs[f"mask_{name}"] = np.ascontiguousarray(
                mask_arrays[name][None, ...], dtype=np.float32
            )

        start = time.perf_counter()
        out = self._session.run([self._output_name], ort_inputs)[0]  # [1, 2]
        model_ms = (time.perf_counter() - start) * 1000.0
        return float(out[0, 0]), float(out[0, 1]), model_ms


# ---------------------------------------------------------------------------
# Rolling latency / health stats
# ---------------------------------------------------------------------------
class LatencyStats:
    """Served/error counters plus a bounded model-latency window (p50/p99)."""

    def __init__(self, window: int = DEFAULT_STATS_WINDOW) -> None:
        self._model_ms: deque[float] = deque(maxlen=max(1, int(window)))
        self.served = 0
        self.errors = 0

    def record(self, model_ms: float) -> None:
        self.served += 1
        self._model_ms.append(float(model_ms))

    def record_error(self) -> None:
        self.errors += 1

    @staticmethod
    def _percentile(values: list[float], pct: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        if len(ordered) == 1:
            return ordered[0]
        rank = pct / 100.0 * (len(ordered) - 1)
        low = int(math.floor(rank))
        high = int(math.ceil(rank))
        if low == high:
            return ordered[low]
        frac = rank - low
        return ordered[low] * (1.0 - frac) + ordered[high] * frac

    def snapshot(self) -> dict[str, float]:
        window = list(self._model_ms)
        return {
            "served": self.served,
            "errors": self.errors,
            "model_ms_p50": self._percentile(window, 50.0),
            "model_ms_p99": self._percentile(window, 99.0),
            "window": len(window),
        }


# ---------------------------------------------------------------------------
# Sidecar server
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SidecarConfig:
    """Runtime knobs for :class:`StudentSidecar`."""

    host: str = "127.0.0.1"
    port: int = DEFAULT_PORT
    idle_exit_sec: float = DEFAULT_IDLE_EXIT_SEC
    log_path: Path = DEFAULT_LOG_PATH
    stats_window: int = DEFAULT_STATS_WINDOW
    accept_timeout: float = DEFAULT_ACCEPT_TIMEOUT
    stats_log_interval_sec: float = DEFAULT_STATS_LOG_INTERVAL_SEC


# Connection outcomes.
_OUTCOME_BYE = "bye"
_OUTCOME_DISCONNECT = "disconnect"
_OUTCOME_PROTOCOL_ERROR = "protocol_error"


class StudentSidecar:
    """Loopback TCP server serving a :class:`ModelService` over protocol v1."""

    def __init__(
        self,
        service: ModelService,
        config: SidecarConfig | None = None,
        *,
        install_signal_handlers: bool = True,
    ) -> None:
        self._service = service
        self._config = config or SidecarConfig()
        self._install_signal_handlers = install_signal_handlers
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._stats = LatencyStats(self._config.stats_window)
        self._log_handle: Any = None
        self._last_stats_log = 0.0
        self.bound_port: int | None = None

    # -- lifecycle ----------------------------------------------------------
    @property
    def ready(self) -> threading.Event:
        """Set once the listening socket is bound; exposes :attr:`bound_port`."""
        return self._ready

    def request_stop(self) -> None:
        """Ask the serve loop to exit at the next accept/recv boundary."""
        self._stop.set()

    def serve(self) -> int:
        """Run the accept/serve loop until shutdown. Returns process exit code."""
        self._open_log()
        self._log_event("startup", pid=os.getpid(), **self._service.identity.log_block())
        if self._install_signal_handlers:
            self._install_signals()

        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener.bind((self._config.host, self._config.port))
            listener.listen(1)
            listener.settimeout(self._config.accept_timeout)
            self.bound_port = listener.getsockname()[1]
            self._ready.set()
            self._log_event("listening", host=self._config.host, port=self.bound_port)

            had_client = False
            last_disconnect = 0.0
            while not self._stop.is_set():
                try:
                    conn, addr = listener.accept()
                except socket.timeout:
                    if (
                        had_client
                        and self._config.idle_exit_sec >= 0
                        and (time.monotonic() - last_disconnect) >= self._config.idle_exit_sec
                    ):
                        self._log_event("idle_exit", idle_exit_sec=self._config.idle_exit_sec)
                        break
                    continue
                except OSError:
                    break

                if addr[0] not in LOOPBACK_HOSTS:
                    self._log_event("rejected_peer", peer=addr[0])
                    conn.close()
                    continue

                outcome = self._serve_connection(conn, addr)
                had_client = True
                last_disconnect = time.monotonic()
                if outcome == _OUTCOME_BYE:
                    self._stop.set()
        finally:
            listener.close()
            self._log_event("shutdown", **self._stats.snapshot())
            self._close_log()
        return 0

    # -- per-connection -----------------------------------------------------
    def _serve_connection(self, conn: socket.socket, addr: Any) -> str:
        conn.settimeout(self._config.accept_timeout)
        recv = protocol.socket_recv(conn)
        try:
            if not self._handshake(conn, recv):
                return _OUTCOME_DISCONNECT
            self._log_event("client_connected", peer=addr[0])
            return self._serve_loop(conn, recv)
        except ConnectionClosed:
            return _OUTCOME_DISCONNECT
        except (ProtocolError, OSError) as exc:
            self._try_send(conn, protocol.build_error(seq=None, reason=f"protocol_error: {exc}"))
            return _OUTCOME_PROTOCOL_ERROR
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def _handshake(self, conn: socket.socket, recv: protocol.Recv) -> bool:
        message = self._read_message(recv)
        if message is None:
            return False
        if frame_type(message) != protocol.MSG_HELLO:
            self._send(conn, protocol.build_error(seq=None, reason="expected_hello"))
            return False
        if int(message.get("v", 0)) != PROTOCOL_VERSION:
            self._send(conn, protocol.build_error(seq=None, reason="protocol_version_mismatch"))
            self._log_event("handshake_rejected", cause="protocol_version_mismatch")
            return False

        identity = self._service.identity
        got_capture = str(message.get("capture_schema_hash", "")).upper()
        if got_capture != str(identity.source_capture_schema_hash).upper():
            self._send(conn, protocol.build_error(seq=None, reason="capture_schema_hash_mismatch"))
            self._log_event("handshake_rejected", cause="capture_schema_hash_mismatch")
            return False

        expected_model = message.get("expected_model_sha256")
        if expected_model and str(expected_model).upper() != str(identity.model_sha256).upper():
            self._send(conn, protocol.build_error(seq=None, reason="model_sha256_mismatch"))
            self._log_event("handshake_rejected", cause="model_sha256_mismatch")
            return False

        self._send(conn, identity.hello_ack(os.getpid()))
        self._log_event(
            "handshake_ok",
            run_id=message.get("run_id"),
            control_hz=message.get("control_hz"),
        )
        return True

    def _serve_loop(self, conn: socket.socket, recv: protocol.Recv) -> str:
        while not self._stop.is_set():
            message = self._read_message(recv)
            if message is None:
                return _OUTCOME_DISCONNECT
            kind = frame_type(message)
            if kind == protocol.MSG_ACT:
                self._handle_act(conn, message)
            elif kind == protocol.MSG_PING:
                self._send(conn, self._pong())
            elif kind == protocol.MSG_BYE:
                self._log_event("bye")
                return _OUTCOME_BYE
            else:
                self._send(
                    conn,
                    protocol.build_error(seq=message.get("seq"), reason=f"unknown_message: {kind}"),
                )
            self._maybe_log_stats()
        return _OUTCOME_DISCONNECT

    def _handle_act(self, conn: socket.socket, message: Mapping[str, Any]) -> None:
        seq = message.get("seq")
        payload = message.get("payload")
        start = time.perf_counter()
        try:
            if not isinstance(payload, Mapping):
                raise ValueError("act payload missing or not an object")
            ax, ay, model_ms = self._service.predict(payload)
            if not (math.isfinite(ax) and math.isfinite(ay)):
                raise _NonFiniteAction(ax, ay)
        except _NonFiniteAction:
            self._stats.record_error()
            self._send(conn, protocol.build_error(seq=seq, reason="nonfinite_action"))
            return
        except Exception as exc:  # encode error or any inference fault
            self._stats.record_error()
            self._send(conn, protocol.build_error(seq=seq, reason=_reason_for(exc)))
            return

        total_ms = (time.perf_counter() - start) * 1000.0
        self._stats.record(model_ms)
        self._send(
            conn,
            protocol.build_action(seq=int(seq), ax=ax, ay=ay, model_ms=model_ms, total_ms=total_ms),
        )

    # -- io helpers ---------------------------------------------------------
    def _read_message(self, recv: protocol.Recv) -> dict[str, Any] | None:
        """Read one frame; ``None`` on clean disconnect. Frame errors propagate."""
        while not self._stop.is_set():
            try:
                return protocol.read_frame(recv)
            except socket.timeout:
                continue  # idle read timeout — re-check stop flag, keep waiting
            except ConnectionClosed:
                return None
        return None

    def _send(self, conn: socket.socket, message: Mapping[str, Any]) -> None:
        conn.sendall(protocol.pack_frame(message))

    def _try_send(self, conn: socket.socket, message: Mapping[str, Any]) -> None:
        try:
            self._send(conn, message)
        except (OSError, ProtocolError):
            pass

    def _pong(self) -> dict[str, Any]:
        snap = self._stats.snapshot()
        return protocol.build_pong(
            served=snap["served"],
            errors=snap["errors"],
            model_ms_p50=snap["model_ms_p50"],
            model_ms_p99=snap["model_ms_p99"],
        )

    # -- signals ------------------------------------------------------------
    def _install_signals(self) -> None:
        def _handler(signum: int, _frame: Any) -> None:
            self._stop.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, _handler)
            except (ValueError, OSError):  # not in main thread / unsupported
                pass

    # -- logging ------------------------------------------------------------
    def _open_log(self) -> None:
        path = Path(self._config.log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._log_handle = path.open("a", encoding="utf-8")

    def _close_log(self) -> None:
        if self._log_handle is not None:
            try:
                self._log_handle.flush()
                self._log_handle.close()
            finally:
                self._log_handle = None

    def _log_event(self, event: str, **fields: Any) -> None:
        if self._log_handle is None:
            return
        record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": event, **fields}
        self._log_handle.write(json.dumps(record, sort_keys=True) + "\n")
        self._log_handle.flush()

    def _maybe_log_stats(self) -> None:
        now = time.monotonic()
        if now - self._last_stats_log >= self._config.stats_log_interval_sec:
            self._last_stats_log = now
            self._log_event("stats", **self._stats.snapshot())


class _NonFiniteAction(RuntimeError):
    """Internal marker for a non-finite model action."""

    def __init__(self, ax: float, ay: float) -> None:
        super().__init__(f"non-finite action ({ax}, {ay})")


def _reason_for(exc: Exception) -> str:
    """Map an inference exception to a stable ``error`` reason string."""
    name = type(exc).__name__
    if name == "ObservationError":
        return f"encode_error: {exc}"
    return f"sidecar_error: {exc}"
