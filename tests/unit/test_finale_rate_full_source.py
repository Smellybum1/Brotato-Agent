"""Source-text pins for the rate-only finale arm (`finale_rate_full`).

The mod GDScript is never parsed by this suite, so source-text assertions are the
only guard available. This arm isolates the wave-20 control RATE (20 Hz -> 60 Hz)
from the movement POLICY change that finale v2 bundled with it.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/runtime/agent_controller.gd"
CONFIG = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/teacher/config.gd"
WRITER = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/telemetry/telemetry_writer.gd"


def _combat_func(src: str) -> str:
    return src.split("func _handle_combat", 1)[1].split("\nfunc ", 1)[0]


def test_flag_is_declared_default_false_and_read_from_config():
    src = CONTROLLER.read_text(encoding="utf-8")

    assert "var finale_rate_full: bool = false" in src
    assert 'if cfg.has("finale_rate_full"):' in src
    assert 'finale_rate_full = bool(cfg["finale_rate_full"])' in src


def test_divisor_constant_is_untouched_and_merely_bypassed():
    # The flag must not change the tuned v1 schedule for anyone else.
    config = CONFIG.read_text(encoding="utf-8")
    assert "const BOSS_FINALE_RECOMPUTE_DIVISOR := 3" in config


def test_recompute_gate_adds_the_arm_and_leaves_v1_arithmetic_intact():
    body = _combat_func(CONTROLLER.read_text(encoding="utf-8"))

    assert "elif finale_rate_full:" in body
    # The v1 branch is byte-identical and still the else.
    assert (
        "recompute_move = (_finale_move_tick % "
        "_CONFIG_SCRIPT.BOSS_FINALE_RECOMPUTE_DIVISOR) == 1"
    ) in body
    assert "else:\n\t\t\trecompute_move = (_finale_move_tick %" in body


def test_capture_override_excludes_both_full_rate_arms():
    body = _combat_func(CONTROLLER.read_text(encoding="utf-8"))

    # If the override applied on a full-rate arm, finale captures would run at
    # 60 Hz and control_dt_ms would drop ~50 ms -> ~16 ms under a dataset and a
    # student path both fixed at 20 Hz.
    assert (
        "if wave >= _CONFIG_SCRIPT.BOSS_FINALE_WAVE and not finale_v2 "
        "and not finale_rate_full:"
    ) in body
    assert "emit_capture = recompute_move" in body


def test_verification_counters_exist_reset_and_reach_the_summary():
    src = CONTROLLER.read_text(encoding="utf-8")
    body = _combat_func(src)

    assert "var finale_combat_ticks: int = 0" in src
    assert "var finale_recompute_ticks: int = 0" in src
    # Counted only on finale waves, inside the BOSS_FINALE_WAVE branch.
    assert "finale_combat_ticks += 1" in body
    assert "finale_recompute_ticks += 1" in body

    start_run = src.split("func _start_run", 1)[1].split("\nfunc ", 1)[0]
    assert "finale_combat_ticks = 0" in start_run
    assert "finale_recompute_ticks = 0" in start_run

    # end_run copies every extra key into the summary verbatim; begin_run's dict
    # is an allowlist, so the counters travel via end_run's extra dict.
    finish = src.split("func _finish_run", 1)[1].split("\nfunc ", 1)[0]
    assert '"finale_combat_ticks": finale_combat_ticks,' in finish
    assert '"finale_recompute_ticks": finale_recompute_ticks,' in finish


def test_writer_copies_extra_keys_and_seeds_the_counters():
    writer = WRITER.read_text(encoding="utf-8")

    # The mechanism the counters rely on.
    assert "for k in extra.keys():" in writer
    assert "summary[k] = extra[k]" in writer
    assert '"finale_rate_full": meta.get("finale_rate_full", false),' in writer
    assert '"finale_combat_ticks": 0,' in writer
    assert '"finale_recompute_ticks": 0,' in writer


def test_run_meta_and_sentinel_both_record_the_arm():
    src = CONTROLLER.read_text(encoding="utf-8")

    start_run = src.split("func _start_run", 1)[1].split("\nfunc ", 1)[0]
    assert '"finale_rate_full": finale_rate_full,' in start_run

    sentinel = src.split("func _write_mod_ready", 1)[1].split("\nfunc ", 1)[0]
    assert '"finale_rate_full": finale_rate_full,' in sentinel


def test_no_non_ascii_and_no_godot3_in_autoload_construct_added():
    src = CONTROLLER.read_text(encoding="utf-8")
    for line in src.splitlines():
        if "finale_rate_full" in line or "finale_recompute_ticks" in line:
            assert line.isascii(), line
