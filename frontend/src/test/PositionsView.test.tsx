import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import type { ApiEnvelope, BondPositionItem, PageResponse, ResultMeta, SubTypesResponse } from "../api/contracts";
import PositionsView from "../features/positions/components/PositionsView";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="positions-echarts-stub" />,
}));

function meta(resultKind: string): ResultMeta {
  return {
    trace_id: `tr_${resultKind}`,
    basis: "formal",
    result_kind: resultKind,
    formal_use_allowed: true,
    source_version: "sv_test",
    vendor_version: "vv_none",
    rule_version: "rv_test",
    cache_version: "cv_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-01-02T00:00:00Z",
  };
}

function envelope<T>(resultKind: string, result: T): ApiEnvelope<T> {
  return {
    result_meta: meta(resultKind),
    result,
  };
}

describe("PositionsView", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders shell, report date control, and bond tab", async () => {
    const client = createApiClient({ mode: "mock" });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter>
            <PositionsView />
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByTestId("positions-page")).toBeInTheDocument();
    expect(await screen.findByTestId("positions-page-title")).toHaveTextContent("持仓透视");
    expect(await screen.findByTestId("positions-decision-hero")).toHaveTextContent(
      "数据来源：ZQTZ + TYWL",
    );
    expect(screen.getByTestId("positions-data-status")).toHaveTextContent("当前：债券持仓");
    expect(screen.getByTestId("positions-kpi-band")).toHaveTextContent("业务种类");
    expect(screen.getByTestId("positions-filter-tray")).toBeInTheDocument();
    expect(screen.getByText("持仓工作区")).toBeInTheDocument();
    expect(
      await screen.findByRole("combobox", { name: "positions-report-date" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "债券持仓" })).toBeInTheDocument();
  });

  it("renders duplicate bond codes without duplicate React row-key warnings", async () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const client = createApiClient({ mode: "mock" });
    client.getPositionsBondSubTypes = vi.fn(async (): Promise<ApiEnvelope<SubTypesResponse>> =>
      envelope("positions.bonds.sub_types", { sub_types: ["Gov"] }),
    );
    client.getPositionsBondsList = vi.fn(
      async (options): Promise<ApiEnvelope<PageResponse<BondPositionItem>>> =>
        envelope("positions.bonds.list", {
          items: [
            {
              bond_code: "DUP001",
              credit_name: "Issuer A",
              sub_type: "Gov",
              asset_class: "HTM",
              market_value: "100000000.00000000",
              face_value: "100000000.00000000",
              valuation_net_price: "100.00000000",
              yield_rate: "0.03000000",
            },
            {
              bond_code: "DUP001",
              credit_name: "Issuer A",
              sub_type: "Gov",
              asset_class: "AFS",
              market_value: "200000000.00000000",
              face_value: "200000000.00000000",
              valuation_net_price: "100.00000000",
              yield_rate: "0.03100000",
            },
          ],
          total: 2,
          page: options.page,
          page_size: options.pageSize,
        }),
    );
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MemoryRouter>
            <PositionsView />
          </MemoryRouter>
        </ApiClientProvider>
      </QueryClientProvider>,
    );

    await screen.findByTestId("positions-page");
    await waitFor(() =>
      expect(client.getPositionsBondsList).toHaveBeenCalledWith(
        expect.objectContaining({ subType: null }),
      ),
    );
    const subTypeSelect = await screen.findByTestId("positions-bond-subtype-select");
    fireEvent.mouseDown(subTypeSelect.querySelector(".ant-select-selector") ?? subTypeSelect);
    fireEvent.click(await screen.findByTitle("Gov"));

    await waitFor(() => expect(screen.getAllByText("DUP001")).toHaveLength(2));
    const duplicateKeyWarnings = errorSpy.mock.calls.filter(([message]) =>
      String(message).includes("Encountered two children with the same key"),
    );
    expect(duplicateKeyWarnings).toHaveLength(0);
  });
});
