# 系统缺口与完善计划

## 1. 目标与边界

本文只解决一个问题：基于当前仓库已经落地的代码、测试和文档，把 MOSS 从“功能堆积”收敛成“口径一致、可验证、可解释、可维护”的业务系统。

本计划只覆盖当前仓库内已经有真实实现或已进入 cutover 讨论的页面与主链，不借机发起以下事项：

- 不做数据库 schema 重构。
- 不做全局状态架构重写。
- 不做 SDK/基础设施平台化改造。
- 不做与当前页面治理无关的性能专项。
- 不把 placeholder / compat / excluded surface 伪装成已上线主链。

## 2. 当前仓库一句话判断

仓库已经有 formal runtime、`result_meta`、contract tests、governance audit、golden sample harness 这些“底层治理骨架”；当前真正缺的是把这些骨架上升到“指标级、页面级、样本级、文档级”的可执行约束。

## 3. 必须补齐的四类资产

### 3.1 指标字典

- 已有证据：
  - `docs/metric_dictionary.md` 已存在。
  - 当前字典明确覆盖 `MTR-BAL-*`、`MTR-PNL-*`、`MTR-BRG-*`、`MTR-RSK-*`、`MTR-EXEC-*`。
- 仍然缺少的地方：
  - live 页面中的 `bond-dashboard`、`positions`、`average-balance`、`ledger-pnl`、`market-data`、`operations-analysis`、`cashflow-projection`、`concentration-monitor`、`product-category-pnl`、`kpi-performance`、`team-performance`、`platform-config` 还没有进入同一套指标 ID 体系。
  - `frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx` 仍有 `BALANCE_MOCK_KPI` 首屏指标，说明页面 headline KPI 还没有完全绑定到治理后的 `metric_id`。
  - `frontend/src/features/workbench/pages/OperationsAnalysisPage.tsx` 仍直接引用 `businessAnalysisWorkbenchMocks`，说明部分 live 页面还没有指标口径冻结。

### 3.2 页面契约

- 已有证据：
  - `docs/page_contracts.md` 已存在。
  - 当前已经写入的页面契约只有 9 个：`PAGE-DASH-001`、`PAGE-BALANCE-001`、`PAGE-PNL-001`、`PAGE-BRIDGE-001`、`PAGE-RISK-001`、`PAGE-EXEC-OVERVIEW-001`、`PAGE-EXEC-SUMMARY-001`、`PAGE-EXEC-PNL-ATTR-001`、`PAGE-PNL-ATTR-WB-001`。
- 仍然缺少的地方：
  - `frontend/src/router/routes.tsx` 和 `frontend/src/mocks/navigation.ts` 暴露的 live 页面明显多于 9 个，说明“live route 数量”与“有契约的页面数量”不一致。
  - 首页 `/` 仍是多读面聚合页，`DashboardPage.tsx` 自身没有统一的筛选和日期语义约束，只靠页面说明文字兜底。

### 3.3 黄金样本

- 已有证据：
  - `tests/test_golden_samples_capture_ready.py` 已存在。
  - `tests/golden_samples/` 已经有 `GS-BAL-OVERVIEW-A`、`GS-BAL-WORKBOOK-A`、`GS-PNL-OVERVIEW-A`、`GS-PNL-DATA-A`、`GS-BRIDGE-A`、`GS-RISK-A`、`GS-EXEC-OVERVIEW-A`、`GS-EXEC-SUMMARY-A`、`GS-EXEC-PNL-ATTR-A`。
- 仍然缺少的地方：
  - `docs/golden_sample_plan.md`、`docs/golden_sample_catalog.md`、`tests/golden_samples/` 当前都不在 `git ls-files` 返回结果里，说明这些治理资产还没有进入版本化基线。
  - `GS-BOND-HEADLINE-A` 仍未冻结；首页 `/` 也不适合作为首批黄金样本，因为它混合了 live 和 excluded section。

