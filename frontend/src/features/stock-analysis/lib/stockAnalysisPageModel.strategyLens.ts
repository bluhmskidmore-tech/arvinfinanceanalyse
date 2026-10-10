// Strategy lens (multi-strategy pool ledger) for the stock-analysis page model.
import type { LivermoreMarketGateState, LivermoreStrategyPayload } from "../../../api/contracts";
import type { ConsensusSummary } from "./buildConsensusSummary";
import type { StockStrategyLensItem, StockStrategyLensVerdict } from "./stockAnalysisPageModel.types";
import { formatNumber, formatRatioAsPercent } from "./stockAnalysisPageModel.format";
import { localizeMarketDataStatus, localizeStockBackendText } from "./stockAnalysisPageModel.localize";
import { isActionableLivermoreUnsupportedOutput, stockModuleStates, strategyWalkForwardBadge } from "./stockAnalysisPageModel.shared";
import { isStockModulePrimaryExcluded } from "./stockAnalysisPageModel.candidates";

function clampRatio(value: number | null | undefined): number | undefined {
  if (value == null || !Number.isFinite(value)) return undefined;
  return Math.min(1, Math.max(0, value));
}

function stockModulePrimaryReason(
  payload: LivermoreStrategyPayload,
  key: LivermoreStrategyPayload["supported_outputs"][number],
): string {
  const state = stockModuleStates(payload).find((item) => item.key === key);
  const firstReason = state?.reasons?.find((reason) => reason.trim().length > 0);
  return firstReason ? localizeStockBackendText(firstReason, key) : "证据模块仅作观察，不进入主复核。";
}

function meanReversionMarketActiveLabel(
  marketState: LivermoreMarketGateState,
  candidateCount: number,
): string {
  if (marketState !== "WARM") return "门控暂停";
  return candidateCount > 0 ? "条件触发" : "";
}

