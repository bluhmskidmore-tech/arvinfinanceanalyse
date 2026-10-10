import { useCallback, useEffect, useRef, useState } from "react";
import type { QueryClient } from "@tanstack/react-query";

import type { ApiClient } from "../../../api/client";
import type { MacroToolkitChoiceStockRefreshRun } from "../../../api/macroToolkitClient";
import { runPollingTask } from "../../../app/jobs/polling";
import { EM_DASH } from "../../../utils/format";

type RefreshTone = "negative" | "neutral" | "positive" | "warning";

type UseStockSelectionRefreshOptions = {
  client: ApiClient;
  queryClient: QueryClient;
  asOfDate?: string;
};

function refreshRunIdLabel(payload: MacroToolkitChoiceStockRefreshRun): string {
  return payload.run_id ? `run_id ${payload.run_id}` : "run_id 待返回";
}

function refreshRowsLabel(payload: MacroToolkitChoiceStockRefreshRun): string {
  return `历史 ${payload.history_row_count ?? EM_DASH} 行，因子 ${payload.factor_row_count ?? EM_DASH} 行`;
}

function normalizedStatus(value: string | null | undefined): string {
  return (value ?? "").trim().toLowerCase();
}

function refreshClosureStatus(payload: MacroToolkitChoiceStockRefreshRun): string {
  return normalizedStatus(payload.livermore_closure_status);
}

function refreshFailureReason(payload: MacroToolkitChoiceStockRefreshRun): string {
  const closureStatus = refreshClosureStatus(payload);
  return (
    payload.livermore_closure_reason?.trim()
    || payload.failure_category?.trim()
    || payload.error_message?.trim()
    || ((!closureStatus || closureStatus === "unknown") ? "闭环状态未返回" : null)
    || "原因待返回"
  );
}

function refreshStatusLabel(payload: MacroToolkitChoiceStockRefreshRun): string {
  const runId = refreshRunIdLabel(payload);
  const status = normalizedStatus(payload.status);
  const closureStatus = refreshClosureStatus(payload);
  if (status === "completed" && closureStatus === "completed") {
    return `选股已重新计算并完成闭环：${runId} · ${refreshRowsLabel(payload)}`;
  }
  if (status === "failed" || closureStatus === "failed") {
    return `选股闭环失败：${refreshFailureReason(payload)} · ${runId}`;
  }
  if (status === "blocked" || closureStatus === "blocked") {
    return `选股刷新被阻断：${refreshFailureReason(payload)} · ${runId}`;
  }
  if (status === "no_rows" || closureStatus === "no_rows") {
    return `选股刷新无可用数据：${refreshFailureReason(payload)} · ${runId}`;
  }
  if (status === "completed" && (!closureStatus || closureStatus === "unknown")) {
    return `选股闭环失败：闭环状态未返回 · ${runId}`;
  }
  if (status === "partial" || closureStatus === "partial") {
    return `选股数据已刷新，闭环仍未完成：${refreshFailureReason(payload)} · ${runId} · ${refreshRowsLabel(payload)}`;
  }
  return `选股刷新状态：${payload.status} · ${runId} · 闭环 ${payload.livermore_closure_status ?? "待返回"}`;
}

function refreshToneForPayload(payload: MacroToolkitChoiceStockRefreshRun): RefreshTone {
  const status = normalizedStatus(payload.status);
  const closureStatus = refreshClosureStatus(payload);
  if (status === "failed" || status === "blocked" || closureStatus === "failed" || closureStatus === "blocked") {
    return "negative";
  }
  if (status === "completed" && closureStatus === "completed") return "positive";
  return "warning";
}

export function useStockSelectionRefresh({
  client,
  queryClient,
  asOfDate,
}: UseStockSelectionRefreshOptions) {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshResult, setRefreshResult] = useState<string | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [refreshTone, setRefreshTone] = useState<RefreshTone>("neutral");

  // 卸载时取消长任务轮询（最长 240×5s），避免继续请求并对已卸载组件 setState。
  const unmountAbortRef = useRef<AbortController | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    unmountAbortRef.current = controller;
    return () => {
      controller.abort();
    };
  }, []);

  const refreshStockSelection = useCallback(async () => {
    if (isRefreshing) return;

    const signal = unmountAbortRef.current?.signal;
    setIsRefreshing(true);
    setRefreshError(null);
    setRefreshTone("warning");
    setRefreshResult(`正在重新计算选股${asOfDate ? `：${asOfDate}` : ""}`);

    try {
      const refresh = await runPollingTask<MacroToolkitChoiceStockRefreshRun>({
        start: async () => {
          const response = await client.refreshChoiceStock({
            asOfDate,
            refreshHistory: true,
            refreshFactors: true,
            factorMaxStockCount: null,
          });
          return response.result.refresh;
        },
        getStatus: async (runId) => {
          const response = await client.getChoiceStockRefreshStatus(runId);
          return response.result.refresh;
        },
        intervalMs: 5_000,
        maxAttempts: 240,
        isTerminal: (status) => {
          const normalized = normalizedStatus(status);
          return (
            normalized === "completed"
            || normalized === "failed"
            || normalized === "partial"
            || normalized === "no_rows"
            || normalized === "blocked"
          );
        },
        signal,
        onUpdate: (payload) => {
          setRefreshTone(refreshToneForPayload(payload));
          setRefreshResult(refreshStatusLabel(payload));
        },
      });

      const refreshStatus = normalizedStatus(refresh.status);
      const closureStatus = refreshClosureStatus(refresh);
      const isBlocked = refreshStatus === "blocked" || closureStatus === "blocked";
      const isNoRows = refreshStatus === "no_rows" || closureStatus === "no_rows";
      if (isBlocked || isNoRows) {
        if (signal?.aborted) return;
        setRefreshTone(isBlocked ? "negative" : "warning");
        setRefreshResult(refreshStatusLabel(refresh));
        return;
      }

      const isPartial =
        refreshStatus !== "failed"
        && closureStatus !== "failed"
        && (refreshStatus === "partial" || closureStatus === "partial");

      if (isPartial) {
        if (signal?.aborted) return;
        setRefreshTone("warning");
        setRefreshResult(refreshStatusLabel(refresh));
        await queryClient.invalidateQueries({ queryKey: ["stock-analysis"] });
        return;
      }

      if (refreshStatus !== "completed" || closureStatus !== "completed") {
        throw new Error(refreshStatusLabel(refresh));
      }

      if (signal?.aborted) return;
      setRefreshTone("positive");
      setRefreshResult(refreshStatusLabel(refresh));
      await queryClient.invalidateQueries({ queryKey: ["stock-analysis"] });
    } catch (error) {
      if (signal?.aborted) return;
      setRefreshResult(null);
      setRefreshTone("negative");
      setRefreshError(error instanceof Error ? error.message : "选股刷新失败");
    } finally {
      if (!signal?.aborted) {
        setIsRefreshing(false);
      }
    }
  }, [asOfDate, client, isRefreshing, queryClient]);

  const refreshStatusMessage = refreshError ?? refreshResult;
  const refreshStatusTone: RefreshTone = refreshStatusMessage ? refreshTone : "neutral";

  return {
    isRefreshing,
    refreshStatusMessage,
    refreshStatusTone,
    refreshStockSelection,
  };
}
