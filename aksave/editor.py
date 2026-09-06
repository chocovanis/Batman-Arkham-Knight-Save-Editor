"""Safe editing operations. The only module the GUI calls to change a save.

Every rail here exists because of a specific documented hazard. The forbidden
set is what keeps the worst hazard structurally
unreachable rather than merely warned about.
"""

from __future__ import annotations

import struct

from aksave.catalog import (Catalog, challenges_from_flags, trophies_by_region,
                            TOTAL_CHALLENGES, TOTAL_OBJECTS)
from aksave.sgd import (CACHE_REGIONS, CHALLENGE_DONE, CHALLENGE_SOLVED_MIN,
                        RIDDLE_SOLVED, TROPHY_ARRAY_OFF, TROPHY_TOTAL_OFF,
                        SgdFile, encode_fstring)

ALL_TROPHIES_FLAG = "All_Trophies_Collected"

# Writing any of these could let a player reach a state the game cannot
# resolve. They are never writable, at any version, at any setting.
FORBIDDEN = frozenset({
    "CatCollarRemoved",
    "RiddlerCaseClosed",
    "Riddler_CaseClosed",
})
FORBIDDEN_SUBSTRINGS = ("_Percentage_Added", "_Trial", "CaseClosed")

# Which region to leave the last collectible in, most reachable first. Bleake
# Island is where the game starts and the only region every save can get to.
# This is now only the fallback; LEAVE_ONE_FLAG below is tried first.
LEAVE_ONE_REGIONS = ("CityZ", "CityX", "CityY", "Stagg", "Film", "HideOut")

# The one collectible `leave_one` holds back, chosen rather than ranked.
#
# This project verified exactly one location-to-flag mapping, and it verified it
# the only way that works: the player picked the trophy up and we read the flag
# the game wrote (captures/004). Everything else is a guess, and the whole point
# of leaving a collectible behind is that the user can go and find it — so the
# one we can describe is the one we leave.
LEAVE_ONE_FLAG = "PickedUp_CityZ_Pickup_13"

# BEWARE THE NUMBERING. Three schemes name this single object: the save flag
# says Pickup_13, this tool's own display name says "Riddler Trophy 13", and
# IGN's guide calls it Bleake Island trophy 6. Telling a user "trophy 13" and
# then pointing them at IGN sends them to the wrong building — the exact
# confound that cost three in-game attempts in session 6. So the description
# leads with the place and never prints the index.
#
# Kept to plain ASCII on purpose. The CLI prints it, and a Windows console runs
# in the active code page rather than UTF-8, where print() raises
# UnicodeEncodeError on anything the page has no room for. An em-dash here came
# back as a replacement character the first time this was run for real.
LEAVE_ONE_LOCATION = (
    "a Riddler Trophy on Bleake Island, in the warehouse across the bridge "
    "from Ace Chemicals. Hit the ? switch with the up arrow to raise the "
    "containers, then grab the trophy. Armed Riddler drones spawn; a Remote "
    "Batarang through the ? with the down arrow crushes them. "
    "IGN's Bleake Island guide numbers this one trophy 6.")


def skipped_note(editor: "SaveEditor") -> str | None:
    """What to say about areas this save has no Riddler records for yet.

    Shared by the CLI and the GUI on purpose. This is the one refusal an
    ordinary player is actually likely to meet — a save that has not reached
    Arkham Knight HQ finishes at 216/243 and needs to be told why — so both
    surfaces have to say the same thing, in words that name the fix.

    Returns None when there is nothing to report. Plain ASCII: the CLI prints
    it, and a Windows console runs in the active code page, not UTF-8.
    """
    if not editor.untracked_regions:
        return None
    names = ", ".join(sorted(editor.catalog.region_name(r)
                             for r in editor.untracked_regions))
    return (f"SKIPPED {names}: this save has no Riddler records for that area "
            f"yet, so its challenges cannot be set and the total stops short. "
            f"Visit it once in game, save, and run this again to finish the "
            f"set.")


