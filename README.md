# BrotatoAgent

Instrumented deterministic agent for Brotato (Work Package 1 teacher baseline).

**License:** GPL-3.0 (derived from [brotato-full-autobot](https://github.com/HelpFreedom/brotato-full-autobot)). See `LICENSE` and `docs/THIRD_PARTY_NOTICES.md`.

## Benchmark config

Well-Rounded · SMG (else Stick) · Danger 0 · 100% multipliers · Endless off · no wave retry.

## Quick start

```powershell
cd "path\to\Brotato Agent"   # repo root
git submodule update --init --recursive
python scripts\bootstrap.py
.\.venv\Scripts\python.exe scripts\discover_install.py
.\.venv\Scripts\python.exe scripts\backup_user_data.py
.\.venv\Scripts\python.exe scripts\deploy_mod.py --target agent
.\.venv\Scripts\python.exe scripts\launch_benchmark.py
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.tmp\pytest-local
.\.venv\Scripts\python.exe scripts\run_batch.py --runs 20 --launch
.\.venv\Scripts\python.exe scripts\collect_results.py
.\.venv\Scripts\python.exe scripts\validate_telemetry.py
```

## Controls

- **F10** — toggle HUD
- Movement keys — manual override (disables agent for the run)
- **Ctrl+Shift+Q** — emergency stop

## Live monitoring

The read-only monitor can run beside an active gate without changing game or
agent state:

```powershell
.\.venv\Scripts\python.exe scripts\live_monitor.py
```

It refreshes `reports/live_monitor.json` and `reports/live_monitor.md` every
five seconds. The snapshot includes the current wave and HP trend, telemetry
freshness, recent wave damage/threat peaks, shop churn, weapon purchases, and
alerts for early combining or off-plan gun families. Use `--once` for a single
status snapshot.

For an active WP1 gate, read `reports/live_monitor.json` first and then run the
consolidated read-only infrastructure check:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check_gate_status.ps1
```

The command detects the active version from `reports/WP1_ACTIVE_GATE.md` and
reports the exact watchdog tasks/settings, scoped process trees, Brotato,
supervisor/HUD state, newest summary, and post-gate APPCRASH events as compact
JSON. It does not start, stop, or modify anything.

## Layout

See `docs/ARCHITECTURE.md`. Mod sources live in `mod/mods-unpacked/Tom-BrotatoAgent/`.
