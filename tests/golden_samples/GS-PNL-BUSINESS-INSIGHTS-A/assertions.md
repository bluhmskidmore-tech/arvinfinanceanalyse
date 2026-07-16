# GS-PNL-BUSINESS-INSIGHTS-A Assertions

## Source

- `docs/metric_dictionary.md` -> `MTR-PNLBIZ-001` through `MTR-PNLBIZ-007`
- `backend/app/api/routes/pnl.py` -> `GET /api/pnl/by-business-insights`
- `backend/app/services/pnl_by_business_candidate_insights.py` -> `pnl_by_business_insights_envelope`
- `backend/app/core_finance/pnl_by_business_insights.py`
- `backend/app/services/pnl_service.py` (`pnl_by_business_ytd_envelope`, `pnl_by_business_monthly_envelope`)
- `tests/test_pnl_by_business_insights_contract.py`
- `tests/test_pnl_by_business_candidate_insights_contract.py`
- `tests/test_golden_samples_capture_ready.py`

## Required Assertions

- HTTP status is `200` when an explicit `pnl:read` scope is available.
- The approved endpoint is `GET /api/pnl/by-business-insights`; this sample must not call the legacy candidate route.
- The top-level envelope contains `result_meta` and `result`.
- `result_meta.basis == "formal"`.
- `result_meta.result_kind == "pnl.by_business_insights"`.
- `result_meta.formal_use_allowed == true`.
- `result_meta.rule_version == "rv_pnl_by_business_insights_v2"`.
- `result_meta.cache_version == "cv_pnl_by_business_insights_v2"`.
- `result_meta.quality_flag == "warning"`: the two-row fixture is below the six-row minimum for the formal scale-yield quadrant and contains only two observed months for negative-FTP persistence. This warning does not imply a fallback or permit either unavailable metric to be interpreted.
- `result_meta.fallback_mode == "none"`, `result_meta.fallback_date == null`, and `result_meta.date_basis == "formal_report_date_cutoff"`.
- `result_meta.requested_report_date == result_meta.resolved_report_date == result_meta.as_of_date == "2026-02-28"`.
- `result_meta.evidence_rows == 2`, `result_meta.source_surface == "formal_pnl"`, and `result_meta.next_drill == ["business_type", "currency_basis", "instrument"]`.
- `result.result_version == "v2"`; `baseline_requested_report_date`, `baseline_resolved_report_date`, `baseline_fallback_mode`, and `component_evidence` are present and frozen.
- The fixture has exact current-YTD, baseline-YTD, 2025-monthly, and 2026-monthly component evidence; every component reports its requested/resolved date, fallback, quality, vendor, and source version.
- `result.concentration`, `result.negative_ftp_persistence`, `result.share_drift`, `result.scale_yield_quadrant`, and `result.reconciliation_diagnostics` are all present.
- `result.concentration.currency_basis == "CNY_EQUIVALENT"` and `result.concentration.population_basis == "YTD_AVG_BALANCE_PARENT_ROWS"`; only positive YTD parent-row average balances enter the denominator.
- `result.concentration.hhi_pct` is `null` or within `[0, 100]`; the percentage representation must not be confused with the 0-10,000 HHI-points representation.
- `result.negative_ftp_persistence.warning_threshold_pct == "50"` and `minimum_observed_months == 6`.
- When `months_observed < 6`, summary/row `eligible == false`, `status == "insufficient_observations"`, and both formal share and formal longest streak are `null`.
- A row may set `warning_triggered=true` only when `months_observed >= 6` and `negative_ftp_month_share_pct >= 50`; `warning_row_count` equals the number of triggered rows.
- Missing months do not enter the negative-FTP denominator and break a streak. For eligible rows, the overall and row-level longest streak remain no greater than `lookback_months`.
- `result.share_drift.comparison_basis == "PRIOR_YEAR_SAME_PERIOD_YTD_AVG_BALANCE_SHARE"`; the baseline is the exact prior-year same-period cutoff, not prior year-end.
- Share drift is available only when both period totals are positive. New/exited zero-side handling applies only in that state; otherwise the section exposes an availability reason and nullable shares/drift instead of fabricating ±100pp.
- Available share-drift rows are aligned by the union of parent `row_key` values and expose `lifecycle_status` as `continued`, `new`, or `exited`.
- `result.scale_yield_quadrant.currency_basis == "CNY_EQUIVALENT"`, `scale_basis == "YTD_AVG_BALANCE_SHARE"`, and `yield_basis == "FTP_NET_ANNUALIZED_YIELD_PCT"`.
- A formal scale-yield quadrant is available only when at least six parent rows have positive average balance and non-null FTP-after annualized yield. When unavailable, both medians are `null` and `rows == []`.
- Every `result.reconciliation_diagnostics.rows[].untraced_share_pct` is `null` when `total_row_count == 0`, otherwise within `[0, 100]`; the row count is at most the 12-month lookback.

