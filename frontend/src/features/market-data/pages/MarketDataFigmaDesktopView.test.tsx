import { createRef, type ComponentProps } from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MarketDataFigmaDesktopView } from "./MarketDataFigmaDesktopView";

type ViewProps = ComponentProps<typeof MarketDataFigmaDesktopView>;

function buildProps(overrides: Partial<ViewProps> = {}): ViewProps {
  return {
    watchDate: "2026-07-29",
    statusDate: null,
    tickerItems: [],
    rateRows: [],
    moneyRows: [],
    moneySeriesLoading: false,
    moneySeriesError: false,
    analyticalSubstituteCount: 0,
    formalSeriesLoading: false,
    formalSeriesError: false,
    latestSeries: [],
    latestSeriesLoading: false,
    latestSeriesError: false,
    fxFormalStatus: undefined,
    fxFormalLoading: false,
    fxFormalError: false,
    ncdFundingProxy: undefined,
    ncdLoading: false,
    ncdError: false,
    coverageSummary: null,
    coverageSections: [],
    coverageSummaryState: "ready",
    catalogCount: 0,
    catalogLoading: false,
    catalogError: false,
    livermorePayload: undefined,
    livermoreLoading: false,
    livermoreError: false,
    linkagePayload: undefined,
    linkageLoading: false,
    linkageError: false,
    livermoreRef: createRef<HTMLDivElement>(),
    supplyEvents: [],
    supplyLoading: false,
    supplyError: false,
    ...overrides,
  };
}

