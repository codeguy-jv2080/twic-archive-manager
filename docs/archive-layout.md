# Archive layout

The selected archive root contains only managed archive material:

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

ZIPs remain after extraction by default. When the profile turns that option off, a ZIP is deleted only after verified extraction succeeds.
