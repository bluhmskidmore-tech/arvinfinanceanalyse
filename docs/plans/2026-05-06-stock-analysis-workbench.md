# MOSS-V3 股票分析工作台 Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 把现有 Livermore A股趋势观察能力，收口成一个独立、可见、证据优先、只读的“股票分析工作台”。

**Architecture:** 第一阶段不新建交易/写入能力，不改 DuckDB 写边界。前端新建 `/stock-analysis` 页面复用现有 `getLivermoreStrategy` / `getLivermoreSignalConfluence` 读接口；后端只在必要时补充只读派生字段。现有 CrossAsset 页面继续保留，股票页作为更清晰的业务入口。

**Tech Stack:** React + TypeScript + TanStack Query frontend; FastAPI backend; existing Livermore market-data services; Vitest / frontend typecheck / debt audit; pytest for backend regression.

---

## Boundary

Do not do in P0:
- 不新增自动交易、买卖建议、下单、调仓写操作。
- 不新增任意 SQL 或绕过 service/repository 的数据口。
- 不改 Choice/Tushare 权限与凭据。
- 不重构 `marketDataClient.ts` 大结构。
- 不把股票分析标成正式投资建议；统一写成“观察 / 复核 / 证据”。

P0 success means:
- 用户能从市场工作台看到“股票分析”入口。
- `/stock-analysis` 首屏回答：市场状态、行业强弱、候选股、风险退出、数据新鲜度。
- 候选股显示“为什么入选 / 反证 / 失效条件”。如果后端暂未提供，前端先从现有字段派生展示说明。

---

## Task 1: Add stock-analysis navigation entry

**Objective:** 在市场工作台中暴露独立股票分析入口。

**Files:**
- Modify: `frontend/src/mocks/navigation.ts`
- Test: `frontend/src/test/WorkbenchShell.test.tsx`

**Step 1: Add failing navigation test**

In `WorkbenchShell.test.tsx`, add/adjust a test to expect market subnav contains `/stock-analysis` and label `股票分析` when rendering `/cross-asset` or `/stock-analysis`.

Expected assertion shape:
```ts
const subnav = await screen.findByTestId("workbench-section-subnav");
const hrefs = within(subnav).getAllByRole("link").map((link) => link.getAttribute("href"));
expect(hrefs).toEqual(expect.arrayContaining(["/stock-analysis"]));
expect(subnav).toHaveTextContent("股票分析");
```

**Step 2: Run RED**

```bash
cd frontend && npm run test -- src/test/WorkbenchShell.test.tsx --testNamePattern='cross-asset|stock|市场' --pool=forks --poolOptions.forks.singleFork=true
```

Expected: FAIL because `/stock-analysis` is not in navigation.

**Step 3: Implement navigation**

In `frontend/src/mocks/navigation.ts`:
- add `"stock-analysis": "market"` to `workbenchSectionGroups`.
- add a new `workbenchNavigation` item near `market-data` / `cross-asset`:
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

**Step 4: Run GREEN**

Same command as Step 2. Expected: PASS.

---

## Task 2: Add route shell for `/stock-analysis`

**Objective:** 让 `/stock-analysis` 渲染一个独立页面，而不是 placeholder。

**Files:**
- Create: `frontend/src/features/stock-analysis/pages/StockAnalysisPage.tsx`
- Create: `frontend/src/features/stock-analysis/pages/StockAnalysisPage.css`
- Modify: `frontend/src/router/routes.tsx`
- Test: `frontend/src/test/RouteRegistry.test.tsx`

**Step 1: Add failing route test**

In `RouteRegistry.test.tsx`, mock the new page if needed and assert route renders:
```ts
vi.mock("../features/stock-analysis/pages/StockAnalysisPage", () => ({
  default: () => (
    <section data-testid="stock-analysis-page">
      <h1>股票分析</h1>
    </section>
  ),
}));

it("renders the stock-analysis route", async () => {
  renderWorkbenchApp(["/stock-analysis"], { client: mockClient });
  expect(await screen.findByTestId("stock-analysis-page")).toBeInTheDocument();
  expect(await screen.findByRole("heading", { name: "股票分析" })).toBeInTheDocument();
});
```

**Step 2: Run RED**

