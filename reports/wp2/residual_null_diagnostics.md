# WP2 Stage F Phase 2 -- residual near-zero-collapse diagnostics

Device: cuda | pool transitions: 183343 (expected 183343, match=True) | states: 183408

Question: is the near-zero residual the critic's verdict (teacher locally optimal within +/-5 deg) or an artifact of the actor's L2-to-zero regularizer (lambda_0=0.01)?

## Diagnostic 1 -- regularizer ablation

All arms: exact pi2 pool, seed 2, 4000 steps, teacher-mix on, shared init + batch order; lambda_zero is the only difference. |z| and |delta| measured over all replay-pool state embeddings.

| lambda_0 | p99\|z\| | \|delta\| p50 (deg) | \|delta\| p90 | \|delta\| p99 | max\|delta\| |
|---|---|---|---|---|---|
| 0.01 (pi2 report) | 0.012826 | -- | -- | -- | -- |
| 0.0 | 1.557937 | 1.9589 | 4.0647 | 4.5754 | 4.9772 |
| 0.001 | 0.113850 | 0.0444 | 0.1416 | 0.5668 | 4.1690 |
| 0.01 | 0.024137 | 0.0058 | 0.0134 | 0.1207 | 2.2398 |
| 0.01 (deployed ckpt) | 0.012826 | 0.0034 | 0.0131 | 0.0641 | 1.6757 |

Interpretation: lambda_0 monotonically suppresses the residual: |delta| p99 = 4.575 deg at 0.0, 0.567 deg at 0.001, 0.121 deg at 0.01 (p99|z| = 1.558 / 0.114 / 0.024). With NO regularizer the actor moves well off the teacher (|delta| median 1.96 deg), so the near-zero residual at lambda_0=0.01 is produced BY the regularizer, not by an actor that fails to find a direction. The regularizer is NOT exonerated.

## Diagnostic 2 -- critic state-conditional advantage A*(s)

A*(s) = max_d Q1(s,d) - Q1(s,0), grid = 21 pts in [-5,+5] deg. Critic: re-fit pi2 critic: the joint-trained lambda=0.01 arm's twin critic (run_iterate does not checkpoint the critic; this reproduces the pi2 joint TD3 training on the same pool with a controlled seed). n_states=183408, mean|Q(s,0)|=0.07509 (return-unit scale).

Overall A*: p50=0.001263 p90=0.004361 p99=0.017785 max=0.279922
Fraction A* > (0.001,0.01,0.05) abs return: 0.5694, 0.0218, 0.0010
Mean |argmax delta| = 3.4800 deg; fraction argmax at 0 deg = 0.0319

### A* by_wave_band

| stratum | n | A* p50 | A* p90 | A* p99 | A* max | mean\|Q0\| | frac>0.01 |
|---|---|---|---|---|---|---|---|
| 1-5 | 29926 | 0.00126 | 0.00374 | 0.00670 | 0.03996 | 0.06291 | 0.0027 |
| 6-10 | 53516 | 0.00114 | 0.00370 | 0.00765 | 0.13699 | 0.06868 | 0.0046 |
| 11-15 | 58930 | 0.00122 | 0.00432 | 0.01472 | 0.17532 | 0.07562 | 0.0182 |
| 16-19 | 37172 | 0.00137 | 0.00507 | 0.02351 | 0.12402 | 0.08233 | 0.0311 |
| 20 | 3864 | 0.00642 | 0.02715 | 0.08834 | 0.27992 | 0.18055 | 0.3724 |

### A* by_risk_stratum

| stratum | n | A* p50 | A* p90 | A* p99 | A* max | mean\|Q0\| | frac>0.01 |
|---|---|---|---|---|---|---|---|
| 0.00-0.25 | 155446 | 0.00124 | 0.00417 | 0.01284 | 0.19968 | 0.07271 | 0.0154 |
| 0.25-0.50 | 21393 | 0.00127 | 0.00470 | 0.02439 | 0.27992 | 0.07954 | 0.0321 |
| 0.50-0.75 | 5953 | 0.00173 | 0.01214 | 0.04944 | 0.22328 | 0.11159 | 0.1154 |
| 0.75-inf | 616 | 0.00529 | 0.03726 | 0.06512 | 0.07907 | 0.16993 | 0.3815 |

Interpretation: The critic prefers a NONZERO delta for 96.8% of states (mean preferred |delta|=3.48 deg), so it does not certify the teacher as locally optimal -- but the gain is small in absolute return (A* median 0.0013, p99 0.0178, max 0.2799; mean|Q0|=0.0751). It is negligible in early/low-risk states and concentrates in the known-weak strata: wave 20 (A* p99 0.0883, 37% of states >0.01, mean|Q0| 0.181) and risk>=0.5 (0.75+ stratum A* p99 0.0651, 38% >0.01). These are the same strata where bc_v2 offline error is largest.

## Bookkeeping

Cumulative residual ticks (usable student states) across probe+pi1 pools: 183408 (probe 107390 + pi1 76018).
Transitions: probe 107340 + pi1 76003 = 183343.

Summary: The regularizer is the proximate cause of the near-zero residual, and the critic does not certify the teacher as locally optimal. Ablation: with lambda_0=0.0 the actor moves substantially off the teacher (|delta| median 1.96 deg, p99 4.58 deg, p99|z|=1.56); lambda_0=0.001 already suppresses it to |delta| p99 0.57 deg; lambda_0=0.01 pins it to p99|z|=0.024 (deployed pi2 0.0128). So lambda_0=0.01 monotonically overwhelms whatever value signal exists. That signal is small but real: the pi2 critic prefers a nonzero delta for 96.8% of states (mean preferred |delta|=3.48 deg) yet the gain is tiny in absolute return (A* median 0.0013, p99 0.0178, mean|Q0|=0.075). The advantage is negligible in early/low-risk states (w1-5 A* p99 0.0067) and concentrates where bc_v2 is weakest -- wave 20 (A* p99 0.088, 37% of states >0.01, mean|Q0| 0.18) and risk>=0.5 (0.75+ A* p99 0.065, 38% >0.01). Net: the collapse to ~0 is caused by lambda_0=0.01, not by an absence of critic-perceived advantage; but the suppressed advantages are small-magnitude and clustered in high-risk/late-wave pockets. Whether those pockets are genuine teacher-improvements or critic approximation error is not resolvable offline -- the live random-control checkpoint (design 6) would decide.
