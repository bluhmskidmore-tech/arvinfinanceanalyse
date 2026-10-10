# 审计报告：计算模块、页面链路串联与守卫有效性（系统级第一轮）

- 状态：**只读审计，未修改任何生产代码、测试、数据或契约**
- 审计日期：2026-09-02
- 代码基线：`bef54b58`（HEAD）。工作区另有约 690 个未提交改动（`frontend/src` 341 个、`backend/app` 112 个、`tests/golden_samples` 37 个，见 `docs/plans/2026-08-27-uncommitted-work-split-plan.md`）。本报告的静态盘点扫描的是**工作区现状**；两项红灯守卫涉及的文件在工作区无本地改动，结论对 HEAD 成立。
- 审计范围：五条并行取证线
  - A 线 计算模块：`backend/app/core_finance/` 全部 185 个模块
  - B 线 分层边界：`frontend -> api -> services -> core_finance/repositories -> storage` 的守卫测试实际检查内容
  - C 线 页面串联：`navigation.ts` 中 38 条 `readiness: "live"` 路由，从页面组件到 API client、后端路由、service、core_finance 的静态链路
  - D 线 契约漂移：`docs/page_contracts.md`、`docs/live_route_maturity.md`、OpenAPI 基线、`result_meta`
  - E 线 测试有效性：跳过登记、金样本捕获状态、PR 门禁与定时全量的覆盖差
- 与既有审计的关系：`docs/audits/2026-06-10-calculation-logic-audit.md`（计算逻辑审计，11 项 P1）的遗留项现状见 §7；`docs/audits/2026-09-02-market-overview-page-audit.md` 已对 `/market-overview` 及 6 个子页做过浏览器级审计，本报告不重复其发现。
- 证据留存：`.tmp-agent/system-audit/`
  - `inventory_core_finance.py` → `core_finance_inventory.json` / `core_finance_inventory.md` / `core_finance_summary.json`
  - `formal_modules_table.py` → `formal_modules_table.md`
  - `page_chain_inventory.mjs` → `page_chain_inventory.json` / `page_chain_inventory.md`
  - `trace_import_path.mjs`（mock 进入生产闭包的导入链）、`build_matrix.mjs` → `matrix_table.md`
  - pytest 日志：`lineD_pytest_a.log`（契约组，93 通过 1 失败）、`lineD_pytest_b.log`（金样本组，41 通过）

**一句话结论**：正式计算主干（余额、PnL、桥接、风险张量、债券主链）Decimal 纪律完好、28 组金样本的 capture-ready 与 release-matrix 门禁全部通过、OpenAPI 基线与 `result_meta` 门禁全绿，**未发现 P0**。但系统的"串联"目前主要靠**前端**完成：五个一级首页共用同一组 module-home 派生模型，`productCategoryPnlPageModel.ts` 里一段 150 行、写死 H1 月份下标的"候选监控"金融计算被 4 个页面复用，2026-06 审计的信用利差热力图前端聚合（P1 #11）经核实是后端从未供数的死分支（§9 已降为 P2）；而本应拦住这些的"前端不得补算正式指标"守卫只是 8 个 token 的黑名单，且把风险最高的 9 个业务目录整体列入白名单。分层边界的 79 个守卫用例中有 2 个在 HEAD 已经红灯（一项自 08-13、一项自 08-15），因为它们都不在 PR 门禁内。

---

## 0. 分级清单

| 级别 | 编号 | 问题 | 证据 |
| --- | --- | --- | --- |
| P1 | A1（已处置，§9） | 分层边界守卫 2 项在 HEAD 红灯且不在 PR 门禁：`test_no_finance_logic_in_api`（`pnl_attribution.py` 因导入 `KRDAttributionEnvelope` 触发 token `KRD`，自 08-13 `e5345a47`）；`test_service_storage_boundaries::test_choice_news_reserved_ingest_route_has_no_service_ingest_path`（choice-news 排除面新增了 `action="import"` 的 ingest 路由，自 08-15 `d5b3bf74`） | §3.2 |
| P1 | A2 | "前端不得补算正式指标"守卫是 8 个 token 的黑名单，`features/bond-analytics/`、`bond-dashboard/`、`balance-analysis/`、`pnl-attribution/`、`risk-tensor/`、`liability-analytics/` 等 9 个业务目录加 `api/`、`mocks/`、`test/` 整体白名单，另有 34 个文件的片段级/行前缀级例外；任何不含这 8 个词的算式都不会被拦 | §3.1 |
| P1 | C1 | `productCategoryPnlPageModel.ts`（5,373 行）内 `buildProductCategoryManagementMonitoringSurface` 用 `cash/days*365/scale` 反推"达标所需收益率"、算负债抵消比、衍生品波动率、Q1/Q2/H1 均值，月份下标写死（`[4]` = 5 月、`slice(0,3)` = Q1、"1—6 月"），被 `/product-category-pnl`、`/operations-analysis`、`/market-finance`、`/pnl-attribution` 四页复用 | §4.4 |
| P2（原 P1，§9 纠正） | C2 | 2026-06-10 审计 P1 #11 的前端热力图聚合（`buildRatingTenorHeatmapData`，桶映射在前端、未映射行静默丢弃）是**死分支**：后端 `CreditSpreadMigrationResponse` 从未包含 `bond_details`，前端契约把它声明为可选，现网始终走 `concentration_by_rating/tenor` 柱状图回退。风险是一段带自有分桶口径的死代码，而不是现网口径漂移 | §4.4、§7 |
| P1 | C3（后端侧部分处置，§9） | 五个一级首页（`/portfolio`、`/market-overview`、`/risk-overview`、`/performance`、`/reports`）共享同一组 module-home 派生模型（`moduleHomeModel.ts` 4,505 行、`riskHomeAdapter.ts`、`portfolioDecisionModel.ts` 等 11 个文件），并把 `pnl/pnlByBusinessPageModel.ts`、`bond-analytics/adapters/bondAnalyticsAdapter.ts`、`market-data/lib/marketDataTerminalModel.ts` 等子页模型拉进闭包；首页汇总数（`sumIndustryMarketValue`、`zqtzAssetCnyMarketValue`）由前端对子载荷行 float 求和得到 | §4.3 |
| P1 | D1 | 38 个 live 页面按项目自己的成熟度台账只有 6 个是 `governed`；9 个 `governed-mixed-source`、10 个 `candidate`、13 个 `temporary-exception`；导航层 18 页挂 `governanceStatus: "temporary-exception"`；7 页无 PAGE 契约靠白名单放行；页面就绪门禁自述 `business_contract_certified_count=0; evidence_pending_count=23` | §5.1 |
| P2 | A3（部分处置，§9） | `core_finance` 中 47 个模块无任何静态调用方：28 个是 `macro.toolkit.scripts` 包及其 27 个脚本（`runner.py` 以 `runpy.run_path` 执行，排除面）、6 个 caliber 规则模块靠副作用注册、5 个已标注 DORMANT/DEPRECATED、6 个 `balance_workbook/` 委托壳、1 个包根，以及 1 个未标注的死模块 `pnl_yield_display.py`（docstring 声称"外部仍按 V1 名字 import"，实际零调用方） | §2.1 |
| P2 | A4 | 正式主线里 `campisi.py`（29 处）与 `action_attribution.py`（27 处）在出口把 Decimal 金额 `float(...)` 后返回；`adb_deep_analytics.py`（970 行）全程 float、无 Decimal、仅 1 个测试文件 | §2.3 |
| P2（§9 新增） | A5 | 正式信用利差核心 `credit_spread_analysis.py` 的几处"缺失当 0"语义待业务复核：`ytm` 为 NaN / 不可解析时经 `safe_decimal` 归 0，`_normalize_ytm_to_pct` 返回 `Decimal("0")` 而非 `None`，该券被保留并产出 `credit_spread = −基准 × 100` bp（第 87-93、238-240 行）；曲线只含词表外期限标签时 `build_full_curve` 给 13 个标准期限全填 0，基准静默为 0、利差 = ytm × 100（第 77-80、107 行）；负市值行保留并产生负权重（第 88、95、126 行）；历史分位的锚点是历史序列最大日期而非当前日期（第 179 行），陈旧历史不会暴露"过期"信号 | §9 |
| P2 | C4 | 全应用没有共享的"业务日期"上下文：10 个 feature 各自调 `getBalanceAnalysisDates` 取"最新"，PnL / 债券 / 风险张量 / 行情各有自己的 dates 端点，跨域页面（一级首页、`/market-finance`、`/operations-analysis`）把不同 as-of 的读数并排展示无对齐提示（`/market-overview` 审计 S7 已实测到 4 天差） | §4.5 |
| P2 | C5 | 后端 `GET /ui/market-overview/snapshot`（`market_overview_service`）已落地但无任何 live 页面引用；`GET /api/pnl/data`、`/ui/home/overview`、`/ui/home/summary`、`/ui/risk/overview`、`/ui/home/contribution` 等 70 条路由不被任何 live 页面引用（含 `kpi.py` 9 条为动态拼路径的假阳性） | §4.2 |
| P2 | C6 | live 页面内嵌演示数据：`/operations-analysis` 静态示例区（已折叠并打"静态示例数据"徽标）、`/team-performance` 考核目标"前端内置演示数据"（导航 readinessNote 自述）；`/` 的 13 个 mock 文件仅经 `loadMockClient()` 动态 import，按 `VITE_DATA_SOURCE` 门控，不是失败兜底 | §4.4 |
| P2 | D2 | `test_page_contract_metric_bindings_exist_in_metric_dictionary` 红灯：`PAGE-POS-001` 已有 `MTR-*` 行但仍在 `PAGES_WITHOUT_FORMAL_METRIC_BINDINGS` 白名单（工作区 `docs/page_contracts.md` 有未提交改动，可能是并行会话在途工作） | §5.2 |
| P2 | E1（已处置，§9） | PR 门禁（`scripts/backend_release_suite.py` 38 个文件）只含 `test_no_finance_logic_in_frontend.py` 一项边界守卫；`test_no_finance_logic_in_api.py`、`test_api_route_boundaries.py`、`test_service_storage_boundaries.py`、`test_duckdb_write_boundary.py` 只在 main 推送/定时全量 `backend-full-pytest` 中运行，因此 A1 的两项红灯能存活 3 周 | §6.2 |

