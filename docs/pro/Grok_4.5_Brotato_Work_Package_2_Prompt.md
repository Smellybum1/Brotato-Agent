# BrotatoAgent — Grok 4.5 Work Package 2
## Combat Laboratory and Learned Combat Controller

**Owner:** Tom  
**Director:** ChatGPT  
**Implementer:** Grok 4.5  
**Prepared:** 17 July 2026 (Australia/Brisbane)  
**Required predecessor:** Work Package 1 must be formally reported as PASS and tagged `wp1-baseline`  
**Fixed benchmark:** Well-Rounded, SMG, Danger 0, default 100% settings, Endless off, wave retries off  
**Track:** Instrumented game-state agent; this is not yet the human-observation track

---

## BEGIN DIRECTIVE FOR GROK 4.5

### 1. Role and autonomy contract

You are the lead implementation engineer for **BrotatoAgent Work Package 2**. Work autonomously through setup, coding, data collection, debugging, training, evaluation, repair, and documentation. Do not send routine progress reports, ask for approval after intermediate steps, or return merely because an experiment failed.

Return to the director only in one of two states:

1. **PASS:** every mandatory deliverable and acceptance criterion in this directive is satisfied; or
2. **HARD BLOCKER:** after at least three materially different, documented repair approaches, the package cannot proceed without a user credential, destructive or irreversible choice, new licensing decision, unavailable hardware, or essential information that cannot be obtained from the installed game, repository, source, telemetry, logs, runtime inspection, or controlled experiments.

The following are ordinary engineering work and are **not** hard blockers:

- A Python, package, CUDA, ONNX, Gymnasium, or Stable-Baselines3 compatibility problem
- No suitable Python already installed; install a compatible portable/local version
- A missing GPU, unsupported GPU backend, or training that must run on CPU
- IPC disconnects, stale actions, timeout handling, serialization bugs, or port conflicts
- Godot node/API changes, invalid/freed objects, reset nondeterminism, or imperfect seed control
- An observation encoder that initially loses information
- A behavior-cloning policy that drifts, oscillates, or dies
- PPO instability, weak reward shaping, poor hyperparameters, or catastrophic initial policies
- Failure to embed ONNX Runtime directly into Godot
- ONNX export/parity errors that can be repaired or replaced with a compatible export path
- An initial candidate that is worse than the teacher
- Need for more demonstrations, DAgger rounds, scenario fixtures, tests, or refactoring
- A failed batch, individual crash, or useful stack trace
- Long training/evaluation time

Maintain local progress logs and checkpoints so work survives process or game crashes. Do not return a “status so far” message.

### 2. No-push and no-publish rule

Local commits, branches, and tags are required. Unless Tom or the director explicitly asks later:

- Do **not** run `git push`.
- Do **not** open a pull request.
- Do **not** publish a release.
- Do **not** upload or update a Steam Workshop item.
- Do **not** upload models, telemetry, screenshots, recovered assets, or reports to any external service.
- Do **not** add cloud training, remote telemetry, or non-loopback networking.

All model training and inference must be local. IPC must bind only to `127.0.0.1` or use an equally local mechanism such as a named pipe.

### 3. WP1 handoff gate — verify before starting training

Begin WP2 only after the final WP1 report says `Result: PASS`. Independently verify and record the following in `reports/wp2/wp1_handoff_audit.md` and a machine-readable `reports/wp2/wp1_handoff_manifest.json`:

1. The final WP1 batch contains exactly 20 valid, unattended, no-retry, non-Endless Well-Rounded/SMG/D0 runs.
2. At least 18 of 20 are victories.
3. There are zero automation hangs or indefinite loops.
4. There are zero illegal meta-game actions.
5. Every run has a valid terminal event and compact summary.
6. Raw telemetry passes the WP1 schema/sequence/completeness validator.
7. Successive-run chaining handles both victory and defeat.
8. Manual override and emergency stop were actually tested.
9. Save/configuration backup integrity is documented and the installed game/user data remain intact.
10. Bootstrap, deploy, launch, test, and report commands are documented.
11. Unit/integration tests pass from the documented clean-bootstrap state.
12. The repository is clean and locally tagged `wp1-baseline`, with commit hash recorded.

