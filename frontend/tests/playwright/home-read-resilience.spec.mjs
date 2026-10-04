import { expect, test } from "@playwright/test";

const REAL_STATE_BASE_URL =
  process.env.MOSS_PLAYWRIGHT_STATE_BASE_URL ??
  (process.env.MOSS_PLAYWRIGHT_USE_WEB_SERVER === "1"
    ? `http://127.0.0.1:${process.env.MOSS_PLAYWRIGHT_STATE_PORT ?? "5889"}`
    : process.env.MOSS_PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5888");

test("a stalled publication handshake has a deadline and the same page can recover", async ({ page }) => {
  await page.clock.install();
  let blockedRoute;
  await page.route("**/api/system-read-publication", (route) => { blockedRoute = route; });
  await page.goto(new URL("/?report_date=2026-08-31", REAL_STATE_BASE_URL).toString(), {
    waitUntil: "domcontentloaded",
  });
  await expect.poll(() => Boolean(blockedRoute)).toBe(true);
  await page.clock.runFor(15_100);
  await expect(page.getByTestId("workbench-route-error-page")).toBeVisible();
  const reload = page.getByRole("link", { name: "重新加载当前页" });
  await expect(reload).toHaveAttribute("href", "/?report_date=2026-08-31");
  await expect(page.getByRole("link", { name: "返回工作台首页", exact: true })).toBeVisible();

  await page.unroute("**/api/system-read-publication");
  await blockedRoute.abort().catch(() => {});
  await page.clock.resume();
  await reload.click();
  await expect(page.getByTestId("dashboard-home-page")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("workbench-route-error-page")).toHaveCount(0);
});
