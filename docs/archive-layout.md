# Managed archive layout

Each named profile points to an archive root chosen by the user. The root is portable between Windows and Ubuntu because the manifest contains relative paths.

```text
<ArchiveRoot>/
  Downloads/
    PGN/
    CBV/
  Extracted/
    PGN/<issue-number>/
    CBV/<issue-number>/
  Combined/
    twic-all.pgn
  .twic-archive-manager/
    manifest.json
    manifest.json.bak
    sync.lock
    logs/
```

ZIP files remain by default. A profile can turn extraction off, but the application must still validate and record downloaded ZIPs. PGNs are combined only when their managed extracted files are verified; CBVs are always retained individually and never merged.

The app must use same-filesystem `.part` files/staging locations and atomic replacement for final ZIPs, extracted directories, manifest updates, and the combined PGN.
