# Resilience v3 — Roadmap-gated opportunities

This build preserves the approved business rule exactly:

- The parser robustly discovers the correct Opportunities worksheet and header row.
- It recognizes Roadmap aliases such as `Roadmap`, `Road Map`, `Roadmap Status`, and `Roadmap Stage`; harmless spacing/line-break differences are normalized.
- If no Roadmap column can be identified, refresh fails safely and the previous snapshot remains live.
- If a row's Roadmap value is blank (or the source's known missing sentinel `252`), that entire row is ignored and contributes nowhere in the dashboard.
- A nonblank Roadmap is mandatory before an opportunity row may be processed.

All other resilience protections from v2 remain in place.