function compactStrategyLedgerText(value: string, maxLength = 38): string {
  const normalized = value.replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, maxLength)}…`;
}

function shortStrategyBlockerLabel(value: string): string {
  if (value.includes("物化输入覆盖不完整")) {
    return "物化输入覆盖不完整，详见证据账本。";
  }
  if (value.includes("持仓快照缺失")) {
    return "持仓快照缺失，暂不生成该输出。";
  }
  return compactStrategyLedgerText(value);
}

function shortStrategyCoverageLabel(
  text: string | null | undefined,
  inputFamily: string,
  fallback: string,
): string {
  if (!text?.trim()) return fallback;
  const localized = localizeStockBackendText(text, inputFamily);
  if (/hybrid fusion/i.test(text)) return fallback;
  const firstClause = localized.split(/[。；;]/)[0] || localized;
  return compactStrategyLedgerText(firstClause, 42);
}

function strategyCandidateCountLabel(count: number): string {
  return `${count} 只候选`;
}

function strategyBlockerLabel(state: StockStrategyLensItem["state"], statusDetail: string): string {
  if (state === "ready" || state === "empty") return "无阻断";
  return statusDetail || "阻断待确认";
}

function strategyFocusLabel(params: {
  label: string;
  state: StockStrategyLensItem["state"];
  candidates: StockStrategyLensItem["candidates"];
  fallback: string;
}): string {
  const top = params.candidates[0];
  if (top) {
    return `优先核验 ${top.stockName} ${top.stockCode}，再复核${params.label}证据边界。`;
  }
  if (params.state === "blocked" || params.state === "pending") {
    return `补齐${params.label}输入后复核。`;
  }
  if (params.state === "paused") {
    return `${params.label}受门控暂停，等待市场状态重新开放。`;
  }
  return params.fallback;
}

export function buildStrategyLensItems(
  payload: LivermoreStrategyPayload,
  _consensus: ConsensusSummary,
): StockStrategyLensItem[] {
  type StrategyOutputKey = LivermoreStrategyPayload["unsupported_outputs"][number]["key"];

  const unsupportedOutput = (key: StrategyOutputKey) => payload.unsupported_outputs.find((output) => output.key === key);
  const unsupportedReason = (key: StrategyOutputKey) => unsupportedOutput(key)?.reason;
  const localizedReason = (key: StrategyOutputKey) =>
    localizeStockBackendText(unsupportedReason(key), key);
  const shortReason = (key: StrategyOutputKey) => shortStrategyBlockerLabel(localizedReason(key));
  const outputState = (key: StrategyOutputKey, candidateCount: number, exists: boolean) => {
    const output = unsupportedOutput(key);
    const policyPaused = output ? !isActionableLivermoreUnsupportedOutput(output) : false;
    if (isStockModulePrimaryExcluded(payload, key)) {
      if (policyPaused) {
        return {
          state: "paused" as const,
          tone: "neutral" as const,
          statusLabel: "策略暂停",
          statusDetail: shortReason(key),
        };
      }
      return {
        state: "paused" as const,
        tone: "warning" as const,
        statusLabel: "证据区",
        statusDetail: stockModulePrimaryReason(payload, key),
      };
    }
    const reason = unsupportedReason(key);
    if (candidateCount > 0) {
      return {
        state: "ready" as const,
        tone: "positive" as const,
        statusLabel: "已返回",
        statusDetail: "已有候选，进入只读复核。",
      };
    }
    if (reason) {
      if (policyPaused) {
        return {
          state: "paused" as const,
          tone: "neutral" as const,
          statusLabel: "策略暂停",
          statusDetail: shortReason(key),
        };
      }
      return {
        state: "blocked" as const,
        tone: "warning" as const,
        statusLabel: "被阻断",
        statusDetail: shortReason(key),
      };
    }
    if (exists) {
      return {
        state: "empty" as const,
        tone: "neutral" as const,
        statusLabel: "0 候选",
        statusDetail: "策略已计算，本日没有命中标的。",
      };
    }
    return {
      state: "pending" as const,
      tone: "warning" as const,
      statusLabel: "待返回",
      statusDetail: "接口未返回该策略候选，请查看数据边界。",
    };
  };

  const stockPayload = payload.stock_candidates;
  const hybridPayload = payload.hybrid_fusion_candidates;
  const freshTrendPayload = payload.fresh_trend_watchlist;
  const factorPayload = payload.factor_screen_candidates;
  const meanReversionPayload = payload.mean_reversion_candidates;
  const strategyCandidateCounts = {
    hybrid: hybridPayload?.candidate_count ?? 0,
    livermore: stockPayload?.candidate_count ?? 0,
    fresh_trend: freshTrendPayload?.candidate_count ?? 0,
    factor: factorPayload?.candidate_count ?? 0,
    mean_reversion: meanReversionPayload?.candidate_count ?? 0,
  };
  const meanReversionBaseStatus = outputState(
    "mean_reversion_candidates",
    strategyCandidateCounts.mean_reversion,
    Boolean(meanReversionPayload),
  );
  const meanReversionGatePaused = payload.market_gate.state !== "WARM" && !meanReversionPayload;
  const meanReversionPausedDetail =
    meanReversionGatePaused && !/暂停|门控/.test(meanReversionBaseStatus.statusDetail)
      ? `${meanReversionBaseStatus.statusDetail}；门控暂停。`
      : meanReversionBaseStatus.statusDetail;
  const meanReversionStatus = unsupportedReason("mean_reversion_candidates")
    ? {
        ...meanReversionBaseStatus,
        statusDetail: meanReversionPausedDetail,
      }
    : meanReversionGatePaused
      ? {
          state: "paused" as const,
          tone: "neutral" as const,
          statusLabel: "门控暂停",
          statusDetail: `当前市场门控为${localizeMarketDataStatus(payload.market_gate.state)}，超跌观察不触发。`,
        }
      : meanReversionBaseStatus;
  const strategyStatuses = {
    hybrid: outputState("hybrid_fusion", strategyCandidateCounts.hybrid, Boolean(hybridPayload)),
    livermore: outputState("stock_candidates", strategyCandidateCounts.livermore, Boolean(stockPayload)),
    fresh_trend: outputState("fresh_trend_watchlist", strategyCandidateCounts.fresh_trend, Boolean(freshTrendPayload)),
    factor: outputState("factor_screen_candidates", strategyCandidateCounts.factor, Boolean(factorPayload)),
    mean_reversion: meanReversionStatus,
  };
  const strategyMax = Math.max(
    1,
    strategyCandidateCounts.hybrid,
    strategyCandidateCounts.livermore,
    strategyCandidateCounts.fresh_trend,
    strategyCandidateCounts.factor,
    strategyCandidateCounts.mean_reversion,
  );
  const hybridCandidates =
    hybridPayload?.items.slice(0, 3).map((item) => ({
      key: item.stock_code,
      rankLabel: `#${item.rank}`,
      stockCode: item.stock_code,
      stockName: item.stock_name,
      sectorName: item.sector_name,
      metricLabel: `融合分 ${formatNumber(item.fusion_score, 3)}`,
    })) ?? [];
  const livermoreCandidates =
    stockPayload?.items.slice(0, 3).map((item) => ({
      key: item.stock_code,
      rankLabel: `#${item.rank}`,
      stockCode: item.stock_code,
      stockName: item.stock_name,
      sectorName: item.sector_name,
      metricLabel: `收盘强度 ${formatRatioAsPercent(item.close_strength, 0)}`,
    })) ?? [];
  const factorCandidates =
    factorPayload?.items.slice(0, 3).map((item) => ({
      key: item.stock_code,
      rankLabel: `#${item.rank}`,
      stockCode: item.stock_code,
      stockName: item.stock_name,
      sectorName: item.sector_name || item.industry,
      metricLabel: `因子分 ${formatNumber(item.score, 3)}`,
    })) ?? [];
  const freshTrendCandidates =
    freshTrendPayload?.items.slice(0, 3).map((item) => ({
      key: item.stock_code,
      rankLabel: `#${item.rank}`,
      stockCode: item.stock_code,
      stockName: item.stock_name,
      sectorName: item.sector_name,
      metricLabel: `20日动量 ${formatRatioAsPercent(item.return_20d, 1)}`,
    })) ?? [];
  const meanReversionCandidates =
    meanReversionPayload?.items.slice(0, 3).map((item) => ({
      key: item.stock_code,
      rankLabel: `#${item.rank}`,
      stockCode: item.stock_code,
      stockName: item.stock_name,
      sectorName: item.sector_name,
      metricLabel: `20日回撤 ${formatRatioAsPercent(item.drawdown_20d, 1)}`,
    })) ?? [];
  const hybridDetail = hybridPayload?.coverage_note
    ? shortStrategyCoverageLabel(hybridPayload.coverage_note, "hybrid_fusion", "周期/价格/拥挤度合成，仅观察输出")
    : hybridPayload?.observation_only
      ? "只读观察候选"
      : strategyStatuses.hybrid.statusDetail;
  const livermoreDetail = stockPayload?.selection_policy
    ? localizeStockBackendText(stockPayload.selection_policy, "stock_candidates")
    : strategyStatuses.livermore.state === "blocked"
      ? "价格趋势输入未完整落地"
      : strategyStatuses.livermore.statusDetail;
  const factorDetail = factorPayload?.coverage_note
    ? shortStrategyCoverageLabel(factorPayload.coverage_note, "factor_screen_candidates", "因子覆盖已返回")
    : strategyStatuses.factor.statusDetail;
  const freshTrendDetail = freshTrendPayload?.observation_only
    ? "只读观察池，补充过热门控下的新趋势复核。"
    : strategyStatuses.fresh_trend.statusDetail;
  const meanReversionDetail =
    strategyStatuses.mean_reversion.state === "blocked"
      ? strategyStatuses.mean_reversion.statusDetail
      : meanReversionMarketActiveLabel(payload.market_gate.state, strategyCandidateCounts.mean_reversion) ||
        strategyStatuses.mean_reversion.statusDetail;

  return [
    {
      key: "hybrid",
      label: "融合策略",
      subtitle: "多策略合成",
      value: String(strategyCandidateCounts.hybrid),
      unitLabel: "候选",
      detail: hybridDetail,
      tone: strategyStatuses.hybrid.tone,
      state: strategyStatuses.hybrid.state,
      statusLabel: strategyStatuses.hybrid.statusLabel,
      statusDetail: strategyStatuses.hybrid.statusDetail,
      blockerLabel: strategyBlockerLabel(strategyStatuses.hybrid.state, strategyStatuses.hybrid.statusDetail),
      focusLabel: strategyFocusLabel({
        label: "融合策略",
        state: strategyStatuses.hybrid.state,
        candidates: hybridCandidates,
        fallback: "复核周期、趋势、拥挤度证据是否同向。",
      }),
      actionLabel: "查看复核队列",
      candidateCountLabel: strategyCandidateCountLabel(strategyCandidateCounts.hybrid),
      dateLabel: hybridPayload?.as_of_date ?? payload.as_of_date ?? "日期待补",
      formulaLabel: hybridPayload?.formula_version ?? "公式待补",
      evidence: [
        { key: "gate", label: "门控", value: localizeMarketDataStatus(hybridPayload?.market_state ?? payload.market_gate.state) },
        { key: "mode", label: "口径", value: hybridPayload?.observation_only ? "只读观察" : "复核候选" },
        { key: "count", label: "候选", value: hybridPayload ? `${hybridPayload.candidate_count} 只` : "待补" },
      ],
      candidates: hybridCandidates,
      verdict: strategyWalkForwardBadge(hybridPayload?.walk_forward),
      scrollTarget: "stock-analysis-review-queue",
      progress: clampRatio(strategyCandidateCounts.hybrid / strategyMax),
    },
    {
      key: "livermore",
      label: "趋势突破",
      subtitle: "价格趋势",
      value: String(strategyCandidateCounts.livermore),
      unitLabel: "候选",
      detail: livermoreDetail,
      tone: strategyStatuses.livermore.tone,
      state: strategyStatuses.livermore.state,
      statusLabel: strategyStatuses.livermore.statusLabel,
      statusDetail: strategyStatuses.livermore.statusDetail,
      blockerLabel: strategyBlockerLabel(strategyStatuses.livermore.state, strategyStatuses.livermore.statusDetail),
      focusLabel: strategyFocusLabel({
        label: "趋势突破",
        state: strategyStatuses.livermore.state,
        candidates: livermoreCandidates,
        fallback: "复核均线结构、观察位与行业强度是否一致。",
      }),
      actionLabel: "查看复核队列",
      candidateCountLabel: strategyCandidateCountLabel(strategyCandidateCounts.livermore),
      dateLabel: stockPayload?.as_of_date ?? payload.as_of_date ?? "日期待补",
      formulaLabel: stockPayload?.formula_version ?? "公式待补",
      evidence: [
        { key: "input", label: "输入", value: stockPayload ? `${stockPayload.input_stock_count} 只` : "待补" },
        { key: "excluded", label: "剔除", value: stockPayload ? `${stockPayload.excluded_stock_count} 只` : "待补" },
        { key: "history", label: "历史不足", value: stockPayload ? `${stockPayload.insufficient_history_count} 只` : "待补" },
        // Only disclosed when the backend returns fundamental_overlay (older payloads omit it entirely).
        ...(typeof stockPayload?.fundamental_overlay?.factor_missing_count === "number"
          ? [{ key: "factor_missing", label: "缺因子", value: `${stockPayload.fundamental_overlay.factor_missing_count} 只` }]
          : []),
      ],
      candidates: livermoreCandidates,
      verdict: strategyWalkForwardBadge(stockPayload?.walk_forward),
      scrollTarget: "stock-analysis-review-queue",
      progress: clampRatio(strategyCandidateCounts.livermore / strategyMax),
    },
    {
      key: "fresh_trend",
      label: "新趋势观察",
      subtitle: "成长观察",
      value: String(strategyCandidateCounts.fresh_trend),
      unitLabel: "候选",
      detail: freshTrendDetail,
      tone: strategyStatuses.fresh_trend.tone,
      state: strategyStatuses.fresh_trend.state,
      statusLabel: strategyStatuses.fresh_trend.statusLabel,
      statusDetail: strategyStatuses.fresh_trend.statusDetail,
      blockerLabel: strategyBlockerLabel(strategyStatuses.fresh_trend.state, strategyStatuses.fresh_trend.statusDetail),
      focusLabel: strategyFocusLabel({
        label: "新趋势观察",
        state: strategyStatuses.fresh_trend.state,
        candidates: freshTrendCandidates,
        fallback: "复核成长板、均线结构、量能和题材线索是否同向。",
      }),
      actionLabel: "查看观察池",
      candidateCountLabel: strategyCandidateCountLabel(strategyCandidateCounts.fresh_trend),
      dateLabel: freshTrendPayload?.as_of_date ?? payload.as_of_date ?? "日期待补",
      formulaLabel: freshTrendPayload?.formula_version ?? "公式待补",
      evidence: [
        { key: "input", label: "输入", value: freshTrendPayload ? `${freshTrendPayload.input_stock_count} 只` : "待补" },
        { key: "gate", label: "门控", value: localizeMarketDataStatus(freshTrendPayload?.market_state ?? payload.market_gate.state) },
        { key: "mode", label: "口径", value: freshTrendPayload?.observation_only ? "只读观察" : "复核候选" },
      ],
      candidates: freshTrendCandidates,
      verdict: strategyWalkForwardBadge(freshTrendPayload?.walk_forward),
      scrollTarget: "stock-analysis-review-queue",
      progress: clampRatio(strategyCandidateCounts.fresh_trend / strategyMax),
    },
    {
      key: "factor",
      label: "多因子",
      subtitle: "价值质量动量",
      value: String(strategyCandidateCounts.factor),
      unitLabel: "候选",
      detail: factorDetail,
      tone: strategyStatuses.factor.tone,
      state: strategyStatuses.factor.state,
      statusLabel: strategyStatuses.factor.statusLabel,
      statusDetail: strategyStatuses.factor.statusDetail,
      blockerLabel: strategyBlockerLabel(strategyStatuses.factor.state, strategyStatuses.factor.statusDetail),
      focusLabel: strategyFocusLabel({
        label: "多因子",
        state: strategyStatuses.factor.state,
        candidates: factorCandidates,
        fallback: "复核因子覆盖、估值质量与动量分位。",
      }),
      actionLabel: "查看观察池",
      candidateCountLabel: strategyCandidateCountLabel(strategyCandidateCounts.factor),
      dateLabel: factorPayload?.factor_snapshot_as_of_date ?? factorPayload?.as_of_date ?? payload.as_of_date ?? "日期待补",
      formulaLabel: factorPayload?.formula_version ?? "公式待补",
      evidence: [
        { key: "input", label: "输入", value: factorPayload ? `${factorPayload.input_stock_count} 只` : "待补" },
        { key: "gate", label: "门控", value: localizeMarketDataStatus(factorPayload?.market_state ?? payload.market_gate.state) },
        { key: "mode", label: "口径", value: factorPayload?.observation_only ? "只读观察" : "复核候选" },
      ],
      candidates: factorCandidates,
      verdict: strategyWalkForwardBadge(factorPayload?.walk_forward),
      scrollTarget: "stock-analysis-observation-preview",
      progress: clampRatio(strategyCandidateCounts.factor / strategyMax),
    },
    {
      key: "mean_reversion",
      label: "超跌反弹",
      subtitle: "回撤修复",
      value: String(strategyCandidateCounts.mean_reversion),
      unitLabel: "候选",
      detail: meanReversionDetail,
      tone: strategyStatuses.mean_reversion.tone,
      state: strategyStatuses.mean_reversion.state,
      statusLabel: strategyStatuses.mean_reversion.statusLabel,
      statusDetail: strategyStatuses.mean_reversion.statusDetail,
      blockerLabel: strategyBlockerLabel(
        strategyStatuses.mean_reversion.state,
        strategyStatuses.mean_reversion.statusDetail,
      ),
      focusLabel: strategyFocusLabel({
        label: "超跌反弹",
        state: strategyStatuses.mean_reversion.state,
        candidates: meanReversionCandidates,
        fallback: "复核回撤深度、均线距离与市场门控。",
      }),
      actionLabel: "查看观察池",
      candidateCountLabel: strategyCandidateCountLabel(strategyCandidateCounts.mean_reversion),
      dateLabel: meanReversionPayload?.as_of_date ?? payload.as_of_date ?? "日期待补",
      formulaLabel: meanReversionPayload?.formula_version ?? "公式待补",
      evidence: [
        { key: "input", label: "输入", value: meanReversionPayload ? `${meanReversionPayload.input_stock_count} 只` : "待补" },
        { key: "gate", label: "门控", value: localizeMarketDataStatus(meanReversionPayload?.market_state ?? payload.market_gate.state) },
        { key: "history", label: "历史不足", value: meanReversionPayload ? `${meanReversionPayload.insufficient_history_count} 只` : "待补" },
      ],
      candidates: meanReversionCandidates,
      verdict: strategyWalkForwardBadge(meanReversionPayload?.walk_forward),
      scrollTarget: "stock-analysis-observation-preview",
      progress: clampRatio(strategyCandidateCounts.mean_reversion / strategyMax),
    },
  ].sort(compareStrategyLensByVerdict);
}

/** 样本外支持 > 未检验/无判定 > 样本外削弱；同档保持原有池顺序（稳定排序）。 */
const WALK_FORWARD_SORT_WEIGHT: Record<StockStrategyLensVerdict["key"], number> = {
  supported: 0,
  not_assessable: 1,
  weakened: 2,
};

function strategyLensVerdictWeight(item: StockStrategyLensItem): number {
  // 老响应无 walk_forward 字段时与"未检验"同档，不因缺字段被降到削弱池之后。
  return item.verdict ? WALK_FORWARD_SORT_WEIGHT[item.verdict.key] : 1;
}

function compareStrategyLensByVerdict(
  left: StockStrategyLensItem,
  right: StockStrategyLensItem,
): number {
  return strategyLensVerdictWeight(left) - strategyLensVerdictWeight(right);
}
