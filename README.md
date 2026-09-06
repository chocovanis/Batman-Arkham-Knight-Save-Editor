# Arkham Knight — Riddler Save Editor

A small desktop tool that marks Riddler collectibles as collected in a
**Batman: Arkham Knight** save file, so you can finish the Riddler content
without hunting all 243 challenges by hand.

It edits only Riddler collectible flags. Nothing else in your save is touched.

![Windows](https://img.shields.io/badge/Windows-supported-blue)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)
![Licence GPL-3.0](https://img.shields.io/badge/licence-GPL--3.0-green)

---

## TL;DR

- **What it is.** A Windows desktop tool that marks Riddler collectibles as
  collected in a Batman: Arkham Knight save. It edits Riddler collectible flags
  and nothing else.
- **Close the game completely first** — all the way out, not to the main menu.
- **Make your own copy of your save folder** before you start. The tool backs one
  up automatically, but your own copy is what makes a mistake reversible.
- **Getting it:** download the zip from
  [Releases](https://github.com/chocovanis/Batman-Arkham-Knight-Save-Editor/releases)
  and run the `.exe`, or run it from source with Python — the editor itself has
  nothing to install. You can also build the `.exe` yourself, which needs
  PyInstaller. Step-by-step for all three is below.
- **Run it whenever you like.** It fills in only the areas your save has already
  been to and names any it skipped — Arkham Knight HQ is the one most likely to
  be missing. Visit a skipped area once in game, save, and run it again to
  finish the set.
- **"Leave one collectible uncollected" is on by default**, so the achievement
  fires normally when you pick that last one up. The editor tells you exactly
  which one it left and where to find it.
- **The Riddler encounter needs 243/243 *and* a freed Catwoman.** Setting the
  count early does not skip the story, and the content can take a few minutes of
  play to show up.
- **Restore puts back the whole save folder** — every slot, not just the one
  you edited.
- **Your antivirus may flag the `.exe`.** It is an unsigned PyInstaller build and
  that is what those look like to a scanner. Build it yourself or run from
  source — see the FAQ.

Everything below is the long version.

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

- When it **edits**, it writes **only** `BAK1Save<slot>x<rotation>.sgd` files.
  `profile.bin`, `LBGameCache.dat` and `remotecache.vdf` are never touched by an
  edit — that is an allowlist, not a blocklist. (**Restore** is the one
  exception, and it is deliberate: putting a backup back puts back everything
  the backup copied. It asks first, and names what it will overwrite.)
- It never writes trial-completion flags, `CatCollarRemoved`, or the
  case-closed flag. That is what makes the tool safe by construction rather
  than safe by warning: the Riddler boss fight needs **both** 243/243 **and**
  a freed Catwoman, so if you set 243 on an early save the game's own gate
  simply will not start the fight. You get a counter that looks odd, not a
  broken playthrough.
- It only gives you collectibles in areas your save has already been to. A save
  that has never reached Arkham Knight HQ has no Riddler records for it, and
  inventing them would leave the counter and the collectibles menu disagreeing.
  The editor says which areas it skipped and why.
- It refuses a save with no Riddler collectibles in it at all — a brand-new
  game, or the first hour before you find your first trophy. It has no way to
  locate your Riddler records without one to go on, and it says so plainly
  rather than guessing.
- It refuses to write while the game is running.

---

## When should you use it?

**Whenever you like — there is nothing to wait for.** Not a particular
completion percentage, and not a particular point in the story. What decides
what you get is which areas your save has already been to.

The editor gives you collectibles only in areas your save already has Riddler
records for, and tells you which ones it skipped. In a playthrough of your own
the only area ever missing past the prologue is **Arkham Knight HQ** — the
three islands, Stagg Airships and Panessa Studios always turn up together. How
far through the game you are is a poor predictor of it. If it says an area was skipped, visit that area
once in game, save, and run it again to finish the set.

You cannot get this wrong by accident. The worst case is that the count stops
short by whatever the skipped areas hold — 27 challenges if it is only Arkham
Knight HQ — and the editor names every area it skipped, on the status line, in
the tree, and in the log.

Two things worth knowing before you set 243/243:

- **The Riddler encounter needs 243/243 *and* a freed Catwoman.** Setting the
  count early does not skip the story — the game's own gate still holds, because
  the editor will not touch `CatCollarRemoved`.
- **The content does not appear the instant you load.** On a late-game save
  taken to 243/243 with the editor, the encounter became available after a few
  minutes of play. Give it a little time before concluding something is wrong.

Some collectibles are also gated behind main-story or Gotham's Most Wanted
progress in the world itself — a trophy can be behind a door that opens later.
That does not affect the editor, which sets the flag rather than walking you
there, but it is why a late save is a more comfortable starting point.

### Confirmed in game

A save edited by this tool was taken to 243/243 on a late-game Steam
playthrough. The Riddler encounter became available, the fight was played and
won, and the game then saved on top of the edit — keeping every collectible
exactly as the editor had set it.

---

## Download and run

Three ways in. **Option A** is quickest. **Option B** is the one to pick if you
would rather not run a downloaded executable at all — it is not a fallback, it
is the better answer.

### Option A — packaged build (nothing to install)

1. Download `AK-Riddler-Save-Editor.zip` from the
   [Releases](https://github.com/chocovanis/Batman-Arkham-Knight-Save-Editor/releases)
   page.
2. Right-click the zip and choose **Extract All**. Extract the whole folder —
   do not run the `.exe` from inside the zip. Windows names the destination
   after the zip, so you end up with `AK-Riddler-Save-Editor` inside another
   `AK-Riddler-Save-Editor`; the inner one is the folder you want.
3. Open the extracted folder and run **`AK-Riddler-Save-Editor.exe`**.

Windows will probably show **"Windows protected your PC"** the first time. That
is SmartScreen reacting to an executable it has not seen before from a publisher
it does not recognise — it is not a detection. Click **More info**, then **Run
anyway**. If you would rather not, use Option B or C instead.

Keep the `_internal` folder sitting next to the `.exe`. Moving the `.exe` out on
its own stops it starting.

### Option B — run from source

There is nothing to install but Python itself. The editor uses only what ships
with Python: no packages to add, no `pip install`, no `requirements.txt`.

1. **Install Python.** Get 3.10 or newer from
   [python.org/downloads](https://www.python.org/downloads/). On the first
   screen of the installer, **tick "Add python.exe to PATH"** before clicking
   Install. It is easy to miss and the rest of these steps depend on it.
2. **Get the source.** On this repository's page click the green **Code**
   button, then **Download ZIP**, and extract it. Extracting gives you a folder
   named `Batman-Arkham-Knight-Save-Editor-main` with **another folder of the
   same name inside it** — keep opening until you can see
   `ak_riddler_editor.py`. That inner folder is the one you want. With git
   instead:

   ```powershell
   git clone https://github.com/chocovanis/Batman-Arkham-Knight-Save-Editor.git
   cd Batman-Arkham-Knight-Save-Editor
   ```
3. **Open a terminal in that folder.** With `ak_riddler_editor.py` visible in
   Explorer, click into the address bar at the top, type `powershell`, and press
   Enter.
4. **Run it:**

   ```powershell
   python ak_riddler_editor.py
   ```

If step 4 says Python is not recognised, the PATH tick box in step 1 was missed:
re-run the Python installer, choose **Modify**, and enable it. `python --version`
should print 3.10 or higher.

### Option C — build the `.exe` yourself

If you would rather run a binary you built than one you downloaded, follow steps
1–3 of Option B, then:

```powershell
pip install pyinstaller
pyinstaller --onedir --noupx --noconsole --name "AK-Riddler-Save-Editor" --add-data "aksave/data/manifest.json;aksave/data" ak_riddler_editor.py
```

Your build appears in `dist\AK-Riddler-Save-Editor\`. Run the `.exe` from inside
that folder, `_internal` and all.

That is the exact command the released build is made with — you can read it in
[`.github/workflows/build.yml`](.github/workflows/build.yml).

---

## Where your saves live

| Store | Path |
|---|---|
| Steam | `C:\Program Files (x86)\Steam\userdata\<your id>\208650\remote\` |
| GOG / Epic | `Documents\WB Games\Batman Arkham Knight\<your id>\SaveData\` |

Files are named `BAK1Save<slot>x<rotation>.sgd`. **Slot 0 is UI slot 1**, and
each slot keeps up to three rotations (`x0`, `x1`, `x2`) — the game writes them
in turn and loads the most recent. A slot the game has only just created may
hold just one, which is normal.

The editor auto-detects your save folder and opens the save with the **most
playtime** — the game's own counter, which lives inside the file and survives
the folder copies that scramble file timestamps. That is usually your main
playthrough, but it is not necessarily the slot you are on right now. **The
status line names the slot**; use **Open Save…** if it is not the one you
want.

Both the Steam and GOG/Epic variants are supported and detected automatically
(GOG/Epic files carry an extra 4-byte prefix).

### If you install a save you downloaded

**A save file carries the slot number it belongs to inside it, at byte `0x65`, and
the game believes that rather than the filename.** Renaming someone else's
`BAK1Save0x2.sgd` to `BAK1Save2x0.sgd` does not move it to slot 3 — it still claims
slot 1, and it will hide the save you already have there. Your own save is not
deleted, but it disappears from the save list until the downloaded file is removed
or its byte is corrected.

This does not affect the editor, which edits your save where it already is and never
changes its slot. It matters only if you copy save files around by hand. If you do:
set byte `0x65` to the slot digit in the filename, keep a copy of anything you
overwrite, and fully quit and relaunch the game afterwards — the save list is only
read at startup.

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

Achievements in this game are generally awarded when a counter *changes* to the
target value, not when the game notices it is already there. If a save simply
appears at 243/243, the achievement may never fire.

Leaving one collectible uncollected puts you at **242/243**. Pick up that last
one in game and the counter ticks over normally, so the achievement unlocks the
way it would have anyway. This is on by default.

### Where it leaves it

Always the same place, and the editor tells you where in the activity log:

> **A Riddler Trophy on Bleake Island, in the warehouse across the bridge from
> Ace Chemicals.** Hit the `?` switch with the **up** arrow to raise the
> containers, then grab the trophy. Armed Riddler drones spawn; a Remote
> Batarang through the `?` with the **down** arrow crushes them.

If you want a map reference, IGN's
[Bleake Island guide](https://www.ign.com/wikis/batman-arkham-knight/Bleake_Island)
numbers this one **trophy 6** — at roughly map position (1709, 1964), listed as
needing the Remote Batarang.

**Ignore any other number you see for it.** Three different numbering schemes
name this one warehouse: the flag inside the save file, this editor's own
collectible list, and IGN's guide all count Bleake's trophies differently, and
none of them agree. The description above is the thing to trust — it is the one
trophy whose physical location this project verified in game, by picking it up
and reading what the game wrote. That is exactly why it is the one the editor
holds back.

If your save already has that trophy, the editor falls back to another plain
trophy — normally on Bleake Island, or in whatever area your save does track —
and names it in the log, but it cannot tell you where that one is.

**Honest caveat:** we were never able to test whether "leave one" is needed at
all. The only account available already held the Riddler achievement from a
genuine 243/243 playthrough, and an achievement cannot fire twice. So it is a
*conservative default based on how these achievements normally behave*, not
something this project has verified. If you already have the achievement, it
costs you nothing to turn off.

**If you still cannot find it**, turn the option off and re-run. **The game will
not necessarily mark an uncollected collectible on your map** — icons only
appear once you have interrogated the Riddler informant for that area, and the
editor does not touch informant state. Knowing the exact building is what makes
that survivable; without it, the leftover trophy was not findable without a
guide.

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

A backup copies the **whole save folder** — every `.sgd`, plus `profile.bin`
and `LBGameCache.dat` — and **Restore… puts all of them back**: every slot, not
just the one you edited. So if you edit slot 3 on Monday, play slot 1 on
Tuesday and restore on Wednesday, Tuesday's progress in slot 1 goes back too.
Restore names what it is about to overwrite and asks before it does it, refuses
while the game is running, and backs up the current state first — so it can
itself be undone.

Each backup stores a SHA-256 of every file it copied and verifies the copy
immediately. **Restore…** re-verifies every hash *before* it writes anything
back, so a corrupted backup is refused rather than half-applied. A backup whose
manifest is damaged is skipped in the list rather than taking the others with
it.

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
a heuristic scanner. It is unsigned because a code-signing certificate costs more
per year than this tool is worth.

Nothing anyone tells you can prove a stranger's binary is safe, so here is what
you can actually check, best first:

1. **Don't run the binary.** Run from source instead — **Option B**. Nothing is
   compiled and there are no dependencies to install, so there is no binary to
   trust in the first place.
2. **Build the `.exe` yourself** — **Option C**. Two commands, and it is the
   same command the release is built with.
3. **Check your download is intact.** GitHub shows a SHA-256 beside every file
   on the Releases page. To compare it, open the folder you downloaded to, click
   into the address bar, type `powershell`, press Enter, and run:

   ```powershell
   Get-FileHash AK-Riddler-Save-Editor.zip
   ```

   PowerShell prints the hash in CAPITALS; GitHub shows it in lower case behind
   a `sha256:` prefix. That difference is cosmetic — compare the letters and
   digits and ignore the case. This proves you got the file GitHub has; it does
   not prove the file is safe.
4. **Get a second opinion.** Upload the zip to virustotal.com. Upload the file
   rather than searching for its hash: a search that finds nothing means it has
   never been submitted, not that it is clean.

What the tool will and will not touch is in [SECURITY.md](SECURITY.md).

**I edited my save and nothing changed in game.**
In order of likelihood:
1. You added the edited file as a **new** save slot. The game does not reliably
   notice one. Replace a slot it already has — that is what the editor does when
   you point it at an existing save, and it is what save mods tell you to do.
2. The game was still running when you edited. Close it fully and redo the edit.
3. Steam Cloud restored its own copy over yours. Close the game, let Steam
   finish syncing, then edit and start the game from Steam.
4. You edited a different rotation than the one the game loads. The editor
   warns you when the file you opened is not the newest in its slot.

**It says it skipped an area.**
Your save has no Riddler records for that area yet, because you have not been
there. Go there once in game, save, and run the editor again to finish the set.

**It says my save cannot be edited yet.**
You have not picked up a single Riddler collectible in that save. The editor
locates your Riddler records by looking for one you already have, so a save with
none — a brand-new game, or the first hour or so before you find your first
trophy — gives it nothing to work with. Grab any one Riddler Trophy, save, and
open that save instead. One is enough.

**The counter says 243/243 but the boss fight will not start.**
That is the safety gate working as intended, not a bug. The fight also requires
Catwoman to be freed, and this tool will not fake that flag. Play up to the
point where you free her and the fight becomes available.

**Can it edit anything besides Riddler collectibles?**
No, and that is a design decision rather than an oversight. Widening the write
scope is what would make the tool capable of breaking a playthrough.

---

## Contributing / reporting a problem

Open an issue with the contents of the activity log (**Copy log**), and attach
the save file if you can — a save that reproduces the problem is usually the
only way to fix one. GitHub does not accept a `.sgd` file directly, so put it in
a zip first.

One thing to know before you paste: the log includes the full path to your save
folder, which on Steam contains your account ID. If you would rather not post
that, replace it with `...`. Everything else in the log is a record of what the
editor did, and that is the part that helps.

## Licence

Copyright © 2026 chocovanis.

GPL-3.0. See [LICENSE](LICENSE). Not affiliated with, endorsed by, or connected
to Warner Bros., Rocksteady Studios, or DC Comics. Batman: Arkham Knight is
their trademark.

**No game code, assets, text or save data is redistributed here.** The repository
is source only. Its one data file, `aksave/data/manifest.json`, holds two factual
tables about the game and no game content:

- the **18-entry Riddler puzzle table**, derived from the game's own plain-text
  `BmGame/Config/DefaultGame.ini`, which is present in every installation;
- the **315 collectible flag identifiers** (`PickedUp_CityZ_Pickup_21` and the
  like), read out of a save file that already has all of them.

`tools/build_manifest.py` regenerates the whole file, but it reads those
identifiers out of a 100%-complete save and refuses anything else — so you need
such a save as well as the game install. The human-readable names shown in the
editor are assembled from the game's own region and category names plus an
index; no third-party name list is used or shipped.
