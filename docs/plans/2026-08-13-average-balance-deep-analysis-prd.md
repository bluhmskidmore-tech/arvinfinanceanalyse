# PRD：/average-balance 日均分析深化（ADB Deep Insights）

- 日期：2026-08-13
- 页面：`/average-balance`（PAGE-ADB-001，candidate / temporary-exception）
- 状态：已批准实施（本文件即实施契约，实现中如需偏离必须回写本文件）

## 1. 背景与问题

当前 `/average-balance` 页面的后端（`backend/app/services/adb_analysis_service.py` + `backend/app/core_finance/adb_analytics.py`）只输出**描述性统计**：

- 区间日均 vs 期末时点、分类明细、加权 YTM/票息、NIM、覆盖诊断、会计分桶；
- 月度表有环比（MoM）与 YTD 汇总；
- 同比是前端自己拉两次 `/api/analysis/adb/comparison` 拼出来的（只有金额对比，无归因）。

**缺失的深入分析**（用户诉求"后端给的分析太浅了"）：

1. 变动"由谁贡献"——没有分类级贡献归因（环比/同比）；
2. NIM 变动"是量还是价"——没有量价（rate/volume/mix）分解；
3. 日度序列的波动、异常跳变、月末冲高（窗口粉饰）——只有一个总偏离度>5%的粗警示；
4. 结构集中度（HHI/TopN）与期初期末迁移——完全没有；
5. 没有后端生成的结构化结论（insights），页面只能靠人读表。

数据条件已具备：`fact_formal_zqtz_balance_daily` / `fact_formal_tyw_balance_daily`（CNY）覆盖 2024-01-01 ～ 2026-07-31（578 个报告日），2026 YTD 覆盖 212/212 天。

## 2. 目标与非目标

### 目标

- 新增**一个**后端分析端点 `GET /api/analysis/adb/insights`，一次返回：规模变动归因（环比+同比）、NIM 量价归因（环比）、波动与异常检测、结构集中度与迁移、结构化结论列表。
- 前端"日均分析"tab 新增"深度分析"区块渲染上述结果；结论列表并入现有"区间结论与警示"区。
- 全链路 fail-visible：对比期缺数、窗口过短、利率覆盖不足时显式披露原因，不静默降级、不用 0 顶替 null。

### 非目标（明确不做）

- insights 实施不扩展 insights 以外的新分析口径；**comparison 端点**已于 2026-08-14 落地 fail-visible 字段语义（四个 total 按侧可 `null`、`avg_unavailable_reason` / `spot_unavailable_reason`、`coverage_days` 有效日并集），与深度归因同源，详见 `docs/pnl/average-balance-page-contract.md` §Comparison fail-visible；
- 不提升任何 ADB 指标为 formal（envelope 保持 `basis=analytical`、`formal_use_allowed=false`）;
- 不做 LLM 生成文本（insights 为确定性规则）；
- 不改 H/A/T 映射、发行债剔除、FX 中间价、514/516/517 合并等受保护口径；
- 不做月度 tab 的深化（v1 只挂日度区间 tab）；
- 不新增 DuckDB 写路径（纯只读）。

## 3. 架构落位（不可违反）

```
frontend(/average-balance)
  -> GET /api/analysis/adb/insights            (backend/app/api/routes/adb_analysis.py，薄路由)
  -> adb_insights_envelope(...)                (backend/app/services/adb_analysis_service.py，编排+缓存)
      -> _load_adb_raw_data(...) ×3            (本期 / 环比期 / 同比期，复用既有加载与快照补数)
      -> backend/app/core_finance/adb_deep_analytics.py   (新增，纯函数，无 DB 访问)
      -> _build_analytical_envelope(result_kind="adb.insights")
```

