# Partners & Alliances Dashboard — Vercel Dropbox v12 Final

This is the Vercel deployment of the approved local v12 dashboard.

## Live data behavior

- The five Dropbox shared workbooks are the normal live source.
- There is **no hourly/automatic sync**.
- Dropbox is contacted only when a user presses **Refresh Data**.
- The current dashboard remains fully interactive while Refresh runs; the small spinner beside Refresh Data indicates the background request.
- All five workbooks are downloaded and validated first, then both processed dashboard datasets are written to Vercel Blob.
- A version manifest is published last, so users continue seeing the previous complete snapshot until the new complete snapshot is ready.
- After success, the user who pressed Refresh immediately swaps to the new data. Other users get the new shared snapshot on their next page load/section load/refresh.
- The small footer **Import Data** option remains as a backup manual override.

## D365 OPP ID

The List of Opportunities parser now reads the exact source header **`D365 OppID`** first. Legacy header variants remain as fallbacks only.

## Vercel setup

The only required backend storage is the existing **Private Vercel Blob** connection.

The project must have the Blob read-write environment variable created by the Vercel Blob connection:

`BLOB_READ_WRITE_TOKEN`

No Microsoft Graph variables, Dropbox API token, Dropbox account connection, cron job, or import password is required.

After deployment, open `/api/health`. `blobReady` must be `true`.

Then open the dashboard and press **Refresh Data** once. The refresh downloads all five Dropbox workbooks and publishes the new shared snapshot.

## Dropbox sources

The five tested Dropbox shared links are embedded server-side in `api/dropbox_source.py`.

## v12 Blob read fix

This build fixes the Vercel refresh/readback problem where a successful Blob upload was followed by `/api/data_core` returning 503.

The previous `read_private_blob()` treated `BlobClient.get()` as an HTTP response and passed `access='private'` to `get()`. In current `vercel-py`, the authenticated `BlobClient.get()` returns the downloaded body directly and private access is determined by the client's token. The revised implementation:

- reads the bytes returned by `BlobClient.get()` directly;
- uses the uploaded Blob URL for readback;
- keeps pathname fields for compatibility and diagnostics;
- verifies the manifest, core snapshot, and PO snapshot before `/api/sync_dropbox` returns HTTP 200;
- no longer hides manifest read failures as "no snapshot";
- returns the exact failing refresh stage;
- pins `vercel==0.7.2` for a deterministic deployment.

## Mobile layout

Mobile now deliberately uses the same 1920px desktop canvas. The phone browser scales the full dashboard down; responsive mobile rearrangement is not used. Users can zoom/pan as needed.