If any item fails, finish and repair WP1 first. Do not lower its gate, silently waive missing evidence, or train on an unaudited dataset. Failure of the overnight 20-run batch is not a reason to return to the director; continue WP1 failure clustering and repair cycles under the WP1 directive.

After the audit passes:

- Create local branch `wp2-combat-learning` from `wp1-baseline`.
- Freeze a read-only copy or checksum manifest of the WP1 report, configuration, telemetry schemas, teacher policy version, and benchmark summaries.
- Keep the WP1 teacher selectable and reproducible throughout WP2.

### 4. Director decisions for WP2

These decisions are fixed unless a genuine hard blocker forces a return:

1. **Scope is combat movement only.** The deterministic WP1 controller continues to own menus, shops, level-ups, crates, locks, rerolls, combines/sales, and run chaining.
2. **The first learned controller is instrumented.** It may use exact current in-engine state but may not use future spawn information, future shop contents, hidden future RNG outcomes, or altered game mechanics.
3. **Teacher first, then learning.** Build behavior cloning, perform DAgger-style corrective data collection, then train a bounded residual policy with PPO unless a benchmarked comparable algorithm is demonstrably superior after documented PPO attempts.
4. **Primary WP2 live deployment is a local Python/ONNX Runtime sidecar over loopback.** Do not make native ONNX embedding in Godot a milestone dependency. Native in-process inference is optional stretch work only.
5. **Teacher remains the safety fallback.** A timeout, malformed observation, non-finite action, stale sequence, disconnected sidecar, schema mismatch, or missed control deadline must hand control back to the deterministic teacher immediately.
6. **Use the proven WP1 ModLoader/deployment route.** Do not reopen the earlier deployment-path investigation unless the existing route actually stops working.
7. **Evaluation is paired and predeclared.** Select models on training/validation only. The final 100 combat episodes are sealed before final model selection and may not be used for tuning.
8. **Do not claim human-level performance.** WP2 creates a learned instrumented combat controller, not a fair screen-only agent and not a best-human result.

### 5. Mission

Build a repeatable combat laboratory and a learned movement controller that can operate in the live installed game, retain the full WP1 end-to-end run lifecycle, and equal or improve the deterministic teacher on held-out combat episodes without introducing severe failure modes.

The required learning sequence is:

```text
WP1 teacher telemetry
        -> combat dataset + scenario corpus
        -> behavior cloning baseline
        -> DAgger corrective rounds
        -> bounded residual PPO
        -> ONNX export + local sidecar
        -> paired held-out combat evaluation
        -> full-run D0 integration batch
```

### 6. Safeguards and benchmark integrity

All WP1 safeguards remain active. In addition:

- Do not overwrite Brotato originals or Tom’s normal save/configuration.
- Use an isolated agent configuration/profile where practical.
- Do not edit unlocks, progression, materials, health/damage multipliers, wave duration, enemy stats, drop rates, shop odds, reroll rules, or RNG to improve evaluation results.
- Training-only scenario construction and time acceleration are allowed, but final held-out evaluation and full-run evaluation must run at normal game speed and fixed default settings.
- Do not count retries, repeated favorable seeds, resumed waves, or manually rescued episodes.
- Do not omit candidate deaths, teacher deaths, crashes, fallback episodes, or outliers.
- Do not include copyrighted recovered game assets/source in git or model packages.
- Retain GPL-compatible attribution/licensing for the derived mod. Document licenses for all added Python dependencies.
- Put raw datasets, large checkpoints, recovered/local game material, temporary exports, and machine-specific paths under gitignored directories. Track small manifests, schemas, configs, summaries, and checksums.
- Set a configurable local disk budget and prune only redundant checkpoints after retaining the best, final, and diagnostically important failures. Never delete raw final-evaluation evidence.

### 7. Repository additions

Adapt the existing layout rather than duplicating WP1 modules. Add or complete this structure:

