import { readFileSync } from "node:fs";

import { AxeBuilder } from "@axe-core/playwright";
import { test, expect } from "@playwright/test";
import {
  assertNoUnexpectedServiceRequests,
  assertSyntheticReadRequest,
  installSyntheticSystemReads,
  syntheticReadHeaders,
} from "./fixtures/synthetic-system-reads.mjs";

const FORMAL_STATE_BASE_URL =
  process.env.MOSS_PLAYWRIGHT_STATE_BASE_URL ??
  (process.env.MOSS_PLAYWRIGHT_USE_WEB_SERVER === "1"
    ? `http://127.0.0.1:${process.env.MOSS_PLAYWRIGHT_STATE_PORT ?? "5889"}`
    : process.env.MOSS_PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5888");
const GOLDEN_SAMPLE_ID = "GS-PNL-BUSINESS-INSIGHTS-A";
const GOLDEN_RESPONSE = JSON.parse(
  readFileSync(
    new URL(
      `../../../tests/golden_samples/${GOLDEN_SAMPLE_ID}/response.json`,
      import.meta.url,
    ),
    "utf8",
  ),
);

test.describe("governed PnL by-business Insights browser smoke", () => {
  test("renders the governed formal conclusions and has no critical axe violations", async ({ page }) => {
    const requestedFilters = [];
    const generation = "gen-browser-smoke-1";
    const serviceFixture = await installSyntheticSystemReads(page);

    await page.route("**/api/pnl/dates*", async (route) => {
      assertSyntheticReadRequest(route, "/api/pnl/dates");
      await route.fulfill({
        headers: syntheticReadHeaders,
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          result_meta: {
            ...GOLDEN_RESPONSE.result_meta,
            trace_id: "tr_pnl_dates_browser_smoke",
            result_kind: "pnl.dates",
            requested_report_date: null,
            resolved_report_date: null,
            as_of_date: null,
            date_basis: null,
          },
          result: {
            report_dates: ["2026-02-28"],
            formal_fi_report_dates: ["2026-02-28"],
            nonstd_bridge_report_dates: ["2026-02-28"],
          },
        }),
      });
    });

    await page.route("**/api/pnl/by-business/precompute-status?*", async (route) => {
      assertSyntheticReadRequest(route, "/api/pnl/by-business/precompute-status");
      await route.fulfill({
        headers: syntheticReadHeaders,
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          year: 2026,
          status: "completed",
          serving_mode: "published",
          is_current: true,
          run_id: null,
          report_date: "2026-02-28",
          source_version: "sv_browser_smoke",
          rule_version: "rv_browser_smoke",
          queued_at: null,
          started_at: null,
          finished_at: "2026-03-01T00:00:00Z",
          generated_at: "2026-03-01T00:00:00Z",
          record_count: 1,
          error_message: null,
          failure_category: null,
          trigger_reason: null,
          retry_attempt: 0,
          retry_policy: { max_retries: 3, min_backoff_seconds: 15 },
          readiness: "ready",
          generation,
          dependencies: [],
          permissions: { can_rebuild: false, reason: "只读浏览器验收" },
          worker_stalled: false,
        }),
      });
    });

    await page.route("**/api/pnl/by-business-insights?*", async (route) => {
      assertSyntheticReadRequest(route, "/api/pnl/by-business-insights");
      const requestUrl = new URL(route.request().url());
      requestedFilters.push({
        year: requestUrl.searchParams.get("year"),
        asOfDate: requestUrl.searchParams.get("as_of_date"),
        generation: requestUrl.searchParams.get("generation"),
      });
      await route.fulfill({
        headers: syntheticReadHeaders,
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...GOLDEN_RESPONSE,
          result: { ...GOLDEN_RESPONSE.result, generation },
        }),
      });
    });

    await page.goto(`${FORMAL_STATE_BASE_URL}/pnl-by-business-insights`, {
      waitUntil: "domcontentloaded",
    });

    const pageRoot = page.locator('[data-testid="pnl-by-business-insights-page"]');
    await expect(pageRoot).toBeVisible({ timeout: 60_000 });
    await expect(page.locator('[data-testid="pnl-by-business-insights-contract-review"]')).toHaveCount(0);
    await expect.poll(() => requestedFilters.at(-1)).toEqual({
      year: "2026",
      asOfDate: "2026-02-28",
      generation,
    });

    const contractStatus = page.locator('[data-testid="pnl-by-business-insights-contract-status"]');
    await expect(contractStatus).toContainText("warning");
    await expect(contractStatus).toContainText("none");
    await expect(contractStatus).toContainText("2026-02-28");
    await expect(contractStatus).toContainText("tr_pnl_business_insights_gs_a");

    const decisionBrief = page.locator(
      '[data-testid="pnl-by-business-insights-decision-brief"]',
    );
    await expect(decisionBrief).toBeVisible();
    await expect(decisionBrief).toContainText("结构、异常与使用顺序");
    await expect(decisionBrief).toContainText("怎么使用");
    await expect(decisionBrief).toContainText("当前接口未返回利润影响所需输入，本页不作估算");

    const concentration = page.locator(
      '[data-testid="pnl-by-business-insights-concentration-kpis"]',
    );
    // HHI 口径：黄金样本 hhi_pct="53.13"（份额 62.50%/37.50%，raw 53.125 按 core-finance
    // Decimal ROUND_HALF_UP 约定量化；见 GS-PNL-BUSINESS-INSIGHTS-A/assertions.md 与提交 47b9d5527）。
    // 页面经 formatPct 直出后端字符串，不在前端重算。
    await expect(concentration).toContainText("53.13%");
    await expect(concentration).toContainText("100.00%");

    const shareDrift = page.locator('[data-testid="pnl-by-business-insights-share-drift-table"]');
    await expect(shareDrift).toContainText("+7.50pp");
    await expect(shareDrift).toContainText("-7.50pp");

    const reconciliation = page.locator(
      '[data-testid="pnl-by-business-insights-reconciliation-section"]',
    );
    await expect(reconciliation).toBeVisible();
    await expect(reconciliation).toContainText("非业务结论");

    const accessibility = await new AxeBuilder({ page })
      .include('[data-testid="pnl-by-business-insights-page"]')
      .analyze();
    const criticalViolations = accessibility.violations.filter(
      (violation) => violation.impact === "critical",
    );
    expect(criticalViolations).toEqual([]);
    assertNoUnexpectedServiceRequests(serviceFixture, ["/ui/macro/choice-series/latest"]);
  });
});
