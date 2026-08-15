import { test, expect } from "@playwright/test";

const DESKTOP_VIEWPORTS = [
  { label: "1280", width: 1280, height: 900 },
  { label: "1440", width: 1440, height: 900 },
];

const READY_SELECTOR = '[data-testid="bond-analysis-cockpit-conclusion"]';

async function openBondAnalysisDesktop(page, viewport) {
  await page.setViewportSize(viewport);
  await page.goto("/bond-analysis", { waitUntil: "domcontentloaded" });
  await expect(page.locator('[data-testid="bond-analysis-overview"]')).toBeVisible({ timeout: 60_000 });
  await expect(page.locator(READY_SELECTOR)).toBeVisible({ timeout: 60_000 });
  await page.waitForLoadState("networkidle", { timeout: 30_000 }).catch(() => undefined);
}

test.describe("bond analysis desktop first-screen layout", () => {
  for (const viewport of DESKTOP_VIEWPORTS) {
    test(`keeps the conclusion and KPI ribbon in the primary flow at ${viewport.label}px`, async ({ page }) => {
      await openBondAnalysisDesktop(page, viewport);

      const hero = page.getByTestId("bond-analysis-reference-topbar");
      const conclusion = page.getByTestId("bond-analysis-cockpit-conclusion");
      const kpiRibbon = page.getByTestId("bond-analysis-kpi-ribbon");
      const decisionRail = page.getByTestId("bond-analysis-decision-rail");
      const decisionTrust = page.getByTestId("bond-analysis-decision-trust");
      const nextAction = page.getByTestId("bond-analysis-decision-next-action");

      await expect(hero).toBeVisible();
      await expect(conclusion).toBeVisible();
      await expect(kpiRibbon).toBeVisible();
      await expect(decisionRail).toBeVisible();
      await expect(decisionTrust).toBeVisible();
      await expect(nextAction).toBeVisible();

      const heroBox = await hero.boundingBox();
      const conclusionBox = await conclusion.boundingBox();
      const kpiBox = await kpiRibbon.boundingBox();
      expect(heroBox).not.toBeNull();
      expect(conclusionBox).not.toBeNull();
      expect(kpiBox).not.toBeNull();

      expect(conclusionBox.x).toBeGreaterThanOrEqual(heroBox.x);
      expect(conclusionBox.x + conclusionBox.width).toBeLessThanOrEqual(heroBox.x + heroBox.width);
      expect(conclusionBox.width).toBeGreaterThan(heroBox.width * 0.9);
      expect(kpiBox.y).toBeGreaterThan(heroBox.y + heroBox.height);
      expect(Math.abs(kpiBox.x - heroBox.x)).toBeLessThan(2);
      expect(Math.abs(kpiBox.width - heroBox.width)).toBeLessThanOrEqual(2);

      const headline = conclusion.locator(".heroHeadline, [class*='heroHeadline']").first();
      if ((await headline.count()) > 0) {
        await expect(headline).toBeVisible();
        const headlineText = (await headline.textContent())?.trim() ?? "";
        expect(headlineText.length).toBeGreaterThan(0);
      }
    });
  }

  test("stacks conclusion before decision rail on mobile", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/bond-analysis", { waitUntil: "domcontentloaded" });
    await expect(page.locator(READY_SELECTOR)).toBeVisible({ timeout: 60_000 });

    const conclusion = page.getByTestId("bond-analysis-cockpit-conclusion");
    const decisionRail = page.getByTestId("bond-analysis-decision-rail");
    await expect(conclusion).toBeVisible();
    await expect(decisionRail).toBeVisible();

    const conclusionBox = await conclusion.boundingBox();
    const railBox = await decisionRail.boundingBox();
    expect(conclusionBox).not.toBeNull();
    expect(railBox).not.toBeNull();
    expect(conclusionBox.y).toBeLessThan(railBox.y);
  });
});
