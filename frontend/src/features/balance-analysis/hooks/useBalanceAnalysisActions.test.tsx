import type { PropsWithChildren } from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { createApiClient } from "../../../api/client";
import { ApiClientProvider } from "../../../api/clientContext";
import type { BalanceAnalysisRefreshPayload, BalancePositionScope } from "../../../api/contracts";
import { SystemReadInteractionContext } from "../../../router/systemReadInteractionContext";
import { useBalanceAnalysisActions } from "./useBalanceAnalysisActions";

const completed: BalanceAnalysisRefreshPayload = {
  status: "completed",
  run_id: "balance-refresh-test",
  job_name: "balance_analysis_materialize",
  trigger_mode: "sync-fallback",
  report_date: "2025-12-31",
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((next) => { resolve = next; });
  return { promise, resolve };
}

function setup(generation: string | null = null) {
  const refreshBalanceAnalysis = vi.fn(async () => completed);
  const client = {
    ...createApiClient({ mode: "mock" }),
    refreshBalanceAnalysis,
    getBalanceAnalysisRefreshStatus: vi.fn(async () => completed),
    exportBalanceAnalysisSummaryCsv: vi.fn(async () => {
      throw new Error("summary export unavailable");
    }),
    exportBalanceAnalysisWorkbookXlsx: vi.fn(async () => {
      throw new Error("workbook export unavailable");
    }),
  };
  const interaction = { generation, coverageDates: {}, refresh: vi.fn() };
  const refetchCurrentReads = vi.fn(async () => undefined);
  function wrapper({ children }: PropsWithChildren) {
    return (
      <ApiClientProvider client={client}>
        <SystemReadInteractionContext.Provider value={interaction}>
          {children}
        </SystemReadInteractionContext.Provider>
      </ApiClientProvider>
    );
  }
  return { client, interaction, refetchCurrentReads, wrapper };
}

describe("balance analysis refresh and export lifecycle", () => {
  it("waits for rebuild and current reads before releasing the legacy refresh state", async () => {
    const { client, refetchCurrentReads, wrapper } = setup();
    const rebuild = deferred<BalanceAnalysisRefreshPayload>();
    const reads = deferred<undefined>();
    client.refreshBalanceAnalysis.mockReturnValue(rebuild.promise);
    refetchCurrentReads.mockReturnValue(reads.promise);
    const { result } = renderHook(() => useBalanceAnalysisActions({
      selectedReportDate: "2025-12-31",
      positionScope: "asset",
      currencyBasis: "CNY",
    }, refetchCurrentReads), { wrapper });
    let work!: Promise<void>;

    act(() => { work = result.current.handleRefresh(); });

    expect(client.refreshBalanceAnalysis).toHaveBeenCalledWith("2025-12-31");
    expect(result.current.isRefreshing).toBe(true);
    expect(refetchCurrentReads).not.toHaveBeenCalled();
    await act(async () => { rebuild.resolve(completed); await rebuild.promise; });
    await waitFor(() => expect(refetchCurrentReads).toHaveBeenCalledOnce());
    expect(result.current.isRefreshing).toBe(true);
    expect(result.current.refreshAwaitingPublication).toBe(false);

    await act(async () => { reads.resolve(undefined); await work; });

    expect(result.current.isRefreshing).toBe(false);
    expect(result.current.refreshStatus).toBe("计算任务已完成");
    expect(result.current.refreshError).toBeNull();
  });

  it("keeps a pinned generation awaiting publication without directly rereading or changing it", async () => {
    const { interaction, refetchCurrentReads, wrapper } = setup("balance-published");
    const { result } = renderHook(() => useBalanceAnalysisActions({
      selectedReportDate: "2025-12-31",
      positionScope: "asset",
      currencyBasis: "CNY",
    }, refetchCurrentReads), { wrapper });

    await act(async () => { await result.current.handleRefresh(); });

    expect(result.current.refreshAwaitingPublication).toBe(true);
    expect(result.current.refreshStatus).toBe("计算任务已完成");
    expect(result.current.isRefreshing).toBe(false);
    expect(refetchCurrentReads).not.toHaveBeenCalled();
    expect(interaction.refresh).not.toHaveBeenCalled();
    expect(interaction.generation).toBe("balance-published");
  });

  it.each(["asset", "liability"] as const)(
    "exports the %s summary scope and the all-scope workbook with distinct error states",
    async (positionScope: BalancePositionScope) => {
      const { client, refetchCurrentReads, wrapper } = setup();
      const { result } = renderHook(() => useBalanceAnalysisActions({
        selectedReportDate: "2025-12-31",
        positionScope,
        currencyBasis: "CNY",
      }, refetchCurrentReads), { wrapper });

      await act(async () => { await result.current.handleExport(); });

      expect(client.exportBalanceAnalysisSummaryCsv).toHaveBeenCalledWith({
        reportDate: "2025-12-31",
        positionScope,
        currencyBasis: "CNY",
      });
      expect(result.current.refreshError).toBe("汇总表暂未导出，请稍后重试。");
      expect(result.current.isExportingCsv).toBe(false);
      await act(async () => { await result.current.handleWorkbookExport(); });

      expect(client.exportBalanceAnalysisWorkbookXlsx).toHaveBeenCalledWith({
        reportDate: "2025-12-31",
        positionScope: "all",
        currencyBasis: "CNY",
      });
      expect(result.current.refreshError).toBe("工作簿暂未导出，请稍后重试。");
      expect(result.current.isExportingWorkbook).toBe(false);
      expect(refetchCurrentReads).not.toHaveBeenCalled();
    },
  );

  it("keeps read caches untouched when rebuild does not complete", async () => {
    const { client, refetchCurrentReads, wrapper } = setup();
    client.refreshBalanceAnalysis.mockResolvedValue({ ...completed, status: "failed" });
    const { result } = renderHook(() => useBalanceAnalysisActions({
      selectedReportDate: "2025-12-31",
      positionScope: "all",
      currencyBasis: "CNY",
    }, refetchCurrentReads), { wrapper });

    await act(async () => { await result.current.handleRefresh(); });

    expect(refetchCurrentReads).not.toHaveBeenCalled();
    expect(result.current.refreshAwaitingPublication).toBe(false);
    expect(result.current.isRefreshing).toBe(false);
    expect(result.current.refreshError).toBe("正式结果暂未刷新，请稍后重试。");
  });
});
