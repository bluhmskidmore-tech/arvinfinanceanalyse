import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="pnl-bridge-echarts-stub" />,
}));

import * as pollingModule from "../app/jobs/polling";
import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type { Numeric, PnlBridgePayload, PnlDatesPayload, ResultMeta } from "../api/contracts";
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

function bridgeYuan(raw: number, display: string, signAware = true): Numeric {
  return { raw, unit: "yuan", display, precision: 2, sign_aware: signAware };
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

function buildBridgePayload(reportDate: string, instrumentCode: string, totalActualPnlDisplay: string): PnlBridgePayload {
  return {
    report_date: reportDate,
    warnings: ["Residual spike on instrument IC-1", "Curve shock coverage incomplete"],
    summary: {
      row_count: 3,
      ok_count: 2,
      warning_count: 1,
      error_count: 0,
      total_beginning_dirty_mv: bridgeYuan(100, "100", false),
      total_ending_dirty_mv: bridgeYuan(110, "110", false),
      total_carry: bridgeYuan(1.1, "1.1"),
      total_roll_down: bridgeYuan(2.2, "2.2"),
      total_treasury_curve: bridgeYuan(3.3, "3.3"),
      total_credit_spread: bridgeYuan(-0.5, "-0.5"),
      total_fx_translation: bridgeYuan(0.25, "0.25"),
      total_realized_trading: bridgeYuan(4, "4"),
      total_unrealized_fv: bridgeYuan(5, "5"),
      total_manual_adjustment: bridgeYuan(0.1, "0.1"),
      total_explained_pnl: bridgeYuan(15.45, "15.45"),
      total_actual_pnl: bridgeYuan(Number(totalActualPnlDisplay), totalActualPnlDisplay),
      total_residual: bridgeYuan(0.05, "0.05"),
      quality_flag: "warning",
    },
    rows: [
      {
        report_date: reportDate,
        instrument_code: instrumentCode,
        portfolio_name: "Bridge Desk",
        accounting_basis: "FVOCI",
        carry: bridgeYuan(1, "1"),
        roll_down: bridgeYuan(0, "0"),
        treasury_curve: bridgeYuan(0, "0"),
        credit_spread: bridgeYuan(0, "0"),
        fx_translation: bridgeYuan(0, "0"),
        realized_trading: bridgeYuan(2, "2"),
        unrealized_fv: bridgeYuan(3, "3"),
        manual_adjustment: bridgeYuan(0, "0"),
        explained_pnl: bridgeYuan(6, "6"),
        actual_pnl: bridgeYuan(5.9, "5.9"),
        residual: bridgeYuan(0.1, "0.1"),
        residual_ratio: { raw: 0.02, unit: "ratio", display: "0.02", precision: 2, sign_aware: true },
        quality_flag: "warning",
      },
    ],
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

describe("PnlBridgePage", () => {
  it("renders summary cards, waterfall card, warnings, detail grid, and debug panel", async () => {
    const base = createApiClient({ mode: "real" });

    const getFormalPnlDates = vi.fn(async () => ({
      result_meta: buildMeta("pnl.dates", "tr_bridge_dates"),
      result: {
        report_dates: ["2025-12-31"],
        formal_fi_report_dates: ["2025-12-31"],
        nonstd_bridge_report_dates: [],
      } satisfies PnlDatesPayload,
    }));
    const getPnlBridge = vi.fn(async () => ({
      result_meta: buildMeta("pnl.bridge", "tr_bridge_payload"),
      result: buildBridgePayload("2025-12-31", "IC-1", "15.40"),
    }));

    renderPnlBridgePage({
      ...base,
      getFormalPnlDates,
      getPnlBridge,
    });

    const dateSelect = await screen.findByLabelText("pnl-bridge-report-date");
    expect(screen.getByTestId("pnl-bridge-page-title")).toHaveTextContent("正式损益解释");
    expect(screen.getByTestId("pnl-bridge-page-subtitle")).toHaveTextContent("查看实际损益与解释损益的差异");
    expect(screen.getByTestId("pnl-bridge-page-role-badge")).toHaveTextContent("正式解释");
    expect(screen.getByTestId("pnl-bridge-formal-only-note")).toHaveTextContent("正式口径");
    expect(screen.getByRole("heading", { name: "正式桥接汇总" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "桥接明细与归因瀑布" })).toBeInTheDocument();

    await waitFor(() => {
      expect(dateSelect).toHaveValue("2025-12-31");
    });

    const summary = await screen.findByTestId("pnl-bridge-summary-cards");
    expect(summary).toHaveTextContent("15.45");
    expect(summary).toHaveTextContent("15.40");

    const conclusion = await screen.findByTestId("pnl-bridge-conclusion");
    expect(conclusion).toHaveTextContent("当前结论");
    expect(conclusion).toHaveTextContent("解释损益基本贴近实际损益");
    expect(conclusion).toHaveTextContent("残差需要跟踪");

    const warnings = await screen.findByTestId("pnl-bridge-warnings");
    expect(warnings).toHaveTextContent("Residual spike on instrument IC-1");

    expect(screen.getByTestId("pnl-bridge-waterfall-card")).toBeInTheDocument();
    expect(screen.getByText("损益桥接效应拆解")).toBeInTheDocument();

    const detail = await screen.findByTestId("pnl-bridge-detail-table");
    expect(detail).toHaveTextContent("IC-1");
    expect(detail).toHaveTextContent("Bridge Desk");
    expect(detail).toHaveTextContent("手工调整");

    const metaPanel = await screen.findByTestId("pnl-bridge-result-meta-panel");
    expect(metaPanel).toHaveTextContent("正式桥接读模型");
    expect(metaPanel).toHaveTextContent("tr_bridge_payload");
    expect(metaPanel).toHaveTextContent("sv_bridge_test");

    await waitFor(() => {
      expect(getPnlBridge).toHaveBeenCalledWith("2025-12-31");
    });
  });

  it("switches report date, refetches bridge payload, and updates debug meta", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "real" });

    const getFormalPnlDates = vi.fn(async () => ({
      result_meta: buildMeta("pnl.dates", "tr_bridge_dates_switch"),
      result: {
        report_dates: ["2025-12-31", "2025-11-30"],
        formal_fi_report_dates: ["2025-12-31", "2025-11-30"],
        nonstd_bridge_report_dates: [],
      } satisfies PnlDatesPayload,
    }));
    const getPnlBridge = vi.fn(async (reportDate: string) => ({
      result_meta: buildMeta("pnl.bridge", `tr_bridge_${reportDate}`),
      result: buildBridgePayload(
        reportDate,
        reportDate === "2025-12-31" ? "IC-1" : "IC-2",
        reportDate === "2025-12-31" ? "15.40" : "21.80",
      ),
    }));

    renderPnlBridgePage({
      ...base,
      getFormalPnlDates,
      getPnlBridge,
    });

    const dateSelect = await screen.findByLabelText("pnl-bridge-report-date");
    await waitFor(() => {
      expect(dateSelect).toHaveValue("2025-12-31");
    });
    await user.selectOptions(dateSelect, "2025-11-30");

    await waitFor(() => {
      expect(getPnlBridge).toHaveBeenCalledWith("2025-11-30");
    });

    const summary = await screen.findByTestId("pnl-bridge-summary-cards");
    expect(summary).toHaveTextContent("21.80");

    const detail = await screen.findByTestId("pnl-bridge-detail-table");
    expect(detail).toHaveTextContent("IC-2");

    const metaPanel = await screen.findByTestId("pnl-bridge-result-meta-panel");
    expect(metaPanel).toHaveTextContent("tr_bridge_2025-11-30");
    expect(metaPanel).toHaveTextContent("rv_bridge_test");
  });

  it("surfaces loading then empty state when bridge dates are unavailable", async () => {
    const base = createApiClient({ mode: "real" });
    const datesRequest = deferred<{
      result_meta: ResultMeta;
      result: PnlDatesPayload;
    }>();

    renderPnlBridgePage({
      ...base,
      getFormalPnlDates: vi.fn(() => datesRequest.promise),
    });

    await waitFor(() => {
      expect(screen.getByTestId("pnl-bridge-summary-section")).toHaveAttribute("data-state", "loading");
      expect(screen.getByTestId("pnl-bridge-detail-section")).toHaveAttribute("data-state", "loading");
    });

    datesRequest.resolve({
      result_meta: buildMeta("pnl.dates", "tr_bridge_dates_empty"),
      result: {
        report_dates: [],
        formal_fi_report_dates: [],
        nonstd_bridge_report_dates: [],
      },
    });

    await waitFor(() => {
      expect(screen.getByTestId("pnl-bridge-summary-section")).toHaveAttribute("data-state", "empty");
      expect(screen.getByTestId("pnl-bridge-detail-section")).toHaveAttribute("data-state", "empty");
    });

    expect(screen.getByLabelText("pnl-bridge-report-date")).toBeDisabled();
  });

  it("preserves adapter fallback state and still renders summary content", async () => {
    const base = createApiClient({ mode: "real" });

    renderPnlBridgePage({
      ...base,
      getFormalPnlDates: vi.fn(async () => ({
        result_meta: buildMeta("pnl.dates", "tr_bridge_dates_fallback"),
        result: {
          report_dates: ["2025-12-31"],
          formal_fi_report_dates: ["2025-12-31"],
          nonstd_bridge_report_dates: [],
        } satisfies PnlDatesPayload,
      })),
      getPnlBridge: vi.fn(async () => ({
        result_meta: {
          ...buildMeta("pnl.bridge", "tr_bridge_fallback"),
          fallback_mode: "latest_snapshot" as const,
          filters_applied: { report_date: "2025-12-30" },
        },
        result: buildBridgePayload("2025-12-31", "IC-1", "15.40"),
      })),
    });

    await waitFor(() => {
      expect(screen.getByTestId("pnl-bridge-summary-section")).toHaveAttribute("data-state", "fallback");
    });
    expect(screen.getAllByTestId("data-section-fallback-banner")).toHaveLength(2);
    expect(screen.getByTestId("pnl-bridge-summary-cards")).toHaveTextContent("15.40");
  });

  it("refreshes bridge data for the selected report date and shows polling status", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "real" });
    const pollingSpy = vi.spyOn(pollingModule, "runPollingTask").mockImplementation(async (options) => {
      await options.start();
      options.onUpdate?.({
        status: "running",
        run_id: "pnl_materialize:bridge-run",
        report_date: "2025-12-31",
      });
      options.onUpdate?.({
        status: "completed",
        run_id: "pnl_materialize:bridge-run",
        report_date: "2025-12-31",
        source_version: "sv_bridge_refresh",
      });
      return {
        status: "completed",
        run_id: "pnl_materialize:bridge-run",
        job_name: "pnl_materialize",
        trigger_mode: "terminal",
        cache_key: "pnl:phase2:materialize:formal",
        report_date: "2025-12-31",
        source_version: "sv_bridge_refresh",
      };
    });

    const getFormalPnlDates = vi
      .fn()
      .mockResolvedValueOnce({
        result_meta: buildMeta("pnl.dates", "tr_bridge_dates_initial"),
        result: {
          report_dates: ["2025-12-31"],
          formal_fi_report_dates: ["2025-12-31"],
          nonstd_bridge_report_dates: [],
        } satisfies PnlDatesPayload,
      })
      .mockResolvedValueOnce({
        result_meta: buildMeta("pnl.dates", "tr_bridge_dates_refetched"),
        result: {
          report_dates: ["2025-12-31"],
          formal_fi_report_dates: ["2025-12-31"],
          nonstd_bridge_report_dates: [],
        } satisfies PnlDatesPayload,
      });

    const getPnlBridge = vi
      .fn()
      .mockResolvedValueOnce({
        result_meta: buildMeta("pnl.bridge", "tr_bridge_initial"),
        result: buildBridgePayload("2025-12-31", "IC-1", "15.40"),
      })
      .mockResolvedValueOnce({
        result_meta: buildMeta("pnl.bridge", "tr_bridge_refetched"),
        result: buildBridgePayload("2025-12-31", "IC-9", "18.60"),
      });

    const refreshFormalPnl = vi.fn(async () => ({
      status: "queued",
      run_id: "pnl_materialize:bridge-run",
      job_name: "pnl_materialize",
      trigger_mode: "async",
      cache_key: "pnl:phase2:materialize:formal",
      report_date: "2025-12-31",
    }));

    renderPnlBridgePage({
      ...base,
      getFormalPnlDates,
      getPnlBridge,
      refreshFormalPnl,
      getFormalPnlImportStatus: vi.fn(),
    });

    await screen.findByTestId("pnl-bridge-summary-cards");
    await user.click(screen.getByTestId("pnl-bridge-refresh-button"));

    await waitFor(() => {
      expect(refreshFormalPnl).toHaveBeenCalledWith("2025-12-31");
      expect(screen.getByTestId("pnl-bridge-refresh-status")).toHaveTextContent("completed");
      expect(screen.getByTestId("pnl-bridge-refresh-status")).toHaveTextContent("pnl_materialize:bridge-run");
      expect(screen.getByTestId("pnl-bridge-refresh-status")).toHaveTextContent("sv_bridge_refresh");
    });

    await waitFor(() => {
      expect(getFormalPnlDates).toHaveBeenCalledTimes(2);
      expect(getPnlBridge).toHaveBeenCalledTimes(2);
    });

    const detail = await screen.findByTestId("pnl-bridge-detail-table");
    expect(detail).toHaveTextContent("IC-9");

    pollingSpy.mockRestore();
  });

  it("shows refresh error and preserves the last known bridge run snapshot", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "real" });
    const pollingSpy = vi.spyOn(pollingModule, "runPollingTask").mockImplementation(async (options) => {
      await options.start();
      options.onUpdate?.({
        status: "running",
        run_id: "pnl_materialize:bridge-timeout",
        report_date: "2025-12-31",
      });
      throw new Error("任务轮询超时");
    });

    renderPnlBridgePage({
      ...base,
      getFormalPnlDates: vi.fn(async () => ({
        result_meta: buildMeta("pnl.dates", "tr_bridge_dates_error"),
        result: {
          report_dates: ["2025-12-31"],
          formal_fi_report_dates: ["2025-12-31"],
          nonstd_bridge_report_dates: [],
        } satisfies PnlDatesPayload,
      })),
      getPnlBridge: vi.fn(async () => ({
        result_meta: buildMeta("pnl.bridge", "tr_bridge_error"),
        result: buildBridgePayload("2025-12-31", "IC-1", "15.40"),
      })),
      refreshFormalPnl: vi.fn(async () => ({
        status: "queued",
        run_id: "pnl_materialize:bridge-timeout",
        job_name: "pnl_materialize",
        trigger_mode: "async",
        cache_key: "pnl:phase2:materialize:formal",
        report_date: "2025-12-31",
      })),
      getFormalPnlImportStatus: vi.fn(),
    });

    await screen.findByTestId("pnl-bridge-summary-cards");
    await user.click(screen.getByTestId("pnl-bridge-refresh-button"));

    await waitFor(() => {
      expect(screen.getByTestId("pnl-bridge-refresh-status")).toHaveTextContent("任务轮询超时");
      expect(screen.getByTestId("pnl-bridge-result-meta-panel")).toHaveTextContent("正式桥接读模型");
      expect(screen.getByTestId("pnl-bridge-result-meta-panel")).toHaveTextContent("tr_bridge_error");
    });

    pollingSpy.mockRestore();
  });
});
