"""Replay assembly for WP2 Stage F Phase 2 (design §2, §3 credit segmentation).

Turns raw run telemetry into off-policy n-step transitions for the residual
actor-critic. The pipeline is deliberately split so the reward + segmentation
core is torch-free and unit-testable on a synthetic fixture:

  1. :func:`parse_sidecar_actlog` -- partition the sidecar act log on
     ``handshake_ok`` into per-connection ``{seq -> ActRecord}`` maps (the
     round-2 partition-on-handshake approach), tolerant of both the probe act
     line (``delta_deg``/``teacher_*``) and the residual-actor act line
     (``+ z``/``sigma``).
  2. :func:`build_run_telemetry` -- one streaming pass over a run's
     ``events.jsonl`` pairing each ``student_tick`` with the capture it acted on
     (seq join, connection-scoped act map), yielding light per-tick telemetry
     (hp / max_hp / wave / control_dt_ms / source / delta) plus the run's
     terminal result. No observations are held in memory here.
  3. :func:`assemble_transitions` -- PURE reward assembly (design §2: damage /
     max_hp dense cost, +1 per wave completed, +5 victory terminal, -0.1 per
     infrastructure-fallback tick) and n-step-5 segmentation broken at fallback
     ticks and temporal discontinuities, with the 2 s post-reconnect recovery
     window excluded. Emits transitions indexed into a compact ``states`` array.
  4. :func:`encode_states_to_embeddings` -- a second streaming pass that encodes
     only the states referenced by transitions and runs them through the frozen
     trunk to a ``[N, 256]`` embedding matrix (the only torch step).
  5. :class:`ReplayPool` / :class:`TeacherMixSampler` -- batch sampling for the
     trainer, including the delta=0 teacher-mixing transitions drawn from the
     frozen ``combat_obs_v1`` shards (design §3, RLPD zero-residual manifold).

Design deviation recorded here (§3 teacher mixing): the ``combat_obs_v1`` shards
store ``(obs, teacher_action)`` for behavior cloning with NO per-tick reward or
next-state linkage, so they cannot supply TD targets. In v1 the teacher-mixed
delta=0 states therefore feed the ACTOR update only (the -Q(s,pi(s)) +
lambda|delta|^2 term over the zero-residual manifold); the critic trains solely
on reward-bearing residual/probe transitions. This is faithful to F-2
(off-policy-first) and the "pull toward zero-residual" intent without fabricating
rewards for BC data.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

# ---------------------------------------------------------------------------
# Reward configuration (design §2 weights; loadable from reward_v1.yaml)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RewardConfig:
    """reward_v2 weights + discount (design §2). Costs enter negated at assembly."""

    w_damage: float = 1.0          # damage_taken / max_hp, per tick (a cost)
    w_wave: float = 1.0            # +1 per wave_completed
    w_victory: float = 5.0        # terminal victory bonus
    w_intervention: float = 0.1   # per infrastructure-fallback tick (a cost)
    tau_sec: float = 15.0         # discount gamma = exp(-dt/tau)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "RewardConfig":
        import yaml

        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        block = data.get("reward_v2", {}) or {}
        w = block.get("weights", {}) or {}
        disc = block.get("discount", {}) or {}
        return cls(
            w_damage=float(w.get("damage_taken_per_max_hp", 1.0)),
            w_wave=float(w.get("wave_completed", 1.0)),
            w_victory=float(w.get("victory_terminal", 5.0)),
            w_intervention=float(w.get("intervention_fallback_tick", 0.1)),
            tau_sec=float(disc.get("tau_sec", 15.0)),
        )


# Segmentation defaults (design §3 / r2 corrective_config conventions).
DEFAULT_NSTEP = 5
DEFAULT_RECOVERY_TICKS = 40      # 2 s post-reconnect at 20 Hz (design §3)
DEFAULT_DT_MAX_MS = 250.0        # temporal_valid gate (r2: control_dt_ms in (0,250])
STUDENT_SOURCE = "student"


# ---------------------------------------------------------------------------
# Sidecar act log (connection-partitioned)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ActRecord:
    """One sidecar act line: the applied residual + logged teacher action.

    ``delta_deg`` is ``None`` on a zero-teacher passthrough tick (no perturbation).
    ``z`` / ``sigma`` are present for residual-actor logs and ``None`` for the
    Phase-1 probe logs (which carry only ``delta_deg`` + ``teacher_*``).
    """

    delta_deg: float | None
    teacher_x: float
    teacher_y: float
    z: float | None = None
    sigma: float | None = None


def parse_sidecar_actlog(path: str | Path) -> dict[int, dict[int, ActRecord]]:
    """Partition a sidecar JSONL act log into ``{connection -> {seq -> ActRecord}}``.

    The connection index increments on each ``handshake_ok`` (round-2
    partition-on-handshake). Act lines before the first handshake are ignored.
    """
    act_maps: dict[int, dict[int, ActRecord]] = {}
    conn = -1
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        event = rec.get("event")
        if event == "handshake_ok":
            conn += 1
            act_maps.setdefault(conn, {})
        elif event == "act":
            if conn < 0:
                continue
            seq = int(rec["seq"])
            act_maps[conn][seq] = ActRecord(
                delta_deg=(None if rec.get("delta_deg") is None else float(rec["delta_deg"])),
                teacher_x=float(rec.get("teacher_x", 0.0)),
                teacher_y=float(rec.get("teacher_y", 0.0)),
                z=(None if rec.get("z") is None else float(rec.get("z"))),
                sigma=(None if rec.get("sigma") is None else float(rec.get("sigma"))),
            )
    return act_maps


# ---------------------------------------------------------------------------
# Per-tick telemetry (torch-free)
# ---------------------------------------------------------------------------
@dataclass
class TickTelemetry:
    """One control tick's reward-relevant scalars (no observation held here)."""

    seq: int
    source: str
    valid: bool
    wave: int
    hp: float
    max_hp: float
    control_dt_ms: float
    delta_deg: float | None      # applied residual (None => treat as 0 at assembly)


