# Vercel v26 — Timeline layout and hover fix

- Strategic Partners combined graph now fills the full-width panel.
- Its panel height is corrected so the 2020–2026 labels are fully visible.
- Timeline hover now converts pointer coordinates through the SVG transform,
  so it remains accurate with preserveAspectRatio, wide/narrow panels and browser zoom.
- Hover chooses the nearest actual time point rather than estimating by CSS width.
- Endpoint hover zones are expanded so first/last years are easy to reach.

Applied to:
- all Partners Performance trend graphs
- generic dashboard line charts
- Order Book historical trend
- Purchase Orders SAR Amounts Across Years

No data mappings, filters, calculations or business logic changed.
