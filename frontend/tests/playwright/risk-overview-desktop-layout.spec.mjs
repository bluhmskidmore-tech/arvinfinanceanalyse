import { expect, test } from "@playwright/test";
import { buildMockApiEnvelope } from "../../src/mocks/mockApiEnvelope.ts";

const DESKTOP_VIEWPORT = { width: 1440, height: 900 };
const NARROW_DESKTOP_VIEWPORTS = [
  { width: 1280, height: 720 },
  { width: 1280, height: 900 },
  { width: 1281, height: 900 },
];
const MID_DESKTOP_VIEWPORT = { width: 1366, height: 900 };
const FORMAL_STATE_BASE_URL =
  process.env.MOSS_PLAYWRIGHT_STATE_BASE_URL ??
  (process.env.MOSS_PLAYWRIGHT_USE_WEB_SERVER === "1"
    ? `http://127.0.0.1:${process.env.MOSS_PLAYWRIGHT_STATE_PORT ?? "5889"}`
    : process.env.MOSS_PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5888");
const FIXED_REPORT_DATE = "2026-02-28";
const DISCLOSURE_WARNINGS = [
  "Warning fixture 1",
  "Warning fixture 2",
  "Warning fixture 3",
  "Warning fixture 4",
  "Warning fixture 5",
];
const RISK_SECTION_HREFS = [
  "#risk-overview-actions",
  "#risk-overview-bond-evidence",
  "#risk-overview-briefings",
  "#risk-overview-evidence",
  "#risk-overview-quality",
];

async function gotoRiskOverview(page, viewport) {
  await page.setViewportSize(viewport);
  await page.goto("/risk-overview", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("risk-overview-page")).toBeVisible({
    timeout: 60_000,
  });
}

async function installWarningDisclosureFixture(page) {
  await page.route("**/api/risk/tensor/dates", async (route) => {
    await route.fulfill({
      json: buildMockApiEnvelope("risk.tensor.dates", {
        report_dates: [FIXED_REPORT_DATE],
        blocked_report_dates: [],
      }),
    });
  });
  await page.route("**/api/risk/tensor?*", async (route) => {
    await route.fulfill({
      json: buildMockApiEnvelope("risk.tensor", {
        report_date: FIXED_REPORT_DATE,
        portfolio_dv01: "120000.00000000",
        regulatory_dv01: "120000.00000000",
        krd_1y: "25000.00000000",
        krd_3y: "50000.00000000",
        krd_5y: "30000.00000000",
        krd_7y: "10000.00000000",
        krd_10y: "5000.00000000",
        krd_30y: "0.00000000",
        cs01: "18000.00000000",
        portfolio_convexity: "24.50000000",
        portfolio_modified_duration: "4.20000000",
        issuer_concentration_hhi: "0.12000000",
        issuer_top5_weight: "0.36000000",
        asset_cashflow_30d: "300000000.00000000",
        asset_cashflow_90d: "500000000.00000000",
        liability_cashflow_30d: "200000000.00000000",
        liability_cashflow_90d: "250000000.00000000",
        liquidity_gap_30d: "100000000.00000000",
        liquidity_gap_90d: "250000000.00000000",
        liquidity_gap_30d_ratio: "0.05000000",
        total_market_value: "500000000.00000000",
        rate_risk_market_value: "400000000.00000000",
        rate_risk_dv01: "110000.00000000",
        rate_risk_modified_duration: "4.20000000",
        duration_excluded_market_value: "100000000.00000000",
        duration_excluded_count: 2,
        missing_maturity_market_value: "0.00000000",
        missing_maturity_count: 0,
        floating_rate_proxy_market_value: "0.00000000",
        floating_rate_proxy_count: 0,
        payment_frequency_fallback_market_value: "0.00000000",
        payment_frequency_fallback_count: 0,
        bullet_value_date_fallback_market_value: "0.00000000",
        bullet_value_date_fallback_count: 0,
        projection_quality_status: "available",
        bond_count: 8,
        quality_flag: "warning",
        warnings: DISCLOSURE_WARNINGS,
      }),
    });
  });
}

function riskOverviewRail(page) {
  return page.getByTestId("risk-overview-rail");
}

async function getRiskOverviewGeometry(page) {
  return page.evaluate(() => {
    const toRect = (element) => {
      if (!(element instanceof HTMLElement)) {
        return null;
      }

      const box = element.getBoundingClientRect();
      return {
        top: box.top,
        right: box.right,
        bottom: box.bottom,
        left: box.left,
        width: box.width,
        height: box.height,
      };
    };

    const layout = document.querySelector('[data-testid="risk-overview-layout"]');
    const main = document.querySelector('[data-testid="risk-overview-main"]');
    const rail = document.querySelector('aside[data-testid="risk-overview-rail"]');
    const hero = document.querySelector('[data-testid="risk-overview-hero"]');
    const bondEvidence = document.querySelector(
      '[data-testid="risk-overview-bond-evidence"]',
    );
    const bondBoundary = bondEvidence?.querySelector(":scope > div:nth-of-type(2)");
    const bondBoundaryMessage = bondBoundary?.querySelector("b");
    const bondCards = Array.from(
      document.querySelectorAll(
        '[data-testid="risk-overview-bond-oci"], [data-testid="risk-overview-bond-tpl"]',
      ),
    ).map((card) => ({
      testId: card.getAttribute("data-testid"),
      rect: toRect(card),
    }));

    return {
      layout: toRect(layout),
      main: toRect(main),
      rail: toRect(rail),
      hero: toRect(hero),
      bondBoundaryMessage: toRect(bondBoundaryMessage),
      bondCards,
      horizontalOverflow:
        document.documentElement.scrollWidth - window.innerWidth,
      mainLandmarkCount: document.querySelectorAll("main").length,
    };
  });
}

test("risk overview keeps its desktop content out of the dashboard-home header row", async ({
  page,
}) => {
  await gotoRiskOverview(page, DESKTOP_VIEWPORT);

  const riskPage = page.getByTestId("risk-overview-page");
  const hero = page.getByTestId("risk-overview-hero");
  await expect(hero).toBeVisible({ timeout: 60_000 });

  const geometry = await riskPage.evaluate((element) => {
    const layout = element.querySelector('[data-testid="risk-overview-layout"]');
    const heroElement = element.querySelector('[data-testid="risk-overview-hero"]');
    if (!(layout instanceof HTMLElement) || !(heroElement instanceof HTMLElement)) {
      throw new Error("risk overview layout and hero must be rendered");
    }

    const heroBox = heroElement.getBoundingClientRect();
    return {
      layoutClientHeight: layout.clientHeight,
      layoutScrollHeight: layout.scrollHeight,
      heroTop: heroBox.top,
      pageOverflowY: getComputedStyle(element).overflowY,
    };
  });

  expect(geometry.layoutClientHeight).toBeGreaterThan(DESKTOP_VIEWPORT.height / 2);
  expect(geometry.layoutScrollHeight - geometry.layoutClientHeight).toBeLessThanOrEqual(
    24,
  );
  expect(geometry.heroTop).toBeLessThan(DESKTOP_VIEWPORT.height);
  expect(geometry.pageOverflowY).not.toBe("hidden");
});

for (const viewport of NARROW_DESKTOP_VIEWPORTS) {
  test(`risk overview keeps full-width stacked desktop sections at ${viewport.width}x${viewport.height}`, async ({
    page,
  }) => {
    await gotoRiskOverview(page, viewport);

    await expect(page.getByTestId("risk-overview-layout")).toBeVisible();
    await expect(page.getByTestId("risk-overview-main")).toBeVisible();
    await expect(riskOverviewRail(page)).toBeVisible();

    const geometry = await getRiskOverviewGeometry(page);
    expect(geometry.layout).not.toBeNull();
    expect(geometry.main).not.toBeNull();
    expect(geometry.rail).not.toBeNull();

    expect(geometry.main.width).toBeGreaterThan(geometry.layout.width * 0.94);
    expect(geometry.main.left - geometry.layout.left).toBeLessThanOrEqual(24);
    expect(geometry.layout.right - geometry.main.right).toBeLessThanOrEqual(24);
    expect(geometry.rail.width).toBeGreaterThan(geometry.main.width * 0.94);
    expect(Math.abs(geometry.rail.width - geometry.main.width)).toBeLessThanOrEqual(
      24,
    );
    expect(geometry.rail.left - geometry.main.left).toBeLessThanOrEqual(24);
    expect(geometry.rail.top).toBeGreaterThanOrEqual(geometry.main.bottom - 1);
    expect(geometry.rail.top - geometry.main.bottom).toBeLessThanOrEqual(48);
  });
}

test("risk overview keeps bond evidence readable at 1280px desktop width", async ({
  page,
}) => {
  await gotoRiskOverview(page, { width: 1280, height: 900 });

  const geometry = await getRiskOverviewGeometry(page);
  expect(geometry.bondBoundaryMessage).not.toBeNull();
  expect(geometry.bondBoundaryMessage.width).toBeGreaterThan(80);
  expect(geometry.bondBoundaryMessage.height).toBeGreaterThan(18);
  expect(geometry.bondCards).toHaveLength(2);

  for (const card of geometry.bondCards) {
    expect(card.rect).not.toBeNull();
    expect(card.rect.width).toBeGreaterThanOrEqual(320);
  }
});

test("risk overview keeps the two-column desktop layout readable at 1366px", async ({
  page,
}) => {
  await gotoRiskOverview(page, MID_DESKTOP_VIEWPORT);

  const geometry = await getRiskOverviewGeometry(page);
  expect(geometry.main).not.toBeNull();
  expect(geometry.rail).not.toBeNull();
  expect(geometry.rail.left).toBeGreaterThanOrEqual(geometry.main.right - 1);
  expect(geometry.bondCards).toHaveLength(2);

  for (const card of geometry.bondCards) {
    expect(card.rect).not.toBeNull();
    expect(card.rect.width).toBeGreaterThanOrEqual(320);
  }
});

test("risk overview preserves desktop shell and first-screen semantics at 1440x900", async ({
  page,
}) => {
  await gotoRiskOverview(page, DESKTOP_VIEWPORT);

  const geometry = await getRiskOverviewGeometry(page);
  expect(geometry.layout).not.toBeNull();
  expect(geometry.main).not.toBeNull();
  expect(geometry.rail).not.toBeNull();
  expect(geometry.hero).not.toBeNull();

  expect(geometry.rail.left).toBeGreaterThanOrEqual(geometry.main.right - 1);
  expect(geometry.rail.top).toBeLessThan(DESKTOP_VIEWPORT.height);
  expect(geometry.hero.top).toBeLessThan(DESKTOP_VIEWPORT.height);
  expect(geometry.horizontalOverflow).toBeLessThanOrEqual(1);
});

test("risk overview exposes a single main landmark and in-page section navigation", async ({
  page,
}) => {
  await gotoRiskOverview(page, DESKTOP_VIEWPORT);

  const h1 = page.locator("h1");
  await expect(h1).toHaveCount(1);
  await expect(h1).toHaveText("MOSS 利率风险总览");

  const geometry = await getRiskOverviewGeometry(page);
  expect(geometry.mainLandmarkCount).toBe(1);

  const sectionLinks = page
    .getByTestId("risk-overview-page")
    .locator('a[href^="#risk-overview-"]');
  await expect(sectionLinks).toHaveCount(RISK_SECTION_HREFS.length);

  const hrefs = await sectionLinks.evaluateAll((links) =>
    links.map((link) => link.getAttribute("href")).filter(Boolean),
  );

  expect(hrefs).toEqual(RISK_SECTION_HREFS);
  for (const href of hrefs) {
    const targetId = href.slice(1);
    await expect(
      page.locator(`#${targetId}`),
      `${href} should point to a visible section`,
    ).toBeVisible();
  }
});

test("risk overview deterministically discloses warnings beyond the first three", async ({
  page,
}) => {
  await page.setViewportSize(DESKTOP_VIEWPORT);
  await installWarningDisclosureFixture(page);
  await page.goto(new URL("/risk-overview", FORMAL_STATE_BASE_URL).toString(), {
    waitUntil: "domcontentloaded",
  });

  const qualitySection = page.getByTestId("risk-overview-quality");
  await expect(qualitySection).toBeVisible({ timeout: 60_000 });

  const warningList = qualitySection.getByTestId("risk-overview-warning-list");
  const details = qualitySection.getByTestId("risk-overview-warning-details");
  const disclosure = details.locator("summary");
  const remainingWarnings = details.locator("p");

  await expect(warningList.locator(":scope > p")).toHaveCount(3);
  await expect(details).toHaveCount(1);
  await expect(disclosure).toContainText(`其余 ${DISCLOSURE_WARNINGS.length - 3} 条`);
  await expect(remainingWarnings).toHaveCount(DISCLOSURE_WARNINGS.length - 3);
  await expect(remainingWarnings.first()).toBeHidden();

  await disclosure.focus();
  await expect(disclosure).toBeFocused();

  expect(await details.evaluate((element) => element.open)).toBe(false);

  await page.keyboard.press("Enter");

  expect(await details.evaluate((element) => element.open)).toBe(true);
  await expect(remainingWarnings.first()).toBeVisible();
});

test("dashboard home retains its owner-only desktop shell", async ({ page }) => {
  await page.setViewportSize(DESKTOP_VIEWPORT);
  await page.goto("/", { waitUntil: "domcontentloaded" });

  const dashboard = page.getByTestId("dashboard-home-page");
  const scrollRoot = page.getByTestId("dashboard-home-scroll-root");

  await expect(dashboard).toBeVisible({ timeout: 60_000 });
  await expect(scrollRoot).toBeVisible({ timeout: 60_000 });

  const geometry = await dashboard.evaluate((element) => {
    const layout = element.querySelector(
      '[data-testid="dashboard-home-scroll-root"]',
    );
    const pageStyle = getComputedStyle(element);
    const layoutStyle = layout ? getComputedStyle(layout) : null;

    return {
      gridTemplateRows: pageStyle.gridTemplateRows,
      pageOverflowY: pageStyle.overflowY,
      layoutOverflowY: layoutStyle?.overflowY ?? null,
      layoutClientHeight: layout?.clientHeight ?? 0,
    };
  });

  expect(geometry.gridTemplateRows).toMatch(/^42px\s/);
  expect(geometry.pageOverflowY).toBe("hidden");
  expect(geometry.layoutOverflowY).toBe("auto");
  expect(geometry.layoutClientHeight).toBeGreaterThan(
    DESKTOP_VIEWPORT.height / 2,
  );
});
