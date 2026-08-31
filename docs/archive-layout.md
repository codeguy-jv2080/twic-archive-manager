# Archive layout

The selected archive root contains only managed archive material:

```text
<ArchiveRoot>/
  Downloads/
    PGN/
    CBV/
  Extracted/
    PGN/
    CBV/
  Combined/
    twic-all.pgn
  .twic-archive-manager/
    logs/
```

Extracted files are placed directly in the PGN or CBV folder. The TWIC issue
number in each filename identifies the issue; separate issue folders are not
created.

ZIPs remain after extraction by default. When the Saved Setup turns that option
off, the ZIP is deleted after extraction. PGN combination is optional and
creates `Combined/twic-all.pgn` only when the user runs Combine PGNs or enables
Combine-after-sync.

The app uses these actual files as the source of truth; it does not keep
separate per-issue download or extraction records in SQLite.
