# Market Data Visual Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `/market-data` 在不改变任何数据、筛选、日期、来源状态或业务文案的前提下，统一两处分区标题并消除四类同表面重复外框。

**Architecture:** 保留 `PageDecisionHero`、`DataStatusStrip`、现有 KPI 带和所有专用业务组件。页面 TSX 只做两处 `SectionHead` 迁移及 Hero 状态条的结构性上移；页面 CSS 只收窄现有宽泛选择器和补充局部容器样式，不改共享原语或全局主题。

**Tech Stack:** React 18、TypeScript、Ant Design、CSS Modules 共享布局原语、Vitest/Testing Library、Playwright、GitNexus CLI。

---

## 文件边界

生产代码只修改：

- `frontend/src/features/market-data/pages/MarketDataPage.tsx`：迁移两处分区标题，移动 Hero 状态条，不改变其内容和测试锚点。
- `frontend/src/features/market-data/pages/MarketDataPage.css`：删除已退役标题结构的耦合样式，收窄四类重复外框选择器。

验证代码只修改或新增：

- `frontend/src/test/MarketDataPage.test.tsx`：锁定 `SectionHead`、可访问区域和 Hero 单一状态面的 DOM 契约。
- `frontend/tests/playwright/market-data-layout-primitives.spec.mjs`：锁定计算样式、首屏高度基线和 768/390 像素无横向溢出。

不修改 `frontend/src/components/layout/*`、`frontend/src/components/page/*`、`frontend/src/styles/workbenchShell.css`、API、查询 Hook、页面模型、专用图表表格以及当前已有改动的两个市场数据 Playwright 烟测文件。

### Task 0: 刷新影响索引并确认调用面

**Files:**

- Inspect: `.gitnexus/meta.json`
- Inspect: `frontend/src/features/market-data/pages/MarketDataPage.tsx`

- [ ] **Step 1: 核对 GitNexus 索引与当前提交**

Run from repository root:

```powershell
git rev-parse HEAD
node -e "const fs=require('fs');const m=JSON.parse(fs.readFileSync('.gitnexus/meta.json','utf8'));console.log(m.lastCommit)"
```

Expected: 两个提交号不同，证明索引需要刷新；若已经相同，直接进入 Step 3。

- [ ] **Step 2: 用项目规定参数刷新索引**

```powershell
npx gitnexus analyze --skip-agents-md
```

Expected: exit 0，索引指向当前工作树 `F:\MOSS-V3`，且不会重写根指令文件。

- [ ] **Step 3: 查询三个将变化的本地符号**

```powershell
npx gitnexus impact MarketDataPage -d upstream --depth 3 --include-tests -r moss-v3-main-current-20260809
npx gitnexus impact MarketDataFormalRatesBoard -d upstream --depth 3 --include-tests -r moss-v3-main-current-20260809
npx gitnexus impact MarketSectionLead -d upstream --depth 3 --include-tests -r moss-v3-main-current-20260809
npx gitnexus query "market data page rendering explorer and terminal workflow" -r moss-v3-main-current-20260809 -l 5
```

Expected: 直接调用面局限在市场数据路由、当前页面内部和页面测试；若出现其他业务路由的直接调用者或 HIGH/CRITICAL 风险，停止编辑并先向用户报告。

- [ ] **Step 4: 记录本轮不变边界**

在执行记录中明确写下：不改变接口、查询参数、指标格式、`formal_use_allowed`、mixed-source、懒加载门槛、`details` 常驻 DOM、正式外汇首次展开挂载以及任何现有 `market-data-*` 锚点。

### Task 1: 用测试驱动迁移标题并收敛 Hero 状态结构

**Files:**

- Modify: `frontend/src/test/MarketDataPage.test.tsx:212`
- Modify: `frontend/src/features/market-data/pages/MarketDataPage.tsx:1-87, 517-529, 1140-1249, 1310-1318`

