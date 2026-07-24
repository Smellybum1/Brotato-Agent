"""Residual actor for WP2 Stage F Phase 2 (design §3-§4).

The residual actor is the frozen ``bc_v2_f`` student trunk (its aux-capable
representation) plus a small **zero-init** ``z``-head. It emits a bounded angular
residual::

    emb   = trunk(obs)                    # frozen BCPolicyV1 trunk (256-d)
    z     = z_head(emb)                   # small MLP, final layer zero-init
    delta = theta_max * tanh(z)           # bounded to +/- theta_max degrees

served by rotating the teacher action by ``delta`` (magnitude preserved). Because
the ``z``-head's final layer is zero-initialized, a *fresh* actor emits ``z == 0``
and therefore ``delta == 0`` **exactly** for every input — it is pure teacher at
iteration 0 (the property the serving-replay check pins, design §6.3).

Trunk policy (design §3, "shared frozen-ish trunk v1"): the trunk is FROZEN in
v1. Only the ``z``-head trains. Freezing keeps the served representation
identical to the production student, makes the actor checkpoint's forward pass
deterministic, and lets the replay precompute trunk embeddings once (the critic
and actor both read the same fixed embedding). Revisit on evidence (design §3).

The BCPolicyV1 tensor contract is reused verbatim — this module never
reimplements pooling or masking; :func:`trunk_embedding` calls the exact same
per-group encoders, masked pool, and trunk Sequential the student's ``forward``
uses, stopping one layer short of the action head.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import torch
from torch import Tensor, nn

from trainer.models.bc_policy_v1 import BCPolicyV1

# Re-export the single canonical rotation helper (torch-free) from the serving
# layer so the actor's serving math and the sidecar's serving math are provably
# the same code (design §4 / F-1 geometry), never a duplicate.
from trainer.bridge.sidecar import rotate_action  # noqa: F401

#: Amendment F-1 residual half-width: delta is bounded to +/- 5 degrees.
DEFAULT_THETA_MAX_DEG = 5.0
#: On-disk checkpoint format tag (bumped only on a breaking layout change).
RESIDUAL_ACTOR_FORMAT = "residual_actor_v1"


# ---------------------------------------------------------------------------
# Trunk embedding (reuse BCPolicyV1 internals; no reimplementation)
# ---------------------------------------------------------------------------
def trunk_embedding(
    model: BCPolicyV1,
    globals: Tensor,
    entities: Dict[str, Tensor],
    masks: Dict[str, Tensor],
) -> Tensor:
    """Return the BCPolicyV1 trunk embedding ``[B, trunk_hidden[-1]]``.

    Reproduces :meth:`BCPolicyV1.forward` exactly up to (but not including) the
    action head, reusing the model's own encoders / masked pool / trunk. In eval
    mode ``_apply_prev_action_dropout`` is the identity, so the embedding is a
    pure deterministic function of the observation.
    """
    globals_in = model._apply_prev_action_dropout(globals)
    pooled: list[Tensor] = []
    for spec in model.config.group_specs:
        feats = entities[spec.name]
        mask = masks[spec.name]
        encoded = model.encoders[spec.name](feats)
        pooled.append(model._masked_pool(encoded, mask))
    trunk_in = torch.cat(pooled + [globals_in], dim=-1)
    return model.trunk(trunk_in)


# ---------------------------------------------------------------------------
# Config + model
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ResidualActorConfig:
    """Residual-actor hyperparameters.

    ``embedding_dim`` must equal the trunk's last hidden width (256 for the
    stock BCPolicyV1). ``theta_max_deg`` is the F-1 residual bound.
    """

    embedding_dim: int = 256
    z_hidden: int = 64
    theta_max_deg: float = DEFAULT_THETA_MAX_DEG


class ResidualActor(nn.Module):
    """Frozen BCPolicyV1 trunk + zero-init ``z``-head -> bounded angular residual.

    Only the ``z``-head parameters are trainable (:meth:`actor_parameters`); the
    trunk is frozen (``requires_grad_(False)``) so the served representation is
    byte-identical to the production student and the actor forward is
    deterministic.
    """

    def __init__(self, trunk: BCPolicyV1, config: ResidualActorConfig | None = None) -> None:
        super().__init__()
        self.config = config or ResidualActorConfig()
        cfg = self.config
        self.trunk_model = trunk
        # Freeze the trunk: v1 does not fine-tune it (design §3).
        self.trunk_model.requires_grad_(False)
        self.trunk_model.eval()

        self.z_head = nn.Sequential(
            nn.Linear(cfg.embedding_dim, cfg.z_hidden),
            nn.ReLU(),
            nn.Linear(cfg.z_hidden, 1),
        )
        self._zero_init_head()

    def _zero_init_head(self) -> None:
        """Zero-init the FINAL z-head layer so a fresh actor emits delta == 0.

        The final linear's weight and bias are set to exactly zero; hidden
        layers keep their default init. z = 0 for every input at construction =>
        delta = theta_max * tanh(0) = 0 (design §3 zero-init property).
        """
        final = self.z_head[-1]
        assert isinstance(final, nn.Linear)
        nn.init.zeros_(final.weight)
        nn.init.zeros_(final.bias)

    # -- forward pieces ------------------------------------------------------
    def embedding(
        self, globals: Tensor, entities: Dict[str, Tensor], masks: Dict[str, Tensor]
    ) -> Tensor:
        """Frozen trunk embedding for a batch of observations (no grad through trunk)."""
        with torch.no_grad():
            return trunk_embedding(self.trunk_model, globals, entities, masks)

    def z_from_embedding(self, embedding: Tensor) -> Tensor:
        """z-head output ``[B, 1]`` from a (possibly precomputed) trunk embedding."""
        return self.z_head(embedding)

    def delta_deg_from_z(self, z: Tensor) -> Tensor:
        """Bounded angular residual in degrees: ``theta_max * tanh(z)`` -> ``[B]``."""
        return self.config.theta_max_deg * torch.tanh(z).squeeze(-1)

    def delta_deg_from_embedding(self, embedding: Tensor) -> Tensor:
        return self.delta_deg_from_z(self.z_from_embedding(embedding))

    def forward(
        self, globals: Tensor, entities: Dict[str, Tensor], masks: Dict[str, Tensor]
    ) -> tuple[Tensor, Tensor]:
        """Return ``(delta_deg [B], z [B])`` for a batch of raw observations."""
        emb = self.embedding(globals, entities, masks)
        z = self.z_from_embedding(emb)
        delta = self.delta_deg_from_z(z)
        return delta, z.squeeze(-1)

    def actor_parameters(self):
        """Trainable parameters (z-head only; the trunk is frozen)."""
        return self.z_head.parameters()


# ---------------------------------------------------------------------------
# sha-stable checkpoint save / load
# ---------------------------------------------------------------------------
def _sha256_file(path: Path) -> str:
    """Content sha256 of a residual-actor checkpoint file.

    Computed over a CANONICAL serialization of the payload (sorted-key metadata
    JSON + z-head tensor bytes in sorted parameter order), NOT the raw ``.pt``
    bytes: ``torch.save``'s zip container embeds non-deterministic metadata, so
    two identical actors would otherwise hash differently. The canonical digest
    is a stable identity of *what the actor is* (design §4 / §5 determinism) and
    is reproducible from the loaded checkpoint.
    """
    import hashlib

    import torch

    payload = torch.load(str(path), map_location="cpu", weights_only=False)
    return _sha256_payload(payload)


def _sha256_payload(payload: dict[str, Any]) -> str:
    import hashlib

    digest = hashlib.sha256()
    meta = {
        "format": payload.get("format"),
        "config": payload.get("config"),
        "parent_model_sha256": payload.get("parent_model_sha256"),
        "iteration": payload.get("iteration"),
    }
    digest.update(json.dumps(meta, sort_keys=True).encode("utf-8"))
    state = payload.get("z_head_state_dict", {})
    for key in sorted(state):
        tensor = state[key]
        digest.update(key.encode("utf-8"))
        digest.update(bytes(tensor.detach().cpu().contiguous().numpy().tobytes()))
    return digest.hexdigest().upper()


def save_residual_actor(
    actor: ResidualActor,
    path: str | Path,
    *,
    parent_model_sha256: str,
    parent_registry_run_name: str = "",
    iteration: int = 0,
    extra: dict[str, Any] | None = None,
) -> str:
    """Persist the z-head + provenance to ``path``; return the file sha256 (upper hex).

    Only the z-head weights and the config are stored (the trunk is the frozen,
    separately-verified ``bc_v2_f`` best.pt; ``parent_model_sha256`` pins which
    trunk this actor is valid against). The returned sha256 IS the actor's
    serving identity ``model_sha256`` (design §4). The payload is written with
    ``torch.save`` on CPU tensors and sorted-key metadata so identical actors
    produce identical files (sha-stable) within a torch environment.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cfg = actor.config
    z_head_state = {k: v.detach().cpu() for k, v in actor.z_head.state_dict().items()}
    payload = {
        "format": RESIDUAL_ACTOR_FORMAT,
        "z_head_state_dict": z_head_state,
        "config": {
            "embedding_dim": cfg.embedding_dim,
            "z_hidden": cfg.z_hidden,
            "theta_max_deg": cfg.theta_max_deg,
        },
        "parent_model_sha256": str(parent_model_sha256).upper(),
        "parent_registry_run_name": str(parent_registry_run_name),
        "iteration": int(iteration),
        "extra": dict(extra or {}),
    }
    torch.save(payload, str(path))
    return _sha256_payload(payload)


