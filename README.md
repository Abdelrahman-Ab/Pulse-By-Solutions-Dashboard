# Local Order Book Analysis update

This package is the local test build requested before the Vercel deployment build.

## Run
Double-click `start.bat`.

On first run, the local server downloads and processes the five configured source workbooks. After a successful run it keeps the last good local snapshot under `local_cache/`; future launches can open immediately and `Refresh Data` requests a fresh full snapshot.

## Frozen sections
The approved **Opportunities Analysis** and **List of Opportunities** calculations/layout were not redesigned as part of this update. Only the visible internal/source notes requested for removal were cleaned up globally.

## Order Book Analysis
- Order Book global filters use the same searchable multi-select/cross-filtering behavior as Opportunities Analysis.
- Awarding Date uses Year > Quarter > Month hierarchy and the annual trend intentionally ignores only Awarding Date while honoring all other Order Book filters.
- Vendor Name and Partner Name are joined from Purchase Order Summary using Contract ID without duplicating Order Book rows/values.
- GM/CM remains a section-level margin-basis toggle.
- KPI row: OB SAR, OB GM/CM SAR, GM/CM%, Contracts, Vendors.
- New chart layout, independent Vertical/Sector controls, multi-select trend metrics, fixed Market Unit colors, Top N Contracts, and Top N Customers.


### KPI adjustment
- The fifth Order Book KPI is **Vendors**.
- It counts unique matched `Vendor Name` values from Purchase Orders after the Contract ID relationship is applied. Repeated occurrences are counted once.
