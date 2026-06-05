# 07 — 错误与风险静态扫描摘要

以下为 **在本次生成资料包过程中的自动化检索 + 近期命令结果摘录**，不构成完整安全审计或渗透结论。

---

## A. TODO / FIXME

- **`backend/`（`app/` 范围）**：`TODO`/`FIXME` **未命中**（可能团队使用中文「待办」或未标注）。  
- **`frontend/src`**：同上 **未命中**。

---

## B. console.log / print

| 类别 | 发现 |
|------|------|
| `console.log` | `frontend/src` **未发现**命中（可能存在 `console.error`/`warn`）|
| `print(` | **`backend/app/tasks`** 若干 CLI 脚本 `print(..., file=sys.stdout)`：`choice_stock_materialize_run.py`、`fx_mid_backfill.py`、`livermore_position_snapshot_run.py`、`formal_balance_pipeline.py` |

---

## C. 硬编码 URL / Token / Password

| 模式 | 发现 |
|------|------|
| 测试中 `localhost:8000` | `frontend/src/test/ApiClient.test.ts`、`BondAnalyticsView.test.tsx` 等多处 → 与生产/文档端口 **不一致风险** |
| OpenAPI scaffold | `bond-analysis-foundation/api-documentation/openapi.yaml`：`http://localhost:8000` |
| 业务提示写死端口 | `BalanceMovementAnalysisPage.tsx`：`7888` |
| 「类密钥」字面量 grep | **`password`、`secret`、`token`、`api_key` 赋值** 在业务文件 **未发现明显硬编码泄露**（Settings 默认值 `minioadmin` 等为 **开发默认**，须防误上生产）|

---

## D. Mock 数据

- `frontend/src/api/client.ts`：巨量 mock ledger / Campisi block。  
- `frontend/src/mocks/*.ts`、`ledgerPnlMocks.ts`、`campisiMocks.ts`、各 feature `*Mocks*`。  

---

## E. TypeScript **`any`** 与宽松类型

| 文件 | 说明 |
|------|------|
| `executive-dashboard/components/OverviewSection.tsx` | ESLint：**`Unexpected any`**（与 `npm run lint` 失败同源）|

---

## F. try / except 「吞错」或宽捕获

| 位置 | 模式 |
|------|------|
| `core_finance/bond_four_effects.py` `_get_bond_field` | `except (TypeError, ValueError)` 末尾 **`pass`**（日志后吞掉）——易掩 **pd 缺失**环境问题 |
| `adb_analysis.py` | `adb_comparison`、`adb_monthly` 使用 **`except Exception as e`** → HTTP 500 + 字符串（可能信息泄露栈外文本）|

---

## G. 「空数组 / 默认值」伪装有数

多处服务在 Duck 空集时返回 **结构完整、数值为零** envelope；前端须依赖 `result_meta` / banner ——若 UI 省略元数据易出现 **静默空态**。**需结合页面逐项核**。

---

## H. float 与 Decimal 混用

- **核心**：`risk_tensor`、`bond_four_effects`、`attribution_core` → **Decimal**。  
- **工作台 JSON**：`pnl_attribution/workbench.py` → **float** 居多。  
- **Kpi ORM**：`Numeric` ↔ Python `float` 注解。**审计转换链**。

---

## I. 日期硬编码 / 不一致

| 迹象 | |
|------|---|
| 测试数据 `2025-06-03`、`2026-03-31` 等散落于 `**/test/**/*` |
| README `Today's` 与用户环境依赖 |

---

## J. API 端口与代理（7888 / 8000 / 5173）

| 来源 | 端口 |
|------|------|
| `scripts`、`vite`、前端错误 copy | **5888 / 7888** |
| `docker-compose` 文档、`openapi` scaffold、Vitest fetch | **8000 / 5173** |

→ **网关、CORS、e2e、口头运维**易产生 **误判「接口挂了」实为连错端口**。

---

## K. CORS

`backend/app/main.py`：`allow_origins` 来自 **`MOSS_CORS_ORIGINS` 逗号拆分**，`allow_credentials=True` + **通配 methods/headers**。生产若 **镜像 dev 原点列表过宽**，有 **滥用风险**。

---

## L. 权限校验缺口（静态）

| 画像 | API 示例 |
|------|----------|
| 归因只读 | `/api/pnl-attribution/**` GET **无 Depends** |
| Cube 维度 | `GET /api/cube/dimensions/{fact_table}` **无 auth** |
| 大量 Duck 只读 `/ui/**` GET | balance、pnl 读——依赖网络隔离 expectation |

写入面（台账 import、手工调整、kpi mutate）则更常出现 **`ensure_user_allowed`**。

---

## M. SQL 拼接风险

- **偏好**：Parameterized DuckDB / SQLAlchemy。  
- **审计**：对 `duckdb_repo`、手写 `execute(f"...")`** 下一轮人工 spot-check**。

---

## N. N+1 / 大表分页 / 缓存

| 议题 | |
|------|---|
| N+1 | ORM KPI 读写路径相对简单；Duck 「宽表聚合」须在 service _profiler 上轮询 |
| 分页 | Ledger positions API 暴露 `page`/`page_size`；其它列表未必统一 |
| 缓存 | Redis + governance manifests；heavy compute **未必**每层有 HTTP 缓存头 |

---

## O. ESLint / Typecheck / Pytest **当前红点**（与风险叠加）

参见 `08_RUN_AND_TEST.md`：**lint errors**、`tsc -b` build、`pytest` collect ImportError、`Python 3.14` vs `pyproject` `>=3.11`。**CI 与消费者环境漂移**本身就是一种发布风险。

---

## P. 「前后端不一致」显性列表（截至本次 build）

来自 `npm run build`：

- **`LiabilityAnalyticsPage.tsx`**：`getCockpitWarnings`、`getContributionSplit` **不是** `ApiClient` 成员。  
- **`GridContainer` / `DashboardBondHeadlineSection`**：**props / union 类型** 不匹配。  
- **`KpiCard.tsx`**：**CSSProperties** 字符串 vs 字面量联合类型。  
- **`crossAssetTrendChart.ts`**：ECharts `legend` typing。  
- **多个 `BalanceAnalysisPage.test.tsx` mock**：缺 `calendar_days_inclusive`、`adb_denominator_basis`——**契约演进未同步测试**。
