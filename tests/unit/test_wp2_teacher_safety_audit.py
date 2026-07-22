from scripts.wp2_teacher_safety_audit import (
    _avoidable_damage_violations,
    _body_clearance,
    _hard_wall_faults,
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


def test_damage_audit_allows_only_the_bounded_projectile_concession():
    safe = {
        "projectile_escape_clearance": 100.0,
        "projectile_final_clearance": 40.0,
        "body_best_clearance": 70.0,
        "body_selected_clearance": 45.0,
    }
    unsafe = {**safe, "projectile_final_clearance": 39.0}

    assert _avoidable_damage_violations([safe]) == []
    assert _avoidable_damage_violations([unsafe])[0]["reasons"] == [
        "projectile concession exceeds 60 units"
    ]
