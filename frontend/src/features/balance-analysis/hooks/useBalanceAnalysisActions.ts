import { useContext, useState } from "react";

import { useApiClient } from "../../../api/clientContext";
import type { BalanceCurrencyBasis, BalancePositionScope } from "../../../api/contracts";
import { runPollingTask } from "../../../app/jobs/polling";
import { usePollingTaskSignal } from "../../../app/jobs/usePollingTaskSignal";
import { SystemReadInteractionContext } from "../../../router/systemReadInteractionContext";

type BalanceAnalysisActionSelection = {
  selectedReportDate: string;
  positionScope: BalancePositionScope;
  currencyBasis: BalanceCurrencyBasis;
};

function formatRefreshStatusDisplay(status: string | undefined): string {
  if (status === "queued") return "刷新任务已排队";
  if (status === "running") return "刷新任务进行中";
  if (status === "completed") return "计算任务已完成";
  if (status === "failed") return "刷新暂未完成";
  return "刷新任务已有反馈";
}

export function formatOperationIssueDisplay(action: "refresh" | "decision" | "summary-export" | "workbook-export"): string {
  if (action === "decision") {
    return "治理处理结果暂未写入，请稍后重试或联系数据负责人。";
  }
  if (action === "summary-export") {
    return "汇总表暂未导出，请稍后重试。";
  }
  if (action === "workbook-export") {
    return "工作簿暂未导出，请稍后重试。";
  }
  return "正式结果暂未刷新，请稍后重试。";
}

function downloadBlobFile(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

function downloadCsvFile(filename: string, content: string) {
  downloadBlobFile(filename, new Blob([content], { type: "text/csv;charset=utf-8;" }));
}

/** Refreshes legacy reads after rebuild; pinned generations wait for publication. */
export function useBalanceAnalysisActions(
  { selectedReportDate, positionScope, currencyBasis }: BalanceAnalysisActionSelection,
  refetchCurrentReads: () => Promise<unknown>,
) {
  const client = useApiClient();
  const getPollingSignal = usePollingTaskSignal();
  const systemReadInteraction = useContext(SystemReadInteractionContext);

  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isExportingCsv, setIsExportingCsv] = useState(false);
  const [isExportingWorkbook, setIsExportingWorkbook] = useState(false);
  const [refreshStatus, setRefreshStatus] = useState<string | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [refreshAwaitingPublication, setRefreshAwaitingPublication] = useState(false);

  async function handleRefresh() {
    const signal = getPollingSignal();
    if (!selectedReportDate) {
      return;
    }
    setIsRefreshing(true);
    setRefreshError(null);
    setRefreshAwaitingPublication(false);
    try {
      const payload = await runPollingTask({
        signal,
        start: () => client.refreshBalanceAnalysis(selectedReportDate),
        getStatus: (runId) => client.getBalanceAnalysisRefreshStatus(runId),
        onUpdate: (nextPayload) => {
          setRefreshStatus(formatRefreshStatusDisplay(nextPayload.status));
        },
      });
      if (signal?.aborted) return;
      setRefreshStatus(formatRefreshStatusDisplay(payload.status));
      if (payload.status !== "completed") {
        throw new Error(payload.error_message ?? payload.detail ?? `刷新未完成：${payload.status}`);
      }
      if (systemReadInteraction?.generation) {
        setRefreshAwaitingPublication(true);
        return;
      }
      await refetchCurrentReads();
    } catch {
      if (signal?.aborted) return;
      setRefreshError(formatOperationIssueDisplay("refresh"));
    } finally {
      if (!signal?.aborted) setIsRefreshing(false);
    }
  }

  async function handleExport() {
    if (!selectedReportDate) {
      return;
    }
    setIsExportingCsv(true);
    setRefreshError(null);
    try {
      const payload = await client.exportBalanceAnalysisSummaryCsv({
        reportDate: selectedReportDate,
        positionScope,
        currencyBasis,
      });
      downloadCsvFile(payload.filename, payload.content);
    } catch {
      setRefreshError(formatOperationIssueDisplay("summary-export"));
    } finally {
      setIsExportingCsv(false);
    }
  }

  async function handleWorkbookExport() {
    if (!selectedReportDate) {
      return;
    }
    setIsExportingWorkbook(true);
    setRefreshError(null);
    try {
      const payload = await client.exportBalanceAnalysisWorkbookXlsx({
        reportDate: selectedReportDate,
        positionScope: "all",
        currencyBasis,
      });
      downloadBlobFile(payload.filename, payload.content);
    } catch {
      setRefreshError(formatOperationIssueDisplay("workbook-export"));
    } finally {
      setIsExportingWorkbook(false);
    }
  }

  return {
    isRefreshing,
    isExportingCsv,
    isExportingWorkbook,
    refreshStatus,
    refreshError,
    refreshAwaitingPublication,
    handleRefresh,
    handleExport,
    handleWorkbookExport,
  };
}
