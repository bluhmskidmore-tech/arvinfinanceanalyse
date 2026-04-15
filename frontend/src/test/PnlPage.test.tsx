import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import * as pollingModule from "../app/jobs/polling";
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
    portfolio_name: "FI Desk A",
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
    portfolio_name: "NonStd Desk",
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

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
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

    const dateSelect = await screen.findByLabelText("pnl-report-date");
    await waitFor(() => {
      expect(dateSelect).toHaveValue("2025-12-31");
    });

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
    expect(fiTable).toHaveTextContent("FI Desk A");

    await user.click(screen.getByRole("button", { name: "非标桥接" }));

    const nonstdTable = await screen.findByTestId("pnl-nonstd-bridge-table");
    expect(nonstdTable).toHaveTextContent("NS-001");
    expect(nonstdTable).toHaveTextContent("NonStd Desk");
  });

  it("switches report date and refetches overview, rows, and debug meta for the selected date", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "real" });

    const getFormalPnlDates = vi.fn(async () => ({
      result_meta: buildMeta("pnl.dates", "tr_pnl_dates_switch"),
      result: {
        report_dates: ["2025-12-31", "2025-11-30"],
        formal_fi_report_dates: ["2025-12-31", "2025-11-30"],
        nonstd_bridge_report_dates: ["2025-12-31", "2025-11-30"],
      } satisfies PnlDatesPayload,
    }));

    const getFormalPnlOverview = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("pnl.overview", `tr_pnl_overview_${reportDate}`),
      result: {
        report_date: reportDate,
        formal_fi_row_count: 1,
        nonstd_bridge_row_count: 1,
        interest_income_514: reportDate === "2025-12-31" ? "100.00" : "200.00",
        fair_value_change_516: "0.00",
        capital_gain_517: "0.00",
        manual_adjustment: "0.00",
        total_pnl: reportDate === "2025-12-31" ? "100.00" : "200.00",
      } satisfies PnlOverviewPayload,
    }));

    const getFormalPnlData = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("pnl.data", `tr_pnl_data_${reportDate}`),
      result: {
        report_date: reportDate,
        formal_fi_rows: [
          {
            ...sampleFormalFiRow(),
            report_date: reportDate,
            instrument_code: reportDate === "2025-12-31" ? "240001.IB" : "240002.IB",
            trace_id: `tr_formal_${reportDate}`,
          },
        ],
        nonstd_bridge_rows: [
          {
            ...sampleNonstdRow(),
            report_date: reportDate,
            bond_code: reportDate === "2025-12-31" ? "NS-001" : "NS-002",
            trace_id: `tr_nonstd_${reportDate}`,
          },
        ],
      } satisfies PnlDataPayload,
    }));

    renderPnlPage({
      ...base,
      getFormalPnlDates,
      getFormalPnlOverview,
      getFormalPnlData,
    });

    const dateSelect = await screen.findByLabelText("pnl-report-date");

    await waitFor(() => {
      expect(getFormalPnlOverview).toHaveBeenCalledWith("2025-12-31");
      expect(getFormalPnlData).toHaveBeenCalledWith("2025-12-31");
    });

    await user.selectOptions(dateSelect, "2025-11-30");

    await waitFor(() => {
      expect(getFormalPnlOverview).toHaveBeenCalledWith("2025-11-30");
      expect(getFormalPnlData).toHaveBeenCalledWith("2025-11-30");
    });

    const overview = await screen.findByTestId("pnl-overview-cards");
    expect(overview).toHaveTextContent("200.00");

    const fiTable = await screen.findByTestId("pnl-formal-fi-table");
    expect(fiTable).toHaveTextContent("240002.IB");

    const debugPanel = await screen.findByTestId("pnl-result-meta-panel");
    expect(debugPanel).toHaveTextContent('"client_mode": "real"');
    expect(debugPanel).toHaveTextContent('"trace_id": "tr_pnl_data_2025-11-30"');
    expect(debugPanel).toHaveTextContent('"report_date": "2025-11-30"');
  });

  it("surfaces loading and then empty state when no report dates are available", async () => {
    const base = createApiClient({ mode: "real" });
    const datesRequest = deferred<{
      result_meta: ResultMeta;
      result: PnlDatesPayload;
    }>();

    renderPnlPage({
      ...base,
      getFormalPnlDates: vi.fn(() => datesRequest.promise),
    });

    await waitFor(() => {
      expect(screen.getByTestId("pnl-overview-section")).toHaveAttribute("data-state", "loading");
      expect(screen.getByTestId("pnl-data-section")).toHaveAttribute("data-state", "loading");
    });

    datesRequest.resolve({
      result_meta: buildMeta("pnl.dates", "tr_pnl_dates_empty"),
      result: {
        report_dates: [],
        formal_fi_report_dates: [],
        nonstd_bridge_report_dates: [],
      },
    });

    await waitFor(() => {
      expect(screen.getByTestId("pnl-overview-section")).toHaveAttribute("data-state", "empty");
      expect(screen.getByTestId("pnl-data-section")).toHaveAttribute("data-state", "empty");
    });

    expect(screen.getByLabelText("pnl-report-date")).toBeDisabled();
    expect(screen.queryByTestId("pnl-overview-cards")).not.toBeInTheDocument();
  });

  it("surfaces error state and keeps the debug panel available when dates loading fails", async () => {
    const base = createApiClient({ mode: "real" });

    renderPnlPage({
      ...base,
      getFormalPnlDates: vi.fn(async () => {
        throw new Error("pnl dates failed");
      }),
    });

    await waitFor(() => {
      expect(screen.getByTestId("pnl-overview-section")).toHaveAttribute("data-state", "error");
      expect(screen.getByTestId("pnl-data-section")).toHaveAttribute("data-state", "error");
    });

    expect(screen.getByTestId("pnl-result-meta-panel")).toHaveTextContent('"client_mode": "real"');
    expect(screen.getByLabelText("pnl-report-date")).toBeDisabled();
  });

  it("triggers pnl refresh for the selected report date, polls status, and refetches queries", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "real" });
    const pollingSpy = vi.spyOn(pollingModule, "runPollingTask").mockImplementation(async (options) => {
      await options.start();
      options.onUpdate?.({
        status: "running",
        run_id: "pnl_materialize:test-run",
        report_date: "2025-12-31",
      });
      options.onUpdate?.({
        status: "completed",
        run_id: "pnl_materialize:test-run",
        report_date: "2025-12-31",
        source_version: "sv_refresh_done",
      });
      return {
        status: "completed",
        run_id: "pnl_materialize:test-run",
        job_name: "pnl_materialize",
        trigger_mode: "terminal",
        cache_key: "pnl:phase2:materialize:formal",
        report_date: "2025-12-31",
        source_version: "sv_refresh_done",
      };
    });

    const getFormalPnlDates = vi
      .fn()
      .mockResolvedValueOnce({
        result_meta: buildMeta("pnl.dates", "tr_dates_initial"),
        result: {
          report_dates: ["2025-12-31"],
          formal_fi_report_dates: ["2025-12-31"],
          nonstd_bridge_report_dates: ["2025-12-31"],
        } satisfies PnlDatesPayload,
      })
      .mockResolvedValueOnce({
        result_meta: buildMeta("pnl.dates", "tr_dates_refetched"),
        result: {
          report_dates: ["2025-12-31"],
          formal_fi_report_dates: ["2025-12-31"],
          nonstd_bridge_report_dates: ["2025-12-31"],
        } satisfies PnlDatesPayload,
      });

    const getFormalPnlOverview = vi
      .fn()
      .mockResolvedValueOnce({
        result_meta: buildMeta("pnl.overview", "tr_overview_initial"),
        result: {
          report_date: "2025-12-31",
          formal_fi_row_count: 1,
          nonstd_bridge_row_count: 1,
          interest_income_514: "10.00",
          fair_value_change_516: "0.00",
          capital_gain_517: "0.00",
          manual_adjustment: "0.00",
          total_pnl: "10.00",
        } satisfies PnlOverviewPayload,
      })
      .mockResolvedValueOnce({
        result_meta: buildMeta("pnl.overview", "tr_overview_refetched"),
        result: {
          report_date: "2025-12-31",
          formal_fi_row_count: 2,
          nonstd_bridge_row_count: 1,
          interest_income_514: "12.00",
          fair_value_change_516: "0.00",
          capital_gain_517: "0.00",
          manual_adjustment: "0.00",
          total_pnl: "12.00",
        } satisfies PnlOverviewPayload,
      });

    const getFormalPnlData = vi
      .fn()
      .mockResolvedValueOnce({
        result_meta: buildMeta("pnl.data", "tr_data_initial"),
        result: {
          report_date: "2025-12-31",
          formal_fi_rows: [sampleFormalFiRow()],
          nonstd_bridge_rows: [sampleNonstdRow()],
        } satisfies PnlDataPayload,
      })
      .mockResolvedValueOnce({
        result_meta: buildMeta("pnl.data", "tr_data_refetched"),
        result: {
          report_date: "2025-12-31",
          formal_fi_rows: [
            sampleFormalFiRow(),
            {
              ...sampleFormalFiRow(),
              instrument_code: "240009.IB",
              trace_id: "tr_after_refresh",
            },
          ],
          nonstd_bridge_rows: [sampleNonstdRow()],
        } satisfies PnlDataPayload,
      });

    const refreshFormalPnl = vi.fn(async () => ({
      status: "queued",
      run_id: "pnl_materialize:test-run",
      job_name: "pnl_materialize",
      trigger_mode: "async",
      cache_key: "pnl:phase2:materialize:formal",
      report_date: "2025-12-31",
    }));

    const getFormalPnlImportStatus = vi.fn(async () => ({
      status: "completed",
      run_id: "pnl_materialize:test-run",
      job_name: "pnl_materialize",
      trigger_mode: "terminal",
      cache_key: "pnl:phase2:materialize:formal",
      report_date: "2025-12-31",
      source_version: "sv_refresh_done",
    }));

    renderPnlPage({
      ...base,
      getFormalPnlDates,
      getFormalPnlOverview,
      getFormalPnlData,
      refreshFormalPnl,
      getFormalPnlImportStatus,
    });

    await screen.findByTestId("pnl-overview-cards");
    await user.click(screen.getByTestId("pnl-refresh-button"));

    await waitFor(() => {
      expect(refreshFormalPnl).toHaveBeenCalledWith("2025-12-31");
      expect(screen.getByTestId("pnl-refresh-status")).toHaveTextContent("completed");
      expect(screen.getByTestId("pnl-refresh-status")).toHaveTextContent("pnl_materialize:test-run");
      expect(screen.getByTestId("pnl-refresh-status")).toHaveTextContent("sv_refresh_done");
    });

    await waitFor(() => {
      expect(getFormalPnlDates).toHaveBeenCalledTimes(2);
      expect(getFormalPnlOverview).toHaveBeenCalledTimes(2);
      expect(getFormalPnlData).toHaveBeenCalledTimes(2);
    });

    pollingSpy.mockRestore();
  });

  it("shows refresh error when polling rejects and preserves the last known run state", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "real" });
    const pollingSpy = vi.spyOn(pollingModule, "runPollingTask").mockImplementation(async (options) => {
      options.onUpdate?.({
        status: "running",
        run_id: "pnl_materialize:timeout-run",
        report_date: "2025-12-31",
      });
      throw new Error("任务轮询超时");
    });

    renderPnlPage({
      ...base,
      getFormalPnlDates: vi.fn(async () => ({
        result_meta: buildMeta("pnl.dates", "tr_dates_refresh_error"),
        result: {
          report_dates: ["2025-12-31"],
          formal_fi_report_dates: ["2025-12-31"],
          nonstd_bridge_report_dates: ["2025-12-31"],
        } satisfies PnlDatesPayload,
      })),
      getFormalPnlOverview: vi.fn(async () => ({
        result_meta: buildMeta("pnl.overview", "tr_overview_refresh_error"),
        result: {
          report_date: "2025-12-31",
          formal_fi_row_count: 1,
          nonstd_bridge_row_count: 1,
          interest_income_514: "10.00",
          fair_value_change_516: "0.00",
          capital_gain_517: "0.00",
          manual_adjustment: "0.00",
          total_pnl: "10.00",
        } satisfies PnlOverviewPayload,
      })),
      getFormalPnlData: vi.fn(async () => ({
        result_meta: buildMeta("pnl.data", "tr_data_refresh_error"),
        result: {
          report_date: "2025-12-31",
          formal_fi_rows: [sampleFormalFiRow()],
          nonstd_bridge_rows: [sampleNonstdRow()],
        } satisfies PnlDataPayload,
      })),
      refreshFormalPnl: vi.fn(async () => ({
        status: "queued",
        run_id: "pnl_materialize:timeout-run",
        job_name: "pnl_materialize",
        trigger_mode: "async",
        cache_key: "pnl:phase2:materialize:formal",
        report_date: "2025-12-31",
      })),
      getFormalPnlImportStatus: vi.fn(),
    });

    await screen.findByTestId("pnl-overview-cards");
    await user.click(screen.getByTestId("pnl-refresh-button"));

    await waitFor(() => {
      expect(screen.getByTestId("pnl-refresh-status")).toHaveTextContent("任务轮询超时");
      expect(screen.getByTestId("pnl-result-meta-panel")).toHaveTextContent(
        '"status": "running · pnl_materialize:timeout-run · 2025-12-31"',
      );
    });

    pollingSpy.mockRestore();
  });
});
