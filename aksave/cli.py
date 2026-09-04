"""Command line interface. Useful for scripting and for the synthesis proof."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aksave.editor import SaveEditor


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
    if e.untracked_regions:
        print(f"SKIPPED {region_names(e, e.untracked_regions)}: this save has no "
              f"Riddler records for those areas yet. Visit each one once in game, "
              f"save, and run again to finish the set.")
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
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
