import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type { KpiMetric, KpiOwner, KpiPeriodSummaryResponse } from "../api/contracts";
import { BatchPasteModal } from "../features/kpi-performance/components/BatchPasteModal";
import { MetricManageModal } from "../features/kpi-performance/components/MetricManageModal";
import KpiPerformancePage from "../features/kpi-performance/pages/KpiPerformancePage";

function renderWithClient(ui: ReactNode, client: ApiClient) {
  function Wrapper({ children }: { children: ReactNode }) {
    const [queryClient] = useState(
      () =>
        new QueryClient({
          defaultOptions: {
            queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
          },
        }),
    );

    return (
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>{children}</ApiClientProvider>
      </QueryClientProvider>
    );
  }

  return render(<Wrapper>{ui}</Wrapper>);
}

function buildOwner(): KpiOwner {
  return {
    owner_id: 1,
    owner_name: "Owner Alpha",
    org_unit: "Desk A",
    person_name: "Alice",
    year: 2026,
    scope_type: "DEPARTMENT",
    scope_key: { department: "desk-a" },
    is_active: true,
    created_at: "2026-04-01T00:00:00Z",
    updated_at: "2026-04-01T00:00:00Z",
  };
}

function buildMetric(owner: KpiOwner): KpiMetric {
  return {
    metric_id: 11,
    metric_code: "REV_GROWTH",
    owner_id: owner.owner_id,
    year: owner.year,
    major_category: "Growth",
    indicator_category: "Revenue",
    metric_name: "Revenue Growth",
    target_value: "12.0",
    target_text: "Hit growth target",
    score_weight: "10",
    unit: "%",
    scoring_text: "Manual scoring",
    scoring_rule_type: "MANUAL",
    scoring_rule_params: undefined,
    data_source_type: "MANUAL",
    data_source_params: undefined,
    progress_plan: undefined,
    remarks: "Reserved write flow",
    is_active: true,
    created_at: "2026-04-01T00:00:00Z",
    updated_at: "2026-04-01T00:00:00Z",
  };
}

function buildSummary(owner: KpiOwner): KpiPeriodSummaryResponse {
  return {
    owner_id: owner.owner_id,
    owner_name: owner.owner_name,
    year: owner.year,
    period_type: "MONTH",
    period_value: 4,
    period_label: "2026-04",
    period_start_date: "2026-04-01",
    period_end_date: "2026-04-30",
    metrics: [
      {
        metric_id: 11,
        metric_code: "REV_GROWTH",
        metric_name: "Revenue Growth",
        major_category: "Growth",
        indicator_category: "Revenue",
        target_value: "12.0",
        unit: "%",
        score_weight: "10",
        period_actual_value: "9.5",
        period_completion_ratio: "0.79",
        period_progress_pct: "79.00",
        period_score_value: "7.9",
        period_start_date: "2026-04-01",
        period_end_date: "2026-04-30",
        data_date: "2026-04-30",
      },
    ],
    total: 1,
    total_weight: "10",
    total_score: "7.9",
  };
}

describe("KpiPerformancePage governance gating", () => {
  it("keeps KPI in summary-only mode and never calls the reserved daily endpoint", async () => {
    const user = userEvent.setup();
    const owner = buildOwner();
    const summary = buildSummary(owner);
    const base = createApiClient({ mode: "mock" });

    const getKpiOwners = vi.fn(async () => ({ owners: [owner], total: 1 }));
    const getKpiValuesSummary = vi.fn(async () => summary);
    const getKpiValues = vi.fn(async () => ({
      owner_id: owner.owner_id,
      owner_name: owner.owner_name,
      as_of_date: "2026-04-30",
      metrics: [],
      total: 0,
    }));

    renderWithClient(
      <KpiPerformancePage />,
      {
        ...base,
        getKpiOwners,
        getKpiValuesSummary,
        getKpiValues,
      },
    );

    expect(await screen.findByTestId("kpi-performance-page")).toBeInTheDocument();
    expect(screen.getByTestId("kpi-readonly-notice")).toBeInTheDocument();
    expect(getKpiValuesSummary).not.toHaveBeenCalled();

    await user.click(await screen.findByText(owner.owner_name));

    await waitFor(() => {
      expect(getKpiValuesSummary).toHaveBeenCalledWith({
        owner_id: owner.owner_id,
        year: owner.year,
        period_type: "MONTH",
        period_value: expect.any(Number),
      });
    });

    expect(getKpiValues).not.toHaveBeenCalled();
    expect(await screen.findByText("Revenue Growth")).toBeInTheDocument();
    expect(screen.getByTestId("kpi-readonly-table")).toBeInTheDocument();
    expect(screen.getByTestId("kpi-add-metric-button")).toBeDisabled();
    expect(screen.getByTestId("kpi-batch-import-button")).toBeDisabled();
    expect(screen.getByTestId("kpi-fetch-button")).toBeDisabled();
    expect(screen.getByTestId("kpi-export-button")).toBeDisabled();
    expect(screen.getByTestId("kpi-manage-button")).toBeDisabled();
  });

  it("shows the metric management modal as reserved when writes are disabled", () => {
    const owner = buildOwner();
    const metric = buildMetric(owner);
    const base = createApiClient({ mode: "mock" });

    renderWithClient(
      <MetricManageModal
        open
        onClose={() => undefined}
        mode="edit"
        metric={metric}
        owner={owner}
        onSuccess={() => undefined}
        writeEnabled={false}
        disabledReason="Reserved for governed rollout."
      />,
      base,
    );

    expect(screen.getByTestId("kpi-manage-reserved-alert")).toBeInTheDocument();
    expect(screen.getByTestId("kpi-manage-save-button")).toBeDisabled();
    expect(screen.queryByTestId("kpi-manage-delete-button")).not.toBeInTheDocument();
  });

  it("shows the batch import modal as reserved when writes are disabled", () => {
    const owner = buildOwner();
    const metric = buildMetric(owner);
    const base = createApiClient({ mode: "mock" });

    renderWithClient(
      <BatchPasteModal
        open
        onClose={() => undefined}
        owner={owner}
        asOfDate="2026-04-30"
        metrics={[{ ...metric, actual_value: "9.5", progress_pct: "79.00", score_value: "7.9" }]}
        onSuccess={() => undefined}
        writeEnabled={false}
        disabledReason="Reserved for governed rollout."
      />,
      base,
    );

    expect(screen.getByTestId("kpi-batch-import-reserved-alert")).toBeInTheDocument();
    expect(screen.getByTestId("kpi-batch-import-submit-button")).toBeDisabled();
    expect(screen.getByTestId("kpi-batch-import-parse-button")).toBeDisabled();
  });
});