- [ ] **Step 1: 写入必然失败的 DOM 契约测试**

在 `renders the market data page as an institutional terminal cockpit` 用例之前加入：

```tsx
it("uses one hero status surface and shared section-head regions", async () => {
  renderPage(createApiClient({ mode: "mock" }));

  await screen.findByTestId("market-data-kpi-band");

  const hero = screen.getByTestId("market-data-hero");
  const status = screen.getByTestId("market-data-status-strip");
  expect(status.parentElement).toBe(hero);
  expect(hero.querySelector(".moss-page-v2-decision-hero__conclusion")).toBeNull();

  const formalRatesBoard = screen.getByTestId("market-data-formal-rates-board");
  const formalHead = within(formalRatesBoard).getByTestId("market-data-formal-rates-head");
  const formalTitle = within(formalHead).getByRole("heading", {
    level: 2,
    name: "01 正式利率",
  });
  expect(formalRatesBoard).toHaveAttribute("aria-labelledby", "market-data-formal-rates-title");
  expect(formalTitle).toHaveAttribute("id", "market-data-formal-rates-title");
  expect(formalHead).toHaveAttribute("data-numbered", "false");
  expect(within(formalHead).getByText("利率行情")).toBeInTheDocument();
  expect(within(formalHead).getByText("利率曲线与宏观深度")).toBeInTheDocument();
  expect(within(formalHead).getByRole("link", { name: "查看完整曲线" })).toHaveAttribute(
    "href",
    "#market-data-evidence-gate",
  );

  const liquiditySection = screen.getByRole("region", { name: "03 资金市场与存单" });
  const liquidityHead = within(liquiditySection).getByTestId("market-data-liquidity-head");
  const liquidityTitle = within(liquidityHead).getByRole("heading", {
    level: 2,
    name: "03 资金市场与存单",
  });
  expect(liquiditySection).toHaveAttribute("aria-labelledby", "market-data-liquidity-title");
  expect(liquidityTitle).toHaveAttribute("id", "market-data-liquidity-title");
  expect(liquidityHead).toHaveAttribute("data-numbered", "false");
  expect(within(liquidityHead).getByText("资金读数")).toBeInTheDocument();
  expect(
    within(liquidityHead).getByText(
      "DR007、回购与 Shibor 代理矩阵；正式口径摘要见右侧源门禁。",
    ),
  ).toBeInTheDocument();
});
```

- [ ] **Step 2: 运行测试并确认 RED**

Run from `frontend/`:

```powershell
npm run test -- MarketDataPage.test.tsx
```

Expected: FAIL。当前状态条的父节点是 `.moss-page-v2-decision-hero__conclusion`，且页面不存在 `market-data-formal-rates-head` 与 `market-data-liquidity-head` 两个共享标题锚点。

- [ ] **Step 3: 替换导入并删除退役辅助函数**

将 React 导入收窄为：

```tsx
import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
```

删除 `PageSectionLead`、`PageSectionLeadProps` 与 `designTokens` 导入，新增：

```tsx
import { SectionHead } from "../../../components/layout";
```

完整删除 `const s`、`marketDataSectionLeadStyle` 和 `MarketSectionLead`。这些符号只为旧 `PageSectionLead` 抵消上边距，`SectionHead` 自身没有这项旧边距。

- [ ] **Step 4: 用 SectionHead 替换正式利率区头**

将正式利率区块开头替换为：

```tsx
<section
  id="market-data-term-structure"
  className="market-data-formal-rates-board"
  data-testid="market-data-formal-rates-board"
  aria-labelledby="market-data-formal-rates-title"
>
  <div className="market-data-section-head-shell">
    <SectionHead
      category="利率行情"
      title="01 正式利率"
      note="利率曲线与宏观深度"
      actions={<a href="#market-data-evidence-gate">查看完整曲线</a>}
      numbered={false}
      contentGap="flush"
      titleId="market-data-formal-rates-title"
      testId="market-data-formal-rates-head"
    />
  </div>
```

