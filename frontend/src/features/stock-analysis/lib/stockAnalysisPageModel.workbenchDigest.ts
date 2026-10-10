// Workbench data digest (first-screen fact ledger) for the stock-analysis page model.
import type {
  WorkbenchDataDigest,
  WorkbenchDataDigestInput,
  WorkbenchFact,
  WorkbenchFactTone,
  WorkbenchSlowState,
} from "./stockAnalysisPageModel.types";
import { localizeBasisLabel, localizeMarketDataStatus } from "./stockAnalysisPageModel.localize";
import { actionableDiagnostics, actionableUnsupportedOutputs, activeDataGaps } from "./stockAnalysisPageModel.shared";
import { sectorRankFormulaGovernanceLabel } from "./stockAnalysisPageModel.evidence";

function countArrayValue(value: unknown): number | null {
  return Array.isArray(value) ? value.length : null;
}

function countArrayOrRecordValue(value: unknown): number | null {
  if (Array.isArray(value)) return value.length;
  if (value != null && typeof value === "object") return Object.keys(value as Record<string, unknown>).length;
  return null;
}

function isWorkbenchPresent(value: unknown): boolean {
  if (value == null || value === "") return false;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "object") return Object.keys(value as Record<string, unknown>).length > 0;
  return true;
}

function digestCountLabel(value: number | null | undefined, unit = "项"): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "未返回";
  return `${value} ${unit}`;
}

function digestPlainCount(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "未返回";
  return String(value);
}

function countTone(value: number | null | undefined): WorkbenchFactTone {
  if (typeof value !== "number" || !Number.isFinite(value)) return "missing";
  return value > 0 ? "read" : "empty";
}

function presenceTone(isPresent: boolean, whenMissing: WorkbenchFactTone = "missing"): WorkbenchFactTone {
  return isPresent ? "read" : whenMissing;
}

function compactRangeLabel(from: string | null | undefined, to: string | null | undefined): string {
  if (from && to) return `${from} 至 ${to}`;
  if (to) return `截至 ${to}`;
  if (from) return `起始 ${from}`;
  return "窗口未返回";
}

function makeWorkbenchFact(fact: WorkbenchFact): WorkbenchFact {
  return fact;
}

function slowFactFromState({
  id,
  label,
  state,
  sourcePath,
  successValue,
  successSubValue,
  successTone,
}: {
  id: string;
  label: string;
  state: WorkbenchSlowState;
  sourcePath: string;
  successValue: string | null;
  successSubValue: string | null;
  successTone: WorkbenchFactTone;
}): WorkbenchFact {
  if (state === "error") {
    return makeWorkbenchFact({
      id,
      label,
      value: "读取失败",
      subValue: "接口读取失败，无法纳入本次复核台账",
      sourcePath,
      tone: "error",
    });
  }

  if (successValue != null) {
    return makeWorkbenchFact({
      id,
      label,
      value: successValue,
      subValue: successSubValue ?? undefined,
      sourcePath,
      tone: successTone,
    });
  }

  if (state === "slow") {
    return makeWorkbenchFact({
      id,
      label,
      value: "读取较慢",
      subValue: "读取时间较长，暂未纳入首屏摘要",
      sourcePath,
      tone: "slow",
    });
  }

  if (state === "loading") {
    return makeWorkbenchFact({
      id,
      label,
      value: "读取中",
      subValue: `${label}：正在读取历史证据，首屏不阻塞`,
      sourcePath,
      tone: "slow",
    });
  }

  return makeWorkbenchFact({
    id,
    label,
    value: "待触发",
    subValue: "展开复核区或首屏证据请求后读取",
    sourcePath,
    tone: "neutral",
  });
}

