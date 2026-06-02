import { type ReactNode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

import type { DailyChangesPayload } from "../api/contracts";
import { DashboardDailyChangesSection } from "../features/workbench/dashboard/DashboardDailyChangesSection";
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import { sampleDailyChangesResult } from "../fixtures/dashboardCoreWorkbenchSamples";

function TestWrapper({ client, children }: { client: QueryClient; children: ReactNode }) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function LoadingHarness() {
  const query = useQuery({
    queryKey: ["dashboard", "daily-changes", "test"],
    queryFn: () => new Promise<DailyChangesPayload>(() => {}),
    retry: false,
  });
  return <DashboardDailyChangesSection query={query} />;
}

function ResolvedHarness({ payload }: { payload: DailyChangesPayload }) {
  const query = useQuery({
    queryKey: ["dashboard", "daily-changes", "test-resolved"],
    queryFn: async () => payload,
    initialData: payload,
    staleTime: Infinity,
  });
  return <DashboardDailyChangesSection query={query} />;
}

describe("DashboardDailyChangesSection", () => {
  it("shows skeleton while loading", () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <TestWrapper client={client}>
        <LoadingHarness />
      </TestWrapper>,
    );
    expect(screen.getByTestId("dashboard-daily-changes-skeleton")).toBeInTheDocument();
  });

  it("renders periods from mock payload", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const payload = buildMockApiEnvelope("dashboard.daily_changes", sampleDailyChangesResult());

    render(
      <TestWrapper client={client}>
        <ResolvedHarness payload={payload} />
      </TestWrapper>,
    );

    await waitFor(() => {
      expect(screen.getByRole("columnheader", { name: "周期" })).toBeInTheDocument();
    });
    expect(screen.getByRole("columnheader", { name: "净变动" })).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-daily-changes-section")).toBeInTheDocument();
    expect(screen.getAllByRole("row").length).toBeGreaterThan(1);
  });

  it("shows error placeholder when query fails", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    function ErrorHarness() {
      const query = useQuery({
        queryKey: ["dashboard", "daily-changes", "err"],
        queryFn: async () => {
          throw new Error("network");
        },
      });
      return <DashboardDailyChangesSection query={query} />;
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
    const payload = buildMockApiEnvelope("dashboard.daily_changes", sampleDailyChangesResult(), {
      quality_flag: "warning",
    });

    render(
      <TestWrapper client={client}>
        <ResolvedHarness payload={payload} />
      </TestWrapper>,
    );

    expect(await screen.findByTestId("dashboard-daily-changes-quality-badge")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-daily-changes-quality-badge")).toHaveTextContent("warning");
  });
});
