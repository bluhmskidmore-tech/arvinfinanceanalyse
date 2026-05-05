import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import * as pollingModule from "../app/jobs/polling";
import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type {
  ApiBasis,
  PnlDatesPayload,
  PnlV1DataPayload,
  PnlV1DetailRow,
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

function buildMeta(resultKind: string, traceId: string, basis: ApiBasis = "formal"): ResultMeta {
  return {
    trace_id: traceId,
    basis,
    result_kind: resultKind,
    formal_use_allowed: basis === "formal",
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

function sampleFormalFiRow(): PnlV1DetailRow {
  return {
    report_date: "2025-12-31",
    source: "FI",
    asset_code: "240001.IB",
    bond_name: "240001.IB",
    portfolio: "FI Desk A",
    asset_type: "A",
    asset_class: "bond-trading",
    market_value: "0",
    interest_income: "1200.50",
    fair_value_change: "30.25",
    capital_gain: "10.00",
    total_pnl: "1240.75",
    source_version: "sv_pnl_row",
    trace_id: "tr_pnl_fi_row",
  };
}

function sampleNonstdRow(): PnlV1DetailRow {
  return {
    report_date: "2025-12-31",
    source: "NonStd",
    asset_code: "NS-001",
    bond_name: "NS-001",
    portfolio: "NonStd Desk",
    asset_type: "H",
    asset_class: "nonstd",
    market_value: "0",
    interest_income: "500",
    fair_value_change: "20",
    capital_gain: "5",
    total_pnl: "525",
    source_version: "sv_nonstd",
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
    const dataPayload: PnlV1DataPayload = {
      report_date: "2025-12-31",
      source_tables: ["data_input/pnl"],
      rows: [sampleFormalFiRow(), sampleNonstdRow()],
    };

    const getFormalPnlDates = vi.fn(async () => ({
      result_meta: buildMeta("pnl.dates", "tr_pnl_dates"),
      result: datesPayload,
    }));
    const getPnlV1Data = vi.fn(async () => ({
      result_meta: buildMeta("pnl.v1_data", "tr_pnl_data"),
      result: dataPayload,
    }));

    renderPnlPage({
      ...base,
      getFormalPnlDates,
      getPnlV1Data,
    });

    const dateSelect = await screen.findByLabelText("pnl-report-date");
    expect(screen.getByTestId("pnl-page-title")).toHaveTextContent("正式损益明细");
    expect(screen.getByTestId("pnl-page-subtitle")).toHaveTextContent("查看正式口径损益汇总与明细");
    expect(screen.getByTestId("pnl-page-subtitle")).toHaveTextContent("不在前端重算");
    expect(screen.getByTestId("pnl-page-role-badge")).toHaveTextContent("正式明细");
    await waitFor(() => {
      expect(screen.getByTestId("pnl-ledger-link")).toHaveAttribute(
        "href",
        "/ledger-pnl?report_date=2025-12-31",
      );
    });
    expect(screen.getByRole("heading", { name: "正式损益汇总" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "正式明细与非标桥接" })).toBeInTheDocument();

    await waitFor(() => {
      expect(dateSelect).toHaveValue("2025-12-31");
    });

    await waitFor(() => {
      expect(getPnlV1Data).toHaveBeenCalledWith("2025-12-31");
    });

    const overview = await screen.findByTestId("pnl-overview-cards");
    expect(overview).toHaveTextContent("0.17");
    expect(overview).toHaveTextContent("0.01");

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

    const getPnlV1Data = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("pnl.v1_data", `tr_pnl_data_${reportDate}`),
      result: {
        report_date: reportDate,
        source_tables: ["data_input/pnl"],
        rows: [
          {
            ...sampleFormalFiRow(),
            report_date: reportDate,
            asset_code: reportDate === "2025-12-31" ? "240001.IB" : "240002.IB",
            trace_id: `tr_formal_${reportDate}`,
          },
          {
            ...sampleNonstdRow(),
            report_date: reportDate,
            asset_code: reportDate === "2025-12-31" ? "NS-001" : "NS-002",
            trace_id: `tr_nonstd_${reportDate}`,
          },
        ],
      } satisfies PnlV1DataPayload,
    }));

    renderPnlPage({
      ...base,
      getFormalPnlDates,
      getPnlV1Data,
    });

    const dateSelect = await screen.findByLabelText("pnl-report-date");

    await waitFor(() => {
      expect(getPnlV1Data).toHaveBeenCalledWith("2025-12-31");
    });

    await user.selectOptions(dateSelect, "2025-11-30");

    await waitFor(() => {
      expect(getPnlV1Data).toHaveBeenCalledWith("2025-11-30");
    });

    const overview = await screen.findByTestId("pnl-overview-cards");
    expect(overview).toHaveTextContent("0.17");

    const fiTable = await screen.findByTestId("pnl-formal-fi-table");
    expect(fiTable).toHaveTextContent("240002.IB");

    const metaPanel = await screen.findByTestId("pnl-result-meta-panel");
    expect(metaPanel).toHaveTextContent("V1");
    expect(metaPanel).toHaveTextContent("tr_pnl_data_2025-11-30");
    expect(metaPanel).toHaveTextContent("sv_pnl_test");
    expect(metaPanel).toHaveTextContent("rv_pnl_test");
  });

  it("switches from formal to analytical basis and refetches the pnl queries with analytical meta", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "real" });

    const getFormalPnlDates = vi.fn(async (basis?: ApiBasis) => ({
      result_meta: buildMeta("pnl.dates", `tr_pnl_dates_${basis ?? "formal"}`, basis ?? "formal"),
      result: {
        report_dates: ["2025-12-31"],
        formal_fi_report_dates: ["2025-12-31"],
        nonstd_bridge_report_dates: ["2025-12-31"],
      } satisfies PnlDatesPayload,
    }));

    const getPnlV1Data = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("pnl.v1_data", "tr_pnl_data_formal", "formal"),
      result: {
        report_date: reportDate,
        source_tables: ["data_input/pnl"],
        rows: [
          {
            ...sampleFormalFiRow(),
            trace_id: "tr_formal_v1",
          },
          sampleNonstdRow(),
        ],
      } satisfies PnlV1DataPayload,
    }));

    renderPnlPage({
      ...base,
      getFormalPnlDates,
      getPnlV1Data,
    });

    await screen.findByTestId("pnl-overview-cards");

    expect(getFormalPnlDates).toHaveBeenCalledWith("formal");
    expect(getPnlV1Data).toHaveBeenCalledWith("2025-12-31");

    await user.click(screen.getByRole("button", { name: "分析口径" }));

    await waitFor(() => {
      expect(getFormalPnlDates).toHaveBeenCalledWith("analytical");
    });

    expect(screen.getByTestId("pnl-overview-cards")).toHaveTextContent("0.17");
    expect(screen.getByTestId("pnl-formal-fi-table")).toHaveTextContent("240001.IB");
    expect(screen.getByTestId("pnl-result-meta-panel")).toHaveTextContent("analytical");
    expect(screen.getByTestId("pnl-result-meta-panel")).toHaveTextContent("tr_pnl_data_formal");
    expect(screen.getByTestId("pnl-basis-note")).toHaveTextContent("正式口径");
    expect(screen.getByTestId("pnl-refresh-button")).toBeDisabled();
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

    expect(screen.getByTestId("pnl-result-meta-panel")).toHaveTextContent("结果元信息 / 证据");
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

    const getPnlV1Data = vi
      .fn()
      .mockResolvedValueOnce({
        result_meta: buildMeta("pnl.v1_data", "tr_data_initial"),
        result: {
          report_date: "2025-12-31",
          source_tables: ["data_input/pnl"],
          rows: [sampleFormalFiRow(), sampleNonstdRow()],
        } satisfies PnlV1DataPayload,
      })
      .mockResolvedValueOnce({
        result_meta: buildMeta("pnl.v1_data", "tr_data_refetched"),
        result: {
          report_date: "2025-12-31",
          source_tables: ["data_input/pnl"],
          rows: [
            sampleFormalFiRow(),
            sampleNonstdRow(),
            {
              ...sampleFormalFiRow(),
              asset_code: "240009.IB",
              trace_id: "tr_after_refresh",
            },
          ],
        } satisfies PnlV1DataPayload,
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
      getPnlV1Data,
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
      expect(getPnlV1Data).toHaveBeenCalledTimes(2);
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
      getPnlV1Data: vi.fn(async () => ({
        result_meta: buildMeta("pnl.v1_data", "tr_data_refresh_error"),
        result: {
          report_date: "2025-12-31",
          source_tables: ["data_input/pnl"],
          rows: [sampleFormalFiRow(), sampleNonstdRow()],
        } satisfies PnlV1DataPayload,
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
      expect(screen.getByTestId("pnl-result-meta-panel")).toHaveTextContent("tr_data_refresh_error");
    });

    pollingSpy.mockRestore();
  });
});