```bash
cd frontend && npm run test -- src/test/RouteRegistry.test.tsx --testNamePattern='stock-analysis' --pool=forks --poolOptions.forks.singleFork=true
```

Expected: FAIL because route/page does not exist.

**Step 3: Create minimal page**

`frontend/src/features/stock-analysis/pages/StockAnalysisPage.tsx`:
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

`frontend/src/features/stock-analysis/pages/StockAnalysisPage.css`:
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

**Step 4: Wire route**

In `frontend/src/router/routes.tsx`:
- add lazy import:
```ts
const StockAnalysisPage = lazy(
  () => import("../features/stock-analysis/pages/StockAnalysisPage"),
);
```
- in `buildWorkbenchChildRoutes()`, add:
```ts
if (section.path === "/stock-analysis") {
  return {
    path: section.path.slice(1),
    element: routeElement(<StockAnalysisPage />),
  };
}
```

**Step 5: Run GREEN**

```bash
cd frontend && npm run test -- src/test/RouteRegistry.test.tsx --testNamePattern='stock-analysis' --pool=forks --poolOptions.forks.singleFork=true
```

Expected: PASS.

---

## Task 3: Build frontend view-model helpers

**Objective:** 把现有 Livermore payload 转成股票页首屏所需的业务展示模型。

**Files:**
- Create: `frontend/src/features/stock-analysis/lib/stockAnalysisPageModel.ts`
- Test: `frontend/src/test/StockAnalysisPageModel.test.ts`

**Step 1: Add failing model tests**

Test these helpers:
- `buildMarketStateCard(payload)` returns state, exposure label, condition summary.
- `buildSectorRows(payload)` returns sector rows sorted by rank.
- `buildCandidateEvidenceCards(payload)` returns each candidate with evidence, counterEvidence, invalidationRules.
- `buildRiskExitRows(payload)` returns watch/trigger rows from risk_exit.

Example assertions:
```ts
expect(card.title).toBe("市场状态");
expect(card.state).toBe("WARM");
expect(cards[0].evidence.join(" ")).toContain("行业排名");
expect(cards[0].invalidationRules.join(" ")).toContain("10EMA");
```

**Step 2: Run RED**

```bash
cd frontend && npm run test -- src/test/StockAnalysisPageModel.test.ts --pool=forks --poolOptions.forks.singleFork=true
```

Expected: FAIL because file/helpers do not exist.

**Step 3: Implement helpers**

Create `stockAnalysisPageModel.ts` with pure functions only. No React. No fetch. Inputs are existing `LivermoreStrategyPayload` / `LivermoreSignalConfluencePayload` types.

Minimum output types:
```ts
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
```

Candidate evidence should be derived from existing fields:
- `sector_rank` -> 行业排名
- `close` / `breakout_level` -> 突破证据
- `ma20/ma60/ma120` -> 均线结构
- `close_strength` -> 收盘强度
- `abnormal_turnover` -> 换手证据
- `ema10` -> 10EMA 失效观察

**Step 4: Run GREEN**

Same command as Step 2. Expected: PASS.

---

## Task 4: Render P0 stock-analysis page sections

**Objective:** 页面首屏展示“市场状态 -> 行业 -> 个股候选 -> 风险 -> 数据口径”。

**Files:**
- Modify: `frontend/src/features/stock-analysis/pages/StockAnalysisPage.tsx`
- Modify: `frontend/src/features/stock-analysis/pages/StockAnalysisPage.css`
- Test: `frontend/src/test/StockAnalysisPage.test.tsx`

**Step 1: Add failing page test**

Render page with mock ApiClient and assert:
- `股票分析`
- `市场状态`
- `行业强弱`
- `候选股证据卡`
- `风险退出观察`
- `数据口径与边界`
- A candidate stock code/name from mock payload.

**Step 2: Run RED**

```bash
cd frontend && npm run test -- src/test/StockAnalysisPage.test.tsx --pool=forks --poolOptions.forks.singleFork=true
```

Expected: FAIL because sections are not implemented.

**Step 3: Implement queries**

In `StockAnalysisPage.tsx`:
- use `useApiClient()`
- use `useQuery` for `client.getLivermoreStrategy()`
- after strategy resolves with `as_of_date`, use `client.getLivermoreSignalConfluence({ asOfDate })`
- render loading / error / empty states explicitly.

