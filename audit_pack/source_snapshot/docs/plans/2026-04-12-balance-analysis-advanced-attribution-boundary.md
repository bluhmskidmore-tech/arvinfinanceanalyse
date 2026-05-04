# Balance Analysis × Advanced Attribution 边界说明（2026-04-12）

## 目的

收敛「资产负债分析 workbook」与「债券分析 / Phase 3 归因」之间的依赖边界，避免在数据未就绪时把占位字段宣传为正式口径。

## 结论摘要

| 区域 | 依赖 | 当前状态 |
|------|------|----------|
| `balance-analysis` governed workbook（本仓库已实现 section） | 仅 `fact_formal_zqtz_balance_daily` / `fact_formal_tyw_balance_daily` 与 `core_finance/balance_analysis_workbook.py` | 可独立交付；**不得**依赖 `advanced_attribution_bundle` |
| Bond analytics 收益分解 / KRD / 情景 | `bond_analytics` 物化事实、曲线与（未来）交易粒度 | `bond_analytics_service` 对 `roll_down` / `rate_effect` / `spread_effect` 等仍可能为零或占位，见 `PHASE3_WARNING` |
| `advanced_attribution_bundle`（若未来引入） | Phase 3 曲线、成交、基准指数等 | **不是**当前 governed workbook 已支持 section；未在 API 暴露前不得在对外文档中宣称已落地 |

## 代码锚点

- `backend/app/services/bond_analytics_service.py`：`PHASE3_WARNING`、`build_bond_action_attribution_placeholder_envelope` 等占位路径。
- `backend/app/core_finance/bond_analytics/read_models.py`：读模型假设字段存在；缺失时上层返回空或零填充应由 service 显式标注。
- `docs/plans/2026-04-12-balance-analysis-gap-closure.md`：Phase 3 数据前提的总览。

## 明确禁止

- 为「看起来合理」把 `roll_down` / `rate_effect` / `spread_effect` 从 `0` 改成启发式数值（除非有正式曲线与契约测试）。
- 将 `advanced_attribution_bundle` 与当前 workbook 已支持 section 列表混写，造成产品误读。

## Workbook 依赖 Phase 3 的章节（若未来扩展）

以下仅作**前置条件**记录；**当前仓库未**将下列 section 作为已支持项实现：

- 需要久期 / DV01 / 曲线冲击的「全量」监管久期指标（与 workbook 中剩余期限 proxy 区分）。
- 需要交易级归因的「持仓动作」分解。

当前正式监管参考表 `regulatory_limits` 中的 `portfolio_modified_duration` 明确标注为**剩余期限 proxy**，不引用风险张量。
