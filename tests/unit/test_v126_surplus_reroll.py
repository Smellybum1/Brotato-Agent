"""v126 bounded surplus-reroll acceptance ladder (design note v2).

Structure follows the v124/v125 shop tests: source-shape assertions pin the
GDScript, and an independent Python mirror of `_surplus_state` carries the
decision-table, fixture and property/monotonicity work.
"""
import importlib.util
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/teacher/config.gd"
STRATEGY = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/teacher/shop_strategy.gd"
CONTROLLER = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/runtime/agent_controller.gd"
WP2_FIXTURES = ROOT / "tests/fixtures/wp2"

SURPLUS_REROLLS_MAX = 3
SURPLUS_MIN_WAVE = 6
SURPLUS_MAX_WAVE = 19
SHOP_MAX_REROLLS_CAP = 28

EXIT_NO_SURPLUS = "EXIT_NO_SURPLUS"
EXIT_REROLL_LIMIT = "EXIT_REROLL_LIMIT"
EXIT_LOCKED_RESERVE = "EXIT_LOCKED_RESERVE"
EXIT_MATERIAL_VALUE_RESERVE = "EXIT_MATERIAL_VALUE_RESERVE"
EXIT_NEXT_SHOP_RESERVE = "EXIT_NEXT_SHOP_RESERVE"
EXIT_NO_SAFE_POSITIVE_ITEM = "EXIT_NO_SAFE_POSITIVE_ITEM"
EXIT_BOARD_STALE_TIMEOUT = "EXIT_BOARD_STALE_TIMEOUT"


