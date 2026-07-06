import type {
  ApiEnvelope,
  BalanceAnalysisBasisBreakdownPayload,
  BalanceAnalysisOverviewPayload,
  BondDashboardHomeSummaryPayload,
  Numeric,
  PnlAttributionAnalysisSummary,
  ResultMeta,
} from "../api/contracts";
import { formatRawAsNumeric } from "../utils/format";

export const PORTFOLIO_CROSS_PAGE_REPORT_DATE = "2026-05-31";

export const PORTFOLIO_CROSS_PAGE_EXPECTED = {
  bondMarketValueYi: "1,234.57",
  bondDuration: "6.79",
  bondDv01Wan: "2,345.68",
  bondCount: "908",
  balanceAssetYi: "987.65",
  balanceLiabilityYi: "123.46",
  pnlDriverRatio: "0.43",
  portfolioName: "cross-page-source-check",
  assetTypeName: "policy-bank",
  ratingName: "AAA",
  maturityName: "1Y-3Y",
  industryName: "financial",
  yieldBucketName: "2.5%-3.0%",
  spreadName: "credit-corp",
  businessTypeName: "credit-corp",
  pnlFinding: "distinct-pnl-finding",
} as const;

export function portfolioCrossPageNumeric(
  raw: number,
  unit: Numeric["unit"],
  signAware = false,
): Numeric {
  return formatRawAsNumeric({ raw, unit, sign_aware: signAware });
}

export function portfolioCrossPageMeta(
  resultKind: string,
  overrides: Partial<ResultMeta> = {},
): ResultMeta {
  return {
    trace_id: `${resultKind}_trace`,
    basis: "formal",
    result_kind: resultKind,
    formal_use_allowed: true,
    source_version: "sv_portfolio_cross_page",
    vendor_version: "vv_none",
    rule_version: "rv_portfolio_cross_page",
    cache_version: "cv_portfolio_cross_page",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    requested_report_date: PORTFOLIO_CROSS_PAGE_REPORT_DATE,
    resolved_report_date: PORTFOLIO_CROSS_PAGE_REPORT_DATE,
    as_of_date: PORTFOLIO_CROSS_PAGE_REPORT_DATE,
    fallback_date: null,
    generated_at: "2026-06-05T00:00:00Z",
    ...overrides,
  };
}

export function portfolioCrossPageEnvelope<T>(
  resultKind: string,
  result: T,
  overrides: Partial<ResultMeta> = {},
): ApiEnvelope<T> {
  return {
    result_meta: portfolioCrossPageMeta(resultKind, overrides),
    result,
  };
}

