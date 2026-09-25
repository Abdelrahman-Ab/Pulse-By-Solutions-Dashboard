# Local v23 — Empty filter search fields

This update changes only filter search-box behavior.

Across all sections:
- after Clear, the search box is empty;
- after selecting or deselecting any option, the search box is empty;
- after Select shown, the current search is used first, then the search box is cleared;
- any stale literal `Unassigned` value is suppressed before rendering and on focus.

Applies to Opportunities Analysis, List of Opportunities, Order Book Analysis,
Business with Partners, PO Details, and Partners Performance.

No calculation, chart, data mapping, cross-highlight, or business logic was changed.
