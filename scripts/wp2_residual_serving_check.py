"""WP2 Stage F Phase 2 -- zero-init residual-actor serving check (design §6.3).

Proves the serving contract's central safety property: a FRESH (zero-init)
residual actor served at ``explore_sigma == 0`` reproduces PURE TEACHER actions
over a large batch of frozen payloads -- the residual is identically zero, so the
reply equals the teacher action to float noise. This is the offline gate that
must pass before iteration-0 collection (design §5 / §6.3).

The check:
  1. loads + verifies the frozen ``bc_v2_f`` trunk chain,
  2. builds a fresh zero-init :class:`ResidualActor`, saves a sha-stable
     checkpoint, and serves it through :class:`ResidualActorService` at sigma 0,
  3. replays >= 1000 frozen capture payloads (from a Phase-1 probe run's
     ``events.jsonl``) through ``service.predict`` and asserts, for every tick,
     ``|delta| == 0`` (to float noise) and ``reply == teacher.action`` to 1e-6.

No game, no deploy, no commit. ASCII console. Exit 0 on PASS, 1 on FAIL, 2 on IO.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_PARENT_REGISTRY = REPO_ROOT / "models" / "registry" / "bc_v2_f_s1.json"
DEFAULT_RUNS_ROOT = Path("C:/Users/moxhe/AppData/Roaming/Brotato/brotato_agent/runs")
DEFAULT_PROBE_RUN = "run_1784891038_60320"   # conn-1 victory w20 probe run
DEFAULT_REPORT = REPO_ROOT / "reports" / "wp2" / "residual_serving_check.json"
REPLY_TOL = 1e-6
DELTA_TOL = 1e-9


def _load_payloads(run_id: str, runs_root: Path, limit: int) -> list[dict]:
    """Stream a run's combat_capture payloads (each carries teacher.action)."""
    events_path = runs_root / run_id / "events.jsonl"
    payloads: list[dict] = []
    with events_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            e = json.loads(line)
            if e.get("event") != "combat_capture":
                continue
            payload = e.get("payload", {}) or {}
            teacher = payload.get("teacher", {}) or {}
            if "action" not in teacher:
                continue
            payloads.append(payload)
            if len(payloads) >= limit:
                break
    return payloads


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Zero-init residual-actor serving check (design 6.3)")
    parser.add_argument("--parent-registry", default=str(DEFAULT_PARENT_REGISTRY))
    parser.add_argument("--runs-root", default=str(DEFAULT_RUNS_ROOT))
    parser.add_argument("--probe-run", default=DEFAULT_PROBE_RUN)
    parser.add_argument("--min-payloads", type=int, default=1000)
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--checkpoint-out", default=str(REPO_ROOT / ".tmp" / "residual_pi0_zeroinit.pt"))
    args = parser.parse_args(argv)

    try:
        from trainer.bridge.sidecar import ResidualActorService, TorchModelService
        from trainer.rl.residual_actor import ResidualActor, save_residual_actor

        print("=== WP2 Stage F Phase 2: zero-init residual-actor serving check ===", flush=True)

        # 1. verified frozen trunk chain.
        parent = TorchModelService.from_registry(args.parent_registry, checkpoint="best")
        parent_sha = parent.identity.model_sha256
        print(f"parent trunk: {parent.identity.registry_run_name} (best.pt {parent_sha[:12]})", flush=True)

        # 2. fresh zero-init actor -> sha-stable checkpoint.
        actor = ResidualActor(parent._model)
        ckpt_path = Path(args.checkpoint_out)
        actor_sha = save_residual_actor(
            actor, ckpt_path, parent_model_sha256=parent_sha,
            parent_registry_run_name=parent.identity.registry_run_name, iteration=0,
        )
        print(f"zero-init actor checkpoint: {ckpt_path.name} (sha {actor_sha[:12]})", flush=True)

        # 3. serve at sigma 0 and replay frozen payloads.
        service = ResidualActorService.from_registry(
            args.parent_registry, ckpt_path, checkpoint="best", explore_sigma=0.0, actor_seed=0,
        )
        assert service.identity.model_sha256 == actor_sha
        assert service.identity.backend == "residual-actor"

        payloads = _load_payloads(args.probe_run, Path(args.runs_root), args.min_payloads + 200)
        if len(payloads) < args.min_payloads:
            print(f"error: only {len(payloads)} payloads (< {args.min_payloads})", file=sys.stderr)
            return 2

        max_abs_delta = 0.0
        max_reply_err = 0.0
        n_nonzero_teacher = 0
        n_checked = 0
        for payload in payloads:
            ax, ay, _ = service.predict(payload)
            extra = service.act_log_extra()
            teacher = payload["teacher"]["action"]
            tx, ty = float(teacher["x"]), float(teacher["y"])
            if math.hypot(tx, ty) > 0.0:
                n_nonzero_teacher += 1
                d = extra.get("delta_deg")
                if d is not None:
                    max_abs_delta = max(max_abs_delta, abs(float(d)))
            max_reply_err = max(max_reply_err, abs(ax - tx), abs(ay - ty))
            n_checked += 1

        reply_ok = max_reply_err <= REPLY_TOL
        delta_ok = max_abs_delta <= DELTA_TOL
        overall = reply_ok and delta_ok and n_checked >= args.min_payloads

        report = {
            "check": "residual_serving_zero_init",
            "design_ref": "6.3",
            "parent_registry_run_name": parent.identity.registry_run_name,
            "parent_model_sha256": parent_sha,
            "actor_sha256": actor_sha,
            "serving_backend": service.identity.backend,
            "explore_sigma": 0.0,
            "probe_run": args.probe_run,
            "n_payloads_checked": n_checked,
            "n_nonzero_teacher": n_nonzero_teacher,
            "max_abs_delta_deg": max_abs_delta,
            "max_reply_error": max_reply_err,
            "reply_tol": REPLY_TOL,
            "delta_tol": DELTA_TOL,
            "reply_reproduces_teacher": reply_ok,
            "delta_is_zero": delta_ok,
            "overall_pass": overall,
        }
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")

        print(f"checked {n_checked} payloads ({n_nonzero_teacher} non-zero teacher)", flush=True)
        print(f"max |delta| = {max_abs_delta:.3e} deg (tol {DELTA_TOL:.0e})", flush=True)
        print(f"max |reply - teacher| = {max_reply_err:.3e} (tol {REPLY_TOL:.0e})", flush=True)
        print(f"RESULT: {'PASS' if overall else 'FAIL'}", flush=True)
        print(f"report: {args.report}", flush=True)
        return 0 if overall else 1
    except (FileNotFoundError, KeyError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
