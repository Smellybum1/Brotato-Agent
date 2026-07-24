"""Unit tests for Stage F Phase 2 replay assembly (design §2/§3, §6.1 rung 1).

Reward assembly on a synthetic fixture, n-step segmentation (fallback + temporal
breaks), the post-reconnect recovery-window exclusion, delta=0 handling, the
teacher-mixing sampler, and connection-partitioned act-log parsing. Pure /
torch-free except the sampler and telemetry-file tests.
"""
from __future__ import annotations

import json
import math

import pytest

from trainer.rl.replay import (
    ActRecord,
    DEFAULT_DT_MAX_MS,
    RewardConfig,
    RunTelemetry,
    TickTelemetry,
    TeacherMixSampler,
    assemble_transitions,
    build_run_telemetry,
    parse_sidecar_actlog,
)

R = RewardConfig()  # defaults: damage 1, wave 1, victory 5, intervention 0.1, tau 15


def _tick(seq, wave, hp, *, source="student", valid=True, dt=50.0, delta=1.0, max_hp=10.0):
    return TickTelemetry(
        seq=seq, source=source, valid=valid, wave=wave, hp=hp,
        max_hp=max_hp, control_dt_ms=dt, delta_deg=delta,
    )


# ---------------------------------------------------------------------------
# Reward assembly (nstep=1 -> clean per-step values)
# ---------------------------------------------------------------------------
def test_damage_cost_normalized_by_max_hp():
    # hp holds then drops 10 -> 8 across step 1->2 with max_hp 10 => cost 0.2.
    ticks = [_tick(1, 1, 10.0), _tick(2, 1, 10.0), _tick(3, 1, 8.0)]
    run = RunTelemetry("r", ticks, terminal_result="defeat")
    states, trans = assemble_transitions(run, R, nstep=1)
    # transition starting at state 0 covers step 0->1: no damage.
    assert trans[0].reward_nstep == pytest.approx(0.0)
    # transition starting at state 1 covers step 1->2: -0.2.
    assert trans[1].reward_nstep == pytest.approx(-0.2)


def test_wave_completed_bonus():
    ticks = [_tick(1, 1, 10.0), _tick(2, 2, 10.0)]  # wave increments across the step
    run = RunTelemetry("r", ticks, terminal_result="defeat")
    _, trans = assemble_transitions(run, R, nstep=1)
    assert trans[0].reward_nstep == pytest.approx(1.0)


def test_victory_terminal_bonus_and_done():
    ticks = [_tick(1, 20, 10.0), _tick(2, 20, 10.0)]
    run = RunTelemetry("r", ticks, terminal_result="victory")
    _, trans = assemble_transitions(run, R, nstep=1)
    term = [t for t in trans if t.done == 1.0]
    assert len(term) == 1
    assert term[0].reward_nstep == pytest.approx(5.0)


def test_defeat_has_no_terminal_bonus():
    ticks = [_tick(1, 20, 10.0), _tick(2, 20, 10.0)]
    run = RunTelemetry("r", ticks, terminal_result="defeat")
    _, trans = assemble_transitions(run, R, nstep=1)
    assert all(t.done == 0.0 for t in trans)


def test_discount_uses_next_tick_dt():
    ticks = [_tick(1, 1, 10.0), _tick(2, 1, 10.0, dt=100.0)]
    run = RunTelemetry("r", ticks, terminal_result="defeat")
    _, trans = assemble_transitions(run, R, nstep=1)
    expected = math.exp(-(0.1) / R.tau_sec)
    assert trans[0].gamma_bootstrap == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------
def test_temporal_discontinuity_breaks_segment():
    # A large control_dt_ms (> dt_max) on tick 3 breaks the chain there.
    ticks = [
        _tick(1, 1, 10.0), _tick(2, 1, 10.0),
        _tick(3, 2, 10.0, dt=DEFAULT_DT_MAX_MS + 100.0), _tick(4, 2, 10.0),
    ]
    run = RunTelemetry("r", ticks, terminal_result="defeat")
    states, trans = assemble_transitions(run, R, nstep=5)
    assert len(states) == 4
    # No transition may bootstrap across the seq2->seq3 break.
    # Segment A = {s1,s2} (1 step), Segment B = {s3,s4} (1 step) => 2 transitions.
    assert len(trans) == 2


def test_seq_gap_breaks_segment():
    ticks = [_tick(1, 1, 10.0), _tick(2, 1, 10.0), _tick(4, 1, 10.0), _tick(5, 1, 10.0)]
    run = RunTelemetry("r", ticks, terminal_result="defeat")
    _, trans = assemble_transitions(run, R, nstep=5)
    # {1,2} and {4,5} -> 1 step each.
    assert len(trans) == 2


