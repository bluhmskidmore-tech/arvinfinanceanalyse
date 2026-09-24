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
const SHARED_BOND_NOTICE = "风险报告日未返回，债券分析辅助证据未发起读取。";
const BOND_BASIS_ROW_LABEL = "系统比较基期";
const BOND_TREND_COUNT_SUMMARY = /^历史趋势含 \d+ 条待复核提示。$/;
// 2026-02-28 is an exact natural month end, which is what enables the comparison plan.
// 2025-10-31 is deliberately withheld so one trend slot stays unavailable: that gap is
// what makes the trend carry a review notice while the other five months still plot.
const BOND_COMPARISON_AVAILABLE_DATES = [
  "2025-02-28",
  "2025-09-30",
  "2025-11-30",
  "2025-12-31",
  "2026-01-31",
  FIXED_REPORT_DATE,
];
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

async function gotoRiskOverview(page, viewport, baseUrl) {
  await page.setViewportSize(viewport);
  const target = baseUrl
    ? new URL("/risk-overview", baseUrl).toString()
    : "/risk-overview";
  await page.goto(target, { waitUntil: "domcontentloaded" });
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

function bondNumeric(raw, unit) {
  return { raw, unit, display: String(raw), precision: 2, sign_aware: false };
}

/** Passes every gate in `buildRiskBondDv01Summary`, so the card reaches its readable state. */
function buildBondDv01Payload(reportDate, accountingClass) {
  const monthSeed = Number(reportDate.slice(5, 7));
  const faceValue = 1_000_000_000 + monthSeed * 10_000_000;
  return {
    report_date: reportDate,
    accounting_class: accountingClass,
    dv01_basis: "face_value_modified_duration",
    scenario_pnl_basis: "face_value_dv01_linear",
    total_face_value: bondNumeric(faceValue, "yuan"),
    total_market_value: bondNumeric(faceValue * 1.02, "yuan"),
    face_weighted_modified_duration: bondNumeric(4 + monthSeed / 100, "ratio"),
    total_dv01: bondNumeric(400_000 + monthSeed * 1_000, "dv01"),
    position_count: 12,
    shock_scenarios: [],
    tenor_buckets: [],
    top_bonds: [],
    top_issuers: [],
    warnings: [],
    computed_at: "2026-03-01T00:00:00Z",
  };
}

/**
 * Drives the bond evidence region into its enabled-comparison shape: both cards read
 * cleanly, so the region status line and each card's comparison basis resolve to the
 * very same plan sentence, and the one withheld month end gives the trend a notice that
 * the card disclosure already carries.
 */
async function installBondComparisonFixture(page) {
  await page.route("**/api/risk/tensor/dates", async (route) => {
    await route.fulfill({
      json: buildMockApiEnvelope("risk.tensor.dates", {
        report_dates: [FIXED_REPORT_DATE],
        blocked_report_dates: [],
      }),
    });
  });
  await page.route("**/api/bond-analytics/dates", async (route) => {
    await route.fulfill({
      json: buildMockApiEnvelope("bond-analytics.dates", {
        report_dates: BOND_COMPARISON_AVAILABLE_DATES,
      }),
    });
  });
  await page.route("**/api/bond-analytics/dv01-risk?*", async (route) => {
    const params = new URL(route.request().url()).searchParams;
    await route.fulfill({
      json: buildMockApiEnvelope(
        "bond-analytics.dv01-risk",
        buildBondDv01Payload(
          params.get("report_date") ?? FIXED_REPORT_DATE,
          (params.get("accounting_class") ?? "OCI").toUpperCase(),
        ),
        { basis: "formal", formal_use_allowed: true },
      ),
    });
  });
}

/** Drives the region into the blocked shape where both classes report one identical notice. */
async function installBondBlockedDateFixture(page) {
  await page.route("**/api/risk/tensor/dates", async (route) => {
    await route.fulfill({
      json: buildMockApiEnvelope("risk.tensor.dates", {
        report_dates: [],
        blocked_report_dates: [FIXED_REPORT_DATE],
      }),
    });
  });
}

/**
 * Aggregates rendered leaf text in the bond evidence region, split into region scope and
 * card scope. Leaf granularity keeps every label, status line, notice item and trend
 * paragraph as one entry, so repeated prose can be counted instead of pixel-compared.
 * Text is trimmed but never whitespace-collapsed, because the display-layer dedup rules
 * key off character-for-character equality.
 */
async function readBondEvidenceText(page) {
  return page.evaluate((basisRowLabel) => {
    const CARD_SELECTOR =
      '[data-testid="risk-overview-bond-oci"], [data-testid="risk-overview-bond-tpl"]';
    const section = document.querySelector(
      '[data-testid="risk-overview-bond-evidence"]',
    );
    if (!section) {
      throw new Error("bond evidence region must be rendered");
    }

    const leaves = Array.from(section.querySelectorAll("*"))
      .filter((element) => element.children.length === 0)
      .map((element) => ({ element, text: element.textContent.trim() }))
      .filter((leaf) => leaf.text);
    const listTexts = (root, selector) =>
      Array.from(root?.querySelectorAll(selector) ?? []).map((item) =>
        item.textContent.trim(),
      );

    return {
      statusText:
        section
          .querySelector(
            '[data-testid="risk-overview-bond-comparison-status"] b',
          )
          ?.textContent.trim() ?? "",
      regionTexts: leaves
        .filter((leaf) => !leaf.element.closest(CARD_SELECTOR))
        .map((leaf) => leaf.text),
      cardTexts: leaves
        .filter((leaf) => leaf.element.closest(CARD_SELECTOR))
        .map((leaf) => leaf.text),
      sharedNoticeItems: listTexts(
        section.querySelector(
          '[data-testid="risk-overview-bond-shared-notices"]',
        ),
        "li",
      ),
      cards: Array.from(section.querySelectorAll(CARD_SELECTOR)).map((card) => {
        const key = card
          .getAttribute("data-testid")
          .replace("risk-overview-", "");
        const trend = card.querySelector(
          `[data-testid="risk-overview-${key}-dv01-trend"]`,
        );
        return {
          key,
          hasBasisRow: Array.from(card.querySelectorAll("div")).some(
            (row) => row.firstElementChild?.textContent.trim() === basisRowLabel,
          ),
          trendParagraphs: listTexts(trend, "p"),
          trendPointCount: Number(trend?.getAttribute("data-point-count")),
          trendExpectedPointCount: Number(
            trend?.getAttribute("data-expected-points"),
          ),
          noticeItems: listTexts(
            card.querySelector(`[data-testid="risk-overview-${key}-notices"]`),
            "li",
          ),
        };
      }),
    };
  }, BOND_BASIS_ROW_LABEL);
}

/** Prose carries a full stop; bare labels, dates and numbers do not. */
function sentencesOf(texts) {
  return texts.filter((text) => text.includes("。"));
}

/**
 * The region status leaves `data-state="loading"` only once the bond dates, current
 * snapshots and history reads have all settled, which is when the region status sentence
 * and each card's comparison basis reach their final text.
 */
async function settleBondEvidence(page) {
  const bondEvidence = page.getByTestId("risk-overview-bond-evidence");
  const status = bondEvidence.getByTestId(
    "risk-overview-bond-comparison-status",
  );
  await expect(status).toBeVisible({ timeout: 60_000 });
  await expect(status).not.toHaveAttribute("data-state", "loading", {
    timeout: 60_000,
  });
  return bondEvidence;
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
      // A decorative shell backdrop (::before, bottom: -18px) inflates scrollHeight,
      // so measure whether the rail actually scrolls instead of comparing heights.
      railScrolls:
        rail instanceof HTMLElement
          ? (() => {
              const initial = rail.scrollTop;
              rail.scrollTop = initial + 64;
              const moved = rail.scrollTop !== initial;
              rail.scrollTop = initial;
              return moved;
            })()
          : null,
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
  expect(geometry.railScrolls).toBe(false);
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

test("risk overview shares identical bond notices in one keyboard disclosure", async ({
  page,
}) => {
  // No usable report date means both accounting classes report the very same
  // blocked notice, which is the state the shared disclosure exists for.
  await page.route("**/api/risk/tensor/dates", async (route) => {
    await route.fulfill({
      json: buildMockApiEnvelope("risk.tensor.dates", {
        report_dates: [],
        blocked_report_dates: [FIXED_REPORT_DATE],
      }),
    });
  });
  await gotoRiskOverview(page, DESKTOP_VIEWPORT, FORMAL_STATE_BASE_URL);

  const bondEvidence = page.getByTestId("risk-overview-bond-evidence");
  const sharedNotices = bondEvidence.getByTestId(
    "risk-overview-bond-shared-notices",
  );
  const disclosure = sharedNotices.locator("summary");
  const sharedNotice = sharedNotices.getByText(SHARED_BOND_NOTICE, {
    exact: true,
  });

  await expect(sharedNotices).toHaveCount(1, { timeout: 60_000 });
  await expect(disclosure).toHaveCount(1);
  await expect(sharedNotice).toHaveCount(1);
  await expect(sharedNotice).toBeHidden();
  await expect(
    bondEvidence.getByText(SHARED_BOND_NOTICE, { exact: true }),
  ).toHaveCount(1);

  expect(
    await sharedNotices.evaluate((element) => {
      if (!(element instanceof HTMLDetailsElement)) {
        throw new Error("shared bond notices must use a details element");
      }
      return element.open;
    }),
  ).toBe(false);

  for (const summaryKey of ["bond-oci", "bond-tpl"]) {
    await expect(
      bondEvidence.getByTestId(`risk-overview-${summaryKey}-notices`),
    ).toHaveCount(0);
  }

  await disclosure.focus();
  await expect(disclosure).toBeFocused();
  await page.keyboard.press("Enter");

  expect(await sharedNotices.evaluate((element) => element.open)).toBe(true);
  await expect(sharedNotice).toBeVisible();
});

test("risk overview keeps distinct bond notices collapsed on each card", async ({
  page,
}) => {
  // Both classes lead with their own 630 sentence under this fixture, which is what keeps
  // the notices on each card instead of merging them into the shared disclosure.
  await installBondComparisonFixture(page);
  await gotoRiskOverview(page, DESKTOP_VIEWPORT, FORMAL_STATE_BASE_URL);

  const bondEvidence = page.getByTestId("risk-overview-bond-evidence");
  const ociNotices = bondEvidence.getByTestId("risk-overview-bond-oci-notices");

  await expect(ociNotices).toHaveCount(1, { timeout: 60_000 });
  await expect(
    bondEvidence.getByTestId("risk-overview-bond-shared-notices"),
  ).toHaveCount(0);
  expect(await ociNotices.evaluate((element) => element.open)).toBe(false);

  const summary = ociNotices.locator("summary");
  await expect(summary).toHaveText(/^口径提示（\d+ 条）$/);

  const collapsedBody = ociNotices.locator("li").first();
  await expect(collapsedBody).toBeHidden();

  await summary.focus();
  await page.keyboard.press("Enter");

  expect(await ociNotices.evaluate((element) => element.open)).toBe(true);
  await expect(collapsedBody).toBeVisible();
});

const BOND_EVIDENCE_DEDUP_STATES = [
  {
    name: "enabled comparison basis",
    install: installBondComparisonFixture,
    // The plan sentence reaches the region status line and both cards, so the cards must
    // drop their own basis row.
    expectCardBasisRow: false,
  },
  {
    name: "blocked report date",
    install: installBondBlockedDateFixture,
    // The region reports why the plan is off while the cards report that it is off, which
    // are different sentences, so suppressing the card row here would lose basis evidence.
    expectCardBasisRow: true,
  },
];

for (const state of BOND_EVIDENCE_DEDUP_STATES) {
  test(`risk overview never repeats a bond evidence sentence across region and card scope with ${state.name}`, async ({
    page,
  }) => {
    await state.install(page);
    await gotoRiskOverview(page, DESKTOP_VIEWPORT, FORMAL_STATE_BASE_URL);
    await settleBondEvidence(page);

    const evidence = await readBondEvidenceText(page);
    expect(evidence.cards.map((card) => card.key)).toEqual([
      "bond-oci",
      "bond-tpl",
    ]);
    expect(evidence.statusText).not.toBe("");
    expect(evidence.cards.map((card) => card.hasBasisRow)).toEqual([
      state.expectCardBasisRow,
      state.expectCardBasisRow,
    ]);

    const cardSentences = new Set(sentencesOf(evidence.cardTexts));
    const repeatedAcrossScopes = Array.from(
      new Set(sentencesOf(evidence.regionTexts)),
    ).filter((sentence) => cardSentences.has(sentence));
    expect(
      repeatedAcrossScopes,
      "no bond evidence sentence may render in both region and card scope",
    ).toEqual([]);

    const statusOccurrences = [
      ...evidence.regionTexts,
      ...evidence.cardTexts,
    ].filter((text) => text === evidence.statusText).length;
    expect(
      statusOccurrences,
      "the region comparison status sentence must render exactly once",
    ).toBe(1);
  });
}

test("risk overview summarizes bond trend notices already carried by a disclosure", async ({
  page,
}) => {
  await installBondComparisonFixture(page);
  await gotoRiskOverview(page, DESKTOP_VIEWPORT, FORMAL_STATE_BASE_URL);
  const bondEvidence = await settleBondEvidence(page);

  // Both classes lead with their own 630 sentence here, so notices stay on each card
  // instead of merging into the shared disclosure.
  await expect(
    bondEvidence.getByTestId("risk-overview-bond-oci-notices"),
  ).toHaveCount(1);
  await expect(
    bondEvidence.getByTestId("risk-overview-bond-tpl-notices"),
  ).toHaveCount(1);

  const evidence = await readBondEvidenceText(page);
  expect(evidence.cards).toHaveLength(2);

  for (const card of evidence.cards) {
    // Guards against a vacuous pass: the withheld month end must leave the trend short of
    // its expected points, which is exactly when the trend has notices to repeat.
    expect(card.trendPointCount).toBeGreaterThan(0);
    expect(card.trendPointCount).toBeLessThan(card.trendExpectedPointCount);
    expect(card.noticeItems.length).toBeGreaterThan(0);

    const disclosedNotices = new Set([
      ...card.noticeItems,
      ...evidence.sharedNoticeItems,
    ]);
    // The empty-state paragraph is deliberately exempt: with no plottable point it is the
    // only inline explanation for the missing chart, so it keeps its verbatim wording even
    // though the disclosure carries the same sentence. Guard the notice line only.
    const repeatedByTrend = card.trendParagraphs
      .filter((paragraph) => card.trendPointCount > 0)
      .filter((paragraph) => disclosedNotices.has(paragraph));
    expect(
      repeatedByTrend,
      `${card.key} trend must not repeat a disclosed notice verbatim`,
    ).toEqual([]);

    const trendNoticeParagraphs = card.trendParagraphs.filter((paragraph) =>
      paragraph.includes("待复核提示"),
    );
    expect(trendNoticeParagraphs).toHaveLength(1);
    expect(trendNoticeParagraphs[0]).toMatch(BOND_TREND_COUNT_SUMMARY);
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
