# ARCHITECTURE

## 目的

这份文档不是业务规则说明书，而是基于当前目录树、入口文件和各层 `AGENTS.md` 整理出的仓库地图。它回答三个问题：

1. 这个仓库的系统形态是什么。
2. 代码和文档应该去哪里找。
3. 哪些局部目录受更细粒度的 `AGENTS.md` 约束。

## 当前边界

顶层 `AGENTS.md` 和 `backend/app/AGENTS.md` 共同定义了当前默认执行边界：

- 当前默认主线是 `repo-wide Phase 2` formal-compute mainline。
- 默认纳入链路包括：formal balance、formal PnL、formal FX、formal yield curve、PnL bridge、risk tensor、core bond-analytics formal read surfaces。
- 默认排除面包括：Agent MVP / 实际 agent query、`source_preview`、`macro-data`、`choice-news`、market-data preview/vendor/analytical 扩展、`qdb_gl_monthly_analysis`、`liability_analytics_compat`，以及超出已落地范围的 `executive.*`。

这意味着仓库里虽然同时存在更多页面、路由和历史计划文档，但它们不自动等于“当前 repo-wide 已开放执行范围”。

## AGENTS 作用域

当前仓库中能直接影响阅读和改动方式的 `AGENTS.md` 有四层：

| 作用域 | 文件 | 作用 |
| --- | --- | --- |
| repo 全局 | `AGENTS.md` | 定义当前任务优先级、scope discipline、页面规则、验证要求。 |
| backend/app 子树 | `backend/app/AGENTS.md` | 固定后端层级方向，强调 formal compute 与写入边界。 |
| tests 子树 | `tests/AGENTS.md` | 定义测试边界与默认可验证范围。 |
| docs bundle 子树 | `docs/codex_prd_merged_bundle/AGENTS.md` | 仅约束 bundle 快照目录，不是运行时代码约束。 |

如果你修改的是根目录、`docs/`、`frontend/`、`scripts/` 等位置，主要受顶层 `AGENTS.md` 约束；只有改到 `backend/app/` 或 `tests/` 子树时，才需要额外叠加对应局部规则。

## 分层结构

仓库遵循固定调用方向：

`frontend -> api -> services -> (repositories / core_finance / governance) -> storage`

这一层级在顶层 `AGENTS.md`、`backend/app/AGENTS.md` 和 `docs/architecture.md` 中是一致的。

### 每层职责

- `frontend/`: 页面、组件、路由和前端适配器；消费后端结果，不承担正式金融计算。
- `backend/app/api/`: FastAPI 路由入口和响应编排。
- `backend/app/services/`: 业务读取编排、边界控制、结果封装。
- `backend/app/repositories/`: DuckDB、Postgres、Redis、对象存储和外部供应商访问。
- `backend/app/core_finance/`: 正式金融公式和核心计算实现。
- `backend/app/governance/`: 设置、lineage、锁和审计。
- `backend/app/tasks/`: 物化、worker、数据刷新与异步写入入口。

## 仓库目录树

下面是适合日常导航的精简目录树：

