import { describe, expect, it } from "vitest";

import type { ProductCategoryPnlRow, ResultMeta } from "../../../api/contracts";
import { designTokens } from "../../../theme/designSystem";

import {
  PRODUCT_CATEGORY_AS_OF_DATE_GAP_COPY,
  PRODUCT_CATEGORY_FTP_SCENARIO_OPTIONS,
  PRODUCT_CATEGORY_VALUE_TONE_COLORS,
  PRODUCT_CATEGORY_GOVERNED_DETAIL_VIEWS,
  PRODUCT_CATEGORY_MAIN_PAGE_VIEWS,
  availableViewsSupportMainPageSelector,
  buildProductCategoryDerivedAnalysisPlan,
  buildProductCategoryTrendSnapshot,
  collectProductCategoryGovernanceNotices,
  defaultProductCategoryScenarioRateForReportDate,
  formatProductCategoryDualMetaDistinctLine,
  formatProductCategoryReportMonthLabel,
  formatProductCategoryRowDisplayValue,
  formatProductCategoryValue,
  formatProductCategoryYieldValue,
  mainPageViewsAreGovernedDetailSubset,
  selectDisplayedProductCategoryGrandTotal,
  selectProductCategoryDetailRows,
  selectProductCategoryTrendReportDates,
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
    expect(formatProductCategoryReportMonthLabel("2026-02-28")).toBe("2026年02月");
    expect(formatProductCategoryReportMonthLabel("2025-12-31")).toBe("2025年12月");
    expect(formatProductCategoryReportMonthLabel("not-a-date")).toBe("not-a-date");
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

  it("builds a data-derived analysis plan from totals and product rows", () => {
    const interestCurrent = row({
      category_id: "interest_earning_assets",
      category_name: "生息资产",
      cnx_scale: "289850000000",
      business_net_income: "145000000",
      weighted_yield: "2.40",
    });
    const interestPrevious = row({
      category_id: "interest_earning_assets",
      category_name: "生息资产",
      report_date: "2026-01-31",
      cnx_scale: "280000000000",
      business_net_income: "120000000",
      weighted_yield: "2.35",
    });
    const interbankCurrent = row({
      category_id: "interbank_lending_assets",
      category_name: "拆放同业",
      cnx_scale: "17160000000",
      cny_scale: "15691000000",
      foreign_scale: "1469000000",
      business_net_income: "10000000",
      weighted_yield: "2.50",
    });
    const interbankPrevious = row({
      category_id: "interbank_lending_assets",
      category_name: "拆放同业",
      report_date: "2026-01-31",
      cnx_scale: "16000000000",
      cny_scale: "15000000000",
      foreign_scale: "1000000000",
      business_net_income: "8000000",
      weighted_yield: "2.45",
    });
    const tplCurrent = row({
      category_id: "bond_tpl",
      category_name: "TPL",
      cnx_scale: "86498000000",
      business_net_income: "37000000",
      weighted_yield: "2.31",
    });
    const tplPrevious = row({
      category_id: "bond_tpl",
      category_name: "TPL",
      report_date: "2026-01-31",
      cnx_scale: "82000000000",
      business_net_income: "30000000",
      weighted_yield: "2.20",
    });
    const assetCurrent = row({
      category_id: "asset_total",
      business_net_income: "270000000",
      weighted_yield: "2.68",
      is_total: true,
    });
    const assetPrevious = row({
      category_id: "asset_total",
      report_date: "2026-01-31",
      business_net_income: "250000000",
      weighted_yield: "2.55",
      is_total: true,
    });
    const liabilityCurrent = row({
      category_id: "liability_total",
      side: "liability",
      business_net_income: "16000000",
      weighted_yield: "1.63",
      is_total: true,
    });
    const liabilityPrevious = row({
      category_id: "liability_total",
      side: "liability",
      report_date: "2026-01-31",
      business_net_income: "15000000",
      weighted_yield: "1.60",
      is_total: true,
    });
    const plan = buildProductCategoryDerivedAnalysisPlan({
      rows: [
        interbankCurrent,
        row({
          category_id: "bond_investment",
          category_name: "债券投资",
          cnx_scale: "336178000000",
          business_net_income: "227000000",
          weighted_yield: "2.63",
        }),
        tplCurrent,
        row({
          category_id: "repo_assets",
          category_name: "买入返售",
          cnx_scale: "23011000000",
          business_net_income: "-5000000",
        }),
        interestCurrent,
        row({
          category_id: "asset_total",
          category_name: "资产端合计",
          business_net_income: "270000000",
          is_total: true,
        }),
      ],
      assetTotal: assetCurrent,
      liabilityTotal: liabilityCurrent,
      grandTotal: row({ category_id: "grand_total", business_net_income: "286000000", is_total: true }),
      currentRate: "1.60",
      baselineRate: "1.75",
      contributionViews: {
        monthly: {
          assetTotal: assetCurrent,
          liabilityTotal: liabilityCurrent,
          grandTotal: row({ category_id: "grand_total", business_net_income: "286000000", is_total: true }),
        },
        ytd: {
          assetTotal: row({ category_id: "asset_total", business_net_income: "810000000", is_total: true }),
          liabilityTotal: row({
            category_id: "liability_total",
            side: "liability",
            business_net_income: "48000000",
            is_total: true,
          }),
          grandTotal: row({ category_id: "grand_total", business_net_income: "858000000", is_total: true }),
        },
      },
      trendSnapshots: [
        {
          reportDate: "2026-02-28",
          rows: [interbankCurrent, tplCurrent, interestCurrent],
          assetTotal: assetCurrent,
          liabilityTotal: liabilityCurrent,
        },
        {
          reportDate: "2026-01-31",
          rows: [interbankPrevious, tplPrevious, interestPrevious],
          assetTotal: assetPrevious,
          liabilityTotal: liabilityPrevious,
        },
      ],
    });
    const planById = new Map(plan.map((item) => [item.id, item]));

    expect(plan.map((item) => item.id)).toEqual([
      "contribution",
      "interestEarningTrend",
      "spreadLevel",
      "interbankLendingTrend",
      "tplAssetTrend",
      "driver",
      "ftp",
      "review",
    ]);
    expect(planById.get("contribution")).toMatchObject({
      title: "经营贡献拆解",
      metric: "月度损益 2.86 亿元 / 累计损益 8.58 亿元",
      tone: "positive",
    });
    expect(planById.get("contribution")?.detail).toContain("累计：资产端 8.10 亿元");
    expect(planById.get("interestEarningTrend")?.detail).toContain("+98.50 亿元");
    expect(planById.get("spreadLevel")?.metric).toBe("资产负债利差 105bp");
    expect(planById.get("spreadLevel")?.detail).toContain("+10bp");
    expect(planById.get("interbankLendingTrend")?.detail).toContain("人民币日均 156.91 亿元");
    expect(planById.get("tplAssetTrend")?.metric).toBe("日均 864.98 亿元 / 收益率 2.31%");
    expect(planById.get("driver")?.metric).toBe("债券投资 2.27 亿元");
    expect(planById.get("ftp")?.metric).toBe("当前 1.6% / 基准 1.75%");
    expect(planById.get("review")?.detail).toContain("买入返售");
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
