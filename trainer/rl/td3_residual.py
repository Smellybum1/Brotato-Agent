"""TD3-style off-policy residual actor-critic (design §3, RLPD teacher-mixing).

Twin critics ``Q(emb, delta)`` on the frozen ``bc_v2_f`` trunk embedding, target
networks with Polyak averaging, delayed + target-smoothed actor updates, n-step
targets with bootstrap, an actor L2-to-zero regularizer (lambda_0 = 0.01) pulling
the residual toward the teacher, and 50/50 batch mixing between reward-bearing
residual transitions and delta=0 teacher-mixing states (the zero-residual
manifold, design §3).

The critic consumes the precomputed frozen-trunk embedding plus the scalar
residual ``delta`` (degrees); it never re-encodes observations. The actor is the
:class:`~trainer.rl.residual_actor.ResidualActor` z-head reading the same
embeddings, so ``pi(s) = delta_deg_from_embedding(emb)`` is differentiable while
the trunk stays frozen.

:meth:`ResidualTD3.fit_critics` is the ladder rung-2 entry point: it fits the
critics with the actor held at its zero-init (bootstrap action ~ 0) and reports
TD-loss convergence plus the ``Q(s,+delta) - Q(s,-delta)`` dose-response sign.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

import torch
from torch import Tensor, nn


@dataclass(frozen=True)
class TD3Config:
    """TD3 residual hyperparameters (design §3)."""

    theta_max_deg: float = 5.0
    critic_hidden: tuple[int, ...] = (256, 256)
    critic_lr: float = 3e-4
    actor_lr: float = 3e-4
    policy_delay: int = 2            # delayed actor updates (TD3)
    polyak: float = 0.005           # target soft-update rate
    target_noise_deg: float = 1.0   # target-smoothing noise std (degrees)
    noise_clip_deg: float = 2.0     # target-smoothing noise clip (degrees)
    lambda_zero: float = 0.01       # actor L2-to-zero on |delta|^2
    teacher_mix_fraction: float = 0.5
    weight_decay: float = 0.0


class Critic(nn.Module):
    """Single Q-head over ``[embedding ++ delta]`` -> scalar."""

    def __init__(self, embedding_dim: int, hidden: tuple[int, ...]) -> None:
        super().__init__()
        layers: list[nn.Module] = []
        prev = embedding_dim + 1
        for width in hidden:
            layers.append(nn.Linear(prev, width))
            layers.append(nn.ReLU())
            prev = width
        layers.append(nn.Linear(prev, 1))
        self.net = nn.Sequential(*layers)

    def forward(self, embedding: Tensor, delta: Tensor) -> Tensor:
        x = torch.cat([embedding, delta.unsqueeze(-1)], dim=-1)
        return self.net(x).squeeze(-1)


class TwinCritic(nn.Module):
    """Two independent Q-heads (TD3 clipped double-Q)."""

    def __init__(self, embedding_dim: int, hidden: tuple[int, ...]) -> None:
        super().__init__()
        self.q1 = Critic(embedding_dim, hidden)
        self.q2 = Critic(embedding_dim, hidden)

    def forward(self, embedding: Tensor, delta: Tensor) -> tuple[Tensor, Tensor]:
        return self.q1(embedding, delta), self.q2(embedding, delta)


class ResidualTD3:
    """Off-policy residual actor-critic trainer (twin critics + zero-init actor)."""

    def __init__(
        self,
        actor: Any,                 # trainer.rl.residual_actor.ResidualActor
        embedding_dim: int,
        config: TD3Config | None = None,
        *,
        device: str = "cpu",
    ) -> None:
        self.actor = actor
        self.config = config or TD3Config()
        self.device = torch.device(device)
        self.actor.to(self.device)

        self.critic = TwinCritic(embedding_dim, self.config.critic_hidden).to(self.device)
        self.critic_target = copy.deepcopy(self.critic).to(self.device)
        for p in self.critic_target.parameters():
            p.requires_grad_(False)

        # Target actor = a frozen copy of the z-head (trunk is shared + frozen).
        self.target_z_head = copy.deepcopy(self.actor.z_head).to(self.device)
        for p in self.target_z_head.parameters():
            p.requires_grad_(False)

        self.critic_opt = torch.optim.Adam(
            self.critic.parameters(), lr=self.config.critic_lr, weight_decay=self.config.weight_decay
        )
        self.actor_opt = torch.optim.Adam(self.actor.actor_parameters(), lr=self.config.actor_lr)
        self._updates = 0

    # -- helpers -------------------------------------------------------------
    def _actor_delta(self, embedding: Tensor) -> Tensor:
        return self.actor.delta_deg_from_embedding(embedding)

    def _target_delta(self, embedding: Tensor) -> Tensor:
        theta = self.config.theta_max_deg
        z = self.target_z_head(embedding)
        return theta * torch.tanh(z).squeeze(-1)

    def _smoothed_target_delta(self, embedding: Tensor) -> Tensor:
        """Target policy delta with clipped Gaussian smoothing, bound to theta_max."""
        cfg = self.config
        base = self._target_delta(embedding)
        noise = torch.randn_like(base) * cfg.target_noise_deg
        noise = noise.clamp(-cfg.noise_clip_deg, cfg.noise_clip_deg)
        return (base + noise).clamp(-cfg.theta_max_deg, cfg.theta_max_deg)

    # -- critic update -------------------------------------------------------
    def critic_update(self, batch: dict[str, Tensor]) -> float:
        """One twin-critic TD update on a residual batch; returns the TD loss."""
        emb = batch["emb"]
        s_emb = emb.index_select(0, batch["s_idx"])
        sp_emb = emb.index_select(0, batch["sp_idx"])
        delta = batch["delta"]
        R = batch["reward_nstep"]
        gamma = batch["gamma_bootstrap"]
        done = batch["done"]

        with torch.no_grad():
            ap = self._smoothed_target_delta(sp_emb)
            q1t, q2t = self.critic_target(sp_emb, ap)
            q_next = torch.min(q1t, q2t)
            target = R + gamma * (1.0 - done) * q_next

        q1, q2 = self.critic(s_emb, delta)
        loss = nn.functional.mse_loss(q1, target) + nn.functional.mse_loss(q2, target)
        self.critic_opt.zero_grad(set_to_none=True)
        loss.backward()
        self.critic_opt.step()
        return float(loss.detach().cpu().item())

    # -- actor update --------------------------------------------------------
    def actor_update(self, s_emb: Tensor, teacher_emb: Tensor | None) -> float:
        """Delayed actor update: -Q1(s, pi(s)) + lambda_0 * |delta|^2.

        The residual states drive the -Q term (improve where value evidence
        exists); teacher-mix states add zero-residual manifold coverage to the
        L2-to-zero regularizer only (design §3 / replay deviation note).
        """
        cfg = self.config
        delta_s = self._actor_delta(s_emb)
        q1 = self.critic.q1(s_emb, delta_s)
        reg = (delta_s ** 2).mean()
        if teacher_emb is not None and teacher_emb.shape[0] > 0:
            delta_t = self._actor_delta(teacher_emb)
            reg = 0.5 * reg + 0.5 * (delta_t ** 2).mean()
        loss = -q1.mean() + cfg.lambda_zero * reg
        self.actor_opt.zero_grad(set_to_none=True)
        loss.backward()
        self.actor_opt.step()
        return float(loss.detach().cpu().item())

    # -- Polyak target sync --------------------------------------------------
    def _polyak(self) -> None:
        tau = self.config.polyak
        with torch.no_grad():
            for tp, sp in zip(self.critic_target.parameters(), self.critic.parameters()):
                tp.mul_(1.0 - tau).add_(tau * sp)
            for tp, sp in zip(self.target_z_head.parameters(), self.actor.z_head.parameters()):
                tp.mul_(1.0 - tau).add_(tau * sp)

    # -- full train step (critic + delayed actor) ---------------------------
    def train_step(
        self, batch: dict[str, Tensor], teacher_emb: Tensor | None = None
    ) -> dict[str, float]:
        out = {"critic_loss": self.critic_update(batch)}
        self._updates += 1
        if self._updates % self.config.policy_delay == 0:
            s_emb = batch["emb"].index_select(0, batch["s_idx"])
            out["actor_loss"] = self.actor_update(s_emb, teacher_emb)
            self._polyak()
        return out

    # -- rung-2 critic-only fit ---------------------------------------------
    def fit_critics(
        self,
        tensors: dict[str, Tensor],
        *,
        steps: int,
        batch_size: int,
        seed: int = 0,
        log_every: int = 0,
        log: Any = None,
    ) -> list[float]:
        """Fit the twin critics on a fixed transition set (actor frozen at init).

        The actor stays at its zero-init, so the bootstrap action is ~0 and the
        critics regress the n-step returns of the logged residuals. Returns the
        TD-loss history (one entry per step).
        """
        n = int(tensors["s_idx"].shape[0])
        gen = torch.Generator(device="cpu").manual_seed(seed)
        emb = tensors["emb"]
        history: list[float] = []
        for step in range(steps):
            idx = torch.randint(0, n, (batch_size,), generator=gen).to(self.device)
            batch = {
                "emb": emb,
                "s_idx": tensors["s_idx"].index_select(0, idx),
                "sp_idx": tensors["sp_idx"].index_select(0, idx),
                "delta": tensors["delta"].index_select(0, idx),
                "reward_nstep": tensors["reward_nstep"].index_select(0, idx),
                "gamma_bootstrap": tensors["gamma_bootstrap"].index_select(0, idx),
                "done": tensors["done"].index_select(0, idx),
            }
            loss = self.critic_update(batch)
            self._polyak()
            history.append(loss)
            if log_every and log is not None and (step % log_every == 0 or step == steps - 1):
                log(f"  [critic] step {step:5d}/{steps}  td_loss={loss:.6f}")
        return history

    # -- dose-response probe -------------------------------------------------
    @torch.no_grad()
    def dose_response(
        self, embedding: Tensor, delta_mag_deg: float
    ) -> dict[str, float]:
        """Mean ``Q1(s, +delta) - Q1(s, -delta)`` over ``embedding`` states."""
        pos = torch.full((embedding.shape[0],), float(delta_mag_deg), device=embedding.device)
        neg = torch.full((embedding.shape[0],), float(-delta_mag_deg), device=embedding.device)
        q_pos = self.critic.q1(embedding, pos)
        q_neg = self.critic.q1(embedding, neg)
        diff = (q_pos - q_neg)
        mean = float(diff.mean().cpu().item())
        return {
            "delta_mag_deg": float(delta_mag_deg),
            "mean_q_pos": float(q_pos.mean().cpu().item()),
            "mean_q_neg": float(q_neg.mean().cpu().item()),
            "mean_diff": mean,
            "sign": (1 if mean > 0 else (-1 if mean < 0 else 0)),
            "n": int(embedding.shape[0]),
        }
