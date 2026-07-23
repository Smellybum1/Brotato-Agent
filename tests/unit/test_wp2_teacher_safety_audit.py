from scripts.wp2_teacher_safety_audit import (
    _avoidable_damage_violations,
    _body_clearance,
    _body_projectile_floor_unavailable,
    _body_slack_for_wave,
    _damage_rows,
    _dash_audit_hp_floor,
    _effective_dash_arm_floor,
    _hard_wall_faults,
    _projectile_route_clearance,
    _required_body_floor,
    _route_replay,
    _strength_tier_consistent,
    _strength_violation,
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


def test_v122_concession_gate_ignores_the_no_bullets_sentinel():
    # Frozen v121 smoke capture 17514: escape 685.35 was recorded by an
    # inactive projectile pass while the final pass had no bullets in reach
    # (final = -1 sentinel). The replay proved no concession (emitted 681 vs
    # best 685.4); the gate must not treat the sentinel as a clearance.
    sentinel = {
        "projectile_escape_clearance": 685.351013,
        "projectile_final_clearance": -1.0,
        "body_best_clearance": -3.77284,
        "body_selected_clearance": -3.77284,
    }
    assert _avoidable_damage_violations([sentinel]) == []

    # Selected below best-5 so the best-available-escape exemption does not
    # apply, while staying above the 45-unit near-best tier.
    real_concession = {
        "projectile_escape_clearance": 685.351013,
        "projectile_final_clearance": 100.0,
        "body_best_clearance": 60.0,
        "body_selected_clearance": 52.0,
    }
    assert _avoidable_damage_violations([real_concession])[0]["reasons"] == [
        "projectile concession exceeds 60 units"
    ]


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


# ── v123 wave-indexed / strength-conditioned audit units ────────────────────────

def _EPS():
    return 1e-9


def test_v123_required_body_floor_is_wave_indexed():
    # The wider early slack (35) applies ONLY to v123 captures (build_strength
    # present); enforce-pack branch with best 90 makes it visible below 160.
    v123 = {"body_best_clearance": 90.0, "build_strength": 1.0}
    assert abs(_required_body_floor(v123, True, 12) - 55.0) < _EPS()    # 90 - 35
    assert abs(_required_body_floor(v123, True, 13) - 70.0) < _EPS()    # 90 - 20
    assert abs(_required_body_floor(v123, True, 19) - 70.0) < _EPS()    # slack stays 20
    assert abs(_required_body_floor(v123, True, 20) - 70.0) < _EPS()

    # Below-tier branch (best < 45) also carries the wave-indexed slack (v123).
    low = {"body_best_clearance": 40.0, "build_strength": 1.0}
    assert abs(_required_body_floor(low, False, 12) - 5.0) < _EPS()     # 40 - 35
    assert abs(_required_body_floor(low, False, 13) - 20.0) < _EPS()    # 40 - 20

    assert _body_slack_for_wave(12) == 35.0
    assert _body_slack_for_wave(13) == 20.0
    assert _body_slack_for_wave(None) == 20.0


def test_v123_legacy_captures_keep_pre_v123_body_slack():
    # A legacy capture (no strength diagnostics) must keep the flat 20 slack at
    # every wave, so a v122-campaign audit reproduces v122 strictness exactly.
    legacy = {"body_best_clearance": 90.0}
    v123 = {"body_best_clearance": 90.0, "build_strength": 1.0}
    # (c) At wave 10 the legacy capture keeps slack 20 while v123 gets 35.
    assert abs(_required_body_floor(legacy, True, 10) - 70.0) < _EPS()   # 90 - 20
    assert abs(_required_body_floor(v123, True, 10) - 55.0) < _EPS()     # 90 - 35
    # No wave supplied -> late 20 slack regardless of v123 status.
    assert abs(_required_body_floor(legacy, True) - 70.0) < _EPS()
    assert abs(_required_body_floor(v123, True) - 70.0) < _EPS()


def test_v123_dash_hp_floor_clamp_arithmetic():
    # Effective arm floor = wave base (0.35 early / 0.5 late) + strength delta,
    # hard-clamped at 0.30. Early + strong hits the clamp at exactly 0.30.
    assert abs(_effective_dash_arm_floor(12, None) - 0.35) < _EPS()
    assert abs(_effective_dash_arm_floor(12, "strong") - 0.30) < _EPS()   # clamp exact
    assert _effective_dash_arm_floor(12, "strong") >= 0.30
    assert abs(_effective_dash_arm_floor(12, "weak") - 0.40) < _EPS()
    assert abs(_effective_dash_arm_floor(13, None) - 0.5) < _EPS()
    assert abs(_effective_dash_arm_floor(13, "strong") - 0.45) < _EPS()
    # Wave 19 keeps the LATE arm floor (only stall/cooldown/strafe re-greed).
    assert abs(_effective_dash_arm_floor(19, None) - 0.5) < _EPS()

    # Audit HP floor = 0.8 x effective arm - 0.05 (today's 0.40 -> 0.35 margin).
    assert abs(_dash_audit_hp_floor(13, None) - 0.35) < _EPS()
    assert abs(_dash_audit_hp_floor(12, None) - 0.23) < _EPS()
    assert abs(_dash_audit_hp_floor(12, "strong") - 0.19) < _EPS()


def _dash_run(tmp_path, name, *, v123):
    """A single wave-8 dash capture at hp_ratio 0.30, legacy or v123 (neutral)."""
    import json

    debug = {"loot_dash_active": True}
    if v123:
        debug["build_strength"] = 1.0
        debug["strength_tier"] = "neutral"
    events = [
        {
            "event": "combat_capture",
            "ts_ms": 1001,
            "payload": {
                "capture_seq": 1,
                "observation_ts_ms": 1001,
                "wave": 8,
                "player": {"x": 1024.0, "y": 768.0, "speed": 400.0, "hp": 30, "max_hp": 100},
                "teacher": {
                    "action": {"x": 1.0, "y": 0.0},
                    "action_fresh": True,
                    "contributions": {"finale_translation": debug},
                },
                "entities": {"enemies": [], "bosses": [], "projectiles": []},
                "arena": {"width": 2048.0, "height": 1536.0},
            },
        },
        {"event": "run_end", "ts_ms": 3000, "payload": {}},
    ]
    run_dir = tmp_path / name
    run_dir.mkdir()
    (run_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
    )
    (run_dir / "summary.json").write_text(json.dumps({
        "telemetry_complete": True, "errors": 0, "hangs": 0,
        "illegal_actions": 0, "result": "victory", "last_wave": 20,
    }), encoding="utf-8")
    return run_dir


def test_v123_legacy_dash_floor_is_strict_while_v123_dash_floor_loosens(tmp_path):
    from scripts.wp2_teacher_safety_audit import audit_run

    # (a) Legacy capture, wave 8, dash at hp_ratio 0.30 -> flagged (flat 0.35).
    legacy = audit_run(_dash_run(tmp_path, "legacy", v123=False))
    assert [v["reason"] for v in legacy["loot_dash_violations"]] == [
        "dash active below the HP floor"
    ]
    assert not legacy["accepted"]

    # (b) Same capture with v123 keys (neutral tier) -> NOT flagged (floor 0.23).
    v123 = audit_run(_dash_run(tmp_path, "v123", v123=True))
    assert v123["loot_dash_violations"] == []
    assert v123["accepted"]


def test_v123_strength_tier_consistency_gate():
    # Single-sample necessary bands implied by the hysteresis thresholds.
    assert _strength_tier_consistent("strong", 1.30)
    assert not _strength_tier_consistent("strong", 1.10)
    assert _strength_tier_consistent("weak", 0.70)
    assert not _strength_tier_consistent("weak", 0.90)
    assert _strength_tier_consistent("neutral", 1.00)
    assert not _strength_tier_consistent("neutral", 1.30)
    assert not _strength_tier_consistent("neutral", 0.50)

    def payload(strength=None, tier=None, extra=None):
        debug = {}
        if strength is not None:
            debug["build_strength"] = strength
        if tier is not None:
            debug["strength_tier"] = tier
        if extra:
            debug.update(extra)
        return {
            "capture_seq": 1,
            "wave": 8,
            "teacher": {"contributions": {"finale_translation": debug}},
        }

    # Legacy capture (no strength fields) is inert.
    assert _strength_violation(payload()) is None
    # A consistent record passes.
    assert _strength_violation(payload(1.50, "strong")) is None
    # Out-of-range strength is flagged.
    assert "recorded build_strength outside [0, 2]" in _strength_violation(
        payload(3.0, "neutral")
    )["reasons"]
    # A tier that cannot hold at the recorded strength is flagged.
    assert "strength_tier inconsistent with recorded strength" in _strength_violation(
        payload(0.5, "strong")
    )["reasons"]
    # An unknown tier label is flagged.
    assert "unknown strength_tier" in _strength_violation(
        payload(1.0, "turbo")
    )["reasons"]


def test_v123_audit_run_rejects_inconsistent_strength_and_low_hp_dash(tmp_path):
    from scripts.wp2_teacher_safety_audit import audit_run
    import json

    def capture(seq, *, dash=False, strength=1.0, tier="neutral", hp=60, wave=12):
        return {
            "event": "combat_capture",
            "ts_ms": 1000 + seq,
            "payload": {
                "capture_seq": seq,
                "observation_ts_ms": 1000 + seq,
                "wave": wave,
                "player": {"x": 1024.0, "y": 768.0, "speed": 400.0, "hp": hp, "max_hp": 100},
                "teacher": {
                    "action": {"x": 1.0, "y": 0.0},
                    "action_fresh": True,
                    "contributions": {
                        "finale_translation": {
                            "loot_dash_active": dash,
                            "build_strength": strength,
                            "strength_tier": tier,
                        }
                    },
                },
                "entities": {"enemies": [], "bosses": [], "projectiles": []},
                "arena": {"width": 2048.0, "height": 1536.0},
            },
        }

    events = [
        # Consistent, healthy dash at wave 12 strong tier (floor 0.19): hp 0.30 ok.
        capture(1, dash=True, strength=1.30, tier="strong", hp=30),
        # Strong tier recorded at a strength that cannot hold it -> strength fault.
        capture(2, strength=0.50, tier="strong", hp=80),
        # Dash active below the wave-12 neutral floor (0.23): hp 0.20 -> HP fault.
        capture(3, dash=True, strength=1.00, tier="neutral", hp=20),
        {"event": "run_end", "ts_ms": 5000, "payload": {}},
    ]
    run_dir = tmp_path / "run_v123"
    run_dir.mkdir()
    (run_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
    )
    (run_dir / "summary.json").write_text(json.dumps({
        "telemetry_complete": True, "errors": 0, "hangs": 0,
        "illegal_actions": 0, "result": "victory", "last_wave": 20,
    }), encoding="utf-8")

    audit = audit_run(run_dir)
    assert len(audit["strength_violations"]) == 1
    assert audit["strength_violations"][0]["capture_seq"] == 2
    dash_reasons = [v["reason"] for v in audit["loot_dash_violations"]]
    assert "dash active below the HP floor" in dash_reasons
    # The healthy strong-tier dash at hp 0.30 (floor 0.19) is NOT flagged.
    assert all(v["capture_seq"] != 1 for v in audit["loot_dash_violations"])
    assert not audit["accepted"]


# ── v122 exact-20 over-firing gate corrections (frozen fixtures) ─────────────────

import json as _json
from pathlib import Path as _Path

_FIXTURES = _Path(__file__).resolve().parents[1] / "fixtures" / "wp2"


def _run_dir_from_fixture(tmp_path, fixture_name):
    """Materialise a fixture's frozen capture window as a runnable audit dir."""
    data = _json.loads((_FIXTURES / fixture_name).read_text(encoding="utf-8"))
    events = sorted(data["captures"].values(), key=lambda e: e.get("ts_ms", 0))
    last_ts = max((e.get("ts_ms", 0) for e in events), default=0) + 1
    events = events + [{"event": "run_end", "ts_ms": last_ts, "payload": {}}]
    run_dir = tmp_path / data["run_id"]
    run_dir.mkdir()
    (run_dir / "events.jsonl").write_text(
        "\n".join(_json.dumps(e) for e in events) + "\n", encoding="utf-8"
    )
    (run_dir / "summary.json").write_text(_json.dumps({
        "policy_version": data["policy_version"],
        "mod_version": data["mod_version"],
        "telemetry_complete": True, "errors": 0, "hangs": 0,
        "illegal_actions": 0, "result": data.get("result", "victory"),
        "last_wave": 20,
    }), encoding="utf-8")
    return data, run_dir


def _replay_clears_focus(tmp_path, fixture_name):
    from scripts.wp2_teacher_safety_audit import audit_run

    data, run_dir = _run_dir_from_fixture(tmp_path, fixture_name)
    audit = audit_run(run_dir)
    kind = data["violation_kind"]
    focus = data["focus_capture_seq"]
    flagged = {v.get("capture_seq") for v in audit[kind]}
    return focus, flagged


def test_v122a_relief_selection_gate_accepts_the_v121_fallback(tmp_path):
    # run_1784787688 capture 18676: relief active, negative pool-best (-21.0) but
    # the v121 fallback preserved a far clearer command (131.6). Now cleared.
    focus, flagged = _replay_clears_focus(
        tmp_path, "v122_exact20_viol_a_1784787688.json"
    )
    assert focus not in flagged


def test_v122b_body_tier_gate_accepts_the_below_tier_dash(tmp_path):
    # run_1784804435 capture 17442: deliberate loot-dash (19.03) with a relief
    # transient surfacing a 43.44 pool-best below the 45 tier. Now cleared.
    focus, flagged = _replay_clears_focus(
        tmp_path, "v122_exact20_viol_b_1784804435.json"
    )
    assert focus not in flagged


def test_v122c_body_repair_gate_accepts_the_boundary_snap(tmp_path):
    # run_1784805636 capture 9722: input 44.94 snapped to the best sampled lane
    # 45.67 (above tier) with a sub-degree deviation; active flag stayed false.
    focus, flagged = _replay_clears_focus(
        tmp_path, "v122_exact20_viol_c_1784805636.json"
    )
    assert focus not in flagged


# Counter-tests: the corrected gates still catch what they were built for.

def _late_capture(seq, ft, *, wave=18, fresh=True, projectiles=None):
    return {
        "event": "combat_capture",
        "ts_ms": 1000 + seq,
        "payload": {
            "capture_seq": seq,
            "observation_ts_ms": 1000 + seq,
            "wave": wave,
            "player": {"x": 1024.0, "y": 768.0, "speed": 400.0, "hp": 50, "max_hp": 100},
            "teacher": {
                "action": {"x": 1.0, "y": 0.0},
                "action_fresh": fresh,
                "contributions": {"finale_translation": ft},
            },
            "entities": {"enemies": [], "bosses": [], "projectiles": projectiles or []},
            "arena": {"width": 2048.0, "height": 1536.0},
        },
    }


def _audit_events(tmp_path, name, events):
    from scripts.wp2_teacher_safety_audit import audit_run

    events = events + [{"event": "run_end", "ts_ms": 9000, "payload": {}}]
    run_dir = tmp_path / name
    run_dir.mkdir()
    (run_dir / "events.jsonl").write_text(
        "\n".join(_json.dumps(e) for e in events) + "\n", encoding="utf-8"
    )
    (run_dir / "summary.json").write_text(_json.dumps({
        "telemetry_complete": True, "errors": 0, "hangs": 0,
        "illegal_actions": 0, "result": "victory", "last_wave": 20,
    }), encoding="utf-8")
    return audit_run(run_dir)


def test_v122a_counter_undiagnosed_negative_pool_still_fires(tmp_path):
    # relief_best < 0 WITHOUT the v121-fallback signature (selected-projectile
    # clearance is a real 100.0, not the -1 sentinel) must still fire.
    ft = {
        "wall_body_relief_active": True,
        "wall_recovery_active": True,
        "body_safety_active": False,
        "body_emergency_active": False,
        "loot_dash_active": False,
        # -1 sentinel skips the fresh-loop body block; the late-loop relief gate
        # reads the recorded relief_best directly. A real (non -1) projectile
        # clearance defeats the v121-fallback recogniser, so the disqualifier fires.
        "body_selected_clearance": -1.0,
        "wall_relief_best_body_clearance": -5.0,
        "body_projectile_floor": 200.0,
        "body_selected_projectile_clearance": 100.0,
    }
    audit = _audit_events(
        tmp_path, "counter_a", [_late_capture(701, ft, projectiles=[{"x": 5000.0, "y": 5000.0, "vx": 0.0, "vy": 0.0, "radius": 8.0}])]
    )
    assert 701 in {v["capture_seq"] for v in audit["wall_body_relief_selection_violations"]}


def test_v122b_counter_dash_above_tier_still_binds_and_below_tier_waives():
    # best >= 45 dash keeps the BODY_TIER floor (still catches selected < 45);
    # best < 45 dash waives the near-best floor entirely.
    above = {"body_best_clearance": 60.0, "loot_dash_active": True}
    below = {"body_best_clearance": 43.0, "loot_dash_active": True}
    assert _required_body_floor(above, True, 17) == 45.0
    assert 30.0 < 45.0  # a below-tier selected on the above-tier dash still fires
    assert _required_body_floor(below, True, 17) == float("-inf")


def test_v122c_counter_below_tier_selected_fires_regardless_of_active(tmp_path):
    # selected < 45 with best >= 45 must fire the repair gate whether or not the
    # body_safety_active flag is set.
    active_ft = {
        "body_input_clearance": 30.0,
        "body_best_clearance": 60.0,
        "body_selected_clearance": 30.0,
        "body_safety_active": True,
        "body_selected_projectile_clearance": 500.0,
        "body_projectile_floor": 100.0,
    }
    inactive_ft = {**active_ft, "body_safety_active": False}
    audit = _audit_events(tmp_path, "counter_c", [
        _late_capture(801, active_ft, wave=11),
        _late_capture(802, inactive_ft, wave=11),
    ])
    flagged = {v["capture_seq"] for v in audit["body_repair_violations"]}
    assert flagged == {801, 802}
