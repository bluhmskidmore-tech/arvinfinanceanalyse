import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import type { CubeQueryResult, ResultMeta } from "../api/contracts";
import CubeQueryPage from "../features/cube-query/pages/CubeQueryPage";

const resultMeta: ResultMeta = {
  trace_id: "tr_cube_test",
  basis: "formal",
  result_kind: "cube.query",
  formal_use_allowed: true,
  source_version: "sv_test",
  vendor_version: "vv_test",
  rule_version: "rv_test",
  cache_version: "cv_test",
  quality_flag: "ok",
  vendor_status: "ok",
  fallback_mode: "none",
  scenario_flag: false,
  generated_at: "2026-04-13T00:00:00Z",
};

describe("CubeQueryPage", () => {
  it("shows fact table selector on mount and loads dimensions for bond_analytics", async () => {
    const client = createApiClient({ mode: "mock" });
    const dimSpy = vi.spyOn(client, "getCubeDimensions");

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <CubeQueryPage />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByTestId("cube-fact-select")).toBeInTheDocument();
    await waitFor(() => {
      expect(dimSpy).toHaveBeenCalledWith("bond_analytics");
    });
    expect(await screen.findByText("asset_class_std")).toBeInTheDocument();
  });

  it("calls executeCubeQuery and shows results table after run", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    const execSpy = vi.spyOn(client, "executeCubeQuery");
    const sample: CubeQueryResult = {
      report_date: "2025-12-31",
      fact_table: "bond_analytics",
      measures: ["sum(market_value)"],
      dimensions: ["rating"],
      rows: [{ rating: "AAA", market_value: 1234.5678 }],
      total_rows: 1,
      drill_paths: [],
      result_meta: resultMeta,
    };
    execSpy.mockResolvedValue(sample);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <CubeQueryPage />
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    await screen.findByText("asset_class_std");
    const rating = screen.getByText("rating");
    const group = rating.closest(".ant-checkbox-group");
    expect(group).toBeTruthy();
    await user.click(within(group as HTMLElement).getByText("rating"));

    await user.click(screen.getByTestId("cube-execute"));

    await waitFor(() => {
      expect(execSpy).toHaveBeenCalled();
    });

    const firstCall = execSpy.mock.calls[0]![0];
    expect(firstCall.fact_table).toBe("bond_analytics");
    expect(firstCall.basis).toBe("formal");
    expect(firstCall.measures).toContain("sum(market_value)");

    expect(await screen.findByTestId("cube-results-table")).toBeInTheDocument();
    expect(await screen.findByText("1,234.5678")).toBeInTheDocument();
    expect(await screen.findByTestId("cube-result-meta")).toHaveTextContent("tr_cube_test");
  });
});
