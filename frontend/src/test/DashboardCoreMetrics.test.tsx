import { type ReactNode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

import type { CoreMetricsPayload } from "../api/contracts";
import { DashboardCoreMetricsSection } from "../features/workbench/dashboard/DashboardCoreMetricsSection";
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import { sampleCoreMetricsResult } from "../fixtures/dashboardCoreWorkbenchSamples";

function TestWrapper({ client, children }: { client: QueryClient; children: ReactNode }) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function LoadingHarness({ reportDate = "" }: { reportDate?: string }) {
  const query = useQuery({
    queryKey: ["dashboard", "core-metrics", "test", reportDate],
    queryFn: () => new Promise<CoreMetricsPayload>(() => {}),
    retry: false,
  });
  return <DashboardCoreMetricsSection query={query} reportDate={reportDate} />;
}

function ResolvedHarness({
  payload,
  reportDate = "",
}: {
  payload: CoreMetricsPayload;
  reportDate?: string;
}) {
  const query = useQuery({
    queryKey: ["dashboard", "core-metrics", "test", reportDate],
    queryFn: async () => payload,
    initialData: payload,
    staleTime: Infinity,
  });
  return <DashboardCoreMetricsSection query={query} reportDate={reportDate} />;
}

describe("DashboardCoreMetricsSection", () => {
  it("shows skeleton while loading", () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <TestWrapper client={client}>
        <LoadingHarness />
      </TestWrapper>,
    );
    expect(screen.getByTestId("dashboard-core-metrics-skeleton")).toBeInTheDocument();
  });

  it("renders mock payload values", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const payload = buildMockApiEnvelope("dashboard.core_metrics", sampleCoreMetricsResult());

    render(
      <TestWrapper client={client}>
        <ResolvedHarness payload={payload} reportDate="2026-03-31" />
      </TestWrapper>,
    );

    expect(await screen.findByText("债券投资")).toBeInTheDocument();
    expect(screen.getAllByText("同业资产")[0]).toBeInTheDocument();
    expect(screen.getAllByText("同业负债")[0]).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-core-metrics-section")).toBeInTheDocument();
  });

  it("shows error placeholder when query fails", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    function ErrorHarness() {
      const query = useQuery({
        queryKey: ["dashboard", "core-metrics", "err", ""],
        queryFn: async () => {
          throw new Error("network");
        },
      });
      return <DashboardCoreMetricsSection query={query} reportDate="" />;
    }

    render(
      <TestWrapper client={client}>
        <ErrorHarness />
      </TestWrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText("数据暂不可用")).toBeInTheDocument();
    });
  });

  it("shows quality badge when quality_flag is not ok", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const payload = buildMockApiEnvelope("dashboard.core_metrics", sampleCoreMetricsResult(), {
      quality_flag: "warning",
    });

    render(
      <TestWrapper client={client}>
        <ResolvedHarness payload={payload} />
      </TestWrapper>,
    );

    expect(await screen.findByTestId("dashboard-core-metrics-quality-badge")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-core-metrics-quality-badge")).toHaveTextContent("warning");
  });
});
