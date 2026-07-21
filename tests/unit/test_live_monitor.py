import json
from pathlib import Path

from trainer.evaluation.live_monitor import build_run_snapshot, read_events, render_markdown


def event(seq, kind, payload, ts_ms=None):
    return {
        "run_id": "run_test",
        "seq": seq,
        "ts_ms": seq * 500 if ts_ms is None else ts_ms,
        "event": kind,
        "payload": payload,
    }


def test_snapshot_flags_early_combine_and_off_plan_guns():
    events = [
        event(1, "run_start", {"policy_version": "v1", "weapon": "weapon_smg_1"}),
        event(2, "purchase_decision", {"action": {"type": "shop_buy", "item_id": "weapon_smg_1"}}),
        event(3, "purchase_decision", {"action": {"type": "shop_combine", "index": 0}}),
        event(4, "purchase_decision", {"action": {"type": "shop_buy", "item_id": "weapon_laser_gun_1"}}),
        event(5, "combat_tick", {"wave": 5, "hp": 20, "loot": 3, "debug": {"enemies": 8, "projectiles": 0}}),
    ]
    snapshot = build_run_snapshot(events, telemetry_age_sec=2)
    assert snapshot["wave"] == 5
    assert snapshot["severity"] == "warning"
    assert any("combined before six-slot fill" in alert for alert in snapshot["alerts"])
    assert any("weapon_laser_gun" in alert for alert in snapshot["alerts"])


def test_wave_rollups_and_markdown():
    events = [
        event(1, "run_start", {"policy_version": "v1"}),
        event(2, "combat_tick", {"wave": 1, "hp": 15, "debug": {"enemies": 2, "projectiles": 1}}),
        event(3, "player_damage", {"amount": 3, "hp": 12}),
        event(4, "combat_tick", {"wave": 1, "hp": 12, "debug": {"enemies": 7, "projectiles": 2}}),
    ]
    run = build_run_snapshot(events, telemetry_age_sec=1)
    assert run["waves"][0]["damage_taken"] == 3
    assert run["waves"][0]["max_enemies"] == 7
    text = render_markdown({"updated_at": "now", "game_running": True, "hud": {}, "run": run})
    assert "Recent waves" in text
    assert "| 1 | 15 | 12 | 12 | 3 | 7 | 2 |" in text


def test_final_shop_unspent_materials_alert():
    events = [
        event(1, "run_start", {"policy_version": "v1", "weapon": "weapon_smg_1"}),
        event(
            2,
            "purchase_decision",
            {
                "wave": 19,
                "gold_before": 17,
                "reroll_price": 22,
                "action": {"type": "shop_go"},
            },
        ),
    ]
    snapshot = build_run_snapshot(events, telemetry_age_sec=1)
    assert "final shop exited with 17 unspent materials" in snapshot["alerts"]
    assert snapshot["last_shop_actions"][-1]["wave"] == 19


def test_repeated_combine_in_one_shop_is_an_error():
    events = [
        event(1, "run_start", {"policy_version": "v47", "weapon": "weapon_smg_1"}),
        event(2, "purchase_decision", {"wave": 8, "action": {"type": "shop_combine"}}),
        event(3, "purchase_decision", {"wave": 8, "action": {"type": "shop_combine"}}),
    ]
    snapshot = build_run_snapshot(events, telemetry_age_sec=1)
    assert snapshot["severity"] == "error"
    assert "combine safety violated in shop wave(s): 8" in snapshot["alerts"]


def test_stale_shop_lock_is_reported_across_waves():
    locked = {
        "items": [
            {
                "id": "weapon_revolver_1",
                "locked": True,
                "affordable": True,
                "can_buy": False,
            }
        ]
    }
    events = [
        event(1, "run_start", {"policy_version": "v47"}),
        event(2, "combat_tick", {"wave": 12, "hp": 30, "debug": {}}),
        event(3, "purchase_offer", locked),
        event(4, "combat_tick", {"wave": 13, "hp": 31, "debug": {}}),
        event(5, "purchase_offer", locked),
    ]
    snapshot = build_run_snapshot(events, telemetry_age_sec=1)
    assert any(
        "weapon_revolver_1 (waves 12-13)" in alert
        for alert in snapshot["alerts"]
    )


