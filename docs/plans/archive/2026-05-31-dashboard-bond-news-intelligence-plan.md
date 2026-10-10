# 首页债券信息新闻增强 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将经营驾驶舱首页外部信息收窄为债券信息、债券新闻、持仓相关债券事件，让首页优先回答“今天哪些债券信息影响组合判断”。

**Architecture:** 复用现有 `ChoiceNewsEvents` 与首页 `dashboardHomeView`，新增一个债券新闻视图模型，把新闻事件按“持仓命中、发行/招标、评级/信用、市场利率、政策影响”分类。v1 不新增后端接口、不新增数据库、不伪造实时数据；只展示已有事件流和已接入债券/持仓数据能支撑的信息。

**Tech Stack:** React, TypeScript, TanStack Query, Vitest, CSS Modules, existing `ApiClient.getChoiceNewsEvents`.

---

## Product Shape

### 首页主模块：债券信息新闻

替代泛化的“外部情报雷达”，首页只做债券相关信息。模块建议放在现有 `重大信息发布日期前瞻 / 国内外宏观新闻` 附近，标题为：

`债券信息新闻`

模块内分三栏或三组紧凑卡片：

1. **持仓命中**
   - 展示和当前组合持仓、增减仓券、发行人、行业敞口直接相关的新闻。
   - 每条显示：标题、命中对象、专题来源、时间、来源状态。
   - 命中规则必须可解释，例如：`命中持仓：25山东债06`、`命中发行人：民生银行`。
   - 无命中时显示小胶囊：`持仓命中：当前无相关新闻`。

2. **债券市场**
   - 展示债券市场新闻：利率债、信用债、同业存单、地方债、政金债、债市交易、收益率、资金面等。
   - 每条显示：新闻标题、债券主题标签、时间。
   - 重点不是宏观泛新闻，而是能解释债券价格、收益率、久期、信用利差变化的信息。

3. **发行/招标/评级**
   - 展示国债、地方债、政金债、信用债发行与招标结果、评级调整、信用事件。
   - 发行/招标若暂无结构化数据，就只显示已有研究日历里的 `供给/招标` 小提示，不制造结果。
   - 评级/信用事件只在标题或正文明确出现评级、违约、展期、兑付、票息、发行失败等关键词时展示。

### 首页弱化项

- `宏观新闻` 不作为首页主信息流；只保留对债券定价有直接解释力的政策/资金面/利率新闻。
- `宏观数据 Surprise` 不进入首页 v1，可放到宏观专题页或后续版本。
- 全球风险温度、美股、油价等不直接上首页，除非新闻明确影响债券/利率/汇率。

---

## Data Policy

- 不新增后端接口、数据库表、调度器或缓存。
- 不把泛新闻直接塞进首页；必须通过债券关键词、持仓关键词或债券主题分类。
- 不用 LLM 在前端判断风险。
- 不从标题里猜评级结果或招标结果；没有明确结构化内容就只显示新闻原文标题。
- 每条新闻必须保留来源专题和 `received_at`。
- 每个子模块必须显示：`来源`、`数据截至`、`来源状态`、`刷新方式`。

---

## Topic Scope

### v1 可复用专题

在 `ChoiceNewsEvents` 里优先复用已有或 mock 中已出现的主题：

- `tushare.news`：市场快讯
- `tushare.major`：重大新闻
- `tushare.npr`：政策要闻
- `tushare.research`：研究观点
- `S888010007API`：经济数据，仅用于资金面/利率解释
- `C000003006`：政策跟踪，仅用于债券政策/央行/财政相关
- `C000003002`：央行动态，仅用于资金面/货币政策

### 债券关键词

债券主题关键词建议内置在前端 adapter 中，v1 不做配置表：

```ts
const BOND_NEWS_KEYWORDS = [
  "债券",
  "债市",
  "利率债",
  "信用债",
  "同业存单",
  "国债",
  "地方债",
  "政金债",
  "国开债",
  "收益率",
  "久期",
  "信用利差",
  "评级",
  "违约",
  "展期",
  "兑付",
  "发行",
  "招标",
  "票面利率",
  "中标利率",
  "全场倍数",
  "边际倍数",
  "逆回购",
  "MLF",
  "DR007",
  "R007",
  "Shibor",
];
```

---

## Task 1: Add Bond News Topic Query Coverage

**Files:**
- Modify: `frontend/src/features/workbench/dashboard/dashboardMacroNewsTopics.ts`
- Modify: `frontend/src/features/workbench/dashboard/hooks/useDashboardData.ts`
- Test: `frontend/src/test/DashboardHomePage.test.tsx`

**Step 1: Write failing integration test**

Extend the homepage news query test to expect bond-news topic coverage:

