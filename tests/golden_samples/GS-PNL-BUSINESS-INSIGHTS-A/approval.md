# GS-PNL-BUSINESS-INSIGHTS-A Approval

- Sample ID: `GS-PNL-BUSINESS-INSIGHTS-A`
- Status: `approved`
- Sample type: `formal-formula-dto-golden`
- Bound page: `PAGE-PNL-BY-BUSINESS-001`
- Source endpoint: `GET /api/pnl/by-business-insights`
- Metrics: `MTR-PNLBIZ-001`~`MTR-PNLBIZ-007`
- Owner: `组合管理/固收业务分析`
- Approver: `财务管理/资产负债管理`
- Approved at: `2026-07-15`
- Last reviewed: `2026-07-15`

## Approved Scope

This sample approves formula and DTO evidence for the following governed definitions:

1. `MTR-PNLBIZ-001` / `002`: YTD parent-business CNY-equivalent average-balance shares, HHI, and fixed Top 3 share.
2. `MTR-PNLBIZ-003` / `004`: rolling 12-calendar-month negative-FTP persistence; missing months are excluded from the denominator and break a streak; formal interpretation requires at least 6 observed months; `>= 50%` produces a descriptive warning only.
3. `MTR-PNLBIZ-005`: current YTD average-balance share versus prior-year same-period YTD; current/prior parent `row_key` union is retained, with the missing side set to 0 for entered/exited businesses.
4. `MTR-PNLBIZ-006`: formal FI untraced-row share remains `diagnostic_only` and is structurally separate from business conclusions.
5. `MTR-PNLBIZ-007`: relative scale–FTP-after-return quadrant where X is YTD CNY-equivalent average-balance share, Y is FTP-after annualized yield, both split at the current eligible-row median; at least 6 eligible rows are required; labels are descriptive and carry no allocation action.

The approved response contract uses `result_kind=pnl.by_business_insights`, `formal_use_allowed=true`, and includes `scale_yield_quadrant` for `MTR-PNLBIZ-007`.
Each required current/baseline/monthly component must also carry complete upstream lineage and `formal_source_admitted=true`; refresh-bundle or otherwise non-formal source tables do not qualify for the formal envelope.

## Evidence Boundary

- This golden sample proves the approved derived formulas, DTO shape, units, eligibility thresholds, null behavior, and separation of business analysis from diagnostic-only evidence.
- It does **not** prove that the underlying source PnL, balance, FX, manual-adjustment, or lineage facts are independently correct. Those remain subject to formal-fact reconciliation and source evidence.
- Approval does not create a regulatory or internal concentration limit.
- Approval does not create or alter the governed FTP rate caliber inherited from the upstream YTD/monthly PnL chain.
- Quadrant labels must not be translated into增配、压降、退出、考核 or limit decisions.
- `MTR-PNLBIZ-006` must not be mixed into business contribution, drag, concentration, persistence, drift, or quadrant conclusions.
- `MTR-PNLBIZ-006` source failure and no-observation states must remain explicit through `available`/`availability_reason`; an unavailable empty series is not evidence of a zero untraced share.
