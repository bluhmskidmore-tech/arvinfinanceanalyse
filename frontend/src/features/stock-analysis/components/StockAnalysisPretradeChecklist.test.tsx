import { render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { PretradeChecklistPayload } from "../../../api/pretradeChecklistClient";
import { StockAnalysisPretradeChecklist } from "./StockAnalysisPretradeChecklist";

function syntheticPayload(): PretradeChecklistPayload {
  return {
    as_of_date: "2026-08-10",
    signal_kind: "factor_screen",
    checklist_status: "ok",
    candidate_count: 5,
    top_n: 10,
    staleness: { status: "ok", today: "2026-08-12", calendar_gap_days: 2, stale_calendar_days: 5 },
    gate: {
      status: "available",
      state: "WARM",
      exposure: 0.5,
      source: "persisted:livermore_candidate_history",
      note: null,
    },
    position_size_hint: { policy_version: "sizing_rb_v1_stock_candidate", coverage_warning: null },
    items: [
      {
        candidate_rank: 1,
        stock_code: "600001.SH",
        stock_name: "正常股",
        buyable_status: "buyable",
        block_reasons: [],
        data_flags: [],
        position_hint: {
          equal_weight: 0.1,
          raw_weight: 0.125,
          stop_basis: "ema10_stop_ref",
          capped: false,
        },
      },
      {
        candidate_rank: 2,
        stock_code: "600002.SH",
        stock_name: "停牌股",
        trade_status: "停牌一天",
        buyable_status: "blocked_suspended",
        block_reasons: ["suspended"],
        data_flags: [],
        position_hint: { raw_weight: 0.0625, stop_basis: "fallback", capped: false },
      },
      {
        candidate_rank: 3,
        stock_code: "600003.SH",
        stock_name: "涨停股",
        buyable_status: "blocked_limit",
        block_reasons: ["limit_up"],
        data_flags: ["adj_factor_missing"],
        position_hint: { raw_weight: 0.25, stop_basis: "ema10_stop_ref", capped: true },
      },
      {
        candidate_rank: 4,
        stock_code: "600004.SH",
        stock_name: "缺数股",
        buyable_status: "data_missing",
        block_reasons: ["missing_daily_observation"],
        data_flags: ["limit_price_missing"],
        position_hint: null,
      },
      {
        candidate_rank: 5,
        stock_code: "600005.SH",
        stock_name: "低量股",
        buyable_status: "review",
        block_reasons: ["low_liquidity"],
        data_flags: [],
        position_hint: { raw_weight: 0.1, stop_basis: "ema10_stop_ref", capped: false },
      },
    ],
    summary: { buyable_count: 1, blocked_count: 2, review_count: 1, data_missing_count: 1 },
  };
}

describe("StockAnalysisPretradeChecklist", () => {
  it("renders one row per candidate with status pill, position hint and block reasons", async () => {
    const loadChecklist = vi.fn(async () => syntheticPayload());
    render(<StockAnalysisPretradeChecklist loadChecklist={loadChecklist} />);

    const panel = await screen.findByTestId("stock-analysis-pretrade-checklist");
    expect(within(panel).getAllByRole("listitem")).toHaveLength(5);

    // 头部：信号日 + 门控敞口；未过期时不出现 stale 警示。
    expect(within(panel).getByText("信号日 2026-08-10")).toBeInTheDocument();
    expect(within(panel).getByText("门控 暖 · 敞口 50.00%")).toBeInTheDocument();
    expect(screen.queryByTestId("stock-analysis-pretrade-stale")).toBeNull();

    const buyable = screen.getByTestId("stock-analysis-pretrade-row-600001.SH");
    expect(within(buyable).getByText("可买")).toHaveAttribute("data-tone", "positive");
    // 等权主口径优先(门控敞口/候选数)。
    expect(within(buyable).getByText("10.00%")).toBeInTheDocument();
    expect(within(buyable).getByText("—")).toBeInTheDocument(); // 无拦截原因

    const suspended = screen.getByTestId("stock-analysis-pretrade-row-600002.SH");
    expect(within(suspended).getByText("停牌拦")).toHaveAttribute("data-tone", "negative");
    expect(within(suspended).getByText("停牌")).toBeInTheDocument();

    const limitBlocked = screen.getByTestId("stock-analysis-pretrade-row-600003.SH");
    expect(within(limitBlocked).getByText("涨跌停拦")).toHaveAttribute("data-tone", "negative");
    expect(within(limitBlocked).getByText("涨停")).toBeInTheDocument();
    // 门控缺省(无 equal_weight)时回退 risk_budget 上限建议。
    expect(within(limitBlocked).getByText("≤25.00%(封顶)")).toBeInTheDocument();
    expect(within(limitBlocked).getByText("复权缺口")).toBeInTheDocument();

    const dataMissing = screen.getByTestId("stock-analysis-pretrade-row-600004.SH");
    expect(within(dataMissing).getByText("数据缺")).toBeInTheDocument();
    expect(within(dataMissing).getByText("缺当日观测")).toBeInTheDocument();
    expect(within(dataMissing).getByText("涨跌停价缺")).toBeInTheDocument();
    expect(within(dataMissing).getByText("—")).toBeInTheDocument(); // 无仓位建议

    const review = screen.getByTestId("stock-analysis-pretrade-row-600005.SH");
    expect(within(review).getByText("复核")).toHaveAttribute("data-tone", "caution");
    expect(within(review).getByText("流动性不足")).toBeInTheDocument();

    // 脚注汇总与观察面免责。
    expect(within(panel).getByText("可买 1 · 拦截 2 · 复核 1 · 数据缺 1")).toBeInTheDocument();
    expect(within(panel).getByText("观察面输出，不构成交易指令")).toBeInTheDocument();
  });

  it("surfaces stale signal warning and missing gate state", async () => {
    const payload = syntheticPayload();
    payload.checklist_status = "stale";
    payload.staleness = { status: "stale", calendar_gap_days: 21, stale_calendar_days: 5 };
    payload.gate = { status: "missing", note: "门控敞口在该信号日无持久化点位且不可回放" };
    const loadChecklist = vi.fn(async () => payload);
    render(<StockAnalysisPretradeChecklist loadChecklist={loadChecklist} />);

    const panel = await screen.findByTestId("stock-analysis-pretrade-checklist");
    expect(screen.getByTestId("stock-analysis-pretrade-stale")).toHaveTextContent(
      "信号已过期 21 天",
    );
    const gate = within(panel).getByText("门控数据缺失");
    expect(gate).toHaveAttribute("data-gate-status", "missing");
    expect(gate).toHaveAttribute("title", "门控敞口在该信号日无持久化点位且不可回放");
  });

  it("hides the whole panel when the checklist is unavailable (404/failure → null)", async () => {
    const loadChecklist = vi.fn(async () => null);
    const { container } = render(<StockAnalysisPretradeChecklist loadChecklist={loadChecklist} />);
    await waitFor(() => expect(loadChecklist).toHaveBeenCalled());
    await waitFor(() => expect(container.firstChild).toBeNull());
  });

  it("hides the whole panel when the load function rejects", async () => {
    const loadChecklist = vi.fn(async () => {
      throw new Error("boom");
    });
    const { container } = render(<StockAnalysisPretradeChecklist loadChecklist={loadChecklist} />);
    await waitFor(() => expect(loadChecklist).toHaveBeenCalled());
    await waitFor(() => expect(container.firstChild).toBeNull());
  });

  it("hides the whole panel when candidates are empty", async () => {
    const loadChecklist = vi.fn(async () => ({
      as_of_date: "2026-08-10",
      checklist_status: "empty",
      items: [],
    }));
    const { container } = render(<StockAnalysisPretradeChecklist loadChecklist={loadChecklist} />);
    await waitFor(() => expect(loadChecklist).toHaveBeenCalled());
    await waitFor(() => expect(container.firstChild).toBeNull());
  });

  it("tolerates items with every field missing", async () => {
    const loadChecklist = vi.fn(async () => ({ items: [{}] }));
    render(<StockAnalysisPretradeChecklist loadChecklist={loadChecklist} />);
    const panel = await screen.findByTestId("stock-analysis-pretrade-checklist");
    expect(within(panel).getByText("状态待补")).toBeInTheDocument();
    expect(within(panel).getAllByText("—").length).toBeGreaterThan(0);
    expect(within(panel).getByText("信号日 —")).toBeInTheDocument();
    expect(within(panel).getByText("门控数据缺失")).toBeInTheDocument();
  });
});
