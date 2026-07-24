"""WP2 Stage F Phase 2 — residual reinforcement-learning package.

Off-policy residual actor-critic (TD3 flavor, RLPD teacher-mixing) that learns a
small bounded angular residual on top of the frozen teacher action, per
``.tmp/wp2_stage_f_phase2_design.md``. The residual is served through the
existing loopback sidecar; the mod, protocol, and safety rails are untouched.

Modules:
    residual_actor  -- ResidualActor (bc_v2_f trunk + zero-init z-head; delta =
                       theta_max * tanh(z)); serving-forward + sha-stable ckpt.
    replay          -- transition assembly from run telemetry (capture stream +
                       sidecar act log), reward assembly (design §2), n-step
                       segmentation, teacher-mixing sampler.
    td3_residual    -- twin critics on the trunk, target networks, delayed actor
                       updates, n-step targets, actor L2-to-zero, 50/50 mixing.
"""
from __future__ import annotations

from trainer.rl.residual_actor import (
    DEFAULT_THETA_MAX_DEG,
    ResidualActor,
    ResidualActorConfig,
    load_residual_actor,
    rotate_action,
    save_residual_actor,
    trunk_embedding,
)

__all__ = [
    "DEFAULT_THETA_MAX_DEG",
    "ResidualActor",
    "ResidualActorConfig",
    "load_residual_actor",
    "rotate_action",
    "save_residual_actor",
    "trunk_embedding",
]
