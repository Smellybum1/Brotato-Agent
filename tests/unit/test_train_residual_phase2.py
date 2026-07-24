"""Unit tests for the Stage F Phase 2 training-script CLI (config plumbing only).

Covers the ``--actor-l2`` knob that overrides the actor L2-to-zero regularizer
(TD3Config.lambda_zero): default preservation, override parsing, and that the
parsed value feeds a TD3Config unchanged. No training is run here.
"""
from __future__ import annotations

import pytest

from scripts.train_residual_phase2 import DEFAULT_ACTOR_L2, _parse_args


def test_actor_l2_default_is_lambda_zero():
    args = _parse_args(["--mode", "iterate"])
    assert args.actor_l2 == DEFAULT_ACTOR_L2 == 0.01


def test_actor_l2_override_parsed():
    args = _parse_args(["--mode", "iterate", "--actor-l2", "0.001"])
    assert args.actor_l2 == pytest.approx(0.001)


def test_actor_l2_absent_leaves_default():
    # Other iterate flags present, knob absent => default retained.
    args = _parse_args(["--mode", "iterate", "--iteration", "3", "--seed", "3"])
    assert args.actor_l2 == pytest.approx(0.01)


def test_default_matches_td3config_lambda_zero():
    # The literal default must track the trainer's TD3Config default.
    td3 = pytest.importorskip("trainer.rl.td3_residual")
    assert DEFAULT_ACTOR_L2 == td3.TD3Config().lambda_zero


def test_actor_l2_feeds_td3config_lambda_zero():
    # Config plumbing: the parsed knob maps onto TD3Config.lambda_zero.
    td3 = pytest.importorskip("trainer.rl.td3_residual")
    args = _parse_args(["--mode", "iterate", "--actor-l2", "0.0003"])
    cfg = td3.TD3Config(lambda_zero=args.actor_l2)
    assert cfg.lambda_zero == pytest.approx(0.0003)
