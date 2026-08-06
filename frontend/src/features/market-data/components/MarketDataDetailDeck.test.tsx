import { createRef, type ComponentProps } from "react";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type {
  ChoiceMacroLatestPoint,
  LivermoreStrategyPayload,
  ResultMeta,
} from "../../../api/contracts";
import { MarketDataDetailDeck } from "./MarketDataDetailDeck";

type DeckProps = ComponentProps<typeof MarketDataDetailDeck>;

function buildMeta(partial: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr-market-data-detail",
    basis: "analytical",
    result_kind: "market_data.detail",
    formal_use_allowed: false,
    source_version: "sv-detail",
    vendor_version: "vv-detail",
    rule_version: "rv-detail",
    cache_version: "cv-detail",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-07-29T04:00:00Z",
    evidence_rows: 12,
    tables_used: ["fact_market_data"],
    ...partial,
  };
}

function buildPoint(index: number, tier: ChoiceMacroLatestPoint["refresh_tier"] = "stable") {
  return {
    series_id: `series-${index}`,
    series_name: `Macro ${index}`,
    trade_date: "2026-07-28",
    value_numeric: index + 1.25,
    unit: "%",
    source_version: "sv-detail",
    vendor_version: "vv-detail",
    refresh_tier: tier,
    fetch_mode: "latest" as const,
    fetch_granularity: "single" as const,
    quality_flag: "ok" as const,
    latest_change: 0.01 * index,
    recent_points: [
      {
        trade_date: "2026-07-27",
        value_numeric: index + 1,
        source_version: "sv-detail",
        vendor_version: "vv-detail",
        quality_flag: "ok" as const,
      },
      {
        trade_date: "2026-07-28",
        value_numeric: index + 1.25,
        source_version: "sv-detail",
        vendor_version: "vv-detail",
        quality_flag: "ok" as const,
      },
    ],
  } satisfies ChoiceMacroLatestPoint;
}

const livermorePayload = {
  as_of_date: "2026-07-24",
  requested_as_of_date: "2026-07-28",
  strategy_name: "Livermore",
  basis: "analytical",
  market_gate: {
    state: "WARM",
    exposure: 0.5,
    passed_conditions: 2,
    available_conditions: 3,
    required_conditions: 2,
    conditions: [],
  },
  rule_readiness: [
    {
      key: "market_gate",
      title: "市场门",
      status: "ready",
      summary: "市场门可用",
      required_inputs: [],
      missing_inputs: [],
    },
  ],
  diagnostics: [{ severity: "warning", code: "STALE_RISK", message: "风险数据较旧" }],
  data_gaps: [{ input_family: "risk", status: "stale", evidence: "截至 2026-06-30" }],
  supported_outputs: ["market_gate"],
  unsupported_outputs: [],
  module_states: [
    {
      key: "market_gate",
      state: "ready",
      render_mode: "primary",
      source_date: "2026-07-24",
      lag_days: 4,
      threshold_days: 5,
      reasons: [],
      evidence_scope: "primary",
      excludes_from_primary: false,
    },
    {
      key: "sector_rank",
      state: "degraded",
      render_mode: "evidence_only",
      source_date: "2026-07-24",
      lag_days: 4,
      threshold_days: 2,
      reasons: ["数据延迟"],
      evidence_scope: "detail",
      excludes_from_primary: true,
    },
  ],
} satisfies LivermoreStrategyPayload;

