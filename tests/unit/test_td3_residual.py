"""Unit tests for the Stage F Phase 2 TD3 residual trainer (design §3, §6.1).

Twin-critic TD convergence on a synthetic fixture, the dose-response sign probe,
delayed (policy_delay) actor updates, target-smoothing bounds, and the actor
L2-to-zero regularizer path.
"""
from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")
np = pytest.importorskip("numpy")

from trainer.models.bc_policy_v1 import BCPolicyV1, BCPolicyConfig
from trainer.rl.residual_actor import ResidualActor, ResidualActorConfig
from trainer.rl.td3_residual import ResidualTD3, TD3Config, TwinCritic


def _actor(embedding_dim: int = 8) -> ResidualActor:
    torch.manual_seed(0)
    trunk = BCPolicyV1(BCPolicyConfig(trunk_hidden=(16, embedding_dim))).eval()
    return ResidualActor(trunk, ResidualActorConfig(embedding_dim=embedding_dim, z_hidden=16))


def _bandit_tensors(n=512, d=8, reward_fn=None, seed=0):
    """Synthetic bandit transitions (done=1 => target == reward_nstep)."""
    rng = np.random.default_rng(seed)
    emb = torch.from_numpy(rng.standard_normal((n, d)).astype(np.float32))
    delta = torch.from_numpy(rng.uniform(-5.0, 5.0, size=n).astype(np.float32))
    if reward_fn is None:
        reward = torch.from_numpy(rng.standard_normal(n).astype(np.float32))
    else:
        reward = reward_fn(delta)
    return {
        "emb": emb,
        "s_idx": torch.arange(n, dtype=torch.long),
        "sp_idx": torch.arange(n, dtype=torch.long),
        "delta": delta,
        "reward_nstep": reward,
        "gamma_bootstrap": torch.zeros(n),
        "done": torch.ones(n),
    }


def test_twin_critic_returns_two_values():
    critic = TwinCritic(8, (16, 16))
    emb = torch.randn(4, 8)
    delta = torch.randn(4)
    q1, q2 = critic(emb, delta)
    assert q1.shape == (4,) and q2.shape == (4,)


def test_td_loss_converges():
    trainer = ResidualTD3(_actor(8), 8, TD3Config(critic_lr=1e-3), device="cpu")
    tensors = _bandit_tensors(n=512, d=8, seed=1)
    hist = trainer.fit_critics(tensors, steps=600, batch_size=128, seed=2)
    # loss should drop substantially from its early value
    early = sum(hist[:20]) / 20.0
    late = sum(hist[-20:]) / 20.0
    assert late < early * 0.5
    assert late < early


def test_dose_response_sign_matches_reward_slope():
    # reward increases with delta => Q(s,+d) - Q(s,-d) should be positive.
    trainer = ResidualTD3(_actor(8), 8, TD3Config(critic_lr=1e-3), device="cpu")
    tensors = _bandit_tensors(n=1024, d=8, reward_fn=lambda d: 0.2 * d, seed=3)
    trainer.fit_critics(tensors, steps=800, batch_size=256, seed=4)
    dr = trainer.dose_response(tensors["emb"], delta_mag_deg=5.0)
    assert dr["sign"] == 1
    assert dr["mean_diff"] > 0.0


def test_dose_response_negative_slope():
    trainer = ResidualTD3(_actor(8), 8, TD3Config(critic_lr=1e-3), device="cpu")
    tensors = _bandit_tensors(n=1024, d=8, reward_fn=lambda d: -0.2 * d, seed=5)
    trainer.fit_critics(tensors, steps=800, batch_size=256, seed=6)
    dr = trainer.dose_response(tensors["emb"], delta_mag_deg=5.0)
    assert dr["sign"] == -1


def test_target_smoothing_bounded():
    cfg = TD3Config(theta_max_deg=5.0, target_noise_deg=3.0, noise_clip_deg=4.0)
    trainer = ResidualTD3(_actor(8), 8, cfg, device="cpu")
    emb = torch.randn(1000, 8)
    a = trainer._smoothed_target_delta(emb)
    assert torch.all(a.abs() <= cfg.theta_max_deg + 1e-6)


def test_delayed_actor_update_cadence():
    trainer = ResidualTD3(_actor(8), 8, TD3Config(policy_delay=2), device="cpu")
    tensors = _bandit_tensors(n=64, d=8, seed=7)
    batch = {k: v for k, v in tensors.items()}
    out1 = trainer.train_step(batch)
    out2 = trainer.train_step(batch)
    assert "actor_loss" not in out1     # first update: critic only
    assert "actor_loss" in out2         # second update: actor fires (policy_delay=2)
    assert "critic_loss" in out1 and "critic_loss" in out2


def test_actor_update_changes_zhead():
    trainer = ResidualTD3(_actor(8), 8, TD3Config(policy_delay=1), device="cpu")
    tensors = _bandit_tensors(n=128, d=8, seed=8)
    before = [p.detach().clone() for p in trainer.actor.z_head.parameters()]
    # warm the critic so the -Q gradient is non-trivial
    trainer.fit_critics(tensors, steps=50, batch_size=64, seed=9)
    trainer.train_step({k: v for k, v in tensors.items()})
    after = list(trainer.actor.z_head.parameters())
    changed = any(not torch.equal(b, a) for b, a in zip(before, after))
    assert changed


def test_actor_update_with_teacher_mix_states_runs():
    trainer = ResidualTD3(_actor(8), 8, TD3Config(policy_delay=1), device="cpu")
    tensors = _bandit_tensors(n=64, d=8, seed=10)
    trainer.fit_critics(tensors, steps=20, batch_size=32, seed=11)
    s_emb = tensors["emb"]
    teacher_emb = torch.randn(32, 8)
    loss = trainer.actor_update(s_emb, teacher_emb)
    assert isinstance(loss, float)
