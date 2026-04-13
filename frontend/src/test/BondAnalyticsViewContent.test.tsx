import * as React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import { runPollingTask } from "../app/jobs/polling";

let latestOverviewProps: Record<string, unknown> | null = null;
let latestDetailProps: Record<string, unknown> | null = null;
let detailMountSeq = 0;

vi.mock("../app/jobs/polling", () => ({
  runPollingTask: vi.fn(),
}));

vi.mock("../features/bond-analytics/components/BondAnalyticsOverviewPanels", () => ({
  default: function MockBondAnalyticsOverviewPanels(props: Record<string, unknown>) {
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

import { BondAnalyticsViewContent } from "../features/bond-analytics/components/BondAnalyticsViewContent";

const runPollingTaskMock = vi.mocked(runPollingTask);

function renderViewContent(client = createApiClient({ mode: "mock" })) {
  latestOverviewProps = null;
  latestDetailProps = null;

  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false },
    },
  });
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
      getBondAnalyticsActionAttribution: vi.fn(async () => ({
        result_meta: {
          trace_id: "tr_test",
          basis: "formal" as const,
          result_kind: "bond_analytics.action_attribution",
          formal_use_allowed: true,
          source_version: "sv_test",
          vendor_version: "vv_test",
          rule_version: "rv_test",
          cache_version: "cv_test",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-12T00:00:00Z",
        },
        result: {
          report_date: "2026-03-31",
          period_type: "MoM",
          period_start: "2026-03-01",
          period_end: "2026-03-31",
          total_actions: 1,
          total_pnl_from_actions: "100",
          by_action_type: [],
          action_details: [],
          period_start_duration: "3",
          period_end_duration: "3",
          duration_change_from_actions: "0",
          period_start_dv01: "0",
          period_end_dv01: "0",
          warnings: [],
          computed_at: "2026-04-12T00:00:00Z",
        },
      })),
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

  it("propagates overview interactions into the detail mock", async () => {
    const user = userEvent.setup();
    const client = {
      ...createApiClient({ mode: "mock" }),
      getBondAnalyticsActionAttribution: vi.fn(async () => ({
        result_meta: {
          trace_id: "tr_test",
          basis: "formal" as const,
          result_kind: "bond_analytics.action_attribution",
          formal_use_allowed: true,
          source_version: "sv_test",
          vendor_version: "vv_test",
          rule_version: "rv_test",
          cache_version: "cv_test",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-12T00:00:00Z",
        },
        result: {
          report_date: "2026-03-31",
          period_type: "MoM",
          period_start: "2026-03-01",
          period_end: "2026-03-31",
          total_actions: 1,
          total_pnl_from_actions: "100",
          by_action_type: [],
          action_details: [],
          period_start_duration: "3",
          period_end_duration: "3",
          duration_change_from_actions: "0",
          period_start_dv01: "0",
          period_end_dv01: "0",
          warnings: [],
          computed_at: "2026-04-12T00:00:00Z",
        },
      })),
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
      getBondAnalyticsActionAttribution: vi.fn(async () => ({
        result_meta: {
          trace_id: "tr_test",
          basis: "formal" as const,
          result_kind: "bond_analytics.action_attribution",
          formal_use_allowed: true,
          source_version: "sv_test",
          vendor_version: "vv_test",
          rule_version: "rv_test",
          cache_version: "cv_test",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-12T00:00:00Z",
        },
        result: {
          report_date: "2026-03-31",
          period_type: "MoM",
          period_start: "2026-03-01",
          period_end: "2026-03-31",
          total_actions: 1,
          total_pnl_from_actions: "100",
          by_action_type: [],
          action_details: [],
          period_start_duration: "3",
          period_end_duration: "3",
          duration_change_from_actions: "0",
          period_start_dv01: "0",
          period_end_dv01: "0",
          warnings: [],
          computed_at: "2026-04-12T00:00:00Z",
        },
      })),
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
      getBondAnalyticsActionAttribution: vi.fn(async () => ({
        result_meta: {
          trace_id: "tr_test",
          basis: "formal" as const,
          result_kind: "bond_analytics.action_attribution",
          formal_use_allowed: true,
          source_version: "sv_test",
          vendor_version: "vv_test",
          rule_version: "rv_test",
          cache_version: "cv_test",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-12T00:00:00Z",
        },
        result: {
          report_date: "2026-03-31",
          period_type: "MoM",
          period_start: "2026-03-01",
          period_end: "2026-03-31",
          total_actions: 1,
          total_pnl_from_actions: "100",
          by_action_type: [],
          action_details: [],
          period_start_duration: "3",
          period_end_duration: "3",
          duration_change_from_actions: "0",
          period_start_dv01: "0",
          period_end_dv01: "0",
          warnings: [],
          computed_at: "2026-04-12T00:00:00Z",
        },
      })),
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
      getBondAnalyticsActionAttribution: vi.fn(async () => ({
        result_meta: {
          trace_id: "tr_test",
          basis: "formal" as const,
          result_kind: "bond_analytics.action_attribution",
          formal_use_allowed: true,
          source_version: "sv_test",
          vendor_version: "vv_test",
          rule_version: "rv_test",
          cache_version: "cv_test",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-12T00:00:00Z",
        },
        result: {
          report_date: "2026-03-31",
          period_type: "MoM",
          period_start: "2026-03-01",
          period_end: "2026-03-31",
          total_actions: 1,
          total_pnl_from_actions: "100",
          by_action_type: [],
          action_details: [],
          period_start_duration: "3",
          period_end_duration: "3",
          duration_change_from_actions: "0",
          period_start_dv01: "0",
          period_end_dv01: "0",
          warnings: [],
          computed_at: "2026-04-12T00:00:00Z",
        },
      })),
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
