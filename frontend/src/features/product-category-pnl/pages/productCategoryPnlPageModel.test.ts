import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import type {
  ProductCategoryAttributionEffects,
  ProductCategoryAttributionPayload,
  ProductCategoryPnlPayload,
  ProductCategoryPnlRow,
  ResultMeta,
} from "../../../api/contracts";
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
  selectProductCategoryAttributionWaterfallSurface,
  selectProductCategoryDecisionFocusSurface,
  selectProductCategoryIntermediateBusinessIncomeYearComparisonChart,
  selectProductCategoryInterestSpreadAttributionSurface,
  selectProductCategoryInterestSpreadYearComparisonChart,
  selectProductCategoryOperatingAnalysisSurface,
  selectProductCategoryOperatingActionBacktestSurface,
  selectProductCategoryRootCauseSurface,
  selectProductCategoryScenarioExplanation,
  selectProductCategoryScenarioSensitivitySurface,
  selectProductCategoryTplScaleYieldChart,
  selectProductCategoryTwoYearInterestSpreadReportPoints,
  selectProductCategoryTrendReportDates,
  selectProductCategoryTrendReportPoints,
  toneForProductCategoryValue,
} from "./productCategoryPnlPageModel";

const GOLDEN_SAMPLE_A_RESPONSE = JSON.parse(
  readFileSync(
    "../tests/golden_samples/GS-PROD-CAT-PNL-A/response.json",
    "utf8",
  ),
) as { result: ProductCategoryPnlPayload };

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

function attributionPayload(overrides: Partial<ProductCategoryAttributionPayload>): ProductCategoryAttributionPayload {
  return {
    report_date: "2026-02-28",
    compare: "mom",
    current_report_date: "2026-02-28",
    prior_report_date: "2026-01-31",
    state: "complete",
    reason: null,
    rows: [],
    totals: null,
    ...overrides,
  };
}

