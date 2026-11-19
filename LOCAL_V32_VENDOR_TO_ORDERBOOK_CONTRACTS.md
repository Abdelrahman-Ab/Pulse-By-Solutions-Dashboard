# Local v32 — Vendor to Order Book Contract ID synchronization

Behavior:
- Business with Partners remains the source Purchase Order Details filter experience.
- When one or more Vendor Name values are selected, the dashboard derives the Contract IDs
  available in the current Business with Partners scope.
- Those Contract IDs are automatically selected in Order Book Analysis -> Contract ID.
- Only Contract IDs that actually exist in the Order Book dataset are transferred.
- Other active Business with Partners filters can further narrow the synchronized contracts.
- Changing the Vendor or other Business with Partners filters refreshes the synchronized Contract IDs.
- Clearing the Vendor clears the synchronized Order Book Contract ID selection.
- A manual edit of Order Book -> Contract ID releases the automatic-sync ownership so the user can override it.
- Existing Partners Leads behavior, filters, charts, and all v31 lifecycle logic remain unchanged.
