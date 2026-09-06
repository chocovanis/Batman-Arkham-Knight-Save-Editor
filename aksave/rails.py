"""Rails that guard the act of writing."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

SLOT_RE = re.compile(r"^BAK1Save(\d+)x(\d+)\.sgd$", re.IGNORECASE)

# The game keeps exactly three rotations per slot. Confirmed across every save
# folder in the 60-file corpus: no folder holds any rotation number but 0, 1, 2.
ROTATIONS = (0, 1, 2)

GAME_PROCESS = "BatmanAK.exe"
# Keeps tasklist from flashing a console window out of the --noconsole build.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class RailError(Exception):
    """A safety rail refused the operation."""


def check_writable_target(path: Path) -> None:
    """Allowlist, not blocklist: only save slots are ever written.

    profile.bin is SHA-1 protected and LBGameCache.dat is not understood, so
    neither is ours to touch.
    """
    if not SLOT_RE.match(Path(path).name):
        raise RailError(
            f"{Path(path).name} is not a save slot; this tool writes only .sgd "
            f"slot files (BAK1Save<slot>x<rotation>.sgd)")


def slot_rotations(path: Path) -> dict[int, Path]:
    """rotation number -> file, for the slot the given file belongs to.

    Every candidate is re-matched against SLOT_RE rather than trusted from the
    glob. A bare wildcard also matches names like "BAK1Save0x0 - Copy.sgd",
    which users produce constantly by copying a save in Explorer; counting one
    as a rotation would let check_slot_complete pass on a slot that is actually
    missing a rotation.
    """
    m = SLOT_RE.match(Path(path).name)
    if not m:
        raise RailError(f"{Path(path).name} is not a save slot")
    slot = int(m.group(1))

    found: dict[int, Path] = {}
    for candidate in Path(path).parent.glob("*.sgd"):
        hit = SLOT_RE.match(candidate.name)
        if hit and int(hit.group(1)) == slot:
            found[int(hit.group(2))] = candidate
    return found


def slot_files(path: Path) -> list[Path]:
    """The slot's real rotation files, ordered by rotation number."""
    found = slot_rotations(path)
    return [found[r] for r in sorted(found)]


def check_slot_complete(path: Path) -> list[Path]:
    """Confirm the slot has a sane set of rotation files, and list them.

    This used to demand all three of x0/x1/x2 on the grounds that otherwise
    "we cannot know which file the game will read". That reasoning is
    backwards — with a single rotation we know exactly which file it reads —
    and it refused a real save: the user's own slot 1 was created by the game
    with only x1. The hazard actually worth flagging is editing a rotation that
    is not the newest, and the GUI's "not the newest rotation" warning already
    covers that.

    What is still refused: a slot with no rotation files, and any rotation
    number outside 0/1/2, which no folder in the corpus has and which would
    mean we are looking at something other than an Arkham Knight save slot.

    (The name is kept because the GUI imports it; it now means "usable slot".)
    """
    found = slot_rotations(path)
    if not found:
        raise RailError(f"no rotation files found for {Path(path).name}")
    unexpected = sorted(r for r in found if r not in ROTATIONS)
    if unexpected:
        raise RailError(
            f"slot has unexpected rotation number(s) "
            f"{', '.join('x' + str(r) for r in unexpected)}; the game only ever "
            f"writes x0, x1 and x2. Refusing to edit an unfamiliar slot.")
    return [found[r] for r in sorted(found)]


def game_is_running() -> bool:
    """Editing while the game holds the save loses the edit on exit.

    Decoding is done here rather than by subprocess's text mode on purpose.
    tasklist prints the Mem-Usage column with the console codepage's thousands
    separator, which is not valid UTF-8; under Python's UTF-8 mode `text=True`
    therefore raises UnicodeDecodeError *only when a process actually matches*.
    A bare except around that turns the one case the rail exists for into a
    silent "not running" — the rail failing open exactly when it must not.

    Failing open is still the right answer when tasklist is genuinely
    unavailable (a non-Windows host): we cannot tell, so we do not block.
    """
    try:
        out = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {GAME_PROCESS}"],
            capture_output=True, timeout=10, creationflags=_NO_WINDOW).stdout
    except Exception:
        return False
    return GAME_PROCESS.lower() in (out or b"").decode("utf-8", "replace").lower()
