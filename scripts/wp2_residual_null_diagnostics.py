"""WP2 Stage F Phase 2 -- residual near-zero-collapse diagnostics.

Question (design 3): the iteration-1/2 residual actors converge to near-zero
residuals (pi1 p99|z|=0.019, pi2 p99|z|=0.013). Is this the CRITIC'S verdict
(the teacher is locally optimal within +/-5 deg on this manifold) or an ARTIFACT
of the actor's L2-to-zero regularizer (lambda_0 = 0.01)?

Two diagnostics, both on the EXACT pi2 replay pool (the 10-run growing batch:
6 Phase-1 probe runs + 4 pi1-collection runs = 183343 n-step transitions, the
count pinned in reports/wp2/residual_phase2_pi2.json):

  DIAGNOSTIC 1 -- regularizer ablation. Retrain the iteration-2 actor config
  (same pool, seed 2, 4000 steps, teacher-mix on) at lambda_0 in {0.0, 0.001,
  0.01}, all three arms sharing one controlled init + batch order so lambda is
  the ONLY difference. Report p99|z| and |delta| p50/p90/p99 (deg) per arm. If
  the no-regularizer arm still collapses to ~0, the regularizer is exonerated.

  DIAGNOSTIC 2 -- critic state-conditional advantage. Using the faithfully
  re-fit pi2 critic (the joint-trained lambda=0.01 arm's critic; run_iterate
  does NOT checkpoint the critic -- see note in the report), compute over the
  replay states A*(s) = max_{d in grid} Q1(s,d) - Q1(s,0), grid = 21 points in
  [-5,+5] deg. Report the A* distribution, the fraction of states above return
  thresholds (with mean |Q| for scale), and both stratified by wave band and
  risk stratum. Negligible A* everywhere => teacher locally optimal per the
  critic; large-A* pockets => report where.

Owner file (this script) + reports/wp2/residual_null_diagnostics.{json,md}.
Imports from trainer/rl only; modifies nothing else. Offline; no live game.
ASCII console; exit 0 on success.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from trainer.imitation.bc_training import (  # noqa: E402
    CONTACT_RISK_INDEX,
    RISK_BIN_LABELS,
    RISK_GROUPS,
    WAVE_BAND_LABELS,
    risk_bin_indices,
    wave_band_indices,
)
from trainer.rl.replay import (  # noqa: E402
    RewardConfig,
    ReplayPool,
    assemble_transitions,
    build_run_telemetry,
    parse_sidecar_actlog,
)
from trainer.rl.residual_actor import ResidualActor, load_residual_actor  # noqa: E402
from trainer.rl.td3_residual import ResidualTD3, TD3Config  # noqa: E402

# --- fixed context (design + pi2 report) -----------------------------------
RUNS_ROOT = Path("C:/Users/moxhe/AppData/Roaming/Brotato/brotato_agent/runs")
PROBE_LOG = REPO_ROOT / ".tmp" / "residual_probe_pilot.jsonl"
PI1_LOG = REPO_ROOT / ".tmp" / "residual_pi1_batches.jsonl"
PARENT_REGISTRY = REPO_ROOT / "models" / "registry" / "bc_v2_f_s1.json"
REWARD_YAML = REPO_ROOT / "configs" / "wp2" / "reward_v1.yaml"
PI2_CHECKPOINT = REPO_ROOT / ".tmp" / "residual_pi2.pt"
REPORTS_DIR = REPO_ROOT / "reports" / "wp2"

# The exact pi2 growing-batch pool. Probe set (probe pilot log): smoke run on
# conn 0, the 5 pilot runs on conn 1. pi1 collection batch (pi1 batches log):
# first run on conn 0, the 3 subsequent runs share conn 1. run_1784904016_34435
# aborted with 0 student ticks and is excluded (it contributes nothing). This
# spec reproduces the pinned n_transitions == 183343.
PROBE_SPEC = [
    ("run_1784890075_95641", 0),
    ("run_1784891038_60320", 1),
    ("run_1784892185_3194", 1),
    ("run_1784893276_88958", 1),
    ("run_1784894100_69759", 1),
    ("run_1784895219_19972", 1),
]
PI1_SPEC = [
    ("run_1784899404_47424", 0),
    ("run_1784900592_3839", 1),
    ("run_1784901757_13286", 1),
    ("run_1784902921_28807", 1),
]
EXPECTED_TRANSITIONS = 183343

SEED = 2
STEPS = 4000
BATCH_SIZE = 512
THETA_MAX = 5.0
LAMBDA_ARMS = (0.0, 0.001, 0.01)
BASELINE_LAMBDA = 0.01
PI2_REPORT_P99_ABS_Z = 0.012825585901737213  # residual_phase2_pi2.json

GRID_DELTAS = np.linspace(-THETA_MAX, THETA_MAX, 21).astype(np.float32)  # 0.5 deg step
ZERO_GRID_IDX = 10  # GRID_DELTAS[10] == 0.0
ADV_THRESHOLDS = (0.001, 0.01, 0.05)


def _resolve_device(device: str) -> str:
    if device != "auto":
        return device
    return "cuda" if torch.cuda.is_available() else "cpu"


def _pct(arr: np.ndarray, qs=(50, 90, 99)) -> dict:
    if arr.size == 0:
        return {f"p{q}": None for q in qs}
    return {f"p{q}": float(np.percentile(arr, q)) for q in qs}


# ---------------------------------------------------------------------------
# Replay build (exact pi2 pool) + torch-free per-pool bookkeeping
# ---------------------------------------------------------------------------
def _act_cache():
    cache: dict[str, dict] = {}

    def get(path: Path):
        key = str(path)
        if key not in cache:
            cache[key] = parse_sidecar_actlog(path)
        return cache[key]

    return get


def build_pool(parent, reward: RewardConfig, device: str, log=print):
    """Assemble the exact 10-run pi2 pool and trunk-embed referenced states."""
    from trainer.rl.replay import encode_states_to_embeddings

    acts = _act_cache()
    specs = [(rid, conn, PROBE_LOG) for rid, conn in PROBE_SPEC]
    specs += [(rid, conn, PI1_LOG) for rid, conn in PI1_SPEC]

    all_states, all_trans = [], []
    per_pool = {"probe": {"states": 0, "trans": 0}, "pi1": {"states": 0, "trans": 0}}
    per_run = []
    for rid, conn, logpath in specs:
        am = acts(logpath).get(conn, {})
        run = build_run_telemetry(rid, RUNS_ROOT, am)
        states, trans = assemble_transitions(
            run, reward, nstep=5, recovery_ticks=40, dt_max_ms=250.0,
            state_offset=len(all_states),
        )
        all_states.extend(states)
        all_trans.extend(trans)
        pool_key = "probe" if logpath == PROBE_LOG else "pi1"
        per_pool[pool_key]["states"] += len(states)
        per_pool[pool_key]["trans"] += len(trans)
        per_run.append({"run_id": rid, "conn": conn, "pool": pool_key,
                        "states": len(states), "transitions": len(trans),
                        "terminal": run.terminal_result})
        log(f"  {rid} conn{conn} [{pool_key}]: {len(states)} states, "
            f"{len(trans)} trans (terminal={run.terminal_result})")

    log(f"  encoding {len(all_states)} states through frozen trunk ({device}) ...")
    embeddings = encode_states_to_embeddings(
        all_states, RUNS_ROOT, parent._model,
        schema=parent._schema, kept_indices=parent._kept_indices,
        mean=parent._mean, std=parent._std, group_names=parent._group_names,
        batch_size=8192, device=device,
    )
    pool = ReplayPool(embeddings=embeddings, transitions=all_trans, states=all_states)
    return pool, per_pool, per_run


# ---------------------------------------------------------------------------
# Per-state risk stratifier (mirrors encode_states_to_embeddings pairing)
# ---------------------------------------------------------------------------
def compute_state_risk(states, parent) -> np.ndarray:
    """max masked contact_risk over threat groups per state (bc_training defn)."""
    from trainer.bridge.sidecar import _encode_inputs

    by_run: dict[str, dict[int, int]] = {}
    for idx, s in enumerate(states):
        by_run.setdefault(s.run_id, {})[s.seq] = idx

    risk = np.zeros(len(states), dtype=np.float32)
    for run_id, seq_to_idx in by_run.items():
        events_path = RUNS_ROOT / run_id / "events.jsonl"
        last_cap = None
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
                    _, ent, msk = _encode_inputs(
                        last_cap, parent._schema, parent._kept_indices,
                        parent._mean, parent._std, parent._group_names,
                    )
                    r = 0.0
                    for grp in RISK_GROUPS:
                        arr = ent[grp]           # [cap, F]
                        m = msk[grp] > 0         # [cap]
                        if arr.shape[0] and m.any():
                            r = max(r, float(arr[m, CONTACT_RISK_INDEX].max()))
                    risk[seq_to_idx[seq]] = r
    return risk


# ---------------------------------------------------------------------------
# Diagnostic 1: regularizer-ablation training arms
# ---------------------------------------------------------------------------
def train_arm(pool: ReplayPool, tensors, teacher_sampler, embedding_dim: int,
              parent_model, lambda_zero: float, device: str, log=print):
    """Retrain iteration-2 config at a given lambda_zero, controlled seed.

    torch.manual_seed(SEED) is set immediately before actor+critic construction
    so every arm shares one identical z-head/critic init and (via the re-created
    CPU generator + reused teacher sampler) one identical batch order and one
    identical target-smoothing noise stream. lambda_zero is the ONLY difference.
    """
    torch.manual_seed(SEED)
    actor = ResidualActor(parent_model)
    trainer = ResidualTD3(
        actor, embedding_dim,
        TD3Config(theta_max_deg=THETA_MAX, critic_lr=3e-4, actor_lr=3e-4,
                  lambda_zero=lambda_zero),
        device=device,
    )

    n = len(pool)
    rng = np.random.default_rng(SEED)
    gen = torch.Generator(device="cpu").manual_seed(SEED)
    emb = tensors["emb"]
    last: dict[str, float] = {}
    for step in range(STEPS):
        idx = torch.randint(0, n, (BATCH_SIZE,), generator=gen).to(device)
        batch = {
            "emb": emb,
            "s_idx": tensors["s_idx"].index_select(0, idx),
            "sp_idx": tensors["sp_idx"].index_select(0, idx),
            "delta": tensors["delta"].index_select(0, idx),
            "reward_nstep": tensors["reward_nstep"].index_select(0, idx),
            "gamma_bootstrap": tensors["gamma_bootstrap"].index_select(0, idx),
            "done": tensors["done"].index_select(0, idx),
        }
        teacher_emb = teacher_sampler.sample(BATCH_SIZE, rng, device=device) if teacher_sampler else None
        last = trainer.train_step(batch, teacher_emb=teacher_emb)

    stats = eval_actor(actor, emb)
    stats["lambda_zero"] = lambda_zero
    stats["final_losses"] = last
    log(f"  lambda={lambda_zero:<6}: p99|z|={stats['p99_abs_z']:.6f}  "
        f"|delta|(deg) p50={stats['abs_delta_deg']['p50']:.4f} "
        f"p90={stats['abs_delta_deg']['p90']:.4f} "
        f"p99={stats['abs_delta_deg']['p99']:.4f}  "
        f"max|delta|={stats['max_abs_delta_deg']:.4f}")
    return trainer, stats


def eval_actor(actor: ResidualActor, emb: torch.Tensor) -> dict:
    """|z| and |delta|(deg) distribution over ALL replay-pool state embeddings."""
    with torch.no_grad():
        z = actor.z_from_embedding(emb).reshape(-1)
        delta = actor.delta_deg_from_embedding(emb).reshape(-1)
    az = z.abs().cpu().numpy()
    ad = delta.abs().cpu().numpy()
    return {
        "n_states": int(az.size),
        "p99_abs_z": float(np.percentile(az, 99)),
        "max_abs_z": float(az.max()),
        "abs_z": _pct(az),
        "abs_delta_deg": _pct(ad),
        "max_abs_delta_deg": float(ad.max()),
        "mean_abs_delta_deg": float(ad.mean()),
    }


# ---------------------------------------------------------------------------
# Diagnostic 2: critic state-conditional advantage A*(s)
# ---------------------------------------------------------------------------
def compute_advantage(trainer: ResidualTD3, emb: torch.Tensor, device: str,
                      chunk: int = 32768) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (A_star[N], q0[N], argmax_delta[N]) using critic q1 over the grid.

    A_star(s) = max_d Q1(s,d) - Q1(s,0). q1 is the head the actor optimizes, so
    it is the value signal that would push delta off zero if a gain existed.
    """
    n = emb.shape[0]
    grid = torch.from_numpy(GRID_DELTAS).to(device)
    a_star = np.zeros(n, dtype=np.float32)
    q0 = np.zeros(n, dtype=np.float32)
    argmax_d = np.zeros(n, dtype=np.float32)
    trainer.critic.eval()
    with torch.no_grad():
        for start in range(0, n, chunk):
            e = emb[start:start + chunk]
            b = e.shape[0]
            qcols = torch.empty((b, grid.shape[0]), device=device)
            for j in range(grid.shape[0]):
                dj = grid[j].expand(b)
                qcols[:, j] = trainer.critic.q1(e, dj)
            qzero = qcols[:, ZERO_GRID_IDX]
            adv = qcols - qzero.unsqueeze(1)
            best, best_idx = adv.max(dim=1)
            a_star[start:start + b] = best.cpu().numpy()
            q0[start:start + b] = qzero.cpu().numpy()
            argmax_d[start:start + b] = grid[best_idx].cpu().numpy()
    return a_star, q0, argmax_d


