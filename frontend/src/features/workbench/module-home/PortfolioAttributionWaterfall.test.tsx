import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../../lib/echarts", () => ({
  default: ({ option }: { option: unknown }) => (
    <pre data-testid="portfolio-attribution-chart">{JSON.stringify(option)}</pre>
  ),
}));
vi.mock("./useDeferredChartMount", () => ({
  useDeferredChartMount: () => ({ containerRef: vi.fn(), ready: true, onChartReady: vi.fn() }),
}));

import type { Numeric, VolumeRateAttributionPayload } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import { AttributionWaterfallChart } from "../../pnl-attribution/components/AttributionWaterfallChart";
import { PortfolioAttributionWaterfall } from "./PortfolioAttributionWaterfall";

function num(raw: number | null): Numeric {
  return { raw, unit: "yuan", display: raw === null ? EM_DASH : String(raw), precision: 2, sign_aware: true };
}

function payload(): VolumeRateAttributionPayload {
  return {
    current_period: "2026-08",
    previous_period: "2026-07",
    compare_type: "mom",
    attribution_basis: "interest_income_and_direct_pnl",
    total_current_pnl: num(200_000_000),
    total_previous_pnl: num(100_000_000),
    total_pnl_change: num(100_000_000),
    total_volume_effect: num(10_000_000),
    total_rate_effect: num(15_000_000),
    total_interaction_effect: num(50_000),
    total_fair_value_effect: num(80_000_000),
    total_capital_gain_effect: num(-5_000_000),
    total_manual_adjustment_effect: num(0),
    total_recon_error: num(-50_000),
    has_previous_data: true,
    items: [],
  };
}

describe("portfolio attribution uses the same decomposition as the attribution page", () => {
  it("shows all six effects and residual without dropping small values", () => {
    const data = payload();
    render(<>
      <PortfolioAttributionWaterfall payload={data} />
      <AttributionWaterfallChart data={data} state={{ kind: "ok" }} onRetry={vi.fn()} />
    </>);
    const [home, attribution] = screen.getAllByTestId("portfolio-attribution-chart")
      .map((chart) => JSON.parse(chart.textContent ?? "null"));
    expect(home.xAxis.data).toEqual(attribution.xAxis.data);
    expect(home.xAxis.data).toEqual([
      "上期损益", "利息规模效应", "利息收益率效应", "交叉效应",
      "公允价值变动", "投资收益变动", "手工调整变动", "未解释差额", "当期损益",
    ]);
    expect(home.series[0].data.map((point: { value: number }) => point.value))
      .toEqual([1, 0.1, 0.15, 0.0005, 0.8, -0.05, 0, -0.0005, 2]);
    expect(screen.getByText(/2026-07 至 2026-08；利息收益率按期末市值、非年化/)).toBeInTheDocument();
  });

  it("keeps null direct amounts, interaction, and residual as named gaps", () => {
    render(<PortfolioAttributionWaterfall payload={{
      ...payload(),
      total_interaction_effect: null,
      total_fair_value_effect: num(null),
      total_recon_error: null,
    }} />);
    const option = JSON.parse(screen.getByTestId("portfolio-attribution-chart").textContent ?? "null");
    for (const label of ["交叉效应", "公允价值变动", "未解释差额"]) {
      expect(option.series[0].data[option.xAxis.data.indexOf(label)].value).toBeNull();
    }
    expect(option.series[0].data[option.xAxis.data.indexOf("手工调整变动")].value).toBe(0);
  });

  it("does not render a decomposition without a previous period", () => {
    render(<PortfolioAttributionWaterfall payload={{ ...payload(), has_previous_data: false }} />);
    expect(screen.queryByTestId("portfolio-attribution-chart")).not.toBeInTheDocument();
  });
});
