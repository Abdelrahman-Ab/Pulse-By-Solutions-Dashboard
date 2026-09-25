# Vercel v25 — Purchase Order Summary removed

Purchase Order Summary has been deleted from the dashboard architecture.

Refresh Data now uses:
1. List of Opportunities
2. Order Book Values per Market Unit
3. Targets
4. Purchase Order Details
5. Strategic Partners

Purchase Order Details is now the authoritative source for:
- Business with Partners
- PO Details
- Partners Performance
- the compact vendor/partner relationship layer used to enrich Order Book

The refresh endpoint no longer requests or references the deleted Purchase Order Summary Dropbox link.
Manual Import also no longer offers Purchase Order Summary.

All v24 UI behavior, filters, calculations, Strategic Partners controls and performance optimizations are otherwise retained.
