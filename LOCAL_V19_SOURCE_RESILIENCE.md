# Local v19 — Source resilience

- Purchase Order Summary no longer blocks first load when its Dropbox shared link returns HTML/404.
- When available, the original Purchase Order Summary is still preferred.
- Otherwise, its relationship layer is reconstructed from the current Purchase Order Details export for Order Book vendor/partner enrichment.
- Local mode keeps last-good raw source workbooks in `local_cache/source_workbooks` for future transient Dropbox failures.
- Strategic Partners remains optional/non-blocking.
- First-load failure state is hardened so tabs do not crash on missing arrays.
