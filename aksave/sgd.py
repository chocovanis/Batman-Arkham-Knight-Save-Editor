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

    @property
    def section2_start(self) -> int:
        return 57 + self.u32(0x0C)

    @property
    def array_offset(self) -> int:
        """The global flag array count field: 11 bytes into section 2."""
        return self.section2_start + 11

    def read_flags(self) -> list[str]:
        off = self.array_offset
        count = self.u32(off)
        if count > 100_000:
            raise SgdError(f"implausible flag count {count}")
        pos, out = off + 4, []
        for _ in range(count):
            value, pos = decode_fstring(self.body, pos)
            out.append(value)
        self._array_end = pos
        return out

    @property
    def array_end(self) -> int:
        if not hasattr(self, "_array_end"):
            self.read_flags()
        return self._array_end

    @property
    def payload_end(self) -> int:
        return 57 + sum(self.u32(o) for o in SUM_OFFS)

    def validate(self) -> None:
        """Refuse to work with a file whose structure we cannot confirm.

        Each check corresponds to an assumption the write path relies on.
        A file failing any of them is one we would be guessing about.
        """
        if self.version != 6:
            raise SgdError(f"unsupported save version {self.version}")

        end = self.payload_end
        if not 0 < end <= len(self.body):
            raise SgdError(f"declared payload end {end} outside file")

        # The tail must be zero padding; that is the space appends consume.
        # Ten bytes of slack: one corpus file legitimately ends in zeros.
        if any(self.body[end:]):
            raise SgdError("non-zero data found in tail padding")

        pt = self.playtime_seconds
        if not 0 <= pt < MAX_PLAYTIME:
            raise SgdError(f"implausible playtime {pt}; offsets may be wrong")

        if bytes(self.body[self.array_offset - 11:self.array_offset]) != ARRAY_PREFIX:
            raise SgdError("flag array prefix not found where expected")

        self.read_flags()  # raises if the array does not parse cleanly

    def to_bytes(self) -> bytes:
        return bytes(self.prefix) + bytes(self.body)


def encode_fstring(value: str) -> bytes:
    """int32 length INCLUDING the NUL terminator, then ASCII, then NUL."""
    data = value.encode("ascii")
    return struct.pack("<i", len(data) + 1) + data + b"\x00"


def decode_fstring(buf, off: int) -> tuple[str, int]:
    n = struct.unpack_from("<i", buf, off)[0]
    if n <= 0 or n > 512 or off + 4 + n > len(buf):
        raise SgdError(f"bad FString length {n} at offset {off:#x}")
    raw = bytes(buf[off + 4:off + 4 + n])
    if raw[-1:] != b"\x00":
        raise SgdError(f"unterminated FString at offset {off:#x}")
    return raw[:-1].decode("ascii", "replace"), off + 4 + n