---

## 1. 方法与限制

五条线全部是静态取证加定向测试，没有浏览器走查（`/market-overview` 组已有 09-02 浏览器审计）。三个脚本的口径需要先说清，否则后文数字会被误读。

**core_finance 调用方**（A 线）按四种导入形态识别：`from backend.app.core_finance.X import`、`from app.core_finance.X import`（测试侧）、包内相对导入 `from .X import` / `from ..X import`、以及字符串懒加载 `import_module("backend.app.core_finance.X")` 和 `workbook_module_name="..."`。`runpy.run_path` 与 `importlib` 副作用注册不在识别范围，所以 §2.2 的"无静态调用方"要结合逐个复核读。

**页面闭包**（C 线）从 `routes.tsx` 的懒加载入口出发，沿相对导入递归，排除 `*.test.*` 与 `test/`、`__fixtures__/`；在 `src/api/client.ts`、`clientContext.ts`、`mockApiClient.ts`、`queryKeys.ts` 四个组合枢纽处停止展开（否则每页都会拿到全部 279 条端点）。端点归因分两路：闭包内业务代码里出现的 `client.xxx(` 方法名映射到各领域 client 文件中该方法体内的路径字面量，加上 `features/`、`layouts/`、`hooks/`、`app/` 内直接出现的 `/ui/...` `/api/...` 字面量（剔除注释行与 `<code>` 文案）。后端侧解析 `APIRouter(prefix=...)` 与 `@router.get(...)` 拼出 279 条完整路径，再按段匹配。这是**静态可达**，不是运行时实际请求：`ModuleWorkbenchHomePage` 用一个组件承接 `/performance` 与 `/reports`，两页因此拿到相同的 24 条端点，其中宏观工具刷新类 POST 只是被引用到而不一定被调用。

**前端计算热点**用 `annualiz|weightedAverage|/ 365|/ 360|* 10000|* 100|Math.(pow|log|sqrt|exp)|.reduce(... +` 计数，≥3 次的文件入选。它只是定位手段，§4.4 逐个读过才下结论；`pnlByBusinessAnnualizedYield.ts` 就是一个假阳性（只做日期差与格式化）。

**定向测试**在一台同时跑着另一会话 `pytest -n 6 tests` 全量与 uvicorn 的机器上执行，耗时不具参考性；`tests/test_codex_page_readiness_gate.py` 与 `tests/test_backend_api_inventory.py` 两个会拉起 PowerShell / 子进程的文件在本次会话内未跑完，本报告不引用它们的结果。

---

## 2. A 线：计算模块（`backend/app/core_finance/`）

### 2.1 规模与可达性

185 个模块、69,534 行。按调用方分三层：109 个被 services / tasks / api / agent / governance / repositories / scripts 至少一处导入，29 个只在 `core_finance` 包内被引用（`curve_engine.*`、`calibers.descriptor/registry`、`balance_analysis_workbook` 经 `balance_workbook/` 兼容壳、`safe_decimal` 等基础件），47 个没有任何静态调用方（合计 12,745 行）。从 38 个 live 页面静态可达的 `core_finance` 模块共 100 个。

47 个无静态调用方的模块逐个复核后分四类：

| 类别 | 数量 | 模块 | 判断 |
| --- | ---: | --- | --- |
| 宏观工具脚本 | 28 | `macro.toolkit.scripts` 包根 + 27 个脚本（`generate_bond_macro_report` 1,526 行、`backtest_cn` 914 行等） | `macro/toolkit/runner.py:149` 用 `runpy.run_path(..., run_name="__main__")` 执行，属排除面（`tests/AGENTS.md` `surface_macro_toolkit`），静态分析天然看不到 |
| caliber 规则 | 6 | `calibers.rules.{accounting_basis, fx_mid_conversion, hat_mapping, issuance_exclusion, subject_514_516_517_merge}` 及 `rules/__init__` | `calibers/__init__.py:27` 以 `import rules as _rules` 触发副作用注册，是设计使然（`formal_scenario_gate` 被 `analysis_adapters.py` 直接导入，不在孤儿集） |
| 已标注休眠/弃用 | 5 | `attribution_daily`、`benchmark_excess`（调用即抛 `DeprecationWarning`）、`credit_spread`、`var_engine`、`risk_metrics` | 2026-08 已由前序审计标注，docstring 写明接线前置条件；包根 `core_finance/__init__.py` 不导出它们，误用风险仅剩显式 import。另有 `krd`、`curve_engine.bootstrapper` 同样标注 DORMANT，但各有 1 个调用方（分别来自同样休眠的 `credit_spread` 与 `curve_engine/__init__`），`attribution_core` 两个函数标注 DEPRECATED |
| 未标注死代码 | 1 | `pnl_yield_display.py`（78 行） | docstring 称"保留模块名以兼容现有调用方（外部仍按 V1 名字 import）"，全仓只有 `tests/test_caliber_migration_hat_mapping.py` 引用；`/api/pnl/data` 路由也不被任何 live 页面引用 |
| 委托壳 / 包根 | 7 | `balance_workbook` 及 5 个 `_*_tables` / `_utils` 委托壳、`curve_engine` 包根 | 无风险 |

`balance_analysis_workbook.py`（1,820 行）值得单说：它是 workbook 的生产权威实现，但 `balance_analysis_workbook_service.py:60` 以字符串 `workbook_module_name="backend.app.core_finance.balance_analysis_workbook"` 懒加载，普通导入扫描会把它误判为孤儿，本次已用懒加载识别覆盖。

### 2.2 测试与金样本挂钩

32 个模块（含包根）没有任何测试文件直接导入：20 个是上述脚本（其余 7 个脚本各有 1 个测试文件引用），1 个是 `macro.toolkit.akshare` 适配壳；`credit_spread_analysis`、`macro.credit_spread_risk`、`macro.liquidity_stress`、`macro.rate_turning_point`、`macro.yield_curve_shape` 经 API/service 层测试间接覆盖（如 `tests/test_credit_spread_analysis.py` 走 `TestClient`）；`balance_workbook._ifrs9_tables`、`balance_workbook.builder` 是委托壳；`calibers.descriptor/registry` 经包根导入被 `test_caliber_descriptor.py` / `test_caliber_registry.py` 覆盖（扫描口径假阴性）；`pnl_constants` 是常量。真正"核心计算只有间接覆盖"的是 `credit_spread_analysis.py`（正式信用利差链路，`credit_spread.py` docstring 明确指认它为正式实现）。

