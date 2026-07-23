"""Build the ``combat_obs_v1`` dataset pipeline over the qualified v122 exact-20 campaign.

Streams ``events.jsonl`` for each of the 20 qualified runs, encodes every
``combat_capture`` payload with the frozen encoder (:mod:`trainer.observation.encoder_v1`),
and writes one compressed NPZ shard per run plus a manifest and a gate report.

The encoder (``trainer/observation/encoder_v1.py``) and schema
(``configs/wp2/observation_v1.yaml``) are frozen and never modified here.

No game, no deploy, no commit. Run with the project ``.venv`` python.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterator

import numpy as np

# Allow direct invocation (python scripts/wp2_build_combat_obs_v1.py) by putting
# the repo root on sys.path so ``trainer`` imports resolve without PYTHONPATH.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from trainer.observation.encoder_v1 import (
    EncodedObservation,
    ObservationError,
    canonical_digest,
    encode_capture,
    load_schema,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "configs" / "wp2" / "observation_v1.yaml"
ENCODER_REL = "trainer/observation/encoder_v1.py"
AUDIT_JSON = ROOT / "reports" / "wp2" / "v122_exact20_safety_audit.json"
RUNS_ROOT = Path("C:/Users/moxhe/AppData/Roaming/Brotato/brotato_agent/runs")
DATASET_DIR = ROOT / "datasets" / "combat_obs_v1"
MANIFEST_PATH = DATASET_DIR / "manifest.json"
REPORT_MD = ROOT / "reports" / "wp2" / "combat_obs_v1_dataset_report.md"
REPORT_JSON = ROOT / "reports" / "wp2" / "combat_obs_v1_dataset_report.json"

VALID_MIN = 200_000
DIGEST_STRIDE = 5000
TAIL_WAVES = (17, 18, 19, 20)
ALL_WAVES = tuple(range(1, 21))


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def load_run_ids(audit_path: Path) -> list[str]:
    """Return the qualified run ids from the exact-20 safety audit (runs array)."""
    data = json.loads(Path(audit_path).read_text(encoding="utf-8"))
    return [str(run["run_id"]) for run in data["runs"]]


def iter_capture_payloads(events_path: Path) -> Iterator[dict[str, Any]]:
    """Stream ``combat_capture`` payloads from an events.jsonl file (one JSON object per line)."""
    with open(events_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            if event.get("event") == "combat_capture":
                yield event["payload"]


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    """Uppercase hex sha256 of a file, read in chunks."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def git_head_commit(root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except Exception:  # pragma: no cover - git absence is non-fatal for the build
        return "unknown"


