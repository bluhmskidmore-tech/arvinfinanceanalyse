import { useMemo } from "react";

import type {
  BacktestWindowSummary,
  LivermoreSignalConfluencePayload,
  LivermoreStrategyPayload,
  ResultMeta,
} from "../../../api/contracts";
import {
  buildObservationClosureSummary,
  buildStockEndpointEvidenceItems,
  isActionableLivermoreUnsupportedOutput,
  localizeStockBackendText,
} from "../lib/stockAnalysisPageModel";
import type {
  StockEndpointEvidenceQueryState,
  StockObservationClosureReasonInput,
} from "../lib/stockAnalysisPageModel";
import { stockSupplyFallbackLabel } from "../lib/stockAnalysisPageCopy";
import { dataGapFamilyLabel } from "../lib/stockAnalysisPageLabels";
import type { useSectorRankSeriesSupport } from "./useSectorRankSeriesSupport";
import type { useStockAnalysisWorkbenchQueries } from "./useStockAnalysisWorkbenchQueries";

export function endpointQueryState({
  enabled,
  isLoading,
  isFetching,
  isError,
  hasData,
}: {
  enabled: boolean;
  isLoading: boolean;
  isFetching?: boolean;
  isError: boolean;
  hasData: boolean;
}): StockEndpointEvidenceQueryState {
  if (isError) return "error";
  if (hasData) return "success";
  if (!enabled) return "idle";
  if (isLoading || isFetching) return "loading";
  return "idle";
}

function activeStrategyDiagnosticCount(payload: LivermoreStrategyPayload | null): number | null {
  if (!payload) return null;
  return payload.diagnostics.filter((item) => item.severity !== "info").length;
}

function activeDataGapCount(payload: LivermoreStrategyPayload | null): number | null {
  if (!payload) return null;
  return payload.data_gaps.filter((item) => item.status !== "ready").length;
}

function activeUnsupportedOutputCount(payload: LivermoreStrategyPayload | null): number | null {
  if (!payload) return null;
  return payload.unsupported_outputs.filter(isActionableLivermoreUnsupportedOutput).length;
}

function confluenceDiagnosticCount(payload: LivermoreSignalConfluencePayload | null): number | null {
  if (!payload) return null;
  return payload.diagnostics.filter(isActionableConfluenceDiagnostic).length;
}

function replayEvidenceMissingCount(payload: LivermoreSignalConfluencePayload | null): number | null {
  if (!payload?.replay_evidence) return payload ? 0 : null;
  return payload.replay_evidence.status === "available" ? 0 : 1;
}

function backtestWindowPendingDateCount(window: BacktestWindowSummary | null | undefined): number | null {
  if (!window) return null;
  return window.replay_dates_pending > 0 ? window.replay_dates_pending : 0;
}

function backtestWindowUnsupportedDateCount(window: BacktestWindowSummary | null | undefined): number | null {
  if (!window) return null;
  return window.replay_dates_unsupported > 0 ? window.replay_dates_unsupported : 0;
}

function pushFallbackReason(
  reasons: StockObservationClosureReasonInput[],
  {
    endpointId,
    endpointLabel,
    meta,
  }: {
    endpointId: string;
    endpointLabel: string;
    meta?: ResultMeta | null;
  },
) {
  const fallback = meta?.fallback_mode;
  if (!fallback || fallback === "none") return;
  reasons.push({
    key: `${endpointId}:fallback:${fallback}`,
    endpointId,
    endpointLabel,
    kind: "fallback",
    fieldPath: `${endpointId}.result_meta.fallback_mode`,
    displayText: `${endpointLabel}声明${stockSupplyFallbackLabel(fallback)}`,
    rawValueLabel: fallback,
  });
}

function confluenceDiagnosticText(item: LivermoreSignalConfluencePayload["diagnostics"][number]): string {
  if (typeof item === "string") return item;
  return item.message ?? item.code ?? "信号闭环诊断待复核";
}

function isActionableConfluenceDiagnostic(item: LivermoreSignalConfluencePayload["diagnostics"][number]): boolean {
  const message = confluenceDiagnosticText(item).trim().toLowerCase();
  if (!message) return false;
  if (message.includes("no stock candidates available for observation")) return false;
  if (
    message.includes("observation-only output") &&
    message.includes("does not generate trading instructions")
  ) {
    return false;
  }
  if (typeof item === "string") return true;
  return (item.severity ?? "warning") !== "info";
}

