import { test, expect } from "@playwright/test";
import { interceptDesignData } from "./fixtures/market-overview-figma.mjs";

const REAL_STATE_BASE_URL = process.env.MOSS_PLAYWRIGHT_STATE_BASE_URL ??
  `http://127.0.0.1:${process.env.MOSS_PLAYWRIGHT_STATE_PORT ?? "5889"}`;
test.use({ baseURL: REAL_STATE_BASE_URL });

const SUBPAGES = ["/market-overview", "/market-data", "/cross-asset", "/macro-observation", "/macro-toolkit", "/stock-analysis", "/news-events"];
const CHAPTERS = ["#market-overview-judgment", "#market-overview-evidence", "#market-financial-charts-all", "#market-backend-data-all"];

async function openMarketOverview(page, width) {
  const reads = await interceptDesignData(page);
  const snapshots = [], writes = [], scenarioReads = [], errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (/^\/(api|ui)\//.test(path) && !["GET", "HEAD", "OPTIONS"].includes(request.method())) writes.push(path);
    if (path === "/api/risk/scenario-stress") scenarioReads.push(path);
  });
  page.on("response", (response) => {
    if (new URL(response.url()).pathname.endsWith("/ui/market-overview/snapshot") && response.ok()) snapshots.push(response.json());
  });
  await page.setViewportSize({ width, height: 900 });
  await page.goto("/market-overview", { waitUntil: "domcontentloaded" });
  await expect(page.locator('section[aria-labelledby="market-rates-title"]')).toBeVisible({ timeout: 60_000 });
  await expect.poll(() => reads.snapshot).toBeGreaterThan(0);
  await selectFundingView(page, "资金价格");
  await page.waitForLoadState("networkidle", { timeout: 30_000 }).catch(() => undefined);
  const payload = (await Promise.all(snapshots)).at(-1)?.result;
  expect(payload).toBeTruthy();
  expect(reads.paths).toContain("/ui/market-overview/snapshot");
  return { payload, reads, writes, scenarioReads, errors };
}

function observationPanels(page) {
  return {
    funding: page.locator('section[aria-labelledby="market-funding-title"]'),
    rates: page.locator('section[aria-labelledby="market-rates-title"]'),
    trend: page.getByTestId("module-home-market-dense-chart-key-rate-trend"),
    cross: page.getByTestId("module-home-market-dense-chart-cross-asset-move"),
  };
}

async function selectFundingView(page, name) {
  const group = page.getByRole("group", { name: "资金与利率图表", exact: true });
  const button = group.getByRole("button", { name, exact: true });
  await button.click();
  await expect(button).toHaveAttribute("aria-pressed", "true");
  await expect(group.getByRole("button", { name: name === "资金价格" ? "关键利率" : "资金价格", exact: true })).toHaveAttribute("aria-pressed", "false");
  const { funding, trend } = observationPanels(page);
  await expect(name === "资金价格" ? funding.getByTestId("market-funding-chart") : trend).toBeVisible();
  await expect(name === "资金价格" ? trend : funding.getByTestId("market-funding-chart")).not.toBeVisible();
  await (name === "资金价格" ? funding : trend).scrollIntoViewIfNeeded();
}

function expectWithinViewport(box, width) {
  expect(box).toBeTruthy();
  expect(box.x).toBeGreaterThanOrEqual(-1);
  expect(box.x + box.width).toBeLessThanOrEqual(width + 1);
}

async function verifyDrawer(page, kind, observation) {
  const opener = page.getByRole("button", { name: kind === "funding" ? "查看资金依据" : "查看曲线依据" });
  await opener.scrollIntoViewIfNeeded();
  await opener.focus();
  await page.keyboard.press("Enter");
  const drawer = page.getByRole("dialog");
  await expect(drawer).toBeVisible();
  await expect(drawer).toContainText(kind === "funding" ? "资金条件依据" : "利率定价依据");
  if (observation) {
    await expect(drawer).toContainText(observation.rule_version);
    for (const row of observation.evidence) {
      await expect(drawer).toContainText(row.series_id);
      if (row.observation_date) await expect(drawer).toContainText(row.observation_date);
      if (row.value != null) await expect(drawer).toContainText(String(row.value));
    }
  }
  // Visibility precedes the end of the AntD drawer entrance animation.
  await expect.poll(async () => {
    const box = await drawer.boundingBox();
    return box ? box.x >= -1 && box.x + box.width <= page.viewportSize().width + 1 : false;
  }).toBe(true);
  await page.keyboard.press("Escape");
  await expect(drawer).not.toBeVisible();
  await expect(opener).toBeFocused();
}

