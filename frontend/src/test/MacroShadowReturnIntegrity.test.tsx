import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { MacroToolkitShadowPortfolioPeriodReturn, MacroToolkitShadowPortfolioReport } from "../api/macroToolkitClient";
import { ShadowPortfolioReportPanel } from "../features/macro-toolkit/sections/MacroToolkitStrategySections";
import {
  shadowPortfolioPeriodRangeText,
  shadowPortfolioPeriodWinLossText,
} from "../features/macro-toolkit/lib/macroToolkitStrategyDisplaySupport";

describe("shadow return coverage", () => {
  it("does not count an unknown return as a loss or a best period", () => {
    const rows: MacroToolkitShadowPortfolioPeriodReturn[] = [{
      portfolio_key: "shadow", start_date: "2026-01-01", end_date: "2026-02-01",
      gross_return: null, benchmark_return: 0.02, excess_return: null,
      selected_count: 2, observed_return_count: 1, name_turnover: null, traded_notional: 1, cost_results: [],
    }];
    expect(shadowPortfolioPeriodWinLossText(rows)).toBe("收益覆盖不完整，胜负待确认");
    expect(shadowPortfolioPeriodRangeText(rows)).toBe("最佳缺失 / 最差缺失");
  });

  it("renders the incomplete adjusted-return warning without a zero-return card", () => {
    const report: MacroToolkitShadowPortfolioReport = {
      status: "partial", basis: "read_only_shadow", label: "影子组合报告", as_of_date: "2026-02-01",
      completed_periods: 1, factor_dates: ["2026-01-01", "2026-02-01"], rule_version: "test",
      tables_used: [], warnings: ["INCOMPLETE_ADJUSTED_RETURN_COVERAGE"],
      cost_model: { cost_bps: [0, 50], initial_build_included: true, final_liquidation_included: false },
      benchmark: null, portfolios: [], period_returns: [],
    };
    render(<ShadowPortfolioReportPanel report={report} />);
    expect(screen.getByText("部分持仓缺少有效边界价格或复权因子，组合收益及累计结果暂不能确认。")).toBeInTheDocument();
    expect(screen.queryByText("总收益")).not.toBeInTheDocument();
  });
});
