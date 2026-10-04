import { readFileSync } from "node:fs";

import { test, expect } from "@playwright/test";

const FORMAL_STATE_BASE_URL =
  process.env.MOSS_PLAYWRIGHT_STATE_BASE_URL ??
  (process.env.MOSS_PLAYWRIGHT_USE_WEB_SERVER === "1"
    ? `http://127.0.0.1:${process.env.MOSS_PLAYWRIGHT_STATE_PORT ?? "5889"}`
    : process.env.MOSS_PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5888");
const GOLDEN_RESPONSE = JSON.parse(
  readFileSync(
    new URL("../../../tests/golden_samples/GS-PNL-BUSINESS-INSIGHTS-A/response.json", import.meta.url),
    "utf8",
  ),
);

function statusPayload(overrides = {}) {
  return {
    year: 2026,
    status: "completed",
    serving_mode: "published",
    is_current: true,
    run_id: null,
    report_date: "2026-02-28",
    source_version: "sv_browser_flow",
    rule_version: "rv_browser_flow",
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
    generation: "gen-browser-flow-1",
    dependencies: [],
    permissions: { can_rebuild: false, reason: "当前账号仅可查看" },
    last_progress_at: "2026-03-01T00:00:00Z",
    worker_stalled: false,
    recovery_hint: null,
    ...overrides,
  };
}

function resultPayload({ generation, traceId, year = 2026, asOfDate = "2026-02-28" }) {
  return {
    ...GOLDEN_RESPONSE,
    result_meta: {
      ...GOLDEN_RESPONSE.result_meta,
      trace_id: traceId,
      requested_report_date: asOfDate,
      resolved_report_date: asOfDate,
      as_of_date: asOfDate,
    },
    result: {
      ...GOLDEN_RESPONSE.result,
      generation,
      year,
      as_of_date: asOfDate,
    },
  };
}

async function mockDates(page, dates = ["2026-02-28"]) {
  await page.route("**/api/pnl/dates*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        result_meta: {
          ...GOLDEN_RESPONSE.result_meta,
          trace_id: "tr_dates_readiness_flow",
          result_kind: "pnl.dates",
          requested_report_date: null,
          resolved_report_date: null,
          as_of_date: null,
          date_basis: null,
        },
        result: {
          report_dates: dates,
          formal_fi_report_dates: dates,
          nonstd_bridge_report_dates: dates,
        },
      }),
    });
  });
}