# --------------------------------------------------------------------------- #
# Per-run build
# --------------------------------------------------------------------------- #
def build_run(
    run_id: str,
    events_path: Path,
    schema: dict[str, Any],
    dataset_dir: Path,
) -> dict[str, Any]:
    """Encode one run, write its NPZ shard, and return the run manifest entry.

    Returns a dict with counts, per-wave counts, overflow stats, faults, the
    shard filename + sha256, and the determinism spot-check digests.
    """
    groups: list[str] = list(schema["groups"].keys())
    caps = {group: int(schema["groups"][group]["capacity"]) for group in groups}

    globals_rows: list[np.ndarray] = []
    ent_rows: dict[str, list[np.ndarray]] = {group: [] for group in groups}
    mask_rows: dict[str, list[np.ndarray]] = {group: [] for group in groups}
    dropped_rows: dict[str, list[int]] = {group: [] for group in groups}
    seq_list: list[int] = []
    wave_list: list[int] = []
    valid_list: list[bool] = []
    tvalid_list: list[bool] = []

    raw_max = {group: 0 for group in groups}
    overflow_count = {group: 0 for group in groups}
    faults: list[dict[str, Any]] = []
    spot_digests: list[dict[str, Any]] = []

    file_index = 0
    prev_seq: int | None = None
    monotonic = True
    last_enc: EncodedObservation | None = None
    last_seq: int | None = None
    last_index = -1

    for payload in iter_capture_payloads(events_path):
        cseq = payload.get("capture_seq")
        try:
            encoded = encode_capture(payload, schema)
        except ObservationError as exc:
            faults.append({"run_id": run_id, "capture_seq": cseq, "error": str(exc)})
            continue

        source = payload.get("entities", {}) or {}
        for group in groups:
            n_raw = len(source.get(group, []) or [])
            if n_raw > raw_max[group]:
                raw_max[group] = n_raw
            if n_raw > caps[group]:
                overflow_count[group] += 1

        globals_rows.append(np.asarray(encoded.global_features, dtype=np.float32))
        for group in groups:
            ent_rows[group].append(np.asarray(encoded.entities[group], dtype=np.float32))
            mask_rows[group].append(np.asarray(encoded.masks[group], dtype=np.float32))
            dropped_rows[group].append(int(encoded.dropped_counts[group]))

        seq_val = int(cseq) if cseq is not None else -1
        seq_list.append(seq_val)
        wave_list.append(int(payload.get("wave") or 0))
        valid_list.append(bool(encoded.valid))
        tvalid_list.append(bool(encoded.temporal_valid))

        if prev_seq is not None and cseq is not None and seq_val <= prev_seq:
            monotonic = False
        prev_seq = seq_val

        # Determinism spot-check: FIRST (index 0) and every DIGEST_STRIDE-th
        # capture, computed from the float64 EncodedObservation before float32
        # storage. capture_seq order == file order when monotonic (asserted below).
        if file_index % DIGEST_STRIDE == 0:
            spot_digests.append(
                {"position": file_index, "capture_seq": seq_val, "digest": canonical_digest(encoded)}
            )
        last_enc = encoded
        last_seq = seq_val
        last_index = file_index
        file_index += 1

    total = len(seq_list)
    if total == 0:
        raise RuntimeError(f"run {run_id}: no combat_capture payloads found")

    # LAST capture digest (append if not already the last recorded stride sample).
    if last_enc is not None and (not spot_digests or spot_digests[-1]["position"] != last_index):
        spot_digests.append(
            {"position": last_index, "capture_seq": last_seq, "digest": canonical_digest(last_enc)}
        )

    # Order everything by capture_seq (stable). No-op reorder when already monotonic.
    seq = np.asarray(seq_list, dtype=np.int64)
    order = np.argsort(seq, kind="stable")

    arrays: dict[str, np.ndarray] = {
        "global_features": np.stack(globals_rows, axis=0)[order],
        "capture_seq": seq.astype(np.int32)[order],
        "wave": np.asarray(wave_list, dtype=np.int32)[order],
        "valid": np.asarray(valid_list, dtype=bool)[order],
        "temporal_valid": np.asarray(tvalid_list, dtype=bool)[order],
    }
    del globals_rows
    for group in groups:
        arrays[f"entities_{group}"] = np.stack(ent_rows[group], axis=0)[order]
        ent_rows[group] = []
        arrays[f"mask_{group}"] = np.stack(mask_rows[group], axis=0)[order]
        mask_rows[group] = []
        arrays[f"dropped_{group}"] = np.asarray(dropped_rows[group], dtype=np.int32)[order]
        dropped_rows[group] = []
    gc.collect()

    dataset_dir.mkdir(parents=True, exist_ok=True)
    shard_name = f"{run_id}.npz"
    shard_path = dataset_dir / shard_name
    np.savez_compressed(shard_path, **arrays)
    shard_sha = sha256_file(shard_path)
    shard_bytes = shard_path.stat().st_size

    valid_arr = arrays["valid"]
    tvalid_arr = arrays["temporal_valid"]
    wave_arr = arrays["wave"]
    both_arr = valid_arr & tvalid_arr

    per_wave_total: dict[str, int] = {}
    per_wave_valid: dict[str, int] = {}
    for wave in sorted(set(int(w) for w in np.unique(wave_arr))):
        per_wave_total[str(wave)] = int((wave_arr == wave).sum())
        per_wave_valid[str(wave)] = int(((wave_arr == wave) & valid_arr).sum())

    entry = {
        "run_id": run_id,
        "shard_file": shard_name,
        "shard_sha256": shard_sha,
        "shard_bytes": int(shard_bytes),
        "capture_seq_monotonic": bool(monotonic),
        "counts": {
            "total": int(total),
            "valid": int(valid_arr.sum()),
            "temporal_valid": int(tvalid_arr.sum()),
            "valid_and_temporal_valid": int(both_arr.sum()),
        },
        "per_wave_total": per_wave_total,
        "per_wave_valid": per_wave_valid,
        "overflow": {
            group: {
                "overflow_samples": int(overflow_count[group]),
                "max_raw": int(raw_max[group]),
                "capacity": caps[group],
            }
            for group in groups
        },
        "fault_count": len(faults),
        "faults": faults,
        "determinism_spot_check": spot_digests,
    }
    del arrays
    gc.collect()
    return entry