```text
BrotatoAgent/
  configs/
    wp2/
      well_rounded_d0_smg_combat_v1.yaml
      observation_v1.yaml
      reward_v1.yaml
      scenario_split_v1.yaml
  docs/
    COMBAT_LAB.md
    COMBAT_OBSERVATION_V1.md
    IPC_PROTOCOL.md
    TRAINING_PROTOCOL.md
    MODEL_REGISTRY.md
    WP2_EVAL_PROTOCOL.md
  mod/
    mods-unpacked/
      Tom-BrotatoAgent/
        adapter/
        teacher/
        learned/
          combat_bridge.gd
          learned_combat_controller.gd
          safety_fallback.gd
        lab/
          scenario_capture.gd
          scenario_runner.gd
          scenario_registry.gd
  trainer/
    bridge/
    data/
    env/
    models/
    imitation/
    dagger/
    rl/
    export/
    evaluation/
  data/                 # raw/processed large data gitignored
    manifests/          # small manifests/checksums tracked
    raw/
    processed/
    scenarios/
  models/               # large checkpoints/ONNX gitignored
    registry/           # small metadata manifests tracked
  tests/
    unit/
    integration/
    fixtures/
    parity/
  scripts/
    wp2_audit.*
    collect_combat_demos.*
    build_combat_dataset.*
    run_combat_lab.*
    train_bc.*
    run_dagger.*
    train_residual_ppo.*
    export_onnx.*
    evaluate_combat.*
    evaluate_wp2_full_runs.*
    build_wp2_report.*
  reports/
    wp2/
  runs/
    wp2/                 # large raw runs gitignored; summaries retained
```

Use platform-appropriate PowerShell/Python wrappers on Tom’s Windows machine. Every main operation must have a documented non-interactive command and meaningful exit code.

### 8. Stage A — Audit WP1 telemetry and freeze the combat interface

#### 8.1 Telemetry audit

Analyze all valid WP1 combat telemetry before choosing array sizes or model inputs. Produce:

- Tick frequency and missing-tick distribution
- Entity-count percentiles by wave for enemies, hostile projectiles, materials, consumables, crates, and obstacles
- Invalid/freed-object incidence
- Observation-to-action delay
- Teacher action magnitude/direction distribution
- Teacher field contribution distribution where available
- Damage, low-health, wall/corner, dense-projectile, charger, elite, and boss event counts
- Coverage by wave and terminal result
- Duplicate/near-duplicate state rate
- Estimated training-data size after cleaning

If required fields are missing, extend WP1 telemetry compatibly and collect additional teacher runs. Preserve the original schema and introduce a new schema version rather than mutating historical records.

#### 8.2 Versioned observation schema

Create `combat_obs_v1`, with an explicit schema hash and golden fixtures. It must use current state only and include at minimum:

**Global/player features**

- Normalized wave number, elapsed/remaining wave time, and control timestep
- Player-relative arena position and velocity
- HP, max HP, HP ratio, movement speed, armor/dodge and movement-relevant sustain/healing indicators
- Current and previous movement action
- Distances to arena boundaries and directional wall-clearance features
- Active weapon-set summary sufficient to infer preferred engagement range and attack rhythm
- Teacher movement vector and major teacher risk/attraction contributions when training a residual policy
- Observation age/sequence and valid-state flags

**Entity groups with masks**

- Enemies
- Hostile projectiles
- Materials
- Consumables
- Crates
- Trees/obstacles or other collision-relevant arena objects

For each applicable entity, include player-relative normalized position, relative velocity, radius/size, distance, bearing, type/threat identifier, health ratio where legitimately available, collision/contact or projectile threat information, and predicted time/closest approach features where reliable.

Determine capacities from WP1 percentiles rather than guesswork. When truncation is required:

- Use deterministic threat-aware ordering.
- Preserve the most imminent collision threats before merely nearest entities.
- Record dropped-entity counts and aggregate overflow summaries.
- Use explicit masks; padded rows must be provably inert.

Add one-step temporal context when measured bridge/action delay makes a single snapshot non-Markovian enough to harm control. A previous action and selected previous global/risk features are the minimum; use a short frame stack only if evidence supports it.

#### 8.3 Encoder tests

Tests must cover:

- Deterministic ordering
- Translation/player-relative invariance where intended
- Scale/range normalization
- Padding and masks
- Entity overflow/truncation
- Invalid/freed objects
- Empty entity groups
- NaN/Inf rejection
- Schema/hash mismatch
- Golden fixture stability
- Round-trip serialization
- Action range and radial clamping

