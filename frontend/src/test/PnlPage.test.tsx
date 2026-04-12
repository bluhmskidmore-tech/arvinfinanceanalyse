import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type {
  PnlDataPayload,
  PnlDatesPayload,
  PnlFormalFiRow,
  PnlNonStdBridgeRow,
  PnlOverviewPayload,
  ResultMeta,
} from "../api/contracts";
import PnlPage from "../features/pnl/PnlPage";

function renderPnlPage(client: ApiClient) {
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
      <PnlPage />
    </Wrapper>,
  );
}

function buildMeta(resultKind: string, traceId: string): ResultMeta {
  return {
    trace_id: traceId,
    basis: "formal",
    result_kind: resultKind,
    formal_use_allowed: true,
    source_version: "sv_pnl_test",
    vendor_version: "vv_none",
    rule_version: "rv_pnl_test",
    cache_version: "cv_pnl_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-12T08:00:00Z",
  };
}

function sampleFormalFiRow(): PnlFormalFiRow {
  return {
    report_date: "2025-12-31",
    instrument_code: "240001.IB",
    portfolio_name: "利率组合A",
    cost_center: "cc-1",
    invest_type_std: "A",
    accounting_basis: "FVOCI",
    currency_basis: "CNY",
    interest_income_514: "1200.50",
    fair_value_change_516: "30.25",
    capital_gain_517: "10.00",
    manual_adjustment: "0",
    total_pnl: "1240.75",
    source_version: "sv_pnl_row",
    rule_version: "rv_pnl_row",
    ingest_batch_id: "ingest-1",
    trace_id: "tr_pnl_fi_row",
  };
}

function sampleNonstdRow(): PnlNonStdBridgeRow {
  return {
    report_date: "2025-12-31",
    bond_code: "NS-001",
    portfolio_name: "非标池",
    cost_center: "cc-2",
    interest_income_514: "500",
    fair_value_change_516: "20",
    capital_gain_517: "5",
    manual_adjustment: "1",
    total_pnl: "526",
    source_version: "sv_nonstd",
    rule_version: "rv_nonstd",
    ingest_batch_id: "ingest-2",
    trace_id: "tr_nonstd_row",
  };
}

describe("PnlPage", () => {
  it("auto-selects the first report date, shows overview cards, FI grid, and nonstd tab table", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });

    const datesPayload: PnlDatesPayload = {
      report_dates: ["2025-12-31", "2025-11-30"],
      formal_fi_report_dates: ["2025-12-31"],
      nonstd_bridge_report_dates: ["2025-12-31"],
    };
    const overviewPayload: PnlOverviewPayload = {
      report_date: "2025-12-31",
      formal_fi_row_count: 2,
      nonstd_bridge_row_count: 1,
      interest_income_514: "9999.12",
      fair_value_change_516: "123.45",
      capital_gain_517: "88.00",
      manual_adjustment: "1.00",
      total_pnl: "10211.57",
    };
    const dataPayload: PnlDataPayload = {
      report_date: "2025-12-31",
      formal_fi_rows: [sampleFormalFiRow()],
      nonstd_bridge_rows: [sampleNonstdRow()],
    };

    const getFormalPnlDates = vi.fn(async () => ({
      result_meta: buildMeta("pnl.dates", "tr_pnl_dates"),
      result: datesPayload,
    }));
    const getFormalPnlOverview = vi.fn(async () => ({
      result_meta: buildMeta("pnl.overview", "tr_pnl_overview"),
      result: overviewPayload,
    }));
    const getFormalPnlData = vi.fn(async () => ({
      result_meta: buildMeta("pnl.data", "tr_pnl_data"),
      result: dataPayload,
    }));

    renderPnlPage({
      ...base,
      getFormalPnlDates,
      getFormalPnlOverview,
      getFormalPnlData,
    });

    expect(await screen.findByRole("heading", { name: "损益明细" })).toBeInTheDocument();

    const dateSelect = await screen.findByLabelText("pnl-report-date");
    expect(dateSelect).toHaveValue("2025-12-31");

    await waitFor(() => {
      expect(getFormalPnlOverview).toHaveBeenCalledWith("2025-12-31");
      expect(getFormalPnlData).toHaveBeenCalledWith("2025-12-31");
    });

    const overview = await screen.findByTestId("pnl-overview-cards");
    expect(overview).toHaveTextContent("9999.12");
    expect(overview).toHaveTextContent("123.45");
    expect(overview).toHaveTextContent("10211.57");

    const fiTable = await screen.findByTestId("pnl-formal-fi-table");
    expect(fiTable).toHaveTextContent("240001.IB");
    expect(fiTable).toHaveTextContent("利率组合A");

    await user.click(screen.getByRole("button", { name: "非标桥接" }));

    const nonstdTable = await screen.findByTestId("pnl-nonstd-bridge-table");
    expect(nonstdTable).toHaveTextContent("NS-001");
    expect(nonstdTable).toHaveTextContent("非标池");
  });
});
