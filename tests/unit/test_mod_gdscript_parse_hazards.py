"""Static guards for GDScript constructs that fail at PARSE time.

There is no headless Godot in this repo, so mod GDScript is never executed by the
test suite — the first real parse happens at the deploy smoke. A parse error there
takes down the entire mod (ModLoader logs the error, the bot never installs, and
the game sits on the title screen looking like a hang rather than a crash), which
costs a full build/deploy/launch cycle to discover.

The v127 deploy smoke lost a cycle to exactly this: v126 shipped
`elif "items" in RunData and RunData.items != null:` in agent_controller.gd, and
Godot 3 rejects `in` against an autoload at parse time with

    Parse Error: Invalid operand types ("String" and "null") to operator "in".

The codebase already knew (adapter/game_adapter.gd::_danger carries the warning);
nothing enforced it. These tests are cheap and they enforce it.
"""
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MOD_ROOT = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent"

# Autoload singletons this mod reaches into. The parser resolves these names at
# compile time, which is exactly why `in` against them is a parse error rather
# than a runtime one.
AUTOLOADS = (
    "RunData",
    "ProgressData",
    "ItemService",
    "EntityService",
    "MusicManager",
    "Keys",
    "Utils",
)

# A string literal tested against a capitalized identifier. Instance/local names in
# this mod are lowercase (`item`, `owned`, `w`, `state`), so the capital is a
# reliable marker for a class or autoload.
STRING_IN_TYPE = re.compile(r'"[^"]*"\s+in\s+([A-Z][A-Za-z0-9_]*)\b')


def _mod_scripts():
    return sorted(MOD_ROOT.rglob("*.gd"))


def _offending_lines():
    hits = []
    for path in _mod_scripts():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            match = STRING_IN_TYPE.search(code)
            if match:
                hits.append((path.relative_to(ROOT).as_posix(), lineno, line.strip()))
    return hits


def test_mod_scripts_are_discovered():
    # Guards against the sweep silently passing because it scanned nothing.
    scripts = _mod_scripts()
    assert len(scripts) >= 10
    assert any(p.name == "agent_controller.gd" for p in scripts)


def test_no_in_operator_against_autoloads():
    hits = _offending_lines()
    assert hits == [], (
        "`\"prop\" in <Autoload/Class>` is a Godot 3 PARSE error and will take the "
        "whole mod down at deploy. Probe with `Obj.get(\"prop\") != null` instead "
        "(see adapter/game_adapter.gd::_danger):\n"
        + "\n".join(f"  {p}:{n}: {t}" for p, n, t in hits)
    )


def test_autoload_property_probes_use_get():
    # The two probes that motivated this guard, pinned by their fixed form.
    controller = (MOD_ROOT / "runtime/agent_controller.gd").read_text(encoding="utf-8")
    assert 'elif RunData.get("items") != null:' in controller
    assert 'var value = RunData.get("bonus_gold")' in controller


def test_regex_actually_catches_the_v126_regression():
    # Mutation check: the guard is worthless if it cannot see the original defect.
    assert STRING_IN_TYPE.search('\telif "items" in RunData and RunData.items != null:')
    # ...and it must not fire on `in` against an untyped local, which is legal.
    assert not STRING_IN_TYPE.search('\tsnap["value"] = int(item.value) if ("value" in item) else 1')
    assert not STRING_IN_TYPE.search('\t\tif owned == null or not ("my_id" in owned):')
