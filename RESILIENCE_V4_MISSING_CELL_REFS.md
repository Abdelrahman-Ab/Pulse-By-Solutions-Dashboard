# Resilience v4 — XLSX exports without cell references

This build fixes a real export format observed in the uploaded List of Opportunities workbook.

The workbook contains the full table, but many worksheet `<c>` XML elements omit the normal Excel `r` cell reference (for example `H3`) and the worksheet dimension incorrectly reports `A1`. The previous parser used the `r` attribute to determine a cell's column, so every reference-less cell collapsed into the same empty column key and the Opportunities header could not be detected.

The reader now:
- uses the explicit Excel cell reference when present;
- falls back to the cell's ordinal position within the row when the reference is omitted;
- preserves all existing flexible worksheet/header detection;
- preserves the mandatory Roadmap gate exactly: blank/252 Roadmap rows are excluded entirely;
- fails safely and retains the last good snapshot if a truly incompatible workbook is received.

Validated against the uploaded 2026-08-31 Opportunities workbook: 885 Roadmap-populated opportunities parsed, with zero blank-Roadmap rows in the output.