`tests/golden_samples/` 下 28 组样本（全部带 `response.json`）的 capture-ready 与 release-matrix 门禁全部通过（`test_golden_samples_capture_ready.py` + `test_golden_sample_release_matrix.py` + `test_ci_skip_registry.py` 共 41 项通过）。金样本是 API 级信封快照，能按文本关联到的 `core_finance` 模块只有 9 个：`pnl`（GS-PNL-ATTR-WB-A、GS-PNL-BUSINESS-INSIGHTS-A）、`pnl_attribution` / `pnl_attribution.workbench`、`pnl_by_business_insights`、`adb_analytics`（GS-AVERAGE-BALANCE-A / -MONTHLY-A）、`action_attribution`（GS-BOND-ANALYSIS-ACTION-ATTR-A）、`bond_analytics` / `bond_analytics.read_models`（GS-CONCENTRATION-MONITOR-A）、`cashflow_projection`。余额（GS-BAL-*）、桥接（GS-BRIDGE-*）、风险（GS-RISK-*）样本是经 service 间接锁定 `balance_analysis` / `pnl_bridge` / `risk_tensor` 的。

### 2.3 正式主线的数值纪律

41 个正式主线及其基础件模块（`formal_modules_table.md`）里 25 个没有一处 `float(`，`balance_analysis*`、`pnl`、`pnl_bridge`（1,587 行仅 1 处）、`risk_tensor`、`fx_rates`、`cashflow_projection`、`finance_metric_engine`、`product_category_pnl*` 全程 Decimal。三处例外：

- `campisi.py`（957 行，12 个测试文件）：计算在 Decimal，但第 729–734、843–851 行汇总出口 `float(sum(...))`，`by_bond` 行的 `_NUMERIC_BOND_KEYS` 全部 `float(r[k])` 后返回。金额以 float 离开 `core_finance`，靠 service 层 `explicit_numeric` 再包装。
- `action_attribution.py`（478 行，1 个测试 + 1 组金样本）：`pnl_economic` / `pnl_accounting` / `delta_duration` / `total_pnl_from_actions` 等 27 处 `float(...)` 出口。
- `adb_deep_analytics.py`（970 行）：无 Decimal 导入、30 处 `float(`、27 处 `round(`，只有 `tests/test_adb_deep_analytics.py` 一个测试。它服务 `/average-balance`（导航自述"正式余额真源见资产负债分析"，属 `temporary-exception`），但同页与 `/balance-analysis`、`/pnl-by-business`、`/` 共用 `/api/analysis/adb/comparison`。

另有 21 个非正式模块 float 为主且无 Decimal，集中在 `macro.*`、`livermore_*`、`portfolio_backtest`、`vol_target_overlay`、`factor_screen_candidates`——都是策略/观察面，与 `tests/AGENTS.md` 的排除面清单一致。

### 2.4 口径规则的落地方式

六条 caliber 规则（会计基础、Formal/Scenario 门、FX 中间价、H/A/T 映射、发债剔除、514/516/517 合并）以描述符注册在 `calibers` 包，三重保障：`tests/test_caliber_rule_*.py` 六个文件无条件进 release suite；`scripts/check_caliber_gate.py` 按 PR diff 路径触发对应测试；`backend/scripts/audit_caliber_violations.py` 扫描 `services/tasks/schemas/api` 中疑似内联复制并在 CI 以零未豁免违规为门。扫描范围**不含 `frontend/` 和 `core_finance` 自身**——前端只剩 §3.1 的 token 黑名单守着。

---

## 3. B 线：分层边界守卫

### 3.1 守卫实际检查什么

12 个边界守卫文件共 79 个用例，本次定向运行 77 通过、2 失败。按检查强度分三档：

**真结构守卫**（通过）。`test_service_storage_boundaries.py`（`test_duckdb_write_boundary.py` 是它的别名导入）用 AST 断言 api/service 层不打开可写 DuckDB 连接、不调用 repository 的 replace 写入器、不进入 task 写作用域、路由不直接引用 duckdb；`test_repository_task_write_guard.py`、`test_api_deps_guard.py`、`test_backend_import_root_guard.py`、`test_pnl_layer_boundary_guards.py`、`test_balance_analysis_*_boundaries.py`、`test_pnl_bridge_service_boundaries.py` 属同类。这一档是 `frontend -> api -> services -> storage` 方向上真正有牙齿的部分。

**单点守卫**。`test_api_route_boundaries.py` 只检查 `kpi` 一条路由不含 `KpiRepository` / `session.commit` / `_compute_*`。

**token 黑名单**。`test_no_finance_logic_in_frontend.py` 与 `test_no_finance_logic_in_api.py` 用同一份 8 词表：`DV01`、`KRD`、`CS01`、`convexity`、`FVTPL`、`FVOCI`、`债券月均金额`、`formal PnL`。前端版为了让展示代码活下来，把 `features/bond-analytics/`、`bond-dashboard/`、`balance-analysis/`、`balance-movement-analysis/`、`executive-dashboard/`、`liability-analytics/`、`pnl-attribution/`、`risk-overview/`、`risk-tensor/` 九个业务目录连同 `api/`、`mocks/`、`test/` 整目录白名单，再加 14 个文件的片段级例外与 20 个文件的行前缀例外（`moduleHomeModel.ts` 一个文件 20 条前缀）。它能防的是"把 DV01 这个词写进前端"，防不了 §4.4 那种不含任何黑名单词的年化、方差、占比算式；而被白名单整体放过的目录，恰好是最可能出现金融算式的目录。

### 3.2 HEAD 上的两项红灯

`tests/test_no_finance_logic_in_api.py::test_api_layer_does_not_contain_finance_formula_tokens`：`backend/app/api/routes/pnl_attribution.py:12,129` 为 `/advanced/krd` 声明 `response_model=KRDAttributionEnvelope`，schema 类名含 `KRD`。这是 08-13 `e5345a47`（"为 31 个读取端点声明 response_model"）引入的，属 token 守卫的假阳性，但它说明这条守卫三周内没有人跑过。

`tests/test_service_storage_boundaries.py::test_choice_news_reserved_ingest_route_has_no_service_ingest_path`：守卫断言 choice-news 保留路由不得出现 `("choice_news.data", "import")` 权限作用域，而 `backend/app/api/routes/choice_news.py:76-77` 现在有 `ensure_user_allowed(resource="choice_news.data", action="import")`，对应 `POST /ui/news/tushare-npr/ingest` 与 `POST /api/news/tushare-npr/ingest`（两条都不被任何 live 页面引用）。引入提交是 08-15 `d5b3bf74`（"close macro agent and news workflows"）。`tests/AGENTS.md` 把 choice-news 路由启用列为"非默认边界工作"，这条红灯是排除面被推进而 fail-closed 守卫没有同步裁决的实例，需要业务裁决是撤路由还是改守卫。

两项都不在 `RELEASE_SUITE_TESTS`，只会在 `backend-full-pytest`（`if: schedule || push to main`）里以 `ci-full-pytest-failure` issue 的形式出现。

---

## 4. C 线：页面链路串联

### 4.1 页面 × 模块矩阵

38 条 live 路由的静态链路如下。"治理层级"取自 `docs/live_route_maturity.md`（项目自己的台账），"端点"是静态可达的后端路由（匹配/未匹配到后端定义），"service 直接→传递"是路由文件直接导入的 service 数与再展开一层后的数，"core_finance 模块"是经这些 service 静态可达的模块数，"前端计算热点文件"是 §1 启发式命中数。

