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

ZIPs remain after extraction by default. During Sync or the separate Extract ZIP
action, turning that option off deletes the ZIP after extraction. The manual
Create Combined PGN button is different: it always keeps ZIPs when extracting
missing PGNs for combining.

PGN combination is optional and creates or replaces `Combined/twic-all.pgn`.
The desktop Create Combined PGN button honors an explicit issue range and uses
existing PGNs or downloaded ZIPs without downloading anything. Missing local
issues are reported; the available issues are combined. The other desktop
selection modes, the terminal combine command, and automatic combining after
Sync retain combine-all behavior. Automatic combining uses extracted PGNs only.

The app uses these actual files as the source of truth; it does not keep
separate per-issue download or extraction records in SQLite.
