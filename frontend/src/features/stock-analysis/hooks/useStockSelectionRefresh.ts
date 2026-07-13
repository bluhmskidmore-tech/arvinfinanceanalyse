import { useCallback, useState } from "react";
import type { QueryClient } from "@tanstack/react-query";

import type { ApiClient } from "../../../api/client";
import type { MacroToolkitChoiceStockRefreshRun } from "../../../api/macroToolkitClient";
import { runPollingTask } from "../../../app/jobs/polling";

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
  return `历史 ${payload.history_row_count ?? "-"} 行，因子 ${payload.factor_row_count ?? "-"} 行`;
}

function refreshStatusLabel(payload: MacroToolkitChoiceStockRefreshRun): string {
  const runId = refreshRunIdLabel(payload);
  if (payload.status === "completed") {
    return `选股已重新计算：${runId} · ${refreshRowsLabel(payload)}`;
  }
  if (payload.status === "failed") {
    const reason = payload.error_message ?? payload.failure_reason ?? payload.failure_category ?? "原因待返回";
    return `选股刷新失败：${reason} · ${runId}`;
  }
  return `选股刷新状态：${payload.status} · ${runId}`;
}

function refreshToneForStatus(status: string): RefreshTone {
  if (status === "completed") return "positive";
  if (status === "failed") return "negative";
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

  const refreshStockSelection = useCallback(async () => {
    if (isRefreshing) return;

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
      if (gateRefresh.status !== "completed") {
        throw new Error(gateRefresh.message ?? `门禁补充刷新失败：${gateRefresh.status}`);
      }

      setRefreshTone("positive");
      setRefreshResult(
        `${refreshStatusLabel(refresh)}；门禁补充已刷新 ${gateRefresh.computed_rows} 行`,
      );
      await queryClient.invalidateQueries({ queryKey: ["stock-analysis"] });
    } catch (error) {
      setRefreshResult(null);
      setRefreshTone("negative");
      setRefreshError(error instanceof Error ? error.message : "选股刷新失败");
    } finally {
      setIsRefreshing(false);
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
