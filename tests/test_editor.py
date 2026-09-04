# tests/test_editor.py
import pytest
from aksave.catalog import Catalog, challenges_from_flags
from aksave.editor import SaveEditor, RailError
from tests.test_sgd import make_save_with_flags

CAT = Catalog.load()
ALL = [i.flag for i in CAT.items]


def editor(flags):
    return SaveEditor(make_save_with_flags(flags or ["Placeholder"]), CAT)


def test_reports_current_state():
    e = editor(ALL[:10])
    assert e.collected_count == 10
    assert e.challenge_count == challenges_from_flags(ALL[:10])


def test_collect_adds_only_missing():
    e = editor(ALL[:10])
    e.collect(ALL[:20])
    assert e.collected_count == 20


def test_rejects_flag_not_on_manifest():
    e = editor(ALL[:10])
    with pytest.raises(RailError, match="not a known collectible"):
        e.collect(["PickedUp_CityZ_Pickup_999"])


def test_rejects_forbidden_flag():
    e = editor(ALL[:10])
    with pytest.raises(RailError, match="never writable"):
        e.collect(["CatCollarRemoved"])


def test_sets_all_trophies_collected_only_at_full_set():
    e = editor(ALL[:314])
    assert "All_Trophies_Collected" not in e.flags
    e.collect(ALL)
    assert "All_Trophies_Collected" in e.flags


def test_leave_one_stops_at_242():
    e = editor(ALL[:10])
    e.collect_all(leave_one=True)
    assert e.challenge_count == 242
    assert "All_Trophies_Collected" not in e.flags


def test_collect_all_reaches_243():
    e = editor(ALL[:10])
    e.collect_all(leave_one=False)
    assert e.challenge_count == 243


def test_output_round_trips():
    e = editor(ALL[:10])
    e.collect_all(leave_one=False)
    reloaded = SaveEditor(e.to_bytes(), CAT)
    assert reloaded.challenge_count == 243


# --- regressions -----------------------------------------------------------


def test_completion_flag_is_not_counted_as_a_collectible():
    """It is a marker, not an object.

    Counting it toward the 315 fired the auto-append one object early and then
    wrote the flag a second time, leaving a duplicated FString in a format
    where we treat occurrence count as potentially meaningful.
    """
    e = editor(ALL[:313])
    added = e.collect([ALL[313], "All_Trophies_Collected"])
    assert added.count("All_Trophies_Collected") == 1
    assert e.flags.count("All_Trophies_Collected") == 1
    assert e.collected_count == 314
    assert e.challenge_count == challenges_from_flags(ALL[:314])


def test_duplicate_names_in_one_batch_are_written_once():
    """append_flags only sees the save, so a repeat inside one call slipped
    through and was written twice."""
    e = editor(ALL[:10])
    assert e.collect([ALL[20], ALL[20]]) == [ALL[20]]
    assert e.flags.count(ALL[20]) == 1


def test_completion_flag_can_still_be_added_to_an_already_full_save():
    """This state exists in the wild: a real GOG corpus save holds all 315
    objects with the marker absent. The early exit made it unreachable."""
    e = editor(ALL)
    assert "All_Trophies_Collected" not in e.flags
    assert e.collect_all(leave_one=False) == ["All_Trophies_Collected"]
    assert "All_Trophies_Collected" in e.flags
    assert e.challenge_count == 243


# --- writing every cache, not just the array -------------------------------
#
# The first in-game test loaded an edited save cleanly and showed the ORIGINAL
# progress, because only the primary array had been written. These tests pin
# each of the other locations the game keeps.


def test_collect_mirrors_into_every_world_state_store():
    e = editor(ALL[:10])
    e.collect(ALL[:20])
    for store in e.save.read_stores():
        assert {k for k in store.keys if k.startswith("PickedUp_")} == e.collected


def test_store_values_for_new_keys_are_one():
    import struct
    e = editor(ALL[:10])
    before = e.save.read_stores()[0].count
    e.collect(ALL[:12])
    store = e.save.read_stores()[0]
    values = struct.unpack_from(f"<{store.count}i", e.save.body, store.vals_start)
    assert list(values[before:]) == [1, 1]


def test_collect_updates_the_cached_counter_string():
    e = editor(ALL[:10])
    e.collect(ALL[:40])
    counters = e.save.read_counters()
    assert counters.values[counters.RIDDLER] == f"{e.challenge_count}/243"


