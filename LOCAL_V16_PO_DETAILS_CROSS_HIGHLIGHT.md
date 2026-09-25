# Local v16 — PO Details + Cross-Highlighting

This local test build is based on the approved v15 performance version.

## Added
- Fifth `PO Details` tab backed by Purchase Order Details.
- Same Purchase Order global filters as Business with Partners.
- Searchable/sortable live table with lazy row rendering for responsiveness.
- Static bottom summary: Sum of PO SAR, distinct Purchase Orders, Suppliers, and Vendors.

## Chart interaction change
- Chart clicks no longer write into Global Filters.
- Clickable chart elements now cross-highlight related records within the same analytical section.
- Full values remain visible in a faded base; the related share is overlaid at full strength.
- Clicking the same selection again clears the highlight.
- Tooltips show Actual and Highlighted values when a highlight is active.

## Purchase Orders Across Years
- Logic remains unchanged: Accounting Date is ignored; all other Business with Partners filters apply.
- Visual changed to a filled area / line chart.

## Performance
- v15 lazy filter-option loading and filter/result caches are preserved.
- PO Details renders rows in chunks while scrolling instead of creating all table rows at once.
