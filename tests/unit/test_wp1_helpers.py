from trainer.evaluation.wp1_helpers import (
    action_is_legal,
    normalize_player_relative,
    phase_transition_valid,
    score_item_tier,
    serialize_event,
    shop_legal_actions,
)


def test_normalize_player_relative():
    ents = [{"x": 110, "y": 50}, {"x": 90, "y": 40}]
    out = normalize_player_relative(ents, {"x": 100, "y": 40})
    assert out[0]["nx"] == 10
    assert out[0]["ny"] == 10
    assert out[1]["nx"] == -10
    assert out[1]["ny"] == 0


def test_shop_legal_actions_and_mask():
    items = [
        {"slot": 0, "price": 10, "affordable": True, "locked": False},
        {"slot": 1, "price": 50, "affordable": False, "locked": True},
    ]
    legal = shop_legal_actions(items, gold=20)
    assert "shop_go" in legal
    assert "shop_reroll" in legal
    assert action_is_legal({"type": "shop_buy", "slot": 0}, legal)
    assert action_is_legal({"type": "shop_unlock", "slot": 1}, legal)
    assert not action_is_legal({"type": "shop_buy", "slot": 9}, legal)


def test_score_item_tier():
    assert score_item_tier(0) == 3.0
    assert score_item_tier(3) == 14.0
    assert score_item_tier(99) == 30.0


def test_phase_transitions():
    assert phase_transition_valid("MAIN_MENU", "CHARACTER_SELECT")
    assert phase_transition_valid("COMBAT", "SHOP")
    assert not phase_transition_valid("MAIN_MENU", "SHOP")


def test_serialize_event_fields():
    ev = serialize_event("run_1", 1, "run_start", {"danger": 0})
    assert ev["schema_version"] == "1.0.0"
    assert ev["seq"] == 1
    assert ev["event"] == "run_start"
