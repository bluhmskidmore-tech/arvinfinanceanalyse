# Codex PRD Merged Bundle

这是一份可直接并入仓库的 Codex 交接包，已经把以下内容收敛到一套口径：
- `prd-moss-agent-analytics-os.md`：系统北极星与顶层架构
- `MOSS-V2`：目标实现架构与运行边界
- `MOSS V1`：旧系统逻辑与历史公式参考，不再作为目标实现架构

## 建议落仓方式

1. 将根目录 `AGENTS.md` 合并到仓库根目录。
2. 将 `prd-moss-agent-analytics-os.md` 放到仓库根目录。
3. 将 `docs/` 下文件放入仓库 `docs/`。
4. 将 `docs/CODEX_KICKOFF_PROMPT.md` 原样发给 Codex。
5. 先只执行 `Phase 1`，不要跨阶段。

## 文档优先级

1. `AGENTS.md`
2. `prd-moss-agent-analytics-os.md`
3. `docs/MOSS-V2 系统架构说明`（若仓库已存在）
4. `docs/CODEX_HANDOFF.md`
5. `docs/IMPLEMENTATION_PLAN.md`
6. `docs/calc_rules.md`
7. `docs/data_contracts.md`
8. `docs/CACHE_SPEC.md`
9. `docs/acceptance_tests.md`
10. `MOSS 系统：取值逻辑、计算层与规则总览`（仅作旧逻辑参考）

## 交付边界

本包不替你实现代码，只替你把 Codex 的约束、目标、阶段边界和验收标准写成可执行文档。
