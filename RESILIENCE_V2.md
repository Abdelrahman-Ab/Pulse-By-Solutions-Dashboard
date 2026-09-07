# Resilience v2

This build removes Roadmap as a hard prerequisite for an opportunity row.

Changes:
- scans up to 5000 rows on every worksheet for the opportunity table
- recognizes broader Opportunity ID / D365 / customer / topic / roadmap aliases
- accepts opportunity rows based on multiple independent business fields
- missing or renamed Roadmap becomes `Unassigned` rather than deleting the row
- keeps all existing Dropbox retry, XLSX validation, private Blob verification, atomic publish, snapshot fallback, and desktop-on-mobile behavior
- pipelineVersion reports `resilient-v2`
