import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AdbMonthlyDataItem } from "../api/contracts";
import { LiabilityNimStressMonthlyPanel } from "../features/liability-analytics/components/LiabilityNimStressMonthlyPanel";
import { EM_DASH } from "../utils/format";

function buildAdbMonth(overrides: Partial<AdbMonthlyDataItem> = {}): AdbMonthlyDataItem {
  return {
    month: "2026-06",
    month_label: "2026年6月",
    num_days: 30,
    avg_assets: 1_000_000_000,
    avg_liabilities: 800_000_000,
    asset_yield: 3.2,
    liability_cost: 2.1,
    net_interest_margin: 1.1,
    mom_change_assets: null,
    mom_change_pct_assets: null,
    mom_change_liabilities: null,
    mom_change_pct_liabilities: null,
    breakdown_assets: [],
    breakdown_liabilities: [],
    ...overrides,
  };
}

describe("LiabilityNimStressMonthlyPanel", () => {
  it("marks the monthly stressed NIM as an unofficial frontend-derived preview", () => {
    render(<LiabilityNimStressMonthlyPanel adbMonth={buildAdbMonth()} />);

    expect(screen.getByText("压力测试：NIM 敏感性（+50bps，非官方预览）")).toBeInTheDocument();
    const note = screen.getByTestId("liability-nim-monthly-unofficial-note");
    expect(note.textContent).toContain("非官方预览");
    expect(note.textContent).toContain("前端演算");
    expect(note.textContent).toContain("−50bp");
  });

  it("renders EM_DASH instead of a fake stressed value when monthly NIM is missing", () => {
    render(
      <LiabilityNimStressMonthlyPanel
        adbMonth={buildAdbMonth({ net_interest_margin: null })}
      />,
    );

    expect(screen.getByText(`Δ ${EM_DASH}`)).toBeInTheDocument();
    expect(screen.queryByText("-0.50%")).not.toBeInTheDocument();
  });
});
