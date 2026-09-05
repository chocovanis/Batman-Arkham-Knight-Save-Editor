"""Tests that drive the assembled application.

Everything in `test_gui.py` checks a pure function or asserts on source text.
That is the wrong level for the code that actually writes to a save: `_write`
is the single function standing between a click and a real 51-hour
playthrough, and it runs three rails, takes the backup, does the
tmp-plus-os.replace and re-verifies — none of which any pure function can
reach.

Every defect these tests were written for is a behaviour of the assembled app
rather than of any one function, which is why a full audit of the individual
modules did not find them. So these construct a real `EditorApp` against a
real Tk root and a real save folder on disk.

Skipped automatically where there is no display, so the suite still runs on a
headless machine.
"""

import gc
import time

import pytest

from aksave.backup import create_backup, list_backups
from aksave.catalog import Catalog
from tests.test_sgd import make_save_with_flags

tk = pytest.importorskip("tkinter")

CAT = Catalog.load()
ALL = [i.flag for i in CAT.items]


class Recorder:
    """Stands in for tkinter.messagebox so nothing blocks on a modal.

    `answers` supplies the return value per dialog kind, so a test can decide
    what the user clicked. Anything unset returns None, which is falsy - the
    same as clicking No.
    """

    def __init__(self, answers=None):
        self.calls = []
        self.answers = dict(answers or {})

    def _record(self, kind):
        def show(title, message, **kw):
            self.calls.append((kind, title, message))
            return self.answers.get(kind)
        return show

    def __getattr__(self, name):
        return self._record(name)

    @property
    def titles(self):
        return [t for _, t, _ in self.calls]

    @property
    def text(self):
        return "\n".join(m for _, _, m in self.calls)


@pytest.fixture
def root():
    """A withdrawn Tk root, one per test so no state leaks between them.

    Retried, because creating roots in quick succession fails intermittently —
    about one run in three, one of them came back "couldn't read file
    .../tcl8.6/auto.tcl: no such file or directory" while the others were
    fine. Skipping on that would quietly drop a test that guards the write
    path, which is the opposite of what this file is for. A genuine absence
    of a display still skips, after three tries.
    """
    last = None
    for attempt in range(3):
        try:
            r = tk.Tk()
            break
        except tk.TclError as exc:
            last = exc
            time.sleep(0.25)
    else:
        pytest.skip(f"no Tk display available: {last}")
    r.withdraw()
    yield r
    gc.collect()                # finalise Tk objects while Tcl is still up
    try:
        r.destroy()
    except tk.TclError:
        pass
    gc.collect()


@pytest.fixture
def slot(tmp_path):
    """A save folder shaped like a real one.

    Three rotations with DISTINCT playtimes, because that is what the game
    writes: it plays on and saves again, so each rotation is further along
    than the last. Equal playtimes are the pathological case and get their
    own fixture (`tied`) — building the ordinary fixture that way meant every
    test here was unknowingly exercising the ambiguous path.
    """
    import struct
    d = tmp_path / "remote"
    d.mkdir()
    for name, playtime in (("BAK1Save0x0.sgd", 90_000.0),      # current
                           ("BAK1Save0x1.sgd", 80_000.0),
                           ("BAK1Save0x2.sgd", 70_000.0)):
        raw = bytearray(make_save_with_flags(ALL[:40]))
        struct.pack_into("<f", raw, 0x69, playtime)
        (d / name).write_bytes(bytes(raw))
    (d / "profile.bin").write_bytes(b"profile-original")
    (d / "LBGameCache.dat").write_bytes(b"cache-original")
    return d


@pytest.fixture
def make_app(root, monkeypatch):
    """Build an EditorApp against a save folder, and dispose of it properly.

    Disposal is not optional here. `EditorApp` holds `tk.StringVar` and
    `tk.BooleanVar`, and `Variable.__del__` calls into Tcl. Left to chance,
    those are collected whenever the next GC happens to run — which, in this
    file, can be on a worker thread inside a LATER test, because the write
    path runs off the UI thread. Tcl aborts the whole process when that
    happens: `Windows fatal exception: code 0x80000003`, with the traceback
    pointing at an innocent `json.loads` in `Catalog.load`.

    So every app built here is finalised on the main thread, while its
    interpreter is still alive, before the test ends.
    """
    import ak_riddler_editor as mod

    built = []

    def build(slot_dir):
        monkeypatch.setattr(mod, "find_save_dirs", lambda: [slot_dir])
        box = Recorder()
        monkeypatch.setattr(mod, "messagebox", box)
        app = mod.EditorApp(root)
        app.box = box
        app.slot_dir = slot_dir
        built.append(app)
        return app

    yield build

    for app in built:
        app.theme = app.leave_one = None
        app.activity.on_failure = None
        app.activity.buttons = []
    built.clear()
    gc.collect()


