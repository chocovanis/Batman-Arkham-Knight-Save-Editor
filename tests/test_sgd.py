# tests/test_sgd.py
import struct
import pytest
from aksave.sgd import SgdFile, STEAM_SIZE, SgdError, ARRAY_PREFIX, SUM_OFFS


def make_save(prefix=b"", sections=None, array_entries=None):
    """Build a minimal but structurally valid save for unit tests."""
    sections = sections or {}
    body = bytearray(STEAM_SIZE)
    struct.pack_into("<I", body, 0x00, 6)       # format version
    struct.pack_into("<I", body, 0x14, 9)       # constant
    struct.pack_into("<I", body, 0x3C, 60)      # constant
    struct.pack_into("<f", body, 0x69, 3600.0)  # 1 hour playtime
    for off, val in sections.items():
        struct.pack_into("<I", body, off, val)
    return bytes(prefix) + bytes(body)


def test_detects_steam_platform():
    s = SgdFile(make_save())
    assert s.platform == "Steam"
    assert s.prefix_len == 0


def test_detects_gog_platform():
    s = SgdFile(make_save(prefix=struct.pack("<I", STEAM_SIZE)))
    assert s.platform == "GOG/Epic"
    assert s.prefix_len == 4


def test_rejects_wrong_size():
    with pytest.raises(SgdError, match="size"):
        SgdFile(b"\x00" * 1234)


def test_reads_version_and_playtime():
    s = SgdFile(make_save())
    assert s.version == 6
    assert s.playtime_seconds == pytest.approx(3600.0)


from aksave.sgd import encode_fstring, decode_fstring


def test_encode_fstring_length_includes_nul():
    assert encode_fstring("AB") == b"\x03\x00\x00\x00AB\x00"


def test_decode_fstring_round_trips():
    blob = encode_fstring("PickedUp_CityZ_Pickup_1")
    value, end = decode_fstring(blob, 0)
    assert value == "PickedUp_CityZ_Pickup_1"
    assert end == len(blob)


def test_flag_array_round_trip():
    names = ["Alpha", "Beta_2", "PickedUp_CityZ_Pickup_1"]
    save = make_save_with_flags(names)
    s = SgdFile(save)
    assert s.read_flags() == names


