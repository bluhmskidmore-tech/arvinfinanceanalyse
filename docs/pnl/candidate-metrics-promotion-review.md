# 业务种类候选分析指标转正评审材料

## 文档说明

| 字段 | 内容 |
|------|------|
| 页面 | `PAGE-CONTRACT-PENDING:/pnl-by-business-insights` |
| 前端路由 | `/pnl-by-business-insights` |
| 页面文件 | `frontend/src/features/pnl-business-insights/PnlByBusinessInsightsPage.tsx` |
| 当前状态 | 全部指标 `status=candidate`，`formal_use_allowed=false` |
| Golden Sample | `GS-PNL-BUSINESS-INSIGHTS-A`（`captured-awaiting-approval`） |
| 字典登记 | `docs/metric_dictionary.md` §15.2.11（`MTR-PNLBIZ-001`~`006`） |
| 最后审阅 | 2026-07-07 |

**阅读指引**：本文档面向业务方与治理审批人，不要求阅读代码。每个指标均说明「回答什么业务问题」「怎么算」「数据从哪来」「转正前需确认什么」。

**全局免责声明（与页面一致）**：

> 本页指标为候选分析（`status=candidate`），仅供内部参考，不构成正式业务结论；最终审批需业务 owner 确认后方可用于正式汇报。

**与正式业务种类损益页的关系**：

- 正式页：`PAGE-PNL-BY-BUSINESS-001`（`/pnl-by-business`），见 `docs/page_contracts.md` §14.8.1。
- 候选页不替代、不扩展正式页的 PnL / FTP / 集中度限额口径。
- 前 4 个业务分析指标（集中度、负 FTP、份额漂移、资本效率象限）均基于已有 YTD / 月报父级行二次聚合或前端展示归类，**不重新查询原始事实表**（未追溯趋势除外）。
- 未追溯 PnL 趋势属于**数据链路诊断**，不得与月报 / YTD 业务贡献结论混用。

---

## 指标一览

| # | 页面模块 | 建议 Metric ID | 计算位置 | API |
|---|----------|----------------|----------|-----|
| 1 | 业务种类集中度 | `MTR-PNLBIZ-001`、`MTR-PNLBIZ-002` | 后端 | `GET /api/pnl/by-business-candidate-insights` |
| 2 | 负 FTP 持续性 | `MTR-PNLBIZ-003`、`MTR-PNLBIZ-004` | 后端 | 同上 |
| 3 | 份额漂移 | `MTR-PNLBIZ-005` | 后端 | 同上 |
| 4 | 资本效率象限 | *待登记*（建议 `MTR-PNLBIZ-007`） | **前端浏览器端** | `GET /api/pnl/by-business-ytd` |
| 5 | 未追溯 PnL 趋势 | `MTR-PNLBIZ-006` | 后端 | `GET /api/pnl/by-business-candidate-insights`（`reconciliation_diagnostics`） |

---

## 1. 业务种类集中度分析

### 1.1 业务定义

**回答的问题**：截至所选报告日，组合在 ZQTZ 父级业务种类上的**日均规模**是否过度集中于少数几类？集中度有多高？

这是结构风险观察指标，**不是**监管或内部已批准的集中度限额合规结论。

### 1.2 计算口径

| 子指标 | Metric ID | 公式 / 规则 | 单位 | 精度 |
|--------|-----------|-------------|------|------|
| 业务种类 HHI | `MTR-PNLBIZ-001` | `HHI% = Σ(share_i²) × 100`，其中 `share_i = avg_balance_i / Σ avg_balance` | `%` | 2 位小数 |
| 前 N 大占比合计 | `MTR-PNLBIZ-002` | `top_n_share% = Σ(top N 的 share_i) × 100`，默认 `N=3` | `%` | 2 位小数 |
| 各行占比明细 | — | `share_pct_i = avg_balance_i / Σ avg_balance × 100` | `%` | 2 位小数 |

**聚合维度**：

- 粒度：ZQTZ **父级业务种类**（`row_key` + `business_type`）。
- 排除规则（与正式业务种类页一致）：
  - `row_key` 含 `_detail_` 的明细行；
  - `business_type` 以「其中：」开头的子项行；
  - `source_note` 含「其中项」的行。
