# Codex Handoff: MOSS-V3 股票分析工作台 P0

> 交给 Codex 执行的完整实现说明。请严格按本文实施，不要扩大范围。

## 0. 任务目标

在 `F:\MOSS-V3` / `/mnt/f/MOSS-V3` 中，把现有 Livermore / Choice A股观察能力做成一个独立、可见、只读、证据优先的“股票分析工作台”。

新增一个前端页面：

- 路由：`/stock-analysis`
- 导航标签：`股票分析`
- 所属分组：市场工作台
- 页面定位：A股市场状态、行业强弱、候选股证据、风险退出、数据口径边界

P0 不新增后端核心计算，不新增交易动作，不新增任意 SQL，不新增自动调仓/买卖建议。

---

## 1. 当前代码事实

当前仓库已有股票/ Livermore 能力，主要位置如下：

### 1.1 前端合同

- `frontend/src/api/contracts.ts`
  - `LivermoreStrategyPayload`
  - `LivermoreMarketGate`
  - `LivermoreSectorRankPayload`
  - `LivermoreStockCandidatesPayload`
  - `LivermoreRiskExitPayload`
  - `LivermoreSignalConfluencePayload`

现有字段包括：

- `market_gate`
- `sector_rank`
- `stock_candidates`
- `risk_exit`
- `rule_readiness`
- `data_gaps`
- `diagnostics`
- `supported_outputs`
- `unsupported_outputs`

### 1.2 前端 API Client

- `frontend/src/api/marketDataClient.ts`

现有方法：

- `getLivermoreStrategy({ asOfDate? })`
- `getLivermoreSignalConfluence({ asOfDate? })`
- `materializeLivermorePositionSnapshot(...)`
- `materializeLivermoreManualPositionSnapshot(...)`

P0 只用前两个读方法。不要在股票页调用写入/物化方法。

### 1.3 现有页面

- `frontend/src/features/cross-asset/pages/CrossAssetDriversPage.tsx`
- `frontend/src/features/cross-asset/pages/CrossAssetPage.tsx`
- `frontend/src/test/CrossAssetPage.test.tsx`

CrossAsset 页面里已经有 Livermore A股策略状态、候选、风险退出和手工持仓快照相关逻辑。P0 股票页可参考这里的展示口径，但不要直接复制大段复杂页面逻辑。

### 1.4 导航和路由

- `frontend/src/mocks/navigation.ts`
- `frontend/src/router/routes.tsx`
- `frontend/src/test/WorkbenchShell.test.tsx`
- `frontend/src/test/RouteRegistry.test.tsx`

`/cross-asset` 当前属于 `market` 分组。新增 `/stock-analysis` 也应属于 `market` 分组。

### 1.5 后端只读服务

- `backend/app/api/routes/market_data_livermore.py`
- `backend/app/services/market_data_livermore_service.py`
- `backend/app/core_finance/livermore_strategy.py`
- `backend/app/core_finance/livermore_sector_rank.py`
- `backend/app/core_finance/livermore_stock_candidates.py`
- `backend/app/core_finance/livermore_risk_exit.py`

P0 不需要改这些文件。除非现有前端合同无法满足展示，才允许做很小的只读补充；但默认不要改后端。

---

## 2. 绝对边界

### 必须做

1. 新增 `/stock-analysis` 页面。
2. 市场工作台导航里显示 `股票分析`。
3. 页面首屏显示：
   - 市场状态
   - 行业强弱
   - 候选股证据卡
   - 风险退出观察
   - 数据口径与边界
4. 候选股必须解释：
   - 为什么入选
   - 反证 / 待补证据
   - 失效条件
5. 明确显示：仅观察、复核和研究，不构成交易指令。
6. 基本面 / 估值 / 银行股字段当前缺失时必须显式展示“待补”，不得 mock 成事实。

### 禁止做

1. 禁止新增买入/卖出/下单/调仓/自动交易动作。
2. 禁止在前端使用“买入建议”“卖出建议”等措辞。
3. 禁止新增任意 SQL 网关。
4. 禁止绕过现有 API client 直接访问 DuckDB / 文件 / vendor。
5. 禁止改 Choice / Tushare 凭据与权限。
6. 禁止大规模重构 `marketDataClient.ts`。
7. 禁止修改无关页面、债券分析、损益、宏观工具等 unrelated dirty files。
8. 禁止把 analytical / Livermore 结果包装成正式投资结论。

