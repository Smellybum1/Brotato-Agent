from scripts.wp2_teacher_safety_audit import (
    _avoidable_damage_violations,
    _body_clearance,
    _body_projectile_floor_unavailable,
    _damage_rows,
    _hard_wall_faults,
    _projectile_route_clearance,
    _required_body_floor,
    _route_replay,
    _wall_body_relief_violation,
    _wall_recovery_progress_violation,
)


def _payload(*, x=500.0, y=500.0, action=(1.0, 0.0), speed=100.0, enemies=None):
    return {
        "player": {"x": x, "y": y, "speed": speed},
        "teacher": {"action": {"x": action[0], "y": action[1]}},
        "entities": {"enemies": enemies or [], "bosses": []},
        "arena": {"width": 2048.0, "height": 1536.0},
    }


def test_body_clearance_replays_the_final_emitted_action():
    payload = _payload(
        enemies=[{"x": 600.0, "y": 500.0, "vx": 0.0, "vy": 0.0, "radius": 10.0}]
    )

    assert abs(_body_clearance(payload) - 30.0) < 0.0001
    assert abs(_body_clearance(payload, legacy_sampled=True) - 30.0) < 0.0001


def test_v116_continuous_body_clearance_sees_fast_crossings():
    # Frozen v115 smoke capture 19557 (run_1784768114_34909). The horned
    # bruiser charged at ~940 u/s across the commanded down-left path; the
    # player was hit one capture later. Every recorded diagnostic read ~95
    # units because the 120 ms sample grid straddled the crossing.
    payload = _payload(
        x=1715.578613,
        y=320.020935,
        action=(-0.707107, 0.707107),
        speed=436.0,
        enemies=[
            {
                "x": 1673.89209,
                "y": 349.065704,
                "vx": 879.658691,
                "vy": -331.361664,
                "radius": 16.278799,
            }
        ],
    )

    legacy = _body_clearance(payload, legacy_sampled=True)
    continuous = _body_clearance(payload)

    assert abs(legacy - 95.305712) < 0.01
    assert continuous < 5.0


def test_v116_projectile_route_clearance_sees_straddled_bullets():
    # Frozen v115 smoke capture 20505. The emitted escape passed through a
    # stationary radius-23 bullet at t~56 ms; the t=0 and t=0.12 samples both
    # read ~28 units and the recorded escape clearance matched them.
    payload = _payload(x=1549.171997, y=818.717346, action=(0.258819, -0.965926), speed=504.0)
    payload["entities"]["projectiles"] = [
        {"x": 1554.74353, "y": 791.196716, "vx": 0.0, "vy": 0.0, "radius": 23.0}
    ]

    assert _projectile_route_clearance(payload) < 5.0


def test_v121_relief_floor_fallback_is_diagnosed_not_flagged():
    # Frozen v120 smoke capture 18555: relief floor 45 exceeded every sampled
    # lane (best 13.3) while the incoming command held 46.5; the runtime keeps
    # the baseline and must mirror it in the selected diagnostic.
    fallback = {
        "wall_body_relief_active": True,
        "body_safety_active": False,
        "body_emergency_active": False,
        "body_input_clearance": 46.465576,
        "body_best_clearance": 13.299061,
        "body_selected_clearance": 46.465576,
        "body_projectile_floor": 120.0,
        "body_selected_projectile_clearance": -1.0,
    }

    assert _body_projectile_floor_unavailable(fallback)
    # Without relief, mismatched input/best keeps the strict signature.
    assert not _body_projectile_floor_unavailable(
        {**fallback, "wall_body_relief_active": False}
    )
    # A best clearance above the contact tier is a real pool; no exemption.
    assert not _body_projectile_floor_unavailable(
        {**fallback, "body_best_clearance": 60.0}
    )


def test_v118_loot_dash_relaxes_only_the_pack_tier():
    ordinary = {"body_best_clearance": 200.0}
    dashing = {"body_best_clearance": 200.0, "loot_dash_active": True}

    # Ordinary route must stay within 20 of best (capped at 160).
    assert _required_body_floor(ordinary, True) == 160.0
    # A dash needs only the 45-unit contact floor.
    assert _required_body_floor(dashing, True) == 45.0
    # Emergencies still dominate the dash relaxation.
    emergency = {**dashing, "body_emergency_active": True}
    assert _required_body_floor(emergency, True) == 195.0


