"""Build ``human_obs_absvel_v1`` — the human-labelled dataset re-encoded with
ABSOLUTE entity velocity.

Identical to ``scripts/wp2_build_human_obs_v1.py`` in every respect (same runs,
same row filters, same fixture-held-out split, same labels) except that entity
channels 2,3 hold ``entity.v`` instead of ``entity.v - player.v``. See
``trainer/observation/encoder_v1_absvel.py`` for why.

Implemented by rebinding the module globals of the original builder rather than
copying it, so the two datasets cannot drift apart in their filtering, split or
reporting logic.

The val fixtures are FORCED to the two already held out by
``configs/wp2/human_dataset_split_v1.yaml`` so the absvel numbers are comparable
to the previous runs row-for-row. Re-deriving the split would silently change
the denominator.

No game, no deploy, no commit. Run with the project ``.venv`` python.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.wp2_build_human_obs_v1 as base  # noqa: E402
from trainer.observation import encoder_v1_absvel  # noqa: E402

# The two fixtures already in validation for human_dataset_split_v1.
VAL_FIXTURES = ("881b35244be74181", "fd3db2b0a5d75e35")


#: Two variants. ``absvel`` fixes channels 2,3 only; ``absvel_dsort`` ALSO ranks
#: each group by distance instead of contact_risk, closing the slot-permutation
#: leak (see encoder_v1_absvel._entity_row).
VARIANTS = {
    "absvel": ("observation_v1_absvel.yaml", "human_obs_absvel_v1",
               "human_absvel_split_v1", "human_bc_input_v3_absvel.yaml"),
    "absvel_dsort": ("observation_v1_absvel_dsort.yaml", "human_obs_absvel_dsort_v1",
                     "human_absvel_dsort_split_v1", "human_bc_input_v4_absvel_dsort.yaml"),
}


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    variant = "absvel"
    if "--variant" in args:
        i = args.index("--variant")
        variant = args[i + 1]
        del args[i:i + 2]
    schema_file, dataset_id, split_id, input_file = VARIANTS[variant]

    # Encoder swap. ``scan_run`` and ``verify_v127_additive_inertness`` both read
    # ``encode_capture`` from the builder module's globals, so one rebind covers
    # the build and its inertness proof.
    base.encode_capture = encoder_v1_absvel.encode_capture
    base.SCHEMA_PATH = ROOT / "configs" / "wp2" / schema_file
    base.SCHEMA_ID = dataset_id
    base.SPLIT_ID = split_id
    base.DATASET_DIR = ROOT / "datasets" / dataset_id
    base.SPLIT_CONFIG = ROOT / "configs" / "wp2" / f"{split_id}.yaml"
    base.INPUT_CONFIG_FOR_LOADER = ROOT / "configs" / "wp2" / input_file
    base.REPORT_MD = ROOT / "reports" / "wp2" / f"{dataset_id}_dataset_report.md"
    base.REPORT_JSON = ROOT / "reports" / "wp2" / f"{dataset_id}_dataset_report.json"

    if not any(a.startswith("--dataset-dir") for a in args):
        args += ["--dataset-dir", str(base.DATASET_DIR)]
    if not any(a.startswith("--split-config") for a in args):
        args += ["--split-config", str(base.SPLIT_CONFIG)]
    if not any(a.startswith("--val-fixture") for a in args):
        for fixture in VAL_FIXTURES:
            args += ["--val-fixture", fixture]
    print(f"absvel build: schema={base.SCHEMA_PATH.name} "
          f"encoder=encoder_v1_absvel.encode_capture")
    return base.main(args)


if __name__ == "__main__":
    raise SystemExit(main())
