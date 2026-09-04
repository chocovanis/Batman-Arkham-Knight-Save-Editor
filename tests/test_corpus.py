"""Regression tests against the real save corpus.

Set AK_CORPUS to the folder holding the save collections. Skipped otherwise,
because the corpus is copyrighted game data and is never committed.
"""
import os
import re
from pathlib import Path

import pytest

from aksave.catalog import challenges_from_flags
from aksave.sgd import SgdFile

CORPUS = os.environ.get("AK_CORPUS")
pytestmark = pytest.mark.skipif(not CORPUS, reason="AK_CORPUS not set")

# (relative path, expected challenge count) — verified by hand against the
# game's own cached counter string in every case.
CASES = [
    ("MySaves/BAK1Save1x1.sgd", 0),
    ("Save files 1/Riddler Save Game/Riddler 123 from 243 main story 59 procent/BAK1Save2x0.sgd", 123),
    ("Save files 1/Riddler Save Game/Riddler 143 of 243/BAK1Save2x0.sgd", 143),
    ("Save files 1/Riddler Save Game/Riddler 183 from 243/BAK1Save2x0.sgd", 183),
    ("Save files 1/Riddler Save Game/Riddler 223 from 243/BAK1Save2x0.sgd", 223),
    ("Save files 5/BAK1Save3x0.sgd", 0),
    ("Save files 6/BAK1Save0x0.sgd", 242),
    ("Save files 6/BAK1Save0x1.sgd", 243),
    ("Save files 3/BAK1Save0x0.sgd", 243),          # GOG/Epic variant
    ("MySaves/BAK1Save0x0.sgd", 243),
]


def load(rel):
    return SgdFile((Path(CORPUS) / rel).read_bytes())


@pytest.mark.parametrize("rel,expected", CASES)
def test_challenge_count_matches_games_own_counter(rel, expected):
    save = load(rel)
    save.validate()
    assert challenges_from_flags(save.read_flags()) == expected

    # The game caches its own counter string; it must agree with our maths.
    counters = re.findall(rb"\d{1,3}/243", bytes(save.body[:0x8000]))
    if counters:
        assert counters[0].decode() == f"{expected}/243" or \
               f"{expected}/243".encode() in counters


def test_gog_variant_detected():
    assert load("Save files 3/BAK1Save0x0.sgd").platform == "GOG/Epic"
    assert load("MySaves/BAK1Save0x0.sgd").platform == "Steam"


def test_appending_reproduces_a_real_save_transition():
    """SF6 0x0 -> 0x1 differ by one collectible. Our append must match."""
    before, after = load("Save files 6/BAK1Save0x0.sgd"), load("Save files 6/BAK1Save0x1.sgd")
    added = [f for f in after.read_flags() if f not in set(before.read_flags())]
    assert added == ["PickedUp_HideOut_Pickup_15", "All_Trophies_Collected"]

    grew = before.append_flags(added)
    assert grew == 58
    assert challenges_from_flags(before.read_flags()) == 243
    before.validate()


def all_saves():
    """Every real save in the corpus, excluding our own generated proofs."""
    for path in sorted(Path(CORPUS).rglob("*.sgd")):
        if "proof" not in path.parts:
            yield path


def test_every_corpus_save_mirrors_its_flags_into_the_store():
    """The invariant the old writer broke.

    In every genuine save the set of PickedUp_ keys in every world-state store
    is exactly the set in the primary flag array. An edit that updates one and not
    the other produces a file the game loads and then ignores.
    """
    checked = 0
    for path in all_saves():
        save = SgdFile(path.read_bytes())
        primary = {f for f in save.read_flags() if f.startswith("PickedUp_")}
        if not primary:
            continue                      # brand-new saves have no store yet
        for store in save.read_stores():
            assert {k for k in store.keys
                    if k.startswith("PickedUp_")} == primary, (path, hex(store.len_off))
        checked += 1
    assert checked > 50


def test_challenge_maths_matches_every_cached_counter_in_the_corpus():
    """Ground truth for the number we now write onto the HUD."""
    for path in all_saves():
        save = SgdFile(path.read_bytes())
        counters = save.read_counters()
        assert counters.values[counters.RIDDLER] == \
            f"{challenges_from_flags(save.read_flags())}/243", path


