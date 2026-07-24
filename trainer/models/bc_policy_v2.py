"""Behavior-cloning policy v2 for WP2 M4 (DAgger round 1, candidate B).

``BCPolicyV2`` reuses :class:`~trainer.models.bc_policy_v1.BCPolicyV1` *verbatim*
as its serving trunk (stored under the ``.base`` submodule) and adds two auxiliary
heads on the trunk's penultimate hidden representation (the 256-d output of the
shared trunk, before the tanh action head):

  * ``aux_damage``: ``Linear(hidden, 1)`` -> a logit for
    P(hp loss within the next 10 ticks / 0.5 s); trained with BCE-with-logits.
  * ``aux_margin``: ``Linear(hidden, 1)`` -> a sigmoid in [0, 1] approximating the
    min-over-horizon safety margin ``1 - max entity contact_risk``; trained with
    a Huber loss.

The aux heads exist ONLY to shape the shared representation during training (design
§7). They are dropped at serving time: :meth:`export_base_state_dict` returns a
state_dict that is byte-for-byte load-compatible with a fresh
``BCPolicyV1(config).load_state_dict(..., strict=True)``, so the qualified
sidecar / ONNX pipeline serves the base unchanged.

Contract guarantee (tested): in eval mode, ``BCPolicyV2.forward`` produces the
*identical* action tensor a standalone ``BCPolicyV1`` with the same base weights
would produce — the trunk math is replicated op-for-op, never re-derived.
"""

from __future__ import annotations

from typing import Dict, Tuple

import torch
from torch import Tensor, nn

from trainer.models.bc_policy_v1 import BCPolicyConfig, BCPolicyV1


class BCPolicyV2(nn.Module):
    """BCPolicyV1 serving trunk (``.base``) plus two training-only aux heads."""

    def __init__(self, base_config: BCPolicyConfig | None = None) -> None:
        super().__init__()
        self.base = BCPolicyV1(base_config)
        hidden = self.base.config.trunk_hidden[-1]
        # Aux heads read the shared trunk hidden (penultimate representation).
        self.aux_damage = nn.Linear(hidden, 1)
        self.aux_margin = nn.Linear(hidden, 1)

    @property
    def config(self) -> BCPolicyConfig:
        return self.base.config

    # -- shared trunk (replicates BCPolicyV1.forward up to the action head) ---
    def _trunk_hidden(
        self,
        globals: Tensor,
        entities: Dict[str, Tensor],
        masks: Dict[str, Tensor],
    ) -> Tensor:
        """Compute the shared trunk hidden [B, trunk_hidden[-1]].

        Mirrors :meth:`BCPolicyV1.forward` exactly (same prev-action dropout,
        same per-group encode + masked pool, same concat order, same trunk) so
        that ``self.base.head`` applied to this hidden reproduces the base model
        bit-for-bit.
        """
        base = self.base
        globals_in = base._apply_prev_action_dropout(globals)

        pooled: list[Tensor] = []
        for spec in base.config.group_specs:
            feats = entities[spec.name]
            mask = masks[spec.name]
            encoded = base.encoders[spec.name](feats)
            pooled.append(base._masked_pool(encoded, mask))

        trunk_in = torch.cat(pooled + [globals_in], dim=-1)
        return base.trunk(trunk_in)

    # -- serving forward: action only, identical to BCPolicyV1 ---------------
    def forward(
        self,
        globals: Tensor,
        entities: Dict[str, Tensor],
        masks: Dict[str, Tensor],
    ) -> Tensor:
        hidden = self._trunk_hidden(globals, entities, masks)
        return torch.tanh(self.base.head(hidden))

    # -- training forward: action + aux head outputs -------------------------
    def forward_with_aux(
        self,
        globals: Tensor,
        entities: Dict[str, Tensor],
        masks: Dict[str, Tensor],
    ) -> Tuple[Tensor, Tensor, Tensor]:
        """Return (action [B,2], aux_damage_logit [B], aux_margin [B] in [0,1])."""
        hidden = self._trunk_hidden(globals, entities, masks)
        action = torch.tanh(self.base.head(hidden))
        aux_damage_logit = self.aux_damage(hidden).squeeze(-1)
        aux_margin = torch.sigmoid(self.aux_margin(hidden)).squeeze(-1)
        return action, aux_damage_logit, aux_margin

    # -- serving export ------------------------------------------------------
    def export_base_state_dict(self) -> Dict[str, Tensor]:
        """State_dict of the base trunk only — strict-load compatible with a
        fresh ``BCPolicyV1(config)``. The aux heads are intentionally omitted."""
        return self.base.state_dict()

    def num_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters())

    def num_base_parameters(self) -> int:
        return sum(p.numel() for p in self.base.parameters())
