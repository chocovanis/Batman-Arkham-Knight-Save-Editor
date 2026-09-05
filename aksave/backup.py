"""Backup and restore for a save slot.

A backup is only useful if it is trustworthy, so every copy is verified by
hash on creation and re-verified on restore.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

COPY_PATTERNS = ("*.sgd", "profile.bin", "LBGameCache.dat")


class BackupError(Exception):
    pass


@dataclass(frozen=True)
class BackupEntry:
    path: Path
    created: str
    label: str
    files: int


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_backup(slot_dir: Path, backup_root: Path, label: str = "") -> Path:
    slot_dir, backup_root = Path(slot_dir), Path(backup_root)
    files = sorted({p for pat in COPY_PATTERNS for p in slot_dir.glob(pat)})
    if not files:
        raise BackupError(f"nothing to back up in {slot_dir}")

    # The stamp resolves to the second, and two backups inside one second are
    # ordinary: clicking "Back Up Now" and then an edit, which takes its own
    # backup, does it. Without the suffix the second mkdir raises a raw
    # FileExistsError and aborts the edit, so disambiguate instead.
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    dest, attempt = backup_root / stamp, 1
    while dest.exists():
        attempt += 1
        dest = backup_root / f"{stamp}-{attempt}"
    dest.mkdir(parents=True, exist_ok=False)

    digests = {}
    for src in files:
        shutil.copy2(src, dest / src.name)
        digest = _sha256(src)
        if _sha256(dest / src.name) != digest:
            raise BackupError(f"copy of {src.name} did not verify")
        digests[src.name] = digest

    (dest / "manifest.json").write_text(json.dumps({
        "created": dest.name, "label": label,
        "source": str(slot_dir), "files": digests,
    }, indent=1))
    return dest


def list_backups(backup_root: Path) -> list[BackupEntry]:
    """Every usable backup, newest first. One bad entry must not cost the rest.

    The loop is guarded per directory because this is the recovery path, and
    the events that damage a backup are the same events that send the user
    looking for one. `manifest.json` is written last and in a single un-flushed
    write, so an interrupted backup leaves exactly the truncated or NUL-padded
    file that `json.loads` rejects — and an unguarded raise here took every
    other backup in the folder with it.
    """
    root = Path(backup_root)
    if not root.is_dir():
        return []
    try:
        entries = sorted(root.iterdir(), reverse=True)
    except OSError:
        return []

    out = []
    for d in entries:
        try:
            mf = d / "manifest.json"
            if not (d.is_dir() and mf.exists()):
                continue
            m = json.loads(mf.read_text())
            out.append(BackupEntry(d, m.get("created", d.name), m.get("label", ""),
                                   len(m.get("files", {}))))
        except (OSError, ValueError, TypeError, AttributeError):
            continue        # a damaged backup is skipped, never fatal
    return out


def backup_contents(backup_dir: Path) -> list[str]:
    """The filenames a restore from this backup would put back.

    Needed before the restore runs, so the user can be told what is about to
    be overwritten. Never raises: a backup too damaged to read is one we
    cannot describe, and the caller decides what to do about that.
    """
    try:
        m = json.loads((Path(backup_dir) / "manifest.json").read_text())
        return sorted(m.get("files", {}))
    except (OSError, ValueError, TypeError, AttributeError):
        return []


def restore_backup(backup_dir: Path, slot_dir: Path) -> list[str]:
    backup_dir, slot_dir = Path(backup_dir), Path(slot_dir)
    manifest = json.loads((backup_dir / "manifest.json").read_text())

    # Verify everything before writing anything — a half-restore is worse
    # than no restore.
    for name, digest in manifest["files"].items():
        src = backup_dir / name
        if not src.exists():
            raise BackupError(f"backup is missing {name}")
        if _sha256(src) != digest:
            raise BackupError(f"checksum mismatch for {name}; backup is corrupt")

    for name in manifest["files"]:
        shutil.copy2(backup_dir / name, slot_dir / name)
    return sorted(manifest["files"])
