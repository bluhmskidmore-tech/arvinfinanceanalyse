import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ComponentProps } from "react";
import { MemoryRouter } from "react-router-dom";

import type { DashboardHomeView } from "../dashboardHomeView";
import { DashboardHomeToolbar } from "./DashboardHomeToolbar";

const headerStatus: DashboardHomeView["headerStatus"] = {
  dataStatusKind: "ok",
  dataUpdatedAt: "09:15",
  marketStatus: "市场同步",
  valuationLabel: "估值完成",
  valuationTone: "ok",
  riskReviewCount: 0,
  showRiskReview: false,
  dataSyncPrefix: "数据更新",
};

function renderToolbar(overrides: Partial<ComponentProps<typeof DashboardHomeToolbar>> = {}) {
  const props: ComponentProps<typeof DashboardHomeToolbar> = {
    headerStatus,
    reportDateInput: "2026-04-30",
    onReportDateChange: vi.fn(),
    toolbarSearch: "",
    onSearchChange: vi.fn(),
    allowPartial: false,
    onAllowPartialChange: vi.fn(),
    onRefresh: vi.fn(),
    refreshLabel: "刷新",
    ...overrides,
  };

  render(
    <MemoryRouter>
      <DashboardHomeToolbar {...props} />
    </MemoryRouter>,
  );

  return props;
}

describe("DashboardHomeToolbar", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("uses a native date input for report date selection", () => {
    const showPicker = vi.fn();
    Object.defineProperty(HTMLInputElement.prototype, "showPicker", {
      configurable: true,
      value: showPicker,
    });
    const onReportDateChange = vi.fn();

    renderToolbar({ onReportDateChange });

    const reportDateInput = screen.getByLabelText("报告日") as HTMLInputElement;
    expect(reportDateInput).toHaveAttribute("type", "date");

    fireEvent.click(reportDateInput);
    expect(showPicker).toHaveBeenCalledTimes(1);

    fireEvent.change(reportDateInput, { target: { value: "2026-03-31" } });
    expect(onReportDateChange).toHaveBeenCalledWith("2026-03-31");
  });
});