@pytest.fixture
def gui(make_app, slot):
    return make_app(slot)


def pump(app, timeout=20.0):
    """Run the event loop until the worker thread has finished.

    Activity drains its queue from a `root.after` callback, which only fires
    while events are being processed, and no mainloop is running here.
    """
    deadline = time.monotonic() + timeout
    app.root.update()
    while app.activity.busy and time.monotonic() < deadline:
        app.root.update()
        time.sleep(0.005)
    for _ in range(6):                      # let the final callbacks land
        app.root.update()
        time.sleep(0.005)
    assert not app.activity.busy, "worker did not finish"


def log_text(app):
    return app.log_widget.get("1.0", "end")


# --- the write path, end to end --------------------------------------------


def test_collect_everything_writes_the_save_and_backs_it_up_first(gui):
    before = (gui.slot_dir / "BAK1Save0x0.sgd").read_bytes()
    gui.on_collect_all()
    pump(gui)

    from aksave.editor import SaveEditor
    after = SaveEditor(gui.save_path.read_bytes(), CAT)
    assert after.challenge_count == 242
    assert gui.save_path.read_bytes() != before

    backups = list_backups(gui.backup_root())
    assert len(backups) == 1, "a write must be preceded by exactly one backup"
    assert (backups[0].path / gui.save_path.name).read_bytes() == before


def test_a_write_never_touches_profile_bin_or_the_game_cache(gui):
    gui.on_collect_all()
    pump(gui)
    assert (gui.slot_dir / "profile.bin").read_bytes() == b"profile-original"
    assert (gui.slot_dir / "LBGameCache.dat").read_bytes() == b"cache-original"


# --- the defect that could commit an edit the user did not ask for ---------


def test_a_second_collect_everything_click_does_not_rewrite_the_save(gui):
    """`collect_all` returns [] once there is nothing left to add, but the GUI
    called `_write` regardless: a full backup, an os.replace over the live
    save, and a log reading "Wrote 2,428,928 bytes / Verified: 242/243" for a
    click that changed nothing."""
    gui.on_collect_all()
    pump(gui)
    stamp = gui.save_path.stat().st_mtime_ns
    backups_before = len(list_backups(gui.backup_root()))

    gui.on_collect_all()
    pump(gui)

    assert gui.save_path.stat().st_mtime_ns == stamp, \
        "the live save was rewritten for a no-op click"
    assert len(list_backups(gui.backup_root())) == backups_before, \
        "a no-op click took another full-folder backup"
    assert "Wrote" not in log_text(gui).split("Adding 0 flags")[-1]


def test_a_failed_write_that_cannot_be_re_read_closes_the_save(gui, monkeypatch):
    """The worst path found in the audit.

    `work()` mutates the in-memory editor before `_write` runs any rail, and
    the recovery is `reload()`. When the re-read ALSO fails, `load()`
    deliberately keeps the previous editor — correct for Open Save…, wrong
    here, because what it keeps is the abandoned mutation. The window then
    renders the last good state while memory holds 242/243, and the next
    click serialises it: 302 flags the user never asked for, logged as
    "Adding 0 flags".
    """
    import ak_riddler_editor as mod

    def explode(*a, **kw):
        raise OSError("the save folder went away")

    monkeypatch.setattr(mod.os, "replace", explode)
    monkeypatch.setattr(mod.Path, "read_bytes", explode)

    gui.on_collect_all()
    pump(gui)

    assert gui.editor is None, \
        "an editor we could not verify against disk is still committable"
    assert gui.save_path is None


