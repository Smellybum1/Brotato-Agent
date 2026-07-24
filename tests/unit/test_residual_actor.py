"""Unit tests for the Stage F Phase 2 residual actor (design §3, §6.1 rung 1).

Covers the zero-init property (fresh actor's delta == 0 exactly), the tanh
bound / saturation, the shared rotation math vs the probe, and sha-stable
checkpoint save/load round-trip.
"""
from __future__ import annotations

import math

import pytest

torch = pytest.importorskip("torch")

from trainer.models.bc_policy_v1 import BCPolicyV1, BCPolicyConfig
from trainer.rl.residual_actor import (
    DEFAULT_THETA_MAX_DEG,
    ResidualActor,
    ResidualActorConfig,
    load_residual_actor,
    rotate_action,
    save_residual_actor,
    trunk_embedding,
)


def _trunk() -> BCPolicyV1:
    torch.manual_seed(0)
    return BCPolicyV1(BCPolicyConfig()).eval()


def _obs(batch: int = 4, seed: int = 1):
    torch.manual_seed(seed)
    cfg = BCPolicyConfig()
    globals_t = torch.randn(batch, cfg.global_dim)
    entities = {}
    masks = {}
    for spec in cfg.group_specs:
        entities[spec.name] = torch.randn(batch, spec.capacity, cfg.entity_feature_dim)
        # random present/absent mask, but keep at least one present row
        m = (torch.rand(batch, spec.capacity) > 0.5).float()
        m[:, 0] = 1.0
        masks[spec.name] = m
    return globals_t, entities, masks


# ---------------------------------------------------------------------------
# Zero-init property (the central rung-3 guarantee)
# ---------------------------------------------------------------------------
def test_fresh_actor_delta_is_exactly_zero():
    actor = ResidualActor(_trunk())
    g, ent, msk = _obs()
    delta, z = actor(g, ent, msk)
    assert torch.equal(z, torch.zeros_like(z))
    assert torch.equal(delta, torch.zeros_like(delta))


def test_zero_init_delta_zero_reproduces_teacher_via_rotation():
    actor = ResidualActor(_trunk())
    g, ent, msk = _obs()
    delta, _ = actor(g, ent, msk)
    d = float(delta[0].item())
    assert d == 0.0
    # rotating any teacher vector by delta==0 is an exact identity
    for tx, ty in [(0.6, -0.8), (1.0, 0.0), (-0.3, 0.95)]:
        rx, ry = rotate_action(tx, ty, d)
        assert rx == tx and ry == ty


def test_final_layer_zero_init():
    actor = ResidualActor(_trunk())
    final = actor.z_head[-1]
    assert torch.equal(final.weight, torch.zeros_like(final.weight))
    assert torch.equal(final.bias, torch.zeros_like(final.bias))


# ---------------------------------------------------------------------------
# Bound / saturation
# ---------------------------------------------------------------------------
def test_delta_bounded_by_theta_max():
    actor = ResidualActor(_trunk())
    # Force a large positive z by loading a large final-layer bias.
    with torch.no_grad():
        actor.z_head[-1].bias.fill_(50.0)
    g, ent, msk = _obs(batch=8)
    delta, z = actor(g, ent, msk)
    assert torch.all(delta.abs() <= DEFAULT_THETA_MAX_DEG + 1e-6)
    # saturates near +theta_max
    assert torch.all(delta > DEFAULT_THETA_MAX_DEG - 1e-3)


def test_delta_bounded_negative_saturation():
    actor = ResidualActor(_trunk())
    with torch.no_grad():
        actor.z_head[-1].bias.fill_(-50.0)
    g, ent, msk = _obs(batch=8)
    delta, _ = actor(g, ent, msk)
    assert torch.all(delta < -DEFAULT_THETA_MAX_DEG + 1e-3)
    assert torch.all(delta.abs() <= DEFAULT_THETA_MAX_DEG + 1e-6)


def test_custom_theta_max_respected():
    actor = ResidualActor(_trunk(), ResidualActorConfig(theta_max_deg=3.0))
    with torch.no_grad():
        actor.z_head[-1].bias.fill_(50.0)
    g, ent, msk = _obs()
    delta, _ = actor(g, ent, msk)
    assert torch.all(delta.abs() <= 3.0 + 1e-6)


# ---------------------------------------------------------------------------
# Trunk is frozen, only z-head trains
# ---------------------------------------------------------------------------
def test_trunk_frozen_only_zhead_trainable():
    actor = ResidualActor(_trunk())
    assert all(not p.requires_grad for p in actor.trunk_model.parameters())
    assert all(p.requires_grad for p in actor.z_head.parameters())
    trainable = list(actor.actor_parameters())
    assert len(trainable) == len(list(actor.z_head.parameters()))


def test_trunk_embedding_matches_forward_prefix():
    trunk = _trunk()
    g, ent, msk = _obs()
    emb = trunk_embedding(trunk, g, ent, msk)
    assert emb.shape == (g.shape[0], trunk.config.trunk_hidden[-1])
    # applying the head to the embedding reproduces the full BC forward
    expected = torch.tanh(trunk.head(emb))
    got = trunk(g, ent, msk)
    assert torch.allclose(expected, got, atol=1e-6)


# ---------------------------------------------------------------------------
# Checkpoint save/load round-trip + sha stability
# ---------------------------------------------------------------------------
def test_checkpoint_roundtrip_preserves_forward(tmp_path):
    actor = ResidualActor(_trunk())
    with torch.no_grad():  # give the z-head non-trivial weights
        for p in actor.z_head.parameters():
            p.add_(torch.randn_like(p) * 0.1)
    g, ent, msk = _obs()
    before, _ = actor(g, ent, msk)

    path = tmp_path / "actor.pt"
    sha = save_residual_actor(actor, path, parent_model_sha256="ABC123", iteration=1)
    assert len(sha) == 64

    reloaded, meta = load_residual_actor(path, _trunk())
    after, _ = reloaded(g, ent, msk)
    assert torch.allclose(before, after, atol=1e-6)
    assert meta["parent_model_sha256"] == "ABC123"
    assert meta["iteration"] == 1


def test_checkpoint_sha_stable_across_identical_saves(tmp_path):
    actor = ResidualActor(_trunk())
    with torch.no_grad():
        actor.z_head[-1].bias.fill_(0.25)
    p1 = tmp_path / "a1.pt"
    p2 = tmp_path / "a2.pt"
    sha1 = save_residual_actor(actor, p1, parent_model_sha256="X")
    sha2 = save_residual_actor(actor, p2, parent_model_sha256="X")
    assert sha1 == sha2


def test_load_rejects_embedding_dim_mismatch(tmp_path):
    actor = ResidualActor(_trunk(), ResidualActorConfig(embedding_dim=256))
    path = tmp_path / "a.pt"
    save_residual_actor(actor, path, parent_model_sha256="X")
    # a trunk whose hidden width differs from the stored embedding_dim
    small = BCPolicyV1(BCPolicyConfig(trunk_hidden=(128, 128))).eval()
    with pytest.raises(ValueError):
        load_residual_actor(path, small)
