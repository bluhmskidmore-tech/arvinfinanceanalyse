import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import {
  DashboardCockpitHeader,
  type DashboardCockpitHeaderProps,
} from "./DashboardCockpitHeader";
import { buildDashboardCockpitHeaderStatus } from "../dashboardCockpitHomeModel";

const baseProps: DashboardCockpitHeaderProps = {
  viewModel: {
    reportDate: "2026-04-30",
    headerStatus: {
      dataUpdatedAt: "09:15",
      dataSyncPrefix: "数据已更新",
      marketStatus: "市场已收盘",
      valuationLabel: "估值已完成",
      valuationTone: "ok" as const,
      dataFreshnessState: "fresh" as const,
      notificationCount: 2,
      riskReviewCount: 3,
      showRiskReview: true,
    },
  },
  toolbarSearch: "",
  onSearchChange: vi.fn(),
  reportDateInput: "",
  onReportDateChange: vi.fn(),
  allowPartial: false,
  onAllowPartialChange: vi.fn(),
  modeLabel: "演示视角",
  onRefresh: vi.fn(),
  refreshLabel: "刷新",
};

function renderHeader(props: Partial<typeof baseProps> = {}) {
  return render(
    <MemoryRouter>
      <DashboardCockpitHeader {...baseProps} {...props} />
    </MemoryRouter>,
  );
}

describe("DashboardCockpitHeader", () => {
  it("keeps non-ISO report date labels out of the native date input", () => {
    renderHeader({
      viewModel: {
        ...baseProps.viewModel,
        reportDate: "最新可用",
      },
      reportDateInput: "最新报告日",
    });

    expect(screen.getByLabelText("报告日")).toHaveValue("");
  });

  it("prefers an ISO requested report date when available", () => {
    renderHeader({
      viewModel: {
        ...baseProps.viewModel,
        reportDate: "最新可用",
      },
      reportDateInput: "2026-04-30",
    });

    expect(screen.getByLabelText("报告日")).toHaveValue("2026-04-30");
  });

  it("surfaces missing snapshot time as pending valuation status", () => {
    const headerStatus = buildDashboardCockpitHeaderStatus({
      reportDate: "2026-04-30",
      alertCount: 0,
      useMockFallback: false,
    });

    renderHeader({
      viewModel: {
        ...baseProps.viewModel,
        headerStatus,
      },
    });

    expect(screen.getByText("数据时间待同步 待同步")).toBeInTheDocument();
    expect(screen.getByText("估值待同步")).toBeInTheDocument();
  });
});
