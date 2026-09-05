"""Batman: Arkham Knight — Riddler Save Editor."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont

PALETTES = {
    "light": dict(bg="#f5f5f7", surface="#ffffff", text="#1c1c1e",
                  muted="#6b6b70", accent="#0a6cff", border="#d8d8dc",
                  ok="#1a7f37", warn="#9a6700", error="#b42318"),
    "dark":  dict(bg="#16181c", surface="#1f2228", text="#e8e8ea",
                  muted="#9a9aa2", accent="#4c9aff", border="#2f333a",
                  ok="#3fb950", warn="#d29922", error="#f85149"),
}


def detect_system_theme() -> str:
    """Windows exposes the app theme in the registry; default to light."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return "light" if value else "dark"
    except Exception:
        return "light"


UI_FONT, MONO_FONT = "Segoe UI", "Consolas"
BASE_PT, HEADING_PT, MONO_PT, ROW_PX = 10, 13, 9, 24


def ui_font_scale(screen_w: int) -> float:
    """How much to enlarge UI type for a display of this width.

    Tk already converts points to pixels through the OS DPI setting, which
    keeps text at the system's idea of "normal". Normal is not the same as
    right here: the window is sized as a fraction of the screen, so on a large
    panel it is far wider than the layout needs and normal-sized text floats in
    it looking lost. Grow the type with the display, capped so it never becomes
    cartoonish, and floored at 1.0 so ordinary 1080p screens are untouched.
    """
    return min(1.4, max(1.0, screen_w / 1920))