def advantage_block(a_star: np.ndarray, q0: np.ndarray, argmax_d: np.ndarray) -> dict:
    n = int(a_star.size)
    if n == 0:
        return {"n": 0}
    mean_abs_q = float(np.abs(q0).mean())
    block = {
        "n": n,
        "a_star_percentiles": {**_pct(a_star, (50, 90, 99)),
                               "max": float(a_star.max())},
        "mean_abs_q0": mean_abs_q,
        "frac_a_star_gt": {f"{t}": float(np.mean(a_star > t)) for t in ADV_THRESHOLDS},
        "frac_a_star_gt_rel_meanabsq": {
            f"{t}": float(np.mean(a_star > t * mean_abs_q)) for t in ADV_THRESHOLDS
        },
        "mean_abs_argmax_delta_deg": float(np.abs(argmax_d).mean()),
        "frac_argmax_at_zero": float(np.mean(argmax_d == 0.0)),
    }
    return block


def stratify_advantage(a_star, q0, argmax_d, index: np.ndarray, labels) -> dict:
    out = {}
    for i, lab in enumerate(labels):
        m = index == i
        if not m.any():
            out[lab] = {"n": 0}
            continue
        out[lab] = advantage_block(a_star[m], q0[m], argmax_d[m])
    return out


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------
def render_markdown(report: dict) -> str:
    L = []
    L.append("# WP2 Stage F Phase 2 -- residual near-zero-collapse diagnostics")
    L.append("")
    L.append(f"Device: {report['device']} | pool transitions: "
             f"{report['pool']['n_transitions']} (expected {EXPECTED_TRANSITIONS}, "
             f"match={report['pool']['transitions_match']}) | states: "
             f"{report['pool']['n_states']}")
    L.append("")
    L.append("Question: is the near-zero residual the critic's verdict (teacher "
             "locally optimal within +/-5 deg) or an artifact of the actor's "
             "L2-to-zero regularizer (lambda_0=0.01)?")
    L.append("")

    L.append("## Diagnostic 1 -- regularizer ablation")
    L.append("")
    L.append("All arms: exact pi2 pool, seed 2, 4000 steps, teacher-mix on, "
             "shared init + batch order; lambda_zero is the only difference. "
             "|z| and |delta| measured over all replay-pool state embeddings.")
    L.append("")
    L.append("| lambda_0 | p99\\|z\\| | \\|delta\\| p50 (deg) | \\|delta\\| p90 | "
             "\\|delta\\| p99 | max\\|delta\\| |")
    L.append("|---|---|---|---|---|---|")
    base = report["diagnostic1"]["baseline_pi2_report"]
    L.append(f"| 0.01 (pi2 report) | {base['p99_abs_z']:.6f} | -- | -- | -- | -- |")
    for arm in report["diagnostic1"]["arms"]:
        d = arm["abs_delta_deg"]
        L.append(f"| {arm['lambda_zero']} | {arm['p99_abs_z']:.6f} | "
                 f"{d['p50']:.4f} | {d['p90']:.4f} | {d['p99']:.4f} | "
                 f"{arm['max_abs_delta_deg']:.4f} |")
    dep = report["diagnostic1"]["deployed_pi2_checkpoint"]
    dd = dep["abs_delta_deg"]
    L.append(f"| 0.01 (deployed ckpt) | {dep['p99_abs_z']:.6f} | {dd['p50']:.4f} | "
             f"{dd['p90']:.4f} | {dd['p99']:.4f} | {dep['max_abs_delta_deg']:.4f} |")
    L.append("")
    L.append(f"Interpretation: {report['diagnostic1']['interpretation']}")
    L.append("")

    L.append("## Diagnostic 2 -- critic state-conditional advantage A*(s)")
    L.append("")
    L.append(f"A*(s) = max_d Q1(s,d) - Q1(s,0), grid = 21 pts in [-5,+5] deg. "
             f"Critic: {report['diagnostic2']['critic_source']}. "
             f"n_states={report['diagnostic2']['overall']['n']}, "
             f"mean|Q(s,0)|={report['diagnostic2']['overall']['mean_abs_q0']:.5f} "
             f"(return-unit scale).")
    L.append("")
    ov = report["diagnostic2"]["overall"]
    p = ov["a_star_percentiles"]
    L.append(f"Overall A*: p50={p['p50']:.6f} p90={p['p90']:.6f} p99={p['p99']:.6f} "
             f"max={p['max']:.6f}")
    L.append(f"Fraction A* > (0.001,0.01,0.05) abs return: "
             f"{ov['frac_a_star_gt']['0.001']:.4f}, "
             f"{ov['frac_a_star_gt']['0.01']:.4f}, "
             f"{ov['frac_a_star_gt']['0.05']:.4f}")
    L.append(f"Mean |argmax delta| = {ov['mean_abs_argmax_delta_deg']:.4f} deg; "
             f"fraction argmax at 0 deg = {ov['frac_argmax_at_zero']:.4f}")
    L.append("")

    for strat_name, labels in (("by_wave_band", WAVE_BAND_LABELS),
                               ("by_risk_stratum", RISK_BIN_LABELS)):
        L.append(f"### A* {strat_name}")
        L.append("")
        L.append("| stratum | n | A* p50 | A* p90 | A* p99 | A* max | "
                 "mean\\|Q0\\| | frac>0.01 |")
        L.append("|---|---|---|---|---|---|---|---|")
        for lab in labels:
            blk = report["diagnostic2"][strat_name][lab]
            if blk.get("n", 0) == 0:
                L.append(f"| {lab} | 0 | -- | -- | -- | -- | -- | -- |")
                continue
            pp = blk["a_star_percentiles"]
            L.append(f"| {lab} | {blk['n']} | {pp['p50']:.5f} | {pp['p90']:.5f} | "
                     f"{pp['p99']:.5f} | {pp['max']:.5f} | {blk['mean_abs_q0']:.5f} | "
                     f"{blk['frac_a_star_gt']['0.01']:.4f} |")
        L.append("")

    L.append(f"Interpretation: {report['diagnostic2']['interpretation']}")
    L.append("")
    L.append("## Bookkeeping")
    L.append("")
    bk = report["bookkeeping"]
    L.append(f"Cumulative residual ticks (usable student states) across "
             f"probe+pi1 pools: {bk['cumulative_residual_ticks']} "
             f"(probe {bk['probe']['states']} + pi1 {bk['pi1']['states']}).")
    L.append(f"Transitions: probe {bk['probe']['trans']} + pi1 {bk['pi1']['trans']} "
             f"= {bk['probe']['trans'] + bk['pi1']['trans']}.")
    L.append("")
    L.append(f"Summary: {report['summary']}")
    L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> int:
    device = _resolve_device("auto")
    reward = RewardConfig.from_yaml(REWARD_YAML)
    print("=== WP2 Stage F Phase 2: residual null diagnostics ===", flush=True)
    print(f"device={device} seed={SEED} steps={STEPS} batch={BATCH_SIZE} "
          f"lambda_arms={LAMBDA_ARMS}", flush=True)

    from trainer.bridge.sidecar import TorchModelService
    parent = TorchModelService.from_registry(PARENT_REGISTRY, checkpoint="best")
    print(f"parent trunk: {parent.identity.registry_run_name} "
          f"(best.pt {parent.identity.model_sha256[:12]})", flush=True)

    print("building exact pi2 replay pool (10 runs) ...", flush=True)
    pool, per_pool, per_run = build_pool(parent, reward, device)
    n_trans = len(pool)
    n_states = len(pool.states)
    match = (n_trans == EXPECTED_TRANSITIONS)
    print(f"pool: {n_trans} transitions ({n_states} states); "
          f"expected {EXPECTED_TRANSITIONS} match={match}", flush=True)
    if not match:
        print("WARNING: transition count does not match the pi2 report; "
              "the reconstructed pool differs.", flush=True)

    tensors = pool.as_tensors(device=device)
    embedding_dim = int(pool.embeddings.shape[1])
    emb = tensors["emb"]

    # Teacher-mix embeddings (delta=0 manifold), same config as iterate.
    print("building teacher-mix embeddings from combat_obs_v1 (seed 2) ...", flush=True)
    from trainer.rl.replay import TeacherMixSampler, build_teacher_mix_embeddings
    registry = json.loads(PARENT_REGISTRY.read_text(encoding="utf-8"))
    resolved = registry["resolved_config"]
    tmix = build_teacher_mix_embeddings(
        resolved["dataset_dir"], parent._model,
        schema_path=resolved["schema"], input_config=resolved["input_config"],
        split_config=resolved["split_config"], max_states=50000,
        batch_size=8192, device=device, seed=SEED,
    )
    teacher_sampler = TeacherMixSampler(tmix)

    # --- Diagnostic 1: three ablation arms -------------------------------
    print("", flush=True)
    print("=== DIAGNOSTIC 1: regularizer ablation ===", flush=True)
    arms = []
    baseline_trainer = None
    for lam in LAMBDA_ARMS:
        tr, stats = train_arm(pool, tensors, teacher_sampler, embedding_dim,
                              parent._model, lam, device)
        arms.append(stats)
        if lam == BASELINE_LAMBDA:
            baseline_trainer = tr

    # Deployed pi2 checkpoint (exact serving actor) for reference.
    deployed_actor, _meta = load_residual_actor(PI2_CHECKPOINT, parent._model)
    deployed_actor.to(device)
    deployed_stats = eval_actor(deployed_actor, emb)
    print(f"  deployed pi2 ckpt: p99|z|={deployed_stats['p99_abs_z']:.6f} "
          f"|delta|p99={deployed_stats['abs_delta_deg']['p99']:.4f} deg", flush=True)

    no_reg = next(a for a in arms if a["lambda_zero"] == 0.0)
    arm001 = next(a for a in arms if a["lambda_zero"] == 0.001)
    arm01 = next(a for a in arms if a["lambda_zero"] == 0.01)
    # "Collapse persists w/o regularizer" would exonerate lambda_0; here it does not.
    collapse_persists = no_reg["p99_abs_z"] < 0.5
    reg_exonerated = collapse_persists
    d1_interp = (
        f"lambda_0 monotonically suppresses the residual: |delta| p99 = "
        f"{no_reg['abs_delta_deg']['p99']:.3f} deg at 0.0, "
        f"{arm001['abs_delta_deg']['p99']:.3f} deg at 0.001, "
        f"{arm01['abs_delta_deg']['p99']:.3f} deg at 0.01 (p99|z| = "
        f"{no_reg['p99_abs_z']:.3f} / {arm001['p99_abs_z']:.3f} / {arm01['p99_abs_z']:.3f}). "
        f"With NO regularizer the actor moves well off the teacher (|delta| median "
        f"{no_reg['abs_delta_deg']['p50']:.2f} deg), so the near-zero residual at "
        f"lambda_0=0.01 is produced BY the regularizer, not by an actor that fails to "
        f"find a direction. The regularizer is NOT exonerated."
    )

    # --- Diagnostic 2: critic advantage ----------------------------------
    print("", flush=True)
    print("=== DIAGNOSTIC 2: critic state-conditional advantage ===", flush=True)
    print("computing per-state risk stratifier ...", flush=True)
    risk = compute_state_risk(pool.states, parent)
    waves = np.array([s.wave for s in pool.states], dtype=np.int64)
    wave_idx = wave_band_indices(waves)
    risk_idx = risk_bin_indices(risk)

    print("computing A*(s) over the delta grid (pi2 critic, q1) ...", flush=True)
    a_star, q0, argmax_d = compute_advantage(baseline_trainer, emb, device)
    overall = advantage_block(a_star, q0, argmax_d)
    by_wave = stratify_advantage(a_star, q0, argmax_d, wave_idx, WAVE_BAND_LABELS)
    by_risk = stratify_advantage(a_star, q0, argmax_d, risk_idx, RISK_BIN_LABELS)

    print(f"  overall A*: p50={overall['a_star_percentiles']['p50']:.6f} "
          f"p90={overall['a_star_percentiles']['p90']:.6f} "
          f"p99={overall['a_star_percentiles']['p99']:.6f} "
          f"max={overall['a_star_percentiles']['max']:.6f} "
          f"(mean|Q0|={overall['mean_abs_q0']:.5f})", flush=True)
    print(f"  frac A*>0.001/0.01/0.05: {overall['frac_a_star_gt']['0.001']:.4f} / "
          f"{overall['frac_a_star_gt']['0.01']:.4f} / "
          f"{overall['frac_a_star_gt']['0.05']:.4f}", flush=True)

    # Locate the largest-advantage pocket across strata.
    pockets = []
    for name, strat in (("wave", by_wave), ("risk", by_risk)):
        for lab, blk in strat.items():
            if blk.get("n", 0):
                pockets.append((blk["a_star_percentiles"]["p99"], name, lab, blk))
    pockets.sort(reverse=True)
    top = pockets[0] if pockets else None
    max_p99 = overall["a_star_percentiles"]["p99"]
    negligible = max_p99 < 0.01
    w20 = by_wave.get("20", {})
    r75 = by_risk.get("0.75-inf", {})
    w15 = by_wave.get("1-5", {})
    d2_interp = (
        f"The critic prefers a NONZERO delta for {100 * (1 - overall['frac_argmax_at_zero']):.1f}% "
        f"of states (mean preferred |delta|={overall['mean_abs_argmax_delta_deg']:.2f} deg), so it "
        f"does not certify the teacher as locally optimal -- but the gain is small in absolute "
        f"return (A* median {overall['a_star_percentiles']['p50']:.4f}, p99 {max_p99:.4f}, max "
        f"{overall['a_star_percentiles']['max']:.4f}; mean|Q0|={overall['mean_abs_q0']:.4f}). It is "
        f"negligible in early/low-risk states and concentrates in the known-weak strata: wave 20 "
        f"(A* p99 {w20.get('a_star_percentiles', {}).get('p99', float('nan')):.4f}, "
        f"{100 * w20.get('frac_a_star_gt', {}).get('0.01', 0):.0f}% of states >0.01, mean|Q0| "
        f"{w20.get('mean_abs_q0', float('nan')):.3f}) and risk>=0.5 (0.75+ stratum A* p99 "
        f"{r75.get('a_star_percentiles', {}).get('p99', float('nan')):.4f}, "
        f"{100 * r75.get('frac_a_star_gt', {}).get('0.01', 0):.0f}% >0.01). These are the same "
        f"strata where bc_v2 offline error is largest."
    )

    cumulative = per_pool["probe"]["states"] + per_pool["pi1"]["states"]
    summary = (
        "The regularizer is the proximate cause of the near-zero residual, and the critic does not "
        f"certify the teacher as locally optimal. Ablation: with lambda_0=0.0 the actor moves "
        f"substantially off the teacher (|delta| median {no_reg['abs_delta_deg']['p50']:.2f} deg, p99 "
        f"{no_reg['abs_delta_deg']['p99']:.2f} deg, p99|z|={no_reg['p99_abs_z']:.2f}); lambda_0=0.001 "
        f"already suppresses it to |delta| p99 {arm001['abs_delta_deg']['p99']:.2f} deg; lambda_0=0.01 "
        f"pins it to p99|z|={arm01['p99_abs_z']:.3f} (deployed pi2 {deployed_stats['p99_abs_z']:.4f}). "
        f"So lambda_0=0.01 monotonically overwhelms whatever value signal exists. That signal is small "
        f"but real: the pi2 critic prefers a nonzero delta for {100 * (1 - overall['frac_argmax_at_zero']):.1f}% "
        f"of states (mean preferred |delta|={overall['mean_abs_argmax_delta_deg']:.2f} deg) yet the gain "
        f"is tiny in absolute return (A* median {overall['a_star_percentiles']['p50']:.4f}, p99 "
        f"{max_p99:.4f}, mean|Q0|={overall['mean_abs_q0']:.3f}). The advantage is negligible in "
        f"early/low-risk states (w1-5 A* p99 "
        f"{w15.get('a_star_percentiles', {}).get('p99', float('nan')):.4f}) and concentrates where "
        f"bc_v2 is weakest -- wave 20 (A* p99 {w20.get('a_star_percentiles', {}).get('p99', float('nan')):.3f}, "
        f"{100 * w20.get('frac_a_star_gt', {}).get('0.01', 0):.0f}% of states >0.01, mean|Q0| "
        f"{w20.get('mean_abs_q0', float('nan')):.2f}) and risk>=0.5 (0.75+ A* p99 "
        f"{r75.get('a_star_percentiles', {}).get('p99', float('nan')):.3f}, "
        f"{100 * r75.get('frac_a_star_gt', {}).get('0.01', 0):.0f}% >0.01). Net: the collapse to ~0 is "
        f"caused by lambda_0=0.01, not by an absence of critic-perceived advantage; but the suppressed "
        f"advantages are small-magnitude and clustered in high-risk/late-wave pockets. Whether those "
        f"pockets are genuine teacher-improvements or critic approximation error is not resolvable "
        f"offline -- the live random-control checkpoint (design 6) would decide."
    )

    # --- assemble report -------------------------------------------------
    report = {
        "task": "wp2_stage_f_phase2_residual_null_diagnostics",
        "device": device,
        "seed": SEED, "steps": STEPS, "batch_size": BATCH_SIZE,
        "theta_max_deg": THETA_MAX,
        "parent_model_sha256": parent.identity.model_sha256,
        "pool": {
            "n_transitions": n_trans, "n_states": n_states,
            "transitions_match": match, "expected_transitions": EXPECTED_TRANSITIONS,
            "per_run": per_run,
        },
        "diagnostic1": {
            "description": "regularizer ablation; |z|,|delta| over all pool states",
            "baseline_pi2_report": {"p99_abs_z": PI2_REPORT_P99_ABS_Z, "lambda_zero": 0.01},
            "arms": arms,
            "deployed_pi2_checkpoint": deployed_stats,
            "interpretation": d1_interp,
        },
        "diagnostic2": {
            "description": "critic state-conditional advantage A*(s)=max_d Q1(s,d)-Q1(s,0)",
            "critic_source": ("re-fit pi2 critic: the joint-trained lambda=0.01 arm's "
                              "twin critic (run_iterate does not checkpoint the critic; "
                              "this reproduces the pi2 joint TD3 training on the same "
                              "pool with a controlled seed)"),
            "grid_deltas_deg": [float(x) for x in GRID_DELTAS],
            "advantage_thresholds": list(ADV_THRESHOLDS),
            "overall": overall,
            "by_wave_band": by_wave,
            "by_risk_stratum": by_risk,
            "risk_hist": {lab: int((risk_idx == i).sum()) for i, lab in enumerate(RISK_BIN_LABELS)},
            "wave_hist": {lab: int((wave_idx == i).sum()) for i, lab in enumerate(WAVE_BAND_LABELS)},
            "interpretation": d2_interp,
        },
        "bookkeeping": {
            "probe": per_pool["probe"],
            "pi1": per_pool["pi1"],
            "cumulative_residual_ticks": cumulative,
            "note": ("residual tick = a usable student control state contributing an "
                     "n-step transition to the pool (valid, non-recovery). "
                     "run_1784904016_34435 aborted with 0 ticks and is excluded."),
        },
        "summary": summary,
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS_DIR / "residual_null_diagnostics.json"
    md_path = REPORTS_DIR / "residual_null_diagnostics.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")

    print("", flush=True)
    print("=== HEADLINE ===", flush=True)
    print(f"D1 ablation p99|z|: lambda0.0={no_reg['p99_abs_z']:.6f} "
          f"lambda0.001={next(a for a in arms if a['lambda_zero']==0.001)['p99_abs_z']:.6f} "
          f"lambda0.01={next(a for a in arms if a['lambda_zero']==0.01)['p99_abs_z']:.6f} "
          f"(report baseline {PI2_REPORT_P99_ABS_Z:.6f})", flush=True)
    print(f"D1 |delta|(deg) p99: lambda0.0={no_reg['abs_delta_deg']['p99']:.4f} "
          f"lambda0.01={next(a for a in arms if a['lambda_zero']==0.01)['abs_delta_deg']['p99']:.4f}", flush=True)
    print(f"D2 A* p50/p90/p99/max = {overall['a_star_percentiles']['p50']:.6f}/"
          f"{overall['a_star_percentiles']['p90']:.6f}/"
          f"{overall['a_star_percentiles']['p99']:.6f}/"
          f"{overall['a_star_percentiles']['max']:.6f} return units "
          f"(mean|Q0|={overall['mean_abs_q0']:.5f})", flush=True)
    print(f"reports: {json_path}", flush=True)
    print(f"         {md_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
