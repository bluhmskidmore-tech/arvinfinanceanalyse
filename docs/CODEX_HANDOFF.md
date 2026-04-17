# CODEX_HANDOFF.md

## 1. 你正在构建的是什么

这是一个银行固定收益领域的生产级内部系统。

系统本体是：

`Agent 可调用的分析操作系统`

前端工作台、管理报表和 Agent 查询，只是同一个分析底座的不同消费层。

## 2. 目标形态

采用：

`模块化单体 + 分层分析栈`

暂不拆微服务。

固定调用方向：

`frontend -> api -> services -> (repositories / core_finance / governance) -> storage`

## 3. 非谈判边界

- 正式金融计算只能在 `backend/app/core_finance/` 实现一次。
- `backend/app/api/` 只允许做参数校验、鉴权、调用 service、返回响应。
- `frontend/` 不允许补算正式金融指标。
- `Scenario` 不得污染 `Formal`。
- DuckDB API 常态只读；写入只能走 `backend/app/tasks/`。
- 所有正式结果必须带 `result_meta`。
- 前端、管理报表、Agent 必须共用同一分析服务层。
- 不得删功能，只允许补齐、纠错、重构。

## 4. 文档优先级

阅读顺序如下：

1. `AGENTS.md`
2. `prd-moss-agent-analytics-os.md`
3. `docs/MOSS-V2 系统架构说明`
4. `docs/V2_TO_V3_MIGRATION_INVENTORY.md`
5. `docs/DOCUMENT_AUTHORITY.md`
6. `docs/IMPLEMENTATION_PLAN.md`
7. `docs/calc_rules.md`
8. `docs/data_contracts.md`
9. `docs/CACHE_SPEC.md`
10. `docs/acceptance_tests.md`
11. `MOSS 系统：取值逻辑、计算层与规则总览`

## 5. 技术栈冻结

前端：
- React
- TypeScript
- Vite
- TanStack Query
- Ant Design
- AG Grid
- ECharts
- Claude 风格 theme layer

后端：
- Python 3.11+
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x

存储与异步：
- PostgreSQL：配置、权限、治理、任务、审计、映射、人工调整
- DuckDB：分析事实表、宽表、物化分析缓存
- Redis：队列、热缓存、锁
- Dramatiq：异步任务
- MinIO / S3：原始文件、导出文件、快照归档

数据源：
- 内部：`zqtz`、`tyw`
- 文件：FI 损益、非标 `514 / 516 / 517`、日均、FX 中间价
- 外部：Choice、AkShare

PnL 文件类源的 `data_input` 布局与回归测试对照：`docs/pnl/appendix-pnl-fixture-matrix.md`。

## 6. 目标目录

```text
repo/
  AGENTS.md
  prd-moss-agent-analytics-os.md
  .codex/
    config.toml
  docs/
    DOCUMENT_AUTHORITY.md
    CODEX_HANDOFF.md
    IMPLEMENTATION_PLAN.md
    CACHE_SPEC.md
    calc_rules.md
    data_contracts.md
    acceptance_tests.md
    pnl/
      README.md
      appendix-pnl-fixture-matrix.md
  backend/
    app/
      api/
      services/
      core_finance/
      repositories/
      tasks/
      governance/
      schemas/
      models/
      security/
      main.py
  frontend/
    src/
      pages/
      components/
      api/
      hooks/
      theme/
  sql/
  config/
  scripts/
  tests/
  sample_data/
```

## 7. 正式计算一期能力

`backend/app/core_finance/` 一期至少包含：

- H/A/T -> AC/FVOCI/FVTPL 映射
- 债券月均金额
- 发行类债券剔除
- USD 资产按当日中间价折算 CNY
- Formal PnL（514/516/517）
- Formal / Analytical / Ledger bridge
- risk tensor（DV01 / KRD / CS01 / convexity）
- maturity bucket / pricing bucket / currency basis

## 8. 一期必须保留的工作台

- 首页总览
- 债券头寸工作台
- 同业工作台
- 正式损益工作台
- 非标损益工作台
- 风险工作台
- 对账与治理工作台
- Agent 工作台

## 9. 当前执行边界

当前默认执行边界已切换为 `repo-wide Phase 2（通用正式计算）`。

默认边界解释如下：

- 本次 repo-wide `Phase 2` cutover 只覆盖 formal-compute 主链：
  - formal balance
  - formal PnL
  - formal FX
  - formal yield curve
  - PnL bridge
  - risk tensor
  - 核心 bond analytics formal read surfaces
- `Phase 1 closeout` 仍属于历史收口概念，只用于未纳入 cutover 的骨架、预览、占位、验证和治理欠账。
- `.omx/plans/` 中的 `next-slice`、`closeout`、`execution-plan` 文档是计划，不是执行权限来源。
- dated execution update 仍可用于 repo-wide `Phase 2` 已排除模块或未来新工作流的 scoped override；它们不再是 formal-compute 主链的主要授权来源。
- 当前代码库中已经落下的 thin slice / start pack 需要按“已纳入 cutover 的正式主链”与“仍被排除的消费层/分析层”分别解释。
- 最新的“当前代码状态 vs 当前阶段边界”摘要见 `docs/CURRENT_BOUNDARY_HANDOFF_2026-04-10.md`。

本次 cutover 明确排除：

- `executive.*` 中除 `executive-consumer cutover v1` 以外的其余路由
- 当前已纳入 `executive-consumer cutover v1` 的范围：
  - `/ui/home/overview`
  - `/ui/home/summary`
  - `/ui/pnl/attribution`
- 当前仍排除：
  - `/ui/risk/overview`
  - `/ui/home/alerts`
  - `/ui/home/contribution`
- Agent MVP / `/api/agent/query` / `/agent`
- `source_preview` / `macro-data` / `choice-news` / `market-data` 的 preview/vendor/analytical surface
- `qdb_gl_monthly_analysis`、`liability_analytics_compat` 等 analytical-only / compatibility 模块
- cube-query、broad frontend rollout、以及其他 `Phase 3 / Phase 4` 风格扩张项

若工作属于排除项，仍需新的明确授权或后续阶段定义。

## 9.1 Agent Phase 1 当前状态

当前 Agent 仅完成 `Phase 1 skeleton`，不具备真实查询能力。

已存在的占位语义：

- `POST /api/agent/query` 已注册，但固定返回 `503 disabled stub`
- `/agent` 路由可访问，但在主导航中保持隐藏
- Agent 页面内容来自本地 typed fixture，不走真实 Agent API data flow

以上都属于 Agent-ready foundation，不代表 Agent 已上线。

后续约束：

- closeout 完成后，暂停 Agent 实现工作
- 只有当系统 `Phase 2` 正式计算层与 `Phase 3` 证据 / lineage 前置完成后，才允许恢复 Agent Phase 4A / 4B 实施

## 10. 每轮必须交付

- 变更文件清单
- 测试结果
- 未完成项
- 下一轮建议
- 风险说明

## 11. 迁移资产入口

涉及历史模块来源、V2 迁移资产分层、`library / wired / candidate` 状态、以及
`库级实现 / 主流程实现 / 端到端实现` 判断时，统一以
`docs/V2_TO_V3_MIGRATION_INVENTORY.md` 为当前入口文档。
