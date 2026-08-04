import * as React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import { runPollingTask } from "../app/jobs/polling";
import type { Numeric, ResultMeta } from "../api/contracts";
import type { ActionAttributionResponse } from "../features/bond-analytics/types";
import { formatRawAsNumeric } from "../utils/format";

vi.mock("../mocks/navigation", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../mocks/navigation")>()),
  isAgentFrontendEnabled: () => true,
}));

let latestOverviewProps: Record<string, unknown> | null = null;
let latestDetailProps: Record<string, unknown> | null = null;
let detailMountSeq = 0;
const lazyModuleLoads = vi.hoisted(() => ({ detail: 0 }));

vi.mock("../app/jobs/polling", () => ({
  runPollingTask: vi.fn(),
}));

vi.mock("../features/bond-analytics/components/BondAnalyticsOverviewPanels", () => ({
  BondAnalyticsOverviewPanels: function MockBondAnalyticsOverviewPanels(props: Record<string, unknown>) {
      latestOverviewProps = props;
      return (
        <div data-testid="mock-bond-analytics-overview-panels">
          <button
            type="button"
            data-testid="trigger-open-credit-spread"
            onClick={() =>
              (props.onOpenModuleDetail as (key: string) => void)("credit-spread")
            }
          >
            open credit-spread
          </button>
          <button
            type="button"
            data-testid="trigger-report-date"
            onClick={() => (props.onReportDateChange as (d: string) => void)("2025-12-31")}
          >
            set report date
          </button>
          <button
            type="button"
            data-testid="trigger-period-type"
            onClick={() => (props.onPeriodTypeChange as (p: string) => void)("YTD")}
          >
            set period type
          </button>
          <button
            type="button"
            data-testid="trigger-refresh"
            onClick={() => (props.onRefreshAnalytics as () => void)()}
          >
            refresh
          </button>
          <span data-testid="overview-last-run-id">
            {String(props.lastAnalyticsRefreshRunId ?? "")}
          </span>
          <span data-testid="overview-refresh-error">{String(props.analyticsRefreshError ?? "")}</span>
        </div>
      );
  },
}));

vi.mock("../features/bond-analytics/components/BondAnalyticsDetailSection", () => {
  lazyModuleLoads.detail += 1;
  return {
    BondAnalyticsDetailSection: function MockBondAnalyticsDetailSection(
      props: Record<string, unknown>,
    ) {
      const instance = React.useMemo(() => {
        detailMountSeq += 1;
        return detailMountSeq;
      }, []);
      latestDetailProps = props;
      return (
        <div
          data-testid="mock-bond-analytics-detail-section"
          data-detail-instance={instance}
          data-active-tab={String(props.activeTab)}
        />
      );
    },
  };
});

vi.mock("../features/bond-analytics/components/RiskTrendChart", () => ({
  default: function MockRiskTrendChart() {
    return <div data-testid="mock-risk-trend-chart" />;
  },
}));

vi.mock("../features/bond-analytics/components/BondEventCalendar", () => ({
  default: function MockBondEventCalendar() {
    return <div data-testid="mock-bond-event-calendar" />;
  },
}));

vi.mock("../features/agent/AgentPanel", () => ({
  AgentPanel: function MockAgentPanel({
    pageId,
    reportDate = null,
    currentFilters = {},
    defaultFilters = {},
    selectedRows = [],
    contextNote = null,
  }: {
    pageId: string;
    reportDate?: string | null;
    currentFilters?: Record<string, unknown>;
    defaultFilters?: Record<string, unknown>;
    selectedRows?: Array<Record<string, unknown>>;
    contextNote?: string | null;
  }) {
    const pageContext = {
      page_id: pageId,
      current_filters:
        reportDate != null
          ? { ...defaultFilters, ...currentFilters, report_date: reportDate }
          : { ...defaultFilters, ...currentFilters },
      selected_rows: selectedRows,
      context_note: contextNote,
    };
    return (
      <div data-testid="agent-panel">
        <code data-testid="agent-panel-page-context">{JSON.stringify(pageContext)}</code>
      </div>
    );
  },
}));

