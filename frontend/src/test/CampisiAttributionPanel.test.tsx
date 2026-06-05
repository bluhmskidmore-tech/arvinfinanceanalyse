import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="campisi-echarts-stub" />,
}));

import type {
  CampisiAttributionPayload,
  CampisiFourEffectsPayload,
  Numeric,
} from "../api/contracts";
import { CampisiAttributionPanel } from "../features/pnl-attribution/components/CampisiAttributionPanel";

function numeric(raw: number | null, unit: Numeric["unit"], display = ""): Numeric {
  return {
    raw,
    unit,
    display,
    precision: 2,
    sign_aware: true,
  };
}

describe("CampisiAttributionPanel", () => {
  it("renders formal closure warning for current four-effect payloads", () => {
    const data: CampisiFourEffectsPayload = {
      report_date: "2026-04-30",
      period_start: "2026-03-31",
      period_end: "2026-04-30",
      num_days: 30,
      totals: {
        income_return: 600_000_000,
        treasury_effect: 200_000_000,
        spread_effect: -100_000_000,
        selection_effect: 100_000_000,
        total_return: 800_000_000,
        market_value_start: 12_000_000_000,
      },
      by_asset_class: [],
      by_bond: [],
      formal_closure: {
        basis: "pnl.bridge.total_actual_pnl",
        report_date: "2026-04-30",
        status: "warning",
        campisi_total_return: 800_000_000,
        formal_actual_pnl: 700_000_000,
        residual_to_formal_pnl: -100_000_000,
        residual_ratio: 0.142857,
        message: "Campisi total return does not close to formal PnL.",
      },
    };

    render(<CampisiAttributionPanel data={data} state={{ kind: "ok" }} onRetry={() => {}} />);

    const warning = screen.getByTestId("campisi-formal-closure-warning");
    expect(warning).toBeInTheDocument();
    expect(warning).toHaveTextContent("+8.00 亿");
    expect(screen.getByTestId("campisi-driver-summary")).toHaveTextContent("75.0%");
  });

  it("makes the main Campisi driver and quiet effects obvious", () => {
    const data: CampisiFourEffectsPayload = {
      report_date: "2026-04-30",
      period_start: "2026-03-31",
      period_end: "2026-04-30",
      num_days: 30,
      totals: {
        income_return: 529_838_963.09,
        treasury_effect: 0,
        spread_effect: 0,
        selection_effect: 6_106_054.95,
        total_return: 535_945_018.04,
        market_value_start: 343_822_795_478.69,
      },
      by_asset_class: [],
      by_bond: [],
      formal_closure: {
        basis: "pnl.bridge.total_actual_pnl",
        report_date: "2026-04-30",
        status: "closed",
        campisi_total_return: 535_945_018.04,
        formal_actual_pnl: 535_945_018.04,
        residual_to_formal_pnl: 0,
        residual_ratio: 0,
        message: "Campisi total return closes to formal PnL.",
      },
    };

    render(<CampisiAttributionPanel data={data} state={{ kind: "ok" }} onRetry={() => {}} />);

    const boundary = screen.getByTestId("campisi-capability-boundary");
    expect(boundary).toHaveTextContent("尚未实现交易员能力评价");
    expect(boundary).toHaveTextContent("个券跑赢同类基准");

    const summary = screen.getByTestId("campisi-driver-summary");
    expect(summary).toHaveTextContent("主要贡献：收入效应");
    expect(summary).toHaveTextContent("约 98.9%");
    expect(summary).toHaveTextContent("几乎没有影响：国债曲线、信用利差");
    expect(summary).toHaveTextContent("不能直接等同交易员主动选券能力");
    expect(screen.queryByTestId("campisi-formal-closure-warning")).not.toBeInTheDocument();
  });

  it("renders legacy governed pct raw ratios as percent points", () => {
    const data: CampisiAttributionPayload = {
      report_date: "2026-04-30",
      period_start: "2026-03-31",
      period_end: "2026-04-30",
      num_days: 30,
      total_market_value: numeric(12_000_000_000, "yuan", "+120.00 亿"),
      total_return: numeric(800_000_000, "yuan", "+8.00 亿"),
      total_return_pct: numeric(0.066667, "pct", "+6.67%"),
      total_income: numeric(600_000_000, "yuan", "+6.00 亿"),
      total_treasury_effect: numeric(200_000_000, "yuan", "+2.00 亿"),
      total_spread_effect: numeric(-100_000_000, "yuan", "-1.00 亿"),
      total_selection_effect: numeric(100_000_000, "yuan", "+1.00 亿"),
      income_contribution_pct: numeric(0.75, "pct", "+75.00%"),
      treasury_contribution_pct: numeric(0.25, "pct", "+25.00%"),
      spread_contribution_pct: numeric(-0.125, "pct", "-12.50%"),
      selection_contribution_pct: numeric(0.125, "pct", "+12.50%"),
      primary_driver: "income",
      interpretation: "legacy campisi",
      items: [],
    };

    render(<CampisiAttributionPanel data={data} state={{ kind: "ok" }} onRetry={() => {}} />);

    expect(screen.getByTestId("campisi-driver-summary")).toHaveTextContent("75.0%");
    expect(screen.queryByText(/0\.8%/)).not.toBeInTheDocument();
  });
});
