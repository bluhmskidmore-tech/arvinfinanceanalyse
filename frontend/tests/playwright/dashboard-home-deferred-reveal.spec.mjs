import { expect, test } from "@playwright/test";

test.describe("dashboard home deferred reveal", () => {
  test("reveals below-fold content already within the desktop viewport", async ({
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
    await expect(workGrid).toBeVisible({ timeout: 60_000 });
  });

  test("keeps small-screen content deferred during light input and loads it when scrolling near the boundary", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 800, height: 480 });
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("dashboard-home-hero")).toBeVisible({
      timeout: 60_000,
    });

    const scrollRoot = page.getByTestId("dashboard-home-scroll-root");
    const sentinel = page.getByTestId("dashboard-home-deferred-sentinel");
    const workGrid = page.getByTestId("dashboard-home-work-grid");
    const distanceFromScrollViewport = () => sentinel.evaluate((element) => {
      const root = document.querySelector('[data-testid="dashboard-home-scroll-root"]');
      if (!(root instanceof HTMLElement)) {
        throw new Error("dashboard home scroll root must be an HTMLElement");
      }
      return element.getBoundingClientRect().top - root.getBoundingClientRect().bottom;
    });

    expect(await distanceFromScrollViewport()).toBeGreaterThan(200);
    await scrollRoot.hover();
    await page.mouse.wheel(0, 24);
    await page.keyboard.press("ArrowDown");
    await expect.poll(() => scrollRoot.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
    expect(await distanceFromScrollViewport()).toBeGreaterThan(200);
    // Cross the observer's initial delay while the boundary stays outside its margin.
    await page.waitForTimeout(1_100);
    await expect(workGrid).toHaveCount(0);

    await page.mouse.wheel(0, Math.ceil(await distanceFromScrollViewport()) - 100);
    await expect(workGrid).toHaveCount(1);
    await page.mouse.wheel(0, 300);
    await expect(workGrid).toBeVisible({ timeout: 60_000 });
  });
});