def test_progress_cache_agrees_with_the_flags_in_every_corpus_save():
    from aksave.catalog import trophies_by_region
    from aksave.sgd import CACHE_REGIONS
    for path in all_saves():
        save = SgdFile(path.read_bytes())
        by_region = trophies_by_region(save.read_flags())
        expected = [by_region.get(r, 0) for r in CACHE_REGIONS]
        trophies, total = save.read_trophy_cache()
        assert trophies == expected, path
        assert total == sum(expected), path
        for offset, region_id in save.read_region_records():
            assert save.body[save.region_count_offset(offset)] == \
                expected[region_id - 1], path


def test_synthesised_243_matches_the_real_one_everywhere_it_should():
    """The end-to-end proof: edit SF6 0x0 and compare against SF6 0x1.

    The two rotations are about three minutes of play apart, so they also
    differ in position, streamed levels, difficulty tiers, stats counters and
    an unlocked concept-art entry. None of that is collectible state. What must
    match is every location that records collectibles — and the section-2 byte
    length, which the game grew by exactly the amount our insert grows it.
    """
    from aksave.editor import SaveEditor

    source = (Path(CORPUS) / "Save files 6/BAK1Save0x0.sgd").read_bytes()
    editor = SaveEditor(source)
    assert editor.challenge_count == 242
    assert editor.collect(["PickedUp_HideOut_Pickup_15"]) == [
        "PickedUp_HideOut_Pickup_15", "All_Trophies_Collected"]

    ours = SgdFile(editor.to_bytes())
    theirs = load("Save files 6/BAK1Save0x1.sgd")

    assert ours.read_flags() == theirs.read_flags()
    assert ours.read_counters().values == theirs.read_counters().values
    assert ours.read_trophy_cache() == theirs.read_trophy_cache()
    assert [(i, ours.body[ours.region_count_offset(o)])
            for o, i in ours.read_region_records()] == \
           [(i, theirs.body[theirs.region_count_offset(o)])
            for o, i in theirs.read_region_records()]
    assert [{k for k in s.keys if k.startswith("PickedUp_")} for s in ours.read_stores()] == \
           [{k for k in s.keys if k.startswith("PickedUp_")} for s in theirs.read_stores()]

    # The per-challenge bytes must agree on which challenges are done. They
    # need not agree byte for byte: 4 and 5 both mean solved, and the game
    # writes 4 on a fresh pickup that later settles to 5. We write the settled
    # value, which is what two fully complete corpus saves carry throughout.
    def solved(save):
        return [[v >= 4 for v in values]
                for _, _, values in save.read_challenge_records()]
    assert solved(ours) == solved(theirs)
    assert sum(v for record in solved(ours) for v in record) == 243

    assert ours.u32(0x10) == theirs.u32(0x10)
    assert len(ours.to_bytes()) == len(source)


def test_editing_a_gog_save_keeps_the_prefix_and_still_validates():
    from aksave.editor import SaveEditor
    raw = (Path(CORPUS) / "Save files 3/BAK1Save0x0.sgd").read_bytes()
    editor = SaveEditor(raw)
    assert editor.platform == "GOG/Epic"
    editor.collect_all(leave_one=False)          # only the completion marker
    out = editor.to_bytes()
    assert len(out) == len(raw)
    assert out[:4] == raw[:4]
    assert SaveEditor(out).challenge_count == 243


def test_the_challenge_records_reproduce_the_games_own_counter():
    """The per-challenge status bytes ARE the collectibles-menu model.

    18 records totalling exactly 243 status bytes, and the number of bytes >= 4
    equals the counter the game displays — on every corpus save that has them.
    This was very nearly written off as difficulty tuning.
    """
    checked = 0
    for path in all_saves():
        save = SgdFile(path.read_bytes())
        records = save.read_challenge_records()
        if not records:
            continue
        done = sum(1 for _, _, values in records for v in values if v >= 4)
        counters = save.read_counters()
        assert f"{done}/243" == counters.values[counters.RIDDLER], path
        if len(records) == 18:
            assert sum(len(v) for _, _, v in records) == 243, path
        checked += 1
    assert checked > 50


def test_each_status_byte_matches_its_piece_in_the_manifest():
    """Slot i of puzzle P is solved iff piece i of puzzle P is held.

    The manifest's puzzle table comes from the game's own DefaultGame.ini; this
    is what proves it lines up with what the saves actually contain.
    """
    from aksave.catalog import Catalog
    catalog = Catalog.load()
    checked = 0
    for path in all_saves():
        save = SgdFile(path.read_bytes())
        collected = {f for f in save.read_flags() if f.startswith("PickedUp_")}
        for _, puzzle_id, values in save.read_challenge_records():
            puzzle = catalog.puzzle(puzzle_id)
            assert len(puzzle.pieces) == len(values), (path, puzzle_id)
            assert puzzle.satisfied(collected) == [v >= 4 for v in values], \
                (path, puzzle_id)
            checked += len(values)
    assert checked > 12000


