import { expect, test } from "@playwright/test";

const realStateBaseURL = process.env.MOSS_PLAYWRIGHT_STATE_BASE_URL
  ?? (process.env.MOSS_PLAYWRIGHT_USE_WEB_SERVER === "1"
    ? `http://127.0.0.1:${process.env.MOSS_PLAYWRIGHT_STATE_PORT ?? "5889"}`
    : process.env.MOSS_PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5889");
test.use({ baseURL: realStateBaseURL });

// Synthetic conversation only; all API requests are intercepted in the browser.
const firstQuestion = "帮我整理这段会议记录，提炼需要跟进的事项";
const secondQuestion = "把刚才的事项整理为一段简短说明";
const scope = "::user%3Aweb-user";
const turnsKey = `moss.agent.conversationTurns.v1${scope}`;
const runKey = `moss.agent.latestRunId.v1${scope}`;
const answer = (text) => ({
  answer: text,
  cards: [],
  evidence: {
    tables_used: [],
    filters_applied: { provider: "hermes", transport: "bridge", model: "test-model" },
    evidence_rows: 0,
    quality_flag: "ok",
  },
  result_meta: { trace_id: "tr_browser_fixture", basis: "analytical", result_kind: "agent.hermes" },
  next_drill: [],
  suggested_actions: [],
});
const secondAnswer = "第二轮已完成的说明，停止其他回答后仍应保留。";
const seedTurns = [
  { id: "first", question: firstQuestion, retryMode: "ordinary", result: answer("第一轮的原回答。") },
  { id: "second", question: secondQuestion, retryMode: "ordinary", result: answer(secondAnswer) },
];
const runningRun = {
  run_id: "agent_run:browser_fixture", status: "running", provider: "hermes",
  model: "test-model", transport: "bridge", toolsets: "", question: firstQuestion,
};

async function isolateApi(page, baseURL, handleRun) {
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== new URL(baseURL).origin) return route.abort();
    if (url.pathname === "/api/agent/models") {
      return route.fulfill({ json: {
        provider: "hermes", default_model: "test-model", source: "configured",
        models: [{ id: "test-model", label: "测试模型", reasoning_efforts: [] }],
      } });
    }
    if (url.pathname.startsWith("/api/agent/runs")) return handleRun(route, url);
    if (/^\/(api|ui|health)(\/|$)/.test(url.pathname)) return route.abort();
    return route.continue();
  });
}

for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
  test(`historical regeneration preserves the later answer at ${viewport.width}px`, async ({ page, baseURL }, testInfo) => {
    await page.setViewportSize(viewport);
    await page.emulateMedia({ reducedMotion: "reduce" });
    const requests = [];
    await isolateApi(page, baseURL, (route, url) => {
      requests.push(`${route.request().method()} ${url.pathname}`);
      if (url.pathname.endsWith("/events")) return route.fulfill({ status: 503 });
      return route.fulfill({ json: url.pathname.endsWith("/cancel")
        ? { ...runningRun, status: "cancelled" } : runningRun });
    });
    await page.addInitScript(({ turnsKey, seedTurns }) => {
      localStorage.setItem(turnsKey, JSON.stringify(seedTurns));
    }, { turnsKey, seedTurns });
    await page.goto("/agent");
    await expect(page.getByText(secondAnswer, { exact: true })).toBeVisible();
    await page.getByRole("button", { name: `重新生成：${firstQuestion}`, exact: true }).click();

    const activeStatus = page.getByRole("status", { name: "正在重新回答历史问题" });
    await expect(activeStatus).toContainText(firstQuestion);
    await expect(page.getByRole("button", { name: `编辑问题：${secondQuestion}`, exact: true })).toBeDisabled();
    await expect(page.getByTestId("agent-panel-submit")).toHaveAccessibleName(`停止等待当前回答：${firstQuestion}`);
    await expect(page.getByTestId("agent-panel-submit")).toBeInViewport();
    await activeStatus.getByRole("button", { name: "查看正在回答的问题" }).click();
    await expect(page.locator('[data-agent-turn-id="first"]')).toBeInViewport();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath("historical-regeneration.png") });

    await page.getByTestId("agent-panel-submit").click();
    await expect(activeStatus).toHaveCount(0);
    await expect(page.getByText(secondAnswer, { exact: true })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "向 Agent 提问" })).toHaveValue(firstQuestion);
    await expect.poll(() => page.evaluate((key) => JSON.parse(localStorage.getItem(key)), turnsKey))
      .toEqual(expect.arrayContaining([
        expect.objectContaining({ id: "first", stopped: true }),
        expect.objectContaining({ id: "second", result: expect.objectContaining({ answer: secondAnswer }) }),
      ]));
    expect(requests.filter((item) => item === "POST /api/agent/runs")).toHaveLength(1);
  });
}

