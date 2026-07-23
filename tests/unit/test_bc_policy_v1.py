"""CPU-only unit tests for the WP2 BC policy model (trainer/models/bc_policy_v1)."""

import math

import pytest
import torch

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


torch.manual_seed(0)


def _make_batch(model: BCPolicyV1, batch: int, *, seed: int = 0, extreme: bool = False):
    """Build a random (globals, entities, masks) batch matching the model config."""

    g = torch.Generator().manual_seed(seed)
    cfg = model.config
    if extreme:
        globals_t = torch.full((batch, cfg.global_dim), 1.0)
        globals_t[:, ::2] = -1.0
    else:
        globals_t = torch.randn(batch, cfg.global_dim, generator=g)

    entities = {}
    masks = {}
    for spec in cfg.group_specs:
        if extreme:
            feats = torch.full((batch, spec.capacity, cfg.entity_feature_dim), 1.0)
            feats[:, :, ::2] = -1.0
        else:
            feats = torch.randn(
                batch, spec.capacity, cfg.entity_feature_dim, generator=g
            )
        # Randomly populate a prefix of rows per sample (threat-ranked packing).
        mask = torch.zeros(batch, spec.capacity)
        for b in range(batch):
            n = torch.randint(0, spec.capacity + 1, (1,), generator=g).item()
            mask[b, :n] = 1.0
        entities[spec.name] = feats
        masks[spec.name] = mask
    return globals_t, entities, masks


@pytest.fixture
def model():
    return BCPolicyV1(BCPolicyConfig()).eval()


# -- output contract --------------------------------------------------------
def test_output_shape_and_range(model):
    globals_t, entities, masks = _make_batch(model, 5)
    out = model(globals_t, entities, masks)
    assert out.shape == (5, 2)
    assert torch.all(out >= -1.0) and torch.all(out <= 1.0)


# -- padded-row inertness ---------------------------------------------------
def test_padded_rows_are_inert(model):
    globals_t, entities, masks = _make_batch(model, 4, seed=1)
    base = model(globals_t, entities, masks)

    perturbed = {k: v.clone() for k, v in entities.items()}
    for spec in model.config.group_specs:
        mask = masks[spec.name]
        pad = mask == 0  # [B, cap]
        noise = torch.randn_like(perturbed[spec.name]) * 1e3
        perturbed[spec.name][pad] = perturbed[spec.name][pad] + noise[pad]

    after = model(globals_t, perturbed, masks)
    assert torch.equal(base, after)


# -- all-empty group --------------------------------------------------------
def test_all_empty_group_is_finite(model):
    globals_t, entities, masks = _make_batch(model, 3, seed=2)
    for spec in model.config.group_specs:
        masks[spec.name].zero_()  # every group empty
    out = model(globals_t, entities, masks)
    assert torch.isfinite(out).all()
    assert out.shape == (3, 2)


# -- NaN safety with extreme inputs -----------------------------------------
def test_no_nan_with_saturated_inputs(model):
    globals_t, entities, masks = _make_batch(model, 4, extreme=True)
    out = model(globals_t, entities, masks)
    assert torch.isfinite(out).all()


# -- determinism in eval ----------------------------------------------------
def test_determinism_in_eval_mode():
    torch.manual_seed(7)
    m = BCPolicyV1(BCPolicyConfig()).eval()
    globals_t, entities, masks = _make_batch(m, 6, seed=3)
    a = m(globals_t, entities, masks)
    b = m(globals_t, entities, masks)
    assert torch.equal(a, b)


# -- previous-action dropout ------------------------------------------------
def test_prev_action_dropout_p1_zeros_configured_indices():
    cfg = BCPolicyConfig(previous_action_dropout_p=1.0)
    m = BCPolicyV1(cfg).train()
    globals_t, entities, masks = _make_batch(m, 5, seed=4)

    ix, iy = cfg.prev_action_indices
    zeroed = globals_t.clone()
    zeroed[:, ix] = 0.0
    zeroed[:, iy] = 0.0

    # p=1.0 in train mode must equal feeding globals with prev-action zeroed,
    # evaluated deterministically in eval mode.
    m_eval = m.eval()
    out_dropout_equiv = m_eval(zeroed, entities, masks)

    m.train()
    torch.manual_seed(123)
    out_train = m(globals_t, entities, masks)
    assert torch.allclose(out_train, out_dropout_equiv, atol=1e-6)


def test_prev_action_dropout_p0_is_identity():
    cfg = BCPolicyConfig(previous_action_dropout_p=0.0)
    m = BCPolicyV1(cfg)
    globals_t, entities, masks = _make_batch(m, 5, seed=5)

    m.train()
    out_train = m(globals_t, entities, masks)
    m.eval()
    out_eval = m(globals_t, entities, masks)
    assert torch.equal(out_train, out_eval)


def test_prev_action_dropout_only_touches_two_indices():
    """Dropout must not alter any global entry other than the two configured."""
    cfg = BCPolicyConfig(previous_action_dropout_p=1.0)
    m = BCPolicyV1(cfg)
    globals_t = torch.randn(8, cfg.global_dim)
    dropped = m._apply_prev_action_dropout(globals_t.requires_grad_(False))
    ix, iy = cfg.prev_action_indices
    diff = (dropped != globals_t)
    changed_cols = diff.any(dim=0).nonzero().flatten().tolist()
    assert set(changed_cols) <= {ix, iy}
    assert torch.all(dropped[:, ix] == 0.0)
    assert torch.all(dropped[:, iy] == 0.0)