- `avg_balance ≤ 0` 的行不参与分子与分母。

**展示规则**：

- 明细表按 `share_pct` 降序排列（前端排序，不重算）。
- `null` 显示为 `—`。

### 1.3 数据来源

**调用链**：

```
GET /api/pnl/by-business-candidate-insights?year={year}&as_of_date={as_of_date}
  → backend/app/api/routes/pnl.py::by_business_candidate_insights
  → backend/app/services/pnl_by_business_candidate_insights.py::compute_business_type_concentration
  → backend/app/services/pnl_service.py::pnl_by_business_ytd_envelope（只读已有 YTD 信封）
```

**上游正式读模型**（间接来源，候选服务不直连）：

- `pnl.by_business_ytd` → `fact_formal_pnl_fi`、`fact_formal_zqtz_balance_daily`、`ZQTZ_ASSET_BOND_ROWS`
- 核心字段：`items[].avg_balance`、`items[].row_key`、`items[].business_type`、`items[].source_note`

**响应字段**：`result.concentration`（`hhi_pct`、`top_n`、`top_n_share_pct`、`rows[]`）

### 1.4 当前实现位置

| 层级 | 路径 | 关键符号 |
|------|------|----------|
| 页面 | `frontend/src/features/pnl-business-insights/PnlByBusinessInsightsPage.tsx` | `ConcentrationTable`、`sortConcentrationRows` |
| API 契约 | `frontend/src/api/contracts.ts` | `PnlByBusinessConcentrationSummary` |
| API 客户端 | `frontend/src/api/pnlClient.ts` | `getPnlByBusinessCandidateInsights` |
| 后端计算 | `backend/app/services/pnl_by_business_candidate_insights.py` | `compute_business_type_concentration` |
| 父级行判定 | `backend/app/core_finance/zqtz_asset_bond_category.py` | `is_parent_zqtz_business_row` |
| Schema | `backend/app/schemas/pnl.py` | `PnlByBusinessConcentrationSummary` |

### 1.5 建议 Owner

**待业务确认**。建议由**组合管理 / 固收业务分析**条线认领（与 `PAGE-PNL-BY-BUSINESS-001` 业务种类损益同一受众），需与风险管理区分「分析集中度」与「限额合规」职责边界。

### 1.6 转正前需业务确认的问题

1. **规模口径**：集中度分母使用 YTD **日均规模**（`avg_balance`，元），而非损益贡献（`total_pnl`）或期末余额（`current_balance`）。是否符合业务对「结构集中度」的定义？
2. **父级行范围**：仅统计 ZQTZ 父级业务种类，不含「其中」明细。是否覆盖业务关心的全部种类？
3. **HHI 解读阈值**：当前无红黄线；转正后是否需要设定内部分析阈值（如 HHI > X% 触发复核）？
4. **前 N 大 N 值**：默认 `top_n=3` 是否合适？是否需按业务种类总数动态调整？
5. **与限额关系**：本指标是否仅作内部分析，还是将来要对接正式集中度限额（若是，需单独 metric contract，不能沿用当前候选口径）？
6. **报告日语义**：`as_of_date` 截断 YTD 累计区间的方式是否与正式业务种类页一致？

### 1.7 转正后建议归属的 Metric Contract 分类

```yaml
page_id: PAGE-CONTRACT-PENDING:/pnl-by-business-insights  # 转正后升级为独立 page contract
page_slug: pnl-by-business-insights
section: 15.2.11 pnl-by-business-insights
metrics:
  - id: MTR-PNLBIZ-001
    name: 业务种类集中度 HHI
    status: candidate → formal（待审批）
    basis: analytical
    display_unit: "%"
    precision: 2
    sign_rule: unsigned percent
    null_rule: null → --
    source_endpoint: GET /api/pnl/by-business-candidate-insights
    bound_sample_id: GS-PNL-BUSINESS-INSIGHTS-A
  - id: MTR-PNLBIZ-002
    name: 业务种类前三大占比合计
    status: candidate → formal（待审批）
    # 其余字段同 MTR-PNLBIZ-001
```

