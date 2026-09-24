import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type {
  LivermoreManualPositionInput,
  MacroBondLinkagePayload,
  MacroBondLinkageTopCorrelation,
} from "../../../api/contracts";
import type { EChartsOption } from "../../../lib/echarts";
import {
  buildCorrelationMatrix,
  buildDriverWaterfall,
  buildMomentumScoreboard,
  computeEquityBondERP,
  detectVolatilityClustering,
  identifyMarketRegime,
  trendGroupLabels,
  type TrendGroupKey,
} from "../lib/crossAssetAnalytics";
import { buildDriverColumns, buildEnvironmentTags } from "../lib/crossAssetDriversModel";
import {
  buildCrossAssetCandidateActions,
  buildCrossAssetClassAnalysisRows,
  buildCrossAssetEquityEvidenceItems,
  buildCrossAssetEventItems,
  buildCrossAssetFirstScreenDisplayContract,
  buildCrossAssetNcdProxyEvidence,
  buildCrossAssetStatusFlags,
  buildCrossAssetWatchList,
  buildResearchSummaryCards,
  buildTransmissionAxisRows,
  formatLinkageCorrelationDisplay,
} from "../lib/crossAssetDriversPageModel";
import { maxCrossAssetHeadlineTradeDate, resolveCrossAssetKpis } from "../lib/crossAssetKpiModel";
import { formatLinkageCorrelationTarget } from "../lib/crossAssetLinkageLabels";
import { formatCrossAssetLinkageWarnings } from "../lib/crossAssetLinkageWarnings";
import { classifyCrossAssetQueryFailure, type CrossAssetModuleFailure } from "../lib/crossAssetQueryFailure";
import { buildCrossAssetTrendOption, buildCrossAssetTrendSummary } from "../lib/crossAssetTrendChart";
import { buildTransmissionChainGraph } from "../lib/crossAssetTransmissionGraph";
import { buildYieldCurveSeries } from "../lib/crossAssetYieldCurve";
import { buildEnvFactorDetailRows } from "../lib/envScoreFactorDetail";

function linkageHeatmapRows(correlations: MacroBondLinkageTopCorrelation[]) {
  if (correlations.length === 0) {
    return [
      {
        id: "empty",
        indicator: "暂无治理后的联动排序",
        current: "不可用",
        mid: "不可用",
        eval: "待定",
        evalTone: "warning" as const,
      },
    ];
  }

  return correlations.slice(0, 8).map((row, index) => {
    const indicator = formatLinkageCorrelationTarget(row.series_name, row.target_family, row.target_tenor);
    const id = [row.series_id, row.series_name, row.target_family, row.target_tenor, row.direction, index]
      .filter(Boolean)
      .join("|");
    const evalTone = row.direction === "positive" ? "bull" : row.direction === "negative" ? "bear" : "warning";
    const evalLabel = row.direction === "positive" ? "正向" : row.direction === "negative" ? "负向" : "混合";
    return {
      id,
      indicator,
      current: formatLinkageCorrelationDisplay(row.correlation_3m),
      mid: formatLinkageCorrelationDisplay(row.correlation_6m),
      eval: evalLabel,
      evalTone,
    };
  });
}

function visibleTrendOptionFor(
  trendOption: EChartsOption | null,
  trendGroup: TrendGroupKey,
  kpis: ReturnType<typeof resolveCrossAssetKpis>,
) {
  const visibleLabels = trendGroupLabels(trendGroup, kpis);
  if (!trendOption || !visibleLabels || !trendOption.legend || !Array.isArray(trendOption.series)) {
    return trendOption;
  }
  const selected: Record<string, boolean> = {};
  for (const series of trendOption.series as Array<{ name?: string }>) {
    if (series.name) {
      selected[series.name] = visibleLabels.has(series.name);
    }
  }
  return {
    ...trendOption,
    legend: {
      ...(typeof trendOption.legend === "object" ? trendOption.legend : {}),
      selected,
    },
  };
}

type CrossAssetViewModelOptions = {
  researchCalendarEnabled: boolean;
  livermoreEnabled: boolean;
};

