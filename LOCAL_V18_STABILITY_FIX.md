# Local v18 stability fix

This build keeps the approved v17 dashboard changes and fixes the startup/refresh crash path.

- Dropbox downloader now tries six direct-download variants, including the original shared-link parameters and `dl.dropboxusercontent.com`.
- Strategic Partners is non-blocking: if that optional workbook is temporarily unavailable, the rest of the dashboard can still refresh normally.
- The frontend no longer dereferences missing dashboard data after an initial source/download failure.
- Switching tabs while data is unavailable now shows a controlled load failure instead of JavaScript `Cannot read properties...` errors.
- Footer/meta rendering is safe before the first successful snapshot.
- `local_cache/` is ignored by Git so locally cached confidential dashboard data is not accidentally committed.
- No business calculations, filter mappings, partner-matching logic, chart logic, or v17 UX requirements were changed.