- RBAC：沿用 `ensure_read_allowed(auth, "adb_analysis", ...)`。
- 缓存：`lru_cache(maxsize=16)`，键 `(start_date, end_date, duckdb_path)`，并提供 `clear_adb_insights_cache()`；沿用 `adb_comparison_envelope` 的 `MOSS_DUCKDB_PATH` 环境检查模式。
- 分类口径：与 comparison 完全同源（ZQTZ 资产用 `_assign_zqtz_bond_categories`，负债用发行分类；TYW 用 `product_type`；利率口径用 `_split_rate_frames` + `build_rate_map` 同一套 enriched frames）。**禁止另起一套分类**。

## 4. 分析口径定义（冻结）

以下公式为验收基准，单元测试必须覆盖闭合性。

### 4.1 对比窗口

- 本期：`[start_date, end_date]`，日历天数 `D = (end-start).days + 1`。
- 环比期（qoq）：紧邻前一段等长区间 `[start_date - D 天, start_date - 1 天]`。
- 同比期（yoy）：`[start_date - 1年, end_date - 1年]`（ISO 日期减 1 年，2/29 回退 2/28，与前端 `shiftIsoDateByYears` 一致）。
- 任一对比窗口加载后无任何数据行 → 该组归因为 `null`，窗口对象 `available=false`、`reason="no_data"`。
- 本期没有任何有效数值余额 → 本期窗口 `available=false`，所有分析块为 `null`，
  `nim_attribution_unavailable_reason="current_unavailable"`，并输出
  `current_unavailable` 质量结论；上游内部归零不得把缺失余额伪装成有效 0。
- 本期 `D <= 1` → 除 `windows` 外所有分析块为 `null`，`insufficient_window=true`。

### 4.2 规模变动归因（scale attribution）

对每侧（资产/负债）、每个对比基准（qoq/yoy）：

- 分类日均与既有 comparison 对账：若 `0 < coverage_days < D`，先按
  `sum_effective_i = Σ(观测余额_i) × D / coverage_days` 做
  `observed_days_scaled_to_calendar` 样本补齐，再计算
  `avg_i = sum_effective_i / D`；满覆盖时等价于 `Σ余额_i / D`。对比期使用自身
  `D`/`coverage_days`，无效或非数值余额不计入余额和及覆盖日。
- comparison 端点（已落地）：`coverage_days` 为两侧**有效余额**观测日并集；无效行不参与金额、coverage、LOCF `end_date_seen`；四个 total 按侧无有效余额为 `null`（valid 0 仍为 `0.0`）；`avg_unavailable_reason` = `insufficient_window` \| `no_data` \| `null`，`spot_unavailable_reason` = `no_data` \| `null`；前端 `null` → `EM_DASH`，偏离/同比不计算。
- `delta_i = avg_i_cur − avg_i_prior`；总变动 `delta_total = total_avg_cur − total_avg_prior`。
- 贡献率 `contribution_pct_i = delta_i / |delta_total| × 100`（`delta_total=0` 时为 null）。
- **闭合性：Σ delta_i ≡ delta_total（容差 1e-6 相对误差）**。分类并集：本期∪对比期，一侧缺失按 0 处理（新增/退出类自然成立）。

### 4.3 NIM 量价归因（rate/volume decomposition，仅 qoq）

利率为百分数单位（2.34 = 2.34%），效应输出 bp（×100）。

每侧加权利率 `R = Σ(balance_i × rate_i) / Σ(balance_i | rate_i 非空)`（沿用 build_rate_map 口径，仅按有利率余额加权）。对每侧：