test("a temporary restore failure keeps the run available after reload", async ({ page, baseURL }) => {
  let reads = 0;
  let writes = 0;
  await isolateApi(page, baseURL, (route) => {
    if (route.request().method() !== "GET") writes += 1;
    reads += 1;
    return reads === 1
      ? route.fulfill({ status: 503, json: { detail: "Temporary fixture outage" } })
      : route.fulfill({ json: { ...runningRun, status: "completed", result: answer("恢复成功的测试回答。") } });
  });
  await page.addInitScript(({ runKey, runId }) => {
    if (!sessionStorage.getItem("agent-restore-seeded")) {
      localStorage.setItem(runKey, runId);
      sessionStorage.setItem("agent-restore-seeded", "true");
    }
  }, { runKey, runId: runningRun.run_id });
  await page.goto("/agent");
  await expect(page.getByRole("status", { name: "上次回答恢复失败" })).toBeVisible();
  await expect(page.getByRole("status", { name: "上次回答恢复失败" }))
    .toContainText("已保留上次运行，连接恢复后刷新页面可继续接回回答。");
  expect(await page.evaluate((key) => localStorage.getItem(key), runKey)).toBe(runningRun.run_id);
  await page.reload();
  await expect(page.getByText("恢复成功的测试回答。", { exact: true })).toBeVisible();
  expect(await page.evaluate((key) => localStorage.getItem(key), runKey)).toBeNull();
  expect(reads).toBe(2);
  expect(writes).toBe(0);
});

for (const recovery of ["complete", "stop"]) {
  test(`reconnecting an interrupted answer reuses the accepted run: ${recovery}`, async ({ page, baseURL }, testInfo) => {
    await page.setViewportSize(recovery === "stop"
      ? { width: 390, height: 844 }
      : { width: 1440, height: 900 });
    const question = "Please summarize this short meeting note.";
    const acceptedRun = { ...runningRun, question };
    const requests = [];
    let reconnecting = false;
    let failedReads = 0;
    await isolateApi(page, baseURL, (route, url) => {
      const method = route.request().method();
      requests.push(`${method} ${url.pathname}`);
      if (url.pathname.endsWith("/events")) return route.fulfill({ status: 503 });
      if (url.pathname.endsWith("/cancel")) {
        return route.fulfill({ json: { ...acceptedRun, status: "cancelled" } });
      }
      if (method === "POST") return route.fulfill({ json: acceptedRun });
      if (!reconnecting) {
        failedReads += 1;
        return route.fulfill({ status: 503, json: { detail: "Temporary fixture outage" } });
      }
      return route.fulfill({ json: recovery === "complete"
        ? { ...acceptedRun, status: "completed", result: answer("重新连接后收到原任务的回答。") }
        : acceptedRun });
    });
    await page.goto("/agent");
    await page.getByRole("textbox", { name: "向 Agent 提问" }).fill(question);
    await page.getByTestId("agent-panel-submit").click();
    const reconnect = page.getByRole("button", { name: `重新连接：${question}`, exact: true });
    await expect(reconnect).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("alert")).toContainText("连接中断");
    expect(failedReads).toBe(4);
    await page.screenshot({ path: testInfo.outputPath("interrupted-answer.png") });
    reconnecting = true;
    await reconnect.click();
    if (recovery === "complete") {
      await expect(page.getByText("重新连接后收到原任务的回答。", { exact: true })).toBeVisible();
      await expect(page.getByRole("alert")).toHaveCount(0);
    } else {
      await expect(page.getByTestId("agent-panel-submit")).toHaveAccessibleName(`停止等待当前回答：${question}`);
      await page.getByTestId("agent-panel-submit").click();
      await expect.poll(() => requests.filter((item) => item.endsWith("/cancel")))
        .toEqual([`POST /api/agent/runs/${encodeURIComponent(acceptedRun.run_id)}/cancel`]);
      await expect(page.getByRole("textbox", { name: "向 Agent 提问" })).toHaveValue(question);
    }
    expect(requests.filter((item) => item === "POST /api/agent/runs")).toHaveLength(1);
    const statusReads = requests.filter((item) => item.startsWith("GET ") && !item.includes("/events"));
    expect(statusReads.length).toBeGreaterThanOrEqual(4);
    expect(new Set(statusReads)).toEqual(new Set([`GET /api/agent/runs/${encodeURIComponent(acceptedRun.run_id)}`]));
  });
}

test("the embedded assistant keeps a cleared or sent default question empty", async ({ page, baseURL }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const result = answer("默认问题已发送，这是隔离测试的回答。");
  await isolateApi(page, baseURL, (route) => route.fulfill({
    json: { ...runningRun, status: "completed", result },
  }));
  await page.route("**/api/agent/query", (route) => route.fulfill({ json: result }));
  await page.goto("/pnl-attribution");
  await page.getByRole("button", { name: "打开损益复核助手", exact: true }).click();
  const input = page.getByRole("textbox", { name: "向 Agent 提问" });
  await expect(input).toHaveValue("/pnl-review");
  await page.getByRole("button", { name: "清空输入：/pnl-review", exact: true }).click();
  await expect(input).toHaveValue("");
  await expect(page.getByTestId("agent-panel-submit")).toBeDisabled();

  await page.getByRole("button", { name: "关闭抽屉", exact: true }).click();
  await page.getByRole("button", { name: "打开损益复核助手", exact: true }).click();
  await expect(input).toHaveValue("/pnl-review");
  await page.getByTestId("agent-panel-submit").click();
  await expect(page.getByText(result.answer, { exact: true })).toBeVisible();
  await expect(input).toHaveValue("");
  await expect(page.getByTestId("agent-panel-submit")).toBeDisabled();
});