@dataclass
class RunTelemetry:
    run_id: str
    ticks: list[TickTelemetry]
    terminal_result: str | None   # "victory" / "defeat" / None


def build_run_telemetry(
    run_id: str,
    runs_root: str | Path,
    act_map: Mapping[int, ActRecord],
) -> RunTelemetry:
    """Stream a run's ``events.jsonl`` into per-tick telemetry (seq join).

    Each ``student_tick`` is paired with the most-recent ``combat_capture``'s
    player/wave scalars (the Phase-1 trajectory-join convention) and, via the
    connection-scoped ``act_map``, its applied residual delta. Ticks with a
    non-positive seq (e.g. ``not_connected`` fallbacks) are still recorded (as
    non-student) so recovery windows and segment breaks are honored.
    """
    events_path = Path(runs_root) / run_id / "events.jsonl"
    ticks: list[TickTelemetry] = []
    terminal: str | None = None
    last_cap: dict[str, Any] | None = None
    with events_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            e = json.loads(line)
            et = e.get("event")
            if et == "combat_capture":
                last_cap = e.get("payload", {}) or {}
            elif et == "student_tick":
                pl = e.get("payload", {}) or {}
                seq = pl.get("seq")
                source = str(pl.get("source", "unknown"))
                if last_cap is None:
                    continue
                player = last_cap.get("player", {}) or {}
                act = act_map.get(int(seq)) if isinstance(seq, int) else None
                ticks.append(
                    TickTelemetry(
                        seq=int(seq) if isinstance(seq, int) else -1,
                        source=source,
                        valid=bool(last_cap.get("valid", False)),
                        wave=int(last_cap.get("wave") or 0),
                        hp=float(player.get("hp", 0.0)),
                        max_hp=float(player.get("max_hp", 0.0)) or 1.0,
                        control_dt_ms=float(last_cap.get("control_dt_ms", 0.0)),
                        delta_deg=(act.delta_deg if act is not None else None),
                    )
                )
            elif et == "run_end":
                terminal = str((e.get("payload", {}) or {}).get("result")) or None
    return RunTelemetry(run_id=run_id, ticks=ticks, terminal_result=terminal)


# ---------------------------------------------------------------------------
# n-step transitions (torch-free assembly)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class StateRef:
    """A usable student state referenced by transitions (index = position)."""

    run_id: str
    seq: int
    wave: int


@dataclass(frozen=True)
class Transition:
    """One off-policy n-step residual transition.

    ``reward_nstep`` is the discounted n-step return; ``gamma_bootstrap`` is the
    product of per-step discounts to the bootstrap state ``sp_idx``. The critic
    target is ``reward_nstep + gamma_bootstrap * (1 - done) * Q'(sp, pi'(sp))``.
    """

    s_idx: int
    sp_idx: int
    delta: float
    reward_nstep: float
    gamma_bootstrap: float
    done: float
    wave: int


@dataclass
class _Step:
    s_pos: int
    sp_pos: int
    delta: float
    reward: float
    gamma: float
    done: float


