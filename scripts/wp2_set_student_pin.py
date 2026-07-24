"""Set or clear the student-serving pin in the live agent_config.json.

Small, auditable surface for the Stage F live pattern: pin the actor sha +
enable student serving before a campaign, restore the idle state after.
Preserves every other key in the config (same contract as
wp2_collect_teacher.set_auto_start).

Usage:
  wp2_set_student_pin.py --enable --sha <MODEL_SHA256>
  wp2_set_student_pin.py --disable --sha <PRODUCTION_PIN_SHA256>
  wp2_set_student_pin.py --show
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SHA256_HEX_LEN = 64


def config_path() -> Path:
    return Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "agent_config.json"


def load_config(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"agent_config.json is not an object: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--enable", action="store_true", help="student_enabled=true + pin sha")
    group.add_argument("--disable", action="store_true", help="student_enabled=false + pin sha")
    group.add_argument("--show", action="store_true", help="print the current config and exit")
    parser.add_argument("--sha", default=None, help="model sha256 to pin (required with --enable/--disable)")
    args = parser.parse_args()

    path = config_path()
    config = load_config(path)

    if args.show:
        json.dump(config, sys.stdout, indent=2)
        print()
        return 0

    if not args.sha or len(args.sha) != SHA256_HEX_LEN:
        parser.error("--sha must be a 64-hex-char sha256 with --enable/--disable")
    sha = args.sha.upper()

    config["student_enabled"] = bool(args.enable)
    config["student_model_sha256"] = sha
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"student_enabled={config['student_enabled']} student_model_sha256={sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
