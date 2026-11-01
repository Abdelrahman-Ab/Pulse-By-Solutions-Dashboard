# Vercel v31 — Accurate Active Pipeline Lifecycle

Based on the approved Local v31.

Active Pipeline Progress changes:
- Only the two progress charts (Value and Margin) use the new historical lifecycle logic.
- Date Opened adds an opportunity to the historical active portfolio.
- Actual Closure Date removes it from the historical active portfolio.
- Blank Closure Date means it remains active through the current weekly marker.
- Current Status is not used to reconstruct historical weekly snapshots.
- Opportunities opened before 2026 are included in the 1-Jan-2026 opening balance if still open then.
- Opportunities already closed before 2026 do not contribute to the 2026 history.
- The charts can now rise and fall as opportunities open and close.
- W / NW and Comm / Ups / Pros / Early controls remain.
- The graphs still stop at the current weekly marker.
- The last X-axis date label is protected from overlapping the previous label.

Data model:
- Existing Expected Closure Date logic remains untouched.
- Real Closure Date is parsed separately as actualClosureDate.

Deployment:
- Local-only launcher/runtime files are removed.
- .git metadata is intentionally excluded.
- Existing Vercel / API / Blob architecture is retained.
