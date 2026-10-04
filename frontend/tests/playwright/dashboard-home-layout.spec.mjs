import { expect, test } from "@playwright/test";

const VIEWPORTS = {
  mobile360: { width: 360, height: 800 },
  mobile390: { width: 390, height: 844 },
  tablet768: { width: 768, height: 1024 },
  desktop1280: { width: 1280, height: 900 },
  desktop1440: { width: 1440, height: 900 },
  desktop1920: { width: 1920, height: 900 },
};

async function openDashboardHome(page, viewport) {
  await page.setViewportSize(viewport);
  await page.goto("/", { waitUntil: "domcontentloaded" });

  const dashboard = page.getByTestId("dashboard-home-page");
  const toolbar = page.getByTestId("dashboard-home-toolbar");
  const scrollRoot = page.getByTestId("dashboard-home-scroll-root");
  const hero = page.getByTestId("dashboard-home-hero");
  const morningHero = page.getByTestId("dashboard-home-morning-hero");
  const kpiStrip = page.getByTestId("dashboard-home-hero-kpi-strip");
  const productHeadline = page.getByTestId("dashboard-home-product-category-headline");
  const productStrip = page.getByTestId("dashboard-home-product-category-strip");
  const today = page.getByRole("region", { name: "今日需处理", exact: true });
  const summary = page.getByRole("region", { name: "组合变化", exact: true });

  await expect(dashboard).toBeVisible({ timeout: 60_000 });
  await expect(toolbar).toBeVisible({ timeout: 60_000 });
  await expect(scrollRoot).toBeVisible({ timeout: 60_000 });
  await expect(hero).toBeVisible({ timeout: 60_000 });
  await expect(morningHero).toBeVisible({ timeout: 60_000 });
  await expect(kpiStrip).toBeVisible({ timeout: 60_000 });
  await expect(productHeadline).toBeVisible({ timeout: 60_000 });
  await expect(productStrip).toBeVisible({ timeout: 60_000 });

  return {
    dashboard,
    toolbar,
    scrollRoot,
    hero,
    morningHero,
    kpiStrip,
    productHeadline,
    productStrip,
    today,
    summary,
  };
}

async function readBox(locator, label) {
  const box = await locator.boundingBox();
  expect(box, `${label} should have a bounding box`).not.toBeNull();
  return box;
}

async function expectNoHorizontalOverflow(locator, label) {
  const widths = await locator.evaluate((element) => ({
    clientWidth: element.clientWidth,
    scrollWidth: element.scrollWidth,
  }));

  expect(
    widths.scrollWidth,
    `${label} should not overflow horizontally`,
  ).toBeLessThanOrEqual(widths.clientWidth + 1);
}

async function expectFourKpis(kpiStrip) {
  await expect(kpiStrip.locator("article")).toHaveCount(4);
}

async function expectSummaryOrderAndHeroContainment({
  hero,
  kpiStrip,
  morningHero,
  productHeadline,
  productStrip,
  today,
  summary,
}) {
  const heroBox = await readBox(hero, "hero");
  const kpiBox = await readBox(kpiStrip, "hero KPI strip");
  const attributionBox = await readBox(morningHero, "attribution summary");
  const productHeadlineBox = await readBox(productHeadline, "product headline");
  const productStripBox = await readBox(productStrip, "product summary strip");
  const todayBox = await readBox(today, "today's decisions");
  const summaryBox = await readBox(summary, "portfolio changes");

  expect(
    todayBox.y + todayBox.height,
    "today's decisions should end before the product summary starts",
  ).toBeLessThanOrEqual(productHeadlineBox.y + 1);

  expect(
    productHeadlineBox.y + productHeadlineBox.height,
    "the product summary should end before portfolio changes start",
  ).toBeLessThanOrEqual(summaryBox.y + 1);

  // Attribution precedes the KPIs: side by side on desktop, stacked on narrow screens.
  const sideBySide = Math.abs(attributionBox.y - kpiBox.y) <= 1;
  if (sideBySide) {
    expect(attributionBox.x + attributionBox.width).toBeLessThanOrEqual(kpiBox.x + 1);
  } else {
    expect(attributionBox.y + attributionBox.height).toBeLessThanOrEqual(kpiBox.y + 1);
  }

  for (const [label, box] of [
    ["KPI strip", kpiBox],
    ["attribution summary", attributionBox],
    ["product headline", productHeadlineBox],
    ["product summary strip", productStripBox],
    ["today's decisions", todayBox],
    ["portfolio changes", summaryBox],
  ]) {
    expect(box.x, `${label} should stay inside the hero on the left edge`)
      .toBeGreaterThanOrEqual(heroBox.x - 1);
    expect(box.x + box.width, `${label} should stay inside the hero on the right edge`)
      .toBeLessThanOrEqual(heroBox.x + heroBox.width + 1);
    expect(box.y, `${label} should stay inside the hero on the top edge`)
      .toBeGreaterThanOrEqual(heroBox.y - 1);
    expect(box.y + box.height, `${label} should stay inside the hero on the bottom edge`)
      .toBeLessThanOrEqual(heroBox.y + heroBox.height + 1);
  }
}

async function expectMobileDocumentNoHorizontalOverflow(page) {
  const widths = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));

  expect(
    widths.scrollWidth,
    "mobile document should not overflow horizontally",
  ).toBeLessThanOrEqual(widths.clientWidth + 1);
}