```ts
const topicCodes = getChoiceNewsEvents.mock.calls.map(([options]) => options.topicCode);
expect(topicCodes).toEqual(
  expect.arrayContaining([
    "tushare.news",
    "tushare.major",
    "tushare.npr",
    "tushare.research",
  ]),
);
```

Run:

```bash
npm run test -- src/test/DashboardHomePage.test.tsx
```

Expected: FAIL because bond-news topics are not queried yet.

**Step 2: Add topic config**

Add:

```ts
export const DASHBOARD_BOND_NEWS_TOPIC_LIMIT = 8;

export const DASHBOARD_BOND_NEWS_TOPICS = [
  { code: "tushare.news", label: "市场快讯" },
  { code: "tushare.major", label: "重大新闻" },
  { code: "tushare.npr", label: "政策要闻" },
  { code: "tushare.research", label: "研究观点" },
] as const;
```

Merge these labels into the existing topic-label map so `dashboardMacroNewsTopicLabel` can label both macro and bond topics.

**Step 3: Query bond topics**

In `useDashboardData.ts`, add:

```ts
const bondNewsQueries = useQueries({
  queries: DASHBOARD_BOND_NEWS_TOPICS.map((topic) => ({
    queryKey: ["dashboard", "bond-news", dataClient.mode, topic.code],
    queryFn: () =>
      dataClient.getChoiceNewsEvents({
        limit: DASHBOARD_BOND_NEWS_TOPIC_LIMIT,
        offset: 0,
        topicCode: topic.code,
      }),
    retry: false,
    staleTime: 60_000,
  })),
});
```

Return `bondNewsQueries`.

---

## Task 2: Build Bond News View Model

**Files:**
- Create: `frontend/src/features/workbench/dashboard-home/adapters/buildHomeBondNewsModel.ts`
- Modify: `frontend/src/features/workbench/dashboard-home/dashboardHomeView.ts`
- Test: `frontend/src/features/workbench/dashboard-home/dashboardHomeView.test.ts`

**Step 1: Write failing model tests**

Add tests for:

1. News title matching a held bond name goes to `holdingHits`.
2. News title matching a bond code goes to `holdingHits`.
3. Bond market keyword news goes to `marketNews`.
4. Rating/default/issuance keyword news goes to `creditAndIssuanceNews`.
5. Duplicate titles are removed.
6. Latest event older than 7 days returns `来源状态：偏旧`.

Example:

```ts
expect(view.bondNews.holdingHits[0]).toMatchObject({
  title: "25山东债06 成交活跃",
  hitLabel: "命中持仓：25山东债06",
  sourceLabel: "市场快讯",
});
expect(view.bondNews.marketNews[0].topicLabel).toBe("债券市场");
expect(view.bondNews.creditAndIssuanceNews[0].topicLabel).toBe("发行/评级");
```

Run:

```bash
npm run test -- src/features/workbench/dashboard-home/dashboardHomeView.test.ts
```

Expected: FAIL because `view.bondNews` does not exist.

**Step 2: Add model types**

```ts
export type HomeBondNewsItem = {
  id: string;
  title: string;
  timeLabel: string;
  sourceLabel: string;
  topicLabel: string;
  hitLabel: string | null;
};

export type HomeBondNewsModel = {
  holdingHits: readonly HomeBondNewsItem[];
  marketNews: readonly HomeBondNewsItem[];
  creditAndIssuanceNews: readonly HomeBondNewsItem[];
  holdingMessage: string | null;
  marketMessage: string | null;
  creditMessage: string | null;
  sourceLabel: string;
  asOfLabel: string;
  statusLabel: string;
  refreshLabel: string;
};
```

**Step 3: Build match candidates**

Candidate sources:

- `topHoldings`: instrument code and instrument name.
- `positionChanges`: instrument code and instrument name.
- `industryDistribution`: industry labels only as weak keywords.

Rules:

- Exact substring match only.
- Codes can match as-is.
- Names shorter than 3 chars are ignored.
- Stop after first strongest hit.
- Strongest order: bond code > bond name > issuer/name > industry.

**Step 4: Categorize news**

Classification:

- `holdingHits`: any title/body contains a holding candidate.
- `creditAndIssuanceNews`: contains rating/default/issuance keywords.
- `marketNews`: contains bond market/rate/funding keywords.

Limits:

- `holdingHits`: 4
- `marketNews`: 5
- `creditAndIssuanceNews`: 4

Empty states:

```ts
holdingMessage: "持仓命中：当前无相关新闻";
marketMessage: "债券市场：暂无相关新闻";
creditMessage: "发行/评级：暂无相关新闻";
```

---

## Task 3: Render Bond News Module

