import * as React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import { runPollingTask } from "../app/jobs/polling";
import type { Numeric, ResultMeta } from "../api/contracts";
import type { ActionAttributionResponse } from "../features/bond-analytics/types";
import { formatRawAsNumeric } from "../utils/format";

let latestOverviewProps: Record<string, unknown> | null = null;
let latestDetailProps: Record<string, unknown> | null = null;
let detailMountSeq = 0;

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

  it("passes initial wiring state into overview and detail mocks", async () => {
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
    await screen.findByTestId("mock-bond-analytics-detail-section");

    await waitFor(() => {
      expect(latestOverviewProps?.reportDate).toBeTruthy();
    });

    const firstDate = (latestOverviewProps?.dateOptions as { value: string }[])[0]?.value;
    expect(firstDate).toBeTruthy();
    expect(latestOverviewProps?.reportDate).toBe(firstDate);
    expect(latestDetailProps?.reportDate).toBe(firstDate);

    expect(latestOverviewProps?.periodType).toBe("MoM");
    expect(latestDetailProps?.periodType).toBe("MoM");

    expect(latestDetailProps?.activeTab).toBe("action-attribution");
    expect(screen.getByTestId("mock-bond-analytics-detail-section")).toHaveAttribute(
      "data-active-tab",
      "action-attribution",
    );
    expect(client.getBondAnalyticsActionAttribution).toHaveBeenCalled();
  });

  it("renders a compact decision cockpit before data-quality and lazy overview evidence", async () => {
    const user = userEvent.setup();
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
    const cockpit = await screen.findByTestId("bond-analysis-decision-cockpit");
    const banner = await screen.findByRole("alert");
    const overview = await screen.findByTestId("mock-bond-analytics-overview-panels");
    const detail = screen.getByTestId("bond-analysis-detail-drilldown");

    expect(toolbar.compareDocumentPosition(cockpit)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(cockpit.compareDocumentPosition(banner)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(banner.compareDocumentPosition(overview)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(cockpit.compareDocumentPosition(detail)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);

    expect(within(cockpit).getByTestId("bond-analysis-decision-trust")).toHaveAttribute(
      "data-state",
      "warning",
    );
    expect(within(cockpit).getByTestId("bond-analysis-decision-source")).toHaveTextContent(
      "2026-03-31",
    );
    expect(within(cockpit).getByTestId("bond-analysis-decision-source")).toHaveTextContent(
      "MoM",
    );
    expect(within(cockpit).getByTestId("bond-analysis-currency-basis-note")).toHaveTextContent(
      "金额指标按人民币/CNY口径展示，外币债券金额已折算为人民币。",
    );
    expect(within(cockpit).getByTestId("bond-analysis-decision-pnl")).toHaveTextContent("2.50");
    expect(within(cockpit).getByText("动作 PnL（人民币/CNY）")).toBeInTheDocument();
    expect(within(cockpit).getByTestId("bond-analysis-decision-duration")).toHaveTextContent("-0.12");
    expect(within(cockpit).getByTestId("bond-analysis-decision-dv01")).toHaveTextContent("120,000");
    expect(within(cockpit).getByTestId("bond-analysis-decision-dv01")).toHaveTextContent("132,000");
    expect(within(cockpit).getByTestId("bond-analysis-decision-warning")).toHaveTextContent("1");

    expect(detail).not.toHaveAttribute("open");
    await user.click(within(cockpit).getByTestId("bond-analysis-decision-next-action"));
    expect(detail).toHaveAttribute("open");
    expect(latestDetailProps?.activeTab).toBe("action-attribution");
  });

  it("keeps the decision cockpit explicit when action-attribution evidence fails", async () => {
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

    const cockpit = await screen.findByTestId("bond-analysis-decision-cockpit");

    await waitFor(() => {
      expect(within(cockpit).getByTestId("bond-analysis-decision-trust")).toHaveAttribute(
        "data-state",
        "blocked",
      );
      expect(within(cockpit).getByTestId("bond-analysis-decision-primary")).toHaveTextContent(
        "backend 503 for action attribution",
      );
      expect(within(cockpit).getByTestId("bond-analysis-decision-pnl")).toHaveTextContent("—");
      expect(within(cockpit).getByTestId("bond-analysis-decision-warning")).toHaveTextContent("1");
    });
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
    expect(latestDetailProps?.activeTab).toBe("credit-spread");

    await user.click(screen.getByTestId("trigger-report-date"));
    expect(latestDetailProps?.reportDate).toBe("2025-12-31");

    await user.click(screen.getByTestId("trigger-period-type"));
    expect(latestDetailProps?.periodType).toBe("YTD");
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
});