```text
F:\MOSS-V3
|- backend/
|  |- app/
|  |  |- agent/
|  |  |- api/routes/
|  |  |- config/
|  |  |- core_finance/
|  |  |- governance/
|  |  |- models/
|  |  |- repositories/
|  |  |- schema_registry/
|  |  |- schemas/
|  |  |- security/
|  |  |- services/
|  |  |- tasks/
|  |  |- main.py
|  |  `- AGENTS.md
|  |- alembic/
|  |- data/
|  |- scripts/
|  `- pyproject.toml
|- frontend/
|  |- src/
|  |  |- api/
|  |  |- app/
|  |  |- components/
|  |  |- features/
|  |  |- layouts/
|  |  |- mocks/
|  |  |- router/
|  |  |- styles/
|  |  |- test/
|  |  |- theme/
|  |  `- utils/
|  |- package.json
|  `- vite.config.ts
|- config/
|- data/
|- data_input/
|- docs/
|- sample_data/
|- scripts/
|- sql/
|- tests/
|- docker-compose.yml
`- README.md
```

## 后端地图

`backend/app/main.py` 是 FastAPI 入口；应用在启动阶段通过 `run_startup_storage_migrations()` 做存储 bootstrap，然后挂载 `backend.app.api.router`。

### `backend/app/api/routes/`

这里按领域拆分 FastAPI 路由文件，当前可见的路由模块包括：

- `balance_analysis.py`
- `bond_analytics.py`
- `bond_dashboard.py`
- `cashflow_projection.py`
- `credit_spread_analysis.py`
- `cube_query.py`
- `executive.py`
- `external_data.py`
- `kpi.py`
- `ledger_pnl.py`
- `liability_analytics.py`
- `market_data_ncd_proxy.py`
- `pnl.py`
- `pnl_attribution.py`
- `positions.py`
- `product_category_pnl.py`
- `research_calendar.py`
- `risk_tensor.py`
- `source_preview.py`

存在这些路由文件，不代表它们都在当前 repo-wide 主线边界内；是否可动、可放量、可视为正式面，仍要回到顶层边界文档判断。

### `backend/app/core_finance/`

这是 formal compute 的核心目录，当前包含：

- 余额/资产负债分析：`balance_analysis.py`、`balance_analysis_workbook.py`
- PnL / 归因：`pnl.py`、`pnl_bridge.py`、`pnl_attribution/`
- 债券分析：`bond_duration.py`、`bond_four_effects.py`、`bond_analytics/`
- 风险：`risk_tensor.py`、`risk_metrics.py`、`krd.py`
- 宏观/信用利差：`macro/`、`credit_spread_analysis.py`
- 产品分类损益：`product_category_pnl.py`

如果一个指标属于“正式金融计算”，按现有架构应该在这里找到最终公式或组合逻辑，而不是在 `frontend/` 或 `api/` 中找到“补算版”。

### `backend/app/services/`

这一层负责把 API、formal compute、仓储和治理约束接起来。当前按页面/域拆了大量服务，例如：

- `balance_analysis_service.py`
- `bond_analytics_service.py`
- `executive_service.py`
- `pnl_service.py`
- `pnl_attribution_service.py`
- `product_category_pnl_service.py`
- `product_category_source_service.py`
- `risk_tensor_service.py`

### `backend/app/repositories/`

这一层隔离外部数据和存储读写，包括：

- DuckDB / schema / snapshot：`duckdb_repo.py`、`duckdb_schema_registry.py`、`snapshot_repo.py`
- Postgres / governance：`postgres_repo.py`、`governance_repo.py`
- Redis / 对象存储：`redis_repo.py`、`object_store_repo.py`
- 外部数据源：`choice_client.py`、`choice_adapter.py`、`tushare_adapter.py`、`akshare_adapter.py`

### `backend/app/tasks/`

所有 DuckDB 物化写入路径都收敛在这里。目录中可见的任务包括：

- `formal_balance_pipeline.py`
- `snapshot_materialize.py`
- `pnl_materialize.py`
- `risk_tensor_materialize.py`
- `yield_curve_materialize.py`
- `worker_bootstrap.py`

## 前端地图

`frontend/src/router/routes.tsx` 是工作台路由总入口；它把页面挂进 `WorkbenchShell`，并对部分历史路径做重定向。

### `frontend/src/features/`

这里是最核心的页面级目录，按业务域拆分，当前包含：

- `average-balance`
- `balance-analysis`
- `bond-analytics`
- `bond-dashboard`
- `cashflow-projection`
- `cross-asset`
- `cube-query`
- `executive-dashboard`
- `ledger-pnl`
- `liability-analytics`
- `market-data`
- `pnl`
- `pnl-attribution`
- `positions`
- `product-category-pnl`
- `risk-overview`
- `risk-tensor`
- `source-preview`
- `workbench`

其中 `routes.tsx` 已验证存在的工作台路径包括：

- `/balance-analysis`
- `/liability-analytics`
- `/pnl`
- `/pnl-bridge`
- `/pnl-attribution`
- `/product-category-pnl`
- `/risk-tensor`
- `/market-data`
- `/bond-dashboard`
- `/bond-analysis`
- `/positions`
- `/average-balance`
- `/ledger-pnl`
- `/cube-query`
- `/cross-asset`

### 共享前端层

- `api/`: HTTP client 和 contract 封装。
- `components/`: 页面外壳、图表、卡片、状态组件。
- `layouts/`: 工作台 Shell。
- `theme/` / `styles/`: 设计系统和样式层。
- `test/`: Vitest + Testing Library 测试目录。

## 配置、数据和运行资产

- `config/`: `.env` 模板、Choice 宏观/新闻配置。
- `data_input/`: 原始输入文件；这里能看到 PnL、总账对账、日均、`TYWLSHOW`、`ZQTZSHOW` 等业务输入。
- `data/`: DuckDB、governance JSONL、archive、runtime logs。
- `sample_data/`: smoke 运行素材。
- `tmp*`: 临时 diff、截图、governance 和 golden capture 输出。

## 文档目录

`docs/` 不是单一说明书，而是多个子集：

- 根层 `.md`: 当前边界、契约、runbook、专题设计。
- `docs/plans/`: 历史和阶段性实施计划。
- `docs/pnl/`: PnL 附录材料。
- `docs/handoff/`: handoff 记录。
- `docs/prompts/`: 历史 prompt 包。
- `docs/codex_prd_merged_bundle/`: bundle 快照，受自己的 `AGENTS.md` 约束。

## 关键入口文件

如果只想知道“先从哪几个文件下手”，优先看这些：

- `AGENTS.md`
- `docs/DOCUMENT_AUTHORITY.md`
- `backend/app/main.py`
- `backend/app/api/__init__.py`
- `frontend/src/router/routes.tsx`
- `scripts/dev-up.ps1`
- `scripts/backend_release_suite.py`

这些文件分别对应：约束、文档权威、后端入口、路由聚合、前端入口、本地开发入口和发布门禁。
