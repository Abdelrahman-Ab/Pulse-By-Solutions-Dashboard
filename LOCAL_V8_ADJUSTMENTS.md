# Local v8 adjustments

- Undid only the prior List of Opportunities Order Book value override.
  - Actual Opp Value is again sourced from the Opportunities data.
  - Actual Opp Value Margin is again sourced from the Opportunities data.
  - Sorting and totals use those original Opportunities fields again.
- Partners Leads logic is unchanged: Opportunities with Roadmap = Won and Channel = Partner provide the OPP IDs selected in the Order Book Opportunity ID filter.
- Moved Partners Leads from the Order Book section header into the Global Filters footer at the far-right side.
- Restyled Partners Leads with the dashboard secondary pink colour.
- Local-only build; start.bat retained.
