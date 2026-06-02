import { test, expect } from "@playwright/test";

const realStockSmokeEnabled = process.env.MOSS_PLAYWRIGHT_REAL_STOCK_SMOKE === "1";
const eventsMonitoringTitle = "\u5173\u952e\u4e8b\u4ef6\u4e0e\u76d1\u63a7";
const themeBreakoutPausedText =
  "\u5e02\u573a\u8fc7\u70ed\u95e8\u63a7\u4e0b\u6682\u505c\u9898\u6750\u89c2\u5bdf";
const themeBreakoutReplayText = "\u5386\u53f2\u56de\u653e\u663e\u793a\u8be5\u6876\u62d6\u7d2f";
const sourceVersionText = "\u6765\u6e90\u7248\u672c";
const ruleVersionText = "\u89c4\u5219\u7248\u672c";
const qualityText = "\u8d28\u91cf";
const channelText = "\u901a\u9053";

test.describe("stock analysis real-data browser smoke", () => {
  test.skip(!realStockSmokeEnabled, "Set MOSS_PLAYWRIGHT_REAL_STOCK_SMOKE=1 to run real stock-analysis smoke.");

  test("renders real Livermore blockers without backend English leaks", async ({ page, request }) => {
    const consoleMessages = [];
    const failedRequests = [];

    page.on("console", (message) => {
      if (["error", "warning"].includes(message.type())) {
        consoleMessages.push(`${message.type()}: ${message.text()}`);
      }
    });
    page.on("requestfailed", (req) => {
      failedRequests.push(`${req.method()} ${req.url()} ${req.failure()?.errorText ?? ""}`);
    });

    const strategyResponse = await request.get("/ui/market-data/livermore");
    expect(strategyResponse.ok()).toBe(true);
    const strategyEnvelope = await strategyResponse.json();
    const themeBlocker = strategyEnvelope.result?.unsupported_outputs?.find(
      (item) => item.key === "theme_breakout",
    );

    await page.goto("/stock-analysis", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("stock-analysis-page")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("stock-analysis-events-monitoring")).toContainText(eventsMonitoringTitle, {
      timeout: 60_000,
    });
    await page.waitForLoadState("networkidle", { timeout: 60_000 }).catch(() => undefined);

    const bodyText = await page.locator("body").innerText();
    const backendEnglishFragments = [
      "Theme breakout execution is paused",
      "concept membership table pending",
      "unsupported_outputs",
      "theme_breakout",
    ];

    if (themeBlocker?.reason?.includes("Theme breakout execution is paused")) {
      await expect(page.locator("body")).toContainText(themeBreakoutPausedText);
      await expect(page.locator("body")).toContainText(themeBreakoutReplayText);
    }

    for (const fragment of backendEnglishFragments) {
      expect(bodyText).not.toContain(fragment);
    }

    const riskItem = strategyEnvelope.result?.risk_exit?.items?.[0];
    if (riskItem?.stock_code) {
      await page.getByTestId(`stock-risk-row-${riskItem.stock_code}`).click();
      const drawer = page.getByTestId("stock-detail-drawer");
      const footer = page.getByTestId("stock-detail-footer-meta");
      await expect(footer).toContainText(sourceVersionText, { timeout: 60_000 });
      await expect(footer).toContainText(ruleVersionText);
      await expect(footer).toContainText(qualityText);
      await expect(footer).toContainText(channelText);

      const drawerText = await drawer.innerText();
      for (const fragment of ["source_version", "rule_version", "quality_flag", "vendor_status"]) {
        expect(drawerText).not.toContain(fragment);
      }
    }

    const apiFailures = failedRequests.filter(
      (entry) =>
        (entry.includes("/ui/") || entry.includes("/api/")) &&
        !entry.includes("net::ERR_ABORTED"),
    );
    expect(apiFailures).toEqual([]);
    expect(consoleMessages).toEqual([]);
  });
});