def load_residual_actor(
    path: str | Path, trunk: BCPolicyV1
) -> tuple[ResidualActor, dict[str, Any]]:
    """Rebuild a :class:`ResidualActor` around ``trunk`` from a saved checkpoint.

    Returns ``(actor, meta)`` where ``meta`` carries the stored provenance
    (format, parent sha, iteration, extra). Raises ``ValueError`` on a format or
    embedding-dim mismatch.
    """
    path = Path(path)
    payload = torch.load(str(path), map_location="cpu", weights_only=False)
    if payload.get("format") != RESIDUAL_ACTOR_FORMAT:
        raise ValueError(f"unexpected residual-actor format: {payload.get('format')!r}")
    cfg_raw = payload["config"]
    config = ResidualActorConfig(
        embedding_dim=int(cfg_raw["embedding_dim"]),
        z_hidden=int(cfg_raw["z_hidden"]),
        theta_max_deg=float(cfg_raw["theta_max_deg"]),
    )
    trunk_dim = trunk.config.trunk_hidden[-1]
    if config.embedding_dim != trunk_dim:
        raise ValueError(
            f"actor embedding_dim {config.embedding_dim} != trunk hidden {trunk_dim}"
        )
    actor = ResidualActor(trunk, config)
    actor.z_head.load_state_dict(payload["z_head_state_dict"])
    actor.eval()
    meta = {
        "format": payload.get("format"),
        "parent_model_sha256": str(payload.get("parent_model_sha256", "")).upper(),
        "parent_registry_run_name": payload.get("parent_registry_run_name", ""),
        "iteration": int(payload.get("iteration", 0)),
        "extra": payload.get("extra", {}),
    }
    return actor, meta