def test_v48_reports_any_combine_as_safety_error():
    events = [
        event(
            1,
            "run_start",
            {"policy_version": "teacher_v1-0.1.48-gun-wp1"},
        ),
        event(
            2,
            "purchase_decision",
            {"wave": 3, "action": {"type": "shop_combine"}},
        ),
    ]
    snapshot = build_run_snapshot(events, telemetry_age_sec=1)
    assert snapshot["severity"] == "error"
    assert "zero-combine safety violated" in snapshot["alerts"]


def test_v57_reports_any_combine_as_safety_error():
    events = [
        event(1, "run_start", {"policy_version": "teacher_v1-0.1.57-gun-wp1"}),
        event(2, "purchase_decision", {"wave": 8, "action": {"type": "shop_combine"}}),
    ]
    snapshot = build_run_snapshot(events, telemetry_age_sec=1)
    assert snapshot["severity"] == "error"
    assert "zero-combine safety violated" in snapshot["alerts"]


def test_v58_reports_combine_and_cooldown_floor_item_as_safety_errors():
    events = [
        event(1, "run_start", {"policy_version": "teacher_v1-0.1.58-gun-wp1"}),
        event(2, "purchase_decision", {"wave": 8, "action": {"type": "shop_combine"}}),
        event(
            3,
            "purchase_decision",
            {
                "wave": 9,
                "action": {"type": "shop_buy", "item_id": "item_ball_and_chain"},
            },
        ),
    ]
    snapshot = build_run_snapshot(events, telemetry_age_sec=1)
    assert snapshot["severity"] == "error"
    assert "zero-combine safety violated" in snapshot["alerts"]
    assert "cooldown-floor item purchased: item_ball_and_chain" in snapshot["alerts"]


def test_v59_accepts_deferred_visible_mouse_combine_after_confirmation():
    events = [
        event(1, "run_start", {"policy_version": "teacher_v1-0.1.59-gun-wp1"}),
        *[
            event(
                index + 2,
                "purchase_decision",
                {"wave": index + 1, "action": {"type": "shop_buy", "item_id": "weapon_smg_1"}},
            )
            for index in range(5)
        ],
        event(7, "purchase_decision", {"wave": 8, "action": {"type": "shop_combine"}}),
        event(
            8,
            "shop_combine_dispatched",
            {"wave": 8, "executor": "deferred_core_combine", "mouse_mode": "visible"},
        ),
        event(
            9,
            "shop_combine_confirmed",
            {
                "wave": 8,
                "wait_ms": 1000,
                "state_changed": True,
                "executor": "deferred_core_combine",
                "mouse_mode_restored": True,
            },
            ts_ms=2000,
        ),
    ]
    snapshot = build_run_snapshot(events, telemetry_age_sec=1)
    assert not any("paced combine safety violated" in alert for alert in snapshot["alerts"])
    assert snapshot["severity"] != "error"


def test_v59_rejects_combine_without_safe_dispatch():
    events = [
        event(1, "run_start", {"policy_version": "teacher_v1-0.1.59-gun-wp1"}),
        event(2, "purchase_decision", {"wave": 8, "action": {"type": "shop_combine"}}),
        event(
            3,
            "shop_combine_confirmed",
            {
                "wave": 8,
                "wait_ms": 1000,
                "state_changed": True,
                "executor": "deferred_core_combine",
                "mouse_mode_restored": True,
            },
            ts_ms=2000,
        ),
    ]
    snapshot = build_run_snapshot(events, telemetry_age_sec=1)
    assert snapshot["severity"] == "error"
    assert any("lacked safe dispatch" in alert for alert in snapshot["alerts"])


