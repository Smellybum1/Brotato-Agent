#!/usr/bin/env python3
"""WP2 Stage F2 -- primary endpoint calculator (BINDING design .tmp/wp2_stage_f2_design.md).

Computes the F2 PRIMARY statistic: a hierarchical run-outcome comparison between
two arms,

  T (pure teacher)  vs  P (deterministic pi4, residual-teacher-base control 14.3)

as P(a random P run outranks a random T run), with a 95% percentile CI from a
run-level cluster bootstrap. Ticks are NEVER units of analysis; the cluster is
the run (Pro review adoption item 4, .tmp/pro_review_adoption_20260725.md).

Read-only on run dirs. No game, no deploy, no network, no torch.

------------------------------------------------------------------------------
Hierarchical run outcome (predeclared, design 40-48)
------------------------------------------------------------------------------
Per run we build the tuple (victory, combat_progress, auc_norm):

1. ``victory``: summary.json ``result`` == "victory" (falling back to the
   run_end event payload's result), the scripts/wp2_telemetry_stats.py audit
   convention shared with scripts/wp2_residual_checkpoint_compare.py.

2. ``combat_progress``: completed waves + fraction of the death wave survived.
   The collector's ``last_wave`` / ``waves_completed`` both name the wave the
   run DIED IN, so for a defeat the completed-wave count is ``last_wave - 1``
   and the death wave is ``last_wave``:

       combat_progress = (last_wave - 1) + observed_ticks_in_death_wave
                                           / expected_ticks(death_wave)

   VICTORIES get combat_progress = 21.0 -- above every possible defeat value
   (a defeat can at most approach 20.0), so the victory tier is enforced by the
   number itself regardless of which tie-break path a comparison takes.

   ESTIMATOR (expected ticks per wave). Waves have a fixed nominal duration but
   a variable observed capture count (capture cadence drifts with load, and the
   mod's per-wave capture totals differ run to run), so the denominator is
   estimated EMPIRICALLY from the runs in THIS invocation rather than from a
   nominal constant:

       expected_ticks(w) = median observed capture count for wave w over all
                           runs (both arms) in this invocation that COMPLETED
                           wave w.

   A run completed wave w iff (victory and w <= last_wave) or
   (defeat and w < last_wave). If NO run in the invocation completed wave w
   (e.g. every run died in that wave), the estimator falls back to the MAXIMUM
   observed tick count for w -- the most conservative available lower bound on
   the true wave length, which keeps every death-wave fraction <= 1.0. The
   fraction is clipped to [0, 1] either way. Pooling BOTH arms for the
   denominator keeps the estimator arm-blind, so it cannot manufacture a
   between-arm difference.

3. ``auc_norm`` (alive-and-healthy AUC): sum over the combat_capture stream of
   (hp / max_hp) * dt, plus zero for the remainder of the fixed 20-wave
   horizon after death, normalized by the horizon length:

       auc_norm = sum_i (hp_i / max_hp_i) * dt_i / horizon
       horizon  = observed_combat_time + post_death_remainder

   dt_i is the wall-clock gap to the next capture (event ``ts_ms``), CLAMPED at
   DT_CLAMP_MS = 1000 ms: gaps larger than that are shop/level-up/loading
   interludes, not combat, and are replaced by the run's median capture gap so
   between-wave dead time neither inflates the horizon nor dilutes the ratio.
   The final capture also gets the median gap. "Observed combat time" is
   therefore the sum of clamped dts, not the run's wall-clock length.

   ESTIMATOR (post-death remainder). The 20-wave horizon length is not directly
   observable for a run that died early, so:

       post_death_remainder = max(0, reference_full_duration - observed_time)
       reference_full_duration = median observed combat time over the VICTORY
                                 runs in this invocation;
                                 fallback (no victories): the longest observed
                                 combat time in this invocation.

   Victories get remainder 0 (they played the whole horizon). Consequence: a
   run that dies at wave 5 is normalized by a near-full horizon and scores a
   small AUC, while a full-length run is normalized by its own length -- i.e.
   the AUC is "fraction of the 20-wave horizon spent alive and at full HP".
   Both estimators are invocation-scoped and therefore reported in the outputs.

------------------------------------------------------------------------------
Pairwise rule and primary statistic
------------------------------------------------------------------------------
compare_runs(p, t) -> 1.0 if P outranks T, 0.0 if T outranks P, 0.5 on exact tie:
  victory beats defeat; else combat_progress (larger wins); else, when progress
  is equal to within PROGRESS_TIE_EPS = 1e-9, auc_norm (larger wins); else 0.5.

  win_probability = mean over all |T| x |P| pairs of compare_runs(p, t)

CI: percentile bootstrap, ``bootstrap_n`` resamples (default 10000), seeded
(default 0), resampling RUNS with replacement within each arm INDEPENDENTLY and
recomputing the full pairwise mean. The outcome tuples themselves are computed
ONCE on the observed set (the wave/horizon estimators are properties of the
invocation, not of a bootstrap replicate) -- so the CI reflects run-sampling
variability, not estimator jitter.

Secondaries reported (non-gating): victory rate per arm, mean/median final wave,
and the full per-run tuple table.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

T_LABEL = "T (pure teacher)"
P_LABEL = "P (deterministic pi4, residual-teacher-base control 14.3)"

VICTORY_PROGRESS = 21.0
PROGRESS_TIE_EPS = 1e-9
DT_CLAMP_MS = 1000.0
CI_PCTS = (2.5, 97.5)
HORIZON_WAVES = 20


# ---------------------------------------------------------------------------
# Run loading (same conventions as scripts/wp2_residual_checkpoint_compare.py)
# ---------------------------------------------------------------------------
def default_runs_dir() -> Path:
    appdata = os.environ.get("APPDATA", r"C:\Users\moxhe\AppData\Roaming")
    return Path(appdata) / "Brotato" / "brotato_agent" / "runs"


@dataclass
class RunRaw:
    """Everything one streaming pass over a run yields for the F2 endpoint.

    Deliberately file-free so unit tests can build synthetic fixtures directly.
    """

    run_id: str
    victory: bool
    last_wave: int
    result: str | None = None
    wave_tick_counts: dict[int, int] = field(default_factory=dict)
    combat_time_sec: float = 0.0
    auc_raw: float = 0.0          # sum (hp/max_hp) * dt, seconds
    n_captures: int = 0

    def completed_wave(self, wave: int) -> bool:
        """Did this run finish `wave`? Defeats never complete their death wave."""
        if self.victory:
            return wave <= self.last_wave
        return wave < self.last_wave

    @property
    def death_wave(self) -> int:
        return self.last_wave


def _load_summary(run_dir: Path) -> dict:
    p = run_dir / "summary.json"
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def load_run(run_id: str, runs_dir: Path) -> RunRaw:
    """One streaming pass over events.jsonl -> RunRaw.

    Captures: every combat_capture carrying a numeric player hp. dt comes from
    consecutive event ts_ms, clamped at DT_CLAMP_MS and back-filled with the
    run's median gap (see module docstring).
    """
    run_dir = runs_dir / run_id
    events_path = run_dir / "events.jsonl"
    ts: list[float] = []
    hp_ratio: list[float] = []
    waves: list[int] = []
    terminal: str | None = None
    with events_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            e = json.loads(line)
            et = e.get("event")
            if et == "combat_capture":
                payload = e.get("payload", {}) or {}
                player = payload.get("player", {}) or {}
                hp = player.get("hp")
                if hp is None:
                    continue
                max_hp = float(player.get("max_hp", 0.0)) or 1.0
                ts.append(float(e.get("ts_ms", 0.0)))
                hp_ratio.append(max(0.0, float(hp)) / max_hp)
                waves.append(int(payload.get("wave") or 0))
            elif et == "run_end":
                terminal = str((e.get("payload", {}) or {}).get("result")) or None

    summary = _load_summary(run_dir)
    result = summary.get("result")
    if result is None:
        result = terminal
    last_wave = summary.get("last_wave")
    if last_wave is None:
        last_wave = summary.get("waves_completed")
    if last_wave is None:
        last_wave = max(waves) if waves else 0

    dts = capture_dts(np.asarray(ts, dtype=np.float64))
    ratios = np.asarray(hp_ratio, dtype=np.float64)
    wave_counts: dict[int, int] = {}
    for w in waves:
        wave_counts[w] = wave_counts.get(w, 0) + 1

    return RunRaw(
        run_id=run_id,
        victory=(result == "victory"),
        last_wave=int(last_wave),
        result=result,
        wave_tick_counts=wave_counts,
        combat_time_sec=float(dts.sum()) / 1000.0,
        auc_raw=float((ratios * dts).sum()) / 1000.0 if ratios.size else 0.0,
        n_captures=len(ts),
    )


def capture_dts(ts_ms: np.ndarray) -> np.ndarray:
    """Per-capture dt in ms: forward gaps, clamped, with the median back-filled.

    Gaps > DT_CLAMP_MS are non-combat interludes (shop, level-up, load) and are
    replaced by the run's median gap; the last capture gets the median too.
    """
    n = int(ts_ms.shape[0])
    if n == 0:
        return np.zeros(0, dtype=np.float64)
    if n == 1:
        return np.zeros(1, dtype=np.float64)
    gaps = np.diff(ts_ms)
    good = gaps[(gaps > 0.0) & (gaps <= DT_CLAMP_MS)]
    median_gap = float(np.median(good)) if good.size else 0.0
    dts = np.where((gaps > 0.0) & (gaps <= DT_CLAMP_MS), gaps, median_gap)
    return np.concatenate([dts, [median_gap]])


# ---------------------------------------------------------------------------
# Invocation-scoped estimators
# ---------------------------------------------------------------------------
def expected_ticks_per_wave(runs: list[RunRaw]) -> dict[int, dict]:
    """Median tick count per wave over runs that COMPLETED that wave.

    Falls back to the max observed count for waves no run completed. Returns
    {wave: {"expected_ticks", "source", "n_completers", "n_observers"}}.
    """
    observed: dict[int, list[int]] = {}
    completed: dict[int, list[int]] = {}
    for r in runs:
        for wave, count in r.wave_tick_counts.items():
            observed.setdefault(wave, []).append(count)
            if r.completed_wave(wave):
                completed.setdefault(wave, []).append(count)
    out: dict[int, dict] = {}
    for wave in sorted(observed):
        comp = completed.get(wave, [])
        if comp:
            est = float(np.median(comp))
            source = "median_of_completers"
        else:
            est = float(max(observed[wave]))
            source = "max_observed_no_completer"
        out[wave] = {
            "expected_ticks": est,
            "source": source,
            "n_completers": len(comp),
            "n_observers": len(observed[wave]),
        }
    return out


def reference_full_duration(runs: list[RunRaw]) -> dict:
    """Reference 20-wave combat duration (seconds) for horizon normalization.

    Median over victory runs; fallback = longest observed combat time.
    """
    vic = [r.combat_time_sec for r in runs if r.victory]
    if vic:
        return {
            "seconds": float(np.median(vic)),
            "source": "median_victory_duration",
            "n_victories": len(vic),
        }
    longest = max((r.combat_time_sec for r in runs), default=0.0)
    return {
        "seconds": float(longest),
        "source": "fallback_longest_observed",
        "n_victories": 0,
    }


# ---------------------------------------------------------------------------
# Outcome tuples
# ---------------------------------------------------------------------------
@dataclass
class Outcome:
    run_id: str
    arm: str
    victory: bool
    combat_progress: float
    auc_norm: float
    final_wave: int
    result: str | None = None
    death_wave_ticks: int = 0
    expected_ticks: float = float("nan")
    death_wave_fraction: float = float("nan")
    combat_time_sec: float = 0.0
    horizon_sec: float = 0.0
    auc_raw: float = 0.0
    n_captures: int = 0

    def as_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "arm": self.arm,
            "result": self.result,
            "victory": bool(self.victory),
            "final_wave": int(self.final_wave),
            "combat_progress": self.combat_progress,
            "auc_norm": self.auc_norm,
            "death_wave_ticks": int(self.death_wave_ticks),
            "expected_ticks_death_wave": self.expected_ticks,
            "death_wave_fraction": self.death_wave_fraction,
            "combat_time_sec": self.combat_time_sec,
            "horizon_sec": self.horizon_sec,
            "auc_raw_sec": self.auc_raw,
            "n_captures": int(self.n_captures),
        }


def build_outcomes(runs: list[RunRaw], arms: dict[str, str]) -> tuple[list[Outcome], dict]:
    """Build the hierarchical outcome tuple for every run, plus the estimators.

    ``arms`` maps run_id -> arm label. Estimators are pooled over ALL runs given
    (both arms) so they are arm-blind.
    """
    ticks_est = expected_ticks_per_wave(runs)
    ref = reference_full_duration(runs)
    outcomes: list[Outcome] = []
    for r in runs:
        if r.victory:
            progress = VICTORY_PROGRESS
            exp_ticks = float("nan")
            frac = float("nan")
            dw_ticks = r.wave_tick_counts.get(r.death_wave, 0)
            remainder = 0.0
        else:
            dw_ticks = r.wave_tick_counts.get(r.death_wave, 0)
            entry = ticks_est.get(r.death_wave)
            exp_ticks = float(entry["expected_ticks"]) if entry else float("nan")
            if exp_ticks and np.isfinite(exp_ticks) and exp_ticks > 0.0:
                frac = min(1.0, max(0.0, dw_ticks / exp_ticks))
            else:
                frac = 0.0
            progress = float(max(0, r.last_wave - 1)) + frac
            remainder = max(0.0, ref["seconds"] - r.combat_time_sec)
        horizon = r.combat_time_sec + remainder
        auc_norm = (r.auc_raw / horizon) if horizon > 0.0 else 0.0
        outcomes.append(
            Outcome(
                run_id=r.run_id,
                arm=arms.get(r.run_id, "?"),
                victory=r.victory,
                combat_progress=float(progress),
                auc_norm=float(auc_norm),
                final_wave=int(r.last_wave),
                result=r.result,
                death_wave_ticks=int(dw_ticks),
                expected_ticks=exp_ticks,
                death_wave_fraction=frac,
                combat_time_sec=r.combat_time_sec,
                horizon_sec=float(horizon),
                auc_raw=r.auc_raw,
                n_captures=r.n_captures,
            )
        )
    estimators = {
        "expected_ticks_per_wave": {str(k): v for k, v in ticks_est.items()},
        "reference_full_duration": ref,
        "horizon_waves": HORIZON_WAVES,
        "dt_clamp_ms": DT_CLAMP_MS,
        "note": (
            "Estimators are invocation-scoped and pooled over both arms "
            "(arm-blind). expected_ticks falls back to the max observed count "
            "for waves no run completed; reference_full_duration falls back to "
            "the longest observed combat time when no run is a victory."
        ),
    }
    return outcomes, estimators


# ---------------------------------------------------------------------------
# Pairwise comparison + primary statistic
# ---------------------------------------------------------------------------
def compare_runs(p: Outcome, t: Outcome) -> float:
    """1.0 if P outranks T, 0.0 if T outranks P, 0.5 on exact tie."""
    if p.victory != t.victory:
        return 1.0 if p.victory else 0.0
    dp = p.combat_progress - t.combat_progress
    if abs(dp) > PROGRESS_TIE_EPS:
        return 1.0 if dp > 0.0 else 0.0
    if p.auc_norm > t.auc_norm:
        return 1.0
    if p.auc_norm < t.auc_norm:
        return 0.0
    return 0.5


def win_probability(t_out: list[Outcome], p_out: list[Outcome]) -> float:
    """Mean over all T x P pairs of [P outranks T] (ties 0.5)."""
    if not t_out or not p_out:
        return float("nan")
    return float(
        np.mean([[compare_runs(p, t) for t in t_out] for p in p_out])
    )


def bootstrap_win_probability(
    t_out: list[Outcome], p_out: list[Outcome], seed: int, n_boot: int
) -> dict:
    """Run-level cluster bootstrap CI (resample each arm independently)."""
    point = win_probability(t_out, p_out)
    if not t_out or not p_out:
        return {
            "point": None, "lo": None, "hi": None,
            "n_t": len(t_out), "n_p": len(p_out),
            "bootstrap_n": int(n_boot), "seed": int(seed),
            "excludes_0p5": None, "direction": None,
        }
    # Precompute the full pairwise matrix once: M[i, j] = compare(p_i, t_j).
    mat = np.asarray(
        [[compare_runs(p, t) for t in t_out] for p in p_out], dtype=np.float64
    )
    rng = np.random.default_rng(seed)
    np_, nt = mat.shape
    stats = np.empty(int(n_boot), dtype=np.float64)
    for i in range(int(n_boot)):
        pi = rng.integers(0, np_, np_)
        ti = rng.integers(0, nt, nt)
        stats[i] = mat[np.ix_(pi, ti)].mean()
    lo, hi = (float(x) for x in np.percentile(stats, CI_PCTS))
    excludes = bool(lo > 0.5 or hi < 0.5)
    return {
        "point": float(point),
        "lo": lo,
        "hi": hi,
        "n_t": len(t_out),
        "n_p": len(p_out),
        "n_pairs": int(np_ * nt),
        "bootstrap_n": int(n_boot),
        "seed": int(seed),
        "ci_percentiles": list(CI_PCTS),
        "excludes_0p5": excludes,
        "direction": ("P favored" if point > 0.5 else "T favored" if point < 0.5 else "tied"),
    }


def arm_secondaries(outcomes: list[Outcome]) -> dict:
    if not outcomes:
        return {
            "n_runs": 0, "victory_rate": None, "n_victories": 0,
            "final_wave_mean": None, "final_wave_median": None,
            "combat_progress_mean": None, "auc_norm_mean": None,
        }
    waves = np.asarray([o.final_wave for o in outcomes], dtype=np.float64)
    vic = np.asarray([1.0 if o.victory else 0.0 for o in outcomes], dtype=np.float64)
    prog = np.asarray([o.combat_progress for o in outcomes], dtype=np.float64)
    auc = np.asarray([o.auc_norm for o in outcomes], dtype=np.float64)
    return {
        "n_runs": len(outcomes),
        "victory_rate": float(vic.mean()),
        "n_victories": int(vic.sum()),
        "final_wave_mean": float(waves.mean()),
        "final_wave_median": float(np.median(waves)),
        "combat_progress_mean": float(prog.mean()),
        "combat_progress_median": float(np.median(prog)),
        "auc_norm_mean": float(auc.mean()),
        "auc_norm_median": float(np.median(auc)),
    }


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------
def analyze(
    t_runs: list[RunRaw],
    p_runs: list[RunRaw],
    *,
    seed: int = 0,
    n_boot: int = 10000,
    validation_only: bool = False,
    excluded: list[dict] | None = None,
) -> dict:
    arms = {r.run_id: "T" for r in t_runs}
    arms.update({r.run_id: "P" for r in p_runs})
    outcomes, estimators = build_outcomes(list(t_runs) + list(p_runs), arms)
    t_out = [o for o in outcomes if o.arm == "T"]
    p_out = [o for o in outcomes if o.arm == "P"]
    primary = bootstrap_win_probability(t_out, p_out, seed, n_boot)

    report = {
        "task": "wp2_stage_f2_endpoint",
        "labels": {"T": T_LABEL, "P": P_LABEL},
        "endpoint": (
            "Hierarchical run outcome: victory > combat progress (completed "
            "waves + fraction of death wave) > alive-and-healthy AUC. Primary "
            "statistic = P(random P run outranks random T run), ties 0.5, with "
            "a 95% percentile CI from a run-level cluster bootstrap. Ticks are "
            "never units of analysis."
        ),
        "seed": int(seed),
        "bootstrap_n": int(n_boot),
        "t_run_ids": [r.run_id for r in t_runs],
        "p_run_ids": [r.run_id for r in p_runs],
        "estimators": estimators,
        "primary": {"win_probability": primary},
        "secondaries": {"T": arm_secondaries(t_out), "P": arm_secondaries(p_out)},
        "runs": [o.as_dict() for o in outcomes],
        "exclusions": list(excluded or []),
    }
    if validation_only:
        report["VALIDATION_ONLY"] = (
            "TOOL VALIDATION ONLY -- not an F2 comparison (arms are Stage F data)"
        )
    return report


def _fmt(x, nd=4) -> str:
    if x is None:
        return "n/a"
    if isinstance(x, float) and not np.isfinite(x):
        return "n/a"
    return f"{x:.{nd}f}" if isinstance(x, float) else str(x)


def render_markdown(report: dict) -> str:
    L: list[str] = []
    if "VALIDATION_ONLY" in report:
        L.append(f"> **{report['VALIDATION_ONLY']}**")
        L.append("")
    L.append("# WP2 Stage F2 -- primary endpoint (hierarchical run outcome)")
    L.append("")
    L.append(f"- Arm T: **{report['labels']['T']}** "
             f"({report['secondaries']['T']['n_runs']} runs)")
    L.append(f"- Arm P: **{report['labels']['P']}** "
             f"({report['secondaries']['P']['n_runs']} runs)")
    L.append(f"- Endpoint: {report['endpoint']}")
    L.append(f"- Bootstrap: {report['bootstrap_n']} run-level resamples, seed "
             f"{report['seed']}, 2.5/97.5 percentile CI. No significance tests.")
    L.append("")

    wp = report["primary"]["win_probability"]
    L.append("## Primary statistic")
    L.append("")
    L.append("| statistic | value |")
    L.append("|---|---|")
    L.append(f"| P(P outranks T) | **{_fmt(wp.get('point'))}** "
             f"[{_fmt(wp.get('lo'))}, {_fmt(wp.get('hi'))}] |")
    L.append(f"| CI vs 0.5 | {'EXCLUDES 0.5' if wp.get('excludes_0p5') else 'straddles 0.5'} |")
    L.append(f"| direction | {wp.get('direction')} |")
    L.append(f"| pairs | {wp.get('n_pairs')} ({wp.get('n_p')} P x {wp.get('n_t')} T) |")
    L.append("")

    L.append("## Secondaries (non-gating)")
    L.append("")
    L.append("| metric | T (pure teacher) | P (deterministic pi4) |")
    L.append("|---|---|---|")
    st, sp = report["secondaries"]["T"], report["secondaries"]["P"]
    for key, lab, nd in (
        ("n_runs", "n_runs", 0),
        ("victory_rate", "victory_rate", 4),
        ("n_victories", "n_victories", 0),
        ("final_wave_mean", "final_wave (mean)", 3),
        ("final_wave_median", "final_wave (median)", 3),
        ("combat_progress_mean", "combat_progress (mean)", 4),
        ("auc_norm_mean", "auc_norm (mean)", 4),
    ):
        L.append(f"| {lab} | {_fmt(st.get(key), nd)} | {_fmt(sp.get(key), nd)} |")
    L.append("")

    L.append("## Per-run outcome tuples")
    L.append("")
    L.append("| arm | run | result | final_wave | combat_progress | auc_norm | "
             "death_wave_ticks | expected_ticks | frac | combat_time_s | horizon_s |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in sorted(report["runs"], key=lambda x: (x["arm"], -x["combat_progress"])):
        L.append(
            f"| {r['arm']} | {r['run_id']} | {r['result']} | {r['final_wave']} | "
            f"{_fmt(r['combat_progress'])} | {_fmt(r['auc_norm'])} | "
            f"{r['death_wave_ticks']} | {_fmt(r['expected_ticks_death_wave'], 1)} | "
            f"{_fmt(r['death_wave_fraction'])} | {_fmt(r['combat_time_sec'], 1)} | "
            f"{_fmt(r['horizon_sec'], 1)} |"
        )
    L.append("")

    est = report["estimators"]
    L.append("## Estimators (invocation-scoped, arm-blind)")
    L.append("")
    L.append(est["note"])
    L.append("")
    ref = est["reference_full_duration"]
    L.append(f"- reference_full_duration = {_fmt(ref['seconds'], 1)} s "
             f"({ref['source']}, {ref['n_victories']} victories)")
    L.append(f"- dt clamp = {est['dt_clamp_ms']:.0f} ms; horizon = {est['horizon_waves']} waves")
    L.append("")
    L.append("| wave | expected_ticks | source | n_completers | n_observers |")
    L.append("|---|---|---|---|---|")
    for wave in sorted(est["expected_ticks_per_wave"], key=lambda k: int(k)):
        e = est["expected_ticks_per_wave"][wave]
        L.append(f"| {wave} | {_fmt(e['expected_ticks'], 1)} | {e['source']} | "
                 f"{e['n_completers']} | {e['n_observers']} |")
    L.append("")

    if report.get("exclusions"):
        L.append("## Exclusions (predeclared technical failure only)")
        L.append("")
        L.append("| run | reason |")
        L.append("|---|---|")
        for x in report["exclusions"]:
            L.append(f"| {x.get('run_id')} | {x.get('reason')} |")
        L.append("")
    return "\n".join(L)


def _split_ids(text: str) -> list[str]:
    return [x.strip() for x in text.split(",") if x.strip()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--t-runs", required=True, help="comma-separated T-arm run_ids")
    ap.add_argument("--p-runs", required=True, help="comma-separated P-arm run_ids")
    ap.add_argument("--runs-dir", default=None,
                    help="collector runs dir (default: %%APPDATA%%/Brotato/brotato_agent/runs)")
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--bootstrap-n", type=int, default=10000)
    ap.add_argument("--exclude", default="",
                    help="comma-separated run_ids to exclude (predeclared technical failure)")
    ap.add_argument("--exclude-reason", default="predeclared technical failure")
    ap.add_argument("--validation-only", action="store_true",
                    help="stamp the outputs 'TOOL VALIDATION ONLY -- not an F2 comparison'")
    args = ap.parse_args(argv)

    runs_dir = Path(args.runs_dir) if args.runs_dir else default_runs_dir()
    excluded_ids = set(_split_ids(args.exclude))
    t_ids = [r for r in _split_ids(args.t_runs) if r not in excluded_ids]
    p_ids = [r for r in _split_ids(args.p_runs) if r not in excluded_ids]

    print("=== WP2 Stage F2: primary endpoint ===", flush=True)
    print(f"runs_dir={runs_dir}", flush=True)
    print(f"seed={args.seed} bootstrap_n={args.bootstrap_n} "
          f"T={len(t_ids)} P={len(p_ids)} excluded={len(excluded_ids)}", flush=True)

    def collect(ids, arm):
        out = []
        for rid in ids:
            if not (runs_dir / rid / "events.jsonl").is_file():
                print(f"  WARN: missing events for {rid} at {runs_dir / rid}", flush=True)
                continue
            r = load_run(rid, runs_dir)
            out.append(r)
            print(f"  [{arm}] {rid}: result={r.result} last_wave={r.last_wave} "
                  f"caps={r.n_captures} combat_time={r.combat_time_sec:.1f}s", flush=True)
        return out

    t_runs = collect(t_ids, "T")
    p_runs = collect(p_ids, "P")

    excluded = [{"run_id": rid, "reason": args.exclude_reason} for rid in sorted(excluded_ids)]
    report = analyze(
        t_runs, p_runs, seed=args.seed, n_boot=args.bootstrap_n,
        validation_only=args.validation_only, excluded=excluded,
    )

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    out_md.write_text(render_markdown(report), encoding="utf-8")

    wp = report["primary"]["win_probability"]
    print("", flush=True)
    if "VALIDATION_ONLY" in report:
        print(f"*** {report['VALIDATION_ONLY']} ***", flush=True)
    print("=== PRIMARY: P(P outranks T) ===", flush=True)
    print(f"  {_fmt(wp.get('point'))} [{_fmt(wp.get('lo'))}, {_fmt(wp.get('hi'))}]  "
          f"({'excludes' if wp.get('excludes_0p5') else 'straddles'} 0.5; "
          f"{wp.get('direction')})", flush=True)
    print(f"  victory rate: T={_fmt(report['secondaries']['T']['victory_rate'])} "
          f"P={_fmt(report['secondaries']['P']['victory_rate'])}", flush=True)
    print(f"json: {out_json}", flush=True)
    print(f"md  : {out_md}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
