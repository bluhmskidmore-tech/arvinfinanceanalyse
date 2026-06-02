import { test, expect } from "@playwright/test";

test.describe("workbench section subnav", () => {
  test("keeps market section links inside the mobile viewport", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/macro-toolkit", { waitUntil: "networkidle" });

    const links = page.locator('[data-testid="workbench-section-subnav"] a');
    await expect(links.first()).toBeVisible();

    const linkBoxes = await links.evaluateAll((items) =>
      items.map((item) => {
        const rect = item.getBoundingClientRect();
        return {
          text: item.textContent?.trim() ?? "",
          left: Math.round(rect.left),
          right: Math.round(rect.right),
        };
      }),
    );

    for (const box of linkBoxes) {
      expect(box.left, `${box.text} starts outside the viewport`).toBeGreaterThanOrEqual(0);
      expect(box.right, `${box.text} ends outside the viewport`).toBeLessThanOrEqual(390);
    }
  });
});
