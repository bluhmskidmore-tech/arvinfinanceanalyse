import { test, expect } from "@playwright/test";

const REAL_STATE_BASE_URL =
  process.env.MOSS_PLAYWRIGHT_STATE_BASE_URL ??
  (process.env.MOSS_PLAYWRIGHT_USE_WEB_SERVER === "1"
    ? "http://127.0.0.1:" + (process.env.MOSS_PLAYWRIGHT_STATE_PORT ?? "5889")
    : process.env.MOSS_PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5888");

async function probeServer(baseURL) {
  if (!baseURL) {
    return { ok: false, reason: "Playwright baseURL is not configured." };
  }

  try {
    const response = await fetch(baseURL, { method: "GET" });
    if (response.ok) {
      return { ok: true, reason: "" };
    }
    return { ok: false, reason: `Smoke server probe failed with ${response.status}.` };
  } catch (error) {
    return {
      ok: false,
      reason: `Smoke server probe failed: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

function qdbMeta(resultKind) {
  return {
    trace_id: `tr_${resultKind}`,
    basis: "analytical",
    result_kind: resultKind,
    formal_use_allowed: false,
    source_version: "sv_qdb_playwright",
    vendor_version: "vv_none",
    rule_version: "rv_qdb_gl_monthly_analysis_v1",
    cache_version: "cv_qdb_gl_monthly_analysis_v1",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-12T00:00:00Z",
  };
}

test.describe("monthly operating analysis audit browser smoke", () => {
  test("renders the empty audit state as an operable real interface page", async ({ page }) => {
    const serverCheck = await probeServer(REAL_STATE_BASE_URL);
    expect(serverCheck.ok, serverCheck.reason).toBe(true);

    const requests = {
      dates: 0,
      adjustments: 0,
      adjustmentMonth: "",
    };

    await page.route("**/ui/qdb-gl-monthly-analysis/dates", async (route) => {
      requests.dates += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          result_meta: qdbMeta("qdb-gl-monthly-analysis.dates"),
          result: { report_months: ["202602", "202603"] },
        }),
      });
    });

    await page.route("**/ui/qdb-gl-monthly-analysis/manual-adjustments?*", async (route) => {
      const requestUrl = new URL(route.request().url());
      if (requestUrl.pathname.endsWith("/export")) {
        await route.continue();
        return;
      }

      requests.adjustments += 1;
      requests.adjustmentMonth = requestUrl.searchParams.get("report_month") ?? "";
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          report_month: requests.adjustmentMonth,
          adjustment_count: 0,
          adjustments: [],
          events: [],
        }),
      });
    });

    const targetUrl = new URL(
      "/product-category-pnl/audit?branch=monthly_operating_analysis&report_month=202603",
      REAL_STATE_BASE_URL,
    );
    await page.goto(targetUrl.toString(), { waitUntil: "domcontentloaded" });

    await expect(page.getByTestId("monthly-operating-analysis-audit-page")).toBeVisible({
      timeout: 60_000,
    });
    await expect(page.getByTestId("monthly-operating-analysis-audit-loading")).toHaveCount(0);
    await expect(page.getByTestId("monthly-operating-analysis-audit-load-error")).toHaveCount(0);
    await expect(page.getByTestId("monthly-operating-analysis-audit-error")).toHaveCount(0);

    await expect(page.getByText("正式接口链路")).toBeVisible();
    await expect(page.getByText("正式只读链路")).toHaveCount(0);
    await expect(page.getByTestId("monthly-operating-analysis-audit-month-select")).toHaveValue("202603");
    await expect(page.getByTestId("monthly-operating-analysis-adjustment-submit")).toBeEnabled();
    await expect(page.getByTestId("monthly-operating-analysis-adjustment-export")).toBeEnabled();
    await expect(page.getByTestId("monthly-operating-analysis-adjustment-list")).toContainText(
      "当前没有调整记录。",
    );
    await expect(page.getByTestId("monthly-operating-analysis-adjustment-events")).toContainText(
      "当前没有调整事件。",
    );

    expect(requests.dates).toBeGreaterThan(0);
    expect(requests.adjustments).toBeGreaterThan(0);
    expect(requests.adjustmentMonth).toBe("202603");
  });
});