def _mark_usable(
    ticks: list[TickTelemetry], recovery_ticks: int
) -> tuple[list[bool], list[bool]]:
    """Return (usable, followed_by_fallback) per raw tick.

    A tick is usable iff it is a valid student tick outside the post-reconnect
    recovery window. ``followed_by_fallback[i]`` is True iff the next raw tick is
    an infrastructure fallback (used to attach the intervention terminal).
    """
    n = len(ticks)
    usable = [False] * n
    recovery_remaining = 0
    for i, t in enumerate(ticks):
        is_student = t.source == STUDENT_SOURCE and t.valid and t.seq >= 1
        if not is_student:
            # Any fallback / invalid tick opens a fresh recovery window.
            recovery_remaining = recovery_ticks
            usable[i] = False
            continue
        if recovery_remaining > 0:
            recovery_remaining -= 1
            usable[i] = False
        else:
            usable[i] = True
    followed_by_fallback = [False] * n
    for i in range(n - 1):
        nxt = ticks[i + 1]
        if not (nxt.source == STUDENT_SOURCE and nxt.valid and nxt.seq >= 1):
            followed_by_fallback[i] = True
    return usable, followed_by_fallback


def assemble_transitions(
    run: RunTelemetry,
    reward: RewardConfig,
    *,
    nstep: int = DEFAULT_NSTEP,
    recovery_ticks: int = DEFAULT_RECOVERY_TICKS,
    dt_max_ms: float = DEFAULT_DT_MAX_MS,
    state_offset: int = 0,
) -> tuple[list[StateRef], list[Transition]]:
    """Assemble n-step transitions from one run's telemetry (pure, torch-free).

    ``state_offset`` shifts emitted state indices so multiple runs can share one
    global ``states``/embedding array. Returns ``(states, transitions)`` where
    each transition's ``s_idx``/``sp_idx`` index ``states`` (already offset).
    """
    ticks = run.ticks
    usable, followed_by_fallback = _mark_usable(ticks, recovery_ticks)

    # Compact usable states, remembering each raw index -> state position.
    states: list[StateRef] = []
    raw_to_state: dict[int, int] = {}
    for i, t in enumerate(ticks):
        if usable[i]:
            raw_to_state[i] = len(states)
            states.append(StateRef(run_id=run.run_id, seq=t.seq, wave=t.wave))

    # Break the usable stream into contiguous segments (seq+1 and dt in (0,dt_max]).
    segments: list[list[int]] = []   # each is a list of raw indices
    current: list[int] = []
    prev_raw: int | None = None
    for i, t in enumerate(ticks):
        if not usable[i]:
            continue
        contiguous = (
            prev_raw is not None
            and t.seq == ticks[prev_raw].seq + 1
            and 0.0 < t.control_dt_ms <= dt_max_ms
        )
        if not contiguous and current:
            segments.append(current)
            current = []
        current.append(i)
        prev_raw = i
    if current:
        segments.append(current)

    last_usable_raw = max(raw_to_state, default=None)

    # Build per-segment step lists, then n-step-assemble each segment.
    transitions: list[Transition] = []
    for seg in segments:
        steps: list[_Step] = []
        for a, b in zip(seg[:-1], seg[1:]):
            ta, tb = ticks[a], ticks[b]
            dmg = max(0.0, ta.hp - tb.hp)
            r = -reward.w_damage * (dmg / ta.max_hp)
            done = 0.0
            if tb.wave > ta.wave:
                r += reward.w_wave
            gamma = math.exp(-(max(tb.control_dt_ms, 0.0) / 1000.0) / reward.tau_sec)
            steps.append(
                _Step(
                    s_pos=state_offset + raw_to_state[a],
                    sp_pos=state_offset + raw_to_state[b],
                    delta=(ta.delta_deg or 0.0),
                    reward=r,
                    gamma=gamma,
                    done=done,
                )
            )
        last_raw = seg[-1]
        last_tick = ticks[last_raw]
        # Intervention terminal: segment ended into an infrastructure fallback
        # (ruling 11 -- fallback tick ends the n-step chain, policy_segment_done).
        if followed_by_fallback[last_raw]:
            steps.append(
                _Step(
                    s_pos=state_offset + raw_to_state[last_raw],
                    sp_pos=state_offset + raw_to_state[last_raw],
                    delta=(last_tick.delta_deg or 0.0),
                    reward=-reward.w_intervention,
                    gamma=1.0,
                    done=1.0,
                )
            )
        # Victory terminal: attach +w_victory to the run's final usable state.
        elif (
            run.terminal_result == "victory"
            and last_usable_raw is not None
            and last_raw == last_usable_raw
        ):
            steps.append(
                _Step(
                    s_pos=state_offset + raw_to_state[last_raw],
                    sp_pos=state_offset + raw_to_state[last_raw],
                    delta=(last_tick.delta_deg or 0.0),
                    reward=reward.w_victory,
                    gamma=1.0,
                    done=1.0,
                )
            )
        transitions.extend(_nstep_from_steps(steps, nstep))

    return states, transitions


