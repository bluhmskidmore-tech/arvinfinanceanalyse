# REPO_MERGE_GUIDE.md

## 目标

把本包并入目标仓库，并把 PRD 升格为 Codex 的最高级别产品蓝图。

## 落仓清单

- 根目录：
  - `AGENTS.md`
  - `prd-moss-agent-analytics-os.md`

- `docs/`：
  - `DOCUMENT_AUTHORITY.md`
  - `CURRENT_EFFECTIVE_ENTRYPOINT.md`
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
   —— **条件未满足**：该文档在当前 checkout 中不存在，本步为空操作
4. 如果仓库已有 `MOSS 系统：取值逻辑、计算层与规则总览`，仅保留为旧逻辑参考
   —— **条件未满足**：同上，该文档在当前 checkout 中不存在，本步为空操作
5. 将 `docs/CODEX_KICKOFF_PROMPT.md` 原样发给 Codex
6. 当前 repo-level 状态入口改为：`AGENTS.md` -> `docs/DOCUMENT_AUTHORITY.md` -> `docs/CURRENT_EFFECTIVE_ENTRYPOINT.md`
7. `docs/CODEX_HANDOFF.md` / `docs/IMPLEMENTATION_PLAN.md` 保留为 reference docs，不再作为并列当前入口

## 空置槽位（第 3、4 步）

第 3、4 步引用的两份文档从未并入本仓库，两步的条件至今未满足。不要把它们当成已存在的文件去查找或
引用，也不要以它们为依据裁决冲突。是否补齐还是正式作废属于 owner 决策；权威说明见
[DOCUMENT_AUTHORITY.md](DOCUMENT_AUTHORITY.md) 的「两个空置槽位（文件从未并入本仓库）」一节，
其中也列出了当前可用的替代文件。

## 不要做的事

- 不要让 Codex 一次做完全部 Phase
- 不要让 Codex 自行决定架构优先级
- 不要让 Codex 在前端或 endpoint 中写正式金融计算
