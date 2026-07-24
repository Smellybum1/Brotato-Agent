#!/usr/bin/env python3
"""WP2 Stage F Phase 2 -- checkpoint comparison (design 1 / phase2 design 6).

At ~300k cumulative residual ticks the checkpoint compares the LEARNED-residual
arm (pi3/pi4 collection runs, explore-sigma 0.3) against the MATCHED RANDOM
CONTROL (the 6 Phase-1 uniform-probe runs, matched theta bound) on damage taken
and wave outcomes, STRATIFIED by wave band and risk stratum. The critic
diagnostic (reports/wp2/residual_null_diagnostics.md) said any real signal lives
in wave 20 and risk>=0.5, so an aggregate-only compare would dilute it; wave 20
is isolated as its own band.

Honest labels (phase2 design 14.3): BOTH arms are residual-teacher-base control.
The learned arm is 'residual-teacher-base control (14.3)'; the control arm is the
'Phase-1 uniform random probe (matched theta bound)'. Neither is an independent
student.

Small-n honesty: ~6 runs per arm. We report percentile bootstrap CIs (seeded)
for arm medians/means and for the learned-minus-control difference. NO
significance tests.

Damage accounting -- TWO views:
  * PRIMARY (outcome metric): the FULL combat_capture stream, unfiltered. Every
    hp drop between consecutive captures is counted (heal-clamped to >=0),
    normalized by max_hp at the pre-drop capture, and attributed to that
    capture's wave band / risk stratum; the tick denominator is ALL captures.
    This is the correct outcome measure -- the RL usability filter below drops
    damage steps that fall in recovery windows / discontinuities, which
    systematically undercounts damage in recovery-heavy runs (a bias correlated
    with infrastructure, not policy). Cross-checked per run against the sum of
    the mod's player_damage events (mismatch flagged if |delta| > 5 hp).
  * SECONDARY ('rl_usable_view', diagnostic only): the reward_v2 / replay
    training view -- per usable student step a->b, max(0, hp_a - hp_b)/max_hp_a,
    with usability + segmentation (valid student tick, outside the 2 s recovery
    window, contiguous seq+1 with control_dt in (0, dt_max]) reusing
    trainer.rl.replay._mark_usable and the assemble_transitions conventions.

The checkpoint_summary and the markdown use the PRIMARY full-stream numbers.

Risk per capture reuses the exact compute_state_risk math: max masked
contact_risk (entity feature index 11) over the threat groups, via
trainer.observation.encoder_v1.encode_capture.

Telemetry loading reuses the existing conventions:
  * combat_capture / student_tick streaming + the student_tick <-> most-recent
    combat_capture seq-join of trainer.rl.replay.build_run_telemetry, in one
    combined pass so risk is computed once per capture;
  * final wave / victory: summary.json result / last_wave, the
    scripts/wp2_telemetry_stats.py audit convention.

Read-only on run dirs. No game, no deploy, no network. Torch-free.

Difference sign convention (learned - control):
  * damage rates: NEGATIVE => learned takes LESS damage (better).
  * final wave / victory rate: POSITIVE => learned reaches further / wins more.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from trainer.imitation.bc_training import (  # noqa: E402
    CONTACT_RISK_INDEX,
    RISK_BIN_LABELS,
    RISK_GROUPS,
    WAVE_BAND_LABELS,
    risk_bin_indices,
    wave_band_indices,
)
from trainer.observation import encoder_v1  # noqa: E402
from trainer.rl.replay import (  # noqa: E402
    DEFAULT_DT_MAX_MS,
    DEFAULT_RECOVERY_TICKS,
    STUDENT_SOURCE,
    RewardConfig,
    TickTelemetry,
    _mark_usable,
)

DEFAULT_SCHEMA = REPO_ROOT / "configs" / "wp2" / "observation_v1.yaml"
DEFAULT_REWARD_YAML = REPO_ROOT / "configs" / "wp2" / "reward_v1.yaml"
RISK_HALF_LABELS = ("0.50-0.75", "0.75-inf")   # the risk>=0.5 strata (edges 0.25,0.5,0.75)
WAVE20_LABEL = "20"
CI_PCTS = (2.5, 97.5)


# ---------------------------------------------------------------------------
# Run telemetry loading (single streaming pass; reuses the replay seq-join +
# encoder_v1 risk math)
# ---------------------------------------------------------------------------
def default_runs_dir() -> Path:
    appdata = os.environ.get("APPDATA", r"C:\Users\moxhe\AppData\Roaming")
    return Path(appdata) / "Brotato" / "brotato_agent" / "runs"


def capture_risk(cap: dict, schema: dict) -> float:
    """Max masked contact_risk over the threat groups for one capture payload.

    Byte-for-byte the compute_state_risk math from
    scripts/wp2_residual_null_diagnostics.py: entities pass through the encoder
    unnormalized, so entity feature index 11 (contact_risk) is the raw risk; the
    max is taken over present rows in the enemies/bosses/projectiles groups and
    starts at 0.0 (an empty threat set => 0 risk).
    """
    try:
        obs = encoder_v1.encode_capture(dict(cap), schema)
    except Exception:
        return float("nan")
    r = 0.0
    for grp in RISK_GROUPS:
        ent = np.asarray(obs.entities.get(grp, []), dtype=np.float32)
        msk = np.asarray(obs.masks.get(grp, []), dtype=np.float32) > 0
        if ent.shape[0] and msk.any():
            r = max(r, float(ent[msk, CONTACT_RISK_INDEX].max()))
    return r


def _load_summary(run_dir: Path) -> dict:
    p = run_dir / "summary.json"
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


class RunStream:
    """Everything one streaming pass over a run yields.

    ``captures`` is the FULL unfiltered combat_capture stream (hp, max_hp, wave,
    risk) -- the primary damage-accounting source. ``ticks`` / ``tick_risks`` are
    the student-tick view used only for the secondary rl_usable diagnostic.
    ``player_damage_sum`` / ``player_damage_events`` are the mod's ground-truth
    damage events, used to cross-check the capture hp-drop sum.
    """

    __slots__ = ("captures", "ticks", "tick_risks", "player_damage_sum",
                 "player_damage_events", "terminal")

    def __init__(self, captures, ticks, tick_risks, pdmg_sum, pdmg_events, terminal):
        self.captures = captures                    # list[(hp, max_hp, wave, risk)]
        self.ticks = ticks                          # list[TickTelemetry]
        self.tick_risks = tick_risks                # np.ndarray parallel to ticks
        self.player_damage_sum = pdmg_sum
        self.player_damage_events = pdmg_events
        self.terminal = terminal


def load_run(run_id: str, runs_dir: Path, schema: dict) -> RunStream:
    """One streaming pass: full capture stream + student-tick view + player_damage.

    The full ``captures`` stream applies NO usability filtering (every
    combat_capture with a numeric player hp is a tick) -- this is the primary
    outcome-metric source, since the replay usability filter (valid student tick,
    2s recovery exclusion, contiguous seq) systematically undercounts damage in
    recovery-heavy runs. The student-tick seq-join still reproduces
    trainer.rl.replay.build_run_telemetry for the rl_usable diagnostic; risk is
    computed once per capture and reused.
    """
    events_path = runs_dir / run_id / "events.jsonl"
    captures: list[tuple[float, float, int, float]] = []
    ticks: list[TickTelemetry] = []
    tick_risks: list[float] = []
    pdmg_sum = 0.0
    pdmg_events = 0
    terminal: str | None = None
    last_cap: dict | None = None
    last_risk: float = float("nan")
    with events_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            e = json.loads(line)
            et = e.get("event")
            if et == "combat_capture":
                last_cap = e.get("payload", {}) or {}
                player = last_cap.get("player", {}) or {}
                last_risk = capture_risk(last_cap, schema)
                hp = player.get("hp")
                if hp is not None:
                    captures.append((
                        float(hp),
                        float(player.get("max_hp", 0.0)) or 1.0,
                        int(last_cap.get("wave") or 0),
                        last_risk,
                    ))
            elif et == "student_tick":
                if last_cap is None:
                    continue
                pl = e.get("payload", {}) or {}
                seq = pl.get("seq")
                source = str(pl.get("source", "unknown"))
                player = last_cap.get("player", {}) or {}
                ticks.append(
                    TickTelemetry(
                        seq=int(seq) if isinstance(seq, int) else -1,
                        source=source,
                        valid=bool(last_cap.get("valid", False)),
                        wave=int(last_cap.get("wave") or 0),
                        hp=float(player.get("hp", 0.0)),
                        max_hp=float(player.get("max_hp", 0.0)) or 1.0,
                        control_dt_ms=float(last_cap.get("control_dt_ms", 0.0)),
                        delta_deg=None,
                    )
                )
                tick_risks.append(last_risk)
            elif et == "player_damage":
                amt = (e.get("payload", {}) or {}).get("amount", 0) or 0
                pdmg_sum += float(amt)
                pdmg_events += 1
            elif et == "run_end":
                terminal = str((e.get("payload", {}) or {}).get("result")) or None
    return RunStream(
        captures, ticks, np.asarray(tick_risks, dtype=np.float64),
        pdmg_sum, pdmg_events, terminal,
    )


def full_stream_steps(captures: list[tuple[float, float, int, float]]) -> dict:
    """Damage from the FULL capture stream: every hp drop between consecutive
    combat_capture events (heal-clamped to >=0), normalized by max_hp at the
    pre-drop capture and attributed to that capture's wave / risk.

    Every capture is a tick (the last one carries a 0 drop -- no successor), so
    the returned arrays are per-capture and the tick denominator is unfiltered.
    """
    n = len(captures)
    waves = np.empty(n, dtype=np.int64)
    risks = np.empty(n, dtype=np.float64)
    norm = np.zeros(n, dtype=np.float64)
    raw = np.zeros(n, dtype=np.float64)
    for i in range(n):
        hp_i, mh_i, w_i, r_i = captures[i]
        waves[i] = w_i
        risks[i] = r_i
        if i + 1 < n:
            drop = max(0.0, hp_i - captures[i + 1][0])
            raw[i] = drop
            norm[i] = drop / mh_i
    return {"wave": waves, "risk": risks, "norm_damage": norm, "raw_damage": raw}


# ---------------------------------------------------------------------------
# Per-run damage-step extraction (reward_v2 normalization) + stratification
# ---------------------------------------------------------------------------
def damage_steps(
    ticks: list[TickTelemetry],
    risks: np.ndarray,
    reward: RewardConfig,
    *,
    recovery_ticks: int = DEFAULT_RECOVERY_TICKS,
    dt_max_ms: float = DEFAULT_DT_MAX_MS,
):
    """Per usable student control step a->b: normalized + raw damage, attributed
    to state a's wave / risk. Segmentation mirrors assemble_transitions.

    Returns dict of parallel np arrays: wave, risk, norm_damage, raw_damage.
    """
    usable, _ = _mark_usable(ticks, recovery_ticks)
    # Contiguous usable segments (seq+1 and control_dt in (0, dt_max]).
    segments: list[list[int]] = []
    current: list[int] = []
    prev_raw: int | None = None
    for i, t in enumerate(ticks):
        if not usable[i]:
            continue
        contiguous = (
            prev_raw is not None
            and t.seq == ticks[prev_raw].seq + 1
            and 0.0 < t.control_dt_ms <= dt_max_ms
        )
        if not contiguous and current:
            segments.append(current)
            current = []
        current.append(i)
        prev_raw = i
    if current:
        segments.append(current)

    waves: list[int] = []
    rs: list[float] = []
    norm: list[float] = []
    raw: list[float] = []
    for seg in segments:
        for a, b in zip(seg[:-1], seg[1:]):
            ta, tb = ticks[a], ticks[b]
            dmg = max(0.0, ta.hp - tb.hp)
            waves.append(ta.wave)
            rs.append(float(risks[a]) if a < risks.shape[0] else float("nan"))
            norm.append(reward.w_damage * (dmg / ta.max_hp))
            raw.append(dmg)
    return {
        "wave": np.asarray(waves, dtype=np.int64),
        "risk": np.asarray(rs, dtype=np.float64),
        "norm_damage": np.asarray(norm, dtype=np.float64),
        "raw_damage": np.asarray(raw, dtype=np.float64),
    }


def _rate(num: np.ndarray, mask: np.ndarray) -> float:
    """Normalized-damage-per-step rate over a boolean subset (nan if empty)."""
    n = int(mask.sum())
    if n == 0:
        return float("nan")
    return float(num[mask].sum() / n)


def view_rates(steps: dict) -> dict:
    """Stratified normalized-damage rates for one damage view.

    ``steps`` provides per-tick arrays wave/risk/norm_damage/raw_damage. Works
    for BOTH the full capture stream (tick = capture) and the rl_usable view
    (tick = usable student step). rate = sum(norm in stratum)/count(ticks in
    stratum); NaN-risk ticks are excluded from risk strata only.
    """
    wave = steps["wave"]
    risk = steps["risk"]
    norm = steps["norm_damage"]
    raw = steps["raw_damage"]
    n = int(norm.shape[0])

    wave_idx = wave_band_indices(wave) if n else np.zeros(0, dtype=np.int64)
    risk_finite = np.isfinite(risk)
    risk_idx = np.full(n, -1, dtype=np.int64)
    if risk_finite.any():
        risk_idx[risk_finite] = risk_bin_indices(risk[risk_finite])

    all_mask = np.ones(n, dtype=bool)
    by_wave = {lab: _rate(norm, wave_idx == i) for i, lab in enumerate(WAVE_BAND_LABELS)}
    by_risk = {lab: _rate(norm, risk_idx == i) for i, lab in enumerate(RISK_BIN_LABELS)}
    ge_half_mask = np.isin(
        risk_idx, [RISK_BIN_LABELS.index(lab) for lab in RISK_HALF_LABELS]
    )
    return {
        "n_ticks": n,
        "norm_damage_total": float(norm.sum()),
        "raw_damage_total": float(raw.sum()),
        "damage_rate_overall": _rate(norm, all_mask),
        "damage_per_1k_overall": (_rate(norm, all_mask) * 1000.0),
        "damage_rate_by_wave_band": by_wave,
        "damage_rate_by_risk_stratum": by_risk,
        "damage_rate_wave20": by_wave.get(WAVE20_LABEL, float("nan")),
        "damage_rate_risk_ge_0p5": _rate(norm, ge_half_mask),
        "n_ticks_wave20": int((wave_idx == WAVE_BAND_LABELS.index(WAVE20_LABEL)).sum()) if n else 0,
        "n_ticks_risk_ge_0p5": int(ge_half_mask.sum()),
        "n_ticks_risk_nan": int((~risk_finite).sum()),
    }


def run_metrics(
    run_id: str,
    full_steps: dict,
    rl_steps: dict,
    summary: dict,
    terminal: str | None,
    player_damage_sum: float = 0.0,
    player_damage_events: int = 0,
) -> dict:
    """Per-run metrics. PRIMARY fields are the full-capture-stream view; the
    replay-filtered view is kept under ``rl_usable_view``. A cross-check against
    the mod's player_damage events flags any hp-drop-sum mismatch > 5 hp.
    """
    fv = view_rates(full_steps)
    rv = view_rates(rl_steps)

    final_wave = summary.get("last_wave")
    if final_wave is None:
        final_wave = summary.get("waves_completed")
    result = summary.get("result")
    if result is None:
        result = terminal
    victory = 1.0 if (result == "victory") else 0.0

    capture_drop_sum = fv["raw_damage_total"]
    delta = capture_drop_sum - float(player_damage_sum)
    mismatch = abs(delta) > 5.0

    return {
        "run_id": run_id,
        "result": result,
        "final_wave": (int(final_wave) if final_wave is not None else None),
        "victory": victory,
        # --- PRIMARY (full capture stream) ---
        "n_capture_ticks": fv["n_ticks"],
        "norm_damage_total": fv["norm_damage_total"],
        "raw_damage_total": capture_drop_sum,
        "damage_rate_overall": fv["damage_rate_overall"],
        "damage_per_1k_overall": fv["damage_per_1k_overall"],
        "damage_rate_by_wave_band": fv["damage_rate_by_wave_band"],
        "damage_rate_by_risk_stratum": fv["damage_rate_by_risk_stratum"],
        "damage_rate_wave20": fv["damage_rate_wave20"],
        "damage_rate_risk_ge_0p5": fv["damage_rate_risk_ge_0p5"],
        "n_ticks_wave20": fv["n_ticks_wave20"],
        "n_ticks_risk_ge_0p5": fv["n_ticks_risk_ge_0p5"],
        "n_ticks_risk_nan": fv["n_ticks_risk_nan"],
        # --- cross-check vs mod ground truth ---
        "capture_drop_sum": capture_drop_sum,
        "player_damage_sum": float(player_damage_sum),
        "player_damage_events": int(player_damage_events),
        "damage_source_delta": delta,
        "damage_source_mismatch": bool(mismatch),
        # --- SECONDARY (replay-usability-filtered; RL-training view) ---
        "rl_usable_view": rv,
    }


# ---------------------------------------------------------------------------
# Bootstrap (seeded percentile CIs; resample runs within arm)
# ---------------------------------------------------------------------------
def _agg(values: np.ndarray, how: str) -> float:
    if values.size == 0:
        return float("nan")
    return float(np.median(values)) if how == "median" else float(np.mean(values))


def bootstrap_ci(values, rng, n_boot: int, how: str = "mean", pcts=CI_PCTS) -> dict:
    """Percentile bootstrap CI for an arm statistic; NaNs dropped before resample."""
    v = np.asarray(values, dtype=np.float64)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return {"point": None, "lo": None, "hi": None, "n": 0, "agg": how}
    m = v.size
    stats = np.empty(n_boot, dtype=np.float64)
    for i in range(n_boot):
        idx = rng.integers(0, m, m)
        stats[i] = _agg(v[idx], how)
    lo, hi = np.percentile(stats, pcts)
    return {
        "point": _agg(v, how),
        "lo": float(lo),
        "hi": float(hi),
        "n": int(m),
        "agg": how,
    }


def bootstrap_diff_ci(learned, control, rng, n_boot: int, how: str = "mean", pcts=CI_PCTS) -> dict:
    """Percentile bootstrap CI for learned-minus-control (resample each arm)."""
    lv = np.asarray(learned, dtype=np.float64)
    lv = lv[np.isfinite(lv)]
    cv = np.asarray(control, dtype=np.float64)
    cv = cv[np.isfinite(cv)]
    if lv.size == 0 or cv.size == 0:
        return {
            "point": None, "lo": None, "hi": None,
            "n_learned": int(lv.size), "n_control": int(cv.size),
            "agg": how, "straddles_zero": None,
        }
    nl, nc = lv.size, cv.size
    stats = np.empty(n_boot, dtype=np.float64)
    for i in range(n_boot):
        ls = _agg(lv[rng.integers(0, nl, nl)], how)
        cs = _agg(cv[rng.integers(0, nc, nc)], how)
        stats[i] = ls - cs
    lo, hi = np.percentile(stats, pcts)
    point = _agg(lv, how) - _agg(cv, how)
    return {
        "point": float(point),
        "lo": float(lo),
        "hi": float(hi),
        "n_learned": int(nl),
        "n_control": int(nc),
        "agg": how,
        "straddles_zero": bool(lo <= 0.0 <= hi),
    }


def _col(metrics: list[dict], key: str) -> np.ndarray:
    return np.asarray([m.get(key, float("nan")) for m in metrics], dtype=np.float64)


def _strat_col(metrics: list[dict], group: str, label: str) -> np.ndarray:
    return np.asarray(
        [m.get(group, {}).get(label, float("nan")) for m in metrics], dtype=np.float64
    )


def arm_block(metrics: list[dict], rng, n_boot: int) -> dict:
    """Arm-level medians/means + CIs for every reported metric."""
    def both(vals):
        return {
            "mean": bootstrap_ci(vals, rng, n_boot, "mean"),
            "median": bootstrap_ci(vals, rng, n_boot, "median"),
        }

    block = {
        "n_runs": len(metrics),
        "runs": metrics,
        "final_wave": both(_col(metrics, "final_wave")),
        "victory_rate": bootstrap_ci(_col(metrics, "victory"), rng, n_boot, "mean"),
        "damage_rate_overall": both(_col(metrics, "damage_rate_overall")),
        "damage_rate_wave20": both(_col(metrics, "damage_rate_wave20")),
        "damage_rate_risk_ge_0p5": both(_col(metrics, "damage_rate_risk_ge_0p5")),
        "damage_rate_by_wave_band": {
            lab: both(_strat_col(metrics, "damage_rate_by_wave_band", lab))
            for lab in WAVE_BAND_LABELS
        },
        "damage_rate_by_risk_stratum": {
            lab: both(_strat_col(metrics, "damage_rate_by_risk_stratum", lab))
            for lab in RISK_BIN_LABELS
        },
        # Secondary diagnostic: the replay-usability-filtered overall rate. NOT
        # used by the checkpoint summary -- shown only to expose the filter bias.
        "rl_usable_view": {
            "damage_rate_overall": both(
                np.asarray(
                    [m["rl_usable_view"]["damage_rate_overall"] for m in metrics],
                    dtype=np.float64,
                )
            ),
        },
    }
    return block


def diff_block(learned: list[dict], control: list[dict], rng, n_boot: int) -> dict:
    """learned-minus-control differences (mean + median) for every metric."""
    def both(lkey_vals, ckey_vals):
        return {
            "mean": bootstrap_diff_ci(lkey_vals, ckey_vals, rng, n_boot, "mean"),
            "median": bootstrap_diff_ci(lkey_vals, ckey_vals, rng, n_boot, "median"),
        }

    return {
        "final_wave": both(_col(learned, "final_wave"), _col(control, "final_wave")),
        "victory_rate": {
            "mean": bootstrap_diff_ci(
                _col(learned, "victory"), _col(control, "victory"), rng, n_boot, "mean"
            )
        },
        "damage_rate_overall": both(
            _col(learned, "damage_rate_overall"), _col(control, "damage_rate_overall")
        ),
        "damage_rate_wave20": both(
            _col(learned, "damage_rate_wave20"), _col(control, "damage_rate_wave20")
        ),
        "damage_rate_risk_ge_0p5": both(
            _col(learned, "damage_rate_risk_ge_0p5"),
            _col(control, "damage_rate_risk_ge_0p5"),
        ),
        "damage_rate_by_wave_band": {
            lab: both(
                _strat_col(learned, "damage_rate_by_wave_band", lab),
                _strat_col(control, "damage_rate_by_wave_band", lab),
            )
            for lab in WAVE_BAND_LABELS
        },
        "damage_rate_by_risk_stratum": {
            lab: both(
                _strat_col(learned, "damage_rate_by_risk_stratum", lab),
                _strat_col(control, "damage_rate_by_risk_stratum", lab),
            )
            for lab in RISK_BIN_LABELS
        },
    }


# ---------------------------------------------------------------------------
# Top-level comparison
# ---------------------------------------------------------------------------
LEARNED_LABEL = "residual-teacher-base control (14.3)"
CONTROL_LABEL = "Phase-1 uniform random probe (matched theta bound)"


def collect_arm(run_ids, runs_dir: Path, schema: dict, reward: RewardConfig, log=print):
    metrics = []
    for rid in run_ids:
        run_dir = runs_dir / rid
        if not (run_dir / "events.jsonl").is_file():
            log(f"  WARN: missing events for {rid} at {run_dir}")
            continue
        stream = load_run(rid, runs_dir, schema)
        full = full_stream_steps(stream.captures)
        rl = damage_steps(stream.ticks, stream.tick_risks, reward)
        summary = _load_summary(run_dir)
        m = run_metrics(
            rid, full, rl, summary, stream.terminal,
            stream.player_damage_sum, stream.player_damage_events,
        )
        metrics.append(m)
        flag = " MISMATCH" if m["damage_source_mismatch"] else ""
        log(f"  {rid}: final_wave={m['final_wave']} victory={int(m['victory'])} "
            f"caps={m['n_capture_ticks']} full_dmg_rate={m['damage_rate_overall']:.6f} "
            f"capture_drop={m['capture_drop_sum']:.0f} vs player_damage="
            f"{m['player_damage_sum']:.0f} ({m['player_damage_events']} evts){flag} | "
            f"rl_usable_dmg_rate={m['rl_usable_view']['damage_rate_overall']:.6f}")
    return metrics


def compare(learned_ids, control_ids, runs_dir, schema, reward, seed, n_boot, log=print):
    log("learned arm:")
    learned = collect_arm(learned_ids, runs_dir, schema, reward, log)
    log("control arm:")
    control = collect_arm(control_ids, runs_dir, schema, reward, log)

    rng = np.random.default_rng(seed)
    learned_arm = arm_block(learned, rng, n_boot)
    control_arm = arm_block(control, rng, n_boot)
    diffs = diff_block(learned, control, rng, n_boot)

    # Predeclared decision surface (emit, don't decide). Full capture stream.
    checkpoint_summary = {
        "note": (
            "Predeclared surface (FULL capture-stream damage): overall + wave-20 + "
            "risk>=0.5 learned-minus-control differences (normalized damage rate). "
            "NEGATIVE damage diff => learned takes less damage. Emitted, not adjudicated."
        ),
        "damage_source": "full_capture_stream",
        "final_wave_diff_mean": diffs["final_wave"]["mean"],
        "victory_rate_diff": diffs["victory_rate"]["mean"],
        "damage_rate_overall_diff_mean": diffs["damage_rate_overall"]["mean"],
        "damage_rate_wave20_diff_mean": diffs["damage_rate_wave20"]["mean"],
        "damage_rate_risk_ge_0p5_diff_mean": diffs["damage_rate_risk_ge_0p5"]["mean"],
    }

    any_mismatch = [
        m["run_id"] for m in (learned + control) if m["damage_source_mismatch"]
    ]
    cross_check = {
        "note": (
            "Per-run capture hp-drop sum vs the mod's player_damage event sum; "
            "mismatch flagged if |delta| > 5 hp."
        ),
        "runs": [
            {
                "run_id": m["run_id"],
                "capture_drop_sum": m["capture_drop_sum"],
                "player_damage_sum": m["player_damage_sum"],
                "player_damage_events": m["player_damage_events"],
                "delta": m["damage_source_delta"],
                "mismatch": m["damage_source_mismatch"],
            }
            for m in (learned + control)
        ],
        "any_mismatch": bool(any_mismatch),
        "mismatch_run_ids": any_mismatch,
    }

    return {
        "task": "wp2_stage_f_phase2_checkpoint_compare",
        "labels": {"learned": LEARNED_LABEL, "control": CONTROL_LABEL},
        "damage_accounting": (
            "PRIMARY = full combat_capture stream, unfiltered (every hp drop between "
            "consecutive captures, heal-clamped, normalized by pre-drop max_hp, "
            "attributed to the pre-drop capture's wave band / risk stratum; tick "
            "denominator = all captures). SECONDARY 'rl_usable_view' = the "
            "replay-usability-filtered RL-training view (valid student tick, 2s "
            "recovery exclusion, contiguous seq); it undercounts damage in "
            "recovery-heavy runs and is a diagnostic only."
        ),
        "sign_convention": (
            "learned - control; damage rates negative => learned better; "
            "final_wave/victory positive => learned better"
        ),
        "seed": seed,
        "bootstrap_n": n_boot,
        "ci_percentiles": list(CI_PCTS),
        "reward_config": {
            "w_damage": reward.w_damage, "w_wave": reward.w_wave,
            "w_victory": reward.w_victory, "w_intervention": reward.w_intervention,
            "tau_sec": reward.tau_sec,
        },
        "wave_band_labels": list(WAVE_BAND_LABELS),
        "risk_bin_labels": list(RISK_BIN_LABELS),
        "learned_run_ids": list(learned_ids),
        "control_run_ids": list(control_ids),
        "learned_arm": learned_arm,
        "control_arm": control_arm,
        "differences": diffs,
        "damage_source_cross_check": cross_check,
        "checkpoint_summary": checkpoint_summary,
    }


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------
def _fmt_ci(ci: dict, nd: int = 5) -> str:
    if ci is None or ci.get("point") is None:
        return "n/a"
    sz = ""
    if "straddles_zero" in ci and ci["straddles_zero"] is not None:
        sz = " [straddles 0]" if ci["straddles_zero"] else " [excludes 0]"
    return f"{ci['point']:.{nd}f} [{ci['lo']:.{nd}f}, {ci['hi']:.{nd}f}]{sz}"


def render_markdown(report: dict) -> str:
    L = []
    L.append("# WP2 Stage F Phase 2 -- residual checkpoint comparison")
    L.append("")
    L.append(f"- Learned arm: **{report['labels']['learned']}** "
             f"({report['learned_arm']['n_runs']} runs)")
    L.append(f"- Control arm: **{report['labels']['control']}** "
             f"({report['control_arm']['n_runs']} runs)")
    L.append(f"- Sign convention: {report['sign_convention']}")
    L.append(f"- Bootstrap: {report['bootstrap_n']} resamples, seed "
             f"{report['seed']}, {report['ci_percentiles'][0]}/"
             f"{report['ci_percentiles'][1]} percentile CIs. No significance tests.")
    L.append("")

    L.append(f"- Damage accounting: {report['damage_accounting']}")
    L.append("")

    def g(x):
        return "n/a" if (x is None or (isinstance(x, float) and not np.isfinite(x))) else (
            f"{x:.5f}" if isinstance(x, float) else str(x))

    L.append("## Per-run table (PRIMARY = full capture stream)")
    L.append("")
    for arm_key, arm_lab in (("learned_arm", "Learned"), ("control_arm", "Control")):
        L.append(f"### {arm_lab}")
        L.append("")
        L.append("| run | final_wave | victory | captures | full_dmg_rate | w20_rate | "
                 "risk>=0.5_rate | capture_drop | player_damage | mismatch | rl_usable_rate |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for m in report[arm_key]["runs"]:
            L.append(f"| {m['run_id']} | {m['final_wave']} | {int(m['victory'])} | "
                     f"{m['n_capture_ticks']} | {g(m['damage_rate_overall'])} | "
                     f"{g(m['damage_rate_wave20'])} | {g(m['damage_rate_risk_ge_0p5'])} | "
                     f"{m['capture_drop_sum']:.0f} | {m['player_damage_sum']:.0f} "
                     f"({m['player_damage_events']}) | "
                     f"{'YES' if m['damage_source_mismatch'] else 'no'} | "
                     f"{g(m['rl_usable_view']['damage_rate_overall'])} |")
        L.append("")

    cc_blk = report["damage_source_cross_check"]
    L.append("### Damage source cross-check")
    L.append("")
    L.append(cc_blk["note"])
    if cc_blk["any_mismatch"]:
        L.append("")
        L.append(f"**MISMATCH flagged for: {', '.join(cc_blk['mismatch_run_ids'])}**")
    else:
        L.append("")
        L.append("All runs agree within 5 hp between the capture hp-drop sum and the "
                 "mod's player_damage events.")
    L.append("")

    L.append("## Arm summaries (point [CI])")
    L.append("")
    L.append("| metric | learned | control |")
    L.append("|---|---|---|")
    la, ca = report["learned_arm"], report["control_arm"]
    L.append(f"| final_wave (mean) | {_fmt_ci(la['final_wave']['mean'], 3)} | "
             f"{_fmt_ci(ca['final_wave']['mean'], 3)} |")
    L.append(f"| final_wave (median) | {_fmt_ci(la['final_wave']['median'], 3)} | "
             f"{_fmt_ci(ca['final_wave']['median'], 3)} |")
    L.append(f"| victory_rate | {_fmt_ci(la['victory_rate'], 3)} | "
             f"{_fmt_ci(ca['victory_rate'], 3)} |")
    L.append(f"| dmg_rate overall (mean) | {_fmt_ci(la['damage_rate_overall']['mean'])} | "
             f"{_fmt_ci(ca['damage_rate_overall']['mean'])} |")
    L.append(f"| dmg_rate wave20 (mean) | {_fmt_ci(la['damage_rate_wave20']['mean'])} | "
             f"{_fmt_ci(ca['damage_rate_wave20']['mean'])} |")
    L.append(f"| dmg_rate risk>=0.5 (mean) | {_fmt_ci(la['damage_rate_risk_ge_0p5']['mean'])} | "
             f"{_fmt_ci(ca['damage_rate_risk_ge_0p5']['mean'])} |")
    L.append(f"| _rl_usable dmg_rate (mean, diagnostic)_ | "
             f"{_fmt_ci(la['rl_usable_view']['damage_rate_overall']['mean'])} | "
             f"{_fmt_ci(ca['rl_usable_view']['damage_rate_overall']['mean'])} |")
    L.append("")

    L.append("### Damage rate by wave band (mean [CI])")
    L.append("")
    L.append("| band | learned | control |")
    L.append("|---|---|---|")
    for lab in WAVE_BAND_LABELS:
        L.append(f"| {lab} | {_fmt_ci(la['damage_rate_by_wave_band'][lab]['mean'])} | "
                 f"{_fmt_ci(ca['damage_rate_by_wave_band'][lab]['mean'])} |")
    L.append("")
    L.append("### Damage rate by risk stratum (mean [CI])")
    L.append("")
    L.append("| stratum | learned | control |")
    L.append("|---|---|---|")
    for lab in RISK_BIN_LABELS:
        L.append(f"| {lab} | {_fmt_ci(la['damage_rate_by_risk_stratum'][lab]['mean'])} | "
                 f"{_fmt_ci(ca['damage_rate_by_risk_stratum'][lab]['mean'])} |")
    L.append("")

    L.append("## Differences (learned - control, mean [CI])")
    L.append("")
    d = report["differences"]
    L.append("| metric | diff [CI] |")
    L.append("|---|---|")
    L.append(f"| final_wave | {_fmt_ci(d['final_wave']['mean'], 3)} |")
    L.append(f"| victory_rate | {_fmt_ci(d['victory_rate']['mean'], 3)} |")
    L.append(f"| dmg_rate overall | {_fmt_ci(d['damage_rate_overall']['mean'])} |")
    L.append(f"| dmg_rate wave20 | {_fmt_ci(d['damage_rate_wave20']['mean'])} |")
    L.append(f"| dmg_rate risk>=0.5 | {_fmt_ci(d['damage_rate_risk_ge_0p5']['mean'])} |")
    for lab in WAVE_BAND_LABELS:
        L.append(f"| dmg_rate band {lab} | "
                 f"{_fmt_ci(d['damage_rate_by_wave_band'][lab]['mean'])} |")
    for lab in RISK_BIN_LABELS:
        L.append(f"| dmg_rate risk {lab} | "
                 f"{_fmt_ci(d['damage_rate_by_risk_stratum'][lab]['mean'])} |")
    L.append("")

    L.append("## Checkpoint summary (predeclared decision surface)")
    L.append("")
    cs = report["checkpoint_summary"]
    L.append(cs["note"])
    L.append("")
    L.append("| highlighted diff | value [CI] |")
    L.append("|---|---|")
    L.append(f"| overall dmg_rate | {_fmt_ci(cs['damage_rate_overall_diff_mean'])} |")
    L.append(f"| wave-20 dmg_rate | {_fmt_ci(cs['damage_rate_wave20_diff_mean'])} |")
    L.append(f"| risk>=0.5 dmg_rate | {_fmt_ci(cs['damage_rate_risk_ge_0p5_diff_mean'])} |")
    L.append(f"| final_wave | {_fmt_ci(cs['final_wave_diff_mean'], 3)} |")
    L.append(f"| victory_rate | {_fmt_ci(cs['victory_rate_diff'], 3)} |")
    L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def _split_ids(text: str) -> list[str]:
    return [x.strip() for x in text.split(",") if x.strip()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--learned-runs", required=True,
                    help="comma-separated learned-arm run_ids")
    ap.add_argument("--control-runs", required=True,
                    help="comma-separated control-arm run_ids")
    ap.add_argument("--runs-dir", default=None,
                    help="collector runs dir (default: %APPDATA%/Brotato/brotato_agent/runs)")
    ap.add_argument("--schema", default=str(DEFAULT_SCHEMA),
                    help="observation schema yaml (default configs/wp2/observation_v1.yaml)")
    ap.add_argument("--reward-yaml", default=str(DEFAULT_REWARD_YAML),
                    help="reward_v2 weights yaml (default configs/wp2/reward_v1.yaml)")
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--bootstrap-n", type=int, default=10000)
    args = ap.parse_args(argv)

    runs_dir = Path(args.runs_dir) if args.runs_dir else default_runs_dir()
    schema = encoder_v1.load_schema(Path(args.schema))
    reward = RewardConfig.from_yaml(args.reward_yaml)
    learned_ids = _split_ids(args.learned_runs)
    control_ids = _split_ids(args.control_runs)

    print("=== WP2 Stage F Phase 2: checkpoint compare ===", flush=True)
    print(f"runs_dir={runs_dir}", flush=True)
    print(f"seed={args.seed} bootstrap_n={args.bootstrap_n} "
          f"learned={len(learned_ids)} control={len(control_ids)}", flush=True)

    report = compare(learned_ids, control_ids, runs_dir, schema, reward,
                     args.seed, args.bootstrap_n)

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    out_md.write_text(render_markdown(report), encoding="utf-8")

    xc = report["damage_source_cross_check"]
    print("", flush=True)
    if xc["any_mismatch"]:
        print(f"CROSS-CHECK: capture-drop vs player_damage MISMATCH (>5hp) in "
              f"{xc['mismatch_run_ids']}", flush=True)
    else:
        print("CROSS-CHECK: all runs agree within 5 hp (capture-drop vs player_damage)",
              flush=True)

    cs = report["checkpoint_summary"]
    print("", flush=True)
    print("=== CHECKPOINT SUMMARY (FULL capture stream; learned - control, mean [CI]) ===", flush=True)
    print(f"overall dmg_rate : {_fmt_ci(cs['damage_rate_overall_diff_mean'])}", flush=True)
    print(f"wave-20 dmg_rate : {_fmt_ci(cs['damage_rate_wave20_diff_mean'])}", flush=True)
    print(f"risk>=0.5 dmg_rate: {_fmt_ci(cs['damage_rate_risk_ge_0p5_diff_mean'])}", flush=True)
    print(f"final_wave       : {_fmt_ci(cs['final_wave_diff_mean'], 3)}", flush=True)
    print(f"victory_rate     : {_fmt_ci(cs['victory_rate_diff'], 3)}", flush=True)
    print(f"json: {out_json}", flush=True)
    print(f"md  : {out_md}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