function buildProps(overrides: Partial<DeckProps> = {}): DeckProps {
  const macroRows = Array.from({ length: 6 }, (_, index) =>
    buildPoint(index, index < 3 ? "stable" : "fallback"),
  );
  const fxRows = Array.from({ length: 6 }, (_, index) => ({
    ...buildPoint(index),
    group_key: "middle_rate" as const,
    series_id: `fx-${index}`,
    series_name: `FX series ${index}`,
    frequency: "daily",
    unit: "rate",
  }));
  const allFalse = {
    catalog: false,
    formalRates: false,
    macroLatest: false,
    fxFormal: false,
    fxAnalytical: false,
    ncd: false,
    bondFutures: false,
    coverage: false,
    linkage: false,
    livermore: false,
    watermarks: false,
    tushare: false,
    supply: false,
  };
  const creditSpreadPoint = {
    series_id: "credit-mtn-5y",
    series_name: "中票利差",
    target_family: "credit_spread",
    target_tenor: "5Y",
    correlation_3m: 0.42,
    correlation_6m: 0.36,
    correlation_1y: 0.28,
    lead_lag_days: 2,
    direction: "positive" as const,
  };
  return {
    detailRef: createRef<HTMLDivElement>(),
    catalog: [
      {
        series_id: "formal-1",
        series_name: "正式目录序列",
        vendor_name: "choice",
        vendor_version: "vv-choice",
        frequency: "daily",
        unit: "%",
        refresh_tier: "stable",
        fetch_mode: "date_slice",
        fetch_granularity: "batch",
        policy_note: "正式稳定读取",
        theme: "macro_market",
        tags: ["macro", "rates"],
      },
      {
        series_id: "series-10",
        series_name: "正式利率序列",
        vendor_name: "choice",
        vendor_version: "vv-choice",
        frequency: "daily",
        unit: "%",
        refresh_tier: "stable",
        fetch_mode: "date_slice",
        fetch_granularity: "batch",
        policy_note: "正式稳定读取",
        theme: "macro_market",
        tags: ["market", "rates"],
      },
      {
        series_id: "series-11",
        series_name: "正式商品序列",
        vendor_name: "choice",
        vendor_version: "vv-choice",
        frequency: "daily",
        unit: "CNY/t",
        refresh_tier: "stable",
        fetch_mode: "date_slice",
        fetch_granularity: "batch",
        policy_note: "正式稳定读取",
        theme: "macro_market",
        tags: ["market", "commodity"],
      },
    ],
    formalRateSeries: [buildPoint(10), buildPoint(11)],
    formalDerivedSpreads: { gov_10y_1y_bp: 42.5 },
    formalUseBlocked: false,
    latestSeries: macroRows,
    macroDerivedSpreads: { ncd_1y_mlf_1y_bp: 18.2 },
    fxFormalStatus: {
      read_target: "duckdb",
      vendor_priority: ["choice"],
      candidate_count: 1,
      materialized_count: 1,
      latest_trade_date: "2026-06-30",
      carry_forward_count: 1,
      rows: [
        {
          base_currency: "USD",
          quote_currency: "CNY",
          pair_label: "USD/CNY",
          series_id: "fx-formal-usdcny",
          series_name: "美元兑人民币",
          vendor_series_code: "USD/CNY",
          trade_date: "2026-06-30",
          observed_trade_date: "2026-06-27",
          mid_rate: 7.1234,
          source_name: "choice_fx",
          vendor_name: "choice",
          vendor_version: "vv-choice",
          source_version: "sv-choice",
          is_business_day: false,
          is_carry_forward: true,
          status: "ok",
        },
      ],
    },
    fxAnalytical: {
      read_target: "duckdb",
      groups: [
        {
          group_key: "middle_rate",
          title: "外汇中间价分析",
          description: "分析观察",
          series: fxRows,
          events: [
            {
              group_key: "fx_event_calendar",
              event_id: "fx-event-1",
              event_date: "2026-07-29",
              event_time: "09:30",
              currency: "USD",
              country: "US",
              event: "利率决议",
              value: "5.25",
              pre_value: "5.25",
              fore_value: "5.25",
              source_version: "sv-event",
              vendor_version: "vv-event",
              quality_flag: "ok",
            },
          ],
        },
      ],
    },
    ncdFundingProxy: {
      as_of_date: "2026-07-24",
      proxy_label: "Tushare Shibor funding proxy",
      is_actual_ncd_matrix: false,
      formal_ncd_matrix_status: {
        status: "source_pending",
        required_shape: "tenor × rating",
        current_proxy_basis: "Shibor",
        choice_status: "missing",
        tushare_status: "proxy_ready",
        missing_requirements: ["rating"],
      },
      rows: [
        {
          row_key: "shibor_fixing",
          label: "Shibor fixing",
          "1M": 1.1,
          "3M": 1.2,
          "6M": 1.3,
          "9M": 1.4,
          "1Y": 1.5,
          quote_count: null,
        },
      ],
      warnings: ["Proxy only"],
    },
    bondFutures: {
      read_target: "duckdb",
      as_of_date: "2026-07-24",
      requested_trade_date: "2026-07-28",
      contract: "T.CFE",
      rows: [
        {
          trade_date: "2026-07-24",
          contract: "T.CFE",
          product_code: "T",
          exchange: "CFFEX",
          member_name: "席位一",
          source_vendor: "choice",
          source_row_no: 1,
          volume: 1000,
          volume_change: 100,
          long_holding: 800,
          long_change: 50,
          short_holding: 600,
          short_change: -20,
          source_version: "sv-futures",
          vendor_version: "vv-futures",
          rule_version: "rv-futures",
        },
      ],
      warnings: [],
    },
    coverageSummary: {
      read_target: "duckdb",
      as_of_date: "2026-07-28",
      generated_at: "2026-07-29T04:00:00Z",
      headline: {
        readiness_label: "7/9 可读",
        formal_fragment_ready: true,
        formal_use_allowed: false,
        analytical_warning_count: 2,
        source_pending_count: 1,
        proxy_only_count: 1,
      },
      sections: [
        {
          key: "ncd_proxy",
          label: "NCD funding proxy",
          status: "proxy_only",
          basis: "analytical",
          formal_use_allowed: false,
          quality_flag: "ok",
          fallback_mode: "none",
          vendor_status: "ok",
          row_count: 1,
          latest_trade_date: "2026-07-24",
          as_of_date: "2026-07-24",
          source_pending: false,
          proxy_only: true,
          message: "Proxy-only NCD funding rows.",
        },
        {
          key: "cash_bond_trades",
          label: "现券成交",
          status: "source_pending",
          basis: "analytical",
          formal_use_allowed: false,
          quality_flag: "warning",
          fallback_mode: "none",
          vendor_status: "vendor_unavailable",
          row_count: 0,
          latest_trade_date: null,
          as_of_date: "2026-07-28",
          source_pending: true,
          proxy_only: false,
          message: "现券成交明细尚未接入。",
        },
      ],
      actions: [
        {
          key: "ncd_proxy",
          label: "NCD funding proxy is proxy-only.",
          severity: "warning",
          target_anchor: "market-data-source-pending-deck",
        },
      ],
    },
    linkage: {
      report_date: "2026-07-28",
      environment_score: { composite_score: 0.42, rate_direction: "down" },
      portfolio_impact: { total_estimated_impact: "120.5" },
      top_correlations: [
        {
          series_id: "corr-1",
          series_name: "M2 同比",
          target_family: "government",
          target_tenor: "10Y",
          correlation_3m: -0.72,
          correlation_6m: -0.65,
          correlation_1y: -0.5,
          lead_lag_days: 3,
          direction: "negative",
          alignment_mode: "conservative",
          sample_size: 45,
          lead_lag_confidence: 0.88,
          effective_observation_span_days: 180,
          winsorized: true,
          zscore_applied: true,
        },
      ],
      research_views: [
        {
          key: "duration",
          stance: "bullish",
          confidence: "medium",
          summary: "久期偏多",
          status: "ready",
        },
      ],
      transmission_axes: [
        {
          axis_key: "liquidity",
          status: "ready",
          stance: "supportive",
          summary: "流动性支持",
        },
      ],
      warnings: ["风险数据截至 2026-06-30"],
      computed_at: "2026-07-29T04:00:00Z",
    },
    creditSegment: "both",
    creditSpreadSlots: [
      { tenor: "3Y", point: null },
      { tenor: "5Y", point: creditSpreadPoint },
      { tenor: "10Y", point: null },
    ],
    livermore: livermorePayload,
    watermarks: {
      summary: {
        catalog_count: 2,
        available_count: 2,
        no_data_count: 0,
        unavailable_count: 0,
        oldest_available_business_date: "2026-06-30",
        newest_available_business_date: "2026-07-28",
        last_successful_ingest: "2026-07-29T03:00:00Z",
      },
      entries: [
        {
          series_id: "wm-fresh",
          series_name: "新鲜序列",
          vendor_name: "choice",
          source_family: "macro",
          domain: "macro",
          frequency: "daily",
          unit: "%",
          row_count: 100,
          latest_business_date: "2026-07-28",
          latest_loaded_at: "2026-07-29T03:00:00Z",
          age_days: 1,
          freshness_tier: "fresh",
          data_status: "available",
        },
        {
          series_id: "wm-expired",
          series_name: "过期序列",
          vendor_name: "choice",
          source_family: "fx",
          domain: "fx",
          frequency: "daily",
          unit: "rate",
          row_count: 80,
          latest_business_date: "2026-06-30",
          latest_loaded_at: "2026-07-01T03:00:00Z",
          age_days: 29,
          freshness_tier: "expired",
          data_status: "available",
        },
      ],
    },
    tushare: {
      money_supply_rows: [
        {
          month: "2026-06-01",
          m0: 10,
          m0_yoy: 1,
          m0_mom: 0.1,
          m1: 20,
          m1_yoy: 2,
          m1_mom: 0.2,
          m2: 30,
          m2_yoy: 3,
          m2_mom: 0.3,
        },
      ],
      money_supply_total_count: 1,
      money_supply_truncated: false,
      eco_cal_rows: [
        {
          event_id: "eco-1",
          event_date: "2026-06-12",
          event_time: "09:30",
          currency: "CNY",
          country: "CN",
          event: "CPI",
          value: "0.2",
          pre_value: "0.1",
          fore_value: "0.3",
        },
      ],
      eco_cal_total_count: 1,
      eco_cal_truncated: false,
      warnings: [],
    },
    supplyEvents: [
      {
        id: "supply-1",
        date: "2026-07-29",
        title: "国债招标",
        kind: "auction",
        severity: "high",
        amount_label: "500 亿元",
        issuer: "财政部",
        note: "10 年期",
        source_url: "https://example.com/source",
        source_label: "公告来源",
      },
    ],
    resultMeta: [{ key: "formal-rates", label: "正式市场序列", meta: buildMeta({ basis: "formal", formal_use_allowed: true }) }],
    loading: allFalse,
    error: allFalse,
    watermarksAccessDenied: false,
    ...overrides,
  };
}