type WorkbenchQueries = ReturnType<typeof useStockAnalysisWorkbenchQueries>;
type SectorRankSeriesSupport = ReturnType<typeof useSectorRankSeriesSupport>;

type UseStockAnalysisEndpointEvidenceOptions = Pick<
  WorkbenchQueries,
  | "analyticsAsOf"
  | "cycleRotationFramework"
  | "formalUseAllowed"
  | "strategyQuery"
  | "strategyPayload"
  | "confluenceQuery"
  | "confluencePayload"
  | "strategyScoreQuery"
  | "strategyScorePayload"
  | "strategyPrioritySection"
  | "strategyBacktestQuery"
  | "strategyBacktestPayload"
  | "strategyBacktestWindow"
  | "strategyBacktestSnapshotFrom"
  | "strategyBacktestSection"
  | "strategyOptimizationQuery"
  | "strategyOptimizationPayload"
  | "strategyOptimizationSection"
  | "cycleProxyBacktestQuery"
  | "cycleProxyBacktestPayload"
  | "cycleFrameworkSection"
  | "candidateHistoryPortfolioBacktestQuery"
  | "candidateHistoryPortfolioBacktestPayload"
> &
  Pick<SectorRankSeriesSupport, "sectorRankSeriesQuery"> & {
    sectorSeriesExpanded: boolean;
    shouldLoadSectorSeriesFallback: boolean;
    firstScreenPriorityRequested: boolean;
    firstScreenOptimizationRequested: boolean;
    candidateHistoryEndpointRequested: boolean;
    cycleProxyEndpointRequested: boolean;
    portfolioProxyEndpointRequested: boolean;
  };

/**
 * 八个接口的证据台账与观察闭环归因：只读各查询的状态位、result_meta 与 payload，
 * 不发起任何请求；入参类型直接取自查询 hook 的返回值，避免页面与 hook 之间的类型漂移。
 */
