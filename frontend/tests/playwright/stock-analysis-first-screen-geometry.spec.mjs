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
 * The selected desktop composition is a dense three-window terminal: a 309px
 * candidate ledger, a flexible dossier, a 247px action rail, and a full-width
 * audit ledger below. Narrow viewports deliberately collapse that relationship.
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
  test("matches the selected three-window desktop geometry at the reference width", async ({ page }) => {
    await openResearchDesk(page, { width: 1487, height: 1058 });
    const rects = await collectDeskRects(page);

    expect(rects.pool.w).toBeGreaterThanOrEqual(305);
    expect(rects.pool.w).toBeLessThanOrEqual(312);
    expect(rects.dossier.w).toBeGreaterThanOrEqual(732);
    expect(rects.dossier.w).toBeLessThanOrEqual(744);
    expect(rects.rail.w).toBeGreaterThanOrEqual(244);
    expect(rects.rail.w).toBeLessThanOrEqual(250);
    expect(Math.abs(rects.pool.y - rects.dossier.y)).toBeLessThanOrEqual(1);
    expect(Math.abs(rects.dossier.y - rects.rail.y)).toBeLessThanOrEqual(1);
    expect(rects.audit.y).toBeGreaterThanOrEqual(rects.pool.bottom + 8);
    expect(rects.audit.w).toBeGreaterThan(rects.desk.w * 0.98);
  });

  test("keeps the candidate ledger dense and free of nested controls", async ({ page }) => {
    await openResearchDesk(page, { width: 1487, height: 1058 });
    const rows = page.locator('[data-testid="stock-analysis-review-queue"] [class*="poolRow"]');
    const rowCount = await rows.count();
    expect(rowCount).toBeGreaterThan(0);
    expect(rowCount).toBeLessThanOrEqual(11);
    for (let index = 0; index < rowCount; index += 1) {
      expect((await rectOf(rows.nth(index))).h).toBeLessThanOrEqual(42);
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

  test("keeps the three-window relationship across desktop widths", async ({ page }) => {
    await openResearchDesk(page, GEOMETRY_VIEWPORTS[1]);
    const wide = await collectDeskRects(page);
    expect(wide.rail.x).toBeGreaterThan(wide.dossier.x);
    expect(Math.abs(wide.rail.y - wide.dossier.y)).toBeLessThanOrEqual(1);

    await openResearchDesk(page, GEOMETRY_VIEWPORTS[3]);
    const compact = await collectDeskRects(page);
    expect(compact.rail.x).toBeGreaterThan(compact.dossier.x);
    expect(Math.abs(compact.rail.y - compact.dossier.y)).toBeLessThanOrEqual(1);
    expect(compact.rail.w).toBeGreaterThanOrEqual(200);
  });
});
