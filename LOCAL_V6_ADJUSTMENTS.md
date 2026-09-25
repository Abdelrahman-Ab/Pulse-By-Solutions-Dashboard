# Local v6 adjustments

- Partners Leads no longer performs a live cross-dataset predicate during every Order Book render/filter operation.
- Clicking Partners Leads now:
  1. reads Opportunities rows where Roadmap = Won and Channel = Partner,
  2. matches them to Order Book using OPP ID / Opportunity ID,
  3. fills the existing Order Book Opportunity ID multi-select filter with those matching IDs.
- After selection, Order Book uses the normal native filter engine only.
- Clicking Partners Leads again clears only the Opportunity ID shortcut selection.
- Manual edits to the Opportunity ID filter turn off the Partners Leads active state.
- Large multi-select membership checks use a cached Set for faster filtering.
- The Local v5 List of Opportunities Won-value replacement remains unchanged.
