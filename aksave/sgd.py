"""Binary layer for Batman: Arkham Knight .sgd save files.

Knows nothing about the Riddler. Everything here was verified against a
60-save corpus spanning both Steam and GOG/Epic builds.

Collectible state is not held in one place. The game keeps a primary flag
array, a global key/value store, a per-region progress cache and a cached
display string, and it updates all of them together. This module can locate
and edit each of them; deciding *what* to write is `aksave.editor`'s job.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

STEAM_SIZE = 2428928
# Section lengths. 0x1C is zero in 58 of 60 corpus saves, which is exactly why
# it was missed when the identity was first derived from a 7-file sample. Two
# GOG saves carry 0x1C = 9247, and omitting it puts payload_end 9247 bytes early
# — mid-FString. Including it, every corpus file validates.
SUM_OFFS = (0x0C, 0x10, 0x18, 0x1C, 0x20, 0x24, 0x28, 0x2C, 0x30, 0x34, 0x38)
SECTION1_LEN_OFF = 0x0C
SECTION2_LEN_OFF = 0x10
SECTION3_LEN_OFF = 0x18
PLAYTIME_OFF = 0x69
ARRAY_PREFIX = bytes.fromhex("000000" + "1c" + "00000000000000")
MAX_PLAYTIME = 1000 * 3600  # a sanity bound, not a game limit

# The progress cache is a run of four counted uint32 arrays whose element
# counts are 9, 9, 9, 10. That signature is unique inside section 2 in all 60
# corpus saves, including brand-new games where every element is zero — which
# is why it is used as the anchor instead of matching on values.
CACHE_SIGNATURE = (9, 9, 9, 10)
CACHE_STRIDE = 40                      # 4-byte count + 9 uint32 elements
TROPHY_ARRAY_OFF = 4                   # anchor -> first element of array 1
TROPHY_TOTAL_OFF = 376                 # anchor -> total trophies collected

# Region slot order inside the progress cache. Established by correlating each
# slot against the per-region PickedUp_*_Pickup_* counts over the whole corpus;
# saves where Film and Stagg differ pin the two that would otherwise be
# ambiguous. This is NOT the order the catalog displays regions in.
CACHE_REGIONS = ("CityX", "CityY", "CityZ", "Film", "Stagg", "HideOut")

# Per-challenge status bytes. 0-3 mean unsolved; 4 and 5 both mean solved and
# the game counts every byte >= 4. A freshly collected piece is written as 4 and
# settles to 5 (10,098 of the 10,442 solved bytes in the corpus are 5), so 5 is
# the resting value and the one we write.
CHALLENGE_DONE = 5
CHALLENGE_SOLVED_MIN = 4

# The riddle-solved array. A fresh solve writes 1 and it later settles to 2;
# both count. We write 2 for the same reason we write 5 above: a real save that
# is entirely 2s exists, and none is entirely 1s.
RIDDLE_SLOTS = 63
RIDDLE_SOLVED = 2


class SgdError(Exception):
    """The file is not a save we understand well enough to touch."""


@dataclass
class Store:
    """A world-state key/value store: what the game has done in that world.

    Two parallel arrays — `count` FStrings followed by `count` int32 values.
    Riddler pickups appear here as `PickedUp_… -> 1`, alongside map objects,
    chapter markers and level-object state. In all 60 corpus saves the set of
    PickedUp_ keys here is exactly equal to the set in the primary flag array;
    the editor's earlier failure in game was writing one and not the other.
    """
    len_off: int
    count_off: int
    keys_start: int
    keys_end: int
    vcount_off: int
    vals_start: int
    vals_end: int
    keys: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.keys)


@dataclass
class Counters:
    """The four `N/M` strings the game displays without recomputing them.

    A counted array of exactly four FStrings in section 1. Index 1 is the
    Riddler counter; the others are unrelated progress trackers we never touch.
    """
    array_off: int
    offsets: list[int]
    values: list[str]

    RIDDLER = 1


def encode_fstring(value: str) -> bytes:
    """int32 length INCLUDING the NUL terminator, then ASCII, then NUL."""
    data = value.encode("ascii")
    return struct.pack("<i", len(data) + 1) + data + b"\x00"


def decode_fstring(buf, off: int) -> tuple[str, int]:
    n = struct.unpack_from("<i", buf, off)[0]
    # UE3 writes an empty FString as a bare length of zero with no payload.
    # Missing this stalls any walk of the section-3 store, which contains them.
    if n == 0:
        return "", off + 4
    if n < 0 or n > 512 or off + 4 + n > len(buf):
        raise SgdError(f"bad FString length {n} at offset {off:#x}")
    raw = bytes(buf[off + 4:off + 4 + n])
    if raw[-1:] != b"\x00":
        raise SgdError(f"unterminated FString at offset {off:#x}")
    return raw[:-1].decode("ascii", "replace"), off + 4 + n


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

    # -- section geometry -------------------------------------------------

    def section_bounds(self, len_off: int) -> tuple[int, int]:
        pos = 57
        for off in SUM_OFFS:
            n = self.u32(off)
            if off == len_off:
                return pos, pos + n
            pos += n
        raise SgdError(f"{len_off:#x} is not a section length offset")

    def section_of(self, offset: int) -> int:
        """Which section length an edit at `offset` must be charged to."""
        pos = 57
        for off in SUM_OFFS:
            n = self.u32(off)
            if pos <= offset <= pos + n:
                return off
            pos += n
        raise SgdError(f"offset {offset:#x} falls outside every section")

    @property
    def section2_start(self) -> int:
        return 57 + self.u32(SECTION1_LEN_OFF)

    @property
    def array_offset(self) -> int:
        """The primary flag array count field: 11 bytes into section 2."""
        return self.section2_start + 11

    @property
    def payload_end(self) -> int:
        return 57 + sum(self.u32(o) for o in SUM_OFFS)

    # -- structure readers ------------------------------------------------

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
        self.read_flags()
        return self._array_end

    def _store_in(self, len_off: int) -> Store | None:
        """Locate a world-state key/value store by parsing, not by an offset.

        A store does not start at a constant distance from its section
        boundary (110, 131 and 136 bytes in three corpus saves), because the
        player-position and streamed-level block before it varies in length.
        So probe forward for a count whose FStrings parse cleanly AND which is
        followed by a second array declaring the identical count. Two
        independent agreements make a false positive essentially impossible.
        """
        start, end = self.section_bounds(len_off)
        for probe in range(start, min(start + 8192, end - 8)):
            count = self.u32(probe)
            if not 1 <= count <= 200_000:
                continue
            try:
                pos, keys = probe + 4, []
                for _ in range(count):
                    value, pos = decode_fstring(self.body, pos)
                    keys.append(value)
            except SgdError:
                continue
            if pos + 4 > end or self.u32(pos) != count:
                continue
            return Store(len_off=len_off, count_off=probe, keys_start=probe + 4,
                         keys_end=pos, vcount_off=pos, vals_start=pos + 4,
                         vals_end=pos + 4 + 4 * count, keys=keys)
        return None

    def read_stores(self) -> list[Store]:
        """Every world-state store that holds collectible keys.

        There is more than one. Section 3 always has one; 12 corpus saves —
        including every one of the user's own — carry a SECOND complete copy in
        section u32[0x20], and the two always agree. Writing only the section-3
        copy would leave the other stale, which is the same class of bug as
        writing only the primary array. The remaining sections hold DLC and
        side-story worlds and never contain a collectible key.
        """
        out = []
        for len_off in SUM_OFFS[2:]:
            store = self._store_in(len_off)
            if store and any(k.startswith("PickedUp_") for k in store.keys):
                out.append(store)
        if not out:
            raise SgdError("no world-state store holding collectibles was found")
        return out

    def read_challenge_records(self) -> list[tuple[int, int, list[int]]]:
        """The per-challenge status bytes: (offset of the first byte, puzzle
        id, current values).

        18 records, one per Riddler puzzle, holding 18 status bytes for each of
        the three city regions and 9 for each of the others — 243 in total,
        exactly the number the game displays. A byte >= 4 means that challenge
        is done: counting them reproduces the game's own counter on all 60
        corpus saves, and matching each byte against the puzzle's piece list
        from the manifest is correct on all 12,960 observed bytes.

        Records for a region the player has never entered are simply absent,
        so a short list is a real answer.
        """
        lo, hi = self.array_end, self.progress_anchor()
        b, out = self.body, []
        for q in range(lo, hi - 8):
            if not (b[q] == 0 and b[q + 2] == 0 and 1 <= b[q + 3] <= 6):
                continue
            count = self.u32(q + 4)
            if count in (9, 18) and all(x <= CHALLENGE_DONE for x in b[q + 8:q + 8 + count]):
                out.append((q + 8, b[q + 1], list(b[q + 8:q + 8 + count])))
        ids = [i for _, i, _ in out]
        if len(ids) != len(set(ids)):
            raise SgdError("ambiguous per-challenge records")
        return out

    def read_counters(self) -> Counters:
        """The counted array of four `N/M` display strings, in section 1."""
        start, end = self.section_bounds(SECTION1_LEN_OFF)
        for probe in range(start, end - 32):
            if self.u32(probe) != 4:
                continue
            try:
                pos, offs, vals = probe + 4, [], []
                for _ in range(4):
                    offs.append(pos)
                    value, pos = decode_fstring(self.body, pos)
                    vals.append(value)
            except SgdError:
                continue
            if all(v.count("/") == 1 and v.replace("/", "").isdigit() for v in vals):
                return Counters(array_off=probe, offsets=offs, values=vals)
        raise SgdError("display counter array not found in section 1")

    def progress_anchor(self) -> int:
        """Start of the 9/9/9/10 uint32-array run that caches Riddler progress."""
        after_array = self.array_end
        _, end = self.section_bounds(SECTION2_LEN_OFF)
        for probe in range(after_array, end - CACHE_STRIDE * 4):
            if all(self.u32(probe + CACHE_STRIDE * i) == n
                   for i, n in enumerate(CACHE_SIGNATURE)):
                return probe
        raise SgdError("Riddler progress cache not found in section 2")

    def read_trophy_cache(self) -> tuple[list[int], int]:
        """Per-region trophy counts (in CACHE_REGIONS order) and their total."""
        anchor = self.progress_anchor()
        counts = list(struct.unpack_from("<6I", self.body,
                                         anchor + TROPHY_ARRAY_OFF))
        return counts, self.u32(anchor + TROPHY_TOTAL_OFF)

    def read_riddle_array(self) -> tuple[int, list[int]]:
        """The 63-slot riddle-solved array: (offset of slot 0, values).

        Riddle indices are a single 1..40 space shared across all six regions,
        not per-region, so one flat array covers them; slot 0 and slots 41..62
        are always zero. A solved riddle holds 1 or 2, and the set of non-zero
        slots equals the held `PickedUp_*_Riddler_*` set in all 60 corpus saves.

        Located structurally — a count of 63 followed by 63 values of at most 2
        — which finds exactly one candidate in every corpus save.
        """
        lo, hi = self.array_end, self.progress_anchor()
        found = []
        for probe in range(lo, hi - 4 * (RIDDLE_SLOTS + 1)):
            if self.u32(probe) != RIDDLE_SLOTS:
                continue
            values = [self.u32(probe + 4 + 4 * i) for i in range(RIDDLE_SLOTS)]
            if all(v <= RIDDLE_SOLVED for v in values):
                found.append((probe + 4, values))
        if len(found) != 1:
            raise SgdError(f"expected one riddle array, found {len(found)}")
        return found[0]

    def read_region_records(self) -> list[tuple[int, int]]:
        """A second per-region copy of the trophy counts, before the cache.

        Each record begins `<uint16 region 1..6><uint32 8|9><00><uint8 count><00>`
        and then runs on for a variable number of bytes we have not decoded, so
        records are found by that header signature rather than by walking a
        grammar we would be guessing at. Returns (offset of the region id,
        region id); the count byte is 7 bytes further on.

        The block is absent entirely in the earliest saves — it appears once a
        region has been scored — so an empty list is a real answer, not a
        failure. `region_count_offset` is where the writer reads and writes.
        """
        lo, hi = self.array_end, self.progress_anchor()
        b, out = self.body, []
        for q in range(lo, hi - 9):
            if (1 <= b[q] <= 6 and b[q + 1] == 0 and b[q + 2] in (8, 9)
                    and b[q + 3] == b[q + 4] == b[q + 5] == b[q + 6] == 0
                    and b[q + 8] == 0):
                out.append((q, b[q]))
        ids = [i for _, i in out]
        if len(ids) != len(set(ids)):
            raise SgdError("ambiguous per-region records")
        if out and self.u32(out[0][0] - 5) != len(out):
            raise SgdError("per-region record count disagrees with the header")
        return out

    @staticmethod
    def region_count_offset(record_offset: int) -> int:
        return record_offset + 7

    # -- validation -------------------------------------------------------

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
        # Non-zero data here means payload_end is wrong for this file, so the
        # append arithmetic would be wrong too — refuse rather than guess.
        if any(self.body[end:]):
            raise SgdError("non-zero data found in tail padding")

        pt = self.playtime_seconds
        if not 0 <= pt < MAX_PLAYTIME:
            raise SgdError(f"implausible playtime {pt}; offsets may be wrong")

        if bytes(self.body[self.array_offset - 11:self.array_offset]) != ARRAY_PREFIX:
            raise SgdError("flag array prefix not found where expected")

        self.read_flags()  # raises if the array does not parse cleanly

    def validate_writable(self) -> None:
        """Everything validate() checks, plus every structure a write touches.

        Writing the primary array alone produces a save the game loads and then
        ignores, so a save we cannot fully locate is one we must not edit.
        """
        self.validate()
        self.read_stores()
        self.read_counters()
        self.progress_anchor()
        self.read_riddle_array()
        if not self.read_region_records() or not self.read_challenge_records():
            raise SgdError(
                "per-region progress records are missing; this save is from "
                "before the game started tracking regions and cannot be edited"
            )

    # -- primitive edits --------------------------------------------------

    def _insert(self, at: int, blob: bytes) -> None:
        """Insert bytes, absorbing the shift into the zero tail padding."""
        grow = len(blob)
        if not grow:
            return
        if self.payload_end + grow > len(self.body):
            raise SgdError("not enough tail padding to insert")
        tail = self.body[at:len(self.body) - grow]
        self.body[at:at + grow] = blob
        self.body[at + grow:] = tail

    def _delete(self, at: int, count: int) -> None:
        """Remove bytes, restoring the same number of zeros to the tail."""
        if not count:
            return
        del self.body[at:at + count]
        self.body.extend(b"\x00" * count)

    def apply(self, edits: list[tuple]) -> dict[int, int]:
        """Apply a batch of edits and fix up the affected section lengths.

        Edits are ('u32', offset, value), ('u8', offset, value),
        ('insert', offset, blob) or ('fstring', offset, text).

        Every offset is taken from the file as it is *now*, so the batch is
        applied from the highest offset downwards: an edit only ever shifts
        bytes above itself, which leaves every lower offset — and every section
        boundary below it — still valid. Section lengths are therefore also
        resolved up front and written once at the end.
        """
        deltas: dict[int, int] = {}
        for kind, at, *rest in edits:
            if kind in ("insert", "fstring"):
                deltas.setdefault(self.section_of(at), 0)

        for edit in sorted(edits, key=lambda e: -e[1]):
            kind, at = edit[0], edit[1]
            if kind == "u32":
                self.set_u32(at, edit[2])
            elif kind == "u8":
                self.body[at] = edit[2]
            elif kind == "insert":
                section = self.section_of(at)
                self._insert(at, edit[2])
                deltas[section] += len(edit[2])
            elif kind == "fstring":
                section = self.section_of(at)
                old, _ = decode_fstring(self.body, at)
                new = encode_fstring(edit[2])
                delta = len(new) - (4 + len(old) + 1)
                if delta > 0:
                    self._insert(at, b"\x00" * delta)
                elif delta < 0:
                    self._delete(at, -delta)
                self.body[at:at + len(new)] = new
                deltas[section] += delta
            else:
                raise SgdError(f"unknown edit {kind}")

        for len_off, delta in deltas.items():
            if delta:
                self.set_u32(len_off, self.u32(len_off) + delta)
        return {k: v for k, v in deltas.items() if v}

    def append_flags(self, names: list[str]) -> int:
        """Append flag names to the primary array only. Returns bytes inserted.

        Kept for tests and for callers that genuinely want the primary array on
        its own. It is NOT enough to make the game show the change — use
        `aksave.editor.SaveEditor.collect`, which writes every location the
        game writes.
        """
        existing = self.read_flags()
        dupes = [n for n in names if n in existing]
        if dupes:
            raise SgdError(f"already present: {dupes[:3]}")

        blob = b"".join(encode_fstring(n) for n in names)
        self.apply([
            ("insert", self.array_end, blob),
            ("u32", self.array_offset, len(existing) + len(names)),
        ])
        return len(blob)

    def to_bytes(self) -> bytes:
        return bytes(self.prefix) + bytes(self.body)
