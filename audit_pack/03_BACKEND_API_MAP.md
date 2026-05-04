# 03 — 后端 HTTP API 清单（扫描）

生成方式：枚举 `backend/app/api/routes/*.py` 中 `APIRouter` 前缀与 `@router.(get|post|put|delete|patch)`；结合 `Depends(get_auth_context)` / `ensure_user_allowed` grep。

**通则**

- **鉴权**：`get_auth_context` 从 Header `X-User-Id`、`X-User-Role` 或环境变量、OS 用户名回退，默认 **非严格 JWT**。
- **`ensure_user_allowed`**：查询 Postgres `user_role_scope`，失败抛 `PermissionError` → 一般由路由转 `403/502`。
- **多数路由无 `response_model`**：标注为 **`dict`/隐式 JSON**；契约维护压力在前端 TS 与业务文档。
- **异常**：多数 DuckDB 类服务用 `HTTPException`；少量 `bare except`/宽 `except Exception`。

---

## A. PnL / 归因 / Campisi（重点）

| Method | Full path | Handler | Service / 备注 | Auth |
|--------|-----------|---------|-----------------|------|
| GET | `/api/pnl-attribution/volume-rate` | `volume_rate` | `pnl_attribution_service.volume_rate_attribution_envelope` | 无 Depends |
| GET | `/api/pnl-attribution/tpl-market` | `tpl_market` | `tpl_market_correlation_envelope` | 无 |
| GET | `/api/pnl-attribution/composition` | `composition` | `pnl_composition_envelope` | 无 |
| GET | `/api/pnl-attribution/summary` | `summary` | `attribution_analysis_summary_envelope` | 无 |
| GET | `/api/pnl-attribution/advanced/carry-rolldown` | `carry_rolldown` | `carry_roll_down_envelope` | 无 |
| GET | `/api/pnl-attribution/advanced/spread` | `spread` | `spread_attribution_envelope` | 无 |
| GET | `/api/pnl-attribution/advanced/krd` | `krd` | `krd_attribution_envelope` | 无 |
| GET | `/api/pnl-attribution/advanced/summary` | `advanced_summary` | `advanced_attribution_summary_envelope` | 无 |
| GET | `/api/pnl-attribution/advanced/campisi` | `campisi` | `campisi_attribution_envelope` | 无 |
| GET | `/api/pnl-attribution/campisi/four-effects` | (campisi 路由模块) | `campisi_*_service` 族 | 见 `campisi_attribution.py` |
| GET | `/api/pnl-attribution/campisi/enhanced` | 同上 | 同上 | 无 |
| GET | `/api/pnl-attribution/campisi/maturity-buckets` | 同上 | 同上 | 无 |
| GET | `/api/pnl/dates` | (`pnl.py`) | — | 无 |
| GET | `/api/pnl/data` | | | 无 |
| GET | `/api/pnl/bridge` | | | 无 |
| GET | `/api/pnl/overview` | | | 无 |
| POST | `/api/data/refresh_pnl` | | | **`Depends(get_auth_context)`**，无 scope 检查时仅身份 |
| GET | `/api/data/import_status/pnl` | | | 无 |
| GET | `/api/ledger-pnl/dates` | `ledger_pnl.py` | | 无 |
| GET | `/api/ledger-pnl/data` | | | 无 |
| GET | `/api/ledger-pnl/summary` | | | 无 |
| — | `/ui/pnl/product-category*` | `product_category_pnl.py` | 产品与手工调整 **读写** | `refresh`、`manual-adjustments*` 等有 **`ensure_user_allowed`** |

**关注点**：归因只读链路普遍 **缺资源级 ACL**（与 KPI/台账导入等写入面不一致）；`/api/data/refresh_pnl` 有权调用头即可触发正式链路（需对齐运维预期）。

---

## B. Bond analysis / Portfolio / Dashboard

| Method | Full path（前缀拼接） | 文件 | Service 方向 |
|--------|---------------------|------|--------------|
| GET | `/api/bond-analytics/*` dates, return-decomposition, benchmark-excess, … | `bond_analytics.py` | `bond_analytics_service` 系列 |
| POST | `/api/bond-analytics/refresh` | 同上 | 物化/刷新 |
| GET | `/api/bond-dashboard/*` | `bond_dashboard.py` | 聚合 KPI |
| GET | `/api/positions/*` | `positions.py` | 持仓透视 |
| GET | `/api/credit-spread-analysis/detail` | `credit_spread_analysis.py` | 信用利差明细 |

---

## C. KPI / Report

| Method | Full path | 鉴权概要 |
|--------|-----------|-----------|
| GET/POST… | `/api/kpi/**` metrics/values/report 等 | 部分 **GET** 无 scope；写入类带 **`ensure_user_allowed`**（resource `kpi.metric`/`kpi.value`）|

---

## D. Ledger / Dashboard / Bank book

| Method | Full path | 鉴权 |
|--------|-----------|------|
| POST | `/api/ledger/import` | `ensure_user_allowed` `ledger.data` import |
| GET | `/api/ledger/dashboard`, `/positions`, … | 多读无 ACL |

