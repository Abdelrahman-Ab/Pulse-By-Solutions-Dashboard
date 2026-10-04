# Local v28 — Active Pipeline Progress layout refinement

Changes from Local v27:
- Active Pipeline Progress is now one global panel immediately above Management Reporting.
- Value and Margin charts are side by side inside the same panel.
- Shared Comm / Ups / Pros / Early controls are centered above the charts.
- Shared W / NW controls are centered directly underneath the Roadmap controls.
- The timeline now stops at the end marker of the current dashboard week.
  With 1-Jan-2026 as the weekly origin, 4-Oct-2026 cuts at 8-Oct-2026.
- Future weeks are not drawn and future Date Opened records are not counted yet.
- Every displayed week has a vertical dashed gridline.
- X-axis labels are deliberately thinned while keeping first/final markers visible,
  so the two half-width charts remain bold and readable.
- Active status logic, Date Opened parsing and all other v27/v26 behavior are retained.
