# Local v31 — Accurate Active Pipeline lifecycle

This build changes only the two Active Pipeline Progress charts (Value and Margin)
plus the opportunity parser needed to expose the real Closure Date.

Lifecycle rule at each weekly marker:
- Included when Date Opened <= weekly marker
- Removed when actual Closure Date <= weekly marker
- Blank Closure Date means the opportunity remains active
- Status is not used to reconstruct the historical weekly portfolio
- Opportunities opened before 2026 contribute to the 1-Jan-2026 starting portfolio
  if they were not already closed by then
- Opportunities closed before 2026 do not contribute to 2026
- The graph still stops at the current weekly marker

Roadmap behavior:
- Comm / Ups / Pros / Early controls remain unchanged
- Rows currently tagged Won are included historically when all four pipeline
  Roadmaps are selected, because the source does not contain their former
  pre-win Roadmap. They then leave the graph on their actual Closure Date.

X-axis:
- Every weekly dashed line remains visible
- Date labels are thinned with a minimum pixel gap
- The final date label is always retained without overlapping the previous label

Existing Expected Closure Date / forecast filters remain unchanged.
The real Closure Date is parsed separately as actualClosureDate.
