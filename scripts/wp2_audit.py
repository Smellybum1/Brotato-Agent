#!/usr/bin/env python3
"""Audit a fixed WP1 run corpus for WP2 combat-interface readiness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trainer.data.wp1_telemetry_audit import audit_runs, render_markdown


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-dir", type=Path, required=True)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args()

    audit = audit_runs(args.runs_dir)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(render_markdown(audit), encoding="utf-8")
    print(json.dumps(audit, indent=2))
    return 0 if audit["runs"] and audit["malformed_events"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
