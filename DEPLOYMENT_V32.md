# Vercel v32 — Vendor to Order Book Contract ID synchronization

Based on the approved Local v32.

New behavior:
- Selecting Vendor Name in Business with Partners derives the related Contract IDs
  from the current Purchase Order Details scope.
- These Contract IDs are automatically selected in Order Book Analysis -> Contract ID.
- Only Contract IDs that exist in the Order Book dataset are transferred.
- Other active Business with Partners filters can further narrow the synchronized contracts.
- Clearing Vendor clears the synchronized Order Book Contract ID selection.
- Manually changing Order Book -> Contract ID releases the automatic sync for user override.
- Existing Partners Leads behavior remains unchanged.

All v31 lifecycle logic, filters, chart behavior, cross-highlighting, favicon handling,
and Vercel/Blob architecture are preserved.

Local-only runtime files and .git metadata are intentionally excluded.