| 路由 | 治理层级 | 契约 | 端点 | 后端路由文件 | service | core_finance | 热点 |
| --- | --- | --- | ---: | --- | ---: | ---: | ---: |
| `/` | governed-mixed-source | PAGE-DASH-001 | 94/7 | 18 个（accounting_asset_movement … research_calendar） | 33→69 | 64 | 2 |
| `/operations-analysis` | temporary-exception | PAGE-OPS-001 | 9/0 | balance_analysis, choice_news, macro_vendor, product_category_pnl, source_preview | 8→21 | 20 | 3 |
| `/market-finance` | temporary-exception | GAP-MARKET-FINANCE-PAGE | 6/0 | balance_analysis, macro_vendor, product_category_pnl | 5→16 | 19 | 3 |
| `/portfolio` | governed-mixed-source | PAGE-PORTFOLIO-HOME-001 | 23/0 | balance_analysis, bond_dashboard, macro_toolkit, pnl_attribution, risk_tensor | 22→35 | 38 | 4 |
| `/bond-analysis` | candidate | PAGE-BOND-ANALYSIS-001 | 25/4 | agent, bond_analytics, bond_dashboard, credit_spread_analysis, macro_vendor, research_calendar | 12→28 | 19 | 0 |
| `/bond-trading-desk` | candidate | PAGE-BOND-DESK-001 | 5/0 | bond_analytics, credit_spread_analysis, positions | 3→7 | 12 | 0 |
| `/cross-asset` | temporary-exception | PAGE-CROSS-ASSET-001 | 7/1 | macro_bond_linkage, macro_vendor, market_data_livermore, market_data_ncd_proxy, research_calendar | 18→31 | 26 | 2 |
| `/team-performance` | temporary-exception | GAP-TEAM-PERFORMANCE-PAGE | 5/0 | pnl, product_category_pnl, team_performance | 6→20 | 15 | 0 |
| `/decision-items` | temporary-exception | GAP-DECISION-ITEMS-PAGE | 4/0 | balance_analysis | 2→8 | 12 | 0 |
| `/balance-analysis` | governed | PAGE-BALANCE-001 | 17/0 | accounting_asset_movement, adb_analysis, balance_analysis | 4→11 | 21 | 1 |
| `/balance-movement-analysis` | governed | PAGE-BAL-MOVE-001 | 3/0 | accounting_asset_movement | 1→2 | 1 | 2 |
| `/liability-analytics` | governed-mixed-source | PAGE-LIAB-ANALYTICS-001 | 12/0 | adb_analysis, balance_analysis, liability_analytics | 5→13 | 20 | 0 |
| `/market-overview` | governed-mixed-source | PAGE-MARKET-HOME-001 | 19/1 | choice_news, macro_toolkit, macro_vendor | 19→27 | 17 | 5 |
| `/market-data` | governed-mixed-source | PAGE-MKT-001 | 16/1 | external_data, macro_bond_linkage, macro_vendor, market_data_livermore, market_data_ncd_proxy, research_calendar | 19→33 | 26 | 0 |
| `/macro-observation` | candidate | PAGE-MACRO-OBS-001 | 15/0 | macro_toolkit | 16→20 | 15 | 1 |
| `/macro-toolkit` | candidate | PAGE-MACRO-TOOLKIT-001 | 15/0 | macro_toolkit | 16→20 | 15 | 1 |
| `/stock-analysis` | temporary-exception | GAP-STOCK-ANALYSIS-PAGE | 33/5 | agent, choice_news, data_health, macro_toolkit, market_data_livermore, strategy_reports | 38→61 | 45 | 4 |
| `/platform-config` | temporary-exception | GAP-PLATFORM-CONFIG-PAGE | 3/0 | health, source_preview | 3→5 | 4 | 0 |
| `/reports` | candidate | PAGE-REPORTS-HOME-001 | 24/0 | cashflow_projection, cube_query, health, macro_toolkit, macro_vendor, pnl, risk_tensor, source_preview | 30→52 | 40 | 4 |
| `/bond-dashboard` | candidate | PAGE-BOND-001 | 2/0 | bond_dashboard | 1→4 | 6 | 1 |
| `/positions` | candidate | PAGE-POS-001 | 11/0 | balance_analysis, positions | 2→8 | 12 | 0 |
| `/average-balance` | temporary-exception | PAGE-ADB-001 | 6/0 | adb_analysis, balance_analysis | 3→10 | 20 | 0 |
| `/ledger-pnl` | candidate | PAGE-LEDGER-PNL-001 | 13/0 | ledger_pnl | 4→7 | 15 | 0 |
| `/bank-ledger-dashboard` | temporary-exception | PAGE-BANK-LEDGER-001 | 6/0 | ledger | 3→3 | 0 | 0 |
| `/risk-overview` | governed-mixed-source | PAGE-RISK-HOME-001 | 25/4 | agent, bond_analytics, cashflow_projection, macro_toolkit, risk_tensor | 26→42 | 36 | 4 |
| `/risk-tensor` | governed | PAGE-RISK-001 | 3/0 | risk_tensor | 3→5 | 1 | 1 |
| `/concentration-monitor` | temporary-exception | PAGE-CONC-001 | 2/0 | bond_analytics | 2→6 | 11 | 1 |
| `/cashflow-projection` | temporary-exception | PAGE-CFP-001 | 2/0 | balance_analysis, cashflow_projection | 3→10 | 15 | 0 |
| `/performance` | governed-mixed-source | PAGE-PERFORMANCE-HOME-001 | 24/0 | 与 `/reports` 相同（同一组件 `ModuleWorkbenchHomePage`） | 30→52 | 40 | 4 |
| `/kpi` | temporary-exception | GAP-KPI-PERFORMANCE-PAGE | 2/1 | kpi | 2→2 | 0 | 0 |
| `/news-events` | temporary-exception | GAP-NEWS-EVENTS-PAGE | 1/0 | choice_news | 1→3 | 0 | 0 |
| `/product-category-pnl` | governed-mixed-source | PAGE-PROD-CAT-PNL-001 | 19/0 | product_category_pnl, qdb_gl_monthly_analysis | 2→6 | 6 | 2 |
| `/pnl` | governed | PAGE-PNL-001 | 7/0 | liability_analytics, pnl | 6→21 | 17 | 0 |
| `/pnl-bridge` | governed | PAGE-BRIDGE-001 | 4/0 | pnl | 4→17 | 14 | 0 |
| `/pnl-attribution` | governed-mixed-source | PAGE-PNL-ATTR-WB-001 | 21/5 | agent, campisi_attribution, pnl, pnl_attribution, product_category_pnl | 12→36 | 28 | 4 |
| `/cube-query` | candidate | PAGE-CUBE-QUERY-001 | 2/0 | cube_query | 2→3 | 1 | 0 |
| `/pnl-by-business` | candidate | PAGE-PNL-BY-BUSINESS-001 | 11/0 | adb_analysis, pnl | 5→19 | 22 | 6 |
| `/pnl-by-business-insights` | governed | PAGE-PNL-BY-BUSINESS-001 | 2/0 | pnl | 4→17 | 14 | 0 |

三处读法提醒：`/bank-ledger-dashboard`、`/kpi`、`/news-events` 的 core_finance 为 0 是真实的——银行台账 KPI 是 `ledger_analytics_repo.py:122-126` 的 SQL `sum(face_amount)`，KPI 计分在 `kpi_workbench_service`，两者都不是正式金融口径；`/kpi` 的 1 条未匹配端点是 client 用 `/api/kpi${path}` 拼路径的静态盲区；`/` 的 7 条未匹配全部是 agent 工作区与 `${suffix}` 拼接，不是缺路由。

### 4.2 端点复用与孤立路由

279 条后端路由中 203 条被至少一个 live 页面静态引用，50 条被 ≥3 页共用。复用最广的是 `GET /ui/balance-analysis/dates`（10 页）、`/ui/macro/choice-series/latest`（8 页；`/market-overview` 审计 S5 已实测它在全应用注册了 6 个不同 react-query key）、以及 `/ui/macro/toolkit/*` 的 13 条端点（8 页——五个一级首页因共享 market home hooks 而全部静态可达，这是 §4.3 耦合的直接后果）。

70 条路由不被任何 live 页面引用。剔除 `kpi.py` 的 9 条假阳性与 `agent_workspace.py` 的 10 条（agent 路由 gated）后，值得业务判断的有：`GET /ui/market-overview/snapshot`（`docs/plans/2026-09-02-market-overview-fix-dispatch/WP-G` 已落后端、WP-H 前端切换未落，在途）；`executive.py` 的 `/ui/home/overview`、`/ui/home/summary`、`/ui/risk/overview`、`/ui/home/contribution`（E1 稳定面，被 release suite 金样本锁定但页面不再消费）；`GET /api/pnl/data`、`/api/pnl/basis-bridge`（`/pnl` 页只消费 7 条端点，这两条是 V1 兼容面）；`source_preview.py` 5 条与 `external_data.py` 5 条（排除面）。

### 4.3 五个一级首页的耦合

`/portfolio`、`/market-overview`、`/risk-overview`、`/performance`、`/reports` 的闭包交集是 11 个 `features/workbench/module-home/` 文件：`moduleHomeModel.ts`（4,505 行）、`moduleHomeConfig.ts`、`riskHomeAdapter.ts`、`portfolioDecisionModel.ts`、`portfolioReadinessGate.ts`、`marketDeskIntelModel.ts`、`marketEvidenceVisual.ts`、`marketHomeRowEnrichment.ts`、`moduleHomeQueryPermission.ts`、`marketModuleDrilldowns.ts`、`portfolioModuleDrilldowns.ts`。这组文件又向下拉入子页面模型：`pnl/pnlByBusinessPageModel.ts` 与 `pnl/zqtzAdbAvgRollup.ts`（6 页共享）、`bond-analytics/adapters/bondAnalyticsAdapter.ts`（7 页）、`market-data/lib/marketDataTerminalModel.ts` 与 `marketDataFormat.ts`（6–7 页）、`bond-dashboard/utils/format.ts`（7 页）。