### 3.4 数据追溯

- 已有证据：
  - `backend/app/schemas/result_meta.py` 已经输出 `trace_id`、`source_version`、`rule_version`、`cache_version`、`quality_flag`、`vendor_status`、`fallback_mode`、`generated_at`。
  - `frontend/src/components/page/FormalResultMetaPanel.tsx` 已经展示部分 provenance。
- 仍然缺少的地方：
  - `ResultMeta` 里没有统一 outward `as_of_date`。
  - `FormalResultMetaPanel` 没有展示 `vendor_status`、`fallback_mode`。
  - `PnlAttributionView.tsx`、`MarketDataPage.tsx` 又各自手工展示一部分 meta，页面级可见性标准不一致。

## 4. 九个维度的缺口与完善计划

## 4.1 业务指标口径

- 当前现状证据：
  - `docs/calc_rules.md`、`docs/data_contracts.md` 已经分别描述计算规则和字段契约。
  - `docs/metric_dictionary.md` 目前只覆盖 balance / pnl / bridge / risk / executive 五类指标。
  - `frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx` 在首屏继续使用 `BALANCE_MOCK_KPI`。
  - `frontend/src/features/workbench/pages/OperationsAnalysisPage.tsx` 引用 `businessAnalysisWorkbenchMocks`。
- 已具备内容：
  - formal balance、formal PnL、PnL bridge、risk tensor、executive v1 已经开始用 `metric_id` 编制字典。
  - `tests/test_pnl_formal_semantics_contract.py`、`tests/test_balance_analysis_api.py`、`tests/test_risk_tensor_api.py` 已经保护部分核心口径。
- 缺口：
  - 还没有覆盖全部 live 页面。
  - 页面 headline KPI 与 `metric_id` 的映射没有被强制要求。
  - 缺少每个指标的 owner、审批人、最后复核日期、样本挂点。
- 风险：
  - 同名指标在不同页面出现不同口径。
  - 页面首屏结论与明细表/导出/样本不一致。
  - 新增页面时容易绕开已有 formal 规则。
- 建议动作：
  1. 先冻结当前 core governed 页面与 executive v1 的指标 ID，不再让页面直接出现“未登记 KPI”。
  2. 按 live 页面补齐 `metric_id -> DTO field -> page section -> test -> golden sample` 五连映射。
  3. 对 mock-only 或 analytical-only 指标显式标记 `candidate` 或 `excluded`，禁止冒充 formal truth。
- 优先级：P0
- 预计工作量：M
- 依赖关系：
  - `docs/metric_dictionary_template.md`
  - `docs/page_contract_template.md`

## 4.2 API / DTO / 前后端契约

- 当前现状证据：
  - `backend/app/schemas/pnl.py`、`backend/app/schemas/balance_analysis.py` 使用 `ConfigDict(extra="forbid")`。
  - `backend/app/schemas/executive_dashboard.py` 仍然只是 `BaseModel`，没有同等严格的 `extra="forbid"` 约束。
  - `frontend/src/api/contracts.ts` 维护了大而全的前端 DTO 镜像。
  - `frontend/src/api/client.ts` 中 `createApiClient()` 默认 `VITE_DATA_SOURCE != real` 时走 `mock`。
  - `frontend/src/api/client.ts` 中 `buildMockApiEnvelope()` 被大量 endpoint 复用。
  - `tests/test_result_meta_on_all_ui_endpoints.py`、`tests/test_pnl_api_contract.py`、`tests/test_balance_analysis_api.py`、`tests/test_bond_analytics_api.py`、`tests/test_executive_dashboard_endpoints.py` 已经覆盖一批 outward contract。
- 已具备内容：
  - `{ result_meta, result }` 的 envelope 已经成为主要 UI endpoint 约定。
  - 主要 governed 页面已有 API contract tests。