def where_to_find(flag: str, catalog: Catalog) -> str:
    """Tell the user where the collectible we left behind actually is.

    Only LEAVE_ONE_FLAG has a location we can stand behind. For anything else
    — which only happens when the user already has that trophy — the honest
    answer is its name plus the escape hatch, because the game does not
    necessarily mark an uncollected collectible on the map.
    """
    if flag == LEAVE_ONE_FLAG:
        return LEAVE_ONE_LOCATION
    name = catalog.item(flag).display if catalog.known(flag) else flag
    return (f"{name}. The game will not necessarily mark it on your map, so if "
            f"you cannot find it, turn \"leave one\" off and run again.")


# Plain ASCII, like everything else a surface may print. See skipped_note.
NOTHING_COLLECTED = (
    "This save has no Riddler collectibles in it yet, so there is nothing here "
    "for the editor to work with. The game does not start keeping Riddler "
    "records until you have picked one up. Collect a single Riddler Trophy "
    "anywhere in the city, save the game, and open that save instead.")


class RailError(Exception):
    """A safety rail refused the operation."""


class SaveEditor:
    def __init__(self, raw: bytes, catalog: Catalog | None = None):
        self.catalog = catalog or Catalog.load()
        self.save = SgdFile(raw)
        self.save.validate()
        self._flags = self.save.read_flags()

        # Checked here, ahead of validate_writable(), purely so the player gets
        # a sentence about their game instead of one about our parser.
        #
        # The tool finds the world-state store by looking for a PickedUp_ key
        # inside it, so a save holding none is unidentifiable and
        # `read_stores()` refuses it with "no world-state store holding
        # collectibles was found" — which, in a dialog titled "Cannot read
        # save", tells a player nothing true: the save read perfectly.
        #
        # Six corpus saves are in this state, and they are not all brand-new
        # games. One is an hour in with 143 flags and not a single PickedUp_,
        # so the condition is "nothing collected", not "nothing played".
        if not any(f.startswith("PickedUp_") for f in self._flags):
            raise RailError(NOTHING_COLLECTED)

        # Not plain validate(): a save whose caches we cannot locate is one we
        # would silently half-edit, which is precisely the failure that made
        # the first in-game test load fine and show the old progress.
        self.save.validate_writable()
        # Set by collect_all(leave_one=True): the collectible the user has to
        # pick up themselves. The callers have to be able to name it.
        self.left_behind: str | None = None

    @property
    def flags(self) -> list[str]:
        return list(self._flags)

    @property
    def platform(self) -> str:
        return self.save.platform

    @property
    def playtime_seconds(self) -> float:
        return self.save.playtime_seconds

    @property
    def collected(self) -> set[str]:
        return {f for f in self._flags if f.startswith("PickedUp_")}

    @property
    def collected_count(self) -> int:
        return len(self.collected)

    @property
    def challenge_count(self) -> int:
        return challenges_from_flags(self._flags)

    @property
    def tracked_regions(self) -> set[str]:
        """Regions this save keeps per-challenge records for.

        The game creates a region's three challenge records the first time the
        player goes there, and a save that has never been to Arkham Knight HQ
        simply has no slots for its 27 challenges. We could not set them
        without inventing records — and the record that would have to be
        invented alongside them, in the per-region block, has a variable length
        we have not decoded. So those regions are out of scope rather than
        guessed at, and the tool says which and why.

        This lines up with the safety model rather than fighting it: you can
        only be given collectibles somewhere the game has already let you go.
        """
        by_puzzle = {p.id: p.region for p in self.catalog.puzzles}
        return {by_puzzle[pid] for _, pid, _ in self.save.read_challenge_records()
                if pid in by_puzzle}

    @property
    def untracked_regions(self) -> set[str]:
        return {p.region for p in self.catalog.puzzles} - self.tracked_regions

    def _check(self, names: list[str]) -> None:
        tracked = self.tracked_regions
        for n in names:
            if n in FORBIDDEN or any(s in n for s in FORBIDDEN_SUBSTRINGS):
                raise RailError(f"{n} is never writable by this tool")
            if n == ALL_TROPHIES_FLAG:
                continue
            if not self.catalog.known(n):
                raise RailError(f"{n} is not a known collectible")
            region = self.catalog.item(n).region
            if region not in tracked:
                raise RailError(
                    f"{n} is in {self.catalog.item(n).region_name}, which this "
                    f"save has no Riddler records for. Visit that area once in "
                    f"game, save, and try again — otherwise the counter and the "
                    f"collectibles menu would disagree.")

    def collect(self, names: list[str]) -> list[str]:
        """Mark the given collectibles collected. Returns what was added."""
        self._check(names)

        # Deduplicate within the batch as well as against the save. append_flags
        # only knows what the save already holds, so a name repeated in `names`
        # would be written as two identical FStrings — a disturbance we have no
        # evidence the game tolerates, in a format where we treat occurrence
        # count as potentially meaningful.
        present = set(self._flags)
        missing: list[str] = []
        for n in names:
            if n not in present:
                missing.append(n)
                present.add(n)

        # The game sets this alongside the final collectible; match that.
        # It is a completion marker, not a collectible, so it must not be
        # counted toward TOTAL_OBJECTS — otherwise passing it explicitly would
        # trip the test one object early and write the flag twice. Computed
        # before the empty-batch exit so a save that already holds all 315
        # objects without the marker can still be finished.
        objects = self.collected | {n for n in missing if n != ALL_TROPHIES_FLAG}
        if len(objects) == TOTAL_OBJECTS and ALL_TROPHIES_FLAG not in present:
            missing.append(ALL_TROPHIES_FLAG)

        if not missing:
            return []

        self._write(missing)
        self._flags = self.save.read_flags()
        return missing

    def _write(self, missing: list[str]) -> dict[int, int]:
        """Write the new flags everywhere the game itself writes them.

        The game keeps several separate records of collectible state and reads
        the caches, not the primary array. Editing the array alone yields a save
        that loads cleanly and displays the old totals — that is exactly what
        happened on the first in-game test. Every location below was confirmed
        by diffing two real rotations one pickup apart and then checking the
        rule against all 60 corpus saves.

        Offsets are all read before anything moves; `SgdFile.apply` applies the
        batch from the highest offset down so they stay valid.
        """
        save = self.save
        flags_after = self._flags + missing
        collected_after = {f for f in flags_after if f.startswith("PickedUp_")}

        stores = save.read_stores()
        counters = save.read_counters()
        anchor = save.progress_anchor()
        records = save.read_region_records()
        challenges = save.read_challenge_records()
        riddle_start, riddle_values = save.read_riddle_array()

        blob = b"".join(encode_fstring(n) for n in missing)
        by_region = trophies_by_region(flags_after)
        trophies = [by_region.get(r, 0) for r in CACHE_REGIONS]

        edits: list[tuple] = [
            # 1. the primary flag array, in section 2
            ("insert", save.array_end, blob),
            ("u32", save.array_offset, len(self._flags) + len(missing)),

            # 2. the per-region progress cache, and its total
            ("u32", anchor + TROPHY_TOTAL_OFF, sum(trophies)),

            # 3. the cached counter string the HUD shows verbatim
            ("fstring", counters.offsets[counters.RIDDLER],
             f"{challenges_from_flags(flags_after)}/{TOTAL_CHALLENGES}"),
        ]
        for i, value in enumerate(trophies):
            edits.append(("u32", anchor + TROPHY_ARRAY_OFF + 4 * i, value))

        # 4. the second per-region copy that sits just before the cache
        for offset, region_id in records:
            edits.append(("u8", save.region_count_offset(offset),
                          trophies[region_id - 1]))

        # 5. every world-state store, appended so no existing index into one
        #    moves. There is more than one: the user's own saves carry a second
        #    complete copy in section 0x20, and leaving it stale would be the
        #    same bug as leaving the primary array alone. Every value is 1; the
        #    corpus holds no PickedUp_ key with any other value.
        for store in stores:
            edits.append(("insert", store.vals_end, struct.pack("<i", 1) * len(missing)))
            edits.append(("u32", store.vcount_off, store.count + len(missing)))
            edits.append(("insert", store.keys_end, blob))
            edits.append(("u32", store.count_off, store.count + len(missing)))

        # 6. the flat riddle-solved array, indexed by the riddle's global 1..40
        #    number rather than by region
        for item in (self.catalog.item(n) for n in missing
                     if n != ALL_TROPHIES_FLAG):
            if item.type == "Riddler" and not riddle_values[item.index]:
                edits.append(("u32", riddle_start + 4 * item.index, RIDDLE_SOLVED))

        # 7. the per-challenge status bytes the collectibles menu reads. Only
        #    slots that are unsolved and should now be solved are touched, so
        #    the write is idempotent, leaves the game's own "just collected"
        #    4s alone, and repairs a save left half-edited by an older build.
        for first, puzzle_id, values in challenges:
            puzzle = self.catalog.puzzle(puzzle_id)
            if len(puzzle.pieces) != len(values):
                raise RailError(
                    f"puzzle {puzzle_id} has {len(puzzle.pieces)} pieces in the "
                    f"manifest but {len(values)} status bytes in this save")
            for i, done in enumerate(puzzle.satisfied(collected_after)):
                if done and values[i] < CHALLENGE_SOLVED_MIN:
                    edits.append(("u8", first + i, CHALLENGE_DONE))

        return save.apply(edits)

    def collect_all(self, leave_one: bool = True) -> list[str]:
        """Collect everything reachable. leave_one keeps achievements poppable.

        Regions the save keeps no records for are skipped rather than refused,
        so a mid-game save still gets everything it can hold; `untracked_regions`
        says what was left out.
        """
        tracked = self.tracked_regions
        wanted = [i.flag for i in self.catalog.items if i.region in tracked]
        self.left_behind = None
        if leave_one:
            remaining = [f for f in wanted if f not in self.collected]
            if len(remaining) <= 1:
                # Already where leave_one wants to be. Still report what is
                # outstanding: a re-run that says nothing reads as the tool
                # having forgotten the collectible it asked the user to find.
                self.left_behind = remaining[0] if remaining else None
                return []
            self.left_behind = self.leave_out(remaining)
            wanted = [f for f in wanted if f != self.left_behind]
        return self.collect(wanted)

    @staticmethod
    def leave_out(remaining: list[str]) -> str:
        """Choose the one collectible the player will pick up themselves.

        This is the single thing the user has to do in game for the achievement
        to fire, so it has to be findable. LEAVE_ONE_FLAG is the only
        collectible whose physical location this project actually verified, so
        it wins outright whenever the save has not already got it.

        The ranking below is the fallback for when it has. It must return
        something: if `leave_out` ever came back empty-handed,
        `collect_all(leave_one=True)` would quietly become a full collect and
        the achievement it exists to protect would never fire. Taking the last
        entry in manifest order chose "Riddle 2 — Stagg Airships": a riddle
        needs you to know where to stand and what to scan, and Stagg is not
        somewhere you can walk to early. Prefer a plain trophy, and prefer
        Bleake Island, which is the first island and the one every save reaches.
        """
        if LEAVE_ONE_FLAG in remaining:
            return LEAVE_ONE_FLAG

        def rank(flag: str) -> tuple:
            _, region, type_ = flag.split("_")[:3]
            region_rank = (LEAVE_ONE_REGIONS.index(region)
                           if region in LEAVE_ONE_REGIONS else len(LEAVE_ONE_REGIONS))
            return (0 if type_ == "Pickup" else 1, region_rank, flag)

        return min(remaining, key=rank)

    def to_bytes(self) -> bytes:
        # Not just validate(): re-locating every structure we wrote is the
        # cheapest way to catch a write that left one of them unparseable.
        self.save.validate_writable()
        return self.save.to_bytes()