def test_saves_with_a_second_store_have_both_in_agreement():
    """12 corpus saves — including every one of the user's own — carry a
    complete second copy of the world state in section 0x20. An edit that
    updated only the first would leave the game reading a stale copy."""
    seen_two = 0
    for path in all_saves():
        save = SgdFile(path.read_bytes())
        primary = {f for f in save.read_flags() if f.startswith("PickedUp_")}
        if not primary:
            continue
        stores = save.read_stores()
        seen_two += len(stores) > 1
        for store in stores:
            assert {k for k in store.keys
                    if k.startswith("PickedUp_")} == primary, (path, hex(store.len_off))
    assert seen_two >= 12


def test_a_real_two_store_save_round_trips_untouched():
    """Every corpus save with two stores is already at 243/243, so this is the
    strongest thing the corpus can say about them; the write path itself is
    covered by test_editor's synthetic two-store save."""
    from aksave.editor import SaveEditor
    raw = (Path(CORPUS) / "MySaves/BAK1Save0x0.sgd").read_bytes()
    editor = SaveEditor(raw)
    assert len(editor.save.read_stores()) == 2
    assert editor.challenge_count == 243
    assert editor.to_bytes() == raw


def test_a_mid_game_save_refuses_regions_it_has_no_records_for():
    """`Riddler 123` has never been to Arkham Knight HQ, so it holds 15
    challenge records, not 18. Granting its 27 HQ challenges anyway would give
    a save whose counter said 243 while its menu showed 216."""
    from aksave.editor import SaveEditor, RailError
    editor = SaveEditor((Path(CORPUS) / "Save files 1/Riddler Save Game/"
                         "Riddler 123 from 243 main story 59 procent/"
                         "BAK1Save2x0.sgd").read_bytes())
    assert editor.untracked_regions == {"HideOut"}
    with pytest.raises(RailError, match="Arkham Knight HQ"):
        editor.collect(["PickedUp_HideOut_Pickup_1"])

    editor.collect_all(leave_one=False)
    done = sum(1 for _, _, values in editor.save.read_challenge_records()
               for v in values if v >= 4)
    assert done == 216                                   # 243 minus HQ's 27
    assert editor.save.read_counters().values[1] == "216/243"
    assert challenges_from_flags(editor.save.read_flags()) == 216


def test_a_save_that_has_been_everywhere_reaches_243():
    from aksave.editor import SaveEditor
    editor = SaveEditor((Path(CORPUS) / "Save files 1/Riddler Save Game/"
                         "Riddler 223 from 243/BAK1Save2x0.sgd").read_bytes())
    assert editor.untracked_regions == set()
    editor.collect_all(leave_one=False)
    assert editor.challenge_count == 243
    assert editor.save.read_counters().values[1] == "243/243"
    done = sum(1 for _, _, values in editor.save.read_challenge_records()
               for v in values if v >= 4)
    assert done == 243


def test_the_riddle_array_matches_the_held_riddles_in_every_corpus_save():
    """Riddle indices are a single 1..40 space shared by all six regions, so
    one flat 63-slot array covers them. It is the fifth place collectible state
    is kept, and it is not derivable from any of the other four."""
    from aksave.catalog import Catalog
    riddles = [i for i in Catalog.load().items if i.type == "Riddler"]
    assert {i.index for i in riddles} == set(range(1, 41))
    for path in all_saves():
        save = SgdFile(path.read_bytes())
        held = {i.index for i in riddles if i.flag in set(save.read_flags())}
        _, values = save.read_riddle_array()
        assert {i for i, v in enumerate(values) if v} == held, path


def test_collecting_riddles_fills_the_riddle_array():
    from aksave.editor import SaveEditor
    editor = SaveEditor((Path(CORPUS) / "Save files 1/Riddler Save Game/"
                         "Riddler 223 from 243/BAK1Save2x0.sgd").read_bytes())
    editor.collect_all(leave_one=False)
    _, values = editor.save.read_riddle_array()
    assert {i for i, v in enumerate(values) if v} == set(range(1, 41))
    assert values[0] == 0 and all(v == 0 for v in values[41:])
