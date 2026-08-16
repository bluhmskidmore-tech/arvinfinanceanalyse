import { expect, test } from "@playwright/test";

// 2026-08-09 4ef35b27 "restore confirmed option two" 之后，首页研究证据带（04 区块）
// 按确认稿把发布历史披露、政策资金面分组、供给提示统一退役为 display:none
// （dashboardHomeOptionTwo.module.css 顶层规则，全视口生效）。
// 本 spec 断言该已提交契约：历史行仍完整驻留 DOM（数据可用、条数披露不缩水），
// 但对首屏零布局占位——首页默认高度不随历史行数增长。
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

    // 已提交的确认稿契约：披露元素被设计性退役（隐藏且零布局占位），
    // 默认也不处于展开态。
    await expect(disclosure).toBeHidden();
    await expect(disclosure).not.toHaveAttribute("open");
    await expect(content).toBeHidden();
    expect(await disclosure.boundingBox()).toBeNull();

    // 数据可用性不缩水：历史行完整驻留 DOM，summary 如实披露条数。
    await expect.poll(() => rows.count(), { timeout: 60_000 }).toBeGreaterThan(0);
    const rowCount = await rows.count();
    await expect(summary).toContainText(`共 ${rowCount} 项`);

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