# --------------------------------------------------------------------------- #
# Gates
# --------------------------------------------------------------------------- #
def evaluate_gates(
    both_valid_total: int,
    per_wave_valid: dict[int, int],
    fault_count: int,
    shards_written: int,
    shards_expected: int,
) -> list[dict[str, Any]]:
    """Pure gate arithmetic. Returns a list of gate result dicts.

    Overflow is intentionally not evaluated here (REPORT-ONLY, decided by the primary).
    """
    valid_total = sum(per_wave_valid.values())
    missing_waves = [w for w in ALL_WAVES if per_wave_valid.get(w, 0) <= 0]
    tail_valid = sum(per_wave_valid.get(w, 0) for w in TAIL_WAVES)
    tail_fraction = (tail_valid / valid_total) if valid_total else 0.0

    gates = [
        {
            "name": "valid_and_temporal_valid_min",
            "status": "PASS" if both_valid_total >= VALID_MIN else "FAIL",
            "value": int(both_valid_total),
            "threshold": VALID_MIN,
            "detail": f"{both_valid_total} >= {VALID_MIN}",
        },
        {
            "name": "all_waves_1_20_represented",
            "status": "PASS" if not missing_waves else "FAIL",
            "value": len(ALL_WAVES) - len(missing_waves),
            "threshold": len(ALL_WAVES),
            "missing_waves": missing_waves,
            "tail_waves_17_20_valid": int(tail_valid),
            "tail_fraction": round(tail_fraction, 6),
            "detail": (
                "all waves 1-20 present among valid samples"
                if not missing_waves
                else f"missing waves {missing_waves}"
            ),
        },
        {
            "name": "zero_encoding_faults",
            "status": "PASS" if fault_count == 0 else "FAIL",
            "value": int(fault_count),
            "threshold": 0,
            "detail": f"{fault_count} ObservationError faults",
        },
        {
            "name": "all_shards_written",
            "status": "PASS" if shards_written == shards_expected else "FAIL",
            "value": int(shards_written),
            "threshold": int(shards_expected),
            "detail": f"{shards_written}/{shards_expected} shards written with checksums",
        },
    ]
    return gates


def aggregate_overflow(run_entries: list[dict[str, Any]], groups: list[str]) -> dict[str, Any]:
    """REPORT-ONLY overflow rollup: per-group overflow samples + max raw across runs."""
    out: dict[str, Any] = {}
    for group in groups:
        overflow_samples = sum(e["overflow"][group]["overflow_samples"] for e in run_entries)
        max_raw = max((e["overflow"][group]["max_raw"] for e in run_entries), default=0)
        capacity = run_entries[0]["overflow"][group]["capacity"] if run_entries else None
        out[group] = {
            "overflow_samples": int(overflow_samples),
            "max_raw": int(max_raw),
            "capacity": capacity,
        }
    return out


