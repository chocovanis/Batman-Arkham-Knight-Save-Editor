# tests/test_sgd.py
import struct
import pytest
from aksave.sgd import SgdFile, STEAM_SIZE, SgdError


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