**分类说明**：`analytical` 二次聚合层；`formal_use_allowed` 转正前须由 owner 明确是否允许进入正式汇报材料（当前服务层硬编码 `false`）。

---

## 2. 负 FTP 业务识别（负 FTP 持续性）

### 2.1 业务定义

**回答的问题**：近 12 个月内，哪些 ZQTZ 父级业务种类**持续跑不赢 FTP**（FTP 后净损益为负）？负 FTP 月份占比多高、最长连续负 FTP 有多久？

这是盈利质量 / 资源配置辅助观察，**不是**已批准的压降或退出决策依据。

### 2.2 计算口径

| 子指标 | Metric ID | 公式 / 规则 | 单位 | 精度 |
|--------|-----------|-------------|------|------|
| 负 FTP 月份占比 | `MTR-PNLBIZ-003` | `negative_ftp_month_share% = 负 FTP 月数 / months_observed × 100` | `%` | 2 位小数 |
| 最长连续负 FTP 月数 | `MTR-PNLBIZ-004` | 在观察窗口内，连续 `ftp_net_pnl < 0` 的最长月数 | 月 | 整数 |
| 覆盖月份数 | — | 窗口内有有效 `ftp_net_pnl` 值的月份数（`months_observed`） | 月 | 整数 |

**判定规则**：

- 负 FTP 月：`ftp_net_pnl < 0`（严格小于零；`null` 或 `≥ 0` 不计入负月）。
- 观察窗口：以 `as_of_date` 为终点，向前追溯 **12 个自然月**（`lookback_months=12`），窗口起止展示为 `window_start_month` ~ `window_end_month`。
- 跨自然年：分别调用对应年份的 `pnl_by_business_monthly_envelope`，按 `month_key` 对齐；某年无数据时跳过该年，不整体报错。
- 某月 bucket 缺失：该月计入序列但 `ftp_net_pnl=null`，**不计入** `months_observed`（缺口不是零，也不是负值）。
- 父级行过滤规则同集中度。

**页面提示阈值（仅 UI，非正式口径）**：

- `negative_ftp_month_share_pct ≥ 50%` 时表格行标黄（`NEGATIVE_FTP_WARN_THRESHOLD_PCT = 50`）。

### 2.3 数据来源

**调用链**：

```
GET /api/pnl/by-business-candidate-insights
  → compute_negative_ftp_persistence
  → pnl_service.pnl_by_business_monthly_envelope（只读已有月报信封）
```

**上游正式读模型**：

- `pnl.by_business_monthly` → 同上事实表链路
- 核心字段：`months[].items[].ftp_net_pnl`（父级行）、`months[].summary.ftp_net_pnl`（组合汇总，写入 summary 级统计）

**FTP 利率来源**：继承 YTD / 月报信封内已计算的 FTP 口径（见 `docs/pnl/plan-e-ftp-rate-unification-decision.md`）；候选服务不单独定义 FTP 利率。

**响应字段**：`result.negative_ftp_persistence`

### 2.4 当前实现位置

| 层级 | 路径 | 关键符号 |
|------|------|----------|
| 页面 | `frontend/src/features/pnl-business-insights/PnlByBusinessInsightsPage.tsx` | `NegativeFtpPersistenceTable`、`NEGATIVE_FTP_WARN_THRESHOLD_PCT` |
| API 契约 | `frontend/src/api/contracts.ts` | `PnlByBusinessNegativeFtpPersistenceSummary` |
| 后端计算 | `backend/app/services/pnl_by_business_candidate_insights.py` | `compute_negative_ftp_persistence`、`_persistence_stats`、`_longest_negative_streak` |
| Schema | `backend/app/schemas/pnl.py` | `PnlByBusinessNegativeFtpPersistenceSummary` |

### 2.5 建议 Owner

**待业务确认**。建议由**固收业务分析 / 组合绩效**条线认领；FTP 利率口径变更需与 `product-category-pnl` 治理同步确认。

### 2.6 转正前需业务确认的问题

