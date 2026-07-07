# GS-PNL-BUSINESS-INSIGHTS-A Assertions

## Source

- `docs/metric_dictionary.md` -> `MTR-PNLBIZ-001` through `MTR-PNLBIZ-005`
- `backend/app/api/routes/pnl.py`
- `backend/app/services/pnl_by_business_candidate_insights.py`
- `backend/app/services/pnl_service.py` (`pnl_by_business_ytd_envelope`, `pnl_by_business_monthly_envelope`)
- `tests/test_pnl_by_business_candidate_insights_contract.py`
- `tests/test_golden_samples_capture_ready.py`

## Required Assertions

- HTTP status is `200` when an explicit `pnl:read` scope is available.
- The top-level envelope contains `result_meta` and `result`.
- `result_meta.basis == "analytical"`.
- `result_meta.result_kind == "pnl.by_business_candidate_insights"`.
- `result_meta.formal_use_allowed == false` (hardcoded in `pnl_by_business_candidate_insights_envelope`; cannot be overridden by any caller argument).
- `result_meta.source_version == "sv_pnl_by_business_candidate_insights_2026_2026-02-28"`.
- `result_meta.rule_version == "rv_pnl_by_business_candidate_insights_v1"`.
- `result_meta.cache_version == "cv_pnl_by_business_candidate_insights_v1"`.
- `result_meta.quality_flag == "ok"`.
- `result_meta.fallback_mode == "none"`.
- `result_meta.requested_report_date == result_meta.resolved_report_date == result_meta.as_of_date == "2026-02-28"`.
- `result_meta.tables_used == ["pnl.by_business_ytd", "pnl.by_business_monthly"]` (this endpoint only re-aggregates those two envelopes; it never re-queries `fact_formal_pnl_fi` / `fact_formal_zqtz_balance_daily` directly).
- `result.concentration`, `result.negative_ftp_persistence`, and `result.share_drift` sections are all present in `result`.
- `result.concentration.hhi_pct` is `null` or within `[0, 100]`.
- `result.negative_ftp_persistence.negative_ftp_longest_streak_months <= result.negative_ftp_persistence.lookback_months` (structurally guaranteed: the streak can never exceed the number of months in the lookback window).
- Every row in `result.negative_ftp_persistence.rows[]` also satisfies `negative_ftp_longest_streak_months <= lookback_months`.

## Frozen Values

- `MTR-PNLBIZ-001` / `MTR-PNLBIZ-002`: `result.concentration.hhi_pct == "53.12"`, `result.concentration.top_n_share_pct == "100.00"` (two parent ZQTZ business types, 62.50%/37.50% YTD average-balance shares).
- `MTR-PNLBIZ-003` / `MTR-PNLBIZ-004`: `result.negative_ftp_persistence.negative_ftp_month_share_pct == "0.00"`, `result.negative_ftp_persistence.negative_ftp_longest_streak_months == 0` over the 3 observed months in the trailing 12-month window (`2025-03`..`2026-02`); the other 9 months are outside the fixture's seeded data and are treated as gaps, not zero/negative.
- `MTR-PNLBIZ-005`: `result.share_drift.rows[0].drift_pp == "-7.50"` (treasury bond share dropped from 70.00% at 2025-12-31 baseline to 62.50%) and `result.share_drift.rows[1].drift_pp == "7.50"` (policy financial bond share rose from 30.00% to 37.50%).

## Boundary

- This sample freezes the `GET /api/pnl/by-business-candidate-insights` candidate analytics DTO for `PAGE-CONTRACT-PENDING:/pnl-by-business-insights`.
- It preserves `formal_use_allowed=false`; `MTR-PNLBIZ-001` through `MTR-PNLBIZ-005` remain candidate display metrics with pending confirmation.
- It does not replace, extend, or reinterpret `PAGE-PNL-BY-BUSINESS-001` (`docs/page_contracts.md` §14.8.1), which still has no newly approved `MTR-*` metric binding in this pass.
- It does not approve a business-type concentration limit, an FTP rate caliber, or a strategic interpretation of share drift.
- Direct governance review, catalog/date evidence, manual audit closure, and business-owner approval remain separate.
