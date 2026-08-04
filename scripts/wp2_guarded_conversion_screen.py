#!/usr/bin/env python3
"""Run the fixed §42 guarded-conversion mediator screen one trial at a time.

The design is frozen in reports/wp2/clearance_guarded_conversion_screen_prereg.md.
This driver does not deploy. It requires an exact installed/source content match,
arms after deploy, reads the config back, delegates one bounded run to the proven
teacher collector, and records the fixed slot-to-run mapping.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import wp2_collect_teacher as collector


ORDER = ("C", "T", "T", "C", "T", "C", "C", "T")
EXPECTED_BUILD = "0.2.80-wp2-capture"
WEAPONS = [
    "weapon_pistol",
    "weapon_smg",
    "weapon_revolver",
    "weapon_shredder",
    "weapon_crossbow",
    "weapon_laser_gun",
    "weapon_",
]


def config_path() -> Path:
    return Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "agent_config.json"


def runs_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "runs"


def expected_source_files(source: Path) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix in {".pyc", ".pyo"} or path.name.startswith("."):
            continue
        name = "mods-unpacked/Tom-BrotatoAgent/" + path.relative_to(source).as_posix()
        out[name] = path.read_bytes()
    return out


def verify_installed_content(root: Path) -> Path:
    stamp_path = root / ".deploy_stamp"
    if not stamp_path.is_file():
        raise RuntimeError("missing .deploy_stamp; deploy 0.2.80 before running §42")
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    if stamp.get("target") != "agent":
        raise RuntimeError(f"deploy target is {stamp.get('target')!r}, not agent")
    zip_path = Path(stamp.get("zip", ""))
    if not zip_path.is_file():
        raise RuntimeError(f"installed zip is missing: {zip_path}")
    source = root / "mod" / "mods-unpacked" / "Tom-BrotatoAgent"
    expected = expected_source_files(source)
    with zipfile.ZipFile(zip_path) as archive:
        names = {
            name for name in archive.namelist()
            if not name.endswith("/")
        }
        if names != set(expected):
            missing = sorted(set(expected) - names)
            extra = sorted(names - set(expected))
            raise RuntimeError(
                f"installed/source file set mismatch; missing={missing[:5]} extra={extra[:5]}"
            )
        mismatched = [name for name, body in expected.items() if archive.read(name) != body]
        config_text = archive.read(
            "mods-unpacked/Tom-BrotatoAgent/teacher/config.gd"
        ).decode("utf-8", errors="replace")
    if mismatched:
        raise RuntimeError(f"installed/source content mismatch: {mismatched[:8]}")
    port_lines = [
        line for line in config_text.splitlines()
        if "EXPERIMENT_PORT_WR_PROFILE_TO :=" in line
    ]
    if len(port_lines) != 1 or ':= ""' not in port_lines[0]:
        raise RuntimeError(f"experimental profile port is not inert: {port_lines}")
    print(f"CONTENT MATCH: {len(expected)}/{len(expected)} installed files equal source")
    print("PORT INERT: EXPERIMENT_PORT_WR_PROFILE_TO is empty")
    return zip_path


def fixed_config(treatment: bool) -> dict:
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
        "clearance_guarded_conversion": treatment,
        "engage_distance_scale": 1.0,
        "body_clearance_scale": 1.0,
        "route_scores_enabled": False,
        "calm_threat_mult": 1.0,
        "tail_calm_penalty_mult": 1.0,
        "tail_calm_clearance_mult": 1.0,
    }


def arm_and_read_back(treatment: bool) -> None:
    wanted = fixed_config(treatment)
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
        "ARM READBACK: ranger danger=5 pistol-first "
        f"clearance_guarded_conversion={treatment} all other arms inert"
    )


def read_slot_run(state_path: Path) -> str | None:
    if not state_path.is_file():
        return None
    state = json.loads(state_path.read_text(encoding="utf-8-sig"))
    ids = state.get("collected_run_ids") or []
    if state.get("status") == "complete" and len(ids) == 1:
        return str(ids[0])
    return None


def validate_slot_summary(run_id: str, arm: str) -> None:
    path = runs_dir() / run_id / "summary.json"
    summary = json.loads(path.read_text(encoding="utf-8"))
    faults = []
    fault = collector.summary_fault(summary)
    if fault:
        faults.append(fault)
    expected = {
        "character_observed": "character_ranger",
        "danger": 5,
        "weapon": "weapon_pistol_1",
        "clearance_guarded_conversion": arm == "T",
        "route_scores_enabled": False,
        "body_clearance_scale": 1,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            faults.append(f"{key}={summary.get(key)!r}, expected {value!r}")
    if summary.get("mod_version") != EXPECTED_BUILD:
        faults.append(f"mod_version={summary.get('mod_version')!r}")
    if faults:
        raise RuntimeError(f"slot summary {run_id} invalid: {'; '.join(faults)}")


def write_manifest(path: Path, slots: list[dict]) -> None:
    collector.atomic_json(
        path,
        {
            "schema_version": 1,
            "design": "s42_clearance_guarded_conversion_screen",
            "fixed_order": list(ORDER),
            "mod_version": EXPECTED_BUILD,
            "slots": slots,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", type=Path, default=Path(".tmp/s42_guarded_conversion"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if collector.game_running():
        raise SystemExit("ABORT: Brotato is already running; attribute and stop it before §42")
    verify_installed_content(root)
    args.work_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.work_dir / "manifest.json"
    slots: list[dict] = []
    if manifest_path.is_file():
        existing = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        slots = list(existing.get("slots") or [])
        for index, row in enumerate(slots):
            if index >= len(ORDER) or row.get("arm") != ORDER[index]:
                raise RuntimeError("existing manifest does not match the preregistered order")

    for index, arm in enumerate(ORDER, start=1):
        slot_dir = args.work_dir / f"slot_{index:02d}_{arm.lower()}"
        state_path = slot_dir / "state.json"
        report_path = slot_dir / "collector_report.json"
        run_id = read_slot_run(state_path)
        if run_id is None:
            if state_path.exists():
                state = json.loads(state_path.read_text(encoding="utf-8-sig"))
                raise RuntimeError(
                    f"slot {index} has non-complete collector state "
                    f"({state.get('status')!r}: {state.get('stop_reason')!r}); "
                    "diagnose it explicitly — automatic top-up is forbidden"
                )
            if len(slots) >= index:
                raise RuntimeError(f"manifest has slot {index} but collector state is incomplete")
            arm_and_read_back(arm == "T")
            slot_dir.mkdir(parents=True, exist_ok=True)
            command = [
                sys.executable,
                str(root / "scripts" / "wp2_collect_teacher.py"),
                "--runs", "1",
                "--state-file", str(state_path),
                "--report-file", str(report_path),
                "--launch",
            ]
            print(f"SLOT {index}/8 arm={arm}: launching exactly one bounded run", flush=True)
            subprocess.check_call(command, cwd=root)
            run_id = read_slot_run(state_path)
            if run_id is None:
                raise RuntimeError(f"slot {index} collector returned without one complete run")
        validate_slot_summary(run_id, arm)
        row = {"slot": index, "arm": arm, "run_id": run_id}
        if len(slots) < index:
            slots.append(row)
            write_manifest(manifest_path, slots)
        elif slots[index - 1] != row:
            raise RuntimeError(f"slot {index} manifest/state disagreement")
        print(f"SLOT {index}/8 arm={arm}: certified {run_id}", flush=True)

    arm_and_read_back(False)
    print(f"§42 COLLECTION COMPLETE: 8/8; manifest={manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
