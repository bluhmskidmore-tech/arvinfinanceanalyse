import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ComponentProps } from "react";
import { MemoryRouter, useLocation } from "react-router-dom";

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

function LocationProbe() {
  const location = useLocation();
  return (
    <output data-testid="toolbar-location-probe">
      {`${location.pathname}${location.search}${location.hash}`}
    </output>
  );
}

function makeToolbarProps(
  overrides: Partial<ComponentProps<typeof DashboardHomeToolbar>> = {},
): ComponentProps<typeof DashboardHomeToolbar> {
  return {
    headerStatus,
    reportDateInput: "2026-04-30",
    onReportDateChange: vi.fn(),
    reportDateContext: {
      requestedDate: "",
      actualDataDate: "2026-04-30",
      divergenceReason: null,
      dataAsOfDate: "2026-04-30 16:00",
      mode: "exact",
    },
    toolbarSearch: "",
    onSearchChange: vi.fn(),
    terminalKpis: [],
    decisionActions: [],
    allowPartial: false,
    onAllowPartialChange: vi.fn(),
    onRefresh: vi.fn(),
    refreshLabel: "刷新",
    ...overrides,
  };
}

function renderToolbar(overrides: Partial<ComponentProps<typeof DashboardHomeToolbar>> = {}) {
  const props = makeToolbarProps(overrides);
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

  it("uses readable copy for the partial-data toggle", () => {
    const { rerender } = render(
      <MemoryRouter>
        <DashboardHomeToolbar {...makeToolbarProps({ allowPartial: true })} />
      </MemoryRouter>,
    );

    expect(screen.getByLabelText("显示部分数据")).toBeChecked();

    rerender(
      <MemoryRouter>
        <DashboardHomeToolbar {...makeToolbarProps({ allowPartial: false })} />
      </MemoryRouter>,
    );

    expect(screen.getByLabelText("仅完整数据")).not.toBeChecked();
  });
  it("passes the actual data date to search navigation", () => {
    render(
      <MemoryRouter>
        <DashboardHomeToolbar
          {...makeToolbarProps({
            reportDateInput: "2026-05-01",
            reportDateContext: {
              requestedDate: "2026-05-01",
              actualDataDate: "2026-04-30",
              divergenceReason: "fallback",
              dataAsOfDate: "2026-04-30 16:00",
              mode: "fallback",
            },
            toolbarSearch: "Open search action",
            decisionActions: [
              {
                id: "search-action",
                title: "Open search action",
                priority: "high",
                sourceLabel: "risk",
                reason: "Review the risk queue",
                to: "/risk-overview?tab=limits#breaches",
                statusKind: "ready",
              },
            ],
          })}
        />
        <LocationProbe />
      </MemoryRouter>,
    );
    const input = screen.getByRole("combobox");
    fireEvent.focus(input);
    fireEvent.keyDown(input, { key: "Enter" });

    expect(screen.getByTestId("toolbar-location-probe")).toHaveTextContent(
      "/risk-overview?tab=limits&report_date=2026-04-30#breaches",
    );
  });
  it("does not invent a report date when no actual data date exists", () => {
    render(
      <MemoryRouter>
        <DashboardHomeToolbar
          {...makeToolbarProps({
            reportDateInput: "2026-05-01",
            reportDateContext: {
              requestedDate: "2026-05-01",
              actualDataDate: "",
              divergenceReason: "no snapshot",
              dataAsOfDate: "",
              mode: "empty",
            },
            toolbarSearch: "Open no-date action",
            decisionActions: [
              {
                id: "no-date-search-action",
                title: "Open no-date action",
                priority: "high",
                sourceLabel: "risk",
                reason: "Review the risk queue",
                to: "/risk-overview?tab=limits#breaches",
                statusKind: "ready",
              },
            ],
          })}
        />
        <LocationProbe />
      </MemoryRouter>,
    );
    const input = screen.getByRole("combobox");
    fireEvent.focus(input);
    fireEvent.keyDown(input, { key: "Enter" });

    expect(screen.getByTestId("toolbar-location-probe")).toHaveTextContent(
      "/risk-overview?tab=limits#breaches",
    );
  });
});
