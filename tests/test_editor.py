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
