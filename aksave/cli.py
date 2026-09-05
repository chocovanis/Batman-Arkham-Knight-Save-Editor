"""Command line interface. Useful for scripting and for the synthesis proof."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aksave.editor import (RailError, SaveEditor, skipped_note,
                           where_to_find)
from aksave.sgd import SgdError


def fmt_time(seconds: float) -> str:
    return f"{int(seconds // 3600)}h{int(seconds % 3600 // 60):02d}m"


def region_names(editor, regions):
    return ", ".join(sorted(editor.catalog.region_name(r) for r in regions))


def cmd_info(args):
    e = SaveEditor(Path(args.save).read_bytes())
    print(f"platform  : {e.platform}")
    print(f"playtime  : {fmt_time(e.playtime_seconds)}")
    print(f"collected : {e.collected_count}/315 objects")
    print(f"challenges: {e.challenge_count}/243")
    if e.untracked_regions:
        print(f"not editable: {region_names(e, e.untracked_regions)} "
              f"(no Riddler records in this save yet)")


def cmd_collect_all(args):
    src = Path(args.save)
    e = SaveEditor(src.read_bytes())
    before = e.challenge_count
    added = e.collect_all(leave_one=args.leave_one)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(e.to_bytes())
    print(f"{before}/243 -> {e.challenge_count}/243  (+{len(added)} flags)")
    if e.left_behind:
        print(f"LEFT ONE for you to pick up in game, so the achievement still "
              f"fires: {where_to_find(e.left_behind, e.catalog)}")
    note = skipped_note(e)
    if note:
        print(note)
    print(f"wrote {out} ({out.stat().st_size} bytes)")


def main(argv=None):
    p = argparse.ArgumentParser(prog="aksave")
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("info", help="show save state")
    i.add_argument("save")
    i.set_defaults(func=cmd_info)

    c = sub.add_parser("collect-all", help="write a fully collected copy")
    c.add_argument("save")
    c.add_argument("-o", "--out", required=True)
    c.add_argument("--no-leave-one", dest="leave_one", action="store_false")
    c.set_defaults(func=cmd_collect_all, leave_one=True)

    args = p.parse_args(argv)
    try:
        args.func(args)
    except (RailError, SgdError, OSError) as exc:
        # An expected refusal or a missing/locked file is not a bug in the
        # tool, and a 20-line traceback for "you typed the wrong path" buries
        # the one line that matters.
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
