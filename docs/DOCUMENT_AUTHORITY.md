# DOCUMENT_AUTHORITY.md

## 目的

统一 Codex 在本仓库中处理“北极星 PRD、目标架构、阶段边界、历史逻辑、dated override”时的决策顺序，避免把计划材料、历史说明和当前执行授权混在一起。

## 权威顺序

1. `AGENTS.md`
2. `prd-moss-agent-analytics-os.md`
3. `docs/MOSS-V2 系统架构说明`
4. `docs/CODEX_HANDOFF.md`
5. `docs/IMPLEMENTATION_PLAN.md`
6. `docs/calc_rules.md`
7. `docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md`（产品类别余额/日均/规模读模型；别名页面 `balance-analysis`以本文与代码为准）
8. `docs/data_contracts.md`
9. `docs/CACHE_SPEC.md`
10. `docs/acceptance_tests.md`
11. `MOSS 系统：取值逻辑、计算层与规则总览`

## 冲突处理

- 如果 `V1` 与 `PRD / V2` 冲突，以 `PRD / V2` 为准。
- 如果 `历史逻辑参考` 与 `正式实现边界` 冲突，以 `AGENTS.md`、`PRD`、`V2` 为准。
- 如果 `前端便利` 与 `正式金融计算唯一入口` 冲突，以 `backend/app/core_finance/` 唯一入口为准。
- 如果 `计划材料` 与 `当前执行边界` 冲突，以权威文档中的当前边界说明和 dated execution update 为准。

## 阶段边界规则

- 仓库默认执行边界已切换为 `repo-wide Phase 2（通用正式计算）`。
- 本次 repo-wide `Phase 2` cutover 只覆盖 formal-compute 主链：
  - formal balance
  - formal PnL
  - formal FX
  - formal yield curve
  - PnL bridge
  - risk tensor
  - 核心 bond analytics formal read surfaces
- `Phase 1 closeout` 仍保留为历史收口概念，但只适用于未纳入本次 cutover 的骨架、预览、占位、验证与治理欠账。
- `.omx/plans/` 中的 `next-slice`、`closeout`、`execution-plan`、`prd-*`、`test-spec-*` 文档属于计划与候选执行面，不单独构成执行授权。
- 只有以下两类材料可以放开未纳入 cutover 的默认 stop line：
  - 更高优先级的人类指令；
  - dated execution update。
- dated execution update 默认按 **scoped override** 解释：
  - 只对被点名工作流生效；
  - 不自动扩张 repo-wide `Phase 2` 已排除的模块；
  - 不得被拿来为无关工作流背书。

## 当前有效 scoped override

- `docs/CURRENT_EXECUTION_UPDATE_2026-04-09.md`
- `docs/CURRENT_EXECUTION_UPDATE_2026-04-10.md`
- `docs/CURRENT_EXECUTION_UPDATE_2026-04-11.md`
- `docs/CURRENT_EXECUTION_UPDATE_2026-04-12.md`
- 最新的“当前代码状态 vs 当前阶段边界”摘要见 `docs/CURRENT_BOUNDARY_HANDOFF_2026-04-10.md`

其作用范围用于：

- 记录历史 scoped lane 的授权范围
- 为 repo-wide `Phase 2` 明确排除的工作流提供额外局部授权
- 为未来未纳入 cutover 的新工作流提供命名授权模板

repo-wide `Phase 2` 当前明确不放开的范围包括：

- Agent MVP / Phase 4A / 4B
- `executive.*` 中除 `executive-consumer cutover v1` 以外的其余路由
- `executive-consumer cutover v1` 当前已纳入：
  - `/ui/home/overview`
  - `/ui/home/summary`
  - `/ui/pnl/attribution`
- `executive-consumer cutover v1` 当前仍排除：
  - `/ui/risk/overview`
  - `/ui/home/alerts`
  - `/ui/home/contribution`
- `source_preview` / `macro-data` / `choice-news` / `market-data` 的 preview/vendor/analytical surface
- `qdb_gl_monthly_analysis`、`liability_analytics_compat` 等 analytical-only / compatibility 模块
- 无关工作流的 `next slice`
- broad frontend rollout

## PnL 附录（fixture 对照）

- `docs/pnl/appendix-pnl-fixture-matrix.md`：`source_family`、FI / NonStd / 多源并存场景与现有测试断言的对照；**不**新增业务口径，只作引用对齐。
- `docs/pnl/README.md`：PnL 附录包的索引。

## 三类文档的作用

### PRD

定义系统本体、北极星、目标架构、技术栈冻结、数据平面、结果契约、阶段边界。

### V2 架构说明

定义目标实现架构、运行边界、DuckDB 单写者、服务分层、存储职责。

### V1 / 历史总览

定义旧系统“数据如何取、公式曾经在哪算、历史行为是什么”；适合做迁移参考、口径对照和回归验证，不再作为新实现边界文档。

## 对 Codex 的直接要求

- 不得把历史 `services` 唯一计算入口模式复制到新架构。
- 新代码中的正式金融计算必须实现于 `backend/app/core_finance/`。
- `backend/app/api/` 必须保持薄层。
- 前端和 Agent 必须消费同一 `services -> core_finance -> storage` 链路。
- 不得把 `.omx/plans/` 中的计划标题、阶段名或 next-slice 命名误读为已获准执行。