import { BondAnalyticsViewContent } from "../features/bond-analytics/components/BondAnalyticsViewContent";

const runPollingTaskMock = vi.mocked(runPollingTask);

function numeric(
  raw: number | null,
  unit: Numeric["unit"],
  signAware = false,
  precision?: number,
): Numeric {
  return formatRawAsNumeric({
    raw,
    unit,
    sign_aware: signAware,
    ...(precision === undefined ? {} : { precision }),
  });
}

const yuan = (raw: number | null) => numeric(raw, "yuan", true);
const ratio = (raw: number | null, precision?: number) => numeric(raw, "ratio", false, precision);
const dv01 = (raw: number | null, precision?: number) => numeric(raw, "dv01", false, precision);

function createResultMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_test",
    basis: "formal",
    result_kind: "bond_analytics.action_attribution",
    formal_use_allowed: true,
    source_version: "sv_test",
    vendor_version: "vv_test",
    rule_version: "rv_test",
    cache_version: "cv_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-12T00:00:00Z",
    ...overrides,
  };
}

function createActionAttributionResult(
  overrides: Partial<ActionAttributionResponse> = {},
): ActionAttributionResponse {
  return {
    report_date: "2026-03-31",
    period_type: "MoM",
    period_start: "2026-03-01",
    period_end: "2026-03-31",
    total_actions: 1,
    total_pnl_from_actions: yuan(100),
    by_action_type: [],
    action_details: [],
    period_start_duration: ratio(3),
    period_end_duration: ratio(3),
    duration_change_from_actions: ratio(0),
    period_start_dv01: dv01(0),
    period_end_dv01: dv01(0),
    warnings: [],
    computed_at: "2026-04-12T00:00:00Z",
    ...overrides,
  };
}

function createActionAttributionEnvelope() {
  return {
    result_meta: createResultMeta(),
    result: createActionAttributionResult(),
  };
}

function renderViewContent(
  client = createApiClient({ mode: "mock" }),
  queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false },
    },
  }),
) {
  latestOverviewProps = null;
  latestDetailProps = null;

  return render(
    <MemoryRouter>
      <ApiClientProvider client={client}>
        <QueryClientProvider client={queryClient}>
          <BondAnalyticsViewContent />
        </QueryClientProvider>
      </ApiClientProvider>
    </MemoryRouter>,
  );
}

