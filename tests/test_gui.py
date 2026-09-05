"""Headless tests for the GUI's non-widget logic.

Deliberately narrow. Nothing here constructs a Tk root, so the file is safe to
collect on a CI runner with no desktop session: importing tkinter is fine, only
instantiating it is not. The widget behaviour is verified by driving the real
app against copied saves, which needs a display and so is not part of pytest.
"""

import os
import pytest
import struct

import ak_riddler_editor as app
from aksave.sgd import STEAM_SIZE

from tests.test_sgd import make_save_with_flags


def _save(tmp_path, name, playtime, mtime):
    raw = bytearray(make_save_with_flags(["A"]))
    struct.pack_into("<f", raw, 0x69, playtime)
    p = tmp_path / name
    p.write_bytes(bytes(raw))
    os.utime(p, (mtime, mtime))
    return p


def test_rotation_rank_prefers_playtime_over_mtime(tmp_path):
    """Copying a save folder gives every rotation one identical mtime.

    Ranking on mtime alone then resolves the tie arbitrarily, and the app would
    announce "not the newest rotation" naming a file at random. Playtime lives
    inside the file and survives the copy, so it decides.
    """
    older = _save(tmp_path, "BAK1Save0x0.sgd", playtime=3600.0, mtime=1_700_000_000)
    newer = _save(tmp_path, "BAK1Save0x1.sgd", playtime=7200.0, mtime=1_700_000_000)

    assert app.EditorApp._rotation_rank(newer) > app.EditorApp._rotation_rank(older)


def test_rotation_rank_falls_back_to_mtime_when_playtime_ties(tmp_path):
    a = _save(tmp_path, "BAK1Save0x0.sgd", playtime=3600.0, mtime=1_700_000_000)
    b = _save(tmp_path, "BAK1Save0x1.sgd", playtime=3600.0, mtime=1_700_000_500)

    assert app.EditorApp._rotation_rank(b) > app.EditorApp._rotation_rank(a)


def test_rotation_rank_survives_an_unreadable_file(tmp_path):
    """A rotation we cannot parse must rank last, not raise: the warning is a
    convenience and must never be able to stop a save from opening."""
    good = _save(tmp_path, "BAK1Save0x0.sgd", playtime=3600.0, mtime=1_700_000_000)
    bad = tmp_path / "BAK1Save0x1.sgd"
    bad.write_bytes(b"not a save")
    os.utime(bad, (1_700_000_500, 1_700_000_500))

    assert app.EditorApp._rotation_rank(good) > app.EditorApp._rotation_rank(bad)


def test_type_labels_cover_every_type_in_the_manifest():
    """populate_tree indexes TYPE_LABELS directly, so a manifest type with no
    label is a KeyError that empties the whole tree."""
    from aksave.catalog import Catalog

    types = {i.type for i in Catalog.load().items}
    assert types <= set(app.TYPE_LABELS)


def test_a_full_save_is_still_the_expected_size():
    """Cheap guard on the test helper the rest of this file leans on."""
    assert len(make_save_with_flags(["A"])) == STEAM_SIZE


# --- window sizing ---------------------------------------------------------
# The bug this replaces only ever appeared on a display the author did not
# have, so the sizing rule is a pure function and gets checked against the
# whole range rather than against whatever monitor happens to be attached.

SCREENS = [
    (1280, 720),    # small laptop
    (1366, 768),    # the most common cheap laptop panel
    (1440, 900),
    (1600, 900),
    (1920, 1080),   # by far the most common desktop
    (2560, 1440),
    (3440, 1440),   # ultrawide
    (3840, 2160),   # 4K, and this machine
    (5120, 1440),   # super-ultrawide
]


@pytest.mark.parametrize("sw,sh", SCREENS)
def test_window_always_fits_on_screen(sw, sh):
    w, h, x, y = app.window_geometry(sw, sh)
    assert 0 < w <= sw and 0 < h <= sh
    assert x >= 0 and y >= 0
    assert x + w <= sw, "window runs off the right edge"
    assert y + h <= sh, "window runs off the bottom edge"


