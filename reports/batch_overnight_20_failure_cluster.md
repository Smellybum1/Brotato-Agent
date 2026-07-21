# Overnight batch failure cluster (batch_overnight_20)

Gate: **6/20 wins** (need ≥18). Date: 2026-07-18.

## Defeat wave buckets (14 losses)

| Band | Count | Notes |
|---|---:|---|
| 6–10 | 4 | Often elite-density (wave 9–10); 30–57 nearby enemies at death |
| 16–19 | 8 | Dominant cluster; contact swarms, 20–65 nearby enemies |
| 20 | 2 | Boss wave; high projectile counts (≈30) on some ticks |

## Mechanism

- Deaths are **contact-swarm collapses**, not automation hangs (0 hangs, 0 illegal meta).
- Shop is buying/rerolling normally; `materials_spent=0` in summaries is a telemetry counter bug, not no-buy.
- `dodge_caution` was configured on profiles but **never applied** in `potential_field.gd`.

## Repair applied (v2 deploy)

1. Wire `dodge_caution` into contact radius, engage spring, projectile threat, and escape clearances.
2. Add pack-density repulsion for ≥8 enemies within 280px.
3. Suppress loot vacuum under dense packs.
4. Stronger global contact/engage constants.
5. Well-Rounded: longer kite (`engage_scale` 1.55), EHP bias 1.45, prefer gun/precise, dodge/HP tags.

Next gate: `batch_overnight_20_v2` (≥18/20).
