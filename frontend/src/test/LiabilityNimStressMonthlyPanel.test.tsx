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
    // 有意与前端旧演算值（nim - 0.5 = 0.60）不同，证明渲染的是后端字段。
    nim_stress: { nim_stressed: 0.35, delta_bp: -50 },
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
  it("renders the backend official nim_stress instead of a frontend derivation", () => {
    render(<LiabilityNimStressMonthlyPanel adbMonth={buildAdbMonth()} />);

    expect(screen.getByText("压力测试：NIM 敏感性（+50bps）")).toBeInTheDocument();
    expect(
      screen.queryByTestId("liability-nim-monthly-unofficial-note"),
    ).not.toBeInTheDocument();
    const note = screen.getByTestId("liability-nim-monthly-official-note");
    expect(note.textContent).toContain("后端正式口径");
    expect(note.textContent).toContain("−50bp");

    // 后端字段 0.35 而非前端演算 1.1 - 0.5 = 0.60。
    expect(screen.getByText("0.35%")).toBeInTheDocument();
    expect(screen.queryByText("0.60%")).not.toBeInTheDocument();
    expect(screen.getByText("-50 bp（负债成本 +50bps，NIM 同幅下行）")).toBeInTheDocument();
  });

  it("renders EM_DASH when the backend reports null nim_stress for a NIM-less month", () => {
    render(
      <LiabilityNimStressMonthlyPanel
        adbMonth={buildAdbMonth({
          net_interest_margin: null,
          nim_stress: { nim_stressed: null, delta_bp: null },
        })}
      />,
    );

    expect(screen.getByText(`Δ ${EM_DASH}`)).toBeInTheDocument();
    expect(screen.queryByText("-0.50%")).not.toBeInTheDocument();
    expect(screen.queryByText("0.60%")).not.toBeInTheDocument();
  });

  it("falls back to EM_DASH when nim_stress is absent from an older payload", () => {
    render(
      <LiabilityNimStressMonthlyPanel
        adbMonth={buildAdbMonth({ nim_stress: undefined })}
      />,
    );

    // 即便 NIM 存在也不做前端演算：无后端压力字段时展示占位。
    expect(screen.getByText("1.10%")).toBeInTheDocument();
    expect(screen.getByText(`Δ ${EM_DASH}`)).toBeInTheDocument();
    expect(screen.queryByText("0.60%")).not.toBeInTheDocument();
  });
});
