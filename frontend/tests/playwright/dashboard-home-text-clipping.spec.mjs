import { expect, test } from "@playwright/test";

/**
 * 首页卡片高度大量写死（如分布列 145px、持仓矩阵 331px），内容一旦多出几像素就会把末行
 * 文字拦腰切断——不是省略号，是字形被横切。这类问题 jsdom 测不出来：视觉契约测试只断言
 * CSS 字符串字面量，而 jsdom 不做真实布局。只有真实浏览器量得出来。
 */
const VIEWPORTS = [
  { width: 1280, height: 1000 },
  { width: 1440, height: 1000 },
  { width: 1920, height: 1000 },
];

/**
 * 承载固定高度卡片的区块。等 deferred 容器可见是不够的：容器先挂载、内容后填充，
 * 早扫一步会在空页面上扫出 0 处裁切而报通过（1920px 曾这样假通过）。
 */
const CONTENT_ANCHORS = [
  "dashboard-home-structure-expanded-grid",
  "dashboard-home-position-changes",
  "dashboard-home-research-calendar",
  "dashboard-home-policy-funding-pane",
];

/**
 * mock 数据源下持仓矩阵和政策分组都是空的，分布列也只有两列，任何高度都装得下。
 * 这时扫出 0 处裁切不代表布局没问题，只代表没内容可裁——直接判过等于给虚假绿灯，
 * 而虚假绿灯正是这批裁切问题长期没被发现的原因，所以宁可显式跳过。
 */
async function measureContentDepth(page) {
  return page.evaluate(() => ({
    matrixRows: document.querySelectorAll(
      '[data-testid="dashboard-home-position-change-row"]',
    ).length,
    policyItems: document.querySelectorAll(
      '[data-layout-role="research-policy-item"]',
    ).length,
  }));
}

/**
 * 容器可见早于行数据填充，直接读一次会把「还在加载」误判成「数据源没内容」。
 * 轮询到有内容为止，超时后仍为空才当作数据源过瘦。窗口给到 30s：首页冷启动取数偶尔要
 * 十几秒，窗口太短会随机跳过，等于随机丢掉防护。
 */
async function waitForContentDepth(page, timeoutMs = 30_000) {
  const deadline = Date.now() + timeoutMs;
  let depth = await measureContentDepth(page);
  while (
    Date.now() < deadline &&
    depth.matrixRows === 0 &&
    depth.policyItems === 0
  ) {
    await page.waitForTimeout(500);
    depth = await measureContentDepth(page);
  }
  return depth;
}

async function collectClippedText(page) {
  return page.evaluate(() => {
    /** 找最近的裁切祖先；可滚动容器不算裁切，因为内容够得着。 */
    const clippingAncestor = (element) => {
      let node = element.parentElement;
      while (node && node !== document.body) {
        const { overflowY } = getComputedStyle(node);
        if (overflowY === "hidden" || overflowY === "clip") return node;
        if (overflowY === "auto" || overflowY === "scroll") return null;
        node = node.parentElement;
      }
      return null;
    };

    const describe = (element) =>
      element.getAttribute("data-layout-role") ??
      element.getAttribute("data-testid") ??
      element.getAttribute("aria-label") ??
      element.className?.toString().slice(0, 48) ??
      element.tagName;

    const clipped = [];
    for (const element of document.querySelectorAll("body *")) {
      if (element.children.length > 0) continue;
      const text = (element.textContent ?? "").trim();
      if (!text) continue;

      const style = getComputedStyle(element);
      if (style.display === "none" || style.visibility === "hidden") continue;

      const rect = element.getBoundingClientRect();
      if (rect.height === 0 || rect.width === 0) continue;

      const box = clippingAncestor(element);
      if (!box) continue;

      const boxBottom = box.getBoundingClientRect().top + box.clientHeight;
      const overflow = rect.bottom - boxBottom;
      // 只报「露一半切一半」。整行落在可视区外属于折叠或懒渲染，不是裁切。
      if (overflow > 1.5 && rect.top < boxBottom - 1.5) {
        clipped.push({
          text: text.slice(0, 40),
          overflowPx: Math.round(overflow * 10) / 10,
          container: describe(box),
        });
      }
    }
    return clipped;
  });
}

/**
 * 三个宽度共用一次页面加载，而不是各开一个并行 worker：并行时三个浏览器同时拉首页数据
 * 会把后端压到部分请求拿不到内容，测试随机跳过，等于随机丢掉防护。视口切换只触发 CSS
 * 重排，不需要重新取数。
 */
test.describe("dashboard home text clipping", () => {
  test("renders every card line unclipped across desktop widths", async ({
    page,
  }) => {
    await page.setViewportSize({
      width: VIEWPORTS[0].width,
      height: VIEWPORTS[0].height,
    });
    await page.goto("/", { waitUntil: "domcontentloaded" });

    await expect(page.getByTestId("dashboard-home-page")).toBeVisible({
      timeout: 60_000,
    });
    // 被裁的卡片都在延迟渲染的下半页里，扫描前必须等它们落地。
    await expect(
      page.getByTestId("dashboard-home-deferred-content"),
    ).toBeVisible({
      timeout: 60_000,
    });
    for (const anchor of CONTENT_ANCHORS) {
      await expect(page.getByTestId(anchor)).toBeVisible({ timeout: 60_000 });
    }
    await page
      .waitForLoadState("networkidle", { timeout: 30_000 })
      .catch(() => undefined);

    const depth = await waitForContentDepth(page);
    test.skip(
      depth.matrixRows === 0 && depth.policyItems === 0,
      "data source has no position-matrix rows and no policy items, so nothing can clip; point MOSS_PLAYWRIGHT_BASE_URL at a real-data server for real coverage",
    );

    const failures = [];
    for (const viewport of VIEWPORTS) {
      await page.setViewportSize({
        width: viewport.width,
        height: viewport.height,
      });
      // 让重排和数据填充引起的行高变化稳定下来再量。
      await page.waitForTimeout(700);
      const clipped = await collectClippedText(page);
      if (clipped.length > 0) {
        failures.push({ width: viewport.width, clipped });
      }
    }

    expect(
      failures,
      `these lines are cut in half by a fixed-height container:\n${JSON.stringify(failures, null, 2)}`,
    ).toEqual([]);
  });
});
