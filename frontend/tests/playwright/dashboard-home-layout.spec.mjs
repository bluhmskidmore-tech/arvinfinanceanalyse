import { expect, test } from "@playwright/test";

const VIEWPORTS = {
  mobile360: { width: 360, height: 800 },
  mobile390: { width: 390, height: 844 },
  tablet768: { width: 768, height: 1024 },
  desktop1440: { width: 1440, height: 1000 },
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

async function expectProductSummaryInsideHeroAndBeforeKpis({
  hero,
  kpiStrip,
  productHeadline,
  productStrip,
}) {
  const heroBox = await readBox(hero, "hero");
  const kpiBox = await readBox(kpiStrip, "hero KPI strip");
  const productHeadlineBox = await readBox(productHeadline, "product headline");
  const productStripBox = await readBox(productStrip, "product summary strip");

  expect(
    productHeadlineBox.y + productHeadlineBox.height,
    "product summary should end before the KPI strip starts",
  ).toBeLessThanOrEqual(kpiBox.y + 1);

  expect(
    productHeadlineBox.x,
    "product headline should stay inside the hero on the left edge",
  ).toBeGreaterThanOrEqual(heroBox.x - 1);
  expect(
    productHeadlineBox.x + productHeadlineBox.width,
    "product headline should stay inside the hero on the right edge",
  ).toBeLessThanOrEqual(heroBox.x + heroBox.width + 1);
  expect(
    productHeadlineBox.y,
    "product headline should stay inside the hero on the top edge",
  ).toBeGreaterThanOrEqual(heroBox.y - 1);
  expect(
    productHeadlineBox.y + productHeadlineBox.height,
    "product headline should stay inside the hero on the bottom edge",
  ).toBeLessThanOrEqual(heroBox.y + heroBox.height + 1);

  expect(
    productStripBox.x,
    "product summary strip should stay inside the hero on the left edge",
  ).toBeGreaterThanOrEqual(heroBox.x - 1);
  expect(
    productStripBox.x + productStripBox.width,
    "product summary strip should stay inside the hero on the right edge",
  ).toBeLessThanOrEqual(heroBox.x + heroBox.width + 1);
  expect(
    productStripBox.y + productStripBox.height,
    "product summary strip should stay inside the hero on the bottom edge",
  ).toBeLessThanOrEqual(heroBox.y + heroBox.height + 1);
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

async function expectRequiredSummaryInInitialViewport(
  { kpiStrip, productHeadline },
  viewport,
) {
  const productHeadlineBox = await readBox(productHeadline, "product headline");
  const kpiBox = await readBox(kpiStrip, "hero KPI strip");

  expect(
    productHeadlineBox.y + productHeadlineBox.height,
    "the required product summary should be fully visible in the initial viewport",
  ).toBeLessThanOrEqual(viewport.height + 1);
  expect(
    kpiBox.y,
    "the governed KPI strip should start in the initial viewport",
  ).toBeLessThanOrEqual(viewport.height + 1);
}

async function expectSharedSummaryLayout(page, viewport, options = {}) {
  const handles = await openDashboardHome(page, viewport);
  await expectFourKpis(handles.kpiStrip);
  await expectNoHorizontalOverflow(handles.productHeadline, "product headline");
  await expectNoHorizontalOverflow(handles.productStrip, "product summary strip");
  await expectProductSummaryInsideHeroAndBeforeKpis(handles);

  if (options.assertInitialViewport) {
    await expectRequiredSummaryInInitialViewport(handles, viewport);
  }

  if (options.assertMobileDocumentOverflow) {
    await expectMobileDocumentNoHorizontalOverflow(page);
  }

  return handles;
}

test.describe("dashboard home layout", () => {
  test("keeps the 360 mobile hero summary visible without horizontal overflow", async ({
    page,
  }) => {
    await expectSharedSummaryLayout(page, VIEWPORTS.mobile360, {
      assertInitialViewport: true,
      assertMobileDocumentOverflow: true,
    });
  });

  test("keeps the 390 mobile hero summary visible without horizontal overflow", async ({
    page,
  }) => {
    await expectSharedSummaryLayout(page, VIEWPORTS.mobile390, {
      assertInitialViewport: true,
      assertMobileDocumentOverflow: true,
    });
  });

  test("keeps the 768 tablet hero summary visible without horizontal overflow", async ({
    page,
  }) => {
    await expectSharedSummaryLayout(page, VIEWPORTS.tablet768, {
      assertInitialViewport: true,
    });
  });

  test("aligns desktop hero and deferred content", async ({ page }) => {
    const { hero } = await expectSharedSummaryLayout(page, VIEWPORTS.desktop1440);
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
  });
});