1. **负 FTP 定义**：以月度 `ftp_net_pnl < 0` 为准，是否应改为「FTP 后年化收益率 < 0」或「低于某基准 spread」？
2. **观察窗口**：12 个自然月是否合适？是否应改为滚动 4 季、财年 YTD 等？
3. **缺口处理**：月报未发布月份视为缺口（不计入分母），是否符合业务预期？是否应 forward-fill 或视为负向信号？
4. **标黄阈值 50%**：是否为业务认可的预警线？转正后是否写入 metric contract？
5. **组合 vs 分业务**：除分业务表格外，summary 级 `negative_ftp_month_share_pct` 是否需要在页面首屏展示？
6. **与资源配置关系**：本指标转正后是否允许用于部室考核或限额审批？若不允许，需在 contract 中明确 `analytical_only`。

### 2.7 转正后建议归属的 Metric Contract 分类

```yaml
metrics:
  - id: MTR-PNLBIZ-003
    name: 负 FTP 月份占比（近12月）
    status: candidate → formal（待审批）
    basis: analytical
    display_unit: "%"
    precision: 2
    sign_rule: unsigned percent
    null_rule: null → --
    source_endpoint: GET /api/pnl/by-business-candidate-insights
    bound_sample_id: GS-PNL-BUSINESS-INSIGHTS-A
  - id: MTR-PNLBIZ-004
    name: 负 FTP 最长连续月数（近12月）
    status: candidate → formal（待审批）
    basis: analytical
    display_unit: 月
    precision: 0
    sign_rule: unsigned integer count
```

---

## 3. 份额漂移

### 3.1 业务定义

**回答的问题**：各 ZQTZ 父级业务种类在 YTD 日均规模中的份额，相对**上一年末**基准漂移了多少个百分点？

用于观察业务结构迁移趋势，**不是**战略配置目标达成率。

### 3.2 计算口径

| 子指标 | Metric ID | 公式 / 规则 | 单位 | 精度 |
|--------|-----------|-------------|------|------|
| 当前份额 | — | 当年 `as_of_date` 截断下的 `share_pct`（同集中度口径） | `%` | 2 位小数 |
| 基准份额 | — | 上一年 `12-31` 的 `share_pct` | `%` | 2 位小数 |
| 漂移 | `MTR-PNLBIZ-005` | `drift_pp = current_share_pct − baseline_share_pct` | `pp`（百分点） | 2 位小数，带符号 |

**对齐规则**：

- 按 `row_key` 对齐当前行与基准行。
- 基准年：`baseline_year = year − 1`，基准日：`{baseline_year}-12-31`。
- 上一年无 formal 数据时：`baseline_available=false`，页面展示「上一年无数据，无法计算漂移」；各行 `baseline_share_pct` / `drift_pp` 为 `null`。
- 当年有、去年无的业务种类：`baseline_share_pct=null`，`drift_pp=null`。
- 展示按 `|drift_pp|` 降序（前端排序）。

**口径备注（与字典差异）**：

- `docs/metric_dictionary.md` 登记名为「当前-年初」；**实际实现基准为上一年末（12-31）**，非当年年初。转正时必须统一命名与口径说明。

### 3.3 数据来源

**调用链**：

```
GET /api/pnl/by-business-candidate-insights
  → compute_business_type_share_drift
  → compute_business_type_concentration（当年 + 上一年各调用一次）
  → pnl_service.pnl_by_business_ytd_envelope
```

**响应字段**：`result.share_drift`（`baseline_year`、`baseline_as_of_date`、`baseline_available`、`rows[]`）

### 3.4 当前实现位置

| 层级 | 路径 | 关键符号 |
|------|------|----------|
| 页面 | `frontend/src/features/pnl-business-insights/PnlByBusinessInsightsPage.tsx` | `ShareDriftTable`、`formatSignedPp` |
| API 契约 | `frontend/src/api/contracts.ts` | `PnlByBusinessShareDriftSummary` |
| 后端计算 | `backend/app/services/pnl_by_business_candidate_insights.py` | `compute_business_type_share_drift` |
| Schema | `backend/app/schemas/pnl.py` | `PnlByBusinessShareDriftSummary` |

### 3.5 建议 Owner

**待业务确认**。建议由**组合战略 / 资产配置**条线认领，或与集中度指标同一 owner。

### 3.6 转正前需业务确认的问题

