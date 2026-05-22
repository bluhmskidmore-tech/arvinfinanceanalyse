import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { DashboardCockpitHeader } from "./DashboardCockpitHeader";

const baseProps = {
  viewModel: {
    reportDate: "2026-04-30",
    headerStatus: {
      dataUpdatedAt: "09:15",
      marketStatus: "市场已收盘",
      notificationCount: 2,
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
});