Normalization statistics must be computed from the training split only and saved with the model. Do not leak validation or final-test statistics into training.

### 9. Stage B — Local bridge and combat laboratory

#### 9.1 Loopback bridge

Create a robust, versioned protocol between the Godot mod and local Python process. Use a compact length-prefixed format such as MessagePack or a rigorously framed JSON/binary equivalent. The protocol must include:

- Protocol/schema/model version handshake
- Run ID, episode ID, sequence number, and monotonic timestamp
- Observation and legal/action-validity flags
- Reset/start/step/terminal/error messages
- Heartbeat and bounded reconnect
- Action deadline and stale-action rejection
- Explicit normal termination versus timeout truncation
- Sidecar/model health and model hash

Bind only to loopback. Reject non-loopback peers. A missing sidecar must never prevent the teacher from playing normally.

#### 9.2 Control rate

Benchmark 15, 20, and 30 decisions per second on representative late-wave states. Select the highest rate that leaves reliable game performance and inference margin; default to 20 Hz if results are equivalent. Record the selected control period in all model/evaluation manifests.

#### 9.3 Scenario system

Implement a scenario registry and reset runner using native game behavior. Support these tiers:

1. **Wave-start build snapshots:** reconstruct the player’s wave, stats, weapons, and relevant inventory from valid teacher runs, then run the normal wave.
2. **Mid-wave combat snapshots:** restore enough current entities/player state to recreate diagnostic states where the game APIs permit it.
3. **Scenario families:** when exact restoration or RNG replay is impossible, recreate a fixed initial build and scenario parameters with recorded seeds/repetitions and evaluate distributionally.
4. **Targeted training-only micro-scenarios:** corners, projectile walls/crossfire, chargers, encirclement, low-health healing routes, wall escape, elite attacks, and boss patterns using the game’s native entities/resources. These may train and diagnose the controller but must be clearly labeled synthetic and excluded from claims about ordinary full-run frequency.

A scenario specification must record at least:

```text
scenario_schema_version
scenario_id
source_run/source_tick or synthetic provenance
category and difficulty stratum
game/mod/config/schema versions
character, weapon/build, danger, wave
player state
entity/spawn state or reconstruction parameters
RNG seed/state when available
normal-speed duration/termination rule
expected legal action space
checksum/hash
```

Do not serialize and commit copyrighted game resources. Store identifiers and runtime-reconstructable parameters only.

#### 9.4 Reset repeatability

For deterministic-capable scenarios, replay the same teacher action stream and compare state checksums. Target exact agreement; otherwise quantify divergence. Lack of perfect determinism is not a blocker: switch to paired scenario-family repetitions with the same initial parameters and report uncertainty.

The runner must complete at least five consecutive reset/run/terminal/reset cycles in each required category without game restart or stale state:

- Early ordinary combat
- Middle ordinary combat
- Late/dense combat
- Elite and/or boss combat
- Adversarial failure/low-health recovery combat

#### 9.5 Sealed splits

Before final candidate selection, create and checksum:

- Training scenario pool: at least 200 episodes/seeded instances spanning all categories
- Validation set: at least 50 episodes, never used for gradient updates
- Final held-out test set: exactly 100 episodes, 20 per category above

Split by source run and scenario family, not by individual rows/ticks. Related snapshots from the same source sequence must remain in one split. Store the final-test manifest and hash before final tuning begins; evaluation code must warn if it is accessed from a training command.

### 10. Stage C — Teacher demonstration dataset

Build a clean, versioned combat dataset from WP1 and additional teacher/scenario runs.

Mandatory dataset requirements:

- At least 200,000 valid control transitions after cleaning; collect more teacher runs if WP1 data is insufficient.
- At least 20 complete source runs and representation from every wave band: 1–5, 6–10, 11–15, 16–19, and wave 20.
- Coverage of all five scenario categories.
- Each row links observation, mask, teacher action, teacher reason/contributions, next observation, reward components where applicable, damage/events, terminal/truncated flags, and provenance.
- Recovery, menu, paused, invalid, stale, duplicated, or manually overridden ticks are excluded or explicitly labeled and masked from supervised loss.
- Exact duplicate runs/states do not dominate training.
- Rare severe states are retained and may be weighted, but sampling weights must be documented.
- Train/validation/test separation is enforced by source-run/scenario IDs.

