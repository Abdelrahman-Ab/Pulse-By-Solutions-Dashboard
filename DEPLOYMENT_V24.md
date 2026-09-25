# Vercel v24 — Strategic Partners buttons fix

This build is based on approved Local v23.

Only functional fix:
- The large **Strategic Partners** chart now respects its own independent
  Egypt / KSA / Growing Markets / Total buttons.
- Turning a series off hides that line and recalculates the chart scale from
  the remaining visible series.
- Turning it back on restores the line.
- The 20 individual partner charts keep their existing independent controls.

Deployment preparation:
- local-only launcher/server files removed;
- existing Vercel API, Dropbox processing, Blob snapshot architecture,
  mappings, filters, calculations, cross-highlighting and UI retained.
