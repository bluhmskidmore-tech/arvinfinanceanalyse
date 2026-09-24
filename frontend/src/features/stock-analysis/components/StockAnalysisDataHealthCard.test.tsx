import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { DataHealthFetchResult, DataHealthPayload } from "../../../api/dataHealthClient";
import { StockAnalysisDataHealthCard } from "./StockAnalysisDataHealthCard";

function ok(payload: DataHealthPayload): DataHealthFetchResult {
  return { kind: "ok", payload };
}

function syntheticPayload(): DataHealthPayload {
  return {
    as_of_date: "2026-08-13",
    overall_status: "missing",
    threshold_note: "阈值：落后 >2 天 warn、>5 天 stale（自然日近似交易日）",
    sections: [
      {
        key: "observation_freshness",
        label: "行情观测新鲜度",
        status: "ok",
        metric: "2026-08-11 · 落后 2 天",
        detail: "choice_stock_daily_observation max(trade_date)=2026-08-11，距今 2 自然日",
        as_of: "2026-08-11",
      },
      {
        key: "adjustment_factor_gap",
        label: "复权因子缺口",
        status: "stale",
        metric: "5,022 行缺复权",
        detail: "执行历史 return_*_net 非空但 *_net_adj 空：20d 视角 2,077",
        as_of: "2026-07-21",
      },
      {
        key: "limit_price_backfill",
        label: "涨跌停数值表",
        status: "missing",
        metric: "0 行",
        detail: "stock_limit_price_daily 未回填（0 行）",
        as_of: null,
      },
      {
        key: "scheduled_tasks",
        label: "调度任务",
        status: "warn",
        metric: "1/2 正常",
        detail: "MOSS-DailyDataRefresh: 上次 2026-08-12 17:30:00，LastResult 1",
        as_of: null,
      },
    ],
  };
}

