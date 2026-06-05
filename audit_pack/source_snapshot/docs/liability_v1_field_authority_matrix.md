# Liability V1 Field Authority Matrix

## Scope and stance

This document is a first-pass authority matrix for the 4 current liability V1 compatibility-seam interfaces:

1. `/api/risk/buckets`
2. `/api/analysis/yield_metrics`
3. `/api/analysis/liabilities/counterparty`
4. `/api/liabilities/monthly`

Current interface identity:

- All 4 endpoints are `V1 compatibility seam` outward surfaces.
- All 4 endpoints are `plain JSON` compatibility payloads, not governed `result_meta` surfaces.
- `formal_use_allowed` is therefore `false` for every exposed field in this matrix.
- V1 is a compatibility oracle only. V1 samples may bind payload shape, field presence, ordering, null behavior, display labels, and presentation units. V1 samples may not independently decide formal-sensitive semantics.

Authority precedence for semantic disputes:

1. [../AGENTS.md](../AGENTS.md)
2. [../prd-moss-agent-analytics-os.md](../prd-moss-agent-analytics-os.md)
3. [DOCUMENT_AUTHORITY.md](DOCUMENT_AUTHORITY.md)
4. `docs/MOSS-V2 系统架构说明` (repo priority slot; the tracked checkout currently does not expose this file as a standalone path)
5. [calc_rules.md](calc_rules.md)
6. [data_contracts.md](data_contracts.md)
7. [CACHE_SPEC.md](CACHE_SPEC.md)
8. V1 samples

Repo current-state navigation enters through [CURRENT_EFFECTIVE_ENTRYPOINT.md](CURRENT_EFFECTIVE_ENTRYPOINT.md), but that file is navigation-only and is not itself an authority source for semantic disputes.

Column notes:

- `basis`: initial outward basis classification for this seam field, not a governed cache/result basis.
- `allowed_source`: what source may be used to validate or derive the field in the current first pass.
- `V1_binding_level`: `strong` = V1 may strongly bind compatibility behavior, `medium` = V1 may guide presentation behavior, `weak` = V1 may only trigger investigation.
- `semantic_sensitivity`: `low`, `medium`, `high`.

## Interface identity

| interface | identity | current envelope | governed surface | notes |
|---|---|---|---|---|
| `/api/risk/buckets` | V1 compatibility seam | plain JSON | no | Snapshot-derived seam aggregate; no `result_meta` |
| `/api/analysis/yield_metrics` | V1 compatibility seam | plain JSON | no | Rate semantics are sensitive; V1 cannot settle formula ownership |
| `/api/analysis/liabilities/counterparty` | V1 compatibility seam | plain JSON | no | Counterparty exclusion and type mapping are sensitive |
| `/api/liabilities/monthly` | V1 compatibility seam | plain JSON | no | Monthly basis gate resolved as `observed` for the current seam workflow |

## Matrix

