# Partners & Alliances Dashboard — Vercel Cloud Test

This project keeps the approved **v7 dashboard UI and business logic** and replaces only the static/local data layer with Vercel cloud functions.

## Current cloud sources

- List of Opportunities — OneDrive live shared link
- Order Book Values per Market Unit — OneDrive live shared link
- Targets — OneDrive live shared link
- Purchase Order Summary — OneDrive live shared link
- Purchase Order Details — OneDrive live shared link

The exact links are configured in `api/cloud_common.py`.

## How it works

- `/api/core` downloads Opportunities + Order Book + Targets in parallel, parses them server-side, gzip-compresses the processed JSON, and returns it to the dashboard.
- The normal `/api/core` response is cached at Vercel's edge for 60 seconds with stale-while-revalidate.
- Clicking **Refresh Data** calls the endpoint with `refresh=1`, bypassing the cache and reading the current OneDrive files immediately.
- `/api/purchase_orders` is lazy-loaded only when **Business with Partners** is opened. It downloads Purchase Order Summary + Details in parallel and builds the PO date relationship.
- There are no Excel snapshots in this deployment package.

## Why the response is compressed

Vercel Functions have a 4.5 MB request/response payload limit. The current processed datasets are much larger as raw JSON, but highly repetitive and compress very well. Current local validation:

- Core JSON: ~24.5 MB raw → ~0.74 MB gzip
- Purchase Orders JSON: ~19.0 MB raw → ~1.82 MB gzip

The browser automatically decompresses `Content-Encoding: gzip` responses.

## Deploy with GitHub (recommended)

1. Create a new GitHub repository, for example `partners-alliances-dashboard`.
2. Upload **the contents of this folder** to the repository root. `index.html`, `vercel.json`, and the `api` folder must be at the root.
3. Sign in to Vercel.
4. Choose **Add New → Project**.
5. Import the GitHub repository.
6. Framework preset: **Other** (if Vercel asks). Root directory: repository root.
7. No environment variables are required for this first public-link test.
8. Click **Deploy**.

## Verify deployment

After Vercel gives you a URL such as `https://partners-alliances-dashboard.vercel.app`:

1. Open `/api/health` — it should return `{"ok": true, ...}`.
2. Test each cloud workbook independently if needed:
   - `/api/source_check?source=opportunities`
   - `/api/source_check?source=orderbook`
   - `/api/source_check?source=targets`
   - `/api/source_check?source=po`
   - `/api/source_check?source=podates`
3. Open the dashboard root `/`.
4. The first uncached request can take several seconds because Vercel must download and parse the Excel files. Subsequent requests are served from the Vercel cache and should be much faster.
5. **Business with Partners** is intentionally lazy-loaded and may take longer on its first uncached opening because Purchase Order Details is the largest source.

## Live refresh test

1. Keep the Vercel dashboard open.
2. Change a recognizable record in List of Opportunities and save the OneDrive workbook.
3. Wait for OneDrive to finish saving the change.
4. Press **Refresh Data** in Opportunities Analysis.
5. Search for the modified record in List of Opportunities or verify the affected KPI.
6. Restore the original Excel value and press Refresh Data again.

For an Order Book test, change a 2026 `OB SAR` value temporarily. `Awarded` should update directly from Order Book and does not require OpportunityID matching.

## Expected baseline checks

With the test files used during development, the parser produced:

- 841 valid Opportunities
- 28,857 Order Book rows
- 30,023 Purchase Orders
- 30,023 / 30,023 PO-date matches
- Egypt 2026 Awarded reconciles to the 2026 Egypt Actual OB SAR in Order Book Analysis

The actual values on Vercel will reflect whatever is currently in the live OneDrive workbooks.

## Important production note

This test reads the current OneDrive **sharing links** directly from Vercel. If the owner changes the sharing permissions or Microsoft blocks server-side access to an anonymous/shared URL, use Microsoft Graph authentication for the production version. The dashboard UI/business logic does not need to change for that migration.
