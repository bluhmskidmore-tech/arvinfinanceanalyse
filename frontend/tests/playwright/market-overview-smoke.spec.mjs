import { test, expect } from "@playwright/test";

const MARKET_READY_SELECTOR = '[data-testid="module-workbench-home"]';
const EXPECTED_SUBPAGE_HREFS = [
  "/market-overview",
  "/market-data",
  "/cross-asset",
  "/macro-observation",
  "/macro-toolkit",
  "/stock-analysis",
  "/news-events",
];
const EXPECTED_CHAPTER_HREFS = [
  "#market-overview-judgment",
  "#market-overview-evidence",
  "#market-financial-charts-all",
  "#market-backend-data-all",
];
const EXPECTED_ACTION_HREFS = ["/macro-toolkit", "/market-data", "/cross-asset"];
// The sixth macro-toolkit row is an operational output-file status. The page
// deliberately keeps it out of the market-signal strip.
const EXPECTED_MARKET_SIGNAL_COUNT = 5;

const suspiciousTextPattern = /[\uFFFD]|\u93C3|\u9359|\u5BF0|\u9215/;

async function openMarketOverview(page, viewport) {
  await page.setViewportSize(viewport);
  await page.goto("/market-overview", { waitUntil: "domcontentloaded" });
  await expect(page.locator(MARKET_READY_SELECTOR)).toBeVisible({ timeout: 60_000 });
  await page.waitForLoadState("networkidle", { timeout: 30_000 }).catch(() => undefined);
}

function expectBoxWithinViewport(box, width, label) {
  expect(box, `${label} should have a bounding box`).toBeTruthy();
  expect(box.x, `${label} should not overflow left`).toBeGreaterThanOrEqual(-1);
  expect(box.x + box.width, `${label} should not overflow right`).toBeLessThanOrEqual(
    width + 1,
  );
}