- 占比 `share_i = rate_balance_i / Σ rate_balance`（用有利率余额，基准=对比期，Laspeyres）。
- 利率效应 `rate_effect_i = share_prior_i × (rate_cur_i − rate_prior_i) × 100`（bp；任一期 rate 为 null → 0，缺口滚入 residual）。
- 结构效应 `mix_effect_i = (share_cur_i − share_prior_i) × (rate_prior_i − R_prior) × 100`（bp；新增类 `share_prior=0`、`rate_prior` 用 `R_prior` 顶替即 mix=share_cur×(rate_cur−R_prior)×100 归入 mix，实现可选等价式，测试按闭合性验收）。
- 残差 `residual_bp = (R_cur − R_prior)×100 − Σ(rate_effect_i + mix_effect_i)`，**必须原样披露**。
- NIM 归因：`nim_delta_bp = (NIM_cur − NIM_prior)×100`；`asset_side.total_effect_bp = (asset_yield_cur − asset_yield_prior)×100`；`liability_side.total_effect_bp = (liability_cost_cur − liability_cost_prior)×100`；恒等式 `nim_delta_bp = asset_side.total − liability_side.total`（负债成本上升压缩 NIM）。
- 任一期任一侧 `R` 为 null → `nim_attribution=null` + `reason="rate_unavailable"`。

### 4.4 波动与异常（volatility）

对本期日度总资产、总负债两条序列（仅观测日，缺失日不补 0）：

- `mean` / `std`（样本标准差，n−1）/ `cv = std/mean`（mean=0 → null）；`min`/`max` 各带日期。
- 最大单日变动：相邻观测日 `change_t = bal_t − bal_{t−1}` 绝对值最大的一条（date/delta/pct）。
- 异常日：对 `change_t` 序列计算 z-score（其自身 mean/std），`|z| ≥ 2.5` 判异常；输出 ≤10 条按 |z| 降序；`std=0` 或观测点 <5 → 空数组 + `anomaly_detection_available=false`。
- 月末效应（窗口粉饰深化）：对本期内每个自然月，若该月观测日 ≥5：`month_end = 该月最后观测日余额`，`mid = 该月其余观测日均值`，`uplift_pct_m = (month_end − mid)/mid × 100`。输出跨月平均 `uplift_pct` 与 `months_observed`；`flagged = uplift_pct > 1.0`（资产/负债各自判断）。

### 4.5 结构集中度（concentration）

对每侧，取本期**首个观测日**与**末个观测日**的分类余额分布：

- `hhi = Σ(share_i²)`（share 为 0–1 小数，输出 4 位小数）；
- `top3_share` / `top5_share`（0–1 小数）；
- 迁移 movers：`share_end_i − share_start_i`（百分点，pp），按 |Δ| 降序取前 8；
- 首末观测日相同（区间只有 1 个观测日）→ `concentration=null` + `reason="single_observation"`。

### 4.6 结论规则（insights，确定性规则引擎）

severity ∈ `info | notice | warning`；dimension ∈ `scale | nim | volatility | concentration | quality`。规则（v1 固定阈值，写死在 core_finance）：

| id | 条件 | severity |
| --- | --- | --- |
| `scale_qoq_move` | qoq 可用且资产或负债 `|delta_pct| > 3%`：给出方向 + 前 2 大贡献分类 | 5%以上 notice，否则 info |
| `nim_compression` | `nim_delta_bp < -10` → 指出主导侧（资产 rate / 负债 rate / mix，取 |bp| 最大项） | ≤−20bp warning，否则 notice |
| `nim_expansion` | `nim_delta_bp > +10` | info |
| `anomaly_days` | 异常日 ≥1：列出最大 |z| 的日期与金额 | 有 |z|≥4 warning，否则 notice |
| `month_end_effect` | 任一侧 `flagged=true`：月末均值高于月中 X% | warning |
| `concentration_up` | 任一侧 `hhi_end − hhi_start > 0.02` | notice |
| `current_unavailable` | 本期没有任何有效数值余额 | info |
| `comparison_unavailable` | qoq 或 yoy `available=false` | info |
| `rate_coverage_low` | 本期任一侧利率覆盖 < 0.9（复用本期 build_rate_map coverage） | info |

每条输出：`{ id, severity, dimension, title, detail, evidence: object }`，title/detail 为简体中文完整句，数值嵌入 detail（亿元 2 位小数、bp 1 位、% 2 位）。