---

## 3. 仓库脏文件注意事项

执行前必须先运行：

```bash
git status --short
```

当前仓库可能已有大量 unrelated dirty files，例如：

- `backend/app/api/routes/macro_toolkit.py`
- `backend/app/core_finance/qdb_gl_monthly_analysis.py`
- `backend/app/repositories/duckdb_migrations.py`
- `backend/app/services/bond_analytics_service.py`
- `backend/app/services/qdb_gl_monthly_analysis_service.py`
- `backend/app/tasks/choice_stock_materialize.py`
- `frontend/src/features/bond-analytics/...`
- `frontend/src/features/ledger-pnl/...`
- `frontend/src/features/macro-toolkit/...`
- 多个 `.tmp-pytest-*` 临时目录

不要格式化、提交、重写或总结这些无关文件。只改本任务列出的文件。

---

## 4. 实施文件清单

### 新建文件

1. `frontend/src/features/stock-analysis/pages/StockAnalysisPage.tsx`
2. `frontend/src/features/stock-analysis/pages/StockAnalysisPage.css`
3. `frontend/src/features/stock-analysis/lib/stockAnalysisPageModel.ts`
4. `frontend/src/test/StockAnalysisPage.test.tsx`
5. `frontend/src/test/StockAnalysisPageModel.test.ts`

### 修改文件

1. `frontend/src/mocks/navigation.ts`
2. `frontend/src/router/routes.tsx`
3. `frontend/src/test/WorkbenchShell.test.tsx`
4. `frontend/src/test/RouteRegistry.test.tsx`

### 不应修改

默认不要修改：

- `frontend/src/api/client.ts`
- `frontend/src/api/marketDataClient.ts`
- `backend/app/**`
- `tests/**`

除非测试发现类型合同确实缺字段，否则不改 API 合同。

---

## 5. 任务分解

## Task 1: 导航接入

### 目标

让市场工作台子导航出现 `股票分析`，路径为 `/stock-analysis`。

### 修改文件

- `frontend/src/mocks/navigation.ts`
- `frontend/src/test/WorkbenchShell.test.tsx`

### 实现要求

在 `workbenchSectionGroups` 中加入：

```ts
"stock-analysis": "market",
```

在 `workbenchNavigation` 中靠近 `market-data` / `macro-toolkit` / `cross-asset` 添加：

```ts
{
  key: "stock-analysis",
  label: "股票分析",
  path: "/stock-analysis",
  icon: "market",
  description: "A股市场状态、行业强弱、候选股证据与风险观察",
  readiness: "live",
  readinessLabel: "观察口径",
  governanceStatus: "temporary-exception",
  readinessNote:
    "复用 Livermore / Choice 股票只读分析链路，仅展示观察和复核证据，不生成交易指令。",
},
```

### 测试要求

在 `WorkbenchShell.test.tsx` 中增加或更新测试：

```ts
it("uses transparent main surface for cross-asset and keeps market workbench subnav", async () => {
  renderShellAt("/cross-asset");

  expect(await screen.findByText("cross-asset body")).toBeInTheDocument();
  const subnav = await screen.findByTestId("workbench-section-subnav");
  const hrefs = within(subnav).getAllByRole("link").map((link) => link.getAttribute("href"));
  expect(hrefs).toEqual(
    expect.arrayContaining(["/market-data", "/macro-toolkit", "/cross-asset", "/stock-analysis", "/news-events"]),
  );
  expect(subnav).toHaveTextContent("股票分析");
});
```

如果原测试硬编码 `toHaveLength(4)`，改成 `toHaveLength(5)` 或改用 arrayContaining，避免过度脆弱。

### 验证命令

```bash
cd frontend && npm run test -- src/test/WorkbenchShell.test.tsx --testNamePattern='cross-asset|市场|stock' --pool=forks --poolOptions.forks.singleFork=true
```

---

## Task 2: 路由接入

### 目标

`/stock-analysis` 能渲染股票分析页面。