def _load_audit_module():
    spec = importlib.util.spec_from_file_location(
        "wp2_v126_shop_audit", ROOT / "scripts/wp2_v126_shop_audit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDIT = _load_audit_module()


# ── Python mirror of teacher/shop_strategy.gd::_surplus_state ─────────────────

def locked_item_reserve(items):
    return sum(int(it.get("price", 0)) for it in items if it.get("locked", False))


def material_value_reserve(owned_items, gold, table):
    """Fractions all address the same material pool -> max, never sum."""
    reserve = 0
    for owned in owned_items:
        item_id = owned.get("id") if isinstance(owned, dict) else owned
        if item_id not in table:
            continue
        entry = table[item_id]
        flat = int(entry.get("flat", 0))
        scaled = int(round(float(entry.get("fraction_of_gold", 0.0)) * max(gold, 0)))
        reserve = max(reserve, flat, scaled)
    return reserve


def surplus_state(*, wave, gold, reroll_price, items=(), owned_items=(),
                  material_table=None, next_shop_reserve=0,
                  surplus_rerolls=0, session_rerolls=0,
                  board_has_safe_positive_item=True):
    material_table = material_table or {}
    in_window = SURPLUS_MIN_WAVE <= wave <= SURPLUS_MAX_WAVE
    locked = locked_item_reserve(items)
    material = material_value_reserve(owned_items, gold, material_table)
    # Wave-19 terminal-liquidation posture: no future shop exists.
    next_shop = 0 if wave >= 19 else next_shop_reserve
    spendable = gold - locked - material - next_shop
    out = {
        "in_window": in_window, "wave": wave, "gold": gold,
        "reroll_price": reroll_price, "locked_item_reserve": locked,
        "material_value_reserve": material, "next_shop_reserve": next_shop,
        "spendable_surplus": spendable, "surplus_rerolls": surplus_rerolls,
        "surplus_rerolls_max": SURPLUS_REROLLS_MAX,
        "reroll": False, "exit_reason": EXIT_NO_SURPLUS,
    }
    if not in_window:
        return out
    if (surplus_rerolls >= SURPLUS_REROLLS_MAX
            or session_rerolls >= SHOP_MAX_REROLLS_CAP):
        out["exit_reason"] = (EXIT_REROLL_LIMIT if board_has_safe_positive_item
                              else EXIT_NO_SAFE_POSITIVE_ITEM)
        return out
    if spendable - reroll_price > 0:
        out["reroll"] = True
        out["exit_reason"] = ""
        return out
    if locked > 0 and spendable + locked - reroll_price > 0:
        out["exit_reason"] = EXIT_LOCKED_RESERVE
    elif material > 0 and spendable + material - reroll_price > 0:
        out["exit_reason"] = EXIT_MATERIAL_VALUE_RESERVE
    elif next_shop > 0 and spendable + next_shop - reroll_price > 0:
        out["exit_reason"] = EXIT_NEXT_SHOP_RESERVE
    else:
        out["exit_reason"] = EXIT_NO_SURPLUS
    return out


def run_shop(*, wave, gold, reroll_price, price_step=0, qualifying_after=None,
             **kwargs):
    """Simulate one shop visit: surplus rerolls until the rule fails.

    ``qualifying_after`` is the reroll index after which a qualifying buy
    appears; the buy loop runs FIRST every board, so it short-circuits the
    surplus rule (which is exactly the v125-ordering guarantee).
    """
    surplus_rerolls = 0
    price = reroll_price
    trace = []
    while True:
        if qualifying_after is not None and surplus_rerolls == qualifying_after:
            trace.append(("buy", price))
            return {"rerolls": surplus_rerolls, "gold": gold, "trace": trace,
                    "exit_reason": "", "bought": True}
        state = surplus_state(wave=wave, gold=gold, reroll_price=price,
                              surplus_rerolls=surplus_rerolls, **kwargs)
        if not state["reroll"]:
            return {"rerolls": surplus_rerolls, "gold": gold, "trace": trace,
                    "exit_reason": state["exit_reason"], "bought": False,
                    "state": state}
        gold -= price
        surplus_rerolls += 1
        price += price_step
        trace.append(("reroll", price))


# ── 1. source shape ───────────────────────────────────────────────────────────

def test_v126_config_constants_and_reserve_table():
    config = CONFIG.read_text(encoding="utf-8")

    assert "const SURPLUS_REROLLS_MAX := 3" in config
    assert "const SURPLUS_MIN_WAVE := 6" in config
    assert "const SURPLUS_MAX_WAVE := 19" in config
    assert "const SURPLUS_NEXT_SHOP_RESERVE := {" in config
    assert "const SURPLUS_MATERIAL_VALUE_ITEMS := {" in config
    assert '"item_piggy_bank": {"fraction_of_gold": 1.0},' in config
    for code in (EXIT_NO_SURPLUS, EXIT_REROLL_LIMIT, EXIT_LOCKED_RESERVE,
                 EXIT_MATERIAL_VALUE_RESERVE, EXIT_NEXT_SHOP_RESERVE,
                 EXIT_NO_SAFE_POSITIVE_ITEM, EXIT_BOARD_STALE_TIMEOUT):
        assert f'"{code}"' in config

    # The wave table covers exactly waves 6..19 and w19 is the terminal 0.
    table = config.split("const SURPLUS_NEXT_SHOP_RESERVE := {", 1)[1].split("\n}", 1)[0]
    waves = [int(m) for m in re.findall(r"^\t(\d+):", table, re.MULTILINE)]
    assert waves == list(range(SURPLUS_MIN_WAVE, SURPLUS_MAX_WAVE + 1))
    assert re.search(r"^\t19: 0,$", table, re.MULTILINE)
    # Terminal posture is enforced in code, not only in the table.
    assert (
        "static func surplus_next_shop_reserve(wave: int) -> int:\n"
        "\t# Wave-19 terminal-liquidation posture: no future shop exists.\n"
        "\tif wave >= FINAL_SHOP_WAVE:\n"
        "\t\treturn 0"
    ) in config


def test_v126_surplus_block_runs_after_every_buy_and_after_the_v125_reroll():
    strategy = STRATEGY.read_text(encoding="utf-8")
    decide = strategy.split("func decide_shop", 1)[1].split("func decide_levelup", 1)[0]

    # The surplus block sits strictly after the v125 reroll fire and before the
    # bare shop_go fallthrough — it therefore cannot preempt a buy or alter any
    # v125 decision (v125 is byte-identical whenever the rule never fires).
    v125_fire = decide.index('return {"type": "shop_reroll", "score": best_here}')
    surplus = decide.index("var surplus := _surplus_state(")
    surplus_fire = decide.index('"surplus_reroll": true')
    go = decide.rindex('return {"type": "shop_go", "score": 0.0}')
    assert v125_fire < surplus < surplus_fire < go
    # Every buy/sell/combine/lock return precedes the surplus block.
    for marker in ('return {"type": "shop_buy"', 'best_action = ["shop_buy"',
                   '"type": "shop_combine", "index": ci'):
        assert decide.index(marker) < surplus

    # One reroll at a time: the surplus path bumps both the dedicated counter
    # and the shared per-visit reroll count, and never precomputes a count.
    assert "_session_surplus_rerolls += 1" in decide
    assert decide.count("_session_surplus_rerolls += 1") == 1
    assert "var _session_surplus_rerolls: int = 0" in strategy
    assert "_session_surplus_rerolls = 0" in strategy  # per-wave session reset


def test_v126_reserve_helpers_and_reason_precedence_in_source():
    strategy = STRATEGY.read_text(encoding="utf-8")
    state = strategy.split("func _surplus_state", 1)[1].split(
        "# ─────────────────────────── decide_shop", 1)[0]

    assert "func _locked_item_reserve(items: Array) -> int:" in strategy
    assert "func _material_value_reserve(build: Dictionary, gold: int) -> int:" in strategy
    assert "func _board_has_safe_positive_item(" in strategy
    # Fractions address one pool -> max, never sum.
    assert "reserve = int(max(reserve, max(flat, scaled)))" in strategy
    # Reserve arithmetic exactly as designed.
    assert ("var spendable := gold - locked_reserve - material_reserve "
            "- next_shop_reserve") in state
    assert "if spendable - reroll_price > 0:" in state
    # Budget check precedes the arithmetic; binding-reserve attribution order.
    budget = state.index("var budget_exhausted: bool = (")
    fire = state.index("if spendable - reroll_price > 0:")
    locked = state.index("BotConfig.SHOP_EXIT_LOCKED_RESERVE")
    material = state.index("BotConfig.SHOP_EXIT_MATERIAL_VALUE_RESERVE")
    next_shop = state.index("BotConfig.SHOP_EXIT_NEXT_SHOP_RESERVE")
    assert budget < fire < locked < material < next_shop
    assert "_session_rerolls >= BotConfig.SHOP_MAX_REROLLS_CAP" in state


def test_v126_controller_board_barrier_and_exit_reason_telemetry():
    controller = CONTROLLER.read_text(encoding="utf-8")

    assert "const SHOP_SURPLUS_CONFIRM_INTERVAL = 0.6" in controller
    assert "const SHOP_SURPLUS_CONFIRM_TIMEOUT = 4.0" in controller
    assert "func _shop_board_signature(state: Dictionary) -> String:" in controller
    # Barrier is evaluated BEFORE any decision is taken on a possibly stale board.
    barrier = controller.index("if _pending_surplus_wave >= 0:")
    decide = controller.index("var decision = choose_meta_action(state,")
    arm = controller.index("_pending_surplus_signature = _shop_board_signature(state)")
    assert barrier < decide < arm
    assert "if surplus_signature == _pending_surplus_signature:" in controller
    assert 'telem.emit("shop_surplus_stale_timeout"' in controller
    assert 'telem.emit("shop_surplus_reroll_confirmed"' in controller
    assert "_CONFIG_SCRIPT.SHOP_EXIT_BOARD_STALE_TIMEOUT" in controller
    # Exit reason + arithmetic reach telemetry on purchase_decision.
    assert '"exit_reason": action.get("exit_reason", "")' in controller
    assert '"surplus": action.get("surplus", {})' in controller
    # Owned items feed material_value_reserve.
    assert 'owned_items.append({"id": str(owned.my_id)})' in controller
    assert '"items": owned_items,' in controller
    # The owned-item lookup must never be able to break _build_dict: both the
    # 1.1.x accessor and the older flat array are handled, else an empty list.
    assert 'if RunData.has_method("get_player_items"):' in controller
    assert 'elif "items" in RunData and RunData.items != null:' in controller


# ── 2. the three evidence boards ──────────────────────────────────────────────

def _fixture(wave):
    return json.loads(
        (WP2_FIXTURES / f"v126_rich_exit_boards_w{wave}.json").read_text(encoding="utf-8"))


def test_v126_w17_and_w18_rich_exits_must_reroll_or_buy():
    # The two late-game rich exits v125 produced with a tier-3 potato (w17) and
    # an affordable +25% damage glass_cannon (w18) left on the board.
    for wave in (17, 18):
        fx = _fixture(wave)
        assert fx["action_taken"] == "shop_go"  # v125 behaviour, frozen
        state = surplus_state(
            wave=fx["wave"], gold=fx["gold_at_exit"],
            reroll_price=fx["reroll_price"], items=fx["items"],
            surplus_rerolls=fx["surplus_rerolls_before_exit"],
            session_rerolls=fx["session_rerolls_before_exit"])
        assert state["reroll"] is True, f"wave {wave} must not bare-exit"
        assert state["exit_reason"] == ""
        assert state["spendable_surplus"] - fx["reroll_price"] > 0


def test_v126_w10_exit_invariants_only():
    # Design note v2 acceptance step 1: w10 is invariants-only. No below-threshold
    # filler is bought (the surplus rule never buys — it only rerolls), no reserve
    # is breached, and the action is consistent with the computed cap and budget.
    fx = _fixture(10)
    state = surplus_state(
        wave=fx["wave"], gold=fx["gold_at_exit"], reroll_price=fx["reroll_price"],
        items=fx["items"], surplus_rerolls=fx["surplus_rerolls_before_exit"],
        session_rerolls=fx["session_rerolls_before_exit"])
    # No reserve is breached whichever way it goes.
    assert state["locked_item_reserve"] == 0  # nothing locked on this board
    assert state["spendable_surplus"] <= state["gold"]
    if state["reroll"]:
        # Legitimate only while a real surplus survives every reserve.
        assert state["spendable_surplus"] - fx["reroll_price"] > 0
        assert state["surplus_rerolls"] < SURPLUS_REROLLS_MAX
    else:
        assert state["exit_reason"] in {
            EXIT_NO_SURPLUS, EXIT_REROLL_LIMIT, EXIT_LOCKED_RESERVE,
            EXIT_MATERIAL_VALUE_RESERVE, EXIT_NEXT_SHOP_RESERVE,
            EXIT_NO_SAFE_POSITIVE_ITEM}
    # The surplus rule cannot buy: no board item is purchased by this path.
    assert all(not it["locked"] for it in fx["items"])


def test_v126_evidence_boards_match_the_recorded_evidence_file():
    evidence = json.loads(
        (ROOT / "reports/wp2/v126_evidence_rich_exit_w10.json").read_text(encoding="utf-8"))
    assert _fixture(10)["gold_at_exit"] == 417
    assert _fixture(10)["reroll_price"] == 11
    others = {row["wave"]: row for row in evidence["additional_instances_same_run"]}
    for wave in (17, 18):
        assert _fixture(wave)["gold_at_exit"] == others[wave]["gold_at_exit"]
    # w18's board still carries the affordable glass_cannon that was left behind.
    ids = {it["id"] for it in _fixture(18)["items"]}
    assert "item_glass_cannon" in ids


# ── 3. property / monotonicity suite (all seven design properties) ────────────

def test_property_more_gold_never_causes_an_earlier_exit():
    board = dict(wave=12, reroll_price=20, price_step=5)
    previous = -1
    for gold in range(0, 400, 7):
        result = run_shop(gold=gold, **board)
        assert result["rerolls"] >= previous
        previous = result["rerolls"]


def test_property_higher_reroll_price_never_increases_reroll_count():
    previous = None
    for price in range(1, 200, 3):
        result = run_shop(wave=12, gold=300, reroll_price=price, price_step=0)
        if previous is not None:
            assert result["rerolls"] <= previous
        previous = result["rerolls"]


def test_property_qualifying_item_after_reroll_one_is_bought_before_reroll_two():
    result = run_shop(wave=12, gold=1000, reroll_price=10, price_step=5,
                      qualifying_after=1)
    assert result["bought"] is True
    assert result["rerolls"] == 1  # never reached a second reroll

    strategy = STRATEGY.read_text(encoding="utf-8")
    decide = strategy.split("func decide_shop", 1)[1].split("func decide_levelup", 1)[0]
    # Structural guarantee: the buy loop is re-entered on the refreshed board
    # before the surplus block can be reached again.
    assert decide.index('best_action = ["shop_buy"') < decide.index(
        "var surplus := _surplus_state(")


def test_property_exactly_three_surplus_rerolls_maximum_never_four():
    result = run_shop(wave=12, gold=100_000, reroll_price=1, price_step=0)
    assert result["rerolls"] == SURPLUS_REROLLS_MAX == 3
    assert result["exit_reason"] == EXIT_REROLL_LIMIT
    # And the shared per-visit cap still binds independently.
    capped = run_shop(wave=12, gold=100_000, reroll_price=1, price_step=0,
                      session_rerolls=SHOP_MAX_REROLLS_CAP)
    assert capped["rerolls"] == 0
    assert capped["exit_reason"] == EXIT_REROLL_LIMIT


def test_property_locked_item_stays_affordable_after_all_actions():
    locked_price = 250
    items = [{"id": "item_locked", "price": locked_price, "locked": True}]
    result = run_shop(wave=14, gold=600, reroll_price=30, price_step=10, items=items)
    assert result["gold"] >= locked_price
    # And the exit is attributed to the locked reserve when that is what binds.
    tight = surplus_state(wave=14, gold=260, reroll_price=30, items=items)
    assert tight["reroll"] is False
    assert tight["exit_reason"] == EXIT_LOCKED_RESERVE


def test_property_stale_board_produces_no_duplicate_action():
    # Mirror of the controller barrier: one action per board signature.
    class Barrier:
        def __init__(self):
            self.pending = None
            self.at = 0.0
            self.actions = 0

        def tick(self, now, signature):
            if self.pending is not None:
                if now - self.at < 0.6:
                    return "wait"
                if signature == self.pending:
                    if now - self.at >= 4.0:
                        self.pending = None
                        return EXIT_BOARD_STALE_TIMEOUT
                    return "wait"
                self.pending = None
            self.actions += 1
            return "act"

    barrier = Barrier()
    assert barrier.tick(0.0, "board_a") == "act"
    barrier.pending, barrier.at = "board_a", 0.0     # surplus reroll dispatched
    # Stale board across the whole confirm window: never a second action.
    for now in (0.1, 0.7, 1.5, 3.0, 3.9):
        assert barrier.tick(now, "board_a") == "wait"
    assert barrier.actions == 1
    # Confirmed refresh -> exactly one action on the new signature.
    assert barrier.tick(4.5, "board_b") == "act"
    assert barrier.actions == 2
    # Timeout path releases the barrier with the designated reason code.
    barrier.pending, barrier.at = "board_b", 5.0
    assert barrier.tick(9.5, "board_b") == EXIT_BOARD_STALE_TIMEOUT


def test_property_wave19_large_surplus_converts_unless_every_option_is_vetoed():
    # Terminal posture: next_shop_reserve is forced to 0 even if a table entry
    # existed, so a large surplus always converts...
    state = surplus_state(wave=19, gold=1200, reroll_price=30,
                          next_shop_reserve=500)
    assert state["next_shop_reserve"] == 0
    assert state["reroll"] is True
    # ...until the reroll budget is spent, and then the reason distinguishes a
    # board where every option hits a veto from a merely exhausted budget.
    vetoed = surplus_state(wave=19, gold=1200, reroll_price=30,
                           surplus_rerolls=SURPLUS_REROLLS_MAX,
                           board_has_safe_positive_item=False)
    assert vetoed["exit_reason"] == EXIT_NO_SAFE_POSITIVE_ITEM
    buyable = surplus_state(wave=19, gold=1200, reroll_price=30,
                            surplus_rerolls=SURPLUS_REROLLS_MAX,
                            board_has_safe_positive_item=True)
    assert buyable["exit_reason"] == EXIT_REROLL_LIMIT


# ── 4. reserve arithmetic units ───────────────────────────────────────────────

def test_reserve_arithmetic_locked_material_and_next_shop():
    items = [{"id": "a", "price": 100, "locked": True},
             {"id": "b", "price": 60, "locked": True},
             {"id": "c", "price": 900, "locked": False}]
    assert locked_item_reserve(items) == 160

    table = {"item_piggy_bank": {"fraction_of_gold": 1.0},
             "item_coupon": {"flat": 40}}
    assert material_value_reserve([], 500, table) == 0
    assert material_value_reserve([{"id": "item_piggy_bank"}], 500, table) == 500
    assert material_value_reserve([{"id": "item_coupon"}], 500, table) == 40
    # Several matching items address the same pool: max, never sum.
    assert material_value_reserve(
        [{"id": "item_piggy_bank"}, {"id": "item_coupon"}], 500, table) == 500
    assert material_value_reserve([{"id": "item_missile"}], 500, table) == 0

    state = surplus_state(wave=12, gold=500, reroll_price=10, items=items,
                          owned_items=[{"id": "item_coupon"}],
                          material_table=table, next_shop_reserve=75)
    assert state["locked_item_reserve"] == 160
    assert state["material_value_reserve"] == 40
    assert state["next_shop_reserve"] == 75
    assert state["spendable_surplus"] == 500 - 160 - 40 - 75 == 225
    assert state["reroll"] is True


def test_reserve_arithmetic_binding_reason_attribution():
    table = {"item_piggy_bank": {"fraction_of_gold": 1.0}}
    # Only the material reserve is individually binding.
    state = surplus_state(wave=12, gold=100, reroll_price=10,
                          owned_items=[{"id": "item_piggy_bank"}],
                          material_table=table)
    assert state["spendable_surplus"] == 0
    assert state["exit_reason"] == EXIT_MATERIAL_VALUE_RESERVE
    # Only the next-shop reserve is individually binding.
    state = surplus_state(wave=12, gold=100, reroll_price=10, next_shop_reserve=95)
    assert state["exit_reason"] == EXIT_NEXT_SHOP_RESERVE
    # Nothing reserved and still no surplus -> plain no-surplus.
    state = surplus_state(wave=12, gold=8, reroll_price=10)
    assert state["exit_reason"] == EXIT_NO_SURPLUS
    # Outside the 6..19 window the rule never engages.
    for wave in (1, 5, 20):
        out = surplus_state(wave=wave, gold=5000, reroll_price=10)
        assert out["in_window"] is False
        assert out["reroll"] is False
        assert out["exit_reason"] == EXIT_NO_SURPLUS


def test_reserve_arithmetic_tracks_reroll_price_escalation():
    # The rule is re-evaluated against the ACTUAL current price each time, so an
    # escalating price stops the loop before the budget cap does.
    result = run_shop(wave=15, gold=120, reroll_price=30, price_step=40)
    assert result["rerolls"] == 2          # 30 then 70; 110 exceeds the 90 left
    assert result["gold"] == 20
    assert result["exit_reason"] == EXIT_NO_SURPLUS
    # A free reroll (price 0) still requires a strictly positive surplus.
    assert surplus_state(wave=15, gold=1, reroll_price=0)["reroll"] is True
    assert surplus_state(wave=15, gold=0, reroll_price=0)["reroll"] is False


# ── 5. audit mirror ───────────────────────────────────────────────────────────

def _decision(action, surplus, wave=12, exit_reason=""):
    return {"event": "purchase_decision",
            "payload": {"action": action, "wave": wave, "surplus": surplus,
                        "exit_reason": exit_reason}}


def test_audit_constants_track_the_gdscript_config():
    assert AUDIT.SURPLUS_REROLLS_MAX == SURPLUS_REROLLS_MAX
    assert AUDIT.SURPLUS_MIN_WAVE == SURPLUS_MIN_WAVE
    assert AUDIT.SURPLUS_MAX_WAVE == SURPLUS_MAX_WAVE
    assert AUDIT.SHOP_MAX_REROLLS_CAP == SHOP_MAX_REROLLS_CAP
    assert AUDIT.REASON_CODES == {
        EXIT_NO_SURPLUS, EXIT_REROLL_LIMIT, EXIT_LOCKED_RESERVE,
        EXIT_MATERIAL_VALUE_RESERVE, EXIT_NEXT_SHOP_RESERVE,
        EXIT_NO_SAFE_POSITIVE_ITEM, EXIT_BOARD_STALE_TIMEOUT}


def test_audit_flags_a_rich_exit_that_should_have_rerolled():
    # The w17 evidence board replayed as a v126 exit: the rule still held, so
    # exiting there is a violation the audit must catch.
    fx = _fixture(17)
    held = surplus_state(wave=fx["wave"], gold=fx["gold_at_exit"],
                         reroll_price=fx["reroll_price"], items=fx["items"])
    assert AUDIT.rule_holds(held) is True
    report = AUDIT.audit_events(
        [_decision({"type": "shop_go"}, held, wave=17,
                   exit_reason=EXIT_NO_SURPLUS)], "run_test")
    assert len(report["surplus_exit_violations"]) == 1
    assert report["violation_count"] >= 1


def test_audit_flags_reason_code_inconsistency_and_passes_a_clean_stream():
    good = surplus_state(wave=12, gold=8, reroll_price=10)
    clean = AUDIT.audit_events(
        [_decision({"type": "shop_go"}, good, exit_reason=EXIT_NO_SURPLUS)], "r")
    assert clean["violation_count"] == 0
    assert clean["reason_code_counts"] == {EXIT_NO_SURPLUS: 1}

    bad = AUDIT.audit_events(
        [_decision({"type": "shop_go"}, good, exit_reason=EXIT_LOCKED_RESERVE)], "r")
    assert len(bad["reason_code_violations"]) == 1
    assert bad["reason_code_violations"][0]["expected"] == EXIT_NO_SURPLUS

    unknown = AUDIT.audit_events(
        [_decision({"type": "shop_go"}, good, exit_reason="EXIT_MADE_UP")], "r")
    assert len(unknown["unknown_reason_codes"]) == 1


def test_audit_flags_a_fourth_surplus_reroll_and_counts_barrier_events():
    reroll = {"type": "shop_reroll", "surplus_reroll": True}
    state = surplus_state(wave=12, gold=1000, reroll_price=5)
    events = [_decision(reroll, state) for _ in range(4)]
    events.append({"event": "shop_surplus_reroll_confirmed", "payload": {}})
    events.append({"event": "shop_surplus_stale_timeout",
                   "payload": {"exit_reason": EXIT_BOARD_STALE_TIMEOUT}})
    report = AUDIT.audit_events(events, "r")
    assert report["surplus_rerolls"] == 4
    assert len(report["surplus_budget_violations"]) == 1
    assert report["confirmed_board_refreshes"] == 1
    assert report["stale_board_timeouts"] == 1


def test_audit_ignores_pre_v126_streams():
    # A v125 stream carries no `surplus` block; the audit must stay silent.
    report = AUDIT.audit_events(
        [{"event": "purchase_decision",
          "payload": {"action": {"type": "shop_go"}, "wave": 17}}], "r")
    assert report["violation_count"] == 0
    assert report["surplus_exits_with_reason"] == 0