def _nstep_from_steps(steps: list[_Step], nstep: int) -> list[Transition]:
    """Roll a contiguous per-segment step list into n-step transitions."""
    out: list[Transition] = []
    m = len(steps)
    for p in range(m):
        R = 0.0
        G = 1.0
        sp = steps[p].sp_pos
        done = 0.0
        for i in range(nstep):
            if p + i >= m:
                break
            st = steps[p + i]
            R += G * st.reward
            G *= st.gamma
            sp = st.sp_pos
            if st.done:
                done = 1.0
                break
        out.append(
            Transition(
                s_idx=steps[p].s_pos,
                sp_idx=sp,
                delta=steps[p].delta,
                reward_nstep=R,
                gamma_bootstrap=G,
                done=done,
                wave=0,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Embedding encode (the single torch step)
# ---------------------------------------------------------------------------
def encode_states_to_embeddings(
    states: list[StateRef],
    runs_root: str | Path,
    trunk: Any,
    *,
    schema: dict[str, Any],
    kept_indices: Any,
    mean: Any,
    std: Any,
    group_names: tuple[str, ...],
    batch_size: int = 4096,
    device: str = "cpu",
):
    """Encode every referenced state's observation and trunk-embed it -> ``[N, 256]``.

    Reproduces the SAME state<->observation pairing as :func:`build_run_telemetry`:
    each ``student_tick`` acts on the most-recent ``combat_capture`` (the payload
    it was served), joined by the student-tick seq (the continuous sidecar seq,
    which is NOT the per-run ``capture_seq``). A single extra streaming pass per
    run encodes only the referenced states (memory stays bounded to the embedding
    matrix). Reuses the sidecar's ``_encode_inputs`` and the frozen trunk exactly.
    """
    import numpy as np
    import torch

    from trainer.bridge.sidecar import _encode_inputs
    from trainer.rl.residual_actor import trunk_embedding

    # Group states by run and required seq for a targeted re-stream.
    by_run: dict[str, dict[int, int]] = {}
    for idx, s in enumerate(states):
        by_run.setdefault(s.run_id, {})[s.seq] = idx

    n = len(states)
    trunk_dim = trunk.config.trunk_hidden[-1]
    embeddings = np.zeros((n, trunk_dim), dtype=np.float32)

    trunk = trunk.to(device).eval()

    # Buffers of encoded inputs pending a trunk batch.
    pend_idx: list[int] = []
    pend_g: list[Any] = []
    pend_ent: dict[str, list[Any]] = {g: [] for g in group_names}
    pend_mask: dict[str, list[Any]] = {g: [] for g in group_names}

    def _flush() -> None:
        if not pend_idx:
            return
        g = torch.from_numpy(np.stack(pend_g)).to(device)
        ent = {name: torch.from_numpy(np.stack(pend_ent[name])).to(device) for name in group_names}
        msk = {name: torch.from_numpy(np.stack(pend_mask[name])).to(device) for name in group_names}
        with torch.no_grad():
            emb = trunk_embedding(trunk, g, ent, msk).detach().cpu().numpy()
        for j, target in enumerate(pend_idx):
            embeddings[target] = emb[j]
        pend_idx.clear()
        pend_g.clear()
        for name in group_names:
            pend_ent[name].clear()
            pend_mask[name].clear()

    for run_id, seq_to_idx in by_run.items():
        events_path = Path(runs_root) / run_id / "events.jsonl"
        last_cap: dict[str, Any] | None = None
        with events_path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                e = json.loads(line)
                et = e.get("event")
                if et == "combat_capture":
                    last_cap = e.get("payload", {}) or {}
                elif et == "student_tick":
                    seq = (e.get("payload", {}) or {}).get("seq")
                    if not isinstance(seq, int) or seq not in seq_to_idx or last_cap is None:
                        continue
                    standardized, ent_arrays, mask_arrays = _encode_inputs(
                        last_cap, schema, kept_indices, mean, std, group_names
                    )
                    pend_idx.append(seq_to_idx[seq])
                    pend_g.append(standardized)
                    for name in group_names:
                        pend_ent[name].append(ent_arrays[name])
                        pend_mask[name].append(mask_arrays[name])
                    if len(pend_idx) >= batch_size:
                        _flush()
    _flush()
    return embeddings


# ---------------------------------------------------------------------------
# Replay pool + teacher-mixing sampler
# ---------------------------------------------------------------------------
@dataclass
class ReplayPool:
    """Embeddings + n-step transitions, batchable for the critic/actor."""

    embeddings: Any               # np.ndarray [N, D] float32
    transitions: list[Transition]
    states: list[StateRef] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.transitions)

    def as_tensors(self, device: str = "cpu"):
        """Materialize transition columns as tensors (s_emb, delta, R, gamma, sp_emb, done, wave)."""
        import numpy as np
        import torch

        emb = torch.from_numpy(np.asarray(self.embeddings, dtype=np.float32)).to(device)
        s_idx = torch.tensor([t.s_idx for t in self.transitions], dtype=torch.long, device=device)
        sp_idx = torch.tensor([t.sp_idx for t in self.transitions], dtype=torch.long, device=device)
        delta = torch.tensor([t.delta for t in self.transitions], dtype=torch.float32, device=device)
        R = torch.tensor([t.reward_nstep for t in self.transitions], dtype=torch.float32, device=device)
        gamma = torch.tensor([t.gamma_bootstrap for t in self.transitions], dtype=torch.float32, device=device)
        done = torch.tensor([t.done for t in self.transitions], dtype=torch.float32, device=device)
        wave = torch.tensor([s.wave for s in self.states], dtype=torch.long, device=device) if self.states else None
        return {
            "emb": emb,
            "s_idx": s_idx,
            "sp_idx": sp_idx,
            "delta": delta,
            "reward_nstep": R,
            "gamma_bootstrap": gamma,
            "done": done,
            "state_wave": wave,
        }


class TeacherMixSampler:
    """Delta=0 teacher-mixing states from the frozen ``combat_obs_v1`` shards.

    Precomputes trunk embeddings for a (subsampled) set of teacher observations
    and yields ``(embedding, delta=0)`` batches. These feed the ACTOR update's
    zero-residual manifold coverage (design §3; see the module deviation note).
    """

    def __init__(self, embeddings: Any) -> None:
        import numpy as np

        self._emb = np.asarray(embeddings, dtype=np.float32)

    def __len__(self) -> int:
        return int(self._emb.shape[0])

    def sample(self, batch_size: int, rng: Any, device: str = "cpu"):
        import numpy as np
        import torch

        idx = rng.integers(0, self._emb.shape[0], size=batch_size)
        emb = torch.from_numpy(np.ascontiguousarray(self._emb[idx])).to(device)
        return emb


def build_teacher_mix_embeddings(
    dataset_dir: str | Path,
    trunk: Any,
    *,
    schema_path: str | Path,
    input_config: str | Path,
    split_config: str | Path,
    max_states: int = 50000,
    batch_size: int = 4096,
    device: str = "cpu",
    seed: int = 0,
):
    """Precompute trunk embeddings for a random subset of combat_obs_v1 train obs.

    Standardizes with the dataset's own train normalization (matches BC training)
    and runs the frozen trunk over a seeded random subset of the train split.
    """
    import numpy as np
    import torch

    from trainer.data.bc_dataset import load_bc_dataset
    from trainer.imitation.bc_training import _build_device_split
    from trainer.rl.residual_actor import trunk_embedding

    dataset = load_bc_dataset(str(dataset_dir), str(split_config), str(input_config), str(schema_path))
    group_names = tuple(spec.name for spec in trunk.config.group_specs)
    prev_idx = trunk.config.prev_action_indices

    torch_device = torch.device(device)
    split = _build_device_split(
        dataset.train, dataset.normalization, group_names, prev_idx, torch_device, pin=False
    )

    n = split.size
    rng = np.random.default_rng(seed)
    take = min(max_states, n)
    sel = np.sort(rng.choice(n, size=take, replace=False))
    trunk = trunk.to(torch_device).eval()
    out = np.zeros((take, trunk.config.trunk_hidden[-1]), dtype=np.float32)
    for start in range(0, take, batch_size):
        chunk = sel[start:start + batch_size]
        idx = torch.from_numpy(chunk).to(torch_device)
        g = split.globals.index_select(0, idx)
        ent = {grp: split.entities[grp].index_select(0, idx) for grp in group_names}
        msk = {grp: split.masks[grp].index_select(0, idx) for grp in group_names}
        with torch.no_grad():
            emb = trunk_embedding(trunk, g, ent, msk).detach().cpu().numpy()
        out[start:start + len(chunk)] = emb
    return out
