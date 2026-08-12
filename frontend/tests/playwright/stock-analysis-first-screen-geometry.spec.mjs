import { test, expect } from "@playwright/test";

/**
 * Real-browser geometry guard for the stock-analysis decision first screen.
 *
 * Motivation: the page CSS accumulated ~20k lines of layered grid overrides;
 * a stale `grid-template-areas` shell once squeezed the first-screen cards to
 * 195px and threw the evidence disclosure into a phantom side column. jsdom
 * cannot catch that class of bug, so the layout contract is asserted here
 * against the rendered cascade instead of against CSS source text.
 */

const BASE_URL = process.env.MOSS_PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5888";

const rectOf = (locator) =>
  locator.evaluate((el) => {
    const b = el.getBoundingClientRect();
    return { x: b.x, y: b.y, w: b.width, h: b.height, bottom: b.y + b.height };
  });

async function openFirstScreen(page, viewport) {
  await page.setViewportSize(viewport);
  await page.goto(`${BASE_URL}/stock-analysis`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector('[data-testid="stock-analysis-decision-first-screen"]', {
    timeout: 60_000,
  });
  // Deferred sections and the sector chart settle shortly after first paint.
  await page.waitForTimeout(1500);
}

async function collectFirstScreenRects(page) {
  const get = (testId) => rectOf(page.getByTestId(testId).first());
  return {
    workbench: await get("stock-analysis-first-screen-workbench"),
    decision: await get("stock-analysis-decision-first-screen"),
    hero: await get("stock-analysis-decision-panel"),
    gate: await get("stock-analysis-gate-conditions-card"),
    macro: await get("stock-analysis-macro-cycle-card"),
    sector: await get("stock-analysis-sector-strength-card"),
    factor: await get("stock-analysis-factor-candidates-card"),
    rail: await get("stock-analysis-first-screen-rail"),
    evidence: await get("stock-analysis-evidence-disclosure"),
  };
}

function assertSingleColumnLayout(r) {
  // The decision screen owns the full row: no phantom aside column may steal width.
  expect(r.decision.w).toBeGreaterThan(r.workbench.w * 0.95);
  expect(r.hero.w).toBeGreaterThan(r.decision.w * 0.95);

  // Gate / macro / sector sit on one row with equal widths.
  expect(Math.abs(r.gate.y - r.macro.y)).toBeLessThanOrEqual(2);
  expect(Math.abs(r.macro.y - r.sector.y)).toBeLessThanOrEqual(2);
  expect(Math.abs(r.gate.w - r.macro.w)).toBeLessThanOrEqual(4);
  expect(Math.abs(r.macro.w - r.sector.w)).toBeLessThanOrEqual(4);
  expect(r.gate.w).toBeGreaterThan(280);

  // Factor table and the review/gap rail share a row; the rail keeps a sane width.
  expect(Math.abs(r.factor.y - r.rail.y)).toBeLessThanOrEqual(2);
  expect(r.rail.w).toBeGreaterThanOrEqual(260);
  expect(r.rail.w).toBeLessThanOrEqual(380);
  expect(r.factor.w + r.rail.w).toBeGreaterThan(r.decision.w * 0.9);

  // Evidence disclosure stays a full-width collapsed strip below the first screen.
  expect(r.evidence.w).toBeGreaterThan(r.workbench.w * 0.95);
  expect(r.evidence.h).toBeLessThan(100);
  expect(r.evidence.y).toBeGreaterThanOrEqual(r.factor.bottom - 5);
}

test.describe("stock-analysis first-screen geometry", () => {
  test("keeps the decision first screen single-column at desktop width", async ({ page }) => {
    await openFirstScreen(page, { width: 1920, height: 1080 });
    assertSingleColumnLayout(await collectFirstScreenRects(page));
  });

  test("keeps the decision first screen single-column at 1280 width", async ({ page }) => {
    await openFirstScreen(page, { width: 1280, height: 900 });
    assertSingleColumnLayout(await collectFirstScreenRects(page));
  });

  test("keeps macro layer name, weight, and status from overlapping", async ({ page }) => {
    await openFirstScreen(page, { width: 1920, height: 1080 });
    const overlaps = await page.evaluate(() => {
      const rows = document.querySelectorAll(".stock-analysis-page__fs-macro-layers > li");
      const issues = [];
      for (const row of rows) {
        const parts = [
          row.querySelector(".stock-analysis-page__fs-macro-layer-name"),
          row.querySelector("small"),
          row.querySelector("em"),
        ].filter(Boolean);
        for (let i = 0; i < parts.length - 1; i += 1) {
          const left = parts[i].getBoundingClientRect();
          const right = parts[i + 1].getBoundingClientRect();
          if (right.x < left.x + left.width - 1) {
            issues.push(`${row.textContent?.trim().slice(0, 30)}`);
          }
        }
      }
      return issues;
    });
    expect(overlaps).toEqual([]);
  });

  /**
   * Density guard for the observation-pool queue: the section once spent 569px
   * on a single 141px lead card plus two collapsed layers. The queue must stay a
   * dense ledger at the factor-table rhythm instead of regrowing hero cards.
   */
  test("keeps the observation queue dense with every candidate row visible", async ({ page }) => {
    await openFirstScreen(page, { width: 1920, height: 1080 });
    await page.waitForSelector('[data-testid="stock-analysis-candidate-dense-table"]', {
      timeout: 60_000,
    });

    const rows = await page.evaluate(() => {
      const table = document.querySelector('[data-testid="stock-analysis-candidate-dense-table"]');
      if (!table) return [];
      return [...table.querySelectorAll("tbody tr")].map((row) => ({
        id: row.getAttribute("data-testid") ?? "",
        h: row.getBoundingClientRect().height,
        visible: row.getBoundingClientRect().height > 0 && row.getBoundingClientRect().width > 0,
      }));
    });

    const visibleRows = rows.filter((row) => row.visible);
    expect(visibleRows.length).toBeGreaterThanOrEqual(8);
    expect(Math.max(...visibleRows.map((row) => row.h))).toBeLessThanOrEqual(28);
  });

  test("keeps the first screen free of horizontal overflow", async ({ page }) => {
    await openFirstScreen(page, { width: 1280, height: 900 });
    const overflowing = await page.evaluate(() => {
      const root = document.querySelector('[data-testid="stock-analysis-decision-first-screen"]');
      if (!root) return ["missing first screen"];
      return [...root.querySelectorAll("*")]
        .filter(
          (el) =>
            el.scrollWidth - el.clientWidth > 2 && getComputedStyle(el).overflowX === "visible",
        )
        .slice(0, 5)
        .map((el) => `${el.tagName}.${String(el.className).slice(0, 60)}`);
    });
    expect(overflowing).toEqual([]);
  });
});