@pytest.mark.parametrize("sw,sh", SCREENS)
def test_window_is_centred(sw, sh):
    w, h, x, y = app.window_geometry(sw, sh)
    # Left and right margins differ by at most a rounding pixel.
    assert abs((sw - w - x) - x) <= 1
    assert abs((sh - h - y) - y) <= 1


@pytest.mark.parametrize("sw,sh", SCREENS)
def test_window_is_big_enough_for_the_layout(sw, sh):
    """The layout needs about 1000px. Anything narrower clips the Status
    column, which is the defect that prompted the rule."""
    w, h, _, _ = app.window_geometry(sw, sh)
    assert w >= min(app.FLOOR_W, sw - 40)
    assert h >= min(app.FLOOR_H, sh - 80)


@pytest.mark.parametrize("sw,sh", SCREENS)
def test_minsize_never_exceeds_the_window(sw, sh):
    """A minsize larger than the window makes it un-resizable and can push it
    off screen on the small panels."""
    w, h, _, _ = app.window_geometry(sw, sh)
    assert min(app.MIN_W, w) <= w
    assert min(app.MIN_H, h) <= h


def test_bigger_screens_get_bigger_windows():
    widths = [app.window_geometry(sw, sh)[0] for sw, sh in
              [(1280, 720), (1920, 1080), (2560, 1440), (3840, 2160)]]
    assert widths == sorted(widths)
    assert widths[-1] > widths[0], "a 4K window should not be laptop-sized"


def test_absurdly_small_screen_does_not_produce_a_negative_window():
    w, h, x, y = app.window_geometry(640, 480)
    assert w > 0 and h > 0 and x >= 0 and y >= 0


@pytest.mark.parametrize("sw,sh", SCREENS)
def test_ui_font_scale_stays_in_range(sw, sh):
    assert 1.0 <= app.ui_font_scale(sw) <= 1.4


def test_ordinary_screens_are_left_alone_and_large_ones_scale_up():
    """1080p is the common case and should render exactly as designed; a 4K
    panel needs bigger type or the UI reads as tiny."""
    assert app.ui_font_scale(1920) == 1.0
    assert app.ui_font_scale(1366) == 1.0
    assert app.ui_font_scale(3840) > 1.2


def test_theming_has_no_optional_engine_behind_a_try_except():
    """The type sizing once lived in an `except ImportError` branch that ran
    only when sv_ttk was absent — so it did nothing in the packaged build,
    which shipped sv_ttk, and glyphs measured 10px on a 4K screen.

    sv_ttk is gone now (224 ms/frame on resize against clam's 39), and the
    sizing must stay unconditional. Assert structurally that apply_theme has
    no try/except around its styling and still sizes the named fonts.
    """
    import inspect
    import textwrap

    src = textwrap.dedent(inspect.getsource(app.apply_theme))
    body = src.split('"""', 2)[-1]

    assert "nametofont" in body, "the named-font sizing has gone missing"
    assert "sv_ttk" not in body, "an optional theme engine came back into the body"

    # Every styling call must sit at function-body indentation. Anything deeper
    # means it is nested inside a conditional or a try, which is exactly how the
    # sizing came to be skipped in the shipped build.
    for marker in ('style.theme_use', 'style.configure(".", ',
                   'style.configure("Treeview"'):
        lines = [ln for ln in body.splitlines() if marker in ln]
        assert lines, f"{marker} has gone missing from apply_theme"
        for ln in lines:
            assert len(ln) - len(ln.lstrip()) == 4, f"{marker} is nested: {ln!r}"


# --- the status line -------------------------------------------------------
# Extracted from refresh() so it can be checked without a display. This is the
# line the user reads to confirm the tool is pointed at the save they meant,
# which is the single most consequential thing the window tells them.

from pathlib import Path

from aksave.catalog import Catalog
from aksave.editor import SaveEditor

CAT = Catalog.load()
ALL = [i.flag for i in CAT.items]


def _editor(flags=None, **kw):
    return SaveEditor(make_save_with_flags(flags or ALL[:10], **kw), CAT)