- 缺口：
  - DTO 严格性不一致。
  - mock / real 双模式默认行为容易把 contract 漂移藏在本地开发阶段。
  - 页面层还没有“section -> endpoint -> DTO -> metric_id”的契约清单。
- 风险：
  - 后端字段漂移无法第一时间在页面设计层暴露。
  - 本地 mock 正常但 real 模式失配。
  - executive / analytical surface 容易在无显式标注时被误当成 formal。
- 建议动作：
  1. 用页面契约把每个 section 的 endpoint / DTO / basis / tests 全部钉死。
  2. 文档上统一规定 outward DTO 的严格性要求，避免一部分 schema fail-closed、一部分 schema 默默放行。
  3. 后续新增页面时，先补契约表，再开 API。
- 优先级：P0
- 预计工作量：M
- 依赖关系：
  - 指标字典
  - 页面契约

## 4.3 页面级产品定义与信息架构

- 当前现状证据：
  - `frontend/src/router/routes.tsx` 用 `workbenchNavigation` 生成页面路由，并把 non-live route 自动导向 placeholder。
  - `frontend/src/mocks/navigation.ts` 中同时存在 live、placeholder、gated 三类页面。
  - `docs/page_contracts.md` 当前只覆盖 9 个页面。
  - `frontend/src/features/workbench/pages/DashboardPage.tsx` 页面文案明确写了“首页不提供统一筛选”。
  - `frontend/src/features/workbench/dashboard/FixedIncomeDashboardHub.tsx` 仍引用 `dashboardHubMock`。
- 已具备内容：
  - live 与 placeholder 的分界已经进入导航定义。
  - 核心 governed 页面已经有首批页面契约。
- 缺口：
  - 大量 live 页面没有 page contract。
  - 首页 `/` 的主问题、禁止 section、跨页跳转边界还没有被正式文档化。
  - 部分 live 页面仍混用 mock 内容和 real read surfaces。
- 风险：
  - 页面越做越像“模块拼盘”，而不是回答一个明确业务问题。
  - 用户无法区分“主链页面”和“兼容页面”。
  - 页面说明与实际路由 readiness 可能逐步漂移。
- 建议动作：
  1. 先把 `/`、`/bond-dashboard`、`/positions`、`/market-data`、`/operations-analysis` 纳入页面契约。
  2. 每个页面契约必须定义“首屏先回答什么，不回答什么，哪些 section 禁止加入”。
  3. 对 live 但仍含 mock 的页面，在契约中显式标记 mixed-source / candidate，不再默认视作 fully governed。
- 优先级：P0
- 预计工作量：L
- 依赖关系：
  - 页面契约模板
  - 指标字典

## 4.4 前端设计系统与数值展示规范

- 当前现状证据：
  - `frontend/src/theme/tokens.ts`、`frontend/src/components/KpiCard.tsx`、`frontend/src/components/StatusPill.tsx`、`frontend/src/components/page/PagePrimitives.tsx` 已经存在。
  - `frontend/src/components/page/FormalResultMetaPanel.tsx` 说明页面层已经开始统一 provenance 面板。
  - 在 `frontend/src` 中，`toFixed` 命中 216 次，`toLocaleString` 命中 18 次。
  - 还存在多个局部 formatter：`frontend/src/utils/format.ts`、`frontend/src/features/bond-dashboard/utils/format.ts`、`frontend/src/features/bond-analytics/utils/formatters.ts`。
- 已具备内容：
  - 视觉组件层已经有 shared tokens 和 shared cards。
  - 部分页面已经复用 `KpiCard` / `PagePrimitives` / `FormalResultMetaPanel`。
- 缺口：
  - 缺少统一的金额、比例、bp、单位换算、精度、正负号、空值和 stale 展示规范。
  - 同类数值仍大量使用页面内联格式化。
  - 没有“页面 headline 数字必须标明单位与口径”的统一要求。
- 风险：
  - 同一指标在两个页面出现不同精度、不同单位、不同 null 表达。
  - 业务同学会把视觉差异误读成口径差异。