describe("MarketDataDetailDeck", () => {
  it("renders every returned business row across the page data domains", () => {
    render(<MarketDataDetailDeck {...buildProps()} />);

    expect(within(screen.getByTestId("market-data-detail-formal-rates-table")).getByText("Macro 11")).toBeInTheDocument();
    expect(within(screen.getByTestId("market-data-detail-formal-category-rail")).getByText("利率与流动性")).toBeInTheDocument();
    expect(within(screen.getByTestId("market-data-detail-formal-category-rail")).getByText("商品")).toBeInTheDocument();
    expect(within(screen.getByTestId("market-data-detail-macro-latest-table")).getByText("Macro 5")).toBeInTheDocument();
    expect(screen.getByText("正式目录序列")).toBeInTheDocument();
    expect(screen.getByText("Shibor fixing")).toBeInTheDocument();
    expect(screen.getByText("NCD funding proxy")).toBeInTheDocument();
    expect(within(screen.getByTestId("market-data-detail-livermore-modules-table")).getByText("sector_rank")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-detail-livermore-business")).toBeInTheDocument();
    expect(within(screen.getByTestId("market-data-detail-fx-group-middle_rate")).getByText("FX series 5")).toBeInTheDocument();
    expect(screen.getByText("利率决议")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-fx-formal-collapse")).toHaveAttribute(
      "data-expanded",
      "true",
    );
    expect(screen.getByTestId("market-data-fx-formal-table")).toBeInTheDocument();
    expect(screen.getByText(/席位一/)).toBeInTheDocument();
    expect(screen.getByText("45 / 0.880")).toBeInTheDocument();
    expect(screen.getByText("180 天")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-detail-linkage-business")).toBeInTheDocument();
    expect(screen.getAllByText("过期").length).toBeGreaterThan(0);
    expect(screen.getByText("500 亿元")).toBeInTheDocument();
    expect(screen.getByText("30.00")).toBeInTheDocument();
    expect(screen.getByText("M0（单位未提供）")).toBeInTheDocument();
    expect(screen.getByText("CPI")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-detail-tushare-card")).toHaveTextContent(
      "货币供给 1/1 个独立月份（已展示全部）",
    );
    expect(screen.getByTestId("market-data-detail-tushare-card")).toHaveTextContent(
      "经济日历 1/1 个独立事件（已展示全部）",
    );
    expect(screen.getByTestId("market-data-source-pending-contract-note")).toHaveTextContent(
      "尚未接入：现券成交",
    );
    expect(screen.getByTestId("market-data-detail-result-meta-formal-rates")).toBeInTheDocument();
  });

  it("shows access denial separately from a genuine empty watermark result", () => {
    const props = buildProps({
      watermarks: undefined,
      watermarksAccessDenied: true,
      error: {
        ...buildProps().error,
        watermarks: true,
      },
    });
    render(<MarketDataDetailDeck {...props} />);

    expect(screen.getByTestId("market-data-detail-watermark-state")).toHaveTextContent(
      "当前账号缺少数据水位读取权限",
    );
    expect(screen.getByTestId("market-data-detail-watermark-state")).toHaveTextContent(
      "没有把受限结果显示成空数据",
    );
  });

  it("keeps a blocked formal bundle visible without presenting it as formal-ready", () => {
    render(<MarketDataDetailDeck {...buildProps({ formalUseBlocked: true })} />);

    const card = screen.getByTestId("market-data-detail-formal-rates-card");
    expect(card).toHaveClass("market-data-series-category-card--analytical");
    expect(card).toHaveTextContent("formal · blocked");
    expect(card).toHaveTextContent("禁止作为正式口径");
    expect(card).toHaveTextContent("Macro 10");
  });

  it("shows genuine empty watermarks as empty instead of access restricted", () => {
    render(
      <MarketDataDetailDeck
        {...buildProps({
          watermarks: {
            summary: {
              catalog_count: 0,
              available_count: 0,
              no_data_count: 0,
              unavailable_count: 0,
            },
            entries: [],
          },
        })}
      />,
    );

    expect(screen.getByTestId("market-data-detail-watermark-state")).toHaveTextContent(
      "数据水位当前没有返回条目",
    );
    expect(screen.getByTestId("market-data-detail-deck")).toHaveTextContent("水位 0");
    expect(screen.getByTestId("market-data-detail-deck")).not.toHaveTextContent("水位 受限");
  });

  it("shows an empty state when Tushare returns a successful zero-row payload", () => {
    render(
      <MarketDataDetailDeck
        {...buildProps({
          tushare: {
            money_supply_rows: [],
            eco_cal_rows: [],
            warnings: [],
          },
        })}
      />,
    );

    expect(screen.getByTestId("market-data-detail-tushare-state")).toHaveTextContent(
      "补充数据当前没有返回",
    );
  });

  it("shows server totals and truncation instead of implying a limited Tushare window is complete", () => {
    const props = buildProps();
    if (!props.tushare) {
      throw new Error("tushare fixture missing");
    }

    render(
      <MarketDataDetailDeck
        {...props}
        tushare={{
          ...props.tushare,
          money_supply_total_count: 22,
          money_supply_truncated: true,
          eco_cal_total_count: 100,
          eco_cal_truncated: true,
        }}
      />,
    );

    const card = screen.getByTestId("market-data-detail-tushare-card");
    expect(card).toHaveTextContent("货币供给 1/22 个独立月份（仅显示当前窗口）");
    expect(card).toHaveTextContent("经济日历 1/100 个独立事件（仅显示当前窗口）");
  });

  it("does not render the conservative linkage rows twice when they equal the primary rows", () => {
    const props = buildProps();
    if (!props.linkage) {
      throw new Error("linkage fixture missing");
    }
    const duplicateRows = props.linkage.top_correlations;

    render(
      <MarketDataDetailDeck
        {...props}
        linkage={{
          ...props.linkage,
          method_variants: {
            conservative: {
              method_meta: { variant: "conservative" },
              top_correlations: duplicateRows,
            },
            market_timing: {
              method_meta: { variant: "market_timing" },
              top_correlations: [],
            },
          },
        }}
      />,
    );

    const card = screen.getByTestId("market-data-detail-linkage-card");
    expect(within(card).getByText("主相关 / 保守对齐")).toBeInTheDocument();
    expect(within(card).getAllByText("M2 同比")).toHaveLength(1);
    expect(screen.queryByTestId("market-data-detail-linkage-conservative-table")).not.toBeInTheDocument();
  });

  it("applies the active credit segment to a visible credit-spread result panel", () => {
    const props = buildProps();
    const mtnPoint = props.creditSpreadSlots.find((slot) => slot.point)?.point;
    if (!mtnPoint) {
      throw new Error("credit spread fixture missing");
    }
    const urbanPoint = {
      ...mtnPoint,
      series_id: "credit-urban-5y",
      series_name: "城投利差",
    };

    const { rerender } = render(
      <MarketDataDetailDeck
        {...props}
        creditSegment="mtn"
        creditSpreadSlots={[
          { tenor: "3Y", point: null },
          { tenor: "5Y", point: mtnPoint },
          { tenor: "10Y", point: null },
        ]}
      />,
    );

    const filteredPanel = screen.getByTestId("market-data-detail-credit-spread-filtered");
    expect(filteredPanel).toHaveAttribute("data-filter", "mtn");
    expect(filteredPanel).toHaveTextContent("中票利差");
    expect(filteredPanel).not.toHaveTextContent("城投利差");

    rerender(
      <MarketDataDetailDeck
        {...props}
        creditSegment="urban"
        creditSpreadSlots={[
          { tenor: "3Y", point: null },
          { tenor: "5Y", point: urbanPoint },
          { tenor: "10Y", point: null },
        ]}
      />,
    );

    expect(filteredPanel).toHaveAttribute("data-filter", "urban");
    expect(filteredPanel).toHaveTextContent("城投利差");
    expect(filteredPanel).not.toHaveTextContent("中票利差");
  });
});
