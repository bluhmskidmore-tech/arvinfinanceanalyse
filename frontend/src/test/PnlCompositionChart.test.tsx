import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: ({ option }: { option?: unknown }) => (
    <div data-testid="pnl-composition-echarts-stub">{JSON.stringify(option ?? null)}</div>
  ),
}));

import type { Numeric, PnlCompositionPayload } from "../api/contracts";
import type { DataSectionState } from "../components/DataSection.types";
import { PnLCompositionChart } from "../features/pnl-attribution/components/PnLCompositionChart";

function num(raw: number | null, unit: Numeric["unit"] = "yuan"): Numeric {
  return {
    raw,
    unit,
    display: "",
    precision: 2,
    sign_aware: false,
  };
}

function numDisplay(raw: number | null, unit: Numeric["unit"], display: string): Numeric {
  return {
    raw,
    unit,
    display,
    precision: 2,
    sign_aware: true,
  };
}

const readyState: DataSectionState = { kind: "ok" };

describe("PnLCompositionChart", () => {
  it("renders other income in visible breakdowns and trend series when present", () => {
    const data: PnlCompositionPayload = {
      report_period: "2026-03",
      report_date: "2026-03-31",
      total_pnl: num(125_000_000),
      total_interest_income: num(72_000_000),
      total_fair_value_change: num(38_000_000),
      total_capital_gain: num(12_000_000),
      total_other_income: num(3_000_000),
      interest_pct: num(57.6, "pct"),
      fair_value_pct: num(30.4, "pct"),
      capital_gain_pct: num(9.6, "pct"),
      other_pct: num(2.4, "pct"),
      items: [
        {
          category: "利率债",
          category_type: "asset",
          level: 0,
          total_pnl: num(45_000_000),
          interest_income: num(28_000_000),
          fair_value_change: num(12_000_000),
          capital_gain: num(4_000_000),
          other_income: num(1_000_000),
          interest_pct: num(62.2, "pct"),
          fair_value_pct: num(26.7, "pct"),
          capital_gain_pct: num(8.9, "pct"),
          other_pct: num(2.2, "pct"),
        },
      ],
      trend_data: [
        {
          period: "2026-03",
          period_label: "2026年03月",
          interest_income: num(25_000_000),
          fair_value_change: num(18_000_000),
          capital_gain: num(4_500_000),
          total_pnl: num(50_500_000),
          other_income: num(3_000_000),
        },
      ],
    };

    render(<PnLCompositionChart data={data} state={readyState} onRetry={() => {}} />);

    expect(screen.getByText("其他收入")).toBeInTheDocument();
    expect(screen.getByText("占比 2.4%")).toBeInTheDocument();
    expect(screen.getByText("其他(亿)")).toBeInTheDocument();
    expect(screen.getByText("+0.03 亿")).toBeInTheDocument();

    const chartStubs = screen.getAllByTestId("pnl-composition-echarts-stub");
    expect(chartStubs.some((node) => node.textContent?.includes("其他收入") ?? false)).toBe(true);
    expect(chartStubs.every((node) => !node.textContent?.includes('"type":"pie"'))).toBe(true);
    expect(chartStubs.some((node) => node.textContent?.includes('"type":"bar"') ?? false)).toBe(true);
  });

  it("renders governed pct display instead of raw ratio values", () => {
    const data: PnlCompositionPayload = {
      report_period: "2026-04",
      report_date: "2026-04-30",
      total_pnl: num(851_450_000),
      total_interest_income: num(534_920_000),
      total_fair_value_change: num(156_730_000),
      total_capital_gain: num(159_800_000),
      total_other_income: num(0),
      interest_pct: numDisplay(0.628245986565378, "pct", "+62.82%"),
      fair_value_pct: numDisplay(0.1840714304113674, "pct", "+18.41%"),
      capital_gain_pct: numDisplay(0.18768258302325463, "pct", "+18.77%"),
      other_pct: numDisplay(0, "pct", "+0.00%"),
      items: [],
      trend_data: [],
    };

    render(<PnLCompositionChart data={data} state={readyState} onRetry={() => {}} />);

    expect(screen.getByText(/\+62\.82%/)).toBeInTheDocument();
    expect(screen.queryByText(/0\.6%/)).not.toBeInTheDocument();
  });
});