def make_save_with_flags(names, regions=True, second_store=False, skip_regions=()):
    """Build a save carrying every structure the writer touches.

    A minimal file with only the primary flag array is not good enough to test
    against any more: the whole point of the current writer is that it also
    edits the section-3 store, the section-2 progress cache, the per-region
    records and the section-1 counter string. So the fixture builds all of
    them, consistent with `names`, exactly as a real save has them.

    `regions=False` omits the per-region record block, reproducing the very
    early saves in the corpus that genuinely do not have one yet.
    `second_store=True` adds the second complete world state that 12 corpus
    saves — including all of the user's own — carry in section 0x20.
    `skip_regions=("HideOut",)` reproduces a save that has never been to an
    area. The game creates a region's records the first time the player goes
    there, so `Riddler 123` in the corpus carries 15 challenge records and 5
    per-region records rather than 18 and 6. The corpus is not available on
    CI, so this is the only place that shape gets covered there.
    """
    from aksave.catalog import Catalog, challenges_from_flags, trophies_by_region
    from aksave.sgd import (CACHE_REGIONS, CHALLENGE_DONE, RIDDLE_SLOTS,
                            RIDDLE_SOLVED)

    blob = b"".join(encode_fstring(n) for n in names)
    by_region = trophies_by_region(names)
    trophies = [by_region.get(r, 0) for r in CACHE_REGIONS]

    # --- section 1: the four display counters -------------------------
    sec1 = bytearray(b"\x00" * 64)
    # Slot 1 is the Riddler counter; the other three track unrelated things.
    counters = ["0/243", f"{challenges_from_flags(names)}/243", "0/286", "0/78"]
    sec1 += struct.pack("<I", 4)
    for text in counters:
        sec1 += encode_fstring(text)
    sec1 += b"\x00" * 64

    # --- section 2: flag array, per-region records, progress cache -----
    sec2 = bytearray(ARRAY_PREFIX) + struct.pack("<I", len(names)) + blob
    sec2 += b"\x00" * 16

    # The flat riddle-solved array, indexed by the riddle's global 1..40 number.
    solved = [0] * RIDDLE_SLOTS
    for name in names:
        parts = name.split("_")
        if name.startswith("PickedUp_") and parts[2] == "Riddler":
            solved[int(parts[3])] = RIDDLE_SOLVED
    sec2 += struct.pack("<I", RIDDLE_SLOTS)
    sec2 += struct.pack(f"<{RIDDLE_SLOTS}I", *solved)
    sec2 += b"\x00" * 16

    skipped_ids = {CACHE_REGIONS.index(r) + 1 for r in skip_regions}
    if regions:
        kept = [r for r in range(1, 7) if r not in skipped_ids]
        sec2 += struct.pack("<I", len(kept)) + b"\x00"   # count, then a filler
        for region_id in kept:
            record = bytearray(16)
            record[0] = region_id
            record[2] = 9 if region_id <= 3 else 8
            record[7] = trophies[region_id - 1]
            sec2 += record

        # The 18 per-challenge status records, one per Riddler puzzle, holding
        # one byte per piece in the manifest's order. A region the player has
        # never entered genuinely has no record, which is what regions=False
        # models.
        collected = {f for f in names if f.startswith("PickedUp_")}
        for puzzle in Catalog.load().puzzles:
            region_id = CACHE_REGIONS.index(puzzle.region) + 1
            if region_id in skipped_ids:
                continue
            status = bytes(CHALLENGE_DONE if done else 3
                           for done in puzzle.satisfied(collected))
            sec2 += bytes([0, puzzle.id, 0, region_id])
            sec2 += struct.pack("<I", len(status)) + status
    sec2 += b"\x00" * 16
    anchor = len(sec2)
    for count in (9, 9, 9, 10):
        sec2 += struct.pack("<I", count) + struct.pack(f"<{count}I", *([0] * count))
    sec2 += b"\x00" * 512
    struct.pack_into("<9I", sec2, anchor + 4, *(trophies + [0, 0, 0]))
    struct.pack_into("<I", sec2, anchor + 376, sum(trophies))

    # --- sections 3 and, optionally, 5: the world-state stores ---------
    def store(keys):
        out = bytearray(struct.pack("<I", len(keys)))
        out += b"".join(encode_fstring(k) for k in keys)
        out += struct.pack("<I", len(keys)) + struct.pack("<i", 1) * len(keys)
        return out + b"\x00" * 64

    sections = [(0x0C, sec1), (0x10, sec2), (0x18, store(list(names)))]
    if second_store:
        # Deliberately a different key order: the two stores in a real save
        # agree on content, not on order.
        sections.append((0x20, store(list(reversed(names)))))

    body = bytearray(STEAM_SIZE)
    struct.pack_into("<I", body, 0x00, 6)
    struct.pack_into("<f", body, 0x69, 3600.0)
    pos = 57
    for len_off, section in sections:
        struct.pack_into("<I", body, len_off, len(section))
        body[pos:pos + len(section)] = section
        pos += len(section)
    return bytes(body)


def test_payload_end_matches_section_sum():
    s = SgdFile(make_save_with_flags(["A"]))
    assert s.payload_end == 57 + sum(s.u32(o) for o in SUM_OFFS)


def test_validate_accepts_good_file():
    SgdFile(make_save_with_flags(["A"])).validate()  # must not raise


def test_validate_rejects_tail_garbage():
    raw = bytearray(make_save_with_flags(["A"]))
    s = SgdFile(bytes(raw))
    raw[s.payload_end + 100] = 0xFF          # non-zero past the declared end
    with pytest.raises(SgdError, match="padding"):
        SgdFile(bytes(raw)).validate()


def test_validate_rejects_absurd_playtime():
    raw = bytearray(make_save_with_flags(["A"]))
    struct.pack_into("<f", raw, 0x69, 1e12)
    with pytest.raises(SgdError, match="playtime"):
        SgdFile(bytes(raw)).validate()


def test_append_adds_flags_and_preserves_size():
    original = make_save_with_flags(["A", "B"])
    s = SgdFile(original)
    before_len = s.u32(0x10)
    s.append_flags(["PickedUp_CityZ_Pickup_1"])

    assert s.read_flags() == ["A", "B", "PickedUp_CityZ_Pickup_1"]
    assert len(s.to_bytes()) == len(original)          # size invariant
    # 23 chars + NUL + 4-byte prefix = 28
    assert s.u32(0x10) == before_len + 28
    s.validate()


