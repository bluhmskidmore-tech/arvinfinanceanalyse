import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import type { ApiClient } from "../../../api/client";
import type {
  LivermoreCandidateHistoryPortfolioBacktestPayload,
  LivermoreCycleProxyBacktestPayload,
  LivermoreSignalConfluencePayload,
  LivermoreStrategyPayload,
  StockAnalysisWorkbenchPayload,
} from "../../../api/contracts";
import { useDeferredSectionSeen } from "../../../hooks/useDeferredSectionSeen";
import type { WorkbenchSlowState } from "../lib/stockAnalysisPageModel";
import { subtractIsoCalendarDays } from "../lib/stockAnalysisDate";
import { stockAnalysisReadQueryOptions } from "../lib/stockAnalysisQueryOptions";
import { resolveStockAnalysisFormalUseAllowed } from "../lib/stockAnalysisWorkbenchQueueModel";

type SlowEvidenceQuery = {
  isLoading: boolean;
  isFetching: boolean;
  isError: boolean;
  isSuccess: boolean;
};

function useSlowEvidenceState(query: SlowEvidenceQuery, timeoutMs = 8000): WorkbenchSlowState {
  const [isSlow, setIsSlow] = useState(false);

  useEffect(() => {
    if (!query.isLoading && !query.isFetching) {
      setIsSlow(false);
      return undefined;
    }

    const timer = window.setTimeout(() => setIsSlow(true), timeoutMs);
    return () => window.clearTimeout(timer);
  }, [query.isLoading, query.isFetching, timeoutMs]);

  if (query.isError) return "error";
  if (query.isSuccess) return "success";
  if (isSlow) return "slow";
  if (query.isLoading || query.isFetching) return "loading";
  return "idle";
}

function isLivermoreStrategyPayload(value: unknown): value is LivermoreStrategyPayload {
  if (value == null || typeof value !== "object") return false;
  const payload = value as Partial<LivermoreStrategyPayload>;
  return payload.basis === "analytical" && payload.market_gate != null && Array.isArray(payload.supported_outputs);
}

function extractWorkbenchStrategyPayload(
  payload: StockAnalysisWorkbenchPayload | null | undefined,
): LivermoreStrategyPayload | null {
  const mainResult = payload?.modules.main?.result;
  return isLivermoreStrategyPayload(mainResult) ? mainResult : null;
}

/**
 * 股票分析工作台的全部数据读取：主策略快照 + 依赖其 as_of_date 的六个分析接口。
 *
 * 四个 `useDeferredSectionSeen` 门控以主策略的 as_of_date 为启用条件，因此必须和
 * 主查询同住一个 hook；页面只拿到 `seen` 与 `ref` 把它们挂到深研区块上。
 */
