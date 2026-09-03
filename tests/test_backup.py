from datetime import datetime

import pytest

import aksave.backup as backup_mod
from aksave.backup import create_backup, list_backups, restore_backup, BackupError


@pytest.fixture
def slot(tmp_path):
    src = tmp_path / "remote"
    src.mkdir()
    for name in ("BAK1Save0x0.sgd", "BAK1Save0x1.sgd", "BAK1Save0x2.sgd"):
        (src / name).write_bytes(b"original-" + name.encode())
    return src


def test_backup_copies_and_verifies(tmp_path, slot):
    b = create_backup(slot, tmp_path / "backups", label="242/243")
    assert (b / "BAK1Save0x0.sgd").read_bytes() == b"original-BAK1Save0x0.sgd"
    assert (b / "manifest.json").exists()


def test_backup_is_listed_with_its_label(tmp_path, slot):
    create_backup(slot, tmp_path / "backups", label="242/243")
    entries = list_backups(tmp_path / "backups")
    assert len(entries) == 1
    assert entries[0].label == "242/243"


def test_restore_puts_files_back(tmp_path, slot):
    b = create_backup(slot, tmp_path / "backups", label="x")
    (slot / "BAK1Save0x0.sgd").write_bytes(b"CLOBBERED")
    restore_backup(b, slot)
    assert (slot / "BAK1Save0x0.sgd").read_bytes() == b"original-BAK1Save0x0.sgd"


def test_restore_detects_corrupted_backup(tmp_path, slot):
    b = create_backup(slot, tmp_path / "backups", label="x")
    (b / "BAK1Save0x0.sgd").write_bytes(b"tampered")
    with pytest.raises(BackupError, match="checksum"):
        restore_backup(b, slot)


# --- regressions -----------------------------------------------------------


def test_two_backups_in_the_same_second_are_both_kept(tmp_path, slot, monkeypatch):
    """The stamp resolves to the second, and two backups inside one second are
    ordinary - "Back Up Now" followed by an edit, which backs up again. The
    second mkdir used to raise a raw FileExistsError and abort the edit."""
    class Frozen:
        @staticmethod
        def now():
            return datetime(2026, 9, 3, 23, 37, 13)

    monkeypatch.setattr(backup_mod, "datetime", Frozen)
    root = tmp_path / "backups"
    first = create_backup(slot, root, label="before")
    second = create_backup(slot, root, label="after")

    assert first != second
    assert {e.label for e in list_backups(root)} == {"before", "after"}
    restore_backup(second, slot)   # the second one is a real, usable backup
