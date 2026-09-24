import { expect, test } from "@playwright/test";

test.describe("dashboard home deferred reveal", () => {
  test("reveals below-fold content when the desktop layout scroll container moves", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("dashboard-home-page")).toBeVisible({
      timeout: 60_000,
    });
    await expect(page.getByTestId("dashboard-home-hero")).toBeVisible({
      timeout: 60_000,
    });

    const workGrid = page.getByTestId("dashboard-home-work-grid");
    await expect(workGrid).toHaveCount(0);

    await page.getByTestId("dashboard-home-scroll-root").evaluate((element) => {
      if (!(element instanceof HTMLElement)) {
        throw new Error("dashboard home scroll root must be an HTMLElement");
      }
      element.scrollTop = element.scrollHeight;
      element.dispatchEvent(new Event("scroll"));
    });

    await expect(workGrid).toBeVisible({ timeout: 60_000 });
  });
});
