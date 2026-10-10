import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ApiEnvelope, FxAnalyticalPayload, FxAnalyticalSeriesPoint } from "../api/contracts";
import { EM_DASH } from "../utils/format";

const chartCard = vi.hoisted(() => ({ render: vi.fn() }));

// Only the canvas boundary is replaced. The FX deck/card/table and chart-option builder are real.
vi.mock("../components/charts/ChartCard", () => ({
  ChartCard: (props: { testId?: string; option: unknown }) => {
    chartCard.render(props);
    return <figure data-testid={props.testId} />;
  },
}));

import { MarketDataFxThemeCard } from "../features/market-data/components/MarketDataFxThemeCard";
import type { FxAnalyticalGroup } from "../api/contracts";

// Exercise the current theme-card consumer; the obsolete deck is not restored.
function FxGroups({ groups, groupTitle }: { groups: FxAnalyticalGroup[]; groupTitle: (title: string) => string }) {
  return <>{groups.map((group) => <MarketDataFxThemeCard key={group.group_key} group={group} title={groupTitle(group.title)} />)}</>;
}
import { buildMarketDataPageModel } from "../features/market-data/pages/marketDataPageModel";

const FALLBACK_WARNING =
  "SYNTHETIC FX_USDCNY: selected 2026-10-05 after invalid 2026-10-06; latest_change unavailable.";

function fxPoint(overrides: Partial<FxAnalyticalSeriesPoint> = {}): FxAnalyticalSeriesPoint {
  return {
    group_key: "middle_rate",
    series_id: "FX_USDCNY",
    series_name: "中间价:美元兑人民币",
    trade_date: "2026-10-05",
    value_numeric: 7.2,
    frequency: "daily",
    unit: "CNY/USD",
    source_version: "synthetic_source_20261005",
    vendor_version: "synthetic_vendor_20261005",
    refresh_tier: "stable",
    fetch_mode: "date_slice",
    fetch_granularity: "batch",
    policy_note: "Synthetic consumer-control fixture",
    quality_flag: "warning",
    latest_change: null,
    // Match the backend's newest-first raw trail, including the invalid observation.
    recent_points: [
      {
        trade_date: "2026-10-06",
        value_numeric: 0,
        source_version: "synthetic_source_20261006",
        vendor_version: "synthetic_vendor_20261006",
        quality_flag: "warning",
      },
      {
        trade_date: "2026-10-05",
        value_numeric: 7.2,
        source_version: "synthetic_source_20261005",
        vendor_version: "synthetic_vendor_20261005",
        quality_flag: "ok",
      },
      {
        trade_date: "2026-10-04",
        value_numeric: 7.1,
        source_version: "synthetic_source_20261004",
        vendor_version: "synthetic_vendor_20261004",
        quality_flag: "ok",
      },
    ],
    ...overrides,
  };
}

function fxEnvelope(series: FxAnalyticalSeriesPoint[]): ApiEnvelope<FxAnalyticalPayload> {
  return {
    result_meta: {
      trace_id: "synthetic_fx_consumer_control",
      basis: "analytical",
      result_kind: "market-data.fx.analytical",
      formal_use_allowed: false,
      source_version: "synthetic_source_20261005",
      vendor_version: "synthetic_vendor_20261005",
      rule_version: "synthetic_fx_control",
      cache_version: "synthetic_fx_control",
      quality_flag: "warning",
      vendor_status: "ok",
      fallback_mode: "none",
      scenario_flag: false,
      generated_at: "2026-10-06T12:00:00Z",
      filters_applied: { warnings: [FALLBACK_WARNING] },
    },
    result: {
      read_target: "duckdb",
      groups: [{
        group_key: "middle_rate",
        title: "Analytical FX: middle-rates",
        description: "Synthetic FX consumer controls",
        series,
      }],
    },
  };
}

