# Security

This tool runs entirely offline. It makes no network connections, collects no
telemetry, and its only effect on your system is reading and writing the save
files you select, plus backups it writes next to your save folder.

## What it will and will not touch

It writes **only** `BAK1Save<slot>x<rotation>.sgd` files, and only ones you have
selected. That is an allowlist, not a blocklist:

- `profile.bin` is SHA-1 protected and is never written.
- `LBGameCache.dat` is not understood and is never written.
- `remotecache.vdf` belongs to Steam and is never written.

**Restore is the one exception, and it is deliberate.** Putting a backup back
puts back every file that backup copied: every `.sgd` in the folder — not only
the slot you edited — plus `profile.bin` and `LBGameCache.dat`. It names exactly
what it will overwrite and asks first, refuses while the game is running,
re-verifies every file's SHA-256 before it writes anything, and backs up the
current state first, so a restore can itself be undone. (`remotecache.vdf` is
never copied into a backup, so nothing writes it, Restore included.)

It also refuses to write a set of flags that could put a playthrough into a state
the game cannot resolve — trial flags, `CatCollarRemoved`, and the case-closed
flag. Those are not configurable and not exposed in the UI.

Every write is preceded by a hash-verified backup and followed by re-reading the
file back off disk to confirm it says what it should.

All of the above describes the desktop editor, which is what the release
contains. The repository also holds `aksave/cli.py`, a developer entry point. It
still refuses the forbidden flags, because that rail lives in the editing core
rather than in the interface — but it writes wherever its `--out` argument
points, and it takes no backup.

## Antivirus false positives

If your antivirus flags the packaged build, that is a known PyInstaller false
positive — it is what an unsigned, freshly-built Python executable looks like to
a heuristic scanner. It is unsigned because a code-signing certificate costs more
per year than this tool is worth.

Nothing anyone tells you can prove a stranger's binary is safe. What you can do,
in order of how much it actually settles:

1. **Don't run the binary at all.** Run from source instead:

       python ak_riddler_editor.py

   The editor has no dependencies. `pyproject.toml` declares none, and every
   import in the codebase ships with Python itself. Nothing is compiled and
   nothing is downloaded, so there is no binary to trust.

2. **Build the executable yourself** from the source in this repository. The
   README's "Option C" gives the exact command — it is the same one
   `.github/workflows/build.yml` runs to produce the release.

3. **Check your download is intact.** GitHub publishes a SHA-256 next to every
   release asset. Compare it with your copy, from a PowerShell prompt opened in
   the folder you downloaded to:

       Get-FileHash AK-Riddler-Save-Editor.zip

   `Get-FileHash` is built into Windows. It prints the hash in CAPITALS, while
   GitHub shows it in lower case behind a `sha256:` prefix — that difference is
   cosmetic, so compare the letters and digits and ignore the case. This proves
   you have the file GitHub has; it does not prove that file is safe.

4. **Get a second opinion.** Upload the zip to virustotal.com for a multi-engine
   scan. Upload the file rather than searching for its hash: a hash search that
   finds nothing means the file has never been submitted, not that it is clean.

## Reporting an issue

Open an issue on this repository, or contact the repository owner.
