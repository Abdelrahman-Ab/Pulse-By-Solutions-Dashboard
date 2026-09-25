# Opportunities refresh resilience fix

This build keeps the approved dashboard UI, desktop-on-mobile behavior, Dropbox refresh architecture, and private Vercel Blob handling unchanged.

## Fix
The List of Opportunities parser no longer assumes:
- the data is always in `xl/worksheets/sheet1.xml`
- the header is always exactly Excel row 3
- harmless header formatting/spelling variants never occur

It now auto-detects the most likely worksheet and header row from known opportunity columns, and normalizes header spacing, line breaks and punctuation for matching while preserving canonical dashboard field names.

This addresses refresh failures where Dropbox returns a valid XLSX but `process:all-workbooks` reports `List of Opportunities produced no valid opportunities.` after the workbook has been re-exported or its layout changed.

Atomic snapshot behavior remains unchanged: a failed refresh does not replace the currently published Vercel Blob snapshot.