Store raw append-only data separately from derived Parquet/array shards. Generate a dataset card containing schema hash, source hashes, counts, exclusions, distributions, known biases, and checksums.

### 11. Stage D — Behavior cloning baseline

#### 11.1 Model

Implement a compact entity-centric PyTorch policy suitable for CPU inference. Preferred architecture:

- Separate shared entity encoders for enemies, projectiles, pickups/healing, and obstacles
- Masked pooling or lightweight attention for each entity group
- Concatenation with global/player/weapon/teacher features
- Small policy trunk
- Two-dimensional `tanh` movement-action head in `[-1, 1]`
- Optional auxiliary heads for immediate risk, damage probability, or teacher field components when validation proves useful

Do not start with a giant recurrent or vision model. Keep parameter count and latency small. Any recurrence must be justified by measured partial observability or delay.

#### 11.2 Loss and training discipline

Use a documented combination of directional/cosine loss and magnitude Huber/MSE loss, with masks for invalid labels. Track angular error, cosine similarity, magnitude error, action saturation, and errors stratified by wave/scenario/risk.

- Seed Python, NumPy, PyTorch, data shuffling, and scenario generation where possible.
- Train at least three random seeds for the selected BC configuration.
- Select checkpoints using validation data only.
- Use early stopping and retain full configs, logs, environment lock, data manifest, git commit, and checkpoint hashes.
- A model that only predicts the global mean teacher direction is not acceptable.

Evaluate BC both offline and in validation scenarios before moving to final residual training. A catastrophic direct policy must fall back safely; repair it rather than exposing final full runs to an obviously broken checkpoint.

### 12. Stage E — DAgger-style corrective collection

Behavior cloning alone is vulnerable to compounding off-distribution errors. Perform at least two corrective rounds:

1. Run the current candidate in training scenarios with teacher actions queried on every state.
2. Use the candidate action unless the safety layer intervenes; log candidate, executed, and teacher actions separately.
3. Prioritize disagreement states, imminent-collision states, corner/wall states, oscillations, low-health routes, and states reached only by the candidate.
4. Add at least 25,000 valid new transitions per round unless a convergence analysis justifies a larger equivalent event-based corpus.
5. Retrain and compare on the unchanged validation set.

Do not contaminate the final 100-episode set. Record safety-intervention frequency and distinguish it from infrastructure fallback.

### 13. Stage F — Residual reinforcement learning

#### 13.1 Gymnasium environment

Create a standards-compliant custom environment around the combat lab. It must:

- Expose normalized observations and a symmetric continuous `Box(-1, 1, shape=(2,))` residual action.
- Apply the action as a bounded residual around the teacher:

```text
executed = radial_clamp(teacher_action + alpha * residual_action)
```

- Start with a conservative `alpha`, then increase it through curriculum only when validation safety permits.
- Distinguish `terminated` from `truncated` correctly.
- Pass Stable-Baselines3 `check_env` and random-action smoke tests.
- Use wrappers/monitoring that preserve true episode returns and lengths.
- Log every reward component and the unshaped outcome metrics.

#### 13.2 Reward design

Use configurable, normalized reward terms. The primary objective is survival/wave completion. A reasonable starting structure is:

- Large positive terminal reward for scenario/wave completion
- Large negative terminal reward for death
- Damage-taken penalty normalized by max HP
- Potential-based change in imminent-collision/clearance risk
- Small near-hit or dangerous-overlap penalty
- Small wall/corner entrapment penalty
- Small action-jitter penalty
- Small material/healing-route benefit only when it does not overpower survival
- Initial teacher-deviation regularization, annealed as the residual policy becomes safe

Do not reward hidden future information. Do not optimize only teacher-action similarity once RL begins. Audit for reward hacking such as stalling, wall hugging, refusing useful pickups, farming easy time, or exploiting truncation.

#### 13.3 Curriculum and randomization

Train progressively:

1. Early/middle ordinary scenarios with small residual bound
2. Late dense combat
3. Low-health recovery and known WP1 failure clusters
4. Elite/boss and projectile-pattern scenarios
5. Mixed full distribution with larger residual bound where safe

Randomize only within observed or explicitly documented game-realistic ranges: initial positions, spawn timing, entity counts, movement/projectile speed, build snapshots, control latency of zero/one tick, and selected player stats. Never randomize final held-out evaluation.

#### 13.4 PPO protocol

Use PPO as the default residual learner. Run a bounded, documented validation sweep rather than hand-selecting a lucky run. Train at least three seeds for the final configuration/family. Keep training, validation, and final-test scenarios separate.

If PPO remains clearly unsuitable after at least three materially different, well-diagnosed configurations, Grok may substitute a comparable continuous-control algorithm locally without asking first, provided:

- The reason is documented.
- The same observation/action/reward and held-out evaluation protocol are retained.
- Teacher fallback remains unchanged.
- The final report labels the substitution clearly.

Algorithm instability is not itself a hard blocker.

### 14. Stage G — ONNX export and live inference

#### 14.1 Export and parity

Export the selected policy to ONNX using an opset supported by the pinned local ONNX Runtime. Bundle no Python pickles as the only deployable artifact.

Run parity tests on at least 10,000 held-out observation fixtures, including empty groups, capacity overflow, high-risk states, and edge normalization values. Require:

- No NaN/Inf outputs
- Identical action range/clamping behavior
- Maximum absolute PyTorch-versus-ONNX action difference no greater than `1e-4`, unless a separately justified precision mode has a stricter behavior-level equivalence test
- Matching schema, normalization, and model hashes

#### 14.2 Local sidecar

Implement a non-interactive sidecar command that:

- Loads the pinned ONNX model and normalization manifest
- Binds to loopback only
- Performs protocol/schema/model handshakes
- Returns deterministic actions for deterministic mode
- Exposes health, model hash, and latency telemetry
- Shuts down cleanly when the game exits
- Reconnects only within bounded rules
- Requires no cloud account or service

CPU inference is the reference path. Optional GPU execution providers may be benchmarked, but the PASS model must have a reliable CPU path.

#### 14.3 Latency and fallback

Measure model-only and end-to-end observation-to-action latency on Tom’s machine with the final ONNX model under representative early, late, and boss loads.

Acceptance latency:

- Model-only p99 is at most 10 ms.
- End-to-end p99 is at most half the selected control period.
- At least 99.9% of actions arrive within one full control period.
- There are no runs of more than two consecutive missed action deadlines.

On any miss or invalidity, execute the teacher action for that tick. Log the cause. The game must remain fully playable if the sidecar is absent or killed mid-wave.

Distinguish:

- **Infrastructure fallback:** timeout, disconnect, stale/malformed data, NaN, version mismatch
- **Safety intervention:** learned action is valid but a predeclared emergency shield replaces/limits it
- **Residual teacher base:** expected use of the teacher vector in the residual formulation

Do not misreport residual control as a fully independent policy.

### 15. Stage H — Validation, ablations, and final evaluation

#### 15.1 Required validation comparisons

On the validation set, compare at least:

- WP1 teacher
- BC-only
- BC plus DAgger
- Final residual-RL candidate

Run at least two targeted ablations on no fewer than 30 fixed validation episodes each:

1. Remove predictive projectile/closest-approach features.
2. Remove either DAgger or risk-shaped reward/teacher regularization, whichever best tests the selected design.

Use ablations to explain design choices, not to tune on the final test set.

#### 15.2 Freeze before final test

Before opening the final 100-episode manifest for evaluation, freeze and checksum:

- Git commit
- Game/mod/config versions
- Observation and protocol schema hashes
- Dataset and normalization manifests
- Model/ONNX hashes
- Reward and policy configs
- Control rate and fallback rules
- Statistical analysis script
- Episode invalidation rules

No model or threshold changes are allowed after seeing final-test outcomes. A genuine infrastructure-invalid episode may be rerun only under predeclared rules and must remain listed with its reason.

#### 15.3 Paired 100-episode combat benchmark