| interface | field_path | basis | formal_use_allowed | owner_layer | owner_doc | allowed_source | V1_binding_level | semantic_sensitivity |
|---|---|---|---|---|---|---|---|---|
| `/api/risk/buckets` | `report_date` | seam-request-echo | false | api/service seam | [../AGENTS.md](../AGENTS.md) | request param or latest available report date | strong | low |
| `/api/risk/buckets` | `liabilities_structure[]` | analytical-seam aggregate | false | service | [data_contracts.md](data_contracts.md) | current seam payload; snapshot rows only for compatibility reconstruction | medium | medium |
| `/api/risk/buckets` | `liabilities_structure[].name` | presentation label | false | service | [data_contracts.md](data_contracts.md) | current seam payload; V1 sample for label/order check | strong | low |
| `/api/risk/buckets` | `liabilities_structure[].amount` | analytical-seam amount | false | service | [data_contracts.md](data_contracts.md) | seam reconstruction from snapshot rows; not governed fact | weak | high |
| `/api/risk/buckets` | `liabilities_structure[].amount_yi` | presentation-unit amount | false | service | [data_contracts.md](data_contracts.md) | derived from seam amount; V1 for display-unit compatibility only | medium | medium |
| `/api/risk/buckets` | `liabilities_term_buckets[]` | analytical-seam bucket aggregate | false | service | [calc_rules.md](calc_rules.md) | seam payload plus bucket reconstruction from snapshot dates | medium | high |
| `/api/risk/buckets` | `liabilities_term_buckets[].bucket` | presentation bucket label | false | service | [calc_rules.md](calc_rules.md) | current seam payload; V1 for label/order only | strong | medium |
| `/api/risk/buckets` | `liabilities_term_buckets[].amount` | analytical-seam amount | false | service | [calc_rules.md](calc_rules.md) | seam reconstruction from snapshot rows; not governed fact | weak | high |
| `/api/risk/buckets` | `liabilities_term_buckets[].amount_yi` | presentation-unit amount | false | service | [calc_rules.md](calc_rules.md) | derived from seam amount; V1 for display-unit compatibility only | medium | medium |
| `/api/risk/buckets` | `interbank_liabilities_structure[]` | analytical-seam aggregate | false | service | [data_contracts.md](data_contracts.md) | seam payload; snapshot rows only for compatibility reconstruction | medium | medium |
| `/api/risk/buckets` | `interbank_liabilities_structure[].name` | presentation label | false | service | [data_contracts.md](data_contracts.md) | current seam payload; V1 for label/order check | strong | low |
| `/api/risk/buckets` | `interbank_liabilities_structure[].amount` | analytical-seam amount | false | service | [data_contracts.md](data_contracts.md) | seam reconstruction from `tyw_interbank_daily_snapshot` only for compatibility investigation | weak | high |
| `/api/risk/buckets` | `interbank_liabilities_structure[].amount_yi` | presentation-unit amount | false | service | [data_contracts.md](data_contracts.md) | derived from seam amount; V1 for display-unit compatibility only | medium | medium |
| `/api/risk/buckets` | `interbank_liabilities_term_buckets[]` | analytical-seam bucket aggregate | false | service | [calc_rules.md](calc_rules.md) | seam payload plus bucket reconstruction from snapshot dates | medium | high |
| `/api/risk/buckets` | `interbank_liabilities_term_buckets[].bucket` | presentation bucket label | false | service | [calc_rules.md](calc_rules.md) | current seam payload; V1 for label/order only | strong | medium |
| `/api/risk/buckets` | `interbank_liabilities_term_buckets[].amount` | analytical-seam amount | false | service | [calc_rules.md](calc_rules.md) | seam reconstruction from snapshot rows; not governed fact | weak | high |
| `/api/risk/buckets` | `interbank_liabilities_term_buckets[].amount_yi` | presentation-unit amount | false | service | [calc_rules.md](calc_rules.md) | derived from seam amount; V1 for display-unit compatibility only | medium | medium |
| `/api/risk/buckets` | `issued_liabilities_structure[]` | analytical-seam aggregate | false | service | [data_contracts.md](data_contracts.md) | seam payload; snapshot rows only for compatibility reconstruction | medium | medium |
| `/api/risk/buckets` | `issued_liabilities_structure[].name` | presentation label | false | service | [data_contracts.md](data_contracts.md) | current seam payload; V1 for label/order check | strong | low |
| `/api/risk/buckets` | `issued_liabilities_structure[].amount` | analytical-seam amount | false | service | [data_contracts.md](data_contracts.md) | seam reconstruction from issuance-like snapshot rows; not governed fact | weak | high |
| `/api/risk/buckets` | `issued_liabilities_structure[].amount_yi` | presentation-unit amount | false | service | [data_contracts.md](data_contracts.md) | derived from seam amount; V1 for display-unit compatibility only | medium | medium |
| `/api/risk/buckets` | `issued_liabilities_term_buckets[]` | analytical-seam bucket aggregate | false | service | [calc_rules.md](calc_rules.md) | seam payload plus bucket reconstruction from snapshot dates | medium | high |
| `/api/risk/buckets` | `issued_liabilities_term_buckets[].bucket` | presentation bucket label | false | service | [calc_rules.md](calc_rules.md) | current seam payload; V1 for label/order only | strong | medium |
| `/api/risk/buckets` | `issued_liabilities_term_buckets[].amount` | analytical-seam amount | false | service | [calc_rules.md](calc_rules.md) | seam reconstruction from snapshot rows; not governed fact | weak | high |
| `/api/risk/buckets` | `issued_liabilities_term_buckets[].amount_yi` | presentation-unit amount | false | service | [calc_rules.md](calc_rules.md) | derived from seam amount; V1 for display-unit compatibility only | medium | medium |
| `/api/analysis/yield_metrics` | `report_date` | seam-request-echo | false | api/service seam | [../AGENTS.md](../AGENTS.md) | request param or latest available report date | strong | low |
| `/api/analysis/yield_metrics` | `kpi` | analytical-seam object | false | service | [CACHE_SPEC.md](CACHE_SPEC.md) | current seam payload only | strong | medium |
| `/api/analysis/yield_metrics` | `kpi.asset_yield` | analytical-seam rate | false | service | [calc_rules.md](calc_rules.md) | seam reconstruction from snapshot rows; semantic disputes escalate to rules, not V1 | weak | high |
| `/api/analysis/yield_metrics` | `kpi.liability_cost` | analytical-seam rate | false | service | [calc_rules.md](calc_rules.md) | seam reconstruction from liability rows; semantic disputes escalate to rules, not V1 | weak | high |
| `/api/analysis/yield_metrics` | `kpi.market_liability_cost` | analytical-seam rate | false | service | [calc_rules.md](calc_rules.md) | seam reconstruction from market-liability subset; V1 only for presentation compatibility | weak | high |
| `/api/analysis/yield_metrics` | `kpi.nim` | analytical-seam derived rate | false | service | [calc_rules.md](calc_rules.md) | derived from seam rates; formal interpretation must not come from V1 | weak | high |
| `/api/analysis/liabilities/counterparty` | `report_date` | seam-request-echo | false | api/service seam | [../AGENTS.md](../AGENTS.md) | request param or latest available report date | strong | low |
| `/api/analysis/liabilities/counterparty` | `total_value` | analytical-seam amount | false | service | [data_contracts.md](data_contracts.md) | seam reconstruction from filtered liability rows; exclusion logic checked against rules | weak | high |
| `/api/analysis/liabilities/counterparty` | `top_10[]` | analytical-seam ranking | false | service | [calc_rules.md](calc_rules.md) | current seam payload plus filtered liability rows | medium | high |
| `/api/analysis/liabilities/counterparty` | `top_10[].name` | seam entity label | false | service | [data_contracts.md](data_contracts.md) | current seam payload; V1 may bind ranking membership and label presentation | strong | medium |
| `/api/analysis/liabilities/counterparty` | `top_10[].value` | analytical-seam amount | false | service | [data_contracts.md](data_contracts.md) | seam reconstruction from filtered liability rows; not governed fact | weak | high |
| `/api/analysis/liabilities/counterparty` | `top_10[].type` | analytical-seam classification | false | service | [calc_rules.md](calc_rules.md) | current seam payload plus classification heuristic; V1 only as compatibility check | medium | high |
| `/api/analysis/liabilities/counterparty` | `top_10[].weighted_cost` | analytical-seam rate | false | service | [calc_rules.md](calc_rules.md) | seam reconstruction from filtered liability rows; formal meaning cannot come from V1 | weak | high |
| `/api/analysis/liabilities/counterparty` | `by_type[]` | analytical-seam grouping | false | service | [calc_rules.md](calc_rules.md) | current seam payload plus grouped liability rows | medium | medium |
| `/api/analysis/liabilities/counterparty` | `by_type[].name` | seam classification label | false | service | [calc_rules.md](calc_rules.md) | current seam payload; V1 for label/order compatibility | strong | medium |
| `/api/analysis/liabilities/counterparty` | `by_type[].value` | analytical-seam amount | false | service | [data_contracts.md](data_contracts.md) | seam reconstruction from filtered liability rows; not governed fact | weak | high |
| `/api/liabilities/monthly` | `year` | seam-request-echo | false | api/service seam | [../AGENTS.md](../AGENTS.md) | request param or default selected year | strong | low |
| `/api/liabilities/monthly` | `months[]` | observed analytical-seam monthly series | false | service | [calc_rules.md](calc_rules.md) | current seam payload under observed-day basis | medium | high |
| `/api/liabilities/monthly` | `months[].month` | seam month key | false | service | [../AGENTS.md](../AGENTS.md) | current seam payload; V1 for ordering and formatting | strong | low |
| `/api/liabilities/monthly` | `months[].month_label` | presentation label | false | service | [../AGENTS.md](../AGENTS.md) | current seam payload; V1 for display label compatibility only | strong | low |
| `/api/liabilities/monthly` | `months[].avg_total_liabilities` | observed analytical-seam monthly average | false | service | [calc_rules.md](calc_rules.md) | current seam payload under observed-day basis | weak | high |
| `/api/liabilities/monthly` | `months[].avg_interbank_liabilities` | observed analytical-seam monthly average | false | service | [calc_rules.md](calc_rules.md) | current seam payload under observed-day basis | weak | high |
| `/api/liabilities/monthly` | `months[].avg_issued_liabilities` | observed analytical-seam monthly average | false | service | [calc_rules.md](calc_rules.md) | current seam payload under observed-day basis | weak | high |
| `/api/liabilities/monthly` | `months[].avg_liability_cost` | observed analytical-seam monthly rate | false | service | [calc_rules.md](calc_rules.md) | current seam payload under observed-day basis | weak | high |
| `/api/liabilities/monthly` | `months[].mom_change` | analytical-seam derived amount | false | service | [calc_rules.md](calc_rules.md) | derived from seam monthly averages; V1 only for compatibility check | weak | high |
| `/api/liabilities/monthly` | `months[].mom_change_pct` | analytical-seam derived percent | false | service | [calc_rules.md](calc_rules.md) | derived from seam monthly averages; V1 only for compatibility check | weak | high |
| `/api/liabilities/monthly` | `months[].counterparty_top10[]` | observed analytical-seam ranking | false | service | [calc_rules.md](calc_rules.md) | current seam payload under observed-day basis | medium | high |
| `/api/liabilities/monthly` | `months[].counterparty_top10[].name` | seam entity label | false | service | [data_contracts.md](data_contracts.md) | current seam payload; V1 may bind ranking membership and label presentation | strong | medium |
| `/api/liabilities/monthly` | `months[].counterparty_top10[].avg_value` | observed analytical-seam monthly average | false | service | [calc_rules.md](calc_rules.md) | current seam payload under observed-day basis | weak | high |
| `/api/liabilities/monthly` | `months[].counterparty_top10[].proportion` | analytical-seam presentation percent | false | service | [calc_rules.md](calc_rules.md) | derived from seam monthly averages; V1 for display compatibility only | medium | medium |
| `/api/liabilities/monthly` | `months[].counterparty_top10[].weighted_cost` | analytical-seam rate | false | service | [calc_rules.md](calc_rules.md) | current seam payload only until monthly basis gate is resolved | weak | high |
| `/api/liabilities/monthly` | `months[].counterparty_top10[].type` | analytical-seam classification | false | service | [calc_rules.md](calc_rules.md) | current seam payload plus classification heuristic | medium | high |
| `/api/liabilities/monthly` | `months[].by_institution_type[]` | observed analytical-seam grouping | false | service | [calc_rules.md](calc_rules.md) | current seam payload under observed-day basis | medium | medium |
| `/api/liabilities/monthly` | `months[].by_institution_type[].type` | seam classification label | false | service | [calc_rules.md](calc_rules.md) | current seam payload; V1 for label/order compatibility | strong | medium |
| `/api/liabilities/monthly` | `months[].by_institution_type[].avg_value` | observed analytical-seam monthly average | false | service | [calc_rules.md](calc_rules.md) | current seam payload under observed-day basis | weak | high |
| `/api/liabilities/monthly` | `months[].structure_overview[]` | observed analytical-seam grouping | false | service | [calc_rules.md](calc_rules.md) | current seam payload under observed-day basis | medium | medium |
| `/api/liabilities/monthly` | `months[].structure_overview[].category` | presentation label | false | service | [calc_rules.md](calc_rules.md) | current seam payload; V1 for label/order compatibility | strong | low |
| `/api/liabilities/monthly` | `months[].structure_overview[].avg_balance` | observed analytical-seam monthly average | false | service | [calc_rules.md](calc_rules.md) | current seam payload under observed-day basis | weak | high |
| `/api/liabilities/monthly` | `months[].structure_overview[].proportion` | analytical-seam presentation percent | false | service | [calc_rules.md](calc_rules.md) | derived from seam monthly averages; V1 for display compatibility only | medium | medium |
| `/api/liabilities/monthly` | `months[].term_buckets[]` | observed analytical-seam bucket aggregate | false | service | [calc_rules.md](calc_rules.md) | current seam payload under observed-day basis | medium | high |
| `/api/liabilities/monthly` | `months[].term_buckets[].bucket` | presentation bucket label | false | service | [calc_rules.md](calc_rules.md) | current seam payload; V1 for label/order compatibility | strong | medium |
| `/api/liabilities/monthly` | `months[].term_buckets[].avg_balance` | observed analytical-seam monthly average | false | service | [calc_rules.md](calc_rules.md) | current seam payload under observed-day basis | weak | high |
| `/api/liabilities/monthly` | `months[].interbank_by_type[]` | observed analytical-seam grouping | false | service | [calc_rules.md](calc_rules.md) | current seam payload under observed-day basis | medium | medium |
| `/api/liabilities/monthly` | `months[].interbank_by_type[].category` | presentation label | false | service | [calc_rules.md](calc_rules.md) | current seam payload; V1 for label/order compatibility | strong | low |
| `/api/liabilities/monthly` | `months[].interbank_by_type[].avg_balance` | observed analytical-seam monthly average | false | service | [calc_rules.md](calc_rules.md) | current seam payload under observed-day basis | weak | high |
| `/api/liabilities/monthly` | `months[].interbank_by_type[].proportion` | analytical-seam presentation percent | false | service | [calc_rules.md](calc_rules.md) | derived from seam monthly averages; V1 for display compatibility only | medium | medium |
| `/api/liabilities/monthly` | `months[].interbank_term_buckets[]` | observed analytical-seam bucket aggregate | false | service | [calc_rules.md](calc_rules.md) | current seam payload under observed-day basis | medium | high |
| `/api/liabilities/monthly` | `months[].interbank_term_buckets[].bucket` | presentation bucket label | false | service | [calc_rules.md](calc_rules.md) | current seam payload; V1 for label/order compatibility | strong | medium |
| `/api/liabilities/monthly` | `months[].interbank_term_buckets[].avg_balance` | observed analytical-seam monthly average | false | service | [calc_rules.md](calc_rules.md) | current seam payload under observed-day basis | weak | high |
| `/api/liabilities/monthly` | `months[].issued_by_type[]` | observed analytical-seam grouping | false | service | [calc_rules.md](calc_rules.md) | current seam payload under observed-day basis | medium | medium |
| `/api/liabilities/monthly` | `months[].issued_by_type[].category` | presentation label | false | service | [calc_rules.md](calc_rules.md) | current seam payload; V1 for label/order compatibility | strong | low |
| `/api/liabilities/monthly` | `months[].issued_by_type[].avg_balance` | observed analytical-seam monthly average | false | service | [calc_rules.md](calc_rules.md) | current seam payload under observed-day basis | weak | high |
| `/api/liabilities/monthly` | `months[].issued_by_type[].proportion` | analytical-seam presentation percent | false | service | [calc_rules.md](calc_rules.md) | derived from seam monthly averages; V1 for display compatibility only | medium | medium |
| `/api/liabilities/monthly` | `months[].issued_term_buckets[]` | observed analytical-seam bucket aggregate | false | service | [calc_rules.md](calc_rules.md) | current seam payload under observed-day basis | medium | high |
| `/api/liabilities/monthly` | `months[].issued_term_buckets[].bucket` | presentation bucket label | false | service | [calc_rules.md](calc_rules.md) | current seam payload; V1 for label/order compatibility | strong | medium |
| `/api/liabilities/monthly` | `months[].issued_term_buckets[].avg_balance` | observed analytical-seam monthly average | false | service | [calc_rules.md](calc_rules.md) | current seam payload under observed-day basis | weak | high |
| `/api/liabilities/monthly` | `months[].counterparty_details[]` | observed analytical-seam ranking detail | false | service | [calc_rules.md](calc_rules.md) | current seam payload under observed-day basis | medium | high |
| `/api/liabilities/monthly` | `months[].counterparty_details[].name` | seam entity label | false | service | [data_contracts.md](data_contracts.md) | current seam payload; V1 may bind ranking membership and label presentation | strong | medium |
| `/api/liabilities/monthly` | `months[].counterparty_details[].avg_value` | observed analytical-seam monthly average | false | service | [calc_rules.md](calc_rules.md) | current seam payload under observed-day basis | weak | high |
| `/api/liabilities/monthly` | `months[].counterparty_details[].proportion` | analytical-seam presentation percent | false | service | [calc_rules.md](calc_rules.md) | derived from seam monthly averages; V1 for display compatibility only | medium | medium |
| `/api/liabilities/monthly` | `months[].counterparty_details[].weighted_cost` | analytical-seam rate | false | service | [calc_rules.md](calc_rules.md) | current seam payload only until monthly basis gate is resolved | weak | high |
| `/api/liabilities/monthly` | `months[].counterparty_details[].type` | analytical-seam classification | false | service | [calc_rules.md](calc_rules.md) | current seam payload plus classification heuristic | medium | high |
| `/api/liabilities/monthly` | `months[].num_days` | observed analytical-seam basis counter | false | service | [calc_rules.md](calc_rules.md) | current seam payload under observed-day basis | weak | high |
| `/api/liabilities/monthly` | `ytd_avg_total_liabilities` | observed analytical-seam yearly average | false | service | [calc_rules.md](calc_rules.md) | current seam payload under observed-day basis | weak | high |
| `/api/liabilities/monthly` | `ytd_avg_liability_cost` | observed analytical-seam yearly rate | false | service | [calc_rules.md](calc_rules.md) | current seam payload under observed-day basis | weak | high |

## Open first-pass gaps

- This matrix documents current exposed fields only. It does not yet declare a governed outward contract.
- `/api/liabilities/monthly` basis gate is now resolved as `observed` for seam comparison. This does not by itself grant semantic approval to numeric values.
- Any future promotion from compatibility seam to governed surface must add `result_meta`, explicit outward `basis`, and cache identity per [CACHE_SPEC.md](CACHE_SPEC.md).
