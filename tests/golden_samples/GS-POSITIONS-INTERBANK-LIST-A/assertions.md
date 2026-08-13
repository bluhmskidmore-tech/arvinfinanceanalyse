# GS-POSITIONS-INTERBANK-LIST-A Assertions

## Source

- `docs/page_contracts.md` -> `PAGE-POS-001`
- `docs/metric_dictionary.md` -> `MTR-POS-002`（§15.2.2）
- `backend/app/api/routes/positions.py`
- `backend/app/services/positions_service.py`
- `backend/app/repositories/positions_repo.py`
- `tests/test_positions_api_contract.py`
- `tests/test_golden_samples_capture_ready.py`

## Required Assertions

- HTTP status is `200` when an explicit `positions:read` scope is available.
- The top-level envelope contains `result_meta` and `result`.
- `result_meta.basis == "analytical"`.
- `result_meta.result_kind == "positions.interbank.list"`.
- `result_meta.formal_use_allowed == false`.
- `result_meta.scenario_flag == false`.
- `result_meta.source_version == "sv-pos-tyw"`（快照行血缘，来自 canonical positions 契约 fixture）.
- `result_meta.rule_version == "rv-pos-test"`（快照行血缘）.
- `result_meta.cache_version == "cv_positions_read_v1"`.
- `result_meta.quality_flag == "warning"`.
- `result_meta.fallback_mode == "none"`.
- `result_meta.requested_report_date == "2026-01-10"`.
- `result_meta.resolved_report_date == "2026-01-10"`.
- `result_meta.as_of_date == "2026-01-10"`.
- `result_meta.date_basis == "positions_snapshot_report_date"`.
- `result_meta.filters_applied == {"report_date": "2026-01-10", "product_type": null, "direction": null, "page": 1, "page_size": 20}`（冻结无产品/方向过滤的全量列表口径）.
- `result_meta.tables_used == ["tyw_interbank_daily_snapshot"]`.
- `result_meta.evidence_rows == 1` and `result_meta.evidence_rows == result.total`.

## Frozen Values

- `MTR-POS-002`: `result.total == 1`（同业持仓记录数；单位 条；precision 0）.
- `result.items[0].deal_id == "T1"`、`counterparty == "CP_ASSET"`、`product_type == "REPO"`、`direction == "Asset"`.
- 同 fixture 的 `T2`（`report_date=2026-01-12`）不进入本报告日列表，冻结单报告日切片语义。
- `result.items[0].amount == "1000.00000000"`.
- `result.items[0].interest_rate == "0.00020000"`（同业低值利率按百分数归一：`0.02` -> `0.02%` -> `0.0002`；与 `tests/test_positions_api_contract.py` 低值利率契约一致）.
- `result.page == 1`、`result.page_size == 20`（route 默认分页口径）.

## Boundary

- This sample freezes the `GET /api/positions/interbank` candidate list DTO for `PAGE-POS-001`.
- It preserves `formal_use_allowed=false`; `MTR-POS-002` remains a candidate display metric with `pending_confirmation=true`, and `GAP-POS-LIST` stays open until owner approval.
- `tyw_interbank_daily_snapshot` is a standardized snapshot input, not an outward formal source-of-truth surface; this sample must not be read as formal balance, liability, PnL, or risk truth.
- It does not replace `GS-BAL-OVERVIEW-A` balance truth or any formal `MTR-*` approval.
- Direct governance review, catalog/date evidence, manual audit closure, and business-owner approval remain separate.
