# Local v15 — Interactive Filter Performance

Business logic and dashboard visuals are unchanged. This build only optimizes interaction speed in Order Book Analysis and Business with Partners.

Optimizations:
- Lazy-load filter option lists only for the dropdown that is actually open.
- Cache Order Book and Purchase Order filtered row sets by current filter signature.
- Cache cascading dropdown option lists.
- Compile active filter selections once per filtering pass instead of rebuilding them for every row.
- Coalesce rapid checkbox changes into one browser-frame redraw.
- Run filter sanitization only when the data snapshot changes, rather than on every click.
- Cache the static Purchase Orders historical trend axis/year baseline instead of recomputing it on every filter action.
- All caches are cleared automatically on data reload/refresh.