### 修改文件

- `frontend/src/router/routes.tsx`
- `frontend/src/test/RouteRegistry.test.tsx`
- 新建 `frontend/src/features/stock-analysis/pages/StockAnalysisPage.tsx`
- 新建 `frontend/src/features/stock-analysis/pages/StockAnalysisPage.css`

### 页面最小实现

`StockAnalysisPage.tsx` 初始可写成：

```tsx
import "./StockAnalysisPage.css";

export default function StockAnalysisPage() {
  return (
    <main className="stock-analysis-page" data-testid="stock-analysis-page">
      <header className="stock-analysis-page__header">
        <p className="stock-analysis-page__eyebrow">A股观察 / Evidence first</p>
        <h1>股票分析</h1>
        <p>
          复用 Livermore 与 Choice 股票只读链路，展示市场状态、行业强弱、候选股证据和风险观察；仅供研究复核，不构成交易指令。
        </p>
      </header>
    </main>
  );
}
```

`StockAnalysisPage.css` 初始可写成：

```css
.stock-analysis-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 4px 0 32px;
}

.stock-analysis-page__header {
  border: 1px solid rgba(15, 23, 42, 0.1);
  border-radius: 18px;
  padding: 20px;
  background: linear-gradient(135deg, rgba(15, 23, 42, 0.96), rgba(30, 64, 175, 0.88));
  color: #fff;
}

.stock-analysis-page__eyebrow {
  margin: 0 0 6px;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  opacity: 0.76;
}
```

### 路由修改

在 `routes.tsx` 增加 lazy import：

```ts
const StockAnalysisPage = lazy(
  () => import("../features/stock-analysis/pages/StockAnalysisPage"),
);
```

在 `buildWorkbenchChildRoutes()` 中加入：

```ts
if (section.path === "/stock-analysis") {
  return {
    path: section.path.slice(1),
    element: routeElement(<StockAnalysisPage />),
  };
}
```

### RouteRegistry 测试

在 `RouteRegistry.test.tsx` 加 mock：

```ts
vi.mock("../features/stock-analysis/pages/StockAnalysisPage", () => ({
  default: () => (
    <section data-testid="stock-analysis-page">
      <h1>股票分析</h1>
    </section>
  ),
}));
```

加测试：

```ts
it("renders the stock-analysis route", async () => {
  renderWorkbenchApp(["/stock-analysis"], { client: mockClient });
  expect(await screen.findByTestId("stock-analysis-page")).toBeInTheDocument();
  expect(await screen.findByRole("heading", { name: "股票分析" })).toBeInTheDocument();
});
```

### 验证命令

```bash
cd frontend && npm run test -- src/test/RouteRegistry.test.tsx --testNamePattern='stock-analysis' --pool=forks --poolOptions.forks.singleFork=true
```

---

## Task 3: 新增股票页 View Model

### 目标

把 `LivermoreStrategyPayload` / `LivermoreSignalConfluencePayload` 转成页面可直接展示的业务模型。

### 新建文件

- `frontend/src/features/stock-analysis/lib/stockAnalysisPageModel.ts`
- `frontend/src/test/StockAnalysisPageModel.test.ts`

### 输出类型建议

```ts
import type {
  LivermoreSignalConfluencePayload,
  LivermoreStrategyPayload,
} from "../../../api/contracts";

export type StockMarketStateCard = {
  title: string;
  state: string;
  exposureLabel: string;
  passedLabel: string;
  basisLabel: string;
  warnings: string[];
};

export type StockSectorRow = {
  rank: number;
  sectorCode: string;
  sectorName: string;
  score: string;
  pctChange: string;
  turnover: string;
  amplitude: string;
  constituentCount: number;
};

export type StockCandidateEvidenceCard = {
  rank: number;
  stockCode: string;
  stockName: string;
  sectorName: string;
  headline: string;
  evidence: string[];
  counterEvidence: string[];
  invalidationRules: string[];
};

export type StockRiskExitRow = {
  stockCode: string;
  stockName: string;
  status: "triggered" | "watch";
  latestClose: string;
  exitWatchPrice: string;
  reason: string;
};
```

### 必需函数

