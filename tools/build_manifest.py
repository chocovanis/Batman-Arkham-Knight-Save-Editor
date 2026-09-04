"""Generate aksave/data/manifest.json from a complete save.

Run once. The output is committed; the input save is not.

Usage:
    python tools/build_manifest.py <complete_save.sgd> <names.tsv> <out.json>                                    [<DefaultGame.ini>]

The 315 collectible flag names are not derivable - the indices are sparse
(CityX_Pickup runs 1..41 but skips 14, 15 and 16). They must be extracted
from a save that is verified complete, so the generator hard-fails on any
save that does not carry exactly 315 PickedUp_ flags.

Display names
-------------
The optional TSV of third-party display names is NOT used by this project:
its licence is unresolved, so we do not redistribute it. Pass a path that
does not exist (the argument is kept so the fallback stays exercised) and
every item gets a generated name instead, with ``named`` false throughout.

Generated names number each (region, type) group sequentially from 1, NOT
by the raw flag index. The raw indices are sparse, so a raw index would
render "Riddler Trophy 41 - Miagani Island" in a region that only holds 38
trophies. The true sparse index is still kept in the ``index`` field - that
is what the flag itself is built from; the ordinal is for the player's eyes
only.
"""
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from aksave.sgd import SgdFile

EXPECTED_ITEMS = 315
EXPECTED_PIECES = 243

# `[BmGame.RGameInfo].RiddlerPuzzles` in the game's own DefaultGame.ini: 18
# puzzles whose ordered Pieces lists total exactly 243. The save stores one
# status byte per piece, in this order, and the number of those bytes >= 4 is
# the number the game displays. Without this table we can set the flags but not
# the per-challenge state the collectibles menu reads.
PUZZLE_RE = re.compile(r"^\s*\.RiddlerPuzzles\s*=")
PIECE_RE = re.compile(
    r"\(Type=(\w+?)(?:,Id=(\d+))?(?:,Collection=\w+,Count=(\d+))?\)")
PIECE_TYPES = {"RiddlerPiece_Trophy": "Pickup", "RiddlerPiece_Cameo": "Riddler",
               "RiddlerPiece_Bomb": "Bomb"}
BREAKABLE_OF = {"CityX": "MilitiaShield", "CityY": "MilitiaShield",
                "CityZ": "MilitiaShield", "Stagg": "InsectCrate",
                "Film": "JackInTheBox", "HideOut": "MiniDrone"}


def parse_puzzles(ini_path):
    """[{id, region, pieces:[flag | {breakable: N}]}] straight from the ini."""
    puzzles = []
    for line in Path(ini_path).read_text(encoding="utf-8", errors="replace").splitlines():
        if not PUZZLE_RE.match(line):
            continue
        pid = int(re.search(r"Id=(\d+)", line).group(1))
        region = re.search(r"Category=RiddlerCategory_(\w+)", line).group(1)
        # The ini writes "Hideout"; every save writes "HideOut".
        region = "HideOut" if region == "Hideout" else region
        pieces = []
        for kind, index, count in PIECE_RE.findall(line.split("Pieces=(", 1)[1]):
            if kind == "RiddlerPiece_Breakable":
                pieces.append({"breakable": int(count)})
            else:
                pieces.append(f"PickedUp_{region}_{PIECE_TYPES[kind]}_{index}")
        puzzles.append({"id": pid, "region": region, "pieces": pieces})

    total = sum(len(p["pieces"]) for p in puzzles)
    if total != EXPECTED_PIECES:
        sys.exit(f"expected {EXPECTED_PIECES} puzzle pieces, parsed {total}")
    return puzzles

REGIONS = {
    "CityZ": "Bleake Island", "CityX": "Miagani Island", "CityY": "Founders' Island",
    "Stagg": "Stagg Airships", "Film": "Panessa Studios", "HideOut": "Arkham Knight HQ",
}
TYPES = {
    "Pickup": "Riddler Trophy", "Riddler": "Riddle", "Bomb": "Bomb Rioter",
    "MilitiaShield": "Breakable", "InsectCrate": "Breakable",
    "JackInTheBox": "Breakable", "MiniDrone": "Breakable",
}


def parse_flag(flag):
    """PickedUp_<region>_<type>_<index> -> (region, type, index)."""
    _, region, type_, index = flag.split("_", 3)
    return region, type_, int(index)


def display_ordinals(flags):
    """flag -> 1-based position within its (region, type) group, by index.

    Sequential, so the player sees 1..N with no gaps, while ``index`` keeps
    the sparse value the game's flag string actually uses.
    """
    groups = {}
    for flag in flags:
        region, type_, index = parse_flag(flag)
        groups.setdefault((region, type_), []).append((index, flag))

    ordinals = {}
    for members in groups.values():
        for ordinal, (_, flag) in enumerate(sorted(members), start=1):
            ordinals[flag] = ordinal
    return ordinals


def main(save_path, tsv_path, out_path, ini_path=None):
    flags = sorted(f for f in SgdFile(Path(save_path).read_bytes()).read_flags()
                   if f.startswith("PickedUp_"))
    if len(flags) != EXPECTED_ITEMS:
        sys.exit(f"expected {EXPECTED_ITEMS} collectibles, found {len(flags)} "
                 f"- not a complete save")

    names = {}
    if Path(tsv_path).exists():
        text = Path(tsv_path).read_text(encoding="utf-8", errors="replace")
        for row in csv.DictReader(text.splitlines(), delimiter="\t"):
            key = (row.get("SaveFileId") or "").strip()
            if key.startswith("PickedUp_"):
                names[key] = (row.get("Name") or "").strip()

    ordinals = display_ordinals(flags)

    items = []
    for flag in flags:
        region, type_, index = parse_flag(flag)
        items.append({
            "flag": flag,
            "region": region,
            "region_name": REGIONS[region],
            "type": type_,
            "type_name": TYPES[type_],
            "index": index,
            "display": names.get(flag)
                       or f"{TYPES[type_]} {ordinals[flag]} - {REGIONS[region]}",
            "named": flag in names,
        })

    blank = [i for i in items if not i["display"]]
    if blank:
        sys.exit(f"{len(blank)} item(s) ended up with an empty display name")

    displays = {i["display"] for i in items}
    if len(displays) != len(items):
        sys.exit(f"display names are not unique: {len(displays)} for {len(items)} items")

    data = {"items": items}
    if ini_path:
        data["puzzles"] = parse_puzzles(ini_path)
        known = {i["flag"] for i in items}
        unknown = [p for z in data["puzzles"] for p in z["pieces"]
                   if isinstance(p, str) and p not in known]
        if unknown:
            sys.exit(f"puzzle table names {len(unknown)} flag(s) that are not "
                     f"in the manifest, e.g. {unknown[:3]}")

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(
        json.dumps(data, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(f"wrote {len(items)} items; {sum(i['named'] for i in items)} with source names")
    if ini_path:
        print(f"wrote {len(data['puzzles'])} puzzles, "
              f"{sum(len(p['pieces']) for p in data['puzzles'])} pieces")


if __name__ == "__main__":
    main(*sys.argv[1:5])
