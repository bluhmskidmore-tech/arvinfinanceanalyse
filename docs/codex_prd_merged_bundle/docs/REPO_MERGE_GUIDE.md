# REPO_MERGE_GUIDE.md

## 目标

把本包并入目标仓库，并把 PRD 升格为 Codex 的最高级别产品蓝图。

## 落仓清单

- 根目录：
  - `AGENTS.md`
  - `prd-moss-agent-analytics-os.md`

- `docs/`：
  - `DOCUMENT_AUTHORITY.md`
  - `CODEX_HANDOFF.md`
  - `IMPLEMENTATION_PLAN.md`
  - `CODEX_KICKOFF_PROMPT.md`
  - `CACHE_SPEC.md`
  - `calc_rules.md`
  - `data_contracts.md`
  - `acceptance_tests.md`
  - `SYSTEM_STACK_SPEC_FOR_CODEX.md`

## 立即执行动作

1. 合并 `AGENTS.md`
2. 放入 `prd-moss-agent-analytics-os.md`
3. 如果仓库已有 `docs/MOSS-V2 系统架构说明`，保留并纳入阅读顺序
4. 如果仓库已有 `MOSS 系统：取值逻辑、计算层与规则总览`，仅保留为旧逻辑参考
5. 将 `docs/CODEX_KICKOFF_PROMPT.md` 原样发给 Codex
6. 强制 Codex 只做 `Phase 1`

## 不要做的事

- 不要让 Codex 一次做完全部 Phase
- 不要让 Codex 自行决定架构优先级
- 不要让 Codex 在前端或 endpoint 中写正式金融计算
