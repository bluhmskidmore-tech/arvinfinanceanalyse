import { test, expect } from "@playwright/test";

test.describe("dashboard home responsive order", () => {
  test("shows the main decision hero before the decision rail on mobile", async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 800 });
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.locator('[data-testid="dashboard-home-page"]')).toBeVisible({
      timeout: 60_000,
    });

    const hero = page.locator('[data-testid="dashboard-home-hero"]');
    const rail = page.locator('[data-testid="dashboard-home-decision-rail"]');
    const kpiStrip = page.locator('[data-testid="dashboard-home-hero-kpi-strip"]');
    const productHeadline = page.locator('[data-testid="dashboard-home-product-category-headline"]');
    const sourceSummary = page.locator(
      '[data-testid="dashboard-home-source-mobile-summary"]',
    );
    await expect(hero).toBeVisible({ timeout: 60_000 });
    await expect(rail).toBeVisible();
    await expect(kpiStrip).toBeVisible();
    await expect(productHeadline).toBeVisible();
    await expect(sourceSummary).toBeVisible();

    const decisionCopy = page.locator(
      '[data-testid="dashboard-home-morning-hero"] [class*="dhApiDecisionBody"] p',
    );
    await expect(decisionCopy).toBeVisible();
    const decisionCopyBox = await decisionCopy.boundingBox();
    expect(decisionCopyBox.height).toBeGreaterThan(24);

    const visibleKpiLabels = await kpiStrip
      .locator('[class*="dhApiKpiLabel"]')
      .evaluateAll((labels) =>
        labels.filter((label) => {
          const rect = label.getBoundingClientRect();
          return rect.width > 0 && rect.height > 0;
        }).length,
      );
    expect(visibleKpiLabels).toBe(4);

    const mobileStatusWidth = await page
      .locator('[data-testid="dashboard-home-data-status"]')
      .evaluate((element) => ({
        clientWidth: element.clientWidth,
        scrollWidth: element.scrollWidth,
      }));
    expect(mobileStatusWidth.scrollWidth).toBeLessThanOrEqual(mobileStatusWidth.clientWidth + 1);

    const heroBox = await hero.boundingBox();
    const railBox = await rail.boundingBox();
    const kpiBox = await kpiStrip.boundingBox();
    const productBox = await productHeadline.boundingBox();
    expect(heroBox.y).toBeLessThan(railBox.y);
    const mobileGeometry = await page.evaluate(() => {
      const selectors = {
        toolbar: '[class*="dhTopbar"]',
        report: '[data-testid="dashboard-home-report-identity"]',
        decision: '[data-testid="dashboard-home-morning-hero"]',
        sources: '[aria-label="来源核验"]',
        kpis: '[data-testid="dashboard-home-hero-kpi-strip"]',
      };
      return Object.fromEntries(Object.entries(selectors).map(([key, selector]) => {
        const rect = document.querySelector(selector)?.getBoundingClientRect();
        return [key, rect ? { y: Math.round(rect.y), height: Math.round(rect.height) } : null];
      }));
    });
    const firstProductValue = productHeadline.locator("strong").first();
    await expect(firstProductValue).toBeVisible();
    const firstProductValueBox = await firstProductValue.boundingBox();
    expect(
      firstProductValueBox.y + firstProductValueBox.height,
      `mobile geometry: ${JSON.stringify(mobileGeometry)}`,
    ).toBeLessThanOrEqual(800);
    expect(kpiBox.y, `mobile geometry: ${JSON.stringify(mobileGeometry)}`).toBeLessThan(800);
    expect(productBox.y, `mobile geometry: ${JSON.stringify(mobileGeometry)}`).toBeLessThan(800);

    const firstScreenWidths = await Promise.all([
      kpiStrip.evaluate((element) => ({
        clientWidth: element.clientWidth,
        scrollWidth: element.scrollWidth,
      })),
      productHeadline.getByTestId("dashboard-home-product-category-strip").evaluate((element) => ({
        clientWidth: element.clientWidth,
        scrollWidth: element.scrollWidth,
      })),
    ]);
    for (const width of firstScreenWidths) {
      expect(width.scrollWidth).toBeLessThanOrEqual(width.clientWidth + 1);
    }

    const visibleKpiCards = await kpiStrip.locator("article").evaluateAll((cards) =>
      cards.filter((card) => {
        const rect = card.getBoundingClientRect();
        return rect.left >= 0 && rect.right <= 360 && rect.top >= 0 && rect.bottom <= 800;
      }).length,
    );
    expect(visibleKpiCards).toBe(4);

    const governedKpiValues = await kpiStrip.locator("article strong").allTextContents();
    expect(governedKpiValues).toHaveLength(4);
    expect(governedKpiValues.every((value) => value.trim() && value.trim() !== "—")).toBe(true);

    const visibleSourceRows = await page
      .locator('[aria-label="来源核验"] [class*="dhApiSourceRow"]')
      .evaluateAll((rows) =>
        rows.filter((row) => getComputedStyle(row).display !== "none").length,
      );
    expect(visibleSourceRows).toBe(6);

    const clippedValues = await page
      .locator('[data-testid="dashboard-home-hero-kpi-strip"] strong')
      .evaluateAll((values) =>
        values
          .filter((value) => value.getBoundingClientRect().width > 0)
          .map((value) => ({
            text: value.textContent,
            clientWidth: value.clientWidth,
            scrollWidth: value.scrollWidth,
          }))
          .filter((value) => value.scrollWidth > value.clientWidth + 1),
      );
    expect(clippedValues).toEqual([]);

    const inaccessibleProductDetails = await productHeadline.locator("small").evaluateAll((details) =>
      details.map((detail) => {
        const style = getComputedStyle(detail);
        return {
          text: detail.textContent,
          fontSize: Number.parseFloat(style.fontSize),
          whiteSpace: style.whiteSpace,
          clientWidth: detail.clientWidth,
          scrollWidth: detail.scrollWidth,
        };
      }).filter((detail) =>
        detail.fontSize < 12 ||
        detail.whiteSpace === "nowrap" ||
        detail.scrollWidth > detail.clientWidth + 1
      ),
    );
    expect(inaccessibleProductDetails).toEqual([]);

    const sourceStrip = page.getByRole("region", {
      name: "来源核验明细，可用左右方向键横向浏览",
    });
    await sourceStrip.evaluate((element) => {
      element.scrollLeft = 0;
    });
    await sourceStrip.focus();
    await expect(sourceStrip).toBeFocused();
    expect(await sourceStrip.evaluate((element) => element.scrollLeft)).toBe(0);
    await page.keyboard.press("ArrowRight");
    await expect
      .poll(() => sourceStrip.evaluate((element) => element.scrollLeft))
      .toBeGreaterThan(0);
  });

  test("keeps the required product-category headline in the compact-tablet first viewport", async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.locator('[data-testid="dashboard-home-page"]')).toBeVisible({
      timeout: 60_000,
    });

    const productHeadline = page.locator('[data-testid="dashboard-home-product-category-headline"]');
    await expect(productHeadline).toBeVisible();
    const productBox = await productHeadline.boundingBox();
    const firstProductValueBox = await productHeadline.locator("strong").first().boundingBox();
    expect(productBox.y).toBeLessThan(1024);
    expect(firstProductValueBox.y + firstProductValueBox.height).toBeLessThanOrEqual(1024);

    const firstScreenWidths = await page.evaluate(() => {
      const selectors = [
        '[data-testid="dashboard-home-hero-kpi-strip"]',
        '[data-testid="dashboard-home-product-category-strip"]',
      ];
      return selectors.map((selector) => {
        const element = document.querySelector(selector);
        return { clientWidth: element.clientWidth, scrollWidth: element.scrollWidth };
      });
    });
    for (const width of firstScreenWidths) {
      expect(width.scrollWidth).toBeLessThanOrEqual(width.clientWidth + 1);
    }

    const sourceDetail = page.locator('[class*="dhApiSourceGrid"]');
    await expect(sourceDetail).toHaveAttribute("aria-label", "来源核验明细");
    await expect(sourceDetail).not.toHaveAttribute("tabindex");
  });

  test("keeps the primary product value visible at the wider mobile breakpoint", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.locator('[data-testid="dashboard-home-page"]')).toBeVisible({
      timeout: 60_000,
    });

    const productHeadline = page.locator('[data-testid="dashboard-home-product-category-headline"]');
    const firstProductValue = productHeadline.locator("strong").first();
    await expect(firstProductValue).toBeVisible();
    const firstProductValueBox = await firstProductValue.boundingBox();
    expect(firstProductValueBox.y + firstProductValueBox.height).toBeLessThanOrEqual(844);
  });

  test("aligns desktop evidence to the main column and spans the product summary", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.locator('[data-testid="dashboard-home-page"]')).toBeVisible({
      timeout: 60_000,
    });

    const primary = page.locator('[class*="dhPrimaryMain"]');
    const deferred = page.locator('[data-testid="dashboard-home-deferred-content"]');
    const hero = page.locator('[data-testid="dashboard-home-hero"]');
    const product = page.locator('[data-testid="dashboard-home-product-category-headline"]');
    await expect(primary).toBeVisible();
    await expect(deferred).toBeAttached();
    await expect(hero).toBeVisible();
    await expect(product).toBeVisible();

    const primaryBox = await primary.boundingBox();
    const deferredBox = await deferred.boundingBox();
    const heroBox = await hero.boundingBox();
    const productBox = await product.boundingBox();

    expect(Math.abs(primaryBox.x - deferredBox.x)).toBeLessThanOrEqual(2);
    expect(Math.abs(primaryBox.width - deferredBox.width)).toBeLessThanOrEqual(2);
    expect(Math.abs(heroBox.x - productBox.x)).toBeLessThanOrEqual(2);
    expect(Math.abs(heroBox.width - productBox.width)).toBeLessThanOrEqual(3);
  });
});