其后的 `market-data-workbench-shared-meta`、正式利率表、曲线、走势图与关键期限指标原样保留。

- [ ] **Step 5: 把 DataStatusStrip 移成 Hero 的第一个内容子节点**

删除 `PageDecisionHero` 从 `conclusion={` 开始到对应闭合花括号结束的整个属性。在 `actions` 属性结束后的 Hero 内容区、ticker 空态之前插入：

```tsx
<DataStatusStrip testId="market-data-status-strip" className="market-data-hero-status">
  <span>{statusBadges.readinessVerdict}</span>
  {statusBadges.overviewReadinessLabel !== statusBadges.readinessVerdict ? (
    <>
      <span aria-hidden="true">·</span>
      <span>{statusBadges.overviewReadinessLabel}</span>
    </>
  ) : null}
  {formalUseBlocked ? (
    <>
      <span aria-hidden="true">·</span>
      <span className="market-data-hero-status-warn">{basisChipLabel}</span>
    </>
  ) : null}
  {refreshStatus ? (
    <>
      <span aria-hidden="true">·</span>
      <span className="market-data-hero-status-accent">{refreshStatus}</span>
    </>
  ) : null}
  {refreshError ? (
    <>
      <span aria-hidden="true">·</span>
      <span className="market-data-hero-status-danger">{refreshError}</span>
    </>
  ) : null}
</DataStatusStrip>
```

状态内容、顺序、颜色类和 `market-data-status-strip` 锚点逐字保持。

- [ ] **Step 6: 用语义化 section 和 SectionHead 替换资金区头**

将资金区外层与旧辅助标题替换为：

```tsx
<section
  className="market-data-lower-deck-section"
  aria-labelledby="market-data-liquidity-title"
>
  <div className="market-data-section-head-shell">
    <SectionHead
      category="资金读数"
      title="03 资金市场与存单"
      note="DR007、回购与 Shibor 代理矩阵；正式口径摘要见右侧源门禁。"
      numbered={false}
      contentGap="flush"
      titleId="market-data-liquidity-title"
      testId="market-data-liquidity-head"
    />
  </div>
```

把该区原来的闭合 `</div>` 对应改为 `</section>`；`MarketDataLiquidityDeck` 的全部 props 和子组件原样保留。

- [ ] **Step 7: 运行测试并确认 GREEN**

```powershell
npm run test -- MarketDataPage.test.tsx
```

Expected: `MarketDataPage.test.tsx` 全部通过，既有 KPI、正式口径、筛选、懒加载与治理锚点断言保持绿色。

- [ ] **Step 8: 仅提交本任务文件**

```powershell
git add -- frontend/src/test/MarketDataPage.test.tsx frontend/src/features/market-data/pages/MarketDataPage.tsx
git diff --cached --check
git commit --only -m "refactor: align market data section headers" -- frontend/src/test/MarketDataPage.test.tsx frontend/src/features/market-data/pages/MarketDataPage.tsx
```

Expected: 提交只包含上述两个文件；工作区其他改动仍保持原状态。

### Task 2: 用 Playwright 红绿测试压平四类重复外框

**Files:**

- Create: `frontend/tests/playwright/market-data-layout-primitives.spec.mjs`
- Modify: `frontend/src/features/market-data/pages/MarketDataPage.css:38-54, 403-428, 2347-2356, 2409-2434, 2814-2838, 3007-3126, 3639-3644, 3737-3792`

- [ ] **Step 1: 新建计算样式与响应式契约测试**

创建 `frontend/tests/playwright/market-data-layout-primitives.spec.mjs`：

```js
import { expect, test } from "@playwright/test";

const DESKTOP = { width: 1440, height: 900 };
const FIRST_SCREEN_STACK_MAX_HEIGHT = 1281;

async function openMarketData(page, viewport, suffix = "") {
  await page.setViewportSize(viewport);
  await page.goto(`/market-data${suffix}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("market-data-page")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("market-data-kpi-band")).toBeVisible({ timeout: 30_000 });
}

