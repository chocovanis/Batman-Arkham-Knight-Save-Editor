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

It also refuses to write a set of flags that could put a playthrough into a state
the game cannot resolve — trial flags, `CatCollarRemoved`, and the case-closed
flag. Those are not configurable and not exposed in the UI.

Every write is preceded by a hash-verified backup and followed by re-reading the
file back off disk to confirm it says what it should.

## Antivirus false positives

If your antivirus flags the packaged build, that is a known PyInstaller false
positive — it is what an unsigned, freshly-built Python executable looks like to
a heuristic scanner. The full source is in this repository, and release binaries
are built by GitHub Actions with build provenance attestation. Verify one with:

    gh attestation verify <file> -R chocovanis/Batman-Arkham-Knight-Save-Editor

You can also skip the binary entirely and run from source:

    python ak_riddler_editor.py

## Reporting an issue

Open an issue on this repository, or contact the repository owner.
