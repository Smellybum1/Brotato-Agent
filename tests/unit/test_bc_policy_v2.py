"""CPU-only unit tests for BCPolicyV2 (trainer/models/bc_policy_v2).

Verifies the aux-head architecture, the serving-export compatibility contract
(exported base strict-loads into a fresh BCPolicyV1), and the bit-identical
equivalence of BCPolicyV2.forward to BCPolicyV1.forward when the base weights
are shared.
"""
from __future__ import annotations

import torch

from trainer.models.bc_policy_v1 import BCPolicyConfig, BCPolicyV1
from trainer.models.bc_policy_v2 import BCPolicyV2


ENTITY_DIM = 15


def _make_batch(model, batch: int, *, seed: int = 0):
    g = torch.Generator().manual_seed(seed)
    cfg = model.config
    globals_t = torch.randn(batch, cfg.global_dim, generator=g)
    entities, masks = {}, {}
    for spec in cfg.group_specs:
        feats = torch.randn(batch, spec.capacity, ENTITY_DIM, generator=g)
        mask = torch.zeros(batch, spec.capacity)
        for b in range(batch):
            n = torch.randint(0, spec.capacity + 1, (1,), generator=g).item()
            mask[b, :n] = 1.0
        entities[spec.name] = feats
        masks[spec.name] = mask
    return globals_t, entities, masks


# -- output contract --------------------------------------------------------
def test_forward_shape_and_range():
    m = BCPolicyV2(BCPolicyConfig()).eval()
    g, ent, msk = _make_batch(m, 5)
    out = m(g, ent, msk)
    assert out.shape == (5, 2)
    assert torch.all(out >= -1.0) and torch.all(out <= 1.0)


def test_forward_with_aux_shapes_and_ranges():
    m = BCPolicyV2(BCPolicyConfig()).eval()
    g, ent, msk = _make_batch(m, 7, seed=2)
    action, damage_logit, margin = m.forward_with_aux(g, ent, msk)
    assert action.shape == (7, 2)
    assert damage_logit.shape == (7,)
    assert margin.shape == (7,)
    # margin passes through sigmoid -> [0, 1]; damage is a raw logit (unbounded).
    assert torch.all(margin >= 0.0) and torch.all(margin <= 1.0)


# -- serving-export contract ------------------------------------------------
def test_export_base_state_dict_strict_loads_into_bc_policy_v1():
    cfg = BCPolicyConfig()
    m = BCPolicyV2(cfg)
    exported = m.export_base_state_dict()
    fresh = BCPolicyV1(cfg)
    # strict=True must succeed: keys must match BCPolicyV1 exactly.
    fresh.load_state_dict(exported, strict=True)
    # And the exported dict must NOT contain any aux-head keys.
    assert not any(k.startswith("aux_") for k in exported)


def test_forward_identical_to_bc_policy_v1_with_shared_base():
    cfg = BCPolicyConfig()
    torch.manual_seed(17)
    v2 = BCPolicyV2(cfg).eval()
    v1 = BCPolicyV1(cfg).eval()
    # Share the base weights: load v2's exported base into the standalone v1.
    v1.load_state_dict(v2.export_base_state_dict(), strict=True)

    g, ent, msk = _make_batch(v2, 6, seed=5)
    out_v2 = v2(g, ent, msk)
    out_v1 = v1(g, ent, msk)
    assert torch.equal(out_v2, out_v1)


# -- aux heads receive gradient ---------------------------------------------
def test_aux_heads_have_gradients():
    m = BCPolicyV2(BCPolicyConfig()).train()
    g, ent, msk = _make_batch(m, 8, seed=9)
    action, damage_logit, margin = m.forward_with_aux(g, ent, msk)
    loss = action.pow(2).mean() + damage_logit.mean() + margin.mean()
    loss.backward()
    for name, p in m.named_parameters():
        assert p.grad is not None, f"no grad for {name}"
    assert m.aux_damage.weight.grad.abs().sum() > 0
    assert m.aux_margin.weight.grad.abs().sum() > 0


def test_param_counts_v2_exceeds_base():
    m = BCPolicyV2(BCPolicyConfig())
    assert m.num_parameters() > m.num_base_parameters()
    # Aux heads add exactly 2 * (hidden + 1) params.
    hidden = m.config.trunk_hidden[-1]
    assert m.num_parameters() - m.num_base_parameters() == 2 * (hidden + 1)


def test_base_matches_standalone_v1_param_count():
    cfg = BCPolicyConfig()
    m = BCPolicyV2(cfg)
    v1 = BCPolicyV1(cfg)
    assert m.num_base_parameters() == v1.num_parameters()
