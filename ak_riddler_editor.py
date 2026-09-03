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
    """Apply a palette. Uses sv_ttk when available, else a hand-built theme."""
    palette = PALETTES[mode]
    pt = lambda size: max(1, round(size * scale))
    try:
        import sv_ttk
        sv_ttk.set_theme(mode)
    except Exception:
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(".", background=palette["bg"], foreground=palette["text"],
                        fieldbackground=palette["surface"], borderwidth=0,
                        font=(UI_FONT, pt(BASE_PT)))
        style.configure("TFrame", background=palette["bg"])
        style.configure("TLabel", background=palette["bg"], foreground=palette["text"])
        style.configure("Muted.TLabel", foreground=palette["muted"])
        style.configure("Heading.TLabel",
                        font=(UI_FONT + " Semibold", pt(HEADING_PT)))
        style.configure("TButton", padding=(round(14 * scale), round(7 * scale)),
                        background=palette["surface"])
        style.map("TButton",
                  background=[("active", palette["accent"]), ("disabled", palette["bg"])],
                  foreground=[("active", "#ffffff"), ("disabled", palette["muted"])])
        style.configure("Accent.TButton", background=palette["accent"], foreground="#ffffff")
        # Row height has to grow with the type or the rows clip their own text.
        style.configure("Treeview", background=palette["surface"],
                        fieldbackground=palette["surface"], foreground=palette["text"],
                        rowheight=round(ROW_PX * scale), borderwidth=0,
                        font=(UI_FONT, pt(BASE_PT)))
        style.configure("Treeview.Heading",
                        font=(UI_FONT + " Semibold", pt(BASE_PT)))
        style.configure("TCheckbutton", background=palette["bg"],
                        foreground=palette["text"])
        style.configure("TScrollbar", background=palette["surface"],
                        troughcolor=palette["bg"], arrowcolor=palette["text"],
                        borderwidth=0)
        # A readonly Combobox keeps clam's own field colours unless the readonly
        # state is mapped explicitly, which in dark mode leaves the selected
        # value as dark grey text on a dark field - effectively invisible.
        style.configure("TCombobox", arrowcolor=palette["text"])
        style.map("TCombobox",
                  fieldbackground=[("readonly", palette["surface"])],
                  background=[("readonly", palette["surface"])],
                  foreground=[("readonly", palette["text"])],
                  selectbackground=[("readonly", palette["surface"])],
                  selectforeground=[("readonly", palette["text"])])
        # The dropdown itself is a classic tk Listbox, reachable only this way.
        root.option_add("*TCombobox*Listbox.background", palette["surface"])
        root.option_add("*TCombobox*Listbox.foreground", palette["text"])
        root.option_add("*TCombobox*Listbox.selectBackground", palette["accent"])
        root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    # Type sizing is applied to BOTH branches, deliberately and last.
    #
    # sv_ttk installs its own theme with its own fonts, so while this lived
    # inside the fallback the scale silently did nothing whenever sv_ttk was
    # present — which is precisely the packaged build, because the release
    # workflow pip-installs sv-ttk. The app measured 10px glyphs on a 4K panel
    # for exactly that reason: the code that was supposed to enlarge them was
    # in the branch that never ran.
    #
    # Named fonts first (ttk themes derive from them, and classic widgets use
    # them directly), then the specific styles, so neither engine can win.
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

    style = ttk.Style(root)
    style.configure(".", font=(UI_FONT, pt(BASE_PT)))
    style.configure("TLabel", font=(UI_FONT, pt(BASE_PT)))
    style.configure("Muted.TLabel", font=(UI_FONT, pt(BASE_PT)))
    style.configure("Heading.TLabel", font=(UI_FONT + " Semibold", pt(HEADING_PT)))
    style.configure("TButton", font=(UI_FONT, pt(BASE_PT)))
    style.configure("Accent.TButton", font=(UI_FONT, pt(BASE_PT)))
    style.configure("TCheckbutton", font=(UI_FONT, pt(BASE_PT)))
    style.configure("TCombobox", font=(UI_FONT, pt(BASE_PT)))
    # Row height must come from the font's own metrics, not a scaled constant.
    # A fixed multiplier is a guess about how tall the type will render, and
    # when it guesses low the rows clip their own descenders — "Miagani",
    # "Stagg", "HQ" all lost their tails at rowheight = 24 * 1.4.
    body = tkfont.Font(root=root, family=UI_FONT, size=pt(BASE_PT))
    row_h = max(round(ROW_PX * scale), body.metrics("linespace") + round(8 * scale))
    style.configure("Treeview", font=(UI_FONT, pt(BASE_PT)), rowheight=row_h)
    style.configure("Treeview.Heading", font=(UI_FONT + " Semibold", pt(BASE_PT)))

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
                self.queue.put(("log", f"FAILED: {exc}"))
                self.queue.put(("log", traceback.format_exc().strip()))
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