## 5. API 契约（冻结）

`GET /api/analysis/adb/insights?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`

- 422：缺参/非法日期；400：start > end；200：其余情况（含空数据，fail-visible 由 payload 表达）。
- 响应 = `_build_analytical_envelope(result_kind="adb.insights", basis="analytical", formal_use_allowed=false)` + `result` 如下（TypeScript 记法）：

```ts
type AdbInsightsWindow = {
  start_date: string; end_date: string;
  calendar_days_inclusive: number;
  coverage_days: number;              // 该窗口含有效余额的不重复观测日数
  available: boolean;
  reason: "ok" | "no_data" | null;
};

type AdbScaleContributionRow = {
  category: string;
  side: "asset" | "liability";
  current_avg: number | null;         // 元
  prior_avg: number | null;           // 元；对比期缺该类=0 参与 delta 但此处披露 null
  delta: number;                      // 元
  contribution_pct: number | null;    // 占总变动 |delta_total| 的 %
};

type AdbScaleAttribution = {
  side_totals: {
    assets: { current_avg: number; prior_avg: number; delta: number; delta_pct: number | null };
    liabilities: { current_avg: number; prior_avg: number; delta: number; delta_pct: number | null };
  };
  asset_contributions: AdbScaleContributionRow[];      // 按 |delta| 降序，全量
  liability_contributions: AdbScaleContributionRow[];
};

type AdbNimSideAttribution = {
  total_effect_bp: number;            // 该侧加权利率变动（bp）
  rate_effect_bp: number;             // Σ 分类利率效应
  mix_effect_bp: number;              // Σ 分类结构效应
  residual_bp: number;
  by_category: Array<{
    category: string;
    share_current: number | null;     // 0–1
    share_prior: number | null;
    rate_current: number | null;      // %
    rate_prior: number | null;
    rate_effect_bp: number;
    mix_effect_bp: number;
  }>;                                 // 按 |rate+mix| 降序，全量
};

type AdbNimAttribution = {
  basis: "qoq";
  nim_current: number | null;         // %
  nim_prior: number | null;
  nim_delta_bp: number | null;
  asset_side: AdbNimSideAttribution;
  liability_side: AdbNimSideAttribution;
};

type AdbVolatilitySeries = {
  mean: number; std: number; cv: number | null;
  min: { date: string; value: number };
  max: { date: string; value: number };
  max_daily_change: { date: string; delta: number; pct: number | null } | null;
};

type AdbAnomalyItem = {
  date: string; side: "asset" | "liability";
  value: number; delta: number; zscore: number;
  direction: "up" | "down";
};

type AdbMonthEndEffect = {
  uplift_pct: number | null; months_observed: number; flagged: boolean;
};

type AdbVolatilityBlock = {
  assets: AdbVolatilitySeries | null;         // 观测日 <2 → null
  liabilities: AdbVolatilitySeries | null;
  anomaly_detection_available: boolean;
  anomalies: AdbAnomalyItem[];
  month_end_effect: { assets: AdbMonthEndEffect; liabilities: AdbMonthEndEffect } | null;
};

type AdbConcentrationSide = {
  start_observation_date: string; end_observation_date: string;
  hhi_start: number; hhi_end: number;         // 0–1，4 位小数
  top3_share_start: number; top3_share_end: number;
  top5_share_start: number; top5_share_end: number;
  movers: Array<{ category: string; share_start_pct: number; share_end_pct: number; delta_pp: number }>;
};

type AdbInsightItem = {
  id: string;
  severity: "info" | "notice" | "warning";
  dimension: "scale" | "nim" | "volatility" | "concentration" | "quality";
  title: string;                      // 中文短句
  detail: string;                     // 中文完整句，含数值
  evidence: Record<string, unknown>;
};

type AdbInsightsPayload = {
  start_date: string; end_date: string;
  calendar_days_inclusive: number;
  insufficient_window: boolean;       // D<=1 时 true，此时以下分析块全为 null
  windows: { current: AdbInsightsWindow; qoq: AdbInsightsWindow; yoy: AdbInsightsWindow };
  scale_attribution: { qoq: AdbScaleAttribution | null; yoy: AdbScaleAttribution | null };
  nim_attribution: AdbNimAttribution | null;
  nim_attribution_unavailable_reason: string | null;   // "rate_unavailable" | "comparison_unavailable" | "current_unavailable" | "insufficient_window" | null
  volatility: AdbVolatilityBlock | null;
  concentration: { assets: AdbConcentrationSide | null; liabilities: AdbConcentrationSide | null; reason: string | null } | null;
  insights: AdbInsightItem[];         // 永不为 null，可为空数组
};
```

