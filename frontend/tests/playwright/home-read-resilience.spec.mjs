import { expect, test } from "@playwright/test";
import { buildMockApiEnvelope } from "../../src/mocks/mockApiEnvelope.ts";
import { mockHomeSnapshot } from "../../src/mocks/workbench.ts";
import {
  assertNoUnexpectedServiceRequests,
  assertSyntheticReadRequest,
  homeAuxiliaryGetPaths,
  installSyntheticSystemReads,
  SYNTHETIC_READ_GENERATION,
  syntheticReadHeaders,
} from "./fixtures/synthetic-system-reads.mjs";

const REAL_STATE_BASE_URL =
  process.env.MOSS_PLAYWRIGHT_STATE_BASE_URL ??
  (process.env.MOSS_PLAYWRIGHT_USE_WEB_SERVER === "1"
    ? `http://127.0.0.1:${process.env.MOSS_PLAYWRIGHT_STATE_PORT ?? "5889"}`
    : process.env.MOSS_PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5888");

test("a stalled publication handshake has a deadline and the same page can recover", async ({ page }) => {
  await page.clock.install();
  const serviceFixture = await installSyntheticSystemReads(page);
  const reportDate = "2026-08-31";
  const snapshotReads = [];
  await page.route("**/ui/home/snapshot**", async (route) => {
    assertSyntheticReadRequest(route, "/ui/home/snapshot");
    snapshotReads.push({
      reportDate: new URL(route.request().url()).searchParams.get("report_date"),
      generation: route.request().headers()["x-moss-read-generation"],
    });
    await route.fulfill({
      headers: syntheticReadHeaders,
      json: buildMockApiEnvelope("home.snapshot", {
        ...mockHomeSnapshot,
        report_date: reportDate,
        domains_effective_date: { balance_sheet: reportDate, pnl: reportDate },
      }),
    });
  });
  let blockedRoute;
  await page.route("**/api/system-read-publication", (route) => {
    expect(route.request().method()).toBe("GET");
    blockedRoute = route;
  });
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
  await expect.poll(() => snapshotReads.at(-1)).toEqual({
    reportDate,
    generation: SYNTHETIC_READ_GENERATION,
  });
  assertNoUnexpectedServiceRequests(serviceFixture, [
    ...homeAuxiliaryGetPaths,
    "/api/bond-analytics/top-holdings",
  ]);
});
