"""Stage A step 1b/2: classify runs and report version distributions."""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(ROOT, ".tmp", "stageA", "run_index.jsonl")

FULL_RUN_MIN_MS = 900000


def load():
    rows = []
    with open(IDX, "r", encoding="utf-8") as fh:
        for line in fh:
            rows.append(json.loads(line))
    return rows


def main():
    rows = load()
    print("total summaries: %d" % len(rows))
    print("result counts:", Counter(r["result"] for r in rows).most_common())
    print("last_wave counts:", sorted(Counter(r["last_wave"] for r in rows).items(), key=lambda x: (x[0] is None, x[0])))
    dur = [r["duration_ms"] for r in rows if isinstance(r["duration_ms"], (int, float))]
    print("duration_ms present: %d / %d" % (len(dur), len(rows)))
    print("full-run (>%d ms): %d" % (FULL_RUN_MIN_MS, sum(1 for d in dur if d >= FULL_RUN_MIN_MS)))

    died = [r for r in rows if r["result"] == "defeat" and r["last_wave"] == 17]
    surv = [r for r in rows if isinstance(r["last_wave"], int) and r["last_wave"] >= 18]
    print("\nRAW died_at_17=%d  survivors(wave>=18)=%d" % (len(died), len(surv)))

    def fullrun(rs):
        return [r for r in rs if isinstance(r["duration_ms"], (int, float)) and r["duration_ms"] >= FULL_RUN_MIN_MS]

    diedF, survF = fullrun(died), fullrun(surv)
    print("after full-run duration filter: died=%d survivors=%d" % (len(diedF), len(survF)))
    print("died with events.jsonl: %d ; survivors with events: %d"
          % (sum(1 for r in diedF if r["has_events"]), sum(1 for r in survF if r["has_events"])))

    def vdist(rs, label):
        c = Counter((r["policy_version"], r["mod_version"]) for r in rs)
        print("\n%s version distribution (n=%d):" % (label, len(rs)))
        for (p, m), n in c.most_common():
            print("  %-40s %-24s %d" % (p, m, n))
        return c

    vdist(diedF, "DIED_AT_17")
    vdist(survF, "SURVIVOR")
    return diedF, survF


if __name__ == "__main__":
    main()
