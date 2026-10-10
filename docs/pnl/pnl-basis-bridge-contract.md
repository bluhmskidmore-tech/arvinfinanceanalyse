# PnL Basis Bridge Contract

## Scope

- Endpoint: `GET /api/pnl/basis-bridge?report_date=YYYY-MM-DD`
- Result kind: `pnl.basis_bridge`
- Basis: `analytical`; `formal_use_allowed=false`; `quality_flag=warning` while the crosswalk remains pending.
- Purpose: reconcile the system by-business operating view to formal recognized PnL and formal product-category FTP-after income without pretending that unlike scopes are the same metric.
- This diagnostic creates no new `MTR-*` metric and does not replace `/api/pnl/overview`, `/api/pnl/by-business-monthly`, or `/ui/pnl/product-category`.

## Source fields

| Meaning | Source |
| --- | --- |
| System gross/manual/FTP/FTP-net | `/api/pnl/by-business-monthly` month `summary` |
| Unallocated formal PnL | `/api/pnl/by-business-monthly` month `unallocated_pnl` |
| Monthly formal recognized PnL | `/api/pnl/overview.total_pnl` |
| YTD formal recognized PnL | Sum of month `source_total_pnl - manual_adjustment` |
| Product gross cash | `/ui/pnl/product-category.grand_total.cnx_cash` |
| Product FTP | `grand_total.cny_ftp + grand_total.foreign_ftp` |
| Product FTP-after income | `grand_total.business_net_income` |

All amounts use CNY yuan and the same requested/resolved `report_date`. A date mismatch fails closed.

## Bridge identities

```text
system_ftp_net = system_gross - system_ftp_cost
product_ftp_net = product_gross_cash - product_ftp_cost

formal_recognized
  = system_gross
  - system_manual_adjustment
  + system_unallocated_pnl
  + rounding_alignment

product_ftp_net
  = system_ftp_net
  - system_manual_adjustment
  + system_unallocated_pnl
  + rounding_alignment
  + formal_to_product_gross_scope_mapping_residual
  + (system_ftp_cost - product_ftp_cost)
```

Every arithmetic closure residual must be within `0.01` yuan. A breach raises an error rather than returning a misleading bridge.

## Interpretation boundary

- `system_to_formal_gross.mapping_status=not_required`: the components are directly tied to source totals and rounding.
- `system_to_product_ftp_net.mapping_status=pending_crosswalk`: the bridge closes arithmetically, but `formal_to_product_gross_scope_mapping_residual` is not a business attribution.
- Pending governance evidence is an approved product–account–business-type crosswalk and an FTP rate/days/ADB-denominator split. Until then, the residual must remain visible and must not be renamed as a specific product contribution.

## Tests

- `tests/test_pnl_basis_bridge_contract.py`
- `tests/test_pnl_api_contract.py` and product-category tests remain the upstream source contracts.
