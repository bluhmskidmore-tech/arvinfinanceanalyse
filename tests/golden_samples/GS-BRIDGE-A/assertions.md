# GS-BRIDGE-A Assertions

## Source

- `tests/test_pnl_api_contract.py`
- `docs/golden_sample_catalog.md`

## Required assertions

- HTTP status is `200`.
- `result_meta.basis == "formal"`.
- `result_meta.result_kind == "pnl.bridge"`.
- `result.report_date == "2025-12-31"`.
- `rows.length == 1`.
- `rows[0].instrument_code == "240001.IB"`.
- `MTR-BRG-003 == "12.50000000"`.
- `MTR-BRG-008 == "1.75000000"`.
- `MTR-BRG-009 == "-3.25000000"`.
- `MTR-BRG-010 == "0.50000000"`.
- `MTR-BRG-011 == "14.75000000"`（互斥分解：explained 不含 516，2026-08-11 审计 PNL-01）.
- `MTR-BRG-012 == "11.50000000"`.
- `MTR-BRG-013 == "-3.25000000"`（残差 = 未被市场效应解释的 516；本样本无可用曲线，516 全额落入残差）.
- `summary.row_count == 1`.
- `warnings[0]` keeps the current phase-3 partial delivery warning.

## Sample profile

- This is an `error-profile normal sample`（2026-08-11 起）：FVTPL 行带非零 516 且无可用曲线时，
  互斥分解口径下残差比率 |−3.25|/11.50 ≈ 28% 触发 `error`，这是诚实的质量标记而非样本缺陷。
- 旧口径（explained 同时累加会计分项与市场效应）会使残差恒为 0、质量恒为 ok，
  已被 2026-08-11 计算端审计判定为 P0 缺陷（PNL-01/PNL-02）并修复。
- It is valid even though current bridge coverage is not all-green.

## Reconciliation

- Reconcile `actual_pnl` directionally with `GS-PNL-OVERVIEW-A`.
