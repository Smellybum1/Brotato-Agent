#!/usr/bin/env python3
"""Audit append-only WP2 combat-capture events and write small reports."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trainer.data.combat_capture_audit import audit_capture_runs, render_markdown


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=Path(os.environ.get("APPDATA", "")) / "Brotato" / "brotato_agent" / "runs",
    )
    parser.add_argument("--run-id", action="append", default=[])
    parser.add_argument("--output-prefix", default="wp2_combat_capture_audit_v2")
    args = parser.parse_args()
    schema = ROOT / "configs" / "wp2" / "combat_capture_v2.schema.json"
    audit = audit_capture_runs(args.runs_dir, schema, set(args.run_id) or None)
    output_dir = ROOT / "reports" / "wp2"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{args.output_prefix}.json"
    markdown_path = output_dir / f"{args.output_prefix}.md"
    json_path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(audit), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(markdown_path), **audit}, indent=2))
    return 0 if audit["schema_mismatches"] == 0 and audit["invalid_actions"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
