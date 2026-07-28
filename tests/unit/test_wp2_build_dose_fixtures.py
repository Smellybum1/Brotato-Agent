import io
import json
from pathlib import Path

import pytest

from scripts import wp2_build_dose_fixtures as mod


def _save(wave: int = 16, boss: str = "boss_crab", weapon: str = "weapon_smg_2") -> dict:
    return {
        "current_run_state": {
            "current_wave": wave,
            "bosses_spawn": [boss],
            "enemy_scaling": {"damage": 1, "health": 1, "speed": 1},
            "players_data": [{"gold": 25, "weapons": [{"my_id": weapon}]}],
        }
    }


def _write_snapshot(path: Path, payload: dict) -> None:
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh)


def _index_row(**kw):
    base = {
        "digest": "d0",
        "file": "f.json",
        "source_run_id": "run_a",
        "current_wave": 16,
        "gold": 10,
        "hp": 40,
        "level": 18,
        "n_weapons": 6,
        "n_items": 30,
        "boss": "predator",
    }
    base.update(kw)
    return base


def test_selects_lowest_gold_per_run():
    rows = [
        _index_row(source_run_id="r1", gold=400, digest="hi"),
        _index_row(source_run_id="r1", gold=25, digest="lo"),
        _index_row(source_run_id="r2", gold=7, digest="r2lo"),
    ]
    sel = mod.select_fixtures(rows)
    assert [r["digest"] for r in sel] == ["lo", "r2lo"]


def test_filters_to_wave_16_only():
    rows = [
        _index_row(source_run_id="r1", current_wave=15, gold=1, digest="w15"),
        _index_row(source_run_id="r1", current_wave=16, gold=500, digest="w16"),
        _index_row(source_run_id="r2", current_wave=17, gold=1, digest="w17"),
    ]
    sel = mod.select_fixtures(rows)
    assert [r["digest"] for r in sel] == ["w16"]


def test_all_three_arms_round_tripped_identically(tmp_path: Path):
    src = tmp_path / "src.json"
    _write_snapshot(src, _save())
    outs = {}
    for arm, dose in mod.ARMS:
        out = tmp_path / f"out__{arm}.json"
        mod.build_arm(src, out, dose)
        outs[arm] = mod.read_json(out)

    for arm, dose in mod.ARMS:
        state = outs[arm]["current_run_state"]
        assert state["enemy_scaling"]["health"] == dose
        assert state["enemy_scaling"]["damage"] == 1
        assert state["enemy_scaling"]["speed"] == 1
        assert state["current_wave"] == 16
        assert state["bosses_spawn"] == ["boss_crab"]

    # The control is NOT a byte copy: it went through the same load/dump path, so
    # every arm differs from every other ONLY in enemy_scaling.health.
    for arm in ("H75", "H50"):
        a = json.loads(json.dumps(outs["C"]))
        b = json.loads(json.dumps(outs[arm]))
        a["current_run_state"]["enemy_scaling"]["health"] = None
        b["current_run_state"]["enemy_scaling"]["health"] = None
        assert a == b

    # No BOM, LF only.
    raw = (tmp_path / "out__C.json").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in raw


def test_readback_assertion_fires_on_corrupted_write(tmp_path: Path, monkeypatch):
    src = tmp_path / "src.json"
    _write_snapshot(src, _save())

    def corrupt_write(path, payload):
        bad = json.loads(json.dumps(payload))
        bad["current_run_state"]["enemy_scaling"]["health"] = 1
        with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(bad, fh)

    monkeypatch.setattr(mod, "write_json", corrupt_write)
    with pytest.raises(SystemExit) as exc:
        mod.build_arm(src, tmp_path / "bad.json", 0.5)
    assert "readback mismatch" in str(exc.value)


def test_readback_assertion_fires_on_dropped_weapons(tmp_path: Path, monkeypatch):
    src = tmp_path / "src.json"
    _write_snapshot(src, _save())

    def corrupt_write(path, payload):
        bad = json.loads(json.dumps(payload))
        bad["current_run_state"]["players_data"][0]["weapons"] = []
        with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(bad, fh)

    monkeypatch.setattr(mod, "write_json", corrupt_write)
    with pytest.raises(SystemExit) as exc:
        mod.build_arm(src, tmp_path / "bad2.json", 0.75)
    assert "weapons=" in str(exc.value)