def test_after_that_failure_nothing_can_be_written(gui, monkeypatch):
    """The second half of the same defect: the click that used to commit it.

    Only `os.replace` is broken, and only for the first call — the failure has
    to end so the follow-up click happens under ordinary conditions, which is
    exactly how a transient lock (antivirus, Steam Cloud, OneDrive) behaves.
    """
    import ak_riddler_editor as mod

    real_replace, broken = mod.os.replace, [True]

    def flaky(*a, **kw):
        if broken[0]:
            broken[0] = False
            raise OSError("the file was locked")
        return real_replace(*a, **kw)

    from aksave.editor import SaveEditor

    original = (gui.slot_dir / "BAK1Save0x0.sgd").read_bytes()
    monkeypatch.setattr(mod.os, "replace", flaky)

    gui.on_collect_all()
    pump(gui)

    # Nothing reached disk, and - the part that used to be false - memory is
    # not left ahead of it. That gap was the whole defect: the in-memory
    # editor held 242/243 while the file held 40/243, so a later click on one
    # trophy added nothing, logged "Adding 0 flags", and serialised the lot.
    on_disk = gui.slot_dir / "BAK1Save0x0.sgd"
    assert on_disk.read_bytes() == original
    assert gui.editor.challenge_count == \
        SaveEditor(on_disk.read_bytes(), CAT).challenge_count, \
        "the in-memory editor is ahead of the file it would be written to"

    # A retry is now ordinary work, reported honestly, not a stale commit.
    gui.on_collect_all()
    pump(gui)
    assert "Adding 0 flags" not in log_text(gui)
    assert SaveEditor(on_disk.read_bytes(), CAT).challenge_count == 242


# --- restore ---------------------------------------------------------------