def test_v64_keeps_deferred_combine_safety_enforcement():
    events = [
        event(1, "run_start", {"policy_version": "teacher_v1-0.1.64-gun-wp1"}),
        event(2, "purchase_decision", {"wave": 8, "action": {"type": "shop_combine"}}),
        event(
            3,
            "shop_combine_confirmed",
            {
                "wave": 8,
                "wait_ms": 1000,
                "state_changed": True,
                "executor": "deferred_core_combine",
                "mouse_mode_restored": True,
            },
            ts_ms=2000,
        ),
    ]
    snapshot = build_run_snapshot(events, telemetry_age_sec=1)
    assert snapshot["severity"] == "error"
    assert any("lacked safe dispatch" in alert for alert in snapshot["alerts"])


def test_v65_accepts_one_safeguarded_final_shop_combine():
    events = [
        event(
            1,
            "run_start",
            {
                "policy_version": "teacher_v1-0.1.65-gun-wp1",
                "weapon": "weapon_smg_1",
            },
        ),
        *[
            event(
                index + 2,
                "purchase_decision",
                {
                    "wave": index + 1,
                    "action": {"type": "shop_buy", "item_id": "weapon_smg_1"},
                },
            )
            for index in range(5)
        ],
        event(7, "purchase_decision", {"wave": 19, "action": {"type": "shop_combine"}}),
        event(
            8,
            "shop_combine_dispatched",
            {"wave": 19, "executor": "deferred_core_combine", "mouse_mode": "visible"},
        ),
        event(
            9,
            "shop_combine_confirmed",
            {
                "wave": 19,
                "wait_ms": 1000,
                "state_changed": True,
                "executor": "deferred_core_combine",
                "mouse_mode_restored": True,
            },
            ts_ms=5000,
        ),
    ]
    snapshot = build_run_snapshot(events, telemetry_age_sec=1)
    assert "final-shop combine safety violated" not in snapshot["alerts"]
    assert not any("paced combine safety violated" in alert for alert in snapshot["alerts"])
    assert snapshot["severity"] != "error"


def test_v59_rejects_combine_confirmation_timeout():
    events = [
        event(1, "run_start", {"policy_version": "teacher_v1-0.1.59-gun-wp1"}),
        *[
            event(
                index + 2,
                "purchase_decision",
                {"wave": index + 1, "action": {"type": "shop_buy", "item_id": "weapon_smg_1"}},
            )
            for index in range(5)
        ],
        event(7, "purchase_decision", {"wave": 8, "action": {"type": "shop_combine"}}),
        event(
            8,
            "shop_combine_dispatched",
            {"wave": 8, "executor": "deferred_core_combine", "mouse_mode": "visible"},
        ),
        event(
            9,
            "shop_combine_confirmation_timeout",
            {"wave": 8, "wait_ms": 5000, "mouse_mode_restored": True},
            ts_ms=6000,
        ),
    ]
    snapshot = build_run_snapshot(events, telemetry_age_sec=1)
    assert snapshot["severity"] == "error"
    assert any("confirmation timed out" in alert for alert in snapshot["alerts"])


def test_v51_rejects_shop_action_before_combine_confirmation():
    events = [
        event(1, "run_start", {"policy_version": "teacher_v1-0.1.51-gun-wp1"}),
        event(2, "purchase_decision", {"wave": 8, "action": {"type": "shop_combine"}}),
        event(3, "purchase_decision", {"wave": 8, "action": {"type": "shop_reroll"}}),
    ]
    snapshot = build_run_snapshot(events, telemetry_age_sec=1)
    assert snapshot["severity"] == "error"
    assert any("acted before combine confirmation" in alert for alert in snapshot["alerts"])


def test_v51_accepts_delayed_changed_state_confirmation():
    events = [
        event(1, "run_start", {"policy_version": "teacher_v1-0.1.51-gun-wp1"}),
        event(2, "purchase_decision", {"wave": 8, "action": {"type": "shop_combine"}}),
        event(
            3,
            "shop_combine_confirmed",
            {"wave": 8, "wait_ms": 1000, "state_changed": True},
            ts_ms=2000,
        ),
        event(4, "purchase_decision", {"wave": 8, "action": {"type": "shop_reroll"}}),
    ]
    snapshot = build_run_snapshot(events, telemetry_age_sec=1)
    assert not any("paced combine safety violated" in alert for alert in snapshot["alerts"])


