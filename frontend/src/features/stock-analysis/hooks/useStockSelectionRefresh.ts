import { useCallback, useEffect, useRef, useState } from "react";
import type { QueryClient } from "@tanstack/react-query";

import type { ApiClient } from "../../../api/client";
import type { MacroToolkitChoiceStockRefreshRun } from "../../../api/macroToolkitClient";
import type { LivermoreGateSupplementRefreshAcceptance } from "../../../api/marketDataClient";
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

function refreshStatusLabel(payload: MacroToolkitChoiceStockRefreshRun): string {
  const runId = refreshRunIdLabel(payload);
  if (payload.status === "completed") {
    return `选股已重新计算：${runId} · ${refreshRowsLabel(payload)}`;
  }
  if (payload.status === "failed") {
    const reason = payload.failure_category?.trim() || "原因待返回";
    return `选股刷新失败：${reason} · ${runId}`;
  }
  return `选股刷新状态：${payload.status} · ${runId}`;
}

function refreshToneForStatus(status: string): RefreshTone {
  if (status === "completed") return "positive";
  if (status === "failed") return "negative";
  return "warning";
}

function gateRefreshStatusLabel(payload: LivermoreGateSupplementRefreshAcceptance): string {
  if (payload.status === "completed") {
    return `门禁补充已刷新 ${payload.computed_rows ?? 0} 行，run_id ${payload.run_id}`;
  }
  if (payload.status === "failed") {
    const reason = payload.failure_category?.trim() || payload.error_message?.trim() || payload.status;
    return `门禁补充刷新失败：${reason} · run_id ${payload.run_id}`;
  }
  if (
    payload.status === "partial"
    || payload.status === "insufficient_data"
    || payload.status === "no_computable_dates"
  ) {
    return payload.message ?? `门禁补充状态：${payload.status} · run_id ${payload.run_id}`;
  }
  return `门禁补充刷新已受理并排队：run_id ${payload.run_id}`;
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
        signal,
        onUpdate: (payload) => {
          setRefreshTone(refreshToneForStatus(payload.status));
          setRefreshResult(refreshStatusLabel(payload));
        },
      });

      if (refresh.status !== "completed") {
        throw new Error(refreshStatusLabel(refresh));
      }

      const gateRefresh = await client.refreshGateSupplement({
        ...(asOfDate ? { asOfDate } : {}),
      });
      const gateRefreshStatus = await runPollingTask<LivermoreGateSupplementRefreshAcceptance>({
        start: async () => gateRefresh,
        getStatus: async (runId) => client.getLivermoreGateSupplementRefreshStatus(runId),
        intervalMs: 3_000,
        maxAttempts: 120,
        signal,
        isTerminal: (status) =>
          status === "completed"
          || status === "failed"
          || status === "partial"
          || status === "insufficient_data"
          || status === "no_computable_dates",
        onUpdate: (payload) => {
          setRefreshTone(payload.status === "completed" ? "positive" : "warning");
          setRefreshResult(`${refreshStatusLabel(refresh)}；${gateRefreshStatusLabel(payload)}`);
        },
      });
      if (gateRefreshStatus.status !== "completed") {
        throw new Error(gateRefreshStatusLabel(gateRefreshStatus));
      }

      if (signal?.aborted) return;
      setRefreshTone("positive");
      setRefreshResult(
        `${refreshStatusLabel(refresh)}；${gateRefreshStatusLabel(gateRefreshStatus)}`,
      );
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
