# GS-POSITIONS-BONDS-LIST-A Assertions

## Source

- `docs/page_contracts.md` -> `PAGE-POS-001`
- `docs/metric_dictionary.md` -> `MTR-POS-001`（§15.2.2）
- `backend/app/api/routes/positions.py`
- `backend/app/services/positions_service.py`
- `backend/app/repositories/positions_repo.py`
- `tests/test_positions_api_contract.py`
- `tests/test_golden_samples_capture_ready.py`

## Required Assertions

- HTTP status is `200` when an explicit `positions:read` scope is available.
- The top-level envelope contains `result_meta` and `result`.
- `result_meta.basis == "analytical"`.
- `result_meta.result_kind == "positions.bonds.list"`.
- `result_meta.formal_use_allowed == false`.
- `result_meta.scenario_flag == false`.
- `result_meta.source_version == "sv-pos-test"`（快照行血缘，来自 canonical positions 契约 fixture）.
- `result_meta.rule_version == "rv-pos-test"`（快照行血缘）.
- `result_meta.cache_version == "cv_positions_read_v1"`.
- `result_meta.quality_flag == "warning"`.
- `result_meta.fallback_mode == "none"`.
- `result_meta.requested_report_date == "2026-01-10"`.
- `result_meta.resolved_report_date == "2026-01-10"`.
- `result_meta.as_of_date == "2026-01-10"`.
- `result_meta.date_basis == "positions_snapshot_report_date"`.
- `result_meta.filters_applied == {"report_date": "2026-01-10", "sub_type": null, "page": 1, "page_size": 20, "include_issued": false}`（冻结默认 `include_issued=false` 与无业务种类过滤的全量列表口径）.
- `result_meta.tables_used == ["zqtz_bond_daily_snapshot"]`.
- `result_meta.evidence_rows == 2` and `result_meta.evidence_rows == result.total`.

## Frozen Values

- `MTR-POS-001`: `result.total == 2`（债券持仓记录数；单位 条；precision 0）.
- `result.items[0].bond_code == "B001"`、`result.items[0].sub_type == "GOV"`.
- `result.items[1].bond_code == "B003"`、`result.items[1].sub_type == "CREDIT"`.
- 发行类（`is_issuance_like=true`）的 `B002` 在默认 `include_issued=false` 下被排除，不进入 `total` / `evidence_rows`.
- `result.items[0].market_value == "100.00000000"`、`valuation_net_price == "100.00000000"`（市值/面值×100 归一）.
- `result.items[0].yield_rate == "0.03000000"`、`result.items[1].yield_rate == "0.04500000"`（小数收益率 8 位字符串）.
- `result.page == 1`、`result.page_size == 20`（route 默认分页口径）.

## Boundary

- This sample freezes the `GET /api/positions/bonds` candidate list DTO for `PAGE-POS-001`.
- It preserves `formal_use_allowed=false`; `MTR-POS-001` remains a candidate display metric with `pending_confirmation=true`, and `GAP-POS-LIST` stays open until owner approval.
- `zqtz_bond_daily_snapshot` is a standardized snapshot input, not an outward formal source-of-truth surface; this sample must not be read as formal balance, PnL, bond-dashboard headline, or risk truth.
- It does not replace `GS-BAL-OVERVIEW-A` balance truth or any formal `MTR-*` approval.
- Direct governance review, catalog/date evidence, manual audit closure, and business-owner approval remain separate.