def test_slot_label_maps_a_filename_to_the_slot_the_game_shows():
    """BAK1Save0x* is UI slot 1. Nobody knows that, so the window has to say
    it: a save folder holding a 51-hour playthrough and a throwaway differs
    only by one digit in the middle of a filename."""
    assert app.slot_label(Path("BAK1Save0x0.sgd")) == "Slot 1"
    assert app.slot_label(Path("BAK1Save1x1.sgd")) == "Slot 2"
    assert app.slot_label(Path("BAK1Save2x0.sgd")) == "Slot 3"


def test_slot_label_falls_back_to_the_filename_when_it_is_not_a_slot():
    assert app.slot_label(Path("something-else.sgd")) == "something-else.sgd"


def test_status_line_leads_with_the_slot_and_keeps_the_filename():
    line = app.status_text(Path("BAK1Save2x0.sgd"), _editor(), None)
    assert line.startswith("Slot 3")
    assert "BAK1Save2x0.sgd" in line
    assert "Steam" in line
    assert "243 challenges" in line


def test_status_line_says_when_an_area_cannot_be_edited():
    """A save that has never reached Arkham Knight HQ finishes 27 challenges
    short. The CLI has always said so; the window said nothing at all."""
    e = _editor(skip_regions=("HideOut",))
    line = app.status_text(Path("BAK1Save2x0.sgd"), e, None)
    assert "Arkham Knight HQ" in line


def test_status_line_is_quiet_when_every_area_is_editable():
    assert "not editable" not in app.status_text(Path("BAK1Save2x0.sgd"), _editor(), None)


def test_status_line_still_warns_about_an_older_rotation():
    line = app.status_text(Path("BAK1Save2x0.sgd"), _editor(),
                           Path("BAK1Save2x1.sgd"))
    assert "newest" in line
    assert "BAK1Save2x1.sgd" in line


def test_region_row_marks_the_area_the_editor_cannot_touch():
    """The tree lists all six areas whether or not the save can hold them."""
    untracked = {"HideOut"}
    assert app.region_row_label("Arkham Knight HQ", "HideOut", untracked) != "Arkham Knight HQ"
    assert "not editable" in app.region_row_label("Arkham Knight HQ", "HideOut", untracked)
    assert app.region_row_label("Bleake Island", "CityZ", untracked) == "Bleake Island"


# --- messages the window must not lose -------------------------------------
# These paths need a Tk root to exercise, so they are asserted structurally,
# the same way the theming test is. What they guard is not cosmetic: the GUI
# used to be silent about both of these, and each silence looks exactly like
# the tool being broken.


def test_the_window_reports_an_area_it_could_not_edit():
    """The CLI has always printed skipped_note. The window never mentioned
    untracked regions anywhere — not the status line, not the tree, not the
    log — so a mid-game save that finished at 215/243 gave the user a wrong
    number and no explanation."""
    import inspect

    src = inspect.getsource(app)
    assert "skipped_note" in src, "the skipped-area message has gone missing"
    for method in (app.EditorApp.load, app.EditorApp.on_collect_all):
        assert "skipped_note" in inspect.getsource(method), \
            f"{method.__name__} no longer reports a skipped area"
    assert "untracked" in inspect.getsource(app.status_text)
    assert "untracked" in inspect.getsource(app.EditorApp.populate_tree)


def test_the_window_says_where_the_collectible_it_left_behind_is():
    """Leaving one uncollected is only useful if the user can find it, and the
    tree cannot show it: the whole point is that it is NOT collected."""
    import inspect

    src = inspect.getsource(app.EditorApp.on_collect_all)
    assert "where_to_find" in src
    assert "left_behind" in src


def test_the_window_never_prints_the_left_behind_trophys_index():
    """THE NUMBERING TRAP: the save flag says Pickup_13, this tool's display
    name says "Riddler Trophy 13", and IGN calls the same warehouse Bleake
    Island trophy 6. Printing the number alongside a guide reference sends the
    user to the wrong building."""
    from aksave.editor import LEAVE_ONE_FLAG, where_to_find

    note = where_to_find(LEAVE_ONE_FLAG, CAT)
    assert CAT.item(LEAVE_ONE_FLAG).display not in note
    assert app.TYPE_LABELS["Pickup"] + " 13" not in note