describe("MarketDataFigmaDesktopView coverage states", () => {
  it("renders every returned coverage item instead of truncating after twelve entries", () => {
    const sections = Array.from({ length: 13 }, (_, index) => ({
      key: `section_${index}`,
      label: `覆盖域 ${index}`,
      status: "ready" as const,
      basis: "formal" as const,
      formal_use_allowed: true,
      quality_flag: "ok" as const,
      fallback_mode: "none" as const,
      vendor_status: "ok" as const,
      row_count: index + 1,
      latest_trade_date: "2026-07-29",
      source_pending: false,
      proxy_only: false,
      message: "coverage regression",
    }));

    render(
      <MarketDataFigmaDesktopView
        {...buildProps({ coverageSections: sections })}
      />,
    );

    expect(screen.getByTestId("market-data-figma-coverage-section_12")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-figma-coverage-macro_catalog")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-figma-coverage-strategy_observation")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-figma-coverage-macro_bond_linkage")).toBeInTheDocument();
  });

  it("shows row-level truth for formal and analytical curve and funding observations", () => {
    const formalRate = {
      key: "formal-rate",
      seriesId: "M003",
      seriesName: "1年期国债到期收益率",
      variety: "国债",
      tenor: "1Y",
      rateText: "1.55%",
      deltaText: "+1bp",
      tradeDate: "2026-07-29",
      origin: "rates_bundle" as const,
      basis: "formal" as const,
      formalUseAllowed: true,
      fallbackMode: "none" as const,
      vendorStatus: "ok" as const,
      sourceVersion: "sv_formal",
      vendorVersion: "vv_formal",
      qualityFlag: "ok" as const,
      sourceMode: "date_slice",
      sparklineValues: [1.53, 1.55],
    };
    const analyticalRate = {
      ...formalRate,
      key: "analytical-rate",
      seriesId: "EMM00166466",
      seriesName: "10年期国债到期收益率",
      tenor: "10Y",
      rateText: "1.71%",
      tradeDate: "2026-07-28",
      origin: "macro_latest" as const,
      basis: "analytical" as const,
      formalUseAllowed: false,
      fallbackMode: "latest_snapshot" as const,
      vendorStatus: "vendor_stale" as const,
      qualityFlag: "warning" as const,
    };
    const analyticalMoney = {
      ...analyticalRate,
      key: "analytical-money",
      seriesId: "M002",
      seriesName: "DR007",
      name: "DR007",
      rateText: "1.88%",
    };

    render(
      <MarketDataFigmaDesktopView
        {...buildProps({
          rateRows: [formalRate, analyticalRate],
          moneyRows: [analyticalMoney],
          analyticalSubstituteCount: 2,
        })}
      />,
    );

    expect(screen.getByTestId("market-data-figma-curve-truth-formal-rate")).toHaveTextContent(
      "正式可用 · 07-29 · 正常",
    );
    expect(screen.getByTestId("market-data-figma-curve-truth-analytical-rate")).toHaveTextContent(
      "分析补位 · 07-28 · 需复核 · 回退快照 · 供应商延迟",
    );
    expect(screen.getByTestId("market-data-figma-funding-truth-analytical-money")).toHaveTextContent(
      "分析补位 · 07-28 · 需复核 · 回退快照 · 供应商延迟",
    );
  });

  it("separates money-market failure from a successful empty formal curve", () => {
    render(
      <MarketDataFigmaDesktopView
        {...buildProps({
          latestSeriesError: true,
          moneySeriesError: true,
        })}
      />,
    );

    const curveEmpty = screen
      .getByTestId("market-data-figma-curve-panel")
      .querySelector(".market-data-figma-empty");
    const fundingEmpty = screen
      .getByTestId("market-data-figma-funding-panel")
      .querySelector(".market-data-figma-empty");
    expect(curveEmpty).not.toHaveTextContent(/\u8bfb\u53d6\u5931\u8d25/);
    expect(fundingEmpty).toHaveTextContent(/\u8bfb\u53d6\u5931\u8d25/);
    expect(
      screen
        .getByRole("heading", { name: "利率曲线与资金面" })
        .closest(".market-data-figma-section-header"),
    ).toHaveTextContent("资金面序列异常");
  });

  it("keeps the operational summary as the first row of the content grid", () => {
    render(<MarketDataFigmaDesktopView {...buildProps()} />);

    expect(screen.getByTestId("market-data-figma-content").firstElementChild).toBe(
      screen.getByTestId("market-data-figma-operational-summary"),
    );
  });

  it("uses the latest received news event instead of the Choice query date for freshness", () => {
    render(
      <MarketDataFigmaDesktopView
        {...buildProps({
          coverageSections: [
            {
              key: "formal_rates",
              label: "正式市场序列",
              status: "ready",
              basis: "formal",
              formal_use_allowed: true,
              quality_flag: "ok",
              fallback_mode: "none",
              vendor_status: "ok",
              row_count: 1,
              latest_trade_date: "2026-07-28",
              source_pending: false,
              proxy_only: false,
              message: "formal market date",
            },
          ],
          newsPayload: {
            total_rows: 1,
            limit: 12,
            offset: 0,
            as_of_date: "2026-07-30",
            excluded_future_rows: 0,
            payload_json_included: false,
            events: [
              {
                event_key: "choice-event-1",
                received_at: "2026-07-27T09:30:00Z",
                group_id: "market",
                content_type: "news",
                serial_id: 1,
                request_id: 1,
                error_code: 0,
                error_msg: "",
                topic_code: "macro",
                item_index: 0,
                payload_text: null,
                display_text: "政策观察",
                payload_json: null,
              },
            ],
          },
        })}
      />,
    );

    expect(screen.getByTestId("market-data-figma-operational-summary")).toHaveTextContent(
      "截至 2026-07-28",
    );
    expect(screen.getByTestId("market-data-figma-coverage-choice_news")).toHaveAttribute(
      "title",
      "数据日期 2026-07-27",
    );
  });

  it("labels a successful empty coverage summary as no data instead of deferred", () => {
    render(
      <MarketDataFigmaDesktopView
        {...buildProps({ coverageSummaryState: "empty" })}
      />,
    );

    const coverage = screen.getByTestId("market-data-figma-coverage-coverage_summary");
    expect(coverage).toHaveAttribute("data-tone", "watch");
    expect(coverage).toHaveTextContent("无数据");
  });

  it("keeps independent envelopes out of coverage when the summary is unavailable", () => {
    render(
      <MarketDataFigmaDesktopView
        {...buildProps({
          coverageSummaryState: "error",
          catalogCount: 7,
          livermoreError: true,
          linkageError: true,
        })}
      />,
    );

    expect(screen.getByTestId("market-data-figma-coverage-summary-state")).toHaveTextContent(
      "覆盖摘要不可用",
    );
    expect(screen.getByTestId("market-data-figma-coverage-coverage_summary")).toBeInTheDocument();
    expect(screen.queryByTestId("market-data-figma-coverage-macro_catalog")).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("market-data-figma-coverage-strategy_observation"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("market-data-figma-coverage-macro_bond_linkage"),
    ).not.toBeInTheDocument();
    expect(screen.getByTestId("market-data-figma-operational-summary")).toHaveTextContent(
      "截至 待返回 · 就绪 0 · 观察/代理 0 · 待接入 0 · 按需 0 · 异常 1",
    );
    expect(screen.getByTestId("market-data-figma-supply-panel")).toHaveTextContent(
      "宏观目录 7 条",
    );
    expect(screen.getByTestId("market-data-figma-strategy-panel")).toHaveTextContent(
      "策略观察加载失败，未使用演示数据替代。",
    );
  });

  it("recognizes linkage evidence returned only in the market-timing method variant", () => {
    render(
      <MarketDataFigmaDesktopView
        {...buildProps({
          linkagePayload: {
            report_date: "2026-07-28",
            environment_score: {},
            portfolio_impact: {},
            top_correlations: [],
            method_variants: {
              conservative: {
                method_meta: { variant: "conservative" },
                top_correlations: [],
              },
              market_timing: {
                method_meta: { variant: "market_timing" },
                top_correlations: [
                  {
                    series_id: "timing-only",
                    series_name: "市场时点证据",
                    target_family: "government",
                    target_tenor: "10Y",
                    correlation_3m: 0.42,
                    correlation_6m: null,
                    correlation_1y: null,
                    lead_lag_days: 1,
                    direction: "positive",
                    alignment_mode: "market_timing",
                  },
                ],
              },
            },
            warnings: [],
            computed_at: "2026-07-29T04:00:00Z",
          },
        })}
      />,
    );

    const linkage = screen.getByTestId("market-data-figma-coverage-macro_bond_linkage");
    expect(linkage).toHaveAttribute("data-tone", "watch");
    expect(linkage).toHaveTextContent("观察");
    expect(linkage).not.toHaveTextContent("无结果");
  });
});
