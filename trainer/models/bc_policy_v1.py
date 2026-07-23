"""Behavior-cloning policy model v1 for WP2 (packet §11).

Masked entity-set encoder over the frozen ``combat_obs_v1`` schema. See
``.tmp/wp2_m2_training_architecture.md`` §3 (model) and §4 (loss).

The tensor contract is fixed by the primary and MUST NOT change:

    forward(
        globals:  Tensor[B, global_dim]  (float32),
        entities: dict[name -> Tensor[B, capacity, entity_feature_dim]],
        masks:    dict[name -> Tensor[B, capacity]]  (1.0 present / 0.0 padded),
    ) -> actions Tensor[B, 2] in [-1, 1]  (tanh head)

Padded entity rows are provably inert: encoder outputs are multiplied by the
mask before mean pooling, and a mask-aware max fills padded rows with -inf so
they can never be selected. Perturbing a masked-out row's features leaves the
output bit-identical.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple

import torch
from torch import Tensor, nn

_EPS = 1e-6


@dataclass(frozen=True)
class GroupSpec:
    """An ordered entity group: its name and per-observation capacity."""

    name: str
    capacity: int


@dataclass(frozen=True)
class BCPolicyConfig:
    """Configuration for :class:`BCPolicyV1`.

    ``group_specs`` are ordered; pooled group features are concatenated in this
    order, so the order is part of the model contract. ``prev_action_indices``
    are the column positions of ``previous_action_x`` / ``previous_action_y``
    within the ``global_dim``-wide masked global vector — supplied by config,
    never computed here.
    """

    group_specs: Tuple[GroupSpec, ...] = field(
        default_factory=lambda: (
            GroupSpec("enemies", 64),
            GroupSpec("bosses", 2),
            GroupSpec("projectiles", 32),
            GroupSpec("materials", 64),
            GroupSpec("consumables", 24),
            GroupSpec("crates", 2),
            GroupSpec("obstacles", 8),
        )
    )
    global_dim: int = 40
    entity_feature_dim: int = 15
    entity_hidden: int = 64
    trunk_hidden: Tuple[int, ...] = (512, 256)
    previous_action_dropout_p: float = 0.1
    prev_action_indices: Tuple[int, int] = (15, 16)


def _entity_encoder(in_dim: int, hidden: int) -> nn.Sequential:
    """Per-group MLP: in_dim -> hidden -> hidden (LayerNorm + ReLU each stage)."""

    return nn.Sequential(
        nn.Linear(in_dim, hidden),
        nn.LayerNorm(hidden),
        nn.ReLU(),
        nn.Linear(hidden, hidden),
        nn.LayerNorm(hidden),
        nn.ReLU(),
    )


class BCPolicyV1(nn.Module):
    """Masked entity-set encoder producing a 2-D movement action in [-1, 1]."""

    def __init__(self, config: BCPolicyConfig | None = None) -> None:
        super().__init__()
        self.config = config or BCPolicyConfig()
        cfg = self.config

        # Separate encoder weights per group. ModuleDict keeps ordering stable
        # via the config's group_specs tuple (we never iterate the dict for the
        # concat order — always cfg.group_specs).
        self.encoders = nn.ModuleDict(
            {
                spec.name: _entity_encoder(cfg.entity_feature_dim, cfg.entity_hidden)
                for spec in cfg.group_specs
            }
        )

        # Each group pools to mean(hidden) ++ max(hidden) = 2*hidden.
        pooled_per_group = 2 * cfg.entity_hidden
        trunk_in = pooled_per_group * len(cfg.group_specs) + cfg.global_dim

        trunk_layers: list[nn.Module] = []
        prev = trunk_in
        for width in cfg.trunk_hidden:
            trunk_layers.append(nn.Linear(prev, width))
            trunk_layers.append(nn.LayerNorm(width))
            trunk_layers.append(nn.ReLU())
            prev = width
        self.trunk = nn.Sequential(*trunk_layers)
        self.head = nn.Linear(prev, 2)

    # -- previous-action input dropout --------------------------------------
    def _apply_prev_action_dropout(self, globals_in: Tensor) -> Tensor:
        """Zero BOTH prev-action entries for a Bernoulli-selected subset of the
        batch (per sample, not per element). Training only; identity in eval."""

        p = self.config.previous_action_dropout_p
        if not self.training or p <= 0.0:
            return globals_in

        ix, iy = self.config.prev_action_indices
        batch = globals_in.shape[0]
        # keep == 1 -> retain prev action; drop == 0 -> zero both entries.
        keep = (
            torch.rand(batch, device=globals_in.device, dtype=globals_in.dtype) >= p
        ).to(globals_in.dtype)
        out = globals_in.clone()
        out[:, ix] = out[:, ix] * keep
        out[:, iy] = out[:, iy] * keep
        return out

    # -- masked pooling ------------------------------------------------------
    @staticmethod
    def _masked_pool(encoded: Tensor, mask: Tensor) -> Tensor:
        """Masked mean ⊕ masked max over the capacity dim.

        encoded: [B, cap, H]; mask: [B, cap] (1 present / 0 padded).
        Padded rows are inert: mean multiplies them by 0, max fills them -inf.
        All-empty groups pool to zeros for both halves.
        """

        mask_f = mask.to(encoded.dtype)  # [B, cap]
        mask_col = mask_f.unsqueeze(-1)  # [B, cap, 1]
        count = mask_f.sum(dim=1, keepdim=True)  # [B, 1]
        has_any = count > 0  # [B, 1]

        # Masked mean: sum of masked rows / count (clamped so empty -> 0).
        summed = (encoded * mask_col).sum(dim=1)  # [B, H]
        mean = summed / count.clamp_min(1.0)  # empty -> 0/1 = 0

        # Mask-aware max: padded rows -> -inf so they can never win; empty
        # groups (all -inf) collapse to 0.
        neg_inf = torch.finfo(encoded.dtype).min
        mask_bool = mask_f > 0
        masked = encoded.masked_fill(~mask_bool.unsqueeze(-1), neg_inf)
        maxed = masked.max(dim=1).values  # [B, H]
        maxed = torch.where(has_any, maxed, torch.zeros_like(maxed))

        return torch.cat([mean, maxed], dim=-1)  # [B, 2H]

    # -- forward -------------------------------------------------------------
    def forward(
        self,
        globals: Tensor,
        entities: Dict[str, Tensor],
        masks: Dict[str, Tensor],
    ) -> Tensor:
        globals_in = self._apply_prev_action_dropout(globals)

        pooled: list[Tensor] = []
        for spec in self.config.group_specs:
            feats = entities[spec.name]  # [B, cap, F]
            mask = masks[spec.name]  # [B, cap]
            encoded = self.encoders[spec.name](feats)  # [B, cap, H]
            pooled.append(self._masked_pool(encoded, mask))

        trunk_in = torch.cat(pooled + [globals_in], dim=-1)
        hidden = self.trunk(trunk_in)
        return torch.tanh(self.head(hidden))

    def num_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters())


# ---------------------------------------------------------------------------
# Loss and metrics (architecture note §4)
# ---------------------------------------------------------------------------
def _safe_norm(vec: Tensor) -> Tensor:
    """Row-wise L2 norm, floored at _EPS for safe division."""

    return vec.norm(dim=-1).clamp_min(_EPS)


def _huber(x: Tensor, delta: float) -> Tensor:
    """Element-wise Huber on a scalar residual x."""

    absx = x.abs()
    quad = 0.5 * x * x
    lin = delta * (absx - 0.5 * delta)
    return torch.where(absx <= delta, quad, lin)


def cosine_similarity(pred: Tensor, target: Tensor) -> Tensor:
    """Eps-safe cosine similarity per sample -> [B]."""

    dot = (pred * target).sum(dim=-1)
    return dot / (_safe_norm(pred) * _safe_norm(target))


def magnitude_error(pred: Tensor, target: Tensor) -> Tensor:
    """Signed magnitude residual |pred| - |target| per sample -> [B]."""

    return pred.norm(dim=-1) - target.norm(dim=-1)


def angular_error_deg(pred: Tensor, target: Tensor, mag_eps: float = 0.01) -> Tensor:
    """Per-sample angular error in degrees -> [B].

    Masked the same way as the loss: samples whose target magnitude is
    <= ``mag_eps`` have an undefined direction and are returned as NaN.
    """

    cos = cosine_similarity(pred, target).clamp(-1.0, 1.0)
    ang = torch.rad2deg(torch.acos(cos))
    valid = target.norm(dim=-1) > mag_eps
    return torch.where(valid, ang, torch.full_like(ang, float("nan")))


def saturation_fraction(pred: Tensor, threshold: float = 0.99) -> Tensor:
    """Fraction of action components with |component| > threshold -> scalar."""

    return (pred.abs() > threshold).to(pred.dtype).mean()


def bc_loss(
    pred: Tensor,
    target: Tensor,
    lambda_mag: float = 0.5,
    huber_delta: float = 0.5,
    mag_eps: float = 0.01,
) -> Tuple[Tensor, Dict[str, Tensor]]:
    """Direction + magnitude behavior-cloning loss (note §4).

    L = mean_B[ 1[|target| > mag_eps] * (1 - cos(pred, target))
                + lambda_mag * Huber_delta(|pred| - |target|) ]

    Returns (scalar loss, dict of detached scalar components).
    """

    target_mag = target.norm(dim=-1)
    direction_mask = (target_mag > mag_eps).to(pred.dtype)

    cos = cosine_similarity(pred, target)
    direction_term = direction_mask * (1.0 - cos)

    mag_residual = pred.norm(dim=-1) - target_mag
    mag_term = _huber(mag_residual, huber_delta)

    per_sample = direction_term + lambda_mag * mag_term
    loss = per_sample.mean()

    # Direction term averaged over the samples that actually contribute.
    n_dir = direction_mask.sum().clamp_min(1.0)
    components = {
        "loss": loss.detach(),
        "direction_term": (direction_term.sum() / n_dir).detach(),
        "magnitude_term": mag_term.mean().detach(),
        "direction_masked_fraction": (1.0 - direction_mask.mean()).detach(),
    }
    return loss, components
