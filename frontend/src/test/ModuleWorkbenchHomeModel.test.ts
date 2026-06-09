import { describe, expect, it } from "vitest";
import type { UseQueryResult } from "@tanstack/react-query";

import type { ApiEnvelope, ResultMeta } from "../api/contracts";
import { buildModuleHomeView } from "../features/workbench/module-home/moduleHomeModel";
import { formatRawAsNumeric } from "../utils/format";

function meta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "module_home_trace",
    basis: "formal",
    result_kind: "module.home.test",
    formal_use_allowed: true,
    source_version: "sv_module_home",
    vendor_version: "vv_module_home",
    rule_version: "rv_module_home",
    cache_version: "cv_module_home",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-06-01T00:00:00Z",
    ...overrides,
  };
}

function envelope<T>(result: T, overrides: Partial<ResultMeta> = {}): ApiEnvelope<T> {
  return {
    result_meta: meta(overrides),
    result,
  };
}

function query<T>(options: {
  data?: T;
  error?: boolean;
  loading?: boolean;
  refetching?: boolean;
}): UseQueryResult<T> {
  const hasData = options.data !== undefined;
  const loading = Boolean(options.loading);
  const refetching = Boolean(options.refetching);
  return {
    data: options.data,
    error: options.error ? new Error("query failed") : null,
    isError: Boolean(options.error),
    isLoading: loading && !hasData,
    isFetching: loading || refetching,
    status: options.error ? "error" : loading && !hasData ? "pending" : "success",
    fetchStatus: loading || refetching ? "fetching" : "idle",
  } as UseQueryResult<T>;
}

type ModuleHomeQueries = Parameters<typeof buildModuleHomeView>[2];

function portfolioGovernanceQueries(options: {
  balanceDate?: string;
  bondDate?: string;
  pnlDate?: string;
  bondMeta?: Partial<ResultMeta>;
  bondMetaMissing?: boolean;
  balanceMeta?: Partial<ResultMeta>;
  riskMeta?: Partial<ResultMeta>;
  pnlMeta?: Partial<ResultMeta>;
  pnlMetaMissing?: boolean;
  pnlError?: boolean;
  pnlLoading?: boolean;
  pnlNoData?: boolean;
  portfolioComparisonError?: boolean;
  riskDates?: string[];
  riskDatesMeta?: Partial<ResultMeta>;
  riskDatesError?: boolean;
  riskDatesLoading?: boolean;
  riskDatesNoData?: boolean;
} = {}): ModuleHomeQueries {
  const balanceDate = options.balanceDate ?? "2026-05-31";
  const bondDate = options.bondDate ?? "2026-05-31";
  const pnlDate = options.pnlDate ?? bondDate;
  return {
    balanceDates: query({ data: envelope({ report_dates: [balanceDate] }) }),
    balanceOverview: query({
      data: envelope(
        {
          report_date: balanceDate,
          position_scope: "all",
          currency_basis: "CNY",
          detail_row_count: 1710,
          summary_row_count: 2,
          total_market_value_amount: "332281921064.45",
          total_amortized_cost_amount: "321000000000.00",
          total_accrued_interest_amount: "1280000000.00",
          asset_total_market_value_amount: "332281921064.45",
          liability_total_market_value_amount: "180644372831.27",
          asset_total_amortized_cost_amount: "321000000000.00",
          liability_total_amortized_cost_amount: "178000000000.00",
          asset_total_accrued_interest_amount: "1280000000.00",
          liability_total_accrued_interest_amount: "644372831.27",
        },
        {
          result_kind: "balance-analysis.overview",
          requested_report_date: balanceDate,
          resolved_report_date: balanceDate,
          as_of_date: balanceDate,
          tables_used: ["fact_formal_zqtz_balance_daily"],
          evidence_rows: 1710,
          ...options.balanceMeta,
        },
      ),
    }),
    bondDates: query({ data: envelope({ report_dates: [bondDate] }) }),
    bondHeadline: query({
      data: options.bondMetaMissing
        ? {
            ...envelope(
              {
                report_date: bondDate,
                prev_report_date: "2026-04-30",
                kpis: {
                  total_market_value: formatRawAsNumeric({ raw: 332_281_921_064.45, unit: "yuan", sign_aware: false }),
                  unrealized_pnl: formatRawAsNumeric({ raw: 8_202_912_484.65, unit: "yuan", sign_aware: true }),
                  weighted_ytm: formatRawAsNumeric({ raw: 0.02561294, unit: "pct", sign_aware: false }),
                  weighted_duration: formatRawAsNumeric({ raw: 3.45, unit: "ratio", sign_aware: false }),
                  weighted_coupon: formatRawAsNumeric({ raw: 0.01871629, unit: "pct", sign_aware: false }),
                  credit_spread_median: formatRawAsNumeric({ raw: 0.023682, unit: "pct", sign_aware: false }),
                  total_dv01: formatRawAsNumeric({ raw: 105_628_442.39590558, unit: "dv01", sign_aware: false }),
                  bond_count: 1710,
                },
                prev_kpis: null,
              },
              {
                result_kind: "bond_dashboard.home_summary",
                requested_report_date: bondDate,
                resolved_report_date: bondDate,
                as_of_date: bondDate,
                tables_used: ["fact_formal_bond_analytics_daily"],
                evidence_rows: 1710,
                ...options.bondMeta,
              },
            ),
            result_meta: undefined as unknown as ResultMeta,
          }
        : envelope(
        {
          report_date: bondDate,
          prev_report_date: "2026-04-30",
          kpis: {
            total_market_value: formatRawAsNumeric({ raw: 332_281_921_064.45, unit: "yuan", sign_aware: false }),
            unrealized_pnl: formatRawAsNumeric({ raw: 8_202_912_484.65, unit: "yuan", sign_aware: true }),
            weighted_ytm: formatRawAsNumeric({ raw: 0.02561294, unit: "pct", sign_aware: false }),
            weighted_duration: formatRawAsNumeric({ raw: 3.45, unit: "ratio", sign_aware: false }),
            weighted_coupon: formatRawAsNumeric({ raw: 0.01871629, unit: "pct", sign_aware: false }),
            credit_spread_median: formatRawAsNumeric({ raw: 0.023682, unit: "pct", sign_aware: false }),
            total_dv01: formatRawAsNumeric({ raw: 105_628_442.39590558, unit: "dv01", sign_aware: false }),
            bond_count: 1710,
          },
          prev_kpis: null,
        },
        {
          result_kind: "bond_dashboard.home_summary",
          requested_report_date: bondDate,
          resolved_report_date: bondDate,
          as_of_date: bondDate,
          tables_used: ["fact_formal_bond_analytics_daily"],
          evidence_rows: 1710,
          ...options.bondMeta,
        },
      ),
    }),
    bondPortfolioComparison: options.portfolioComparisonError
      ? query({ error: true })
      : query({
          data: envelope(
            {
              report_date: bondDate,
              items: [
                {
                  portfolio_name: "FI",
                  total_market_value: formatRawAsNumeric({ raw: 332_281_921_064.45, unit: "yuan", sign_aware: false }),
                  bond_count: 1710,
                  weighted_ytm: formatRawAsNumeric({ raw: 0.02561294, unit: "pct", sign_aware: false }),
                  weighted_duration: formatRawAsNumeric({ raw: 3.45, unit: "ratio", sign_aware: false }),
                  total_dv01: formatRawAsNumeric({ raw: 105_628_442.39590558, unit: "dv01", sign_aware: false }),
                },
              ],
            },
            {
              result_kind: "bond_dashboard.portfolio_comparison",
              requested_report_date: bondDate,
              resolved_report_date: bondDate,
              as_of_date: bondDate,
              tables_used: ["fact_formal_bond_analytics_daily"],
              evidence_rows: 1710,
            },
          ),
        }),
    bondRisk: query({
      data: envelope(
        {
          report_date: bondDate,
          total_market_value: formatRawAsNumeric({ raw: 332_281_921_064.45, unit: "yuan", sign_aware: false }),
          total_dv01: formatRawAsNumeric({ raw: 105_628_442.39590558, unit: "dv01", sign_aware: false }),
          weighted_duration: formatRawAsNumeric({ raw: 3.45, unit: "ratio", sign_aware: false }),
          credit_ratio: formatRawAsNumeric({ raw: 0.18, unit: "ratio", sign_aware: false }),
          weighted_convexity: formatRawAsNumeric({ raw: 28.73609304, unit: "ratio", sign_aware: false }),
          total_spread_dv01: formatRawAsNumeric({ raw: 25_862_175.57270329, unit: "dv01", sign_aware: false }),
          reinvestment_ratio_1y: formatRawAsNumeric({ raw: 0.3448817, unit: "ratio", sign_aware: false }),
        },
        {
          result_kind: "bond_dashboard.risk_indicators",
          requested_report_date: bondDate,
          resolved_report_date: bondDate,
          as_of_date: bondDate,
          tables_used: ["fact_formal_bond_analytics_daily"],
          evidence_rows: 1710,
          ...options.riskMeta,
        },
      ),
    }),
    pnlSummary: options.pnlError
      ? query({ error: true })
      : options.pnlLoading
        ? query({ loading: true })
        : options.pnlNoData
          ? query({})
          : query({
      data: options.pnlMetaMissing
        ? {
            ...envelope(
              {
                report_date: pnlDate,
                primary_driver: "rate",
                primary_driver_pct: formatRawAsNumeric({ raw: 0.58, unit: "ratio", sign_aware: false }),
                key_findings: ["利率为本期主要归因驱动。"],
                tpl_market_aligned: true,
                tpl_market_note: "与 TPL 市场变动方向一致。",
              },
              {
                result_kind: "pnl-attribution.summary",
                requested_report_date: pnlDate,
                resolved_report_date: pnlDate,
                as_of_date: pnlDate,
                tables_used: ["fact_formal_pnl_fi"],
                evidence_rows: 1710,
                ...options.pnlMeta,
              },
            ),
            result_meta: undefined as unknown as ResultMeta,
          }
        : envelope(
        {
          report_date: pnlDate,
          primary_driver: "rate",
          primary_driver_pct: formatRawAsNumeric({ raw: 0.58, unit: "ratio", sign_aware: false }),
          key_findings: ["利率为本期主要归因驱动。"],
          tpl_market_aligned: true,
          tpl_market_note: "与 TPL 市场变动方向一致。",
        },
        {
          result_kind: "pnl-attribution.summary",
          requested_report_date: pnlDate,
          resolved_report_date: pnlDate,
          as_of_date: pnlDate,
          tables_used: ["fact_formal_pnl_fi"],
          evidence_rows: 1710,
          ...options.pnlMeta,
        },
      ),
    }),
    riskDates: options.riskDatesError
      ? query({ error: true })
      : options.riskDatesLoading
        ? query({ loading: true })
        : options.riskDatesNoData
          ? query({})
          : query({
              data: envelope(
                { report_dates: options.riskDates ?? [bondDate] },
                {
                  result_kind: "risk.tensor.dates",
                  basis: "formal",
                  formal_use_allowed: true,
                  requested_report_date: bondDate,
                  resolved_report_date: options.riskDates?.[0] ?? bondDate,
                  as_of_date: options.riskDates?.[0] ?? bondDate,
                  ...options.riskDatesMeta,
                },
              ),
            }),
  };
}