def test_fallback_breaks_and_adds_intervention_cost():
    ticks = [
        _tick(1, 3, 10.0), _tick(2, 3, 10.0), _tick(3, 3, 10.0),
        _tick(4, 3, 10.0, source="teacher_fallback", valid=False, delta=None),
        _tick(5, 3, 10.0), _tick(6, 3, 10.0), _tick(7, 3, 10.0),
    ]
    run = RunTelemetry("r", ticks, terminal_result="defeat")
    states, trans = assemble_transitions(run, R, nstep=1, recovery_ticks=1)
    # states: seq 1,2,3 (seg A), seq 6,7 (seg B; seq5 excluded as recovery).
    assert len(states) == 5
    inter = [t for t in trans if t.done == 1.0 and t.reward_nstep == pytest.approx(-R.w_intervention)]
    assert len(inter) == 1


def test_recovery_window_excludes_ticks_after_fallback():
    ticks = [
        _tick(1, 3, 10.0),
        _tick(2, 3, 10.0, source="teacher_fallback", valid=False, delta=None),
        _tick(3, 3, 10.0), _tick(4, 3, 10.0), _tick(5, 3, 10.0),
    ]
    run = RunTelemetry("r", ticks, terminal_result="defeat")
    states, _ = assemble_transitions(run, R, nstep=5, recovery_ticks=2)
    # seq1 (seg alone), then fallback; seq3,seq4 are recovery-excluded; seq5 usable.
    seqs = sorted(s.seq for s in states)
    assert seqs == [1, 5]


def test_none_delta_becomes_zero():
    ticks = [_tick(1, 1, 10.0, delta=None), _tick(2, 1, 10.0, delta=None)]
    run = RunTelemetry("r", ticks, terminal_result="defeat")
    _, trans = assemble_transitions(run, R, nstep=1)
    assert trans[0].delta == 0.0


def test_transition_count_matches_start_steps_nstep():
    ticks = [_tick(s, 1, 10.0) for s in range(1, 8)]  # 7 contiguous states, 6 steps
    run = RunTelemetry("r", ticks, terminal_result="defeat")
    _, trans = assemble_transitions(run, R, nstep=5)
    assert len(trans) == 6  # one transition per start step


# ---------------------------------------------------------------------------
# Teacher-mixing sampler (delta=0 manifold)
# ---------------------------------------------------------------------------
def test_teacher_mix_sampler_shape_and_dtype():
    np = pytest.importorskip("numpy")
    torch = pytest.importorskip("torch")
    emb = np.random.randn(20, 8).astype(np.float32)
    sampler = TeacherMixSampler(emb)
    assert len(sampler) == 20
    rng = np.random.default_rng(0)
    batch = sampler.sample(6, rng)
    assert isinstance(batch, torch.Tensor)
    assert tuple(batch.shape) == (6, 8)


# ---------------------------------------------------------------------------
# Act-log parsing (connection-partitioned; probe + actor lines)
# ---------------------------------------------------------------------------
def test_parse_sidecar_actlog_partitions_on_handshake(tmp_path):
    lines = [
        {"event": "startup"},
        {"event": "handshake_ok", "run_id": "a"},
        {"event": "act", "seq": 1, "delta_deg": 2.5, "teacher_x": 0.6, "teacher_y": 0.8},
        {"event": "act", "seq": 2, "delta_deg": None, "teacher_x": 0.0, "teacher_y": 0.0},
        {"event": "handshake_ok", "run_id": "b"},
        {"event": "act", "seq": 1, "delta_deg": -1.0, "teacher_x": 1.0, "teacher_y": 0.0,
         "z": 0.3, "sigma": 0.3},
    ]
    path = tmp_path / "log.jsonl"
    path.write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")
    maps = parse_sidecar_actlog(path)
    assert set(maps.keys()) == {0, 1}
    assert maps[0][1] == ActRecord(delta_deg=2.5, teacher_x=0.6, teacher_y=0.8)
    assert maps[0][2].delta_deg is None
    assert maps[1][1].z == 0.3 and maps[1][1].sigma == 0.3


# ---------------------------------------------------------------------------
# Telemetry build from a tiny synthetic events.jsonl
# ---------------------------------------------------------------------------
def test_build_run_telemetry_joins_capture_and_act(tmp_path):
    run_id = "run_x"
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    events = [
        {"event": "run_start", "payload": {"run_id": run_id}},
        {"event": "combat_capture", "payload": {
            "capture_seq": 1, "valid": True, "wave": 1, "control_dt_ms": 50,
            "player": {"hp": 10, "max_hp": 10}}},
        {"event": "student_tick", "payload": {"seq": 1, "source": "student"}},
        {"event": "combat_capture", "payload": {
            "capture_seq": 2, "valid": True, "wave": 1, "control_dt_ms": 50,
            "player": {"hp": 8, "max_hp": 10}}},
        {"event": "student_tick", "payload": {"seq": 2, "source": "student"}},
        {"event": "run_end", "payload": {"result": "defeat"}},
    ]
    (run_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(x) for x in events), encoding="utf-8"
    )
    act_map = {1: ActRecord(2.0, 0.6, 0.8), 2: ActRecord(-1.5, 0.1, 0.9)}
    run = build_run_telemetry(run_id, tmp_path, act_map)
    assert run.terminal_result == "defeat"
    assert len(run.ticks) == 2
    assert run.ticks[0].hp == 10.0 and run.ticks[0].delta_deg == 2.0
    assert run.ticks[1].hp == 8.0 and run.ticks[1].delta_deg == -1.5
