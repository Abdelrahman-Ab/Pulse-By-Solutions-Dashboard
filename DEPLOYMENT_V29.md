# Vercel v29 — Active Pipeline Progress + cross-browser favicon fix

Based on approved Local v28.

Dashboard changes retained:
- Active Pipeline status logic excludes Won, Lost - Commercial, Lost - Technical.
- Date Opened is available in List of Opportunities.
- Active Pipeline Progress is one combined panel above Management Reporting.
- Value and Margin are side by side.
- Comm / Ups / Pros / Early controls are shared.
- W / NW controls are shared and centered below the Roadmap controls.
- Weekly progression stops at the end marker of the current week.
- Weekly dashed gridlines and readable x-axis labels are retained.

Favicon fix:
- The previous Vercel build output copied index.html and assets/ but did not copy favicon files
  into the configured public output directory.
- The build now explicitly copies favicon.ico, PNG favicons, Apple touch icon,
  Android/Chrome icons, and site.webmanifest into public/.
- favicon.ico is now multi-resolution (16, 32, 48, 64, 128, 256).
- HTML uses standard icon declarations for Chrome, Brave, Edge, Firefox and Apple devices.
