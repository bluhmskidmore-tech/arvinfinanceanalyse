import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: ({ option }: { option?: unknown }) => {
    const typed = option as {
      tooltip?: { valueFormatter?: (value: unknown) => string };
    };
    const formatter = typed.tooltip?.valueFormatter;
    return (
      <div
        data-testid="waterfall-stub"
        data-tooltip-null={formatter?.(null)}
        data-tooltip-undefined={formatter?.(undefined)}
        data-tooltip-zero={formatter?.(0)}
      >
        {JSON.stringify(option ?? null)}
      </div>
    );
  },
}));

import type { Numeric, VolumeRateAttributionPayload } from "../api/contracts";
import { AttributionWaterfallChart } from "../features/pnl-attribution/components/AttributionWaterfallChart";

function num(raw: number | null): Numeric {
  return { raw, unit: "yuan", display: "", precision: 2, sign_aware: true };
}

function undefinedNum(): Numeric {
  return { ...num(null), raw: undefined } as unknown as Numeric;
}

describe("AttributionWaterfallChart", () => {
  it("keeps missing values as gaps and preserves real zero", () => {
    const data = {
      current_period: "2026-06",
      previous_period: "2026-05",
      compare_type: "mom",
      total_current_pnl: undefinedNum(),
      total_previous_pnl: num(null),
      total_pnl_change: num(null),
      total_volume_effect: num(null),
      total_rate_effect: num(0),
      total_interaction_effect: num(null),
      total_recon_error: num(null),
      items: [],
      has_previous_data: true,
    } satisfies VolumeRateAttributionPayload;

    render(
      <AttributionWaterfallChart
        data={data}
        state={{ kind: "ok" }}
        onRetry={vi.fn()}
      />,
    );

    const option = JSON.parse(
      screen.getByTestId("waterfall-stub").textContent ?? "null",
    );
    // 交叉效应缺失时保留断点列，不再被静默省略。
    expect(option.xAxis.data).toEqual([
      "上期损益",
      "规模效应",
      "利率效应",
      "交叉效应",
      "当期损益",
    ]);
    expect(
      option.series[0].data.map((point: { value: number | null }) => point.value),
    ).toEqual([null, null, 0, null, null]);

    const chart = screen.getByTestId("waterfall-stub");
    expect(chart).toHaveAttribute("data-tooltip-null", "—");
    expect(chart).toHaveAttribute("data-tooltip-undefined", "—");
    expect(chart).toHaveAttribute("data-tooltip-zero", "0.00 亿元");
  });

  it("keeps a tiny interaction effect (<0.001 yi) visible instead of dropping it", () => {
    const data = {
      current_period: "2026-06",
      previous_period: "2026-05",
      compare_type: "mom",
      total_current_pnl: num(500_000_000),
      total_previous_pnl: num(400_000_000),
      total_pnl_change: num(100_000_000),
      total_volume_effect: num(60_000_000),
      total_rate_effect: num(39_950_000),
      total_interaction_effect: num(50_000),
      total_recon_error: num(0),
      items: [],
      has_previous_data: true,
    } satisfies VolumeRateAttributionPayload;

    render(
      <AttributionWaterfallChart
        data={data}
        state={{ kind: "ok" }}
        onRetry={vi.fn()}
      />,
    );

    const option = JSON.parse(
      screen.getByTestId("waterfall-stub").textContent ?? "null",
    );
    expect(option.xAxis.data).toContain("交叉效应");
    const crossIndex = option.xAxis.data.indexOf("交叉效应");
    // 满数据走标准归因桥：series[0] 是透明垫柱，可见效应柱在 id="bridge-bars"。
    const bridgeBars = option.series.find(
      (series: { id?: string }) => series.id === "bridge-bars",
    );
    expect(bridgeBars).toBeTruthy();
    // 微小交叉效应仍以真实柱高（|Δ|=0.0005 亿）保留，不被阈值静默省略。
    expect(bridgeBars.data[crossIndex].value).toBeCloseTo(0.0005, 6);
    // 图例金额以亿元展示（0.05 百万元 = +0.00 亿）。
    expect(screen.getByText(/交叉效应\s*\+0\.00 亿/)).toBeInTheDocument();
  });

  it("shows the unexplained residual in the legend when total_recon_error is present", () => {
    const data = {
      current_period: "2026-06",
      previous_period: "2026-05",
      compare_type: "mom",
      total_current_pnl: num(500_000_000),
      total_previous_pnl: num(400_000_000),
      total_pnl_change: num(100_000_000),
      total_volume_effect: num(60_000_000),
      total_rate_effect: num(30_000_000),
      total_interaction_effect: num(5_000_000),
      total_recon_error: num(5_000_000),
      items: [],
      has_previous_data: true,
    } satisfies VolumeRateAttributionPayload;

    render(
      <AttributionWaterfallChart
        data={data}
        state={{ kind: "ok" }}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByText(/未解释差额\s*\+0\.05 亿/)).toBeInTheDocument();
    expect(screen.getByText(/当期损益\s*\+5\.00 亿/)).toBeInTheDocument();
  });

  it("omits the residual legend entry when total_recon_error is missing", () => {
    const data = {
      current_period: "2026-06",
      previous_period: "2026-05",
      compare_type: "mom",
      total_current_pnl: num(500_000_000),
      total_previous_pnl: num(400_000_000),
      total_pnl_change: num(100_000_000),
      total_volume_effect: num(60_000_000),
      total_rate_effect: num(30_000_000),
      total_interaction_effect: num(5_000_000),
      total_recon_error: num(null),
      items: [],
      has_previous_data: true,
    } satisfies VolumeRateAttributionPayload;

    render(
      <AttributionWaterfallChart
        data={data}
        state={{ kind: "ok" }}
        onRetry={vi.fn()}
      />,
    );

    // 说明文案仍会提到「未解释差额」概念，这里只断言图例金额行不存在。
    expect(screen.queryByText(/未解释差额\s*[+-]?\d/)).not.toBeInTheDocument();
  });
});
