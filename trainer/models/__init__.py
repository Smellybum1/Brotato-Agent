"""Trainer model modules for WP2 behavior cloning."""

from trainer.models.bc_policy_v1 import (
    BCPolicyConfig,
    BCPolicyV1,
    GroupSpec,
    angular_error_deg,
    bc_loss,
    cosine_similarity,
    magnitude_error,
    saturation_fraction,
)

__all__ = [
    "BCPolicyConfig",
    "BCPolicyV1",
    "GroupSpec",
    "angular_error_deg",
    "bc_loss",
    "cosine_similarity",
    "magnitude_error",
    "saturation_fraction",
]
