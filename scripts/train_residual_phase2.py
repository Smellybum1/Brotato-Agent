"""WP2 Stage F Phase 2 residual training (design §1, §3, §5, §6.2).

Non-interactive. Two entry modes:

  --mode rung2    Ladder rung 2 (design §6.2): build the off-policy replay from
                  the 6 Phase-1 probe runs, fit the twin critics with the actor
                  held at its zero-init, and report TD-loss convergence plus the
                  early-wave ``Q(s,+delta) - Q(s,-delta)`` dose-response sign.

  --mode iterate  The growing-batch iteration (design §1): ingest a run batch's
                  sidecar log + runs, (re)build the replay pool, train N off-
                  policy steps with 50/50 teacher-mixing, run the §5 offline
                  promotion gates, and emit the actor checkpoint + registry
                  manifest ``models/registry/residual_pi<k>.json``.

Offline only: no live game interaction, no deploy, no commit. ASCII console.
Exit 0 on success, 1 on a failed gate / usage error, 2 on IO error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from trainer.rl.replay import (  # noqa: E402
    ActRecord,
    RewardConfig,
    ReplayPool,
    assemble_transitions,
    build_run_telemetry,
    encode_states_to_embeddings,
    parse_sidecar_actlog,
)

DEFAULT_PARENT_REGISTRY = REPO_ROOT / "models" / "registry" / "bc_v2_f_s1.json"
DEFAULT_REWARD = REPO_ROOT / "configs" / "wp2" / "reward_v1.yaml"
DEFAULT_RUNS_ROOT = Path("C:/Users/moxhe/AppData/Roaming/Brotato/brotato_agent/runs")
DEFAULT_PROBE_LOG = REPO_ROOT / ".tmp" / "residual_probe_pilot.jsonl"
REPORTS_DIR = REPO_ROOT / "reports" / "wp2"
REGISTRY_DIR = REPO_ROOT / "models" / "registry"

# Phase-1 probe runs -> sidecar connection (smoke = conn 0; 5 pilot = conn 1).
PROBE_RUN_CONN: dict[str, int] = {
    "run_1784890075_95641": 0,   # smoke defeat w15
    "run_1784891038_60320": 1,   # victory w20
    "run_1784892185_3194": 1,    # defeat w19
    "run_1784893276_88958": 1,   # defeat w15
    "run_1784894100_69759": 1,   # defeat w20
    "run_1784895219_19972": 1,   # victory w20
}
EARLY_WAVE_HI = 10  # early+mid bands (w1-10) where the pilot dose-response is +

# Default actor L2-to-zero regularizer; mirrors TD3Config.lambda_zero (kept as a
# literal so CLI parsing stays torch-free — trainer.rl.td3_residual imports torch).
DEFAULT_ACTOR_L2 = 0.01


# ---------------------------------------------------------------------------
# Shared replay build
# ---------------------------------------------------------------------------
def _load_parent(registry_path: str | Path):
    from trainer.bridge.sidecar import TorchModelService

    return TorchModelService.from_registry(registry_path, checkpoint="best")


def build_replay(
    run_conn: dict[str, int],
    sidecar_log: str | Path,
    runs_root: str | Path,
    parent,
    reward: RewardConfig,
    *,
    nstep: int,
    recovery_ticks: int,
    dt_max_ms: float,
    device: str,
    log=print,
) -> ReplayPool:
    """Assemble transitions from every run and trunk-embed the referenced states.

    ``run_conn`` values may be a bare connection index (act log = ``sidecar_log``)
    or a ``(conn, logpath)`` tuple for runs recorded in a different sidecar log —
    the growing replay pool spans multiple collection sessions (probe pilot +
    each pi_k batch), each with its own log file.
    """
    log_cache: dict[str, dict[int, dict[int, ActRecord]]] = {}

    def _acts_for(logpath: str | Path) -> dict[int, dict[int, ActRecord]]:
        key = str(logpath)
        if key not in log_cache:
            log_cache[key] = parse_sidecar_actlog(logpath)
        return log_cache[key]

    all_states = []
    all_trans = []
    for run_id, spec in run_conn.items():
        conn, logpath = spec if isinstance(spec, tuple) else (spec, None)
        act_map = _acts_for(logpath or sidecar_log).get(conn, {})
        run = build_run_telemetry(run_id, runs_root, act_map)
        states, trans = assemble_transitions(
            run, reward, nstep=nstep, recovery_ticks=recovery_ticks,
            dt_max_ms=dt_max_ms, state_offset=len(all_states),
        )
        all_states.extend(states)
        all_trans.extend(trans)
        log(f"  {run_id} conn{conn}: {len(run.ticks)} ticks -> {len(states)} states, "
            f"{len(trans)} transitions (terminal={run.terminal_result})")
    log(f"  encoding {len(all_states)} states through the frozen trunk ({device}) ...")
    embeddings = encode_states_to_embeddings(
        all_states, runs_root, parent._model,
        schema=parent._schema, kept_indices=parent._kept_indices,
        mean=parent._mean, std=parent._std, group_names=parent._group_names,
        batch_size=8192, device=device,
    )
    return ReplayPool(embeddings=embeddings, transitions=all_trans, states=all_states)


def _resolve_device(device: str) -> str:
    if device != "auto":
        return device
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


# ---------------------------------------------------------------------------
# Rung 2: critic-only fit + dose-response
# ---------------------------------------------------------------------------
def run_rung2(args) -> int:
    import numpy as np
    import torch

    from trainer.rl.residual_actor import ResidualActor
    from trainer.rl.td3_residual import ResidualTD3, TD3Config

    device = _resolve_device(args.device)
    reward = RewardConfig.from_yaml(args.reward)
    print("=== WP2 Stage F Phase 2: rung 2 critic-only fit (design 6.2) ===", flush=True)
    print(f"device={device} reward=(dmg {reward.w_damage}, wave {reward.w_wave}, "
          f"victory {reward.w_victory}, intervention {reward.w_intervention}, tau {reward.tau_sec})",
          flush=True)

    parent = _load_parent(args.parent_registry)
    print(f"parent trunk: {parent.identity.registry_run_name} "
          f"(best.pt {parent.identity.model_sha256[:12]})", flush=True)

    pool = build_replay(
        PROBE_RUN_CONN, args.sidecar_log, args.runs_root, parent, reward,
        nstep=args.nstep, recovery_ticks=args.recovery_ticks, dt_max_ms=args.dt_max_ms,
        device=device,
    )
    print(f"replay: {len(pool)} transitions over {len(pool.states)} states", flush=True)

    tensors = pool.as_tensors(device=device)
    embedding_dim = int(pool.embeddings.shape[1])

    actor = ResidualActor(parent._model)  # zero-init; frozen during critic fit
    trainer = ResidualTD3(
        actor, embedding_dim,
        TD3Config(theta_max_deg=args.theta_max_deg, critic_lr=args.critic_lr),
        device=device,
    )

    print(f"fitting twin critics: {args.steps} steps, batch {args.batch_size} ...", flush=True)
    history = trainer.fit_critics(
        tensors, steps=args.steps, batch_size=args.batch_size, seed=args.seed,
        log_every=max(1, args.steps // 10), log=print,
    )
    early = float(np.mean(history[:20]))
    late = float(np.mean(history[-20:]))
    converged = bool(late < early and all(np.isfinite(history)))

    # Dose-response over early+mid-wave states (w1-10), where the pilot measured a
    # positive displacement dose-response.
    waves = np.array([s.wave for s in pool.states], dtype=np.int64)
    early_mask = (waves >= 1) & (waves <= EARLY_WAVE_HI)
    emb_all = tensors["emb"]
    early_emb = emb_all[torch.from_numpy(np.where(early_mask)[0]).to(device)]
    dr_early = trainer.dose_response(early_emb, delta_mag_deg=args.theta_max_deg)
    dr_all = trainer.dose_response(emb_all, delta_mag_deg=args.theta_max_deg)

    report = {
        "rung": 2,
        "design_ref": "6.2",
        "device": device,
        "parent_model_sha256": parent.identity.model_sha256,
        "reward": {
            "w_damage": reward.w_damage, "w_wave": reward.w_wave,
            "w_victory": reward.w_victory, "w_intervention": reward.w_intervention,
            "tau_sec": reward.tau_sec,
        },
        "nstep": args.nstep,
        "n_transitions": len(pool),
        "n_states": len(pool.states),
        "critic_fit": {
            "steps": args.steps,
            "batch_size": args.batch_size,
            "td_loss_early_mean": early,
            "td_loss_late_mean": late,
            "td_loss_final": float(history[-1]),
            "converged": converged,
        },
        "dose_response_early_w1_10": dr_early,
        "dose_response_all_waves": dr_all,
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / "residual_phase2_rung2_critic_fit.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("", flush=True)
    print(f"TD loss: early(mean20)={early:.6f}  late(mean20)={late:.6f}  "
          f"final={history[-1]:.6f}  converged={converged}", flush=True)
    print(f"dose-response early w1-{EARLY_WAVE_HI} (delta +/-{args.theta_max_deg} deg): "
          f"mean[Q(s,+d)-Q(s,-d)] = {dr_early['mean_diff']:+.6f}  sign={dr_early['sign']:+d}  "
          f"(n={dr_early['n']})", flush=True)
    print(f"dose-response all waves: mean_diff = {dr_all['mean_diff']:+.6f}  "
          f"sign={dr_all['sign']:+d}  (n={dr_all['n']})", flush=True)
    print(f"report: {out}", flush=True)
    return 0


# ---------------------------------------------------------------------------
# Iterate: growing-batch training + offline gates + promotion (design §1, §5)
# ---------------------------------------------------------------------------
def _offline_gates(actor, pool, tensors, device: str) -> dict:
    """Design §5 promotion gates: finite losses (caller), |z| unsaturated,
    serving==training determinism at sigma 0."""
    import numpy as np
    import torch

    emb = tensors["emb"]
    with torch.no_grad():
        z = actor.z_from_embedding(emb).reshape(-1)
        delta_a = actor.delta_deg_from_embedding(emb)
        delta_b = actor.config.theta_max_deg * torch.tanh(z)
    p99_abs_z = float(torch.quantile(z.abs(), 0.99).cpu().item()) if z.numel() else 0.0
    determinism_max = float((delta_a - delta_b).abs().max().cpu().item()) if z.numel() else 0.0
    return {
        "p99_abs_z": p99_abs_z,
        "p99_abs_z_ok": bool(p99_abs_z < 2.5),
        "serving_determinism_max_delta_diff": determinism_max,
        "serving_determinism_ok": bool(determinism_max <= 1e-6),
    }


def run_iterate(args) -> int:
    import numpy as np
    import torch

    from trainer.rl.residual_actor import (
        ResidualActor,
        save_residual_actor,
        write_actor_registry_manifest,
    )
    from trainer.rl.replay import TeacherMixSampler, build_teacher_mix_embeddings
    from trainer.rl.td3_residual import ResidualTD3, TD3Config

    device = _resolve_device(args.device)
    reward = RewardConfig.from_yaml(args.reward)
    run_conn = _load_run_conn(args.run_conn)
    print("=== WP2 Stage F Phase 2: iterate (design 1/5) ===", flush=True)
    print(f"device={device} iteration k={args.iteration} runs={list(run_conn)}", flush=True)

    parent = _load_parent(args.parent_registry)
    registry = json.loads(Path(args.parent_registry).read_text(encoding="utf-8"))
    resolved = registry["resolved_config"]

    pool = build_replay(
        run_conn, args.sidecar_log, args.runs_root, parent, reward,
        nstep=args.nstep, recovery_ticks=args.recovery_ticks, dt_max_ms=args.dt_max_ms,
        device=device,
    )
    if len(pool) == 0:
        print("error: empty replay pool", file=sys.stderr)
        return 1
    tensors = pool.as_tensors(device=device)
    embedding_dim = int(pool.embeddings.shape[1])

    # Teacher-mixing embeddings (delta=0 zero-residual manifold, design §3).
    teacher_sampler = None
    if args.teacher_mix:
        print("  building teacher-mix embeddings from combat_obs_v1 ...", flush=True)
        tmix = build_teacher_mix_embeddings(
            resolved["dataset_dir"], parent._model,
            schema_path=resolved["schema"], input_config=resolved["input_config"],
            split_config=resolved["split_config"], max_states=args.teacher_mix_states,
            batch_size=8192, device=device, seed=args.seed,
        )
        teacher_sampler = TeacherMixSampler(tmix)

    actor = ResidualActor(parent._model, )
    trainer = ResidualTD3(
        actor, embedding_dim,
        TD3Config(theta_max_deg=args.theta_max_deg, critic_lr=args.critic_lr,
                  actor_lr=args.actor_lr, lambda_zero=args.actor_l2),
        device=device,
    )
    print(f"actor L2-to-zero lambda_0={args.actor_l2}", flush=True)

    n = len(pool)
    rng = np.random.default_rng(args.seed)
    gen = torch.Generator(device="cpu").manual_seed(args.seed)
    emb = tensors["emb"]
    print(f"training {args.steps} off-policy steps (batch {args.batch_size}, "
          f"teacher_mix={args.teacher_mix}) ...", flush=True)
    last: dict[str, float] = {}
    for step in range(args.steps):
        idx = torch.randint(0, n, (args.batch_size,), generator=gen).to(device)
        batch = {
            "emb": emb,
            "s_idx": tensors["s_idx"].index_select(0, idx),
            "sp_idx": tensors["sp_idx"].index_select(0, idx),
            "delta": tensors["delta"].index_select(0, idx),
            "reward_nstep": tensors["reward_nstep"].index_select(0, idx),
            "gamma_bootstrap": tensors["gamma_bootstrap"].index_select(0, idx),
            "done": tensors["done"].index_select(0, idx),
        }
        teacher_emb = None
        if teacher_sampler is not None:
            teacher_emb = teacher_sampler.sample(args.batch_size, rng, device=device)
        last = trainer.train_step(batch, teacher_emb=teacher_emb)
        if step % max(1, args.steps // 10) == 0 or step == args.steps - 1:
            print(f"  step {step:5d}/{args.steps} "
                  f"critic={last.get('critic_loss', float('nan')):.5f} "
                  f"actor={last.get('actor_loss', float('nan')):.5f}", flush=True)

    finite = all(np.isfinite(v) for v in last.values())
    gates = _offline_gates(actor, pool, tensors, device)
    gates["finite_losses"] = bool(finite)
    gates["overall_pass"] = bool(
        gates["finite_losses"] and gates["p99_abs_z_ok"] and gates["serving_determinism_ok"]
    )

    # Emit actor checkpoint + registry manifest (always write; gate result recorded).
    ckpt_path = Path(args.checkpoint_out or (REPO_ROOT / ".tmp" / f"residual_pi{args.iteration}.pt"))
    actor_sha = save_residual_actor(
        actor, ckpt_path, parent_model_sha256=parent.identity.model_sha256,
        parent_registry_run_name=parent.identity.registry_run_name, iteration=args.iteration,
        extra={"gates": gates, "steps": args.steps},
    )
    manifest_path = REGISTRY_DIR / f"residual_pi{args.iteration}.json"
    write_actor_registry_manifest(
        manifest_path, actor_checkpoint=str(ckpt_path), actor_sha256=actor_sha,
        parent_registry=str(args.parent_registry), parent_model_sha256=parent.identity.model_sha256,
        iteration=args.iteration, theta_max_deg=args.theta_max_deg,
        explore_sigma=args.explore_sigma, reward_id="reward_v2",
        schema_hash=parent.identity.observation_schema_hash,
        source_capture_schema_hash=parent.identity.source_capture_schema_hash,
        extra={"gates": gates},
    )
    report = {
        "iteration": args.iteration,
        "device": device,
        "n_transitions": len(pool),
        "teacher_mix": bool(args.teacher_mix),
        "final_losses": last,
        "gates": gates,
        "actor_checkpoint": str(ckpt_path),
        "actor_sha256": actor_sha,
        "registry_manifest": str(manifest_path),
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / f"residual_phase2_pi{args.iteration}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"gates: {gates}", flush=True)
    print(f"actor: {ckpt_path} (sha {actor_sha[:12]})  manifest: {manifest_path}", flush=True)
    print(f"report: {out}", flush=True)
    return 0 if gates["overall_pass"] else 1


def _load_run_conn(spec: str | None) -> dict[str, object]:
    """Parse a ``run_id:conn[:logpath]`` comma list, defaulting to the probe set.

    The optional third field routes that run's act-log join to a different
    sidecar log file than ``--sidecar-log`` (multi-session replay pools).
    """
    if not spec:
        return dict(PROBE_RUN_CONN)
    out: dict[str, object] = {}
    for item in spec.split(","):
        item = item.strip()
        if not item:
            continue
        # split at most twice: the third field is a path and may itself
        # contain a drive colon (C:/...).
        parts = item.split(":", 2)
        run_id = parts[0].strip()
        conn = int(parts[1]) if len(parts) > 1 and parts[1] else 0
        if len(parts) > 2 and parts[2].strip():
            out[run_id] = (conn, parts[2].strip())
        else:
            out[run_id] = conn
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="WP2 Stage F Phase 2 residual training")
    p.add_argument("--mode", choices=("rung2", "iterate"), default="rung2")
    p.add_argument("--parent-registry", default=str(DEFAULT_PARENT_REGISTRY))
    p.add_argument("--reward", default=str(DEFAULT_REWARD))
    p.add_argument("--runs-root", default=str(DEFAULT_RUNS_ROOT))
    p.add_argument("--sidecar-log", default=str(DEFAULT_PROBE_LOG))
    p.add_argument("--device", default="auto")
    p.add_argument("--nstep", type=int, default=5)
    p.add_argument("--recovery-ticks", type=int, default=40)
    p.add_argument("--dt-max-ms", type=float, default=250.0)
    p.add_argument("--theta-max-deg", type=float, default=5.0)
    p.add_argument("--critic-lr", type=float, default=3e-4)
    p.add_argument("--actor-lr", type=float, default=3e-4)
    p.add_argument("--actor-l2", type=float, default=DEFAULT_ACTOR_L2,
                   help="iterate: actor L2-to-zero regularizer lambda_0 "
                        "(overrides TD3Config.lambda_zero; default 0.01)")
    p.add_argument("--steps", type=int, default=4000)
    p.add_argument("--batch-size", type=int, default=512)
    p.add_argument("--seed", type=int, default=0)
    # iterate-only
    p.add_argument("--iteration", type=int, default=1)
    p.add_argument("--run-conn", default=None, help="iterate: run_id:conn,... (default: probe set)")
    p.add_argument("--teacher-mix", action="store_true", help="iterate: enable 50/50 teacher mixing")
    p.add_argument("--teacher-mix-states", type=int, default=50000)
    p.add_argument("--explore-sigma", type=float, default=0.3)
    p.add_argument("--checkpoint-out", default=None)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.mode == "rung2":
            return run_rung2(args)
        return run_iterate(args)
    except (FileNotFoundError, KeyError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