后果有两层。工程上，`/performance` 与 `/reports` 这两个和市场无关的首页，闭包里带着市场工具刷新 POST 与 Livermore 读链路的代码；改 `pnlByBusinessPageModel.ts` 一处会同时影响 6 个路由，而 `frontend/AGENTS.md` 的 Tier 3 影响分析目前只能靠 GitNexus 手工做。业务上，首页汇总数有一部分是前端从子载荷行求和得到：`moduleHomeModel.ts:3232-3244 sumIndustryMarketValue` 把行业分布各项 `total_market_value` 以 JS number 累加后再包装成 `Numeric`；`:1158-1172 zqtzAssetCnyMarketValue` 对 `basis_breakdown` 行求和用于评级 tie-out 副标题；`:1133-1156 distributionRows` 在后端未给总量时用各项之和当分母。后端给的是 Decimal 字符串，前端求和是 float，首页与子页面在大额上可能出现末位不一致。`/ui/market-overview/snapshot` 的方向（把首页聚合搬回后端）是对的，但目前只覆盖市场首页且尚未接线。

### 4.4 前端里的金融计算

启发式命中的 23 个文件逐个读后，分三类。

**假阳性 / 纯展示**：`pnlByBusinessAnnualizedYield.ts`（docstring 明确"后端返回百分点，本文件只负责展示格式化"，`/365` 是日期差）、`zqtzAdbAvgRollup.ts`（2026-06 P1 #10 的整改结果：父级日均已由后端 `/api/pnl/by-business-ytd` 返回，前端只做来源解析）、`pnlByBusinessExport.ts`（导出列映射）、`PnlByBusinessPage.tsx`（22 处全是 `formatAnnualizedYieldPctDisplay(row.annualized_yield_pct)` 之类的格式化）、`riskHomeAdapter.ts`（占比 → 百分数、柱宽）。`/pnl-by-business` 这一域的前端纪律是好的。

**分析性金融计算（P1 C1）**：`product-category-pnl/pages/productCategoryPnlPageModel.ts:4640-4830` 的 `buildProductCategoryManagementMonitoringSurface`。它取 TPL 行的 `scale`、`business_net_income`、`yield_pct`、`baseline_ftp_rate_pct`、`days`，用

```ts
const requiredYield = currentTplFtp + (threshold.targetPnl / currentTplScale) * (365 / currentTplDays) * 100;
const liftBp = (requiredYield - currentTplYield) * 100;
```

反推"达到 5 月 / H1 均值 / Q1 均值净营收所需收益率"，再算负债端正负池抵消比（`:4757-4760`）、衍生品 6 个月 PnL 的总体标准差（`:4798-4804`）、前三月集中度、Q1/Q2/H1 均值与"H2 按 Q2 节奏"外推。这正是后端 `core_finance/product_category_pnl.py:278` 注释里的期间收益率公式 `cash/days*365/scale` 的反函数，在前端重写了一遍。月份下标写死：`safeTplPnlValues[4]` 配文案"达到 5 月净营收水平"、`slice(0, 3)` 为 Q1、`slice(3, 6)` 为 Q2、`periodLabel: "${year} 年 1—6 月"`——只对"报告期 = 6 月"成立，7 月起 `h1Snapshots` 语义即失效。输出标了 `metricStatus: PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS`（候选），这是对的，但 §4.3 已说明这个模型被 `/operations-analysis`、`/market-finance`、`/pnl-attribution` 三个非产品分类页面导入。token 守卫对它零覆盖。

**死分支（C2，§9 纠正为 P2）**：`bond-analytics/components/creditSpreadViewSupport.ts:187-221 buildRatingTenorHeatmapData` 确实在前端持有评级 / 期限桶映射并做 float 累加，但它的输入 `data.bond_details` 来自 `GET /api/bond-analytics/credit-spread-migration`，而后端 `CreditSpreadMigrationResponse`（`schemas/bond_analytics.py:525-581`）没有这个字段，`bondAnalyticsClient.ts:272` 只在响应里有数组时才映射，mock 客户端也返回空数组。因此 `CreditSpreadView.tsx:206-219` 的热力图分支在任何数据源下都不会渲染，用户看到的一直是 `concentration_by_rating/tenor` 的柱状图。它是一段带着自有口径的死代码——若将来后端补出 `bond_details`，这套前端分桶会在没有任何契约约束的情况下自动激活。处置应是删除该分支（或由产品决定是否作为后端聚合的正式图表重做），而不是把前端聚合"搬"到后端。

**已披露的内嵌演示数据（P2 C6）**：`OperationsAnalysisPage.tsx:21-24` 静态导入 `businessAnalysisWorkbenchMocks.ts` 的 `OPERATIONS_CALENDAR_MOCK` / `OPERATIONS_WATCH_ITEMS`，渲染在默认折叠、带"静态示例数据"徽标的 `<details>` 内；`/team-performance` 导航 readinessNote 自述"考核目标分为前端内置演示数据"。`/` 闭包里的 13 个 mock 文件（`homeMarketTickerMockClient.ts`、`bondAnalyticsMockClient.ts`、`mocks/workbench.ts`、`fixtures/dashboardCoreWorkbenchSamples.ts` 等）全部经 `homeSupplementalClient.ts:295-325 loadMockClient()` 与 `homeMarketTickerClient.ts` 的动态 `import()` 进入，只在 `VITE_DATA_SOURCE=mock` 下装载，`client.ts:175-198` 在生产构建下对 mock 抛错——这是门控而不是失败兜底，不构成缺陷，但意味着首页 bundle 的 chunk 图里带着这些文件。

### 4.5 日期口径没有共享层

`getBalanceAnalysisDates` 在 10 个 feature 里各自调用（`balance-analysis/hooks/useBalanceAnalysisData.ts`、`market-finance`、`decision-items`、`cashflow-projection`、`average-balance`、`liability-analytics`、`positions`、`operations-analysis`、`dashboard-home/useDashboardHomeViewModel.ts`、`module-home/usePortfolioHomeQueries.ts`），各自"取可用日期中最新的一档"；PnL 用 `/api/pnl/dates`（6 页）、债券用 `/api/bond-analytics/dates`（5 页）与 `/api/bond-dashboard/dates`（4 页）、风险用 `/api/risk/tensor/dates`（5 页）、行情用各序列自己的 as-of。全仓没有 `ReportDateContext` 一类的共享业务日期上下文（只有 `dashboard-home/homeReportDateLabel.ts` 做首页标签）。同一屏并排展示多域读数的页面——五个一级首页、`/market-finance`、`/operations-analysis`——因此没有机制发现各卡片 as-of 不同；`/market-overview` 审计 S7 实测到 `/stock-analysis` 与首页差 4 天且无交叉提示，是这个结构问题的一个实例。

---

## 5. D 线：契约

### 5.1 页面契约覆盖与治理层级

`docs/page_contracts.md` 有 34 个 `PAGE-*` 章节；`tests/test_live_route_page_contract_completeness.py` 要求每条 live 路由有 PAGE 契约，7 条以 `TEMP_EXCEPTION_ROUTE_PAGE_CONTRACT_WHITELIST` 放行：`/market-finance`、`/team-performance`、`/decision-items`、`/stock-analysis`、`/platform-config`、`/kpi`、`/news-events`（对应 `GAP-*` 占位，`/decision-items` 有写接口却只作为 PAGE-BALANCE-001 的小节存在）。

`docs/live_route_maturity.md` 对 38 条 live 路由的层级分布：`governed` 6（`/balance-analysis`、`/balance-movement-analysis`、`/risk-tensor`、`/pnl`、`/pnl-bridge`、`/pnl-by-business-insights`）、`governed-mixed-source` 9、`candidate` 10、`temporary-exception` 13。导航层另有 18 条路由带 `governanceStatus: "temporary-exception"`（比台账多 5 条，因为 `/bond-dashboard`、`/positions`、`/ledger-pnl`、`/product-category-pnl`、`/pnl-by-business` 在台账里是 `candidate` / `governed-mixed-source` 但导航仍标临时开放）。`tests/test_codex_page_readiness_gate.py:2301-2304` 断言的门禁摘要写着 `business_contract_certified_count=0; evidence_pending_count=23; business_owner_action_signoff_missing_or_invalid_item_count=5`。这三份口径合起来说的是同一件事：**能被当作正式真值直接引用的页面只有 6 个，其余 32 个页面的读数在治理上都带限定词**，而一级首页、`/market-finance`、`/operations-analysis` 恰恰是把这些带限定词的读数并排展示的地方（§4.3、§4.5）。

### 5.2 契约门禁运行结果

