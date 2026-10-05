import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { interceptDesignData } from "./fixtures/market-overview-figma.mjs";

const design = fileURLToPath(new URL("../../../output/design/market-overview-figma-v1/", import.meta.url));
const output = path.resolve(process.env.MOSS_PLAYWRIGHT_OUTPUT_DIR ?? "../.codex-tmp/playwright-results", "market-overview-figma");
const REAL_STATE_BASE_URL = process.env.MOSS_PLAYWRIGHT_STATE_BASE_URL ??
  `http://127.0.0.1:${process.env.MOSS_PLAYWRIGHT_STATE_PORT ?? "5889"}`;
test.use({ baseURL: REAL_STATE_BASE_URL });
fs.mkdirSync(output, { recursive: true });
const pngSize = (filename) => {
  if (!fs.existsSync(filename)) return null;
  const b = fs.readFileSync(filename); return { width: b.readUInt32BE(16), height: b.readUInt32BE(20) };
};

test.describe("market overview Figma v1.4 browser acceptance", () => {
  for (const width of [1440, 1024, 390]) {
    test(`synthetic design fixture at ${width}px`, async ({ page }) => {
      const reads = await interceptDesignData(page);
      await page.setViewportSize({ width, height: width === 390 ? 844 : 1024 });
      await page.goto("/market-overview", { waitUntil: "domcontentloaded" });
      const root = page.getByTestId("module-workbench-home");
      await expect(root).toBeVisible({ timeout: 60_000 });
      await expect.poll(() => reads.snapshot).toBeGreaterThan(0);
      await expect(page.getByTestId("workbench-terminal-bar")).toHaveCount(0);
      if (width === 1024) {
        const rail = page.locator("#workbench-primary-navigation");
        const opener = page.getByRole("button", { name: "打开主导航", exact: true });
        await expect(rail).not.toBeVisible();
        await opener.focus();
        await page.keyboard.press("Enter");
        await expect(rail).toBeVisible();
        const link = rail.locator('a[href="/market-overview"]').first();
        await link.click({ trial: true });
        await page.keyboard.press("Escape");
        await expect(rail).not.toBeVisible();
        await expect(opener).toBeFocused();
      }
      await page.evaluate(() => document.fonts.ready);
      await expect(root).toContainText("资金价格小幅回落");
      expect(reads.scenario).toBe(0);
      expect(reads.full).toBe(0);
      const risk = page.locator("#market-risk-observation");
      await expect(risk).toBeVisible();
      await expect(page.getByTestId("market-risk-current-score")).toHaveText("—");
      await expect(risk).toContainText("当前待核验");
      await expect(risk).toContainText("近 60 期历史");
      await expect(page.getByTestId("market-home-events-summary").getByText("公开市场操作公告", { exact: true })).toBeVisible();
      await expect(page.getByText("CPI 同比", { exact: true }).first()).toBeVisible();
      const before = path.join(output, `browser-${width}-unloaded.png`);
      await page.screenshot({ path: before, fullPage: true, animations: "disabled" });
      const geometry = await root.evaluate((node) => {
        const rect = (el) => { const r = el.getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height }; };
        return { root: rect(node), viewport: innerWidth, scrollWidth: document.documentElement.scrollWidth, sections: [...node.querySelectorAll("section[id], article[id]")].map((el) => ({ id: el.id, ...rect(el) })), controls: [...node.querySelectorAll("button, a, input, select, summary")].filter((el) => el.getClientRects().length).map((el) => ({ text: el.textContent?.trim().slice(0, 50), ...rect(el) })) };
      });
      const referenceName = width === 1440 ? "desktop-full-v1.4.png" : width === 1024 ? "tablet-full-v1.4.png" : "mobile-full-v1.4.png";
      fs.writeFileSync(path.join(output, `geometry-${width}.json`), JSON.stringify({ reference: pngSize(path.join(design, referenceName)), screenshot: pngSize(before), geometry, limitation: "DOM geometry and screenshot evidence; no pixel parity assertion." }, null, 2));
      expect(geometry.scrollWidth).toBeLessThanOrEqual(width + 2);
      await page.getByRole("button", { name: "加载组合情景", exact: true }).click();
      const scenario = page.getByRole("dialog");
      await expect(scenario).toBeVisible();
      await expect.poll(() => reads.scenario).toBe(1);
      await expect(scenario).toContainText("2026-09-04");
      await scenario.locator(".ant-drawer-close").click();
      await expect(scenario).not.toBeVisible();
      await expect(page.locator("#market-home-scenario")).toContainText("1,250,000");
      await page.evaluate(() => window.scrollTo(0, 0));
      await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
      await page.screenshot({ path: path.join(output, `browser-${width}-loaded.png`), fullPage: true, animations: "disabled" });
      const opener = risk.getByRole("button", { name: "评分依据", exact: true });
      await opener.scrollIntoViewIfNeeded();
      await opener.focus(); await page.keyboard.press("Enter");
      const drawer = page.getByRole("dialog");
      await expect(drawer).toBeVisible();
      await expect.poll(() => reads.full).toBe(1);
      await expect(drawer).toContainText("评分组成");
      await expect(drawer).toContainText("当前评分 —");
      await expect(drawer).toContainText("商品波动");
      await drawer.getByRole("button", { name: "商品扩展与影子分析", exact: true }).click();
      await expect(drawer).toContainText("6 类有记录");
      await expect(drawer.getByRole("textbox", { name: "审批材料原文" })).toHaveAttribute("readonly", "");
      await drawer.getByRole("button", { name: "返回评分依据", exact: true }).click();
      await expect(drawer).toContainText("当前评分 —");
      await page.screenshot({ path: path.join(output, `crisis-drawer-${width}.png`), animations: "disabled" });
      await page.keyboard.press("Escape");
      await expect(drawer).not.toBeVisible();
      await expect(opener).toBeFocused();
      await expect(page.getByTestId("market-risk-current-score")).toHaveText("—");
      if (width === 390) {
        for (const control of await risk.locator("button, a").all()) {
          const box = await control.boundingBox();
          expect(box.height, await control.textContent()).toBeGreaterThanOrEqual(44);
        }
      }
      if (width === 1440) {
        const nav = page.getByTestId("module-home-market-chapter-nav");
        await nav.getByRole("link", { name: "专题图表", exact: true }).click();
        const topics = page.locator("#market-financial-charts-all");
        await expect(topics).toHaveAttribute("open");
        await expect(topics.locator('[data-testid^="module-home-market-chart-"]')).toHaveCount(12);
        for (const ref of await topics.locator('[data-chart-view="reference"] a[href^="#"]').all()) {
          await expect(page.locator(await ref.getAttribute("href"))).toHaveCount(1);
        }
        await nav.getByRole("link", { name: "全部行情", exact: true }).click();
        await expect(page.locator("#market-backend-data-all")).toHaveAttribute("open");
        await expect(page.locator("#market-backend-data-all").getByRole("table").first()).toBeVisible();
      }
      expect(reads.errors).toEqual([]);
      expect(reads.writes).toEqual([]);
    });
  }

  test("real HTTP publication state and source return with synthetic responses", async ({ page }) => {
    const reads = await interceptDesignData(page);
    await page.setViewportSize({ width: 1440, height: 1024 });
    const response = page.waitForResponse(r => new URL(r.url()).pathname === "/ui/market-overview/snapshot" && r.ok());
    await page.goto("/market-overview", { waitUntil: "domcontentloaded" });
    const payload = (await (await response).json()).result;
    const score = page.getByTestId("market-risk-current-score");
    await expect(score).toBeVisible({ timeout: 60_000 });
    if (payload.crisis.current_available === false || payload.crisis.history_only === true) await expect(score).toHaveText("—");
    await expect(page.locator("#market-risk-observation")).toContainText(payload.crisis.report_date);
    await page.getByRole("button", { name: "宏观详情", exact: true }).click();
    const drawer = page.getByRole("dialog");
    await expect(drawer).toBeVisible();
    await drawer.getByRole("link", { name: "进入宏观观察", exact: true }).click();
    await expect(page).toHaveURL(/\/macro-observation\?.*origin=market-overview/);
    await expect(page.getByRole("complementary", { name: "市场总览来源" })).toBeVisible();
    await expect(page.getByTestId("macro-observation-page")).toBeVisible();
    await expect(page.getByTestId("macro-observation-loading-note")).not.toBeVisible();
    await expect(page.getByTestId("macro-observation-error-state")).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "当日观察结论", exact: true })).toBeVisible();
    expect(reads.paths).toContain("/ui/macro/toolkit/analysis");
    await page.getByRole("link", { name: "返回市场总览", exact: true }).click();
    await expect(page).toHaveURL(/\/market-overview#market-overview-evidence$/);
    await expect(page.getByTestId("market-home-macro-summary")).toBeVisible();
    expect(reads.writes).toEqual([]);
    expect(reads.errors).toEqual([]);
    await page.screenshot({ path: path.join(output, "live-return-1440.png"), fullPage: false, animations: "disabled" });
  });
});
