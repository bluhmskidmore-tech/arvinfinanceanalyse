import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../../lib/echarts", () => ({
  default: ({ option }: { option: unknown }) => (
    <pre data-testid="direct-pnl-chart">{JSON.stringify(option)}</pre>
  ),
}));

import type { Numeric, VolumeRateAttributionPayload } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import { AttributionWaterfallChart } from "./AttributionWaterfallChart";
import { VolumeRateBridgePanel } from "./PnlAttributionVolumeRateTab";
import { VolumeRateAnalysisChart } from "./VolumeRateAnalysisChart";
import { buildVolumeRateBridgeSummary } from "./pnlAttributionViewModel";

function num(raw: number | null, rawText?: string): Numeric {
  return {
    raw,
    ...(rawText === undefined ? {} : { raw_text: rawText }),
    unit: "yuan",
    display: raw === null ? EM_DASH : String(raw),
    precision: 2,
    sign_aware: true,
  };
}

function directPayload(): VolumeRateAttributionPayload {
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
    total_interaction_effect: num(5_000_000),
    total_fair_value_effect: num(60_000_000),
    total_capital_gain_effect: num(5_000_000),
    total_manual_adjustment_effect: num(1_000_000),
    total_recon_error: num(4_000_000),
    has_previous_data: true,
    items: [],
  };
}

