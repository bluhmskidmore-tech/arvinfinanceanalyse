import { test, expect } from "@playwright/test";

test.describe("workbench section subnav", () => {
  test("reveals every market section link by keyboard inside the mobile viewport", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/macro-toolkit", { waitUntil: "networkidle" });

    const links = page.locator('[data-testid="workbench-section-subnav"] a');
    await expect(links.first()).toBeVisible();

    const nav = page.locator('[data-testid="workbench-section-subnav"]');
    const navBox = await nav.boundingBox();
    expect(Math.round(navBox.x)).toBeGreaterThanOrEqual(0);
    expect(Math.round(navBox.x + navBox.width)).toBeLessThanOrEqual(390);
    // 75aa35afdd deliberately uses a narrow-screen scroll rail. Every item must
    // still become visible through keyboard focus without widening the page.
    await links.first().focus();
    for (let index = 0; index < await links.count(); index += 1) {
      const link = links.nth(index);
      if (index > 0) await page.keyboard.press("Tab");
      await expect(link).toBeFocused();
      await expect(link).toBeInViewport();
      const rect = await link.boundingBox();
      const box = { text: await link.innerText(), left: Math.round(rect.x), right: Math.round(rect.x + rect.width) };
      expect(box.left, `${box.text} starts outside the viewport`).toBeGreaterThanOrEqual(0);
      expect(box.right, `${box.text} ends outside the viewport`).toBeLessThanOrEqual(390);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    }
  });
});