信封层：`tables_used` 为三个窗口加载的并集；任一窗口用了快照补数 → `quality_flag="warning"`、`fallback_mode="latest_snapshot"`（沿用 `_adb_uses_snapshot_fallback` 逻辑，`adb_denominator_basis` 取三窗口中最"混合"的一个）。

## 6. 前端要求

- 契约新增到 `frontend/src/api/contracts/cubeAdb.ts`（`AdbInsightsResponse = payload & { result_meta?: ResultMeta }`），client 方法 `getAdbInsights(startDate, endDate)` 加入 `liabilityAdbClient.ts`（real：GET 上述端点、展平 envelope 同 `getAdbComparison` 现有模式；mock：新增确定性演示数据，放在该文件既有 mock 工厂旁）+ `clientContext.ts` 注册。
- 新组件目录 `frontend/src/features/average-balance/components/`：
  - `AdbDeepAnalysisSection.tsx`（容器：4 个子区 + 加载/错误态）；
  - 子组件可自行组织（建议 `AdbScaleAttributionPanel` / `AdbNimAttributionPanel` / `AdbVolatilityPanel` / `AdbConcentrationPanel`），复用 `AdbSectionHead`、`AdbKpiStrip`、`.adb-panel`/`.adb-two-col` 既有样式类与 antd Table，禁止新的内联布局 style。
- `AverageBalanceView.tsx` 最小侵入：新增一个 `useQuery`（key 含 client.mode/start/end，`enabled` 同 comparison 成功后），在"分类明细"section 之后挂 `<AdbDeepAnalysisSection ... />`；`insights` 列表渲染进现有"区间结论与警示"区（追加在既有 Alert 之后，按 severity 映射 antd Alert type：warning→warning，notice→info，info→info 且视觉降权）。
- 缺数语义：null → `EM_DASH`；对比期 `available=false` → 显示"对比期无数据（YYYY-MM-DD～YYYY-MM-DD）"；本期 `available=false` → 整区显示"本期无有效余额，无法计算深度分析"；`insufficient_window` → 整区显示"区间过短，无法计算深度分析"。
- 单位：金额亿元 2 位；效应 bp 1 位；占比/百分比 2 位；沿用页面既有 `formatYi`/`formatPct` 风格（可提取到组件内本地 helper，但缺失渲染必须用 `EM_DASH`）。
- 深色主题：正负 tone 用 `src/utils/tone.ts` 的 `TONE_CSS_VAR`，禁止浅色 semantic 色直灌。

## 7. 治理与文档

- `docs/page_contracts.md` PAGE-ADB-001：路由清单加 `GET /api/analysis/adb/insights`；C 节必有 section 表加 `deep_analysis` 行；E 节 Endpoint/DTO 表加一行（basis=analytical，`result_kind=adb.insights`）；F 节指标映射追加：
  - `MTR-ADB-004` 区间规模变动归因（candidate / pending_confirmation）
  - `MTR-ADB-005` NIM 量价归因（candidate / pending_confirmation）
  - `MTR-ADB-006` 日度波动与异常检测（candidate / pending_confirmation）
  - `MTR-ADB-007` 结构集中度与迁移（candidate / pending_confirmation）
