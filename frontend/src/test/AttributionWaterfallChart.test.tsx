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
    expect(
      option.series[0].data.map((point: { value: number | null }) => point.value),
    ).toEqual([null, null, 0, null]);

    const chart = screen.getByTestId("waterfall-stub");
    expect(chart).toHaveAttribute("data-tooltip-null", "—");
    expect(chart).toHaveAttribute("data-tooltip-undefined", "—");
    expect(chart).toHaveAttribute("data-tooltip-zero", "0.00 亿元");
  });
});