export function useCrossAssetViewModel({
  researchCalendarEnabled,
  livermoreEnabled,
}: CrossAssetViewModelOptions) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  const [trendGroup, setTrendGroup] = useState<TrendGroupKey>("all");

  const latestQuery = useQuery({
    queryKey: ["workbench-shell", "choice-macro-latest", client.mode],
    queryFn: () => client.getChoiceMacroLatest(),
    retry: false,
    refetchOnMount: "always",
  });
  const latestSeries = useMemo(() => latestQuery.data?.result.series ?? [], [latestQuery.data?.result.series]);
  const latestMeta = latestQuery.data?.result_meta;
  const crossAssetDataDate = useMemo(() => maxCrossAssetHeadlineTradeDate(latestSeries), [latestSeries]);
  const linkageReportDate = useMemo(() => {
    if (crossAssetDataDate) return crossAssetDataDate;
    if (latestSeries.length === 0) return "";
    return latestSeries.map((point) => point.trade_date).sort((left, right) => right.localeCompare(left))[0];
  }, [crossAssetDataDate, latestSeries]);

  const researchCalendarQuery = useQuery({
    queryKey: ["cross-asset", "research-calendar", client.mode, linkageReportDate],
    queryFn: () => client.getResearchCalendarEvents({ reportDate: linkageReportDate }),
    enabled: researchCalendarEnabled && Boolean(linkageReportDate),
    retry: false,
  });
  const macroBondLinkageQuery = useQuery({
    queryKey: ["cross-asset", "macro-bond-linkage", client.mode, linkageReportDate],
    queryFn: () => client.getMacroBondLinkageAnalysis({ reportDate: linkageReportDate }),
    enabled: Boolean(linkageReportDate),
    retry: false,
  });
  const ncdFundingProxyQuery = useQuery({
    queryKey: ["cross-asset", "ncd-funding-proxy", client.mode],
    queryFn: () => client.getNcdFundingProxy(),
    retry: false,
  });

  const livermoreAsOfDate = crossAssetDataDate || linkageReportDate;
  const livermoreStrategyQuery = useQuery({
    queryKey: ["cross-asset", "livermore-strategy", client.mode, livermoreAsOfDate],
    queryFn: () => client.getLivermoreStrategy({ asOfDate: livermoreAsOfDate }),
    enabled: livermoreEnabled && Boolean(livermoreAsOfDate),
    retry: false,
  });
  const livermoreStrategyResolvedAsOfDate = livermoreStrategyQuery.data?.result?.as_of_date || livermoreAsOfDate;
  const livermoreSignalConfluenceQueryKey = [
    "cross-asset",
    "livermore-signal-confluence",
    client.mode,
    livermoreStrategyResolvedAsOfDate,
  ] as const;
  const livermoreSignalConfluenceQuery = useQuery({
    queryKey: livermoreSignalConfluenceQueryKey,
    queryFn: () => client.getLivermoreSignalConfluence({ asOfDate: livermoreStrategyResolvedAsOfDate }),
    enabled:
      livermoreEnabled &&
      Boolean(livermoreStrategyResolvedAsOfDate && !livermoreStrategyQuery.isLoading),
    retry: false,
  });
  const livermoreManualPositionMutation = useMutation({
    mutationFn: (options: { asOfDate: string; positions: LivermoreManualPositionInput[] }) => {
      if (!options.asOfDate) {
        throw new Error("缺少策略日期，无法写入持仓。");
      }
      return client.materializeLivermoreManualPositionSnapshot(options);
    },
    onSuccess: () => {
      void livermoreStrategyQuery.refetch();
      void queryClient.invalidateQueries({ queryKey: livermoreSignalConfluenceQueryKey });
      void queryClient.refetchQueries({
        queryKey: livermoreSignalConfluenceQueryKey,
        type: "active",
      });
    },
  });
  const livermoreManualSubmitError =
    livermoreManualPositionMutation.error instanceof Error
      ? livermoreManualPositionMutation.error.message
      : livermoreManualPositionMutation.error
        ? String(livermoreManualPositionMutation.error)
        : null;

  const macroBondLinkage = useMemo(
    () => macroBondLinkageQuery.data?.result ?? ({} as Partial<MacroBondLinkagePayload>),
    [macroBondLinkageQuery.data?.result],
  );
  const linkageMeta = macroBondLinkageQuery.data?.result_meta;
  const macroBondLinkageWarnings = useMemo(
    () => formatCrossAssetLinkageWarnings(macroBondLinkage.warnings ?? []),
    [macroBondLinkage.warnings],
  );
  const linkageUnavailableReason = macroBondLinkageQuery.isError
    ? classifyCrossAssetQueryFailure(macroBondLinkageQuery.error)
    : undefined;
  const moduleFailures = useMemo((): CrossAssetModuleFailure[] => {
    const failures: CrossAssetModuleFailure[] = [];
    if (latestQuery.isError) failures.push({ module: "choice_macro.latest", kind: classifyCrossAssetQueryFailure(latestQuery.error) });
    if (macroBondLinkageQuery.isError) {
      failures.push({ module: "macro_bond_linkage.analysis", kind: classifyCrossAssetQueryFailure(macroBondLinkageQuery.error) });
    }
    if (ncdFundingProxyQuery.isError) {
      failures.push({ module: "market_data_ncd_proxy", kind: classifyCrossAssetQueryFailure(ncdFundingProxyQuery.error) });
    }
    return failures;
  }, [latestQuery.error, latestQuery.isError, macroBondLinkageQuery.error, macroBondLinkageQuery.isError, ncdFundingProxyQuery.error, ncdFundingProxyQuery.isError]);

  const env = useMemo(() => macroBondLinkage.environment_score ?? {}, [macroBondLinkage.environment_score]);
  const kpis = useMemo(() => resolveCrossAssetKpis(latestSeries), [latestSeries]);
  // The drivers page is pinned to the dh-api terminal theme; charts get concrete dark colors.
  const trendOption = useMemo(() => buildCrossAssetTrendOption(latestSeries, "terminal"), [latestSeries]);
  const visibleTrendOption = useMemo(
    () => visibleTrendOptionFor(trendOption, trendGroup, kpis),
    [kpis, trendGroup, trendOption],
  );
  const trendSummary = useMemo(() => buildCrossAssetTrendSummary(kpis), [kpis]);
  const correlationMatrix = useMemo(() => buildCorrelationMatrix(kpis), [kpis]);
  const momentumRows = useMemo(() => buildMomentumScoreboard(kpis), [kpis]);
  const yieldCurves = useMemo(() => buildYieldCurveSeries(latestSeries), [latestSeries]);
  const envFactorDetailRows = useMemo(
    () => buildEnvFactorDetailRows(macroBondLinkage.environment_score),
    [macroBondLinkage.environment_score],
  );
  const envFactorScoringMethod = useMemo((): string | null => {
    const factors = macroBondLinkage.environment_score?.contributing_factors ?? [];
    for (const factor of factors) {
      const method = factor?.scoring_method;
      if (typeof method === "string" && method.trim()) {
        return method;
      }
    }
    return null;
  }, [macroBondLinkage.environment_score]);
  const volAlert = useMemo(() => detectVolatilityClustering(kpis), [kpis]);
  const marketRegime = useMemo(() => identifyMarketRegime(kpis), [kpis]);
  const firstScreenConclusion = useMemo(() => {
    if (macroBondLinkageQuery.isLoading || latestQuery.isLoading) return null;
    if (env.signal_description) return env.signal_description;
    if (macroBondLinkageQuery.isError) {
      const prefix = linkageUnavailableReason === "permission" ? "联动分析权限受限" : "联动分析暂不可用";
      return `${prefix}；首屏参考市场体制 ${marketRegime.label}：${marketRegime.description}`;
    }
    return null;
  }, [env.signal_description, latestQuery.isLoading, linkageUnavailableReason, macroBondLinkageQuery.isError, macroBondLinkageQuery.isLoading, marketRegime.description, marketRegime.label]);
  const erpData = useMemo(() => computeEquityBondERP(kpis), [kpis]);
  const waterfallBars = useMemo(() => buildDriverWaterfall(env), [env]);
  const drivers = useMemo(() => buildDriverColumns(env), [env]);
  const envTags = useMemo(() => buildEnvironmentTags(env), [env]);
  const heatmapRows = useMemo(() => linkageHeatmapRows(macroBondLinkage.top_correlations ?? []), [macroBondLinkage.top_correlations]);
  const researchViewCards = useMemo(
    () =>
      buildResearchSummaryCards({
        researchViews: macroBondLinkage.research_views,
        env,
        topCorrelations: macroBondLinkage.top_correlations ?? [],
        linkageWarnings: macroBondLinkageWarnings,
        linkageUnavailable: macroBondLinkageQuery.isError,
        linkageUnavailableReason,
      }),
    [env, linkageUnavailableReason, macroBondLinkage.research_views, macroBondLinkage.top_correlations, macroBondLinkageQuery.isError, macroBondLinkageWarnings],
  );
  const transmissionAxisRows = useMemo(
    () =>
      buildTransmissionAxisRows({
        transmissionAxes: macroBondLinkage.transmission_axes,
        env,
        linkageUnavailable: macroBondLinkageQuery.isError,
        linkageUnavailableReason,
      }),
    [env, linkageUnavailableReason, macroBondLinkage.transmission_axes, macroBondLinkageQuery.isError],
  );
  const transmissionChainGraph = useMemo(
    () => buildTransmissionChainGraph({ transmissionAxisRows, kpis, researchViewCards }),
    [transmissionAxisRows, kpis, researchViewCards],
  );
  const assetClassAnalysisRows = useMemo(
    () => buildCrossAssetClassAnalysisRows({ kpis, transmissionAxes: transmissionAxisRows, latestMeta, linkageMeta }),
    [kpis, latestMeta, linkageMeta, transmissionAxisRows],
  );
  const equityEvidenceItems = useMemo(() => buildCrossAssetEquityEvidenceItems(kpis, latestMeta), [kpis, latestMeta]);
  const ncdProxyPayload = ncdFundingProxyQuery.data?.result ?? null;
  const livermoreStrategyPayload = livermoreStrategyQuery.data?.result ?? null;
  const livermoreSignalConfluencePayload = livermoreSignalConfluenceQuery.data?.result ?? null;
  const ncdProxyEvidence = useMemo(
    () =>
      buildCrossAssetNcdProxyEvidence({
        result: ncdProxyPayload,
        available: ncdFundingProxyQuery.isSuccess && !ncdFundingProxyQuery.isError && Boolean(ncdFundingProxyQuery.data),
        failureKind: ncdFundingProxyQuery.isError ? classifyCrossAssetQueryFailure(ncdFundingProxyQuery.error) : undefined,
      }),
    [ncdFundingProxyQuery.data, ncdFundingProxyQuery.error, ncdFundingProxyQuery.isError, ncdFundingProxyQuery.isSuccess, ncdProxyPayload],
  );
  const candidateActions = useMemo(
    () =>
      buildCrossAssetCandidateActions({
        researchViews: macroBondLinkage.research_views,
        transmissionAxes: macroBondLinkage.transmission_axes,
        env,
        topCorrelations: macroBondLinkage.top_correlations ?? [],
        linkageWarnings: macroBondLinkageWarnings,
        ncdProxy: ncdProxyPayload,
        linkageUnavailable: macroBondLinkageQuery.isError,
        linkageUnavailableReason,
      }),
    [env, linkageUnavailableReason, macroBondLinkage.research_views, macroBondLinkage.top_correlations, macroBondLinkage.transmission_axes, macroBondLinkageQuery.isError, macroBondLinkageWarnings, ncdProxyPayload],
  );
  const eventItems = useMemo(() => buildCrossAssetEventItems({ events: researchCalendarQuery.data ?? [] }), [researchCalendarQuery.data]);
  const watchRows = useMemo(
    () =>
      buildCrossAssetWatchList({
        kpis,
        researchViews: macroBondLinkage.research_views,
        transmissionAxes: macroBondLinkage.transmission_axes,
        topCorrelations: macroBondLinkage.top_correlations ?? [],
        linkageWarnings: macroBondLinkageWarnings,
        linkageUnavailable: macroBondLinkageQuery.isError,
        linkageUnavailableReason,
      }),
    [kpis, linkageUnavailableReason, macroBondLinkage.research_views, macroBondLinkage.top_correlations, macroBondLinkage.transmission_axes, macroBondLinkageQuery.isError, macroBondLinkageWarnings],
  );
  const statusFlags = useMemo(
    () =>
      latestQuery.isLoading || (Boolean(linkageReportDate) && macroBondLinkageQuery.isLoading)
        ? []
        : buildCrossAssetStatusFlags({
            latestMeta,
            linkageMeta,
            latestSeries,
            crossAssetDataDate,
            linkageReportDate,
            linkageWarnings: macroBondLinkageWarnings,
            moduleFailures,
          }),
    [crossAssetDataDate, latestMeta, latestQuery.isLoading, latestSeries, linkageMeta, linkageReportDate, macroBondLinkageQuery.isLoading, macroBondLinkageWarnings, moduleFailures],
  );
  const firstScreenDisplay = useMemo(
    () =>
      buildCrossAssetFirstScreenDisplayContract({
        reportDate: crossAssetDataDate || linkageReportDate,
        firstScreenConclusion,
        marketRegime,
        drivers,
        envTags,
        assetClassAnalysisRows,
        statusFlags,
        isLoading: macroBondLinkageQuery.isLoading || latestQuery.isLoading,
      }),
    [
      assetClassAnalysisRows,
      crossAssetDataDate,
      drivers,
      envTags,
      firstScreenConclusion,
      latestQuery.isLoading,
      linkageReportDate,
      macroBondLinkageQuery.isLoading,
      marketRegime,
      statusFlags,
    ],
  );
  const hasPortfolioImpact = Object.keys(macroBondLinkage.portfolio_impact ?? {}).length > 0;
  const linkageBodyEmpty =
    macroBondLinkageQuery.isSuccess &&
    Boolean(linkageReportDate) &&
    macroBondLinkage.environment_score?.composite_score == null &&
    !hasPortfolioImpact &&
    macroBondLinkageWarnings.length === 0 &&
    (macroBondLinkage.top_correlations ?? []).length === 0;
  const topCorrelationSummary = macroBondLinkage.top_correlations?.[0]
    ? formatLinkageCorrelationTarget(
        macroBondLinkage.top_correlations[0].series_name,
        macroBondLinkage.top_correlations[0].target_family,
        macroBondLinkage.top_correlations[0].target_tenor,
      )
    : null;

  return {
    assetClassAnalysisRows,
    candidateActions,
    correlationMatrix,
    crossAssetDataDate,
    drivers,
    env,
    envFactorDetailRows,
    envFactorScoringMethod,
    envTags,
    equityEvidenceItems,
    erpData,
    eventItems,
    firstScreenDisplay,
    firstScreenConclusion,
    hasPortfolioImpact,
    heatmapRows,
    kpis,
    latestMeta,
    latestQuery,
    linkageBodyEmpty,
    linkageMeta,
    linkageReportDate,
    livermoreAsOfDate,
    livermoreManualPositionMutation,
    livermoreManualSubmitError,
    livermoreSignalConfluencePayload,
    livermoreSignalConfluenceQuery,
    livermoreStrategyPayload,
    livermoreStrategyQuery,
    livermoreStrategyResolvedAsOfDate,
    macroBondLinkage,
    macroBondLinkageQuery,
    macroBondLinkageWarnings,
    marketRegime,
    momentumRows,
    ncdFundingProxyQuery,
    ncdProxyEvidence,
    researchCalendarQuery,
    researchViewCards,
    statusFlags,
    setTrendGroup,
    topCorrelationSummary,
    transmissionAxisRows,
    transmissionChainGraph,
    trendGroup,
    trendSummary,
    visibleTrendOption,
    volAlert,
    waterfallBars,
    watchRows,
    yieldCurves,
  };
}
