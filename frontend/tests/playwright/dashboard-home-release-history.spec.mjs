import { expect, test } from "@playwright/test";

test.describe("dashboard home release history disclosure", () => {
  test("keeps every history row available without growing the homepage by default", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/", { waitUntil: "domcontentloaded" });

    const disclosure = page.getByTestId("dashboard-home-release-history-disclosure");
    const summary = disclosure.locator("summary");
    const content = disclosure.locator(":scope > div");
    const rows = disclosure.getByTestId("dashboard-home-release-history-row");

    const deferredSentinel = page.getByTestId("dashboard-home-deferred-sentinel");
    await expect(deferredSentinel).toBeAttached();
    await deferredSentinel.scrollIntoViewIfNeeded();
    await expect(disclosure).toBeVisible({ timeout: 60_000 });
    await disclosure.scrollIntoViewIfNeeded();
    await expect(disclosure).not.toHaveAttribute("open");
    await expect(content).toBeHidden();

    await expect.poll(() => rows.count(), { timeout: 60_000 }).toBeGreaterThan(0);
    const rowCount = await rows.count();
    await expect(summary).toContainText(`共 ${rowCount} 项`);

    const collapsedBox = await disclosure.boundingBox();
    expect(collapsedBox?.height).toBeLessThanOrEqual(52);

    await summary.click();
    await expect(disclosure).toHaveAttribute("open", "");
    await expect(content).toBeVisible();
    await expect(rows.first()).toBeVisible();
    expect(await rows.count()).toBe(rowCount);

    const expandedBox = await disclosure.boundingBox();
    expect(expandedBox?.height).toBeGreaterThan(collapsedBox?.height ?? 0);
    expect(expandedBox?.height).toBeLessThanOrEqual(520);

    await rows.last().scrollIntoViewIfNeeded();
    await expect(rows.last()).toBeVisible();
  });
});
