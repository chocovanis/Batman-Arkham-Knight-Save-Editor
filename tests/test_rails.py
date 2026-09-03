import pytest

import aksave.rails as rails
from aksave.rails import (RailError, check_writable_target, check_slot_complete,
                          game_is_running, slot_files)


def test_rejects_non_sgd_target(tmp_path):
    p = tmp_path / "profile.bin"
    p.write_bytes(b"x")
    with pytest.raises(RailError, match="only .sgd"):
        check_writable_target(p)


def test_rejects_lbgamecache(tmp_path):
    p = tmp_path / "LBGameCache.dat"
    p.write_bytes(b"x")
    with pytest.raises(RailError, match="only .sgd"):
        check_writable_target(p)


def test_accepts_sgd(tmp_path):
    p = tmp_path / "BAK1Save0x0.sgd"
    p.write_bytes(b"x")
    check_writable_target(p)   # must not raise


def test_slot_complete_requires_all_rotations(tmp_path):
    for n in ("BAK1Save0x0.sgd", "BAK1Save0x1.sgd"):
        (tmp_path / n).write_bytes(b"x")
    with pytest.raises(RailError, match="rotation"):
        check_slot_complete(tmp_path / "BAK1Save0x0.sgd")


def test_slot_complete_passes_with_three(tmp_path):
    for n in ("BAK1Save0x0.sgd", "BAK1Save0x1.sgd", "BAK1Save0x2.sgd"):
        (tmp_path / n).write_bytes(b"x")
    check_slot_complete(tmp_path / "BAK1Save0x0.sgd")


def test_game_running_returns_bool():
    assert isinstance(game_is_running(), bool)


# --- regressions -----------------------------------------------------------
# Each of these reproduces a defect found by review of the first implementation.


def test_slot_complete_rejects_an_explorer_copy_as_a_rotation(tmp_path):
    """A bare BAK1Save0x*.sgd wildcard also matches "BAK1Save0x0 - Copy.sgd".

    Users make those constantly. Counting one as a rotation let the rail pass a
    slot that was genuinely missing x2 - the exact state it exists to block.
    """
    for n in ("BAK1Save0x0.sgd", "BAK1Save0x1.sgd", "BAK1Save0x0 - Copy.sgd"):
        (tmp_path / n).write_bytes(b"x")
    with pytest.raises(RailError, match="x2"):
        check_slot_complete(tmp_path / "BAK1Save0x0.sgd")


def test_slot_complete_names_the_rotation_that_is_missing(tmp_path):
    for n in ("BAK1Save0x0.sgd", "BAK1Save0x2.sgd"):
        (tmp_path / n).write_bytes(b"x")
    with pytest.raises(RailError, match="x1"):
        check_slot_complete(tmp_path / "BAK1Save0x0.sgd")


def test_slot_files_lists_only_real_rotations_of_this_slot(tmp_path):
    for n in ("BAK1Save0x0.sgd", "BAK1Save0x1.sgd", "BAK1Save0x2.sgd",
              "BAK1Save0x0 - Copy.sgd", "BAK1Save1x0.sgd", "notasave.sgd"):
        (tmp_path / n).write_bytes(b"x")
    assert [q.name for q in slot_files(tmp_path / "BAK1Save0x0.sgd")] == [
        "BAK1Save0x0.sgd", "BAK1Save0x1.sgd", "BAK1Save0x2.sgd"]


# tasklist writes the Mem Usage column with the console codepage's thousands
# separator. 0xFF is not valid UTF-8, and it appears only on a row that
# actually matched - so text=True raised UnicodeDecodeError precisely when a
# process was found, and the bare except turned that into a silent
# "not running": the rail failing open exactly when it must not.
MATCHING_ROW = (
    b"Image Name    PID Session Name  Mem Usage\r\n"
    b"BatmanAK.exe 1234 Console      1\xff234 K\r\n"
)
NO_MATCH_ROW = b"INFO: No tasks are running which match the specified criteria.\r\n"


def _fake_tasklist(monkeypatch, stdout):
    class Result:
        pass

    Result.stdout = stdout
    monkeypatch.setattr(rails.subprocess, "run", lambda *a, **k: Result())


def test_game_running_survives_non_utf8_tasklist_output(monkeypatch):
    _fake_tasklist(monkeypatch, MATCHING_ROW)
    assert game_is_running() is True


def test_matching_row_really_is_undecodable_as_utf8():
    """Guards the premise of the test above: if this ever decodes cleanly the
    regression it protects against has stopped being reproducible."""
    with pytest.raises(UnicodeDecodeError):
        MATCHING_ROW.decode("utf-8")


def test_game_not_running_when_tasklist_reports_no_match(monkeypatch):
    _fake_tasklist(monkeypatch, NO_MATCH_ROW)
    assert game_is_running() is False


def test_game_running_fails_open_when_tasklist_is_unavailable(monkeypatch):
    """Not a Windows host: we cannot tell, so we must not block every edit."""
    def boom(*a, **k):
        raise FileNotFoundError("tasklist")

    monkeypatch.setattr(rails.subprocess, "run", boom)
    assert game_is_running() is False
