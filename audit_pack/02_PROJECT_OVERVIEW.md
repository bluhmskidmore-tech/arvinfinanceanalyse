# 02 — 项目概览（审计）

> 基于 `README.md`、`frontend/package.json`、`backend/pyproject.toml`、`backend/app`、`frontend/src/router`、导航配置等快照整理；**不构成业务口径认定**。

## 技术栈总览

| 层级 | 技术 |
|------|------|
| 前端运行时 | React 18、TypeScript、Vite 5 |
| UI | Ant Design 5、`@ant-design/icons` |
| 数据获取 | `@tanstack/react-query` |
| 表格 / 图表 | ag-grid、eCharts 6、`echarts-for-react` |
| 路由 | `react-router-dom` v6（懒加载页面）|
| 后端框架 | FastAPI、Uvicorn |
| Python | `pyproject.toml` 要求 ≥3.11（当前 CI/本机若为 3.14 可能存在依赖差异风险）|
| 关系库 / ORM | PostgreSQL、`SQLAlchemy` 2、`Alembic` |
| OLAP / 本地分析 | DuckDB |
| 其他后端依赖 | Redis、Dramatiq、MinIO、Requests、BeautifulSoup、pydantic-settings 等 |

## 前端结构与状态管理

- **无** Redux/Zustand 等全局 Store 目录（`frontend/src/store` **不存在**）；页面级多用 React Query + 本地组件 state。
- 设计令牌与主题：`frontend/src/theme/`（含 `designSystem.ts`、`tokens.ts`）。
- 导航与路由就绪标签：`frontend/src/mocks/navigation.ts`，与 `frontend/src/router/routes.tsx` 手工分支映射工作台子路由。
- Mock：`frontend/src/mocks/` 及散落在各 feature 的 `*Mocks*`；统一 API 门面主要是 `frontend/src/api/client.ts`（体量大，`AGENTS.md` 要求新客户走向 domain client）。

## 后端组织

- **唯一正式金融计算目录**：`backend/app/core_finance/`（仓库中 **没有** `backend/app/core/` 包；审计代码请以 `core_finance` 为准）。
- API：`backend/app/api/routes/` 下按域拆分；聚合见 `backend/app/api/__init__.py`。
- 服务编排：`backend/app/services/`。
- 任务 / 写入链路：`backend/app/tasks/`（DuckDB 物化等）。
- 配置：`backend/app/governance/settings.py`（含 `MOSS_` 前缀环境变量）。
- **`backend/requirements.txt` 不存在**：依赖以 **`backend/pyproject.toml`** 为准。

## 数据库类型

| 用途 | 技术 | 备注 |
|------|------|------|
| 治理 / KPI / 作业状态 | PostgreSQL | ORM：`backend/app/models/` |
| 分析事实与健康检查 | DuckDB（文件路径默认 `data/moss.duckdb`）| 多条只读查询与物化写入 |
| 缓存 / broker | Redis | 设置项见 `MOSS_REDIS_DSN` |
| 归档 | MinIO 或本地 `MOSS_LOCAL_ARCHIVE_PATH` | 由 `MOSS_OBJECT_STORE_MODE` 控制 |

## 当前启动方式（文档与脚本约定）

- **Windows 一键**：`scripts/dev-up.ps1`（README：Frontend `5888`，API `7888`，健康检查示例 `127.0.0.1:7888`）。
- **分拆脚本**：`dev-postgres-up.ps1`、`dev-api.ps1`、`dev-worker.ps1`、`dev-frontend.ps1`。
- **Docker Compose**：`docker compose up ...` → API 映射文档基线 **`8000`**，前端 **`5173`**（与本机 dev 端口 **不一致**，属环境与文档混用的审计关注点）。
- **Vite 代理**：`frontend/vite.config.ts` 默认 `MOSS_VITE_API_PROXY ?? http://127.0.0.1:7888`，同时代理 `/ui`、`/api`、`/health`。

## 主要业务模块（后端域）

损益与经营：`pnl`、`pnl_bridge`、`ledger_pnl`、`product_category_pnl`、`qdb_gl_monthly_analysis`、`balance_analysis`、`adb_analysis`。  
债券与组合：`bond_analytics`、`bond_dashboard`、`positions`、`campisi_attribution` / `pnl_attribution`。  
市场与宏观：`market_data_*`、`macro_vendor`、`macro_bond_linkage`、`external_data`、`research_calendar`。  
风险：`risk_tensor`、`credit_spread_analysis`、`cashflow_projection`。  
执行层 UI：`executive`。  
多维：`cube_query`。  
其他：`ledger` 导入、`source_preview`、`liability_analytics`、`kpi`、`agent`、`health`。

## 已实现页面（工作台，概览）

`routes.tsx` + `navigation.ts`：**live** 页面包括驾驶舱首页、经营分析、债券分析、跨资产驱动、资产负债、余额变动、决策事项、负债分析、损益与桥接、产品损益、损益归因、风险张量、集中度监控、现金流预测、KPI、团队绩效（例外标记）、台账与总账损益、债券总览、持仓透视、日均、市场数据、中台配置等。  
**placeholder / 隐藏**：如 Source Preview、`/reports` 报表中心、风险总览、新闻事件、多维查询、`/agent` 等——多数仍挂载占位组件。

## 已实现 API（概览）

前缀高度分裂：`/api/*`、`/ui/*`、`/health/*`；`liability_analytics` 等模块在 **`APIRouter` 无前缀** 情况下直接声明以 `/api/...` / `/ui/...` 开头的路径，与同文件风格不统一。**完整枚举见 `03_BACKEND_API_MAP.md`**。

## 疑似未完成 / 半成品（静态证据）

- **Executive**：`/ui/home/overview`、`summary`、`pnl/attribution` 已接线；`/risk/overview`、`home/contribution`、`home/alerts`、`home/snapshot` 等直接 **503 Reserved**。
- **宏观 / Choice 供应商面**：`macro_vendor`、`choice_news` 多个 handler 首部调用 `_raise_*_reserved_surface()` → **503**，与「某些 UI 仍可走代理」共存，易造成「接口存在但不可用」观感。
- **Campisi**：`pnl_attribution/workbench.py` 中 `build_campisi_attribution` 对 **利差/选股效应**标注 **STUB**，需信用曲线等业务数据。
- **前端**：`LiabilityAnalyticsPage` 等对 `ApiClient` 方法与类型定义 **不同步**时会出现编译错误（详见 `08`）。

## 最可能的技术债（优先阅读顺序）

1. **端口与环境矩阵分裂**：Compose `8000/5173` vs 脚本 `7888/5888` vs 测试中 `localhost:8000`。  
2. **`client.ts` 巨型聚合**：与新 endpoint 增长点冲突（`AGENTS.md` debt guardrails）。  
3. **`float` 与 `Decimal` 混用**：`core_finance` 部分聚合用 Decimal，工作台层大量 `dict`/`float`。  
4. **鉴权模型偏阶段一**：header / 环境变量 / 操作系统用户回退，`ensure_user_allowed` 仅点在部分写入类路由。  
5. **路由 `response_model` 稀缺**：多数是 `dict[str, object]`，OpenAPI / 校验弱，前后端契约靠约定与手写 TS 类型。  
6. **占位与 503**：导航仍展示但路由占位或后端 reserved，产品与合规需区分「未实现」vs「围栏」。
