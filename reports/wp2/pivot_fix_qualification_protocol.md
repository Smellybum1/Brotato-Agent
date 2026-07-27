# Pivot-fix qualification — PRE-REGISTERED

**Written and committed BEFORE trial 1.** The purpose is to convert an overwhelming but
UNPAIRED result into a qualified one, and then to flip `finale_pivot_projectiles` to
default-ON. Until that happens the shipped agent does not use the fix.

## What is already known, and why it is not sufficient

| | trials | victories | damage median |
|---|---|---|---|
| pivot fix ON (control arms + discovery) | 111 | **111 = 1.000** | **16** |
| pivot OFF, rate campaign (historical) | 63 | 41 = 0.651 | 64 |
| pivot OFF, v2 confirm campaign (historical) | 64 | 45 = 0.703 | 70.5 |

Mechanism is established independently: 84-91% of wave-20 damage had no cause in the
agent's state, the invoker control showed 0%, and closing the blind spot took it to 0.0%.

**Why it is still not sufficient:** the pivot-OFF numbers come from DIFFERENT BUILDS and
different sessions. Build/session drift has never been ruled out by a paired test. The
project has been burned once by a strong-looking unpaired result (finale v2 campaign 1),
and the rule is that the comparison must be same-build and pre-registered.

## Arms

| arm | flags |
|---|---|
| control | *(none)* — the shipped default |
| treatment | `--finale-pivot-projectiles` |

Same build (0.2.48), same 8 fixtures, arms alternating in rounds so drift cannot align
with an arm.

## Primary metric: VICTORY RATE — and here that is the right choice

The co-rotation and ring-radius campaigns used damage because their control arm was
pinned at the ceiling (64/64) and win rate had no room to move. **That does not apply
here**: the control arm is the agent WITHOUT the fix, historically ~0.65-0.70, so win
rate has ample room and is the outcome that actually matters.

Damage taken is recorded as a strong SECONDARY (expected ~64 -> ~16).

## Design and decision rule — FIXED NOW

8 fixtures x 4 trials x 2 arms = **64 trials**, ~1.2 h. Smaller than the previous
campaigns on purpose: the expected effect is ~0.67 -> ~1.00, and 32/arm detects that
with near-certainty. (Contrast the ~19 pp effects earlier in this project, where 64/arm
gave only 61% power — the error I made and corrected on 2026-07-27.)

**PASS requires BOTH:**
1. Pooled Fisher exact **p < 0.05**
2. Treatment victory rate **>** control victory rate

**If it passes, `finale_pivot_projectiles` flips to DEFAULT-ON** and the mod ships with
it. That is the point of this campaign; it is not another candidate-gathering exercise.

If it fails, the flag stays off and the 111/111 result must be treated as a
build-confounded artifact, however implausible that looks now.

## Validity gate — checked first, can VOID

- 0 arm mismatches; every trial's recorded `finale_pivot_projectiles` matches its arm.
- **Treatment must show `enemy_projectile_rotating.gd` in the capture stream; control
  must show ZERO.** This is a structural signature the control arm cannot fake — 0 in
  426,116 control observations historically. If it does not separate, the campaign is
  VOID.
- Infrastructure-invalid trials (e.g. `game_exited_before_summary`) are excluded and
  reported with a worst-case sensitivity, not treated as arm compromise.

## Stated in advance

The expected result is a large, obvious win. **If the control arm comes in far above its
historical ~0.67** — say near 1.00 — that would mean something OTHER than the fix
improved the agent between builds, and the 111/111 attribution is wrong. That is the
specific way this campaign can surprise us, and it is the reason to run it.