async function expectCoreKpiInInitialViewport(
  { kpiStrip },
  viewport,
) {
  const coreValueBox = await readBox(
    kpiStrip.locator("article").first().locator("strong"),
    "first core KPI value",
  );

  expect(
    coreValueBox.y,
    "the first core KPI value should not be above the initial viewport",
  ).toBeGreaterThanOrEqual(0);
  expect(
    coreValueBox.y + coreValueBox.height,
    "the first core KPI value should be readable in the initial viewport",
  ).toBeLessThanOrEqual(viewport.height + 1);
}

async function expectSharedSummaryLayout(page, viewport, options = {}) {
  const handles = await openDashboardHome(page, viewport);
  await expectFourKpis(handles.kpiStrip);
  await expectNoHorizontalOverflow(handles.hero, "hero");
  await expectNoHorizontalOverflow(handles.kpiStrip, "KPI strip");
  await expectNoHorizontalOverflow(handles.productHeadline, "product headline");
  await expectNoHorizontalOverflow(handles.productStrip, "product summary strip");
  await expectSummaryOrderAndHeroContainment(handles);

  if (options.assertInitialViewport) {
    await expectCoreKpiInInitialViewport(handles, viewport);
  }

  if (options.assertMobileDocumentOverflow) {
    await expectMobileDocumentNoHorizontalOverflow(page);
  }

  return handles;
}

test.describe("dashboard home layout", () => {
  test("prioritizes core KPIs in the 360 mobile viewport without horizontal overflow", async ({
    page,
  }) => {
    await expectSharedSummaryLayout(page, VIEWPORTS.mobile360, {
      assertInitialViewport: true,
      assertMobileDocumentOverflow: true,
    });
  });

  test("prioritizes core KPIs in the 390 mobile viewport without horizontal overflow", async ({
    page,
  }) => {
    await expectSharedSummaryLayout(page, VIEWPORTS.mobile390, {
      assertInitialViewport: true,
      assertMobileDocumentOverflow: true,
    });
  });

  test("prioritizes core KPIs in the 768 tablet viewport without horizontal overflow", async ({
    page,
  }) => {
    await expectSharedSummaryLayout(page, VIEWPORTS.tablet768, {
      assertInitialViewport: true,
    });
  });

  for (const viewport of [VIEWPORTS.desktop1280, VIEWPORTS.desktop1440, VIEWPORTS.desktop1920]) {
    test(`aligns desktop panels, KPI values and toolbar at ${viewport.width}px`, async ({ page }) => {
      const { hero, toolbar, kpiStrip, morningHero } = await expectSharedSummaryLayout(page, viewport, {
        assertInitialViewport: true,
      });
      await expectNoHorizontalOverflow(toolbar, "desktop toolbar");
      const attributionBox = await readBox(morningHero, "attribution");
      const kpiBox = await readBox(kpiStrip, "KPIs");
      expect(Math.abs(attributionBox.y - kpiBox.y)).toBeLessThanOrEqual(1);

      const values = await kpiStrip.locator("article > strong").evaluateAll(elements => elements.map(element => ({
        y: element.getBoundingClientRect().y,
        font: getComputedStyle(element).fontSize,
        clipped: element.scrollWidth > element.clientWidth + 1 || element.scrollHeight > element.clientHeight + 1,
      })));
      expect(values).toHaveLength(4);
      expect(Math.max(...values.map(value => value.y)) - Math.min(...values.map(value => value.y))).toBeLessThanOrEqual(1);
      expect(new Set(values.map(value => value.font)).size).toBe(1);
      expect(values.some(value => value.clipped)).toBe(false);

      const toolbarGroups = await toolbar.locator('[data-role="dashboard-home-toolbar-left"], [data-role="dashboard-home-toolbar-right"]').all();
      const left = await readBox(toolbarGroups[0], "toolbar left");
      const right = await readBox(toolbarGroups[1], "toolbar right");
      expect(left.x + left.width <= right.x + 1 || left.y + left.height <= right.y + 1).toBe(true);

      // Exercise the focused state as well as the default, without issuing a search.
      const search = page.getByRole("combobox", { name: "搜索指标、报告或动作入口" });
      await search.focus();
      await expect(search).toBeFocused();
      await expectNoHorizontalOverflow(toolbar, "focused desktop toolbar");
      await search.press("Escape");
      const deferredContent = page.getByTestId("dashboard-home-deferred-content");

      await expect(deferredContent).toBeVisible({ timeout: 60_000 });

      const heroBox = await readBox(hero, "hero");
      const deferredBox = await readBox(deferredContent, "deferred content");

      expect(
        Math.abs(heroBox.x - deferredBox.x),
        "desktop hero and deferred content should share a left edge",
      ).toBeLessThanOrEqual(2);
      expect(
        Math.abs(heroBox.x + heroBox.width - (deferredBox.x + deferredBox.width)),
        "desktop hero and deferred content should share a right edge",
      ).toBeLessThanOrEqual(2);

      for (const name of ["重点持仓与变动", "风险概览", "组合透视"]) {
        const panel = page.getByRole("region", { name, exact: true });
        await expect(panel).toBeVisible();
        await expectNoHorizontalOverflow(panel, name);
      }
    });
  }
});