export function buildWorkbenchDataDigest({
  main,
  signalConfluence,
  candidateHistory,
  strategyScore,
  strategyOptimization,
  cycleProxyBacktest,
  portfolioBacktest,
  sectorRankSeries,
  candidateHistoryState = "idle",
  strategyScoreState = "idle",
}: WorkbenchDataDigestInput): WorkbenchDataDigest {
  const factorCandidateCount = countArrayValue(main?.factor_screen_candidates?.items);
  const hybridCandidateCount = countArrayValue(main?.hybrid_fusion_candidates?.items);
  const sectorRankCount = countArrayValue(main?.sector_rank?.items);
  const moduleStateCount = countArrayValue(main?.module_states);
  const ruleReadinessCount = countArrayValue(main?.rule_readiness);
  const dataGapCount = main ? activeDataGaps(main).length : null;
  const diagnosticCount = main ? actionableDiagnostics(main).length : null;
  const unsupportedCount = main ? actionableUnsupportedOutputs(main).length : null;
  const supportedCount = countArrayValue(main?.supported_outputs);
  const signalContextCount = signalConfluence
    ? [
        signalConfluence.macro_context,
        signalConfluence.adversarial_context,
        signalConfluence.strategy_context,
        signalConfluence.closed_loop_state,
      ].filter(isWorkbenchPresent).length
    : null;
  const entryObservationCount = countArrayValue(signalConfluence?.entry_observations);
  const exitObservationCount = countArrayValue(signalConfluence?.exit_observations);
  const replaySampleCount = countArrayValue(signalConfluence?.replay_evidence?.sample_items);
  const replayRowCount =
    typeof signalConfluence?.replay_evidence?.row_count === "number"
      ? signalConfluence.replay_evidence.row_count
      : null;
  const sectorSeriesCount = countArrayValue(sectorRankSeries?.series);
  const strategyOptimizationCount = countArrayValue(strategyOptimization?.strategy_summaries);
  const strategySliceCount = countArrayValue(strategyOptimization?.slices);
  const cycleNavCount = countArrayValue(cycleProxyBacktest?.nav_series);
  const portfolioNavCount = countArrayValue(portfolioBacktest?.nav_series);
  const rebalanceLogCount = countArrayValue(portfolioBacktest?.rebalance_log);
  const proxyWarningCount =
    (countArrayValue(cycleProxyBacktest?.warnings) ?? 0) + (countArrayValue(portfolioBacktest?.warnings) ?? 0);
  const missingInputCount =
    (countArrayValue(cycleProxyBacktest?.missing_full_strategy_inputs) ?? 0) +
    (countArrayValue(portfolioBacktest?.missing_full_strategy_inputs) ?? 0);
  const candidateHistoryItemCount = countArrayValue(candidateHistory?.items);
  const strategyScoreRowCount = countArrayValue(strategyScore?.rows);
  const strategyScoreCurrentRowCount = countArrayValue(strategyScore?.current_market_state_rows);
  const strategyScoreScopeCount = countArrayOrRecordValue(strategyScore?.stock_candidate_state_scopes);
  const openIssueCount = (dataGapCount ?? 0) + (diagnosticCount ?? 0) + (unsupportedCount ?? 0);

  const primaryFacts: WorkbenchFact[] = [
    makeWorkbenchFact({
      id: "data-date",
      label: "数据日期",
      value: main?.as_of_date ?? "未返回",
      subValue: main?.requested_as_of_date ? `请求 ${main.requested_as_of_date}` : "使用最新可用快照",
      sourcePath: "strategy.result.as_of_date",
      tone: main?.as_of_date ? "read" : "missing",
      isPrimary: true,
    }),
    makeWorkbenchFact({
      id: "strategy-basis",
      label: "策略口径",
      value: localizeBasisLabel(main?.basis),
      subValue: main?.strategy_name ? "趋势策略只读复核" : "策略名称未返回",
      sourcePath: "strategy.result.strategy_name",
      tone: main?.strategy_name ? "read" : "missing",
      isPrimary: true,
    }),
    makeWorkbenchFact({
      id: "candidate-depth",
      label: "候选厚度",
      value: `${digestPlainCount(factorCandidateCount)} / ${digestPlainCount(hybridCandidateCount)}`,
      subValue: "多因子 / 融合候选",
      sourcePath: "strategy.result.factor_screen_candidates.items + hybrid_fusion_candidates.items",
      tone:
        factorCandidateCount == null && hybridCandidateCount == null
          ? "missing"
          : (factorCandidateCount ?? 0) + (hybridCandidateCount ?? 0) > 0
            ? "read"
            : "empty",
      isPrimary: true,
    }),
    makeWorkbenchFact({
      id: "open-issues",
      label: "证据缺口",
      value: `${openIssueCount} 项`,
      subValue: `缺口 ${digestPlainCount(dataGapCount)} / 诊断 ${digestPlainCount(diagnosticCount)} / 未支持 ${digestPlainCount(unsupportedCount)}`,
      sourcePath: "strategy.result.data_gaps + diagnostics + unsupported_outputs",
      tone: openIssueCount > 0 ? "warning" : "read",
      isPrimary: true,
    }),
  ];

  const candidateFacts: WorkbenchFact[] = [
    makeWorkbenchFact({
      id: "factor-candidates",
      label: "多因子候选",
      value: digestCountLabel(factorCandidateCount, "只"),
      subValue: main?.factor_screen_candidates?.formula_version,
      sourcePath: "strategy.result.factor_screen_candidates.items",
      tone: countTone(factorCandidateCount),
    }),
    makeWorkbenchFact({
      id: "hybrid-candidates",
      label: "融合候选",
      value: digestCountLabel(hybridCandidateCount, "只"),
      subValue: main?.hybrid_fusion_candidates?.formula_version,
      sourcePath: "strategy.result.hybrid_fusion_candidates.items",
      tone: countTone(hybridCandidateCount),
    }),
    makeWorkbenchFact({
      id: "sector-rank",
      label: "行业排名",
      value: digestCountLabel(sectorRankCount, "个"),
      subValue: sectorRankFormulaGovernanceLabel(main?.sector_rank),
      sourcePath: "strategy.result.sector_rank.items",
      tone: countTone(sectorRankCount),
    }),
    makeWorkbenchFact({
      id: "module-states",
      label: "模块状态",
      value: digestCountLabel(moduleStateCount, "组"),
      subValue: `可输出 ${digestPlainCount(supportedCount)} / 规则 ${digestPlainCount(ruleReadinessCount)}`,
      sourcePath: "strategy.result.module_states",
      tone: countTone(moduleStateCount),
    }),
  ];

  const evidenceFacts: WorkbenchFact[] = [
    makeWorkbenchFact({
      id: "gate-readiness",
      label: "门控/规则",
      value: `${isWorkbenchPresent(main?.market_gate) ? "门控已返回" : "门控未返回"} / ${digestCountLabel(ruleReadinessCount, "条")}`,
      subValue: main?.market_gate?.state ? `市场状态 ${localizeMarketDataStatus(main.market_gate.state)}` : undefined,
      sourcePath: "strategy.result.market_gate + rule_readiness",
      tone: presenceTone(isWorkbenchPresent(main?.market_gate)),
    }),
    makeWorkbenchFact({
      id: "signal-context",
      label: "信号上下文",
      value: digestCountLabel(signalContextCount, "组"),
      subValue: `进入 ${digestPlainCount(entryObservationCount)} / 退出 ${digestPlainCount(exitObservationCount)}`,
      sourcePath: "signalConfluence.result.macro_context + strategy_context + closed_loop_state",
      tone: countTone(signalContextCount),
    }),
    makeWorkbenchFact({
      id: "replay-evidence",
      label: "回放证据",
      value: replayRowCount != null ? `${replayRowCount} 行` : digestCountLabel(replaySampleCount, "条样例"),
      subValue: replaySampleCount != null ? `首屏样例 ${replaySampleCount}` : "样例未返回",
      sourcePath: "signalConfluence.result.replay_evidence",
      tone: countTone(replayRowCount ?? replaySampleCount),
    }),
    makeWorkbenchFact({
      id: "sector-series",
      label: "行业序列",
      value: digestCountLabel(sectorSeriesCount, "条"),
      subValue: sectorRankSeries
        ? `top ${sectorRankSeries.top_k} / ${sectorRankSeries.window_days}日 / ${sectorRankSeries.formula_version}`
        : "序列未返回",
      sourcePath: "sectorRankSeries.result.series",
      tone: countTone(sectorSeriesCount),
    }),
    makeWorkbenchFact({
      id: "proxy-backtest",
      label: "代理回放",
      value: `${digestPlainCount(cycleNavCount)} / ${digestPlainCount(portfolioNavCount)}`,
      subValue: `周期 NAV / 组合 NAV；再平衡 ${digestPlainCount(rebalanceLogCount)}`,
      sourcePath: "cycleProxyBacktest.result.nav_series + portfolioBacktest.result.nav_series",
      tone:
        cycleNavCount == null && portfolioNavCount == null
          ? "missing"
          : (cycleNavCount ?? 0) + (portfolioNavCount ?? 0) > 0
            ? "read"
            : "empty",
    }),
    makeWorkbenchFact({
      id: "proxy-warnings",
      label: "代理边界",
      value: `${proxyWarningCount + missingInputCount} 项`,
      subValue: `提示 ${proxyWarningCount} / 缺输入 ${missingInputCount}`,
      sourcePath: "cycleProxyBacktest.result.warnings + portfolioBacktest.result.missing_full_strategy_inputs",
      tone: proxyWarningCount + missingInputCount > 0 ? "warning" : "read",
    }),
    makeWorkbenchFact({
      id: "optimization-depth",
      label: "优化诊断",
      value: `${digestPlainCount(strategyOptimizationCount)} / ${digestPlainCount(strategySliceCount)}`,
      subValue: "策略摘要 / 切片",
      sourcePath: "strategyOptimization.result.strategy_summaries + slices",
      tone:
        strategyOptimizationCount == null && strategySliceCount == null
          ? "missing"
          : (strategyOptimizationCount ?? 0) + (strategySliceCount ?? 0) > 0
            ? "read"
            : "empty",
    }),
  ];

  const slowFacts: WorkbenchFact[] = [
    slowFactFromState({
      id: "candidate-history",
      label: "候选历史",
      state: candidateHistoryState,
      sourcePath: "candidateHistory.result.items",
      successValue: candidateHistory ? digestCountLabel(candidateHistoryItemCount, "行") : null,
      successSubValue: candidateHistory
        ? `${compactRangeLabel(candidateHistory.snapshot_from, candidateHistory.snapshot_to)}；summary ${
            candidateHistory.summary ? "已返回" : "未返回"
          } / window ${candidateHistory.backtest_window_summary ? "已返回" : "未返回"}`
        : null,
      successTone: countTone(candidateHistoryItemCount),
    }),
    slowFactFromState({
      id: "strategy-score",
      label: "优先级评分",
      state: strategyScoreState,
      sourcePath: "strategyScore.result.rows",
      successValue: strategyScore ? `${digestPlainCount(strategyScoreRowCount)} / ${digestPlainCount(strategyScoreCurrentRowCount)}` : null,
      successSubValue: strategyScore
        ? `${compactRangeLabel(strategyScore.snapshot_from, strategyScore.snapshot_to)}；scope ${digestPlainCount(
            strategyScoreScopeCount,
          )} / min ${strategyScore.min_sample}`
        : null,
      successTone: countTone(strategyScoreRowCount),
    }),
  ];

  return {
    primaryFacts,
    candidateFacts,
    evidenceFacts,
    slowFacts,
  };
}