describe("interest attribution and direct non-interest changes", () => {
  it("includes every direct effect in coverage and preserves the remaining residual", () => {
    const data = directPayload();
    const summary = buildVolumeRateBridgeSummary(data)!;
    expect(summary).toMatchObject({
      includesDirectPnl: true,
      fairValueEffect: 60_000_000,
      capitalGainEffect: 5_000_000,
      manualAdjustmentEffect: 1_000_000,
      explainedEffect: 96_000_000,
      unexplainedEffect: 4_000_000,
      coveragePct: 96,
      status: "residual",
    });
    render(<VolumeRateBridgePanel data={data} summary={summary} />);
    expect(screen.getByText("解释覆盖 96.0%")).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /公允价值变动/ })).toHaveTextContent("+0.60 亿");
    expect(screen.getByRole("row", { name: /投资收益变动/ })).toHaveTextContent("+0.05 亿");
    expect(screen.getByRole("row", { name: /手工调整变动/ })).toHaveTextContent("+0.01 亿");
    expect(screen.getByRole("row", { name: /未解释差额/ })).toHaveTextContent("+0.04 亿");
    expect(screen.getByText(/当月利息收益率 = 当月利息收入 ÷ 期末市值，非年化/)).toBeInTheDocument();
  });

  it("uses exact decimal text for the six-effect sum and coverage", () => {
    const summary = buildVolumeRateBridgeSummary({
      ...directPayload(),
      total_current_pnl: num(12_000, "12000"),
      total_previous_pnl: num(2_000, "1999.999999999999"),
      total_pnl_change: num(10_000, "10000.000000000001"),
      total_volume_effect: num(0.1, "0.1"),
      total_rate_effect: num(0.2, "0.2"),
      total_interaction_effect: num(0.3, "0.3"),
      total_fair_value_effect: num(11_999.1, "11999.1"),
      total_capital_gain_effect: num(0.1, "0.1"),
      total_manual_adjustment_effect: num(0.2, "0.2"),
      total_recon_error: num(-2_000, "-1999.999999999999"),
    });
    expect(summary?.explainedEffect).toBe(12_000);
    expect(summary?.coveragePct).toBeCloseTo(120, 12);
    expect(summary?.effectSharesEligible).toBe(true);
  });

  it.each([null, num(null), undefined])("keeps a missing new effect missing (%j)", (missing) => {
    const data = { ...directPayload(), total_fair_value_effect: missing };
    const summary = buildVolumeRateBridgeSummary(data)!;
    expect(summary).toMatchObject({
      includesDirectPnl: true,
      fairValueEffect: undefined,
      explainedEffect: undefined,
      coveragePct: undefined,
      status: "missing",
    });
    render(<VolumeRateBridgePanel data={data} summary={summary} />);
    expect(screen.getByTestId("volume-rate-bridge-panel")).toHaveTextContent("归因字段不完整");
    const row = screen.getByRole("row", { name: /公允价值变动/ });
    expect(within(row).getAllByText(EM_DASH)).toHaveLength(2);
  });

  it("preserves the three-effect presentation for an older payload without direct fields", () => {
    const data = directPayload();
    delete data.attribution_basis;
    delete data.total_fair_value_effect;
    delete data.total_capital_gain_effect;
    delete data.total_manual_adjustment_effect;
    data.total_recon_error = num(70_000_000);
    const summary = buildVolumeRateBridgeSummary(data)!;
    expect(summary).toMatchObject({ includesDirectPnl: false, explainedEffect: 30_000_000, coveragePct: 30 });
    render(<VolumeRateBridgePanel data={data} summary={summary} />);
    expect(screen.queryByRole("row", { name: /公允价值变动/ })).not.toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(5);
  });

  it("keeps all six effect columns and the residual in a complete waterfall", () => {
    render(<AttributionWaterfallChart data={directPayload()} state={{ kind: "ok" }} onRetry={vi.fn()} />);
    const option = JSON.parse(screen.getByTestId("direct-pnl-chart").textContent ?? "null");
    expect(option.xAxis.data).toEqual([
      "上期损益", "利息规模效应", "利息收益率效应", "交叉效应",
      "公允价值变动", "投资收益变动", "手工调整变动", "未解释差额", "当期损益",
    ]);
    const bars = option.series.find((series: { id?: string }) => series.id === "bridge-bars");
    expect(bars.data.map((point: { value: number }) => point.value)).toEqual(
      [1, 0.1, 0.15, 0.05, 0.6, 0.05, 0.01, 0.04, 2].map((value) => expect.closeTo(value, 8)),
    );
    const connectors = option.series.find((series: { id?: string }) => series.id === "bridge-connectors");
    expect(connectors.data.at(-1)[1]).toBeCloseTo(2, 8);
    expect(screen.getByText("未解释差额 +0.04 亿")).toBeInTheDocument();
  });

  it("retains missing direct effects as labeled gaps while showing a genuine zero", () => {
    const data = {
      ...directPayload(),
      total_fair_value_effect: null,
      total_manual_adjustment_effect: num(0),
    };
    render(<AttributionWaterfallChart data={data} state={{ kind: "ok" }} onRetry={vi.fn()} />);
    const option = JSON.parse(screen.getByTestId("direct-pnl-chart").textContent ?? "null");
    expect(option.series.some((series: { id?: string }) => series.id === "bridge-bars")).toBe(false);
    expect(option.series[0].data[option.xAxis.data.indexOf("公允价值变动")].value).toBeNull();
    expect(option.series[0].data[option.xAxis.data.indexOf("手工调整变动")].value).toBe(0);
    expect(screen.getByText("公允价值变动 —")).toBeInTheDocument();
    expect(screen.getByText("手工调整变动 +0.00 亿")).toBeInTheDocument();
  });

  it("shows direct changes and missing amounts for asset and liability detail rows", () => {
    const data = directPayload();
    data.items = ["asset", "liability"].map((categoryType) => ({
      category: categoryType === "asset" ? "债券" : "同业负债",
      category_type: categoryType,
      level: 0,
      current_scale: num(1_000_000_000),
      previous_scale: num(900_000_000),
      current_pnl: num(200_000_000),
      previous_pnl: num(100_000_000),
      current_yield_pct: null,
      previous_yield_pct: null,
      pnl_change: num(100_000_000),
      pnl_change_pct: null,
      volume_effect: num(10_000_000),
      rate_effect: num(15_000_000),
      interaction_effect: num(5_000_000),
      fair_value_effect: num(60_000_000),
      capital_gain_effect: num(5_000_000),
      manual_adjustment_effect: null,
      attrib_sum: num(95_000_000),
      recon_error: num(5_000_000),
      volume_contribution_pct: null,
      rate_contribution_pct: null,
    }));
    render(<VolumeRateAnalysisChart data={data} state={{ kind: "ok" }} onRetry={vi.fn()} />);
    expect(screen.getByRole("columnheader", { name: "期末规模·当期" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "当月利息收益率·当期" })).toBeInTheDocument();
    for (const category of ["债券", "同业负债"]) {
      const cells = within(screen.getByRole("row", { name: new RegExp(category) })).getAllByRole("cell");
      expect(cells[10]).toHaveTextContent("0.6000");
      expect(cells[11]).toHaveTextContent("0.0500");
      expect(cells[12]).toHaveTextContent(EM_DASH);
      expect(cells[14]).toHaveTextContent("0.0500");
    }
  });
});
