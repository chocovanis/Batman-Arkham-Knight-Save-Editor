# Arkham Knight — Riddler Save Editor

A small desktop tool that marks Riddler collectibles as collected in a
**Batman: Arkham Knight** save file, so you can finish the Riddler content
without hunting all 243 challenges by hand.

It edits only Riddler collectible flags. Nothing else in your save is touched.

![Windows](https://img.shields.io/badge/Windows-supported-blue)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)
![Licence GPL-3.0](https://img.shields.io/badge/licence-GPL--3.0-green)

---

## ⚠️ Back up your save first

The tool takes a verified backup automatically before every write, and it puts
that backup **outside** your cloud-synced save folder so Steam cannot clean it
up. Even so: **make your own copy of your save folder before you start.** It
costs ten seconds and it is the only thing that makes a mistake reversible.

Steam Cloud will happily overwrite a local save with its own copy. Close the
game *completely* before editing — not to the main menu, all the way out.

---

## What it does

- Shows what your save currently has: platform, playtime, and
  `N/243 challenges (M/315 objects)`.
- Lets you collect **everything**, or select individual collectibles from a
  tree grouped by region and type.
- Optionally **leaves one collectible uncollected**, so the achievement still
  pops when you pick that last one up in game (see below).
- Takes a hash-verified backup before every write, and lists backups so you can
  restore one in a click.
- Re-reads the file after writing and checks it says what it should.

## What it deliberately will not do

This matters more than the feature list.

- It writes **only** `BAK1Save<slot>x<rotation>.sgd` files. `profile.bin`,
  `LBGameCache.dat` and `remotecache.vdf` are never written — that is an
  allowlist, not a blocklist.
- It never writes trial-completion flags, `CatCollarRemoved`, or the
  case-closed flag. That is what makes the tool safe by construction rather
  than safe by warning: the Riddler boss fight needs **both** 243/243 **and**
  a freed Catwoman, so if you set 243 on an early save the game's own gate
  simply will not start the fight. You get a counter that looks odd, not a
  broken playthrough.
- It refuses to edit a save slot that does not have all three rotation files.
- It refuses to write while the game is running.

---

## Download and run

**Option A — packaged build (no Python needed)**

1. Download `AK-Riddler-Save-Editor.zip` from the
   [Releases](https://github.com/chocovanis/Batman-Arkham-Knight-Save-Editor/releases)
   page.
2. Extract the whole folder — do not run the `.exe` from inside the zip.
3. Run **`AK-Riddler-Save-Editor.exe`**.

**Option B — from source**

```bash
git clone https://github.com/chocovanis/Batman-Arkham-Knight-Save-Editor.git
cd Batman-Arkham-Knight-Save-Editor
python ak_riddler_editor.py
```

Python 3.10 or newer. No dependencies are required; `pip install sv-ttk` gets
you a nicer theme if you want one.

---

## Where your saves live

| Store | Path |
|---|---|
| Steam | `C:\Program Files (x86)\Steam\userdata\<your id>\208650\remote\` |
| GOG / Epic | `Documents\WB Games\Batman Arkham Knight\<your id>\SaveData\` |

Files are named `BAK1Save<slot>x<rotation>.sgd`. **Slot 0 is UI slot 1**, and
each slot keeps three rotations (`x0`, `x1`, `x2`) — the game writes them in
turn and loads the most recent. The editor auto-detects your save folder and
opens the most recently written file, which is the one the game will read.

Both the Steam and GOG/Epic variants are supported and detected automatically
(GOG/Epic files carry an extra 4-byte prefix).

---

## Usage

1. **Close Batman: Arkham Knight completely.**
2. Launch the editor. It finds your save folder and loads the newest save.
3. Check the status line — it should match what the game shows you.
4. Click **Back Up Now** if you want an extra restore point.
5. Either:
   - tick or untick **Leave one collectible uncollected**, then click
     **Collect Everything**; or
   - select individual entries in the tree and click **Collect Selected**.
6. Launch the game and load that slot.

The activity log records every step, including where the backup went. **Copy
log** puts it on your clipboard if you need to report a problem.

### The "leave one uncollected" option

Arkham Knight awards its Riddler achievements when the counter *changes* to the
target value, not when the game notices it is already there. If a save simply
appears at 243/243, the achievement may never fire.

Leaving one collectible uncollected puts you at **242/243**. Pick up that last
one in game and the counter ticks over normally, so the achievement unlocks the
way it would have anyway. This is on by default and it is the recommended
setting. Turn it off only if you do not care about achievements.

---

## Backups and restore

Every write is preceded by a backup, so you normally do not have to think about
this. Backups go to:

```
<your save folder>\..\RiddlerEditorBackups\<date>_<time>\
```

One level **above** the save folder, deliberately. On Steam the save folder is
`remote\`, which is Steam Cloud's sync root — anything left in there is uploaded
against your cloud quota and can be removed during conflict resolution. The
parent folder is not synced.

Each backup stores a SHA-256 of every file it copied and verifies the copy
immediately. **Restore…** re-verifies every hash *before* it writes anything
back, so a corrupted backup is refused rather than half-applied.

**Open Backup Folder** and **Open Save Folder** open them in Explorer.

---

## FAQ

**Will this get me banned?**
No. Arkham Knight's multiplayer was cancelled before launch — there is no online
service, no leaderboards and no anti-cheat. Steam achievements are awarded
locally by the game.

**My antivirus flagged the download.**
That is a PyInstaller false positive, and a common one: an unsigned executable
built by bundling a Python interpreter looks structurally like packed malware to
a heuristic scanner. The full source is in this repository, release builds are
produced by GitHub Actions with build provenance attestation, and you can verify
one with `gh attestation verify <file> -R chocovanis/Batman-Arkham-Knight-Save-Editor`.
If you would rather not deal with it, run from source instead — see Option B.

**I edited my save and nothing changed in game.**
In order of likelihood:
1. The game was still running when you edited. Close it fully and redo the edit.
2. Steam Cloud restored its own copy over yours. Close the game, let Steam
   finish syncing, then edit and start the game from Steam.
3. You edited a different rotation than the one the game loads. The editor
   warns you when the file you opened is not the newest in its slot.

**The counter says 243/243 but the boss fight will not start.**
That is the safety gate working as intended, not a bug. The fight also requires
Catwoman to be freed, and this tool will not fake that flag. Play up to the
point where you free her and the fight becomes available.

**Can it edit anything besides Riddler collectibles?**
No, and that is a design decision rather than an oversight. Widening the write
scope is what would make the tool capable of breaking a playthrough.

---

## How it works

Arkham Knight saves are fixed-size, uncompressed, unencrypted and unchecksummed.
Riddler collectibles are recorded as the **presence of a flag name** in a counted
string array — collecting something means appending a string and adjusting one
length field in the header. That is exactly what this tool does, and no more:
existing bytes are never moved or rewritten, and the file size never changes.

The format was reverse-engineered from a corpus of 53 real save files across
both platforms and every progression state from 0 to 243. The challenge count
computed from the flags matches the game's own cached counter in every one.

## Contributing / reporting a problem

Open an issue with the contents of the activity log (**Copy log**). Please do
not attach save files to a public issue — they are large and they are your
personal game data.

## Licence

GPL-3.0. See [LICENSE](LICENSE). Not affiliated with, endorsed by, or connected
to Warner Bros., Rocksteady Studios, or DC Comics. Batman: Arkham Knight is
their trademark.