release suite 中的契约类测试本次单独跑了 6 个文件：`test_live_route_page_contract_completeness.py`、`test_result_meta_on_all_ui_endpoints.py`、`test_api_contract_baseline_gate.py`、`test_page_contract_metric_dictionary_completeness.py`、`test_metric_dictionary_golden_sample_completeness.py`、`test_api_response_model_field_preservation.py`，共 94 项，93 通过。唯一失败是 `test_page_contract_metric_bindings_exist_in_metric_dictionary`：`PAGE-POS-001` 已出现 `MTR-*` 行但仍列在 `PAGES_WITHOUT_FORMAL_METRIC_BINDINGS`。该测试不在 release suite；工作区 `docs/page_contracts.md` 有未提交改动，这条可能是并行会话的在途工作，需在提交前收口。

OpenAPI 基线（`contracts/openapi/openapi.default.json`）门禁、31 个读取端点的 `response_model` 字段零丢失断言、全部 `/ui/*` GET 信封含 `result_meta` 的断言均通过。

---

## 6. E 线：测试有效性

### 6.1 跳过与金样本

`tests/ci_skip_registry.json` 登记 51 个文件、74 处依赖型跳过（real-data 23、symlink 17、system-db 14、other 13、redis 5、postgres 2），`test_ci_skip_registry.py` 静态守卫通过，未登记跳过为零。`docs/plans/2026-08-27-skipped-tests-inventory.md` 已逐条分类（70 处中 67 处环境门控合理保留、1 处待确认、2 处疑似遗忘），本报告不重复。前端 vitest 静态 `.skip` 仅 4 处；此前审计报告里"194 skipped"是 `-t` 名称过滤的副产物，不是跳过债务。

28 组金样本的 capture-ready 与 release-matrix 门禁全部通过（§2.2）。`tests/AGENTS.md` 记录的排除面遗留套件约 1,577 个用例（agent 395、livermore 431、macro_toolkit 287 …）以 `excluded_surface_*` 标记隔离在默认门禁外。

### 6.2 PR 门禁与定时全量的覆盖差

`scripts/backend_release_suite.py` 的 `RELEASE_SUITE_TESTS` 有 38 个文件，边界守卫只收了 `test_no_finance_logic_in_frontend.py`。`.github/workflows/ci.yml` 里 PR 跑 release suite，`backend-full-pytest` 只在 `schedule` 或 `push` 到 `main` 时跑全量并在失败时开 issue。这解释了 §3.2 两项红灯为何能从 08-13 / 08-15 存活到今天：它们在 PR 阶段不可见，在 main 上以 issue 形式存在。同理，§5.2 的 metric dictionary 白名单陈旧、`test_api_route_boundaries.py`、`test_service_storage_boundaries.py` 的其余 70 余项断言都不在 PR 门禁内。

`tests/test_codex_page_readiness_gate.py` 会拉起 PowerShell 执行 `scripts/codex-page-readiness.ps1` 与 `scripts/codex_page_readiness.py`，本次在有并行全量测试负载的机器上运行超过 20 分钟未完成，无法给出结论，记为观察项而非缺陷。

---

## 7. 2026-06-10 审计遗留 P1 的现状

| # | 当时的问题 | 现状 | 证据 |
| --- | --- | --- | --- |
| 1 | `balance_analysis_workbook.py` vs `balance_workbook/_analysis_tables.py` Campisi 票息两套实现单位互斥 | **已关闭**：`balance_workbook/` 改为纯委托壳，"不再维护第二套公式" | `balance_analysis_workbook.py:1-17` docstring；`_analysis_tables.py:5` 直接 import 权威实现 |
| 2 | `bond_analytics/engine.py` 利率单位 `abs>1 -> /100` 启发式盲区 | **已关闭**：改为 `rate_units.normalize_percent_rate_to_decimal`，显式百分数口径，>20% 拒收 | `engine.py:571-586` |
| 3 | `pnl_bridge.py` vs `attribution_daily.py` roll_down 符号相反 | **已缓解**：`attribution_daily` 标注 DORMANT、无生产调用方；符号裁决本身未见 calc_rules 更新 | `attribution_daily.py:1-3` |
| 4 | `qdb_gl_monthly_analysis.py` position-vs-ledger 同源自比 | **已披露**：函数 docstring 改写为"自检占位，不具备独立对账能力"，告警类型改名 `ledger_self_check_placeholder` | `qdb_gl_monthly_analysis.py:618-637` |
| 5 | `yield_by_period.py` 季/年聚合把快照求和当分母 | **已关闭**：`_avg_scale_across_report_dates` "mean of per-report_date portfolio scales (not sum of snapshots)" | `yield_by_period.py:84-94` |
| 6 | `pnl_bridge.py` `actual_pnl=0` 时 residual_ratio 强制 0、质量 "ok" | **已关闭**：`actual_pnl_missing` → `quality_flag="warning"`、`residual_ratio unavailable` | `pnl_bridge.py:501-551` |
| 7 | `macro_bond_linkage.py` 流动性分项符号极性反 | **已关闭**：`ENVIRONMENT_COMPOSITE_FORMULA_VERSION = "macro_env_composite_v2_liquidity_inverted"`，`liquidity_tightness_score = -liquidity_score` | `macro_bond_linkage.py:28, 499-504` |
| 9 | `BalanceMovementAnalysisPage.tsx` 占比前端重算 | **已关闭**：页面文案"占比使用后端正式 current_balance_pct；页面不补算缺失值" | `BalanceMovementAnalysisPage.tsx:2158` |
| 10 | `zqtzAdbAvgRollup.ts` / `yieldAnalysisAggregates.ts` 前端补算 PnL 聚合与日均 rollup | **已关闭**（rollup 部分）：父级日均改由后端 `/api/pnl/by-business-ytd` 返回 | `zqtzAdbAvgRollup.ts:1-7` |
| 11 | `CreditSpreadView.tsx` 评级×期限热力图前端聚合、桶映射硬编码 | **代码仍在，但已确认为死分支**：后端响应从未包含 `bond_details`，热力图在任何数据源下都不渲染；前端分桶映射与 float 累加仍留在 `buildRatingTenorHeatmapData` 中，属待删除的死代码而非现网口径风险（见 §4.4、§9） | `creditSpreadViewSupport.ts:187-221`；`CreditSpreadView.tsx:206-219`；`schemas/bond_analytics.py:525-581` |

10 项开放 P1 中 8 项已关闭或以披露方式缓解，1 项（#3）靠休眠规避，1 项（#11）代码未动但经本次核实为死分支。#10 的 `yieldAnalysisAggregates.ts` 部分本次未复核。

---

## 8. 建议的处置与第二阶段

按"业务指标正确性 > 页面闭合 > 可追溯 > 最小改动"的优先级，第二阶段建议分三组推进，每组都能独立成 PR。

**先修门禁，再修代码**（A1、E1、D2）。把 `test_no_finance_logic_in_api.py`、`test_service_storage_boundaries.py`、`test_api_route_boundaries.py`、`test_page_contract_metric_dictionary_completeness.py` 加进 `RELEASE_SUITE_TESTS`，让红灯先在 PR 阶段可见；`KRDAttributionEnvelope` 的假阳性可以给 token 守卫加"schema 类名"例外或改用 AST 只检查表达式；choice-news ingest 路由需要业务裁决——是撤路由还是把守卫改成显式登记的排除面豁免；`PAGE-POS-001` 白名单随在途的 `page_contracts.md` 改动一并收口。

**把前端算式收回后端**（C1、C2、C3）。`buildProductCategoryManagementMonitoringSurface` 整段迁到 `product_category_pnl_service` 或新的候选读模型端点，后端按 `report_date` 决定窗口而不是写死 H1，前端只保留展示；信用利差热力图由 `credit_spread_analysis_service` 返回 `rating × tenor_bucket` 矩阵与 `unmapped_market_value`，前端不再持有桶映射；一级首页的 `sumIndustryMarketValue` / `zqtzAssetCnyMarketValue` 改为消费后端总量字段，`/ui/market-overview/snapshot` 的接线（WP-H）完成后，用同样模式把 `/portfolio` 与 `/risk-overview` 的汇总迁回后端。这组改动落地后，再把 `test_no_finance_logic_in_frontend.py` 的 10 个目录白名单逐个收窄，并考虑用 AST 级规则（例如 `features/**` 内禁止对 `Numeric` 字段做 `reduce` 求和、禁止 `/ 365`）替换 token 黑名单。

