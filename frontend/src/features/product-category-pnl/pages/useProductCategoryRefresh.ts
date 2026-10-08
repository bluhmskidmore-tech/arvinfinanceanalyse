import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { ApiClient } from "../../../api/client";
import { runPollingTask } from "../../../app/jobs/polling";
import { usePollingTaskSignal } from "../../../app/jobs/usePollingTaskSignal";

type RefreshClient = Pick<
  ApiClient,
  "mode" | "refreshProductCategoryPnl" | "getProductCategoryRefreshStatus"
>;

/** Owns the refresh lifecycle shared by the refresh button and adjustment actions. */
export function useProductCategoryRefresh(client: RefreshClient) {
  const queryClient = useQueryClient();
  const getPollingSignal = usePollingTaskSignal();
  const [refreshPollSnapshot, setRefreshPollSnapshot] = useState<{
    status: string;
    run_id?: string;
  } | null>(null);
  const [lastRefreshRunId, setLastRefreshRunId] = useState<string | null>(null);
  const refresh = useMutation({
    retry: false,
    mutationFn: async () => {
      const signal = getPollingSignal();
      setRefreshPollSnapshot(null);
      const payload = await runPollingTask({
        signal,
        start: () => client.refreshProductCategoryPnl(),
        getStatus: (runId) => client.getProductCategoryRefreshStatus(runId),
        onUpdate: ({ status, run_id }) => {
          setRefreshPollSnapshot({ status, run_id });
        },
      });
      if (signal?.aborted) return;
      setLastRefreshRunId(payload.run_id);
      if (payload.status !== "completed") {
        throw new Error(payload.detail ?? `刷新任务未完成：${payload.status}`);
      }

      // All page queries use [domain, surface, mode, ...]. Read the current
      // observers after completion so changing dates/panels during polling works.
      const filters = {
        queryKey: ["product-category-pnl"],
        predicate: (query: { queryKey: readonly unknown[] }) =>
          query.queryKey[2] === client.mode,
      };
      // Discard reads started before materialization completed, including reads
      // without cached data. Their older response must not make the cache fresh.
      await queryClient.cancelQueries(filters);
      if (signal?.aborted) return;
      await queryClient.invalidateQueries({ ...filters, refetchType: "active" });
      // Disabled/unmounted queries stay stale until consumed. Query errors remain
      // on their existing page error/retry surfaces, separate from task failure.
    },
    onSettled: () => {
      if (!getPollingSignal()?.aborted) setRefreshPollSnapshot(null);
    },
  });

  return {
    isRefreshing: refresh.isPending,
    refreshPollSnapshot,
    refreshError: refresh.error
      ? refresh.error instanceof Error
        ? refresh.error.message
        : "刷新损益数据失败"
      : null,
    lastRefreshRunId,
    handleRefresh: () => refresh.mutate(),
    runRefreshWorkflow: () => refresh.mutateAsync(),
  };
}
