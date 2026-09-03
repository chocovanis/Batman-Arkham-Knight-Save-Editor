"""Safe editing operations. The only module the GUI calls to change a save.

Every rail here exists because of a specific documented hazard; see the design
spec section 5. The forbidden set is what keeps the worst hazard structurally
unreachable rather than merely warned about.
"""

from __future__ import annotations

from aksave.catalog import Catalog, challenges_from_flags, TOTAL_OBJECTS
from aksave.sgd import SgdFile

ALL_TROPHIES_FLAG = "All_Trophies_Collected"

# Writing any of these could let a player reach a state the game cannot
# resolve. They are never writable, at any version, at any setting.
FORBIDDEN = frozenset({
    "CatCollarRemoved",
    "RiddlerCaseClosed",
    "Riddler_CaseClosed",
})
FORBIDDEN_SUBSTRINGS = ("_Percentage_Added", "_Trial", "CaseClosed")


class RailError(Exception):
    """A safety rail refused the operation."""


class SaveEditor:
    def __init__(self, raw: bytes, catalog: Catalog | None = None):
        self.catalog = catalog or Catalog.load()
        self.save = SgdFile(raw)
        self.save.validate()
        self._flags = self.save.read_flags()

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

    def _check(self, names: list[str]) -> None:
        for n in names:
            if n in FORBIDDEN or any(s in n for s in FORBIDDEN_SUBSTRINGS):
                raise RailError(f"{n} is never writable by this tool")
            if n != ALL_TROPHIES_FLAG and not self.catalog.known(n):
                raise RailError(f"{n} is not a known collectible")

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

        self.save.append_flags(missing)
        self._flags = self.save.read_flags()
        return missing

    def collect_all(self, leave_one: bool = True) -> list[str]:
        """Collect everything. leave_one keeps achievements poppable in-game."""
        wanted = [i.flag for i in self.catalog.items]
        if leave_one:
            remaining = [f for f in wanted if f not in self.collected]
            if len(remaining) <= 1:
                return []
            wanted = [f for f in wanted if f != remaining[-1]]
        return self.collect(wanted)

    def to_bytes(self) -> bytes:
        self.save.validate()          # never emit a file we would refuse to read
        return self.save.to_bytes()