- 建议动作：
  1. 先在模板层定义展示规范，不先做大规模 formatter 重构。
  2. 每个 `metric_id` 必填 `display_unit / precision / sign_rule / null_rule / stale_copy`。
  3. 后续再把重复格式化逻辑按页面优先级逐步收口。
- 优先级：P1
- 预计工作量：M
- 依赖关系：
  - 指标字典
  - 页面契约

## 4.5 数据质量、追溯、as_of_date、fallback 可见性

- 当前现状证据：
  - `backend/app/schemas/result_meta.py` 输出 `quality_flag`、`vendor_status`、`fallback_mode`、`generated_at`，但没有统一 `as_of_date`。
  - `frontend/src/components/page/FormalResultMetaPanel.tsx` 当前只展示 `quality_flag`，不展示 `vendor_status` 和 `fallback_mode`。
  - `frontend/src/features/pnl-attribution/components/PnlAttributionView.tsx` 手工展示 `generated_at`、`quality_flag`、`fallback_mode`。
  - `frontend/src/features/market-data/pages/MarketDataPage.tsx` 也有单独的 meta 细节面板。
  - `git grep as_of_date` 的结果主要落在 KPI 模块，core governed 页面没有统一 outward `as_of_date`。
- 已具备内容：
  - 后端已经能给出 trace/version/fallback/quality 基础信息。
  - 前端已有 provenance 面板可复用。
- 缺口：
  - `as_of_date`、`requested_report_date`、`resolved_report_date` 没有形成统一页面契约。
  - fallback / stale / vendor unavailable 的页面可见性不一致。
  - 首屏 KPI 是否必须展示 freshness / fallback 提示没有统一规则。
- 风险：
  - 页面显示“最新”，实际是 carry-forward 或 latest snapshot。
  - 用户能看到 `quality_flag`，但看不到为什么 degraded。
  - 页面间数据追溯成本高。
- 建议动作：
  1. 在页面契约模板中强制填写 `requested_report_date / resolved_report_date / as_of_date / generated_at / fallback visibility`。
  2. 把 `vendor_status`、`fallback_mode` 纳入统一 meta 面板与页面异常态设计。
  3. 对所有 first-screen KPI 增加“何时必须显式提示 stale / fallback”的规则。
- 优先级：P0
- 预计工作量：M
- 依赖关系：
  - 页面契约模板
  - 设计系统展示规范

## 4.6 对账与黄金样本

- 当前现状证据：
  - `tests/test_golden_samples_capture_ready.py` 已经把 golden sample 读取、断言和 API replay 固化。
  - `tests/golden_samples/` 已有 9 个样本包，每个目录都有 `request.json`、`response.json`、`assertions.md`、`approval.md`。
  - `scripts/backend_release_suite.py` 已经把 `tests/test_golden_samples_capture_ready.py` 纳入 release suite。
  - `docs/golden_sample_catalog.md` 里已经明确把 `/` 和 `GS-BOND-HEADLINE-A` 暂时排除在首批之外。
  - 但这些样本和目录当前仍未进入 `git ls-files`。
- 已具备内容：
  - 黄金样本结构、测试入口、首批 sample ids 都已经存在。
- 缺口：
  - 样本资产尚未成为版本化基线。
  - bond analytics headline、首页聚合页、缺 page contract 的 live 页面还没有样本策略。
  - 样本与指标字典 / 页面契约之间还缺强连接。
- 风险：
  - golden sample 存在但不可审计、不可稳定回放。
  - release suite 对本地工作区状态敏感。
  - 跨页对账无法制度化。
- 建议动作：
  1. 先把 Batch A 视为“当前仓库最小可信样本集”，不要继续扩张范围。
  2. 把样本目录、catalog、plan 与 `metric_id` / `page_id` 建立硬链接。
  3. 新样本只允许在“页面契约已完成 + 指标字典已登记”之后新增。
