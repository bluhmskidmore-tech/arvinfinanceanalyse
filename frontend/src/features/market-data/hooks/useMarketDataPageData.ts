import { useCallback, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import { apiQueryKeys } from "../../../api/queryKeys";
import { runPollingTask } from "../../../app/jobs/polling";
import {
  externalDataQueryOptions,
  nonCancellingRefetchOptions,
} from "../../../app/externalDataRefreshPolicy";
import { buildMarketDataPageModel } from "../pages/marketDataPageModel";

function todayIsoDate() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function useMarketDataPageData() {
  const client = useApiClient();
  const queryClient = useQueryClient();
  const [watchDate, setWatchDate] = useState(todayIsoDate);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshStatus, setRefreshStatus] = useState("");
  const [refreshError, setRefreshError] = useState("");

  const catalogQuery = useQuery({
    queryKey: ["market-data", "macro-foundation", client.mode],
    queryFn: () => client.getMacroFoundation(),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "stable", fetch_mode: "date_slice" }),
  });
  const latestQuery = useQuery({
    queryKey: ["market-data", "choice-macro-latest", client.mode],
    queryFn: () => client.getChoiceMacroLatest(),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "fallback", fetch_mode: "latest" }),
  });
  const fxAnalyticalQuery = useQuery({
    queryKey: ["market-data", "fx-analytical", client.mode],
    queryFn: () => client.getFxAnalytical(),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "fallback", fetch_mode: "latest" }),
  });
  const ncdFundingProxyQuery = useQuery({
    queryKey: ["market-data", "ncd-funding-proxy", client.mode],
    queryFn: () => client.getNcdFundingProxy(),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "fallback", fetch_mode: "latest" }),
  });
  const livermoreStrategyQuery = useQuery({
    queryKey: ["market-data", "livermore-strategy", client.mode, watchDate],
    queryFn: () => client.getLivermoreStrategy({ asOfDate: watchDate }),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "stable", fetch_mode: "date_slice" }),
  });
  const formalRatesQuery = useQuery({
    queryKey: apiQueryKeys.marketRates(client.mode, watchDate),
    queryFn: () => client.getMarketDataRates(),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "stable", fetch_mode: "date_slice" }),
  });

  const basePageModel = useMemo(
    () =>
      buildMarketDataPageModel({
        catalogEnvelope: catalogQuery.data,
        latestEnvelope: latestQuery.data,
        fxAnalyticalEnvelope: fxAnalyticalQuery.data,
        formalRatesEnvelope: formalRatesQuery.data,
        livermoreStrategyEnvelope: livermoreStrategyQuery.data,
        ncdFundingProxyMeta: ncdFundingProxyQuery.data?.result_meta,
      }),
    [
      catalogQuery.data,
      latestQuery.data,
      fxAnalyticalQuery.data,
      formalRatesQuery.data,
      livermoreStrategyQuery.data,
      ncdFundingProxyQuery.data?.result_meta,
    ],
  );

  const macroBondLinkageQueryKey = useMemo(
    () => ["market-data", "macro-bond-linkage", client.mode, basePageModel.linkageReportDate] as const,
    [client.mode, basePageModel.linkageReportDate],
  );
  const macroBondLinkageQuery = useQuery({
    queryKey: macroBondLinkageQueryKey,
    queryFn: () => client.getMacroBondLinkageAnalysis({ reportDate: basePageModel.linkageReportDate }),
    enabled: Boolean(basePageModel.linkageReportDate),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "fallback", fetch_mode: "latest" }),
  });

  const pageModel = useMemo(
    () =>
      buildMarketDataPageModel({
        catalogEnvelope: catalogQuery.data,
        latestEnvelope: latestQuery.data,
        fxAnalyticalEnvelope: fxAnalyticalQuery.data,
        formalRatesEnvelope: formalRatesQuery.data,
        macroBondLinkageEnvelope: macroBondLinkageQuery.data,
        livermoreStrategyEnvelope: livermoreStrategyQuery.data,
        ncdFundingProxyMeta: ncdFundingProxyQuery.data?.result_meta,
      }),
    [
      catalogQuery.data,
      latestQuery.data,
      fxAnalyticalQuery.data,
      formalRatesQuery.data,
      macroBondLinkageQuery.data,
      livermoreStrategyQuery.data,
      ncdFundingProxyQuery.data?.result_meta,
    ],
  );

  const refreshMacroBondLinkage = useCallback(async () => {
    if (!basePageModel.linkageReportDate) {
      return;
    }
    await queryClient.cancelQueries({ queryKey: macroBondLinkageQueryKey, exact: true });
    const envelope = await client.getMacroBondLinkageAnalysis({
      reportDate: basePageModel.linkageReportDate,
    });
    queryClient.setQueryData(macroBondLinkageQueryKey, envelope);
  }, [basePageModel.linkageReportDate, client, macroBondLinkageQueryKey, queryClient]);

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    setRefreshError("");
    setRefreshStatus("正在刷新宏观数据（回填 30 天）…");
    try {
      const payload = await runPollingTask({
        start: () => client.refreshChoiceMacro(30),
        getStatus: (runId) => client.getChoiceMacroRefreshStatus(runId),
        intervalMs: 3000,
        maxAttempts: 120,
        onUpdate: (p) => {
          setRefreshStatus([p.status, p.run_id].filter(Boolean).join(" · "));
        },
      });
      if (payload.status !== "completed") {
        throw new Error(payload.error_message ?? `刷新未完成：${payload.status}`);
      }
      setRefreshStatus("刷新完成");
      await Promise.all([
        catalogQuery.refetch(nonCancellingRefetchOptions),
        latestQuery.refetch(nonCancellingRefetchOptions),
        formalRatesQuery.refetch(nonCancellingRefetchOptions),
        fxAnalyticalQuery.refetch(nonCancellingRefetchOptions),
        ncdFundingProxyQuery.refetch(nonCancellingRefetchOptions),
        refreshMacroBondLinkage(),
        livermoreStrategyQuery.refetch(nonCancellingRefetchOptions),
      ]);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setRefreshError(msg);
      setRefreshStatus("");
    } finally {
      setIsRefreshing(false);
    }
  }, [
    client,
    catalogQuery,
    latestQuery,
    formalRatesQuery,
    fxAnalyticalQuery,
    ncdFundingProxyQuery,
    refreshMacroBondLinkage,
    livermoreStrategyQuery,
  ]);

  return {
    clientMode: client.mode,
    watchDate,
    setWatchDate,
    isRefreshing,
    refreshStatus,
    refreshError,
    handleRefresh,
    pageModel,
    catalogQuery,
    latestQuery,
    fxAnalyticalQuery,
    ncdFundingProxyQuery,
    livermoreStrategyQuery,
    formalRatesQuery,
    macroBondLinkageQuery,
    ncdFundingProxy: ncdFundingProxyQuery.data?.result,
    refreshGateSupplement: () => client.refreshGateSupplement({ asOfDate: watchDate }),
  };
}