export function useStockAnalysisEndpointEvidence({
  analyticsAsOf,
  cycleRotationFramework,
  formalUseAllowed,
  strategyQuery,
  strategyPayload,
  confluenceQuery,
  confluencePayload,
  sectorRankSeriesQuery,
  sectorSeriesExpanded,
  shouldLoadSectorSeriesFallback,
  strategyScoreQuery,
  strategyScorePayload,
  strategyPrioritySection,
  firstScreenPriorityRequested,
  strategyBacktestQuery,
  strategyBacktestPayload,
  strategyBacktestWindow,
  strategyBacktestSnapshotFrom,
  strategyBacktestSection,
  candidateHistoryEndpointRequested,
  strategyOptimizationQuery,
  strategyOptimizationPayload,
  strategyOptimizationSection,
  firstScreenOptimizationRequested,
  cycleProxyBacktestQuery,
  cycleProxyBacktestPayload,
  cycleFrameworkSection,
  cycleProxyEndpointRequested,
  candidateHistoryPortfolioBacktestQuery,
  candidateHistoryPortfolioBacktestPayload,
  portfolioProxyEndpointRequested,
}: UseStockAnalysisEndpointEvidenceOptions) {
  const endpointEvidenceItems = useMemo(() => {
    const sectorSeriesPayload = sectorRankSeriesQuery.data?.result ?? null;
    const strategyBacktestMissingInputCount =
      strategyBacktestWindow?.date_reasons.filter((item) => item.reason_code.startsWith("missing_")).length ?? null;

    return buildStockEndpointEvidenceItems([
      {
        key: "strategy",
        label: "主策略快照",
        queryState: endpointQueryState({
          enabled: true,
          isLoading: strategyQuery.isLoading,
          isFetching: strategyQuery.isFetching,
          isError: strategyQuery.isError,
          hasData: Boolean(strategyQuery.data),
        }),
        meta: strategyQuery.data?.result_meta,
        asOfDate: strategyPayload?.as_of_date,
        warningCount: activeStrategyDiagnosticCount(strategyPayload),
        unsupportedCount: activeUnsupportedOutputCount(strategyPayload),
        missingInputCount: activeDataGapCount(strategyPayload),
      },
      {
        key: "signal-confluence",
        label: "信号闭环",
        queryState: endpointQueryState({
          enabled: Boolean(strategyPayload?.as_of_date),
          isLoading: confluenceQuery.isLoading,
          isFetching: confluenceQuery.isFetching,
          isError: confluenceQuery.isError,
          hasData: Boolean(confluenceQuery.data),
        }),
        meta: confluenceQuery.data?.result_meta,
        asOfDate: confluencePayload?.as_of_date ?? strategyPayload?.as_of_date,
        warningCount: confluenceDiagnosticCount(confluencePayload),
        missingInputCount: replayEvidenceMissingCount(confluencePayload),
        unsupportedCount: 0,
      },
      {
        key: "sector-series",
        label: "板块支撑序列",
        queryState: endpointQueryState({
          enabled: Boolean((sectorSeriesExpanded || shouldLoadSectorSeriesFallback) && analyticsAsOf),
          isLoading: sectorRankSeriesQuery.isLoading,
          isFetching: sectorRankSeriesQuery.isFetching,
          isError: sectorRankSeriesQuery.isError,
          hasData: Boolean(sectorRankSeriesQuery.data),
        }),
        meta: sectorRankSeriesQuery.data?.result_meta,
        asOfDate: sectorSeriesPayload?.as_of_date ?? analyticsAsOf,
        warningCount: sectorSeriesPayload ? sectorSeriesPayload.unsupported_notes.length : null,
        missingInputCount: sectorSeriesPayload?.state === "missing" ? 1 : 0,
        unsupportedCount: 0,
      },
      {
        key: "strategy-score",
        label: "优先级评分",
        queryState: endpointQueryState({
          enabled: Boolean(analyticsAsOf && (strategyPrioritySection.seen || firstScreenPriorityRequested)),
          isLoading: strategyScoreQuery.isLoading,
          isFetching: strategyScoreQuery.isFetching,
          isError: strategyScoreQuery.isError,
          hasData: Boolean(strategyScoreQuery.data),
        }),
        meta: strategyScoreQuery.data?.result_meta,
        asOfDate: strategyScorePayload?.as_of_date ?? analyticsAsOf,
        snapshotFrom: strategyScorePayload?.snapshot_from,
        snapshotTo: strategyScorePayload?.snapshot_to,
        warningCount: strategyScorePayload
          ? strategyScorePayload.rows.filter((row) => row.sample_status !== "sufficient").length
          : null,
        missingInputCount: backtestWindowPendingDateCount(strategyScorePayload?.backtest_window_summary),
        unsupportedCount: backtestWindowUnsupportedDateCount(strategyScorePayload?.backtest_window_summary),
      },
      {
        key: "candidate-history",
        label: "策略回溯窗口",
        queryState: endpointQueryState({
          enabled: Boolean(
            analyticsAsOf && (strategyBacktestSection.seen || candidateHistoryEndpointRequested),
          ),
          isLoading: strategyBacktestQuery.isLoading,
          isFetching: strategyBacktestQuery.isFetching,
          isError: strategyBacktestQuery.isError,
          hasData: Boolean(strategyBacktestQuery.data),
        }),
        meta: strategyBacktestQuery.data?.result_meta,
        snapshotFrom: strategyBacktestPayload?.snapshot_from ?? strategyBacktestSnapshotFrom,
        snapshotTo: strategyBacktestPayload?.snapshot_to ?? analyticsAsOf,
        warningCount: backtestWindowPendingDateCount(strategyBacktestWindow),
        unsupportedCount: backtestWindowUnsupportedDateCount(strategyBacktestWindow),
        missingInputCount: strategyBacktestMissingInputCount,
      },
      {
        key: "strategy-optimization",
        label: "策略优化",
        queryState: endpointQueryState({
          enabled: Boolean(analyticsAsOf && (strategyOptimizationSection.seen || firstScreenOptimizationRequested)),
          isLoading: strategyOptimizationQuery.isLoading,
          isFetching: strategyOptimizationQuery.isFetching,
          isError: strategyOptimizationQuery.isError,
          hasData: Boolean(strategyOptimizationQuery.data),
        }),
        meta: strategyOptimizationQuery.data?.result_meta,
        asOfDate: strategyOptimizationPayload?.as_of_date ?? analyticsAsOf,
        snapshotFrom: strategyOptimizationPayload?.snapshot_from,
        snapshotTo: strategyOptimizationPayload?.snapshot_to,
        warningCount: strategyOptimizationPayload?.sample_maturity?.insufficient_count ?? null,
        missingInputCount: strategyOptimizationPayload?.pending_summary.pending_rows ?? null,
        unsupportedCount: backtestWindowUnsupportedDateCount(strategyOptimizationPayload?.backtest_window_summary),
      },
      {
        key: "cycle-proxy",
        label: "周期代理回溯",
        queryState: endpointQueryState({
          enabled: Boolean(
            analyticsAsOf &&
              cycleRotationFramework &&
              (cycleFrameworkSection.seen || cycleProxyEndpointRequested),
          ),
          isLoading: cycleProxyBacktestQuery.isLoading,
          isFetching: cycleProxyBacktestQuery.isFetching,
          isError: cycleProxyBacktestQuery.isError,
          hasData: Boolean(cycleProxyBacktestQuery.data),
        }),
        meta: cycleProxyBacktestQuery.data?.result_meta,
        snapshotFrom: cycleProxyBacktestPayload?.snapshot_from,
        snapshotTo: cycleProxyBacktestPayload?.snapshot_to ?? analyticsAsOf,
        warningCount: cycleProxyBacktestPayload?.warnings.length ?? null,
        missingInputCount: cycleProxyBacktestPayload?.missing_full_strategy_inputs.length ?? null,
        unsupportedCount: cycleProxyBacktestPayload?.status === "unsupported" ? 1 : 0,
      },
      {
        key: "portfolio-proxy",
        label: "组合代理回溯",
        queryState: endpointQueryState({
          enabled: Boolean(
            analyticsAsOf &&
              cycleRotationFramework &&
              (cycleFrameworkSection.seen || portfolioProxyEndpointRequested),
          ),
          isLoading: candidateHistoryPortfolioBacktestQuery.isLoading,
          isFetching: candidateHistoryPortfolioBacktestQuery.isFetching,
          isError: candidateHistoryPortfolioBacktestQuery.isError,
          hasData: Boolean(candidateHistoryPortfolioBacktestQuery.data),
        }),
        meta: candidateHistoryPortfolioBacktestQuery.data?.result_meta,
        snapshotFrom: candidateHistoryPortfolioBacktestPayload?.snapshot_from,
        snapshotTo: candidateHistoryPortfolioBacktestPayload?.snapshot_to ?? analyticsAsOf,
        warningCount: candidateHistoryPortfolioBacktestPayload?.warnings.length ?? null,
        missingInputCount: candidateHistoryPortfolioBacktestPayload?.missing_full_strategy_inputs.length ?? null,
        unsupportedCount: candidateHistoryPortfolioBacktestPayload?.status === "unsupported" ? 1 : 0,
      },
    ]);
  }, [
    analyticsAsOf,
    candidateHistoryPortfolioBacktestPayload,
    candidateHistoryPortfolioBacktestQuery.data,
    candidateHistoryPortfolioBacktestQuery.isError,
    candidateHistoryPortfolioBacktestQuery.isFetching,
    candidateHistoryPortfolioBacktestQuery.isLoading,
    candidateHistoryEndpointRequested,
    confluencePayload,
    confluenceQuery.data,
    confluenceQuery.isError,
    confluenceQuery.isFetching,
    confluenceQuery.isLoading,
    cycleFrameworkSection.seen,
    cycleProxyBacktestPayload,
    cycleProxyBacktestQuery.data,
    cycleProxyBacktestQuery.isError,
    cycleProxyBacktestQuery.isFetching,
    cycleProxyBacktestQuery.isLoading,
    cycleProxyEndpointRequested,
    cycleRotationFramework,
    firstScreenPriorityRequested,
    firstScreenOptimizationRequested,
    portfolioProxyEndpointRequested,
    sectorRankSeriesQuery.data,
    sectorRankSeriesQuery.isError,
    sectorRankSeriesQuery.isFetching,
    sectorRankSeriesQuery.isLoading,
    sectorSeriesExpanded,
    shouldLoadSectorSeriesFallback,
    strategyBacktestPayload,
    strategyBacktestQuery.data,
    strategyBacktestQuery.isError,
    strategyBacktestQuery.isFetching,
    strategyBacktestQuery.isLoading,
    strategyBacktestSection.seen,
    strategyBacktestSnapshotFrom,
    strategyBacktestWindow,
    strategyOptimizationPayload,
    strategyOptimizationQuery.data,
    strategyOptimizationQuery.isError,
    strategyOptimizationQuery.isFetching,
    strategyOptimizationQuery.isLoading,
    strategyOptimizationSection.seen,
    strategyPayload,
    strategyPrioritySection.seen,
    strategyQuery.data,
    strategyQuery.isError,
    strategyQuery.isFetching,
    strategyQuery.isLoading,
    strategyScorePayload,
    strategyScoreQuery.data,
    strategyScoreQuery.isError,
    strategyScoreQuery.isFetching,
    strategyScoreQuery.isLoading,
  ]);

  const observationClosureReasonInputs = useMemo(() => {
    const reasons: StockObservationClosureReasonInput[] = [];
    const addReason = (reason: StockObservationClosureReasonInput | null | undefined) => {
      if (reason) reasons.push(reason);
    };
    const addListReasons = ({
      endpointId,
      endpointLabel,
      kind,
      fieldRoot,
      values,
      textForValue,
    }: {
      endpointId: string;
      endpointLabel: string;
      kind: StockObservationClosureReasonInput["kind"];
      fieldRoot: string;
      values: unknown[] | null | undefined;
      textForValue: (value: unknown, index: number) => string;
    }) => {
      values?.forEach((value, index) => {
        addReason({
          key: `${endpointId}:${kind}:${fieldRoot}:${index}`,
          endpointId,
          endpointLabel,
          kind,
          fieldPath: `${fieldRoot}.${index}`,
          displayText: textForValue(value, index),
        });
      });
    };

    pushFallbackReason(reasons, {
      endpointId: "strategy",
      endpointLabel: "主策略快照",
      meta: strategyQuery.data?.result_meta,
    });
    pushFallbackReason(reasons, {
      endpointId: "signal-confluence",
      endpointLabel: "信号闭环",
      meta: confluenceQuery.data?.result_meta,
    });
    pushFallbackReason(reasons, {
      endpointId: "sector-series",
      endpointLabel: "板块支撑序列",
      meta: sectorRankSeriesQuery.data?.result_meta,
    });
    pushFallbackReason(reasons, {
      endpointId: "strategy-score",
      endpointLabel: "优先级评分",
      meta: strategyScoreQuery.data?.result_meta,
    });
    pushFallbackReason(reasons, {
      endpointId: "candidate-history",
      endpointLabel: "策略回溯窗口",
      meta: strategyBacktestQuery.data?.result_meta,
    });
    pushFallbackReason(reasons, {
      endpointId: "strategy-optimization",
      endpointLabel: "策略优化",
      meta: strategyOptimizationQuery.data?.result_meta,
    });
    pushFallbackReason(reasons, {
      endpointId: "cycle-proxy",
      endpointLabel: "周期代理回溯",
      meta: cycleProxyBacktestQuery.data?.result_meta,
    });
    pushFallbackReason(reasons, {
      endpointId: "portfolio-proxy",
      endpointLabel: "组合代理回溯",
      meta: candidateHistoryPortfolioBacktestQuery.data?.result_meta,
    });

    addListReasons({
      endpointId: "strategy",
      endpointLabel: "主策略快照",
      kind: "data-gap",
      fieldRoot: "main.result.data_gaps",
      values: strategyPayload?.data_gaps.filter((item) => item.status !== "ready"),
      textForValue: (value) => {
        const gap = value as NonNullable<LivermoreStrategyPayload["data_gaps"]>[number];
        return `${dataGapFamilyLabel(gap.input_family)}：${localizeStockBackendText(gap.evidence, gap.input_family)}`;
      },
    });
    addListReasons({
      endpointId: "strategy",
      endpointLabel: "主策略快照",
      kind: "diagnostic",
      fieldRoot: "main.result.diagnostics",
      values: strategyPayload?.diagnostics.filter((item) => item.severity !== "info"),
      textForValue: (value) => {
        const diagnostic = value as NonNullable<LivermoreStrategyPayload["diagnostics"]>[number];
        return localizeStockBackendText(diagnostic.message, diagnostic.input_family);
      },
    });
    addListReasons({
      endpointId: "strategy",
      endpointLabel: "主策略快照",
      kind: "unsupported",
      fieldRoot: "main.result.unsupported_outputs",
      values: strategyPayload?.unsupported_outputs.filter(isActionableLivermoreUnsupportedOutput),
      textForValue: (value) => {
        const output = value as NonNullable<LivermoreStrategyPayload["unsupported_outputs"]>[number];
        return `${dataGapFamilyLabel(output.key)}：${localizeStockBackendText(output.reason, output.key)}`;
      },
    });
    addListReasons({
      endpointId: "signal-confluence",
      endpointLabel: "信号闭环",
      kind: "diagnostic",
      fieldRoot: "signalConfluence.result.diagnostics",
      values: confluencePayload?.diagnostics.filter(isActionableConfluenceDiagnostic),
      textForValue: (value) =>
        localizeStockBackendText(
          confluenceDiagnosticText(value as LivermoreSignalConfluencePayload["diagnostics"][number]),
          "signal_confluence",
        ),
    });
    addListReasons({
      endpointId: "sector-series",
      endpointLabel: "板块支撑序列",
      kind: "unsupported",
      fieldRoot: "sectorRankSeries.result.unsupported_notes",
      values: sectorRankSeriesQuery.data?.result?.unsupported_notes,
      textForValue: (value) => localizeStockBackendText(String(value), "sector_rank"),
    });
    addListReasons({
      endpointId: "cycle-proxy",
      endpointLabel: "周期代理回溯",
      kind: "warning",
      fieldRoot: "cycleProxyBacktest.result.warnings",
      values: cycleProxyBacktestPayload?.warnings,
      textForValue: (value) => localizeStockBackendText(String(value), "cycle_proxy_backtest"),
    });
    addListReasons({
      endpointId: "cycle-proxy",
      endpointLabel: "周期代理回溯",
      kind: "missing-input",
      fieldRoot: "cycleProxyBacktest.result.missing_full_strategy_inputs",
      values: cycleProxyBacktestPayload?.missing_full_strategy_inputs,
      textForValue: (value) => `缺完整策略输入：${dataGapFamilyLabel(String(value))}`,
    });
    addListReasons({
      endpointId: "portfolio-proxy",
      endpointLabel: "组合代理回溯",
      kind: "warning",
      fieldRoot: "portfolioBacktest.result.warnings",
      values: candidateHistoryPortfolioBacktestPayload?.warnings,
      textForValue: (value) => localizeStockBackendText(String(value), "portfolio_proxy_backtest"),
    });
    addListReasons({
      endpointId: "portfolio-proxy",
      endpointLabel: "组合代理回溯",
      kind: "missing-input",
      fieldRoot: "portfolioBacktest.result.missing_full_strategy_inputs",
      values: candidateHistoryPortfolioBacktestPayload?.missing_full_strategy_inputs,
      textForValue: (value) => `缺完整策略输入：${dataGapFamilyLabel(String(value))}`,
    });
    if ((strategyOptimizationPayload?.pending_summary.pending_rows ?? 0) > 0) {
      addReason({
        key: "strategy-optimization:pending-summary",
        endpointId: "strategy-optimization",
        endpointLabel: "策略优化",
        kind: "missing-input",
        fieldPath: "strategyOptimization.result.pending_summary",
        displayText: `优化待处理 ${strategyOptimizationPayload?.pending_summary.pending_rows ?? 0} 行`,
      });
    }
    if ((strategyOptimizationPayload?.sample_maturity?.insufficient_count ?? 0) > 0) {
      addReason({
        key: "strategy-optimization:sample-maturity",
        endpointId: "strategy-optimization",
        endpointLabel: "策略优化",
        kind: "warning",
        fieldPath: "strategyOptimization.result.sample_maturity",
        displayText: `样本成熟度不足 ${strategyOptimizationPayload?.sample_maturity?.insufficient_count ?? 0} 项`,
      });
    }
    return reasons;
  }, [
    candidateHistoryPortfolioBacktestPayload,
    candidateHistoryPortfolioBacktestQuery.data?.result_meta,
    confluencePayload,
    confluenceQuery.data?.result_meta,
    cycleProxyBacktestPayload,
    cycleProxyBacktestQuery.data?.result_meta,
    sectorRankSeriesQuery.data?.result,
    sectorRankSeriesQuery.data?.result_meta,
    strategyBacktestQuery.data?.result_meta,
    strategyOptimizationPayload,
    strategyOptimizationQuery.data?.result_meta,
    strategyPayload,
    strategyQuery.data?.result_meta,
    strategyScoreQuery.data?.result_meta,
  ]);

  const observationClosureSummary = useMemo(
    () =>
      buildObservationClosureSummary({
        endpointItems: endpointEvidenceItems,
        reasonInputs: observationClosureReasonInputs,
        formalUseAllowed,
        approvalStatus: "gap_or_observational",
      }),
    [endpointEvidenceItems, formalUseAllowed, observationClosureReasonInputs],
  );

  return { endpointEvidenceItems, observationClosureSummary };
}
