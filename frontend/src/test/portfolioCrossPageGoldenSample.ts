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
      items: [],
    },
    asset_rating: {
      report_date: PORTFOLIO_CROSS_PAGE_REPORT_DATE,
      group_by: "rating",
      total_market_value: marketValue,
      items: [],
    },
    maturity: {
      report_date: PORTFOLIO_CROSS_PAGE_REPORT_DATE,
      total_market_value: marketValue,
      items: [],
    },
    industry: {
      report_date: PORTFOLIO_CROSS_PAGE_REPORT_DATE,
      items: [],
    },
    yield_distribution: {
      report_date: PORTFOLIO_CROSS_PAGE_REPORT_DATE,
      weighted_ytm: ytm,
      items: [],
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
      ],
    },
    spread: {
      report_date: PORTFOLIO_CROSS_PAGE_REPORT_DATE,
      items: [],
    },
    business_type: {
      report_date: PORTFOLIO_CROSS_PAGE_REPORT_DATE,
      items: [],
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
    rows: [],
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