```ts
export function buildMarketStateCard(payload: LivermoreStrategyPayload): StockMarketStateCard;
export function buildSectorRows(payload: LivermoreStrategyPayload): StockSectorRow[];
export function buildCandidateEvidenceCards(payload: LivermoreStrategyPayload): StockCandidateEvidenceCard[];
export function buildRiskExitRows(payload: LivermoreStrategyPayload, confluence?: LivermoreSignalConfluencePayload | null): StockRiskExitRow[];
export function buildDataBoundaryNotes(payload: LivermoreStrategyPayload): string[];
```

### 业务口径

候选股证据从现有字段派生：

- `sector_rank` -> `行业排名第 X`
- `close` / `breakout_level` -> `收盘价突破观察位`
- `ma20` / `ma60` / `ma120` -> `均线结构`
- `close_strength` -> `收盘强度`
- `abnormal_turnover` -> `换手放大`
- `ema10` -> `10EMA 失效观察`

反证 / 待补证据必须包含：

- `基本面与估值证据未接入，不参与当前候选排序。`
- `新闻、公告、财报事件尚未进入候选卡。`

失效条件至少包含：

- `收盘跌破 10EMA 或突破位后需降级复核。`
- `所属行业强度跌出前列需重新复核。`
- `数据质量为 stale / missing 时不得继续解释为有效观察。`

### 测试建议

`StockAnalysisPageModel.test.ts` 用最小 mock payload，不必依赖完整 ApiClient。

断言：

```ts
expect(buildMarketStateCard(payload).title).toBe("市场状态");
expect(buildSectorRows(payload)[0].sectorName).toBe("AI");
expect(buildCandidateEvidenceCards(payload)[0].evidence.join(" ")).toContain("行业排名");
expect(buildCandidateEvidenceCards(payload)[0].counterEvidence.join(" ")).toContain("基本面与估值证据未接入");
expect(buildCandidateEvidenceCards(payload)[0].invalidationRules.join(" ")).toContain("10EMA");
```

### 验证命令

```bash
cd frontend && npm run test -- src/test/StockAnalysisPageModel.test.ts --pool=forks --poolOptions.forks.singleFork=true
```

---

## Task 4: 完整渲染股票分析页面

### 目标

`StockAnalysisPage` 真实调用 ApiClient 读接口并展示 P0 五块内容。

### 修改文件

- `frontend/src/features/stock-analysis/pages/StockAnalysisPage.tsx`
- `frontend/src/features/stock-analysis/pages/StockAnalysisPage.css`
- `frontend/src/test/StockAnalysisPage.test.tsx`

### 数据读取

页面中：

1. `const client = useApiClient();`
2. `useQuery` 调用 `client.getLivermoreStrategy()`。
3. 拿到 `strategy.result.as_of_date` 后，再调用 `client.getLivermoreSignalConfluence({ asOfDate })`。
4. confluence 失败不能导致整个页面失败；应显示“联动观察暂不可用”。

### 页面结构

必须包含：

```tsx
<h1>股票分析</h1>
<section>市场状态</section>
<section>行业强弱</section>
<section>候选股证据卡</section>
<section>风险退出观察</section>
<section>银行股专题待补证据</section>
<section>数据口径与边界</section>
```

### 展示要求

#### 市场状态

显示：

- `market_gate.state`
- exposure 百分比
- passed / required conditions
- 每个 condition 的 label / status / evidence

#### 行业强弱

显示 sector rank rows：

- rank
- sector name
- score
- pct change
- turnover
- amplitude
- constituent count

无数据时显示：

`当前行业强弱不可用，请检查 Choice 股票目录和当日股票落地覆盖。`

#### 候选股证据卡

每张卡显示：

- stock code / name
- sector
- headline
- 入选证据
- 反证 / 待补证据
- 失效条件

措辞必须是：

- `观察`
- `候选`
- `复核`
- `失效条件`

不要出现：

- `买入建议`
- `卖出建议`
- `下单`
- `调仓指令`

#### 风险退出观察

显示：

- risk_exit items
- risk_exit watch_items
- confluence exit observations if available

标签用：

- `触发复核`
- `观察中`
- `退出观察价`

不要用“卖出价”。