**Step 4: Render sections**

Sections:
1. `市场状态`
2. `行业强弱`
3. `候选股证据卡`
4. `风险退出观察`
5. `数据口径与边界`

All candidate/action wording must use:
- `观察`
- `复核`
- `失效条件`

Do not use:
- `买入`
- `卖出`
- `交易指令`

If backend field name includes `buy_trigger_price`, frontend label should be `观察触发价` / `入场观察价`, not `买入价`.

**Step 5: Run GREEN**

Same command as Step 2. Expected: PASS.

---

## Task 5: Add optional bank-stock evidence placeholder panel

**Objective:** 为用户最关心的银行股研究留出清晰入口，但不伪造数据。

**Files:**
- Modify: `frontend/src/features/stock-analysis/pages/StockAnalysisPage.tsx`
- Test: `frontend/src/test/StockAnalysisPage.test.tsx`

**Step 1: Add failing test**

Assert page contains:
- `银行股专题待补证据`
- `PB / ROE / 分红率 / NIM / 不良率 / 资本充足率`
- `当前仅展示待补字段，不参与候选排序`

**Step 2: Implement static placeholder panel**

Add a panel below candidate cards:
```tsx
<section className="stock-analysis-page__panel">
  <h2>银行股专题待补证据</h2>
  <p>当前 P0 不伪造银行基本面数据；后续接入 PB / ROE / 分红率 / NIM / 不良率 / 资本充足率后，再进入候选证据卡。</p>
</section>
```

**Step 3: Run test**

```bash
cd frontend && npm run test -- src/test/StockAnalysisPage.test.tsx --pool=forks --poolOptions.forks.singleFork=true
```

Expected: PASS.

---

## Task 6: Add backend-only optional candidate explanation endpoint? Defer unless needed

**Objective:** 明确 P0 不强行加后端，避免范围扩大。

Do not implement a new backend endpoint in P0 unless frontend cannot derive explanation from existing payload.

If later required, add only a read-only endpoint:
- `GET /ui/market-data/livermore/stock-analysis`
- service wraps `livermore_strategy_envelope` and adds explanation strings.

But preferred P0 is frontend view-model only.

---

## Task 7: Validation suite

**Objective:** 完成最小可交付验证。

Run:
```bash
cd frontend && npm run test -- src/test/StockAnalysisPageModel.test.ts src/test/StockAnalysisPage.test.tsx src/test/RouteRegistry.test.tsx src/test/WorkbenchShell.test.tsx --pool=forks --poolOptions.forks.singleFork=true
cd frontend && npm run typecheck
cd frontend && npm run debt:audit
uv run --project backend python -m pytest tests/test_choice_stock_adapter.py tests/test_market_data_livermore_api.py tests/test_livermore_stock_candidates.py tests/test_livermore_sector_rank.py tests/test_livermore_risk_exit.py -q
```

If a backend test path does not exist, search the existing Livermore test names and run the closest current files. Do not silently skip.

---

## P1 Follow-up Plan

After P0 page lands:
1. Add `stock_analysis` Agent page_context.
2. Add news/announcement evidence rows.
3. Add valuation/basic-factor table, especially bank-stock fields.
4. Add Bayesian evidence update model.
5. Add candidate tracking and post-selection attribution.

Recommended next data model for P1:
```ts
export type StockEvidenceUpdate = {
  stock_code: string;
  as_of_date: string;
  prior_view: "positive" | "neutral" | "negative" | "unknown";
  evidence_type: "price" | "sector" | "fundamental" | "valuation" | "news" | "risk";
  direction: "support" | "against" | "neutral";
  summary: string;
  source: string;
  confidence: number;
};
```

---

## Final Acceptance Criteria

- `/stock-analysis` route opens.
- Market workbench navigation exposes `股票分析`.
- Page shows market state, sector rank, candidate evidence, risk exit, and data boundary.
- All wording is observation/research only.
- Missing fundamentals are visible as missing, not mocked as facts.
- Frontend targeted tests pass.
- Typecheck and debt audit pass.
- Backend Livermore regression remains green.
