import { expect, test } from "@playwright/test";

async function openMarketData(page, viewport, suffix = "") {
  await page.setViewportSize(viewport);
  await page.goto(`/market-data${suffix}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("market-data-page")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("market-data-kpi-band")).toBeVisible({ timeout: 60_000 });
}

async function readSurface(locator) {
  return locator.evaluate((element) => {
    const style = getComputedStyle(element);
    return {
      borderTopWidth: style.borderTopWidth,
      borderLeftWidth: style.borderLeftWidth,
      backgroundColor: style.backgroundColor,
      boxShadow: style.boxShadow,
    };
  });
}

async function expectNeutralSurface(locator) {
  const surface = await readSurface(locator);
  expect.soft(surface.borderTopWidth).toBe("0px");
  expect.soft(surface.backgroundColor).toBe("rgba(0, 0, 0, 0)");
  expect.soft(surface.boxShadow).toBe("none");
}

async function expectFramedSurface(locator) {
  const surface = await readSurface(locator);
  expect(Number.parseFloat(surface.borderTopWidth)).toBeGreaterThan(0);
}

test.describe("market data layout primitives", () => {
  test("keeps one framed primitive at each desktop hierarchy level", async ({ page }) => {
    const desktop = { width: 1440, height: 900 };
    await openMarketData(page, desktop);

    const hero = page.getByTestId("market-data-hero");
    const heroStatus = hero.locator(":scope > [data-testid='market-data-status-strip']");
    await expect(heroStatus).toHaveCount(1);
    await expect(hero.locator(".moss-page-v2-decision-hero__conclusion")).toHaveCount(0);
    expect.soft((await readSurface(heroStatus)).borderLeftWidth).toBe("3px");

    const extendedTerminalMount = page.locator('[data-lazy-mount="extended-terminal"]');
    await extendedTerminalMount.scrollIntoViewIfNeeded();
    const extendedTerminalSection = page.getByTestId("market-data-extended-terminal-section");
    await expect(extendedTerminalSection).toBeVisible({ timeout: 60_000 });
    await expectNeutralSurface(extendedTerminalSection);
    await expectFramedSurface(page.getByTestId("market-data-extended-terminal-collapse"));

    const tushareCollapse = page.getByTestId("market-data-tushare-collapse");
    await tushareCollapse.scrollIntoViewIfNeeded();
    await tushareCollapse.locator(".ant-collapse-header").first().click();
    const tushareContent = tushareCollapse.locator(
      ".ant-collapse-content-box > .market-data-lower-deck-section",
    );
    await expect(tushareContent).toBeVisible({ timeout: 60_000 });
    await expectNeutralSurface(tushareContent);
    await expectFramedSurface(tushareContent.locator(".market-data-tushare-panel").first());

    await openMarketData(page, desktop, "?view=explorer");
    const explorer = page.getByTestId("market-data-explorer-view");
    await expect(explorer).toBeVisible({ timeout: 60_000 });
    await expectNeutralSurface(explorer);
    await expectFramedSurface(explorer.locator(".market-data-explorer__directory").first());
  });

  test("keeps the formal rates board within the desktop baseline", async ({ page }) => {
    await openMarketData(page, { width: 1440, height: 900 });

    const distance = await page.evaluate(() => {
      const hero = document.querySelector('[data-testid="market-data-hero"]');
      const formalRatesBoard = document.querySelector(
        '[data-testid="market-data-formal-rates-board"]',
      );
      if (!(hero instanceof HTMLElement) || !(formalRatesBoard instanceof HTMLElement)) {
        throw new Error("Market data baseline anchors are missing");
      }
      return formalRatesBoard.getBoundingClientRect().bottom - hero.getBoundingClientRect().top;
    });

    expect(distance).toBeLessThanOrEqual(1281);
  });

  test("keeps the formal rates grid as a balanced 2x2 board on desktop", async ({ page }) => {
    await openMarketData(page, { width: 1440, height: 900 });

    const formalGrid = page.locator(".market-data-formal-rates-grid");
    await expect(formalGrid).toBeVisible();
    await expect(page.getByTestId("market-data-rate-quote-table")).toBeVisible();
    await expect(page.getByTestId("market-data-key-rate-list")).toBeVisible();
    await expect(page.getByTestId("market-data-rate-trend-panel")).toBeVisible();
    await expect(page.getByTestId("market-data-formal-rates-curve")).toBeVisible();

    const layout = await page.evaluate(() => {
      const grid = document.querySelector(".market-data-formal-rates-grid");
      const quote = document.querySelector('[data-testid="market-data-rate-quote-table"]');
      const key = document.querySelector('[data-testid="market-data-key-rate-list"]');
      const trend = document.querySelector('[data-testid="market-data-rate-trend-panel"]');
      const curve = document.querySelector('[data-testid="market-data-formal-rates-curve"]');
      if (
        !(grid instanceof HTMLElement) ||
        !(quote instanceof HTMLElement) ||
        !(key instanceof HTMLElement) ||
        !(trend instanceof HTMLElement) ||
        !(curve instanceof HTMLElement)
      ) {
        throw new Error("Formal grid anchors are missing");
      }
      const gridRect = grid.getBoundingClientRect();
      const quoteRect = quote.getBoundingClientRect();
      const keyRect = key.getBoundingClientRect();
      const trendRect = trend.getBoundingClientRect();
      const curveRect = curve.getBoundingClientRect();
      return {
        quoteKeyTopDelta: Math.abs(quoteRect.top - keyRect.top),
        trendCurveTopDelta: Math.abs(trendRect.top - curveRect.top),
        secondRowStartsAfterFirstRow: Math.min(trendRect.top, curveRect.top) - Math.max(quoteRect.bottom, keyRect.bottom),
        gridHeight: gridRect.height,
        quoteWidthRatio: quoteRect.width / gridRect.width,
        keyWidthRatio: keyRect.width / gridRect.width,
        trendWidthRatio: trendRect.width / gridRect.width,
        curveWidthRatio: curveRect.width / gridRect.width,
      };
    });

    expect(layout.quoteKeyTopDelta).toBeLessThanOrEqual(1);
    expect(layout.trendCurveTopDelta).toBeLessThanOrEqual(1);
    expect(layout.secondRowStartsAfterFirstRow).toBeGreaterThanOrEqual(0);
    expect(layout.gridHeight).toBeLessThanOrEqual(760);
    expect(layout.quoteWidthRatio).toBeGreaterThanOrEqual(0.45);
    expect(layout.quoteWidthRatio).toBeLessThanOrEqual(0.52);
    expect(layout.keyWidthRatio).toBeGreaterThanOrEqual(0.45);
    expect(layout.keyWidthRatio).toBeLessThanOrEqual(0.52);
    expect(layout.trendWidthRatio).toBeGreaterThanOrEqual(0.45);
    expect(layout.trendWidthRatio).toBeLessThanOrEqual(0.52);
    expect(layout.curveWidthRatio).toBeGreaterThanOrEqual(0.45);
    expect(layout.curveWidthRatio).toBeLessThanOrEqual(0.52);
  });

  test("keeps hero actions and status on the same desktop command row", async ({ page }) => {
    await openMarketData(page, { width: 1440, height: 900 });

    const hero = page.getByTestId("market-data-hero");
    const heroStatus = hero.locator(":scope > [data-testid='market-data-status-strip']");
    const heroActions = hero.locator(".market-data-hero-actions");
    const kpiBand = hero.locator(":scope > [data-testid='market-data-kpi-band']");
    await expect(heroStatus).toHaveCount(1);
    await expect(heroActions).toBeVisible();
    await expect(kpiBand).toBeVisible();

    const layout = await page.evaluate(() => {
      const heroElement = document.querySelector('[data-testid="market-data-hero"]');
      const status = heroElement?.querySelector(':scope > [data-testid="market-data-status-strip"]');
      const actions = heroElement?.querySelector(".market-data-hero-actions");
      const kpi = heroElement?.querySelector(':scope > [data-testid="market-data-kpi-band"]');
      if (
        !(status instanceof HTMLElement) ||
        !(actions instanceof HTMLElement) ||
        !(kpi instanceof HTMLElement)
      ) {
        throw new Error("Hero command row anchors are missing");
      }

      const statusRect = status.getBoundingClientRect();
      const actionsRect = actions.getBoundingClientRect();
      const kpiRect = kpi.getBoundingClientRect();
      return {
        centerDelta: Math.abs(
          statusRect.top + statusRect.height / 2 - (actionsRect.top + actionsRect.height / 2),
        ),
        kpiTop: kpiRect.top,
        commandRowBottom: Math.max(statusRect.bottom, actionsRect.bottom),
      };
    });

    expect(layout.centerDelta).toBeLessThanOrEqual(2);
    expect(layout.kpiTop).toBeGreaterThanOrEqual(layout.commandRowBottom);
  });

  test("keeps the NCD card body close to its content on desktop", async ({ page }) => {
    await openMarketData(page, { width: 1440, height: 900 });

    const ncdCard = page.getByTestId("market-data-ncd-card");
    await ncdCard.scrollIntoViewIfNeeded();
    await expect(ncdCard).toBeVisible();

    const trailingGap = await ncdCard.evaluate((card) => {
      const body = card.querySelector(".market-data-series-category-card__body");
      if (!(body instanceof HTMLElement)) {
        throw new Error("NCD card body is missing");
      }

      const visibleElements = Array.from(body.querySelectorAll("*")).filter((element) => {
        if (!(element instanceof HTMLElement)) {
          return false;
        }
        const style = getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return (
          style.display !== "none" &&
          style.visibility !== "hidden" &&
          rect.width > 0 &&
          rect.height > 0
        );
      });

      const deepestBottom = visibleElements.reduce((bottom, element) => {
        return Math.max(bottom, element.getBoundingClientRect().bottom);
      }, body.getBoundingClientRect().top);

      return card.getBoundingClientRect().bottom - deepestBottom;
    });

    expect(trailingGap).toBeLessThanOrEqual(24);
  });

  test("shows a readable label before the extended terminal block mounts", async ({ page }) => {
    await openMarketData(page, { width: 1440, height: 900 });

    const placeholder = page.locator(
      '[data-lazy-mount="extended-terminal"] .market-data-lazy-placeholder',
    );
    await expect(placeholder).toBeVisible();
    await expect(placeholder).toContainText(/\S+/);
  });

  test("keeps the extended terminal placeholder compact before mount", async ({ page }) => {
    await openMarketData(page, { width: 1440, height: 900 });

    const placeholder = page.locator(
      '[data-lazy-mount="extended-terminal"] .market-data-lazy-placeholder',
    );
    await expect(placeholder).toBeVisible();

    const height = await placeholder.evaluate((element) => element.getBoundingClientRect().height);
    expect(height).toBeLessThanOrEqual(112);
  });

  test("does not overflow the tablet viewport", async ({ page }) => {
    await openMarketData(page, { width: 768, height: 1024 });

    const viewport = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }));
    expect(viewport.scrollWidth).toBeLessThanOrEqual(viewport.clientWidth + 1);
  });

  test("switches the hero and formal rates board to one column at the 1100px boundary", async ({ page }) => {
    await openMarketData(page, { width: 1100, height: 900 });

    const layout = await page.evaluate(() => {
      const hero = document.querySelector('[data-testid="market-data-hero"]');
      const status = hero?.querySelector(':scope > [data-testid="market-data-status-strip"]');
      const actions = hero?.querySelector(".market-data-hero-actions");
      const panels = [
        document.querySelector('[data-testid="market-data-rate-quote-table"]'),
        document.querySelector('[data-testid="market-data-key-rate-list"]'),
        document.querySelector('[data-testid="market-data-rate-trend-panel"]'),
        document.querySelector('[data-testid="market-data-formal-rates-curve"]'),
      ];
      if (
        !(status instanceof HTMLElement) ||
        !(actions instanceof HTMLElement) ||
        panels.some((panel) => !(panel instanceof HTMLElement))
      ) {
        throw new Error("Market data 1100px boundary anchors are missing");
      }

      const statusRect = status.getBoundingClientRect();
      const actionsRect = actions.getBoundingClientRect();
      const panelRects = panels.map((panel) => panel.getBoundingClientRect());
      return {
        actionsStartAfterStatus: actionsRect.top - statusRect.bottom,
        panelLeftSpread: Math.max(...panelRects.map((rect) => rect.left)) -
          Math.min(...panelRects.map((rect) => rect.left)),
        panelWidthSpread: Math.max(...panelRects.map((rect) => rect.width)) -
          Math.min(...panelRects.map((rect) => rect.width)),
        panelTopOrder: panelRects.map((rect) => rect.top),
      };
    });

    expect(layout.actionsStartAfterStatus).toBeGreaterThanOrEqual(0);
    expect(layout.panelLeftSpread).toBeLessThanOrEqual(1);
    expect(layout.panelWidthSpread).toBeLessThanOrEqual(1);
    expect(layout.panelTopOrder).toEqual([...layout.panelTopOrder].sort((left, right) => left - right));
  });

  test("does not overflow the mobile viewport", async ({ page }) => {
    await openMarketData(page, { width: 390, height: 844 });

    const viewport = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }));
    expect(viewport.scrollWidth).toBeLessThanOrEqual(viewport.clientWidth + 1);
  });
});
