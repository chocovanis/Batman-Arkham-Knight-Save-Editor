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


def make_save_with_flags(names):
    """Place a counted flag array at the location the real format uses."""
    sec1_len = 4096
    body = bytearray(STEAM_SIZE)
    struct.pack_into("<I", body, 0x00, 6)
    struct.pack_into("<I", body, 0x0C, sec1_len)
    struct.pack_into("<f", body, 0x69, 3600.0)
    arr = 57 + sec1_len + 11
    body[arr - 11:arr] = ARRAY_PREFIX
    struct.pack_into("<I", body, arr, len(names))
    blob = b"".join(encode_fstring(n) for n in names)
    body[arr + 4:arr + 4 + len(blob)] = blob
    struct.pack_into("<I", body, 0x10, 11 + 4 + len(blob))
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