# --------------------------------------------------------------------------- #
# Report rendering
# --------------------------------------------------------------------------- #
def render_report_md(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# combat_obs_v1 dataset build report")
    lines.append("")
    lines.append(f"- schema_id: `{report['schema_id']}`")
    lines.append(f"- observation schema hash: `{report['observation_schema_hash']}`")
    lines.append(f"- source capture schema hash: `{report['source_capture_schema_hash']}`")
    lines.append(f"- encoder: `{report['encoder_path']}` @ `{report['repo_head_commit']}`")
    lines.append(f"- runs: {report['run_count']} | build wall time: {report['build_wall_seconds']:.1f}s")
    lines.append(f"- dataset size on disk: {report['dataset_bytes']:,} bytes")
    lines.append("")
    lines.append("## Gates")
    lines.append("")
    lines.append("| gate | status | value | threshold | detail |")
    lines.append("| --- | --- | --- | --- | --- |")
    for gate in report["gates"]:
        lines.append(
            f"| {gate['name']} | {gate['status']} | {gate['value']} | {gate['threshold']} | {gate['detail']} |"
        )
    lines.append(f"| capacity_overflow | REPORT | see below | n/a | report-only, primary decides |")
    lines.append("")
    lines.append(f"Overall: **{report['overall_status']}** (overflow gate is report-only)")
    lines.append("")
    lines.append("## Aggregate counts")
    lines.append("")
    agg = report["aggregate"]
    lines.append(f"- total samples: {agg['total']:,}")
    lines.append(f"- valid: {agg['valid']:,}")
    lines.append(f"- temporal_valid: {agg['temporal_valid']:,}")
    lines.append(f"- valid AND temporal_valid: {agg['valid_and_temporal_valid']:,}")
    lines.append(f"- encoding faults: {agg['fault_count']}")
    lines.append("")
    lines.append("## Per-wave valid sample counts (aggregate)")
    lines.append("")
    lines.append("| wave | valid samples |")
    lines.append("| --- | --- |")
    for wave in ALL_WAVES:
        lines.append(f"| {wave} | {report['per_wave_valid'].get(str(wave), 0):,} |")
    lines.append("")
    tail = report["gates"][1]
    lines.append(
        f"Waves 17-20 tail: {tail['tail_waves_17_20_valid']:,} valid "
        f"({tail['tail_fraction']:.4f} of valid samples)"
    )
    lines.append("")
    lines.append("## Capacity overflow (REPORT-ONLY)")
    lines.append("")
    lines.append("| group | capacity | overflow samples | max raw entity count |")
    lines.append("| --- | --- | --- | --- |")
    for group, stats in report["overflow"].items():
        lines.append(
            f"| {group} | {stats['capacity']} | {stats['overflow_samples']:,} | {stats['max_raw']} |"
        )
    lines.append("")
    lines.append("## Per-run shards")
    lines.append("")
    lines.append("| run_id | samples | valid&temporal | faults | shard sha256 (first 16) |")
    lines.append("| --- | --- | --- | --- | --- |")
    for entry in report["runs"]:
        lines.append(
            f"| {entry['run_id']} | {entry['counts']['total']:,} | "
            f"{entry['counts']['valid_and_temporal_valid']:,} | {entry['fault_count']} | "
            f"{entry['shard_sha256'][:16]} |"
        )
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Main build
# --------------------------------------------------------------------------- #
def run_build(
    run_ids: list[str],
    schema: dict[str, Any],
    runs_root: Path,
    dataset_dir: Path,
) -> dict[str, Any]:
    groups: list[str] = list(schema["groups"].keys())
    start = time.time()
    run_entries: list[dict[str, Any]] = []
    for run_id in run_ids:
        events_path = runs_root / run_id / "events.jsonl"
        if not events_path.exists():
            raise FileNotFoundError(f"missing events.jsonl for {run_id}: {events_path}")
        t0 = time.time()
        entry = build_run(run_id, events_path, schema, dataset_dir)
        entry["build_seconds"] = round(time.time() - t0, 2)
        run_entries.append(entry)
        print(
            f"  {run_id}: {entry['counts']['total']} samples, "
            f"{entry['counts']['valid_and_temporal_valid']} valid&temporal, "
            f"{entry['fault_count']} faults, {entry['build_seconds']}s",
            flush=True,
        )
    wall = time.time() - start

    # Aggregates
    agg = {
        "total": sum(e["counts"]["total"] for e in run_entries),
        "valid": sum(e["counts"]["valid"] for e in run_entries),
        "temporal_valid": sum(e["counts"]["temporal_valid"] for e in run_entries),
        "valid_and_temporal_valid": sum(e["counts"]["valid_and_temporal_valid"] for e in run_entries),
        "fault_count": sum(e["fault_count"] for e in run_entries),
    }
    per_wave_valid_int: dict[int, int] = {w: 0 for w in ALL_WAVES}
    per_wave_valid_str: dict[str, int] = {}
    for entry in run_entries:
        for wave_str, count in entry["per_wave_valid"].items():
            per_wave_valid_str[wave_str] = per_wave_valid_str.get(wave_str, 0) + count
            per_wave_valid_int[int(wave_str)] = per_wave_valid_int.get(int(wave_str), 0) + count

    overflow = aggregate_overflow(run_entries, groups)
    dataset_bytes = sum(e["shard_bytes"] for e in run_entries)

    gates = evaluate_gates(
        both_valid_total=agg["valid_and_temporal_valid"],
        per_wave_valid=per_wave_valid_int,
        fault_count=agg["fault_count"],
        shards_written=len(run_entries),
        shards_expected=len(run_ids),
    )
    overall = "PASS" if all(g["status"] == "PASS" for g in gates) else "FAIL"

    encoder_head = git_head_commit(ROOT)

    manifest = {
        "schema_id": schema["schema_id"],
        "observation_schema_hash": schema["_schema_hash"],
        "source_capture_schema_hash": schema["source_capture_schema_hash"],
        "encoder_path": ENCODER_REL,
        "repo_head_commit": encoder_head,
        "runs_root": str(runs_root),
        "run_count": len(run_ids),
        "aggregate": {**agg, "dataset_bytes": int(dataset_bytes)},
        "runs": run_entries,
    }

    report = {
        "schema_id": schema["schema_id"],
        "observation_schema_hash": schema["_schema_hash"],
        "source_capture_schema_hash": schema["source_capture_schema_hash"],
        "encoder_path": ENCODER_REL,
        "repo_head_commit": encoder_head,
        "run_count": len(run_ids),
        "build_wall_seconds": round(wall, 2),
        "dataset_bytes": int(dataset_bytes),
        "aggregate": agg,
        "per_wave_valid": per_wave_valid_str,
        "overflow": overflow,
        "gates": gates,
        "overflow_gate": "REPORT",
        "overall_status": overall,
        "runs": [
            {
                "run_id": e["run_id"],
                "shard_file": e["shard_file"],
                "shard_sha256": e["shard_sha256"],
                "counts": e["counts"],
                "fault_count": e["fault_count"],
            }
            for e in run_entries
        ],
    }
    return {"manifest": manifest, "report": report, "wall": wall}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build combat_obs_v1 dataset")
    parser.add_argument("--audit", type=Path, default=AUDIT_JSON)
    parser.add_argument("--runs-root", type=Path, default=RUNS_ROOT)
    parser.add_argument("--dataset-dir", type=Path, default=DATASET_DIR)
    args = parser.parse_args()

    schema = load_schema(SCHEMA_PATH)
    run_ids = load_run_ids(args.audit)
    print(f"Building combat_obs_v1 over {len(run_ids)} runs -> {args.dataset_dir}", flush=True)

    result = run_build(run_ids, schema, args.runs_root, args.dataset_dir)

    args.dataset_dir.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(result["manifest"], indent=2), encoding="utf-8")
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(result["report"], indent=2), encoding="utf-8")
    REPORT_MD.write_text(render_report_md(result["report"]), encoding="utf-8")

    report = result["report"]
    print("\n=== GATES ===", flush=True)
    for gate in report["gates"]:
        print(f"  [{gate['status']}] {gate['name']}: {gate['detail']}", flush=True)
    print(f"  [REPORT] capacity_overflow: {report['overflow']}", flush=True)
    print(f"\nOverall: {report['overall_status']}  (wall {result['wall']:.1f}s)", flush=True)
    print(f"Dataset bytes: {report['dataset_bytes']:,}", flush=True)
    print(f"Manifest: {MANIFEST_PATH}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
