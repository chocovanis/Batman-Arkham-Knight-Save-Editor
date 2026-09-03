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
    """Convert collected objects into the number the game displays."""
    collected = {f for f in flags if f.startswith("PickedUp_")}
    breakables = sum(1 for f in collected if f.split("_")[2] in BREAKABLE_TYPES)
    singles = len(collected) - breakables
    return singles + breakables // BREAKABLES_PER_CHALLENGE


class Catalog:
    def __init__(self, items: list[Item]):
        self.items = items
        self._by_flag = {i.flag: i for i in items}

    @classmethod
    def load(cls, path: Path | None = None) -> "Catalog":
        path = path or Path(__file__).parent / "data" / "manifest.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls([Item(**{k: v for k, v in d.items() if k != "named"})
                    for d in raw["items"]])

    @property
    def regions(self) -> list[str]:
        return REGION_ORDER

    def item(self, flag: str) -> Item:
        return self._by_flag[flag]

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
