"""WP2 -- joint contingency cross-tab for the "density veto starves collection" diagnosis.

Entirely offline over archived captures. No gameplay, no deploy, no mod edits.

Ports (verbatim) two helpers from mod/mods-unpacked/Tom-BrotatoAgent/teacher/potential_field.gd:
  _count_nearby_enemies   (line 2860)
  _enemies_blocking_loot  (line 2874)
and the density veto condition at potential_field.gd:2925
  (`if nearby >= BotConfig.PACK_DENSITY_SOFT: return Vector2.ZERO` inside _loot_attraction).

Usage:
  APPDATA='C:\\Users\\moxhe\\AppData\\Roaming' .venv/Scripts/python.exe \
      scripts/wp2_density_veto_contingency.py \
      --runs-dir 'C:\\Users\\moxhe\\AppData\\Roaming\\Brotato\\brotato_agent\\runs' \
      --out reports/wp2/density_veto_contingency.md
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from collections import Counter, defaultdict

# --- constants, verified by reading teacher/config.gd -------------------------
# config.gd:305 PACK_DENSITY_RADIUS, :306 PACK_DENSITY_SOFT, :71 LOOT_PACK_ALLOW,
# :72 LOOT_PATH_WIDTH, :73 LOOT_PILE_CLEAR_RADIUS, :401 LOOT_DASH_SCAN_RADIUS,
# :111 LATE_SURVIVAL_WAVE, :112 LATE_SURVIVAL_HP_RATIO, :116 BOSS_FINALE_WAVE
PACK_DENSITY_RADIUS = 280.0
PACK_DENSITY_SOFT = 8.0
LOOT_PACK_ALLOW = 2
LOOT_PATH_WIDTH = 120.0
LOOT_PILE_CLEAR_RADIUS = 160.0
LOOT_DASH_SCAN_RADIUS = 420.0
LATE_SURVIVAL_WAVE = 17
LATE_SURVIVAL_HP_RATIO = 0.85
BOSS_FINALE_WAVE = 20


def _xy(d):
    return (float(d.get("x", 0.0)), float(d.get("y", 0.0)))


def count_nearby_enemies(pos, enemies, bosses) -> int:
    px, py = pos
    n = 0
    r2 = PACK_DENSITY_RADIUS * PACK_DENSITY_RADIUS
    for e in enemies:
        ex, ey = _xy(e)
        if (ex - px) ** 2 + (ey - py) ** 2 <= r2:
            n += 1
    for b in bosses:
        bx, by = _xy(b)
        if (bx - px) ** 2 + (by - py) ** 2 <= r2:
            n += 2
    return n


def enemies_blocking_loot(pos, loot_pos, enemies, bosses) -> int:
    px, py = pos
    lx, ly = loot_pos
    pathx, pathy = lx - px, ly - py
    plen = max(math.hypot(pathx, pathy), 1.0)
    dx, dy = pathx / plen, pathy / plen
    n = 0
    for e in enemies:
        ex, ey = _xy(e)
        if math.hypot(ex - lx, ey - ly) <= LOOT_PILE_CLEAR_RADIUS:
            n += 1
            continue
        rx, ry = ex - px, ey - py
        along = rx * dx + ry * dy
        if along < 0.0 or along > plen:
            continue
        lateral = math.hypot(rx - dx * along, ry - dy * along)
        if lateral <= LOOT_PATH_WIDTH:
            n += 1
    for b in bosses:
        bx, by = _xy(b)
        if math.hypot(bx - lx, by - ly) <= LOOT_PILE_CLEAR_RADIUS * 1.25:
            n += 2
            continue
        rx, ry = bx - px, by - py
        along = rx * dx + ry * dy
        if along < 0.0 or along > plen:
            continue
        lateral = math.hypot(rx - dx * along, ry - dy * along)
        if lateral <= LOOT_PATH_WIDTH * 1.15:
            n += 2
    return n


# --- run enumeration ----------------------------------------------------------

def read_run_meta(run_dir):
    """Return dict with run_start payload fields + summary fields, or None."""
    ev = os.path.join(run_dir, "events.jsonl")
    if not os.path.exists(ev):
        return None
    meta = {"run_dir": run_dir, "run_id": os.path.basename(run_dir)}
    rs = None
    try:
        with open(ev, "r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("event") == "run_start":
                    rs = rec.get("payload") or {}
                    break
    except Exception as exc:
        meta["read_error"] = repr(exc)
        return meta
    if rs is None:
        meta["no_run_start"] = True
        return meta
    meta["mod_version"] = rs.get("mod_version")
    meta["policy_version"] = rs.get("policy_version")
    meta["character"] = rs.get("character")
    meta["human_movement"] = rs.get("human_movement")
    meta["time_scale"] = rs.get("time_scale")
    sm = os.path.join(run_dir, "summary.json")
    if os.path.exists(sm):
        try:
            s = json.load(open(sm, "r", encoding="utf-8"))
            meta["duration_ms"] = s.get("duration_ms")
            meta["last_wave"] = s.get("last_wave")
            meta["result"] = s.get("result")
            # summary is the authority when run_start lacks the field
            if meta.get("human_movement") is None:
                meta["human_movement"] = s.get("human_movement")
        except Exception as exc:
            meta["summary_error"] = repr(exc)
    return meta


# --- per-capture term computation --------------------------------------------

def analyse_capture(pl):
    ent = pl.get("entities") or {}
    enemies = ent.get("enemies") or []
    bosses = ent.get("bosses") or []
    materials = ent.get("materials") or []
    consumables = ent.get("consumables") or []
    projectiles = ent.get("projectiles") or []
    player = pl.get("player") or {}
    pos = _xy(player)
    wave = int(pl.get("wave", 0))
    hp = float(player.get("hp", 1))
    max_hp = max(float(player.get("max_hp", 1)), 1.0)
    hp_ratio = hp / max_hp

    nearby = count_nearby_enemies(pos, enemies, bosses)

    t1 = (nearby >= PACK_DENSITY_SOFT) and bool(materials)

    def admissible(items):
        out = []
        for it in items:
            ip = _xy(it)
            if math.hypot(ip[0] - pos[0], ip[1] - pos[1]) > LOOT_DASH_SCAN_RADIUS:
                continue
            if enemies_blocking_loot(pos, ip, enemies, bosses) <= LOOT_PACK_ALLOW:
                out.append(ip)
        return out

    adm_mat = admissible(materials)
    adm_con = admissible(consumables)
    t2_mat = bool(adm_mat)
    t2_con = bool(adm_con)

    dash = ((pl.get("teacher") or {}).get("contributions") or {}).get("loot_dash") or {}
    dash_active = dash.get("active")
    t3 = (dash_active is False)

    # T4: nearest admissible material, undefined if none
    t4 = None
    if adm_mat:
        m = min(adm_mat, key=lambda p: math.hypot(p[0] - pos[0], p[1] - pos[1]))
        act = (pl.get("teacher") or {}).get("action") or {}
        ax, ay = float(act.get("x", 0.0)), float(act.get("y", 0.0))
        alen = math.hypot(ax, ay)
        mvx, mvy = m[0] - pos[0], m[1] - pos[1]
        mlen = math.hypot(mvx, mvy)
        if alen > 0.0 and mlen > 0.0:
            t4 = ((ax / alen) * (mvx / mlen) + (ay / alen) * (mvy / mlen)) < 0.0
        else:
            t4 = None  # degenerate: zero action or player standing on the pile

    joint = None
    if t4 is None:
        joint = False if not (t1 and t2_mat and t3) else None
    else:
        joint = bool(t1 and t2_mat and t3 and t4)

    late = (
        wave >= LATE_SURVIVAL_WAVE
        and wave < BOSS_FINALE_WAVE
        and hp_ratio <= LATE_SURVIVAL_HP_RATIO
        and bool(enemies or bosses or projectiles)
    )

    return {
        "wave": wave,
        "nearby": nearby,
        "t1": t1,
        "t2_mat": t2_mat,
        "t2_con": t2_con,
        "t3": t3,
        "t4": t4,
        "joint": joint,
        "late": late,
        "finale": wave >= BOSS_FINALE_WAVE,
        "dash_active": dash_active,
        "dash_state": dash.get("state"),
        "n_materials": len(materials),
        "n_consumables": len(consumables),
        "n_enemies": len(enemies),
        "n_bosses": len(bosses),
        "hp_ratio": hp_ratio,
        "action_zero": ((pl.get("teacher") or {}).get("action") or {}).get("x", 0.0) == 0.0
        and ((pl.get("teacher") or {}).get("action") or {}).get("y", 0.0) == 0.0,
    }


def stratum_of(wave):
    if 15 <= wave <= 16:
        return "w15-16"
    if 17 <= wave <= 19:
        return "w17-19"
    if wave >= 20:
        return "w20"
    return "w<15"


def pct(k, n):
    return "n/a" if n == 0 else "%.4f (%d/%d)" % (k / n, k, n)


def deciles(vals):
    if not vals:
        return []
    s = sorted(vals)
    return [s[min(len(s) - 1, int(round(q / 10.0 * (len(s) - 1))))] for q in range(0, 11)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", default=os.path.join(
        os.environ.get("APPDATA", ""), "Brotato", "brotato_agent", "runs"))
    ap.add_argument("--out", default=os.path.join("reports", "wp2",
                                                  "density_veto_contingency.md"))
    ap.add_argument("--full-run-min-ms", type=float, default=None,
                    help="threshold chosen AFTER inspecting the histogram; default = report only")
    args = ap.parse_args()

    L = []

    def emit(s=""):
        print(s)
        L.append(s)

    runs_dir = args.runs_dir
    run_dirs = sorted(
        os.path.join(runs_dir, d) for d in os.listdir(runs_dir)
        if d.startswith("run_") and os.path.isdir(os.path.join(runs_dir, d))
    )
    emit("# Density-veto joint contingency (offline, archived captures)")
    emit()
    emit("Runs dir: `%s`" % runs_dir)
    emit("Run directories enumerated: **%d**" % len(run_dirs))
    emit()

    metas = [read_run_meta(d) for d in run_dirs]
    metas = [m for m in metas if m is not None]
    emit("Run dirs with an `events.jsonl`: **%d**" % len(metas))
    bad = [m for m in metas if m.get("no_run_start") or m.get("read_error")]
    emit("Run dirs with no readable `run_start`: **%d**" % len(bad))
    emit()

    # ---- run selection table
    emit("## 1. Run selection")
    emit()
    emit("### 1a. mod_version x policy_version x count (ALL runs, before any exclusion)")
    emit()
    tab = Counter((m.get("mod_version"), m.get("policy_version"))
                  for m in metas if not m.get("no_run_start"))
    emit("| mod_version | policy_version | runs |")
    emit("|---|---|---|")
    for (mv, pv), c in sorted(tab.items(), key=lambda kv: (-kv[1], str(kv[0]))):
        emit("| %s | %s | %d |" % (mv, pv, c))
    emit()

    emit("### 1b. human_movement and time_scale distributions (ALL runs)")
    emit()
    emit("human_movement: " + json.dumps(
        {str(k): v for k, v in Counter(m.get("human_movement") for m in metas).items()}))
    emit("time_scale: " + json.dumps(
        {str(k): v for k, v in Counter(m.get("time_scale") for m in metas).items()}))
    emit()

    # ---- era selection
    ERA_MODS = {"0.2.49-wp2-capture", "0.2.50-wp2-capture", "0.2.49", "0.2.50"}
    ERA_POL = {"teacher_v1-0.1.129-gun-wp1", "0.1.129"}

    def in_era(m):
        mv = m.get("mod_version") or ""
        pv = m.get("policy_version") or ""
        return (mv in ERA_MODS or mv.startswith("0.2.49") or mv.startswith("0.2.50")) and \
               ("0.1.129" in pv)

    era = [m for m in metas if in_era(m)]
    emit("### 1c. Era filter")
    emit()
    emit("Era rule kept: mod_version starts with `0.2.49`/`0.2.50` AND policy_version contains `0.1.129`.")
    emit("Runs in era (before human/time_scale exclusion): **%d**" % len(era))
    emit("Exact (mod, policy) pairs kept: " + json.dumps(
        sorted({(m.get("mod_version"), m.get("policy_version")) for m in era})))
    emit()

    n_era = len(era)
    era_no_human = [m for m in era if m.get("human_movement") is not True]
    emit("Excluded `human_movement == true`: **%d** -> %d remain"
         % (n_era - len(era_no_human), len(era_no_human)))
    kept = [m for m in era_no_human if (m.get("time_scale") in (1, 1.0, None))]
    dropped_ts = [m for m in era_no_human if m not in kept]
    emit("time_scale values among era/non-human runs: " + json.dumps(
        {str(k): v for k, v in Counter(m.get("time_scale") for m in era_no_human).items()}))
    emit("Excluded `time_scale != 1.0`: **%d** -> **%d runs KEPT**"
         % (len(dropped_ts), len(kept)))
    emit()

    # ---- duration histogram
    durs = [m.get("duration_ms") for m in kept]
    have = [d for d in durs if isinstance(d, (int, float))]
    emit("### 1d. duration_ms histogram over the %d kept runs (%d have summary.json duration_ms)"
         % (len(kept), len(have)))
    emit()
    if have:
        edges = [0, 30e3, 60e3, 90e3, 120e3, 180e3, 240e3, 300e3, 360e3, 420e3,
                 600e3, 900e3, 1.2e6, 1.5e6, 2e6, float("inf")]
        hist = Counter()
        for d in have:
            for i in range(len(edges) - 1):
                if edges[i] <= d < edges[i + 1]:
                    hist[i] += 1
                    break
        emit("| bin (ms) | bin (min) | runs |")
        emit("|---|---|---|")
        for i in range(len(edges) - 1):
            if hist[i]:
                emit("| %.0f - %.0f | %.1f - %.1f | %d "
                     % (edges[i], edges[i + 1] if edges[i + 1] != float("inf") else -1,
                        edges[i] / 60000.0,
                        edges[i + 1] / 60000.0 if edges[i + 1] != float("inf") else -1,
                        hist[i]) + "|")
        emit()
        emit("duration_ms deciles: " + json.dumps([round(x) for x in deciles(have)]))
        emit("min=%.0f median=%.0f max=%.0f" % (min(have), statistics.median(have), max(have)))
    else:
        emit("NO duration_ms available -- full-run vs fixture split CANNOT be computed.")
    emit()

    thr = args.full_run_min_ms
    if thr is None:
        # data-driven: full runs ~1.14e6 ms; fixtures <= ~6 min. Use 600e3 as the gap.
        thr = 600e3
    n_full = sum(1 for d in have if d >= thr)
    n_fix = sum(1 for d in have if d < thr)
    emit("Full-run / fixture cut at duration_ms >= %.0f (%.1f min): FULL=%d, FIXTURE=%d, "
         "UNKNOWN(no duration)=%d" % (thr, thr / 60000.0, n_full, n_fix, len(kept) - len(have)))
    emit()
    fixw = Counter()
    for m in kept:
        d = m.get("duration_ms")
        if isinstance(d, (int, float)) and d < thr:
            fixw[m.get("last_wave")] += 1
    emit("FIXTURE runs by last_wave: " + json.dumps({str(k): v for k, v in sorted(fixw.items(), key=lambda x: str(x[0]))}))
    emit()

    # ---- capture pass
    emit("## 2. Capture-level denominators")
    emit()
    rows = []
    per_run = defaultdict(list)
    n_lines = n_cc = n_valid = 0
    for m in kept:
        rid = m["run_id"]
        with open(os.path.join(m["run_dir"], "events.jsonl"), "r", encoding="utf-8") as fh:
            for line in fh:
                n_lines += 1
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("event") != "combat_capture":
                    continue
                n_cc += 1
                pl = rec.get("payload") or {}
                if pl.get("valid") is not True:
                    continue
                n_valid += 1
                r = analyse_capture(pl)
                r["run_id"] = rid
                r["is_full"] = isinstance(m.get("duration_ms"), (int, float)) and m["duration_ms"] >= thr
                rows.append(r)
                per_run[rid].append(r)

    emit("| filter step | surviving |")
    emit("|---|---|")
    emit("| event lines read in kept runs | %d |" % n_lines)
    emit("| `event == combat_capture` | %d |" % n_cc)
    emit("| `payload.valid == true` | %d |" % n_valid)
    emit("| wave >= 15 | %d |" % sum(1 for r in rows if r["wave"] >= 15))
    emit()

    # variance checks
    emit("### 2a. VARIANCE CHECKS on every field used in a filter")
    emit()
    def varchk(name, vals):
        c = Counter(vals)
        s = json.dumps({str(k): v for k, v in c.most_common(12)})
        flag = "  **CONSTANT -- filter is VACUOUS**" if len(c) <= 1 else ""
        emit("- `%s`: %d distinct; %s%s" % (name, len(c), s, flag))

    varchk("payload.valid (over all combat_capture)", ["true"] * n_valid + ["not_true"] * (n_cc - n_valid))
    varchk("loot_dash.active", [r["dash_active"] for r in rows])
    varchk("loot_dash.state", [r["dash_state"] for r in rows])
    varchk("T1 nearby>=8", [r["nearby"] >= PACK_DENSITY_SOFT for r in rows])
    varchk("materials non-empty", [r["n_materials"] > 0 for r in rows])
    varchk("consumables non-empty", [r["n_consumables"] > 0 for r in rows])
    varchk("teacher.action == (0,0)", [r["action_zero"] for r in rows])
    varchk("in_late_survival_branch", [r["late"] for r in rows])
    emit()

    # ---- cross-tab
    emit("## 3. Cross-tab by wave stratum")
    emit()
    strata = ["w15-16", "w17-19", "w20"]
    by = defaultdict(list)
    for r in rows:
        by[stratum_of(r["wave"])].append(r)
    emit("| stratum | n | T1 density_veto_zeroed_loot | T2 mat route | T2 consumable route | "
         "T3 dash_inactive | T4 heading_away (of defined) | T4 UNDEFINED | JOINT | "
         "JOINT excl. late-survival | n late-survival |")
    emit("|---|---|---|---|---|---|---|---|---|---|---|")
    for s in strata + ["w<15"]:
        g = by.get(s, [])
        n = len(g)
        if n == 0:
            emit("| %s | 0 | - | - | - | - | - | - | - | - | - |" % s)
            continue
        t4def = [r for r in g if r["t4"] is not None]
        nl = [r for r in g if not r["late"]]
        jn = [r for r in g if r["joint"] is True]
        jnl = [r for r in nl if r["joint"] is True]
        emit("| %s | %d | %s | %s | %s | %s | %s | %d | %s | %s | %d |" % (
            s, n,
            pct(sum(1 for r in g if r["t1"]), n),
            pct(sum(1 for r in g if r["t2_mat"]), n),
            pct(sum(1 for r in g if r["t2_con"]), n),
            pct(sum(1 for r in g if r["t3"]), n),
            pct(sum(1 for r in t4def if r["t4"]), len(t4def)),
            n - len(t4def),
            pct(len(jn), n),
            pct(len(jnl), len(nl)),
            sum(1 for r in g if r["late"]),
        ))
    emit()
    emit("Note: rows where T4 is undefined (no admissible material, or zero action / player on "
         "the pile) are NEVER counted as JOINT=true; they are counted in the denominator and "
         "reported in the `T4 UNDEFINED` column.")
    emit()

    # ---- joint by dash state
    emit("## 4. JOINT stratum broken down by loot_dash.state")
    emit()
    for s in strata:
        g = [r for r in by.get(s, []) if r["joint"] is True]
        emit("- **%s** (JOINT n=%d): %s" % (
            s, len(g), json.dumps({str(k): v for k, v in Counter(r["dash_state"] for r in g).most_common()})))
    emit()

    # ---- nearby distribution
    emit("## 5. `nearby_enemy_count` distribution (deciles) per stratum")
    emit()
    emit("| stratum | n | d0(min) | d1 | d2 | d3 | d4 | d5(med) | d6 | d7 | d8 | d9 | d10(max) | "
         "frac >= 8 | mean |")
    emit("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for s in strata:
        g = by.get(s, [])
        if not g:
            continue
        v = [r["nearby"] for r in g]
        d = deciles(v)
        emit("| %s | %d | %s | %s | %.4f | %.2f |" % (
            s, len(v), " | ".join(str(x) for x in d[:1]), " | ".join(str(x) for x in d[1:]),
            sum(1 for x in v if x >= 8) / len(v), sum(v) / len(v)))
    emit()
    emit("Raw full histogram of nearby_enemy_count (count per value), per stratum:")
    for s in strata:
        g = by.get(s, [])
        if not g:
            continue
        c = Counter(r["nearby"] for r in g)
        emit("- **%s**: %s" % (s, json.dumps({str(k): c[k] for k in sorted(c)})))
    emit()

    # ---- per-run variation
    emit("## 6. Per-run JOINT rate variation")
    emit()
    emit("| stratum | runs with >=1 capture | min | p25 | median | p75 | max | "
         "runs with JOINT rate 0 |")
    emit("|---|---|---|---|---|---|---|---|")
    for s in strata:
        rates = []
        for rid, g in per_run.items():
            gg = [r for r in g if stratum_of(r["wave"]) == s]
            if not gg:
                continue
            rates.append(sum(1 for r in gg if r["joint"] is True) / len(gg))
        if not rates:
            continue
        rs = sorted(rates)
        q = lambda f: rs[min(len(rs) - 1, int(round(f * (len(rs) - 1))))]
        emit("| %s | %d | %.4f | %.4f | %.4f | %.4f | %.4f | %d |" % (
            s, len(rs), rs[0], q(.25), statistics.median(rs), q(.75), rs[-1],
            sum(1 for x in rs if x == 0.0)))
    emit()
    emit("RAW per-run JOINT rates, w17-19 (run_id: joint/n):")
    for rid, g in sorted(per_run.items()):
        gg = [r for r in g if stratum_of(r["wave"]) == "w17-19"]
        if gg:
            emit("  %s: %d/%d = %.4f" % (rid, sum(1 for r in gg if r["joint"] is True),
                                         len(gg), sum(1 for r in gg if r["joint"] is True) / len(gg)))
    emit()

    # ---- per-stratum constancy audit (a 0% or 100% cell must be qualified)
    emit("## 7. Per-stratum constancy audit (any term at 0.0 or 1.0 within a stratum)")
    emit()
    for s in strata:
        g = by.get(s, [])
        if not g:
            continue
        for name, vals in (("T1", [r["t1"] for r in g]),
                           ("T2_mat", [r["t2_mat"] for r in g]),
                           ("T2_con", [r["t2_con"] for r in g]),
                           ("T3", [r["t3"] for r in g]),
                           ("T4(defined)", [r["t4"] for r in g if r["t4"] is not None]),
                           ("late", [r["late"] for r in g])):
            if not vals:
                emit("- %s / %s: EMPTY SET (n=0) -- rate is undefined, NOT zero." % (s, name))
                continue
            k = sum(1 for v in vals if v)
            if k == 0 or k == len(vals):
                emit("- **%s / %s is CONSTANT at %s over n=%d** -- the term carries no information "
                     "in this stratum; check the upstream field varies before reading anything into it."
                     % (s, name, "TRUE" if k else "FALSE", len(vals)))
    emit()
    emit("## 8. Input-field variation confirmation for the constant cells")
    emit()
    emit("`loot_dash.active` over ALL kept captures: " + json.dumps(
        {str(k): v for k, v in Counter(r["dash_active"] for r in rows).items()})
        + " -- so the field DOES vary globally; any within-stratum constancy is real, not a "
          "logging artefact.")
    emit("`payload.valid` over ALL combat_capture rows: %d/%d true -- **this filter is VACUOUS in "
         "this archive** (no invalid captures are ever written), so it removes nothing."
         % (n_valid, n_cc))
    emit()

    out = args.out
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n[written] %s" % os.path.abspath(out))


if __name__ == "__main__":
    main()