## Frozen Values

- `MTR-PNLBIZ-001` / `MTR-PNLBIZ-002`: `total_avg_balance == "1000.00"`, `hhi_pct == "53.12"`, and `top_n_share_pct == "100.00"`. The two current-period parent rows have YTD average-balance shares of 62.50% and 37.50%.
- `MTR-PNLBIZ-003` / `MTR-PNLBIZ-004`: the rolling window is `2025-03` through `2026-02`, but only 2026-01 and 2026-02 are observed. Overall and both populated business rows have `months_observed == 2`, `eligible == false`, `status == "insufficient_observations"`, null formal share/streak, and `warning_triggered == false`. The other ten months are gaps, not zeros.
- `MTR-PNLBIZ-005`: the exact baseline cutoff is `2025-02-28`. Policy financial bond rises from 30.00% to 37.50% (`+7.50pp`) and treasury bond falls from 70.00% to 62.50% (`-7.50pp`); both rows have `lifecycle_status == "continued"`.
- `MTR-PNLBIZ-007`: `minimum_eligible_rows == 6`, `eligible_row_count == 2`, and `total_avg_balance == "1000.00"`; therefore `available == false`, both medians are `null`, and `rows == []`.
- `MTR-PNLBIZ-006`: reconciliation remains a separate diagnostic. Its two in-window rows are `2026-01-31` and `2026-02-28`, each with `untraced_row_count == 0`, `total_row_count == 2`, and `untraced_share_pct == "0.00"`. The 2025-02-28 comparison baseline is outside this diagnostic's `2025-03` through `2026-02` window.

## Boundary

- This sample freezes the approved formal interface for `GET /api/pnl/by-business-insights` at the exact cutoff `2026-02-28` and binds the approved definitions `MTR-PNLBIZ-001` through `MTR-PNLBIZ-007`.
- It is an intentionally small, two-parent fixture. It does **not** represent, reproduce, approve, or validate the real `2026-06-30` values, population, rankings, warnings, or management conclusions.
- `formal_use_allowed=true` applies to the approved derived definitions and exact-cutoff contract. It does not approve a concentration limit, a different FTP rate caliber, materiality thresholds, or any 增配、压降、退出 recommendation.
- `MTR-PNLBIZ-006` remains diagnostic-only and structurally separate from business-analysis conclusions. Its direct formal-fact reconciliation query must not be described as a business contribution or drag calculation.
- An unavailable `MTR-PNLBIZ-007` quadrant is the required fail-closed result for fewer than six eligible rows; callers must not reconstruct a two-row quadrant in the frontend.
- Ineligible `MTR-PNLBIZ-003` / `MTR-PNLBIZ-004` values are also required fail-closed results; callers must not calculate or display the raw two-month ratio or streak as a formal conclusion.
- Page-level certification, live `2026-06-30` tie-out, and later-cutoff business-owner conclusions remain separate from this historical fixture.
