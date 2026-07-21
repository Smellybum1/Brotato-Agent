# Evaluation Protocol (WP1)

## Fixed config

- Character: Well-Rounded (`character_well_rounded`)
- Starting weapon: SMG if offered else Stick
- Danger: 0; multipliers 100%; Endless off; wave retry off

## Ladder

1. Unit tests
2. Dry-run fixtures
3. Five launch/load/exit smoke cycles
4. One unattended D0 run
5. Five unattended D0 runs
6. Twenty-run final batch

## Pass gate

- Exactly 20 valid no-retry non-Endless runs
- ≥18 victories
- Zero hangs / indefinite loops
- Zero illegal meta actions
- Valid terminal event + summary per run
- Telemetry validation passes

Do not delete outliers. Do not count retries as wins.