- 优先级：P0
- 预计工作量：S
- 依赖关系：
  - 页面契约
  - 指标字典

## 4.7 自动化回归测试

- 当前现状证据：
  - `tests/test_backend_release_suite.py` 固定了 governed phase2 backend release suite。
  - `tests/test_result_meta_on_all_ui_endpoints.py` 已经保护 UI JSON envelope。
  - `tests/test_balance_analysis_docs_contract.py`、`tests/test_backend_release_gate_docs.py` 已经说明“文档也可以被测试”。
  - 当前没有看到针对 `docs/metric_dictionary.md`、`docs/page_contracts.md`、`docs/golden_sample_catalog.md` 的 completeness test。
- 已具备内容：
  - code contract tests 和部分 docs contract tests 已存在。
  - golden sample harness 已可执行。
- 缺口：
  - 缺少 `live route -> page contract` 完整性测试。
  - 缺少 `page contract -> metric dictionary` 完整性测试。
  - 缺少 `metric dictionary -> golden sample` 追踪测试。
  - 缺少数值展示规则回归测试。
- 风险：
  - 文档和路由悄悄分叉。
  - 新页面/新指标上线时没有被治理文档捕获。
- 建议动作：
  1. 下一阶段增加轻量 completeness tests，不做平台化测试框架重写。
  2. 先从 route/page/metric/sample 四张表的交叉完整性开始。
  3. 再补 unit display / stale copy / fallback visibility 的页面回归测试。
- 优先级：P1
- 预计工作量：M
- 依赖关系：
  - 指标字典
  - 页面契约
  - 黄金样本目录

## 4.8 监控、日志、错误追踪

- 当前现状证据：
  - `scripts/audit_governance_lineage.py`、`scripts/backend_release_suite.py`、`governance-lineage-audit.json` 已经形成治理审计路径。
  - `backend/app/tasks/build_runs.py`、`tests/test_governance_logging.py` 已经覆盖 build run logging。
  - `backend/app/governance/agent_audit.py`、`tests/test_agent_audit_log_contract.py` 说明 agent audit 也有独立流水。
  - `trace_id` 在 repository / service / result_meta / schema_registry 中广泛出现。
- 已具备内容：
  - 后端级日志与治理审计基础较完整。
  - release gate 已把 lineage audit 纳入前置。
- 缺口：
  - 没有“页面 owner 如何根据 `trace_id` / `vendor_status` / `fallback_mode` 处理问题”的页面级 runbook。
  - 没有把 repeated stale / vendor_unavailable 上升为页面治理告警规则。
  - 前端错误态更多是页面内局部处理，缺统一约束文本。
- 风险：
  - 技术上可追溯，运营上不可落地。
  - 同类故障在不同页面重复出现不同提示。
- 建议动作：
  1. 在 page contract 中补 `owner / runbook / escalation` 字段。
  2. 用页面契约固定 `404 / 503 / stale / fallback / vendor_unavailable` 的用户可见语义。
  3. 保持现有 backend lineage audit 作为唯一 release preflight，不扩成新平台。
- 优先级：P1
- 预计工作量：S
- 依赖关系：
  - 页面契约模板

## 4.9 文档与交接

- 当前现状证据：
  - `docs/` 下已经有 `DOCUMENT_AUTHORITY.md`、`CODEX_HANDOFF.md`、`CURRENT_BOUNDARY_HANDOFF_2026-04-10.md`、`EXECUTIVE_CONSUMER_CUTOVER_V1.md`、`acceptance_tests.md` 等大量治理文档。
  - `tests/test_backend_release_gate_docs.py` 和 `tests/test_balance_analysis_docs_contract.py` 说明部分文档已纳入回归。
  - 当前这批关键治理文档和样本目录在 `git status --short` 中仍是 `??`，还没有纳入版本控制基线。
- 已具备内容：
  - 文档文化和 handoff 机制是存在的。
  - 部分关键文档已经被测试锁定。
