"""Tests for the snapshot collector's library-selection helpers."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.wp2_snapshot_collector import (
    boss_label,
    newest_telemetry_run_id,
    select_library,
)


def row(digest, boss="predator", gold=100, src="run_a", **over):
    rec = {"digest": digest, "file": f"{digest}.json", "boss": boss,
           "gold": gold, "source_run_id": src}
    rec.update(over)
    return rec


def test_one_row_per_source_run_id():
    rows = [row("a", src="run_1"), row("b", src="run_1"), row("c", src="run_2")]
    out = select_library(rows, "predator")
    assert len(out) == 2
    assert {r["source_run_id"] for r in out} == {"run_1", "run_2"}


def test_prefers_lowest_gold_row_within_a_run():
    rows = [row("hi", gold=250, src="run_1"), row("lo", gold=12, src="run_1")]
    out = select_library(rows, "predator")
    assert [r["digest"] for r in out] == ["lo"]


def test_lowest_gold_regardless_of_index_order():
    rows = [row("lo", gold=5, src="run_1"), row("hi", gold=900, src="run_1")]
    assert [r["digest"] for r in select_library(rows, "predator")] == ["lo"]


def test_filters_by_boss():
    rows = [row("a", boss="predator", src="run_1"), row("b", boss="invoker", src="run_2")]
    out = select_library(rows, "invoker")
    assert [r["digest"] for r in out] == ["b"]


def test_null_source_run_id_rows_are_separate_entries():
    rows = [row("a", src=None, gold=10), row("b", src=None, gold=999)]
    out = select_library(rows, "predator")
    assert len(out) == 2
    assert {r["digest"] for r in out} == {"a", "b"}


def test_missing_source_run_id_key_is_its_own_group():
    rows = [row("a"), row("b")]
    for r in rows:
        r.pop("source_run_id")
    assert len(select_library(rows, "predator")) == 2


def test_one_per_run_false_returns_every_matching_row():
    rows = [row("a", src="run_1"), row("b", src="run_1"), row("c", boss="invoker")]
    out = select_library(rows, "predator", one_per_run=False)
    assert [r["digest"] for r in out] == ["a", "b"]


def test_row_without_boss_field_falls_back_to_bosses_spawn():
    r = {"digest": "a", "bosses_spawn": ["boss_crab"], "gold": 1, "source_run_id": "run_1"}
    assert boss_label(["boss_crab"]) == "predator"
    assert [x["digest"] for x in select_library([r], "predator")] == ["a"]


def test_unknown_gold_never_beats_a_known_gold():
    rows = [row("known", gold=400, src="run_1"), row("unknown", gold=None, src="run_1")]
    assert [r["digest"] for r in select_library(rows, "predator")] == ["known"]


def test_empty_rows():
    assert select_library([], "predator") == []


def test_newest_telemetry_run_id_picks_latest_events_mtime(tmp_path):
    for name, mtime in (("run_old", 1000), ("run_new", 5000)):
        d = tmp_path / name
        d.mkdir()
        ev = d / "events.jsonl"
        ev.write_text("{}\n", encoding="utf-8")
        import os

        os.utime(ev, (mtime, mtime))
    assert newest_telemetry_run_id(tmp_path) == "run_new"


def test_newest_telemetry_run_id_none_when_no_candidates(tmp_path):
    (tmp_path / "empty_dir").mkdir()
    assert newest_telemetry_run_id(tmp_path) is None


def test_newest_telemetry_run_id_none_when_root_missing(tmp_path):
    assert newest_telemetry_run_id(tmp_path / "nope") is None


def test_both_boss_ids_map_to_verified_entities():
    """Both mappings were verified against real runs, not guessed.

    boss_crab -> predator: run_1785036448_61774 (bosses_spawn ["boss_crab"], then
    predator captures at wave 20). boss_wizard -> invoker: run_1785042605_79051
    (bosses_spawn ["boss_wizard"], then 1,397 invoker captures at wave 20).

    This matters because predator is the boss the agent actually loses to, while
    invoker has never beaten it. Mislabelling would silently build a library of
    the easy boss -- the exact failure the collector's own docstring warns about.
    """
    assert boss_label(["boss_crab"]) == "predator"
    assert boss_label(["boss_wizard"]) == "invoker"
    # An unknown id must fall through to the RAW id, never a plausible guess.
    assert boss_label(["boss_unknown_future"]) == "boss_unknown_future"
    assert boss_label(None) == "unknown"


def test_stale_stored_label_does_not_hide_a_fixture():
    """A row archived before an id was mapped carries a RAW id in `boss`.

    Rows written on 2026-07-26 before boss_wizard->invoker was added store
    boss="boss_wizard". Selecting for "invoker" must still find them, or the
    Invoker fixtures -- the planned internal control for a latency fix -- become
    silently unselectable. An "if absent" fallback never fires for these rows
    because the field is present, just stale.
    """
    stale = {"digest": "d1", "boss": "boss_wizard", "bosses_spawn": ["boss_wizard"],
             "gold": 45, "source_run_id": "run_x"}
    assert len(select_library([stale], "invoker")) == 1
    assert select_library([stale], "boss_wizard") == []
    assert select_library([stale], "predator") == []
