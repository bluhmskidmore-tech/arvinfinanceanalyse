import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Numeric, VolumeRateAttributionPayload } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import { VolumeRateBridgePanel } from "./PnlAttributionVolumeRateTab";
import {
  buildVolumeRateBridgeSummary,
  VOLUME_RATE_CLOSURE_DISCLOSURE,
} from "./pnlAttributionViewModel";

function numeric(overrides: Partial<Numeric>): Numeric {
  return {
    raw: overrides.raw ?? null,
    unit: overrides.unit ?? "yuan",
    display: overrides.display ?? EM_DASH,
    precision: overrides.precision ?? 2,
    sign_aware: overrides.sign_aware ?? true,
  };
}

function closedPayload(): VolumeRateAttributionPayload {
  return {
    current_period: "2026-04",
    previous_period: "2026-03",
    compare_type: "mom",
    total_current_pnl: numeric({ raw: 1_200_000 }),
    total_previous_pnl: numeric({ raw: 1_000_000 }),
    total_pnl_change: numeric({ raw: 200_000 }),
    total_volume_effect: numeric({ raw: 100_000 }),
    total_rate_effect: numeric({ raw: 60_000 }),
    total_interaction_effect: numeric({ raw: 30_000 }),
    total_recon_error: numeric({ raw: 10_000 }),
    has_previous_data: true,
    items: [],
  };
}

describe("VolumeRateBridgePanel closure disclosure", () => {
  it("renders the frontend-tolerance disclosure next to the closure status label", () => {
    const data = closedPayload();
    const summary = buildVolumeRateBridgeSummary(data);
    if (summary === null) {
      throw new Error("expected volume-rate bridge summary for closed payload");
    }

    render(<VolumeRateBridgePanel data={data} summary={summary} />);

    expect(screen.getByText("归因闭合")).toBeInTheDocument();
    expect(screen.getByTestId("volume-rate-bridge-closure-disclosure")).toHaveTextContent(
      VOLUME_RATE_CLOSURE_DISCLOSURE,
    );
    expect(screen.getByTestId("volume-rate-bridge-panel")).toHaveTextContent(
      "闭合判定为前端口径（容差 1 万元，非后端契约）",
    );
  });
});