# -- loss: zero-magnitude target masks the direction term -------------------
def test_zero_magnitude_target_masks_direction():
    pred = torch.tensor([[0.7, 0.7]])
    zero_target = torch.tensor([[0.0, 0.0]])
    loss, comp = bc_loss(pred, zero_target)
    # Direction term is masked out; only the magnitude Huber survives.
    mag = pred.norm()  # |pred| - 0
    expected_mag = 0.5 * (0.5 * min(mag, torch.tensor(0.5)) ** 2) if mag <= 0.5 else None
    # |pred| ~ 0.99 > delta=0.5 -> linear Huber region.
    huber = 0.5 * (mag - 0.5 * 0.5)
    expected = (0.5 * huber).item()
    assert math.isclose(loss.item(), expected, rel_tol=1e-5)
    assert comp["direction_masked_fraction"].item() == 1.0


# -- loss: perfect prediction on unit target -> ~0 --------------------------
def test_perfect_prediction_zero_loss():
    target = torch.tensor([[1.0, 0.0], [0.0, 1.0], [0.6, 0.8]])
    loss, comp = bc_loss(target.clone(), target)
    assert loss.item() < 1e-6
    assert comp["direction_term"].item() < 1e-6
    assert comp["magnitude_term"].item() < 1e-6


# -- loss: opposite unit direction -> direction term ~= 2 -------------------
def test_opposite_direction_term_is_two():
    target = torch.tensor([[1.0, 0.0]])
    pred = torch.tensor([[-1.0, 0.0]])
    loss, comp = bc_loss(pred, target)
    assert math.isclose(comp["direction_term"].item(), 2.0, rel_tol=1e-5)
    # magnitude matches -> magnitude term ~ 0, so loss ~ direction term.
    assert math.isclose(comp["magnitude_term"].item(), 0.0, abs_tol=1e-6)
    assert math.isclose(loss.item(), 2.0, rel_tol=1e-5)


# -- loss: Huber magnitude behaves at |pred|=0 vs 1 -------------------------
def test_magnitude_huber_regions():
    target = torch.tensor([[1.0, 0.0]])
    # |pred| = 0 -> residual -1, |res| > delta=0.5 -> linear: 0.5*(1 - 0.25)=0.375
    pred_zero = torch.tensor([[0.0, 0.0]])
    _, comp0 = bc_loss(pred_zero, target)
    assert math.isclose(comp0["magnitude_term"].item(), 0.375, rel_tol=1e-5)
    # |pred| = 1 -> residual 0 -> Huber 0
    pred_one = torch.tensor([[1.0, 0.0]])
    _, comp1 = bc_loss(pred_one, target)
    assert math.isclose(comp1["magnitude_term"].item(), 0.0, abs_tol=1e-7)
    # Small residual 0.2 < delta -> quadratic: 0.5*0.2^2 = 0.02
    pred_small = torch.tensor([[0.8, 0.0]])
    _, comp2 = bc_loss(pred_small, target)
    assert math.isclose(comp2["magnitude_term"].item(), 0.02, rel_tol=1e-5)


# -- gradient flow ----------------------------------------------------------
def test_gradient_flows_to_all_parameters():
    m = BCPolicyV1(BCPolicyConfig()).train()
    globals_t, entities, masks = _make_batch(m, 8, seed=9)
    target = torch.randn(8, 2)
    target = target / target.norm(dim=1, keepdim=True)  # unit targets
    pred = m(globals_t, entities, masks)
    loss, _ = bc_loss(pred, target)
    loss.backward()
    missing = [n for n, p in m.named_parameters() if p.grad is None]
    assert not missing, f"no grad for: {missing}"
    assert all(torch.isfinite(p.grad).all() for p in m.parameters())


# -- metric helpers ---------------------------------------------------------
def test_metric_helpers():
    target = torch.tensor([[1.0, 0.0], [0.0, 0.0]])
    pred = torch.tensor([[0.0, 1.0], [0.5, 0.5]])
    # cosine of orthogonal -> 0
    cos = cosine_similarity(pred, target)
    assert math.isclose(cos[0].item(), 0.0, abs_tol=1e-6)
    # angular error: 90deg for row 0, NaN for zero-target row 1
    ang = angular_error_deg(pred, target)
    assert math.isclose(ang[0].item(), 90.0, rel_tol=1e-4)
    assert math.isnan(ang[1].item())
    # magnitude error signed
    mag = magnitude_error(pred, target)
    assert math.isclose(mag[0].item(), 0.0, abs_tol=1e-6)
    # saturation fraction
    sat = saturation_fraction(torch.tensor([[1.0, 0.5], [0.995, -0.1]]))
    assert math.isclose(sat.item(), 2.0 / 4.0, rel_tol=1e-6)


# -- parameter budget -------------------------------------------------------
def test_parameter_count_under_budget():
    m = BCPolicyV1(BCPolicyConfig())
    n = m.num_parameters()
    print(f"\nBCPolicyV1 parameter count: {n:,}")
    assert n < 2_000_000
