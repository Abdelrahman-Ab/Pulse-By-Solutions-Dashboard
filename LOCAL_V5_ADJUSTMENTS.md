# Local v5 adjustments

- Added an Order Book Analysis toggle button: **Partners Leads**.
  - When active, Order Book rows are restricted to Opportunity IDs whose matching opportunity has `Channel = Partner` and `Status = Won`.
  - Match key: Opportunity ID / OPP ID only.
  - The button acts in addition to the existing Order Book global filters and Reset Filters also turns it off.
- List of Opportunities only:
  - For rows with `Status = Won`, `Actual Opp Value` is replaced by the sum of matching Order Book `OB SAR` values using OPP ID only.
  - For rows with `Status = Won`, `Actual Opp Value Margin` is replaced by the sum of matching Order Book `GM SAR` values using OPP ID only.
  - Non-Won rows retain their original opportunity values.
  - Table sorting and the two Actual-value totals use the replaced values.
  - No Opportunities Analysis KPI/chart logic was changed.