def test_v118_loot_dash_gates_bound_duration_and_hp(tmp_path):
    from scripts.wp2_teacher_safety_audit import audit_run
    import json

    def capture(seq, dash, hp=60):
        return {
            "event": "combat_capture",
            "ts_ms": 1000 + seq,
            "payload": {
                "capture_seq": seq,
                "observation_ts_ms": 1000 + seq,
                "wave": 12,
                "player": {"x": 1024.0, "y": 768.0, "speed": 400.0, "hp": hp, "max_hp": 100},
                "teacher": {
                    "action": {"x": 1.0, "y": 0.0},
                    "action_fresh": True,
                    "contributions": {"finale_translation": {"loot_dash_active": dash}},
                },
                "entities": {"enemies": [], "bosses": [], "projectiles": []},
                "arena": {"width": 2048.0, "height": 1536.0},
            },
        }

    # 27 consecutive dash captures exceed the 26-capture bound once; one dash
    # capture at 20 HP violates the HP floor.
    events = [capture(i, True) for i in range(1, 28)]
    events.append(capture(28, True, hp=20))
    events.append(capture(29, False))
    events.append({"event": "run_end", "ts_ms": 5000, "payload": {}})
    run_dir = tmp_path / "run_dash"
    run_dir.mkdir()
    (run_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
    )
    (run_dir / "summary.json").write_text(json.dumps({
        "telemetry_complete": True, "errors": 0, "hangs": 0,
        "illegal_actions": 0, "result": "victory", "last_wave": 20,
    }), encoding="utf-8")

    audit = audit_run(run_dir)
    reasons = [v["reason"] for v in audit["loot_dash_violations"]]
    assert "dash episode exceeded the runtime commit bound" in reasons
    assert "dash active below the HP floor" in reasons
    assert audit["loot_dash_capture_count"] == 28
    assert not audit["accepted"]


def test_v117_nonfresh_finale_captures_reject_the_run(tmp_path):
    from scripts.wp2_teacher_safety_audit import audit_run
    import json

    def capture(seq, fresh):
        return {
            "event": "combat_capture",
            "ts_ms": 1000 + seq,
            "payload": {
                "capture_seq": seq,
                "observation_ts_ms": 1000 + seq,
                "wave": 20,
                "player": {"x": 1024.0, "y": 768.0, "speed": 400.0},
                "teacher": {
                    "action": {"x": 1.0, "y": 0.0},
                    "action_fresh": fresh,
                    "contributions": {"finale_translation": {}},
                },
                "entities": {"enemies": [], "bosses": [], "projectiles": []},
                "arena": {"width": 2048.0, "height": 1536.0},
            },
        }

    events = [capture(1, False), capture(2, False),
              {"event": "run_end", "ts_ms": 2000, "payload": {}}]
    run_dir = tmp_path / "run_test"
    run_dir.mkdir()
    (run_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
    )
    (run_dir / "summary.json").write_text(json.dumps({
        "telemetry_complete": True, "errors": 0, "hangs": 0,
        "illegal_actions": 0, "result": "victory", "last_wave": 20,
    }), encoding="utf-8")

    audit = audit_run(run_dir)
    assert audit["nonfresh_finale_capture_count"] == 2
    assert not audit["accepted"]

    legacy = audit_run(run_dir, legacy_sampled=True)
    assert legacy["nonfresh_finale_capture_count"] == 0
    assert legacy["accepted"]


def test_v116_route_replay_flags_avoidable_projectile_crossing():
    payload = _payload(x=1549.171997, y=818.717346, action=(0.258819, -0.965926), speed=504.0)
    payload["entities"]["projectiles"] = [
        {"x": 1554.74353, "y": 791.196716, "vx": 0.0, "vy": 0.0, "radius": 23.0}
    ]

    replay = _route_replay(payload)

    assert replay is not None
    assert replay["emitted_projectile_clearance"] < 5.0
    # Every lane shares the current 28.08-unit distance at t=0, so the best
    # alternative equals it; the gate fires on the 20-unit relative gain.
    assert replay["best_projectile_clearance"] > 25.0

    row = {
        "projectile_escape_clearance": 28.078943,
        "projectile_final_clearance": 28.078943,
        "body_best_clearance": 131.970617,
        "body_selected_clearance": 160.144821,
        "route_replay": replay,
    }
    violations = _avoidable_damage_violations([row])

    assert violations and (
        "emitted route crossed a projectile path while a clearer sampled lane existed"
        in violations[0]["reasons"]
    )


def test_hard_wall_audit_checks_the_held_command_projection():
    payload = _payload(x=100.0, action=(-1.0, 0.0), speed=100.0)

    assert _hard_wall_faults(payload) == ["left"]


def test_wall_body_relief_audit_catches_a_held_route_through_a_pack():
    payload = _payload(
        x=500.0,
        y=1200.0,
        action=(1.0, 0.0),
        speed=463.0,
        enemies=[{"x": 600.0, "y": 1200.0, "vx": 0.0, "vy": 0.0, "radius": 20.0}],
    )
    payload.update({"wave": 20, "capture_seq": 20520})
    payload["entities"]["projectiles"] = []
    payload["teacher"]["contributions"] = {
        "finale_translation": {
            "wall_recovery_active": True,
            "projectile_safety_active": False,
            "body_selected_clearance": 30.0,
        }
    }

    violation = _wall_body_relief_violation(payload)

    assert violation is not None
    assert violation["capture_seq"] == 20520
    assert violation["relief_best"] >= 90.0


