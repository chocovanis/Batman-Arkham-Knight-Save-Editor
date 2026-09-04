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


def test_slot_with_one_rotation_is_accepted(tmp_path):
    """The game really does create these.

    The user's own slot 1 held only x1. Demanding all three rotations refused a
    genuine save; with one rotation we know exactly which file the game reads.
    """
    (tmp_path / "BAK1Save1x1.sgd").write_bytes(b"x")
    assert [p.name for p in check_slot_complete(tmp_path / "BAK1Save1x1.sgd")]         == ["BAK1Save1x1.sgd"]


def test_slot_with_no_rotations_is_refused(tmp_path):
    with pytest.raises(RailError, match="no rotation files"):
        check_slot_complete(tmp_path / "BAK1Save0x0.sgd")


def test_slot_with_an_unfamiliar_rotation_number_is_refused(tmp_path):
    """No folder in the corpus uses a rotation outside 0/1/2, so one that does
    is not a shape we have ever seen the game write."""
    for n in ("BAK1Save0x0.sgd", "BAK1Save0x7.sgd"):
        (tmp_path / n).write_bytes(b"x")
    with pytest.raises(RailError, match="x7"):
        check_slot_complete(tmp_path / "BAK1Save0x0.sgd")


def test_slot_complete_passes_with_three(tmp_path):
    for n in ("BAK1Save0x0.sgd", "BAK1Save0x1.sgd", "BAK1Save0x2.sgd"):
        (tmp_path / n).write_bytes(b"x")
    check_slot_complete(tmp_path / "BAK1Save0x0.sgd")


def test_game_running_returns_bool():
    assert isinstance(game_is_running(), bool)


# --- regressions -----------------------------------------------------------
# Each of these reproduces a defect found by review of the first implementation.


def test_an_explorer_copy_is_not_counted_as_a_rotation(tmp_path):
    """A bare BAK1Save0x*.sgd wildcard also matches "BAK1Save0x0 - Copy.sgd",
    which users produce constantly by copying a save in Explorer. It is not a
    rotation and must never be offered as one."""
    for n in ("BAK1Save0x0.sgd", "BAK1Save0x1.sgd", "BAK1Save0x0 - Copy.sgd"):
        (tmp_path / n).write_bytes(b"x")
    assert [p.name for p in check_slot_complete(tmp_path / "BAK1Save0x0.sgd")]         == ["BAK1Save0x0.sgd", "BAK1Save0x1.sgd"]


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
