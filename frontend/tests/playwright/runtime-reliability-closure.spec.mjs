import { expect, test } from "@playwright/test";

const baseURL = process.env.MOSS_PLAYWRIGHT_STATE_BASE_URL
  ?? process.env.MOSS_PLAYWRIGHT_BASE_URL
  ?? "http://127.0.0.1:5889";

// All service traffic is fulfilled locally; these tests never submit real updates.
async function installServices(page, responses) {
  const writes = [];
  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (/^\/(api|ui|health)(\/|$)/.test(url.pathname)) {
      if (!["GET", "HEAD"].includes(request.method())) {
        writes.push(`${request.method()} ${url.pathname}`);
        await route.fulfill({ status: 405, json: { detail: "Read-only browser fixture" } });
        return;
      }
      if (url.pathname === "/api/system-read-publication") {
        await route.fulfill({ json: { enabled: false, generation: null, coverage_dates: {} } });
        return;
      }
      const response = responses[url.pathname];
      if (response) {
        await route.fulfill(typeof response === "function" ? response(url) : { json: response });
      } else {
        await route.fulfill({ status: 503, json: { detail: "Not part of this browser fixture" } });
      }
      return;
    }
    if (url.origin !== new URL(baseURL).origin) {
      await route.abort();
      return;
    }
    await route.continue();
  });
  return writes;
}

function overview(canManage = true) {
  const run = {
    report_date: "2026-08-31", workflow: "core_financial", status: "failed", attempt: 1,
    submitted_at: "2026-09-22T00:00:00Z", updated_at: "2026-09-22T00:01:00Z",
    message: "合成失败回执", current_step: null,
  };
  return {
    checked_at: "2026-09-22T00:02:00Z", input_directory: "fixtures/input",
    permissions: { core: canManage, balance: canManage, market: false },
    schedule: { status: "available", detail: "合成调度状态", tasks: [
      { task_name: "MOSS-DataUpdateQueue", label: "财务更新与文件检查", status: "ready",
        last_run_time: null, next_run_time: null, last_result: "0" },
    ] },
    financial_dates: [], steps: [{ key: "verify", label: "结果日期核验" }],
    runs: [
      { ...run, run_id: "browser-publish-failed", failure_receipt: { failed_step: "publish" },
        steps: [{ key: "verify", label: "结果日期核验", status: "completed" },
          { key: "publish", label: "财务发布", status: "failed", error_message: "合成发布连接失败" }] },
      { ...run, run_id: "browser-compute-failed", report_date: "2026-07-31",
        failure_receipt: { failed_step: "balance" },
        steps: [{ key: "balance", label: "余额计算", status: "failed" }] },
    ],
  };
}

test("publication failures expose the receipt without the full-update retry shortcut", async ({ page }) => {
  const writes = await installServices(page, {
    "/api/data-updates": overview(),
    "/api/data-updates/preflight": (url) => ({ json: {
      report_date: url.searchParams.get("report_date"), ready: false,
      input_directory: "fixtures/input", checks: [],
    } }),
  });
  await page.goto(`${baseURL}/platform-config`);
  const center = page.getByTestId("data-update-center");
  await expect(center).toBeVisible();
  const published = center.locator("li").filter({ hasText: "财务计算已完成，发布待处理" });
  await expect(published).toHaveCount(1);
  await expect(published.getByRole("button", { name: "重新提交此日期" })).toHaveCount(0);
  await published.getByText("查看失败回执与已完成步骤", { exact: true }).click();
  await expect(published).toContainText("browser-publish-failed");
  await expect(published.getByText("合成发布连接失败")).toBeVisible();
  await center.getByRole("button", { name: "重新提交此日期" }).click();
  await expect(center.getByLabel("报告日期", { exact: true })).toHaveValue("2026-07-31");
  expect(writes).toEqual([]);
});

test("viewers can inspect publication failures without receiving write controls", async ({ page }) => {
  const writes = await installServices(page, { "/api/data-updates": overview(false) });
  await page.goto(`${baseURL}/platform-config`);
  const center = page.getByTestId("data-update-center");
  await expect(center.getByText("财务计算已完成，发布待处理")).toBeVisible();
  await center.getByText("查看失败回执与已完成步骤", { exact: true }).click();
  await expect(center.getByText("合成发布连接失败")).toBeVisible();
  await expect(center.getByRole("button", { name: "重新提交此日期" })).toHaveCount(0);
  await expect(center.getByRole("button", { name: "立即更新", exact: true })).toBeDisabled();
  expect(writes).toEqual([]);
});

for (const [variant, badPayload] of Object.entries({
  "missing envelope": {},
  "null result": { result: null, result_meta: {} },
  "missing fields": { result: {}, result_meta: {} },
  "invalid field types": { result: { report_dates: {}, rows: {} }, result_meta: {} },
})) {
test(`a malformed date envelope (${variant}) remains a visible, retryable page error`, async ({ page }) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  let reads = 0;
  const writes = await installServices(page, {
    "/ui/balance-movement-analysis/dates": () => { reads += 1; return { json: badPayload }; },
  });
  await page.goto(`${baseURL}/balance-movement-analysis`);
  const status = page.getByTestId("balance-movement-analysis-date-status");
  await expect(status).toContainText("报告日期加载失败");
  const before = reads;
  await status.getByRole("button", { name: "重试读取" }).click();
  await expect.poll(() => reads).toBeGreaterThan(before);
  await expect(status).toContainText("报告日期加载失败");
  await expect(page.getByTestId("workbench-route-error-page")).toHaveCount(0);
  expect(errors).toEqual([]);
  expect(writes).toEqual([]);
});

test(`a malformed detail envelope (${variant}) is visible without requesting materialization`, async ({ page }) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  let reads = 0;
  const writes = await installServices(page, {
    "/ui/balance-movement-analysis/dates": {
      result_meta: { basis: "analytical", as_of_date: "2026-08-31" },
      result: { report_dates: ["2026-08-31"], currency_basis: "CNX",
        latest_read_model_report_date: "2026-08-31", latest_upstream_control_report_date: "2026-08-31",
        freshness_status: "fresh" },
    },
    "/ui/balance-movement-analysis": () => { reads += 1; return { json: badPayload }; },
  });
  await page.goto(`${baseURL}/balance-movement-analysis?report_date=2026-08-31`);
  const status = page.getByTestId("balance-movement-analysis-detail-status");
  await expect(status).toContainText("余额变动加载失败");
  await expect(page.getByText("等待物化", { exact: true })).toHaveCount(0);
  const before = reads;
  await status.getByRole("button", { name: "重试读取" }).click();
  await expect.poll(() => reads).toBeGreaterThan(before);
  await expect(status).toContainText("余额变动加载失败");
  expect(errors).toEqual([]);
  expect(writes).toEqual([]);
});
}