def test_collect_updates_the_progress_cache_and_its_total():
    from aksave.catalog import trophies_by_region
    from aksave.sgd import CACHE_REGIONS
    e = editor(ALL[:10])
    e.collect_all(leave_one=False)
    by_region = trophies_by_region(e.flags)
    expected = [by_region.get(r, 0) for r in CACHE_REGIONS]
    trophies, total = e.save.read_trophy_cache()
    assert trophies == expected
    assert total == sum(expected) == 179


def test_collect_updates_the_second_per_region_copy():
    from aksave.catalog import trophies_by_region
    from aksave.sgd import CACHE_REGIONS
    e = editor(ALL[:10])
    e.collect_all(leave_one=False)
    by_region = trophies_by_region(e.flags)
    for offset, region_id in e.save.read_region_records():
        region = CACHE_REGIONS[region_id - 1]
        assert e.save.body[e.save.region_count_offset(offset)] == by_region[region]


def test_counter_string_growing_a_digit_keeps_the_file_parseable():
    """9/243 -> 243/243 inserts two bytes into section 1, shifting every
    section after it. Everything must still be locatable afterwards."""
    e = editor(ALL[:9])
    assert len(e.save.read_counters().values[1].split("/")[0]) == 1
    e.collect_all(leave_one=False)
    reloaded = SaveEditor(e.to_bytes(), CAT)
    assert reloaded.challenge_count == 243
    assert reloaded.save.read_counters().values[1] == "243/243"
    assert reloaded.save.read_trophy_cache()[1] == 179


def test_a_save_with_no_region_records_is_refused_rather_than_half_edited():
    import pytest as _pytest
    from aksave.sgd import SgdError
    raw = make_save_with_flags(ALL[:10], regions=False)
    with _pytest.raises(SgdError, match="per-region"):
        SaveEditor(raw, CAT)


def test_leave_one_leaves_a_reachable_bleake_island_trophy():
    """It used to leave "Riddle 2 — Stagg Airships".

    A riddle needs you to know where to stand and what to scan, and Stagg is
    not reachable early, so the one thing the user had to do themselves was the
    hardest thing on the list.
    """
    e = editor(ALL[:10])
    e.collect_all(leave_one=True)
    missing = [f for f in ALL if f not in e.collected]
    assert len(missing) == 1
    region, type_ = missing[0].split("_")[1], missing[0].split("_")[2]
    assert (region, type_) == ("CityZ", "Pickup")
    assert e.challenge_count == 242


def test_leave_one_falls_back_when_bleake_is_already_finished():
    already = [f for f in ALL if f.split("_")[1] == "CityZ"]
    e = editor(already)
    e.collect_all(leave_one=True)
    missing = [f for f in ALL if f not in e.collected]
    assert len(missing) == 1
    assert missing[0].split("_")[2] == "Pickup"     # still a trophy, not a riddle
    assert e.challenge_count == 242


def test_both_world_state_stores_are_updated():
    """12 corpus saves carry a second complete world state in section 0x20,
    and all of the user's own do. Updating only the first leaves the game
    reading a stale copy — the same bug as writing only the primary array."""
    raw = make_save_with_flags(ALL[:10], second_store=True)
    e = SaveEditor(raw, CAT)
    assert len(e.save.read_stores()) == 2
    e.collect(ALL[:30])
    stores = e.save.read_stores()
    assert len(stores) == 2
    for store in stores:
        assert {k for k in store.keys if k.startswith("PickedUp_")} == e.collected


def test_collect_marks_the_matching_challenge_slots():
    e = editor(ALL[:10])
    e.collect_all(leave_one=False)
    records = e.save.read_challenge_records()
    assert sum(1 for _, _, values in records for v in values if v >= 4) == 243
    for _, puzzle_id, values in records:
        assert CAT.puzzle(puzzle_id).satisfied(e.collected) == [v >= 4 for v in values]


def test_challenge_slots_already_solved_are_left_alone():
    """A slot the game marked 4 (just collected) is still solved; rewriting it
    to 5 would be a disturbance with nothing to gain."""
    from aksave.sgd import SgdFile
    raw = bytearray(make_save_with_flags(ALL[:40]))
    s = SgdFile(bytes(raw))
    first, puzzle_id, values = next(r for r in s.read_challenge_records()
                                    if any(v >= 4 for v in r[2]))
    solved_at = next(i for i, v in enumerate(values) if v >= 4)
    raw[first + solved_at] = 4
    e = SaveEditor(bytes(raw), CAT)
    e.collect(ALL[:30])
    after = next(r for r in e.save.read_challenge_records() if r[1] == puzzle_id)
    assert after[2][solved_at] == 4
