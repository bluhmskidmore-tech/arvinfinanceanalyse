import { describe, expect, it } from "vitest";

import type { ProductCategoryPnlRow, ResultMeta } from "../../../api/contracts";
import { designTokens } from "../../../theme/designSystem";

import {
  PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY,
  PRODUCT_CATEGORY_FTP_SCENARIO_OPTIONS,
  PRODUCT_CATEGORY_VALUE_TONE_COLORS,
  buildProductCategoryDiagnosticsSurface,
  buildProductCategoryLiabilitySideTrendSurface,
  PRODUCT_CATEGORY_GOVERNED_DETAIL_VIEWS,
  PRODUCT_CATEGORY_MAIN_PAGE_VIEWS,
  availableViewsSupportMainPageSelector,
  buildProductCategoryTrendSnapshot,
  collectProductCategoryGovernanceNotices,
  defaultProductCategoryScenarioRateForReportDate,
  formatProductCategoryAttributionEffect,
  formatProductCategoryDualMetaDistinctLine,
  formatProductCategoryReportMonthLabel,
  formatProductCategoryRowDisplayValue,
  formatProductCategoryValue,
  formatProductCategoryYieldValue,
  mainPageViewsAreGovernedDetailSubset,
  selectDisplayedProductCategoryGrandTotal,
  selectProductCategoryDetailRows,
  selectProductCategoryIntermediateBusinessIncomeYearComparisonChart,
  selectProductCategoryInterestSpreadAttributionSurface,
  selectProductCategoryInterestSpreadYearComparisonChart,
  selectProductCategoryTplScaleYieldChart,
  selectProductCategoryTwoYearInterestSpreadReportPoints,
  selectProductCategoryTrendReportDates,
  selectProductCategoryTrendReportPoints,
  toneForProductCategoryValue,
} from "./productCategoryPnlPageModel";

