"""The 315 Riddler collectibles and the 243-challenge arithmetic.

Knows nothing about files. Breakables are the only non-1:1 category: 90
physical objects credit one challenge per 5 destroyed, giving 18 slots.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

BREAKABLE_TYPES = frozenset({"MilitiaShield", "InsectCrate", "JackInTheBox", "MiniDrone"})
BREAKABLES_PER_CHALLENGE = 5
TOTAL_CHALLENGES = 243
TOTAL_OBJECTS = 315

REGION_ORDER = ["CityZ", "CityX", "CityY", "Stagg", "Film", "HideOut"]
TYPE_ORDER = ["Pickup", "Riddler", "Bomb", "MilitiaShield", "InsectCrate",
              "JackInTheBox", "MiniDrone"]


@dataclass(frozen=True)
class Item:
    flag: str
    region: str
    region_name: str
    type: str
    type_name: str
    index: int
    display: str


def challenges_from_flags(flags) -> int:
    """Convert collected objects into the number the game displays.

    Breakables are credited per region, not globally. The two rules agree on
    almost every save, which is how the global one survived: it is off by one
    only when several regions each hold a part-finished group of five. The
    corpus does contain such a save — `Riddler 183/BAK1Save2x2.sgd`, where the
    game's own counter says 166 and the global rule says 167 — so the
    per-region rule is the correct one. It matches all 64 corpus saves.
    """
    collected = {f for f in flags if f.startswith("PickedUp_")}
    breakables: dict[str, int] = {}
    singles = 0
    for flag in collected:
        region, type_ = flag.split("_")[1], flag.split("_")[2]
        if type_ in BREAKABLE_TYPES:
            breakables[region] = breakables.get(region, 0) + 1
        else:
            singles += 1
    return singles + sum(n // BREAKABLES_PER_CHALLENGE for n in breakables.values())


def trophies_by_region(flags) -> dict[str, int]:
    """Riddler trophies held, per region code. Drives the progress cache."""
    out: dict[str, int] = {}
    for flag in {f for f in flags if f.startswith("PickedUp_")}:
        parts = flag.split("_")
        if len(parts) >= 3 and parts[2] == "Pickup":
            out[parts[1]] = out.get(parts[1], 0) + 1
    return out


BREAKABLE_OF = {"CityZ": "MilitiaShield", "CityX": "MilitiaShield",
                "CityY": "MilitiaShield", "Stagg": "InsectCrate",
                "Film": "JackInTheBox", "HideOut": "MiniDrone"}


@dataclass(frozen=True)
class Puzzle:
    """One of the 18 Riddler puzzles, and its pieces in the game's own order.

    A piece is either a collectible flag or `{"breakable": N}`, a cumulative
    threshold over that region's 15 breakables — which is how 90 breakable
    objects become 18 challenges. The save holds one status byte per piece in
    exactly this order, so the order is load-bearing, not cosmetic.
    """
    id: int
    region: str
    pieces: tuple

    def satisfied(self, collected: set[str]) -> list[bool]:
        broken = sum(1 for f in collected
                     if f.startswith(f"PickedUp_{self.region}_{BREAKABLE_OF[self.region]}_"))
        return [broken >= p["breakable"] if isinstance(p, dict) else p in collected
                for p in self.pieces]


class Catalog:
    def __init__(self, items: list[Item], puzzles: list[Puzzle] | None = None):
        self.items = items
        self.puzzles = puzzles or []
        self._by_flag = {i.flag: i for i in items}

    @classmethod
    def load(cls, path: Path | None = None) -> "Catalog":
        path = path or Path(__file__).parent / "data" / "manifest.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls([Item(**{k: v for k, v in d.items() if k != "named"})
                    for d in raw["items"]],
                   [Puzzle(id=p["id"], region=p["region"], pieces=tuple(p["pieces"]))
                    for p in raw.get("puzzles", [])])

    def puzzle(self, puzzle_id: int) -> Puzzle:
        for p in self.puzzles:
            if p.id == puzzle_id:
                return p
        raise KeyError(f"no puzzle {puzzle_id} in the manifest")

    @property
    def regions(self) -> list[str]:
        return REGION_ORDER

    def item(self, flag: str) -> Item:
        return self._by_flag[flag]

    def region_name(self, region: str) -> str:
        for i in self.items:
            if i.region == region:
                return i.region_name
        return region

    def known(self, flag: str) -> bool:
        return flag in self._by_flag

    def grouped(self) -> dict[str, dict[str, list[Item]]]:
        """region -> type -> items, in display order. Drives the GUI tree."""
        out: dict[str, dict[str, list[Item]]] = {}
        for region in REGION_ORDER:
            by_type: dict[str, list[Item]] = {}
            for type_ in TYPE_ORDER:
                found = sorted((i for i in self.items
                                if i.region == region and i.type == type_),
                               key=lambda i: i.index)
                if found:
                    by_type[type_] = found
            out[region] = by_type
        return out