**治理与可追溯**（A3、A4、C4、C5、D1）。给 `pnl_yield_display.py` 补 DORMANT 标注或删除，并决定 `/api/pnl/data`、`/api/pnl/basis-bridge`、executive 四条 `/ui/home/*` 路由的去留；`campisi.py` / `action_attribution.py` 出口的 `float(...)` 改为 Decimal 字符串或 `Numeric`，与 `explicit_numeric` 策略对齐；引入一个最小的共享业务日期上下文（至少在五个一级首页与 `/market-finance`、`/operations-analysis` 上显示各域 as-of 并在不一致时提示）；13 条 `temporary-exception` 路由里 `/average-balance`、`/concentration-monitor`、`/cashflow-projection`、`/cross-asset` 四条台账已写明"owner signoff still required before leaving temporary-exception"，是最接近晋级的候选，值得优先安排 owner 审批。

本报告未触及 `backend/app/core_finance/` 任何正式计算路径的行为；对正式金融路径的影响为**无**。

---

## 9. 处置记录（2026-09-02 同日，后端侧第一批）

审计写完后按 §8"先修门禁"一组先行处置了 A1、E1 与 A3 中不需要业务裁决的部分，全部是测试、门禁清单与 docstring 改动，未改任何路由、服务或 `core_finance` 计算逻辑，未提交。

**A1-a `tests/test_no_finance_logic_in_api.py`**。根因是纯文本 token 匹配把 schema 类型名 `KRDAttributionEnvelope` 当成公式。改为先用 `ast` 剥离 import 语句与 import 绑定进来的名字（含 `as` 别名），再做 token 扫描；源码无法解析时回退全文扫描。新增自检用例覆盖四种情形：有导入名且含 `total_DV01 = ...` 仍检出、仅导入并使用类型名不再误报、本地 `class KRDAttributionEnvelope` 定义仍算泄漏、语法错误回退后仍检出。词表未改。

**A1-b `tests/test_service_storage_boundaries.py::test_choice_news_reserved_ingest_route_has_no_service_ingest_path`**。根因是第三个断言"不得出现 `import` 作用域"早于 `choice_news.py` 现行"RBAC 先于保留 503"的设计（`_ensure_choice_news_ingest_allowed` → `_raise_choice_news_reserved_surface`，由 `tests/test_choice_news_routes.py::test_tushare_npr_ingest_requires_import_scope_before_reserved_503` 钉住）。改为：按路由装饰器识别 handler，凡直接内联或经助手做了 `action="import"` 检查的 handler 必须同时调用 `_raise_choice_news_reserved_surface`，且路由不得从 `backend.app.services*` 导入名字含 `ingest` 的符号；至少要有一个这样的 handler，否则 fail-loud 提示重新审视。反向自检（`.tmp-agent/system-audit/negative_check_choice_news_guard.py`）：现行路由通过，一个内联做 import 检查并直接调用服务写入、不抛 503 的假路由被以 `tushare_npr_ingest_ui performs import-scope RBAC but does not raise the reserved 503` 拒绝。路由文件本身未动。

**E1 `scripts/backend_release_suite.py` / `tests/test_backend_release_suite.py`**。在 `RELEASE_SUITE_TESTS` 的 `test_no_finance_logic_in_frontend.py` 之后追加 `test_no_finance_logic_in_api.py`、`test_api_route_boundaries.py`、`test_service_storage_boundaries.py`（共 34 个静态守卫用例，`--collect-only` 0.48 s），钉住测试同步镜像；`test_duckdb_write_boundary.py` 未纳入，因为它只是前者 4 个用例的重新导出，纳入会让同一门禁重复执行这 4 个用例（`--collect-only` 显示 34 个节点中 4 个同名）。`--dry-run` 计划确认三个文件出现在 pytest 参数里，并与另一会话在同两个文件里追加的 5 条 release-approval 条目及 `MOSS_SKIP_STORAGE_READINESS_CHECKS` 共存。`docs/TESTING.md` 声明脚本常量是唯一权威源，无需同步。

**A3 `backend/app/core_finance/pnl_yield_display.py`**。模块 docstring 最前面按 `var_engine.py` / `credit_spread.py` 的写法加 DORMANT 标注（无生产调用方，仅 `tests/test_caliber_migration_hat_mapping.py` 引用；接线前先确认 V1 `/api/pnl/data` 口径是否仍需保留），并把"外部仍按 V1 名字 import"改成与事实一致的表述。函数与函数体未动。

**验证**：`pytest tests/test_no_finance_logic_in_api.py tests/test_api_route_boundaries.py tests/test_service_storage_boundaries.py tests/test_duckdb_write_boundary.py tests/test_no_finance_logic_in_frontend.py tests/test_backend_release_suite.py tests/test_backend_release_gate_docs.py tests/test_ci_workflow_contents.py tests/test_caliber_migration_hat_mapping.py` → 300 passed；`ruff check` 五个改动文件 → All checks passed；`tests/test_choice_news_routes.py -k tushare_npr_ingest` 通过。

**未处置、待裁决**：D2（`PAGE-POS-001` 白名单陈旧）涉及另一会话未提交的 `docs/page_contracts.md`，留给该在途工作收口；A4（`campisi` / `action_attribution` 出口 `float(...)`）会改变正式路径的序列化并牵动 GS-BOND-ANALYSIS-ACTION-ATTR-A 金样本，需要先定数值表示口径；C1/C2/C3 的后端侧（候选监控读模型、评级×期限矩阵、首页总量字段）是新增契约，需要先定 PAGE/MTR 绑定再实现；C5 的 70 条无页面引用路由去留需要业务决定。

**剩余风险**：新 API 守卫会剥离所有 import 绑定名，若 API 层从 services 导入了名字本身含 token 的函数并调用，将不再报警——但这本就是允许的"调用服务层"路径，真正的风险（API 层自定义含公式名的变量/类）仍被抓住；两处门禁改动与另一会话的在途 hunk 位于相邻行，若对方回滚或变基自身 hunk，git 可能把两处判为同一冲突块，需人工合并。

### 9.1 后端侧第二批（同日）

**C2 纠正为死分支**。核实 `GET /api/bond-analytics/credit-spread-migration` 的后端模型 `CreditSpreadMigrationResponse` 没有 `bond_details`，前端热力图分支不可达（§4.4 已改写）。不做后端工作；前端删除该分支留待前端批次，是否作为后端聚合的正式图表重做由产品决定。

**C3 后端侧：行业分布 payload 补 `total_market_value`**。`BondDashboardIndustryDistributionPayload`（`schemas/bond_dashboard.py:267-285`）追加顶层 `total_market_value: Numeric`（yuan），description 写明是"返回 items（按 top_n 截断、剔除空行业名）市值之和，即各项 percentage 的分母；不是组合总市值"；`_bond_dashboard_industry_payload`（`bond_dashboard_service.py:870`）把已有的分母 `tot` 以 `_amt(tot)` 透传，与同文件资产结构 / 期限结构 payload 的既有先例一致；`tests/test_bond_dashboard_api_contract.py:1108-1117` 新增断言：顶层总量等于各项之和、首项 percentage 等于该项 / 总量（Q8 量化后精确比较）。影响分析：函数无外部调用方，模型只被 `routes/bond_dashboard.py` 导入，LOW。验证：四个 bond-dashboard 测试文件 + 字段保留测试 + 新核心单测合计 104 通过；`api_contract_check.py baseline-check --baseline-ref HEAD` 两个 surface 均 `breaking=0`（default additive=386、full additive=400，其中绝大部分是工作区里其他在途改动，如 `Numeric.raw_text`、`result_meta.data_built_at`）。前端 `moduleHomeModel.ts:3232 sumIndustryMarketValue` 尚未切换消费该字段，属前端批次。

**OpenAPI 基线的处理**。子代理曾运行 `baseline-update` 重写 `contracts/openapi/openapi.default.json` / `openapi.full.json`（+8,092 / −908 行），其中绝大部分是另一会话未提交的 API 改动；本次已把这两个文件回退到 HEAD，工作区不携带他人变更。但 `scripts/api_contract_check.py` 的 `stale_baseline = disk_text != head_text`（第 1172 行）会让磁盘快照与当前导出不一致时判 fail，CI 在 PR 阶段（`baseline-check --baseline-ref origin/<base>`）和 main 新鲜度检查都不带 `--allow-stale-baseline`，所以**提交这条改动时必须同一提交内运行 `baseline-update` 并带上两份 JSON**；届时基线会连带收录当时工作区内所有其他未入基线的 API 变更，提交者需知悉。

**A 线补充：`credit_spread_analysis.py` 直接单测**。新增 `backend/tests/core_finance/test_credit_spread_analysis.py`，56 个 characterization 用例，直接导入模块的 3 个 dataclass、3 个公开函数与 7 个私有辅助，覆盖 `compute_bond_spreads` 正常路径与过滤分支、`_normalize_ytm_to_pct` 全部分支（0.2 阈值严格大于、None/NaN/不可解析）、基准收益率解析（实际期限优先于 tenor_bucket、两端平推、未知标签抛错）、`build_spread_term_structure` 聚合与排序、历史窗口 / 分位 / 中位数边界；期望值按源码公式以 Decimal 手算并在 docstring 标注行号；曲线刻意只给两个节点以避开三次样条。运行 56 通过，ruff 通过，`test_ci_skip_registry` 通过。写测试过程中固定下来的实现语义即 A5（分级清单），本次未改模块行为——若业务裁决要改其中任一条，这份测试对应用例要同步更新。