def test_the_leave_one_label_says_where_without_saying_which_number():
    """The checkbox is the last thing the user reads before clicking, and it
    is the one control that decides whether the save ends at 242 or 243. It
    should place the trophy without inviting a lookup by number."""
    label = app.LEAVE_ONE_LABEL
    assert "Bleake Island" in label
    assert "achievement" in label
    assert "13" not in label
    assert len(label) < 130, "a tk.Checkbutton label does not wrap"


# --- refusing a save the player can do something about ---------------------
# Opening a clean new-game slot in the packaged build produced an error dialog
# titled "Cannot read save" containing "no world-state store holding
# collectibles was found". The save read fine, and the sentence was about our
# parser. Both halves are now decided by a pure function.


def test_an_explained_refusal_is_information_not_an_error():
    from aksave.editor import NOTHING_COLLECTED
    from aksave.editor import RailError as EditorRailError

    kind, title, message = app.refusal_dialog(EditorRailError(NOTHING_COLLECTED))
    assert kind == "info"
    assert "cannot be edited" in title.lower()
    assert message == NOTHING_COLLECTED
    assert "read" not in title.lower(), "the save read perfectly well"


def test_an_unrecognised_file_is_still_a_real_error():
    from aksave.sgd import SgdError

    kind, title, message = app.refusal_dialog(SgdError("unexpected size 1234"))
    assert kind == "error"
    assert "1234" in message


def test_a_refusal_we_did_not_anticipate_says_so_rather_than_pretending():
    kind, title, message = app.refusal_dialog(ValueError("boom"))
    assert kind == "error"
    assert "boom" in message


def test_load_routes_both_kinds_through_that_one_decision():
    import inspect

    src = inspect.getsource(app.EditorApp.load)
    assert "refusal_dialog" in src
    assert "showinfo" in src and "showerror" in src


# --- auto-detect must not open the one file the tool cannot edit -----------


def test_autodetect_prefers_a_save_that_can_actually_be_edited(tmp_path):
    """_best_candidate already prefers a complete slot, for the stated reason
    that "auto-loading the one file the tool cannot edit reads as a bug rather
    than as a rail doing its job". A brand-new save is the same case: it has
    the newest playtime in a folder where an older save is the real one."""
    def write(name, flags, playtime):
        raw = bytearray(make_save_with_flags(flags))
        struct.pack_into("<f", raw, 0x69, playtime)
        p = tmp_path / name
        p.write_bytes(bytes(raw))
        os.utime(p, (1_700_000_000, 1_700_000_000))
        return p

    real = write("BAK1Save0x0.sgd", ALL[:40], 40_000.0)
    write("BAK1Save1x1.sgd", [], 90_000.0)          # brand new, but "newest"

    assert app.EditorApp._best_candidate(sorted(tmp_path.glob("*.sgd"))) == real


# --- how a failed operation is reported ------------------------------------
# Three confirmed findings share one cause. Activity logged "FAILED: <msg>"
# and then the full traceback into a 9-line panel, which scrolled the only
# actionable line out of view; no failure ever raised a dialog; and because
# on_error=reload succeeded, the last line in the log read "Loaded <save>
# (Steam, 51h08m, 215/243)" — a failed write signing off as a success.


def test_a_rail_refusal_says_plainly_that_nothing_was_written():
    from aksave.editor import NOTHING_COLLECTED
    from aksave.editor import RailError as EditorRailError

    kind, title, message, tb = app.failure_dialog(EditorRailError(NOTHING_COLLECTED))
    assert kind == "info"
    assert "nothing" in title.lower() or "not" in title.lower()
    assert message == NOTHING_COLLECTED
    assert tb is False, "a rail doing its job is not a crash"


def test_the_game_running_refusal_is_a_refusal_not_a_crash():
    kind, title, message, tb = app.failure_dialog(app.Refused("the game is running"))
    assert kind == "info"
    assert tb is False


