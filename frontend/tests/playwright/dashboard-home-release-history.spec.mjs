import { expect, test } from "@playwright/test";

// a97f0f3a restored the release-history disclosure on 2026-09-16. Its summary is
// accessible, while the history stays collapsed so row count does not increase
// the default research panel height.
test.describe("dashboard home release history disclosure", () => {
  test("keeps every history row available without growing the homepage by default", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/", { waitUntil: "domcontentloaded" });

    const disclosure = page.getByTestId("dashboard-home-release-history-disclosure");
    const summary = disclosure.locator("summary");
    const content = disclosure.locator(":scope > div");
    const rows = disclosure.getByTestId("dashboard-home-release-history-row");

    const deferredSentinel = page.getByTestId("dashboard-home-deferred-sentinel");
    await expect(deferredSentinel).toBeAttached();
    await deferredSentinel.scrollIntoViewIfNeeded();

    // 延迟区块加载完成：研究日历分区可见，披露元素进入 DOM。
    const researchCalendar = page.getByTestId("dashboard-home-research-calendar");
    await expect(researchCalendar).toBeVisible({ timeout: 60_000 });
    await researchCalendar.scrollIntoViewIfNeeded();
    await expect(disclosure).toBeAttached({ timeout: 60_000 });

    await expect(disclosure).toBeVisible();
    await expect(disclosure).not.toHaveAttribute("open");
    await expect(content).toBeHidden();
    const collapsed = await disclosure.boundingBox();
    const summaryBox = await summary.boundingBox();
    expect(collapsed.height).toBeLessThanOrEqual(summaryBox.height + 2);

    // 数据可用性不缩水：历史行完整驻留 DOM，summary 如实披露条数。
    await expect.poll(() => rows.count(), { timeout: 60_000 }).toBeGreaterThan(0);
    const rowCount = await rows.count();
    await expect(summary).toContainText(`共 ${rowCount} 项`);
    await summary.focus();
    await page.keyboard.press("Enter");
    await expect(disclosure).toHaveAttribute("open", "");
    await expect(rows.first()).toBeVisible();
    await expect(rows).toHaveCount(rowCount);
    await page.keyboard.press("Enter");
    await expect(content).toBeHidden();

    // 同组退役面（政策资金面分组、供给提示）同样不得回流首屏。
    await expect(
      researchCalendar.locator('[data-layout-role="research-policy-groups"]'),
    ).toBeHidden();
    await expect(
      researchCalendar.locator('[data-layout-role="research-supply-strip"]'),
    ).toBeHidden();

    // 可见的研究证据面保持存在：发布前瞻窗格仍在首页承载日历上下文。
    await expect(
      researchCalendar.locator('[data-layout-role="research-release-pane"]'),
    ).toBeVisible();
  });
});