async function readSurface(locator) {
  return locator.evaluate((element) => {
    const style = getComputedStyle(element);
    return {
      borderTopWidth: style.borderTopWidth,
      borderLeftWidth: style.borderLeftWidth,
      backgroundColor: style.backgroundColor,
      boxShadow: style.boxShadow,
    };
  });
}

function expectNeutralSurface(surface, label) {
  expect(surface.borderTopWidth, `${label} should not draw an outer border`).toBe("0px");
  expect(surface.backgroundColor, `${label} should not draw another surface`).toBe(
    "rgba(0, 0, 0, 0)",
  );
  expect(surface.boxShadow, `${label} should not draw an outer shadow`).toBe("none");
}

function expectFramedSurface(surface, label) {
  expect(
    Number.parseFloat(surface.borderTopWidth),
    `${label} should retain a visible boundary`,
  ).toBeGreaterThan(0);
}

async function expectNoDocumentOverflow(page, label) {
  const widths = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(widths.scrollWidth, `${label} should not overflow horizontally`).toBeLessThanOrEqual(
    widths.clientWidth + 1,
  );
}

async function readBox(locator, label) {
  const box = await locator.boundingBox();
  expect(box, `${label} should have a bounding box`).not.toBeNull();
  return box;
}

test("removes known same-surface frames while retaining inner work areas", async ({ page }) => {
  await openMarketData(page, DESKTOP);

  const hero = page.getByTestId("market-data-hero");
  const status = page.getByTestId("market-data-status-strip");
  await expect(hero.locator(":scope > [data-testid='market-data-status-strip']")).toHaveCount(1);
  await expect(hero.locator(".moss-page-v2-decision-hero__conclusion")).toHaveCount(0);
  expect((await readSurface(status)).borderLeftWidth).toBe("3px");

  const extendedMount = page.locator('[data-lazy-mount="extended-terminal"]');
  await extendedMount.scrollIntoViewIfNeeded();
  const extendedOuter = page.getByTestId("market-data-extended-terminal-section");
  const extendedInner = page.getByTestId("market-data-extended-terminal-collapse");
  await expect(extendedOuter).toBeVisible({ timeout: 30_000 });
  expectNeutralSurface(await readSurface(extendedOuter), "extended terminal wrapper");
  expectFramedSurface(await readSurface(extendedInner), "extended terminal collapse");

  const tushareCollapse = page.getByTestId("market-data-tushare-collapse");
  await tushareCollapse.scrollIntoViewIfNeeded();
  await tushareCollapse.locator(".ant-collapse-header").first().click();
  const tushareWrapper = tushareCollapse.locator(
    ".ant-collapse-content-box > .market-data-lower-deck-section",
  );
  const tusharePanel = tushareCollapse.locator(".market-data-tushare-panel").first();
  await expect(tusharePanel).toBeVisible({ timeout: 30_000 });
  expectNeutralSurface(await readSurface(tushareWrapper), "Tushare content wrapper");
  expectFramedSurface(await readSurface(tusharePanel), "Tushare business panel");

  await openMarketData(page, DESKTOP, "?view=explorer");
  const explorer = page.getByTestId("market-data-explorer-view");
  const directory = explorer.locator(".market-data-explorer__directory").first();
  await expect(explorer).toBeVisible({ timeout: 30_000 });
  expectNeutralSurface(await readSurface(explorer), "series explorer root");
  expectFramedSurface(await readSurface(directory), "series explorer directory");
});

test("keeps the governed first-screen stack within the recorded mock baseline", async ({ page }) => {
  await openMarketData(page, DESKTOP);
  const heroBox = await readBox(page.getByTestId("market-data-hero"), "market data hero");
  const formalBox = await readBox(
    page.getByTestId("market-data-formal-rates-board"),
    "formal rates board",
  );
  expect(formalBox.y + formalBox.height - heroBox.y).toBeLessThanOrEqual(
    FIRST_SCREEN_STACK_MAX_HEIGHT,
  );
});