describe("ModuleWorkbenchHome model", () => {
  it("builds a ready portfolio home from existing API envelopes", () => {
    const view = buildModuleHomeView(
      "portfolio",
      { mode: "real" },
      {
        balanceDates: query({ data: envelope({ report_dates: ["2026-03-31"] }) }),
        balanceOverview: query(
          {
            data: envelope({
              report_date: "2026-03-31",
              position_scope: "all",
              currency_basis: "CNY",
              detail_row_count: 3,
              summary_row_count: 2,
              total_market_value_amount: "100000000",
              total_amortized_cost_amount: "99000000",
              total_accrued_interest_amount: "1000000",
              asset_total_market_value_amount: "80000000",
              liability_total_market_value_amount: "20000000",
              asset_total_amortized_cost_amount: "79000000",
              liability_total_amortized_cost_amount: "20000000",
              asset_total_accrued_interest_amount: "800000",
              liability_total_accrued_interest_amount: "200000",
            }),
          },
        ),
      },
    );

    expect(view.stateLabel).toBe("已接入");
    expect(view.kpis.map((item) => item.value)).toContain("0.8 亿元");
    expect(view.kpis.map((item) => item.value)).toContain("0.2 亿元");
    expect(view.dataNote.lines.join(" ")).not.toContain("读取失败");
  });

  it("formats bond headline market value as yi instead of raw yuan display", () => {
    const view = buildModuleHomeView(
      "portfolio",
      { mode: "real" },
      {
        balanceDates: query({ data: envelope({ report_dates: ["2026-03-31"] }) }),
        bondDates: query({ data: envelope({ report_dates: ["2026-04-30"] }) }),
        bondHeadline: query({
          data: envelope({
            report_date: "2026-04-30",
            prev_report_date: null,
            kpis: {
              total_market_value: formatRawAsNumeric({
                raw: 348_819_181_969.63,
                unit: "yuan",
                sign_aware: false,
              }),
              unrealized_pnl: formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: true }),
              weighted_ytm: formatRawAsNumeric({ raw: 0.0285, unit: "pct", sign_aware: false }),
              weighted_duration: formatRawAsNumeric({ raw: 3.45, unit: "ratio", sign_aware: false }),
              weighted_coupon: formatRawAsNumeric({ raw: 0.0312, unit: "pct", sign_aware: false }),
              credit_spread_median: formatRawAsNumeric({ raw: 0.0085, unit: "pct", sign_aware: false }),
              total_dv01: formatRawAsNumeric({ raw: -125_430.5, unit: "dv01", sign_aware: false }),
              bond_count: 428,
            },
            prev_kpis: null,
          }),
        }),
      },
    );

    const bondMarket = view.kpis.find((item) => item.key === "bond-market");
    expect(bondMarket?.value).toContain("亿元");
    expect(bondMarket?.value).toMatch(/3,?488\.19/);
    expect(bondMarket?.value).not.toContain("348,819");
  });

  it("derives the industry distribution total from returned industry rows", () => {
    const view = buildModuleHomeView(
      "portfolio",
      { mode: "real" },
      {
        bondDates: query({ data: envelope({ report_dates: ["2026-04-30"] }) }),
        bondIndustry: query({
          data: envelope({
            report_date: "2026-04-30",
            items: [
              {
                industry_name: "金融债",
                total_market_value: formatRawAsNumeric({ raw: 100_000_000, unit: "yuan", sign_aware: false }),
                bond_count: 2,
                percentage: formatRawAsNumeric({ raw: 0.333333, unit: "pct", sign_aware: false }),
              },
              {
                industry_name: "产业债",
                total_market_value: formatRawAsNumeric({ raw: 200_000_000, unit: "yuan", sign_aware: false }),
                bond_count: 3,
                percentage: formatRawAsNumeric({ raw: 0.666667, unit: "pct", sign_aware: false }),
              },
            ],
          }),
        }),
      },
    );

    const industryPanel = view.distributionPanels?.find((panel) => panel.key === "industry");
    expect(industryPanel?.rows).toHaveLength(2);
    expect(industryPanel?.rows.map((row) => row.marketValue)).toEqual(["1.00 亿元", "2.00 亿元"]);
    expect(industryPanel?.totalDisplay).toBe("3.00 亿");
  });

  it("does not synthesize an industry total when industry distribution rows are empty", () => {
    const view = buildModuleHomeView(
      "portfolio",
      { mode: "real" },
      {
        bondDates: query({ data: envelope({ report_dates: ["2026-04-30"] }) }),
        bondIndustry: query({
          data: envelope({
            report_date: "2026-04-30",
            items: [],
          }),
        }),
      },
    );

    const industryPanel = view.distributionPanels?.find((panel) => panel.key === "industry");
    expect(industryPanel?.rows).toHaveLength(0);
    expect(industryPanel?.totalDisplay).toBeUndefined();
  });

  it("marks the portfolio depth status returned when any depth read has data", () => {
    const view = buildModuleHomeView(
      "portfolio",
      { mode: "real" },
      {
        bondDates: query({ data: envelope({ report_dates: ["2026-04-30"] }) }),
        bondYield: query({
          data: envelope({
            report_date: "2026-04-30",
            weighted_ytm: formatRawAsNumeric({ raw: 0.028, unit: "pct", sign_aware: false }),
            items: [],
          }),
        }),
      },
    );

    expect(view.statuses.find((item) => item.key === "bond-depth")).toMatchObject({
      value: "已返回",
      detail: expect.stringContaining("至少一个子读面已返回"),
      tone: "ok",
    });
  });

  it("keeps empty governance data explicit instead of rendering blank cards", () => {
    const view = buildModuleHomeView(
      "governance",
      { mode: "mock" },
      {
        healthLive: query({ data: { status: "" } }),
        healthSummary: query({ data: { status: "" } }),
        sourceFoundation: query({ data: envelope({ sources: [] }) }),
        cubeDimensions: query({
          data: {
            fact_table: "bond_analytics",
            dimensions: [],
            measures: [],
            measure_fields: [],
          },
        }),
      },
    );

    expect(view.kpis).toHaveLength(4);
    expect(view.kpis.some((item) => item.value === "0")).toBe(true);
    expect(view.statuses.some((item) => item.value === "规划中")).toBe(true);
    expect(view.detailPanels?.some((panel) => panel.key === "source-status")).toBe(true);
    expect(view.detailPanels?.some((panel) => panel.key === "cube-dimensions")).toBe(true);
    expect(view.detailPanels?.find((panel) => panel.key === "source-status")?.rows).toHaveLength(0);
  });

  it("builds governance detail panels from source foundation and cube dimensions", () => {
    const view = buildModuleHomeView(
      "governance",
      { mode: "mock" },
      {
        healthLive: query({ data: { status: "ok" } }),
        healthSummary: query({ data: { status: "ok" } }),
        sourceFoundation: query({
          data: envelope({
            sources: [
              {
                source_family: "zqtz",
                report_date: "2025-12-31",
                source_file: "ZQTZSHOW-20251231.xls",
                total_rows: 1724,
                manual_review_count: 0,
                source_version: "sv_mock_zqtz_preview",
                rule_version: "rv_phase1_source_preview_v1",
                group_counts: { 债券类: 1571, 回购类: 0 },
              },
              {
                source_family: "tyw",
                report_date: "2025-12-31",
                source_file: "TYWLSHOW-20251231.xls",
                total_rows: 2395,
                manual_review_count: 18,
                source_version: "sv_mock_tyw_preview",
                rule_version: "rv_phase1_source_preview_v1",
                group_counts: { 债券类: 0, 回购类: 1060 },
              },
            ],
          }),
        }),
        cubeDimensions: query({
          data: {
            fact_table: "bond_analytics",
            dimensions: ["asset_class_std", "rating", "bond_type"],
            measures: ["sum", "avg"],
            measure_fields: ["market_value", "duration"],
          },
        }),
      },
    );

    expect(view.stateLabel).toBe("已接入");
    expect(view.kpis.find((item) => item.key === "source-count")?.value).toBe("2");
    expect(view.kpis.find((item) => item.key === "cube-dimensions")?.value).toBe("3");

    const sourcePanel = view.detailPanels?.find((panel) => panel.key === "source-status");
    expect(sourcePanel?.rows.some((row) => row.label === "ZQTZ" && row.value === "正常")).toBe(true);
    expect(sourcePanel?.rows.some((row) => row.label === "TYW" && row.value.includes("待复核"))).toBe(
      true,
    );
    expect(sourcePanel?.meta).toContain("source-foundation");

    const cubePanel = view.detailPanels?.find((panel) => panel.key === "cube-dimensions");
    expect(cubePanel?.rows.some((row) => row.label === "事实表" && row.value === "bond_analytics")).toBe(
      true,
    );
    expect(cubePanel?.rows.some((row) => row.label === "rating" && row.value === "维度")).toBe(true);
    expect(cubePanel?.rows.some((row) => row.label === "market_value" && row.value === "度量字段")).toBe(
      true,
    );
    expect(cubePanel?.meta).toContain("cube / bond_analytics");
  });

  it("does not attach governance detail panels to portfolio home", () => {
    const view = buildModuleHomeView(
      "portfolio",
      { mode: "mock" },
      {
        balanceDates: query({ data: envelope({ report_dates: ["2026-03-31"] }) }),
      },
    );

    expect(view.detailPanels?.some((panel) => panel.key === "source-status") ?? false).toBe(false);
  });

  it("surfaces source errors and forbids frontend backfilling", () => {
    const view = buildModuleHomeView(
      "risk",
      { mode: "real" },
      {
        riskDates: query({ error: true }),
      },
    );

    expect(view.stateLabel).toBe("读取失败");
    expect(view.statuses[0]?.value).toBe("读取失败");
    expect(view.dataNote.lines.join(" ")).toContain("不使用前端补数");
  });

  it("keeps stale or fallback metadata visible in KPI details", () => {
    const view = buildModuleHomeView(
      "market",
      { mode: "real" },
      {
        marketRates: query(
          {
            data: envelope(
              {
                read_target: "duckdb" as const,
                series: [],
              },
              {
                quality_flag: "stale",
                fallback_mode: "latest_snapshot",
                fallback_date: "2026-05-31",
              },
            ),
          },
        ),
      },
    );

    expect(view.kpis.find((item) => item.key === "rate-series")?.detail).toContain(
      "2026-05-31",
    );
    expect(view.kpis.find((item) => item.key === "rate-series")?.tone).toBe("watch");
  });

  it("builds market key rate snapshots from existing market-data terminal specs", () => {
    const view = buildModuleHomeView(
      "market",
      { mode: "mock" },
      {
        choiceLatest: query({
          data: envelope({
            read_target: "duckdb",
            series: [
              {
                series_id: "M002",
                series_name: "DR007",
                trade_date: "2026-04-10",
                value_numeric: 1.83,
                unit: "%",
                source_version: "sv_choice_macro_mock",
                vendor_version: "vv_choice_macro_20260410",
              },
              {
                series_id: "M003",
                series_name: "1年期国债到期收益率",
                trade_date: "2026-04-10",
                value_numeric: 1.56,
                unit: "%",
                source_version: "sv_choice_macro_mock",
                vendor_version: "vv_choice_macro_20260410",
              },
            ],
          }),
        }),
        marketRates: query({
          data: envelope({
            read_target: "duckdb",
            series: [
              {
                series_id: "M001",
                series_name: "公开市场7天逆回购利率",
                trade_date: "2026-04-10",
                value_numeric: 1.75,
                unit: "%",
                source_version: "sv_market_data_rates_mock",
                vendor_version: "vv_choice_macro_20260410",
                refresh_tier: "stable",
              },
            ],
          }),
        }),
        marketCatalog: query({
          data: envelope({
            read_target: "duckdb",
            series: [
              {
                series_id: "M001",
                series_name: "公开市场7天逆回购利率",
                vendor_name: "choice",
                vendor_version: "vv_choice_catalog_v1",
                frequency: "daily",
                unit: "%",
                refresh_tier: "stable",
              },
            ],
          }),
        }),
      },
    );

    const snapshot = view.detailPanels?.find((panel) => panel.key === "key-rate-snapshot");
    expect(snapshot?.rows.some((row) => row.label === "DR007")).toBe(true);
    expect(snapshot?.rows.some((row) => row.label === "7天逆回购")).toBe(true);
    expect(view.detailPanels?.some((panel) => panel.key === "formal-rate-series")).toBe(true);
    expect(view.detailPanels?.some((panel) => panel.key === "catalog-overview")).toBe(true);
    expect(view.detailPanels?.some((panel) => panel.key === "latest-macro-snapshot")).toBe(true);
    expect(view.detailPanels?.some((panel) => panel.key === "yield-curve-quotes")).toBe(true);
  });

  it("only builds percent rate charts when at least two percent rows exist", () => {
    const mixedRows = [
      {
        key: "M001",
        label: "7天逆回购",
        value: "1.75%",
        tradeDate: "2026-04-10",
        source: "M001",
        tone: "ok" as const,
      },
      {
        key: "CA.CSI300",
        label: "沪深300",
        value: "4807.31",
        tradeDate: "2026-04-10",
        source: "CA.CSI300",
        tone: "ok" as const,
      },
      {
        key: "M003",
        label: "10Y国债",
        value: "1.71%",
        tradeDate: "2026-04-10",
        source: "M003",
        tone: "ok" as const,
      },
    ];

    const view = buildModuleHomeView(
      "market",
      { mode: "mock" },
      {
        choiceLatest: query({ data: envelope({ read_target: "duckdb", series: [] }) }),
        marketRates: query({
          data: envelope({
            read_target: "duckdb",
            series: mixedRows.map((row) => ({
              series_id: row.key,
              series_name: row.label,
              trade_date: row.tradeDate,
              value_numeric: Number.parseFloat(row.value),
              unit: row.value.includes("%") ? "%" : "点",
              source_version: "sv_test",
              vendor_version: "vv_test",
            })),
          }),
        }),
      },
    );

    const formalPanel = view.detailPanels?.find((panel) => panel.key === "formal-rate-series");
    expect(formalPanel?.chart?.categories).toEqual(["7天逆回购", "10Y国债"]);
    expect(formalPanel?.chart?.values).toEqual([1.75, 1.71]);

    const snapshotPanel = view.detailPanels?.find((panel) => panel.key === "key-rate-snapshot");
    expect(snapshotPanel?.chart).toBeUndefined();
  });

  it("builds macro toolkit detail panels from analysis envelope", () => {
    const view = buildModuleHomeView(
      "market",
      { mode: "mock" },
      {
        choiceLatest: query({ data: envelope({ read_target: "duckdb", series: [] }) }),
        macroToolkitAnalysis: query({
          data: envelope({
            default_data_sources: ["choice"],
            as_of_date: "2026-04-30",
            conclusion: {
              stance: "中性观察",
              tone: "neutral",
              summary: "风险资产和资金利率证据接近。",
              recommended_action: "优先运行 signal_aggregator。",
            },
            coverage: {
              indicator_count: 8,
              hit_count: 7,
              hit_rate: 0.875,
              script_count: 24,
              output_file_count: 0,
            },
            indicators: [],
            signal_cards: [
              {
                key: "liquidity",
                title: "流动性",
                stance: "偏松",
                tone: "positive",
                score: 78,
                evidence: ["DR007 1.82%"],
              },
            ],
            capability_results: [],
            strategy_summaries: [],
            output_files: [],
            source_checks: [],
            capabilities: [],
            warnings: [],
          }),
        }),
      },
    );

    expect(view.detailPanels?.some((panel) => panel.key === "macro-toolkit-overview")).toBe(true);
    expect(view.detailPanels?.some((panel) => panel.key === "macro-toolkit-signals")).toBe(true);
    expect(view.briefings.some((item) => item.title === "宏观工具")).toBe(true);
    expect(view.briefings.find((item) => item.title === "宏观工具")?.conclusion).toContain("中性观察");
    expect(view.statuses.some((item) => item.key === "macro-toolkit")).toBe(true);
    expect(view.kpis.some((item) => item.key === "macro-toolkit-hit")).toBe(true);
  });

  it("keeps market detail panels visible while queries refetch cached data", () => {
    const view = buildModuleHomeView(
      "market",
      { mode: "real" },
      {
        choiceLatest: query({
          data: envelope({
            read_target: "duckdb",
            series: [
              {
                series_id: "M002",
                series_name: "DR007",
                trade_date: "2026-04-10",
                value_numeric: 1.83,
                unit: "%",
                source_version: "sv_choice_macro_mock",
                vendor_version: "vv_choice_macro_20260410",
              },
            ],
          }),
          refetching: true,
        }),
        marketRates: query({ data: envelope({ read_target: "duckdb", series: [] }) }),
        marketCatalog: query({ data: envelope({ read_target: "duckdb", series: [] }) }),
      },
    );

    const snapshotPanel = view.detailPanels?.find((panel) => panel.key === "key-rate-snapshot");
    expect(snapshotPanel?.stateLabel).toBe("已返回");
    expect(snapshotPanel?.rows.some((row) => row.label === "DR007")).toBe(true);
  });

  it("builds extended macro toolkit panels when analysis includes risk and strategy payloads", () => {
    const view = buildModuleHomeView(
      "market",
      { mode: "mock" },
      {
        choiceLatest: query({ data: envelope({ read_target: "duckdb", series: [] }) }),
        macroToolkitAnalysis: query({
          data: envelope({
            default_data_sources: ["choice"],
            as_of_date: "2026-04-30",
            conclusion: {
              stance: "中性观察",
              tone: "neutral",
              summary: "风险资产和资金利率证据接近。",
              recommended_action: "优先运行 signal_aggregator。",
            },
            coverage: {
              indicator_count: 8,
              hit_count: 7,
              hit_rate: 0.875,
              script_count: 24,
              output_file_count: 0,
            },
            indicators: [],
            signal_cards: [],
            a_share_risk: {
              trade_date: "2026-04-30",
              status: "degraded",
              risk_score: 64,
              risk_level: "orange",
              risk_name: "橙色风险",
              summary: "市场踩踏风险升温。",
              position_rule: "总仓位上限30%。",
              metrics: { up_count: 186 },
              triggered_rules: ["跌停家数超过50"],
              watch_next: ["上涨家数是否恢复"],
              warnings: [],
              tables_used: [],
            },
            hason_strategy: {
              key: "hason_macro_strategy",
              framework_name: "Hason Macro",
              basis: "analytical",
              observation_only: true,
              formal_use_allowed: false,
              formal_metric_id: null,
              status: "observation_ready",
              display_status: "observation_ready",
              readiness: {
                ready_modules: 2,
                partial_modules: 1,
                missing_modules: 0,
                missing_script_count: 0,
                total_modules: 3,
                ratio: 0.67,
              },
              modules: [
                {
                  key: "M1",
                  label: "模块一",
                  status: "ready",
                  scripts: [],
                  available_scripts: ["script_a"],
                  missing_scripts: [],
                  evidence: [],
                },
              ],
              runtime_output_status: "current",
              runtime_outputs: [],
              required_runtime_outputs: [],
              runtime_output_gaps: [],
              missing_runtime_outputs: [],
              stale_runtime_outputs: [],
              boundary: "observation-only",
              source_trace: [],
            },
            shadow_portfolio_report: {
              status: "complete",
              basis: "read_only_shadow",
              label: "影子组合报告",
              as_of_date: "2026-05-27",
              completed_periods: 13,
              factor_dates: [],
              rule_version: "rv_test",
              tables_used: [],
              warnings: [],
              cost_model: {
                cost_bps: [0],
                initial_build_included: true,
                final_liquidation_included: false,
              },
              benchmark: null,
              portfolios: [],
              period_returns: [],
            },
            cffex_member_rank: {
              materialized: true,
              status: "ok",
              row_count: 80,
              latest_trade_date: "2026-04-30",
              contracts: [],
              source_vendors: ["choice"],
              freshness_status: "current",
              reference_date: "2026-04-30",
              stale_days: 0,
            },
            capability_results: [],
            strategy_summaries: [],
            output_files: [],
            source_checks: [],
            capabilities: [],
            warnings: [],
          }),
        }),
      },
    );

    expect(view.detailPanels?.some((panel) => panel.key === "macro-toolkit-a-share-risk")).toBe(true);
    expect(view.detailPanels?.some((panel) => panel.key === "macro-toolkit-hason")).toBe(true);
    expect(view.detailPanels?.some((panel) => panel.key === "macro-toolkit-shadow")).toBe(true);
    expect(view.detailPanels?.some((panel) => panel.key === "macro-toolkit-runtime")).toBe(true);
    expect(view.statuses.some((item) => item.key === "a-share-risk")).toBe(true);
  });

  it("builds portfolio detail panels from bond-dashboard and attribution reads", () => {
    const view = buildModuleHomeView(
      "portfolio",
      { mode: "real" },
      {
        balanceDates: query({ data: envelope({ report_dates: ["2026-03-31"] }) }),
        bondDates: query({ data: envelope({ report_dates: ["2026-04-30"] }) }),
        bondRisk: query({
          data: envelope({
            report_date: "2026-04-30",
            total_market_value: formatRawAsNumeric({ raw: 100_000_000_000, unit: "yuan", sign_aware: false }),
            total_dv01: formatRawAsNumeric({ raw: -125_430.5, unit: "dv01", sign_aware: false }),
            weighted_duration: formatRawAsNumeric({ raw: 3.45, unit: "ratio", sign_aware: false }),
            credit_ratio: formatRawAsNumeric({ raw: 0.42, unit: "pct", sign_aware: false }),
            weighted_convexity: formatRawAsNumeric({ raw: 0.12, unit: "ratio", sign_aware: false }),
            total_spread_dv01: formatRawAsNumeric({ raw: 12_000, unit: "dv01", sign_aware: false }),
            reinvestment_ratio_1y: formatRawAsNumeric({ raw: 0.18, unit: "pct", sign_aware: false }),
          }),
        }),
        pnlSummary: query({
          data: envelope({
            report_date: "2026-04-30",
            primary_driver: "volume",
            primary_driver_pct: formatRawAsNumeric({ raw: 0.53, unit: "pct", sign_aware: false }),
            key_findings: ["规模效应主导本期损益变动。"],
            tpl_market_aligned: true,
            tpl_market_note: "TPL 与市场方向一致。",
          }),
        }),
      },
    );

    expect(view.detailPanels?.some((panel) => panel.key === "risk-indicators-detail")).toBe(true);
    expect(view.detailPanels?.some((panel) => panel.key === "pnl-attribution-summary")).toBe(true);
    expect(view.kpis.some((item) => item.key === "bond-credit-spread")).toBe(true);
    expect(view.briefings[2]?.conclusion).toContain("规模");
  });

  it("builds a PM decision cockpit from portfolio exposure and read-path evidence", () => {
    const view = buildModuleHomeView(
      "portfolio",
      { mode: "real" },
      {
        balanceDates: query({ data: envelope({ report_dates: ["2026-04-30"] }) }),
        balanceOverview: query({
          data: envelope(
            {
              report_date: "2026-04-30",
              position_scope: "all",
              currency_basis: "CNY",
              detail_row_count: 3,
              summary_row_count: 2,
              total_market_value_amount: "100000000",
              total_amortized_cost_amount: "99000000",
              total_accrued_interest_amount: "1000000",
              asset_total_market_value_amount: "80000000",
              liability_total_market_value_amount: "20000000",
              asset_total_amortized_cost_amount: "79000000",
              liability_total_amortized_cost_amount: "20000000",
              asset_total_accrued_interest_amount: "800000",
              liability_total_accrued_interest_amount: "200000",
            },
            {
              requested_report_date: "2026-04-30",
              resolved_report_date: "2026-04-30",
              as_of_date: "2026-04-30",
            },
          ),
        }),
        bondDates: query({ data: envelope({ report_dates: ["2026-04-30"] }) }),
        bondHeadline: query({
          data: envelope(
            {
              report_date: "2026-04-30",
              prev_report_date: null,
              kpis: {
                total_market_value: formatRawAsNumeric({ raw: 100_000_000_000, unit: "yuan", sign_aware: false }),
                unrealized_pnl: formatRawAsNumeric({ raw: 820_000_000, unit: "yuan", sign_aware: true }),
                weighted_ytm: formatRawAsNumeric({ raw: 0.0256, unit: "pct", sign_aware: false }),
                weighted_duration: formatRawAsNumeric({ raw: 4.45, unit: "ratio", sign_aware: false }),
                weighted_coupon: formatRawAsNumeric({ raw: 0.0312, unit: "pct", sign_aware: false }),
                credit_spread_median: formatRawAsNumeric({ raw: 0.0237, unit: "pct", sign_aware: false }),
                total_dv01: formatRawAsNumeric({ raw: -125_430.5, unit: "dv01", sign_aware: false }),
                bond_count: 428,
              },
              prev_kpis: null,
            },
            {
              result_kind: "bond_dashboard.home_summary",
              requested_report_date: "2026-04-30",
              resolved_report_date: "2026-04-30",
              as_of_date: "2026-04-30",
              quality_flag: "ok",
              fallback_mode: "none",
              evidence_rows: 428,
              tables_used: ["fact_formal_bond_analytics_daily"],
            },
          ),
        }),
        bondRisk: query({
          data: envelope(
            {
              report_date: "2026-04-30",
              total_market_value: formatRawAsNumeric({ raw: 100_000_000_000, unit: "yuan", sign_aware: false }),
              total_dv01: formatRawAsNumeric({ raw: -125_430.5, unit: "dv01", sign_aware: false }),
              weighted_duration: formatRawAsNumeric({ raw: 4.45, unit: "ratio", sign_aware: false }),
              credit_ratio: formatRawAsNumeric({ raw: 0.42, unit: "pct", sign_aware: false }),
              weighted_convexity: formatRawAsNumeric({ raw: 0.12, unit: "ratio", sign_aware: false }),
              total_spread_dv01: formatRawAsNumeric({ raw: 12_000, unit: "dv01", sign_aware: false }),
              reinvestment_ratio_1y: formatRawAsNumeric({ raw: 0.18, unit: "pct", sign_aware: false }),
            },
            {
              requested_report_date: "2026-04-30",
              resolved_report_date: "2026-04-30",
              as_of_date: "2026-04-30",
            },
          ),
        }),
        pnlSummary: query({
          data: envelope(
            {
              report_date: "2026-04-30",
              primary_driver: "volume",
              primary_driver_pct: formatRawAsNumeric({ raw: 0.53, unit: "pct", sign_aware: false }),
              key_findings: ["规模效应主导本期损益变动。"],
              tpl_market_aligned: true,
              tpl_market_note: "TPL 与市场方向一致。",
            },
            {
              requested_report_date: "2026-04-30",
              resolved_report_date: "2026-04-30",
              as_of_date: "2026-04-30",
            },
          ),
        }),
        riskDates: query({
          data: envelope(
            { report_dates: ["2026-04-30"] },
            {
              requested_report_date: "2026-04-30",
              resolved_report_date: "2026-04-30",
              as_of_date: "2026-04-30",
            },
          ),
        }),
      },
    );

    expect(view.decision?.title).toBe("今日组合判断");
    expect(view.decision?.conclusion).toContain("信用");
    expect(view.decision?.detail).toContain("不使用前端补数");
    expect(view.decision?.detail).toContain("bond_dashboard.home_summary");
    expect(view.decision?.detail).toContain("fact_formal_bond_analytics_daily");
    expect(view.decision?.detail).toContain("无回退");
    expect(view.decision?.facts.map((fact) => fact.label)).toEqual(
      expect.arrayContaining(["信用占比", "DV01", "归因摘要", "数据链路", "证据样本"]),
    );
    expect(view.decision?.facts.find((fact) => fact.label === "证据样本")?.value).toBe("428 行");
    expect(view.decision?.actions).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          title: "信用结构复核",
          path: "/bond-dashboard",
          evidence: expect.stringContaining("42.00%"),
        }),
        expect.objectContaining({
          title: "子组合分层核验",
          path: "/bond-dashboard",
        }),
      ]),
    );
  });

  it("blocks portfolio decision-grade wording when bond evidence is analytical", () => {
    const view = buildModuleHomeView(
      "portfolio",
      { mode: "real" },
      portfolioGovernanceQueries({
        bondMeta: {
          basis: "analytical",
          formal_use_allowed: false,
          quality_flag: "warning",
        },
      }),
    );

    expect(view.kpis.find((item) => item.key === "bond-market")?.value).toBe("3,322.82 亿元");
    expect(view.decision?.conclusion).toContain("仅供分析");
    expect(view.decision?.detail).toContain("formal_use_allowed=false");
    expect(view.decision?.detail).toContain("basis=analytical");
    expect(view.decision?.actions?.some((action) => action.title === "信用结构复核")).toBe(false);
    expect(view.decision?.actions?.map((action) => action.title)).toEqual(
      expect.arrayContaining(["来源证据复核", "债券总览核对", "收益归因复核"]),
    );
  });

  it("blocks portfolio decision-grade wording for fallback or stale evidence while preserving values", () => {
    const view = buildModuleHomeView(
      "portfolio",
      { mode: "real" },
      portfolioGovernanceQueries({
        bondMeta: {
          quality_flag: "stale",
          fallback_mode: "latest_snapshot",
          fallback_date: "2026-04-30",
        },
      }),
    );

    expect(view.kpis.find((item) => item.key === "bond-market")?.value).toBe("3,322.82 亿元");
    expect(view.decision?.conclusion).toContain("仅供分析");
    expect(view.decision?.detail).toContain("fallback=latest_snapshot/2026-04-30");
    expect(view.decision?.detail).toContain("quality=stale");
    expect(view.decision?.actions?.some((action) => action.title.includes("调仓"))).toBe(false);
  });

  it("blocks portfolio decisions when source report dates are mismatched", () => {
    const view = buildModuleHomeView(
      "portfolio",
      { mode: "real" },
      portfolioGovernanceQueries({
        balanceDate: "2026-05-30",
        bondDate: "2026-05-31",
        pnlDate: "2026-05-31",
      }),
    );

    expect(view.decision?.conclusion).toContain("仅供分析");
    expect(view.decision?.detail).toContain("日期不一致");
    expect(view.decision?.detail).toContain("资产负债=2026-05-30");
    expect(view.decision?.detail).toContain("债券总览=2026-05-31");
    expect(view.decision?.detail).toContain("损益归因=2026-05-31");
    expect(view.decision?.facts.find((fact) => fact.label === "源日期")?.value).toContain("2026-05-30");
  });

  it.each([
    [
      "bond headline earlier",
      { bondMeta: { resolved_report_date: "2026-05-30", as_of_date: "2026-05-30" } },
      "债券总览 meta_date=2026-05-30",
    ],
    [
      "risk indicators earlier",
      { riskMeta: { resolved_report_date: "2026-05-30", as_of_date: "2026-05-30" } },
      "风险指标 meta_date=2026-05-30",
    ],
    [
      "balance overview earlier",
      { balanceMeta: { resolved_report_date: "2026-05-30", as_of_date: "2026-05-30" } },
      "资产负债 meta_date=2026-05-30",
    ],
    [
      "pnl summary earlier",
      { pnlMeta: { resolved_report_date: "2026-05-30", as_of_date: "2026-05-30" } },
      "损益归因 meta_date=2026-05-30",
    ],
    [
      "bond headline later",
      { bondMeta: { resolved_report_date: "2026-06-01", as_of_date: "2026-06-01" } },
      "债券总览 meta_date=2026-06-01",
    ],
    [
      "risk indicators later",
      { riskMeta: { resolved_report_date: "2026-06-01", as_of_date: "2026-06-01" } },
      "风险指标 meta_date=2026-06-01",
    ],
    [
      "balance overview later",
      { balanceMeta: { resolved_report_date: "2026-06-01", as_of_date: "2026-06-01" } },
      "资产负债 meta_date=2026-06-01",
    ],
    [
      "pnl summary later",
      { pnlMeta: { resolved_report_date: "2026-06-01", as_of_date: "2026-06-01" } },
      "损益归因 meta_date=2026-06-01",
    ],
  ] satisfies Array<[string, Parameters<typeof portfolioGovernanceQueries>[0], string]>)(
    "blocks portfolio decision-grade wording when %s result_meta date differs from the anchor",
    (_caseName, options, expectedReason) => {
      const view = buildModuleHomeView(
        "portfolio",
        { mode: "real" },
        portfolioGovernanceQueries(options),
      );

      expect(view.kpis.find((item) => item.key === "bond-market")?.value).toBe("3,322.82 亿元");
      expect(view.decision?.conclusion).toContain("仅供分析");
      expect(view.decision?.detail).toContain(expectedReason);
      expect(view.decision?.actions?.some((action) => action.title === "信用结构复核")).toBe(false);
    },
  );

  it("blocks portfolio decision-grade wording when a secondary source metadata date differs", () => {
    const view = buildModuleHomeView(
      "portfolio",
      { mode: "real" },
      portfolioGovernanceQueries({
        bondMeta: {
          resolved_report_date: "2026-05-31",
          requested_report_date: "2026-05-31",
          as_of_date: "2026-05-30",
        },
      }),
    );

    expect(view.kpis.find((item) => item.key === "bond-market")?.value).toBe("3,322.82 亿元");
    expect(view.decision?.conclusion).toContain("仅供分析");
    expect(view.decision?.detail).toContain("债券总览 meta_date=2026-05-30");
    expect(view.decision?.actions?.some((action) => action.title === "信用结构复核")).toBe(false);
  });

  it("blocks portfolio decision-grade wording when a secondary source metadata date is missing", () => {
    const view = buildModuleHomeView(
      "portfolio",
      { mode: "real" },
      portfolioGovernanceQueries({
        bondMeta: {
          resolved_report_date: "2026-05-31",
          requested_report_date: "2026-05-31",
          as_of_date: null,
        },
      }),
    );

    expect(view.kpis.find((item) => item.key === "bond-market")?.value).toBe("3,322.82 亿元");
    expect(view.decision?.conclusion).toContain("仅供分析");
    expect(view.decision?.detail).toContain("债券总览 report_date 缺失");
    expect(view.decision?.actions?.some((action) => action.title === "信用结构复核")).toBe(false);
  });

  it("surfaces missing same-date risk tensor readiness without hiding portfolio values", () => {
    const view = buildModuleHomeView(
      "portfolio",
      { mode: "real" },
      portfolioGovernanceQueries({
        bondDate: "2026-05-31",
        riskDates: ["2026-04-30"],
      }),
    );

    expect(view.kpis.find((item) => item.key === "bond-market")?.value).toBe("3,322.82 亿元");
    expect(view.decision?.conclusion).toContain("仅供监控");
    expect(view.decision?.detail).toContain("风险张量未闭合至 2026-05-31");
    expect(view.decision?.detail).toContain("最新 2026-04-30");
    expect(view.decision?.facts.find((fact) => fact.label === "风险闭合")?.value).toContain("2026-04-30");
  });

  it("does not mark risk tensor as same-day closed when risk date metadata differs from the anchor", () => {
    const view = buildModuleHomeView(
      "portfolio",
      { mode: "real" },
      portfolioGovernanceQueries({
        bondDate: "2026-05-31",
        riskDates: ["2026-05-31"],
        riskDatesMeta: {
          resolved_report_date: "2026-05-30",
          as_of_date: "2026-05-30",
        },
      }),
    );

    expect(view.kpis.find((item) => item.key === "bond-market")?.value).toBe("3,322.82 亿元");
    expect(view.decision?.conclusion).toContain("仅供监控");
    expect(view.decision?.detail).toContain("风险闭合证据 meta_date=2026-05-30");
    expect(view.decision?.detail).not.toContain("同日闭合 2026-05-31");
    expect(view.decision?.facts.find((fact) => fact.label === "风险闭合")?.value).not.toContain("同日闭合");
  });

  it("does not mark risk tensor as same-day closed when a secondary risk metadata date differs", () => {
    const view = buildModuleHomeView(
      "portfolio",
      { mode: "real" },
      portfolioGovernanceQueries({
        bondDate: "2026-05-31",
        riskDates: ["2026-05-31"],
        riskDatesMeta: {
          resolved_report_date: "2026-05-31",
          requested_report_date: "2026-05-31",
          as_of_date: "2026-05-30",
        },
      }),
    );

    expect(view.kpis.find((item) => item.key === "bond-market")?.value).toBe("3,322.82 亿元");
    expect(view.decision?.conclusion).toContain("仅供监控");
    expect(view.decision?.detail).toContain("风险闭合证据 meta_date=2026-05-30");
    expect(view.decision?.facts.find((fact) => fact.label === "风险闭合")?.value).not.toContain("同日闭合");
  });

  it("does not mark risk tensor as same-day closed when a secondary risk metadata date is missing", () => {
    const view = buildModuleHomeView(
      "portfolio",
      { mode: "real" },
      portfolioGovernanceQueries({
        bondDate: "2026-05-31",
        riskDates: ["2026-05-31"],
        riskDatesMeta: {
          resolved_report_date: "2026-05-31",
          requested_report_date: "2026-05-31",
          as_of_date: null,
        },
      }),
    );

    expect(view.kpis.find((item) => item.key === "bond-market")?.value).toBe("3,322.82 亿元");
    expect(view.decision?.conclusion).toContain("仅供监控");
    expect(view.decision?.detail).toContain("风险闭合证据 report_date 缺失");
    expect(view.decision?.facts.find((fact) => fact.label === "风险闭合")?.value).not.toContain("同日闭合");
  });

  it.each([
    ["error", { riskDatesError: true }],
    ["loading", { riskDatesLoading: true }],
    ["no data", { riskDatesNoData: true }],
    ["empty", { riskDates: [] }],
    [
      "non-formal",
      {
        riskDatesMeta: {
          basis: "analytical",
          formal_use_allowed: false,
        },
      },
    ],
  ] satisfies Array<[string, Parameters<typeof portfolioGovernanceQueries>[0]]>)(
    "does not mark risk tensor as same-day closed when risk dates are %s",
    (_caseName, options) => {
      const view = buildModuleHomeView(
        "portfolio",
        { mode: "real" },
        portfolioGovernanceQueries(options),
      );

      expect(view.kpis.find((item) => item.key === "bond-market")?.value).toBe("3,322.82 亿元");
      expect(view.decision?.conclusion).toContain("仅供监控");
      expect(view.decision?.detail).toContain("风险闭合证据");
      expect(view.decision?.detail).not.toContain("同日闭合 2026-05-31");
      expect(view.decision?.facts.find((fact) => fact.label === "风险闭合")?.value).not.toContain("同日闭合");
    },
  );

  it.each([
    ["pnl read error", { pnlError: true }, "损益归因读取失败"],
    ["pnl no data", { pnlNoData: true }, "损益归因未返回"],
    [
      "pnl analytical",
      {
        pnlMeta: {
          basis: "analytical",
          formal_use_allowed: false,
        },
      },
      "损益归因 basis=analytical",
    ],
    [
      "pnl warning",
      {
        pnlMeta: {
          quality_flag: "warning",
        },
      },
      "损益归因 quality=warning",
    ],
    ["pnl date mismatch", { pnlDate: "2026-05-30" }, "损益归因=2026-05-30"],
  ] satisfies Array<[string, Parameters<typeof portfolioGovernanceQueries>[0], string]>)(
    "blocks portfolio decision-grade wording when %s",
    (_caseName, options, expectedReason) => {
      const view = buildModuleHomeView(
        "portfolio",
        { mode: "real" },
        portfolioGovernanceQueries(options),
      );

      expect(view.kpis.find((item) => item.key === "bond-market")?.value).toBe("3,322.82 亿元");
      expect(view.decision?.conclusion).toContain("仅供分析");
      expect(view.decision?.detail).toContain(expectedReason);
      expect(view.decision?.actions?.some((action) => action.title === "信用结构复核")).toBe(false);
    },
  );

  it.each([
    ["missing bond result_meta", { bondMetaMissing: true }, "债券总览证据元数据缺失"],
    [
      "fallback mode",
      {
        bondMeta: {
          fallback_mode: "latest_snapshot",
        },
      },
      "债券总览 fallback=latest_snapshot",
    ],
    [
      "fallback date",
      {
        bondMeta: {
          fallback_date: "2026-04-30",
        },
      },
      "债券总览 fallback=none/2026-04-30",
    ],
    [
      "missing quality",
      {
        bondMeta: {
          quality_flag: "missing",
        },
      },
      "债券总览 quality=missing",
    ],
    [
      "missing report date metadata",
      {
        bondMeta: {
          requested_report_date: null,
          resolved_report_date: null,
          as_of_date: null,
        },
      },
      "债券总览 report_date 缺失",
    ],
  ] satisfies Array<[string, Parameters<typeof portfolioGovernanceQueries>[0], string]>)(
    "blocks portfolio decision-grade wording when source metadata has %s",
    (_caseName, options, expectedReason) => {
      const view = buildModuleHomeView(
        "portfolio",
        { mode: "real" },
        portfolioGovernanceQueries(options),
      );

      expect(view.kpis.find((item) => item.key === "bond-market")?.value).toBe("3,322.82 亿元");
      expect(view.decision?.conclusion).toContain("仅供分析");
      expect(view.decision?.detail).toContain(expectedReason);
      expect(view.decision?.actions?.some((action) => action.title === "信用结构复核")).toBe(false);
    },
  );

  it("does not let portfolio comparison failure block decision evidence readiness", () => {
    const view = buildModuleHomeView(
      "portfolio",
      { mode: "real" },
      portfolioGovernanceQueries({
        portfolioComparisonError: true,
      }),
    );

    expect(view.stateLabel).toBe("已接入");
    expect(view.decision?.conclusion).not.toContain("仅供分析");
    expect(view.decision?.detail).toContain("同日闭合 2026-05-31");
    expect(view.decision?.actions?.map((action) => action.title)).toContain("子组合分层核验");
  });

  it("guards mock portfolio samples from decision-grade conclusions", () => {
    const view = buildModuleHomeView(
      "portfolio",
      { mode: "mock" },
      {
        bondDates: query({ data: envelope({ report_dates: ["2026-04-30"] }) }),
        bondHeadline: query({
          data: envelope({
            report_date: "2026-04-30",
            prev_report_date: null,
            kpis: {
              total_market_value: formatRawAsNumeric({ raw: 100_000_000_000, unit: "yuan", sign_aware: false }),
              unrealized_pnl: formatRawAsNumeric({ raw: 820_000_000, unit: "yuan", sign_aware: true }),
              weighted_ytm: formatRawAsNumeric({ raw: 0.0256, unit: "pct", sign_aware: false }),
              weighted_duration: formatRawAsNumeric({ raw: 4.45, unit: "ratio", sign_aware: false }),
              weighted_coupon: formatRawAsNumeric({ raw: 0.0312, unit: "pct", sign_aware: false }),
              credit_spread_median: formatRawAsNumeric({ raw: 0.0237, unit: "pct", sign_aware: false }),
              total_dv01: formatRawAsNumeric({ raw: -125_430.5, unit: "dv01", sign_aware: false }),
              bond_count: 428,
            },
            prev_kpis: null,
          }),
        }),
        bondRisk: query({
          data: envelope({
            report_date: "2026-04-30",
            total_market_value: formatRawAsNumeric({ raw: 100_000_000_000, unit: "yuan", sign_aware: false }),
            total_dv01: formatRawAsNumeric({ raw: -125_430.5, unit: "dv01", sign_aware: false }),
            weighted_duration: formatRawAsNumeric({ raw: 4.45, unit: "ratio", sign_aware: false }),
            credit_ratio: formatRawAsNumeric({ raw: 0.42, unit: "pct", sign_aware: false }),
            weighted_convexity: formatRawAsNumeric({ raw: 0.12, unit: "ratio", sign_aware: false }),
            total_spread_dv01: formatRawAsNumeric({ raw: 12_000, unit: "dv01", sign_aware: false }),
            reinvestment_ratio_1y: formatRawAsNumeric({ raw: 0.18, unit: "pct", sign_aware: false }),
          }),
        }),
      },
    );

    const decisionValues = view.decision?.facts.map((fact) => fact.value).join(" ") ?? "";
    expect(view.stateLabel).toBe("模拟数据");
    expect(view.stateDetail).toContain("不可用于业务决策");
    expect(view.kpis.every((item) => item.value === "模拟数据")).toBe(true);
    expect(view.decision?.conclusion).toContain("模拟");
    expect(view.decision?.detail).toContain("不可用于业务决策");
    expect(view.decision?.actions?.some((action) => action.title === "信用结构复核")).toBe(false);
    expect(decisionValues).not.toContain("42.00%");
    expect(decisionValues).not.toContain("-12.54");
    expect(decisionValues).not.toContain("428");
  });

  it("does not fail the portfolio core read path when only attribution summary fails", () => {
    const view = buildModuleHomeView(
      "portfolio",
      { mode: "real" },
      {
        balanceDates: query({ data: envelope({ report_dates: ["2026-03-31"] }) }),
        balanceOverview: query({
          data: envelope({
            report_date: "2026-03-31",
            position_scope: "all",
            currency_basis: "CNY",
            detail_row_count: 3,
            summary_row_count: 2,
            total_market_value_amount: "100000000",
            total_amortized_cost_amount: "99000000",
            total_accrued_interest_amount: "1000000",
            asset_total_market_value_amount: "80000000",
            liability_total_market_value_amount: "20000000",
            asset_total_amortized_cost_amount: "79000000",
            liability_total_amortized_cost_amount: "20000000",
            asset_total_accrued_interest_amount: "800000",
            liability_total_accrued_interest_amount: "200000",
          }),
        }),
        bondDates: query({ data: envelope({ report_dates: ["2026-04-30"] }) }),
        bondHeadline: query({
          data: envelope({
            report_date: "2026-04-30",
            prev_report_date: null,
            kpis: {
              total_market_value: formatRawAsNumeric({ raw: 100_000_000_000, unit: "yuan", sign_aware: false }),
              unrealized_pnl: formatRawAsNumeric({ raw: 820_000_000, unit: "yuan", sign_aware: true }),
              weighted_ytm: formatRawAsNumeric({ raw: 0.0256, unit: "pct", sign_aware: false }),
              weighted_duration: formatRawAsNumeric({ raw: 3.45, unit: "ratio", sign_aware: false }),
              weighted_coupon: formatRawAsNumeric({ raw: 0.0312, unit: "pct", sign_aware: false }),
              credit_spread_median: formatRawAsNumeric({ raw: 0.0237, unit: "pct", sign_aware: false }),
              total_dv01: formatRawAsNumeric({ raw: -125_430.5, unit: "dv01", sign_aware: false }),
              bond_count: 428,
            },
            prev_kpis: null,
          }),
        }),
        bondRisk: query({
          data: envelope({
            report_date: "2026-04-30",
            total_market_value: formatRawAsNumeric({ raw: 100_000_000_000, unit: "yuan", sign_aware: false }),
            total_dv01: formatRawAsNumeric({ raw: -125_430.5, unit: "dv01", sign_aware: false }),
            weighted_duration: formatRawAsNumeric({ raw: 3.45, unit: "ratio", sign_aware: false }),
            credit_ratio: formatRawAsNumeric({ raw: 0.18, unit: "pct", sign_aware: false }),
            weighted_convexity: formatRawAsNumeric({ raw: 0.12, unit: "ratio", sign_aware: false }),
            total_spread_dv01: formatRawAsNumeric({ raw: 12_000, unit: "dv01", sign_aware: false }),
            reinvestment_ratio_1y: formatRawAsNumeric({ raw: 0.18, unit: "pct", sign_aware: false }),
          }),
        }),
        pnlSummary: query({ error: true }),
      },
    );

    expect(view.stateLabel).toBe("已接入");
    expect(view.decision?.conclusion).not.toContain("读链路异常");
    expect(view.decision?.facts.find((fact) => fact.label === "数据链路")?.value).toContain("已接入");
    expect(view.decision?.facts.find((fact) => fact.label === "归因摘要")?.value).toBe("读取失败");
    expect(view.statuses.find((status) => status.key === "pnl-summary")?.value).toBe("读取失败");
  });

  it("keeps the portfolio first screen stable while slow depth reads are still settling", () => {
    const view = buildModuleHomeView(
      "portfolio",
      { mode: "real" },
      {
        balanceDates: query({ data: envelope({ report_dates: ["2026-05-31"] }) }),
        balanceOverview: query({
          data: envelope({
            report_date: "2026-05-31",
            position_scope: "all",
            currency_basis: "CNY",
            detail_row_count: 3,
            summary_row_count: 2,
            total_market_value_amount: "100000000",
            total_amortized_cost_amount: "99000000",
            total_accrued_interest_amount: "1000000",
            asset_total_market_value_amount: "80000000",
            liability_total_market_value_amount: "20000000",
            asset_total_amortized_cost_amount: "79000000",
            liability_total_amortized_cost_amount: "20000000",
            asset_total_accrued_interest_amount: "800000",
            liability_total_accrued_interest_amount: "200000",
          }),
        }),
        bondDates: query({ data: envelope({ report_dates: ["2026-05-31"] }) }),
        bondHeadline: query({
          data: envelope({
            report_date: "2026-05-31",
            prev_report_date: null,
            kpis: {
              total_market_value: formatRawAsNumeric({ raw: 100_000_000_000, unit: "yuan", sign_aware: false }),
              unrealized_pnl: formatRawAsNumeric({ raw: 820_000_000, unit: "yuan", sign_aware: true }),
              weighted_ytm: formatRawAsNumeric({ raw: 0.0256, unit: "pct", sign_aware: false }),
              weighted_duration: formatRawAsNumeric({ raw: 3.45, unit: "ratio", sign_aware: false }),
              weighted_coupon: formatRawAsNumeric({ raw: 0.0312, unit: "pct", sign_aware: false }),
              credit_spread_median: formatRawAsNumeric({ raw: 0.0237, unit: "pct", sign_aware: false }),
              total_dv01: formatRawAsNumeric({ raw: -125_430.5, unit: "dv01", sign_aware: false }),
              bond_count: 428,
            },
            prev_kpis: null,
          }),
        }),
        bondRisk: query({
          data: envelope({
            report_date: "2026-05-31",
            total_market_value: formatRawAsNumeric({ raw: 100_000_000_000, unit: "yuan", sign_aware: false }),
            total_dv01: formatRawAsNumeric({ raw: -125_430.5, unit: "dv01", sign_aware: false }),
            weighted_duration: formatRawAsNumeric({ raw: 3.45, unit: "ratio", sign_aware: false }),
            credit_ratio: formatRawAsNumeric({ raw: 0.18, unit: "pct", sign_aware: false }),
            weighted_convexity: formatRawAsNumeric({ raw: 0.12, unit: "ratio", sign_aware: false }),
            total_spread_dv01: formatRawAsNumeric({ raw: 12_000, unit: "dv01", sign_aware: false }),
            reinvestment_ratio_1y: formatRawAsNumeric({ raw: 0.18, unit: "pct", sign_aware: false }),
          }),
        }),
        bondPortfolioComparison: query({
          data: envelope({
            report_date: "2026-05-31",
            items: [
              {
                portfolio_name: "FI",
                total_market_value: formatRawAsNumeric({ raw: 100_000_000_000, unit: "yuan", sign_aware: false }),
                bond_count: 428,
                weighted_ytm: formatRawAsNumeric({ raw: 0.0256, unit: "pct", sign_aware: false }),
                weighted_duration: formatRawAsNumeric({ raw: 3.45, unit: "ratio", sign_aware: false }),
                total_dv01: formatRawAsNumeric({ raw: -125_430.5, unit: "dv01", sign_aware: false }),
              },
            ],
          }),
        }),
        bondAssetType: query({ error: true }),
        pnlSummary: query({ loading: true }),
      },
    );

    expect(view.stateLabel).toBe("已接入");
    expect(view.stateDetail).not.toContain("部分组合读链路失败");
    expect(view.decision?.conclusion).not.toContain("读链路异常");
    expect(view.decision?.facts.find((fact) => fact.label === "数据链路")?.value).toContain("已接入");
    expect(view.decision?.facts.find((fact) => fact.label === "归因摘要")?.value).toBe("读取中");
    expect(view.statuses.find((status) => status.key === "bond-structure")?.value).toBe("读取失败");
    expect(view.statuses.find((status) => status.key === "pnl-summary")?.value).toBe("读取中");
  });

  it("shows partial access when portfolio core dates and balance have landed but bond reads are still settling", () => {
    const view = buildModuleHomeView(
      "portfolio",
      { mode: "real" },
      {
        balanceDates: query({ data: envelope({ report_dates: ["2026-05-31"] }) }),
        balanceOverview: query({
          data: envelope({
            report_date: "2026-05-31",
            position_scope: "all",
            currency_basis: "CNY",
            detail_row_count: 3,
            summary_row_count: 2,
            total_market_value_amount: "100000000",
            total_amortized_cost_amount: "99000000",
            total_accrued_interest_amount: "1000000",
            asset_total_market_value_amount: "80000000",
            liability_total_market_value_amount: "20000000",
            asset_total_amortized_cost_amount: "79000000",
            liability_total_amortized_cost_amount: "20000000",
            asset_total_accrued_interest_amount: "800000",
            liability_total_accrued_interest_amount: "200000",
          }),
        }),
        bondDates: query({ data: envelope({ report_dates: ["2026-05-31"] }) }),
        bondHeadline: query({ loading: true }),
        bondRisk: query({ loading: true }),
        bondPortfolioComparison: query({ loading: true }),
        pnlSummary: query({ loading: true }),
      },
    );

    expect(view.stateLabel).toBe("部分接入");
    expect(view.stateDetail).not.toContain("部分组合读链路失败");
    expect(view.decision?.facts.find((fact) => fact.label === "数据链路")?.value).toContain("部分接入");
    expect(view.decision?.facts.find((fact) => fact.label === "归因摘要")?.value).toBe("读取中");
    expect(view.statuses.find((status) => status.key === "bond")?.value).toBe("读取中");
  });

  it("does not attach market detail panels to portfolio home", () => {
    const view = buildModuleHomeView(
      "portfolio",
      { mode: "mock" },
      {
        balanceDates: query({ data: envelope({ report_dates: ["2026-03-31"] }) }),
      },
    );

    expect(view.detailPanels?.some((panel) => panel.key === "key-rate-snapshot") ?? false).toBe(false);
    expect(view.distributionPanels).toBeDefined();
  });

  it("builds risk detail panels from risk tensor and cashflow envelopes", () => {
    const view = buildModuleHomeView(
      "risk",
      { mode: "mock" },
      {
        riskDates: query({
          data: envelope({ report_dates: ["2026-02-28", "2026-01-31"] }),
        }),
        riskTensor: query({
          data: envelope({
            report_date: "2026-02-28",
            portfolio_dv01: "120000.00000000",
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
            bond_count: 8,
            quality_flag: "warning",
            warnings: [],
          }),
        }),
        cashflow: query({
          data: envelope({
            report_date: "2026-02-28",
            duration_gap: formatRawAsNumeric({ raw: 1.25, unit: "ratio", sign_aware: true }),
            asset_duration: formatRawAsNumeric({ raw: 3.8, unit: "ratio", sign_aware: false }),
            liability_duration: formatRawAsNumeric({ raw: 2.55, unit: "ratio", sign_aware: false }),
            equity_duration: formatRawAsNumeric({ raw: 5.2, unit: "ratio", sign_aware: true }),
            rate_sensitivity_1bp: formatRawAsNumeric({ raw: 125_000, unit: "yuan", sign_aware: true }),
            reinvestment_risk_12m: formatRawAsNumeric({ raw: 0.185, unit: "pct", sign_aware: false }),
            monthly_buckets: [],
            top_maturing_assets_12m: [],
            warnings: [],
            computed_at: "2026-06-01T00:00:00Z",
          }),
        }),
      },
    );

    expect(view.stateLabel).toBe("已接入");
    expect(view.kpis.find((item) => item.key === "portfolio-dv01")?.value).toContain("万元");
    expect(view.kpis.find((item) => item.key === "liquidity-gap")?.label).toBe("久期缺口");

    const tensorPanel = view.detailPanels?.find((panel) => panel.key === "risk-tensor-detail");
    expect(tensorPanel?.rows.some((row) => row.label === "KRD 5Y")).toBe(true);
    expect(tensorPanel?.rows.some((row) => row.label === "CS01")).toBe(true);
    expect(tensorPanel?.meta).toContain("risk-tensor");
    expect(tensorPanel?.meta).toContain("2026-02-28");

    const cashflowPanel = view.detailPanels?.find((panel) => panel.key === "cashflow-projection-detail");
    expect(cashflowPanel?.rows.some((row) => row.label === "久期缺口")).toBe(true);
    expect(cashflowPanel?.rows.some((row) => row.label === "12M 再投资风险")).toBe(true);
    expect(cashflowPanel?.meta).toContain("cashflow-projection");
  });

  it("does not attach risk detail panels to market home", () => {
    const view = buildModuleHomeView(
      "market",
      { mode: "mock" },
      {
        choiceLatest: query({
          data: envelope({ read_target: "duckdb", series: [] }),
        }),
      },
    );

    expect(view.detailPanels?.some((panel) => panel.key === "risk-tensor-detail")).toBe(false);
  });

  it("builds performance detail panels from kpi summary and pnl ytd envelopes", () => {
    const view = buildModuleHomeView(
      "performance",
      { mode: "mock" },
      {
        kpiOwners: query({
          data: {
            owners: [{ owner_id: 1, owner_name: "固定收益部" } as never],
            total: 1,
          },
        }),
        kpiSummary: query({
          data: {
            owner_id: 1,
            owner_name: "固定收益部",
            year: 2026,
            period_type: "YEAR",
            period_label: "2026年度",
            period_start_date: "2026-01-01",
            period_end_date: "2026-05-31",
            metrics: [
              {
                metric_id: 101,
                metric_code: "KPI_BOND_YIELD",
                metric_name: "债券投资收益率",
                major_category: "收益类",
                target_value: "4.50",
                unit: "%",
                score_weight: "15.00",
                period_actual_value: "4.20",
                period_score_value: "12.50",
                period_start_date: "2026-01-01",
                period_end_date: "2026-05-31",
                data_date: "2026-05-31",
              },
            ],
            total: 1,
            total_weight: "100.00",
            total_score: "12.50",
          },
        }),
        pnlYtd: query({
          data: envelope({
            year: 2026,
            period_type: "yearly",
            period_label: "2026年累计",
            period_start_date: "2026-01-01",
            period_end_date: "2026-05-31",
            total_pnl: "100000000",
            source_tables: ["fact_formal_pnl_fi"],
            items: [
              {
                row_key: "zqtz",
                sort_order: 1,
                business_type: "债券投资",
                interest_income: "80000000",
                fair_value_change: "10000000",
                capital_gain: "10000000",
                manual_adjustment: "0",
                total_pnl: "100000000",
                avg_balance: "5000000000",
                current_balance: "5000000000",
                balance_yield_pct: "0.02",
                annualized_yield_pct: null,
                ftp_rate_pct: "1.60",
                ftp_cost: null,
                ftp_net_pnl: null,
                ftp_net_annualized_yield_pct: null,
                proportion: "0.65",
                assets_count: 120,
              },
            ],
          }),
        }),
      },
    );

    expect(view.stateLabel).toBe("已接入");
    expect(view.kpis.find((item) => item.key === "business-pnl")?.value).toBe("1 亿元");

    const kpiPanel = view.detailPanels?.find((panel) => panel.key === "kpi-metric-detail");
    expect(kpiPanel?.rows.some((row) => row.label === "债券投资收益率")).toBe(true);
    expect(kpiPanel?.rows[0]?.value).toContain("得分");
    expect(kpiPanel?.meta).toContain("来源 kpi");
    expect(kpiPanel?.meta).toContain("2026年度");

    const pnlPanel = view.detailPanels?.find((panel) => panel.key === "business-pnl-detail");
    expect(pnlPanel?.rows.some((row) => row.label === "债券投资")).toBe(true);
    expect(pnlPanel?.rows[0]?.value).toContain("亿元");
    expect(pnlPanel?.rows[0]?.value).not.toContain("100,000,000");
    expect(pnlPanel?.meta).toContain("来源 pnl/by-business");
    expect(pnlPanel?.meta).toContain("2026年累计");
  });

  it("does not attach performance detail panels to portfolio home", () => {
    const view = buildModuleHomeView(
      "portfolio",
      { mode: "mock" },
      {
        balanceDates: query({ data: envelope({ report_dates: ["2026-03-31"] }) }),
        kpiSummary: query({
          data: {
            owner_id: 1,
            owner_name: "固定收益部",
            year: 2026,
            period_type: "YEAR",
            period_label: "2026年度",
            period_start_date: "2026-01-01",
            period_end_date: "2026-05-31",
            metrics: [],
            total: 0,
            total_weight: "100.00",
            total_score: "0.00",
          },
        }),
      },
    );

    expect(view.detailPanels?.some((panel) => panel.key === "kpi-metric-detail") ?? false).toBe(false);
  });

  it("surfaces performance source errors without frontend backfilling", () => {
    const view = buildModuleHomeView(
      "performance",
      { mode: "real" },
      {
        kpiSummary: query({ error: true }),
        pnlYtd: query({ error: true }),
      },
    );

    expect(view.stateLabel).toBe("读取失败");
    const kpiPanel = view.detailPanels?.find((panel) => panel.key === "kpi-metric-detail");
    expect(kpiPanel?.stateLabel).toBe("读取失败");
    expect(kpiPanel?.rows).toHaveLength(0);
    expect(kpiPanel?.stateDetail).toContain("不使用前端补数");
  });
});