- `docs/metric_dictionary.md`：按既有 `MTR-ADB-00x` 条目格式追加上述 4 条 candidate 指标（公式引用本 PRD §4）。
- `docs/pnl/average-balance-page-contract.md` 侧翼草稿：追加 insights 端点小节（与主契约一致的摘要）。
- 所有响应 `formal_use_allowed=false` 不变；本 PRD 不构成任何 formal 提升。

## 8. 验收标准（可观察）

1. `GET /api/analysis/adb/insights?start_date=2026-01-01&end_date=2026-07-31` 返回 200，payload 含非空 `scale_attribution.qoq/yoy`、`nim_attribution`、`volatility`、`concentration`、`insights ≥ 1` 条；`result_meta.formal_use_allowed=false`、`basis=analytical`。
2. 闭合性测试通过：Σ分类 delta = 总 delta；rate+mix+residual = 该侧总效应；`nim_delta_bp = asset_total − liability_total`。
3. 对比期无数据（如 start=2024-01-01）→ `qoq.available=false`、`scale_attribution.qoq=null`、HTTP 200、`comparison_unavailable` insight 存在。
4. 单日窗口 → `insufficient_window=true`、分析块全 null、HTTP 200。
5. 前端 `/average-balance` 日均 tab 出现"深度分析"区块，四个面板渲染真实数据，异常/月末效应触发时出现 warning 提示；mock 模式亦可渲染。
6. 现有测试全绿：`tests/test_adb_analysis_api.py`、`frontend/src/test/AverageBalancePage.test.tsx`、`AverageBalanceView.test.tsx`；新增后端/前端测试全绿；`npm run lint`/`typecheck`/`debt:audit` 通过。
7. comparison 以外既有端点（`/adb`、`/monthly`、`/coverage`）响应逐字节不变；comparison 仅允许 fail-visible 语义对齐（见 §4.2 与侧翼合同），不得另扩口径。

## 9. 任务拆分与模型分配

| 任务 | 范围 | 难度 | 模型 | 依赖 |
| --- | --- | --- | --- | --- |
| T1 后端 | `core_finance/adb_deep_analytics.py`（纯函数）+ 单测；service `adb_insights_envelope` + 缓存；route + API 测试 | 高（金融归因公式+闭合性） | claude-opus-5-thinking-max-fast | 无（契约已冻结） |
| T2 前端 | contracts + client(real/mock) + clientContext + 深度分析组件 + View 挂载 + Vitest | 中 | claude-sonnet-5-thinking-high | 契约已冻结，可与 T1 并行 |
| T3 文档 | page_contracts / metric_dictionary / 侧翼草稿 | 低 | composer-2.5-fast | 本 PRD |
| T4 审计 | calc-audit-balance-accounting 审计 T1 计算正确性 | — | 项目审计代理 | T1 完成 |
| T5 集成验证 | 全量测试 + 真实链路浏览器验证 + debt 审计 | — | 主代理 | T1+T2 |

## 10. 风险

- 量价分解残差：占比按"有利率余额"计算，利率覆盖不足时 residual 变大——已通过 `residual_bp` 显式披露 + `rate_coverage_low` insight 缓解；
- 对比期快照补数：qoq/yoy 窗口若走 snapshot fallback，口径为原币（与本期 formal CNY 存在小偏差）——envelope `quality_flag=warning` 披露，页面已有快照降级警示语义可复用；
- lru_cache 与物化任务时序：backfill 后需 `clear_adb_insights_cache()`（与 comparison 缓存同一清理路径，T1 需在 backfill 路由的缓存清理处一并接入，若现有 backfill 无清理则保持一致不加）；
- `AverageBalanceView.tsx` 已 1335 行：新代码必须放独立组件文件，View 只加挂载点，防止进一步膨胀。