def test_a_locked_file_explains_itself_instead_of_showing_a_winerror():
    """The most likely real failure: antivirus, OneDrive or Steam holding the
    file. `[WinError 5] Access is denied` on its own tells a player nothing."""
    kind, title, message, tb = app.failure_dialog(
        PermissionError(13, "Access is denied"))
    assert kind == "error"
    assert "another program" in message or "read-only" in message
    assert "backed up" in message, "the user needs to know their save is safe"


def test_an_unexpected_bug_still_shows_its_traceback():
    kind, title, message, tb = app.failure_dialog(KeyError("puzzle 99"))
    assert kind == "error"
    assert tb is True
    assert "KeyError" in message


# --- choosing which save to open -------------------------------------------
# The acceptance test found this the hard way. "Open Save…" was a raw file
# dialog listing BAK1Save0x0 / 0x1 / 0x2 / 1x1 / 2x0 / 2x1 / 2x2 with nothing
# to say which was which, the user picked a rotation the game does not load,
# and the only objection was a log line that scrolled past while the button
# stayed live. The edit landed on a file the game never read.


def _folder(tmp_path, spec):
    """spec: {filename: (flags, playtime)}"""
    import struct
    for name, (flags, playtime) in spec.items():
        raw = bytearray(make_save_with_flags(flags))
        struct.pack_into("<f", raw, 0x69, playtime)
        (tmp_path / name).write_bytes(bytes(raw))
    return sorted(tmp_path.glob("BAK1Save*.sgd"))


def test_every_save_is_described_by_slot_playtime_and_progress(tmp_path):
    from aksave.catalog import Catalog
    paths = _folder(tmp_path, {
        "BAK1Save0x0.sgd": (ALL[:40], 184101.0),
        "BAK1Save2x0.sgd": (ALL[:20], 71786.0),
    })
    rows = app.save_rows(paths, Catalog.load())
    assert [r.slot for r in rows] == ["Slot 1", "Slot 3"]
    assert rows[0].playtime == "51h08m"
    assert "243" in rows[0].progress
    assert all(r.name.startswith("BAK1Save") for r in rows)


def test_the_rotation_the_game_loads_is_marked_and_the_others_are_not(tmp_path):
    from aksave.catalog import Catalog
    paths = _folder(tmp_path, {
        "BAK1Save0x0.sgd": (ALL[:40], 184101.0),   # most playtime -> current
        "BAK1Save0x1.sgd": (ALL[:40], 183754.0),
        "BAK1Save0x2.sgd": (ALL[:40], 172036.0),
    })
    rows = app.save_rows(paths, Catalog.load())
    assert [r.current for r in rows] == [True, False, False]
    assert "BAK1Save0x0.sgd" in app.save_row_text(rows[0])
    assert "current" in app.save_row_text(rows[0]).lower()
    assert "current" not in app.save_row_text(rows[1]).lower()


def test_current_is_decided_per_slot_not_across_the_whole_folder(tmp_path):
    """Every slot has its own current rotation. Marking only the highest
    playtime in the folder would leave slot 3 with nothing marked at all."""
    from aksave.catalog import Catalog
    paths = _folder(tmp_path, {
        "BAK1Save0x0.sgd": (ALL[:40], 184101.0),
        "BAK1Save2x0.sgd": (ALL[:20], 71786.0),
        "BAK1Save2x1.sgd": (ALL[:20], 71000.0),
    })
    by_name = {r.name: r for r in app.save_rows(paths, Catalog.load())}
    assert by_name["BAK1Save0x0.sgd"].current
    assert by_name["BAK1Save2x0.sgd"].current
    assert not by_name["BAK1Save2x1.sgd"].current


def test_a_save_that_cannot_be_edited_says_so_in_the_list(tmp_path):
    """Better to see "no collectibles yet" on the row than to pick it and get
    a dialog."""
    from aksave.catalog import Catalog
    paths = _folder(tmp_path, {
        "BAK1Save0x0.sgd": (ALL[:40], 184101.0),
        "BAK1Save1x1.sgd": ([], 15.0),
    })
    rows = {r.name: r for r in app.save_rows(paths, Catalog.load())}
    assert rows["BAK1Save0x0.sgd"].problem is None
    assert rows["BAK1Save1x1.sgd"].problem
    assert "collectible" in app.save_row_text(rows["BAK1Save1x1.sgd"]).lower()