test.describe("PnL by-business whole-page readiness browser flow", () => {
  test("moves from pending to a fixed ready generation before reading formal results", async ({ page }) => {
    await mockDates(page);
    let statusReads = 0;
    const requestedGenerations = [];
    await page.route("**/api/pnl/by-business/precompute-status?*", async (route) => {
      statusReads += 1;
      const pending = statusReads === 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(statusPayload(pending ? {
          status: "running",
          serving_mode: "unavailable",
          is_current: false,
          run_id: "run-browser-pending",
          readiness: "pending",
          generation: null,
          finished_at: null,
          generated_at: null,
        } : {})),
      });
    });
    await page.route("**/api/pnl/by-business-insights?*", async (route) => {
      const generation = new URL(route.request().url()).searchParams.get("generation");
      requestedGenerations.push(generation);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(resultPayload({
          generation,
          traceId: "tr_browser_ready_generation",
        })),
      });
    });

    await page.goto(`${FORMAL_STATE_BASE_URL}/pnl-by-business-insights`, { waitUntil: "domcontentloaded" });
    await expect(page.locator('[data-testid="pnl-by-business-insights-precompute-state"]')).toContainText("准备中");
    await expect(page.locator('[data-testid="pnl-by-business-insights-contract-status"]')).toContainText(
      "tr_browser_ready_generation",
      { timeout: 15_000 },
    );
    expect(requestedGenerations).toEqual(["gen-browser-flow-1"]);
  });

  test("keeps a late prior-cutoff response from replacing the selected cutoff", async ({ page }) => {
    await mockDates(page, ["2026-02-28", "2025-02-28"]);
    await page.route("**/api/pnl/by-business/precompute-status?*", async (route) => {
      const url = new URL(route.request().url());
      const asOfDate = url.searchParams.get("as_of_date");
      const generation = asOfDate === "2025-02-28" ? "gen-browser-2025" : "gen-browser-2026";
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(statusPayload({
          year: Number(asOfDate.slice(0, 4)),
          report_date: asOfDate,
          generation,
        })),
      });
    });
    let releaseFirst;
    const firstRequestHeld = new Promise((resolve) => {
      releaseFirst = resolve;
    });
    await page.route("**/api/pnl/by-business-insights?*", async (route) => {
      const url = new URL(route.request().url());
      const asOfDate = url.searchParams.get("as_of_date");
      const generation = url.searchParams.get("generation");
      if (asOfDate === "2026-02-28") {
        await firstRequestHeld;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(resultPayload({
          generation,
          traceId: asOfDate === "2025-02-28" ? "tr_browser_selected_2025" : "tr_browser_late_2026",
          year: Number(asOfDate.slice(0, 4)),
          asOfDate,
        })),
      }).catch(() => {});
    });

    await page.goto(`${FORMAL_STATE_BASE_URL}/pnl-by-business-insights`, { waitUntil: "domcontentloaded" });
    await expect.poll(() => page.locator('[aria-label="pnl-by-business-insights-as-of-date"]').inputValue()).toBe("2026-02-28");
    await page.locator('[aria-label="pnl-by-business-insights-year"]').selectOption("2025");
    await expect(page.locator('[data-testid="pnl-by-business-insights-contract-status"]')).toContainText(
      "tr_browser_selected_2025",
    );
    releaseFirst();
    await page.waitForTimeout(100);
    await expect(page.locator('[data-testid="pnl-by-business-insights-contract-status"]')).toContainText(
      "tr_browser_selected_2025",
    );
    await expect(page.locator('[data-testid="pnl-by-business-insights-contract-status"]')).not.toContainText(
      "tr_browser_late_2026",
    );
  });

  test("keeps stale viewer state fail-closed without exposing the preparation action", async ({ page }) => {
    await mockDates(page);
    let insightsReads = 0;
    await page.route("**/api/pnl/by-business/precompute-status?*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(statusPayload({
          serving_mode: "unavailable",
          is_current: false,
          readiness: "stale",
          generation: null,
        })),
      });
    });
    await page.route("**/api/pnl/by-business-insights?*", async (route) => {
      insightsReads += 1;
      await route.abort();
    });

    await page.goto(`${FORMAL_STATE_BASE_URL}/pnl-by-business-insights`, { waitUntil: "domcontentloaded" });
    const state = page.locator('[data-testid="pnl-by-business-insights-precompute-state"]');
    await expect(state).toContainText("结果已过期");
    await expect(state).toContainText("当前账号仅可查看");
    await expect(state.getByRole("button", { name: "请求后台准备" })).toHaveCount(0);
    await expect(page.locator('[data-testid="pnl-by-business-insights-decision-brief"]')).toHaveCount(0);
    expect(insightsReads).toBe(0);
  });

  test("lets an authorized operator request whole-page preparation", async ({ page }) => {
    await mockDates(page);
    let rebuildQuery = null;
    await page.route("**/api/pnl/by-business/precompute-status?*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(statusPayload({
          status: "failed",
          serving_mode: "unavailable",
          is_current: false,
          readiness: "failed",
          generation: null,
          error_message: "materialization failed",
          permissions: { can_rebuild: true, reason: null },
        })),
      });
    });
    await page.route("**/api/pnl/by-business/precompute-rebuild?*", async (route) => {
      rebuildQuery = new URL(route.request().url()).searchParams;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(statusPayload({
          status: "queued",
          serving_mode: "unavailable",
          is_current: false,
          run_id: "run-browser-rebuild",
          readiness: "pending",
          generation: null,
          permissions: { can_rebuild: true, reason: null },
        })),
      });
    });

    await page.goto(`${FORMAL_STATE_BASE_URL}/pnl-by-business-insights`, { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: "请求后台准备" }).click();
    await expect(page.locator('[data-testid="pnl-by-business-insights-precompute-state"]')).toContainText(
      "run-browser-rebuild",
    );
    expect(rebuildQuery.get("year")).toBe("2026");
    expect(rebuildQuery.get("as_of_date")).toBe("2026-02-28");
    expect(rebuildQuery.get("include_page_dependencies")).toBe("true");
  });
});