**Files:**
- Create: `frontend/src/features/workbench/dashboard-home/sections/BondNewsSection.tsx`
- Modify: `frontend/src/features/workbench/dashboard-home/TerminalHomeContent.tsx`
- Modify: `frontend/src/features/workbench/dashboard-home/dashboardHome.module.css`
- Test: `frontend/src/features/workbench/dashboard-home/sections/BondNewsSection.test.tsx`

**Step 1: Write failing component test**

Render a fixture and assert:

```ts
expect(screen.getByText("债券信息新闻")).toBeInTheDocument();
expect(screen.getByText("持仓命中")).toBeInTheDocument();
expect(screen.getByText("债券市场")).toBeInTheDocument();
expect(screen.getByText("发行/评级")).toBeInTheDocument();
expect(screen.getByText("来源：Choice / Tushare 债券新闻")).toBeInTheDocument();
expect(screen.getByText("数据截至 04-21 15:06")).toBeInTheDocument();
```

Run:

```bash
npm run test -- src/features/workbench/dashboard-home/sections/BondNewsSection.test.tsx
```

Expected: FAIL because component does not exist.

**Step 2: Implement component**

Layout:

- One card title: `债券信息新闻`
- Credibility strip under title.
- Three compact columns:
  - `持仓命中`
  - `债券市场`
  - `发行/评级`

Each item:

```tsx
<span>{item.topicLabel}</span>
<strong>{item.title}</strong>
<small>{item.hitLabel ?? item.sourceLabel} · {item.timeLabel}</small>
```

**Step 3: Place on homepage**

In `TerminalHomeContent.tsx`, place:

```tsx
<BondNewsSection bondNews={view.bondNews} />
```

Recommended placement:

- After top holdings / risk exposure area.
- Before research reports.

Reason: bond news should explain portfolio and risk before the user reaches reports.

---

## Task 4: Keep Macro News Secondary

**Files:**
- Modify: `frontend/src/features/workbench/dashboard-home/sections/ResearchCalendarSection.tsx`
- Modify: `frontend/src/features/workbench/dashboard-home/adapters/buildHomeMacroBriefingModel.ts`
- Test: `frontend/src/features/workbench/dashboard-home/sections/ResearchCalendarSection.test.tsx`

**Step 1: Rename macro/news positioning**

Keep `重大信息发布日期前瞻`, but change the right pane emphasis:

- From: `国内外宏观新闻`
- To: `政策与资金面`

Only show news that is bond-relevant by keyword:

- 央行
- 逆回购
- MLF
- DR007
- Shibor
- 国债收益率
- 地方债
- 财政
- 货币政策

If no match:

```text
政策与资金面：暂无债券相关更新
```

**Step 2: Keep credibility strip**

Do not remove the existing `来源 / 数据截至 / 来源状态 / 刷新` strip.

---

## Task 5: Validation

Run in order:

```bash
npm run test -- src/features/workbench/dashboard-home/dashboardHomeView.test.ts src/features/workbench/dashboard-home/sections/BondNewsSection.test.tsx src/features/workbench/dashboard-home/sections/ResearchCalendarSection.test.tsx src/test/DashboardHomePage.test.tsx
npx eslint src/features/workbench/dashboard-home/adapters/buildHomeBondNewsModel.ts src/features/workbench/dashboard-home/sections/BondNewsSection.tsx src/features/workbench/dashboard-home/TerminalHomeContent.tsx src/features/workbench/dashboard-home/dashboardHomeView.ts src/test/DashboardHomePage.test.tsx
npm run typecheck
npm run debt:audit
```

Browser check at `http://localhost:5888/`:

- Shows `债券信息新闻`.
- Shows `持仓命中 / 债券市场 / 发行/评级`.
- Empty states are compact and do not create large blank space.
- Every news module shows `来源 / 数据截至 / 来源状态 / 刷新`.
- Existing `重大信息发布日期前瞻` still renders.
- 首页不出现泛化的“外部情报雷达”。
- No console errors.

Full `npm run lint` and `npm run build` should be attempted, but current unrelated BalanceAnalysis errors may still block them. Do not fix BalanceAnalysis as part of this plan unless explicitly requested.

---

## Scope Guardrails

- Do not change backend routes.
- Do not change database schema.
- Do not add dependencies.
- Do not add generic external intelligence modules to the homepage.
- Do not show stock/general macro/commodity news unless directly bond-relevant.
- Do not use LLM summaries in frontend.
- Do not infer rating or default status when the source text does not explicitly say it.

---

## Recommended Delivery Order

1. Add bond-news topic queries.
2. Build deterministic bond-news view model.
3. Render `债券信息新闻` module.
4. Filter existing macro pane down to `政策与资金面`.
5. Verify visible homepage and targeted tests.
