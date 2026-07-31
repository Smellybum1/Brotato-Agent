"""Q2: inter-contact interval distribution by wave, from HP-drop diffs between captures."""
import argparse, json, os, sys, io
from collections import defaultdict, Counter


def pct(xs, p):
    if not xs:
        return None
    s = sorted(xs)
    i = min(len(s) - 1, max(0, int(round((p / 100.0) * (len(s) - 1)))))
    return s[i]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ext-dir", required=True)
    ap.add_argument("--index", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--character", default=None)
    ap.add_argument("--danger", type=int, default=None)
    ap.add_argument("--window-sec", type=float, default=10.0)
    a = ap.parse_args()
    idx = {r["run_id"]: r for r in json.load(open(a.index, encoding="utf-8"))}
    iv = defaultdict(list)          # wave -> intervals (sec)
    runs_w = defaultdict(set)
    contacts_w = Counter()
    span_w = defaultdict(float)
    win_tot = Counter(); win_zero = Counter()
    win_counts = defaultdict(list)
    gaps_dropped = Counter()
    used = Counter(); dt_small = 0; caps_tot = 0
    for fn in sorted(os.listdir(a.ext_dir)):
        rid = fn[:-5]
        m = idx.get(rid, {})
        if a.character and m.get("character") != a.character:
            continue
        if a.danger is not None and m.get("danger") != a.danger:
            continue
        r = json.load(open(os.path.join(a.ext_dir, fn), encoding="utf-8"))
        caps = r["caps"]
        if not caps:
            continue
        used[m.get("character")] += 1
        bywave = defaultdict(list)
        for ts, wave, hp, dt, valid, x, y in caps:
            caps_tot += 1
            if dt < 10:
                dt_small += 1
            bywave[wave].append((ts, hp, dt))
        for wave, seq in bywave.items():
            seq.sort()
            runs_w[wave].add(rid)
            span = (seq[-1][0] - seq[0][0]) / 1000.0
            span_w[wave] += span
            ct = []
            for i in range(1, len(seq)):
                gap = seq[i][0] - seq[i - 1][0]
                if gap > 2000:            # capture stream discontinuity
                    gaps_dropped[wave] += 1
                    continue
                if seq[i][1] < seq[i - 1][1]:
                    ct.append(seq[i][0])
            contacts_w[wave] += len(ct)
            for i in range(1, len(ct)):
                iv[wave].append((ct[i] - ct[i - 1]) / 1000.0)
            # 10s windows tiled from wave start
            t0 = seq[0][0]; t1 = seq[-1][0]
            wl = int(a.window_sec * 1000)
            nwin = max(0, int((t1 - t0) // wl))
            counts = [0] * nwin
            for t in ct:
                k = int((t - t0) // wl)
                if 0 <= k < nwin:
                    counts[k] += 1
            win_tot[wave] += nwin
            win_zero[wave] += sum(1 for c in counts if c == 0)
            win_counts[wave].extend(counts)
    out = {"n_runs": sum(used.values()), "chars": dict(used),
           "captures": caps_tot, "captures_dt_lt_10ms": dt_small, "waves": {}}
    for w in sorted(iv | contacts_w.keys() if False else set(list(contacts_w) + list(iv))):
        xs = iv[w]
        wc = win_counts[w]
        out["waves"][w] = {
            "runs": len(runs_w[w]), "contacts": contacts_w[w], "intervals": len(xs),
            "wave_seconds_total": round(span_w[w], 1),
            "median_s": pct(xs, 50), "p75_s": pct(xs, 75), "p90_s": pct(xs, 90),
            "p99_s": pct(xs, 99), "max_s": max(xs) if xs else None,
            "min_s": min(xs) if xs else None,
            "windows": win_tot[w], "windows_zero": win_zero[w],
            "pct_windows_zero": 100.0 * win_zero[w] / win_tot[w] if win_tot[w] else None,
            "median_window_contacts": pct(wc, 50), "mean_window_contacts":
                (sum(wc) / len(wc)) if wc else None,
            "stream_gaps_skipped": gaps_dropped[w],
        }
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    print("runs", out["n_runs"], dict(used), "caps", caps_tot, "dt<10ms", dt_small)
    print("%-5s %5s %8s %9s %7s %7s %7s %7s %7s %8s %8s %8s %8s" % (
        "wave", "runs", "contacts", "intervals", "med", "p75", "p90", "p99", "max",
        "wins", "zeroWin", "%zero", "meanCt"))
    for w in sorted(out["waves"]):
        d = out["waves"][w]
        f = lambda k: "-" if d[k] is None else "%.2f" % d[k]
        print("%-5d %5d %8d %9d %7s %7s %7s %7s %7s %8d %8d %8s %8s" % (
            w, d["runs"], d["contacts"], d["intervals"], f("median_s"), f("p75_s"),
            f("p90_s"), f("p99_s"), f("max_s"), d["windows"], d["windows_zero"],
            "-" if d["pct_windows_zero"] is None else "%.1f" % d["pct_windows_zero"],
            "-" if d["mean_window_contacts"] is None else "%.2f" % d["mean_window_contacts"]))


if __name__ == "__main__":
    main()
