import { test, expect } from "@playwright/test";

test.describe("dashboard home responsive order", () => {
  test("shows the main decision hero before the decision rail on mobile", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/", { waitUntil: "networkidle" });

    const hero = page.locator('[data-testid="dashboard-home-hero"]');
    const rail = page.locator('[data-testid="dashboard-home-decision-rail"]');
    await expect(hero).toBeVisible();
    await expect(rail).toBeVisible();

    const heroBox = await hero.boundingBox();
    const railBox = await rail.boundingBox();
    expect(heroBox.y).toBeLessThan(railBox.y);
  });
});
