"""Regression tests against the real save corpus.

Set AK_CORPUS to the folder holding the save collections. Skipped otherwise,
because the corpus is copyrighted game data and is never committed.
"""
import os
import re
from pathlib import Path

import pytest

from aksave.catalog import challenges_from_flags
from aksave.sgd import SgdFile

CORPUS = os.environ.get("AK_CORPUS")
pytestmark = pytest.mark.skipif(not CORPUS, reason="AK_CORPUS not set")

# (relative path, expected challenge count) — verified by hand against the
# game's own cached counter string in every case.
CASES = [
    ("MySaves/BAK1Save1x1.sgd", 0),
    ("Save files 1/Riddler Save Game/Riddler 123 from 243 main story 59 procent/BAK1Save2x0.sgd", 123),
    ("Save files 1/Riddler Save Game/Riddler 143 of 243/BAK1Save2x0.sgd", 143),
    ("Save files 1/Riddler Save Game/Riddler 183 from 243/BAK1Save2x0.sgd", 183),
    ("Save files 1/Riddler Save Game/Riddler 223 from 243/BAK1Save2x0.sgd", 223),
    ("Save files 5/BAK1Save3x0.sgd", 0),
    ("Save files 6/BAK1Save0x0.sgd", 242),
    ("Save files 6/BAK1Save0x1.sgd", 243),
    ("Save files 3/BAK1Save0x0.sgd", 243),          # GOG/Epic variant
    ("MySaves/BAK1Save0x0.sgd", 243),
]


def load(rel):
    return SgdFile((Path(CORPUS) / rel).read_bytes())


@pytest.mark.parametrize("rel,expected", CASES)
def test_challenge_count_matches_games_own_counter(rel, expected):
    save = load(rel)
    save.validate()
    assert challenges_from_flags(save.read_flags()) == expected

    # The game caches its own counter string; it must agree with our maths.
    counters = re.findall(rb"\d{1,3}/243", bytes(save.body[:0x8000]))
    if counters:
        assert counters[0].decode() == f"{expected}/243" or \
               f"{expected}/243".encode() in counters


def test_gog_variant_detected():
    assert load("Save files 3/BAK1Save0x0.sgd").platform == "GOG/Epic"
    assert load("MySaves/BAK1Save0x0.sgd").platform == "Steam"


def test_appending_reproduces_a_real_save_transition():
    """SF6 0x0 -> 0x1 differ by one collectible. Our append must match."""
    before, after = load("Save files 6/BAK1Save0x0.sgd"), load("Save files 6/BAK1Save0x1.sgd")
    added = [f for f in after.read_flags() if f not in set(before.read_flags())]
    assert added == ["PickedUp_HideOut_Pickup_15", "All_Trophies_Collected"]

    grew = before.append_flags(added)
    assert grew == 58
    assert challenges_from_flags(before.read_flags()) == 243
    before.validate()
