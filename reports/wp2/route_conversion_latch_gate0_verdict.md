# §44 — Safety-revalidated route-conversion latch Gate 0 verdict

**Verdict: `DATA_LIMITED`.** The conservative archive lower bound fails the temporal bars, but the
archive observes only 75.63% of active future captures against the preregistered 90% adequacy bar.
The latch is not closed. No mod edit, deploy, game launch, or new run was part of this gate.

Pre-registration: `route_conversion_latch_gate0_prereg.md`, commit `6af02d4`, before the stateful
replay was computed. Analyzer/tests: commit `dfebc1d`, also before execution. Full result:
`route_conversion_latch_gate0_result.json`.

## Controls first

All fixed controls passed before latch results:

| control | result |
|---|---:|
| expected/valid route-score runs | **8/8** |
| fresh captures | **65,662/65,662** |
| stale / non-increasing / parse failures | **0/65,662 / 0/65,662 / 0/65,662** |
| §40 analysis set | **23,501** |
| vector reconstruction | **23,509/23,722 = 99.10%** |
| floor reconstruction | **23,722/23,722 = 100%** |
| admission reconstruction | **23,502/23,509 = 99.97%** |
| selection reconstruction | **23,501/23,502 = 99.996%** |
| stateless §41 guarded flips | **11,457/23,501**, exact |
| stateless §40 unguarded flips | **15,274**, exact |
| disabled-policy changes | **0/23,501** |

Every run supplied both stateful triggers and non-triggers. All **8,469/8,469** retained future
steps passed each of the projectile, body-retention, subcritical, enemy-slack, and 15.1° checks.
The state-machine/inherited checks passed 18 focused unit tests plus the §40 and §41 embedded
self-tests.

## The blocking measurement

Only **9,400/12,429 = 75.63%** of fresh captures encountered while a latch was active carried a
reconstructable candidate set. The preregistered adequacy bar for a closing failure was 90%.
Per-run observability was consistently low at 72.67–76.70%; this is not one bad archive member.

Release reasons expose the mechanism:

| release | episodes |
|---|---:|
| unobservable `baseline_kept` | **2,854/4,039** |
| no safe candidate within 15.1° | **931/4,039** |
| unobservable ranked/reconstruction exclusion | **158/4,039** |
| reached horizon | **73/4,039** |
| unobservable no-threats | **17/4,039** |
| missed future window | **6/4,039** |

The v129 route instrument records candidate rows only after the ranking loop is reached.
`baseline_kept` returns before that recording loop, even though raw candidate geometry has already
been computed in the mod. Conservatively releasing there measures instrument reach, not candidate
unavailability.

## Conservative lower-bound result

With every unobservable capture forced to release:

- **4,039** stateful latch episodes;
- duration p10/median/p90 **0.051 / 0.102 / 0.349 s**;
- **587/4,039 = 14.53%** lasted at least 0.30 s;
- **73/3,985 = 1.83%** future-eligible episodes reached 0.60 s;
- all 8/8 runs contributed a horizon episode, but leave-one-run-out rates were only
  1.68–1.98%, far below the 20%/25% bars.

Those temporal bars fail, but under the frozen decision rule low observability makes the verdict
`DATA_LIMITED`, not `FAIL`.

## Positive controls and reported context

The visible portion shows that the latch is neither vacuous nor a disguised copy of current routing:

- retained future overrides: **7,548/8,469 = 89.13%** against the ≥20% authority bar;
- retained-heading error p10/median/p90: **0° / 0° / 15.0°**;
- retained body ratio p10/median/p90: **0.849 / 1.000 / 1.492**;
- current projected in-range delta p10/median/p90: **0.000 / 0.154 / 0.467**;
- retained versus recorded-command angle p10/median/p90: **0° / 105° / 165°**;
- first-trigger projected gain median: **0.182**.

These do not rescue the gate. They show only that when candidate rows are visible, the proposed latch
often has safe, materially different command authority.

## Independent reproduction

A separate stateful enumeration that imported only the already-validated §40/§41 reconstruction,
not the §44 analyzer, reproduced exactly: 4,039 episodes; 9,400/12,429 observability; 8,469 retained;
7,548 overrides; duration median 0.102; 587 ≥0.30-second episodes; 73/3,985 horizon reaches; and all
six release counts.

## Licensed next step

Per the preregistration, `DATA_LIMITED` licenses only a **default-inert all-exit revalidation
instrument** and a fixed telemetry-acquisition protocol. The smallest useful instrument records the
already-computed 24 raw candidate rows plus the current projectile floor and incumbent body reference
before `baseline_kept` returns. It must not alter the selected route or emitted action, and positive
and negative-arm parity must prove that.

§44 does not license latch implementation, a treatment comparison, a mediator claim, or a survival
campaign. A new acquisition must first raise active-future observability above the fixed bar and rerun
the same §44 mechanism boundaries without retuning them.
