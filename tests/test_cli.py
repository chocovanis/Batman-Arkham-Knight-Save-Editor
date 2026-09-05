"""The command line interface.

The GUI is what users run; the CLI is what scripts and the synthesis proof run,
and it is the only surface where the skip and leave-one messages can be checked
against real output rather than by reading the source.
"""

import pytest

from aksave.catalog import Catalog
from aksave.cli import main
from tests.test_sgd import make_save_with_flags

CAT = Catalog.load()
ALL = [i.flag for i in CAT.items]


@pytest.fixture
def save(tmp_path):
    p = tmp_path / "BAK1Save0x0.sgd"
    p.write_bytes(make_save_with_flags(ALL[:10]))
    return p


def test_info_reports_the_state_of_the_save(save, capsys):
    main(["info", str(save)])
    out = capsys.readouterr().out
    assert "Steam" in out
    assert "10/315 objects" in out


def test_collect_all_says_where_to_find_the_one_it_left(save, tmp_path, capsys):
    """Leaving a collectible behind is only useful if the user can find it."""
    main(["collect-all", str(save), "-o", str(tmp_path / "out.sgd")])
    out = capsys.readouterr().out
    assert "242/243" in out
    assert "Ace Chemicals" in out
    assert "Bleake Island" in out


def test_collect_all_never_prints_the_trophy_index_next_to_the_location(save, tmp_path, capsys):
    """THE NUMBERING TRAP: the flag says Pickup_13, the display name says
    "Riddler Trophy 13" and IGN calls the same object Bleake Island trophy 6.
    A user given the number and then a guide goes to the wrong building."""
    main(["collect-all", str(save), "-o", str(tmp_path / "out.sgd")])
    out = capsys.readouterr().out
    assert "Riddler Trophy 13" not in out


def test_no_leave_one_reaches_243_and_says_nothing_about_finding_anything(save, tmp_path, capsys):
    main(["collect-all", str(save), "-o", str(tmp_path / "out.sgd"), "--no-leave-one"])
    out = capsys.readouterr().out
    assert "243/243" in out
    assert "Ace Chemicals" not in out


def test_everything_the_cli_prints_survives_a_windows_console(save, tmp_path, capsys):
    """A Windows console runs in the active code page, not UTF-8, and print()
    raises UnicodeEncodeError on a character the page has no room for. An
    em-dash in the leave-one note came back as a replacement character the
    first time this was run for real, which is one code page away from an
    unhandled crash on the tool's most important message."""
    main(["collect-all", str(save), "-o", str(tmp_path / "out.sgd")])
    out = capsys.readouterr().out
    out.encode("cp437")     # raises UnicodeEncodeError if anything is exotic
    assert out.isascii()


def test_collect_all_reports_a_skipped_area_in_the_shared_wording(tmp_path, capsys):
    """The GUI and the CLI must say the same thing about a skipped area, so
    both take the sentence from skipped_note rather than writing their own."""
    from aksave.editor import SaveEditor, skipped_note

    p = tmp_path / "BAK1Save0x0.sgd"
    p.write_bytes(make_save_with_flags(ALL[:10], skip_regions=("HideOut",)))
    main(["collect-all", str(p), "-o", str(tmp_path / "out.sgd"),
          "--no-leave-one"])
    out = capsys.readouterr().out

    expected = skipped_note(SaveEditor(p.read_bytes(), CAT))
    assert expected in out
    assert "216/243" in out       # 243 minus Arkham Knight HQ's 27


def test_info_reports_a_skipped_area_too(tmp_path, capsys):
    """A user checking state before editing should learn about it then, not
    only after the write."""
    p = tmp_path / "BAK1Save0x0.sgd"
    p.write_bytes(make_save_with_flags(ALL[:10], skip_regions=("HideOut",)))
    main(["info", str(p)])
    assert "Arkham Knight HQ" in capsys.readouterr().out


def test_a_missing_file_is_one_line_not_a_traceback(tmp_path, capsys):
    """Every ordinary mistake — a typo'd path, a folder, a file that is not a
    save — used to end in a raw traceback."""
    rc = main(["info", str(tmp_path / "nope.sgd")])
    assert rc == 1
    err = capsys.readouterr().err
    assert err.startswith("error: ")
    assert "Traceback" not in err


def test_a_file_that_is_not_a_save_is_refused_the_same_way(tmp_path, capsys):
    junk = tmp_path / "BAK1Save0x0.sgd"
    junk.write_bytes(b"this is not a save file")
    assert main(["info", str(junk)]) == 1
    assert "Traceback" not in capsys.readouterr().err


def test_a_save_with_nothing_collected_is_refused_in_the_players_words(tmp_path, capsys):
    p = tmp_path / "BAK1Save0x0.sgd"
    p.write_bytes(make_save_with_flags([]))
    assert main(["info", str(p)]) == 1
    err = capsys.readouterr().err
    assert "no Riddler collectibles" in err
    assert "world-state" not in err


def test_success_still_returns_zero(save, tmp_path):
    assert main(["collect-all", str(save), "-o", str(tmp_path / "out.sgd")]) == 0
