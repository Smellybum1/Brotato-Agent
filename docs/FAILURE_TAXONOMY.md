# Failure Taxonomy

| Code | Meaning |
|------|---------|
| `combat_death` | Player died before wave 20 |
| `boss_fail` | Lost on wave 20 boss |
| `shop_stall` | Shop/upgrade UI did not advance |
| `menu_nav_fail` | Could not select character/weapon/danger |
| `no_movement` | Combat watchdog: no movement updates |
| `no_valid_phase` | Phase unknown too long |
| `unexpected_main_menu` | Returned to menu mid-run |
| `manual_override` | Human took control |
| `emergency_stop` | Ctrl+Shift+Q |
| `telemetry_fault` | Writer failures / incomplete run |
| `illegal_action` | Meta action rejected by legality mask |
| `automation_fault` | Terminal recovery exhaustion |
| `compat_break` | API/node mismatch vs game version |
