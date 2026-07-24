"""WP2 Stage F Phase 1 -- residual-probe pilot analysis (design section 3).

Analysis-only. Reads (read-only) the 6 residual-probe runs collected under
theta_max = 5 degrees, the residual-probe sidecar delta log, and the frozen
v122 exact-20 teacher baseline audit, and computes the Phase-1 analysis
deliverable that feeds the (delegated) Phase-2 GO/NO-GO verdict:

  1. Per-run infra audit summary (control fraction, faults, join coverage of the
     delta log against the student_tick / capture streams). Reuses the round-1
     ``audit_run`` primitive and the round-2 sidecar-partition idea.
  2. EFFECT ESTIMABILITY -- for each probed tick t (a non-zero teacher vector
     that received a sampled angular delta), lateral displacement
        L_k(t) = <(pos[t+k] - pos[t]), perp_hat(u_t)>
     where u_t is the teacher direction at t and perp_hat is the +90-degree
     rotation of u_t in the SAME (x,y) action-vector algebra the probe rotates
     in (see SIGN CONVENTION below), so a positive delta is expected to produce
     a positive L. Regress L_k on delta (OLS through-origin AND with intercept)
     for k in {5,10,20}, overall and per wave band, plus naive binned means of
     L_10 with CIs.
  3. OUTCOME SENSITIVITY -- probe wave/result profile vs the v122 teacher
     baseline: Fisher exact on victories, Mann-Whitney on last_wave, measured
     deltas with CIs. Descriptive only, NO causal claims.
  4. SUPPORT COVERAGE -- probed-tick fraction, zero-vector fraction, delta
     acceptance per wave band and per nearest-enemy risk stratum.

SIGN CONVENTION (verified against trainer/bridge/sidecar.py ResidualProbeService):
the probe returns rx = tx*cos(d) - ty*sin(d); ry = tx*sin(d) + ty*cos(d), i.e.
R(d) = [[cos,-sin],[sin,cos]] applied to the teacher vector. d/dd at d=0 maps
u=(ux,uy) to (-uy, ux); that is the +90-degree ("counterclockwise" in the raw
action-vector algebra) rotation. We therefore define
    perp_hat(u) = (-uy, ux) / |u|
so executed ~= u + d * perp*|u| and a positive delta rotates the executed
direction toward +perp. Positive L therefore means the player displaced to the
+perp ("counterclockwise", raw-algebra) side, and a sign-consistent effect is a
POSITIVE slope. NOTE: Brotato/Godot screen y points DOWN, so this raw-algebra
"counterclockwise" appears clockwise on screen; only internal consistency
(positive delta => positive expected L) matters and it holds by construction.

No game, no deploy, no commit. ASCII console. Exit 0 on success, 2 on IO error.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.wp2_dagger_r1_run_audit import audit_run  # noqa: E402

ROOT = _REPO_ROOT
RUNS_ROOT = Path("C:/Users/moxhe/AppData/Roaming/Brotato/brotato_agent/runs")
SIDECAR_LOG = ROOT / ".tmp" / "residual_probe_pilot.jsonl"
V122_AUDIT = ROOT / "reports" / "wp2" / "v122_exact20_safety_audit.json"
REPORT_JSON = ROOT / "reports" / "wp2" / "residual_probe_pilot_analysis.json"
REPORT_MD = ROOT / "reports" / "wp2" / "residual_probe_pilot_analysis.md"

# Probe runs. Smoke = connection 0; the 5 pilot runs share connection 1 (one
# persistent sidecar handshake, seq continuous across the 5 runs).
SMOKE_RUN = "run_1784890075_95641"           # defeat w15
PILOT_RUNS = [
    "run_1784891038_60320",  # VICTORY w20  (conn-1 handshake run_id)
    "run_1784892185_3194",   # defeat w19
    "run_1784893276_88958",  # defeat w15
    "run_1784894100_69759",  # defeat w20
    "run_1784895219_19972",  # VICTORY w20
]
ALL_RUNS = [SMOKE_RUN] + PILOT_RUNS
RUN_CONN = {SMOKE_RUN: 0, **{r: 1 for r in PILOT_RUNS}}

THETA_MAX_DEG = 5.0
HORIZONS = [5, 10, 20]
# Wave bands: (label, lo, hi) inclusive.
WAVE_BANDS = [
    ("w1-5", 1, 5),
    ("w6-10", 6, 10),
    ("w11-15", 11, 15),
    ("w16-19", 16, 19),
    ("w20", 20, 20),
]
EARLY_MID_BANDS = {"w1-5", "w6-10"}
# Naive L_10 delta bins: [-5,-3),[-3,-1),[-1,1),[1,3),[3,5]  (5 is closed at top).
DELTA_BINS = [(-5.0, -3.0), (-3.0, -1.0), (-1.0, 1.0), (1.0, 3.0), (3.0, 5.0001)]
RISK_LABELS = ["near(<=200)", "mid(200-500)", "far(>500/none)"]


# --------------------------------------------------------------------------- #
# Sidecar delta log (connection-partitioned)
# --------------------------------------------------------------------------- #
def load_sidecar(path: Path) -> dict[str, Any]:
    """Parse the residual-probe sidecar JSONL: startup, per-connection act maps
    {seq -> (delta_deg, teacher_x, teacher_y)}, handshake order, serving stats."""
    startup: dict[str, Any] | None = None
    handshakes: list[tuple[int, str]] = []
    act_maps: dict[int, dict[int, tuple[Any, float, float]]] = {}
    probed_counts: dict[int, int] = {}
    zero_counts: dict[int, int] = {}
    stats_events = 0
    errors_total = 0
    conn = -1
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        et = rec.get("event")
        if et == "startup" and startup is None:
            startup = rec
        elif et == "handshake_ok":
            conn += 1
            handshakes.append((conn, str(rec.get("run_id"))))
            act_maps.setdefault(conn, {})
            probed_counts.setdefault(conn, 0)
            zero_counts.setdefault(conn, 0)
        elif et == "act":
            if conn < 0:
                continue
            seq = int(rec["seq"])
            dd = rec.get("delta_deg")
            act_maps[conn][seq] = (dd, float(rec["teacher_x"]), float(rec["teacher_y"]))
            if dd is None:
                zero_counts[conn] += 1
            else:
                probed_counts[conn] += 1
        elif et == "stats":
            stats_events += 1
            errors_total += int(rec.get("errors", 0))
    return {
        "startup": startup,
        "handshakes": handshakes,
        "act_maps": act_maps,
        "probed_counts": probed_counts,
        "zero_counts": zero_counts,
        "serving": {"stats_events": stats_events, "errors_total": errors_total},
    }


# --------------------------------------------------------------------------- #
# Per-run trajectory: pair each student_tick with the capture it acted on
# --------------------------------------------------------------------------- #
def band_for_wave(wave: int) -> str | None:
    for label, lo, hi in WAVE_BANDS:
        if lo <= wave <= hi:
            return label
    return None


def nearest_enemy_dist(entities: dict[str, Any]) -> float | None:
    """Player-relative nearest threat distance from enemy nx/ny (fallback to
    projectiles). None when no threats present."""
    best: float | None = None
    if not isinstance(entities, dict):
        return None
    for key in ("enemies", "bosses", "projectiles"):
        for ent in entities.get(key, []) or []:
            if not isinstance(ent, dict):
                continue
            nx = ent.get("nx")
            ny = ent.get("ny")
            if not isinstance(nx, (int, float)) or not isinstance(ny, (int, float)):
                continue
            d = math.hypot(float(nx), float(ny))
            if best is None or d < best:
                best = d
    return best


def risk_stratum(dist: float | None) -> str:
    if dist is None or dist > 500.0:
        return RISK_LABELS[2]
    if dist <= 200.0:
        return RISK_LABELS[0]
    return RISK_LABELS[1]


def build_trajectory(run_id: str) -> dict[str, Any]:
    """One streaming pass: seq -> tick record {x,y,wave,valid,source,risk}, and
    total damage taken (player_damage.amount)."""
    events_path = RUNS_ROOT / run_id / "events.jsonl"
    tick: dict[int, dict[str, Any]] = {}
    last_pos: tuple[float, float, int, bool, str | None] | None = None
    total_damage = 0
    n_damage = 0
    with open(events_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            e = json.loads(line)
            et = e.get("event")
            if et == "combat_capture":
                pl = e.get("payload", {}) or {}
                p = pl.get("player", {}) or {}
                risk = risk_stratum(nearest_enemy_dist(pl.get("entities", {}) or {}))
                last_pos = (
                    float(p.get("x", 0.0)),
                    float(p.get("y", 0.0)),
                    int(pl.get("wave") or 0),
                    bool(pl.get("valid")),
                    risk,
                )
            elif et == "student_tick":
                pl = e.get("payload", {}) or {}
                seq = pl.get("seq")
                if isinstance(seq, int) and seq >= 1 and last_pos is not None:
                    tick[int(seq)] = {
                        "x": last_pos[0],
                        "y": last_pos[1],
                        "wave": last_pos[2],
                        "valid": last_pos[3],
                        "risk": last_pos[4],
                        "source": str(pl.get("source", "unknown")),
                    }
            elif et == "player_damage":
                pl = e.get("payload", {}) or {}
                amt = pl.get("amount")
                if isinstance(amt, (int, float)):
                    total_damage += int(amt)
                    n_damage += 1
    return {"tick": tick, "total_damage": total_damage, "n_damage_events": n_damage}


# --------------------------------------------------------------------------- #
# Effect samples
# --------------------------------------------------------------------------- #
def collect_effect_samples(
    run_id: str, tick: dict[int, dict[str, Any]], act_map: dict[int, tuple[Any, float, float]]
) -> list[dict[str, Any]]:
    """For each probed tick present in this run, emit one sample per horizon k
    whose window [t..t+k] is contiguous, valid, student-controlled and within a
    single wave (no shop/fallback/temporal discontinuity crossing)."""
    samples: list[dict[str, Any]] = []
    for t, rec in tick.items():
        act = act_map.get(t)
        if act is None:
            continue
        dd, tx, ty = act
        if dd is None:
            continue  # zero-vector passthrough: not a probed tick
        nu = math.hypot(tx, ty)
        if nu == 0.0:
            continue
        px = -ty / nu
        py = tx / nu  # perp_hat = (-uy, ux)/|u|  (see SIGN CONVENTION)
        base = tick[t]
        band = band_for_wave(base["wave"])
        for k in HORIZONS:
            ok = True
            for j in range(1, k + 1):
                nxt = tick.get(t + j)
                if nxt is None or not nxt["valid"] or nxt["source"] != "student":
                    ok = False
                    break
            if not ok:
                continue
            end = tick[t + k]
            if end["wave"] != base["wave"]:
                continue  # window crosses a wave boundary (temporal discontinuity)
            dx = end["x"] - base["x"]
            dy = end["y"] - base["y"]
            L = dx * px + dy * py
            samples.append(
                {
                    "run": run_id,
                    "k": k,
                    "delta": float(dd),
                    "L": L,
                    "band": band,
                    "wave": base["wave"],
                    "risk": base["risk"],
                }
            )
    return samples


# --------------------------------------------------------------------------- #
# Regressions
# --------------------------------------------------------------------------- #
def ols_through_origin(xs: list[float], ys: list[float]) -> dict[str, Any]:
    n = len(xs)
    Sxx = sum(x * x for x in xs)
    if n < 3 or Sxx == 0.0:
        return {"model": "origin", "n": n, "slope": None, "se": None, "snr": None, "r2": None}
    Sxy = sum(x * y for x, y in zip(xs, ys))
    b = Sxy / Sxx
    sse = sum((y - b * x) ** 2 for x, y in zip(xs, ys))
    syy = sum(y * y for y in ys)
    sigma2 = sse / (n - 1)
    se = math.sqrt(sigma2 / Sxx) if Sxx > 0 else None
    snr = (b / se) if se and se > 0 else None
    r2 = (1.0 - sse / syy) if syy > 0 else None
    return {
        "model": "origin",
        "n": n,
        "slope": b,
        "se": se,
        "snr": snr,
        "r2": r2,
    }


def ols_intercept(xs: list[float], ys: list[float]) -> dict[str, Any]:
    n = len(xs)
    if n < 4:
        return {"model": "intercept", "n": n, "slope": None, "intercept": None,
                "se": None, "snr": None, "r2": None}
    xbar = sum(xs) / n
    ybar = sum(ys) / n
    sxx = sum((x - xbar) ** 2 for x in xs)
    if sxx == 0.0:
        return {"model": "intercept", "n": n, "slope": None, "intercept": None,
                "se": None, "snr": None, "r2": None}
    sxy = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys))
    b = sxy / sxx
    a = ybar - b * xbar
    sse = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    sst = sum((y - ybar) ** 2 for y in ys)
    sigma2 = sse / (n - 2)
    se = math.sqrt(sigma2 / sxx)
    snr = (b / se) if se > 0 else None
    r2 = (1.0 - sse / sst) if sst > 0 else None
    return {
        "model": "intercept",
        "n": n,
        "slope": b,
        "intercept": a,
        "se": se,
        "snr": snr,
        "r2": r2,
    }


def binned_means(samples_k10: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for lo, hi in DELTA_BINS:
        vals = [s["L"] for s in samples_k10 if lo <= s["delta"] < hi]
        n = len(vals)
        if n == 0:
            out.append({"bin": f"[{lo:g},{hi if hi <= 5 else 5:g})", "n": 0,
                        "mean": None, "se": None, "ci_lo": None, "ci_hi": None})
            continue
        mean = sum(vals) / n
        if n >= 2:
            var = sum((v - mean) ** 2 for v in vals) / (n - 1)
            se = math.sqrt(var / n)
        else:
            se = None
        ci_lo = mean - 1.96 * se if se is not None else None
        ci_hi = mean + 1.96 * se if se is not None else None
        out.append({
            "bin": f"[{lo:g},{hi if hi <= 5 else 5:g})",
            "n": n, "mean": mean, "se": se, "ci_lo": ci_lo, "ci_hi": ci_hi,
        })
    return out


# --------------------------------------------------------------------------- #
# Outcome statistics (small-n, exact where possible)
# --------------------------------------------------------------------------- #
def fisher_exact_2x2(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact p for table [[a,b],[c,d]] (rows: group; cols:
    success/failure). Sums hypergeometric probabilities <= observed."""
    from math import comb

    r1, r2 = a + b, c + d
    c1, n = a + c, a + b + c + d

    def hg(x: int) -> float:
        return comb(c1, x) * comb(n - c1, r1 - x) / comb(n, r1)

    p_obs = hg(a)
    lo = max(0, r1 - (n - c1))
    hi = min(r1, c1)
    p = 0.0
    for x in range(lo, hi + 1):
        px = hg(x)
        if px <= p_obs * (1 + 1e-9):
            p += px
    return min(1.0, p)


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def mann_whitney(a: list[float], b: list[float]) -> dict[str, Any]:
    """Mann-Whitney U (a vs b) with tie-corrected normal approximation."""
    na, nb = len(a), len(b)
    combined = [(v, 0) for v in a] + [(v, 1) for v in b]
    combined.sort(key=lambda t: t[0])
    ranks = [0.0] * len(combined)
    i = 0
    tie_term = 0.0
    while i < len(combined):
        j = i
        while j + 1 < len(combined) and combined[j + 1][0] == combined[i][0]:
            j += 1
        avg = (i + 1 + j + 1) / 2.0
        for m in range(i, j + 1):
            ranks[m] = avg
        t = j - i + 1
        tie_term += t ** 3 - t
        i = j + 1
    ra = sum(r for r, (_, g) in zip(ranks, combined) if g == 0)
    ua = ra - na * (na + 1) / 2.0
    ub = na * nb - ua
    u = min(ua, ub)
    n = na + nb
    mu = na * nb / 2.0
    sigma2 = (na * nb / 12.0) * ((n + 1) - tie_term / (n * (n - 1)))
    if sigma2 <= 0:
        return {"U": u, "p_normal": None, "z": None}
    z = (u - mu + 0.5) / math.sqrt(sigma2)  # continuity-corrected toward mu
    # two-sided normal p
    p = math.erfc(abs(z) / math.sqrt(2))
    return {"U": u, "U_a": ua, "U_b": ub, "z": z, "p_normal": min(1.0, p)}