1. **基准日选择**：上一年末（12-31）vs 当年年初（1-1）vs 自定义战略基准日——业务认可哪一个？
2. **漂移幅度阈值**：多大 `pp` 变动应触发讨论？是否需要分业务种类设定容忍带？
3. **新种类 / 退出种类**：仅当年存在或仅去年存在的行如何处理（当前为 `null`）？
4. **与集中度关系**：漂移与 HHI 是否联合解读？转正后是否需要在首屏给出组合级漂移摘要？
5. **字典名称修正**：是否将 `MTR-PNLBIZ-005` 名称改为「相对上一年末份额漂移」以避免误导？
6. **历史可比性**：若上一年 YTD 信封因 FTP 口径统一（见 plan-e 决策）发生修订，漂移历史序列是否需重算说明？

### 3.7 转正后建议归属的 Metric Contract 分类

```yaml
metrics:
  - id: MTR-PNLBIZ-005
    name: 业务种类份额漂移（当前 − 上一年末，百分点）  # 建议修正字典名称
    status: candidate → formal（待审批）
    basis: analytical
    display_unit: pp
    precision: 2
    sign_rule: signed; positive = 份额上升
    null_rule: null → --
    source_endpoint: GET /api/pnl/by-business-candidate-insights
    bound_sample_id: GS-PNL-BUSINESS-INSIGHTS-A
```

---

## 4. 资本效率象限

### 4.1 业务定义

**回答的问题**：在当前 YTD 时点，各 ZQTZ 父级业务种类相对 peers 属于「规模大/小 × FTP 后效率高/低」哪一类？哪些值得增配、哪些需要压缩或观察？

这是资源配置讨论的**辅助分类视图**，分割线为中位数，**不代表**业务已确认的分类标准或正式组合指标。

### 4.2 计算口径

| 维度 | 字段 | 公式 / 规则 | 单位 |
|------|------|-------------|------|
| 规模轴 | `proportion` | `proportion = total_pnl_row / total_pnl_all × 100`（前端将 API 返回的小数 ×100 展示为 `%`） | `%` |
| 效率轴 | `ftp_net_annualized_yield_pct` | 继承 YTD 信封已计算的 FTP 后年化收益率 | `%` |
| 规模分割线 | — | 所有合格父级行 `proportion_pct` 的**中位数** | `%` |
| 效率分割线 | — | 所有合格父级行 `ftp_net_annualized_yield_pct` 的**中位数** | `%` |

**象限归类**（浏览器端，非后端持久化）：

| 象限 key | 名称 | 条件 | 页面提示 |
|----------|------|------|----------|
| `large_high` | 规模大 · 效率高 | `proportion ≥ 中位数` 且 `yield ≥ 中位数` | 重点关注：增配价值 |
| `large_low` | 规模大 · 效率低 | `proportion ≥ 中位数` 且 `yield < 中位数` | 重点关注：是否压缩 |
| `small_high` | 规模小 · 效率高 | `proportion < 中位数` 且 `yield ≥ 中位数` | 重点关注：是否值得增配 |
| `small_low` | 规模小 · 效率低 | `proportion < 中位数` 且 `yield < 中位数` | 重点关注：边际业务 |

**纳入条件**：

- 仅 ZQTZ 父级行（`isParentZqtzBusinessRow`，规则与后端 `is_parent_zqtz_business_row` 一致）。
- `proportion` 与 `ftp_net_annualized_yield_pct` 均非 `null` 才纳入；任一缺失则跳过该行。
- 象限内按 `proportion_pct` 降序排列。

**重要限制**：

- **计算完全在浏览器端完成**（`buildCapitalEfficiencyQuadrantModel`），后端无对应字段；`result_meta.formal_use_allowed` 来自 YTD API（`true`），但象限归类本身未经治理登记。
- 规模轴使用 **损益贡献占比**（`proportion`），与集中度使用的 **日均规模占比**（`share_pct`）不同——两模块回答不同问题，不可混读。

### 4.3 数据来源

**调用链**：

```
GET /api/pnl/by-business-ytd?year={year}&as_of_date={as_of_date}
  → backend/app/api/routes/pnl.py::by_business_ytd
  → pnl_service.pnl_by_business_ytd_envelope
  → 前端 CapitalEfficiencyQuadrantPanel.buildCapitalEfficiencyQuadrantModel
```