test.describe("market overview browser smoke", () => {
  test("renders the dense market overview contract on desktop", async ({ page }) => {
    await openMarketOverview(page, { width: 1440, height: 1100 });

    const root = page.getByTestId("module-workbench-home");
    await expect(root).not.toHaveText(suspiciousTextPattern);

    // Nocturne scope 生效：页根声明 scope，--dh-api-bg 解析为 Nocturne 底色。
    await expect(root).toHaveAttribute("data-moss-theme-scope", "market-overview");
    const canvasToken = await root.evaluate((node) =>
      getComputedStyle(node).getPropertyValue("--dh-api-bg").trim(),
    );
    expect(canvasToken).toBe("#161826");

    const subpageNav = page.getByTestId("module-home-market-subpage-nav");
    const chapterNav = page.getByTestId("module-home-market-chapter-nav");
    const dense = page.getByTestId("module-home-market-dense");
    const toolbar = page.getByTestId("module-home-toolbar");
    const utility = page.getByTestId("module-home-market-dense-utility");
    const search = page.getByTestId("module-home-market-dense-search");
    const refresh = page.getByTestId("module-home-market-dense-refresh");

    await expect(subpageNav).toBeVisible();
    await expect(chapterNav).toBeVisible();
    await expect(dense).toBeVisible();
    await expect(toolbar).toBeVisible();
    await expect(utility).toBeVisible();
    await expect(search).toBeVisible();
    await expect(refresh).toBeVisible();

    const subpageHrefs = await subpageNav
      .locator("a")
      .evaluateAll((links) => links.map((link) => link.getAttribute("href")));
    const chapterHrefs = await chapterNav
      .locator("a")
      .evaluateAll((links) => links.map((link) => link.getAttribute("href")));
    for (const href of EXPECTED_SUBPAGE_HREFS) {
      expect(subpageHrefs).toContain(href);
    }
    for (const href of EXPECTED_CHAPTER_HREFS) {
      expect(chapterHrefs).toContain(href);
    }
    await expect(subpageNav.locator('a[aria-current="page"]')).toHaveCount(1);
    await expect(chapterNav.locator('a[aria-current="location"]')).toHaveCount(1);

    await expect(page.locator("#market-overview-judgment")).toBeVisible();
    await expect(page.locator("#market-overview-evidence")).toBeVisible();
    await expect(page.locator("#market-financial-charts-all")).toBeVisible();
    await expect(page.locator("#market-backend-data-all")).toBeVisible();

    await expect(page.locator("#market-overview-judgment")).toContainText("DR007");
    await expect(page.locator("#market-overview-evidence")).toContainText("DR007");

    const actionQueue = page.locator("#market-overview-actions");
    const actionLinks = actionQueue.locator("a");
    await expect(actionQueue).toBeVisible();
    const actionHrefs = await actionLinks.evaluateAll((links) =>
      links.map((link) => link.getAttribute("href")),
    );
    expect(actionHrefs).toEqual(EXPECTED_ACTION_HREFS);
    const actionTones = await actionLinks.evaluateAll((links) =>
      links.map((link) => link.getAttribute("data-tone")),
    );
    for (const tone of actionTones) {
      expect(tone).toMatch(/^(up|down|watch|ok|muted|error)$/);
    }

    const denseCharts = page.locator('[data-testid^="module-home-market-dense-chart-"]');
    await expect(denseCharts).toHaveCount(6);
    await expect(denseCharts.filter({ has: page.getByText("DR007", { exact: true }) }).first()).toBeVisible();

    const signalCards = page.locator("#market-overview-signals article");
    await expect(signalCards).toHaveCount(EXPECTED_MARKET_SIGNAL_COUNT);
    const signalTones = await signalCards.evaluateAll((cards) =>
      cards.map((card) => card.getAttribute("data-tone")),
    );
    for (const tone of signalTones) {
      expect(tone).toMatch(/^(alert|watch|ok|muted)$/);
    }
  });

  test("keeps the dense market overview rails and first-screen surfaces inside a mobile viewport", async ({ page }) => {
    await openMarketOverview(page, { width: 390, height: 844 });

    const noHorizontalOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 2,
    );
    expect(noHorizontalOverflow).toBe(true);

    const subpageNav = page.getByTestId("module-home-market-subpage-nav");
    const chapterNav = page.getByTestId("module-home-market-chapter-nav");
    const dense = page.getByTestId("module-home-market-dense");
    const toolbar = page.getByTestId("module-home-toolbar");
    const search = page.getByTestId("module-home-market-dense-search");
    const refresh = page.getByTestId("module-home-market-dense-refresh");
    const judgment = page.locator("#market-overview-judgment");

    await expect(subpageNav).toBeVisible();
    await expect(chapterNav).toBeVisible();
    await expect(dense).toBeVisible();
    await expect(toolbar).toBeVisible();
    await expect(search).toBeVisible();
    await expect(refresh).toBeVisible();
    await expect(judgment).toBeVisible();
    await expect(judgment).toContainText("DR007");

    // 工具栏搜索框是常驻控件（不再做 30px 图标化折叠），聚焦不改变几何。
    expectBoxWithinViewport(await subpageNav.boundingBox(), 390, "subpage nav");
    expectBoxWithinViewport(await chapterNav.boundingBox(), 390, "chapter nav");
    expectBoxWithinViewport(await toolbar.boundingBox(), 390, "toolbar");
    expectBoxWithinViewport(await search.boundingBox(), 390, "search box");
    expectBoxWithinViewport(await refresh.boundingBox(), 390, "refresh button");

    await search.locator("input").focus();
    await expect(search.locator("input")).toBeFocused();
    expectBoxWithinViewport(await search.boundingBox(), 390, "focused search box");

    await page.locator("#market-overview-evidence").scrollIntoViewIfNeeded();
    const signalCards = page.locator("#market-overview-signals article");
    await expect(signalCards.first()).toBeVisible();
    await expect(signalCards).toHaveCount(EXPECTED_MARKET_SIGNAL_COUNT);
  });
});