def median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return float("nan")
    if n % 2:
        return float(s[n // 2])
    return (s[n // 2 - 1] + s[n // 2]) / 2.0


def diff_ci_normal(m1: float, v1: float, n1: int, m2: float, v2: float, n2: int) -> tuple[float, float]:
    se = math.sqrt(v1 / n1 + v2 / n2) if n1 and n2 else 0.0
    d = m1 - m2
    return (d - 1.96 * se, d + 1.96 * se)


def mean_var(xs: list[float]) -> tuple[float, float]:
    n = len(xs)
    if n == 0:
        return (float("nan"), 0.0)
    m = sum(xs) / n
    v = sum((x - m) ** 2 for x in xs) / (n - 1) if n > 1 else 0.0
    return (m, v)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def fmt(v: Any, nd: int = 3) -> str:
    if v is None:
        return "NA"
    if isinstance(v, float):
        if math.isnan(v):
            return "NA"
        return f"{v:.{nd}f}"
    return str(v)


def main() -> int:
    try:
        if not SIDECAR_LOG.exists():
            print(f"error: sidecar log missing: {SIDECAR_LOG}", file=sys.stderr)
            return 2
        print("=== WP2 Stage F Phase 1: residual-probe pilot analysis ===", flush=True)
        side = load_sidecar(SIDECAR_LOG)
        act_maps = side["act_maps"]
        startup = side["startup"] or {}
        print(f"sidecar startup: backend={startup.get('backend')} "
              f"run_name={startup.get('registry_run_name')}", flush=True)
        print(f"handshakes: {side['handshakes']}", flush=True)

        # ---- 1. Infra audit + trajectory build ----
        run_reports: list[dict[str, Any]] = []
        all_samples: list[dict[str, Any]] = []
        probe_last_wave: list[float] = []
        probe_victory: list[int] = []
        probe_damage: list[float] = []
        for run_id in ALL_RUNS:
            conn = RUN_CONN[run_id]
            act_map = act_maps.get(conn, {})
            entry = audit_run(run_id, RUNS_ROOT, smoke=False)
            traj = build_trajectory(run_id)
            tick = traj["tick"]
            # join coverage: student-control ticks with a matching sidecar act.
            student_seqs = [s for s, r in tick.items() if r["source"] == "student"]
            matched = sum(1 for s in student_seqs if s in act_map)
            join_cov = matched / len(student_seqs) if student_seqs else 0.0
            # probed ticks present in this run (delta not None, seq in run range).
            probed_in_run = sum(
                1 for s in student_seqs
                if s in act_map and act_map[s][0] is not None
            )
            samples = collect_effect_samples(run_id, tick, act_map)
            all_samples.extend(samples)

            is_victory = 1 if str(entry["result"]).lower() == "victory" else 0
            probe_last_wave.append(float(entry["summary_last_wave"] or entry["wave_reached"]))
            probe_victory.append(is_victory)
            probe_damage.append(float(traj["total_damage"]))

            rr = {
                "run_id": run_id,
                "connection": conn,
                "smoke": run_id == SMOKE_RUN,
                "result": entry["result"],
                "last_wave": entry["summary_last_wave"],
                "wave_reached": entry["wave_reached"],
                "student_control_fraction": entry["student_control_fraction"],
                "student_ticks": entry["student_ticks"],
                "fallback_ticks": entry["fallback_ticks"],
                "clamp_count": entry["clamp_count"],
                "faults": {
                    "errors": entry["telemetry"]["errors"],
                    "hangs": entry["telemetry"]["hangs"],
                    "illegal_actions": entry["telemetry"]["illegal_actions"],
                    "schema_mismatches": entry["telemetry"]["capture_schema_hash_mismatches"],
                    "missing_teacher_action": entry["telemetry"]["captures_missing_teacher_action"],
                    "integrity_ok": entry["telemetry"]["integrity_ok"],
                },
                "latency_ms": entry["latency_ms"],
                "capture_count": entry["capture_count"],
                "trajectory_ticks": len(tick),
                "student_seqs": len(student_seqs),
                "join_coverage_tick_to_act": round(join_cov, 6),
                "probed_ticks_in_run": probed_in_run,
                "probed_fraction": round(probed_in_run / len(student_seqs), 6) if student_seqs else 0.0,
                "total_damage_taken": traj["total_damage"],
                "n_damage_events": traj["n_damage_events"],
                "effect_samples": len(samples),
            }
            run_reports.append(rr)
            print(f"  {run_id} conn{conn} result={entry['result']} last_wave={entry['summary_last_wave']} "
                  f"ctrl={entry['student_control_fraction']:.4f} join_cov={join_cov:.4f} "
                  f"probed={probed_in_run} samples={len(samples)} dmg={traj['total_damage']} "
                  f"integ={entry['telemetry']['integrity_ok']}", flush=True)

        # ---- 2. Effect estimability: regressions per k x band ----
        def subset(k: int, band: str | None) -> tuple[list[float], list[float]]:
            xs, ys = [], []
            for s in all_samples:
                if s["k"] != k:
                    continue
                if band is not None and s["band"] != band:
                    continue
                xs.append(s["delta"])
                ys.append(s["L"])
            return xs, ys

        effect: dict[str, Any] = {"origin": {}, "intercept": {}}
        snr_table_origin: dict[str, dict[str, Any]] = {}
        snr_table_intercept: dict[str, dict[str, Any]] = {}
        for k in HORIZONS:
            kk = f"k{k}"
            effect["origin"][kk] = {}
            effect["intercept"][kk] = {}
            snr_table_origin[kk] = {}
            snr_table_intercept[kk] = {}
            for band_label in ["overall"] + [b[0] for b in WAVE_BANDS]:
                band = None if band_label == "overall" else band_label
                xs, ys = subset(k, band)
                o = ols_through_origin(xs, ys)
                m = ols_intercept(xs, ys)
                effect["origin"][kk][band_label] = o
                effect["intercept"][kk][band_label] = m
                snr_table_origin[kk][band_label] = {"n": o["n"], "slope": o["slope"], "snr": o["snr"]}
                snr_table_intercept[kk][band_label] = {"n": m["n"], "slope": m["slope"], "snr": m["snr"]}

        # Binned means of L_10 (overall).
        k10 = [s for s in all_samples if s["k"] == 10]
        binned = binned_means(k10)

        # Sign consistency across k<=10 in early+mid bands (both models).
        def sign_consistent(model_key: str) -> dict[str, Any]:
            checks = []
            all_pos = True
            for k in [5, 10]:
                kk = f"k{k}"
                for band in EARLY_MID_BANDS:
                    slope = effect[model_key][kk][band]["slope"]
                    n = effect[model_key][kk][band]["n"]
                    pos = (slope is not None and slope > 0)
                    checks.append({"k": k, "band": band, "slope": slope, "n": n, "positive": pos})
                    if slope is None or slope <= 0:
                        all_pos = False
            return {"all_positive_early_mid_k<=10": all_pos, "checks": checks}

        sign_origin = sign_consistent("origin")
        sign_intercept = sign_consistent("intercept")

        # ---- 3. Outcome sensitivity vs v122 baseline ----
        v122 = json.loads(V122_AUDIT.read_text(encoding="utf-8"))
        base_runs = v122["runs"]
        base_last_wave = [float(r["last_wave"]) for r in base_runs]
        base_victory = [1 if str(r["result"]).lower() == "victory" else 0 for r in base_runs]
        base_damage = [float(sum(int(d.get("amount", 0)) for d in r.get("damage_events", [])))
                       for r in base_runs]

        pv = sum(probe_victory)
        pn = len(probe_victory)
        bv = sum(base_victory)
        bn = len(base_victory)
        fisher_p = fisher_exact_2x2(pv, pn - pv, bv, bn - bv)
        pv_ci = wilson_ci(pv, pn)
        bv_ci = wilson_ci(bv, bn)
        mw_wave = mann_whitney(probe_last_wave, base_last_wave)
        pm, pvar = mean_var(probe_last_wave)
        bm, bvar = mean_var(base_last_wave)
        wave_diff_ci = diff_ci_normal(pm, pvar, pn, bm, bvar, bn)
        mw_dmg = mann_whitney(probe_damage, base_damage)
        pdm, pdvar = mean_var(probe_damage)
        bdm, bdvar = mean_var(base_damage)

        outcome = {
            "probe": {
                "n": pn, "victories": pv, "victory_rate": pv / pn, "victory_wilson_ci": pv_ci,
                "last_waves": probe_last_wave, "last_wave_median": median(probe_last_wave),
                "last_wave_mean": pm,
                "total_damage": probe_damage, "damage_median": median(probe_damage), "damage_mean": pdm,
            },
            "baseline_v122": {
                "n": bn, "victories": bv, "victory_rate": bv / bn, "victory_wilson_ci": bv_ci,
                "last_waves": base_last_wave, "last_wave_median": median(base_last_wave),
                "last_wave_mean": bm,
                "total_damage": base_damage, "damage_median": median(base_damage), "damage_mean": bdm,
                "damage_note": "v122 damage = sum of the safety audit's tracked damage_events "
                               "amounts; probe damage = sum of raw player_damage.amount. Inclusion "
                               "semantics differ -- treat damage comparison as caveated/descriptive.",
            },
            "victory_fisher_exact_p_two_sided": fisher_p,
            "victory_rate_diff_probe_minus_base": pv / pn - bv / bn,
            "last_wave_mann_whitney": mw_wave,
            "last_wave_diff_probe_minus_base": pm - bm,
            "last_wave_diff_ci95": wave_diff_ci,
            "damage_mann_whitney": mw_dmg,
            "damage_diff_probe_minus_base_mean": pdm - bdm,
        }

        # ---- 4. Support coverage ----
        # Probed vs zero-vector fractions (from sidecar, per connection + total).
        probed_total = sum(side["probed_counts"].values())
        zero_total = sum(side["zero_counts"].values())
        acts_total = probed_total + zero_total
        # Delta acceptance per wave band and risk stratum (probed effect samples
        # are per k; use k=5 sample set as the probed-tick census proxy at the
        # finest horizon, plus a raw per-tick census from trajectories).
        # Per-tick census across runs joined to deltas:
        band_census: dict[str, dict[str, Any]] = {b[0]: {"probed": 0, "deltas": []} for b in WAVE_BANDS}
        risk_census: dict[str, dict[str, Any]] = {r: {"probed": 0, "deltas": []} for r in RISK_LABELS}
        for run_id in ALL_RUNS:
            conn = RUN_CONN[run_id]
            act_map = act_maps.get(conn, {})
            traj = build_trajectory(run_id)
            for s, rec in traj["tick"].items():
                if rec["source"] != "student":
                    continue
                act = act_map.get(s)
                if act is None or act[0] is None:
                    continue
                band = band_for_wave(rec["wave"])
                if band and band in band_census:
                    band_census[band]["probed"] += 1
                    band_census[band]["deltas"].append(float(act[0]))
                risk = rec["risk"]
                if risk in risk_census:
                    risk_census[risk]["probed"] += 1
                    risk_census[risk]["deltas"].append(float(act[0]))

        def summarize_deltas(d: dict[str, Any]) -> dict[str, Any]:
            out = {}
            for key, val in d.items():
                ds = val["deltas"]
                n = len(ds)
                mean_abs = sum(abs(x) for x in ds) / n if n else None
                out[key] = {
                    "probed_ticks": val["probed"],
                    "mean_abs_delta": mean_abs,
                    "min_delta": min(ds) if ds else None,
                    "max_delta": max(ds) if ds else None,
                }
            return out

        coverage = {
            "acts_total": acts_total,
            "probed_ticks": probed_total,
            "zero_vector_ticks": zero_total,
            "probed_fraction": probed_total / acts_total if acts_total else 0.0,
            "zero_vector_fraction": zero_total / acts_total if acts_total else 0.0,
            "per_wave_band": summarize_deltas(band_census),
            "per_risk_stratum": summarize_deltas(risk_census),
            "risk_stratum_defn": "nearest-threat distance (px) from enemy/boss/projectile nx,ny: "
                                 "near<=200, mid 200-500, far>500 or no threat.",
        }

        go_criteria = (
            "GO to Phase 2 requires: sign-consistent displacement effect "
            "detectable at k<=10 ticks with |effect| SNR >= 3 in at least the "
            "early+mid bands, and no behavioral degradation vs the teacher "
            "baseline beyond noise. (design section 3; verdict DELEGATED to primary.)"
        )

        report = {
            "stage": "F",
            "phase": 1,
            "theta_max_deg": THETA_MAX_DEG,
            "sign_convention": (
                "perp_hat(u)=(-uy,ux)/|u|, the +90deg rotation in the raw action-vector "
                "algebra the probe rotates in (R=[[cos,-sin],[sin,cos]], dR/dd@0 maps u->(-uy,ux)); "
                "positive delta => positive expected L => sign-consistent effect is a POSITIVE slope. "
                "Godot screen y is down so this is visually clockwise; only internal consistency matters."
            ),
            "sidecar": {
                "startup": startup,
                "handshakes": side["handshakes"],
                "serving": side["serving"],
                "probed_counts": side["probed_counts"],
                "zero_counts": side["zero_counts"],
            },
            "runs": run_reports,
            "effect_estimability": {
                "horizons": HORIZONS,
                "snr_table_origin": snr_table_origin,
                "snr_table_intercept": snr_table_intercept,
                "regressions": effect,
                "binned_means_L10": binned,
                "sign_consistency_origin": sign_origin,
                "sign_consistency_intercept": sign_intercept,
                "total_effect_samples": len(all_samples),
            },
            "outcome_sensitivity": outcome,
            "support_coverage": coverage,
            "go_criteria_verbatim": go_criteria,
            "verdict": "DEFERRED_TO_PRIMARY (no verdict issued by this analysis)",
        }

        REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
        REPORT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
        REPORT_MD.write_text(render_md(report), encoding="utf-8")

        print_console(report)
        print(f"\nreport json: {REPORT_JSON}", flush=True)
        print(f"report md:   {REPORT_MD}", flush=True)
        return 0
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr, flush=True)
        return 2


# --------------------------------------------------------------------------- #
# Console + markdown rendering
# --------------------------------------------------------------------------- #
def print_console(report: dict[str, Any]) -> None:
    ee = report["effect_estimability"]
    print("\n--- SNR TABLE (k x band): through-origin slope[px/deg] / SNR (n) ---", flush=True)
    bands = ["overall"] + [b[0] for b in WAVE_BANDS]
    header = "k    | " + " | ".join(f"{b:>12}" for b in bands)
    print(header, flush=True)
    for k in HORIZONS:
        kk = f"k{k}"
        cells = []
        for b in bands:
            e = ee["regressions"]["origin"][kk][b]
            cells.append(f"{fmt(e['slope'],3):>5}/{fmt(e['snr'],2):>4}({e['n']})")
        print(f"k={k:<3}| " + " | ".join(f"{c:>12}" for c in cells), flush=True)
    print("\n--- SNR TABLE (k x band): with-intercept slope[px/deg] / SNR (n) ---", flush=True)
    print(header, flush=True)
    for k in HORIZONS:
        kk = f"k{k}"
        cells = []
        for b in bands:
            e = ee["regressions"]["intercept"][kk][b]
            cells.append(f"{fmt(e['slope'],3):>5}/{fmt(e['snr'],2):>4}({e['n']})")
        print(f"k={k:<3}| " + " | ".join(f"{c:>12}" for c in cells), flush=True)

    so = ee["sign_consistency_origin"]["all_positive_early_mid_k<=10"]
    si = ee["sign_consistency_intercept"]["all_positive_early_mid_k<=10"]
    print(f"\nsign-consistent (positive slope) k<=10 early+mid bands: "
          f"through-origin={so}  with-intercept={si}", flush=True)

    print("\n--- Binned means of L_10 (px) by delta bin (overall, 95% CI) ---", flush=True)
    for b in ee["binned_means_L10"]:
        print(f"  delta {b['bin']:>10}: n={b['n']:>6}  mean_L10={fmt(b['mean'],3):>8}  "
              f"CI=[{fmt(b['ci_lo'],3)},{fmt(b['ci_hi'],3)}]", flush=True)

    oc = report["outcome_sensitivity"]
    p = oc["probe"]
    bl = oc["baseline_v122"]
    print("\n--- Outcome sensitivity: probe vs v122 baseline (NO causal claims) ---", flush=True)
    print(f"  victories: probe {p['victories']}/{p['n']} (rate {p['victory_rate']:.3f}, "
          f"Wilson CI [{p['victory_wilson_ci'][0]:.3f},{p['victory_wilson_ci'][1]:.3f}]) "
          f"vs base {bl['victories']}/{bl['n']} (rate {bl['victory_rate']:.3f}, "
          f"CI [{bl['victory_wilson_ci'][0]:.3f},{bl['victory_wilson_ci'][1]:.3f}])", flush=True)
    print(f"  Fisher exact two-sided p = {oc['victory_fisher_exact_p_two_sided']:.4f}  "
          f"(victory-rate diff {oc['victory_rate_diff_probe_minus_base']:+.3f})", flush=True)
    print(f"  last_wave: probe median {p['last_wave_median']:.1f} mean {p['last_wave_mean']:.2f} "
          f"vs base median {bl['last_wave_median']:.1f} mean {bl['last_wave_mean']:.2f}", flush=True)
    mw = oc["last_wave_mann_whitney"]
    print(f"  last_wave Mann-Whitney U={mw['U']:.1f} p={fmt(mw['p_normal'],4)}  "
          f"diff {oc['last_wave_diff_probe_minus_base']:+.2f} "
          f"CI95 [{oc['last_wave_diff_ci95'][0]:.2f},{oc['last_wave_diff_ci95'][1]:.2f}]", flush=True)
    mwd = oc["damage_mann_whitney"]
    print(f"  damage(caveated): probe median {p['damage_median']:.1f} vs base "
          f"{bl['damage_median']:.1f}  MW U={mwd['U']:.1f} p={fmt(mwd['p_normal'],4)}", flush=True)

    cov = report["support_coverage"]
    print("\n--- Support coverage ---", flush=True)
    print(f"  probed fraction {cov['probed_fraction']:.4f}  zero-vector fraction "
          f"{cov['zero_vector_fraction']:.4f}  (acts total {cov['acts_total']})", flush=True)
    print("  per wave band: band -> probed_ticks, mean|delta|", flush=True)
    for band, v in cov["per_wave_band"].items():
        print(f"    {band:>7}: probed={v['probed_ticks']:>7}  mean|d|={fmt(v['mean_abs_delta'],3)}", flush=True)
    print("  per risk stratum: stratum -> probed_ticks, mean|delta|", flush=True)
    for st, v in cov["per_risk_stratum"].items():
        print(f"    {st:>16}: probed={v['probed_ticks']:>7}  mean|d|={fmt(v['mean_abs_delta'],3)}", flush=True)

    print("\n--- GO criteria (verbatim, verdict DEFERRED) ---", flush=True)
    print("  " + report["go_criteria_verbatim"], flush=True)


def render_md(report: dict[str, Any]) -> str:
    L: list[str] = []
    ee = report["effect_estimability"]
    oc = report["outcome_sensitivity"]
    cov = report["support_coverage"]
    bands = ["overall"] + [b[0] for b in WAVE_BANDS]
    L.append("# WP2 Stage F Phase 1 -- residual-probe pilot analysis")
    L.append("")
    L.append(f"- theta_max: {report['theta_max_deg']} deg | probe seed run_name: "
             f"`{report['sidecar']['startup'].get('registry_run_name')}`")
    L.append(f"- **Verdict: {report['verdict']}**")
    L.append("")
    L.append("## Sign convention (verified from ResidualProbeService)")
    L.append("")
    L.append(report["sign_convention"])
    L.append("")
    L.append("## 1. Per-run infra audit")
    L.append("")
    L.append("| run | conn | smoke | result | last_wave | ctrl_frac | join_cov | probed | "
             "eff_samples | errors | hangs | illegal | integrity |")
    L.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in report["runs"]:
        f = r["faults"]
        L.append(f"| {r['run_id']} | {r['connection']} | {r['smoke']} | {r['result']} | "
                 f"{r['last_wave']} | {r['student_control_fraction']:.4f} | "
                 f"{r['join_coverage_tick_to_act']:.4f} | {r['probed_ticks_in_run']} | "
                 f"{r['effect_samples']} | {f['errors']} | {f['hangs']} | {f['illegal_actions']} | "
                 f"{f['integrity_ok']} |")
    L.append("")
    L.append("## 2. Effect estimability")
    L.append("")
    L.append(f"Total effect samples: {ee['total_effect_samples']}")
    L.append("")
    for model_key, title in [("origin", "through-origin"), ("intercept", "with-intercept")]:
        L.append(f"### SNR table ({title}): slope [px/deg] / SNR / n")
        L.append("")
        L.append("| k | " + " | ".join(bands) + " |")
        L.append("| " + " | ".join(["---"] * (len(bands) + 1)) + " |")
        for k in HORIZONS:
            kk = f"k{k}"
            cells = []
            for b in bands:
                e = ee["regressions"][model_key][kk][b]
                cells.append(f"{fmt(e['slope'],3)}/{fmt(e['snr'],2)}/{e['n']}")
            L.append(f"| {k} | " + " | ".join(cells) + " |")
        L.append("")
    L.append(f"Sign-consistent (positive slope) at k<=10 in early+mid bands: "
             f"through-origin=**{ee['sign_consistency_origin']['all_positive_early_mid_k<=10']}**, "
             f"with-intercept=**{ee['sign_consistency_intercept']['all_positive_early_mid_k<=10']}**")
    L.append("")
    L.append("### Naive binned means of L_10 (px) by delta bin (overall)")
    L.append("")
    L.append("| delta bin | n | mean L_10 | 95% CI |")
    L.append("| --- | --- | --- | --- |")
    for b in ee["binned_means_L10"]:
        L.append(f"| {b['bin']} | {b['n']} | {fmt(b['mean'],3)} | "
                 f"[{fmt(b['ci_lo'],3)}, {fmt(b['ci_hi'],3)}] |")
    L.append("")
    L.append("## 3. Outcome sensitivity vs v122 baseline (NO causal claims)")
    L.append("")
    p = oc["probe"]
    bl = oc["baseline_v122"]
    L.append(f"- victories: probe **{p['victories']}/{p['n']}** (rate {p['victory_rate']:.3f}, "
             f"Wilson CI [{p['victory_wilson_ci'][0]:.3f}, {p['victory_wilson_ci'][1]:.3f}]) vs "
             f"baseline **{bl['victories']}/{bl['n']}** (rate {bl['victory_rate']:.3f}, "
             f"CI [{bl['victory_wilson_ci'][0]:.3f}, {bl['victory_wilson_ci'][1]:.3f}])")
    L.append(f"- Fisher exact two-sided p = **{oc['victory_fisher_exact_p_two_sided']:.4f}**; "
             f"victory-rate diff {oc['victory_rate_diff_probe_minus_base']:+.3f}")
    mw = oc["last_wave_mann_whitney"]
    L.append(f"- last_wave: probe median {p['last_wave_median']:.1f} (mean {p['last_wave_mean']:.2f}) vs "
             f"baseline median {bl['last_wave_median']:.1f} (mean {bl['last_wave_mean']:.2f}); "
             f"Mann-Whitney U={mw['U']:.1f} p={fmt(mw['p_normal'],4)}; diff "
             f"{oc['last_wave_diff_probe_minus_base']:+.2f} CI95 "
             f"[{oc['last_wave_diff_ci95'][0]:.2f}, {oc['last_wave_diff_ci95'][1]:.2f}]")
    mwd = oc["damage_mann_whitney"]
    L.append(f"- damage (CAVEATED, semantics differ): probe median {p['damage_median']:.1f} vs "
             f"baseline median {bl['damage_median']:.1f}; MW U={mwd['U']:.1f} p={fmt(mwd['p_normal'],4)}")
    L.append(f"  - {bl['damage_note']}")
    L.append(f"- probe last_waves: {p['last_waves']}")
    L.append("")
    L.append("## 4. Support coverage")
    L.append("")
    L.append(f"- probed fraction {cov['probed_fraction']:.4f}; zero-vector fraction "
             f"{cov['zero_vector_fraction']:.4f} (acts total {cov['acts_total']})")
    L.append("")
    L.append("| wave band | probed ticks | mean\\|delta\\| | min delta | max delta |")
    L.append("| --- | --- | --- | --- | --- |")
    for band, v in cov["per_wave_band"].items():
        L.append(f"| {band} | {v['probed_ticks']} | {fmt(v['mean_abs_delta'],3)} | "
                 f"{fmt(v['min_delta'],3)} | {fmt(v['max_delta'],3)} |")
    L.append("")
    L.append(f"Risk stratum ({cov['risk_stratum_defn']}):")
    L.append("")
    L.append("| risk stratum | probed ticks | mean\\|delta\\| |")
    L.append("| --- | --- | --- |")
    for st, v in cov["per_risk_stratum"].items():
        L.append(f"| {st} | {v['probed_ticks']} | {fmt(v['mean_abs_delta'],3)} |")
    L.append("")
    L.append("## GO criteria (verbatim; verdict deferred to primary)")
    L.append("")
    L.append("> " + report["go_criteria_verbatim"])
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    raise SystemExit(main())
