Marks Riddler collectibles as collected in a **Batman: Arkham Knight** save file,
so you can finish the Riddler content without hunting all 243 challenges by hand.
It edits Riddler collectible flags and nothing else.

## Install

1. Download `AK-Riddler-Save-Editor.zip` below.
2. Right-click it and choose **Extract All**. Extract the whole folder — do not
   run the `.exe` from inside the zip. Windows names the destination after the
   zip, so you end up with `AK-Riddler-Save-Editor` inside another folder of the
   same name; the inner one is the one you want.
3. Open the extracted folder and run **`AK-Riddler-Save-Editor.exe`**, keeping
   the `_internal` folder next to it.

Windows will probably show **"Windows protected your PC"** the first time — that
is SmartScreen reacting to an unrecognised publisher, not a detection. Click
**More info**, then **Run anyway**.

**Close Batman: Arkham Knight completely first** — all the way out, not to the
main menu. And make your own copy of your save folder before you start: the
editor takes a verified backup automatically, but your own copy is what makes a
mistake reversible.

## If your antivirus flags it

It is an unsigned PyInstaller build, and that is exactly what those look like to
a heuristic scanner. You do not have to take my word for it:

- **Don't run the binary at all.** Run from source instead — there are no
  dependencies to install, because the editor uses only what ships with Python.
  See *Option B* in the README.
- **Build the `.exe` yourself.** Two commands, and it is the exact command this
  release was built with. See *Option C*.
- **Check your download is intact.** GitHub publishes a SHA-256 next to the file
  above. Compare it by running `Get-FileHash AK-Riddler-Save-Editor.zip` in a
  PowerShell prompt opened in your downloads folder. PowerShell prints it in
  CAPITALS and GitHub shows it in lower case behind a `sha256:` prefix — compare
  the letters and digits, ignore the case.
- **Get a second opinion.** Upload the zip to virustotal.com — upload the file
  rather than searching for its hash, since a search that finds nothing means it
  has never been submitted, not that it is clean.

## Worth knowing

- Steam and GOG/Epic saves are both supported and detected automatically.
- It fills in only the areas your save has already been to and names any it
  skipped — visit a skipped area once in game, save, and run it again.
- **"Leave one collectible uncollected" is on by default**, so the achievement
  fires normally when you pick that last one up. The editor tells you which one
  it left and where to find it.
- The Riddler encounter needs **243/243 _and_ a freed Catwoman**. Setting the
  count early does not skip the story, and the content can take a few minutes of
  play to appear.
- **Restore puts back the whole save folder** — every slot, not just the one you
  edited, plus `profile.bin` and `LBGameCache.dat`. It asks first.

Full instructions, including the beginner walkthrough for running from source,
are in the [README](https://github.com/chocovanis/Batman-Arkham-Knight-Save-Editor#readme).
Licence: GPL-3.0, included in the zip.
