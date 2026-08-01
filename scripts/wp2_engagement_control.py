#!/usr/bin/env python
"""Engagement control: per-character share of shop WEAPON purchases that are
(a) MELEE and (b) outside `set_gun`.

This is the BARE-arm control for the profile-port engagement readback. The port
sets allow_melee=false and allowed_weapon_sets=["set_gun"], so a post-port zero
is only informative if the un-ported rate is provably non-zero for the same
character.

Method (the trap): weapon metadata (`weapon_type`, `sets`) lives on the
`purchase_offer` event, NOT on the buy. A buy is a `purchase_decision` event
with payload.action.type == "shop_buy" and the bought id at
payload.action.item_id. Each buy is joined to the most recent preceding
`purchase_offer` board in the same run. The event-type key is e["event"].

Reads events.jsonl line by line (files can exceed 100 MB).
"""
from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict


def load_run_ids(state_files):
    run_ids = []
    seen = set()
    for sf in state_files:
        with open(sf, "r", encoding="utf-8") as fh:
            st = json.load(fh)
        for rid in st.get("collected_run_ids", []):
            if rid not in seen:
                seen.add(rid)
                run_ids.append(rid)
    return run_ids


def scan_run(run_dir):
    """Return (character, list of joined weapon buys, diagnostics)."""
    summary_path = os.path.join(run_dir, "summary.json")
    character = "<unknown>"
    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as fh:
            summary = json.load(fh)
        character = summary.get("character") or summary.get(
            "character_observed") or "<unknown>"

    board = {}          # id -> offer entry from the most recent board
    buys = []
    unjoined = 0
    total_buys = 0

    events_path = os.path.join(run_dir, "events.jsonl")
    if not os.path.exists(events_path):
        return character, buys, {"unjoined": 0, "total_buys": 0, "missing": True}

    with open(events_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except ValueError:
                continue
            ev = e.get("event")
            if ev == "purchase_offer":
                items = (e.get("payload") or {}).get("items") or []
                board = {}
                for it in items:
                    iid = it.get("id")
                    if iid is not None:
                        board[iid] = it
            elif ev == "purchase_decision":
                action = (e.get("payload") or {}).get("action") or {}
                if action.get("type") != "shop_buy":
                    continue
                total_buys += 1
                item_id = action.get("item_id")
                entry = board.get(item_id)
                if entry is None:
                    unjoined += 1
                    continue
                if entry.get("category") != "weapon":
                    continue
                buys.append(entry)

    return character, buys, {
        "unjoined": unjoined,
        "total_buys": total_buys,
        "missing": False,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True)
    ap.add_argument("--state-file", action="append", required=True)
    ap.add_argument("--label", required=True)
    args = ap.parse_args()

    run_ids = load_run_ids(args.state_file)

    per_char = defaultdict(lambda: {
        "runs": 0, "weapon_buys": 0, "melee": 0, "non_set_gun": 0,
        "all_buys": 0, "unjoined": 0, "no_sets_field": 0,
        "no_weapon_type_field": 0, "missing_runs": 0,
    })

    missing_dirs = []
    for rid in run_ids:
        run_dir = os.path.join(args.runs_dir, rid)
        if not os.path.isdir(run_dir):
            missing_dirs.append(rid)
            continue
        character, buys, diag = scan_run(run_dir)
        c = per_char[character]
        c["runs"] += 1
        if diag["missing"]:
            c["missing_runs"] += 1
        c["all_buys"] += diag["total_buys"]
        c["unjoined"] += diag["unjoined"]
        for entry in buys:
            c["weapon_buys"] += 1
            wt = entry.get("weapon_type")
            if wt is None:
                c["no_weapon_type_field"] += 1
            elif wt == "melee":
                c["melee"] += 1
            sets = entry.get("sets")
            if sets is None:
                c["no_sets_field"] += 1
            elif "set_gun" not in sets:
                c["non_set_gun"] += 1

    print("label: %s" % args.label)
    print("runs-dir: %s" % args.runs_dir)
    print("state-files: %s" % ", ".join(args.state_file))
    print("run ids listed: %d   run dirs missing: %d" %
          (len(run_ids), len(missing_dirs)))
    if missing_dirs:
        print("  missing: %s" % ", ".join(missing_dirs[:10]))
    print("")
    header = ("%-26s %5s %10s %8s %18s %18s" %
              ("character", "runs", "shop_buys", "weapons", "melee/weapons",
               "non_set_gun/weapons"))
    print(header)
    print("-" * len(header))
    for character in sorted(per_char):
        c = per_char[character]
        w = c["weapon_buys"]
        melee_s = "%d/%d" % (c["melee"], w)
        nsg_s = "%d/%d" % (c["non_set_gun"], w)
        if w:
            melee_s += " = %.4f" % (c["melee"] / w)
            nsg_s += " = %.4f" % (c["non_set_gun"] / w)
        else:
            melee_s += " = VACUOUS"
            nsg_s += " = VACUOUS"
        print("%-26s %5d %10d %8d %18s %18s" %
              (character, c["runs"], c["all_buys"], w, melee_s, nsg_s))

    print("")
    print("diagnostics (per character):")
    for character in sorted(per_char):
        c = per_char[character]
        print("  %-24s unjoined_buys=%d  offers_missing_weapon_type=%d  "
              "offers_missing_sets=%d  runs_without_events=%d" %
              (character, c["unjoined"], c["no_weapon_type_field"],
               c["no_sets_field"], c["missing_runs"]))


if __name__ == "__main__":
    main()
