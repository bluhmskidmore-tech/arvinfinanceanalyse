# GS-LEDGER-PNL-SUMMARY-A Assertions

## Source

- `docs/page_contracts.md` -> `PAGE-LEDGER-PNL-001`
- `docs/metric_dictionary.md` -> `MTR-LPN-001` through `MTR-LPN-003`
- `backend/app/api/routes/ledger_pnl.py`
- `backend/app/services/ledger_pnl_service.py`
- `tests/test_ledger_pnl_service.py`
- `tests/test_golden_samples_capture_ready.py`

## Required Assertions

- HTTP status is `200`.
- The top-level envelope contains `result_meta` and `result`.
- `result_meta.basis == "ledger"`.
- `result_meta.result_kind == "ledger_pnl.summary"`.
- `result_meta.formal_use_allowed == false`.
- `result_meta.source_version == "sv_ledger_pnl_summary_gs_a"`.
- `result_meta.rule_version == "rv_ledger_pnl_v1"`.
- `result_meta.cache_version == "cv_ledger_pnl_v1"`.
- `result_meta.quality_flag == "ok"`.
- `result_meta.fallback_mode == "none"`.
- `result_meta.requested_report_date == "2026-04-30"`.
- `result_meta.resolved_report_date == "2026-04-30"`.
- `result_meta.as_of_date == "2026-04-30"`.
- `result_meta.date_basis == "ledger_report_date"`.
- `result_meta.filters_applied == {"report_date": "2026-04-30", "currency": "ALL"}`.
- `result_meta.tables_used == ["qdb_general_ledger_workbook"]`.
- `result_meta.evidence_rows == 2`.

## Frozen Values

- `MTR-LPN-001`: `result.ledger_monthly_pnl_core.yuan == "10"`.
- `MTR-LPN-002`: `result.ledger_monthly_pnl_all.yuan == "10"`.
- `MTR-LPN-003`: `result.ledger_net_assets.yuan == "70"`.
- `result.ledger_total_assets.yuan == "150"`.
- `result.ledger_total_liabilities.yuan == "80"`.
- `result.by_currency` contains `CNX=3` and `CNY=7`.
- `result.by_account` contains `51401000001=7` and `51601000001=3`.

## Boundary

- This sample freezes the `GET /api/ledger-pnl/summary` page-level summary DTO for `PAGE-LEDGER-PNL-001`.
- It is a capture-ready sample awaiting approval, not an approved business-contract sample.
- It preserves `formal_use_allowed=false`; `MTR-LPN-001` through `MTR-LPN-003` remain candidate display metrics with pending confirmation.
- It does not replace `/api/pnl/overview`, `/product-category-pnl`, `/api/pnl/bridge`, or the formal financial indicator source contract.
- It does not reuse `GS-LEDGER-PNL-FIN-IND-202603-B`; that fixture remains a formal financial indicator source-contract fixture only.
- Direct governance review, catalog/date evidence, manual audit closure, and business-owner approval remain separate.