**验证汇总**：`pytest backend/tests/core_finance/test_credit_spread_analysis.py tests/test_bond_dashboard_api_contract.py tests/test_bond_dashboard_bundle.py tests/test_bond_dashboard_numeric_migration.py tests/test_api_response_model_field_preservation.py` → 104 passed；`tests/test_api_contract_baseline_gate.py` → 39 passed（基线回退后复跑）；`ruff check` 四个改动文件 → All checks passed。

**仍待裁决**：A4、C1 后端读模型、C5、D2 与 §9 首段相同；新增 A5 需固收业务方裁决"缺失当 0"是否改为跳过并披露。`zqtzAssetCnyMarketValue` 对应的 `BalanceAnalysisBasisBreakdownPayload` 是 `extra="forbid"` 的正式契约（PAGE-BALANCE-001），补分源总量字段需要同步指标字典与金样本，不在本批。

### 9.2 前端侧第一批（同日）

**C2 删除信用利差热力图死分支**。Tier 2（单页、`/bond-analysis` 信用利差 tab）。删除的内容：`creditSpreadViewSupport.ts` 中 `buildRatingTenorHeatmapData`、`ratingTenorHeatmapOption` 与随之无用的前端分桶表（`CREDIT_DIST_TENOR_LABELS` 8 档、`CREDIT_DIST_RATING_LABELS` 6 档、`mapTenorBucketToXIndex` 15 项映射、`mapRatingToBucket`）；`CreditSpreadView.tsx` 的 `creditDistributionView` 热力图分支与渲染块，空态文案由"暂无评级×期限明细或集中度数据"改为"后端未返回评级 / 期限集中度数据"，并在 useMemo 上方注明分布只消费 `concentration_by_rating / concentration_by_tenor`；前端契约 `api/contracts/bondAnalytics.ts` 删除 `CreditSpreadBondDetailRow` 类型与 `CreditSpreadMigrationPayload.bond_details?`，`features/bond-analytics/types.ts` 同步删除再导出；`bondAnalyticsClient.ts` 与 `homeSupplementalClient.ts` 两处 `normalizeCreditSpreadMigrationEnvelope` 删除对 `bond_details` 的归一化（两个文件是同款复制，一并处理）。仓内所有 `bond_details: []` 夹具（`ApiClient.test.ts`、`HomeStartupClient.test.ts`、`BondAnalyticsView.test.tsx`、`bondAnalyticsAdapter.test.ts`、`bondAnalyticsMockClient.ts`）经逐个核对均属 `ReturnDecompositionResponse`（该模型的 `bond_details` 是后端真实字段），未动。`CreditSpreadView.test.tsx` 新增两条：响应夹带个券行时分布卡仍走空态（前端不再从明细分桶）、后端给出评级 / 期限集中度时渲染两张柱图。与 2026-06 P1-11 决策包的关系：决策包"现状即 B 行为（前端聚合）"的描述本就不准确——现状是不可达代码；本次删除后现状变为"前端不持有分桶口径、仅渲染后端集中度"，与推荐选项 A 的前端侧要求一致，但 A 的后端侧（治理化的评级×期限矩阵契约）仍未实施，owner 决策仍开放。

**验证**：`npm run test -- src/test/CreditSpreadView.test.tsx src/test/BondAnalyticsDetailSection.test.tsx src/features/bond-analytics` → 10 文件 62 通过（含新增 2 条）；`npm run typecheck` 通过；`eslint` 七个改动文件通过；`npm run debt:audit` 六项中五项通过，唯一失败是 `moduleHomeModel.ts` 4,624 行 > 基线 4,505，属另一会话同时段在该文件追加的约 120 行，与本批无关；`tests/test_no_finance_logic_in_frontend.py` 红灯，唯一命中是 `moduleHomeModel.ts` 中另一会话新加的注释行"规模/久期/DV01 用相对百分比"（`git diff` 可见为新增行，HEAD 中该文件 63 处 DV01 全在既有行前缀例外内），本批七个文件均未出现在守卫命中列表。

**C3 前端接线：行业分布面板改读后端总量**（21:49 起执行，此前 `moduleHomeModel.ts` 等三个文件在 21:01–21:21 间持续被另一会话写入，等其静默 26 分钟后才动手）。Tier 3（`moduleHomeModel.ts` 被五个一级首页共享），但改动只落在行业面板一处：`api/contracts/bondDashboard.ts` 的 `IndustryDistPayload` 加必填 `total_market_value: Numeric`，注释写明是 top_n 截断后各项市值之和、即 percentage 的分母、不是组合总市值，与后端 §9.1 的字段语义一字对应；`moduleHomeModel.ts` 删除 `sumIndustryMarketValue`（13 行 JS number 累加）与 `industryTotalMarketValue` 中间量，行业面板的 `distributionRows` 分母和 `totalMarketValue` 改为 `industry?.total_market_value`，与相邻的券种 / 评级 / 期限三个面板写法一致；`formatRawAsNumeric` 在该文件已无使用，import 一并删除。另一会话在等待期间已把该面板标题改成"行业分布（Top10）"、合计前缀"Top10 合计"，与后端字段口径恰好一致，无需再改文案。五处构造该 payload 的夹具补字段：`bondAnalyticsMockClient.ts` 用既有 `totalMarketValue`（328,709,000,000，与六行之和相等）、`portfolioCrossPageGoldenSample.ts` 用既有 `marketValue`（123,456,789,012.34，与六行之和相等）、`ModuleWorkbenchHomePage.test.tsx` 用既有常量 332,281,921,064.45、`BondDashboardPage.test.tsx` 两处（`IndustryTable` 单行夹具 `yuan(1)`、空分区夹具 `yuan(0)`）。`ModuleWorkbenchHomeModel.test.ts` 的"derives the industry distribution total from returned industry rows"改名为"reads the industry distribution total from the backend instead of summing rows"，夹具刻意让后端总量 3.50 亿 ≠ 行合计 3.00 亿，断言合计显示"Top10 合计 3.50 亿"，从而证明前端不再求和；空行夹具补 `total_market_value: 0`，仍断言不显示合计（空行时面板走 watch 态）。`distributionRows` 在调用方未传总量时的 `items.reduce` 回退保留，仅剩收益率分布（后端无总量字段、且只算柱宽不显示数值）在用。`/bond-dashboard` 的 `IndustryTable` 只渲染行，本就不算合计，不受影响。

**验证**：`npm run typecheck` 通过（首轮发现 `BondDashboardPage.test.tsx:276` 空分区夹具漏补，补后通过）；`npm run test -- src/test/ModuleWorkbenchHomeModel.test.ts src/test/ModuleWorkbenchHomePage.test.tsx src/test/BondDashboardPage.test.tsx src/test/PortfolioHomeCrossPageConsistency.test.tsx src/features/workbench/dashboard-home src/features/bond-dashboard` → 42 文件 552 条中 551 通过、1 失败；失败项 `ModuleWorkbenchHomePage.test.tsx:2269 "fails closed when yield distribution returns no buckets"` 是 `getByRole("tab", { name: /收益率/ })` 同时匹配到"收益率"与另一会话新改名的"券种收益率"两个页签（错误输出可见），且该测试断言"1 个结构为空"而现渲染"4 个结构为空"，均为对方在途改动自身的红灯，行业面板不在该页签组内；`eslint` 七个改动文件通过；`tests/test_no_finance_logic_in_frontend.py` 仍红，命中已从 1 处变为 2 处（`moduleHomeModel.ts`、`PortfolioHomeLayout.tsx` 各一处 DV01），均为另一会话新增行；`audit_frontend_debt.mjs` 报 `moduleHomeModel.ts` 4,661 行 > 基线 4,505，本批净减 14 行，超基线部分全部来自对方。

**并发风险提示**：另一会话在 21:49:14 写了 `PortfolioHomeLayout.tsx`，说明其在本批执行时已恢复活动，只是恰好没再写本批触碰的三个文件。若其后以整文件方式回写 `moduleHomeModel.ts`，本批在该文件的三处小 hunk（import 行、行业面板两行、删除的 13 行函数）可能被覆盖；复核方法是 `rg sumIndustryMarketValue frontend/src`，应无命中。