**上游正式读模型**：

- `pnl.by_business_ytd`（`formal_use_allowed=true`）
- 核心字段：`items[].proportion`、`items[].ftp_net_annualized_yield_pct`、`items[].total_pnl`
- `proportion` 在 `pnl_service._ytd_business_item_from_group` 中按 `total_pnl / total_pnl_for_proportion` 计算

**数据表**（经 YTD 信封间接）：`fact_formal_pnl_fi`、`fact_formal_zqtz_balance_daily`、`ZQTZ_ASSET_BOND_ROWS`

### 4.4 当前实现位置

| 层级 | 路径 | 关键符号 |
|------|------|----------|
| 页面 | `frontend/src/features/pnl-business-insights/PnlByBusinessInsightsPage.tsx` | `CapitalEfficiencyQuadrantPanel` 挂载、`ytdQuery` |
| 象限模型 | `frontend/src/features/pnl-business-insights/CapitalEfficiencyQuadrantPanel.tsx` | `buildCapitalEfficiencyQuadrantModel`、`classifyQuadrant`、`median` |
| 父级行判定 | `frontend/src/features/pnl/pnlByBusinessPageModel.ts` | `isParentZqtzBusinessRow` |
| API 客户端 | `frontend/src/api/pnlClient.ts` | `getPnlByBusinessYtd` |
| 后端 YTD | `backend/app/services/pnl_service.py` | `pnl_by_business_ytd_envelope`、`_ytd_business_item_from_group` |

### 4.5 建议 Owner

**待业务确认**。建议由**组合管理 / 资产配置**条线认领；需明确是否接受「浏览器端中位数分割」作为分析工具，或转正时必须后端化。

### 4.6 转正前需业务确认的问题

1. **规模轴定义**：使用损益贡献 `proportion` 而非日均规模 `avg_balance`——业务是否认可「资本效率」的「规模」指贡献占比？
2. **效率轴定义**：`ftp_net_annualized_yield_pct` 是否为业务认可的效率度量？是否应改为 ROE、风险调整后收益等？
3. **中位数分割线**：当期样本中位数随业务种类集合变化而变，不具备跨期可比性。是否改为固定阈值（如规模 >10%、收益率 >X%）？
4. **后端化要求**：转正是否要求将象限归类下沉到 `core_finance` / 后端服务，避免前后端重复逻辑？
5. **Metric 登记**：当前未在 `metric_dictionary.md` 登记。转正需新增 `MTR-PNLBIZ-007`（或拆分多条）并补 golden sample。
6. **行动含义**：四象限的「增配 / 压缩 / 边际」文案是否仅为提示，还是可作为正式投委会材料语言？
7. **与集中度模块一致性**：同一页面两套「份额」口径（`share_pct` vs `proportion`）是否需在 UI 上更显著区分？

### 4.7 转正后建议归属的 Metric Contract 分类

```yaml
# 当前字典无对应行；转正时建议新增
metrics:
  - id: MTR-PNLBIZ-007  # 建议编号，待治理确认
    name: 资本效率象限（规模贡献 × FTP后年化收益率）
    status: candidate（待首次登记）
    basis: analytical
    display_unit: 分类标签 + 辅助 %（proportion、ftp_net_annualized_yield_pct）
    precision: 2
    sign_rule: quadrant label; 效率轴为 signed percent
    null_rule: 缺 proportion 或 yield → 不纳入象限
    source_endpoint: GET /api/pnl/by-business-ytd + page-local quadrant model
    computation_location: frontend（转正时应评估是否迁移 backend）
    bound_page_id: PAGE-CONTRACT-PENDING:/pnl-by-business-insights
    bound_sample_id: none（转正前需补 capture）
    pending_confirmation: true
```

**分类说明**：建议归类为 `analytical` + `page-local derived`；若保持前端计算，必须在 page contract 中写明「浏览器端仅做展示归类，不重算正式口径」。

---

## 5. 未追溯 PnL 趋势（对账健康度诊断）

### 5.1 业务定义

**回答的问题**：近 12 个月各月末，`fact_formal_pnl_fi` 中无法追溯到 ZQTZ 余额行的损益记录占比是否在改善？数据链路是否健康？