for (const viewport of [
  { width: 768, height: 1024 },
  { width: 390, height: 844 },
]) {
  test(`keeps ${viewport.width}px layout free of document overflow`, async ({ page }) => {
    await openMarketData(page, viewport);
    await expectNoDocumentOverflow(page, `${viewport.width}px market data page`);
  });
}
```

`1281` 来自改动前固定 mock 数据下的实测：Hero 顶部到正式利率板底部为 `1279.609375px`，只允许 1 像素舍入余量。

- [ ] **Step 2: 运行新测试并确认 RED**

Run from `frontend/`:

```powershell
$env:MOSS_PLAYWRIGHT_USE_WEB_SERVER="1"
$env:MOSS_PLAYWRIGHT_REUSE_SERVER="0"
npx playwright test -c playwright.config.mjs tests/playwright/market-data-layout-primitives.spec.mjs --workers=1
```

Expected: FAIL。扩展终端外层、Tushare 内容包裹和 Explorer 根节点当前都是 `1px` 边框与非透明背景；Hero 状态条在未补局部样式时左边框也是 `1px`。

- [ ] **Step 3: 增加 Hero 单一状态面与标题容器的局部样式**

在 Hero 状态颜色规则之后加入：

```css
.market-data-page__decision-hero-shell > .market-data-hero-status {
  border-color: var(--dh-api-line);
  border-left: 3px solid var(--dh-api-blue);
  border-radius: var(--dh-api-radius);
  background: var(--dh-api-panel-2);
}

.market-data-section-head-shell {
  padding: 13px 16px 0;
  background:
    linear-gradient(
      90deg,
      color-mix(in srgb, var(--market-data-card-accent, var(--imd-blue)) 7%, var(--dh-api-panel)),
      var(--dh-api-panel) 58%
    );
}

.market-data-section-head-shell a {
  color: var(--imd-blue);
  text-decoration: none;
  white-space: nowrap;
}