Run both the WP1 teacher and final learned candidate on exactly the same 100 held-out scenario instances, 20 in each category:

- Early ordinary
- Middle ordinary
- Late/dense
- Elite and/or boss
- Adversarial failure/low-health recovery

Use normal game speed. Keep build, scenario parameters, episode duration, termination rules, and all non-combat decisions identical. Randomize or counterbalance execution order where practical to avoid thermal/order bias.

Record at minimum:

- Survival and scenario/wave completion
- Time alive
- Damage taken and damage per surviving second
- Minimum HP ratio
- Kills/damage dealt where reliable
- Materials/consumables/crates collected
- Near-collision events
- Wall/corner dwell and entrapment events
- Action oscillation/saturation
- Infrastructure fallbacks and safety interventions
- Model and end-to-end latency
- Crash/hang/invalid episode status

Report Wilson intervals for individual completion rates and a paired bootstrap or equivalent confidence interval for candidate-minus-teacher differences. Report raw per-episode outcomes, not only means.

#### 15.4 Combat non-inferiority gate

The learned candidate passes the combat comparison only when all are true:

1. Across 100 episodes, the candidate completion/survival count is at least the teacher count minus 3.
2. The paired 95% confidence-interval lower bound for the completion-rate difference is at least `-5` percentage points.
3. No category’s completion rate is more than 10 percentage points below the teacher.
4. There is no new severe recurrent failure mode: non-finite output, policy freeze, persistent oscillation, repeated corner suicide, projectile-pattern collapse, or systematic low-health pathing failure.
5. Among episodes completed by both policies, candidate damage per surviving second and near-collision rate are each no more than 10% worse than the teacher on the paired aggregate; report paired confidence intervals and analyze any trade-off.
6. Infrastructure fallback occurs on fewer than 0.5% of eligible control ticks.
7. Safety intervention occurs on fewer than 5% of eligible ticks, and no test episode is effectively teacher-only because the learned path failed.
8. The learned model is successfully queried on at least 99% of eligible combat ticks.
9. Residual actions are non-trivial and state-dependent; demonstrate that the model is not merely emitting zero while the teacher does all work.

Equality/non-inferiority is sufficient for M2, but any credible improvement must be highlighted with uncertainty rather than exaggerated.

#### 15.5 Full-run integration batch

After the combat gate passes, run exactly 20 new unattended full Well-Rounded/SMG/D0 runs with:

- Learned combat candidate active
- WP1 deterministic meta-game controller unchanged
- Default settings, normal game speed, no retries, Endless off
- Same watchdog, telemetry, terminal handling, and batch reporting standards as WP1

Required integration result:

- At least 18 victories out of 20
- Zero automation hangs
- Zero illegal meta-game actions
- Zero unreported sidecar/controller crashes
- Valid terminal event and summary for all 20 runs
- Telemetry validation passes
- Every fallback/intervention is counted

Do not silently revert whole difficult waves to teacher control. Tick-level predeclared fallback is permitted and must meet the rates above.

### 16. Mandatory WP2 PASS criteria

Work Package 2 is PASS only when every item below is true:

- WP1 handoff audit passes and `wp1-baseline` is preserved.
- Branch `wp2-combat-learning` contains the work, with no external push.
- `combat_obs_v1`, IPC protocol, action semantics, reward schema, scenario schema, and dataset schema are versioned and documented.
- Observation/encoder/action tests pass, including golden fixtures and invalid-object handling.
- The combat lab completes five consecutive reset cycles in every required category.
- Training, validation, and sealed 100-episode final-test splits are source-family separated and checksummed.
- The cleaned teacher dataset contains at least 200,000 valid transitions and required wave/category coverage.
- BC is trained with at least three seeds.
- At least two DAgger corrective rounds are completed.
- Residual PPO or an authorized evidence-based comparable algorithm is trained and evaluated with at least three final-family seeds.
- The Gymnasium environment passes `check_env`, random-action tests, and termination/truncation tests.
- ONNX export passes 10,000-fixture parity and non-finite tests.
- Local CPU sidecar, handshake, disconnect, timeout, stale-action, and teacher-fallback integration tests pass.
- Final model meets latency criteria.
- Required validation comparisons and two ablations are reported.
- The paired 100-episode combat gate passes with confidence intervals and complete raw outcome table.
- The 20-run full-game integration gate passes at 18/20 or better with zero hangs and complete telemetry.
- The WP1 teacher remains selectable and reproduces its baseline behavior within expected run variance.
- Manual override and emergency stop still work with the sidecar active and after the sidecar is killed.
- No evaluation-integrity shortcut or hidden game-setting change occurred.
- Tests pass from the documented local bootstrap/deploy process.
- Repository is clean and locally tagged `wp2-learned-combat`.

