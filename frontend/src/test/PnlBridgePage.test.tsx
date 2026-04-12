import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="pnl-bridge-echarts-stub" />,
}));

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type { PnlBridgePayload, PnlDatesPayload, ResultMeta } from "../api/contracts";
import PnlBridgePage from "../features/pnl/PnlBridgePage";

function renderPnlBridgePage(client: ApiClient) {
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

  return render(
    <Wrapper>
      <PnlBridgePage />
    </Wrapper>,
  );
}

function buildMeta(resultKind: string, traceId: string): ResultMeta {
  return {
    trace_id: traceId,
    basis: "formal",
    result_kind: resultKind,
    formal_use_allowed: true,
    source_version: "sv_bridge_test",
    vendor_version: "vv_none",
    rule_version: "rv_bridge_test",
    cache_version: "cv_bridge_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-12T08:00:00Z",
  };
}

describe("PnlBridgePage", () => {
  it("renders summary cards, warnings, detail grid, and waterfall section heading", async () => {
    const base = createApiClient({ mode: "mock" });

    const datesPayload: PnlDatesPayload = {
      report_dates: ["2025-12-31"],
      formal_fi_report_dates: ["2025-12-31"],
      nonstd_bridge_report_dates: [],
    };

    const bridgePayload: PnlBridgePayload = {
      report_date: "2025-12-31",
      warnings: ["Residual spike on instrument IC-1", "Curve shock coverage incomplete"],
      summary: {
        row_count: 3,
        ok_count: 2,
        warning_count: 1,
        error_count: 0,
        total_beginning_dirty_mv: "100",
        total_ending_dirty_mv: "110",
        total_carry: "1.1",
        total_roll_down: "2.2",
        total_treasury_curve: "3.3",
        total_credit_spread: "-0.5",
        total_fx_translation: "0.25",
        total_realized_trading: "4",
        total_unrealized_fv: "5",
        total_manual_adjustment: "0.1",
        total_explained_pnl: "15.45",
        total_actual_pnl: "15.40",
        total_residual: "0.05",
        quality_flag: "warning",
      },
      rows: [
        {
          instrument_code: "IC-1",
          portfolio_name: "桥接组合",
          accounting_basis: "FVOCI",
          carry: "1",
          roll_down: "0",
          treasury_curve: "0",
          credit_spread: "0",
          fx_translation: "0",
          realized_trading: "2",
          unrealized_fv: "3",
          manual_adjustment: "0",
          explained_pnl: "6",
          actual_pnl: "5.9",
          residual: "0.1",
          residual_ratio: "0.02",
          quality_flag: "warning",
        },
      ],
    };

    const getFormalPnlDates = vi.fn(async () => ({
      result_meta: buildMeta("pnl.dates", "tr_bridge_dates"),
      result: datesPayload,
    }));
    const getPnlBridge = vi.fn(async () => ({
      result_meta: buildMeta("pnl.bridge", "tr_bridge_payload"),
      result: bridgePayload,
    }));

    renderPnlBridgePage({
      ...base,
      getFormalPnlDates,
      getPnlBridge,
    });

    expect(await screen.findByRole("heading", { name: "损益桥接" })).toBeInTheDocument();

    const summary = await screen.findByTestId("pnl-bridge-summary-cards");
    expect(summary).toHaveTextContent("15.45");
    expect(summary).toHaveTextContent("15.40");

    const warnings = await screen.findByTestId("pnl-bridge-warnings");
    expect(warnings).toHaveTextContent("Residual spike on instrument IC-1");

    expect(screen.getByText("桥接分解（汇总分项，瀑布图）")).toBeInTheDocument();

    const detail = await screen.findByTestId("pnl-bridge-detail-table");
    expect(detail).toHaveTextContent("IC-1");
    expect(detail).toHaveTextContent("桥接组合");

    await waitFor(() => {
      expect(getPnlBridge).toHaveBeenCalledWith("2025-12-31");
    });
  });
});
