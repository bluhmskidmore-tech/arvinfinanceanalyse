# DOCUMENT_AUTHORITY.md

## 目的

统一 Codex 在本仓库中处理“北极星 PRD、目标架构、阶段边界、历史逻辑、dated override”时的决策顺序，避免把计划材料、历史说明和当前执行授权混在一起。

## 权威顺序

以下每一项都已核对为仓库中**实际存在**的文件（2026-08-13）：

1. `AGENTS.md`
2. `prd-moss-agent-analytics-os.md`
3. `docs/calc_rules.md`
4. `docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md`（产品类别余额/日均/规模读模型；别名页面 `balance-analysis`以本文与代码为准）
5. `docs/data_contracts.md`
6. `docs/CACHE_SPEC.md`
7. `docs/acceptance_tests.md`

产品 PRD 的权威正文只维护在仓库根 [prd-moss-agent-analytics-os.md](../prd-moss-agent-analytics-os.md)。[docs/ 下的旧 PRD 路径](prd-moss-agent-analytics-os.md) 只保留章节跳转，不承载另一份产品定义或执行授权；当前范围仍由本文的[阶段边界规则](#阶段边界规则)和 [Current Surface Boundaries](#current-surface-boundaries) 维护。

### 两个空置槽位（文件从未并入本仓库）

历史上这条链在第 3 位和末位还列过两份文档，但它们**在本仓库里不存在**（已按全部扩展名检索
`docs/` 与仓库根，`git ls-files` 亦无匹配）：

| 原槽位 | 标题 | 状态 |
| --- | --- | --- |
| 第 3 位 | `docs/MOSS-V2 系统架构说明` | 未并入。`docs/REPO_MERGE_GUIDE.md` 把它写成条件性导入（「如果仓库已有…则保留」），条件未满足 |
| 末位 | `MOSS 系统：取值逻辑、计算层与规则总览` | 未并入，同上 |

因此：

- **不得**以这两份文档为依据裁决任何冲突，也不得声称「已按 V2 架构说明确认」。
- 需要目标架构口径时，用实际存在的 `docs/SYSTEM_STACK_SPEC_FOR_CODEX.md`（技术栈与分层冻结）
  和 `docs/architecture.md`（当前目录树与边界地图）；两者都是**说明**，不自动获得上表的权威位次。
- 是否补齐这两份文档、或正式声明槽位作废，属于 owner 决策，不由执行方自行填充。
- 同源引用已全部就地标注并回指本节（2026-08-13 复核）：`docs/liability_v1_field_authority_matrix.md`、
  `docs/CODEX_HANDOFF.md`、`docs/CODEX_KICKOFF_PROMPT.md`、`docs/REPO_MERGE_GUIDE.md`。
- `docs/codex_prd_merged_bundle/` 是历史快照目录（`docs/README.md` 标为 archived/reference）。目录内
  5 份副本（`AGENTS.md`、`docs/DOCUMENT_AUTHORITY.md`、`docs/CODEX_HANDOFF.md`、
  `docs/CODEX_KICKOFF_PROMPT.md`、`docs/REPO_MERGE_GUIDE.md`）**刻意不改**，以保留交接包原貌；
  提示写在该目录的 wrapper `docs/codex_prd_merged_bundle/README.md` 里，回指本节。

## Current-State Navigation

For current repo state, use this read path:

1. `AGENTS.md`
2. `docs/DOCUMENT_AUTHORITY.md`
3. `docs/CURRENT_EFFECTIVE_ENTRYPOINT.md`

`docs/CURRENT_EFFECTIVE_ENTRYPOINT.md` is navigation/index only. It cannot grant scope, override boundary docs, or elevate supporting artifacts into repo-level authority.

## Role-Specific Reference Docs

The following docs remain useful, but they are not the repo-level current-state entrypoint:

- `docs/CODEX_HANDOFF.md`
  - repo background and reference handoff
- `docs/IMPLEMENTATION_PLAN.md`
  - phase / implementation reference plan
- `docs/page_contracts.md`
  - page-level contracts to read after repo-level current-state lookup is clear
- `docs/plans/market-workbench-cursor-prompts.md`
  - 市场工作台（`/market-data` 及相关路由）**Cursor 可执行外围任务**的拆分与验收提示；用于与 `PAGE-MKT-001`（`docs/page_contracts.md` §13.8）对齐执行顺序，**不**改变上文权威顺序，也不将其中措辞升格为指标定义或 formal 口径

## 冲突处理

- 如果 `历史逻辑参考` 与 `正式实现边界` 冲突，以 `AGENTS.md`、`PRD` 和上面权威顺序里**实际存在**的
  文档为准（原文写的是「以 `AGENTS.md`、`PRD`、`V2` 为准」，但 V2 文档从未并入，见上节）。
- 如果 `前端便利` 与 `正式金融计算唯一入口` 冲突，以 `backend/app/core_finance/` 唯一入口为准。
- 如果 `计划材料` 与 `当前执行边界` 冲突，以权威文档中的当前边界说明和 dated execution update 为准。
- 如果 `docs/CURRENT_EFFECTIVE_ENTRYPOINT.md` 与 `AGENTS.md` / `docs/DOCUMENT_AUTHORITY.md` / applicable dated execution update 冲突，以后者为准，并把 entrypoint 视为待更新的 navigation doc。

## Backend Canonical Gate

对于当前 repo-wide `Phase 2` governed formal-compute release，backend canonical gate 为：

- `python scripts/backend_release_suite.py`

说明：

- 该命令是当前 release cutoff 使用的 named bounded backend release suite；上面那行是门禁的
  **规范名称**（CI 里 `uv sync --frozen` 已把 venv 前置进 `PATH`，那里的裸 `python` 是对的）。
- **本机执行时必须显式指定解释器**，因为开发机上的 `python` 常被无关 venv 遮蔽：

```powershell
.\.venv\Scripts\python.exe scripts\backend_release_suite.py
```

- `.\.venv\Scripts\python.exe -m pytest -q` 仍可作为 broader diagnostic command 使用，但不作为
  当前 release cutoff 的 canonical backend gate。

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
- 当前任务已有的用户指令只要明确覆盖该工作流，就满足该任务的范围授权；不因它属于 excluded surface 再次索要同一授权。局部开发授权不等于正式金融口径晋升或生产启用授权。
- dated execution update 默认按 **scoped override** 解释：
  - 只对被点名工作流生效；
  - 不自动扩张 repo-wide `Phase 2` 已排除的模块；
  - 不得被拿来为无关工作流背书。

## 当前有效 scoped override

- `docs/CURRENT_EXECUTION_UPDATE_2026-04-09.md`
- `docs/CURRENT_EXECUTION_UPDATE_2026-04-10.md`
- `docs/CURRENT_EXECUTION_UPDATE_2026-04-11.md`
- `docs/CURRENT_EXECUTION_UPDATE_2026-04-12.md`
- repo-level current-state navigation 入口见 `docs/CURRENT_EFFECTIVE_ENTRYPOINT.md`
- dated execution update 的选择按 active-lane applicability，不按 recency alone
- 当前“代码状态 vs 阶段边界”摘要源见 `docs/CURRENT_BOUNDARY_HANDOFF_2026-04-10.md`

其作用范围用于：

- 记录历史 scoped lane 的授权范围
- 为 repo-wide `Phase 2` 明确排除的工作流提供额外局部授权
- 为未来未纳入 cutover 的新工作流提供命名授权模板

## Current Surface Boundaries

本节维护后端与测试入口共用的当前范围；发布验收条件仍见 [V3_CUTOFF_EXIT_CRITERIA.md](V3_CUTOFF_EXIT_CRITERIA.md)。

`executive-consumer cutover v1` 当前已纳入以下 E1 读取接口，保留其 analytical envelope 和 `formal_use_allowed=false` 语义：

- `/ui/home/overview`
- `/ui/home/summary`
- `/ui/home/snapshot`
- `/ui/pnl/attribution`

repo-wide `Phase 2` 默认范围仍不包含以下扩展：

- Agent MVP / Phase 4A / 4B 的生产启用
- `executive.*` 超出上述 E1 接口的 governed rollout
- `source_preview` / `macro-data` / `choice-news` / `market-data` 的 preview/vendor/analytical 扩展
- `qdb_gl_monthly_analysis`、`liability_analytics_compat` 等 analytical-only / compatibility 模块的范围扩张
- cube-query broad rollout 及其他 `Phase 3 / Phase 4` 扩展
- 无关工作流的 `next slice`
- broad frontend rollout

已落地接口的维护与正式金融口径晋升应分别判断。当前运行契约如下：

- `/ui/risk/overview`、`/ui/home/alerts`、`/ui/home/contribution`：通过读取权限校验后仍显式 `503 fail-closed`
- `cube-query` public routes 已开放为受控 query surface；当前只按已覆盖事实表与 `result_meta` 声明查询结果口径，不等同于新增页面级正式指标真值面
- liability-analytics public routes 已开放为 analytical compatibility surface；必须显式保留 mixed-source / compat 边界，不得误写为 formal balance/PnL truth
- retained frontend entries：placeholder / compat / hidden，不代表已晋升 live governed page

## PnL 附录（fixture 对照）

- `docs/pnl/appendix-pnl-fixture-matrix.md`：`source_family`、FI / NonStd / 多源并存场景与现有测试断言的对照；**不**新增业务口径，只作引用对齐。
- `docs/pnl/README.md`：PnL 附录包的索引。

## 文档分类的作用

### PRD（`prd-moss-agent-analytics-os.md`，存在）

定义系统本体、北极星、目标架构、技术栈冻结、数据平面、结果契约、阶段边界。

### 目标实现架构（原「V2 架构说明」槽位，**文件不存在**）

原本承载目标实现架构、运行边界、DuckDB 单写者、服务分层、存储职责。该文件从未并入本仓库。
这些内容目前分散在 `prd-moss-agent-analytics-os.md`、`docs/SYSTEM_STACK_SPEC_FOR_CODEX.md`
和 `backend/app/AGENTS.md` 中，没有单一权威载体——这是一个已知缺口，不要假装它已被覆盖。

### V1 / 历史总览（原槽位，**文件不存在**）

原本承载旧系统「数据如何取、公式曾经在哪算、历史行为是什么」。仓库里能用于迁移参考与口径对照的
实际文件是 `docs/V2_TO_V3_MIGRATION_INVENTORY.md` 与 `docs/V2_V3_PARITY_MATRIX.md`；它们是清单/对照
矩阵，不是新实现边界文档。

## 对 Codex 的直接要求

- 不得把历史 `services` 唯一计算入口模式复制到新架构。
- 新代码中的正式金融计算必须实现于 `backend/app/core_finance/`。
- `backend/app/api/` 必须保持薄层。
- 前端和 Agent 必须消费同一 `services -> core_finance -> storage` 链路。
- 不得把 `.omx/plans/` 中的计划标题、阶段名或 next-slice 命名误读为已获准执行。
