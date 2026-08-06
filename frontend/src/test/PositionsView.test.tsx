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

function meta(resultKind: string, overrides: Partial<ResultMeta> = {}): ResultMeta {
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
    ...overrides,
  };
}

function envelope<T>(
  resultKind: string,
  result: T,
  metaOverrides: Partial<ResultMeta> = {},
): ApiEnvelope<T> {
  return {
    result_meta: meta(resultKind, metaOverrides),
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

  it("surfaces active positions list result_meta in the first-screen data status", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getBalanceAnalysisDates = vi.fn(async () =>
      envelope("balance-analysis.dates", { report_dates: ["2026-04-30"] }),
    );
    client.getPositionsBondSubTypes = vi.fn(async (): Promise<ApiEnvelope<SubTypesResponse>> =>
      envelope("positions.bonds.sub_types", { sub_types: ["信用债"] }),
    );
    client.getPositionsBondsList = vi.fn(
      async (options): Promise<ApiEnvelope<PageResponse<BondPositionItem>>> =>
        envelope(
          "positions.bonds.list",
          {
            items: [],
            total: 0,
            page: options.page,
            page_size: options.pageSize,
          },
          {
            quality_flag: "warning",
            fallback_mode: "latest_snapshot",
            source_version: "sv_positions_warning",
            generated_at: "2026-05-01T08:00:00Z",
          },
        ),
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

    const status = await screen.findByTestId("positions-data-status");
    await waitFor(() => {
      expect(status).toHaveTextContent("质量标记：预警");
      expect(status).toHaveTextContent("降级模式：最新快照降级");
      expect(status).toHaveTextContent("生成时间：2026-05-01T08:00:00Z");
      expect(status).toHaveTextContent("来源版本：sv_positions_warning");
    });
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