def test_wall_body_relief_audit_replays_held_action_not_stale_diagnostic():
    payload = _payload(
        x=500.0,
        y=1200.0,
        action=(1.0, 0.0),
        speed=463.0,
        enemies=[{"x": 100.0, "y": 1200.0, "vx": 0.0, "vy": 0.0, "radius": 20.0}],
    )
    payload.update({"wave": 20, "capture_seq": 20546})
    payload["entities"]["projectiles"] = []
    payload["teacher"]["contributions"] = {
        "finale_translation": {
            "wall_recovery_active": True,
            "projectile_safety_active": False,
            # Deliberately stale and dangerous; the current carried action is
            # already above the relief trigger and must be replayed instead.
            "body_selected_clearance": 10.0,
        }
    }

    assert _body_clearance(payload) >= 140.0
    assert _wall_body_relief_violation(payload) is None


def test_wall_progress_audit_accepts_active_bounded_body_relief():
    payload = _payload(x=300.0, action=(-1.0, 0.0), speed=100.0)
    payload.update({"capture_seq": 20547})
    payload["teacher"]["contributions"] = {
        "finale_translation": {
            "body_safety_active": True,
            "wall_recovery_active": True,
            "wall_body_relief_active": True,
        }
    }

    assert _wall_recovery_progress_violation(payload) is None
    payload["teacher"]["contributions"]["finale_translation"][
        "wall_body_relief_active"
    ] = False
    assert _wall_recovery_progress_violation(payload) is not None


def test_damage_audit_allows_only_the_bounded_projectile_concession():
    safe = {
        "projectile_escape_clearance": 100.0,
        "projectile_final_clearance": 40.0,
        "body_best_clearance": 70.0,
        "body_selected_clearance": 50.0,
    }
    unsafe = {**safe, "projectile_final_clearance": 39.0}

    assert _avoidable_damage_violations([safe]) == []
    assert _avoidable_damage_violations([unsafe])[0]["reasons"] == [
        "projectile concession exceeds 60 units"
    ]


def test_damage_audit_allows_unbounded_concession_only_for_best_body_emergency():
    best_available = {
        "projectile_escape_clearance": 98.0783,
        "projectile_final_clearance": 17.575,
        "body_best_clearance": 41.602264,
        "body_selected_clearance": 41.602264,
    }
    worse_pack_lane = {**best_available, "body_selected_clearance": 33.194206}

    assert _avoidable_damage_violations([best_available]) == []
    assert _avoidable_damage_violations([worse_pack_lane])[0]["reasons"] == [
        "projectile concession exceeds 60 units"
    ]


def test_body_emergency_audit_requires_near_best_escape():
    ordinary = {"body_best_clearance": 86.5}
    emergency = {"body_best_clearance": 86.5, "body_emergency_active": True}

    assert _required_body_floor(ordinary) == 45.0
    assert _required_body_floor(ordinary, True) == 66.5
    assert _required_body_floor(emergency) == 81.5


def test_v110_ordinary_body_tier_rejects_observed_worse_pack_lane():
    # Frozen v109 exact-20 run 2 capture 21282. Both lanes passed the active
    # projectile tier, but the emitted route gave away 57.7 units of body
    # clearance and was followed by a 20-damage hit one capture later.
    observed = {
        "wave": 20,
        "projectile_escape_clearance": 223.772247,
        "projectile_final_clearance": 304.690308,
        "body_best_clearance": 182.581696,
        "body_selected_clearance": 124.864822,
    }

    assert _required_body_floor(observed, True) == 160.0
    assert _avoidable_damage_violations([observed])[0]["reasons"] == [
        "selected body path missed the required near-best tier"
    ]


def test_v114_damage_review_includes_mid_campaign_pack_routes():
    events = [
        {
            "event": "combat_capture",
            "ts_ms": 612050,
            "payload": {
                "capture_seq": 11040,
                "wave": 12,
                "teacher": {
                    "contributions": {
                        "finale_translation": {
                            "projectile_safety_active": False,
                            "projectile_escape_clearance": -1.0,
                            "projectile_final_clearance": -1.0,
                            "body_best_clearance": 269.6,
                            "body_selected_clearance": 13.0,
                            "body_emergency_active": False,
                        }
                    }
                },
            },
        },
        {
            "event": "player_damage",
            "seq": 12387,
            "ts_ms": 613000,
            "payload": {"amount": 11, "hp": 34},
        },
    ]

    rows = _damage_rows(events, 612050)

    assert rows[0]["wave"] == 12
    assert _avoidable_damage_violations(rows)[0]["reasons"] == [
        "selected body path missed the required near-best tier"
    ]


def test_projectile_floor_unavailable_only_accepts_unchanged_no_repair_fallback():
    fallback = {
        "body_input_clearance": 89.019873,
        "body_best_clearance": 89.019873,
        "body_selected_clearance": 89.019873,
        "body_projectile_floor": 507.575745,
        "body_selected_projectile_clearance": -1.0,
        "body_safety_active": False,
        "body_emergency_active": False,
    }

    assert _body_projectile_floor_unavailable(fallback)
    assert not _body_projectile_floor_unavailable(
        {**fallback, "body_safety_active": True}
    )
    assert not _body_projectile_floor_unavailable(
        {**fallback, "body_selected_clearance": 50.0}
    )
    assert not _body_projectile_floor_unavailable(
        {**fallback, "body_selected_projectile_clearance": -2.0}
    )
    assert not _body_projectile_floor_unavailable(
        {**fallback, "body_projectile_floor": -1.0e18}
    )
