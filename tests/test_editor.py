# tests/test_editor.py
import pytest
from aksave.catalog import Catalog, challenges_from_flags
from aksave.editor import (LEAVE_ONE_FLAG, RailError, SaveEditor,
                           skipped_note, where_to_find)
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


# --- the hard-coded "leave one" trophy -------------------------------------
# Session 6 pinned exactly one location to exactly one flag by having the
# player pick the trophy up and reading what the game wrote. That single
# verified mapping is what `leave_one` now holds back, so the collectible the
# user has to find themselves is one we can actually describe.


def test_leave_one_holds_back_the_one_trophy_whose_location_we_verified():
    e = editor(ALL[:10])
    e.collect_all(leave_one=True)
    missing = [f for f in ALL if f not in e.collected]
    assert missing == [LEAVE_ONE_FLAG]
    assert e.challenge_count == 242


def test_leave_out_falls_back_to_the_ranking_when_that_trophy_is_taken():
    """If the user already has Pickup_13, leave_out must still return
    something — otherwise collect_all(leave_one=True) silently becomes a full
    collect and the achievement never fires."""
    remaining = [f for f in ALL if f != LEAVE_ONE_FLAG]
    chosen = SaveEditor.leave_out(remaining)
    assert chosen != LEAVE_ONE_FLAG
    assert chosen.split("_")[1:3] == ["CityZ", "Pickup"]


def test_collect_all_records_which_collectible_it_left():
    """The CLI and the GUI both have to tell the user what to go and find, so
    the choice cannot stay buried inside collect_all."""
    e = editor(ALL[:10])
    e.collect_all(leave_one=True)
    assert e.left_behind == LEAVE_ONE_FLAG


def test_collect_all_without_leave_one_leaves_nothing_behind():
    e = editor(ALL[:10])
    e.collect_all(leave_one=False)
    assert e.left_behind is None


def test_the_hard_coded_trophy_is_a_real_bleake_island_trophy():
    assert CAT.known(LEAVE_ONE_FLAG)
    item = CAT.item(LEAVE_ONE_FLAG)
    assert (item.region, item.type) == ("CityZ", "Pickup")


def test_the_note_describes_where_the_trophy_is_and_never_prints_its_number():
    """THE NUMBERING TRAP. Three schemes name this one object: the save flag
    says Pickup_13, the tool's own display name says "Riddler Trophy 13", and
    IGN calls it Bleake Island trophy 6. A user told "trophy 13" who then opens
    IGN goes to the wrong building — the exact confound that wasted three
    in-game attempts in session 6. Lead with the location; never print a bare
    number next to an IGN reference."""
    note = where_to_find(LEAVE_ONE_FLAG, CAT)
    assert "Bleake Island" in note
    assert "Ace Chemicals" in note
    assert "13" not in note
    assert CAT.item(LEAVE_ONE_FLAG).display not in note


def test_the_note_for_any_other_collectible_names_it_and_says_what_to_do():
    """The fallback has no location data, so the honest answer is the name plus
    the escape hatch: turn the option off."""
    other = "PickedUp_CityX_Pickup_1"
    note = where_to_find(other, CAT)
    assert CAT.item(other).display in note
    assert "leave one" in note.lower()


# --- areas the save has no Riddler records for -----------------------------
# The game creates a region's challenge records the first time the player goes
# there. `Riddler 123` in the corpus has 15 records and 5 per-region records
# rather than 18 and 6, because it has never reached Arkham Knight HQ. The
# corpus is not on CI, so the shape is synthesised here too.


def test_the_fixture_can_build_a_save_that_has_never_reached_an_area():
    e = SaveEditor(make_save_with_flags(ALL[:10], skip_regions=("HideOut",)), CAT)
    assert e.untracked_regions == {"HideOut"}
    assert len(e.save.read_challenge_records()) == 15
    assert len(e.save.read_region_records()) == 5


def test_skipped_note_names_the_area_and_says_how_to_fix_it():
    e = SaveEditor(make_save_with_flags(ALL[:10], skip_regions=("HideOut",)), CAT)
    note = skipped_note(e)
    assert "Arkham Knight HQ" in note
    assert "visit" in note.lower()


