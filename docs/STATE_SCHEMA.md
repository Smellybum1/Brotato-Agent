# State Schema (v1.0.0)

Top-level snapshot fields:

```text
schema_version
run_id
policy_version
game_version
phase
wave
elapsed_wave_time (optional)
remaining_wave_time (optional)
player {x,y,hp,max_hp,speed}
weapons[]
enemies[] / bosses[] / projectiles[] / materials[] / consumables[] / crates[] / trees[]
arena {width,height}
shop {items, reroll_price, gold}
level_up {options}
crate_choice {item}
legal_actions
```

Combat entities include raw absolute coordinates and, when player is known, player-relative `nx`/`ny`.
Invalid/freed Godot objects are skipped via `is_instance_valid` checks.