def test_an_unreadable_file_is_listed_rather_than_dropped(tmp_path):
    """Dropping it silently would leave the user hunting for a file they can
    see in Explorer."""
    from aksave.catalog import Catalog
    _folder(tmp_path, {"BAK1Save0x0.sgd": (ALL[:40], 184101.0)})
    (tmp_path / "BAK1Save0x1.sgd").write_bytes(b"not a save")
    rows = {r.name: r for r in app.save_rows(sorted(tmp_path.glob("BAK1Save*.sgd")),
                                             Catalog.load())}
    assert rows["BAK1Save0x1.sgd"].problem
    assert not rows["BAK1Save0x1.sgd"].current


def test_rows_are_ordered_by_slot_then_by_how_current_they_are(tmp_path):
    from aksave.catalog import Catalog
    paths = _folder(tmp_path, {
        "BAK1Save2x0.sgd": (ALL[:20], 71000.0),
        "BAK1Save2x1.sgd": (ALL[:20], 71786.0),
        "BAK1Save0x0.sgd": (ALL[:40], 184101.0),
    })
    rows = app.save_rows(paths, Catalog.load())
    assert [r.name for r in rows] == ["BAK1Save0x0.sgd", "BAK1Save2x1.sgd",
                                      "BAK1Save2x0.sgd"]


# --- rotations we genuinely cannot tell apart ------------------------------
# Evidence from the acceptance test: three rotations installed with identical
# playtime, the edit written to the one with the newest mtime, and the game
# loaded a different one. So mtime is NOT the game's rule, and ranking on it
# presents a guess as a fact. Where playtime ties, say so.


def test_no_rotation_is_called_current_when_the_playtimes_tie(tmp_path):
    from aksave.catalog import Catalog
    paths = _folder(tmp_path, {
        "BAK1Save2x0.sgd": (ALL[:20], 71786.0),
        "BAK1Save2x1.sgd": (ALL[:20], 71786.0),
        "BAK1Save2x2.sgd": (ALL[:20], 71786.0),
    })
    rows = app.save_rows(paths, Catalog.load())
    assert not any(r.current for r in rows), \
        "mtime broke the tie and named a file the game does not load"
    assert all(r.ambiguous for r in rows)
    assert "cannot tell" in app.save_row_text(rows[0]).lower()


def test_a_clear_winner_is_still_marked_current(tmp_path):
    from aksave.catalog import Catalog
    paths = _folder(tmp_path, {
        "BAK1Save2x0.sgd": (ALL[:20], 71786.0),
        "BAK1Save2x1.sgd": (ALL[:20], 90000.0),
    })
    rows = {r.name: r for r in app.save_rows(paths, Catalog.load())}
    assert rows["BAK1Save2x1.sgd"].current
    assert not rows["BAK1Save2x1.sgd"].ambiguous
    assert not rows["BAK1Save2x0.sgd"].current


def test_only_the_tied_leaders_are_ambiguous(tmp_path):
    """A rotation that is plainly behind is not ambiguous, it is just old."""
    from aksave.catalog import Catalog
    paths = _folder(tmp_path, {
        "BAK1Save2x0.sgd": (ALL[:20], 90000.0),
        "BAK1Save2x1.sgd": (ALL[:20], 90000.0),
        "BAK1Save2x2.sgd": (ALL[:20], 10000.0),
    })
    rows = {r.name: r for r in app.save_rows(paths, Catalog.load())}
    assert rows["BAK1Save2x0.sgd"].ambiguous
    assert rows["BAK1Save2x1.sgd"].ambiguous
    assert not rows["BAK1Save2x2.sgd"].ambiguous


def test_a_lone_rotation_is_neither_ambiguous_nor_unmarked(tmp_path):
    from aksave.catalog import Catalog
    paths = _folder(tmp_path, {"BAK1Save1x1.sgd": (ALL[:20], 71786.0)})
    row = app.save_rows(paths, Catalog.load())[0]
    assert row.current and not row.ambiguous