def test_skipped_note_is_silent_when_every_area_is_tracked():
    assert skipped_note(editor(ALL[:10])) is None


def test_skipped_note_is_plain_ascii():
    """It is printed by the CLI, and a Windows console is not UTF-8."""
    e = SaveEditor(make_save_with_flags(ALL[:10], skip_regions=("HideOut",)), CAT)
    assert skipped_note(e).isascii()


def test_collect_all_on_such_a_save_stops_short_and_the_note_explains_it():
    e = SaveEditor(make_save_with_flags(ALL[:10], skip_regions=("HideOut",)), CAT)
    e.collect_all(leave_one=False)
    assert e.challenge_count == 216          # 243 minus Arkham Knight HQ's 27
    assert skipped_note(e) is not None


# --- a save with nothing collected in it yet -------------------------------
# The user opened their clean new-game slot in the packaged tool and got
# "no world-state store holding collectibles was found" in a dialog box titled
# "Cannot read save". Both halves of that are wrong for a player: the save read
# perfectly well, and the sentence describes our parser rather than their game.


def test_a_save_with_nothing_collected_is_refused_before_anything_else():
    """The tool identifies the world-state store by finding a PickedUp_ key in
    it. With no collectibles anywhere there is no key to find, so there is
    genuinely nothing to edit — but that has to be said in those terms."""
    with pytest.raises(RailError, match="no Riddler collectibles"):
        SaveEditor(make_save_with_flags([]), CAT)


def test_that_refusal_tells_the_player_what_to_do_about_it():
    with pytest.raises(RailError) as exc:
        SaveEditor(make_save_with_flags([]), CAT)
    message = str(exc.value)
    assert "pick up" in message.lower() or "collect" in message.lower()
    assert "save" in message.lower()
    assert "world-state" not in message, "that is a sentence about our parser"
    assert message.isascii()


def test_a_save_holding_a_single_collectible_is_accepted():
    """One is enough: it is the key that identifies the store."""
    e = SaveEditor(make_save_with_flags(["PickedUp_CityZ_Pickup_1"]), CAT)
    assert e.collected_count == 1


def test_flags_that_are_not_collectibles_do_not_count_as_progress():
    """The corpus save an hour into the game carries 143 flags and not one
    PickedUp_, and it is refused for exactly the same reason as a brand-new
    one — so the refusal must key off collectibles, not off flags."""
    with pytest.raises(RailError, match="no Riddler collectibles"):
        SaveEditor(make_save_with_flags(["SomeStoryFlag", "AnotherFlag"]), CAT)


# --- GOG/Epic saves --------------------------------------------------------
# A supported platform whose only end-to-end coverage was corpus-gated, so it
# ran nowhere except this machine. GOG/Epic files carry a 4-byte prefix ahead
# of the body, and every offset in the writer is relative to the body.


def test_a_gog_save_is_edited_and_keeps_its_prefix(gog_prefix=b"\x00\x0a\x0a\x00"):
    raw = gog_prefix + make_save_with_flags(ALL[:10])
    e = SaveEditor(raw, CAT)
    assert e.platform == "GOG/Epic"
    e.collect_all(leave_one=False)
    out = e.to_bytes()
    assert out[:4] == gog_prefix
    assert len(out) == len(raw)

    again = SaveEditor(out, CAT)
    assert again.platform == "GOG/Epic"
    assert again.challenge_count == 243


def test_the_prefix_does_not_shift_any_structure_the_writer_touches():
    """The bug this guards against is silent: every locator is an offset into
    `body`, so a prefix leaking into one of them would corrupt a GOG save
    while a Steam save stayed perfect."""
    steam = SaveEditor(make_save_with_flags(ALL[:10]), CAT)
    gog = SaveEditor(b"\x00\x0a\x0a\x00" + make_save_with_flags(ALL[:10]), CAT)
    steam.collect_all(leave_one=False)
    gog.collect_all(leave_one=False)
    assert gog.to_bytes()[4:] == steam.to_bytes()
