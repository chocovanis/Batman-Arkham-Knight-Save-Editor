"""Binary layer for Batman: Arkham Knight .sgd save files.

Knows nothing about the Riddler. Everything here was verified against a
27-save corpus spanning both Steam and GOG/Epic builds; see the design spec.
"""

from __future__ import annotations

import struct

STEAM_SIZE = 2428928
SUM_OFFS = (0x0C, 0x10, 0x18, 0x20, 0x24, 0x28, 0x2C, 0x30, 0x34, 0x38)
SECTION2_LEN_OFF = 0x10
PLAYTIME_OFF = 0x69
ARRAY_PREFIX = bytes.fromhex("000000" + "1c" + "00000000000000")
MAX_PLAYTIME = 1000 * 3600  # a sanity bound, not a game limit


class SgdError(Exception):
    """The file is not a save we understand well enough to touch."""


class SgdFile:
    def __init__(self, raw: bytes):
        prefix = len(raw) - STEAM_SIZE
        if prefix not in (0, 4):
            raise SgdError(
                f"unexpected size {len(raw)}; expected {STEAM_SIZE} (Steam) "
                f"or {STEAM_SIZE + 4} (GOG/Epic)"
            )
        self.prefix_len = prefix
        self.prefix = raw[:prefix]
        self.body = bytearray(raw[prefix:])

    @property
    def platform(self) -> str:
        return "Steam" if self.prefix_len == 0 else "GOG/Epic"

    def u32(self, off: int) -> int:
        return struct.unpack_from("<I", self.body, off)[0]

    def set_u32(self, off: int, val: int) -> None:
        struct.pack_into("<I", self.body, off, val)

    @property
    def version(self) -> int:
        return self.u32(0x00)

    @property
    def playtime_seconds(self) -> float:
        return struct.unpack_from("<f", self.body, PLAYTIME_OFF)[0]

    def to_bytes(self) -> bytes:
        return bytes(self.prefix) + bytes(self.body)
