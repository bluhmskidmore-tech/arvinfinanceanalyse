import { test, expect } from "@playwright/test";

test.beforeEach(async ({ context, baseURL }) => {
  await context.route("**/*", (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== new URL(baseURL).origin || /^\/(api|ui|health)(\/|$)/.test(url.pathname)) return route.abort();
    return route.continue();
  });
});

/**
 * Real-browser geometry guard for the stock-analysis research desk.
 *
 * The dossier keeps the primary reading space. The candidate ledger and action
 * rail sit alongside it when the content container has room; with the workbench
 * sidebar present they share the left column, then stack on narrow screens.
 * The audit ledger always spans the available content width.
 */

const BASE_URL = process.env.MOSS_PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5888";
const GEOMETRY_VIEWPORTS = [
  { label: "ultrawide", width: 2708, height: 900 },
  { label: "desktop-xl", width: 1920, height: 1080 },
  { label: "desktop-lg", width: 1440, height: 900 },
  { label: "desktop", width: 1280, height: 900 },
  { label: "laptop", width: 1024, height: 768 },
  { label: "tablet", width: 768, height: 1024 },
  { label: "mobile", width: 390, height: 844 },
];

const rectOf = (locator) =>
  locator.evaluate((element) => {
    const box = element.getBoundingClientRect();
    return {
      x: box.x,
      y: box.y,
      right: box.right,
      bottom: box.bottom,
      w: box.width,
      h: box.height,
    };
  });

