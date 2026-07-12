import { test, expect } from "@playwright/test";

const DESKTOP_VIEWPORTS = [
  { name: "1280", width: 1280, height: 720 },
  { name: "1440", width: 1440, height: 720 },
];

const FIRST_SCREEN_SELECTORS = [
  '[data-testid="product-category-contract-hero"]',
  '[data-testid="product-category-formal-readiness-band"]',
  '[data-testid="product-category-unified-controls"]',
  '[data-testid="product-category-data-status-strip"]',
  '[data-testid="product-category-section-nav"]',
];

for (const viewport of DESKTOP_VIEWPORTS) {
  test(`desktop decision cockpit stays complete at ${viewport.name}px`, async ({ page }, testInfo) => {
    const consoleErrors = [];
    page.on("console", (message) => {
      if (message.type() === "error") {
        consoleErrors.push(message.text());
      }
    });

    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.goto("/product-category-pnl", { waitUntil: "networkidle" });

    await expect(page.locator('[data-testid="product-category-page"]')).toBeVisible();
    await expect(page.locator('[data-testid="product-category-formal-readiness-band"]')).toBeVisible();
    await expect(page.locator('[data-testid="product-category-core-metric"]')).toHaveCount(5);
    await expect(page.locator('[data-testid="product-category-driver-item"]')).toHaveCount(3);
    await expect(page.locator('[data-testid="product-category-next-analysis-preview"]')).toBeHidden();

    for (const selector of FIRST_SCREEN_SELECTORS) {
      const box = await page.locator(selector).boundingBox();
      expect(box, `${selector} should have a desktop layout box`).not.toBeNull();
      expect(box.y, `${selector} should start inside the first screen`).toBeLessThan(viewport.height);
      expect(
        box.y + box.height,
        `${selector} should remain completely visible inside the first screen`,
      ).toBeLessThanOrEqual(viewport.height);
    }

    const attributionBox = await page
      .locator('[data-testid="product-category-attribution-workbench"]')
      .boundingBox();
    expect(attributionBox).not.toBeNull();
    expect(attributionBox.y, "the next analysis region should peek into the first screen").toBeLessThan(
      viewport.height,
    );
    expect(
      attributionBox.y + attributionBox.height,
      "only the beginning of the next analysis region should be visible",
    ).toBeGreaterThan(viewport.height);

    const viewportMetrics = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }));
    expect(viewportMetrics.scrollWidth).toBeLessThanOrEqual(viewportMetrics.clientWidth);
    expect(consoleErrors).toEqual([]);

    await page.screenshot({
      path: testInfo.outputPath(`product-category-pnl-desktop-${viewport.name}.png`),
      fullPage: false,
    });
  });
}