def test_append_is_exact_byte_arithmetic():
    """The game grew section 2 by exactly 58 for these two names (spec 4.1)."""
    s = SgdFile(make_save_with_flags(["A"]))
    before = s.u32(0x10)
    s.append_flags(["PickedUp_HideOut_Pickup_15", "All_Trophies_Collected"])
    assert s.u32(0x10) - before == 58


def test_append_rejects_duplicates():
    s = SgdFile(make_save_with_flags(["A"]))
    with pytest.raises(SgdError, match="already present"):
        s.append_flags(["A"])


def test_append_refuses_when_padding_insufficient():
    s = SgdFile(make_save_with_flags(["A"]))
    s.set_u32(0x18, STEAM_SIZE - 200)   # consume nearly all the padding
    with pytest.raises(SgdError, match="padding"):
        s.append_flags(["X" * 100])


# --- the caches the game actually reads ------------------------------------


def test_locates_the_world_state_store():
    names = ["PickedUp_CityZ_Pickup_1", "Alpha"]
    s = SgdFile(make_save_with_flags(names))
    stores = s.read_stores()
    assert len(stores) == 1
    assert stores[0].keys == names
    assert stores[0].count == 2


def test_locates_the_challenge_records():
    flags = [f"PickedUp_CityZ_Pickup_{i}" for i in (2, 3, 9, 11)]
    s = SgdFile(make_save_with_flags(flags))
    records = s.read_challenge_records()
    assert len(records) == 18
    assert sum(len(values) for _, _, values in records) == 243
    done = sum(1 for _, _, values in records for v in values if v >= 4)
    assert done == 4                     # four trophies, four challenges


def test_locates_the_display_counters():
    s = SgdFile(make_save_with_flags(["PickedUp_CityZ_Pickup_1"]))
    counters = s.read_counters()
    assert len(counters.values) == 4
    assert counters.values[counters.RIDDLER] == "1/243"


def test_locates_the_progress_cache():
    flags = [f"PickedUp_CityX_Pickup_{i}" for i in range(3)]
    s = SgdFile(make_save_with_flags(flags))
    trophies, total = s.read_trophy_cache()
    assert trophies == [3, 0, 0, 0, 0, 0]      # CACHE_REGIONS starts with CityX
    assert total == 3


def test_locates_the_per_region_records():
    flags = [f"PickedUp_HideOut_Pickup_{i}" for i in range(4)]
    s = SgdFile(make_save_with_flags(flags))
    records = s.read_region_records()
    assert [region for _, region in records] == [1, 2, 3, 4, 5, 6]
    assert s.body[s.region_count_offset(records[5][0])] == 4    # HideOut is 6


def test_validate_writable_refuses_a_save_with_no_region_records():
    s = SgdFile(make_save_with_flags(["PickedUp_CityZ_Pickup_1"], regions=False))
    s.validate()                                    # readable
    with pytest.raises(SgdError, match="per-region"):
        s.validate_writable()                       # but not editable


def test_apply_charges_a_growing_fstring_to_its_own_section():
    """The counter string lives in section 1, not the section the array is in.

    A digit-count change there is a real insertion, so it must be charged to
    u32[0x0C]; charging it to the array's section would corrupt the layout.
    """
    s = SgdFile(make_save_with_flags(["PickedUp_CityZ_Pickup_1"]))
    before = (s.u32(0x0C), s.u32(0x10))
    counters = s.read_counters()
    s.apply([("fstring", counters.offsets[counters.RIDDLER], "100/243")])
    assert s.u32(0x0C) == before[0] + 2             # "1/243" -> "100/243"
    assert s.u32(0x10) == before[1]
    assert s.read_counters().values[1] == "100/243"
    s.validate()


def test_apply_handles_a_shrinking_fstring():
    """Unreachable from collect(), which only ever adds, but apply() owns the
    arithmetic in both directions and a one-sided implementation would hide a
    sign error until something else needed it."""
    s = SgdFile(make_save_with_flags([f"PickedUp_CityZ_Pickup_{i}" for i in range(100)]))
    assert s.read_counters().values[1] == "100/243"
    before = s.u32(0x0C)
    counters = s.read_counters()
    s.apply([("fstring", counters.offsets[counters.RIDDLER], "1/243")])
    assert s.u32(0x0C) == before - 2
    assert s.read_counters().values[1] == "1/243"
    s.validate()
