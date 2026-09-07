# Refresh resilience hardening

This build hardens the existing v12 dashboard without changing its approved UI/data model.

## Protection added

- Dropbox downloads retry automatically and reject HTML, partial ZIPs and corrupt XLSX packages.
- Excel table discovery scans worksheets and header rows instead of assuming sheet1 / fixed header positions.
- Opportunity parser accepts common harmless header variants (spacing, line breaks, Road Map, Opp ID, Market Unit, etc.).
- Targets are detected across worksheets/rows and support common market/target header variants.
- PO Details detects header-driven exports and falls back to the legacy column layout on the best matching worksheet.
- Processing errors identify the exact dataset/stage.
- Suspicious row-count collapses/explosions are rejected rather than published over the last good dashboard.
- A major D365 ID coverage collapse is rejected as likely schema drift.
- Blob writes remain atomic and are fully read back/validated before a refresh is reported as successful.
- The newest 3 verified snapshots are retained as a small rollback window. Older snapshots are cleaned up.
- Reads are self-healing: if the newest snapshot is unreadable/corrupt, the API automatically serves the next valid rollback snapshot.
- Concurrent refreshes cannot easily delete each other's just-published snapshot because cleanup retains a rollback window.
- Refresh failures explicitly tell the user the current dashboard remains safe and unchanged.

## Important limit

No parser can guarantee compatibility with an arbitrary future redesign of all five source workbooks. This build is designed to tolerate common export/reformatting changes and, when it cannot safely interpret a source, fail closed and keep serving the last known-good snapshot rather than publishing bad/empty data.
