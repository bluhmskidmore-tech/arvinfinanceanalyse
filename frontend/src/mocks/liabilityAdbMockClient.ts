/** Demo-only implementation kept outside the real API clients. */
import type { AdbInsightsWindow, ResultMeta } from "../api/contracts";
import type { LiabilityAdbClientMethods } from "../api/liabilityAdbClient";

import { formatRawAsNumeric } from "../utils/format";
type Delay = () => Promise<void>;

type LiabilityAdbMockBundle = Pick<
  typeof import("./mockApiEnvelope"),
  "buildMockApiEnvelope"
>;

type EnsureLiabilityAdbMockBundle = () => Promise<LiabilityAdbMockBundle>;

function buildLiabilityAnalyticalMockMeta(resultKind: string): ResultMeta {
  return {
    trace_id: `tr_${resultKind}_mock`,
    basis: "analytical",
    result_kind: resultKind,
    formal_use_allowed: false,
    source_version: "sv_liability_mock",
    vendor_version: "vv_none",
    rule_version: "rv_liability_mock",
    cache_version: "cv_liability_mock",
    quality_flag: "warning",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: new Date().toISOString(),
  };
}

export function createDemoLiabilityAdbClient(
  delay: Delay,
  ensureMockClientBundle: EnsureLiabilityAdbMockBundle,
): LiabilityAdbClientMethods {
  return {
    async getLiabilityRiskBuckets(reportDate?: string | null) {
      await delay();
      return {
        result_meta: buildLiabilityAnalyticalMockMeta("liability_analytics.risk_buckets"),
        report_date: reportDate?.trim() || "",
        liabilities_structure: [],
        liabilities_term_buckets: [],
        interbank_liabilities_structure: [],
        interbank_liabilities_term_buckets: [],
        issued_liabilities_structure: [],
        issued_liabilities_term_buckets: [],
      };
    },
    async getLiabilityYieldMetrics(reportDate?: string | null) {
      await delay();
      return {
        result_meta: buildLiabilityAnalyticalMockMeta("liability_analytics.yield_metrics"),
        report_date: reportDate?.trim() || "",
        kpi: {
          asset_yield: null,
          liability_cost: null,
          market_liability_cost: null,
          nim: null,
        },
        history: [],
        scatter: [],
      };
    },
    async getYieldByPeriod(options: { year: number; periodType?: "monthly" | "quarterly" | "yearly" }) {
      await delay();
      const y = options.year;
      const pt = options.periodType ?? "monthly";
      return {
        year: y,
        period_type: pt,
        periods: [
          {
            period: `${y}-12`,
            period_type: pt,
            start_date: `${y}-12-01`,
            end_date: `${y}-12-31`,
            num_days: 31,
            total_avg_balance: 1_000_000_000,
            total_pnl: 1_300_000,
            overall_yield: 0.13,
            overall_annualized_yield: 1.53,
            weighted_portfolio_yield: 0.13,
            weighted_portfolio_annualized_yield: 1.53,
            items: [
              {
                business_type_primary: "政策性金融债",
                total_pnl: 1_300_000,
                scale_amount: 1_000_000_000,
                yield_pct: 0.13,
              },
            ],
          },
        ],
      };
    },
    async getLiabilityCounterparty(options: { reportDate?: string | null; topN?: number }) {
      await delay();
      return {
        result_meta: buildLiabilityAnalyticalMockMeta("liability_analytics.counterparty"),
        report_date: options.reportDate?.trim() || "",
        total_value: formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: false }),
        top10_share: null,
        hhi: null,
        population_count: 0,
        is_truncated: false,
        top_10: [],
        by_type: [],
      };
    },
    async getLiabilityKnowledgeBrief() {
      await delay();
      return {
        result_meta: {
          trace_id: "tr_liability_knowledge_mock",
          basis: "analytical",
          result_kind: "liability.page_knowledge",
          formal_use_allowed: false,
          source_version: "sv_liability_knowledge_mock",
          vendor_version: "vv_none",
          rule_version: "rv_liability_knowledge_v1",
          cache_version: "cv_liability_knowledge_v1",
          quality_flag: "warning",
          vendor_status: "ok",
          fallback_mode: "none",
          scenario_flag: false,
          generated_at: new Date().toISOString(),
        },
        result: {
          page_id: "liability-analytics",
          available: false,
          vault_path: null,
          status_note: "mock-no-obsidian",
          notes: [],
        },
      };
    },
    async getCockpitWarnings(reportDate?: string | null) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "liability.cockpit_warnings",
        {
          report_date: reportDate?.trim() || "",
          watch_items: [],
          alert_events: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getContributionSplit(reportDate?: string | null) {
      await delay();
      return (await ensureMockClientBundle()).buildMockApiEnvelope(
        "liability.contribution_split",
        {
          report_date: reportDate?.trim() || "",
          contributions: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async getLiabilitiesMonthly(year: number) {
      await delay();
      return {
        result_meta: buildLiabilityAnalyticalMockMeta("liability_analytics.monthly"),
        year,
        months: [],
        ytd_avg_total_liabilities: null,
        ytd_avg_liability_cost: null,
      };
    },
    async getLiabilitiesMonthlySummary(year: number) {
      await delay();
      return {
        result_meta: buildLiabilityAnalyticalMockMeta("liability_analytics.monthly_summary"),
        year,
        months: [],
        ytd_avg_total_liabilities: null,
        ytd_avg_liability_cost: null,
      };
    },
    async getLiabilitiesMonthlyDetail(month: string) {
      await delay();
      return {
        result_meta: buildLiabilityAnalyticalMockMeta("liability_analytics.monthly_detail"),
        year: Number.parseInt(month.slice(0, 4), 10),
        selected_month: month,
        detail: null,
      };
    },
    async getLiabilityAdbMonthly(year: number) {
      await delay();
      return {
        result_meta: buildLiabilityAnalyticalMockMeta("adb.monthly"),
        year,
        months: [],
        ytd_avg_assets: 0,
        ytd_avg_liabilities: 0,
        ytd_asset_yield: null,
        ytd_liability_cost: null,
        ytd_nim: null,
        unit: "percent",
      };
    },
    async getAdb(_params: { startDate: string; endDate: string }) {
      await delay();
      return {
        summary: {
          total_avg_assets: 0,
          total_avg_liabilities: 0,
          end_spot_assets: 0,
          end_spot_liabilities: 0,
        },
        trend: [],
        breakdown: [],
      };
    },
    async getAdbComparison(_startDate: string, _endDate: string, _options?: { topN?: number }) {
      await delay();
      return {
        report_date: "",
        start_date: "",
        end_date: "",
        calendar_days_inclusive: 0,
        adb_denominator_basis: "snapshot_calendar" as const,
        num_days: 0,
        coverage_days: 0,
        simulated: false,
        total_spot_assets: 0,
        total_avg_assets: 0,
        total_spot_liabilities: 0,
        total_avg_liabilities: 0,
        total_avg_interbank_assets: 0,
        total_avg_interbank_liabilities: 0,
        asset_yield: null,
        liability_cost: null,
        net_interest_margin: null,
        assets_breakdown: [],
        liabilities_breakdown: [],
      };
    },
    async getAdbMonthly(year: number) {
      await delay();
      return {
        year,
        months: [],
        ytd_avg_assets: 0,
        ytd_avg_liabilities: 0,
        ytd_asset_yield: null,
        ytd_liability_cost: null,
        ytd_nim: null,
        unit: "percent",
      };
    },
    async getAdbCoverage(_startDate: string, _endDate: string) {
      await delay();
      return {
        start_date: _startDate,
        end_date: _endDate,
        calendar_days: 0,
        snapshot_tables: {},
        formal_tables: {},
        snapshot_date_count: 0,
        formal_date_count: 0,
        missing_dates: [],
        missing_count: 0,
        coverage_pct: 0,
      };
    },
    async getAdbInsights(startDate: string, endDate: string) {
      await delay();
      // 演示数据集与 getAdbComparison 一样没有余额行，这里返回后端在「本期无有效余额」
      // 分支下的同形响应：三个窗口全部 no_data、分析块全 null，页面显式披露不可用而不是渲染 0。
      const unavailableWindow = (start: string, end: string): AdbInsightsWindow => ({
        start_date: start,
        end_date: end,
        calendar_days_inclusive: 0,
        coverage_days: 0,
        available: false,
        reason: "no_data",
      });
      return {
        result_meta: buildLiabilityAnalyticalMockMeta("adb.insights"),
        start_date: startDate,
        end_date: endDate,
        calendar_days_inclusive: 0,
        insufficient_window: false,
        windows: {
          current: unavailableWindow(startDate, endDate),
          qoq: unavailableWindow("", ""),
          yoy: unavailableWindow("", ""),
        },
        scale_attribution: { qoq: null, yoy: null },
        nim_attribution: null,
        nim_attribution_unavailable_reason: "current_unavailable",
        volatility: null,
        concentration: null,
        insights: [],
      };
    },
  };
}