def test_one_unreadable_backup_does_not_hide_the_others(gui):
    """`list_backups` had no per-entry guard, and it runs on the UI thread
    outside Activity — so in the --noconsole build one truncated manifest
    made the Restore button a silent no-op with no dialog and no log line."""
    good = create_backup(gui.slot_dir, gui.backup_root(), label="123/243")
    bad = create_backup(gui.slot_dir, gui.backup_root(), label="242/243")
    text = (bad / "manifest.json").read_text()
    (bad / "manifest.json").write_text(text[: len(text) // 2])

    entries = list_backups(gui.backup_root())
    assert [e.path for e in entries] == [good]

    gui.on_restore()                       # must not be a silent no-op
    gui.root.update()
    assert gui.box.calls or gui.root.winfo_children()


def test_restore_refuses_while_the_game_is_running(gui, monkeypatch):
    """Restore is the recovery path and had no rails at all. Restoring under a
    running game loses the restore when the game exits — the same hazard the
    write path refuses, on the path a user reaches only on a bad day."""
    import ak_riddler_editor as mod

    backup = create_backup(gui.slot_dir, gui.backup_root(), label="123/243")
    (gui.slot_dir / "BAK1Save0x0.sgd").write_bytes(b"x" * 2428928)
    monkeypatch.setattr(mod, "game_is_running", lambda: True)

    gui.restore_from(backup)
    pump(gui)

    assert (gui.slot_dir / "BAK1Save0x0.sgd").read_bytes() == b"x" * 2428928
    assert "running" in log_text(gui).lower()


def test_restore_takes_its_own_backup_before_rolling_the_folder_back(gui):
    """Restore overwrites every slot in the folder plus profile.bin. Without a
    backup of the current state it is a one-way trip, and the state it
    discards may be the one the user actually wanted."""
    backup = create_backup(gui.slot_dir, gui.backup_root(), label="before")
    gui.on_collect_all()
    pump(gui)
    edited = gui.save_path.read_bytes()

    gui.restore_from(backup)
    pump(gui)

    assert gui.save_path.read_bytes() != edited, "the restore did not happen"
    recovered = [b for b in list_backups(gui.backup_root())
                 if (b.path / gui.save_path.name).read_bytes() == edited]
    assert recovered, "the state the restore discarded was not backed up first"


# --- what a selection in the tree actually means ---------------------------


def region_row(gui, name):
    return next(i for i in gui.tree.get_children("")
                if gui.tree.item(i, "text").startswith(name))


def test_selecting_a_region_row_collects_that_whole_region(gui):
    """The tree is grouped by region precisely to invite region-at-a-time
    collection, but a region row's iid is a Tk-assigned "I001" that
    `catalog.known` rejects — so selecting "Bleake Island  0/66" and clicking
    Collect Selected answered "Nothing selected"."""
    row = region_row(gui, "Bleake Island")
    gui.tree.selection_set(row)

    flags = gui._selected_flags()
    assert len(flags) == sum(1 for i in CAT.items if i.region == "CityZ")
    assert all(CAT.item(f).region == "CityZ" for f in flags)

    gui.on_collect_selected()
    pump(gui)
    assert "Nothing selected" not in gui.box.titles
    assert all(i.flag in gui.editor.collected
               for i in CAT.items if i.region == "CityZ")


def test_a_mixed_selection_does_not_silently_drop_the_group_row(gui):
    """Worse than a refusal: selecting a region row plus two trophies used to
    collect only the two, discarding the row covering 66 collectibles, and log
    "Adding 2 flags" with nothing to say the rest had been dropped."""
    row = region_row(gui, "Bleake Island")
    loose = [i.flag for i in CAT.items if i.region == "CityX"][:2]
    gui.tree.selection_set((row, *loose))

    flags = gui._selected_flags()
    assert set(loose) <= set(flags)
    assert len(flags) > len(loose) + 1


def test_selecting_an_area_the_save_has_never_reached_explains_itself(make_app,
                                                                     tmp_path):
    """It would be refused by `_check` anyway — but only after the click, as a
    RailError with a traceback in the log and no dialog."""
    import struct
    d = tmp_path / "remote"
    d.mkdir()
    for name, playtime in (("BAK1Save0x0.sgd", 90_000.0),
                           ("BAK1Save0x1.sgd", 80_000.0),
                           ("BAK1Save0x2.sgd", 70_000.0)):
        raw = bytearray(make_save_with_flags(ALL[:40], skip_regions=("HideOut",)))
        struct.pack_into("<f", raw, 0x69, playtime)
        (d / name).write_bytes(bytes(raw))
    app = make_app(d)
    box = app.box

    row = next(i for i in app.tree.get_children("")
               if "Arkham Knight HQ" in app.tree.item(i, "text"))
    assert "not editable" in app.tree.item(row, "text")
    app.tree.selection_set(row)
    app.on_collect_selected()
    app.root.update()

    assert "Not editable yet" in box.titles
    assert "Arkham Knight HQ" in box.text
    assert "Traceback" not in app.log_widget.get("1.0", "end")


def test_a_leaf_in_an_unreachable_area_says_so_on_its_own_row(make_app, tmp_path):
    """Once the region is expanded, its "(not editable)" parent is off screen."""
    d = tmp_path / "remote"
    d.mkdir()
    (d / "BAK1Save0x0.sgd").write_bytes(
        make_save_with_flags(ALL[:40], skip_regions=("HideOut",)))
    app = make_app(d)

    flag = next(i.flag for i in CAT.items if i.region == "HideOut")
    assert app.tree.item(flag, "values")[0] == "not editable"
    other = next(i.flag for i in CAT.items
                 if i.region == "CityZ" and i.flag not in app.editor.collected)
    assert app.tree.item(other, "values")[0] == "—"


# --- a failure has to leave the log ----------------------------------------


def test_a_failed_write_raises_a_dialog_and_does_not_sign_off_as_a_success(gui,
                                                                          monkeypatch):
    """`on_error=reload` succeeds, so the last line in the log used to read
    "Loaded BAK1Save0x0.sgd (Steam, 1h00m, 40/243)" — a failed write signing
    off as a success, with no dialog anywhere."""
    import ak_riddler_editor as mod

    monkeypatch.setattr(mod, "game_is_running", lambda: True)
    gui.on_collect_all()
    pump(gui)

    assert gui.box.calls, "a failure has to reach the window, not just the log"
    kind, title, message = gui.box.calls[-1]
    assert kind == "showinfo", "a rail refusing is not a crash"
    assert "running" in message
    assert "Traceback" not in log_text(gui)


# --- the rotation trap, found by the acceptance test -----------------------
# The tool warned that BAK1Save2x0.sgd was not the rotation the game loads,
# then left the button live. The click came twelve seconds later, the edit
# landed on a file the game never read, and the result looked exactly like
# the tool being broken.


@pytest.fixture
def stale(tmp_path):
    """A slot whose current rotation is NOT the one sorted first."""
    import struct
    d = tmp_path / "remote"
    d.mkdir()
    for name, playtime in (("BAK1Save0x0.sgd", 40_000.0),      # oldest
                           ("BAK1Save0x1.sgd", 50_000.0),
                           ("BAK1Save0x2.sgd", 90_000.0)):     # current
        raw = bytearray(make_save_with_flags(ALL[:40]))
        struct.pack_into("<f", raw, 0x69, playtime)
        (d / name).write_bytes(bytes(raw))
    return d


def test_editing_a_stale_rotation_asks_before_writing_anything(make_app, stale):
    app = make_app(stale)
    app.box.answers["askyesno"] = True          # "yes, open the current one"
    before = (stale / "BAK1Save0x0.sgd").read_bytes()

    app.load(stale / "BAK1Save0x0.sgd")
    app.on_collect_all()
    pump(app)

    assert any(k == "askyesno" for k, _, _ in app.box.calls), \
        "the write went ahead with only a log line to object"
    assert (stale / "BAK1Save0x0.sgd").read_bytes() == before
    assert app.save_path.name == "BAK1Save0x2.sgd", \
        "answering yes should leave the current rotation open"


def test_the_confirmation_names_both_files_so_the_choice_is_obvious(make_app, stale):
    app = make_app(stale)
    app.load(stale / "BAK1Save0x0.sgd")
    app.on_collect_all()
    pump(app)

    message = next(m for k, _, m in app.box.calls if k == "askyesno")
    assert "BAK1Save0x0.sgd" in message
    assert "BAK1Save0x2.sgd" in message


def test_editing_a_stale_rotation_on_purpose_is_still_allowed(make_app, stale):
    """A refusal would be wrong: editing an older rotation deliberately is
    legitimate, and the tool should not know better than the user."""
    app = make_app(stale)
    app.box.answers["askyesno"] = False         # "no, edit this one anyway"
    before = (stale / "BAK1Save0x0.sgd").read_bytes()

    app.load(stale / "BAK1Save0x0.sgd")
    app.on_collect_all()
    pump(app)

    assert (stale / "BAK1Save0x0.sgd").read_bytes() != before
    assert app.save_path.name == "BAK1Save0x0.sgd"


def test_opening_the_current_rotation_asks_nothing(make_app, stale):
    app = make_app(stale)
    app.load(stale / "BAK1Save0x2.sgd")
    app.on_collect_all()
    pump(app)

    assert not any(k == "askyesno" for k, _, _ in app.box.calls)
    from aksave.editor import SaveEditor
    assert SaveEditor((stale / "BAK1Save0x2.sgd").read_bytes(),
                      CAT).challenge_count == 242


@pytest.fixture
def tied(tmp_path):
    """Three rotations with identical playtime — your slot 3 after install."""
    import struct
    d = tmp_path / "remote"
    d.mkdir()
    for name in ("BAK1Save2x0.sgd", "BAK1Save2x1.sgd", "BAK1Save2x2.sgd"):
        raw = bytearray(make_save_with_flags(ALL[:40]))
        struct.pack_into("<f", raw, 0x69, 71786.0)
        (d / name).write_bytes(bytes(raw))
    return d


def test_identical_rotations_warn_that_we_cannot_tell_which_one_loads(make_app, tied):
    """The acceptance-test failure, encoded.

    Three rotations, same playtime, edit written to one of them, game loaded
    another. Ranking on mtime named a file we had no reason to believe in, so
    now nothing is named and the user is told to edit all of them.
    """
    app = make_app(tied)
    app.box.answers["askyesno"] = False        # "no, go ahead anyway"
    app.load(tied / "BAK1Save2x0.sgd")
    app.on_collect_all()
    pump(app)

    asked = [m for k, _, m in app.box.calls if k == "askyesno"]
    assert asked, "a tie has to be raised before the write, not after"
    assert "same playtime" in asked[0].lower()
    assert "all" in asked[0].lower()
    assert "BAK1Save2x1.sgd" in asked[0] and "BAK1Save2x2.sgd" in asked[0]


def test_a_tie_does_not_falsely_name_one_rotation_as_newest(make_app, tied):
    """The old warning said "open BAK1Save2x2.sgd instead", picked by mtime.
    That was a guess presented as a fact, and it was wrong."""
    app = make_app(tied)
    app.load(tied / "BAK1Save2x0.sgd")
    assert app.newest_rotation is None
    assert "not the newest rotation" not in log_text(app)


def test_the_status_line_shows_the_tie(make_app, tied):
    app = make_app(tied)
    app.load(tied / "BAK1Save2x0.sgd")
    assert "cannot tell" in app.status.cget("text").lower()


def test_distinct_playtimes_still_produce_the_ordinary_warning(make_app, stale):
    app = make_app(stale)
    app.load(stale / "BAK1Save0x0.sgd")
    assert app.newest_rotation is not None
    assert not app.tied_rotations