function attributionRow(
  partial: Pick<ProductCategoryAttributionPayload["rows"][number], "category_id"> &
    Omit<Partial<ProductCategoryAttributionPayload["rows"][number]>, "effects"> & {
      effects?: Partial<ProductCategoryAttributionEffects>;
    },
): ProductCategoryAttributionPayload["rows"][number] {
  const { effects, ...rest } = partial;
  return {
    category_name: rest.category_name ?? rest.category_id,
    side: rest.side ?? "asset",
    level: rest.level ?? 0,
    state: rest.state ?? "complete",
    current: rest.current ?? null,
    prior: rest.prior ?? null,
    effects: {
      day_effect: "0",
      scale_effect: "0",
      rate_effect: "0",
      ftp_effect: "0",
      direct_effect: "0",
      unexplained_effect: "0",
      explained_effect: "0",
      delta_business_net_income: "0",
      closure_error: "0",
      ...effects,
    },
    ...rest,
  };
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

  it("builds operating analysis from current rows and existing attribution data", () => {
    const rows = [
      row({
        category_id: "bond_investment",
        category_name: "债券投资",
        cnx_scale: yi(3000),
        business_net_income: yi(7),
        weighted_yield: "2.50",
        children: ["bond_ac", "bond_fvoci"],
      }),
      row({
        category_id: "repo_assets",
        category_name: "买入返售",
        cnx_scale: yi(200),
        business_net_income: yi(-0.3),
        weighted_yield: "1.20",
      }),
      row({
        category_id: "bond_ac",
        category_name: "AC债券投资",
        cnx_scale: yi(2000),
        business_net_income: yi(5),
        weighted_yield: "2.60",
        level: 1,
      }),
      row({
        category_id: "bond_fvoci",
        category_name: "FVOCI",
        cnx_scale: yi(1000),
        business_net_income: yi(1),
        weighted_yield: "1.80",
        level: 1,
      }),
      row({
        category_id: "intermediate_business_income",
        category_name: "中间业务收入",
        cnx_scale: "0",
        business_net_income: yi(0.05),
        weighted_yield: null,
      }),
      row({
        category_id: "asset_total",
        category_name: "资产端合计",
        cnx_scale: yi(4200),
        business_net_income: yi(7.75),
        weighted_yield: "2.35",
        is_total: true,
      }),
    ];
    const surface = selectProductCategoryOperatingAnalysisSurface({
      rows,
      grandTotal: row({
        category_id: "grand_total",
        category_name: "全表合计",
        side: "all",
        business_net_income: yi(8),
        is_total: true,
      }),
      attribution: attributionPayload({
        rows: [
          attributionRow({
            category_id: "bond_investment",
            category_name: "债券投资",
            effects: {
              delta_business_net_income: yi(1.5),
              rate_effect: yi(0.9),
              scale_effect: yi(0.2),
              ftp_effect: yi(0.1),
              direct_effect: yi(0.2),
              unexplained_effect: yi(0.1),
            },
          }),
          attributionRow({
            category_id: "repo_assets",
            category_name: "买入返售",
            effects: {
              delta_business_net_income: yi(-0.4),
              rate_effect: yi(-0.3),
              scale_effect: yi(-0.05),
              ftp_effect: yi(-0.03),
              unexplained_effect: yi(-0.02),
            },
          }),
        ],
      }),
    });

    expect(surface.contribution.profitRows[0]).toMatchObject({
      categoryId: "bond_ac",
      categoryLabel: "AC债券投资",
      netIncomeLabel: "5.00",
      contributionLabel: "62.5%",
      tone: "positive",
    });
    expect(surface.contribution.profitRows.map((item) => item.categoryId)).not.toContain("bond_investment");
    expect(surface.contribution.pressureRows[0]).toMatchObject({
      categoryId: "repo_assets",
      netIncomeLabel: "-0.30",
      contributionLabel: "-3.8%",
      tone: "negative",
    });
    expect(surface.movement.rows[0]).toMatchObject({
      categoryId: "repo_assets",
      deltaLabel: "-0.40",
      leadingDriverLabel: "利率因素",
      leadingDriverValueLabel: "-0.30",
    });
    expect(surface.movement.rows.map((item) => item.categoryId)).not.toContain("bond_investment");
    expect(surface.quadrant.rows.map((item) => item.categoryId)).not.toContain("bond_investment");
    expect(surface.quadrant.rows).toEqual([
      expect.objectContaining({
        categoryId: "bond_ac",
        quadrant: "core_profit_pool",
        quadrantLabel: "核心利润池",
      }),
      expect.objectContaining({
        categoryId: "bond_fvoci",
        quadrant: "scale_efficiency_watch",
        quadrantLabel: "高规模低收益",
      }),
      expect.objectContaining({
        categoryId: "repo_assets",
        quadrant: "shrink_or_reprice",
        quadrantLabel: "低规模低收益",
      }),
    ]);
  });

  it("builds an operating action queue from profitability, scale, yield, and attribution evidence", () => {
    const rows = [
      row({
        category_id: "selective_growth_asset",
        category_name: "选择性增长资产",
        cnx_scale: yi(120),
        business_net_income: yi(0.8),
        weighted_yield: "3.20",
      }),
      row({
        category_id: "large_low_yield_asset",
        category_name: "大规模低收益资产",
        cnx_scale: yi(1000),
        business_net_income: yi(0.3),
        weighted_yield: "1.20",
      }),
      row({
        category_id: "loss_asset",
        category_name: "亏损资产",
        cnx_scale: yi(550),
        business_net_income: yi(-0.4),
        weighted_yield: "1.10",
      }),
      row({
        category_id: "unexplained_asset",
        category_name: "未解释资产",
        cnx_scale: yi(800),
        business_net_income: yi(1.1),
        weighted_yield: "2.40",
      }),
    ];
    const surface = selectProductCategoryOperatingAnalysisSurface({
      rows,
      grandTotal: row({
        category_id: "grand_total",
        category_name: "全表合计",
        side: "all",
        business_net_income: yi(1.8),
        is_total: true,
      }),
      attribution: attributionPayload({
        rows: [
          attributionRow({
            category_id: "large_low_yield_asset",
            category_name: "大规模低收益资产",
            effects: {
              delta_business_net_income: yi(-0.2),
              rate_effect: yi(-0.16),
            },
          }),
          attributionRow({
            category_id: "loss_asset",
            category_name: "亏损资产",
            effects: {
              delta_business_net_income: yi(-0.5),
              rate_effect: yi(-0.3),
            },
          }),
          attributionRow({
            category_id: "unexplained_asset",
            category_name: "未解释资产",
            effects: {
              delta_business_net_income: yi(0.6),
              unexplained_effect: yi(0.45),
            },
          }),
        ],
      }),
    });

    expect(surface.actionQueue.emptyCopy).toBeNull();
    expect(surface.actionQueue.rows.map((item) => item.actionKind)).toEqual([
      "shrink_or_limit",
      "review_attribution",
      "reprice_or_improve",
      "selective_growth",
    ]);
    expect(surface.actionQueue.rows).toEqual([
      expect.objectContaining({
        priorityLabel: "P1",
        categoryId: "loss_asset",
        actionLabel: "压降或限额复核",
        triggerLabel: "负贡献叠加收益偏低",
        primaryMetricLabel: "-0.40",
      }),
      expect.objectContaining({
        priorityLabel: "P2",
        categoryId: "unexplained_asset",
        actionLabel: "归因复核",
        triggerLabel: "未解释差异偏高",
        primaryMetricLabel: "+0.45",
      }),
      expect.objectContaining({
        priorityLabel: "P3",
        categoryId: "large_low_yield_asset",
        actionLabel: "重定价/提效",
        triggerLabel: "高规模低收益",
        primaryMetricLabel: "1.20%",
      }),
      expect.objectContaining({
        priorityLabel: "P4",
        categoryId: "selective_growth_asset",
        actionLabel: "选择性扩张",
        triggerLabel: "低规模高收益",
        primaryMetricLabel: "3.20%",
      }),
    ]);
    expect(surface.actionQueue.rows[0]?.evidenceItems).toEqual([
      "净营收 -0.40 亿元",
      "规模 550.00 亿元",
      "收益率 1.10%",
      "变动 -0.50 亿元",
    ]);
  });

  it("requires low-yield evidence before placing a loss row in the operating action queue", () => {
    const surface = selectProductCategoryOperatingAnalysisSurface({
      rows: [
        row({
          category_id: "high_yield_loss_asset",
          category_name: "高收益亏损资产",
          cnx_scale: yi(120),
          business_net_income: yi(-0.4),
          weighted_yield: "4.00",
        }),
        row({
          category_id: "low_yield_scale_asset",
          category_name: "高规模低收益资产",
          cnx_scale: yi(1000),
          business_net_income: yi(0.6),
          weighted_yield: "1.10",
        }),
        row({
          category_id: "core_asset",
          category_name: "核心资产",
          cnx_scale: yi(900),
          business_net_income: yi(1.2),
          weighted_yield: "3.00",
        }),
      ],
      grandTotal: row({
        category_id: "grand_total",
        side: "all",
        business_net_income: yi(1.4),
        is_total: true,
      }),
      attribution: attributionPayload({ rows: [] }),
    });

    expect(surface.actionQueue.rows.map((item) => item.actionKind)).toEqual(["reprice_or_improve"]);
    expect(surface.actionQueue.rows[0]).toEqual(expect.objectContaining({
      categoryId: "low_yield_scale_asset",
      actionLabel: "重定价/提效",
      triggerLabel: "高规模低收益",
    }));
    expect(surface.actionQueue.rows.map((item) => item.categoryId)).not.toContain("high_yield_loss_asset");
  });

  it("uses absolute unexplained attribution and avoids duplicate action rows for the same category", () => {
    const surface = selectProductCategoryOperatingAnalysisSurface({
      rows: [
        row({
          category_id: "loss_reprice_asset",
          category_name: "亏损低收益资产",
          cnx_scale: yi(1200),
          business_net_income: yi(-0.7),
          weighted_yield: "1.00",
        }),
        row({
          category_id: "next_reprice_asset",
          category_name: "次级低收益资产",
          cnx_scale: yi(1000),
          business_net_income: yi(0.4),
          weighted_yield: "1.10",
        }),
        row({
          category_id: "negative_unexplained_asset",
          category_name: "负向未解释资产",
          cnx_scale: yi(800),
          business_net_income: yi(0.5),
          weighted_yield: "2.20",
        }),
        row({
          category_id: "growth_asset",
          category_name: "成长资产",
          cnx_scale: yi(120),
          business_net_income: yi(0.8),
          weighted_yield: "3.20",
        }),
      ],
      grandTotal: row({
        category_id: "grand_total",
        side: "all",
        business_net_income: yi(1),
        is_total: true,
      }),
      attribution: attributionPayload({
        rows: [
          attributionRow({
            category_id: "negative_unexplained_asset",
            category_name: "负向未解释资产",
            effects: {
              delta_business_net_income: yi(-0.8),
              unexplained_effect: yi(-0.65),
            },
          }),
          attributionRow({
            category_id: "loss_reprice_asset",
            category_name: "亏损低收益资产",
            effects: {
              delta_business_net_income: yi(-0.7),
              rate_effect: yi(-0.5),
            },
          }),
        ],
      }),
    });

    expect(surface.actionQueue.rows.map((item) => item.actionKind)).toEqual([
      "shrink_or_limit",
      "review_attribution",
      "reprice_or_improve",
      "selective_growth",
    ]);
    expect(surface.actionQueue.rows.map((item) => item.categoryId)).toEqual([
      "loss_reprice_asset",
      "negative_unexplained_asset",
      "next_reprice_asset",
      "growth_asset",
    ]);
    expect(surface.actionQueue.rows[1]).toEqual(expect.objectContaining({
      actionLabel: "归因复核",
      primaryMetricLabel: "-0.65",
    }));
  });

  it("backtests operating action signals against the next monthly payload", () => {
    const january: ProductCategoryPnlPayload = {
      report_date: "2026-01-31",
      view: "monthly",
      available_views: ["monthly", "ytd"],
      scenario_rate_pct: null,
      rows: [
        row({
          report_date: "2026-01-31",
          category_id: "loss_asset",
          category_name: "亏损资产",
          cnx_scale: yi(600),
          business_net_income: yi(-0.5),
          weighted_yield: "1.00",
        }),
        row({
          report_date: "2026-01-31",
          category_id: "scale_asset",
          category_name: "高规模低收益",
          cnx_scale: yi(1000),
          business_net_income: yi(0.2),
          weighted_yield: "1.20",
        }),
        row({
          report_date: "2026-01-31",
          category_id: "growth_asset",
          category_name: "成长资产",
          cnx_scale: yi(100),
          business_net_income: yi(0.4),
          weighted_yield: "3.20",
        }),
      ],
      asset_total: row({ report_date: "2026-01-31", category_id: "asset_total", is_total: true }),
      liability_total: row({
        report_date: "2026-01-31",
        category_id: "liability_total",
        side: "liability",
        is_total: true,
      }),
      grand_total: row({
        report_date: "2026-01-31",
        category_id: "grand_total",
        side: "all",
        business_net_income: yi(0.1),
        is_total: true,
      }),
    };
    const february: ProductCategoryPnlPayload = {
      ...january,
      report_date: "2026-02-28",
      rows: [
        row({
          report_date: "2026-02-28",
          category_id: "loss_asset",
          category_name: "亏损资产",
          cnx_scale: yi(500),
          business_net_income: yi(-0.2),
          weighted_yield: "1.40",
        }),
        row({
          report_date: "2026-02-28",
          category_id: "scale_asset",
          category_name: "高规模低收益",
          cnx_scale: yi(1100),
          business_net_income: yi(0.15),
          weighted_yield: "1.10",
        }),
        row({
          report_date: "2026-02-28",
          category_id: "growth_asset",
          category_name: "成长资产",
          cnx_scale: yi(150),
          business_net_income: yi(0.5),
          weighted_yield: "3.10",
        }),
      ],
      asset_total: row({ report_date: "2026-02-28", category_id: "asset_total", is_total: true }),
      liability_total: row({
        report_date: "2026-02-28",
        category_id: "liability_total",
        side: "liability",
        is_total: true,
      }),
      grand_total: row({
        report_date: "2026-02-28",
        category_id: "grand_total",
        side: "all",
        business_net_income: yi(0.45),
        is_total: true,
      }),
    };

    const surface = selectProductCategoryOperatingActionBacktestSurface({
      payloads: [january, february],
      attributionsByReportDate: new Map([
        ["2026-01-31", attributionPayload({ report_date: "2026-01-31", rows: [] })],
      ]),
    });

    expect(surface.emptyCopy).toBeNull();
    expect(surface.summary).toEqual(expect.objectContaining({
      evaluatedMonthCount: 1,
      signalCount: 3,
      latestPendingCount: 3,
      coverageLabel: "2026-01-31 至 2026-01-31",
      attributionCoverageLabel: "1/2",
      attributionCoverageDetailLabel: "归因覆盖 1/2；缺少 2026-02-28",
    }));
    expect(surface.actionRows.map((item) => item.actionKind)).toEqual([
      "shrink_or_limit",
      "reprice_or_improve",
      "selective_growth",
    ]);
    expect(surface.actionRows[0]).toEqual(expect.objectContaining({
      actionLabel: "压降或限额复核",
      signalCount: 1,
      hitRateLabel: "100.0%",
      averageNetIncomeDeltaLabel: "+0.30",
      averageYieldDeltaBpLabel: "+40.0bp",
      averageScaleDeltaLabel: "-100.00",
    }));
    expect(surface.actionRows[1]).toEqual(expect.objectContaining({
      actionLabel: "重定价/提效",
      hitRateLabel: "0.0%",
      averageYieldDeltaBpLabel: "-10.0bp",
    }));
    expect(surface.missReasonRows[0]).toEqual(expect.objectContaining({
      actionKind: "reprice_or_improve",
      actionLabel: "重定价/提效",
      missCount: 1,
      missRateLabel: "100.0%",
      primaryReasonLabel: "收益率未改善",
      reasonRows: [
        expect.objectContaining({
          reasonKey: "yield_not_improved",
          reasonLabel: "收益率未改善",
          sampleCount: 1,
        }),
        expect.objectContaining({
          reasonKey: "scale_mismatch",
          reasonLabel: "规模方向错配",
          sampleCount: 1,
        }),
        expect.objectContaining({
          reasonKey: "net_income_drag",
          reasonLabel: "净营收拖累",
          sampleCount: 1,
        }),
      ],
    }));
    expect(surface.calibrationRows[0]).toEqual(expect.objectContaining({
      actionKind: "reprice_or_improve",
      actionLabel: "重定价/提效",
      recommendationLabel: "收紧触发条件",
      reasonLabel: "命中率 0.0%，主因收益率未改善",
      confidenceLabel: "低置信",
      confidenceDetailLabel: "1 条可评价样本",
    }));
    expect(surface.latestReviewRows).toEqual([
      expect.objectContaining({
        categoryId: "scale_asset",
        categoryLabel: "高规模低收益",
        actionLabel: "重定价/提效",
        reviewLabel: "复核后执行",
        reasonLabel: "历史回测建议收紧触发条件：命中率 0.0%，主因收益率未改善",
      }),
    ]);
    expect(surface.actionRows[2]).toEqual(expect.objectContaining({
      actionLabel: "选择性扩张",
      hitRateLabel: "100.0%",
      averageScaleDeltaLabel: "+50.00",
    }));
    expect(surface.examples[0]).toEqual(expect.objectContaining({
      reportDate: "2026-01-31",
      nextReportDate: "2026-02-28",
      categoryLabel: "亏损资产",
      actionLabel: "压降或限额复核",
      outcomeLabel: "命中",
      netIncomeDeltaLabel: "+0.30",
    }));
  });

  it("does not backtest operating actions across non-consecutive report months", () => {
    const january: ProductCategoryPnlPayload = {
      report_date: "2026-01-31",
      view: "monthly",
      available_views: ["monthly", "ytd"],
      scenario_rate_pct: null,
      rows: [
        row({
          report_date: "2026-01-31",
          category_id: "scale_asset",
          category_name: "高规模低收益",
          cnx_scale: yi(1000),
          business_net_income: yi(0.2),
          weighted_yield: "1.20",
        }),
        row({
          report_date: "2026-01-31",
          category_id: "growth_asset",
          category_name: "成长资产",
          cnx_scale: yi(100),
          business_net_income: yi(0.4),
          weighted_yield: "3.20",
        }),
      ],
      asset_total: row({ report_date: "2026-01-31", category_id: "asset_total", is_total: true }),
      liability_total: row({
        report_date: "2026-01-31",
        category_id: "liability_total",
        side: "liability",
        is_total: true,
      }),
      grand_total: row({
        report_date: "2026-01-31",
        category_id: "grand_total",
        side: "all",
        business_net_income: yi(0.6),
        is_total: true,
      }),
    };
    const march: ProductCategoryPnlPayload = {
      ...january,
      report_date: "2026-03-31",
      rows: january.rows.map((item) => ({ ...item, report_date: "2026-03-31" })),
    };

    const surface = selectProductCategoryOperatingActionBacktestSurface({
      payloads: [january, march],
    });

    expect(surface.summary.evaluatedMonthCount).toBe(0);
    expect(surface.summary.signalCount).toBe(0);
    expect(surface.summary.latestPendingCount).toBe(2);
    expect(surface.coverageRows).toEqual([
      {
        reportDate: "2026-01-31",
        nextReportDate: "2026-03-31",
        statusLabel: "跳过：非连续月份",
        signalCount: 2,
        tone: "negative",
      },
      {
        reportDate: "2026-03-31",
        nextReportDate: null,
        statusLabel: "最新月待观察",
        signalCount: 2,
        tone: "neutral",
      },
    ]);
    expect(surface.actionRows).toEqual([]);
    expect(surface.missReasonRows).toEqual([]);
    expect(surface.calibrationRows).toEqual([]);
    expect(surface.latestReviewRows).toEqual([]);
    expect(surface.emptyCopy).toBe("需要至少两个连续月度正式 payload 才能回测行动信号。");
  });

  it("builds a scenario sensitivity matrix from backend scenario payloads only", () => {
    const baseline = {
      report_date: "2026-02-28",
      view: "monthly",
      available_views: ["monthly", "ytd"],
      scenario_rate_pct: null,
      rows: [
        row({
          category_id: "bond_ac",
          category_name: "AC债券投资",
          business_net_income: yi(5),
        }),
        row({
          category_id: "repo_assets",
          category_name: "买入返售",
          business_net_income: yi(-0.5),
        }),
      ],
      asset_total: row({ category_id: "asset_total", business_net_income: yi(6), is_total: true }),
      liability_total: row({
        category_id: "liability_total",
        side: "liability",
        business_net_income: yi(-1.2),
        is_total: true,
      }),
      grand_total: row({ category_id: "grand_total", business_net_income: yi(4.8), is_total: true }),
    } satisfies ProductCategoryPnlPayload;
    const scenarios: ProductCategoryPnlPayload[] = [
      {
        ...baseline,
        scenario_rate_pct: "1.50",
        rows: [
          row({
            category_id: "bond_ac",
            category_name: "AC债券投资",
            business_net_income: yi(5.4),
          }),
          row({
            category_id: "repo_assets",
            category_name: "买入返售",
            business_net_income: yi(-0.3),
          }),
        ],
        asset_total: row({ category_id: "asset_total", business_net_income: yi(6.4), is_total: true }),
        liability_total: row({
          category_id: "liability_total",
          side: "liability",
          business_net_income: yi(-1.1),
          is_total: true,
        }),
        grand_total: row({ category_id: "grand_total", business_net_income: yi(5.3), is_total: true }),
      },
      {
        ...baseline,
        scenario_rate_pct: "2.00",
        rows: [
          row({
            category_id: "bond_ac",
            category_name: "AC债券投资",
            business_net_income: yi(4.2),
          }),
          row({
            category_id: "repo_assets",
            category_name: "买入返售",
            business_net_income: yi(-0.6),
          }),
        ],
        asset_total: row({ category_id: "asset_total", business_net_income: yi(5.3), is_total: true }),
        liability_total: row({
          category_id: "liability_total",
          side: "liability",
          business_net_income: yi(-1.4),
          is_total: true,
        }),
        grand_total: row({ category_id: "grand_total", business_net_income: yi(3.9), is_total: true }),
      },
    ];

    const surface = selectProductCategoryScenarioSensitivitySurface({
      baseline,
      scenarios,
    });

    expect(surface.baselineGrandTotalLabel).toBe("4.80");
    expect(surface.rows).toEqual([
      expect.objectContaining({
        rateLabel: "1.50%",
        assetNetIncomeLabel: "6.40",
        assetDeltaLabel: "+0.40",
        liabilityNetIncomeLabel: "1.10",
        liabilityDeltaLabel: "+0.10",
        grandNetIncomeLabel: "5.30",
        grandDeltaLabel: "+0.50",
        topMoverCategoryLabel: "AC债券投资",
        topMoverDeltaLabel: "+0.40",
        tone: "positive",
      }),
      expect.objectContaining({
        rateLabel: "2.00%",
        assetDeltaLabel: "-0.70",
        liabilityDeltaLabel: "-0.20",
        grandDeltaLabel: "-0.90",
        topMoverCategoryLabel: "AC债券投资",
        topMoverDeltaLabel: "-0.80",
        tone: "negative",
      }),
    ]);
    expect(surface.insightCards).toEqual([
      expect.objectContaining({
        key: "best_case",
        label: "最佳情景",
        valueLabel: "1.50% / 5.30",
        detailLabel: "较基线 +0.50 亿元",
        tone: "positive",
      }),
      expect.objectContaining({
        key: "worst_case",
        label: "最差情景",
        valueLabel: "2.00% / 3.90",
        detailLabel: "较基线 -0.90 亿元",
        tone: "negative",
      }),
      expect.objectContaining({
        key: "range",
        label: "情景区间",
        valueLabel: "1.40",
        detailLabel: "5.30 - 3.90 亿元",
        tone: "neutral",
      }),
      expect.objectContaining({
        key: "ftp_slope",
        label: "FTP 斜率",
        valueLabel: "-0.03",
        detailLabel: "每 1bp 约影响净营收",
        tone: "negative",
      }),
    ]);
    expect(surface.riskRows).toEqual([
      expect.objectContaining({
        categoryLabel: "AC债券投资",
        worstRateLabel: "2.00%",
        worstDeltaLabel: "-0.80",
        occurrenceLabel: "2 个情景触发最大变动",
        tone: "negative",
      }),
    ]);
    expect(surface.pathPoints).toEqual([
      expect.objectContaining({
        rateLabel: "1.50%",
        grandNetIncomeLabel: "5.30",
        grandDeltaLabel: "+0.50",
        positionPct: 0,
        positionClassName: "is-position-0",
        tone: "positive",
      }),
      expect.objectContaining({
        rateLabel: "2.00%",
        grandNetIncomeLabel: "3.90",
        grandDeltaLabel: "-0.90",
        positionPct: 100,
        positionClassName: "is-position-100",
        tone: "negative",
      }),
    ]);
    expect(surface.actionItems).toEqual([
      expect.objectContaining({
        title: "锁定下行情景敞口",
        valueLabel: "-0.90",
        detailLabel: "2.00% 情景较基线少 0.90 亿元",
        tone: "negative",
      }),
      expect.objectContaining({
        title: "优先复核 AC债券投资",
        valueLabel: "-0.80",
        detailLabel: "最大产品行变动出现在 2.00%",
        tone: "negative",
      }),
      expect.objectContaining({
        title: "设置情景监控阈值",
        valueLabel: "1.40",
        detailLabel: "覆盖最佳到最差情景净营收区间",
        tone: "neutral",
      }),
    ]);
    expect(surface.pressureSummary.breakeven).toEqual(
      expect.objectContaining({
        label: "临界 FTP",
        valueLabel: "约 1.68%",
        detailLabel: "线性插值：1.50% 高于基线 +0.50，2.00% 低于基线 -0.90",
        tone: "warning",
      }),
    );
    expect(surface.pressureSummary.sideOffset).toEqual(
      expect.objectContaining({
        rateLabel: "2.00%",
        totalDeltaLabel: "-0.90",
        assetDeltaLabel: "-0.70",
        liabilityDeltaLabel: "-0.20",
        offsetLabel: "0.00",
        conclusionLabel: "资产端与负债端同向承压，未形成冲抵。",
        assetWidthClassName: "is-width-75",
        liabilityWidthClassName: "is-width-25",
        tone: "negative",
      }),
    );
    expect(surface.pressureSummary.reviewRows).toEqual([
      expect.objectContaining({
        priorityLabel: "复核 1",
        categoryId: "bond_ac",
        categoryLabel: "AC债券投资",
        sideLabel: "资产端",
        triggerRateLabel: "2.00%",
        deltaLabel: "-0.80",
        actionLabel: "复核 FTP 敞口、规模与收益率输入",
        tone: "negative",
      }),
      expect.objectContaining({
        priorityLabel: "复核 2",
        categoryId: "repo_assets",
        categoryLabel: "买入返售",
        sideLabel: "资产端",
        triggerRateLabel: "1.50%",
        deltaLabel: "+0.20",
        actionLabel: "确认情景收益改善来源可持续",
        tone: "positive",
      }),
    ]);
    expect(surface.heatRows).toEqual([
      expect.objectContaining({
        categoryLabel: "AC债券投资",
        exposureLabel: "-0.80",
        widthPct: 100,
        widthClassName: "is-width-100",
        tone: "negative",
      }),
      expect.objectContaining({
        categoryLabel: "买入返售",
        exposureLabel: "+0.20",
        widthPct: 25,
        widthClassName: "is-width-25",
        tone: "positive",
      }),
    ]);
    expect(surface.comparisonRows).toEqual([
      expect.objectContaining({
        categoryId: "bond_ac",
        categoryLabel: "AC债券投资",
        sideLabel: "资产端",
        baselineNetIncomeLabel: "5.00",
        bestRateLabel: "1.50%",
        bestDeltaLabel: "+0.40",
        worstRateLabel: "2.00%",
        worstDeltaLabel: "-0.80",
        rangeLabel: "1.20",
        tone: "negative",
        cells: [
          expect.objectContaining({
            rateLabel: "1.50%",
            netIncomeLabel: "5.40",
            deltaLabel: "+0.40",
            tone: "positive",
          }),
          expect.objectContaining({
            rateLabel: "2.00%",
            netIncomeLabel: "4.20",
            deltaLabel: "-0.80",
            tone: "negative",
          }),
        ],
      }),
      expect.objectContaining({
        categoryId: "repo_assets",
        categoryLabel: "买入返售",
        sideLabel: "资产端",
        baselineNetIncomeLabel: "-0.50",
        bestRateLabel: "1.50%",
        bestDeltaLabel: "+0.20",
        worstRateLabel: "2.00%",
        worstDeltaLabel: "-0.10",
        rangeLabel: "0.30",
      }),
    ]);
    expect(surface.actionClosureRows).toEqual([
      expect.objectContaining({
        priorityLabel: "动作 1",
        categoryId: "bond_ac",
        categoryLabel: "AC债券投资",
        sideLabel: "资产端",
        triggerRateLabel: "2.00%",
        exposureLabel: "-0.80",
        scenarioNetIncomeLabel: "4.20",
        recommendationLabel: "压降 FTP 敞口并复核规模、收益率输入",
        evidenceItems: [
          "正式基线净营收 5.00 亿元",
          "2.00% 情景净营收 4.20 亿元",
          "较基线 -0.80 亿元",
        ],
        memoLabel: "AC债券投资在 2.00% 情景较基线 -0.80 亿元；压降 FTP 敞口并复核规模、收益率输入。",
      }),
      expect.objectContaining({
        priorityLabel: "动作 2",
        categoryId: "repo_assets",
        categoryLabel: "买入返售",
        triggerRateLabel: "2.00%",
        exposureLabel: "-0.10",
      }),
    ]);
    expect(surface.analysisCopy).toBe("FTP 上行时全表净营收承压，最差情景较基线 -0.90 亿元。");
    expect(surface.emptyCopy).toBeNull();
  });

  it("builds a selected scenario review explanation from scenario rows and matching attribution evidence", () => {
    const baseline = {
      report_date: "2026-02-28",
      view: "monthly",
      available_views: ["monthly", "ytd"],
      scenario_rate_pct: null,
      rows: [
        row({
          category_id: "bond_ac",
          category_name: "AC债券投资",
          business_net_income: yi(5),
        }),
        row({
          category_id: "repo_assets",
          category_name: "买入返售",
          business_net_income: yi(-0.5),
        }),
      ],
      asset_total: row({ category_id: "asset_total", business_net_income: yi(6), is_total: true }),
      liability_total: row({
        category_id: "liability_total",
        side: "liability",
        business_net_income: yi(-1.2),
        is_total: true,
      }),
      grand_total: row({ category_id: "grand_total", business_net_income: yi(4.8), is_total: true }),
    } satisfies ProductCategoryPnlPayload;
    const scenarios: ProductCategoryPnlPayload[] = [
      {
        ...baseline,
        scenario_rate_pct: "1.50",
        rows: [
          row({ category_id: "bond_ac", category_name: "AC债券投资", business_net_income: yi(5.4) }),
          row({ category_id: "repo_assets", category_name: "买入返售", business_net_income: yi(-0.3) }),
        ],
        asset_total: row({ category_id: "asset_total", business_net_income: yi(6.4), is_total: true }),
        liability_total: row({
          category_id: "liability_total",
          side: "liability",
          business_net_income: yi(-1.1),
          is_total: true,
        }),
        grand_total: row({ category_id: "grand_total", business_net_income: yi(5.3), is_total: true }),
      },
      {
        ...baseline,
        scenario_rate_pct: "2.00",
        rows: [
          row({ category_id: "bond_ac", category_name: "AC债券投资", business_net_income: yi(4.2) }),
          row({ category_id: "repo_assets", category_name: "买入返售", business_net_income: yi(-0.6) }),
        ],
        asset_total: row({ category_id: "asset_total", business_net_income: yi(5.3), is_total: true }),
        liability_total: row({
          category_id: "liability_total",
          side: "liability",
          business_net_income: yi(-1.4),
          is_total: true,
        }),
        grand_total: row({ category_id: "grand_total", business_net_income: yi(3.9), is_total: true }),
      },
    ];
    const attribution = attributionPayload({
      rows: [
        attributionRow({
          category_id: "bond_ac",
          category_name: "AC债券投资",
          effects: {
            delta_business_net_income: yi(-0.9),
            scale_effect: yi(-0.15),
            rate_effect: yi(0.2),
            ftp_effect: yi(-0.55),
            unexplained_effect: yi(-0.25),
            closure_error: yi(0.01),
          },
        }),
      ],
    });

    const surface = selectProductCategoryScenarioSensitivitySurface({ baseline, scenarios });
    const explanation = selectProductCategoryScenarioExplanation({
      categoryId: surface.pressureSummary.reviewRows[0]?.categoryId,
      baseline,
      scenarios,
      attribution,
    });

    expect(explanation).toEqual(
      expect.objectContaining({
        categoryId: "bond_ac",
        categoryLabel: "AC债券投资",
        sideLabel: "资产端",
        triggerRateLabel: "2.00%",
        scenarioDeltaLabel: "-0.80",
        baselineNetIncomeLabel: "5.00",
        scenarioNetIncomeLabel: "4.20",
        summaryLabel: "AC债券投资在 2.00% 情景较正式基线 -0.80 亿元；正式归因显示主导因素为 FTP因素 -0.55 亿元。",
        bridgeLabel: "口径桥：情景压力 -0.80 亿元；正式归因合计 -0.75 亿元；差异 -0.05 亿元。",
        bridgeConclusionLabel: "情景压力与正式归因差异 0.05 亿元，需分开复核情景 FTP 假设和正式归因期间口径。",
        bridgeTone: "warning",
        reviewActionItems: [
          "先复核情景 FTP 假设：确认 2.00% 情景是否只改变 FTP，不混入正式期间变动。",
          "核对正式归因期间口径：确认正式归因的 current/prior 日期、月度/同比口径与情景基线不同。",
          "重点追踪 FTP因素：复核 FTP 输入、基准利率和资产负债侧映射。",
        ],
        emptyCopy: null,
      }),
    );
    expect(explanation?.driverRows).toEqual([
      expect.objectContaining({ label: "FTP因素", valueLabel: "-0.55", tone: "negative" }),
      expect.objectContaining({ label: "未解释", valueLabel: "-0.25", tone: "negative" }),
      expect.objectContaining({ label: "利率因素", valueLabel: "+0.20", tone: "positive" }),
      expect.objectContaining({ label: "规模因素", valueLabel: "-0.15", tone: "negative" }),
    ]);
  });

  it("builds a governed attribution waterfall from the grand total attribution row", () => {
    const grandTotal = attributionRow({
      category_id: "grand_total",
      category_name: "全表合计",
      side: "all",
      current: {
        report_date: "2026-02-28",
        days: 28,
        scale: "0",
        yield_pct: null,
        cash: "0",
        ftp: "0",
        business_net_income: yi(6.1),
      },
      prior: {
        report_date: "2026-01-31",
        days: 31,
        scale: "0",
        yield_pct: null,
        cash: "0",
        ftp: "0",
        business_net_income: yi(5),
      },
      effects: {
        day_effect: yi(-0.2),
        scale_effect: yi(0.7),
        rate_effect: yi(0.4),
        ftp_effect: yi(0.3),
        direct_effect: yi(0.1),
        unexplained_effect: yi(-0.15),
        closure_error: yi(-0.05),
        explained_effect: yi(1.3),
        delta_business_net_income: yi(1.1),
      },
    });

    const surface = selectProductCategoryAttributionWaterfallSurface(
      attributionPayload({
        totals: {
          asset_total: attributionRow({ category_id: "asset_total" }),
          liability_total: attributionRow({ category_id: "liability_total", side: "liability" }),
          grand_total: grandTotal,
        },
      }),
    );

    expect(surface.title).toBe("全表合计经营差异瀑布");
    expect(surface.deltaLabel).toBe("+1.10");
    expect(surface.rows.map((item) => [item.key, item.label, item.valueLabel, item.cumulativeLabel])).toEqual([
      ["prior", "对比期净营收", "5.00", "5.00"],
      ["day_effect", "天数因素", "-0.20", "4.80"],
      ["scale_effect", "规模因素", "+0.70", "5.50"],
      ["rate_effect", "利率因素", "+0.40", "5.90"],
      ["ftp_effect", "FTP因素", "+0.30", "6.20"],
      ["direct_effect", "直接因素", "+0.10", "6.30"],
      ["unexplained_effect", "未解释", "-0.15", "6.15"],
      ["closure_error", "闭合误差", "-0.05", "6.10"],
      ["current", "本期净营收", "6.10", "6.10"],
    ]);
    expect(surface.emptyCopy).toBeNull();
  });

  it("builds a decision focus list from contribution, deterioration, and unexplained drivers", () => {
    const rows = [
      row({
        category_id: "bond_ac",
        category_name: "AC债券投资",
        business_net_income: yi(5),
      }),
      row({
        category_id: "repo_assets",
        category_name: "买入返售",
        business_net_income: yi(-0.7),
      }),
      row({
        category_id: "derivatives",
        category_name: "衍生工具",
        business_net_income: yi(-0.2),
      }),
    ];
    const attribution = attributionPayload({
      rows: [
        attributionRow({
          category_id: "bond_ac",
          category_name: "AC债券投资",
          effects: {
            delta_business_net_income: yi(0.4),
            unexplained_effect: yi(0.05),
          },
        }),
        attributionRow({
          category_id: "repo_assets",
          category_name: "买入返售",
          effects: {
            delta_business_net_income: yi(-0.8),
            unexplained_effect: yi(-0.15),
          },
        }),
        attributionRow({
          category_id: "derivatives",
          category_name: "衍生工具",
          effects: {
            delta_business_net_income: yi(-0.1),
            unexplained_effect: yi(-0.45),
          },
        }),
      ],
    });

    const surface = selectProductCategoryDecisionFocusSurface({
      rows,
      grandTotal: row({ category_id: "grand_total", business_net_income: yi(4.1), is_total: true }),
      attribution,
    });

    expect(surface.items).toEqual([
      expect.objectContaining({
        key: "top_contributor",
        categoryLabel: "AC债券投资",
        reasonLabel: "本期贡献最高",
        primaryLabel: "5.00",
        tone: "positive",
      }),
      expect.objectContaining({
        key: "top_pressure",
        categoryLabel: "买入返售",
        reasonLabel: "本期压力最大",
        primaryLabel: "-0.70",
        tone: "negative",
      }),
      expect.objectContaining({
        key: "largest_deterioration",
        categoryLabel: "买入返售",
        reasonLabel: "环比恶化最大",
        primaryLabel: "-0.80",
        tone: "negative",
      }),
      expect.objectContaining({
        key: "largest_unexplained",
        categoryLabel: "衍生工具",
        reasonLabel: "未解释金额最大",
        primaryLabel: "-0.45",
        secondaryLabel: "需要复核归因残差",
        tone: "negative",
      }),
    ]);
    expect(surface.emptyCopy).toBeNull();
  });

  it("builds a product root-cause drilldown from formal attribution rows", () => {
    const rows = [
      row({
        category_id: "bond_ac",
        category_name: "AC债券投资",
        cnx_scale: yi(130),
        weighted_yield: "2.80",
        business_net_income: yi(1.2),
      }),
      row({
        category_id: "repo_assets",
        category_name: "买入返售",
        cnx_scale: yi(80),
        weighted_yield: "1.70",
        business_net_income: yi(-0.35),
      }),
    ];
    const attribution = attributionPayload({
      rows: [
        attributionRow({
          category_id: "bond_ac",
          category_name: "AC债券投资",
          current: {
            report_date: "2026-02-28",
            days: 28,
            scale: yi(130),
            yield_pct: "2.80",
            cash: yi(0.75),
            ftp: yi(0.12),
            business_net_income: yi(1.2),
          },
          prior: {
            report_date: "2026-01-31",
            days: 31,
            scale: yi(118),
            yield_pct: "2.50",
            cash: yi(0.55),
            ftp: yi(0.1),
            business_net_income: yi(0.72),
          },
          effects: {
            delta_business_net_income: yi(0.48),
            scale_effect: yi(0.16),
            rate_effect: yi(0.24),
            ftp_effect: yi(-0.08),
            direct_effect: yi(0.03),
            unexplained_effect: yi(0.07),
            closure_error: yi(0.01),
          },
        }),
        attributionRow({
          category_id: "repo_assets",
          category_name: "买入返售",
          effects: {
            delta_business_net_income: yi(-0.2),
            scale_effect: yi(-0.04),
            rate_effect: yi(-0.05),
            ftp_effect: yi(-0.03),
            direct_effect: yi(0),
            unexplained_effect: yi(-0.08),
            closure_error: yi(0),
          },
        }),
      ],
    });

    const surface = selectProductCategoryRootCauseSurface({ rows, attribution });

    expect(surface.emptyCopy).toBeNull();
    expect(surface.headline).toMatchObject({
      categoryId: "bond_ac",
      categoryLabel: "AC债券投资",
      deltaLabel: "+0.48",
      driverLabel: "利率因素",
      driverValueLabel: "+0.24",
      currentNetIncomeLabel: "1.20",
      priorNetIncomeLabel: "0.72",
      scaleLabel: "130.00",
      yieldLabel: "2.80%",
    });
    expect(surface.driverRows.map((item) => [item.key, item.label, item.valueLabel, item.shareLabel])).toEqual([
      ["rate_effect", "利率因素", "+0.24", "50.0%"],
      ["scale_effect", "规模因素", "+0.16", "33.3%"],
      ["ftp_effect", "FTP因素", "-0.08", "-16.7%"],
      ["unexplained_effect", "未解释", "+0.07", "14.6%"],
      ["direct_effect", "直接因素", "+0.03", "6.3%"],
      ["closure_error", "闭合误差", "+0.01", "2.1%"],
    ]);
    expect(surface.evidenceItems).toEqual([
      "本期净营收 1.20 亿元",
      "对比期净营收 0.72 亿元",
      "当前规模 130.00 亿元",
      "当前收益率 2.80%",
      "闭合误差 +0.01 亿元",
    ]);
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

  it("freezes the Unit 9 fixture-driven row/field matrix for asset, liability, and grand_total authority", () => {
    const baselineRows = GOLDEN_SAMPLE_A_RESPONSE.result.rows.map((sampleRow) => {
      if (sampleRow.category_id === "repo_liabilities") {
        return {
          ...sampleRow,
          business_net_income: "-123456789",
          cny_net: "-223456789",
          cny_ftp: "-323456789",
          weighted_yield: "1.41",
        };
      }
      if (sampleRow.category_id === "repo_assets") {
        return {
          ...sampleRow,
          business_net_income: "-123456789",
          cny_net: "-223456789",
          cny_ftp: "-323456789",
          weighted_yield: "1.47",
        };
      }
      return sampleRow;
    });
    const detailRows = selectProductCategoryDetailRows(baselineRows, undefined);
    const grandTotal = selectDisplayedProductCategoryGrandTotal(
      undefined,
      GOLDEN_SAMPLE_A_RESPONSE.result.grand_total,
    );

    const matrix = detailRows
      .filter((rowItem) =>
        rowItem.category_id === "repo_assets" || rowItem.category_id === "repo_liabilities",
      )
      .map((rowItem) => ({
        categoryId: rowItem.category_id,
        side: rowItem.side,
        businessNetIncomeDisplay: formatProductCategoryRowDisplayValue(
          rowItem,
          rowItem.business_net_income,
        ),
        cnyNetDisplay: formatProductCategoryRowDisplayValue(rowItem, rowItem.cny_net),
        cnyFtpDisplay: formatProductCategoryRowDisplayValue(rowItem, rowItem.cny_ftp),
        weightedYieldDisplay: formatProductCategoryYieldValue(rowItem.weighted_yield),
      }));

    expect(matrix).toEqual([
      {
        categoryId: "repo_assets",
        side: "asset",
        businessNetIncomeDisplay: "-1.23",
        cnyNetDisplay: "-2.23",
        cnyFtpDisplay: "-3.23",
        weightedYieldDisplay: "1.47",
      },
      {
        categoryId: "repo_liabilities",
        side: "liability",
        businessNetIncomeDisplay: "1.23",
        cnyNetDisplay: "2.23",
        cnyFtpDisplay: "3.23",
        weightedYieldDisplay: "1.41",
      },
    ]);
    expect(detailRows.some((rowItem) => rowItem.category_id === "grand_total")).toBe(false);
    expect(grandTotal).toBe(GOLDEN_SAMPLE_A_RESPONSE.result.grand_total);
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

  it("exposes the no-standalone-as_of_date decision without inventing a replacement date", () => {
    expect(PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY).toContain("归属日期");
    expect(PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY).toContain("不提供独立 as_of_date");
    expect(PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY).toContain("报告日期");
    expect(PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY).toContain("生成时间");
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
