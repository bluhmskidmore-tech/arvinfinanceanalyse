import { useCallback, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import { apiQueryKeys } from "../../../api/queryKeys";
import { runPollingTask } from "../../../app/jobs/polling";
import {
  externalDataQueryOptions,
  nonCancellingRefetchOptions,
} from "../../../app/externalDataRefreshPolicy";
import { buildMarketDataCategoryStore } from "../lib/marketDataCategoryStore";
import { buildMarketDataPageModel } from "../pages/marketDataPageModel";

function todayIsoDate() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

type UseMarketDataPageDataOptions = {
  livermoreEnabled?: boolean;
  linkageEnabled?: boolean;
};

const marketDataQueryFocusOptions = {
  refetchOnWindowFocus: false,
} as const;

export function useMarketDataPageData(options: UseMarketDataPageDataOptions = {}) {
  const livermoreEnabled = options.livermoreEnabled ?? false;
  const linkageEnabled = options.linkageEnabled ?? false;
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
    ...marketDataQueryFocusOptions,
  });
  const latestQuery = useQuery({
    queryKey: ["market-data", "choice-macro-latest", client.mode],
    queryFn: () => client.getChoiceMacroLatest(),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "fallback", fetch_mode: "latest" }),
    ...marketDataQueryFocusOptions,
  });
  const fxAnalyticalQuery = useQuery({
    queryKey: ["market-data", "fx-analytical", client.mode],
    queryFn: () => client.getFxAnalytical(),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "fallback", fetch_mode: "latest" }),
    ...marketDataQueryFocusOptions,
  });
  const fxFormalStatusQuery = useQuery({
    queryKey: ["market-data", "fx-formal-status", client.mode],
    queryFn: () => client.getFxFormalStatus(),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "stable", fetch_mode: "date_slice" }),
    ...marketDataQueryFocusOptions,
  });
  const ncdFundingProxyQuery = useQuery({
    queryKey: ["market-data", "ncd-funding-proxy", client.mode],
    queryFn: () => client.getNcdFundingProxy(),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "fallback", fetch_mode: "latest" }),
    ...marketDataQueryFocusOptions,
  });
  const livermoreStrategyQuery = useQuery({
    queryKey: ["market-data", "livermore-strategy", client.mode, watchDate],
    queryFn: () => client.getLivermoreStrategy({ asOfDate: watchDate }),
    enabled: livermoreEnabled,
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "stable", fetch_mode: "date_slice" }),
    ...marketDataQueryFocusOptions,
  });
  const formalRatesQuery = useQuery({
    queryKey: apiQueryKeys.marketRates(client.mode, watchDate),
    queryFn: () => client.getMarketDataRates(),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "stable", fetch_mode: "date_slice" }),
    ...marketDataQueryFocusOptions,
  });

  const basePageModel = useMemo(
    () =>
      buildMarketDataPageModel({
        catalogEnvelope: catalogQuery.data,
        latestEnvelope: latestQuery.data,
        fxAnalyticalEnvelope: fxAnalyticalQuery.data,
        fxFormalStatusEnvelope: fxFormalStatusQuery.data,
        formalRatesEnvelope: formalRatesQuery.data,
        livermoreStrategyEnvelope: livermoreStrategyQuery.data,
        ncdFundingProxyMeta: ncdFundingProxyQuery.data?.result_meta,
      }),
    [
      catalogQuery.data,
      latestQuery.data,
      fxAnalyticalQuery.data,
      fxFormalStatusQuery.data,
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
    enabled: linkageEnabled && Boolean(basePageModel.linkageReportDate),
    retry: false,
    ...externalDataQueryOptions({ refresh_tier: "fallback", fetch_mode: "latest" }),
    ...marketDataQueryFocusOptions,
  });

  const pageModel = useMemo(
    () =>
      buildMarketDataPageModel({
        catalogEnvelope: catalogQuery.data,
        latestEnvelope: latestQuery.data,
        fxAnalyticalEnvelope: fxAnalyticalQuery.data,
        fxFormalStatusEnvelope: fxFormalStatusQuery.data,
        formalRatesEnvelope: formalRatesQuery.data,
        macroBondLinkageEnvelope: macroBondLinkageQuery.data,
        livermoreStrategyEnvelope: livermoreStrategyQuery.data,
        ncdFundingProxyMeta: ncdFundingProxyQuery.data?.result_meta,
      }),
    [
      catalogQuery.data,
      latestQuery.data,
      fxAnalyticalQuery.data,
      fxFormalStatusQuery.data,
      formalRatesQuery.data,
      macroBondLinkageQuery.data,
      livermoreStrategyQuery.data,
      ncdFundingProxyQuery.data?.result_meta,
    ],
  );

  const resolveLinkageReportDate = useCallback(() => {
    const latestEnvelope = queryClient.getQueryData<Awaited<ReturnType<typeof client.getChoiceMacroLatest>>>([
      "market-data",
      "choice-macro-latest",
      client.mode,
    ]);
    const catalogEnvelope = queryClient.getQueryData<Awaited<ReturnType<typeof client.getMacroFoundation>>>([
      "market-data",
      "macro-foundation",
      client.mode,
    ]);
    return buildMarketDataCategoryStore({
      catalog: catalogEnvelope?.result.catalog ?? [],
      latestSeries: latestEnvelope?.result.series ?? [],
      fxAnalyticalGroups: [],
    }).linkageReportDate;
  }, [client.mode, queryClient]);

  const refreshMacroBondLinkage = useCallback(async () => {
    const reportDate = resolveLinkageReportDate();
    if (!reportDate) {
      return;
    }
    const linkageQueryKey = ["market-data", "macro-bond-linkage", client.mode, reportDate] as const;
    await queryClient.cancelQueries({ queryKey: linkageQueryKey, exact: true });
    const envelope = await client.getMacroBondLinkageAnalysis({ reportDate });
    queryClient.setQueryData(linkageQueryKey, envelope);
  }, [client, queryClient, resolveLinkageReportDate]);

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
      await Promise.all([
        catalogQuery.refetch(nonCancellingRefetchOptions),
        latestQuery.refetch(nonCancellingRefetchOptions),
        formalRatesQuery.refetch(nonCancellingRefetchOptions),
        fxAnalyticalQuery.refetch(nonCancellingRefetchOptions),
        fxFormalStatusQuery.refetch(nonCancellingRefetchOptions),
        ncdFundingProxyQuery.refetch(nonCancellingRefetchOptions),
        livermoreEnabled ? livermoreStrategyQuery.refetch(nonCancellingRefetchOptions) : Promise.resolve(),
      ]);
      await refreshMacroBondLinkage();
      setRefreshStatus("刷新完成");
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
    fxFormalStatusQuery,
    ncdFundingProxyQuery,
    refreshMacroBondLinkage,
    livermoreEnabled,
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
    fxFormalStatusQuery,
    ncdFundingProxyQuery,
    livermoreStrategyQuery,
    formalRatesQuery,
    macroBondLinkageQuery,
    ncdFundingProxy: ncdFundingProxyQuery.data?.result,
    refreshGateSupplement: () => client.refreshGateSupplement({ asOfDate: watchDate }),
  };
}
