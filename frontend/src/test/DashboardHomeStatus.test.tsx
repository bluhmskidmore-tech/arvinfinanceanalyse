import { fireEvent, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { createApiClient, type ApiClient } from "../api/client";
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
  it("surfaces a governed permission failure without claiming the service is unavailable", async () => {
    const client = createRealModeHomeClient({
      getHomeSnapshot: vi.fn(async () => {
        throw new Error("User is not allowed to read executive.");
      }),
    });

    renderWorkbenchApp(["/"], { client });

    const dataStatus = await screen.findByTestId("dashboard-home-data-status");
    await waitFor(() => {
      expect(dataStatus).toHaveAttribute("data-status-kind", "error");
      expect(dataStatus).toHaveTextContent("权限不足");
    });
    const page = screen.getByTestId("dashboard-home-page");
    expect(page).toHaveClass("theme-dh-api");
    expect(page).toHaveAttribute("data-moss-theme", "dark");
    expect(page).toHaveAttribute("data-moss-theme-scope", "dashboard-home");
    expect(page).not.toHaveTextContent("服务不可达");
    expect(screen.getByTestId("dashboard-home-morning-hero")).toBeInTheDocument();
    expect(
      screen
        .getByTestId("dashboard-home-toolbar")
        .querySelector('[data-role="dashboard-home-update-stamp"]'),
    ).toHaveTextContent("更新 —");
    expect(screen.getByPlaceholderText("2026-04-30")).toHaveValue("");
    expect(screen.getByTestId("dashboard-home-kpi-aum")).toHaveAttribute(
      "data-state",
      "empty",
    );
    expect(screen.getByTestId("dashboard-home-kpi-aum")).toHaveTextContent("—");
    expect(screen.getAllByText("无可用快照").length).toBeGreaterThan(0);

    fireEvent.scroll(window);

    const availabilityPanel = await screen.findByTestId("dashboard-home-data-availability");
    expect(availabilityPanel).toHaveTextContent("首页快照权限不足");
    expect(
      screen.getByTestId("dashboard-home-data-availability-retry"),
    ).toHaveTextContent("重新读取");
    expect(await screen.findByTestId("dashboard-home-work-grid")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-home-source-gate")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-home-position-changes")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-home-income-trend")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-home-bottom-grid")).toBeInTheDocument();
    expect(
      screen
        .getByTestId("dashboard-home-bottom-grid")
        .querySelector('small[data-status-kind="error"]'),
    ).toHaveTextContent("不可用");
    expect(screen.getByTestId("dashboard-home-bond-news")).toBeInTheDocument();
    expect(page).not.toHaveTextContent("3,708.10");
    expect(page).not.toHaveTextContent("样例");
  });

  it("describes a generic snapshot failure as a read failure and does not inject preview KPIs", async () => {
    const client = createRealModeHomeClient({
      getHomeSnapshot: vi.fn(async () => {
        throw new Error("snapshot unavailable");
      }),
    });

    renderWorkbenchApp(["/"], { client });

    const hero = await screen.findByTestId("dashboard-home-morning-hero");
    await waitFor(() => {
      expect(screen.getByTestId("dashboard-home-data-status")).toHaveTextContent("首页快照读取失败");
      expect(screen.getByTestId("dashboard-home-kpi-aum")).toHaveAttribute(
        "data-state",
        "empty",
      );
      expect(screen.getByTestId("dashboard-home-kpi-aum")).toHaveTextContent("—");
      expect(hero).not.toHaveTextContent("3,708.10");
      expect(hero).not.toHaveTextContent("样例");
    });
    expect(screen.getByTestId("dashboard-home-page")).not.toHaveTextContent("服务不可达");
  });

  it("retries an unavailable snapshot from the degraded panel and clears the error state", async () => {
    const mockSource = createApiClient({ mode: "mock" });
    const getHomeSnapshot = vi.fn<ApiClient["getHomeSnapshot"]>()
      .mockRejectedValueOnce(new Error("snapshot unavailable"))
      .mockImplementation(async (options) => mockSource.getHomeSnapshot(options));
    const client = createRealModeHomeClient({ getHomeSnapshot });

    renderWorkbenchApp(["/"], { client });

    await waitFor(() => {
      expect(screen.getByTestId("dashboard-home-data-status")).toHaveAttribute(
        "data-status-kind",
        "error",
      );
    });
    fireEvent.scroll(window);

    const retryButton = await screen.findByTestId("dashboard-home-data-availability-retry");
    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(getHomeSnapshot).toHaveBeenCalledTimes(2);
      expect(screen.getByTestId("dashboard-home-data-status")).not.toHaveAttribute(
        "data-status-kind",
        "error",
      );
    });
    await waitFor(() => {
      const availabilityPanel = screen.queryByTestId("dashboard-home-data-availability");
      expect(availabilityPanel?.getAttribute("data-state")).not.toBe("error");
      expect(availabilityPanel?.textContent ?? "").not.toContain("首页快照读取失败");
    });
  });

  it("keeps the degraded panel visible and disables retry while an unresolved retry is pending", async () => {
    const mockSource = createApiClient({ mode: "mock" });
    type HomeSnapshotEnvelope = Awaited<ReturnType<ApiClient["getHomeSnapshot"]>>;
    let resolveRetry!: (value: HomeSnapshotEnvelope) => void;
    const retryRequest = new Promise<HomeSnapshotEnvelope>((resolve) => {
      resolveRetry = resolve;
    });
    const getHomeSnapshot = vi.fn<ApiClient["getHomeSnapshot"]>()
      .mockRejectedValueOnce(new Error("User is not allowed to read executive."))
      .mockImplementationOnce(() => retryRequest);
    const client = createRealModeHomeClient({ getHomeSnapshot });

    renderWorkbenchApp(["/"], { client });

    await waitFor(() => {
      expect(screen.getByTestId("dashboard-home-data-status")).toHaveAttribute(
        "data-status-kind",
        "error",
      );
    });
    fireEvent.scroll(window);

    const retryButton = await screen.findByTestId("dashboard-home-data-availability-retry");
    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(getHomeSnapshot).toHaveBeenCalledTimes(2);
      expect(screen.getByTestId("dashboard-home-data-availability")).toBeInTheDocument();
      expect(screen.getByTestId("dashboard-home-data-availability-retry")).toBeDisabled();
      expect(screen.getByTestId("dashboard-home-data-availability-retry")).toHaveTextContent(
        "刷新中",
      );
    });

    resolveRetry(await mockSource.getHomeSnapshot());

    await waitFor(() => {
      const availabilityPanel = screen.queryByTestId("dashboard-home-data-availability");
      expect(availabilityPanel?.getAttribute("data-state")).not.toBe("error");
      expect(availabilityPanel?.textContent ?? "").not.toContain("首页快照权限不足");
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
    const reportDateContext = screen.getByTestId("dashboard-home-report-date-context");
    expect(reportDateContext).toHaveTextContent("请求 05/31");
    expect(reportDateContext).toHaveTextContent("实际数据 04/30");
    const updateStamp = screen
      .getByTestId("dashboard-home-toolbar")
      .querySelector('[data-role="dashboard-home-update-stamp"]');
    expect(updateStamp).toHaveTextContent(/\d{4}-\d{2}-\d{2} \d{2}:\d{2}/);
    expect(updateStamp).not.toHaveTextContent("沿用报告日");
    expect(updateStamp).not.toHaveTextContent("上次成功");
    fireEvent.scroll(window);
    expect(
      (await screen.findByTestId("dashboard-home-bottom-grid")).querySelector(
        'small[data-status-kind="stale"]',
      ),
    ).toHaveTextContent("数据偏旧");
  });
});
