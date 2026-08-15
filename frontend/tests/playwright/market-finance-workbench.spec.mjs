import { test, expect } from "@playwright/test";

const rootSelector = '[data-testid="market-finance-workbench"]';
const kpiSelector = '[data-testid="market-finance-kpis"]';
const deepContentSelector = '[data-testid="market-finance-evidence-matrix"]';

function collectConsoleErrors(page) {
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(`console: ${message.text()}`);
    }
  });
  page.on("pageerror", (error) => {
    errors.push(`pageerror: ${error.message}`);
  });
  return errors;
}

async function openMarketFinance(page) {
  await page.goto("/market-finance", { waitUntil: "domcontentloaded" });
  await expect(page.locator(rootSelector)).toBeVisible();
  await expect(page.locator('[data-testid="market-finance-data-status"]')).toBeVisible();
  await expect(page.locator(kpiSelector)).toBeVisible();
  await expect(page.getByTestId("market-finance-kpi-asset-market-value")).toContainText("亿元");
  await page.waitForLoadState("load").catch(() => undefined);
}

async function readLayout(page) {
  return page.evaluate(({ rootSelector: rootQuery, kpiSelector: kpiQuery, deepSelector }) => {
    const root = document.querySelector(rootQuery);
    const kpis = document.querySelector(kpiQuery);
    const conclusion = root?.querySelector(
      ".moss-page-v2-decision-hero__conclusion",
    );
    const trustStatus = root?.querySelector(
      '[data-testid="market-finance-data-status"]',
    );
    const deepContent = root?.querySelector(deepSelector);
    const cards = [...(kpis?.querySelectorAll(".moss-page-v2-kpi-metric") ?? [])];
    const rect = (element) => {
      if (!element) {
        return null;
      }
      const box = element.getBoundingClientRect();
      return {
        top: box.top,
        right: box.right,
        bottom: box.bottom,
        left: box.left,
        width: box.width,
        height: box.height,
      };
    };
    const conclusionRect = rect(conclusion);
    const trustStatusRect = rect(trustStatus);
    const deepContentRect = rect(deepContent);
    const viewportWidth = document.documentElement.clientWidth;
    const viewportHeight = window.innerHeight;
    // 2026-08-13 98f190d0 起，mock 模式的固定数据模式横幅（.moss-data-mode-ribbon）
    // 由外壳 padding-top 让位，页面内容整体下移横幅高度。首屏预算按内容坐标核算：
    // 量到的 rect 需先扣除该固定 chrome 高度（real 模式无横幅，恒为 0）。
    const dataModeRibbon = document.querySelector(".moss-data-mode-ribbon");
    const fixedChromeHeight = dataModeRibbon
      ? Math.max(0, dataModeRibbon.getBoundingClientRect().height)
      : 0;

    return {
      viewportWidth,
      viewportHeight,
      fixedChromeHeight,
      documentScrollWidth: Math.max(
        document.documentElement.scrollWidth,
        document.body?.scrollWidth ?? 0,
      ),
      kpiRect: rect(kpis),
      cardRects: cards.map(rect),
      conclusionRect,
      trustStatusRect,
      deepContentRect,
      conclusionBeforeDeep:
        Boolean(conclusion && deepContent) &&
        Boolean(
          conclusion.compareDocumentPosition(deepContent) &
            Node.DOCUMENT_POSITION_FOLLOWING,
        ),
      trustStatusBeforeDeep:
        Boolean(trustStatus && deepContent) &&
        Boolean(
          trustStatus.compareDocumentPosition(deepContent) &
            Node.DOCUMENT_POSITION_FOLLOWING,
        ),
    };
  }, { rootSelector, kpiSelector, deepSelector: deepContentSelector });
}

function expectNoHorizontalOverflow(layout) {
  expect(
    layout.documentScrollWidth,
    "the page should not create document-level horizontal overflow",
  ).toBeLessThanOrEqual(layout.viewportWidth + 1);
}

function expectRectInsideViewport(rect, layout, label, bottomInset = 0) {
  expect(rect, `${label} should be rendered`).not.toBeNull();
  expect(rect.width, `${label} should have width`).toBeGreaterThan(0);
  expect(rect.height, `${label} should have height`).toBeGreaterThan(0);
  expect(rect.left, `${label} should start inside the viewport`).toBeGreaterThanOrEqual(-1);
  expect(rect.right, `${label} should end inside the viewport`).toBeLessThanOrEqual(
    layout.viewportWidth + 1,
  );
  expect(rect.top, `${label} should start inside the viewport`).toBeGreaterThanOrEqual(-1);
  // 内容坐标核算：扣除 mock 横幅固定 chrome 后，首屏内容预算保持原有严格度
  //（页面自身再长高 >~2.7px 仍会失败）。
  expect(
    rect.bottom - layout.fixedChromeHeight,
    `${label} should end inside the first-screen content budget (net of the fixed data-mode ribbon)`,
  ).toBeLessThanOrEqual(layout.viewportHeight - bottomInset);
}

test("market-finance mock 1440x900 keeps the KPI band in the first screen", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const consoleErrors = collectConsoleErrors(page);

  await openMarketFinance(page);
  const layout = await readLayout(page);

  expectNoHorizontalOverflow(layout);
  expectRectInsideViewport(layout.kpiRect, layout, "KPI band", 8);
  expect(layout.cardRects).toHaveLength(4);
  layout.cardRects.forEach((cardRect, index) => {
    expectRectInsideViewport(cardRect, layout, `KPI card ${index + 1}`, 8);
  });
  expect(consoleErrors).toEqual([]);

  await page.screenshot({
    path: testInfo.outputPath("market-finance-1440x900.png"),
    fullPage: false,
  });
});

for (const viewport of [
  { width: 768, height: 900 },
  { width: 390, height: 844 },
]) {
  test(`market-finance ${viewport.width}px keeps trust cues before deep content`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize(viewport);
    const consoleErrors = collectConsoleErrors(page);

    await openMarketFinance(page);
    const layout = await readLayout(page);

    expectNoHorizontalOverflow(layout);
    expect(layout.conclusionBeforeDeep).toBe(true);
    expect(layout.trustStatusBeforeDeep).toBe(true);
    expect(layout.conclusionRect?.top).toBeLessThanOrEqual(
      (layout.deepContentRect?.top ?? Number.POSITIVE_INFINITY) + 1,
    );
    expect(layout.trustStatusRect?.top).toBeLessThanOrEqual(
      (layout.deepContentRect?.top ?? Number.POSITIVE_INFINITY) + 1,
    );
    expect(consoleErrors).toEqual([]);

    await page.screenshot({
      path: testInfo.outputPath(`market-finance-${viewport.width}px.png`),
      fullPage: false,
    });
  });
}