def apply_theme(root: tk.Tk, mode: str, scale: float = 1.0) -> dict:
    """Apply a palette and size the type for this display.

    Hand-built on ttk's `clam`, deliberately, and with no optional theme
    engine behind a try/except. sv_ttk was measured at 224 ms per resize
    frame against clam's 39 ms on the same window — 4.5 fps versus 26 —
    because its widget elements are images that get rescaled on every
    redraw. The cost is independent of what the tree holds (emptying it
    changed nothing), so it is the theme, not our data. Dragging a window
    edge is the single most common thing a user does to a window, and it
    is not worth trading for rounded corners.

    Dropping it also removes the last runtime dependency, which is how the
    other editors in this family are built.
    """
    palette = PALETTES[mode]
    pt = lambda size: max(1, round(size * scale))
    px = lambda n: round(n * scale)

    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(".", background=palette["bg"], foreground=palette["text"],
                    fieldbackground=palette["surface"], borderwidth=0,
                    font=(UI_FONT, pt(BASE_PT)))
    style.configure("TFrame", background=palette["bg"])
    style.configure("TLabel", background=palette["bg"], foreground=palette["text"],
                    font=(UI_FONT, pt(BASE_PT)))
    style.configure("Muted.TLabel", foreground=palette["muted"],
                    font=(UI_FONT, pt(BASE_PT)))
    style.configure("Heading.TLabel", font=(UI_FONT + " Semibold", pt(HEADING_PT)))

    style.configure("TButton", padding=(px(14), px(7)), background=palette["surface"],
                    bordercolor=palette["border"], lightcolor=palette["surface"],
                    darkcolor=palette["surface"], font=(UI_FONT, pt(BASE_PT)))
    style.map("TButton",
              background=[("active", palette["accent"]), ("disabled", palette["bg"])],
              foreground=[("active", "#ffffff"), ("disabled", palette["muted"])])
    style.configure("Accent.TButton", background=palette["accent"], foreground="#ffffff",
                    lightcolor=palette["accent"], darkcolor=palette["accent"])
    style.map("Accent.TButton",
              background=[("active", palette["accent"]), ("disabled", palette["bg"])],
              foreground=[("disabled", palette["muted"])])

    style.configure("TCheckbutton", background=palette["bg"], foreground=palette["text"],
                    font=(UI_FONT, pt(BASE_PT)), indicatorsize=px(14),
                    padding=(0, px(4)))
    style.map("TCheckbutton",
              background=[("active", palette["bg"])],
              indicatorcolor=[("selected", palette["accent"]),
                              ("!selected", palette["surface"])])

    style.configure("TScrollbar", background=palette["surface"],
                    troughcolor=palette["bg"], arrowcolor=palette["text"],
                    bordercolor=palette["bg"], borderwidth=0)

    # clam draws a Combobox field with its own 3-D border, which shows up as a
    # bright rectangle around the control on a dark palette. Flatten it, and
    # map the readonly state explicitly or the selected value renders as dark
    # grey on a dark field.
    style.configure("TCombobox", arrowcolor=palette["text"],
                    bordercolor=palette["border"], lightcolor=palette["surface"],
                    darkcolor=palette["surface"], fieldbackground=palette["surface"],
                    background=palette["surface"], foreground=palette["text"],
                    arrowsize=px(14), padding=(px(6), px(4)),
                    font=(UI_FONT, pt(BASE_PT)))
    style.map("TCombobox",
              fieldbackground=[("readonly", palette["surface"])],
              background=[("readonly", palette["surface"])],
              foreground=[("readonly", palette["text"])],
              bordercolor=[("focus", palette["accent"])],
              lightcolor=[("focus", palette["surface"])],
              darkcolor=[("focus", palette["surface"])],
              selectbackground=[("readonly", palette["surface"])],
              selectforeground=[("readonly", palette["text"])])
    # The dropdown list is a classic tk Listbox, reachable only this way.
    root.option_add("*TCombobox*Listbox.background", palette["surface"])
    root.option_add("*TCombobox*Listbox.foreground", palette["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", palette["accent"])
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    # Row height must come from the font's own metrics, not a scaled constant.
    # A fixed multiplier is a guess about how tall the type renders, and when
    # it guesses low the rows clip their own descenders — "Miagani", "Stagg"
    # and "HQ" all lost their tails at rowheight = 24 * 1.4.
    body = tkfont.Font(root=root, family=UI_FONT, size=pt(BASE_PT))
    row_h = max(px(ROW_PX), body.metrics("linespace") + px(8))
    style.configure("Treeview", background=palette["surface"],
                    fieldbackground=palette["surface"], foreground=palette["text"],
                    rowheight=row_h, borderwidth=0, font=(UI_FONT, pt(BASE_PT)))
    style.map("Treeview",
              background=[("selected", palette["accent"])],
              foreground=[("selected", "#ffffff")])
    style.configure("Treeview.Heading", background=palette["bg"],
                    foreground=palette["text"], relief="flat", borderwidth=0,
                    padding=(px(4), px(6)),
                    font=(UI_FONT + " Semibold", pt(BASE_PT)))
    style.map("Treeview.Heading", background=[("active", palette["bg"])])

    # Named fonts too: classic widgets and dialogs use these directly.
    for name, family, size in (
        ("TkDefaultFont", UI_FONT, BASE_PT),
        ("TkTextFont", UI_FONT, BASE_PT),
        ("TkMenuFont", UI_FONT, BASE_PT),
        ("TkHeadingFont", UI_FONT, BASE_PT),
        ("TkTooltipFont", UI_FONT, BASE_PT),
        ("TkFixedFont", MONO_FONT, MONO_PT),
    ):
        try:
            tkfont.nametofont(name, root=root).configure(family=family, size=pt(size))
        except Exception:
            pass

    root.configure(background=palette["bg"])
    return palette


import queue
import threading
import traceback
from datetime import datetime


class Activity:
    """Runs work off the UI thread and reports it through a log panel.

    tkinter widgets may only be touched from the thread that created them, so
    workers communicate exclusively through a queue that the UI drains.
    """

    def __init__(self, root: tk.Tk, log_widget: tk.Text, buttons: list[ttk.Widget]):
        self.root = root
        self.log_widget = log_widget
        self.buttons = buttons
        self.queue: queue.Queue = queue.Queue()
        self.busy = False
        # Set by the app: how a failure is put in front of the user. Kept as a
        # hook rather than a direct messagebox call so this class stays free of
        # tkinter dialogs and can be driven from a test.
        self.on_failure = None
        self.root.after(50, self._drain)

    def log(self, message: str) -> None:
        self.queue.put(("log", message))

    def run(self, description: str, fn, on_done=None, on_error=None) -> None:
        """Run fn() on a worker thread. Ignored if something is already running.

        on_error is the failure-path counterpart of on_done: it runs on the UI
        thread, in exactly the place on_done would have run, so callers can put
        their own state back in sync after a write that raised partway through.
        It is called with no arguments, because there is no result to hand it.
        """
        if self.busy:
            self.log(f"ignored: {description} (still working)")
            return
        self.busy = True
        self._set_buttons(False)
        self.root.configure(cursor="watch")

        def worker():
            try:
                result = fn(self.log)
                self.queue.put(("done", (on_done, result, False)))
            except Exception as exc:
                # The traceback has to be captured here, while the exception is
                # still active; whether it is worth showing is decided on the
                # UI thread, where the dialog is.
                self.queue.put(("fail", (exc, traceback.format_exc().strip())))
                self.queue.put(("done", (on_error, None, True)))

        threading.Thread(target=worker, daemon=True).start()

    def _set_buttons(self, enabled: bool) -> None:
        for b in self.buttons:
            b.state(["!disabled"] if enabled else ["disabled"])

    def apply_palette(self, palette: dict) -> None:
        """Recolour the log. tk.Text is a classic widget, so ttk theming misses
        it and it would otherwise keep the previous mode's colours."""
        self.log_widget.configure(background=palette["surface"],
                                  foreground=palette["text"],
                                  insertbackground=palette["text"])

    def _drain(self) -> None:
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "log":
                    stamp = datetime.now().strftime("%H:%M:%S")
                    self.log_widget.configure(state="normal")
                    self.log_widget.insert("end", f"{stamp}  {payload}\n")
                    self.log_widget.see("end")
                    self.log_widget.configure(state="disabled")
                elif kind == "fail":
                    # A failure has to leave the window, not just the log. The
                    # log is nine lines and `on_error=reload` writes three more
                    # after this, so an unaccompanied FAILED line ended up
                    # scrolled away under "Loaded ... 215/243" — a failed write
                    # signing off as a success.
                    exc, tb = payload
                    _, _, message, show_tb = failure_dialog(exc)
                    self.queue.put(("log", f"FAILED: {exc}"))
                    if show_tb:
                        self.queue.put(("log", tb))
                    if self.on_failure:
                        try:
                            self.on_failure(exc)
                        except Exception as hook_exc:
                            self.queue.put(("log", f"FAILED (dialog): {hook_exc}"))
                elif kind == "done":
                    # Cleared in every path, so a crashed worker cannot leave
                    # the UI permanently locked.
                    self.busy = False
                    self._set_buttons(True)
                    self.root.configure(cursor="")
                    callback, result, failed = payload
                    if callback:
                        # A callback that raises must not kill the drain loop,
                        # which is the only thing that ever clears `busy`.
                        try:
                            callback() if failed else callback(result)
                        except Exception as exc:
                            self.queue.put(("log", f"FAILED (callback): {exc}"))
        except queue.Empty:
            pass
        self.root.after(50, self._drain)


import os
import subprocess
import sys
from pathlib import Path
from tkinter import filedialog, messagebox

from aksave.backup import (BackupError, backup_contents, create_backup,
                           list_backups, restore_backup)
from aksave.catalog import Catalog
from aksave.editor import RailError as EditorRailError
from aksave.editor import SaveEditor, skipped_note, where_to_find
from aksave.sgd import SgdFile
from aksave.rails import RailError as RailsRailError
from aksave.rails import (SLOT_RE, check_slot_complete, check_writable_target,
                          game_is_running, slot_files)
from aksave.sgd import SgdError

TYPE_LABELS = {"Pickup": "Riddler Trophies", "Riddler": "Riddles",
               "Bomb": "Bomb Rioters", "MilitiaShield": "Breakables",
               "InsectCrate": "Breakables", "JackInTheBox": "Breakables",
               "MiniDrone": "Breakables"}


# Window sizing follows the same rule as the other editors in this family: a
# proportion of the screen with a floor, centred, plus a minsize. Proportional
# rather than fixed, because a hard-coded geometry is wrong on every display
# that is not the author's — the 980x760 this started with left the layout
# wanting 996px on a 4K panel and cut the Status column off the right edge.
SCREEN_FRACTION_W = 0.47
SCREEN_FRACTION_H = 0.75
FLOOR_W, FLOOR_H = 1000, 780      # never smaller than the content needs
MIN_W, MIN_H = 900, 680           # user cannot drag below this


def window_geometry(screen_w: int, screen_h: int) -> tuple[int, int, int, int]:
    """Return (width, height, x, y) for a window on a screen of this size.

    Pure, so it can be checked against the displays this machine does not have
    — which is the whole point, since the bug it replaces only ever showed up
    on somebody else's monitor.
    """
    win_w = max(FLOOR_W, int(screen_w * SCREEN_FRACTION_W))
    win_h = max(FLOOR_H, int(screen_h * SCREEN_FRACTION_H))
    # Never bigger than the screen itself: on a 1366x768 laptop panel the
    # floors above would otherwise push the action buttons off the bottom.
    win_w = min(win_w, max(1, screen_w - 40))
    win_h = min(win_h, max(1, screen_h - 80))
    return win_w, win_h, max(0, (screen_w - win_w) // 2), max(0, (screen_h - win_h) // 2)


# The checkbox is the last thing the user reads before clicking, and the only
# control that decides whether the save ends at 242 or 243, so it names the
# island. It deliberately does NOT name a number: three schemes number that one
# warehouse and they disagree, so an index here would invite the wrong lookup.
# The exact building goes in the log, from aksave.editor.where_to_find.
# A tk.Checkbutton does not wrap, so this has to stay one window-width line.
LEAVE_ONE_LABEL = ("Leave one Bleake Island trophy uncollected, so the "
                   "achievement still unlocks when you pick it up in game")


class Refused(RuntimeError):
    """A rail declined to act. Nothing was written."""


def failure_dialog(exc: BaseException) -> tuple[str, str, str, bool]:
    """How to report an operation that failed: (kind, title, message, traceback).

    Three separate defects came out of not making this distinction. A rail
    refusing is not a crash, and its message is already written for the
    player — printing a traceback under it pushed the one useful line out of
    the nine-line log panel. A locked file is the commonest real failure and
    `[WinError 5] Access is denied` on its own is not something anyone can
    act on. And nothing ever raised a dialog at all, so a failed write ended
    with `reload()` logging "Loaded ... 215/243" and looking like a success.
    """
    if isinstance(exc, (Refused, EditorRailError, RailsRailError,
                        BackupError, SgdError)):
        return "info", "Nothing was changed", str(exc), False

    if isinstance(exc, OSError):
        return "error", "The save could not be written", (
            f"{exc}\n\n"
            f"Usually this means another program is holding the file — the "
            f"game itself, Steam syncing, OneDrive, or an antivirus scan — or "
            f"that the folder is read-only.\n\n"
            f"Close the game and Steam completely, then try again. Your save "
            f"was backed up before the write; the activity log says where."
        ), False

    return "error", "Something went wrong", f"{type(exc).__name__}: {exc}", True


def restore_warning(names: list[str], slot_dir) -> str:
    """What a restore is about to overwrite, in the user's terms.

    Restore is the widest write the tool makes, and the only one that reaches
    outside the save being edited: it puts back every file the backup holds —
    every slot in the folder, `profile.bin` and `LBGameCache.dat` — because
    that is what a rollback means. The editor's whole promise is that it
    touches one slot and never those two files, so the one place it does
    something wider has to say so before it does it.
    """
    saves = [n for n in names if n.lower().endswith(".sgd")]
    others = [n for n in names if n not in saves]
    slots = sorted({slot_label(Path(n)) for n in saves})

    lines = [f"This puts back {len(names)} file(s), overwriting what is in",
             f"{slot_dir} right now:", ""]
    if slots:
        lines.append(f"    {', '.join(slots)}  ({len(saves)} save files)")
    if others:
        lines.append(f"    {', '.join(others)}")
    lines += ["",
              "That includes save slots you are not editing." if len(slots) > 1 else
              "That is the whole save folder, not just the file you have open.",
              "",
              "The current state will be backed up first, so this can be undone.",
              "",
              "Restore now?"]
    return "\n".join(lines)


def refusal_dialog(exc: BaseException) -> tuple[str, str, str]:
    """How to present a save that would not open: (kind, title, message).

    Two different things get called "cannot open" and they deserve different
    dialogs. A `RailError` from the editor means we read the save perfectly and
    are declining to edit it, for a reason the player can act on — that is
    information, and its message is already written for them. Anything else is
    a file we did not understand, which is an error and where the diagnostic
    text is the useful part.

    Getting this wrong is not cosmetic. Opening a clean new-game slot used to
    raise an error box titled "Cannot read save" reading "no world-state store
    holding collectibles was found": a sentence about our parser, under a
    heading that was not true.
    """
    if isinstance(exc, EditorRailError):
        return "info", "This save cannot be edited yet", str(exc)
    return "error", "Cannot read this save", str(exc)


def slot_label(path) -> str:
    """The slot number the game's own save list shows for this filename.

    `BAK1Save0x*` is UI slot 1, and nobody knows that. The consequence of not
    saying it is severe and specific: a save folder can hold a 51-hour
    playthrough and a throwaway test save that differ by one digit in the
    middle of a filename, and the user has no way to tell from the window
    which one is loaded. The playtime helps; the slot number is the answer.

    (This reads the FILENAME. A save also carries its own slot index at byte
    0x65 and the game believes that instead, but the two only disagree for
    files copied in by hand, and the editor never moves a save between slots.)
    """
    m = SLOT_RE.match(Path(path).name)
    return f"Slot {int(m.group(1)) + 1}" if m else Path(path).name


def region_row_label(region_name: str, region: str, untracked: set) -> str:
    """The tree lists all six areas whether or not this save can hold them."""
    if region in untracked:
        return f"{region_name}   (not editable - never visited)"
    return region_name


def status_text(path, editor, newest_rotation) -> str:
    """The one line the user reads to confirm we are pointed at the right save.

    Pure, so the wording can be checked without a display — the widget tests
    cannot construct a Tk root, and this is the most consequential sentence in
    the window.
    """
    h = int(editor.playtime_seconds // 3600)
    m = int(editor.playtime_seconds % 3600 // 60)
    line = "  ·  ".join([
        slot_label(path),
        Path(path).name,
        editor.platform,
        f"{h}h{m:02d}m",
        f"{editor.challenge_count}/243 challenges "
        f"({editor.collected_count}/315 objects)",
    ])
    if editor.untracked_regions:
        names = ", ".join(sorted(editor.catalog.region_name(r)
                                 for r in editor.untracked_regions))
        line += f"  ·  {names} not editable"
    if newest_rotation is not None:
        line += ("  ·  not the newest rotation "
                 f"(the game loads {Path(newest_rotation).name})")
    return line


def find_save_dirs() -> list[Path]:
    """Steam cloud folder first; it is where the game actually reads from."""
    found = []
    for base in (Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) /
                 "Steam" / "userdata",):
        if base.is_dir():
            found += [p for p in base.glob("*/208650/remote") if p.is_dir()]
    docs = Path.home() / "Documents" / "WB Games" / "Batman Arkham Knight"
    found += [p for p in docs.glob("*/SaveData") if p.is_dir()]
    return found


class EditorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.catalog = Catalog.load()
        self.editor: SaveEditor | None = None
        self.save_path: Path | None = None
        # Set by load(): the newer sibling rotation the game would read instead,
        # or None when the opened file is the current one.
        self.newest_rotation: Path | None = None
        self.theme = tk.StringVar(value="auto")
        self.leave_one = tk.BooleanVar(value=True)

        root.title("Arkham Knight — Riddler Save Editor")
        win_w, win_h, x, y = window_geometry(root.winfo_screenwidth(),
                                             root.winfo_screenheight())
        root.geometry(f"{win_w}x{win_h}+{x}+{y}")
        root.minsize(min(MIN_W, win_w), min(MIN_H, win_h))

        self.ui_scale = ui_font_scale(root.winfo_screenwidth())
        self.palette = apply_theme(root, detect_system_theme(), self.ui_scale)

        self._build_header()
        self._build_tree()
        self._build_actions()
        self.activity = Activity(root, self.log_widget, self.buttons)
        self.activity.on_failure = self._show_failure
        self.activity.log("Ready. Choose a save file to begin.")
        self._autodetect()

    def _show_failure(self, exc: BaseException) -> None:
        kind, title, message, _ = failure_dialog(exc)
        (messagebox.showinfo if kind == "info" else messagebox.showerror)(
            title, message)

    # -- zone 1 ---------------------------------------------------------
    def _build_header(self):
        f = ttk.Frame(self.root, padding=(16, 14, 16, 8))
        f.pack(fill="x")
        ttk.Label(f, text="Riddler Save Editor", style="Heading.TLabel").pack(anchor="w")
        self.status = ttk.Label(f, text="No save loaded", style="Muted.TLabel")
        self.status.pack(anchor="w", pady=(2, 10))

        row = ttk.Frame(f)
        row.pack(fill="x")
        ttk.Button(row, text="Open Save…", command=self.on_open).pack(side="left")
        ttk.Label(row, text="  Theme ", style="Muted.TLabel").pack(side="left")
        box = ttk.Combobox(row, textvariable=self.theme, width=8, state="readonly",
                           values=["auto", "light", "dark"])
        # A Combobox draws its value through an entry element that ignores the
        # style font under sv_ttk, so it has to be set on the widget itself -
        # otherwise this is the one control still rendering at 10pt.
        box.configure(font=(UI_FONT, round(BASE_PT * self.ui_scale)))
        box.pack(side="left")
        box.bind("<<ComboboxSelected>>", self.on_theme)

    # -- zone 2 ---------------------------------------------------------
    def _build_tree(self):
        f = ttk.Frame(self.root, padding=(16, 0))
        f.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(f, columns=("state",), show="tree headings",
                                 selectmode="extended")
        self.tree.heading("#0", text="Collectible")
        self.tree.heading("state", text="Status")
        # Width measured from the widest value the column can actually hold,
        # in the font it will actually be drawn in. A fixed 110px was already
        # tight at 100% and cut "collected" clean off once the type scaled up.
        cell = tkfont.Font(root=self.root,
                           family=UI_FONT, size=round(BASE_PT * self.ui_scale))
        state_w = max(cell.measure(s) for s in ("collected", "000/000", "Status"))
        state_w += round(32 * self.ui_scale)
        self.tree.column("state", width=state_w, minwidth=state_w,
                         anchor="center", stretch=False)
        self.tree.column("#0", minwidth=round(220 * self.ui_scale), stretch=True)
        sb = ttk.Scrollbar(f, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def populate_tree(self):
        self.tree.delete(*self.tree.get_children())
        if not self.editor:
            return
        collected = self.editor.collected
        untracked = self.editor.untracked_regions
        for region, by_type in self.catalog.grouped().items():
            items = [i for t in by_type.values() for i in t]
            have = sum(1 for i in items if i.flag in collected)
            node = self.tree.insert(
                "", "end",
                text=region_row_label(self.catalog.item(items[0].flag).region_name,
                                      region, untracked),
                values=(f"{have}/{len(items)}",), open=False)
            for type_, entries in by_type.items():
                thave = sum(1 for i in entries if i.flag in collected)
                sub = self.tree.insert(node, "end", text=TYPE_LABELS[type_],
                                       values=(f"{thave}/{len(entries)}",))
                editable = region not in untracked
                for item in entries:
                    if item.flag in collected:
                        state = "collected"
                    else:
                        # Once the region is expanded its "(not editable)"
                        # parent row is off screen, so each leaf has to say so
                        # for itself.
                        state = "—" if editable else "not editable"
                    self.tree.insert(sub, "end", iid=item.flag, text=item.display,
                                     values=(state,))

    # -- zone 3 ---------------------------------------------------------
    def _build_actions(self):
        f = ttk.Frame(self.root, padding=(16, 10))
        f.pack(fill="x")

        row = ttk.Frame(f)
        row.pack(fill="x", pady=(0, 8))
        self.buttons = []
        for text, cmd, style in (
            ("Collect Selected", self.on_collect_selected, "TButton"),
            ("Collect Everything", self.on_collect_all, "Accent.TButton"),
            ("Back Up Now", self.on_backup, "TButton"),
            ("Restore…", self.on_restore, "TButton"),
        ):
            b = ttk.Button(row, text=text, command=cmd, style=style)
            b.pack(side="left", padx=(0, 8))
            self.buttons.append(b)

        # Explorer shortcuts. Deliberately NOT added to self.buttons: opening a
        # folder is harmless and should stay available while work is running.
        row2 = ttk.Frame(f)
        row2.pack(fill="x", pady=(0, 8))
        ttk.Button(row2, text="Open Save Folder",
                   command=lambda: self.reveal(self.save_path.parent if self.save_path else None)
                   ).pack(side="left", padx=(0, 8))
        ttk.Button(row2, text="Open Backup Folder",
                   command=lambda: self.reveal(self.backup_root() if self.save_path else None)
                   ).pack(side="left")

        # Classic tk.Checkbutton, not ttk. clam draws its checked indicator as
        # a crossed box, which reads just as easily as "disabled" or "no" as it
        # does as "yes" - a bad property for the one control that decides
        # whether the save ends at 242 or 243. The classic widget draws a real
        # tick when on and an empty box when off, which is unambiguous.
        self.leave_one_check = tk.Checkbutton(
            f, variable=self.leave_one, text=LEAVE_ONE_LABEL,
            anchor="w", highlightthickness=0, bd=0,
            font=(UI_FONT, round(BASE_PT * self.ui_scale)),
            background=self.palette["bg"], foreground=self.palette["text"],
            selectcolor=self.palette["surface"],
            activebackground=self.palette["bg"],
            activeforeground=self.palette["text"])
        self.leave_one_check.pack(anchor="w", fill="x", pady=(0, 8))

        self.log_widget = tk.Text(f, height=9, state="disabled", wrap="word",
                                  relief="flat",
                                  # scaled with the rest of the UI, so the
                                  # log does not shrink relative to it
                                  font=(MONO_FONT, round(MONO_PT * self.ui_scale)),
                                  background=self.palette["surface"],
                                  foreground=self.palette["text"])
        self.log_widget.pack(fill="x")
        ttk.Button(f, text="Copy log", command=self.on_copy_log).pack(anchor="e", pady=(6, 0))

    def reveal(self, folder):
        """Open a folder in the system file manager, creating it if needed."""
        if folder is None:
            messagebox.showinfo("No save", "Open a save file first.")
            return
        folder = Path(folder)
        # Runs on the UI thread, outside Activity. In the --noconsole build an
        # exception here reaches nothing at all and the button just looks dead.
        try:
            folder.mkdir(parents=True, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.run(["open", str(folder)])
            else:
                subprocess.run(["xdg-open", str(folder)])
        except Exception as exc:
            self.activity.log(f"Could not open {folder}: {exc}")
            messagebox.showerror(
                "Cannot open folder",
                f"{folder}\n\ncould not be opened:\n{exc}")
            return
        self.activity.log(f"Opened {folder}")

    def backup_root(self) -> Path:
        """Backups live beside the saves, one level ABOVE the sync folder.

        Deliberately not inside `remote/`. That directory is Steam Cloud's sync
        root: anything placed there risks being uploaded against the game's
        cloud quota, or removed during conflict resolution. The parent
        directory is not synced (Steam's own remotecache.vdf lives there), so
        backups are still right next to the saves and one click away, without
        handing them to a service that manages its own contents.
        """
        return self.save_path.parent.parent / "RiddlerEditorBackups"

    def _write(self, log, added: list[str]):
        """Shared write path. Rails, then backup, then write, then verify."""
        # Nothing to add means nothing to write. Without this, a second click
        # on "Collect Everything" took a full-folder backup, ran os.replace
        # over the live save and logged "Wrote 2,428,928 bytes / Verified:
        # 242/243" for a change that did not exist — bumping the save's mtime,
        # provoking a Steam Cloud re-upload, and opening an os.replace window
        # on the user's real playthrough for no reason at all.
        if not added:
            log("Nothing to add — everything selected is already collected. "
                "The save was not touched.")
            if self.editor.left_behind:
                log(f"Still outstanding: "
                    f"{where_to_find(self.editor.left_behind, self.catalog)}")
            return added

        check_writable_target(self.save_path)
        rotations = check_slot_complete(self.save_path)
        log(f"Slot has {len(rotations)} rotation files — OK")
        if game_is_running():
            raise Refused(
                "Batman: Arkham Knight is running. Close the game completely "
                "before editing, or it will overwrite the change on exit.")

        # Label the backup with what is IN it, read back off disk. self.editor
        # has already been mutated by the caller at this point, so labelling
        # from it names the state the user is moving away FROM as the state
        # they are moving TO — the Restore picker would then offer "242/243"
        # for a directory holding the 123/243 save.
        log(f"Backing up {self.save_path.parent}…")
        on_disk = SaveEditor(self.save_path.read_bytes()).challenge_count
        dest = create_backup(self.save_path.parent, self.backup_root(),
                             label=f"{on_disk}/243")
        log(f"Backed up to {dest} (verified, {on_disk}/243)")

        data = self.editor.to_bytes()
        tmp = self.save_path.with_suffix(".sgd.tmp")
        try:
            tmp.write_bytes(data)
            os.replace(tmp, self.save_path)
        except BaseException:
            # Without this a failed replace strands 2.4 MB of .tmp in the
            # user's save folder, forever, with nothing to clean it up.
            tmp.unlink(missing_ok=True)
            raise
        log(f"Wrote {len(data):,} bytes to {self.save_path.name}")

        check = SaveEditor(self.save_path.read_bytes())
        if check.challenge_count != self.editor.challenge_count:
            # After the write, so unlike every other failure here the save on
            # disk HAS changed. "restore from the backup above" assumed the
            # user knew that meant the Restore... button and which row to pick.
            raise RuntimeError(
                f"The save was written but read back as "
                f"{check.challenge_count}/243 instead of "
                f"{self.editor.challenge_count}/243. Something else is writing "
                f"to this folder - Steam Cloud is the usual culprit. Click "
                f"Restore..., pick the backup listed above, and put the game "
                f"back the way it was before trying again.")
        log(f"Verified: {check.challenge_count}/243")
        return added

    def on_collect_all(self):
        if not self._ready():
            return
        # Read the Tk variable here, on the UI thread. Doing it inside work()
        # would touch Tcl from the worker, which is exactly what Activity
        # exists to avoid ("main thread is not in main loop").
        leave_one = self.leave_one.get()
        def work(log):
            added = self.editor.collect_all(leave_one=leave_one)
            log(f"Adding {len(added)} flags → {self.editor.challenge_count}/243")
            if self.editor.left_behind:
                log(f"LEFT ONE for you to pick up in game, so the achievement "
                    f"still fires: "
                    f"{where_to_find(self.editor.left_behind, self.catalog)}")
            # The CLI has always said this; the window said nothing at all, so
            # a save that stops at 215/243 looked like the tool going wrong.
            note = skipped_note(self.editor)
            if note:
                log(note)
            return self._write(log, added)
        # on_error re-reads the file. work() has already mutated self.editor by
        # the time _write can raise, so without this the in-memory save would
        # sit ahead of the disk and the next click would report "Adding 0".
        self.activity.run("collect everything", work, lambda _: self.refresh(),
                          on_error=self.reload)

    def on_collect_selected(self):
        if not self._ready():
            return
        flags = self._selected_flags()
        if not flags:
            messagebox.showinfo("Nothing selected",
                                "Select one or more collectibles first.")
            return
        untracked = self.editor.untracked_regions
        blocked = [f for f in flags if self.catalog.item(f).region in untracked]
        if blocked:
            # _check would refuse these anyway, but only after the user had
            # committed to the click, and as a RailError in the log.
            names = ", ".join(sorted({self.catalog.item(f).region_name
                                      for f in blocked}))
            flags = [f for f in flags if f not in blocked]
            if not flags:
                messagebox.showinfo(
                    "Not editable yet",
                    f"Everything you selected is in {names}, which this save "
                    f"has no Riddler records for yet. Visit it once in game, "
                    f"save, and reopen this file.")
                return
            self.activity.log(f"Skipping {len(blocked)} collectible(s) in {names}: "
                              f"this save has no Riddler records for that area yet.")
        def work(log):
            added = self.editor.collect(flags)
            log(f"Adding {len(added)} flags → {self.editor.challenge_count}/243")
            return self._write(log, added)
        self.activity.run("collect selected", work, lambda _: self.refresh(),
                          on_error=self.reload)

    def _selected_flags(self) -> list[str]:
        """Every collectible the selection covers, group rows included.

        Leaf rows carry `iid=item.flag`; region and type rows get whatever iid
        Tk assigns ("I001"), which `catalog.known` rejects. Filtering the
        selection through `known` therefore threw away exactly the rows the
        tree is grouped to invite you to use: selecting "Bleake Island 0/66"
        and clicking Collect Selected answered "Nothing selected", and a mixed
        selection silently dropped the 66 and collected the two leaves beside
        it.
        """
        out: list[str] = []
        seen: set[str] = set()

        def walk(iid: str) -> None:
            children = self.tree.get_children(iid)
            if children:
                for child in children:
                    walk(child)
            elif self.catalog.known(iid) and iid not in seen:
                seen.add(iid)
                out.append(iid)

        for iid in self.tree.selection():
            walk(iid)
        return out

    def on_backup(self):
        if not self._ready():
            return
        def work(log):
            dest = create_backup(self.save_path.parent, self.backup_root(),
                                 label=f"{self.editor.challenge_count}/243")
            log(f"Backed up to {dest} (verified)")
        self.activity.run("backup", work)

    def on_restore(self):
        # backup_root() is derived from the loaded save's folder, so without
        # this guard clicking Restore before opening anything dereferences
        # None. In a --noconsole build that traceback is invisible and the
        # button just looks dead.
        if not self._ready():
            return
        # list_backups is careful now, but it still walks the filesystem on the
        # UI thread, outside Activity. An exception here reaches nothing: in
        # the --noconsole build sys.stderr is None, so Tk's default handler
        # prints nowhere and the button is simply dead. This is the recovery
        # path; it does not get to fail silently.
        try:
            entries = list_backups(self.backup_root())
        except Exception as exc:
            self.activity.log(f"Could not read the backup folder: {exc}")
            messagebox.showerror(
                "Cannot list backups",
                f"The backup folder could not be read:\n\n{exc}\n\n"
                f"Use Open Backup Folder to look at it directly.")
            return
        if not entries:
            messagebox.showinfo("No backups", "No backups have been made yet.")
            return
        win = tk.Toplevel(self.root)
        win.title("Restore a backup")
        # exportselection=0: without it the listbox loses its selection the
        # moment anything else takes the X selection, and Restore then reads
        # as a dead button.
        lst = tk.Listbox(win, width=52, height=12, exportselection=0)
        for e in entries:
            lst.insert("end", f"{e.created}   {e.label or '—'}   ({e.files} files)")
        lst.pack(padx=14, pady=14)

        def do_restore(_event=None):
            sel = lst.curselection()
            if not sel:
                # Used to return silently, which is indistinguishable from the
                # button being broken.
                messagebox.showinfo(
                    "Nothing chosen", "Select a backup from the list first.",
                    parent=win)
                return
            # This dialog's button is not in self.buttons, so it stays live
            # while work is running. Destroying the window first would then
            # lose the click to the busy guard and take the picker with it.
            if self.activity.busy:
                messagebox.showinfo(
                    "Busy", "Wait for the current operation to finish, then "
                            "choose a backup again.", parent=win)
                return
            entry = entries[sel[0]]
            names = backup_contents(entry.path)
            if not names:
                messagebox.showerror(
                    "Unusable backup",
                    f"{entry.created} has no readable manifest, so there is no "
                    f"way to check what it holds. It will not be restored.",
                    parent=win)
                return
            if not messagebox.askyesno(
                    "Restore this backup?",
                    restore_warning(names, self.save_path.parent), parent=win):
                return
            win.destroy()
            self.restore_from(entry.path, entry.created)

        lst.bind("<Double-Button-1>", do_restore)
        ttk.Button(win, text="Restore", style="Accent.TButton",
                   command=do_restore).pack(pady=(0, 14))

    def restore_from(self, backup_dir: Path, label: str = ""):
        """Roll the save folder back, with the rails a write would get.

        Restore had none at all, which is backwards: it is the widest write
        the tool makes and the one a user only reaches on a bad day. Two
        things were missing and both cost real data.

        The game-running rail. Restoring under a running game loses the
        restore, because the game writes its own save over the top when it
        exits — the exact hazard the edit path refuses, on the path the user
        turns to when the edit went wrong.

        A backup of what is being discarded. Restore overwrites every slot in
        the folder, so a mis-clicked row is otherwise a one-way trip that can
        take a playthrough the user never meant to touch.
        """
        slot_dir = self.save_path.parent          # read on the UI thread

        def work(log):
            if game_is_running():
                raise Refused(
                    "Batman: Arkham Knight is running. Close the game "
                    "completely before restoring, or it will write its own "
                    "save over the restored one when it exits.")
            log(f"Backing up the current state of {slot_dir} first…")
            dest = create_backup(slot_dir, self.backup_root(),
                                 label="before restore")
            log(f"Backed up to {dest} (verified)")
            names = restore_backup(backup_dir, slot_dir)
            log(f"Restored {len(names)} file(s) from {label or backup_dir.name}: "
                f"{', '.join(names)}")

        # restore_backup verifies every hash before copying, but the copy loop
        # itself is not atomic, so a failure partway can still leave disk and
        # memory disagreeing. Re-read either way.
        self.activity.run("restore", work, lambda _: self.reload(),
                          on_error=self.reload)

    def on_copy_log(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.log_widget.get("1.0", "end"))
        self.activity.log("Log copied to clipboard")

    def _ready(self) -> bool:
        if self.editor is None:
            messagebox.showinfo("No save", "Open a save file first.")
            return False
        return True

    @classmethod
    def _best_candidate(cls, saves: list[Path]) -> Path:
        """The most current save that sits in a slot we could actually write.

        Two rules, both learned the hard way. Prefer a complete slot, because
        picking purely by recency opens whatever the game touched last, which
        is often a slot with only one rotation present — and the write rails
        then refuse it. Auto-loading the one file the tool cannot edit reads as
        a bug rather than as a rail doing its job.

        Rank with the same _rotation_rank the "not the newest rotation" warning
        uses. When these two disagreed, the app would open a file and then
        immediately warn that the file it had just opened was the wrong one.

        The same reasoning covers a save with nothing collected in it, which
        the editor refuses: a folder can hold a brand-new game beside a real
        playthrough, and a brand-new game is by definition the one played most
        recently. Testing it by the flag array rather than by constructing a
        SaveEditor keeps this cheap — it is on the startup path, and parsing
        every store in every rotation is not.
        """
        usable = []
        for p in saves:
            try:
                check_slot_complete(p)
                if any(f.startswith("PickedUp_")
                       for f in SgdFile(p.read_bytes()).read_flags()):
                    usable.append(p)
            except Exception:
                pass
        return max(usable or saves, key=cls._rotation_rank)

    def _autodetect(self):
        for d in find_save_dirs():
            saves = sorted(d.glob("BAK1Save*.sgd"))
            if saves:
                self.activity.log(f"Found save folder: {d}")
                self.load(self._best_candidate(saves))
                return
        self.activity.log("No save folder detected — use Open Save…")

    def _open_dialog_dir(self) -> Path:
        """Where "Open Save…" should start.

        The folder of whatever is already loaded, else the auto-detected save
        folder, else the Desktop — never the process working directory, which
        for a packaged build is wherever the shortcut happened to point.
        """
        if self.save_path and self.save_path.parent.is_dir():
            return self.save_path.parent
        for d in find_save_dirs():
            if d.is_dir():
                return d
        desktop = Path.home() / "Desktop"
        return desktop if desktop.is_dir() else Path.home()

    def on_open(self):
        path = filedialog.askopenfilename(
            title="Open Arkham Knight save",
            initialdir=str(self._open_dialog_dir()),
            filetypes=[("Arkham Knight saves", "BAK1Save*.sgd"),
                       ("All files", "*.*")])
        if path:
            self.load(Path(path))

    @staticmethod
    def _rotation_rank(path: Path):
        """How current a rotation is: playtime first, mtime only to break ties.

        Modification time alone is not trustworthy, because it records when the
        bytes last landed on disk rather than how far the playthrough got.
        Anything that rewrites the files in some other order — copying a folder
        with a tool that does not preserve timestamps, unpacking a downloaded
        save, syncing between machines — reorders them by mtime while leaving
        the actual progression untouched. Playtime is the game's own monotonic
        counter and it lives inside the file, so it survives all of that.

        Observed directly: in a folder copied with `cp`, mtime ordered the
        rotations x0 < x1 < x2 while playtime ordered them 8h05 > 8h04 > 5h16.
        Playtime has it right; the file the game would load is x0.
        """
        try:
            playtime = SgdFile(Path(path).read_bytes()).playtime_seconds
        except Exception:
            playtime = -1.0
        return (playtime, Path(path).stat().st_mtime)

    def _newer_rotation(self, path: Path):
        """Return the newer sibling rotation the game would load instead, if any.

        The game keeps three rotations per slot and reads the most recent one.
        Editing an older rotation produces an edit the game never sees, which
        is indistinguishable from the tool being broken, so it is worth saying
        out loud. check_slot_complete only counts the files; it has no opinion
        about which one is current.
        """
        try:
            ranked = {p: self._rotation_rank(p) for p in slot_files(path)}
            if len(ranked) < 2:
                return None
            newest = max(ranked, key=ranked.get)
            here = Path(path).resolve()
            if newest.resolve() == here:
                return None
            # A tie means we genuinely cannot tell the two apart, so warning
            # would be presenting a guess as a fact. Stay quiet instead.
            mine = next((r for p, r in ranked.items() if p.resolve() == here), None)
            if mine is not None and ranked[newest] == mine:
                return None
        except Exception:
            return None
        return newest

    def load(self, path: Path) -> bool:
        try:
            editor = SaveEditor(path.read_bytes(), self.catalog)
        except Exception as exc:
            kind, title, message = refusal_dialog(exc)
            self.activity.log(f"{path.name}: {message}")
            # Nothing was replaced, so say what is still open. Otherwise the
            # log announces a failure while the status line names a different
            # save, and the user cannot tell which one a click would write.
            if self.save_path is not None:
                self.activity.log(f"Still working with {slot_label(self.save_path)} "
                                  f"— {self.save_path.name}")
            (messagebox.showinfo if kind == "info" else messagebox.showerror)(
                title, message)
            return False
        self.editor, self.save_path = editor, path
        self.newest_rotation = self._newer_rotation(path)
        self.refresh()
        h = int(self.editor.playtime_seconds // 3600)
        m = int(self.editor.playtime_seconds % 3600 // 60)
        self.activity.log(f"Loaded {slot_label(path)} — {path.name} "
                          f"({self.editor.platform}, {h}h{m:02d}m, "
                          f"{self.editor.challenge_count}/243)")
        # Say this on open, not only after the write. A user who learns at the
        # end that 27 challenges were unreachable has already spent the click.
        note = skipped_note(self.editor)
        if note:
            self.activity.log(note)
        if self.newest_rotation is not None:
            self.activity.log(
                f"WARNING: {path.name} is not the newest rotation in this slot. "
                f"The game keeps three rotations and loads the most recent one, "
                f"which here is {self.newest_rotation.name}. An edit to this file "
                f"will most likely never be seen in game — open "
                f"{self.newest_rotation.name} instead, unless you specifically "
                f"mean to edit this rotation.")
        return True

    def reload(self):
        """Re-read the file after an operation, successful or failed.

        This is NOT the same situation as "Open Save...". By the time reload
        runs, `work()` has already mutated `self.editor` — collect() and
        collect_all() both change it before `_write` runs a single rail — so
        when the re-read fails, what `load()` politely leaves in place is the
        abandoned mutation.

        That is the one path found that could write data the user did not ask
        for. The window went on rendering the last good state while memory
        held 242/243, and because the flags were already there in memory, the
        next click on a single trophy added nothing, logged "Adding 0 flags",
        and then serialised the lot: 302 flags committed from one click.

        So a save we cannot verify against disk is closed, not kept.
        """
        if not self.save_path:
            return
        path = self.save_path
        if self.load(path):
            return
        self.editor = None
        self.save_path = None
        self.newest_rotation = None
        self.status.configure(text="No save loaded")
        self.tree.delete(*self.tree.get_children())
        self.activity.log(
            f"CLOSED {path.name}. It could not be re-read, so what is in memory "
            f"cannot be trusted against what is on disk and nothing further "
            f"will be written. Check the file is still there and reopen it.")

    def refresh(self):
        if not self.editor:
            return
        self.status.configure(
            text=status_text(self.save_path, self.editor, self.newest_rotation))
        self.populate_tree()

    def on_theme(self, _event=None):
        mode = self.theme.get()
        self.palette = apply_theme(self.root,
                                   detect_system_theme() if mode == "auto" else mode,
                                   self.ui_scale)
        # The log and the leave-one checkbox are classic tk widgets styled by
        # explicit colours, so ttk restyling never reaches them. Without this
        # they keep the previous palette and can end up black on black.
        self.activity.apply_palette(self.palette)
        self.leave_one_check.configure(
            background=self.palette["bg"], foreground=self.palette["text"],
            selectcolor=self.palette["surface"],
            activebackground=self.palette["bg"],
            activeforeground=self.palette["text"])


def main():
    # Sharp rendering on high-DPI displays. Without it Windows treats the app
    # as DPI-unaware and stretches its bitmap instead, which is both blurry and
    # actively wrong: the app then lays out against a virtualised screen size,
    # and the right-hand column ends up clipped. Same call the other editors in
    # this family make, for the same reason.
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    root = tk.Tk()
    try:
        EditorApp(root)
    except Exception as exc:
        # Everything in __init__ and _autodetect runs before there is a log
        # panel to write to, and the packaged build has no console. Without
        # this, an exception here means double-clicking the exe opens nothing
        # at all and says nothing about why.
        import traceback
        messagebox.showerror(
            "The editor could not start",
            f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}")
        raise
    root.mainloop()


if __name__ == "__main__":
    main()
