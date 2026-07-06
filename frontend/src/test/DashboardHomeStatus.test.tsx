import { fireEvent, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { createApiClient, type ApiClient } from "../api/client";
import { todayIsoDate } from "../features/workbench/pages/dashboardPageHelpers";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

vi.mock("../lib/echarts", () => ({
  default: () => null,
}));

function createRealModeHomeClient(overrides: Partial<ApiClient> = {}): ApiClient {
  const base = createApiClient({ mode: "real" });
  return {
    ...base,
    getResearchCalendarEvents: vi.fn(async () => []),
    ...overrides,
  };
}

describe("DashboardHomeStatus", () => {
  it("marks the home snapshot as unavailable when the real snapshot request fails", async () => {
    const client = createRealModeHomeClient({
      getHomeSnapshot: vi.fn(async () => {
        throw new Error("snapshot unavailable");
      }),
    });

    renderWorkbenchApp(["/"], { client });

    const dataStatus = await screen.findByTestId("dashboard-home-data-status");
    await waitFor(() => {
      expect(dataStatus).toHaveAttribute("data-status-kind", "error");
      expect(dataStatus).toHaveTextContent("首页数据服务不可达");
    });
    expect(screen.getByTestId("dashboard-home-rail-data-status")).toHaveAttribute(
      "data-status-kind",
      "error",
    );
    expect(screen.getByTestId("dashboard-home-rail-updated-at")).toHaveTextContent("—");
    expect(screen.getByPlaceholderText("2026-04-30")).toHaveValue(todayIsoDate());
    expect(screen.getByTestId("dashboard-home-kpi-aum")).toHaveTextContent("未取得");
    expect(screen.getAllByText("服务未连接").length).toBeGreaterThan(0);
    expect(screen.getByText("无可用快照")).toBeInTheDocument();
  });

  it("does not replace a failed real snapshot with preview sample KPIs", async () => {
    const client = createRealModeHomeClient({
      getHomeSnapshot: vi.fn(async () => {
        throw new Error("snapshot unavailable");
      }),
    });

    renderWorkbenchApp(["/"], { client });

    const hero = await screen.findByTestId("dashboard-home-morning-hero");
    await waitFor(() => {
      expect(screen.getByTestId("dashboard-home-data-status")).toHaveTextContent("首页数据服务不可达");
      expect(screen.getByTestId("dashboard-home-rail-data-status")).toHaveTextContent("首页数据服务不可达");
      expect(screen.getByTestId("dashboard-home-kpi-aum")).toHaveTextContent("—");
      expect(screen.getByTestId("dashboard-home-kpi-aum")).toHaveTextContent("未取得");
      expect(hero).not.toHaveTextContent("3,708.10");
      expect(hero).not.toHaveTextContent("样例");
    });
  });

  it("marks retained previous snapshot data as stale when a new report date request fails", async () => {
    const mockSource = createApiClient({ mode: "mock" });
    const firstReportDate = "2026-04-30";
    const failedReportDate = "2026-05-31";
    const client = createRealModeHomeClient({
      getHomeSnapshot: vi.fn<ApiClient["getHomeSnapshot"]>(async (options) => {
        if (options?.reportDate === failedReportDate) {
          throw new Error("new report date unavailable");
        }
        const base = await mockSource.getHomeSnapshot(options);
        return {
          ...base,
          result: {
            ...base.result,
            report_date: firstReportDate,
          },
        };
      }),
    });

    renderWorkbenchApp(["/"], { client });

    const reportDateInput = screen.getByPlaceholderText("2026-04-30");
    await waitFor(() => {
      expect(reportDateInput).toHaveValue(firstReportDate);
    });

    fireEvent.change(reportDateInput, {
      target: { value: failedReportDate },
    });

    const dataStatus = await screen.findByTestId("dashboard-home-data-status");
    await waitFor(() => {
      expect(dataStatus).toHaveAttribute("data-status-kind", "stale");
      expect(dataStatus).toHaveTextContent("展示上一版本");
    });
    expect(dataStatus).not.toHaveTextContent("数据已更新");
    expect(screen.getByTestId("dashboard-home-rail-data-status")).toHaveAttribute(
      "data-status-kind",
      "stale",
    );
    const railUpdatedAt = screen.getByTestId("dashboard-home-rail-updated-at");
    expect(railUpdatedAt).toHaveTextContent(`沿用报告日 ${firstReportDate}`);
    expect(railUpdatedAt).not.toHaveTextContent(`${firstReportDate} ${firstReportDate}`);
  });
});