#### 银行股专题待补证据

固定面板：

```text
银行股专题待补证据
PB / ROE / 分红率 / NIM / 不良率 / 拨备覆盖率 / 资本充足率 / 金融市场业务收益敏感性
当前仅展示待补字段，不参与候选排序；后续接入正式或可追溯数据后再进入证据卡。
```

#### 数据口径与边界

显示：

- basis
- formula_version / rule_version if available
- diagnostics
- data_gaps
- supported_outputs
- unsupported_outputs
- result_meta quality_flag / vendor_status / source_version / tables_used if envelope includes meta

### 测试要求

`StockAnalysisPage.test.tsx` 至少覆盖：

1. 正常渲染五大区块。
2. mock payload 中候选股显示证据、反证和失效条件。
3. 基本面 / 银行股证据显示待补，不参与排序。
4. 页面文案不出现 `买入建议` / `卖出建议` / `下单`。
5. strategy API 失败时显示错误态。
6. no candidates 时显示空态。

### 验证命令

```bash
cd frontend && npm run test -- src/test/StockAnalysisPage.test.tsx --pool=forks --poolOptions.forks.singleFork=true
```

---

## Task 5: 页面样式与 debt guardrail

### 目标

股票页可读、紧凑、业务优先，不增加重复 inline style 债务。

### 要求

1. 页面样式放到 `StockAnalysisPage.css`。
2. 不要在 TSX 中堆大量重复 `style={{ ... }}`。
3. 卡片 class 命名统一前缀：`stock-analysis-page__...`。
4. 首屏顺序必须是：结论/状态先，表格/证据后。

### 验证命令

```bash
cd frontend && npm run debt:audit
```

---

## Task 6: 最终回归验证

执行：

```bash
cd frontend && npm run test -- src/test/StockAnalysisPageModel.test.ts src/test/StockAnalysisPage.test.tsx src/test/RouteRegistry.test.tsx src/test/WorkbenchShell.test.tsx --pool=forks --poolOptions.forks.singleFork=true
cd frontend && npm run typecheck
cd frontend && npm run debt:audit
```

后端回归优先运行：

```bash
uv run --project backend python -m pytest tests/test_choice_stock_adapter.py tests/test_market_data_livermore_api.py tests/test_livermore_stock_candidates.py tests/test_livermore_sector_rank.py tests/test_livermore_risk_exit.py -q
```

如果某个测试文件不存在，先用：

```bash
python3 - <<'PY'
from pathlib import Path
for p in Path('tests').glob('*livermore*'):
    print(p)
for p in Path('tests').glob('*choice_stock*'):
    print(p)
PY
```

然后运行存在的最接近测试。不要静默跳过。

---

## 6. Codex 执行方式建议

从仓库根目录运行：

```bash
cd /mnt/f/MOSS-V3
codex exec --full-auto "Read docs/handoff/2026-05-06-stock-analysis-workbench-codex.md and implement the P0 stock-analysis workbench exactly as specified. Keep changes narrow. Do not touch unrelated dirty files. Run the listed targeted frontend checks, typecheck, debt audit, and closest existing backend Livermore/choice_stock regressions. Report changed files and validation results."
```

如果 Codex 不在 relay-only profile 中运行，按用户环境偏好应使用单独 Codex relay profile / session，不要混用 openai-codex-auth session 的仅 model routing 变更。

---

## 7. 完成后汇报格式

Codex 完成后，请输出：

```text
Implemented P0 stock-analysis workbench.

Changed files:
- ...

What changed:
- ...

Validation:
- command -> result
- command -> result

Known risks / follow-up:
- ...
```

不要把 unrelated dirty files 当成自己改动。

---

## 8. P1 后续，不在本轮做

P1 可以单独开任务：

1. Agent page_context 接入股票页。
2. 新闻 / 公告 / 财报事件证据接入。
3. 银行股专题 dashboard：PB / ROE / 分红 / NIM / 不良 / 资本。
4. Bayesian evidence update。
5. 候选股复盘：入选后 1D / 5D / 20D 表现、归因和错误类型。

P1 前不要把 P0 页面扩成“投顾系统”。P0 只是证据优先的研究观察工作台。
