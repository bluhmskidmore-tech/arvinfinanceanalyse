import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it, vi } from "vitest";

import { createApiClient } from "../api/client";
import { createRealBalanceMovementClient } from "../api/balanceMovementClient";
import { preloadWorkbenchRouteModules } from "./preloadWorkbenchRouteModules";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="balance-movement-echarts-stub" />,
}));

beforeAll(async () => {
  await preloadWorkbenchRouteModules("balance-movement-analysis");
}, 20_000);

const jsonResponse = (payload: unknown) => new Response(JSON.stringify(payload), {
  headers: { "Content-Type": "application/json" },
});

describe("BalanceMovementAnalysisPage request boundary", () => {
  it("marks cached detail results after a failed reload and shows pending retry state", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const dates = await baseClient.getBalanceMovementDates();
    const detail = await baseClient.getBalanceMovementAnalysis({ reportDate: dates.result.report_dates[0] });
    const fetchImpl = vi.fn<typeof fetch>(async (input) =>
      jsonResponse(String(input).includes("/dates?") ? dates : detail),
    );
    const realMovementClient = createRealBalanceMovementClient({ fetchImpl, baseUrl: "http://synthetic.local" });
    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: { ...baseClient, ...realMovementClient, refreshBalanceMovementAnalysis: baseClient.refreshBalanceMovementAnalysis },
    });
    const initialSummary = await screen.findByTestId("balance-movement-analysis-summary");
    const originalSummary = initialSummary.textContent;
    fetchImpl.mockImplementation(async (input) => jsonResponse(String(input).includes("/dates?") ? dates : {}));

    await userEvent.click(screen.getByRole("button", { name: "刷新数据" }));

    const error = await screen.findByTestId("balance-movement-analysis-detail-status");
    expect(error).toHaveTextContent("当前显示上次成功读取结果，尚未确认本次更新");
    expect(screen.getByTestId("balance-movement-analysis-summary").textContent).toBe(originalSummary);
    const dataStates = screen.getByTestId("balance-movement-analysis-data-states");
    const loadingState = within(dataStates).getByText("加载中").closest("article");
    expect(loadingState).toHaveTextContent("读取失败");
    expect(loadingState).not.toHaveTextContent("已完成");
    const detailRowsState = within(dataStates).getByText("无明细行").closest("article");
    expect(detailRowsState).toHaveTextContent("未知");
    expect(detailRowsState).toHaveTextContent("本次读取失败");
    expect(detailRowsState).not.toHaveTextContent("AC / OCI / TPL 行已返回");
    const fallbackState = within(dataStates).getByText("回退日期").closest("article");
    expect(fallbackState).toHaveTextContent("未知");
    expect(fallbackState).toHaveTextContent("本次读取失败");

    let finishRetry!: (response: Response) => void;
    fetchImpl.mockImplementation(() => new Promise<Response>((resolve) => { finishRetry = resolve; }));
    await userEvent.click(within(error).getByRole("button", { name: "重试读取" }));
    expect(loadingState).toHaveTextContent("请求中");
    expect(within(error).getByRole("button", { name: "重试读取" })).toBeDisabled();
    await act(async () => { finishRetry(jsonResponse(detail)); });
    await waitFor(() => expect(screen.queryByTestId("balance-movement-analysis-detail-status")).not.toBeInTheDocument());
    expect(loadingState).toHaveTextContent("已完成");
  });

  it.each(["dates", "analysis"] as const)("shows malformed %s responses as a visible read failure", async (endpoint) => {
    const baseClient = createApiClient({ mode: "mock" });
    const dates = await baseClient.getBalanceMovementDates();
    const fetchImpl = vi.fn<typeof fetch>(async (input) =>
      jsonResponse(endpoint === "analysis" && String(input).includes("/dates?") ? dates : {}),
    );
    const realMovementClient = createRealBalanceMovementClient({ fetchImpl, baseUrl: "http://synthetic.local" });
    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: { ...baseClient, ...realMovementClient },
    });

    const error = await screen.findByTestId(`balance-movement-analysis-${endpoint === "dates" ? "date" : "detail"}-status`);
    expect(error).toHaveAttribute("role", "alert");
    expect(error).toHaveTextContent(endpoint === "dates" ? "报告日期加载失败" : "余额变动加载失败");
    expect(screen.queryByTestId("balance-movement-analysis-summary")).not.toBeInTheDocument();
    expect(screen.queryByText("等待物化")).not.toBeInTheDocument();
    const dataStates = screen.getByTestId("balance-movement-analysis-data-states");
    if (endpoint === "dates") {
      const dateState = within(dataStates)
        .getByText("无报告日").closest("article");
      expect(dateState).toHaveTextContent("未知");
      expect(dateState).not.toHaveTextContent("先物化读模型");
      const lagState = within(dataStates).getByText("读模型滞后").closest("article");
      expect(lagState).toHaveTextContent("未知");
      expect(lagState).toHaveTextContent("本次读取失败");
      expect(lagState).not.toHaveTextContent("否");
    } else {
      const detailRowsState = within(dataStates).getByText("无明细行").closest("article");
      expect(detailRowsState).toHaveTextContent("未知");
      expect(detailRowsState).toHaveTextContent("本次读取失败");
      expect(detailRowsState).not.toHaveTextContent("正文显式展示空态");
      const fallbackState = within(dataStates).getByText("回退日期").closest("article");
      expect(fallbackState).toHaveTextContent("未知");
      expect(fallbackState).toHaveTextContent("本次读取失败");
    }

    const detail = await baseClient.getBalanceMovementAnalysis({ reportDate: dates.result.report_dates[0] });
    fetchImpl.mockImplementation(async (input) => jsonResponse(String(input).includes("/dates?") ? dates : detail));
    await userEvent.click(screen.getByRole("button", { name: "重试读取" }));
    expect(await screen.findByTestId("balance-movement-analysis-summary")).toBeInTheDocument();
    expect(screen.queryByTestId("balance-movement-analysis-detail-status")).not.toBeInTheDocument();
    expect(screen.queryByTestId("balance-movement-analysis-date-status")).not.toBeInTheDocument();
    expect(fetchImpl.mock.calls.every(([, init]) => init?.method !== "POST")).toBe(true);
  });

  it.each(["dates", "analysis"] as const)("cancels the in-flight %s GET when the page unmounts", async (endpoint) => {
    const baseClient = createApiClient({ mode: "mock" });
    const dates = await baseClient.getBalanceMovementDates();
    let pendingSignal: AbortSignal | null | undefined;
    const fetchImpl = vi.fn<typeof fetch>(async (input, init) => {
      if (endpoint === "analysis" && String(input).includes("/dates?")) {
        return jsonResponse(dates);
      }
      pendingSignal = init?.signal;
      return new Promise<Response>(() => undefined);
    });
    const realMovementClient = createRealBalanceMovementClient({ fetchImpl, baseUrl: "http://synthetic.local" });
    const { unmount } = renderWorkbenchApp(["/balance-movement-analysis"], {
      client: { ...baseClient, ...realMovementClient },
    });
    await waitFor(() => expect(pendingSignal).toBeInstanceOf(AbortSignal));
    expect(pendingSignal?.aborted).toBe(false);
    const dataStates = screen.getByTestId("balance-movement-analysis-data-states");
    const unconfirmedLabels = endpoint === "dates"
      ? ["无报告日", "无明细行", "读模型滞后", "回退日期"]
      : ["无明细行", "回退日期"];
    for (const label of unconfirmedLabels) {
      expect(within(dataStates).getByText(label).closest("article")).toHaveTextContent("未知");
    }
    if (endpoint === "dates") {
      expect(within(dataStates).getByText("读模型滞后").closest("article"))
        .toHaveTextContent("尚未完成本次读取");
    }

    unmount();

    expect(pendingSignal?.aborted).toBe(true);
  });
});