def test_v55_rejects_final_shop_combine():
    events = [
        event(1, "run_start", {"policy_version": "teacher_v1-0.1.55-gun-wp1"}),
        event(2, "purchase_decision", {"wave": 19, "action": {"type": "shop_combine"}}),
        event(
            3,
            "shop_combine_confirmed",
            {"wave": 19, "wait_ms": 1000, "state_changed": True},
            ts_ms=2000,
        ),
    ]
    snapshot = build_run_snapshot(events, telemetry_age_sec=1)
    assert snapshot["severity"] == "error"
    assert "final-shop combine safety violated" in snapshot["alerts"]


def test_v50_allows_one_carryover_visit_but_rejects_two():
    locked = {
        "items": [
            {
                "id": "weapon_revolver_1",
                "locked": True,
                "affordable": False,
                "can_buy": False,
            }
        ]
    }
    events = [
        event(1, "run_start", {"policy_version": "teacher_v1-0.1.50-gun-wp1"}),
        event(2, "combat_tick", {"wave": 4, "hp": 20, "debug": {}}),
        event(3, "purchase_offer", locked),
        event(4, "combat_tick", {"wave": 5, "hp": 20, "debug": {}}),
        event(5, "purchase_offer", locked),
    ]
    allowed = build_run_snapshot(events, telemetry_age_sec=1)
    assert not any("shop lock persisted" in alert for alert in allowed["alerts"])

    events.extend(
        [
            event(6, "combat_tick", {"wave": 6, "hp": 20, "debug": {}}),
            event(7, "purchase_offer", locked),
        ]
    )
    violated = build_run_snapshot(events, telemetry_age_sec=1)
    assert violated["severity"] == "error"
    assert any("waves 4-6" in alert for alert in violated["alerts"])


def test_expired_lock_cannot_be_relocked_in_the_same_visit():
    events = [
        event(1, "run_start", {"policy_version": "teacher_v1-0.1.50-gun-wp1"}),
        event(
            2,
            "purchase_decision",
            {
                "wave": 14,
                "action": {
                    "type": "shop_unlock",
                    "item_id": "item_bloody_hand",
                    "lock_expired": True,
                },
            },
        ),
        event(
            3,
            "purchase_decision",
            {
                "wave": 14,
                "action": {"type": "shop_lock", "item_id": "item_bloody_hand"},
            },
        ),
    ]
    snapshot = build_run_snapshot(events, telemetry_age_sec=1)
    assert snapshot["severity"] == "error"
    assert any("expired shop lock immediately re-locked" in alert for alert in snapshot["alerts"])


def test_lock_created_before_same_visit_expiry_is_not_reported_as_relock():
    events = [
        event(1, "run_start", {"policy_version": "teacher_v1-0.1.52-gun-wp1"}),
        event(
            2,
            "purchase_decision",
            {"wave": 4, "action": {"type": "shop_lock", "item_id": "item_banner"}},
        ),
        event(
            3,
            "purchase_decision",
            {
                "wave": 4,
                "action": {
                    "type": "shop_unlock",
                    "item_id": "item_banner",
                    "lock_expired": True,
                },
            },
        ),
    ]
    snapshot = build_run_snapshot(events, telemetry_age_sec=1)
    assert not any("immediately re-locked" in alert for alert in snapshot["alerts"])


def test_read_events_keeps_valid_lines():
    path = Path(__file__).resolve().parents[1] / "fixtures" / "_tmp" / "live_monitor_events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(json.dumps(event(1, "run_start", {})) + "\nnot-json\n", encoding="utf-8")
        events, warnings = read_events(path)
        assert len(events) == 1
        assert len(warnings) == 1
    finally:
        path.unlink(missing_ok=True)