**这不是业务分析指标**——反映的是 formal 对账完整性，**不构成**业务贡献、拖累或资源配置依据。页面已与业务分析区块视觉隔离，并附独立免责声明。

### 5.2 计算口径

| 子指标 | Metric ID | 公式 / 规则 | 单位 | 精度 |
|--------|-----------|-------------|------|------|
| 未追溯占比 | `MTR-PNLBIZ-006` | `untraced_share% = untraced_row_count / total_row_count × 100` | `%` | 2 位小数 |
| 未追溯行数 | — | 满足未追溯 SQL 条件的 `fact_formal_pnl_fi` 行数 | 行 | 整数 |
| 总行数 | — | 当日 `fact_formal_pnl_fi` 全部行数 | 行 | 整数 |

**未追溯判定 SQL**（与 `PAGE-PNL-BY-BUSINESS-001` §G 一致）：

- 对给定 `report_date`，在 `fact_formal_pnl_fi` 中不存在匹配的 `fact_formal_zqtz_balance_daily` 资产行：
  - 工具代码（含 `BOND-` 前缀变体）、组合名、成本中心、币种、`position_scope='asset'` 一致；
  - 且余额行 `business_type_primary` 非空。
- 详见 `backend/app/repositories/pnl_repo.py::_UNTRACED_COUNT_SQL`。

**时间序列规则**：

- 观察窗口：近 12 个自然月。
- 每月取该月内 **≤ as_of_date 的最新 formal 报表日**（非自然月末最后一天）；该月无 formal 数据则该月缺席，不插值。
- `total_row_count = 0` 时 `untraced_share_pct = null`（前端图表留空，不 coerce 为 0）。
- 图表使用中性灰色，不用红黄预警色（刻意区分于业务 KPI）。

### 5.3 数据来源

**调用链**：

```
GET /api/pnl/by-business-candidate-insights
  → compute_untraced_reconciliation_trend
  → PnlRepository.list_formal_fi_report_dates
  → PnlRepository.count_untraced_formal_fi_rows_for_dates
  → PnlRepository.count_formal_fi_rows_for_dates
```

**直接查询的数据表**：

- `fact_formal_pnl_fi`（分子分母）
- `fact_formal_zqtz_balance_daily`（追溯匹配）

**与正式页关系**：

- 单日诊断复用 `pnl_service` 中 `count_untraced_formal_fi_rows` 同一 SQL；见 `docs/page_contracts.md` §14.8.1 G。
- 补充证据包：`docs/pnl/pnl-by-business-formal-untraced-diagnostic-2026-05-31.md`、`pnl-by-business-formal-untraced-detail-packet-2026-05-31.md`。

**响应字段**：`result.reconciliation_diagnostics.rows[]`

### 5.4 当前实现位置

| 层级 | 路径 | 关键符号 |
|------|------|----------|
| 页面 | `frontend/src/features/pnl-business-insights/PnlByBusinessInsightsPage.tsx` | `UntracedReconciliationTrendPanel`、`RECONCILIATION_NOTE_TEXT` |
| 图表 | `frontend/src/features/pnl-business-insights/UntracedReconciliationTrendPanel.tsx` | `buildUntracedReconciliationTrendOption` |
| 后端计算 | `backend/app/services/pnl_by_business_candidate_insights.py` | `compute_untraced_reconciliation_trend`、`_resolve_trailing_month_end_report_dates` |
| Repository | `backend/app/repositories/pnl_repo.py` | `count_untraced_formal_fi_rows_for_dates`、`count_formal_fi_rows_for_dates`、`_UNTRACED_COUNT_SQL` |
| Schema | `backend/app/schemas/pnl.py` | `PnlByBusinessUntracedTrendSummary` |

### 5.5 建议 Owner

**待业务确认**。建议由**数据治理 / 正式对账**条线认领（非业务分析 owner）；与 `PAGE-PNL-BY-BUSINESS-001` formal primary 对账治理同一责任域。

### 5.6 转正前需业务确认的问题

