from scripts.wp2_teacher_safety_audit import (
    _avoidable_damage_violations,
    _body_clearance,
    _body_projectile_floor_unavailable,
    _hard_wall_faults,
    _required_body_floor,
    _wall_body_relief_violation,
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

    assert _body_clearance(payload) >= 120.0
    assert _wall_body_relief_violation(payload) is None


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
