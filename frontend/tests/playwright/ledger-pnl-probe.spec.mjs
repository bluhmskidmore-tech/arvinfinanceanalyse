import { test, expect } from "@playwright/test";

const dataSource = process.env.VITE_DATA_SOURCE ?? "real";

/**
 * 已知无害 console 噪音过滤清单（gate: no_console_errors）。
 * 当前为空：mock 模式下 ledger-pnl 首屏预期零 console error / pageerror，
 * 与 market-finance-workbench.spec.mjs 的 mock 断言惯例一致。
 * 如未来必须放行某条噪音，在此添加 RegExp 并逐条注明理由。
 */
const KNOWN_BENIGN_CONSOLE_NOISE = [];

/** 与 LedgerPnlPage.tsx 中 summaryCards 定义一一对应的稳定卡片标题。 */
const SUMMARY_CARD_TITLES = ["核心损益", "全量损益", "总资产", "总负债", "净资产"];

function collectRuntimeErrors(page) {
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(`console: ${message.text()}`);
    }
  });
  page.on("pageerror", (error) => {
    errors.push(`pageerror: ${error.message}`);
  });
  return errors;
}

/**
 * 访问 ledger-pnl 路由并等待首屏核心区域完成渲染。
 * 30s 超时覆盖路由级懒加载与 dev server 首次转译该大页面的耗时。
 */
async function openLedgerPnlAndAwaitCore(page) {
  await page.goto("/ledger-pnl", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("ledger-pnl-page")).toBeVisible({ timeout: 30_000 });

  const summaryCards = page.getByTestId("ledger-pnl-summary-cards");
  await expect(summaryCards).toBeVisible({ timeout: 30_000 });
  // mock summary 查询落地后卡片值由 "—" 变为 "xx.xx 亿元"，据此确认数据链路可用而非空壳。
  await expect(summaryCards).toContainText("亿元", { timeout: 30_000 });
  return summaryCards;
}

test.describe("ledger-pnl mock probe", () => {
  test.skip(dataSource !== "mock", "Ledger-pnl probe requires VITE_DATA_SOURCE=mock.");

  test("page_loads: renders title and mock summary cards", async ({ page }) => {
    const summaryCards = await openLedgerPnlAndAwaitCore(page);

    await expect(page.getByTestId("ledger-pnl-page-title")).toHaveText("总账损益");
    // 模式徽标确认走的是本地演示数据链路，防止 BASE_URL 误指 real 服务器。
    await expect(page.getByText("本地演示数据")).toBeVisible();
    for (const title of SUMMARY_CARD_TITLES) {
      await expect(summaryCards).toContainText(title);
    }
  });

  test("no_console_errors: visit emits no console errors", async ({ page }) => {
    const runtimeErrors = collectRuntimeErrors(page);

    await openLedgerPnlAndAwaitCore(page);

    const unexpectedErrors = runtimeErrors.filter(
      (entry) => !KNOWN_BENIGN_CONSOLE_NOISE.some((pattern) => pattern.test(entry)),
    );
    expect(unexpectedErrors).toEqual([]);
  });
});
