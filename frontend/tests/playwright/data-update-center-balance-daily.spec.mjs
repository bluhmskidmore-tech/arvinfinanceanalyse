import { expect, test } from "@playwright/test";

const REAL_STATE_BASE_URL =
  process.env.MOSS_PLAYWRIGHT_STATE_BASE_URL ??
  (process.env.MOSS_PLAYWRIGHT_USE_WEB_SERVER === "1"
    ? `http://127.0.0.1:${process.env.MOSS_PLAYWRIGHT_STATE_PORT ?? "5889"}`
    : process.env.MOSS_PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5888");
const REPORT_DATE = "2026-08-31";
const EARLIER_DATE = "2026-07-31";

function updateRun(status) {
  const message = {
    completed: "模拟余额任务已完成。",
    waiting_inputs: "模拟余额任务等待文件。",
    failed: "模拟余额任务失败。",
  }[status];
  return {
    run_id: `synthetic-daily-${status}`,
    report_date: REPORT_DATE,
    workflow: "balance_daily",
    status,
    submitted_at: "2026-09-24T00:00:00Z",
    updated_at: "2026-09-24T00:05:00Z",
    message,
    attempt: status === "waiting_inputs" ? 0 : 1,
    current_step: null,
    steps: status === "waiting_inputs" ? [] : [{
      key: "daily_balance_and_risk",
      label: "余额、持仓与风险更新",
      status: status === "completed" ? "completed" : "failed",
    }],
  };
}

function updateOverview(status) {
  return {
    checked_at: "2026-09-24T00:05:00Z",
    input_directory: "C:/synthetic/input",
    permissions: { core: false, balance: true, market: false },
    schedule: {
      status: "available",
      detail: "模拟计划任务状态。",
      tasks: [{
        task_name: "MOSS-DataUpdateQueue",
        label: "财务更新与文件检查",
        status: "ready",
        last_run_time: "2026-09-24 00:05",
        next_run_time: "2026-09-24 00:10",
        last_result: "0",
      }],
    },
    financial_dates: [{
      key: "balance",
      label: "余额分析",
      as_of_date: status === "completed" ? REPORT_DATE : EARLIER_DATE,
      status: "available",
    }],
    runs: [updateRun(status)],
    steps: [{ key: "daily_balance_and_risk", label: "余额、持仓与风险更新" }],
  };
}

function balanceDatesEnvelope(reportDates) {
  return {
    result_meta: {
      trace_id: "synthetic_balance_dates",
      basis: "formal",
      result_kind: "balance-analysis.dates",
      formal_use_allowed: true,
      source_version: "synthetic",
      vendor_version: "vv_none",
      rule_version: "synthetic",
      cache_version: "synthetic",
      quality_flag: "ok",
      vendor_status: "ok",
      fallback_mode: "none",
      scenario_flag: false,
      generated_at: "2026-09-24T00:00:00Z",
    },
    result: { report_dates: reportDates },
  };
}

async function installIsolatedResponses(page, status, reportDates) {
  let datesReadCount = 0;
  // Vite's dev proxy points at a live backend by default. Keep every other
  // operational request inside this browser test instead of reaching it.
  await page.route("**/*", (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (/^\/(api|ui|health)(\/|$)/.test(pathname)) return route.abort();
    return route.continue();
  });
  await page.route("**/api/data-updates", (route) =>
    route.fulfill({ json: updateOverview(status) }),
  );
  await page.route("**/ui/balance-analysis/dates", (route) => {
    datesReadCount += 1;
    return route.fulfill({ json: balanceDatesEnvelope(reportDates) });
  });
  return () => datesReadCount;
}

async function openUpdateCenter(page, status, reportDates) {
  const datesReadCount = await installIsolatedResponses(page, status, reportDates);
  await page.goto(new URL("/platform-config", REAL_STATE_BASE_URL).toString(), {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("data-update-center")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText(updateRun(status).message)).toBeVisible();
  return datesReadCount;
}

test("completed daily balance opens the requested report date", async ({ page }) => {
  const datesReadCount = await openUpdateCenter(page, "completed", [REPORT_DATE, EARLIER_DATE]);
  const resultLink = page.getByRole("link", { name: "查看余额结果" });
  await expect(resultLink).toHaveAttribute(
    "href",
    `/balance-analysis?report_date=${REPORT_DATE}`,
  );

  await resultLink.click();
  await expect(page).toHaveURL(new RegExp(`/balance-analysis\\?report_date=${REPORT_DATE}$`));
  await expect(page.getByTestId("balance-analysis-page")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByLabel("balance-report-date")).toHaveValue(REPORT_DATE);
  await expect(page.getByTestId("balance-analysis-report-date-empty")).toHaveCount(0);
  expect(datesReadCount()).toBeGreaterThan(0);
});

test("the deep link preserves its date when the balance reader lacks it", async ({ page }) => {
  const datesReadCount = await openUpdateCenter(page, "completed", [EARLIER_DATE]);
  await page.getByRole("link", { name: "查看余额结果" }).click();

  await expect(page.getByTestId("balance-analysis-page")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByLabel("balance-report-date")).toHaveValue(REPORT_DATE);
  await expect(page.getByTestId("balance-analysis-report-date-empty")).toContainText(
    `请求 ${REPORT_DATE} 不在当前正式报告日列表中`,
  );
  await expect(page).toHaveURL(new RegExp(`report_date=${REPORT_DATE}$`));
  expect(datesReadCount()).toBeGreaterThan(0);
});

for (const status of ["waiting_inputs", "failed"]) {
  test(`${status} daily balance does not offer a completed-result link`, async ({ page }) => {
    await openUpdateCenter(page, status, [EARLIER_DATE]);
    await expect(page.getByRole("link", { name: "查看余额结果" })).toHaveCount(0);
  });
}