A merely trained model, good offline imitation score, attractive reward curve, or a few successful live waves is not a PASS.

### 17. Prohibited shortcuts

- Do not tune on the final 100 episodes.
- Do not randomly split adjacent ticks from the same run across train and test.
- Do not compare teacher and candidate on different builds or favorable scenario sets.
- Do not remove difficult episodes or losses.
- Do not alter the shop/build teacher to compensate for poor combat.
- Do not use future spawns, future RNG outcomes, future shop items, or inaccessible human-hidden future state.
- Do not change difficulty/accessibility settings, wave duration, enemy stats, player stats, drops, or mechanics for final evaluation.
- Do not count a safety/timeout teacher takeover as learned success without reporting it.
- Do not let the learned controller send menu/meta-game actions.
- Do not make native Godot ONNX embedding a prerequisite when the sidecar works.
- Do not treat perfect scenario determinism as mandatory when paired distributional evaluation is valid.
- Do not create simulated evidence or synthetic “live” logs.
- Do not push, publish, upload, or update Workshop content.
- Do not claim screen-only, human-level, expert-level, or best-human performance.

### 18. Required autonomous repair loop

When a candidate fails a gate:

1. Preserve the failing checkpoint, config, logs, and representative scenario IDs.
2. Cluster failures by mechanism rather than by superficial outcome.
3. Add or repair tests and scenario fixtures reproducing the dominant cluster.
4. Collect corrective teacher/DAgger data where relevant.
5. Change one documented model/reward/environment factor at a time where practical.
6. Re-evaluate on training/validation only.
7. Freeze a new candidate before re-entering final evaluation.

If the final 100-episode set exposes a failure and the model changes, that set becomes diagnostic and may not remain the untouched final test. Create and seal a new equivalent 100-episode final set with no shared source families, then rerun both teacher and candidate.

### 19. Final return format

Return one complete milestone report with exactly these 12 top-level sections:

1. **Result:** PASS or HARD BLOCKER
2. **WP1 handoff audit:** every prerequisite and frozen baseline hash/tag
3. **Environment and repository:** versions, machine capabilities, branch, commit, tag, dependency locks, licenses, and confirmation of no push
4. **Combat laboratory:** bridge, scenario tiers, reset repeatability, determinism findings, and split manifests
5. **Observation/action/reward design:** schemas, capacities, normalization, residual formulation, and safety rules
6. **Dataset:** source runs, transition counts, coverage, exclusions, split leakage checks, DAgger rounds, and manifest hashes
7. **Training:** BC and residual-RL configs, seeds, curves, checkpoint selection, compute path, and reproducibility commands
8. **Model deployment:** ONNX parity, sidecar commands, latency percentiles, disconnect/fallback tests, and model hashes
9. **Validation and ablations:** teacher/BC/DAgger/RL comparisons and required ablations
10. **Final evaluations:** complete paired 100-episode table/statistics plus complete 20-run full-game table and aggregate metrics
11. **Failures and limitations:** every final loss, fallback/intervention analysis, repaired failure clusters, and material unresolved limitations
12. **Artifacts and WP3 recommendation:** exact paths to reports/configs/logs/checkpoints/manifests plus a concrete recommendation for the learned economy/build planner

For `HARD BLOCKER`, also include:

- The exact smallest decision or resource needed
- Three materially different attempted solutions and their evidence
- Full relevant logs/stack traces/protocol captures
- What work was completed despite the blocker
- A safe fallback that preserves WP1 functionality and WP2 artifacts

Do not bundle unrelated questions.

## END DIRECTIVE FOR GROK 4.5