1. **指标性质**：是否同意保持「数据质量诊断」定位，**永不**升格为业务绩效指标？
2. **追溯规则**：当前 strict match 规则是否仍为 owner 批准版本？`cost_center` 宽松回退是否应纳入未追溯统计？
3. **趋势解读**：占比上升是否自动触发治理工单？阈值多少？
4. **与业务区块并置**：即使视觉隔离，放在同一页面是否合适？转正后是否迁到数据治理 / 平台配置页？
5. **分母口径**：以 FI 行数为分母，而非损益金额加权——是否符合治理关注点？
6. **历史缺口**：某月无 formal 报表日时序列留空，业务是否接受？

### 5.7 转正后建议归属的 Metric Contract 分类

```yaml
metrics:
  - id: MTR-PNLBIZ-006
    name: 未追溯 FI 占比（近12个月末趋势）
    status: candidate → formal（待审批）
    basis: formal  # 数据质量 / 对账诊断
    metric_kind: reconciliation_health  # 区别于 analytical 业务二次聚合
    display_unit: "%"
    precision: 2
    sign_rule: unsigned percent
    null_rule: null → 图表留空 / 文案「无数据」
    source_endpoint: GET /api/pnl/by-business-candidate-insights
    bound_sample_id: GS-PNL-BUSINESS-INSIGHTS-A
    usage_constraint: 不得与月报/YTD业务贡献结论混用
    related_page_contract: PAGE-PNL-BY-BUSINESS-001 §G
```

**分类说明**：建议与 `MTR-PNLBIZ-001`~`005` 分属不同 `metric_kind`；在 page contract 中保持独立 section「对账健康度诊断（非业务结论）」。

---

## 跨指标转正检查清单

业务 owner 完成评审前，建议逐项确认：

| # | 检查项 | 涉及指标 |
|---|--------|----------|
| 1 | 是否批准将 `PAGE-CONTRACT-PENDING:/pnl-by-business-insights` 升级为正式 page contract | 全部 |
| 2 | 是否批准 `GS-PNL-BUSINESS-INSIGHTS-A` golden sample | 001~006 |
| 3 | 是否允许将 `formal_use_allowed` 从 `false` 改为 `true`（可按指标分批） | 全部 |
| 4 | FTP 利率口径是否与 `product-category-pnl` 年表统一且历史修订已告知 | 002、004 |
| 5 | 集中度 / 漂移的规模口径（`avg_balance`）是否确认为业务语言 | 001、003、005 |
| 6 | 资本效率象限是否后端化并补 metric 登记 | 004 |
| 7 | 未追溯趋势是否维持诊断定位、不进入业务汇报 | 006 |
| 8 | 负 FTP 标黄阈值、漂移基准日等 UI 参数是否写入 contract | 002、003、005 |
| 9 | 是否在 `docs/metric_dictionary.md` 修正 `MTR-PNLBIZ-005` 名称（上一年末 vs 年初） | 005 |
| 10 | 是否指定各指标业务 owner 与审批人（替换 `TBD`） | 全部 |

---

## 验证与证据索引

| 证据类型 | 路径 |
|----------|------|
| 契约测试 | `tests/test_pnl_by_business_candidate_insights_contract.py` |
| Golden sample 断言 | `tests/golden_samples/GS-PNL-BUSINESS-INSIGHTS-A/assertions.md` |
| Golden sample 审批状态 | `tests/golden_samples/GS-PNL-BUSINESS-INSIGHTS-A/approval.md` |
| 前端页面测试 | `frontend/src/features/pnl-business-insights/PnlByBusinessInsightsPage.test.tsx` |
| 象限面板测试 | `frontend/src/features/pnl-business-insights/CapitalEfficiencyQuadrantPanel.test.tsx` |
| 未追溯趋势测试 | `frontend/src/features/pnl-business-insights/UntracedReconciliationTrendPanel.test.tsx` |
| 正式页对账风险 | `docs/page_contracts.md` §14.8.1 G |
| MCP metric contracts | `moss-metric-contracts`（本次编写时不可用，以上以 `docs/metric_dictionary.md` 为准） |

---

## 变更记录

| 日期 | 说明 |
|------|------|
| 2026-07-07 | 初版：基于 `PnlByBusinessInsightsPage.tsx` 及后端 `pnl_by_business_candidate_insights` 服务整理 5 个页面模块转正评审材料 |
