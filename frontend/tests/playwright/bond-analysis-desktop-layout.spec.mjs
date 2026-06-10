import { test, expect } from "@playwright/test";

const DESKTOP_VIEWPORTS = [
  { label: "1440", width: 1440, height: 900 },
  { label: "1728", width: 1728, height: 1000 },
  { label: "1920", width: 1920, height: 1080 },
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
    test(`keeps conclusion left and decision rail right at ${viewport.label}px`, async ({ page }) => {
      await openBondAnalysisDesktop(page, viewport);

      const conclusion = page.getByTestId("bond-analysis-cockpit-conclusion");
      const decisionRail = page.getByTestId("bond-analysis-decision-rail");
      const decisionTrust = page.getByTestId("bond-analysis-decision-trust");
      const nextAction = page.getByTestId("bond-analysis-decision-next-action");

      await expect(conclusion).toBeVisible();
      await expect(decisionRail).toBeVisible();
      await expect(decisionTrust).toBeVisible();
      await expect(nextAction).toBeVisible();

      const heroAside = page.getByTestId("bond-analysis-hero-aside");
      const conclusionBox = await conclusion.boundingBox();
      const asideBox = await heroAside.boundingBox();
      expect(conclusionBox).not.toBeNull();
      expect(asideBox).not.toBeNull();

      expect(conclusionBox.x).toBeLessThan(asideBox.x);
      expect(Math.abs(conclusionBox.y - asideBox.y)).toBeLessThan(24);

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
