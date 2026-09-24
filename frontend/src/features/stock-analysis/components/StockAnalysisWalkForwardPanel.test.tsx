import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { WalkForwardReportPayload } from "../../../api/strategyReportsClient";
import { StockAnalysisWalkForwardPanel } from "./StockAnalysisWalkForwardPanel";

function syntheticPayload(): WalkForwardReportPayload {
  return {
    generated_at: "2026-08-12T15:11:00+08:00",
    engine_version: "wf-2026.08",
    issue_count: 2,
    schedules: [
      {
        label: "primary_6t_2v_2s",
        train_months: 6,
        valid_months: 2,
        step_months: 2,
        min_windows_for_verdict: 3,
        window_count: 5,
        strategies: [
          {
            strategy: "uptrend_momentum",
            verdict: "oos_weakened",
            verdict_reason: "样本外优势缩水",
            oos_window_count: 3,
            in_sample_excess: 0.08,
            oos_excess_median: 0.01,
            oos_excess_mean: 0.0067,
            excess_sign_consistency: {
              observed_windows: 3,
              positive_windows: 2,
              positive_ratio: 0.6667,
            },
            risk_budget: {
              switch_rate: 0.6667,
              mode_value: 0.005,
              window_params: [
                { window_id: "S1W1", selected: 0.005 },
                { window_id: "S1W2", selected: 0.0025 },
              ],
            },
          },
          {
            strategy: "theme_breakout",
            verdict: "insufficient_windows",
            verdict_reason: "验证窗仅 0 个",
            oos_window_count: 0,
          },
          {
            strategy: "factor_screen",
            verdict: "oos_supported",
            in_sample_excess: 0.02,
            oos_excess_median: 0.015,
            excess_sign_consistency: {
              observed_windows: 4,
              positive_windows: 4,
              positive_ratio: 1,
            },
          },
        ],
      },
      {
        label: "compact_1t_1v_1s",
        train_months: 1,
        valid_months: 1,
        step_months: 1,
        window_count: 18,
        strategies: [{ strategy: "uptrend_momentum", verdict: "oos_inconclusive" }],
      },
    ],
  };
}

describe("StockAnalysisWalkForwardPanel", () => {
  it("renders one row per strategy with verdict, excess pair, ratio and rpt drift", async () => {
    const loadReport = vi.fn(async () => syntheticPayload());
    render(<StockAnalysisWalkForwardPanel loadReport={loadReport} />);

    const panel = await screen.findByTestId("stock-analysis-walk-forward");

    // verdict 排序：支持 → 衰减 → 样本不足。
    const rows = within(panel).getAllByRole("listitem");
    expect(rows).toHaveLength(3);
    expect(rows[0]).toHaveAttribute("data-verdict", "oos_supported");
    expect(rows[1]).toHaveAttribute("data-verdict", "oos_weakened");
    expect(rows[2]).toHaveAttribute("data-verdict", "insufficient_windows");

    const weakened = screen.getByTestId("stock-analysis-walk-forward-row-uptrend_momentum");
    expect(within(weakened).getByText("上升趋势")).toBeInTheDocument();
    expect(within(weakened).getByText("样本外衰减")).toBeInTheDocument();
    expect(within(weakened).getByText("样本外衰减")).toHaveAttribute("title", "样本外优势缩水");
    // 样本内 vs 样本外中位超额数值对(小数 → 百分比,带符号)。
    expect(within(weakened).getByText("+8.00%")).toBeInTheDocument();
    expect(within(weakened).getByText("+1.00%")).toBeInTheDocument();
    // 正超额窗口占比。
    expect(within(weakened).getByText("2/3 (66.67%)")).toBeInTheDocument();
    // rpt 漂移提示 + 逐窗最优序列 tooltip。
    const drift = within(weakened).getByText("切换率 66.67% · 众数 0.005");
    expect(drift).toHaveAttribute("title", "rpt 逐窗最优(训练集选出): 0.005 → 0.0025");

    // 支持结论带克制的 positive 色彩语义。
    const supported = screen.getByTestId("stock-analysis-walk-forward-row-factor_screen");
    expect(within(supported).getByText("样本外支持")).toHaveAttribute("data-tone", "positive");

    // 缺失指标一律 EM_DASH,不崩、不显示 0。
    const insufficient = screen.getByTestId("stock-analysis-walk-forward-row-theme_breakout");
    expect(within(insufficient).getAllByText("—").length).toBeGreaterThan(0);

    // 脚注:验证窗数量与报告日期。
    expect(within(panel).getByText("5 个验证窗 · 定论门槛 3 窗")).toBeInTheDocument();
    expect(within(panel).getByText("报告 2026-08-12 · 2 条数据披露")).toBeInTheDocument();
  });

  it("switches schedules through the tab list", async () => {
    const loadReport = vi.fn(async () => syntheticPayload());
    render(<StockAnalysisWalkForwardPanel loadReport={loadReport} />);
    const panel = await screen.findByTestId("stock-analysis-walk-forward");

    const compactTab = within(panel).getByRole("tab", { name: "训1 验1 步1(月)" });
    expect(compactTab).toHaveAttribute("aria-selected", "false");
    fireEvent.click(compactTab);

    expect(compactTab).toHaveAttribute("aria-selected", "true");
    expect(within(panel).getAllByRole("listitem")).toHaveLength(1);
    expect(within(panel).getByText("方向不定")).toBeInTheDocument();
    expect(within(panel).getByText(/18 个验证窗/)).toBeInTheDocument();
  });

  it("hides the whole panel when the report is missing (404 → null)", async () => {
    const loadReport = vi.fn(async () => null);
    const { container } = render(<StockAnalysisWalkForwardPanel loadReport={loadReport} />);
    await waitFor(() => expect(loadReport).toHaveBeenCalled());
    await waitFor(() => expect(container.firstChild).toBeNull());
  });

  it("hides the whole panel when the request fails", async () => {
    const loadReport = vi.fn(async () => {
      throw new Error("boom");
    });
    const { container } = render(<StockAnalysisWalkForwardPanel loadReport={loadReport} />);
    await waitFor(() => expect(loadReport).toHaveBeenCalled());
    await waitFor(() => expect(container.firstChild).toBeNull());
  });

  it("hides the whole panel when no schedule carries strategy rows", async () => {
    const loadReport = vi.fn(async () => ({
      schedules: [{ label: "primary", strategies: [] }],
    }));
    const { container } = render(<StockAnalysisWalkForwardPanel loadReport={loadReport} />);
    await waitFor(() => expect(loadReport).toHaveBeenCalled());
    await waitFor(() => expect(container.firstChild).toBeNull());
  });

  it("tolerates rows with every field missing", async () => {
    const loadReport = vi.fn(async () => ({
      schedules: [{ strategies: [{}] }],
    }));
    render(<StockAnalysisWalkForwardPanel loadReport={loadReport} />);
    const panel = await screen.findByTestId("stock-analysis-walk-forward");
    expect(within(panel).getByText("结论待补")).toBeInTheDocument();
    expect(within(panel).getAllByText("—").length).toBeGreaterThan(0);
  });
});
