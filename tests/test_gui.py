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


def test_font_scaling_is_not_confined_to_the_fallback_theme():
    """The scaling once lived inside the `except ImportError` branch that runs
    only when sv_ttk is absent — so it did nothing in the packaged build, which
    ships sv_ttk. Glyphs measured 10px on a 4K screen because of it.

    Assert structurally that the sizing runs unconditionally: the font block
    must sit at function-body indentation, not nested inside the try/except.
    """
    import inspect
    import textwrap

    src = textwrap.dedent(inspect.getsource(app.apply_theme))
    body = src.split('"""', 2)[-1]
    sizing = [ln for ln in body.splitlines() if "nametofont" in ln]
    assert sizing, "the named-font sizing loop has gone missing"
    # 8 spaces or more would mean it is inside the try/except suite.
    assert all(len(ln) - len(ln.lstrip()) <= 12 for ln in sizing)
