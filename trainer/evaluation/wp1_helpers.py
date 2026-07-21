"""Python mirrors of WP1 scoring / serialization helpers for unit tests."""
from __future__ import annotations

from typing import Any


PHASES = [
    "BOOT",
    "MAIN_MENU",
    "CHARACTER_SELECT",
    "STARTING_WEAPON_SELECT",
    "DANGER_SELECT",
    "RUN_LOADING",
    "COMBAT",
    "CRATE_RESOLUTION",
    "LEVEL_UP",
    "SHOP",
    "VICTORY",
    "DEFEAT",
    "RECOVERY",
    "TERMINAL_ERROR",
]


def normalize_player_relative(entities: list[dict], player: dict) -> list[dict]:
    px = float(player.get("x", 0))
    py = float(player.get("y", 0))
    out = []
    for e in entities:
        d = dict(e)
        d["nx"] = float(d.get("x", 0)) - px
        d["ny"] = float(d.get("y", 0)) - py
        out.append(d)
    return out


def shop_legal_actions(items: list[dict], gold: int) -> list[Any]:
    acts: list[Any] = ["shop_go", "shop_reroll"]
    for it in items:
        slot = it["slot"]
        if it.get("affordable", gold >= it.get("price", 0)):
            acts.append({"type": "shop_buy", "slot": slot})
        acts.append({"type": "shop_lock" if not it.get("locked") else "shop_unlock", "slot": slot})
    return acts


def action_is_legal(action: dict | str, legal: list[Any]) -> bool:
    if isinstance(action, str):
        return action in legal or any(
            (isinstance(x, dict) and x.get("type") == action) for x in legal
        )
    for x in legal:
        if x == action:
            return True
        if isinstance(x, dict) and isinstance(action, dict):
            if x.get("type") == action.get("type") and x.get("slot", None) == action.get("slot", None):
                return True
    return False


def score_item_tier(tier: int, floors: list[float] | None = None) -> float:
    floors = floors or [3.0, 4.0, 8.0, 14.0, 18.0, 24.0, 30.0]
    if tier < 0:
        return floors[0]
    if tier >= len(floors):
        return floors[-1]
    return floors[tier]


def phase_transition_valid(prev: str, nxt: str) -> bool:
    if prev not in PHASES or nxt not in PHASES:
        return False
    if prev == nxt:
        return True
    allowed = {
        "BOOT": {"MAIN_MENU", "RECOVERY"},
        "MAIN_MENU": {"CHARACTER_SELECT", "RECOVERY"},
        "CHARACTER_SELECT": {"STARTING_WEAPON_SELECT", "MAIN_MENU", "RECOVERY"},
        "STARTING_WEAPON_SELECT": {"DANGER_SELECT", "CHARACTER_SELECT", "RECOVERY"},
        "DANGER_SELECT": {"RUN_LOADING", "COMBAT", "RECOVERY"},
        "RUN_LOADING": {"COMBAT", "RECOVERY"},
        "COMBAT": {"CRATE_RESOLUTION", "LEVEL_UP", "SHOP", "VICTORY", "DEFEAT", "RECOVERY", "MAIN_MENU"},
        "CRATE_RESOLUTION": {"LEVEL_UP", "SHOP", "COMBAT", "RECOVERY"},
        "LEVEL_UP": {"SHOP", "COMBAT", "CRATE_RESOLUTION", "RECOVERY"},
        "SHOP": {"COMBAT", "RUN_LOADING", "VICTORY", "DEFEAT", "RECOVERY"},
        "VICTORY": {"MAIN_MENU", "TERMINAL_ERROR"},
        "DEFEAT": {"MAIN_MENU", "TERMINAL_ERROR"},
        "RECOVERY": set(PHASES),
        "TERMINAL_ERROR": {"MAIN_MENU", "BOOT"},
    }
    return nxt in allowed.get(prev, set())


def serialize_event(run_id: str, seq: int, event: str, payload: dict) -> dict:
    return {
        "schema_version": "1.0.0",
        "run_id": run_id,
        "seq": seq,
        "ts_ms": seq * 100,
        "event": event,
        "payload": payload,
    }
