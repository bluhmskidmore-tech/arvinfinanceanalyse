import { expect, test } from "@playwright/test";

async function openDashboard(page) {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  const dashboard = page.getByTestId("dashboard-home-page");
  await expect(dashboard).toBeVisible({ timeout: 60_000 });
  return dashboard;
}

test.describe("dashboard home motion contract", () => {
  test("keeps the retired ambient canvas out of the current Option Two home", async ({
    page,
  }) => {
    await openDashboard(page);
    await expect(page.getByTestId("dashboard-home-ambient-canvas")).toHaveCount(0);
  });

  test("has no long-running infinite animation under prefers-reduced-motion", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    const dashboard = await openDashboard(page);
    const activeInfiniteAnimations = await dashboard.evaluate((element) =>
      element
        .getAnimations({ subtree: true })
        .filter((animation) => {
          const timing = animation.effect?.getComputedTiming();
          return (
            animation.playState === "running" &&
            timing?.iterations === Infinity &&
            typeof timing.duration === "number" &&
            timing.duration > 10
          );
        })
        .length,
    );

    expect(activeInfiniteAnimations).toBe(0);
  });
});