- 缺口：
  - 指标字典 / 页面契约 / 黄金样本目录还不是正式 authority pack。
  - 缺少一份“当前治理资产索引”，告诉后续维护者先看哪几份文档。
  - 缺少 owner 级 review 周期。
- 风险：
  - 下一轮开发继续依赖 prompt 和记忆，而不是文档。
  - 未纳入版本控制的治理资产很容易丢失或分叉。
- 建议动作：
  1. 把本次 4 份文档视作后续两周的最小 authority pack。
  2. 后续将它们纳入 `DOCUMENT_AUTHORITY.md` 或 `acceptance_tests.md` 的引用链。
  3. 每次页面新增 / contract 变化时同步更新对应 `page_id`、`metric_id`、`sample_id`。
- 优先级：P0
- 预计工作量：S
- 依赖关系：
  - 本次文档包先稳定

## 5. 未来两周最小可执行路线图

### 第 1 周

| 顺序 | 时间 | 目标 | 最小产出 | 依赖 |
| --- | --- | --- | --- | --- |
| 1 | Day 1 | 冻结治理边界 | 将 `metric_dictionary` / `page_contracts` / `golden_sample_*` / `tests/golden_samples` 纳入版本控制；明确 in-scope / excluded surface 列表 | 无 |
| 2 | Day 1-2 | 冻结核心指标 | 补齐 balance / pnl / bridge / risk / executive v1 的 headline KPI 到 `metric_id` 映射；标注 mock-only / candidate 指标 | 步骤 1 |
| 3 | Day 2-3 | 补核心页面契约 | 完成 `/`、`/balance-analysis`、`/pnl`、`/pnl-bridge`、`/risk-tensor`、`/ui/home/*` 契约复核，并新增 `/bond-dashboard`、`/positions`、`/market-data`、`/operations-analysis` 契约 | 步骤 2 |
| 4 | Day 4-5 | 冻结 freshness / fallback 语义 | 在页面契约里统一 `requested_report_date / resolved_report_date / as_of_date / generated_at / fallback visibility` 字段；明确 `FormalResultMetaPanel` 应展示的最小集合 | 步骤 3 |

### 第 2 周

| 顺序 | 时间 | 目标 | 最小产出 | 依赖 |
| --- | --- | --- | --- | --- |
| 5 | Day 6 | 复核黄金样本 Batch A | 让 `docs/golden_sample_plan.md`、`docs/golden_sample_catalog.md`、`tests/golden_samples/` 与 release suite 对齐 | 步骤 1-4 |
| 6 | Day 7 | 建立 page-metric-sample 链接 | 每个 in-scope page contract 引用 `metric_id` 列表和 `sample_id` 列表；每个 `metric_id` 指回 page 和 sample | 步骤 5 |
| 7 | Day 8-9 | 定义最小回归门禁 | 补“live route -> page contract”“page contract -> metric dictionary”“sample_id -> golden sample dir”三类 completeness test 设计说明 | 步骤 6 |
| 8 | Day 10 | 形成下一轮执行清单 | 输出剩余 live 页面缺口列表，明确哪些能继续治理，哪些维持 placeholder / compat / excluded | 步骤 7 |

## 6. 优先级结论

- P0：
  - 指标口径冻结
  - API / DTO / 页面契约链路打通
  - freshness / fallback / as_of 可见性
  - 黄金样本版本化
  - 文档 authority pack 固化
- P1：
  - 数值展示规范
  - completeness 回归测试
  - 页面 owner / runbook / escalation
- P2：
  - 在核心 governed 页面稳定后，再扩展到更外围 live 页面

## 7. 最小执行原则

后续所有动作遵守以下原则：

- 先补字典、契约、样本，再改页面。
- 先锁核心 governed 页面，再扩外围 live 页面。
- 先补缺失映射和可见性，不做基础设施重写。
- 先让现有治理资产进入版本控制和回归门禁，再谈扩张。