export function portfolioCrossPageBondHomeSummary(): BondDashboardHomeSummaryPayload {
  const marketValue = portfolioCrossPageNumeric(123_456_789_012.34, "yuan");
  const duration = portfolioCrossPageNumeric(6.789, "ratio");
  const dv01 = portfolioCrossPageNumeric(23_456_789.01, "dv01");
  const ytm = portfolioCrossPageNumeric(0.02561294, "pct", true);
  const mv = (raw: number) => portfolioCrossPageNumeric(raw, "yuan");
  const pct = (raw: number) => portfolioCrossPageNumeric(raw, "pct");

  return {
    report_date: PORTFOLIO_CROSS_PAGE_REPORT_DATE,
    headline: {
      report_date: PORTFOLIO_CROSS_PAGE_REPORT_DATE,
      prev_report_date: "2026-04-30",
      kpis: {
        total_market_value: marketValue,
        unrealized_pnl: portfolioCrossPageNumeric(8_202_912_484.65, "yuan", true),
        weighted_ytm: ytm,
        weighted_duration: duration,
        weighted_coupon: portfolioCrossPageNumeric(0.01871629, "pct", true),
        credit_spread_median: portfolioCrossPageNumeric(0.023682, "pct", true),
        total_dv01: dv01,
        bond_count: 908,
      },
      prev_kpis: null,
    },
    risk: {
      report_date: PORTFOLIO_CROSS_PAGE_REPORT_DATE,
      total_market_value: marketValue,
      total_dv01: dv01,
      weighted_duration: duration,
      credit_ratio: portfolioCrossPageNumeric(0.1234, "ratio"),
      weighted_convexity: portfolioCrossPageNumeric(28.73609304, "ratio"),
      total_spread_dv01: portfolioCrossPageNumeric(25_862_175.57270329, "dv01"),
      reinvestment_ratio_1y: portfolioCrossPageNumeric(0.3448817, "ratio"),
    },
    asset_type: {
      report_date: PORTFOLIO_CROSS_PAGE_REPORT_DATE,
      group_by: "bond_type",
      total_market_value: marketValue,
      items: [
        {
          category: PORTFOLIO_CROSS_PAGE_EXPECTED.assetTypeName,
          total_market_value: mv(41_600_000_000),
          bond_count: 302,
          percentage: pct(0.33696),
        },
        {
          category: "local-gov",
          total_market_value: mv(29_400_000_000),
          bond_count: 184,
          percentage: pct(0.23814),
        },
        {
          category: "ncd",
          total_market_value: mv(21_200_000_000),
          bond_count: 176,
          percentage: pct(0.17172),
        },
        {
          category: "credit-corp",
          total_market_value: mv(18_800_000_000),
          bond_count: 148,
          percentage: pct(0.15228),
        },
        {
          category: "other",
          total_market_value: mv(12_456_789_012.34),
          bond_count: 98,
          percentage: pct(0.1009),
        },
      ],
    },
    asset_rating: {
      report_date: PORTFOLIO_CROSS_PAGE_REPORT_DATE,
      group_by: "rating",
      total_market_value: marketValue,
      items: [
        {
          category: PORTFOLIO_CROSS_PAGE_EXPECTED.ratingName,
          total_market_value: mv(69_200_000_000),
          bond_count: 468,
          percentage: pct(0.56052),
        },
        {
          category: "AA+",
          total_market_value: mv(24_100_000_000),
          bond_count: 151,
          percentage: pct(0.19521),
        },
        {
          category: "AA",
          total_market_value: mv(13_700_000_000),
          bond_count: 96,
          percentage: pct(0.11097),
        },
        {
          category: "A+",
          total_market_value: mv(8_600_000_000),
          bond_count: 74,
          percentage: pct(0.06966),
        },
        {
          category: "unrated",
          total_market_value: mv(7_856_789_012.34),
          bond_count: 119,
          percentage: pct(0.06364),
        },
      ],
    },
    maturity: {
      report_date: PORTFOLIO_CROSS_PAGE_REPORT_DATE,
      total_market_value: marketValue,
      items: [
        {
          maturity_bucket: "0-1Y",
          total_market_value: mv(18_500_000_000),
          bond_count: 142,
          percentage: pct(0.14985),
        },
        {
          maturity_bucket: PORTFOLIO_CROSS_PAGE_EXPECTED.maturityName,
          total_market_value: mv(44_200_000_000),
          bond_count: 326,
          percentage: pct(0.35802),
        },
        {
          maturity_bucket: "3Y-5Y",
          total_market_value: mv(35_600_000_000),
          bond_count: 208,
          percentage: pct(0.28836),
        },
        {
          maturity_bucket: "5Y-7Y",
          total_market_value: mv(14_100_000_000),
          bond_count: 92,
          percentage: pct(0.11421),
        },
        {
          maturity_bucket: "7Y+",
          total_market_value: mv(11_056_789_012.34),
          bond_count: 140,
          percentage: pct(0.08956),
        },
      ],
    },
    industry: {
      report_date: PORTFOLIO_CROSS_PAGE_REPORT_DATE,
      items: [
        {
          industry_name: PORTFOLIO_CROSS_PAGE_EXPECTED.industryName,
          total_market_value: mv(48_000_000_000),
          bond_count: 292,
          percentage: pct(0.3888),
        },
        {
          industry_name: "urban-investment",
          total_market_value: mv(25_500_000_000),
          bond_count: 166,
          percentage: pct(0.20655),
        },
        {
          industry_name: "transport",
          total_market_value: mv(17_200_000_000),
          bond_count: 118,
          percentage: pct(0.13932),
        },
        {
          industry_name: "utility",
          total_market_value: mv(14_400_000_000),
          bond_count: 98,
          percentage: pct(0.11664),
        },
        {
          industry_name: "manufacturing",
          total_market_value: mv(9_800_000_000),
          bond_count: 82,
          percentage: pct(0.07938),
        },
        {
          industry_name: "other",
          total_market_value: mv(8_556_789_012.34),
          bond_count: 152,
          percentage: pct(0.06931),
        },
      ],
    },
    yield_distribution: {
      report_date: PORTFOLIO_CROSS_PAGE_REPORT_DATE,
      weighted_ytm: ytm,
      items: [
        { yield_bucket: "<2.0%", total_market_value: mv(12_000_000_000), bond_count: 92 },
        { yield_bucket: "2.0%-2.5%", total_market_value: mv(40_000_000_000), bond_count: 268 },
        {
          yield_bucket: PORTFOLIO_CROSS_PAGE_EXPECTED.yieldBucketName,
          total_market_value: mv(43_000_000_000),
          bond_count: 312,
        },
        { yield_bucket: "3.0%-3.5%", total_market_value: mv(18_900_000_000), bond_count: 139 },
        { yield_bucket: ">3.5%", total_market_value: mv(9_556_789_012.34), bond_count: 97 },
      ],
    },
    portfolio_comparison: {
      report_date: PORTFOLIO_CROSS_PAGE_REPORT_DATE,
      items: [
        {
          portfolio_name: PORTFOLIO_CROSS_PAGE_EXPECTED.portfolioName,
          total_market_value: marketValue,
          weighted_ytm: ytm,
          weighted_duration: duration,
          total_dv01: dv01,
          bond_count: 908,
        },
        {
          portfolio_name: "banking-book",
          total_market_value: mv(58_600_000_000),
          weighted_ytm: portfolioCrossPageNumeric(0.0248, "pct", true),
          weighted_duration: portfolioCrossPageNumeric(5.62, "ratio"),
          total_dv01: portfolioCrossPageNumeric(11_800_000, "dv01"),
          bond_count: 352,
        },
        {
          portfolio_name: "trading-book",
          total_market_value: mv(36_200_000_000),
          weighted_ytm: portfolioCrossPageNumeric(0.0271, "pct", true),
          weighted_duration: portfolioCrossPageNumeric(3.24, "ratio"),
          total_dv01: portfolioCrossPageNumeric(7_200_000, "dv01"),
          bond_count: 268,
        },
        {
          portfolio_name: "oci-book",
          total_market_value: mv(28_656_789_012.34),
          weighted_ytm: portfolioCrossPageNumeric(0.0264, "pct", true),
          weighted_duration: portfolioCrossPageNumeric(4.18, "ratio"),
          total_dv01: portfolioCrossPageNumeric(4_456_789.01, "dv01"),
          bond_count: 288,
        },
      ],
    },
    spread: {
      report_date: PORTFOLIO_CROSS_PAGE_REPORT_DATE,
      items: [
        {
          bond_type: "policy-bank",
          median_yield: portfolioCrossPageNumeric(0.0231, "pct", true),
          bond_count: 302,
          total_market_value: mv(41_600_000_000),
        },
        {
          bond_type: "local-gov",
          median_yield: portfolioCrossPageNumeric(0.0244, "pct", true),
          bond_count: 184,
          total_market_value: mv(29_400_000_000),
        },
        {
          bond_type: PORTFOLIO_CROSS_PAGE_EXPECTED.spreadName,
          median_yield: portfolioCrossPageNumeric(0.0312, "pct", true),
          bond_count: 148,
          total_market_value: mv(18_800_000_000),
        },
        {
          bond_type: "ncd",
          median_yield: portfolioCrossPageNumeric(0.0268, "pct", true),
          bond_count: 176,
          total_market_value: mv(21_200_000_000),
        },
      ],
    },
    business_type: {
      report_date: PORTFOLIO_CROSS_PAGE_REPORT_DATE,
      items: [
        {
          name: "policy-bank",
          market_value: "41600000000.00",
          weighted_avg_ytm_pct: "2.31",
          weighted_avg_duration: "5.62",
          duration_source: "formal",
        },
        {
          name: "local-gov",
          market_value: "29400000000.00",
          weighted_avg_ytm_pct: "2.44",
          weighted_avg_duration: "4.81",
          duration_source: "formal",
        },
        {
          name: PORTFOLIO_CROSS_PAGE_EXPECTED.businessTypeName,
          market_value: "18800000000.00",
          weighted_avg_ytm_pct: "3.12",
          weighted_avg_duration: "3.24",
          duration_source: "formal",
        },
        {
          name: "ncd",
          market_value: "21200000000.00",
          weighted_avg_ytm_pct: "2.68",
          weighted_avg_duration: "0.74",
          duration_source: "formal",
        },
      ],
    },
  };
}

