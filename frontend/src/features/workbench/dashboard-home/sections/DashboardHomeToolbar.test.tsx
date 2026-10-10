import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ComponentProps } from "react";
import { MemoryRouter, useLocation } from "react-router-dom";

import { mapToHomeFirstScreenView } from "../dashboardHomeFirstScreenView";
import type { HomeHeaderStatus } from "../dashboardHomeFirstScreenTypes";
import { DashboardHomeToolbar } from "./DashboardHomeToolbar";

const headerStatus: HomeHeaderStatus = {
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

  it("blocks the partial-data toggle until backend date and null semantics are reliable", () => {
    const onAllowPartialChange = vi.fn();
    renderToolbar({ allowPartial: true, onAllowPartialChange });

    const blockedToggle = screen.getByLabelText("仅完整数据");
    expect(blockedToggle).not.toBeChecked();
    expect(blockedToggle).toBeDisabled();
    fireEvent.click(blockedToggle);
    expect(onAllowPartialChange).not.toHaveBeenCalled();
  });

  it("uses readable copy when the partial-data mode is explicitly supported", () => {
    const { rerender } = render(
      <MemoryRouter>
        <DashboardHomeToolbar
          {...makeToolbarProps({ allowPartial: true, partialModeSupported: true })}
        />
      </MemoryRouter>,
    );

    expect(screen.getByLabelText("显示部分数据")).toBeChecked();

    rerender(
      <MemoryRouter>
        <DashboardHomeToolbar
          {...makeToolbarProps({ allowPartial: false, partialModeSupported: true })}
        />
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
  it("keeps the toolbar in a loading state without inventing a failure outage", () => {
    const view = mapToHomeFirstScreenView({
      reportDate: "2026-04-30",
      useMockFallback: false,
      verdict: null,
      metrics: [],
      attribution: null,
      bondHeadline: null,
      portfolio: null,
      snapshotMeta: null,
      alertCount: 0,
      snapshotUnavailable: false,
      snapshotStale: false,
      snapshotLoading: true,
    });
    expect(view.headerStatus.dataStatusKind).toBe("loading");

    renderToolbar({
      headerStatus: view.headerStatus,
      reportDateInput: view.reportDate,
      reportDateContext: view.reportDateContext,
      terminalKpis: view.terminalKpis,
      decisionActions: view.decisionRail.actions,
    });

    expect(screen.getByTestId("dashboard-home-data-status")).toHaveTextContent("读取中");
  });

  it("keeps the update time only in the left stamp, not in the data status pill", () => {
    renderToolbar();

    // 左侧“更新 …”是全页更新时间的唯一出处（fixture 无 generatedAt，回落到 dataUpdatedAt）。
    expect(screen.getByText("更新 09:15")).toBeInTheDocument();

    const dataStatusPill = screen.getByTestId("dashboard-home-data-status");
    expect(dataStatusPill).not.toHaveTextContent("09:15");
    expect(dataStatusPill).toHaveAttribute("data-status-kind", "ok");
  });

  it("collapses both normal-state pills into one muted note and keeps the originals in title", () => {
    renderToolbar();

    const quietNote = screen.getByTestId("dashboard-home-data-status");
    expect(quietNote).toHaveTextContent("快照与估值正常");
    expect(quietNote).toHaveAttribute("title", "数据更新；市场同步 · 估值完成");
    expect(quietNote).not.toHaveTextContent("数据更新");
    expect(quietNote).not.toHaveTextContent("估值完成");
    expect(
      screen.getByTestId("dashboard-home-toolbar").querySelector(
        '[data-role="dashboard-home-market-status"]',
      ),
    ).toBeNull();
    const statusRow = screen.getByTestId("dashboard-home-toolbar").querySelector(
      '[data-role="dashboard-home-status-row"]',
    );
    expect(statusRow?.children).toHaveLength(1);
  });

  it("keeps the semantic stale pill copy when the snapshot state is abnormal", () => {
    renderToolbar({
      headerStatus: {
        ...headerStatus,
        dataStatusKind: "stale",
        dataSyncPrefix: "展示上一版本",
        marketStatus: "新报告日失败",
        valuationLabel: "沿用旧快照",
        valuationTone: "warn",
      },
    });

    const dataStatusPill = screen.getByTestId("dashboard-home-data-status");
    expect(dataStatusPill).toHaveAttribute("data-status-kind", "stale");
    expect(dataStatusPill).toHaveTextContent("展示上一版本");
    expect(dataStatusPill).not.toHaveTextContent("快照与估值正常");
    expect(screen.getByTitle("新报告日失败 · 沿用旧快照")).toHaveTextContent("沿用旧快照");
  });

  it("keeps the amber tone marker when the valuation state is abnormal", () => {
    renderToolbar({
      headerStatus: {
        ...headerStatus,
        marketStatus: "新报告日失败",
        valuationLabel: "沿用旧快照",
        valuationTone: "warn",
      },
    });

    const marketPill = screen.getByTitle("新报告日失败 · 沿用旧快照");
    expect(marketPill).toHaveAttribute("data-valuation-tone", "warn");
    expect(marketPill).toHaveTextContent("沿用旧快照");
  });

  describe("report date age hint", () => {
    const now = new Date(2026, 8, 2, 16, 0);
    const ageHint = () =>
      screen
        .getByTestId("dashboard-home-toolbar")
        .querySelector('[data-role="dashboard-home-report-date-age"]');

    it("flags a report date that is 33 days old in the warning tone with the full sentence in title", () => {
      renderToolbar({
        now,
        reportDateInput: "2026-07-31",
        reportDateContext: {
          requestedDate: "",
          actualDataDate: "2026-07-31",
          divergenceReason: null,
          dataAsOfDate: "2026-07-31",
          generatedAt: "2026-09-02T15:03:41",
          mode: "exact",
        },
      });

      const hint = ageHint();
      expect(hint).toHaveTextContent("距今 33 天");
      expect(hint).toHaveAttribute("data-age-tone", "warn");
      expect(hint).toHaveAttribute(
        "title",
        "报告日 2026-07-31，距今 33 天；最近更新 2026-09-02 15:03",
      );
    });

    it("uses the muted tone when the report date is only a few days old", () => {
      renderToolbar({
        now,
        reportDateInput: "2026-08-30",
        reportDateContext: {
          requestedDate: "",
          actualDataDate: "2026-08-30",
          divergenceReason: null,
          dataAsOfDate: "2026-08-30",
          mode: "exact",
        },
      });

      const hint = ageHint();
      expect(hint).toHaveTextContent("距今 3 天");
      expect(hint).toHaveAttribute("data-age-tone", "muted");
    });

    it("renders nothing for a same-day report date", () => {
      renderToolbar({
        now,
        reportDateInput: "2026-09-02",
        reportDateContext: {
          requestedDate: "",
          actualDataDate: "2026-09-02",
          divergenceReason: null,
          dataAsOfDate: "2026-09-02",
          mode: "exact",
        },
      });

      expect(ageHint()).toBeNull();
    });

    it("renders nothing when the actual data date is missing", () => {
      renderToolbar({
        now,
        reportDateInput: "",
        reportDateContext: {
          requestedDate: "2026-09-01",
          actualDataDate: "",
          divergenceReason: "no snapshot",
          dataAsOfDate: "",
          mode: "empty",
        },
      });

      expect(ageHint()).toBeNull();
    });

    it("renders nothing when the actual data date is malformed", () => {
      renderToolbar({
        now,
        reportDateContext: {
          requestedDate: "",
          actualDataDate: "not-a-date",
          divergenceReason: null,
          dataAsOfDate: "",
          mode: "exact",
        },
      });

      expect(ageHint()).toBeNull();
    });
  });

  it("keeps the clickable risk-review pill with its count", () => {
    renderToolbar({
      headerStatus: { ...headerStatus, showRiskReview: true, riskReviewCount: 3 },
    });

    const riskLink = screen.getByRole("link", { name: /风险待复核/ });
    expect(riskLink).toHaveAttribute("href", "/decision-items");
    expect(riskLink).toHaveTextContent("3");
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
