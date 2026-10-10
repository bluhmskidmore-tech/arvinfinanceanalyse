import { test, expect } from "@playwright/test";

const DESKTOP_VIEWPORTS = [
  { label: "1440", width: 1440, height: 900 },
  { label: "1728", width: 1728, height: 1000 },
  { label: "1920", width: 1920, height: 1080 },
];

// Mock client dates: 2026-03-31 / 2026-02-28 / 2025-12-31. Run with VITE_DATA_SOURCE=mock when backend is down.
const SAMPLE_PATH =
  "/bond-trading-desk?bond_code=230210.IB&report_date=2026-03-31";

async function waitForBondTradingDeskReady(page) {
  await expect(page.locator('[data-testid="bond-trading-desk-page"]')).toBeVisible({
    timeout: 60_000,
  });
  await expect(page.getByTestId("bond-trading-desk-loading")).toHaveCount(0, {
    timeout: 60_000,
  });
  await expect(page.getByTestId("bond-trading-desk-conclusion")).toBeVisible({
    timeout: 60_000,
  });
  await page.waitForLoadState("networkidle", { timeout: 30_000 }).catch(() => undefined);
}

async function openBondTradingDeskDesktop(page, viewport, path = SAMPLE_PATH) {
  await page.setViewportSize(viewport);
  await page.goto(path, { waitUntil: "domcontentloaded" });
  await waitForBondTradingDeskReady(page);
}

test.describe.configure({ mode: "serial" });

test.describe("bond trading desk desktop layout", () => {
  for (const viewport of DESKTOP_VIEWPORTS) {
    test(`keeps conclusion left and decision rail right at ${viewport.label}px`, async ({ page }) => {
      await openBondTradingDeskDesktop(page, viewport);

      const conclusion = page.getByTestId("bond-trading-desk-conclusion");
      const decisionRail = page.getByTestId("bond-trading-desk-decision-rail");
      const metrics = page.getByTestId("bond-trading-desk-metrics");

      await expect(conclusion).toBeVisible({ timeout: 60_000 });
      await expect(decisionRail).toBeVisible({ timeout: 60_000 });
      await expect(metrics).toBeVisible({ timeout: 60_000 });

      const conclusionBox = await conclusion.boundingBox();
      const railBox = await decisionRail.boundingBox();
      expect(conclusionBox).not.toBeNull();
      expect(railBox).not.toBeNull();

      expect(conclusionBox.x).toBeLessThan(railBox.x);
      expect(Math.abs(conclusionBox.y - railBox.y)).toBeLessThan(48);
    });
  }

  test("stacks conclusion before decision rail on mobile", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(SAMPLE_PATH, { waitUntil: "domcontentloaded" });
    await waitForBondTradingDeskReady(page);

    const conclusion = page.getByTestId("bond-trading-desk-conclusion");
    const decisionRail = page.getByTestId("bond-trading-desk-decision-rail");
    await expect(conclusion).toBeVisible();
    await expect(decisionRail).toBeVisible();

    const conclusionBox = await conclusion.boundingBox();
    const railBox = await decisionRail.boundingBox();
    expect(conclusionBox).not.toBeNull();
    expect(railBox).not.toBeNull();
    expect(conclusionBox.y).toBeLessThan(railBox.y);
  });

  test("prompts for bond_code when query param is missing", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/bond-trading-desk", { waitUntil: "domcontentloaded" });
    await expect(page.locator('[data-testid="bond-trading-desk-page"]')).toBeVisible({
      timeout: 60_000,
    });
    await expect(page.getByTestId("bond-trading-desk-missing-bond")).toBeVisible();
    await expect(page.getByTestId("bond-trading-desk-conclusion")).toHaveCount(0);
  });
});