.market-data-section-head-shell a:hover {
  text-decoration: underline;
}
```

不要覆盖 `SectionHead` 内部标题字号、间距、颜色或 DOM；外层 shell 只给零 padding 的 L1 卡提供容器内距和现有渐变表面。

- [ ] **Step 4: 收窄真正的 L1 外框选择器**

把两处宽泛选择器都改为：

```css
.market-data-main > section:not(.market-data-explorer),
.market-data-main > div > section:not(.market-data-extended-terminal-section),
```

把以下三个裸 `.market-data-lower-deck-section` 根规则全部改成只命中资金区直接子节点：

```css
.market-data-main > .market-data-lower-deck-section {
```

对应位置是原文件约第 2348、2815 行以及约第 3119 行分组中的该选择器。这样资金区卡壳继续存在，Tushare Collapse 内容中的同名包裹恢复透明。

- [ ] **Step 5: 删除退役标题结构的 CSS 耦合**

从所有分组中删除 `.market-data-formal-rates-head`、`.market-data-section-lead--compact` 及其后代选择器；仅保留同组中仍在使用的 `.market-data-panel-head`、Collapse header、`.market-data-workbench-shared-meta`、`.market-data-fx-formal-head` 和 `.market-data-series-category-card__head`。删除完成后运行：

```powershell
rg -n "market-data-formal-rates-head|market-data-section-lead--compact" src/features/market-data/pages/MarketDataPage.css src/features/market-data/pages/MarketDataPage.tsx
```

Expected: 无输出。新的标题外层只剩 `.market-data-section-head-shell`，`SectionHead` 内部视觉由 CSS Module 自己负责。

- [ ] **Step 6: 运行新测试并确认 GREEN**

```powershell
npx playwright test -c playwright.config.mjs tests/playwright/market-data-layout-primitives.spec.mjs --workers=1
```

Expected: 4 tests passed；三个冗余外层为透明无边框，Hero 只剩一个 3 像素左强调状态面，内部 Collapse/Tushare/Explorer 工作区边界仍存在，1440 基线与 768/390 无溢出断言通过。

- [ ] **Step 7: 回归市场数据页单元测试**

```powershell
npm run test -- MarketDataPage.test.tsx
```

Expected: 全部通过。

- [ ] **Step 8: 仅提交本任务文件**

```powershell
git add -- frontend/src/features/market-data/pages/MarketDataPage.css frontend/tests/playwright/market-data-layout-primitives.spec.mjs
git diff --cached --check
git commit --only -m "style: flatten market data visual hierarchy" -- frontend/src/features/market-data/pages/MarketDataPage.css frontend/tests/playwright/market-data-layout-primitives.spec.mjs
```

Expected: 提交只包含 CSS 与新增 Playwright 测试。

### Task 3: 全量验证、影响复核与视觉审查

**Files:**

- Verify: `frontend/src/features/market-data/pages/MarketDataPage.tsx`
- Verify: `frontend/src/features/market-data/pages/MarketDataPage.css`
- Verify: `frontend/src/test/MarketDataPage.test.tsx`
- Verify: `frontend/tests/playwright/market-data-layout-primitives.spec.mjs`

- [ ] **Step 1: 运行最窄相关测试**

Run from `frontend/`:

```powershell
npm run test -- MarketDataPage.test.tsx SectionHead.test.tsx
```

Expected: 两个测试文件全部通过，无 console error 或未处理 Promise。

- [ ] **Step 2: 运行新增浏览器契约和既有市场数据烟测**

```powershell
$env:MOSS_PLAYWRIGHT_USE_WEB_SERVER="1"
$env:MOSS_PLAYWRIGHT_REUSE_SERVER="0"
npx playwright test -c playwright.config.mjs tests/playwright/market-data-layout-primitives.spec.mjs tests/playwright/market-data-terminal-smoke.spec.mjs tests/playwright/market-data-workflow-smoke.spec.mjs --workers=1
```

Expected: 新增布局测试和两个既有市场数据烟测全部通过。

- [ ] **Step 3: 运行前端静态检查与债务审计**

```powershell
npm run lint -- src/features/market-data/pages/MarketDataPage.tsx src/test/MarketDataPage.test.tsx tests/playwright/market-data-layout-primitives.spec.mjs
npm run typecheck
npm run debt:audit
```

Expected: 三条命令 exit 0；债务基线不增加，编码完整性审计保持通过。

- [ ] **Step 4: 复核差异与 GitNexus 影响**

Run from repository root:

```powershell
git diff --check HEAD~2..HEAD
git show --stat --oneline HEAD~2..HEAD
npx gitnexus detect-changes --scope compare --base-ref HEAD~2 -r moss-v3-main-current-20260809
```

Expected: 差异检查无错误，两个实现提交只包含四个批准文件；GitNexus 影响局限在市场数据页面渲染和相关测试流程。

- [ ] **Step 5: 做人工视觉审查**

在 1440×900、768×1024、390×844 三个视口检查 `/market-data`。确认 Hero 状态条与 KPI 带仍在首部、两处分区头读感一致、四类重复框消失、正式利率图表和 Explorer 内部工作区仍有清晰边界、文字没有截断、控件没有挤出视口。

- [ ] **Step 6: 进行两阶段子代理审查**

先让规格审查代理逐条对照 `docs/superpowers/specs/2026-08-28-market-data-visual-convergence-design.md`，确认无缺项和范围外改动；规格通过后，再让代码质量审查代理检查选择器特异度、无障碍语义、测试脆弱性和脏工作区隔离。任何问题由对应实现代理修复并重新审查，直到两阶段都通过。