test.describe("market overview browser smoke", () => {
  test("keeps the four chart subjects accessible after the quote tape with dates and restrictions", async ({ page }) => {
    const { payload, writes, scenarioReads, errors } = await openMarketOverview(page, 1440);
    const { funding, rates, trend, cross } = observationPanels(page);
    await expect(funding.getByRole("heading", { name: "资金价格", exact: true })).toBeVisible();
    await expect(rates.getByRole("heading", { name: "国债收益率曲线", exact: true })).toBeVisible();
    const cards = [rates, funding, cross];
    for (const card of cards) {
      await expect(card).toBeVisible();
      await card.scrollIntoViewIfNeeded();
      await expect(card.locator("canvas:visible")).toHaveCount(1);
    }
    const boxes = await Promise.all(cards.map((card) => card.boundingBox()));
    const tape = await page.getByRole("region", { name: "市场行情带", exact: true }).boundingBox();
    expect(tape.y + tape.height).toBeLessThanOrEqual(boxes[0].y);
    // The delivered hierarchy gives the curve its own row, then places funding
    // beside cross-asset evidence; key rates share an explicit funding switch.
    expect(Math.abs(boxes[1].y - boxes[2].y)).toBeLessThan(2);
    expect(boxes[1].y).toBeGreaterThanOrEqual(boxes[0].y + boxes[0].height);
    expect(boxes[2].x).toBeGreaterThanOrEqual(boxes[1].x + boxes[1].width);
    for (const box of boxes) expectWithinViewport(box, 1440);
    for (const card of [funding, rates]) {
      await card.locator("canvas:visible").scrollIntoViewIfNeeded();
      const canvas = await card.locator("canvas:visible").boundingBox();
      expect(canvas.y + canvas.height).toBeLessThanOrEqual(900);
      await expect(card.locator("details:visible")).not.toHaveAttribute("open");
      await expect(card.getByText(/^(资金|曲线)观察日/)).toBeVisible();
      await expect(card.getByText(/^(资金|曲线)观察日/)).toHaveText(/观察日 \d{4}-\d{2}-\d{2}；比较日 \d{4}-\d{2}-\d{2}/);
    }
    for (const [card, observation] of [[funding, payload?.funding_observation], [rates, payload?.rates_observation]]) {
      expect(observation).toBeTruthy();
      const dates = card.getByText(/^(资金|曲线)观察日/);
      await expect(dates).toBeVisible();
      await expect(dates).toContainText(observation.observation_date ?? "—");
      await expect(dates).toContainText(observation.comparison_date ?? "—");
    }
    const status = page.getByTestId("module-home-market-dense-observation-summary");
    await expect(status.locator("..")).not.toHaveAttribute("open");
    if (payload?.gate?.human_reason) await expect(status).toContainText(payload.gate.human_reason);
    await expect(page.getByTestId("module-home-market-dense-observation-context")).not.toBeVisible();
    await status.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("module-home-market-dense-observation-context")).toBeVisible();
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("module-home-market-dense-observation-context")).not.toBeVisible();
    if (payload?.funding_observation?.judgment_allowed === false) await expect(funding.getByText("判断受限", { exact: true })).toBeVisible();
    if (payload?.funding_observation?.rows.find((row) => row.key === "dr007")?.is_proxy) await expect(funding.getByText("代理参考", { exact: true })).toBeVisible();
    if (payload?.funding_observation?.policy_reference.validity_status === "unverified") await expect(funding.getByText("政策基准待核验", { exact: true })).toBeVisible();
    if (payload?.rates_observation?.full_curve_comparison_allowed === false) await expect(rates.getByText("跨期比较待核验", { exact: true })).toBeVisible();
    await selectFundingView(page, "关键利率");
    await expect(trend.locator("canvas")).toHaveCount(1);
    await expect(trend.locator("header > p")).toHaveText(/\d{4}-\d{2}-\d{2}–\d{4}-\d{2}-\d{2} · %/);
    await expect(trend).toContainText("各序列按自身日期展示；缺口留空");
    expectWithinViewport(await trend.boundingBox(), 1440);
    await expect(cross).toContainText("各项比较日期见图中标签，非同日涨跌排名");
    await selectFundingView(page, "资金价格");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 2)).toBe(true);
    expect(writes).toEqual([]);
    expect(scenarioReads).toEqual([]);
    expect(errors).toEqual([]);
  });

  test("restores the evidence opener when Escape interrupts the drawer entrance animation", async ({ page }) => {
    const { writes, scenarioReads, errors } = await openMarketOverview(page, 390);
    // Keep the visual transition unfinished while closing during the asserted
    // entrance phase. This reproduces the rc-drawer destroy-before-focus race.
    await page.addStyleTag({ content: ".ant-drawer-content-wrapper { transition-duration: 5s !important; }" });
    for (const name of ["查看资金依据", "查看曲线依据"]) {
      const opener = page.getByRole("button", { name, exact: true });
      await opener.scrollIntoViewIfNeeded();
      await opener.focus();
      await page.keyboard.press("Enter");
      const drawer = page.getByRole("dialog");
      await expect(drawer).toBeVisible();
      await expect(drawer.locator("..")).toHaveClass(/(?:appear|enter)-active/);
      await page.keyboard.press("Escape");
      await expect(drawer).not.toBeVisible();
      await expect(opener).toBeFocused();
    }
    expect(writes).toEqual([]);
    expect(scenarioReads).toEqual([]);
    expect(errors).toEqual([]);
  });

  test("preserves all twelve original charts and resolves every duplicate reference to a visible original", async ({ page }) => {
    const { writes, scenarioReads, errors } = await openMarketOverview(page, 1440);
    const trend = page.getByTestId("module-home-market-dense-chart-key-rate-trend");
    await selectFundingView(page, "关键利率");
    await expect(trend).toBeVisible();
    await expect(trend.locator("canvas")).toHaveCount(1);
    await expect(page.locator("#market-overview-judgment")).toContainText("关键利率近 20 期走势");
    await expect(page.getByTestId("module-home-market-background-details")).not.toBeVisible();
    await expect(page.getByTestId("module-home-market-dense-chart-news-density")).not.toBeVisible();
    const topics = page.locator("#market-financial-charts-all");
    await expect(topics).not.toHaveAttribute("open");
    await page.getByTestId("module-home-market-chapter-nav").getByRole("link", { name: "专题图表" }).click();
    await expect(topics).toHaveAttribute("open");
    const workbench = page.getByTestId("module-home-market-financial-charts");
    const nav = workbench.getByRole("navigation", { name: "金融图表分组导航" });
    await expect(nav.getByRole("button")).toHaveCount(6);
    await expect(workbench.locator('[data-testid^="module-home-market-chart-"]')).toHaveCount(12);
    await expect(page.locator("#market-financial-section-rates")).toHaveAttribute("data-expanded", "true");

    for (const key of ["yield-curve"]) {
      const original = page.getByTestId(`module-home-market-chart-${key}`);
      await expect(original).toBeVisible();
      await original.scrollIntoViewIfNeeded();
      await expect(page.getByTestId(`module-home-market-chart-ref-${key}`)).toHaveCount(0);
      await expect(page.getByTestId(`module-home-market-dense-chart-${key}`)).toHaveCount(0);
      await expect(original).not.toContainText("该图已在上方");
      // A sparse curve retains its original quote comparison. An empty chart
      // retains its own explicit empty state rather than a reference to another chart.
      await expect.poll(async () => original.locator('canvas, [data-testid^="module-home-market-yield-"], [role="status"]').count()).toBeGreaterThan(0);
    }
    await expect(page.getByTestId("module-home-market-chart-key-rate-trend")).toHaveCount(0);
    await expect(page.getByTestId("module-home-market-chart-ref-key-rate-trend")).toBeVisible();

    for (const name of ["利率与流动性", "跨资产", "宏观信号", "策略与风险", "新闻事件", "数据覆盖"]) {
      const button = nav.getByRole("button", { name, exact: true });
      await button.click();
      const section = page.locator(`#${await button.getAttribute("aria-controls")}`);
      await expect(section).toHaveAttribute("data-expanded", "true");
      await expect(section.locator('[data-testid^="module-home-market-chart-"]')).toHaveCount(2);
    }
    await expect(workbench.locator('[data-chart-view="reference"]')).toHaveCount(2);
    for (const reference of await workbench.locator('[data-chart-view="reference"]').all()) {
      const link = reference.getByRole("link", { name: "查看上方原图" });
      const href = await link.getAttribute("href");
      expect(href).toMatch(/^#market-overview-chart-/);
      const original = page.locator(href);
      await expect(original).toHaveCount(1);
      await expect(original).toBeVisible();
      await link.click();
      await expect(page).toHaveURL(new RegExp(`${href}$`));
      await expect(original).toBeFocused();
      await expect(original).toBeInViewport();
    }
    await workbench.getByRole("button", { name: "重点", exact: true }).click();
    await nav.getByRole("button", { name: "利率与流动性", exact: true }).click();
    await expect(page.getByTestId("module-home-market-chart-yield-curve")).toBeVisible();
    await expect(page.getByTestId("module-home-market-chart-ref-key-rate-trend")).toBeVisible();
    await workbench.getByRole("button", { name: "全览", exact: true }).click();
    expect(writes).toEqual([]);
    expect(scenarioReads).toEqual([]);
    expect(errors).toEqual([]);
  });

  test("shows independent funding and curve evidence while preserving navigation and lazy reads", async ({ page }) => {
    const { payload, writes, scenarioReads, errors } = await openMarketOverview(page, 1440);
    const root = page.getByTestId("module-workbench-home");
    await expect(root).not.toHaveText(/[\uFFFD]|\u93C3|\u9359|\u5BF0|\u9215/);
    await expect(root).toHaveAttribute("data-moss-theme-scope", "market-overview");
    expect(await root.evaluate((node) => getComputedStyle(node).getPropertyValue("--dh-api-bg").trim())).toBe("#161826");
    const subpageNav = page.getByRole("navigation", { name: "市场工作台页面", exact: true });
    const chapters = page.getByTestId("module-home-market-chapter-nav");
    for (const href of SUBPAGES) await expect(subpageNav.locator(`a[href="${href}"]`)).toHaveCount(1);
    for (const href of CHAPTERS) await expect(chapters.locator(`:scope > a[href="${href}"]`)).toHaveCount(1);
    await expect(subpageNav.locator('a[aria-current="page"]')).toHaveCount(1);
    await expect(chapters.locator('a[aria-current="location"]')).toHaveCount(1);
    await expect(page.getByTestId("module-home-toolbar")).toBeVisible();
    await expect(page.getByTestId("module-home-market-dense-refresh")).toBeVisible();
    await expect(page.getByTestId("module-home-market-dense-observation-title")).toHaveText("市场观察");
    await expect(page.locator("#market-overview-signals")).toHaveCount(0);
    await expect(page.getByTestId("module-home-market-dense-directional-coverage")).toHaveCount(0);

    const { funding, rates } = observationPanels(page);
    expect((await rates.boundingBox()).y).toBeLessThan(750);
    const fundingDetails = funding.locator("details:visible");
    const ratesDetails = rates.locator("details");
    await expect(fundingDetails).not.toHaveAttribute("open");
    await expect(ratesDetails).not.toHaveAttribute("open");
    await expect(funding.locator("canvas:visible")).toBeVisible();
    await expect(rates.locator("canvas")).toBeVisible();
    expect((await funding.locator("canvas:visible").boundingBox()).y).toBeLessThan((await fundingDetails.boundingBox()).y);
    expect((await rates.locator("canvas").boundingBox()).y).toBeLessThan((await ratesDetails.boundingBox()).y);
    await fundingDetails.locator("summary").click();
    await ratesDetails.locator("summary").click();
    await expect(funding.getByRole("table", { name: "资金价格与比较日期" })).toBeVisible();
    await expect(rates.getByRole("table", { name: "国债分期限变化" })).toBeVisible();
    await expect(rates.getByRole("table", { name: "国债期限利差变化" })).toBeVisible();
    for (const [panel, observation] of [[funding, payload?.funding_observation], [rates, payload?.rates_observation]]) {
      expect(observation).toBeTruthy();
      await expect(panel).toContainText(observation.observation_date ?? "—");
      await expect(panel).toContainText(observation.comparison_date ?? "—");
      await expect(panel).toContainText(!observation.judgment_allowed ? observation.reason || observation.summary : observation.summary);
      for (const row of observation.rows) await expect(panel.getByRole("table").first()).toContainText(row.label);
    }
    if (payload?.funding_observation?.policy_reference.validity_status === "unverified") await expect(funding).toContainText("政策基准待核验");
    if (payload?.rates_observation?.full_curve_comparison_allowed === false) {
      await expect(rates).toContainText("跨期比较条件未全部核验");
      await expect(rates).not.toContainText("曲线覆盖不完整");
    }
    await verifyDrawer(page, "funding", payload?.funding_observation);
    await verifyDrawer(page, "rates", payload?.rates_observation);

    const verification = page.getByTestId("module-home-market-dense-verification");
    await expect(verification).not.toHaveAttribute("open");
    await verification.locator("summary").click();
    await expect(page.locator("#market-overview-actions")).toBeVisible();
    for (const issue of payload?.gate?.issues ?? []) {
      const row = page.getByTestId(`module-home-market-dense-gate-issue-${issue.key}`);
      await expect(row).toContainText(issue.reason);
      await expect(row.getByRole("link", { name: "进入核验" })).toHaveAttribute("href", issue.route);
    }
    await verification.locator("summary").click();
    await expect(page.locator("#market-financial-charts-all")).not.toHaveAttribute("open");
    await expect(page.locator("#market-backend-data-all")).not.toHaveAttribute("open");
    await chapters.locator(':scope > a[href="#market-backend-data-all"]').click();
    await expect(page.locator("#market-backend-data-all")).toHaveAttribute("open");
    await expect(page.locator("#market-backend-data-all").getByRole("table").first()).toBeVisible();
    expect(writes).toEqual([]);
    expect(scenarioReads).toEqual([]);
    expect(errors).toEqual([]);
  });

  for (const width of [1024, 390]) {
    test(`keeps analysis and keyboard evidence inside ${width}px without page overflow`, async ({ page }) => {
      const { payload, reads, writes, scenarioReads, errors } = await openMarketOverview(page, width);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 2)).toBe(true);
      for (const id of ["module-home-market-chapter-nav", "module-home-toolbar"]) expectWithinViewport(await page.getByTestId(id).boundingBox(), width);
      const { funding, rates, trend, cross } = observationPanels(page);
      for (const card of [rates, funding, cross]) expectWithinViewport(await card.boundingBox(), width);
      if (width === 390) {
        const tape = page.getByRole("region", { name: "市场行情带", exact: true });
        // The delivered tape prioritizes four subjects. The full quote table
        // remains separately accessible through the chapter navigation.
        await expect(tape.locator(":scope > article")).toHaveCount(4);
        for (const label of ["10Y国债", "DR007", "SHIBOR 3M", "USD/CNY"]) {
          await expect(tape.locator(":scope > article").filter({ hasText: label })).toHaveCount(1);
        }
        for (const item of await tape.locator(":scope > article").all()) {
          await expect(item.locator(":scope > span")).toBeVisible();
          await expect(item.locator("strong")).toBeVisible();
          expectWithinViewport(await item.boundingBox(), width);
        }
        const allQuotes = page.getByTestId("module-home-market-chapter-nav").getByRole("link", { name: "全部行情", exact: true });
        await page.locator("#workbench-main-content").focus();
        let quoteLinkReached = false;
        for (let step = 0; step < 60; step += 1) {
          await page.keyboard.press("Tab");
          if (await allQuotes.evaluate(node => node === document.activeElement)) {
            quoteLinkReached = true;
            break;
          }
        }
        expect(quoteLinkReached).toBe(true);
        await expect(allQuotes).toBeFocused();
        await expect(allQuotes).toBeInViewport();
        await page.keyboard.press("Enter");
        const quotes = page.locator("#market-backend-data-all");
        await expect(quotes).toHaveAttribute("open");
        await expect(quotes.getByRole("table").first()).toBeVisible();
        for (const name of ["Brent spot price", "中证全债指数", "USD/CNY", "沪深300指数收盘价", "铜主力期货收盘价"]) {
          await expect(quotes.getByRole("button", { name: `核验 ${name}`, exact: true })).toBeVisible();
        }
        expect(reads.paths).toContain("/ui/macro/choice-series/latest");
        const boxes = await Promise.all([rates, funding, cross].map((card) => card.boundingBox()));
        for (let index = 0; index < boxes.length; index += 1) {
          expectWithinViewport(boxes[index], width);
          if (index > 0) expect(boxes[index].y).toBeGreaterThanOrEqual(boxes[index - 1].y + boxes[index - 1].height);
        }
      }
      await selectFundingView(page, "关键利率");
      await expect(trend.locator("canvas")).toHaveCount(1);
      expectWithinViewport(await trend.boundingBox(), width);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 2)).toBe(true);
      await selectFundingView(page, "资金价格");
      const search = page.getByTestId("module-home-market-dense-search").locator("input");
      await search.focus();
      await expect(search).toBeFocused();
      expectWithinViewport(await search.boundingBox(), width);
      await verifyDrawer(page, "funding", payload?.funding_observation);
      await verifyDrawer(page, "rates", payload?.rates_observation);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 2)).toBe(true);
      expect(writes).toEqual([]);
      expect(scenarioReads).toEqual([]);
      expect(errors).toEqual([]);
    });
  }
});