export function portfolioCrossPageBalanceOverview(): BalanceAnalysisOverviewPayload {
  return {
    report_date: PORTFOLIO_CROSS_PAGE_REPORT_DATE,
    position_scope: "all",
    currency_basis: "CNY",
    detail_row_count: 908,
    summary_row_count: 2,
    total_market_value_amount: "111111111111.11",
    total_amortized_cost_amount: "321000000000.00",
    total_accrued_interest_amount: "1280000000.00",
    asset_total_market_value_amount: "98765432109.87",
    liability_total_market_value_amount: "12345678901.23",
    asset_total_amortized_cost_amount: "321000000000.00",
    liability_total_amortized_cost_amount: "0.00",
    asset_total_accrued_interest_amount: "1280000000.00",
    liability_total_accrued_interest_amount: "0.00",
  };
}

export function portfolioCrossPageBalanceBasis(): BalanceAnalysisBasisBreakdownPayload {
  return {
    report_date: PORTFOLIO_CROSS_PAGE_REPORT_DATE,
    position_scope: "all",
    currency_basis: "CNY",
    rows: [
      {
        source_family: "zqtz",
        invest_type_std: "bond-investment",
        accounting_basis: "FVOCI",
        position_scope: "asset",
        currency_basis: "CNY",
        detail_row_count: 528,
        market_value_amount: "58600000000.00",
        amortized_cost_amount: "57100000000.00",
        accrued_interest_amount: "260000000.00",
      },
      {
        source_family: "zqtz",
        invest_type_std: "bond-investment",
        accounting_basis: "FVTPL",
        position_scope: "asset",
        currency_basis: "CNY",
        detail_row_count: 268,
        market_value_amount: "28200000000.00",
        amortized_cost_amount: "27400000000.00",
        accrued_interest_amount: "118000000.00",
      },
      {
        source_family: "tyw",
        invest_type_std: "bond-financing",
        accounting_basis: "amortized-cost",
        position_scope: "liability",
        currency_basis: "CNY",
        detail_row_count: 112,
        market_value_amount: "12345678901.23",
        amortized_cost_amount: "12100000000.00",
        accrued_interest_amount: "42000000.00",
      },
    ],
  };
}

export function portfolioCrossPagePnlSummary(): PnlAttributionAnalysisSummary {
  return {
    report_date: PORTFOLIO_CROSS_PAGE_REPORT_DATE,
    primary_driver: "rate",
    primary_driver_pct: portfolioCrossPageNumeric(0.4321, "ratio"),
    key_findings: [PORTFOLIO_CROSS_PAGE_EXPECTED.pnlFinding],
    tpl_market_aligned: true,
    tpl_market_note: "TPL market move aligned.",
  };
}
