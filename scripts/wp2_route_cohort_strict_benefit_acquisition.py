#!/usr/bin/env python3
"""Run the fixed six-slot §47 sealed observational acquisition."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import wp2_collect_teacher as collector
from wp2_guarded_conversion_screen import verify_installed_content


EXPECTED_BUILD = "0.2.81-wp2-capture"
EXPECTED_POLICY = "teacher_v1-0.1.129-gun-wp1"
SLOTS = (1, 2, 3, 4, 5, 6)
WEAPONS = [
    "weapon_pistol",
    "weapon_smg",
    "weapon_revolver",
    "weapon_shredder",
    "weapon_crossbow",
    "weapon_laser_gun",
    "weapon_",
]
ERA = {
    "items": 179,
    "weapons": 48,
    "items_hash": "2018397571",
    "weapons_hash": "1530875081",
}


def config_path() -> Path:
    return Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "agent_config.json"


def runs_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "runs"


def fixed_config(instrumented: bool) -> dict:
    return {
        "auto_start": False,
        "resume_from_save": False,
        "character": "character_ranger",
        "danger": 5,
        "weapon_prefixes": WEAPONS,
        "movement_estop_enabled": False,
        "finale_v2": False,
        "finale_rate_full": False,
        "finale_no_panic": False,
        "finale_heal_seek": False,
        "finale_range_keep": False,
        "finale_projectile_priority": False,
        "finale_pivot_projectiles": True,
        "finale_co_rotate": False,
        "finale_ring_radius": False,
        "human_movement": False,
        "rare_gun_lock_persist": False,
        "clearance_guarded_conversion": instrumented,
        "route_scores_enabled": instrumented,
        "route_latch_revalidation_enabled": instrumented,
        "engage_distance_scale": 1.0,
        "body_clearance_scale": 1.0,
        "calm_threat_mult": 1.0,
        "tail_calm_penalty_mult": 1.0,
        "tail_calm_clearance_mult": 1.0,
        "time_scale": 1.0,
    }


def arm_and_read_back(instrumented: bool) -> None:
    wanted = fixed_config(instrumented)
    collector.atomic_json(config_path(), wanted)
    actual = json.loads(config_path().read_text(encoding="utf-8-sig"))
    mismatches = {
        key: {"wanted": value, "read": actual.get(key)}
        for key, value in wanted.items()
        if actual.get(key) != value
    }
    if mismatches:
        raise RuntimeError(f"arm readback mismatch: {mismatches}")
    print(
        "ARM READBACK: ranger D5 pistol-first "
        f"conversion/route_scores/revalidation={instrumented} time_scale=1.0"
    )


def verify_installed_identity(zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        controller = archive.read(
            "mods-unpacked/Tom-BrotatoAgent/runtime/agent_controller.gd"
        ).decode("utf-8", errors="replace")
        telemetry = archive.read(
            "mods-unpacked/Tom-BrotatoAgent/telemetry/telemetry_writer.gd"
        ).decode("utf-8", errors="replace")
    if f'const MOD_VERSION := "{EXPECTED_BUILD}"' not in controller:
        raise RuntimeError("installed MOD_VERSION does not match §47")
    if f'const POLICY_VERSION := "{EXPECTED_POLICY}"' not in telemetry:
        raise RuntimeError("installed POLICY_VERSION does not match §47")
    if collector.MOD_VERSION != EXPECTED_BUILD or collector.POLICY_VERSION != EXPECTED_POLICY:
        raise RuntimeError("collector identity constants do not match §47")
    print(f"INSTALLED IDENTITY: build={EXPECTED_BUILD} policy={EXPECTED_POLICY}")


def read_slot_run(state_path: Path) -> str | None:
    if not state_path.is_file():
        return None
    state = json.loads(state_path.read_text(encoding="utf-8-sig"))
    ids = state.get("collected_run_ids") or []
    if state.get("status") == "complete" and len(ids) == 1:
        return str(ids[0])
    return None


def validate_summary(run_id: str) -> None:
    summary = json.loads((runs_dir() / run_id / "summary.json").read_text(encoding="utf-8"))
    faults = []
    fault = collector.summary_fault(summary)
    if fault:
        faults.append(fault)
    expected = {
        "mod_version": EXPECTED_BUILD,
        "policy_version": EXPECTED_POLICY,
        "character_observed": "character_ranger",
        "danger": 5,
        "requested_danger": 5,
        "danger_ok": True,
        "weapon": "weapon_pistol_1",
        "clearance_guarded_conversion": True,
        "route_scores_enabled": True,
        "route_latch_revalidation_enabled": True,
        "body_clearance_scale": 1,
        "telemetry_complete": True,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            faults.append(f"{key}={summary.get(key)!r}, expected {value!r}")
    if summary.get("unlock_pool") != ERA:
        faults.append(f"unlock_pool={summary.get('unlock_pool')!r}, expected {ERA!r}")
    for key in ("errors", "hangs", "illegal_actions", "nonfinite_fixed"):
        if int(summary.get(key, 0) or 0):
            faults.append(f"{key}={summary.get(key)!r}")
    if faults:
        raise RuntimeError(f"slot summary {run_id} invalid: {'; '.join(faults)}")


def write_manifest(path: Path, slots: list[dict]) -> None:
    collector.atomic_json(
        path,
        {
            "schema_version": 1,
            "design": "s47_route_cohort_strict_benefit_sealed",
            "fixed_slots": list(SLOTS),
            "mod_version": EXPECTED_BUILD,
            "policy_version": EXPECTED_POLICY,
            "slots": slots,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--work-dir", type=Path, default=Path(".tmp/s47_route_cohort_strict_benefit")
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if collector.game_running():
        raise SystemExit("ABORT: Brotato is already running; attribute and stop it before §47")
    zip_path = verify_installed_content(root)
    verify_installed_identity(zip_path)
    args.work_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.work_dir / "manifest.json"
    slots = []
    if manifest_path.is_file():
        existing = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if existing.get("fixed_slots") != list(SLOTS):
            raise RuntimeError("existing manifest does not match fixed §47 slots")
        slots = list(existing.get("slots") or [])

    for slot in SLOTS:
        slot_dir = args.work_dir / f"slot_{slot:02d}_i"
        state_path = slot_dir / "state.json"
        report_path = slot_dir / "collector_report.json"
        run_id = read_slot_run(state_path)
        if run_id is None:
            if state_path.exists():
                state = json.loads(state_path.read_text(encoding="utf-8-sig"))
                raise RuntimeError(
                    f"slot {slot} incomplete ({state.get('status')!r}: "
                    f"{state.get('stop_reason')!r}); automatic replacement/top-up is forbidden"
                )
            if len(slots) >= slot:
                raise RuntimeError(f"manifest has slot {slot} but collector state is incomplete")
            subprocess.check_call(
                [sys.executable, str(root / "scripts/deploy_mod.py"), "--repair-launch"],
                cwd=root,
            )
            arm_and_read_back(True)
            slot_dir.mkdir(parents=True, exist_ok=True)
            command = [
                sys.executable,
                str(root / "scripts/wp2_collect_teacher.py"),
                "--runs", "1",
                "--state-file", str(state_path),
                "--report-file", str(report_path),
                "--launch",
            ]
            print(f"SLOT {slot}/6 arm=I: launching exactly one bounded run", flush=True)
            subprocess.check_call(command, cwd=root)
            run_id = read_slot_run(state_path)
            if run_id is None:
                raise RuntimeError(f"slot {slot} returned without one complete run")
        validate_summary(run_id)
        row = {"slot": slot, "arm": "I", "run_id": run_id}
        if len(slots) < slot:
            slots.append(row)
            write_manifest(manifest_path, slots)
        elif slots[slot - 1] != row:
            raise RuntimeError(f"slot {slot} manifest/state disagreement")
        print(f"SLOT {slot}/6 arm=I: certified {run_id}", flush=True)

    arm_and_read_back(False)
    if collector.game_running():
        collector.stop_game()
    if collector.game_running():
        raise RuntimeError("Brotato still running after §47 park")
    print(f"§47 ACQUISITION COMPLETE: 6/6; manifest={manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