---

## E. Market data / Macro / External / Calendar / News

| Method | Full path | 备注 |
|--------|-----------|------|
| GET/POST | `/ui/market-data/*` Livermore、`/api/macro-bond-linkage/analysis` | 读写组合见源文件 |
| GET/POST | `/ui/news/*`、`/api/news/tushare-npr/ingest` | ingest 503 reserved + 权限骨架 |
| GET | `/ui/calendar/supply-auctions` | |
| GET | `/api/external-data/**` catalog/series | 外部序列只读 |

`macro_vendor`：多数 GET/POST **首行 503 Reserved**（治理边界占位）。

---

## F. Liability / Asset-liability / Risk tensor

| Method | Full path | 备注 |
|--------|-----------|------|
| GET | `/api/risk/buckets` 等 (`liability_analytics.py`，**无前缀 Router**)| 路径内嵌 `/api/...`，与 **`/api/risk/tensor`（风险张量）** 命名空间 **部分重叠语感**，需严防网关规则冲突 |
| GET | `/api/risk/tensor/dates`、`/api/risk/tensor` | `risk_tensor_service` |
| GET | `/ui/liability/business-context` | 知识简报 |

---

## G. Cube / Agent / Preview / Governance-ish

| Method | Full path | 鉴权 |
|--------|-----------|------|
| POST | `/api/cube/query` | `response_model=CubeQueryResponse` + **`Depends(get_auth_context)`** |
| GET | `/api/cube/dimensions/{fact_table}` | **无 `Depends`**（潜在信息暴露面，见 `07`） |
| POST | `/api/agent/query` | **`Depends`** + envelope |
| GET/POST | `/ui/preview/source-foundation*` | refresh 路由带 auth |

---

## H. Balance analysis / Movement / GL / Misc

| 前缀 | 文件 | POST 刷新 / 权限 |
|------|------|------------------|
| `/ui/balance-analysis` | `balance_analysis.py` | `refresh`、`decision-items/status`：**auth + scope** |
| `/ui/balance-movement-analysis` | `accounting_asset_movement.py` | POST refresh：**auth** |
| `/ui/qdb-gl-monthly-analysis` | `qdb_gl_monthly_analysis.py` | 多条 **ensure_user_allowed** |
| `/health/*` | `health.py` | 无 |

---

## I. Executive UI shell

前缀 `/ui`（`executive.py`）：`home/overview`、`summary`、`pnl/attribution` → 已实现；其余多个路由 **`HTTPException 503`**（Reserved）。

---

## J. 「疑似未接前端 / 围栏」的快速信号

| 现象 | API / 示例 |
|------|------------|
| 503 + detail 明示 reserved | `macro_vendor`、`choice_news`、`executive` 部分 |
| Cube 工作台导航 placeholder | `/cube-query` 页面占位，后端 `/api/cube` 已实 |
| 单元测试期望 `localhost:8000` | `frontend/src/test/ApiClient.test.ts` 等与 dev `7888` 脚本并存 |

前后端字段：以 `frontend/src/api/contracts.ts` 注释对齐路径为线索；若有 TS build 报错（如 Liability 缺失方法）即有 **显性不同步**。详见 `04`、`07`。

---

## K. HTTP 方法与文件索引（全集速查）

- `backend/app/api/routes/accounting_asset_movement.py` — `/ui/balance-movement-analysis`  
- `adb_analysis.py` — `/api/analysis/adb*`  
- `agent.py` — `/api/agent/query`  
- `balance_analysis.py` — `/ui/balance-analysis/*`  
- `bond_analytics.py` — `/api/bond-analytics/*`  
- `bond_dashboard.py` — `/api/bond-dashboard/*`  
- `campisi_attribution.py` — `/api/pnl-attribution/campisi/*`（与 `pnl_attribution.py` **共享路径前缀**，OpenAPI 中合并呈现）  
- `cashflow_projection.py` — `/api/cashflow-projection`  
- `choice_news.py` — `/ui/news`、`/api/news`  
- `credit_spread_analysis.py` — `/api/credit-spread-analysis/detail`  
- `cube_query.py` — `/api/cube/query`, `/dimensions/{fact_table}`  
- `executive.py` — `/ui/home/*` 等  
- `external_data.py` — `/api/external-data/*`  
- `health.py` — `/health/*`  
- `kpi.py` — `/api/kpi/*`  
- `ledger.py`、`ledger_pnl.py` — `/api/ledger*`, `/api/ledger-pnl/*`  
- `liability_analytics.py` — 无前缀，`/api/...` `/ui/liability/...` 直挂  
- `macro_bond_linkage.py`、`macro_vendor.py`  
- `market_data_livermore.py`、`market_data_ncd_proxy.py`  
- `pnl.py`、`pnl_attribution.py` — 同上  
- `positions.py`、`product_category_pnl.py`  
- `qdb_gl_monthly_analysis.py`、`research_calendar.py`  
- `risk_tensor.py`、`source_preview.py`  