describe("MS-010 compatible FX consumers (not backend defect-baseline evidence)", () => {
  beforeEach(() => {
    // Freeze only Date, leaving React/antd timers real. Expose the actual responsive date column.
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-10-06T12:00:00Z"));
    chartCard.render.mockClear();
    vi.spyOn(window, "matchMedia").mockImplementation((query) => ({
      matches: /min-width:\s*(576|768|992|1200)px/.test(query),
      media: query,
      onchange: null,
      addListener: () => undefined,
      removeListener: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false,
    }));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("preserves selected observation lineage, null delta and API warnings in the page model", () => {
    const envelope = fxEnvelope([fxPoint()]);
    const before = JSON.stringify(envelope);
    const model = buildMarketDataPageModel({ fxAnalyticalEnvelope: envelope });
    const selected = model.fxAnalyticalGroups[0].series[0];

    expect(model.fxAnalyticalGroups).toBe(envelope.result.groups);
    expect(selected).toMatchObject({
      trade_date: "2026-10-05",
      value_numeric: 7.2,
      source_version: "synthetic_source_20261005",
      vendor_version: "synthetic_vendor_20261005",
      quality_flag: "warning",
      latest_change: null,
      refresh_tier: "stable",
    });
    expect(model.fxAnalyticalSeriesCount).toBe(1);
    expect(model.fxAnalyticalMeta).toBe(envelope.result_meta);
    expect(model.fxAnalyticalMeta?.filters_applied?.warnings).toEqual([FALLBACK_WARNING]);
    expect(model.evidenceLines.fxAnalytical).toContain("仅分析使用 / 部分缺失");
    expect(model.evidenceLines.fxAnalytical).toContain("暂不可用于正式决策");
    // The current generic quality summary does not expose the API's detailed fallback reason.
    expect(model.evidenceLines.fxAnalytical).not.toContain(FALLBACK_WARNING);
    expect(JSON.stringify(envelope)).toBe(before);
  });

  it("renders mixed null, real zero and negative deltas through the real FX deck/card/table", () => {
    const model = buildMarketDataPageModel({
      fxAnalyticalEnvelope: fxEnvelope([
        fxPoint(),
        fxPoint({ series_id: "FX_ZERO", series_name: "Synthetic unchanged rate", latest_change: 0 }),
        fxPoint({ series_id: "FX_NEGATIVE", series_name: "Synthetic falling rate", latest_change: -0.05 }),
      ]),
    });
    render(<FxGroups groups={model.fxAnalyticalGroups} groupTitle={(title) => title} />);

    const card = screen.getByTestId("market-data-fx-group-card-middle_rate");
    expect(within(card).getByRole("columnheader", { name: "变动" })).toBeInTheDocument();
    const fallback = screen.getByTestId("market-data-fx-series-middle_rate-FX_USDCNY");
    const missingDelta = fallback.querySelector(".market-data-series-compact-col-delta");
    expect(missingDelta?.textContent).toBe(EM_DASH);
    expect(missingDelta?.querySelector(".market-data-terminal-ticker-delta")).toBeNull();
    expect(fallback.querySelector(".market-data-series-compact-value")?.textContent).toBe("7.2");
    expect(fallback.querySelector(".market-data-series-compact-date")?.textContent).toBe("2026-10-05");
    expect(fallback.querySelector(".market-data-series-compact-prior")?.textContent).toBe("10-04 7.10");

    const zero = screen.getByTestId("market-data-fx-series-middle_rate-FX_ZERO")
      .querySelector(".market-data-terminal-ticker-delta");
    expect(zero?.textContent).toBe("0 CNY/USD");
    expect(zero).toHaveAttribute("data-tone", "flat");
    const negative = screen.getByTestId("market-data-fx-series-middle_rate-FX_NEGATIVE")
      .querySelector(".market-data-terminal-ticker-delta");
    expect(negative?.textContent).toBe("-0.05 CNY/USD");
    expect(negative).toHaveAttribute("data-tone", "down");
    expect(card).not.toHaveTextContent(FALLBACK_WARNING);
  });

  it("omits the sparse change column when every FX card row has a null change", () => {
    const group = fxEnvelope([
      fxPoint(),
      fxPoint({ series_id: "FX_SINGLE", series_name: "Synthetic single observation", recent_points: [] }),
    ]).result.groups[0];
    render(<MarketDataFxThemeCard group={group} title={group.title} />);

    const card = screen.getByTestId("market-data-fx-group-card-middle_rate");
    expect(within(card).queryByRole("columnheader", { name: "变动" })).not.toBeInTheDocument();
    expect(card.querySelector(".market-data-series-compact-col-delta")).toBeNull();
    expect(card.querySelector(".market-data-terminal-ticker-delta")).toBeNull();
    expect(screen.getByTestId("market-data-fx-series-middle_rate-FX_USDCNY")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-fx-series-middle_rate-FX_SINGLE")).toBeInTheDocument();
  });

  it("retains the raw recent trail including invalid latest zero through the inline chart option", () => {
    const envelope = fxEnvelope([fxPoint()]);
    const before = JSON.stringify(envelope);
    const model = buildMarketDataPageModel({ fxAnalyticalEnvelope: envelope });
    const point = model.fxAnalyticalGroups[0].series[0];
    expect(point.recent_points).toBe(envelope.result.groups[0].series[0].recent_points);
    render(<FxGroups groups={model.fxAnalyticalGroups} groupTitle={(title) => title} />);
    expect(screen.getByTestId("market-data-fx-series-middle_rate-FX_USDCNY")
      .querySelector(".market-data-terminal-sparkline path")).not.toBeNull();
    fireEvent.click(screen.getByTestId("market-data-fx-series-middle_rate-chart-toggle-FX_USDCNY"));

    const chartId = "market-data-fx-series-middle_rate-time-chart-FX_USDCNY";
    expect(screen.getByTestId(chartId)).toBeInTheDocument();
    const props = chartCard.render.mock.calls.find(([entry]) => entry.testId === chartId)?.[0];
    expect(props?.option).toMatchObject({
      xAxis: { data: ["2026-10-04", "2026-10-05", "2026-10-06"] },
      series: [{ data: [7.1, 7.2, 0] }],
    });
    expect(point.latest_change).toBeNull();
    expect(point.trade_date).toBe("2026-10-05");
    expect(JSON.stringify(envelope)).toBe(before);
  });
});
