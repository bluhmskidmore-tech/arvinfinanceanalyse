import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../../lib/echarts", () => ({
  default: () => <div data-testid="volume-rate-echarts-stub" />,
}));

import type { Numeric, VolumeRateAttributionPayload } from "../../../api/contracts";
import type { DataSectionState } from "../../../components/DataSection.types";
import { VolumeRateAnalysisChart } from "./VolumeRateAnalysisChart";

function numeric(
  raw: number | null,
  unit: Numeric["unit"],
  display: string,
  signAware = false,
): Numeric {
  return {
    raw,
    unit,
    display,
    precision: 2,
    sign_aware: signAware,
  };
}

function renderWith(state: DataSectionState, data: VolumeRateAttributionPayload | null = null) {
  render(<VolumeRateAnalysisChart data={data} state={state} onRetry={vi.fn()} />);
}

describe("VolumeRateAnalysisChart state=loading", () => {
  it("shows loading placeholder", () => {
    renderWith({ kind: "loading" });
    expect(screen.getByTestId("data-section-loading")).toBeInTheDocument();
  });
});

describe("VolumeRateAnalysisChart state=error", () => {
  it("shows error with retry", () => {
    renderWith({ kind: "error", message: "fetch failed" });
    expect(screen.getByTestId("data-section-error")).toBeInTheDocument();
  });
});

describe("VolumeRateAnalysisChart state=empty", () => {
  it("shows empty placeholder when no data", () => {
    renderWith({ kind: "empty" });
    expect(screen.getByTestId("data-section-empty")).toBeInTheDocument();
  });
});

describe("VolumeRateAnalysisChart state=vendor_unavailable", () => {
  it("shows vendor unavailable placeholder", () => {
    renderWith({ kind: "vendor_unavailable", details: "pnl unavailable" });
    expect(screen.getByTestId("data-section-vendor-unavailable")).toBeInTheDocument();
  });
});

describe("VolumeRateAnalysisChart state=fallback", () => {
  it("renders fallback banner", () => {
    renderWith({ kind: "fallback", effective_date: "2026-03-31" }, null);
    expect(screen.getByTestId("data-section-fallback-banner")).toBeInTheDocument();
  });
});

describe("VolumeRateAnalysisChart data contract", () => {
  it("renders backend yield pct fields using governed display values", () => {
    const data = {
      current_period: "2026-04",
      previous_period: "2026-03",
      compare_type: "mom",
      total_current_pnl: numeric(110_000, "yuan", "+0.00", true),
      total_previous_pnl: numeric(100_000, "yuan", "+0.00", true),
      total_pnl_change: numeric(10_000, "yuan", "+0.00", true),
      total_volume_effect: numeric(0, "yuan", "+0.00", true),
      total_rate_effect: numeric(10_000, "yuan", "+0.00", true),
      total_interaction_effect: numeric(0, "yuan", "+0.00", true),
      has_previous_data: true,
      items: [
        {
          category: "A",
          category_type: "asset",
          level: 0,
          current_scale: numeric(100_000_000, "yuan", "1.00"),
          current_pnl: numeric(110_000, "yuan", "+0.00", true),
          current_yield_pct: numeric(0.0011, "pct", "+0.11%", true),
          previous_scale: numeric(100_000_000, "yuan", "1.00"),
          previous_pnl: numeric(100_000, "yuan", "+0.00", true),
          previous_yield_pct: numeric(0.001, "pct", "+0.10%", true),
          pnl_change: numeric(10_000, "yuan", "+0.00", true),
          pnl_change_pct: numeric(0.1, "pct", "+10.00%", true),
          volume_effect: numeric(0, "yuan", "+0.00", true),
          rate_effect: numeric(10_000, "yuan", "+0.00", true),
          interaction_effect: numeric(0, "yuan", "+0.00", true),
          attrib_sum: numeric(10_000, "yuan", "+0.00", true),
          recon_error: numeric(0, "yuan", "+0.00", true),
          volume_contribution_pct: numeric(0, "pct", "+0.00%", true),
          rate_contribution_pct: numeric(1, "pct", "+100.00%", true),
        },
      ],
    } as unknown as VolumeRateAttributionPayload;

    renderWith({ kind: "ok" }, data);

    expect(screen.getByText("+0.11%")).toBeInTheDocument();
    expect(screen.getByText("+0.10%")).toBeInTheDocument();
    expect(screen.getByTestId("volume-rate-echarts-stub")).toBeInTheDocument();
  });
});
