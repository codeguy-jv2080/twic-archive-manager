# Managed archive layout

Each profile chooses an archive root. SQLite stores profile and artifact state locally; archive files remain inside the selected root.

```text
<ArchiveRoot>/
  Downloads/
    PGN/
    CBV/
  Extracted/
    PGN/<issue>/
    CBV/<issue>/
  Combined/
    twic-all.pgn
  .twic-archive-manager/
    logs/
    sync.lock
```

Verified ZIP files remain by default. A profile can disable keeping ZIPs; deletion occurs only after verified extraction succeeds.