def write_actor_registry_manifest(
    manifest_path: str | Path,
    *,
    actor_checkpoint: str | Path,
    actor_sha256: str,
    parent_registry: str,
    parent_model_sha256: str,
    iteration: int,
    theta_max_deg: float,
    explore_sigma: float,
    reward_id: str,
    schema_hash: str,
    source_capture_schema_hash: str,
    extra: dict[str, Any] | None = None,
) -> None:
    """Write ``models/registry/residual_pi<k>.json`` for a promoted actor (design §5)."""
    manifest = {
        "run_name": f"residual_pi{iteration}",
        "iteration": int(iteration),
        "kind": "residual_actor",
        "format": RESIDUAL_ACTOR_FORMAT,
        "actor_checkpoint": str(actor_checkpoint),
        "actor_sha256": str(actor_sha256).upper(),
        "parent_registry": str(parent_registry),
        "parent_model_sha256": str(parent_model_sha256).upper(),
        "theta_max_deg": float(theta_max_deg),
        "explore_sigma": float(explore_sigma),
        "reward_id": reward_id,
        "schema_hash": str(schema_hash).upper(),
        "source_capture_schema_hash": str(source_capture_schema_hash).upper(),
        "extra": dict(extra or {}),
    }
    Path(manifest_path).write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