function resultMeta(overrides: Partial<ResultMeta>): ResultMeta {
  return {
    trace_id: "trace_base",
    basis: "formal",
    result_kind: "product_category_pnl.detail",
    formal_use_allowed: true,
    source_version: "sv_x",
    vendor_version: "vv_x",
    rule_version: "rv_x",
    cache_version: "cv_x",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function row(partial: Pick<ProductCategoryPnlRow, "category_id"> & Partial<ProductCategoryPnlRow>): ProductCategoryPnlRow {
  return {
    category_name: partial.category_name ?? partial.category_id,
    side: partial.side ?? "asset",
    level: partial.level ?? 0,
    view: partial.view ?? "monthly",
    report_date: partial.report_date ?? "2026-02-28",
    baseline_ftp_rate_pct: partial.baseline_ftp_rate_pct ?? "1.75",
    cnx_scale: partial.cnx_scale ?? "0",
    cny_scale: partial.cny_scale ?? "0",
    foreign_scale: partial.foreign_scale ?? "0",
    cnx_cash: partial.cnx_cash ?? "0",
    cny_cash: partial.cny_cash ?? "0",
    foreign_cash: partial.foreign_cash ?? "0",
    cny_ftp: partial.cny_ftp ?? "0",
    foreign_ftp: partial.foreign_ftp ?? "0",
    cny_net: partial.cny_net ?? "0",
    foreign_net: partial.foreign_net ?? "0",
    business_net_income: partial.business_net_income ?? "0",
    weighted_yield: partial.weighted_yield ?? null,
    is_total: partial.is_total ?? false,
    children: partial.children ?? [],
    ...partial,
  };
}

function yi(value: number): string {
  return String(value * 100_000_000);
}

function annualizedCash(scaleYi: number, ratePct: number, days: number): string {
  return String(scaleYi * 100_000_000 * (ratePct / 100) * (days / 365));
}

describe("productCategoryPnlPageModel", () => {
  it("keeps main-page view selector scope to monthly and ytd inside the governed API detail surface", () => {
    expect(PRODUCT_CATEGORY_MAIN_PAGE_VIEWS).toEqual(["monthly", "ytd"]);
    expect(PRODUCT_CATEGORY_GOVERNED_DETAIL_VIEWS).toEqual([
      "monthly",
      "qtd",
      "ytd",
      "year_to_report_month_end",
    ]);
    expect(mainPageViewsAreGovernedDetailSubset()).toBe(true);
  });

  it("treats backend available_views as a superset that can include qtd and year_to_report_month_end", () => {
    const typical = ["monthly", "qtd", "ytd", "year_to_report_month_end"];
    expect(availableViewsSupportMainPageSelector(typical)).toBe(true);
    expect(availableViewsSupportMainPageSelector(["monthly", "ytd"])).toBe(true);
    expect(availableViewsSupportMainPageSelector(["monthly"])).toBe(false);
  });

  it("pins the four FTP scenario choices and year defaults used by the main page", () => {
    expect(PRODUCT_CATEGORY_FTP_SCENARIO_OPTIONS).toEqual([
      { value: "2.00", label: "2.0%" },
      { value: "1.75", label: "1.75%" },
      { value: "1.60", label: "1.6%" },
      { value: "1.50", label: "1.5%" },
    ]);
    expect(defaultProductCategoryScenarioRateForReportDate("2025-12-31")).toBe("1.75");
    expect(defaultProductCategoryScenarioRateForReportDate("2026-02-28")).toBe("1.60");
    expect(defaultProductCategoryScenarioRateForReportDate("2024-12-31")).toBe("1.75");
  });

  it("formats report date choices as month labels while preserving invalid input", () => {
    expect(formatProductCategoryReportMonthLabel("2026-02-28")).toBe("\u0032\u0030\u0032\u0036\u5e74\u0030\u0032\u6708");
    expect(formatProductCategoryReportMonthLabel("2025-12-31")).toBe("\u0032\u0030\u0032\u0035\u5e74\u0031\u0032\u6708");
    expect(formatProductCategoryReportMonthLabel("not-a-date")).toBe("not-a-date");
  });

  it("formats attribution effects from governed yuan values into yi display values", () => {
    expect(formatProductCategoryAttributionEffect(yi(0.5))).toBe("0.50");
    expect(formatProductCategoryAttributionEffect(yi(-0.25))).toBe("-0.25");
    expect(formatProductCategoryAttributionEffect(null)).toBe("-");
  });

  it("uses baseline rows as-is when no scenario rows are passed (no re-aggregation)", () => {
    const baseline = [
      row({ category_id: "bond_investment", business_net_income: "1.5" }),
      row({ category_id: "repo_assets", business_net_income: "2" }),
    ];
    const out = selectProductCategoryDetailRows(baseline, undefined);
    expect(out).toHaveLength(2);
    expect(out.map((r) => r.category_id)).toEqual(["repo_assets", "bond_investment"]);
    expect(out.find((r) => r.category_id === "bond_investment")?.business_net_income).toBe("1.5");
  });

  it("replaces table rows with scenario payload rows when scenario rows exist", () => {
    const baseline = [row({ category_id: "bond_investment", business_net_income: "1.0" })];
    const scenario = [row({ category_id: "bond_investment", business_net_income: "9.99" })];
    const out = selectProductCategoryDetailRows(baseline, scenario);
    expect(out).toHaveLength(1);
    expect(out[0]!.business_net_income).toBe("9.99");
  });

  it("drops grand_total from the table body while keeping other rows", () => {
    const baseline = [
      row({ category_id: "bond_investment" }),
      row({ category_id: "grand_total", is_total: true }),
    ];
    const out = selectProductCategoryDetailRows(baseline, undefined);
    expect(out.map((r) => r.category_id)).toEqual(["bond_investment"]);
  });

  it("sorts unknown category_id rows after governed display-order rows", () => {
    const baseline = [
      row({ category_id: "zz_unknown_future_category" }),
      row({ category_id: "bond_investment" }),
    ];
    const out = selectProductCategoryDetailRows(baseline, undefined);
    expect(out.map((r) => r.category_id)).toEqual([
      "bond_investment",
      "zz_unknown_future_category",
    ]);
  });

  it("selects scenario grand total when present, otherwise baseline", () => {
    const b = row({ category_id: "grand_total", business_net_income: "1" });
    const s = row({ category_id: "grand_total", business_net_income: "2" });
    expect(selectDisplayedProductCategoryGrandTotal(undefined, b)?.business_net_income).toBe("1");
    expect(selectDisplayedProductCategoryGrandTotal(s, b)?.business_net_income).toBe("2");
  });

  it("builds the governed diagnostics surface from payload row identities only", () => {
    const repoRow = row({
      category_id: "repo_assets",
      category_name: "Repo Assets",
      business_net_income: "-5000000",
      cny_net: "-5000000",
      weighted_yield: null,
    });
    const missingScaleRow = row({
      category_id: "derivatives",
      category_name: "Derivatives",
      cnx_scale: undefined as unknown as ProductCategoryPnlRow["cnx_scale"],
      business_net_income: "-1000000",
      cny_net: "-1000000",
      weighted_yield: null,
    });
    const assetTotal = row({
      category_id: "asset_total",
      business_net_income: "270000000",
      weighted_yield: "2.68",
      is_total: true,
    });
    const liabilityTotal = row({
      category_id: "liability_total",
      side: "liability",
      business_net_income: "16000000",
      weighted_yield: "1.63",
      is_total: true,
    });

    const surface = buildProductCategoryDiagnosticsSurface({
      rows: [
        row({
          category_id: "bond_investment",
          category_name: "Bond Investment",
          cnx_scale: "336178000000",
          cny_net: "218000000",
          foreign_net: "10000000",
          business_net_income: "227000000",
          weighted_yield: "2.63",
        }),
        repoRow,
        missingScaleRow,
        row({
          category_id: "asset_total",
          category_name: "Asset Total",
          business_net_income: "270000000",
          is_total: true,
        }),
      ],
      assetTotal,
      liabilityTotal,
      grandTotal: row({ category_id: "grand_total", business_net_income: "286000000", is_total: true }),
      trendSnapshots: [
        {
          reportDate: "2026-02-28",
          label: "2026\u5e7402\u6708",
          rows: [],
          assetTotal,
          liabilityTotal,
        },
        {
          reportDate: "2026-01-31",
          label: "2026\u5e7401\u6708",
          rows: [],
          assetTotal: row({
            category_id: "asset_total",
            business_net_income: "250000000",
            weighted_yield: "2.55",
            is_total: true,
          }),
          liabilityTotal: row({
            category_id: "liability_total",
            side: "liability",
            business_net_income: "15000000",
            weighted_yield: "1.60",
            is_total: true,
          }),
        },
      ],
    });

    expect(surface.headlineTotalLabel).toBe("2.86 \u4ebf\u5143");
    expect(surface.matrixRows.map((item) => item.categoryId)).toEqual([
      "bond_investment",
      "repo_assets",
      "derivatives",
    ]);
    expect(surface.matrixRows[0]).toMatchObject({
      categoryLabel: "Bond Investment",
      sideLabel: "\u8d44\u4ea7",
      scaleLabel: "3361.78 \u4ebf\u5143",
      businessNetIncomeLabel: "2.27 \u4ebf\u5143",
      yieldLabel: "2.63%",
      cnyNetLabel: "2.18 \u4ebf\u5143",
      foreignNetLabel: "0.10 \u4ebf\u5143",
    });
    expect(surface.matrixRows[1]?.driverHint).toContain("\u4eba\u6c11\u5e01\u51c0\u6536\u5165\u627f\u538b");
    expect(surface.matrixRows[2]).toMatchObject({
      scaleLabel: "\u89c4\u6a21\u7f3a\u5931",
      yieldLabel: "\u6536\u76ca\u7387\u7f3a\u5931",
    });
    expect(surface.negativeWatchlistRows.map((item) => item.categoryId)).toEqual([
      "repo_assets",
      "derivatives",
    ]);
    expect(surface.negativeWatchlistRows[0]).toMatchObject({
      lossLabel: "-0.05 \u4ebf\u5143",
      yieldLabel: "\u6536\u76ca\u7387\u7f3a\u5931",
    });
    expect(surface.spreadAttribution).toMatchObject({
      state: "ready",
      currentAssetYieldLabel: "2.68%",
      currentLiabilityYieldLabel: "1.63%",
      currentSpreadLabel: "105bp",
      priorSpreadLabel: "95bp",
      spreadDeltaLabel: "+10bp",
    });
  });

  it("returns explicit incomplete diagnostics states when rows or prior spreads are unavailable", () => {
    const surface = buildProductCategoryDiagnosticsSurface({
      rows: [
        row({
          category_id: "asset_total",
          category_name: "Asset Total",
          business_net_income: "270000000",
          is_total: true,
        }),
      ],
      assetTotal: row({
        category_id: "asset_total",
        business_net_income: "270000000",
        weighted_yield: null,
        is_total: true,
      }),
      liabilityTotal: row({
        category_id: "liability_total",
        side: "liability",
        business_net_income: "16000000",
        weighted_yield: "1.63",
        is_total: true,
      }),
      grandTotal: row({ category_id: "grand_total", business_net_income: "286000000", is_total: true }),
      trendSnapshots: [
        {
          reportDate: "2026-02-28",
          label: "2026\u5e7402\u6708",
          rows: [],
          assetTotal: row({
            category_id: "asset_total",
            business_net_income: "270000000",
            weighted_yield: null,
            is_total: true,
          }),
          liabilityTotal: row({
            category_id: "liability_total",
            side: "liability",
            business_net_income: "16000000",
            weighted_yield: "1.63",
            is_total: true,
          }),
        },
      ],
    });

    expect(surface.matrixRows).toEqual([]);
    expect(surface.matrixEmptyCopy).toBe("\u5f53\u524d payload \u672a\u8fd4\u56de\u53ef\u8bca\u65ad\u7684\u4ea7\u54c1\u884c\u3002");
    expect(surface.negativeWatchlistRows).toEqual([]);
    expect(surface.negativeWatchlistEmptyCopy).toBe("\u5f53\u524d payload \u672a\u8fd4\u56de\u53ef\u8bca\u65ad\u7684\u4ea7\u54c1\u884c\u3002");
    expect(surface.spreadAttribution.state).toBe("incomplete");
    if (surface.spreadAttribution.state === "incomplete") {
      expect(surface.spreadAttribution.reason).toBe(
        "\u5f53\u524d\u8d44\u4ea7\u7aef\u6216\u8d1f\u503a\u7aef\u6536\u76ca\u7387\u7f3a\u5931\uff0c\u65e0\u6cd5\u8ba1\u7b97\u5f53\u671f\u5229\u5dee\u3002",
      );
      expect(surface.spreadAttribution.currentSpreadLabel).toBe("-");
      expect(surface.spreadAttribution.priorSpreadLabel).toBe("-");
    }
  });

  it("selects trend dates from the selected report month onward and snapshots payload rows without rollup", () => {
    expect(
      selectProductCategoryTrendReportDates("2026-02-28", [
        "2026-03-31",
        "2026-02-28",
        "2026-01-31",
        "2025-12-31",
        "2025-11-30",
      ]),
    ).toEqual(["2026-02-28", "2026-01-31", "2025-12-31", "2025-11-30"]);
    expect(selectProductCategoryTrendReportDates("", ["2026-02-28"])).toEqual([]);

    const payload = {
      report_date: "2026-02-28",
      view: "monthly",
      available_views: ["monthly"],
      scenario_rate_pct: null,
      rows: [
        row({ category_id: "grand_total", is_total: true }),
        row({ category_id: "interest_earning_assets", cnx_scale: "100000000" }),
      ],
      asset_total: row({ category_id: "asset_total", is_total: true }),
      liability_total: row({ category_id: "liability_total", side: "liability", is_total: true }),
      grand_total: row({ category_id: "grand_total", is_total: true }),
    };
    const snapshot = buildProductCategoryTrendSnapshot(payload);
    expect(snapshot.reportDate).toBe("2026-02-28");
    expect(snapshot.rows.map((r) => r.category_id)).toEqual(["interest_earning_assets"]);
  });

  it("selects quarter-end anchors while keeping the trend chart view basis consistent", () => {
    const points = selectProductCategoryTrendReportPoints("2026-03-31", [
      "2026-03-31",
      "2026-02-28",
      "2026-01-31",
      "2025-12-31",
      "2025-11-30",
      "2025-10-31",
      "2025-09-30",
      "2025-06-30",
      "2025-03-31",
    ]);

    expect(points).toEqual([
      { reportDate: "2026-03-31", view: "monthly", label: "\u0032\u0030\u0032\u0036\u5e74\u0030\u0033\u6708" },
      { reportDate: "2026-02-28", view: "monthly", label: "\u0032\u0030\u0032\u0036\u5e74\u0030\u0032\u6708" },
      { reportDate: "2026-01-31", view: "monthly", label: "\u0032\u0030\u0032\u0036\u5e74\u0030\u0031\u6708" },
      { reportDate: "2025-12-31", view: "monthly", label: "\u0032\u0030\u0032\u0035\u5e74\u0031\u0032\u6708" },
      { reportDate: "2025-11-30", view: "monthly", label: "\u0032\u0030\u0032\u0035\u5e74\u0031\u0031\u6708" },
      { reportDate: "2025-09-30", view: "monthly", label: "\u0032\u0030\u0032\u0035\u5e74Q\u0033" },
      { reportDate: "2025-06-30", view: "monthly", label: "\u0032\u0030\u0032\u0035\u5e74Q\u0032" },
      { reportDate: "2025-03-31", view: "monthly", label: "\u0032\u0030\u0032\u0035\u5e74Q\u0031" },
    ]);
    expect(selectProductCategoryTrendReportDates("2026-03-31", points.map((point) => point.reportDate))).toEqual(
      points.map((point) => point.reportDate),
    );
  });

  it("selects prior full year and current year-to-date points for interest spread comparison", () => {
    const points = selectProductCategoryTwoYearInterestSpreadReportPoints("2026-03-31", [
      "2026-03-31",
      "2026-02-28",
      "2026-01-31",
      "2025-12-31",
      "2025-11-30",
      "2025-10-31",
      "2025-09-30",
      "2025-08-31",
      "2025-07-31",
      "2025-06-30",
      "2025-05-31",
      "2025-04-30",
      "2025-03-31",
      "2025-02-28",
      "2025-01-31",
    ]);

    expect(points).toEqual([
      { reportDate: "2026-03-31", view: "monthly", label: "\u0032\u0030\u0032\u0036\u5e74\u0030\u0033\u6708" },
      { reportDate: "2026-02-28", view: "monthly", label: "\u0032\u0030\u0032\u0036\u5e74\u0030\u0032\u6708" },
      { reportDate: "2026-01-31", view: "monthly", label: "\u0032\u0030\u0032\u0036\u5e74\u0030\u0031\u6708" },
      { reportDate: "2025-12-31", view: "monthly", label: "\u0032\u0030\u0032\u0035\u5e74\u0031\u0032\u6708" },
      { reportDate: "2025-11-30", view: "monthly", label: "\u0032\u0030\u0032\u0035\u5e74\u0031\u0031\u6708" },
      { reportDate: "2025-10-31", view: "monthly", label: "\u0032\u0030\u0032\u0035\u5e74\u0031\u0030\u6708" },
      { reportDate: "2025-09-30", view: "monthly", label: "\u0032\u0030\u0032\u0035\u5e74\u0030\u0039\u6708" },
      { reportDate: "2025-08-31", view: "monthly", label: "\u0032\u0030\u0032\u0035\u5e74\u0030\u0038\u6708" },
      { reportDate: "2025-07-31", view: "monthly", label: "\u0032\u0030\u0032\u0035\u5e74\u0030\u0037\u6708" },
      { reportDate: "2025-06-30", view: "monthly", label: "\u0032\u0030\u0032\u0035\u5e74\u0030\u0036\u6708" },
      { reportDate: "2025-05-31", view: "monthly", label: "\u0032\u0030\u0032\u0035\u5e74\u0030\u0035\u6708" },
      { reportDate: "2025-04-30", view: "monthly", label: "\u0032\u0030\u0032\u0035\u5e74\u0030\u0034\u6708" },
      { reportDate: "2025-03-31", view: "monthly", label: "\u0032\u0030\u0032\u0035\u5e74\u0030\u0033\u6708" },
      { reportDate: "2025-02-28", view: "monthly", label: "\u0032\u0030\u0032\u0035\u5e74\u0030\u0032\u6708" },
      { reportDate: "2025-01-31", view: "monthly", label: "\u0032\u0030\u0032\u0035\u5e74\u0030\u0031\u6708" },
    ]);
  });

  it("groups interest-earning spread by year for same-month comparison", () => {
    const snapshot = (reportDate: string, assetYield: string, liabilityYield: string) =>
      buildProductCategoryTrendSnapshot({
        report_date: reportDate,
        view: "monthly",
        available_views: ["monthly"],
        scenario_rate_pct: null,
        rows: [
          row({
            category_id: "interest_earning_assets",
            report_date: reportDate,
            weighted_yield: assetYield,
          }),
        ],
        asset_total: row({ category_id: "asset_total", report_date: reportDate, is_total: true }),
        liability_total: row({
          category_id: "liability_total",
          side: "liability",
          report_date: reportDate,
          weighted_yield: liabilityYield,
          is_total: true,
        }),
        grand_total: row({ category_id: "grand_total", report_date: reportDate, is_total: true }),
      });

    const chart = selectProductCategoryInterestSpreadYearComparisonChart([
      snapshot("2026-03-31", "2.55", "1.70"),
      snapshot("2025-01-31", "2.20", "1.60"),
      snapshot("2026-01-31", "2.40", "1.65"),
      snapshot("2025-03-31", "2.35", "1.65"),
      snapshot("2025-12-31", "2.40", "1.60"),
      snapshot("2026-02-28", "2.48", "1.68"),
      snapshot("2025-02-28", "2.28", "1.63"),
    ]);

    expect(chart?.labels).toEqual(["\u0031\u6708", "\u0032\u6708", "\u0033\u6708", "\u0031\u0032\u6708"]);
    expect(chart?.monthKeys).toEqual([1, 2, 3, 12]);
    expect(chart?.series).toEqual([
      { year: "\u0032\u0030\u0032\u0035\u5e74", spread: [0.6, 0.65, 0.7, 0.8] },
      { year: "\u0032\u0030\u0032\u0036\u5e74", spread: [0.75, 0.8, 0.85, null] },
    ]);
  });

  it("groups intermediate business income by governed row without total fallback", () => {
    const snapshot = (reportDate: string, incomeYi: number | null, totalYi = 999) =>
      buildProductCategoryTrendSnapshot({
        report_date: reportDate,
        view: "monthly",
        available_views: ["monthly"],
        scenario_rate_pct: null,
        rows:
          incomeYi === null
            ? []
            : [
                row({
                  category_id: "intermediate_business_income",
                  report_date: reportDate,
                  business_net_income: yi(incomeYi),
                }),
              ],
        asset_total: row({
          category_id: "asset_total",
          report_date: reportDate,
          business_net_income: yi(totalYi),
          is_total: true,
        }),
        liability_total: row({
          category_id: "liability_total",
          side: "liability",
          report_date: reportDate,
          business_net_income: yi(totalYi),
          is_total: true,
        }),
        grand_total: row({
          category_id: "grand_total",
          report_date: reportDate,
          business_net_income: yi(totalYi),
          is_total: true,
        }),
      });

    const priorYearSnapshots = Array.from({ length: 12 }, (_, index) => {
      const month = index + 1;
      const reportDate = `2025-${String(month).padStart(2, "0")}-${month === 2 ? "28" : "31"}`;
      return snapshot(reportDate, month === 4 ? null : month, 900 + month);
    });
    const chart = selectProductCategoryIntermediateBusinessIncomeYearComparisonChart([
      snapshot("2026-03-31", 23, 1234),
      snapshot("2026-01-31", 21, 4321),
      ...priorYearSnapshots,
      snapshot("2026-02-28", 22, 5678),
    ]);

    expect(chart?.labels).toEqual([
      "\u0031\u6708",
      "\u0032\u6708",
      "\u0033\u6708",
      "\u0034\u6708",
      "\u0035\u6708",
      "\u0036\u6708",
      "\u0037\u6708",
      "\u0038\u6708",
      "\u0039\u6708",
      "\u0031\u0030\u6708",
      "\u0031\u0031\u6708",
      "\u0031\u0032\u6708",
    ]);
    expect(chart?.series).toEqual([
      {
        year: "\u0032\u0030\u0032\u0035\u5e74",
        income: [1, 2, 3, null, 5, 6, 7, 8, 9, 10, 11, 12],
      },
      {
        year: "\u0032\u0030\u0032\u0036\u5e74",
        income: [21, 22, 23, null, null, null, null, null, null, null, null, null],
      },
    ]);
  });

  it("returns no intermediate business income chart when every governed row is absent", () => {
    const missingSnapshot = (reportDate: string) =>
      buildProductCategoryTrendSnapshot({
        report_date: reportDate,
        view: "monthly",
        available_views: ["monthly"],
        scenario_rate_pct: null,
        rows: [],
        asset_total: row({ category_id: "asset_total", report_date: reportDate, business_net_income: yi(9), is_total: true }),
        liability_total: row({
          category_id: "liability_total",
          side: "liability",
          report_date: reportDate,
          business_net_income: yi(8),
          is_total: true,
        }),
        grand_total: row({ category_id: "grand_total", report_date: reportDate, business_net_income: yi(7), is_total: true }),
      });

    expect(
      selectProductCategoryIntermediateBusinessIncomeYearComparisonChart([
        missingSnapshot("2025-01-31"),
        missingSnapshot("2026-01-31"),
      ]),
    ).toBeNull();
  });

  it("computes RMB interest-earning asset spread from interest_earning_assets CNY cash and scale", () => {
    const snapshot = (
      reportDate: string,
      days: number,
      assetCnyRate: number,
      liabilityCnyRate: number,
    ) =>
      buildProductCategoryTrendSnapshot({
        report_date: reportDate,
        view: "monthly",
        available_views: ["monthly"],
        scenario_rate_pct: null,
        rows: [
          row({
            category_id: "interest_earning_assets",
            report_date: reportDate,
            cny_scale: yi(100),
            cny_cash: annualizedCash(100, assetCnyRate, days),
            weighted_yield: "9.99",
          }),
        ],
        asset_total: row({ category_id: "asset_total", report_date: reportDate, is_total: true }),
        liability_total: row({
          category_id: "liability_total",
          side: "liability",
          report_date: reportDate,
          cny_scale: yi(80),
          cny_cash: annualizedCash(80, liabilityCnyRate, days),
          weighted_yield: "1.00",
          is_total: true,
        }),
        grand_total: row({ category_id: "grand_total", report_date: reportDate, is_total: true }),
      });

    const chart = selectProductCategoryInterestSpreadYearComparisonChart([
      snapshot("2025-01-31", 31, 2.2, 1.5),
      snapshot("2025-02-28", 28, 2.3, 1.6),
      snapshot("2026-01-31", 31, 2.4, 1.55),
      snapshot("2026-02-28", 28, 2.5, 1.65),
    ], "cny");

    expect(chart?.labels).toEqual(["\u0031\u6708", "\u0032\u6708"]);
    expect(chart?.series).toEqual([
      { year: "\u0032\u0030\u0032\u0035\u5e74", spread: [0.7, 0.7] },
      { year: "\u0032\u0030\u0032\u0036\u5e74", spread: [0.85, 0.85] },
    ]);
  });

  it("keeps RMB spread months as null when CNY scale is unavailable", () => {
    const chart = selectProductCategoryInterestSpreadYearComparisonChart([
      buildProductCategoryTrendSnapshot({
        report_date: "2025-01-31",
        view: "monthly",
        available_views: ["monthly"],
        scenario_rate_pct: null,
        rows: [
          row({
            category_id: "interest_earning_assets",
            report_date: "2025-01-31",
            cny_scale: "0",
            cny_cash: annualizedCash(100, 2.2, 31),
            weighted_yield: "9.99",
          }),
        ],
        asset_total: row({ category_id: "asset_total", report_date: "2025-01-31", is_total: true }),
        liability_total: row({
          category_id: "liability_total",
          side: "liability",
          report_date: "2025-01-31",
          cny_scale: yi(80),
          cny_cash: annualizedCash(80, 1.5, 31),
          weighted_yield: "1.00",
          is_total: true,
        }),
        grand_total: row({ category_id: "grand_total", report_date: "2025-01-31", is_total: true }),
      }),
      buildProductCategoryTrendSnapshot({
        report_date: "2026-01-31",
        view: "monthly",
        available_views: ["monthly"],
        scenario_rate_pct: null,
        rows: [
          row({
            category_id: "interest_earning_assets",
            report_date: "2026-01-31",
            cny_scale: yi(100),
            cny_cash: annualizedCash(100, 2.4, 31),
            weighted_yield: "9.99",
          }),
        ],
        asset_total: row({ category_id: "asset_total", report_date: "2026-01-31", is_total: true }),
        liability_total: row({
          category_id: "liability_total",
          side: "liability",
          report_date: "2026-01-31",
          cny_scale: yi(80),
          cny_cash: annualizedCash(80, 1.55, 31),
          weighted_yield: "1.00",
          is_total: true,
        }),
        grand_total: row({ category_id: "grand_total", report_date: "2026-01-31", is_total: true }),
      }),
    ], "cny");

    expect(chart?.series).toEqual([
      { year: "\u0032\u0030\u0032\u0035\u5e74", spread: [null] },
      { year: "\u0032\u0030\u0032\u0036\u5e74", spread: [0.85] },
    ]);
  });

  it("computes weighted interest spread attribution and reconciles bp movement", () => {
    const snapshot = (reportDate: string, assetYield: string, liabilityYield: string) =>
      buildProductCategoryTrendSnapshot({
        report_date: reportDate,
        view: "monthly",
        available_views: ["monthly"],
        scenario_rate_pct: null,
        rows: [
          row({
            category_id: "interest_earning_assets",
            report_date: reportDate,
            cnx_scale: yi(120),
            cnx_cash: annualizedCash(120, Number(assetYield), 31),
            weighted_yield: assetYield,
          }),
        ],
        asset_total: row({ category_id: "asset_total", report_date: reportDate, is_total: true }),
        liability_total: row({
          category_id: "liability_total",
          side: "liability",
          report_date: reportDate,
          cnx_scale: yi(100),
          cnx_cash: annualizedCash(100, Number(liabilityYield), 31),
          weighted_yield: liabilityYield,
          is_total: true,
        }),
        grand_total: row({ category_id: "grand_total", report_date: reportDate, is_total: true }),
      });

    const surface = selectProductCategoryInterestSpreadAttributionSurface(
      [
        snapshot("2025-03-31", "2.35", "1.65"),
        snapshot("2026-03-31", "2.55", "1.70"),
      ],
      { basis: "weighted", month: 3 },
      2026,
    );

    expect(surface.complete).toBe(true);
    expect(surface.incompleteReasons).toEqual([]);
    expect(surface.summary).toMatchObject({
      assetYieldCurrent: 2.55,
      assetYieldPrior: 2.35,
      liabilityYieldCurrent: 1.7,
      liabilityYieldPrior: 1.65,
      spreadCurrent: 0.85,
      spreadPrior: 0.7,
      assetContributionBp: 20,
      liabilityContributionBp: -5,
      spreadDeltaBp: 15,
    });
    expect(surface.summary.spreadDeltaBp).toBe(
      Number(
        (
          (surface.summary.assetContributionBp ?? 0) +
          (surface.summary.liabilityContributionBp ?? 0)
        ).toFixed(1),
      ),
    );
    expect(surface.rows.map((item) => item.key)).toEqual(["asset_yield", "liability_cost", "spread"]);
    expect(surface.details.map((item) => item.key)).toEqual(["interest_earning_assets", "liability_total"]);
  });

  it("computes RMB attribution from CNY cash and scale while ignoring weighted yields", () => {
    const snapshot = (reportDate: string, days: number, assetCnyRate: number, liabilityCnyRate: number) =>
      buildProductCategoryTrendSnapshot({
        report_date: reportDate,
        view: "monthly",
        available_views: ["monthly"],
        scenario_rate_pct: null,
        rows: [
          row({
            category_id: "interest_earning_assets",
            report_date: reportDate,
            cny_scale: yi(100),
            cny_cash: annualizedCash(100, assetCnyRate, days),
            weighted_yield: "9.99",
          }),
        ],
        asset_total: row({ category_id: "asset_total", report_date: reportDate, is_total: true }),
        liability_total: row({
          category_id: "liability_total",
          side: "liability",
          report_date: reportDate,
          cny_scale: yi(80),
          cny_cash: annualizedCash(80, liabilityCnyRate, days),
          weighted_yield: "1.00",
          is_total: true,
        }),
        grand_total: row({ category_id: "grand_total", report_date: reportDate, is_total: true }),
      });

    const surface = selectProductCategoryInterestSpreadAttributionSurface(
      [
        snapshot("2025-03-31", 31, 2.3, 1.6),
        snapshot("2026-03-31", 31, 2.55, 1.7),
      ],
      { basis: "cny", month: 3 },
      2026,
    );

    expect(surface.complete).toBe(true);
    expect(surface.summary).toMatchObject({
      assetYieldCurrent: 2.55,
      assetYieldPrior: 2.3,
      liabilityYieldCurrent: 1.7,
      liabilityYieldPrior: 1.6,
      spreadCurrent: 0.85,
      spreadPrior: 0.7,
      assetContributionBp: 25,
      liabilityContributionBp: -10,
      spreadDeltaBp: 15,
    });
  });

  it("returns incomplete reasons and null RMB contribution when prior CNY scale is unavailable", () => {
    const surface = selectProductCategoryInterestSpreadAttributionSurface(
      [
        buildProductCategoryTrendSnapshot({
          report_date: "2025-03-31",
          view: "monthly",
          available_views: ["monthly"],
          scenario_rate_pct: null,
          rows: [
            row({
              category_id: "interest_earning_assets",
              report_date: "2025-03-31",
              cny_scale: "0",
              cny_cash: annualizedCash(100, 2.3, 31),
              weighted_yield: "9.99",
            }),
          ],
          asset_total: row({ category_id: "asset_total", report_date: "2025-03-31", is_total: true }),
          liability_total: row({
            category_id: "liability_total",
            side: "liability",
            report_date: "2025-03-31",
            cny_scale: yi(80),
            cny_cash: annualizedCash(80, 1.6, 31),
            weighted_yield: "1.00",
            is_total: true,
          }),
          grand_total: row({ category_id: "grand_total", report_date: "2025-03-31", is_total: true }),
        }),
        buildProductCategoryTrendSnapshot({
          report_date: "2026-03-31",
          view: "monthly",
          available_views: ["monthly"],
          scenario_rate_pct: null,
          rows: [
            row({
              category_id: "interest_earning_assets",
              report_date: "2026-03-31",
              cny_scale: yi(100),
              cny_cash: annualizedCash(100, 2.55, 31),
              weighted_yield: "9.99",
            }),
          ],
          asset_total: row({ category_id: "asset_total", report_date: "2026-03-31", is_total: true }),
          liability_total: row({
            category_id: "liability_total",
            side: "liability",
            report_date: "2026-03-31",
            cny_scale: yi(80),
            cny_cash: annualizedCash(80, 1.7, 31),
            weighted_yield: "1.00",
            is_total: true,
          }),
          grand_total: row({ category_id: "grand_total", report_date: "2026-03-31", is_total: true }),
        }),
      ],
      { basis: "cny", month: 3 },
      2026,
    );

    expect(surface.complete).toBe(false);
    expect(surface.summary.assetYieldPrior).toBeNull();
    expect(surface.summary.assetContributionBp).toBeNull();
    expect(surface.summary.spreadDeltaBp).toBeNull();
    expect(surface.incompleteReasons.join(" ")).toContain("\u4eba\u6c11\u5e01");
    expect(surface.incompleteReasons.join(" ")).toContain("\u751f\u606f\u8d44\u4ea7");
  });

  it("sorts trend chart snapshots by report date instead of async query arrival order", () => {
    const snapshots = [
      buildProductCategoryTrendSnapshot({
        report_date: "2026-03-31",
        view: "monthly",
        available_views: ["monthly"],
        scenario_rate_pct: null,
        rows: [
          row({
            category_id: "bond_tpl",
            report_date: "2026-03-31",
            cny_scale: "300000000",
            foreign_scale: "30000000",
            weighted_yield: "3",
          }),
        ],
        asset_total: row({ category_id: "asset_total", is_total: true }),
        liability_total: row({ category_id: "liability_total", side: "liability", is_total: true }),
        grand_total: row({ category_id: "grand_total", is_total: true }),
      }, "2026年03月"),
      buildProductCategoryTrendSnapshot({
        report_date: "2025-03-31",
        view: "monthly",
        available_views: ["monthly"],
        scenario_rate_pct: null,
        rows: [
          row({
            category_id: "bond_tpl",
            report_date: "2025-03-31",
            cny_scale: "100000000",
            foreign_scale: "10000000",
            weighted_yield: "1",
          }),
        ],
        asset_total: row({ category_id: "asset_total", is_total: true }),
        liability_total: row({ category_id: "liability_total", side: "liability", is_total: true }),
        grand_total: row({ category_id: "grand_total", is_total: true }),
      }, "2025年Q1"),
      buildProductCategoryTrendSnapshot({
        report_date: "2025-11-30",
        view: "monthly",
        available_views: ["monthly"],
        scenario_rate_pct: null,
        rows: [
          row({
            category_id: "bond_tpl",
            report_date: "2025-11-30",
            cny_scale: "200000000",
            foreign_scale: "20000000",
            weighted_yield: "2",
          }),
        ],
        asset_total: row({ category_id: "asset_total", is_total: true }),
        liability_total: row({ category_id: "liability_total", side: "liability", is_total: true }),
        grand_total: row({ category_id: "grand_total", is_total: true }),
      }, "2025年11月"),
    ];

    expect(selectProductCategoryTplScaleYieldChart(snapshots)?.labels).toEqual([
      "2025年Q1",
      "2025年11月",
      "2026年03月",
    ]);
  });

  it("builds liability-side trend surface with governed detail rows and comparable deltas", () => {
    const snapshots = [
      buildProductCategoryTrendSnapshot({
        report_date: "2025-03-31",
        view: "monthly",
        available_views: ["monthly"],
        scenario_rate_pct: null,
        rows: [
          row({
            category_id: "interbank_deposits",
            category_name: "同业存放",
            side: "liability",
            report_date: "2025-03-31",
            cnx_scale: yi(75),
            weighted_yield: "1.10",
          }),
          row({
            category_id: "credit_linked_notes",
            category_name: "收益凭证",
            side: "liability",
            report_date: "2025-03-31",
            cnx_scale: yi(18),
            weighted_yield: "3.00",
          }),
        ],
        asset_total: row({ category_id: "asset_total", is_total: true }),
        liability_total: row({
          category_id: "liability_total",
          side: "liability",
          is_total: true,
          cnx_scale: yi(1500),
          weighted_yield: "1.60",
        }),
        grand_total: row({ category_id: "grand_total", is_total: true }),
      }, "2025年Q1"),
      buildProductCategoryTrendSnapshot({
        report_date: "2025-11-30",
        view: "monthly",
        available_views: ["monthly"],
        scenario_rate_pct: null,
        rows: [
          row({
            category_id: "interbank_deposits",
            category_name: "同业存放",
            side: "liability",
            report_date: "2025-11-30",
            cnx_scale: "not_available",
            weighted_yield: "1.20",
          }),
          row({
            category_id: "credit_linked_notes",
            category_name: "收益凭证",
            side: "liability",
            report_date: "2025-11-30",
            cnx_scale: yi(20),
            weighted_yield: "3.10",
          }),
        ],
        asset_total: row({ category_id: "asset_total", is_total: true }),
        liability_total: row({
          category_id: "liability_total",
          side: "liability",
          is_total: true,
          cnx_scale: yi(1600),
          weighted_yield: null,
        }),
        grand_total: row({ category_id: "grand_total", is_total: true }),
      }, "2025年11月"),
      buildProductCategoryTrendSnapshot({
        report_date: "2026-03-31",
        view: "monthly",
        available_views: ["monthly"],
        scenario_rate_pct: null,
        rows: [
          row({
            category_id: "interbank_deposits",
            category_name: "同业存放",
            side: "liability",
            report_date: "2026-03-31",
            cnx_scale: yi(82),
            weighted_yield: "1.30",
          }),
          row({
            category_id: "credit_linked_notes",
            category_name: "收益凭证",
            side: "liability",
            report_date: "2026-03-31",
            cnx_scale: yi(25),
            weighted_yield: "3.25",
          }),
        ],
        asset_total: row({ category_id: "asset_total", is_total: true }),
        liability_total: row({
          category_id: "liability_total",
          side: "liability",
          is_total: true,
          cnx_scale: yi(1700),
          weighted_yield: "1.75",
        }),
        grand_total: row({ category_id: "grand_total", is_total: true }),
      }, "2026年03月"),
    ];

    const surface = buildProductCategoryLiabilitySideTrendSurface(snapshots);

    expect(surface.chart?.labels).toEqual(["2025年Q1", "2025年11月", "2026年03月"]);
    expect(surface.chart?.totalAverageDaily).toEqual([1500, 1600, 1700]);
    expect(surface.chart?.totalRate).toEqual([1.6, null, 1.75]);
    expect(surface.incompleteReasons).toContain("2025年11月负债端利率缺失");
    expect(surface.detailRows.map((item) => item.categoryId)).toContain("credit_linked_notes");
    expect(surface.detailRows.find((item) => item.categoryId === "interbank_deposits")).toMatchObject({
      latestAmountLabel: "82.00",
      amountDeltaLabel: "+7.00",
      latestRateLabel: "1.30",
      rateDeltaLabel: "+10bp",
      comparisonLabel: "日均额：2025年Q1 → 2026年03月；利率：2025年11月 → 2026年03月",
    });
  });

  it("builds a liability-side detail matrix with period cells and adjacent-month movement", () => {
    const snapshots = [
      buildProductCategoryTrendSnapshot({
        report_date: "2026-01-31",
        view: "monthly",
        available_views: ["monthly"],
        scenario_rate_pct: null,
        rows: [
          row({
            category_id: "interbank_deposits",
            category_name: "同业存放",
            side: "liability",
            report_date: "2026-01-31",
            cnx_scale: yi(75),
            weighted_yield: "1.10",
          }),
          row({
            category_id: "interbank_cds",
            category_name: "同业存单",
            side: "liability",
            report_date: "2026-01-31",
            cnx_scale: yi(120),
            weighted_yield: "1.45",
          }),
        ],
        asset_total: row({ category_id: "asset_total", is_total: true }),
        liability_total: row({ category_id: "liability_total", side: "liability", is_total: true }),
        grand_total: row({ category_id: "grand_total", is_total: true }),
      }, "2026年01月"),
      buildProductCategoryTrendSnapshot({
        report_date: "2026-02-28",
        view: "monthly",
        available_views: ["monthly"],
        scenario_rate_pct: null,
        rows: [
          row({
            category_id: "interbank_deposits",
            category_name: "同业存放",
            side: "liability",
            report_date: "2026-02-28",
            cnx_scale: yi(80),
            weighted_yield: "1.20",
          }),
          row({
            category_id: "repo_liabilities",
            category_name: "卖出回购",
            side: "liability",
            report_date: "2026-02-28",
            cnx_scale: yi(51),
            weighted_yield: "1.33",
          }),
        ],
        asset_total: row({ category_id: "asset_total", is_total: true }),
        liability_total: row({ category_id: "liability_total", side: "liability", is_total: true }),
        grand_total: row({ category_id: "grand_total", is_total: true }),
      }, "2026年02月"),
      buildProductCategoryTrendSnapshot({
        report_date: "2026-03-31",
        view: "monthly",
        available_views: ["monthly"],
        scenario_rate_pct: null,
        rows: [
          row({
            category_id: "interbank_deposits",
            category_name: "同业存放更新",
            side: "liability",
            report_date: "2026-03-31",
            cnx_scale: yi(82),
            weighted_yield: "1.30",
          }),
          row({
            category_id: "repo_liabilities",
            category_name: "卖出回购",
            side: "liability",
            report_date: "2026-03-31",
            cnx_scale: "not_available",
            weighted_yield: null,
          }),
        ],
        asset_total: row({ category_id: "asset_total", is_total: true }),
        liability_total: row({ category_id: "liability_total", side: "liability", is_total: true }),
        grand_total: row({ category_id: "grand_total", is_total: true }),
      }, "2026年03月"),
    ];

    const matrix = buildProductCategoryLiabilitySideTrendSurface(snapshots).detailMatrix;

    expect(matrix.periods.map((period) => period.label)).toEqual([
      "2026年01月",
      "2026年02月",
      "2026年03月",
    ]);
    expect(matrix.movementGroupLabel).toBe("环比月度变动情况");
    expect(matrix.rows.map((item) => item.categoryId)).toEqual([
      "liability_total",
      "interbank_deposits",
      "repo_liabilities",
      "interbank_cds",
    ]);
    expect(matrix.rows.find((item) => item.categoryId === "interbank_deposits")).toMatchObject({
      categoryLabel: "同业存放更新",
      cells: [
        { amountLabel: "75.00", rateLabel: "1.10" },
        { amountLabel: "80.00", rateLabel: "1.20" },
        { amountLabel: "82.00", rateLabel: "1.30" },
      ],
      movement: { amountLabel: "+2.00", rateLabel: "+10bp" },
    });
    expect(matrix.rows.find((item) => item.categoryId === "repo_liabilities")).toMatchObject({
      cells: [
        { amountLabel: "-", rateLabel: "-" },
        { amountLabel: "51.00", rateLabel: "1.33" },
        { amountLabel: "-", rateLabel: "-" },
      ],
      movement: { amountLabel: "-", rateLabel: "-" },
    });
    expect(matrix.rows.find((item) => item.categoryId === "interbank_cds")).toMatchObject({
      categoryLabel: "同业存单",
      movement: { amountLabel: "-", rateLabel: "-" },
    });
  });

  it("adds liability total plus CNY and foreign amount structures to the detail matrix", () => {
    const snapshots = [
      buildProductCategoryTrendSnapshot({
        report_date: "2026-01-31",
        view: "monthly",
        available_views: ["monthly"],
        scenario_rate_pct: null,
        rows: [
          row({
            category_id: "interbank_deposits",
            category_name: "同业存放",
            side: "liability",
            report_date: "2026-01-31",
            cnx_scale: yi(75),
            cny_scale: yi(60),
            foreign_scale: yi(15),
            cny_cash: annualizedCash(60, 2.00, 31),
            foreign_cash: annualizedCash(15, 1.00, 31),
            weighted_yield: "1.10",
          }),
          row({
            category_id: "interbank_cds",
            category_name: "同业存单",
            side: "liability",
            report_date: "2026-01-31",
            cnx_scale: yi(120),
            cny_scale: yi(110),
            foreign_scale: yi(10),
            cny_cash: annualizedCash(110, 1.50, 31),
            foreign_cash: annualizedCash(10, 2.50, 31),
            weighted_yield: "1.45",
          }),
        ],
        asset_total: row({ category_id: "asset_total", is_total: true }),
        liability_total: row({
          category_id: "liability_total",
          category_name: "负债合计",
          side: "liability",
          is_total: true,
          report_date: "2026-01-31",
          cnx_scale: yi(195),
          cny_scale: yi(170),
          foreign_scale: yi(25),
          cny_cash: annualizedCash(170, 1.68, 31),
          foreign_cash: annualizedCash(25, 1.60, 31),
          weighted_yield: "1.30",
        }),
        grand_total: row({ category_id: "grand_total", is_total: true }),
      }, "2026年01月"),
      buildProductCategoryTrendSnapshot({
        report_date: "2026-02-28",
        view: "monthly",
        available_views: ["monthly"],
        scenario_rate_pct: null,
        rows: [
          row({
            category_id: "interbank_deposits",
            category_name: "同业存放",
            side: "liability",
            report_date: "2026-02-28",
            cnx_scale: yi(80),
            cny_scale: yi(64),
            foreign_scale: yi(16),
            cny_cash: annualizedCash(64, 2.10, 28),
            foreign_cash: annualizedCash(16, 1.25, 28),
            weighted_yield: "1.20",
          }),
          row({
            category_id: "interbank_cds",
            category_name: "同业存单",
            side: "liability",
            report_date: "2026-02-28",
            cnx_scale: yi(118),
            cny_scale: "not_available",
            foreign_scale: yi(8),
            cny_cash: annualizedCash(108, 1.60, 28),
            foreign_cash: annualizedCash(8, 2.75, 28),
            weighted_yield: "1.40",
          }),
        ],
        asset_total: row({ category_id: "asset_total", is_total: true }),
        liability_total: row({
          category_id: "liability_total",
          category_name: "负债合计",
          side: "liability",
          is_total: true,
          report_date: "2026-02-28",
          cnx_scale: yi(198),
          cny_scale: yi(174),
          foreign_scale: yi(24),
          cny_cash: annualizedCash(174, 2.00, 28),
          foreign_cash: annualizedCash(24, 1.75, 28),
          weighted_yield: "1.25",
        }),
        grand_total: row({ category_id: "grand_total", is_total: true }),
      }, "2026年02月"),
    ];

    const matrix = buildProductCategoryLiabilitySideTrendSurface(snapshots).detailMatrix;

    expect(matrix.rows[0]).toMatchObject({
      categoryId: "liability_total",
      categoryLabel: "负债合计",
      cells: [
        { amountLabel: "195.00", rateLabel: "1.30" },
        { amountLabel: "198.00", rateLabel: "1.25" },
      ],
      movement: { amountLabel: "+3.00", rateLabel: "-5bp" },
    });
    expect(matrix.currencyMatrices.map((item) => item.currencyKey)).toEqual(["cny", "foreign"]);

    const cnyMatrix = matrix.currencyMatrices.find((item) => item.currencyKey === "cny");
    expect(cnyMatrix?.currencyLabel).toBe("人民币结构");
    expect(cnyMatrix?.rows[0]).toMatchObject({
      categoryId: "liability_total",
      categoryLabel: "负债合计",
      cells: [
        { amountLabel: "170.00", rateLabel: "1.68" },
        { amountLabel: "174.00", rateLabel: "2.00" },
      ],
      movement: { amountLabel: "+4.00", rateLabel: "+32bp" },
    });
    expect(cnyMatrix?.rows.find((item) => item.categoryId === "interbank_cds")).toMatchObject({
      cells: [
        { amountLabel: "110.00", rateLabel: "1.50" },
        { amountLabel: "-", rateLabel: "-" },
      ],
      movement: { amountLabel: "-", rateLabel: "-" },
    });

    const foreignMatrix = matrix.currencyMatrices.find((item) => item.currencyKey === "foreign");
    expect(foreignMatrix?.currencyLabel).toBe("外币结构");
    expect(foreignMatrix?.rows[0]).toMatchObject({
      categoryId: "liability_total",
      cells: [
        { amountLabel: "25.00", rateLabel: "1.60" },
        { amountLabel: "24.00", rateLabel: "1.75" },
      ],
      movement: { amountLabel: "-1.00", rateLabel: "+15bp" },
    });
  });

  it("labels mixed-period liability detail movement as prior-period rather than monthly MoM", () => {
    const snapshots = [
      buildProductCategoryTrendSnapshot({
        report_date: "2025-03-31",
        view: "monthly",
        available_views: ["monthly"],
        scenario_rate_pct: null,
        rows: [
          row({
            category_id: "interbank_deposits",
            category_name: "同业存放",
            side: "liability",
            report_date: "2025-03-31",
            cnx_scale: yi(75),
            weighted_yield: "1.10",
          }),
        ],
        asset_total: row({ category_id: "asset_total", is_total: true }),
        liability_total: row({ category_id: "liability_total", side: "liability", is_total: true }),
        grand_total: row({ category_id: "grand_total", is_total: true }),
      }, "2025年Q1"),
      buildProductCategoryTrendSnapshot({
        report_date: "2025-11-30",
        view: "monthly",
        available_views: ["monthly"],
        scenario_rate_pct: null,
        rows: [
          row({
            category_id: "interbank_deposits",
            category_name: "同业存放",
            side: "liability",
            report_date: "2025-11-30",
            cnx_scale: "not_available",
            weighted_yield: "1.20",
          }),
        ],
        asset_total: row({ category_id: "asset_total", is_total: true }),
        liability_total: row({ category_id: "liability_total", side: "liability", is_total: true }),
        grand_total: row({ category_id: "grand_total", is_total: true }),
      }, "2025年11月"),
      buildProductCategoryTrendSnapshot({
        report_date: "2026-03-31",
        view: "monthly",
        available_views: ["monthly"],
        scenario_rate_pct: null,
        rows: [
          row({
            category_id: "interbank_deposits",
            category_name: "同业存放",
            side: "liability",
            report_date: "2026-03-31",
            cnx_scale: yi(82),
            weighted_yield: "1.30",
          }),
        ],
        asset_total: row({ category_id: "asset_total", is_total: true }),
        liability_total: row({ category_id: "liability_total", side: "liability", is_total: true }),
        grand_total: row({ category_id: "grand_total", is_total: true }),
      }, "2026年03月"),
    ];

    const matrix = buildProductCategoryLiabilitySideTrendSurface(snapshots).detailMatrix;

    expect(matrix.movementGroupLabel).toBe("较上期变动");
    expect(matrix.rows.find((item) => item.categoryId === "interbank_deposits")?.movement).toEqual({
      amountLabel: "-",
      rateLabel: "+10bp",
    });
  });

  it("does not backfill missing latest liability detail metrics from historical snapshots", () => {
    const snapshots = [
      buildProductCategoryTrendSnapshot({
        report_date: "2026-02-28",
        view: "monthly",
        available_views: ["monthly"],
        scenario_rate_pct: null,
        rows: [
          row({
            category_id: "interbank_deposits",
            category_name: "同业存放",
            side: "liability",
            report_date: "2026-02-28",
            cnx_scale: yi(75),
            weighted_yield: "1.20",
          }),
        ],
        asset_total: row({ category_id: "asset_total", is_total: true }),
        liability_total: row({
          category_id: "liability_total",
          side: "liability",
          is_total: true,
          cnx_scale: yi(1500),
          weighted_yield: "1.60",
        }),
        grand_total: row({ category_id: "grand_total", is_total: true }),
      }, "2026年02月"),
      buildProductCategoryTrendSnapshot({
        report_date: "2026-03-31",
        view: "monthly",
        available_views: ["monthly"],
        scenario_rate_pct: null,
        rows: [
          row({
            category_id: "interbank_deposits",
            category_name: "同业存放",
            side: "liability",
            report_date: "2026-03-31",
            cnx_scale: "not_available",
            weighted_yield: null,
          }),
        ],
        asset_total: row({ category_id: "asset_total", is_total: true }),
        liability_total: row({
          category_id: "liability_total",
          side: "liability",
          is_total: true,
          cnx_scale: "not_available",
          weighted_yield: null,
        }),
        grand_total: row({ category_id: "grand_total", is_total: true }),
      }, "2026年03月"),
    ];

    const surface = buildProductCategoryLiabilitySideTrendSurface(snapshots);
    expect(surface.chart?.labels).toEqual(["2026年02月", "2026年03月"]);
    expect(surface.chart?.totalAverageDaily).toEqual([1500, null]);
    expect(surface.chart?.totalRate).toEqual([1.6, null]);
    expect(surface.detailRows.find((item) => item.categoryId === "interbank_deposits")).toMatchObject({
      latestAmountLabel: "-",
      amountDeltaLabel: "-",
      latestRateLabel: "-",
      rateDeltaLabel: "-",
      comparisonLabel: "当前指标缺失",
    });
  });

  it("preserves liability-side chart labels when all aggregate points are missing", () => {
    const snapshots = [
      buildProductCategoryTrendSnapshot({
        report_date: "2026-02-28",
        view: "monthly",
        available_views: ["monthly"],
        scenario_rate_pct: null,
        rows: [],
        asset_total: row({ category_id: "asset_total", is_total: true }),
        liability_total: row({
          category_id: "liability_total",
          side: "liability",
          is_total: true,
          cnx_scale: "not_available",
          weighted_yield: null,
        }),
        grand_total: row({ category_id: "grand_total", is_total: true }),
      }, "2026年02月"),
      buildProductCategoryTrendSnapshot({
        report_date: "2026-03-31",
        view: "monthly",
        available_views: ["monthly"],
        scenario_rate_pct: null,
        rows: [],
        asset_total: row({ category_id: "asset_total", is_total: true }),
        liability_total: row({
          category_id: "liability_total",
          side: "liability",
          is_total: true,
          cnx_scale: "not_available",
          weighted_yield: null,
        }),
        grand_total: row({ category_id: "grand_total", is_total: true }),
      }, "2026年03月"),
    ];

    const surface = buildProductCategoryLiabilitySideTrendSurface(snapshots);
    expect(surface.chart?.labels).toEqual(["2026年02月", "2026年03月"]);
    expect(surface.chart?.totalAverageDaily).toEqual([null, null]);
    expect(surface.chart?.totalRate).toEqual([null, null]);
    expect(surface.emptyCopy).toBeNull();
    expect(surface.incompleteReasons).toEqual([
      "2026年02月负债端日均额缺失",
      "2026年02月负债端利率缺失",
      "2026年03月负债端日均额缺失",
      "2026年03月负债端利率缺失",
    ]);
  });

  it("marks latest liability detail rows without a prior comparable snapshot", () => {
    const snapshots = [
      buildProductCategoryTrendSnapshot({
        report_date: "2026-03-31",
        view: "monthly",
        available_views: ["monthly"],
        scenario_rate_pct: null,
        rows: [
          row({
            category_id: "credit_linked_notes",
            category_name: "收益凭证",
            side: "liability",
            report_date: "2026-03-31",
            cnx_scale: yi(25),
            weighted_yield: "3.25",
          }),
        ],
        asset_total: row({ category_id: "asset_total", is_total: true }),
        liability_total: row({
          category_id: "liability_total",
          side: "liability",
          is_total: true,
          cnx_scale: yi(1700),
          weighted_yield: "1.75",
        }),
        grand_total: row({ category_id: "grand_total", is_total: true }),
      }, "2026年03月"),
    ];

    const surface = buildProductCategoryLiabilitySideTrendSurface(snapshots);
    expect(surface.detailRows.find((item) => item.categoryId === "credit_linked_notes")).toMatchObject({
      latestAmountLabel: "25.00",
      amountDeltaLabel: "-",
      latestRateLabel: "3.25",
      rateDeltaLabel: "-",
      comparisonLabel: "缺少可比上期",
    });
  });

  it("formats yuan money values as yi yuan, with liability-side absolute display", () => {
    expect(formatProductCategoryValue("285499749.04110849")).toBe("2.85");
    expect(
      formatProductCategoryRowDisplayValue(
        row({ category_id: "repo_liabilities", side: "liability" }),
        "-123456789",
      ),
    ).toBe("1.23");
    expect(
      formatProductCategoryRowDisplayValue(
        row({ category_id: "repo_assets", side: "asset" }),
        "-123456789",
      ),
    ).toBe("-1.23");
    expect(
      formatProductCategoryRowDisplayValue(
        row({ category_id: "asset_total", side: "all" }),
        "-123456789",
      ),
    ).toBe("-1.23");
  });

  it("formats nullish values as dash and passes through invalid decimal-like strings unchanged", () => {
    expect(formatProductCategoryValue(null)).toBe("-");
    expect(formatProductCategoryValue(undefined)).toBe("-");
    expect(
      formatProductCategoryRowDisplayValue(
        row({ category_id: "repo_liabilities", side: "liability" }),
        "not-a-number",
      ),
    ).toBe("not-a-number");
  });

  it("formats yield values as percentages without money unit scaling", () => {
    expect(formatProductCategoryYieldValue("2.345")).toBe("2.35");
    expect(formatProductCategoryYieldValue(null)).toBe("-");
    expect(formatProductCategoryYieldValue("not-a-number")).toBe("not-a-number");
  });

  it("returns the current visible tone colors for positive, negative, zero, and invalid values", () => {
    expect(PRODUCT_CATEGORY_VALUE_TONE_COLORS).toEqual({
      default: designTokens.color.neutral[900],
      positive: designTokens.color.semantic.profit,
      negative: designTokens.color.semantic.loss,
    });
    expect(toneForProductCategoryValue("12.3")).toBe(PRODUCT_CATEGORY_VALUE_TONE_COLORS.positive);
    expect(toneForProductCategoryValue("-12.3")).toBe(PRODUCT_CATEGORY_VALUE_TONE_COLORS.negative);
    expect(toneForProductCategoryValue("0")).toBe(PRODUCT_CATEGORY_VALUE_TONE_COLORS.default);
    expect(toneForProductCategoryValue("not-a-number")).toBe(
      PRODUCT_CATEGORY_VALUE_TONE_COLORS.default,
    );
    expect(toneForProductCategoryValue(null)).toBe(PRODUCT_CATEGORY_VALUE_TONE_COLORS.default);
  });

  it("exposes a stable as_of_date gap string for the page (no invented as_of_date)", () => {
    expect(PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY).toContain("归属日期");
    expect(PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY).toContain("无独立外显");
  });

  it("collects governance notices for fallback, vendor, and quality degradation from result_meta", () => {
    expect(collectProductCategoryGovernanceNotices(undefined)).toEqual([]);
    expect(collectProductCategoryGovernanceNotices(resultMeta({}))).toEqual([]);

    const allThree = collectProductCategoryGovernanceNotices(
      resultMeta({
        fallback_mode: "latest_snapshot",
        vendor_status: "vendor_stale",
        quality_flag: "stale",
      }),
    );
    expect(allThree.map((n) => n.id)).toEqual([
      "fallback_mode",
      "vendor_status",
      "quality_flag",
    ]);
    expect(allThree[0]?.text).toContain("降级模式");
    expect(allThree[1]?.text).toContain("供应商状态");
    expect(allThree[2]?.text).toContain("质量标记");

    expect(
      collectProductCategoryGovernanceNotices(
        resultMeta({ vendor_status: "vendor_unavailable" }),
      ).map((n) => n.id),
    ).toEqual(["vendor_status"]);
  });

  it("formats a dual-meta line that keeps formal vs scenario trace_id distinguishable", () => {
    const line = formatProductCategoryDualMetaDistinctLine(
      resultMeta({ basis: "formal", trace_id: "t_formal" }),
      resultMeta({ basis: "scenario", trace_id: "t_scen", scenario_flag: true }),
    );
    expect(line).toContain("t_formal");
    expect(line).toContain("t_scen");
    expect(line).toContain("正式口径=正式口径");
    expect(line).toContain("情景口径=情景口径");
  });
});