describe("BondAnalyticsViewContent", () => {
  beforeEach(() => {
    detailMountSeq = 0;
    runPollingTaskMock.mockReset();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("does not preload the detail module before the drilldown is opened", async () => {
    const user = userEvent.setup();
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsDates: vi.fn(async () => ({
        result_meta: createResultMeta({ result_kind: "bond_analytics.dates" }),
        result: { report_dates: ["2026-03-31"] },
      })),
      getBondAnalyticsActionAttribution: vi.fn(async () => createActionAttributionEnvelope()),
    };

    renderViewContent(client);

    await screen.findByTestId("mock-bond-analytics-overview-panels");
    await vi.dynamicImportSettled();

    expect(screen.getByTestId("bond-analysis-detail-drilldown")).not.toHaveAttribute("open");
    expect(lazyModuleLoads.detail).toBe(0);

    await user.click(screen.getByTestId("trigger-open-credit-spread"));

    expect(await screen.findByTestId("mock-bond-analytics-detail-section")).toBeInTheDocument();
    expect(lazyModuleLoads.detail).toBe(1);
  });

  it("defers detail wiring until a drilldown is opened", async () => {
    const user = userEvent.setup();
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsDates: vi.fn(async () => ({
        result_meta: createResultMeta({ result_kind: "bond_analytics.dates" }),
        result: { report_dates: ["2026-03-31"] },
      })),
      getBondAnalyticsActionAttribution: vi.fn(async () => createActionAttributionEnvelope()),
    };
    renderViewContent(client);

    await screen.findByTestId("mock-bond-analytics-overview-panels");

    await waitFor(() => {
      expect(latestOverviewProps?.reportDate).toBeTruthy();
    });

    const firstDate = (latestOverviewProps?.dateOptions as { value: string }[])[0]?.value;
    expect(firstDate).toBeTruthy();
    expect(latestOverviewProps?.reportDate).toBe(firstDate);
    expect(latestOverviewProps?.periodType).toBe("MoM");
    expect(screen.getByTestId("bond-analysis-detail-drilldown")).not.toHaveAttribute("open");
    expect(screen.queryByTestId("mock-bond-analytics-detail-section")).not.toBeInTheDocument();
    expect(latestDetailProps).toBeNull();

    await user.click(screen.getByTestId("trigger-open-credit-spread"));

    expect(await screen.findByTestId("mock-bond-analytics-detail-section")).toHaveAttribute(
      "data-active-tab",
      "credit-spread",
    );
    expect(latestDetailProps?.reportDate).toBe(firstDate);
    expect(latestDetailProps?.periodType).toBe("MoM");
    expect(latestDetailProps?.activeTab).toBe("credit-spread");
    expect(client.getBondAnalyticsActionAttribution).toHaveBeenCalled();
  });

  it("keeps a large report-date list out of the closed DOM and selects an exact searched date", async () => {
    const user = userEvent.setup();
    const reportDates = Array.from({ length: 521 }, (_, index) =>
      new Date(Date.UTC(2026, 11, 31 - index)).toISOString().slice(0, 10),
    );
    const targetReportDate = reportDates[400]!;
    const getBondAnalyticsActionAttribution = vi.fn(async () =>
      createActionAttributionEnvelope(),
    );
    const getResearchCalendarEvents = vi.fn(async () => []);
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsDates: vi.fn(async () => ({
        result_meta: createResultMeta({ result_kind: "bond_analytics.dates" }),
        result: { report_dates: reportDates },
      })),
      getBondAnalyticsActionAttribution,
      getResearchCalendarEvents,
    };

    renderViewContent(client);

    await screen.findByTestId("mock-bond-analytics-overview-panels");
    await waitFor(() => {
      expect(latestOverviewProps?.reportDate).toBe(reportDates[0]);
    });

    expect(document.querySelectorAll("option").length).toBeLessThan(50);

    const reportDateInput = screen.getByRole("combobox", { name: "报告日" });
    await user.click(reportDateInput);
    const listbox = await screen.findByRole("listbox");
    expect(listbox.querySelectorAll('[role="option"]').length).toBeLessThan(50);
    expect(document.querySelector(".ant-select-dropdown")?.className).toContain(
      "toolbarDateDropdown",
    );
    await user.type(reportDateInput, targetReportDate);
    await user.click(await screen.findByTitle(targetReportDate));

    await waitFor(() => {
      expect(latestOverviewProps?.reportDate).toBe(targetReportDate);
      expect(getBondAnalyticsActionAttribution).toHaveBeenLastCalledWith(
        targetReportDate,
        "MoM",
      );
      expect(getResearchCalendarEvents).toHaveBeenLastCalledWith({
        reportDate: targetReportDate,
      });
    });
  });

  it("puts the workstation overview directly after the toolbar", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsDates: vi.fn(async () => ({
        result_meta: createResultMeta({ result_kind: "bond_analytics.dates" }),
        result: { report_dates: ["2026-03-31"] },
      })),
      getBondAnalyticsActionAttribution: vi.fn(async () => ({
        result_meta: createResultMeta({
          quality_flag: "warning",
          fallback_mode: "latest_snapshot",
          result_kind: "bond_analytics.action_attribution",
        }),
        result: createActionAttributionResult({
          total_actions: 4,
          total_pnl_from_actions: yuan(250_000_000),
          duration_change_from_actions: ratio(-0.12),
          period_start_dv01: dv01(120_000),
          period_end_dv01: dv01(132_000),
          warnings: ["duration input unavailable - set to 0"],
        }),
      })),
    };

    renderViewContent(client);

    const toolbar = await screen.findByTestId("bond-analysis-toolbar");
    const overview = await screen.findByTestId("mock-bond-analytics-overview-panels");
    const detail = screen.getByTestId("bond-analysis-detail-drilldown");

    expect(screen.queryByTestId("bond-analysis-decision-cockpit")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(toolbar.compareDocumentPosition(overview)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(overview.compareDocumentPosition(detail)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(detail).toHaveTextContent("复核入口");
    expect(detail).toHaveTextContent("下钻证据与参数");
    expect(detail).toHaveTextContent("不在底部生成新的方向性结论");
    expect(detail).not.toHaveTextContent("分析师解读");
    await waitFor(() => {
      expect(latestOverviewProps?.actionAttributionResult).toEqual(
        expect.objectContaining({
          total_actions: 4,
        }),
      );
    });
    expect(detail).not.toHaveAttribute("open");
    expect(screen.queryByTestId("mock-bond-analytics-detail-section")).not.toBeInTheDocument();
    expect(latestDetailProps).toBeNull();
  });

  it("keeps the workstation visible when action-attribution evidence fails", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsDates: vi.fn(async () => ({
        result_meta: createResultMeta({ result_kind: "bond_analytics.dates" }),
        result: { report_dates: ["2026-03-31"] },
      })),
      getBondAnalyticsActionAttribution: vi.fn(async () => {
        throw new Error("backend 503 for action attribution");
      }),
    };

    renderViewContent(client);

    await screen.findByTestId("mock-bond-analytics-overview-panels");

    await waitFor(() => {
      expect(client.getBondAnalyticsActionAttribution).toHaveBeenCalledWith("2026-03-31", "MoM");
    });
    expect(screen.queryByTestId("bond-analysis-decision-cockpit")).not.toBeInTheDocument();
    expect(latestOverviewProps?.actionAttributionResult).toBeNull();
  });

  it("does not render a decision cockpit when no report date can be resolved", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsDates: vi.fn(async () => ({
        result_meta: createResultMeta({ result_kind: "bond_analytics.dates" }),
        result: { report_dates: [] },
      })),
      getBondAnalyticsActionAttribution: vi.fn(async () => createActionAttributionEnvelope()),
    };

    renderViewContent(client);

    await waitFor(() => {
      expect(client.getBondAnalyticsDates).toHaveBeenCalled();
      expect(client.getBondAnalyticsActionAttribution).not.toHaveBeenCalled();
    });
    expect(screen.queryByTestId("bond-analysis-decision-cockpit")).not.toBeInTheDocument();
  });

  it("loads research calendar events for the effective report date and passes them to the overview panels", async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, refetchOnWindowFocus: false },
      },
    });
    const getResearchCalendarEvents = vi.fn(async () => [
      {
        id: "rc_bond_001",
        date: "2026-03-31",
        title: "政策性金融债招标",
        kind: "auction" as const,
        severity: "high" as const,
        amount_label: "420 亿元",
        note: "国开行",
      },
    ]);
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsDates: vi.fn(async () => ({
        result_meta: createResultMeta({ result_kind: "bond_analytics.dates" }),
        result: { report_dates: ["2026-03-31"] },
      })),
      getBondAnalyticsActionAttribution: vi.fn(async () => createActionAttributionEnvelope()),
      getResearchCalendarEvents,
    };
    renderViewContent(client, queryClient);

    await screen.findByTestId("mock-bond-analytics-overview-panels");

    await waitFor(() => {
      expect(latestOverviewProps?.calendarItems).toEqual([
        expect.objectContaining({
          event: "政策性金融债招标",
          level: "high",
        }),
      ]);
    });

    expect(getResearchCalendarEvents).toHaveBeenCalledWith({ reportDate: "2026-03-31" });
  });

  it("refetches research calendar events when the client mode changes", async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, refetchOnWindowFocus: false },
      },
    });
    const getMockResearchCalendarEvents = vi.fn(async () => [
      {
        id: "rc_mock",
        date: "2026-03-31",
        title: "mock calendar",
        kind: "internal" as const,
        severity: "medium" as const,
      },
    ]);
    const getRealResearchCalendarEvents = vi.fn(async () => [
      {
        id: "rc_real",
        date: "2026-03-31",
        title: "real calendar",
        kind: "internal" as const,
        severity: "high" as const,
      },
    ]);
    const mockClient = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsDates: vi.fn(async () => ({
        result_meta: createResultMeta({ result_kind: "bond_analytics.dates" }),
        result: { report_dates: ["2026-03-31"] },
      })),
      getBondAnalyticsActionAttribution: vi.fn(async () => createActionAttributionEnvelope()),
      getResearchCalendarEvents: getMockResearchCalendarEvents,
    };
    const realClient = {
      ...createApiClient({ mode: "real" }),
      getBondAnalyticsDates: vi.fn(async () => ({
        result_meta: createResultMeta({ result_kind: "bond_analytics.dates" }),
        result: { report_dates: ["2026-03-31"] },
      })),
      getBondAnalyticsActionAttribution: vi.fn(async () => createActionAttributionEnvelope()),
      getResearchCalendarEvents: getRealResearchCalendarEvents,
    };

    const view = renderViewContent(mockClient, queryClient);

    await waitFor(() => {
      expect(getMockResearchCalendarEvents).toHaveBeenCalledWith({ reportDate: "2026-03-31" });
    });
    await waitFor(() => {
      expect(latestOverviewProps?.calendarItems).toEqual([
        expect.objectContaining({ event: "mock calendar", level: "medium" }),
      ]);
    });

    view.rerender(
      <MemoryRouter>
        <ApiClientProvider client={realClient}>
          <QueryClientProvider client={queryClient}>
            <BondAnalyticsViewContent />
          </QueryClientProvider>
        </ApiClientProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(getRealResearchCalendarEvents).toHaveBeenCalledWith({ reportDate: "2026-03-31" });
    });
    await waitFor(() => {
      expect(latestOverviewProps?.calendarItems).toEqual([
        expect.objectContaining({ event: "real calendar", level: "high" }),
      ]);
    });
    expect(getMockResearchCalendarEvents).toHaveBeenCalledTimes(1);
    expect(getRealResearchCalendarEvents).toHaveBeenCalledTimes(1);
  });

  it("propagates overview interactions into the detail mock", async () => {
    const user = userEvent.setup();
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsActionAttribution: vi.fn(async () => createActionAttributionEnvelope()),
    };
    renderViewContent(client);

    await screen.findByTestId("mock-bond-analytics-overview-panels");

    await user.click(screen.getByTestId("trigger-open-credit-spread"));
    await waitFor(() => {
      expect(latestDetailProps?.activeTab).toBe("credit-spread");
    });

    await user.click(screen.getByTestId("trigger-report-date"));
    await waitFor(() => {
      expect(latestDetailProps?.reportDate).toBe("2025-12-31");
    });

    await user.click(screen.getByTestId("trigger-period-type"));
    await waitFor(() => {
      expect(latestDetailProps?.periodType).toBe("YTD");
    });
  });

  it("surfaces successful refresh run id to overview and remounts the detail mock", async () => {
    const user = userEvent.setup();

    runPollingTaskMock.mockImplementation(async (options) => {
      const onUpdate = options.onUpdate as ((p: { run_id?: string; status: string }) => void) | undefined;
      onUpdate?.({ run_id: "run-success", status: "processing" });
      return { status: "completed", run_id: "run-success" };
    });

    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsActionAttribution: vi.fn(async () => createActionAttributionEnvelope()),
    };

    renderViewContent(client);

    await screen.findByTestId("mock-bond-analytics-overview-panels");
    await waitFor(() => {
      expect(latestOverviewProps?.reportDate).toBeTruthy();
    });
    await user.click(screen.getByTestId("trigger-open-credit-spread"));
    await screen.findByTestId("mock-bond-analytics-detail-section");
    const instanceBefore = screen
      .getByTestId("mock-bond-analytics-detail-section")
      .getAttribute("data-detail-instance");

    await user.click(screen.getByTestId("trigger-refresh"));

    await waitFor(() => {
      expect(screen.getByTestId("overview-last-run-id")).toHaveTextContent("run-success");
    });

    expect(latestOverviewProps?.lastAnalyticsRefreshRunId).toBe("run-success");

    await waitFor(() => {
      const after = screen
        .getByTestId("mock-bond-analytics-detail-section")
        .getAttribute("data-detail-instance");
      expect(after).not.toBe(instanceBefore);
    });
  });

  it("surfaces refresh failure to overview when polling does not complete", async () => {
    const user = userEvent.setup();

    runPollingTaskMock.mockResolvedValue({
      status: "failed",
      run_id: "run-bad",
      error_message: "refresh stopped",
    });

    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsActionAttribution: vi.fn(async () => createActionAttributionEnvelope()),
    };

    renderViewContent(client);

    await screen.findByTestId("mock-bond-analytics-overview-panels");
    await waitFor(() => {
      expect(latestOverviewProps?.reportDate).toBeTruthy();
    });

    await user.click(screen.getByTestId("trigger-refresh"));

    await waitFor(() => {
      expect(screen.getByTestId("overview-refresh-error")).not.toHaveTextContent("");
    });

    expect(String(latestOverviewProps?.analyticsRefreshError ?? "")).toContain("refresh stopped");
  });

  it("surfaces refresh failure to overview when polling rejects", async () => {
    const user = userEvent.setup();

    runPollingTaskMock.mockRejectedValue(new Error("network down"));

    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsActionAttribution: vi.fn(async () => createActionAttributionEnvelope()),
    };

    renderViewContent(client);

    await screen.findByTestId("mock-bond-analytics-overview-panels");
    await waitFor(() => {
      expect(latestOverviewProps?.reportDate).toBeTruthy();
    });

    await user.click(screen.getByTestId("trigger-refresh"));

    await waitFor(() => {
      expect(screen.getByTestId("overview-refresh-error")).toHaveTextContent("network down");
    });
  });

  it("opens the review copilot drawer with the bond-analysis page context", { timeout: 45_000 }, async () => {
    const user = userEvent.setup();
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsDates: vi.fn(async () => ({
        result_meta: createResultMeta({ result_kind: "bond_analytics.dates" }),
        result: { report_dates: ["2026-03-31"] },
      })),
      getBondAnalyticsActionAttribution: vi.fn(async () => createActionAttributionEnvelope()),
    };

    renderViewContent(client);

    await screen.findByTestId("mock-bond-analytics-overview-panels");
    await waitFor(() => {
      expect(latestOverviewProps?.reportDate).toBe("2026-03-31");
    });

    await user.click(screen.getByTestId("bond-analysis-agent-open"));

    expect(
      await screen.findByTestId("bond-analysis-agent-drawer", undefined, { timeout: 30_000 }),
    ).toBeInTheDocument();

    const contextCode = await screen.findByTestId("agent-panel-page-context", undefined, {
      timeout: 10_000,
    });
    const pageContext = JSON.parse(contextCode.textContent ?? "{}") as {
      page_id: string;
      current_filters: Record<string, unknown>;
      selected_rows: unknown[];
      context_note: string | null;
    };

    expect(pageContext.page_id).toBe("bond-analysis");
    expect(pageContext.current_filters.report_date).toBe("2026-03-31");
    expect(pageContext.current_filters.period_type).toBe("MoM");
    expect(pageContext.current_filters.asset_class).toBe("all");
    expect(pageContext.current_filters.accounting_class).toBe("all");
    expect(pageContext.selected_rows).toEqual([]);
    expect(pageContext.context_note).toContain("债券分析");
  });
});