describe("StockAnalysisDataHealthCard", () => {
  it("renders one row per section with status dot, label, metric and detail tooltip", async () => {
    const loadHealth = vi.fn(async () => ok(syntheticPayload()));
    render(<StockAnalysisDataHealthCard loadHealth={loadHealth} />);

    const panel = await screen.findByTestId("stock-analysis-data-health");
    expect(within(panel).getAllByRole("listitem")).toHaveLength(4);
    expect(within(panel).getByText("评估日 2026-08-13")).toBeInTheDocument();

    // 整体徽章由后端 overall_status(最差项)决定。
    const overall = screen.getByTestId("stock-analysis-data-health-overall");
    expect(overall).toHaveTextContent("缺失");
    expect(overall).toHaveAttribute("data-status", "missing");

    const freshness = screen.getByTestId("stock-analysis-data-health-row-observation_freshness");
    expect(freshness).toHaveAttribute("data-status", "ok");
    expect(freshness).toHaveAttribute(
      "title",
      "choice_stock_daily_observation max(trade_date)=2026-08-11，距今 2 自然日",
    );
    expect(within(freshness).getByText("行情观测新鲜度")).toBeInTheDocument();
    expect(within(freshness).getByText("2026-08-11 · 落后 2 天")).toBeInTheDocument();

    const adjustment = screen.getByTestId("stock-analysis-data-health-row-adjustment_factor_gap");
    expect(adjustment).toHaveAttribute("data-status", "stale");
    expect(within(adjustment).getByText("5,022 行缺复权")).toBeInTheDocument();

    const scheduled = screen.getByTestId("stock-analysis-data-health-row-scheduled_tasks");
    expect(within(scheduled).getByText("1/2 正常")).toBeInTheDocument();
  });

  it("localizes the tradestatus vocabulary label into business language", async () => {
    const payload = syntheticPayload();
    payload.sections = [
      {
        key: "tradestatus_vocabulary",
        label: "tradestatus 词表",
        status: "ok",
        metric: "3,554 行 · 0.11%",
        detail: "非空且不在可交易白名单共 3,554 行",
      },
    ];
    const loadHealth = vi.fn(async () => ok(payload));
    render(<StockAnalysisDataHealthCard loadHealth={loadHealth} />);

    const row = await screen.findByTestId("stock-analysis-data-health-row-tradestatus_vocabulary");
    expect(within(row).getByText("交易状态词表")).toBeInTheDocument();
    expect(within(row).queryByText("tradestatus 词表")).toBeNull();
  });

  it("derives the overall badge from the worst section when overall_status is absent", async () => {
    const payload = syntheticPayload();
    payload.overall_status = null;
    payload.sections = [
      { key: "a", label: "甲", status: "ok", metric: "x" },
      { key: "b", label: "乙", status: "warn", metric: "y" },
    ];
    const loadHealth = vi.fn(async () => ok(payload));
    render(<StockAnalysisDataHealthCard loadHealth={loadHealth} />);

    const overall = await screen.findByTestId("stock-analysis-data-health-overall");
    expect(overall).toHaveTextContent("警告");
    expect(overall).toHaveAttribute("data-status", "warn");
  });

  it("hides the whole panel only when the capability is missing (404/明确空)", async () => {
    const loadHealth = vi.fn(async (): Promise<DataHealthFetchResult> => ({ kind: "missing" }));
    const { container } = render(<StockAnalysisDataHealthCard loadHealth={loadHealth} />);
    await waitFor(() => expect(loadHealth).toHaveBeenCalled());
    await waitFor(() => expect(container.firstChild).toBeNull());
  });

  it("hides the whole panel when sections are empty", async () => {
    const loadHealth = vi.fn(async () => ok({ as_of_date: "2026-08-13", sections: [] }));
    const { container } = render(<StockAnalysisDataHealthCard loadHealth={loadHealth} />);
    await waitFor(() => expect(loadHealth).toHaveBeenCalled());
    await waitFor(() => expect(container.firstChild).toBeNull());
  });

  it("shows a one-line error with retry on request failure instead of hiding", async () => {
    const user = userEvent.setup();
    const loadHealth = vi
      .fn(async (): Promise<DataHealthFetchResult> => ok(syntheticPayload()))
      .mockResolvedValueOnce({ kind: "error", reason: "HTTP 503" });
    render(<StockAnalysisDataHealthCard loadHealth={loadHealth} />);

    const errorPanel = await screen.findByTestId("stock-analysis-data-health-error");
    expect(errorPanel).toHaveTextContent("健康面加载失败");

    await user.click(screen.getByTestId("stock-analysis-data-health-retry"));
    expect(await screen.findByTestId("stock-analysis-data-health")).toBeInTheDocument();
    expect(loadHealth).toHaveBeenCalledTimes(2);
  });

  it("shows the error state when the load function rejects", async () => {
    const loadHealth = vi.fn(async () => {
      throw new Error("boom");
    });
    render(<StockAnalysisDataHealthCard loadHealth={loadHealth} />);
    expect(await screen.findByTestId("stock-analysis-data-health-error")).toBeInTheDocument();
  });

  it("renders a skeleton placeholder while loading", async () => {
    let resolveLoad: (value: DataHealthFetchResult) => void = () => undefined;
    const loadHealth = vi.fn(
      () =>
        new Promise<DataHealthFetchResult>((resolve) => {
          resolveLoad = resolve;
        }),
    );
    render(<StockAnalysisDataHealthCard loadHealth={loadHealth} />);

    expect(screen.getByTestId("stock-analysis-data-health-loading")).toBeInTheDocument();
    resolveLoad(ok(syntheticPayload()));
    expect(await screen.findByTestId("stock-analysis-data-health")).toBeInTheDocument();
  });

  it("tolerates sections with every field missing", async () => {
    const loadHealth = vi.fn(async () => ok({ sections: [{}] }));
    render(<StockAnalysisDataHealthCard loadHealth={loadHealth} />);
    const panel = await screen.findByTestId("stock-analysis-data-health");
    expect(within(panel).getByText("评估日 —")).toBeInTheDocument();
    expect(within(panel).getAllByText("—").length).toBeGreaterThan(0);
    // status 全缺 → 前端按未知(error 级严重度)推导徽章，展示原状态缺失语义。
    const overall = screen.getByTestId("stock-analysis-data-health-overall");
    expect(overall).toHaveAttribute("data-status", "error");
  });
});