async function openResearchDesk(page, viewport) {
  await page.setViewportSize(viewport);
  await page.goto(`${BASE_URL}/stock-analysis`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector('[data-testid="stock-analysis-research-desk"]', {
    timeout: 60_000,
  });
  await page.waitForTimeout(1200);
}

async function collectDeskRects(page) {
  const get = (testId) => rectOf(page.getByTestId(testId).first());
  return {
    desk: await get("stock-analysis-research-desk"),
    pool: await get("stock-analysis-review-queue"),
    dossier: await get("stock-analysis-research-dossier"),
    rail: await get("stock-analysis-action-rail"),
    audit: await get("stock-analysis-research-audit"),
  };
}

async function collectToolbarGeometry(page) {
  return page.evaluate(() => {
    const rect = (element) => {
      if (!element) return null;
      const box = element.getBoundingClientRect();
      return {
        left: box.left,
        top: box.top,
        right: box.right,
        bottom: box.bottom,
        width: box.width,
        height: box.height,
      };
    };

    const compactChrome = document.querySelector('[data-testid="stock-analysis-page-compact-chrome"]');
    const toolbarOwner = document.querySelector('[data-testid="stock-analysis-page-toolbar-owner"]');
    const toolbarActions = toolbarOwner?.querySelector(".stock-analysis-page__workbench-actions") ?? null;
    const datePicker = toolbarOwner?.querySelector('[data-testid="stock-analysis-as-of-picker"]') ?? null;
    const searchInput = toolbarOwner?.querySelector('[data-testid="stock-analysis-queue-search"]');
    const searchShell = searchInput?.closest("label") ?? null;
    const refreshButton = toolbarOwner?.querySelector('[data-testid="stock-analysis-refresh"]') ?? null;

    return {
      compactChrome: rect(compactChrome),
      toolbarOwner: rect(toolbarOwner),
      actions: rect(toolbarActions),
      datePicker: rect(datePicker),
      searchShell: rect(searchShell),
      refreshButton: rect(refreshButton),
      compactChromeScrollWidth: compactChrome?.scrollWidth ?? 0,
      compactChromeClientWidth: compactChrome?.clientWidth ?? 0,
      toolbarOwnerScrollWidth: toolbarOwner?.scrollWidth ?? 0,
      toolbarOwnerClientWidth: toolbarOwner?.clientWidth ?? 0,
      actionsScrollWidth: toolbarActions?.scrollWidth ?? 0,
      actionsClientWidth: toolbarActions?.clientWidth ?? 0,
    };
  });
}

function overlaps(a, b) {
  return !(
    a.right <= b.left + 1 ||
    b.right <= a.left + 1 ||
    a.bottom <= b.top + 1 ||
    b.bottom <= a.top + 1
  );
}

function expectWithinViewport(rect, viewport, label) {
  expect(rect, `${label} should exist`).not.toBeNull();
  expect(rect.left, `${label} starts outside the viewport`).toBeGreaterThanOrEqual(-1);
  expect(rect.right, `${label} ends outside the viewport`).toBeLessThanOrEqual(viewport.width + 1);
}

function assertToolbarLayout(geometry, viewport) {
  expect(geometry.compactChrome).not.toBeNull();
  expect(geometry.toolbarOwner).not.toBeNull();
  expect(geometry.actions).not.toBeNull();
  expect(geometry.compactChromeScrollWidth - geometry.compactChromeClientWidth).toBeLessThanOrEqual(1);
  expect(geometry.toolbarOwnerScrollWidth - geometry.toolbarOwnerClientWidth).toBeLessThanOrEqual(1);
  expect(geometry.actionsScrollWidth - geometry.actionsClientWidth).toBeLessThanOrEqual(1);

  const controls = [
    ["date picker", geometry.datePicker],
    ["search shell", geometry.searchShell],
    ["refresh button", geometry.refreshButton],
  ];
  controls.forEach(([label, rect]) => expectWithinViewport(rect, viewport, label));

  expect(overlaps(geometry.datePicker, geometry.searchShell)).toBe(false);
  expect(overlaps(geometry.searchShell, geometry.refreshButton)).toBe(false);
}

test.describe("stock-analysis research-desk geometry", () => {
  test("adapts the research panels to the available content width", async ({ page }) => {
    for (const viewport of [
      GEOMETRY_VIEWPORTS[1],
      { width: 1487, height: 1058 },
      GEOMETRY_VIEWPORTS[5],
    ]) {
      await openResearchDesk(page, viewport);
      const rects = await collectDeskRects(page);

      if (viewport.width === 1920) {
        expect(rects.pool.right).toBeLessThan(rects.dossier.x);
        expect(rects.dossier.right).toBeLessThan(rects.rail.x);
        expect(Math.abs(rects.pool.y - rects.dossier.y)).toBeLessThanOrEqual(1);
        expect(Math.abs(rects.dossier.y - rects.rail.y)).toBeLessThanOrEqual(1);
        expect(rects.dossier.w).toBeGreaterThan(Math.max(rects.pool.w, rects.rail.w));
      } else if (viewport.width === 1487) {
        expect(rects.pool.right).toBeLessThan(rects.dossier.x);
        expect(Math.abs(rects.pool.y - rects.dossier.y)).toBeLessThanOrEqual(1);
        expect(Math.abs(rects.pool.x - rects.rail.x)).toBeLessThanOrEqual(1);
        expect(Math.abs(rects.pool.w - rects.rail.w)).toBeLessThanOrEqual(1);
        expect(rects.rail.y).toBeGreaterThan(rects.pool.bottom);
        expect(rects.rail.right).toBeLessThan(rects.dossier.x);
        expect(rects.dossier.w).toBeGreaterThan(rects.pool.w);
      } else {
        expect(Math.abs(rects.pool.x - rects.dossier.x)).toBeLessThanOrEqual(1);
        expect(Math.abs(rects.dossier.x - rects.rail.x)).toBeLessThanOrEqual(1);
        expect(rects.dossier.y).toBeGreaterThan(rects.pool.bottom);
        expect(rects.rail.y).toBeGreaterThan(rects.dossier.bottom);
        for (const panel of [rects.pool, rects.dossier, rects.rail]) {
          expect(panel.w).toBeGreaterThan(rects.desk.w * 0.98);
        }
      }

      expect(rects.audit.y).toBeGreaterThanOrEqual(Math.max(rects.pool.bottom, rects.dossier.bottom, rects.rail.bottom) + 8);
      expect(rects.audit.w).toBeGreaterThan(rects.desk.w * 0.98);
    }
  });

  test("keeps candidate identities and signals readable without nested controls", async ({ page }) => {
    await openResearchDesk(page, { width: 1487, height: 1058 });
    const rows = page.locator('[data-testid="stock-analysis-review-queue"] [class*="poolRow"]');
    const rowCount = await rows.count();
    expect(rowCount).toBeGreaterThan(0);
    expect(rowCount).toBeLessThanOrEqual(11);
    for (let index = 0; index < rowCount; index += 1) {
      const row = rows.nth(index);
      await expect(row.getByRole("button")).toHaveCount(1);
      for (const selector of [
        '[class*="poolIdentity"] strong',
        '[class*="poolIdentity"] strong span',
        '[class*="poolScore"]',
        '[class*="poolChange"]',
        '[class*="poolSignal"]',
      ]) {
        const field = row.locator(selector);
        await expect(field).toBeVisible();
        expect((await field.textContent()).trim()).not.toBe("");
        expect(await field.evaluate((element) => element.scrollWidth - element.clientWidth)).toBeLessThanOrEqual(1);
      }
      const signal = row.locator('[class*="poolSignal"]');
      await expect(signal).toHaveAttribute("title", (await signal.textContent()).trim());
    }
    expect(await page.locator("button button, a button, button a").count()).toBe(0);
  });

  test("renders the live price chart, action stack, note field, and audit rows together", async ({ page }) => {
    await openResearchDesk(page, { width: 1487, height: 1058 });
    await expect(page.getByTestId("stock-analysis-research-dossier").locator("canvas")).toHaveCount(2);
    await expect(page.getByRole("button", { name: "开始深度研究" })).toBeVisible();
    const note = page.getByRole("textbox", { name: "研究备注", exact: true });
    await expect(note).toBeVisible();
    await note.fill("关注成交量与研究证据完整性");
    await page.getByRole("button", { name: "保存", exact: true }).click();
    await expect(note.locator("..").locator('[class*="noteMeta"] span')).toContainText("关注成交量与研究证据完整性");
    expect(
      await page.getByTestId("stock-analysis-research-audit").locator('[class*="auditTableRow"]').count(),
    ).toBeGreaterThanOrEqual(2);
  });

  test("keeps stage navigation available from the compact research menu", async ({ page }) => {
    await openResearchDesk(page, { width: 1487, height: 1058 });
    const summary = page.getByText("策略阶段", { exact: true });
    await summary.click();
    await expect(page.getByRole("navigation", { name: "股票策略阶段" })).toBeVisible();
    await expect(page.getByRole("link", { name: /组合构建/ })).toBeVisible();
  });

  for (const viewport of GEOMETRY_VIEWPORTS) {
    test(`keeps the chrome and research desk overflow-safe at ${viewport.label}`, async ({ page }) => {
      await openResearchDesk(page, viewport);
      assertToolbarLayout(await collectToolbarGeometry(page), viewport);

      const overflow = await page.evaluate(() => ({
        document: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        desk: (() => {
          const element = document.querySelector('[data-testid="stock-analysis-research-desk"]');
          return element ? element.scrollWidth - element.clientWidth : 999;
        })(),
      }));
      expect(overflow.document).toBeLessThanOrEqual(1);
      expect(overflow.desk).toBeLessThanOrEqual(1);
    });
  }

  test("keeps candidate selection and research notes reachable on compact desktops", async ({ page }) => {
    await openResearchDesk(page, GEOMETRY_VIEWPORTS[3]);
    const compact = await collectDeskRects(page);
    expect(compact.pool.right).toBeLessThan(compact.dossier.x);
    expect(compact.rail.y).toBeGreaterThan(compact.pool.bottom);
    expect(compact.rail.right).toBeLessThan(compact.dossier.x);

    const rows = page.getByTestId("stock-analysis-review-queue").locator('[class*="poolRow"]');
    const candidate = rows.nth(1);
    const identity = await candidate.locator('[class*="poolIdentity"] strong').evaluate((element) => ({
      code: element.firstChild.textContent.trim(),
      name: element.querySelector("span").textContent.trim(),
    }));
    await candidate.getByRole("button").click();
    await expect(candidate).toHaveAttribute("data-active", "true");
    const dossier = page.getByTestId("stock-analysis-research-dossier");
    await expect(dossier.getByRole("heading", { name: `${identity.name} ${identity.code}`, exact: true })).toBeVisible();

    const rail = page.getByTestId("stock-analysis-action-rail");
    const note = rail.getByRole("textbox", { name: "研究备注", exact: true });
    await note.scrollIntoViewIfNeeded();
    await expect(note).toBeInViewport();
    await expect(note).toBeEnabled();
    await note.fill("小屏复核备注：保留来源与边界");
    const save = rail.getByRole("button", { name: "保存", exact: true });
    await save.scrollIntoViewIfNeeded();
    await expect(save).toBeInViewport();
    await save.click();
    await expect(rail.locator('[class*="noteMeta"] span')).toHaveText(`${identity.name} ${identity.code}：小屏复核备注：保留来源与边界`);
  });
});
