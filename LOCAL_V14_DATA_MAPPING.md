# Local v14 – Purchase Order Details mapping refresh

- Business with Partners dashboard logic/layout is unchanged from the approved main version.
- Purchase Order Details mapping updated for the new export: Marketunit, Project ID, Buyer, Vendor Name, Vendor Type, and Vendor ID.
- Business with Partners now exposes the 19 filters supplied by the user, in that exact order.
- Purchase Orders SAR Amounts Across Years still ignores Accounting Date and respects every other Business with Partners filter.
- Performance-only changes:
  - fast preferred-header detection for exported XLSX files (including exports that omit Excel row/cell references),
  - memoized Business with Partners filter scans,
  - removed duplicate PO filter sanitization,
  - lower-allocation option building.
- The confidential reference workbook is NOT included in this package.
