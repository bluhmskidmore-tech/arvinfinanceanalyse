import { fireEvent, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { createApiClient, type ApiClient } from "../api/client";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

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
      expect(dataStatus).toHaveTextContent("主快照不可用");
    });
    expect(screen.getByTestId("dashboard-home-rail-data-status")).toHaveAttribute(
      "data-status-kind",
      "error",
    );
    expect(screen.getByTestId("dashboard-home-rail-updated-at")).toHaveTextContent("—");
    expect(screen.getByText("数据未同步")).toBeInTheDocument();
    expect(screen.getByText("等待主快照")).toBeInTheDocument();
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