export function useStockAnalysisWorkbenchQueries({
  client,
  asOfOverride,
  candidateHistoryEndpointRequested,
  cycleProxyEndpointRequested,
  portfolioProxyEndpointRequested,
  firstScreenPriorityRequested,
  firstScreenOptimizationRequested,
}: {
  client: ApiClient;
  asOfOverride: string | null;
  candidateHistoryEndpointRequested: boolean;
  cycleProxyEndpointRequested: boolean;
  portfolioProxyEndpointRequested: boolean;
  firstScreenPriorityRequested: boolean;
  firstScreenOptimizationRequested: boolean;
}) {
  const strategyQueryKey = ["stock-analysis", "workbench", asOfOverride ?? "__default"] as const;

  const strategyQuery = useQuery({
    queryKey: strategyQueryKey,
    queryFn: () =>
      client.getStockAnalysisWorkbench({
        ...(asOfOverride ? { asOfDate: asOfOverride } : {}),
        topK: 10,
      }),
    ...stockAnalysisReadQueryOptions,
  });
  const isInitialWorkbenchLoading =
    strategyQuery.data == null && (strategyQuery.isLoading || strategyQuery.isFetching);

  const strategyPayload = extractWorkbenchStrategyPayload(strategyQuery.data?.result);
  const workbenchPayload: StockAnalysisWorkbenchPayload | null = strategyQuery.data?.result ?? null;
  const pretradeQualification = workbenchPayload?.pretrade_qualification ?? null;
  const pretradeDecisionReady = pretradeQualification?.status === "ready";
  const researchDateAligned = Boolean(
    workbenchPayload?.as_of_date &&
      strategyPayload?.as_of_date &&
      workbenchPayload.as_of_date === strategyPayload.as_of_date,
  );
  const researchReviewReady =
    workbenchPayload?.decision_summary.can_review_candidates === true && researchDateAligned;
  const resultMeta = strategyQuery.data?.result_meta;
  const formalUseAllowed = resolveStockAnalysisFormalUseAllowed(
    workbenchPayload?.formal_use_allowed,
    resultMeta?.formal_use_allowed,
  );
  const analyticsAsOf = strategyPayload?.as_of_date ?? null;
  const deferredSectionsEnabled = pretradeDecisionReady && Boolean(strategyPayload?.as_of_date);
  const cycleFrameworkSection = useDeferredSectionSeen<HTMLElement>(deferredSectionsEnabled);
  const strategyPrioritySection = useDeferredSectionSeen<HTMLElement>(deferredSectionsEnabled);
  const strategyBacktestSection = useDeferredSectionSeen<HTMLElement>(deferredSectionsEnabled);
  const strategyOptimizationSection = useDeferredSectionSeen<HTMLElement>(deferredSectionsEnabled);

  const confluenceQuery = useQuery({
    queryKey: ["stock-analysis", "livermore-signal-confluence", strategyPayload?.as_of_date ?? "__none"],
    queryFn: () =>
      client.getLivermoreSignalConfluence({
        asOfDate: strategyPayload?.as_of_date ?? undefined,
      }),
    enabled: pretradeDecisionReady && Boolean(strategyPayload?.as_of_date),
    ...stockAnalysisReadQueryOptions,
  });

  const confluencePayload: LivermoreSignalConfluencePayload | null =
    confluenceQuery.data?.result ?? null;

  const cycleRotationFramework = strategyPayload?.cycle_rotation_framework;
  const currentMarketState = strategyPayload?.market_gate.state ?? null;
  const strategyScoreQuery = useQuery({
    queryKey: [
      "stock-analysis",
      "livermore-strategy-score",
      analyticsAsOf ?? "__none",
      currentMarketState ?? "__none",
    ] as const,
    queryFn: () =>
      client.getLivermoreStrategyScore({
        snapshotTo: analyticsAsOf ?? undefined,
        currentMarketState: currentMarketState ?? undefined,
        minSample: 20,
        primaryHorizon: "return_5d",
      }),
    enabled: Boolean(
      pretradeDecisionReady &&
        analyticsAsOf &&
        (strategyPrioritySection.seen || firstScreenPriorityRequested),
    ),
    ...stockAnalysisReadQueryOptions,
  });
  const strategyScorePayload = strategyScoreQuery.data?.result ?? null;
  const strategyOptimizationQuery = useQuery({
    queryKey: [
      "stock-analysis",
      "livermore-strategy-optimization",
      analyticsAsOf ?? "__none",
      currentMarketState ?? "__none",
    ] as const,
    queryFn: () =>
      client.getLivermoreStrategyOptimization({
        snapshotTo: analyticsAsOf ?? undefined,
        currentMarketState: currentMarketState ?? undefined,
        minSample: 20,
        primaryHorizon: "return_5d",
      }),
    enabled: Boolean(
      pretradeDecisionReady &&
        analyticsAsOf &&
        (strategyOptimizationSection.seen || firstScreenOptimizationRequested),
    ),
    ...stockAnalysisReadQueryOptions,
  });
  const strategyOptimizationPayload = strategyOptimizationQuery.data?.result ?? null;
  const strategyBacktestSnapshotFrom = subtractIsoCalendarDays(analyticsAsOf, 10);

  const strategyBacktestQuery = useQuery({
    queryKey: [
      "stock-analysis",
      "livermore-candidate-history-strategy-backtest",
      strategyBacktestSnapshotFrom ?? "__none",
      analyticsAsOf ?? "__none",
    ] as const,
    queryFn: () =>
      client.getLivermoreCandidateHistory({
        snapshotFrom: strategyBacktestSnapshotFrom ?? undefined,
        snapshotTo: analyticsAsOf ?? undefined,
        limit: 500,
      }),
    enabled: Boolean(
      analyticsAsOf &&
        ((pretradeDecisionReady && strategyBacktestSection.seen) ||
          (researchReviewReady && candidateHistoryEndpointRequested)),
    ),
    ...stockAnalysisReadQueryOptions,
  });

  const strategyBacktestPayload = strategyBacktestQuery.data?.result ?? null;
  const strategyBacktestWindow = strategyBacktestPayload?.backtest_window_summary ?? null;
  const cycleProxyBacktestQuery = useQuery({
    queryKey: [
      "stock-analysis",
      "livermore-cycle-proxy-backtest",
      analyticsAsOf ?? "__none",
    ] as const,
    queryFn: () =>
      client.getLivermoreCycleProxyBacktest({
        snapshotTo: analyticsAsOf ?? undefined,
      }),
    enabled: Boolean(
      pretradeDecisionReady &&
        analyticsAsOf &&
        cycleRotationFramework &&
        (cycleFrameworkSection.seen || cycleProxyEndpointRequested),
    ),
    ...stockAnalysisReadQueryOptions,
  });
  const cycleProxyBacktestPayload: LivermoreCycleProxyBacktestPayload | null =
    cycleProxyBacktestQuery.data?.result ?? null;
  const candidateHistoryPortfolioBacktestQuery = useQuery({
    queryKey: [
      "stock-analysis",
      "livermore-candidate-history-portfolio-backtest",
      analyticsAsOf ?? "__none",
    ] as const,
    queryFn: () =>
      client.getLivermoreCandidateHistoryPortfolioBacktest({
        snapshotTo: analyticsAsOf ?? undefined,
      }),
    enabled: Boolean(
      pretradeDecisionReady &&
        analyticsAsOf &&
        cycleRotationFramework &&
        (cycleFrameworkSection.seen || portfolioProxyEndpointRequested),
    ),
    ...stockAnalysisReadQueryOptions,
  });
  const candidateHistoryPortfolioBacktestPayload: LivermoreCandidateHistoryPortfolioBacktestPayload | null =
    candidateHistoryPortfolioBacktestQuery.data?.result ?? null;

  const candidateHistorySlowState = useSlowEvidenceState(strategyBacktestQuery);
  const strategyScoreSlowState = useSlowEvidenceState(strategyScoreQuery);

  return {
    strategyQuery,
    isInitialWorkbenchLoading,
    strategyPayload,
    workbenchPayload,
    pretradeQualification,
    pretradeDecisionReady,
    researchDateAligned,
    researchReviewReady,
    resultMeta,
    formalUseAllowed,
    analyticsAsOf,
    cycleFrameworkSection,
    strategyPrioritySection,
    strategyBacktestSection,
    strategyOptimizationSection,
    confluenceQuery,
    confluencePayload,
    cycleRotationFramework,
    currentMarketState,
    strategyScoreQuery,
    strategyScorePayload,
    strategyOptimizationQuery,
    strategyOptimizationPayload,
    strategyBacktestSnapshotFrom,
    strategyBacktestQuery,
    strategyBacktestPayload,
    strategyBacktestWindow,
    cycleProxyBacktestQuery,
    cycleProxyBacktestPayload,
    candidateHistoryPortfolioBacktestQuery,
    candidateHistoryPortfolioBacktestPayload,
    candidateHistorySlowState,
    strategyScoreSlowState,
  };
}