from aksave.backup import create_backup, list_backups, restore_backup
from aksave.catalog import Catalog
from aksave.editor import SaveEditor
from aksave.sgd import SgdFile
from aksave.rails import (check_slot_complete, check_writable_target,
                          game_is_running, slot_files)

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
        self.activity.log("Ready. Choose a save file to begin.")
        self._autodetect()

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
        self.tree.column("state", width=110, anchor="center", stretch=False)
        sb = ttk.Scrollbar(f, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def populate_tree(self):
        self.tree.delete(*self.tree.get_children())
        if not self.editor:
            return
        collected = self.editor.collected
        for region, by_type in self.catalog.grouped().items():
            items = [i for t in by_type.values() for i in t]
            have = sum(1 for i in items if i.flag in collected)
            node = self.tree.insert("", "end", text=self.catalog.item(items[0].flag).region_name,
                                    values=(f"{have}/{len(items)}",), open=False)
            for type_, entries in by_type.items():
                thave = sum(1 for i in entries if i.flag in collected)
                sub = self.tree.insert(node, "end", text=TYPE_LABELS[type_],
                                       values=(f"{thave}/{len(entries)}",))
                for item in entries:
                    self.tree.insert(sub, "end", iid=item.flag, text=item.display,
                                     values=("collected" if item.flag in collected else "—"))

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

        ttk.Checkbutton(
            f, variable=self.leave_one,
            text="Leave one collectible uncollected, so achievements still "
                 "unlock when you pick it up in game",
        ).pack(anchor="w", pady=(0, 8))

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
        folder.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(folder)
        elif sys.platform == "darwin":
            subprocess.run(["open", str(folder)])
        else:
            subprocess.run(["xdg-open", str(folder)])
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
        check_writable_target(self.save_path)
        rotations = check_slot_complete(self.save_path)
        log(f"Slot has {len(rotations)} rotation files — OK")
        if game_is_running():
            raise RuntimeError(
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
            raise RuntimeError("re-read did not match; restore from the backup above")
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
            return self._write(log, added)
        # on_error re-reads the file. work() has already mutated self.editor by
        # the time _write can raise, so without this the in-memory save would
        # sit ahead of the disk and the next click would report "Adding 0".
        self.activity.run("collect everything", work, lambda _: self.refresh(),
                          on_error=self.reload)

    def on_collect_selected(self):
        if not self._ready():
            return
        flags = [i for i in self.tree.selection() if self.catalog.known(i)]
        if not flags:
            messagebox.showinfo("Nothing selected", "Select one or more collectibles first.")
            return
        def work(log):
            added = self.editor.collect(flags)
            log(f"Adding {len(added)} flags → {self.editor.challenge_count}/243")
            return self._write(log, added)
        self.activity.run("collect selected", work, lambda _: self.refresh(),
                          on_error=self.reload)

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
        entries = list_backups(self.backup_root())
        if not entries:
            messagebox.showinfo("No backups", "No backups have been made yet.")
            return
        win = tk.Toplevel(self.root)
        win.title("Restore a backup")
        lst = tk.Listbox(win, width=52, height=12)
        for e in entries:
            lst.insert("end", f"{e.created}   {e.label or '—'}   ({e.files} files)")
        lst.pack(padx=14, pady=14)

        def do_restore():
            sel = lst.curselection()
            if not sel:
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
            win.destroy()
            def work(log):
                names = restore_backup(entry.path, self.save_path.parent)
                log(f"Restored {len(names)} files from {entry.created}")
            # restore_backup verifies every hash before copying, but the copy
            # loop itself is not atomic, so a failure partway can still leave
            # disk and memory disagreeing. Re-read either way.
            self.activity.run("restore", work, lambda _: self.reload(),
                              on_error=self.reload)
        ttk.Button(win, text="Restore", style="Accent.TButton",
                   command=do_restore).pack(pady=(0, 14))

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
        """
        complete = []
        for p in saves:
            try:
                check_slot_complete(p)
                complete.append(p)
            except Exception:
                pass
        return max(complete or saves, key=cls._rotation_rank)

    def _autodetect(self):
        for d in find_save_dirs():
            saves = sorted(d.glob("BAK1Save*.sgd"))
            if saves:
                self.activity.log(f"Found save folder: {d}")
                self.load(self._best_candidate(saves))
                return
        self.activity.log("No save folder detected — use Open Save…")

    def on_open(self):
        path = filedialog.askopenfilename(title="Open Arkham Knight save",
                                          filetypes=[("Save files", "BAK1Save*.sgd")])
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

    def load(self, path: Path):
        try:
            self.editor = SaveEditor(path.read_bytes(), self.catalog)
            self.save_path = path
        except Exception as exc:
            self.activity.log(f"Could not read {path.name}: {exc}")
            messagebox.showerror("Cannot read save", str(exc))
            return
        self.newest_rotation = self._newer_rotation(path)
        self.refresh()
        h = int(self.editor.playtime_seconds // 3600)
        m = int(self.editor.playtime_seconds % 3600 // 60)
        self.activity.log(f"Loaded {path.name} ({self.editor.platform}, {h}h{m:02d}m, "
                          f"{self.editor.challenge_count}/243)")
        if self.newest_rotation is not None:
            self.activity.log(
                f"WARNING: {path.name} is not the newest rotation in this slot. "
                f"The game keeps three rotations and loads the most recent one, "
                f"which here is {self.newest_rotation.name}. An edit to this file "
                f"will most likely never be seen in game — open "
                f"{self.newest_rotation.name} instead, unless you specifically "
                f"mean to edit this rotation.")

    def reload(self):
        if self.save_path:
            self.load(self.save_path)

    def refresh(self):
        if not self.editor:
            return
        h = int(self.editor.playtime_seconds // 3600)
        m = int(self.editor.playtime_seconds % 3600 // 60)
        warn = ""
        if self.newest_rotation is not None:
            warn = ("  ·  not the newest rotation "
                    f"(the game loads {self.newest_rotation.name})")
        self.status.configure(
            text=f"{self.save_path.name}  ·  {self.editor.platform}  ·  {h}h{m:02d}m  "
                 f"·  {self.editor.challenge_count}/243 challenges "
                 f"({self.editor.collected_count}/315 objects){warn}")
        self.populate_tree()

    def on_theme(self, _event=None):
        mode = self.theme.get()
        self.palette = apply_theme(self.root,
                                   detect_system_theme() if mode == "auto" else mode,
                                   self.ui_scale)
        # The log is a classic tk.Text styled by explicit colours, so ttk
        # restyling never reaches it. Without this it keeps the previous
        # palette and can end up black on black.
        self.activity.apply_palette(self.palette)


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
    EditorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
