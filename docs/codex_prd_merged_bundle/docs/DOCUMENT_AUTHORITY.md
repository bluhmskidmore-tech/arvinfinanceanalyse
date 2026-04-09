# DOCUMENT_AUTHORITY.md

## 目的

统一 Codex 在本仓库中处理“旧系统逻辑、目标架构、正式口径、分阶段实施”的决策顺序。

## 权威顺序

1. `AGENTS.md`
2. `prd-moss-agent-analytics-os.md`
3. `docs/MOSS-V2 系统架构说明`
4. `docs/CODEX_HANDOFF.md`
5. `docs/IMPLEMENTATION_PLAN.md`
6. `docs/calc_rules.md`
7. `docs/data_contracts.md`
8. `docs/CACHE_SPEC.md`
9. `docs/acceptance_tests.md`
10. `MOSS 系统：取值逻辑、计算层与规则总览`

## 冲突处理

- 如果 `V1` 和 `PRD / V2` 冲突，以 `PRD / V2` 为准。
- 如果 `业务旧逻辑` 和 `正式实现边界` 冲突，以 `AGENTS.md` 与 `PRD / V2` 的边界为准。
- 如果 `Phase` 边界和“顺手多做一点”冲突，以当前 Phase 边界为准，不得跨阶段。
- 如果 `前端便利` 和 `正式金融计算唯一入口` 冲突，以 `core_finance/` 唯一入口为准。

## 三类文档的作用

### PRD
定义系统本体、目标架构、技术栈冻结、数据平面、结果契约、Agent 栈、阶段边界。

### V2 架构说明
定义目标实现架构、运行边界、DuckDB 单写者、服务分层、存储职责。

### V1 总览
定义旧系统“数据如何取、公式曾经在哪算、历史行为是什么”；适合做迁移参考、口径对照和回归验证，不适合再作为新实现的边界文件。

## 对 Codex 的直接要求

- 不得把 V1 中的 `services` 唯一计算入口继续复制到新架构。
- 新代码中，正式计算必须实现于 `backend/app/core_finance/`。
- 新代码中，`api/` 必须保持薄层。
- 新代码中，前端和 Agent 必须消费同一 `services -> core_finance -> storage` 链路。
