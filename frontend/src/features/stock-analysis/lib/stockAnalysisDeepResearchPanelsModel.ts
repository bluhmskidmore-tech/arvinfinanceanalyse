import type {
  BacktestWindowSummary,
  LivermoreCandidateHistoryHorizonStats,
  LivermoreCandidateHistoryPayload,
  LivermoreCandidateHistoryPortfolioBacktestPayload,
  LivermoreCycleProxyBacktestPayload,
  LivermoreStrategyOptimizationPayload,
  LivermoreStrategyPayload,
  LivermoreStrategyScorePayload,
  LivermoreThemeBreakoutReviewItem,
  LivermoreThemeEvidenceInputState,
  LivermoreThemeBreakoutItem,
} from "../../../api/contracts";
import type { ConsensusSummary } from "./buildConsensusSummary";
import {
  backtestPendingDateCount,
  backtestSourceGapDateCount,
  backtestUnsupportedDateCount,
  resolveStrategyBacktestMetricBasisLabel,
} from "./stockAnalysisBacktestModel";
import {
  finiteCount,
  formatNumber,
  formatPercent,
  formatRatioAsPercent,
  localizeImplementationStage,
  localizeMarketDataStatus,
  localizeStockBackendText,
  localizeStockDataFamily,
  localizeStrategyPanelErrorDetail,
  localizeThemeSourceKind,
  type StockAnalysisEventMonitorRow,
  type StockClosedLoopTone,
  type StockCycleMacroLayerSummary,
  type StockDeepAnalysisGateSummary,
  type StockDeepZoneAuditRow,
  type StockStrategyPanelMiniStat,
  type StockStrategyPanelQueryState,
  type StockStrategyPanelResultSummary,
  type StockThemeBreakoutCard,
  type StockThemeBreakoutLeader,
  type StockThemeBreakoutReviewItem,
  type StockThemeEvidenceStateRow,
  type StockThemeLeaderPreviewItem,
} from "./stockAnalysisPageModel";

function sortedThemeBreakoutItems(payload: LivermoreStrategyPayload): LivermoreThemeBreakoutItem[] {
  return [...(payload.theme_breakout?.items ?? [])].sort((left, right) => left.rank - right.rank);
}
function localizeStockStrategyLabel(
  strategyLabel: string | null | undefined,
  signalKind: string | null | undefined,
): string {
  const label = strategyLabel?.trim();
  const normalizedLabel = label?.toLowerCase().replace(/[\s-]+/g, "_");
  const signalLabel = localizeStockDataFamily(signalKind);
  const fallbackLabel = signalLabel === "输入待确认" ? "策略待确认" : signalLabel;
  if (!label) return fallbackLabel;
  if (label === signalKind || normalizedLabel === signalKind?.trim().toLowerCase().replace(/[\s-]+/g, "_")) {
    return fallbackLabel;
  }
  const compactLabel = normalizedLabel?.replace(/_/g, "");
  if (
    normalizedLabel?.includes("external_vendor") ||
    normalizedLabel?.includes("vendor_") ||
    normalizedLabel?.includes("source_table") ||
    compactLabel?.includes("externalvendor") ||
    compactLabel?.includes("vendor") ||
    compactLabel?.includes("sourcetable") ||
    compactLabel?.includes("choicestock")
  ) {
    return fallbackLabel;
  }
  return label;
}

function strategyPrioritySummaryStatus(label: string | null | undefined): {
  label: string;
  badgeLabel: string;
  tone: StockClosedLoopTone;
} {
  const value = label?.trim();
  if (value === "优先复核") return { label: "优先复核", badgeLabel: "已就绪", tone: "positive" };
  if (value === "降权观察") return { label: "降权观察", badgeLabel: "降权观察", tone: "warning" };
  if (value === "继续观察") return { label: "继续观察", badgeLabel: "观察", tone: "neutral" };
  if (value === "样本不足") return { label: "样本不足", badgeLabel: "样本不足", tone: "warning" };
  return { label: "状态待确认", badgeLabel: "待确认", tone: "warning" };
}
export function buildThemeLeaderPreviewItems(
  cards: StockThemeBreakoutCard[],
  limit = 12,
): StockThemeLeaderPreviewItem[] {
  const items: StockThemeLeaderPreviewItem[] = [];
  for (const card of cards) {
    for (const leader of card.leaders) {
      items.push({
        stockCode: leader.stockCode,
        stockName: leader.stockName,
        themeName: card.themeName,
        themeRank: card.rank,
        pctChange: leader.pctChange,
        turn: leader.turn,
        closeStrength: leader.closeStrength,
        tags: leader.tags,
      });
      if (items.length >= limit) {
        return items;
      }
    }
  }
  return items;
}
function localizeThemeName(name: string | null | undefined): string {
  const value = name?.trim();
  if (!value) return "题材待补";
  const withoutTechnicalSuffix = value
    .replace(/\bproxy\b/gi, "")
    .replace(/\breview\b/gi, "")
    .replace(/\s{2,}/g, " ")
    .trim();
  const labels: Record<string, string> = {
    semiconductor: "半导体",
    electronic: "电子",
  };
  const normalized = withoutTechnicalSuffix.toLowerCase();
  return labels[normalized] ?? (withoutTechnicalSuffix || "题材待补");
}

function localizeThemeText(text: string | null | undefined): string {
  const value = text?.trim();
  if (!value) return "原因待补";
  const lower = value.toLowerCase();
  if (lower.includes("near-miss") && lower.includes("failed gates")) return "强势样本未过门槛，保留观察。";
  if (lower.includes("observation-only") && lower.includes("leaders")) return "强势样本进入观察。";
  if (lower.includes("review-only") && lower.includes("below gate")) return "强势样本未达门槛，保留复核。";
  return value.replace(/\bproxy\b/gi, "代理观察").replace(/_/g, " ");
}

function localizeThemeGateLabel(gate: string): string {
  const labels: Record<string, string> = {
    insufficient_cluster_strength: "簇强度不足",
  };
  return labels[gate] ?? "门槛待确认";
}

export function buildThemeBreakoutCards(payload: LivermoreStrategyPayload): StockThemeBreakoutCard[] {
  // Missing is_proxy must not default to "proxy" (would mislabel real themes).
  const isProxy = payload.theme_breakout?.is_proxy === true;
  return sortedThemeBreakoutItems(payload).map((item) => {
    const sourceKindLabel = localizeThemeSourceKind(item.source_kind, isProxy);
    const usesCurrentOverlay =
      item.source_kind?.trim().toLowerCase() === "tushare_current_overlay" ||
      item.items.some(
        (stock) => stock.concept_source_kind?.trim().toLowerCase() === "tushare_current_overlay",
      );
    const leaders = [...item.items]
      .sort((left, right) => {
        if (left.closed_up_limit !== right.closed_up_limit) {
          return left.closed_up_limit ? -1 : 1;
        }
        if (right.pctchange !== left.pctchange) return right.pctchange - left.pctchange;
        return right.turn - left.turn;
      })
      .slice(0, 5)
      .map((stock) => ({
        stockCode: stock.stock_code,
        stockName: stock.stock_name,
        pctChange: formatPercent(stock.pctchange),
        turn: formatNumber(stock.turn, 2),
        closeStrength: formatRatioAsPercent(stock.close_strength, 0),
        sourceKindLabel: localizeThemeSourceKind(
          stock.concept_source_kind ?? item.source_kind,
          isProxy,
        ),
        tags: [
          stock.closed_up_limit ? "涨停" : null,
          stock.strong ? "强势" : null,
        ].filter((tag): tag is string => Boolean(tag)),
      }));

    const boundaryLabel = usesCurrentOverlay
      ? "当前覆盖 · 非时点 · 不可历史使用 · 仅观察"
      : isProxy
        ? "代理题材观察：由日线、股票名称和申万一级行业拼接，不是概念库或盘中异动源。"
        : "真实题材观察：使用已落地概念成分和异动事件；仍只作复核观察。";
    const movementCount = item.movement_event_count ?? 0;
    const latestEventTitle = item.latest_event_title?.trim() || "暂无最新异动标题";
    const latestEventTime = item.latest_event_time?.trim() || "时间待补";

    return {
      rank: item.rank,
      themeKey: item.theme_key,
      themeName: localizeThemeName(item.theme_name),
      parentSectorLabel: `${localizeThemeName(item.parent_sector_name)} #${item.parent_sector_rank}`,
      summary: `${item.member_count} 只观察股，${item.strong_stock_count} 只强势，${item.limit_stock_count} 只涨停。`,
      reason: localizeThemeText(item.reason),
      boundaryLabel,
      strongCountLabel: `强势 ${item.strong_stock_count}`,
      limitCountLabel: `涨停 ${item.limit_stock_count}`,
      advanceRatioLabel: `上涨占比 ${formatRatioAsPercent(item.advance_ratio, 0)}`,
      avgPctChangeLabel: `均涨跌 ${formatPercent(item.avg_pctchange)}`,
      movementLabel: `异动 ${movementCount}`,
      latestEventLabel: movementCount > 0 ? `${latestEventTime} / ${latestEventTitle}` : "异动事件待补",
      sourceKindLabel,
      leaders,
    };
  });
}

const themeEvidenceInputLabels: Record<string, string> = {
  choice_stock_intraday_movement_event: "盘中异动",
  concept_membership: "概念成分",
  intraday_movement: "盘中异动",
};

const themeEvidenceStatusLabels: Record<string, string> = {
  catalog_unconfirmed: "目录待确认",
  table_missing: "数据源缺失",
  source_table_missing: "数据源缺失",
  landed_no_rows: "已接入无行",
  matched_rows: "已匹配",
  current_overlay: "当前覆盖 · 非时点 · 不可历史使用 · 仅观察",
};

function localizeThemeEvidenceDetail(row: LivermoreThemeEvidenceInputState, inputFamily: string, status: string): string {
  const label = themeEvidenceInputLabels[inputFamily] ?? "题材输入";
  const statusLabel = themeEvidenceStatusLabels[status] ?? "状态待确认";
  const message = row.message?.trim().toLowerCase() ?? "";
  if (message.includes("concept membership") || status === "catalog_unconfirmed") {
    return `${label}：${statusLabel}`;
  }
  if (message.includes("intraday movement") || status === "table_missing") {
    return `${label}：${statusLabel}`;
  }
  return `${label}：${statusLabel}`;
}

function themeEvidenceInputs(payload: LivermoreStrategyPayload): LivermoreThemeEvidenceInputState[] {
  const state = payload.theme_breakout?.evidence_state;
  if (state == null) return [];

  const rows: LivermoreThemeEvidenceInputState[] = [];
  if (state.concept_membership != null) {
    rows.push({
      ...state.concept_membership,
      input_family: state.concept_membership.input_family || "concept_membership",
    });
  }
  if (state.intraday_movement != null) {
    rows.push({
      ...state.intraday_movement,
      input_family: state.intraday_movement.input_family || "intraday_movement",
    });
  }

  const seen = new Set(rows.map((row) => row.input_family));
  for (const row of state.inputs ?? []) {
    const inputFamily = row.input_family ?? "theme_input";
    if (!seen.has(inputFamily)) {
      rows.push(row);
      seen.add(inputFamily);
    }
  }
  return rows;
}

export function buildThemeEvidenceStateRows(payload: LivermoreStrategyPayload): StockThemeEvidenceStateRow[] {
  return themeEvidenceInputs(payload).map((row, index) => {
    const inputFamily = row.input_family ?? `theme_input_${index + 1}`;
    const memberCount = finiteCount(row.member_count);
    const rowCount = finiteCount(row.row_count ?? row.date_row_count);
    const matchedCount = finiteCount(row.matched_row_count);
    const status = String(row.status ?? row.state ?? "unknown");
    return {
      key: inputFamily,
      label: themeEvidenceInputLabels[inputFamily] ?? "题材输入",
      status,
      statusLabel: themeEvidenceStatusLabels[status] ?? "状态待确认",
      detail: localizeThemeEvidenceDetail(row, inputFamily, status),
      rowCountLabel:
        status === "current_overlay"
          ? `成分 ${memberCount} / 命中 ${matchedCount}`
          : `行 ${rowCount} / 命中 ${matchedCount}`,
    };
  });
}

function themeReviewLeaders(item: LivermoreThemeBreakoutReviewItem): StockThemeBreakoutLeader[] {
  return [...(item.items ?? [])]
    .sort((left, right) => {
      if (left.closed_up_limit !== right.closed_up_limit) {
        return left.closed_up_limit ? -1 : 1;
      }
      if (right.pctchange !== left.pctchange) return right.pctchange - left.pctchange;
      return right.turn - left.turn;
    })
    .slice(0, 5)
    .map((stock) => ({
      stockCode: stock.stock_code,
      stockName: stock.stock_name,
      pctChange: formatPercent(stock.pctchange),
      turn: formatNumber(stock.turn, 2),
      closeStrength: formatRatioAsPercent(stock.close_strength, 0),
      sourceKindLabel: localizeThemeSourceKind(stock.concept_source_kind ?? item.source_kind, false),
      tags: [
        stock.closed_up_limit ? "涨停" : null,
        stock.strong ? "强势" : null,
      ].filter((tag): tag is string => Boolean(tag)),
    }));
}

export function buildThemeBreakoutReviewItems(payload: LivermoreStrategyPayload): StockThemeBreakoutReviewItem[] {
  return [...(payload.theme_breakout?.review_items ?? [])]
    .sort((left, right) => (left.rank ?? 9999) - (right.rank ?? 9999))
    .map((item, index) => {
      const failedGates = item.failed_gates ?? item.failed_gate_codes ?? [];
      return {
        rank: item.rank ?? index + 1,
        themeKey: item.theme_key,
        themeName: localizeThemeName(item.theme_name),
        sourceKindLabel: localizeThemeSourceKind(
          item.source_kind,
          payload.theme_breakout?.is_proxy === true,
        ),
        parentSectorLabel: `${localizeThemeName(item.parent_sector_name)} #${item.parent_sector_rank}`,
        summary: `${item.member_count} 只复核样本，${item.strong_stock_count} 只强势，${
          item.limit_stock_count
        } 只涨停，均涨跌 ${formatPercent(item.avg_pctchange)}`,
        failedGateLabel:
          failedGates.length > 0 ? `未过门槛：${failedGates.map(localizeThemeGateLabel).join("、")}` : "门槛待确认",
        reason: localizeThemeText(item.reason),
        leaders: themeReviewLeaders(item),
      };
    });
}
function localizeThemeUnsupportedSummary(reason: string): { detail: string; gateHint?: string } {
  const text = reason.trim();
  const lower = text.toLowerCase();
  if (lower.includes("overheat")) {
    return {
      detail: "市场过热门控下暂停题材执行观察；历史回放显示该桶拖累。",
      gateHint: "OVERHEAT",
    };
  }
  if (lower.includes("no_data") || lower.includes("not landed") || lower.includes("missing")) {
    return {
      detail: "题材输入未落地或门控未开放，暂不出执行结论。",
    };
  }
  if (text.length <= 48) {
    return { detail: text };
  }
  return {
    detail: "门控或数据限制导致暂未产出题材结论，展开查看英文原文。",
  };
}

function formatBacktestRate(value: number | null | undefined, digits = 1): string {
  if (value == null || !Number.isFinite(value)) {
    return "待补";
  }
  return `${(value * 100).toFixed(digits)}%`;
}

function formatBacktestSignedReturn(value: number | null | undefined, digits = 1): string {
  if (value == null || !Number.isFinite(value)) {
    return "待补";
  }
  const pct = value * 100;
  const prefix = pct > 0 ? "+" : "";
  return `${prefix}${pct.toFixed(digits)}%`;
}

function formatBacktestHorizonStatsText(stats: LivermoreCandidateHistoryHorizonStats | undefined): string {
  if (!stats || stats.available_count <= 0) {
    return "样本待补";
  }
  return `胜率 ${formatBacktestRate(stats.win_rate)} / 均收益 ${formatBacktestSignedReturn(stats.avg_return)} / ${stats.available_count}条`;
}

function strategyHorizonShortLabel(horizon: LivermoreStrategyScorePayload["primary_horizon"] | null | undefined): string {
  if (horizon === "return_1d") return "T+1";
  if (horizon === "return_10d") return "T+10";
  if (horizon === "return_20d") return "T+20";
  return "T+5";
}

function pickTopPriorityRow(
  rows: LivermoreStrategyScorePayload["rows"],
): LivermoreStrategyScorePayload["rows"][number] | null {
  const ranked = rows
    .filter((row) => row.priority_score != null && Number.isFinite(row.priority_score))
    .sort((left, right) => (right.priority_score ?? 0) - (left.priority_score ?? 0));
  return ranked[0] ?? rows[0] ?? null;
}

function summarizeThemeMovementCount(payload: LivermoreStrategyPayload): number {
  return (payload.theme_breakout?.items ?? []).reduce(
    (sum, item) => sum + (item.movement_event_count ?? 0),
    0,
  );
}

export function buildDeepAnalysisGateSummary(input: {
  gateState: string | null | undefined;
  themeUnsupportedReason?: string;
  priorityStrategyLabel?: string | null;
}): StockDeepAnalysisGateSummary {
  const gateLabel = input.gateState ? localizeMarketDataStatus(input.gateState) : "门控待补";
  const parts = [`当前市场门控：${gateLabel}`];
  let tone: StockClosedLoopTone = "neutral";

  if (input.themeUnsupportedReason) {
    const localized = localizeThemeUnsupportedSummary(input.themeUnsupportedReason);
    if (localized.gateHint === "OVERHEAT" || input.gateState === "OVERHEAT") {
      parts.push("题材观察暂停");
      tone = "warning";
    } else {
      parts.push("题材未开放");
      tone = "warning";
    }
  }

  if (input.priorityStrategyLabel) {
    parts.push(`优先看${input.priorityStrategyLabel}复核`);
    if (tone === "neutral") tone = "positive";
  } else if (input.gateState === "OVERHEAT") {
    parts.push("优先看多因子复核");
    tone = "warning";
  } else if (input.gateState === "WARM") {
    parts.push("超跌池已激活");
    if (tone === "neutral") tone = "positive";
  }

  return { line: parts.join(" · "), tone };
}

export function buildDeepZoneAuditRows(input: {
  cycleRotationSummary?: Pick<StockStrategyPanelResultSummary, "badgeLabel" | "tone"> | null;
  themeBreakoutSummary?: Pick<StockStrategyPanelResultSummary, "badgeLabel" | "tone"> | null;
  strategyBacktestSummary: Pick<StockStrategyPanelResultSummary, "badgeLabel" | "tone">;
  strategyBacktestDateRangeLabel: string;
  consensusItemCount: number;
  reviewQueueCount: number;
  consensusReviewSummary: Pick<StockStrategyPanelResultSummary, "tone">;
  marketPrioritySummary: Pick<StockStrategyPanelResultSummary, "tone">;
  eventsMonitoringSummary: Pick<StockStrategyPanelResultSummary, "badgeLabel" | "tone">;
  eventMonitorCount: number;
}): StockDeepZoneAuditRow[] {
  return [
    {
      key: "supply",
      label: "供数",
      value: input.cycleRotationSummary?.badgeLabel ?? input.themeBreakoutSummary?.badgeLabel ?? "待确认",
      tone: input.cycleRotationSummary?.tone ?? input.themeBreakoutSummary?.tone ?? "neutral",
    },
    {
      key: "replay",
      label: "回放",
      value: input.strategyBacktestSummary.badgeLabel ?? input.strategyBacktestDateRangeLabel,
      tone: input.strategyBacktestSummary.tone ?? "neutral",
    },
    {
      key: "review",
      label: "候选",
      value: `${input.consensusItemCount} / ${input.reviewQueueCount}`,
      tone: input.consensusReviewSummary.tone ?? input.marketPrioritySummary.tone ?? "neutral",
    },
    {
      key: "events",
      label: "事件",
      value: input.eventsMonitoringSummary.badgeLabel ?? `${input.eventMonitorCount}`,
      tone: input.eventsMonitoringSummary.tone ?? "neutral",
    },
  ];
}

function eventMonitorPriority(row: StockAnalysisEventMonitorRow): number {
  if (row.level === "error") return 3;
  if (row.level === "warning") return 2;
  return 1;
}

function eventMonitorSourceLabel(source: StockAnalysisEventMonitorRow["source"]): string {
  const labels: Record<StockAnalysisEventMonitorRow["source"], string> = {
    diagnostic: "诊断",
    data_gap: "缺口",
    unsupported: "阻断",
    signal_confluence: "联动",
    risk_exit: "风险",
  };
  return labels[source];
}

export function buildCycleRotationPanelSummary(input: {
  framework: NonNullable<LivermoreStrategyPayload["cycle_rotation_framework"]>;
  macroLayer: StockCycleMacroLayerSummary | null;
  portfolioBacktest: LivermoreCandidateHistoryPortfolioBacktestPayload | null;
  proxyBacktest: LivermoreCycleProxyBacktestPayload | null;
  portfolioQueryState?: StockStrategyPanelQueryState;
  proxyQueryState?: StockStrategyPanelQueryState;
}): StockStrategyPanelResultSummary {
  const readyLayers = input.framework.layers.filter((layer) => layer.status === "ready").length;
  const totalLayers = input.framework.layers.length;
  const stageLabel = localizeImplementationStage(input.framework.implementation_stage);
  const proxyReturn =
    input.proxyBacktest?.status === "proxy" ? input.proxyBacktest.summary?.cumulative_return : null;
  const portfolioReturn =
    input.portfolioBacktest?.status === "portfolio_proxy"
      ? input.portfolioBacktest.summary?.cumulative_return
      : null;
  const backtestLoading =
    input.portfolioQueryState === "loading" || input.proxyQueryState === "loading";
  const backtestIdle =
    input.portfolioQueryState === "idle" && input.proxyQueryState === "idle";
  const backtestError =
    input.portfolioQueryState === "error" || input.proxyQueryState === "error";
  const backtestPartiallyTriggered =
    !backtestIdle &&
    (input.portfolioQueryState === "idle" || input.proxyQueryState === "idle");
  const proxySummary = input.proxyBacktest?.summary;
  const validRowCount = (value: number | undefined): number | null =>
    typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null;
  const executionRows = validRowCount(proxySummary?.return_rows_execution_net_adjusted);
  const adjustedFallbackRows = validRowCount(proxySummary?.return_rows_adjusted_fallback);
  const grossFallbackRows = validRowCount(proxySummary?.return_rows_gross_fallback);
  const blockedRows = validRowCount(input.proxyBacktest?.execution_blocked_rows_in_window);
  const includedRows =
    executionRows != null && adjustedFallbackRows != null && grossFallbackRows != null
      ? executionRows + adjustedFallbackRows + grossFallbackRows
      : null;
  const coverageLabel =
    executionRows != null && includedRows != null && includedRows > 0
      ? `${executionRows}/${includedRows}（${Math.round((executionRows / includedRows) * 100)}%）`
      : "待补";
  const preferredField = proxySummary?.return_field_used?.trim();
  const adjustedFallbackField = proxySummary?.return_field_fallback?.trim();
  const grossFallbackField = proxySummary?.return_field_second_fallback?.trim();
  const preferredFieldLabel = preferredField
    ? ` ${preferredField}${preferredField === "return_5d_net_adj" ? "（次日开盘净收益）" : ""}`
    : "待补";
  const adjustedFallbackLabel =
    adjustedFallbackField && adjustedFallbackRows != null
      ? `${adjustedFallbackField} ${adjustedFallbackRows} 行`
      : adjustedFallbackField
        ? `${adjustedFallbackField} 行数待补`
        : "第一档待补";
  const grossFallbackLabel =
    grossFallbackField && grossFallbackRows != null
      ? `${grossFallbackField} ${grossFallbackRows} 行`
      : grossFallbackField
        ? `${grossFallbackField} 行数待补`
        : "第二档待补";
  const proxyBacktestBasisDisclosure = input.proxyBacktest
    ? `入场口径：优先字段${preferredFieldLabel}；可执行入场覆盖${coverageLabel === "待补" ? coverageLabel : ` ${coverageLabel}`}。回退构成：${adjustedFallbackLabel}；${grossFallbackLabel}。阻断剔除${blockedRows == null ? "待补" : ` ${blockedRows} 行`}；公式版本${input.proxyBacktest.formula_version?.trim() ? ` ${input.proxyBacktest.formula_version.trim()}` : "待补"}。`
    : undefined;

  const stats: StockStrategyPanelMiniStat[] = [
    {
      key: "stage",
      label: "阶段",
      value: stageLabel,
      valueTone: input.framework.implementation_stage.includes("proxy") ? "warning" : "emphasis",
    },
    {
      key: "layers",
      label: "就绪",
      value: `${readyLayers}/${totalLayers}`,
      valueTone: readyLayers === totalLayers ? "emphasis" : "warning",
    },
  ];
  if (input.macroLayer) {
    stats.push({
      key: "macro",
      label: "宏观",
      value: input.macroLayer.macroScoreLabel,
      valueTone: input.macroLayer.tone === "positive" ? "emphasis" : "warning",
    });
  }
  if (backtestError) {
    stats.push({ key: "backtest", label: "回测", value: "读取失败", valueTone: "warning" });
  } else if (backtestLoading) {
    stats.push({ key: "backtest", label: "回测", value: "读取中", valueTone: "flat" });
  } else if (backtestIdle) {
    stats.push({ key: "backtest", label: "回测", value: "待触发", valueTone: "flat" });
  } else if (backtestPartiallyTriggered) {
    stats.push({ key: "backtest", label: "回测", value: "部分触发", valueTone: "warning" });
  } else if (!backtestLoading && portfolioReturn != null) {
    stats.push({
      key: "portfolio",
      label: "组合",
      value: formatBacktestSignedReturn(portfolioReturn),
      valueTone: portfolioReturn >= 0 ? "up" : "down",
    });
  } else if (!backtestLoading && proxyReturn != null) {
    stats.push({
      key: "proxy",
      label: "代理",
      value: formatBacktestSignedReturn(proxyReturn),
      valueTone: proxyReturn >= 0 ? "up" : "down",
    });
  } else if (!backtestLoading) {
    stats.push({ key: "backtest", label: "回测", value: "无样本", valueTone: "warning" });
  }

  const macroStatus = input.macroLayer?.statusLabel ?? "待补";
  const headline =
    macroStatus === "已落地" ? "宏观层已落地" : macroStatus === "部分就绪" ? "宏观层部分就绪" : "宏观层待补";
  const detail =
    backtestError
      ? "回测证据读取失败；框架层只读证据保留，当前不作回测结论。"
      : backtestLoading
        ? "回测加载中，展开查看公式、层状态与回测明细。"
        : backtestIdle
        ? "回测证据尚未触发，展开相关复核区后读取。"
        : backtestPartiallyTriggered
          ? "部分回测端点尚未触发；当前已返回证据仅作只读参考。"
          : readyLayers < totalLayers
            ? `就绪 ${readyLayers}/${totalLayers} 层；补齐缺失输入后可进入完整验证。`
            : "各层只读证据已接入，展开查看公式、层状态与回测明细。";

  return {
    headline,
    detail,
    proxyBacktestBasisDisclosure,
    complianceDetail: input.framework.observation_only
      ? "研究观察口径：只读证据已接入；缺失输入补齐前，不生成收益、仓位或执行结论。"
      : "策略口径已接入；仍需结合回测和风险边界复核。",
    badgeLabel: stageLabel,
    stats,
    tone:
      backtestError || backtestPartiallyTriggered
        ? "warning"
        : input.macroLayer?.tone ?? "neutral",
  };
}

export function buildThemeBreakoutPanelSummary(input: {
  payload: LivermoreStrategyPayload;
  cards: StockThemeBreakoutCard[];
  reviewCount: number;
  unsupportedReason?: string;
}): StockStrategyPanelResultSummary {
  const themePayload = input.payload.theme_breakout;
  const isProxy = themePayload?.is_proxy === true;
  const movementTotal = summarizeThemeMovementCount(input.payload);
  const topCard = input.cards[0];
  const coverageCount = themePayload?.items?.length ?? input.cards.length;
  const usesCurrentOverlay = Boolean(
    themePayload?.items?.some(
      (item) => item.source_kind?.trim().toLowerCase() === "tushare_current_overlay",
    ) ||
      themePayload?.evidence_state?.concept_membership?.status === "current_overlay" ||
      themePayload?.evidence_state?.concept_membership?.concept_source_kind ===
        "tushare_current_overlay",
  );

  if (input.unsupportedReason) {
    const localized = localizeThemeUnsupportedSummary(input.unsupportedReason);
    return {
      headline: "题材雷达未开放",
      detail: localized.detail,
      complianceDetail: localized.detail,
      badgeLabel: "暂停",
      stats: [{ key: "status", label: "状态", value: "未开放", valueTone: "warning" }],
      tone: "warning",
    };
  }

  const stats: StockStrategyPanelMiniStat[] = [
    {
      key: "coverage",
      label: "覆盖",
      value: `${coverageCount} 簇`,
      valueTone: coverageCount > 0 ? "emphasis" : "flat",
    },
    {
      key: "movement",
      label: "异动",
      value: `${movementTotal} 条`,
      valueTone: movementTotal > 0 ? "warning" : "flat",
    },
  ];
  if (input.reviewCount > 0) {
    stats.push({
      key: "review",
      label: "未入选",
      value: `${input.reviewCount} 项`,
      valueTone: "warning",
    });
  }
  stats.push({
    key: "mode",
    label: "模式",
    value: usesCurrentOverlay ? "当前覆盖" : isProxy ? "代理" : "概念",
    valueTone: usesCurrentOverlay || isProxy ? "warning" : "emphasis",
  });

  const headline =
    input.cards.length > 0
      ? `#${topCard?.rank ?? 1} ${topCard?.themeName ?? "题材"}领先`
      : "暂无题材突变项";

  return {
    headline,
    detail:
      input.cards.length > 0
        ? (topCard?.summary ?? "展开查看簇内龙头与边界说明。")
        : isProxy
          ? "代理观察：日线+涨停+名称簇，非正式概念库。"
          : "真实概念观察：已落地成分与异动，仍只读复核。",
    complianceDetail: usesCurrentOverlay
      ? "当前覆盖 · 非时点 · 不可历史使用 · 仅观察"
      : isProxy
        ? "代理题材口径：日线、涨停与名称簇观察；不是正式概念库。"
        : undefined,
    badgeLabel: usesCurrentOverlay
      ? "当前覆盖"
      : input.cards.length > 0
        ? "已就绪"
        : isProxy
          ? "代理观察"
          : "概念库",
    stats,
    tone: usesCurrentOverlay ? "warning" : input.cards.length > 0 ? "positive" : "neutral",
  };
}

export function buildConsensusReviewPanelSummary(consensus: ConsensusSummary): StockStrategyPanelResultSummary {
  if (!consensus.hasAnyStrategy) {
    return {
      headline: "暂无候选",
      detail: "今天没有共振候选；先核对门控，再下翻看多因子池或各策略观察池。",
      badgeLabel: "无候选",
      stats: [{ key: "sample", label: "共振", value: "0", valueTone: "warning" }],
      tone: "warning",
    };
  }
  if (consensus.doubleCount <= 0) {
    return {
      headline: "暂无 T+5 共振",
      detail: "今天没有趋势+多因子共振；可先复核单策略池，或查看多因子池排序。",
      badgeLabel: "待复核",
      stats: [
        { key: "trend", label: "趋势", value: `${consensus.strategyCounts.livermore}`, valueTone: "emphasis" },
        { key: "factor", label: "多因子", value: `${consensus.strategyCounts.factor_screen}`, valueTone: "emphasis" },
        { key: "union", label: "去重", value: `${consensus.totalUnion}`, valueTone: "flat" },
      ],
      tone: "warning",
    };
  }

  const top = consensus.items[0];
  return {
    headline: `T+5 共振 ${consensus.doubleCount} 只`,
    detail: top
      ? `下一步：优先复核 ${top.stockName}（${top.stockCode}），${top.strategies.length} 策略同选。`
      : "按共振得分排序，仅作复核先后。",
    badgeLabel: "已就绪",
    stats: [
      {
        key: "double",
        label: "共振",
        value: `${consensus.doubleCount}`,
        valueTone: "emphasis",
      },
      {
        key: "factor",
        label: "多因子",
        value: `${consensus.strategyCounts.factor_screen}`,
        valueTone: "flat",
      },
      {
        key: "trend",
        label: "趋势",
        value: `${consensus.strategyCounts.livermore}`,
        valueTone: "flat",
      },
    ],
    tone: "positive",
  };
}
export function buildMarketPriorityPanelSummary(input: {
  rows: LivermoreStrategyScorePayload["rows"];
  payload: LivermoreStrategyScorePayload | null;
  marketState: string | null;
  queryState: StockStrategyPanelQueryState;
  errorMessage?: string;
}): StockStrategyPanelResultSummary {
  if (input.queryState === "idle") {
    return {
      headline: "待触发",
      detail: "展开策略优先级复核区后读取证据。",
      badgeLabel: "待触发",
      stats: [],
      tone: "neutral",
    };
  }
  if (input.queryState === "loading") {
    return {
      headline: "加载中…",
      loading: true,
      badgeLabel: "加载中",
      stats: [],
      tone: "neutral",
    };
  }
  if (input.queryState === "error") {
    return {
      headline: "优先级暂不可用",
      detail: localizeStrategyPanelErrorDetail(input.errorMessage),
      badgeLabel: "读取失败",
      stats: [],
      tone: "warning",
    };
  }
  const top = pickTopPriorityRow(input.rows);
  const sufficientCount = input.rows.filter((row) => row.sample_status === "sufficient").length;
  const window = input.payload?.backtest_window_summary;
  const sourceGapDateCount = backtestSourceGapDateCount(window);
  const unsupportedDateCount = Math.max(
    0,
    backtestUnsupportedDateCount(window) - sourceGapDateCount,
  );
  if (!top || sufficientCount === 0) {
    const headline =
      sourceGapDateCount > 0
        ? "历史样本源不足"
        : unsupportedDateCount > 0
          ? "回放窗口不支持"
          : "样本不足";
    return {
      headline,
      detail: [
        sourceGapDateCount > 0 ? `历史缺源 ${sourceGapDateCount} 日` : null,
        unsupportedDateCount > 0 ? `窗口不支持 ${unsupportedDateCount} 日` : null,
        `阈值 ${input.payload?.min_sample ?? 30} · 只读排序`,
      ]
        .filter(Boolean)
        .join(" · "),
      badgeLabel:
        sourceGapDateCount > 0
          ? "历史源不足"
          : unsupportedDateCount > 0
            ? "窗口不支持"
            : "样本不足",
      stats: [
        { key: "rows", label: "策略", value: `${input.rows.length}`, tone: "neutral" },
        ...(sourceGapDateCount > 0
          ? [{ key: "unsupported", label: "历史源不足", value: `${sourceGapDateCount} 日`, tone: "warning" as const }]
          : []),
        ...(unsupportedDateCount > 0
          ? [{ key: "window", label: "窗口不支持", value: `${unsupportedDateCount} 日`, tone: "warning" as const }]
          : []),
      ],
      tone: "warning",
    };
  }

  const horizon = input.payload?.primary_horizon ?? "return_5d";
  const horizonStats = top.stats[horizon];
  const status = strategyPrioritySummaryStatus(top.priority_label);
  const coverageLimited = sourceGapDateCount > 0 || unsupportedDateCount > 0;
  return {
    headline: `${status.label} · ${localizeStockStrategyLabel(top.strategy_label, top.signal_kind)}`,
    detail: [
      localizeStockBackendText(top.reason, top.signal_kind),
      sourceGapDateCount > 0 ? `历史缺源 ${sourceGapDateCount} 日` : null,
      unsupportedDateCount > 0 ? `窗口不支持 ${unsupportedDateCount} 日` : null,
    ]
      .filter(Boolean)
      .join(" · "),
    badgeLabel:
      sourceGapDateCount > 0
        ? "部分缺源"
        : unsupportedDateCount > 0
          ? "窗口受限"
          : status.badgeLabel,
    stats: [
      {
        key: "score",
        label: "评分",
        value: top.priority_score?.toFixed(1) ?? "-",
        tone: status.tone,
      },
      {
        key: horizon,
        label: strategyHorizonShortLabel(horizon),
        value: formatBacktestHorizonStatsText(horizonStats),
        tone: coverageLimited ? "warning" : (horizonStats?.win_rate ?? 0) >= 0.5 ? "positive" : "neutral",
      },
    ],
    tone: coverageLimited ? "warning" : status.tone,
  };
}

export function buildStrategyBacktestPanelSummary(input: {
  payload: LivermoreCandidateHistoryPayload | null;
  sampleCount: number;
  window: BacktestWindowSummary | null;
  dateRangeLabel: string;
  rows: Array<{ kind: string; label: string; count: number; stats: Record<string, string> }>;
  queryState: StockStrategyPanelQueryState;
  errorMessage?: string;
}): StockStrategyPanelResultSummary {
  if (input.queryState === "idle") {
    return {
      headline: "待触发",
      detail: "展开策略回溯复核区后读取证据。",
      badgeLabel: "待触发",
      stats: [],
      tone: "neutral",
    };
  }
  if (input.queryState === "loading") {
    return {
      headline: "加载中…",
      loading: true,
      badgeLabel: "加载中",
      stats: [],
      tone: "neutral",
    };
  }
  if (input.queryState === "error") {
    return {
      headline: "回溯暂不可用",
      detail: localizeStrategyPanelErrorDetail(input.errorMessage),
      badgeLabel: "读取失败",
      stats: [],
      tone: "warning",
    };
  }
  const topRow = [...input.rows].sort((left, right) => right.count - left.count)[0];
  const sourceGapDateCount = backtestSourceGapDateCount(input.window);
  const unsupportedDateCount = Math.max(
    0,
    backtestUnsupportedDateCount(input.window) - sourceGapDateCount,
  );
  const pendingDateCount = backtestPendingDateCount(input.window);
  const summary = input.payload?.summary ?? null;
  const executionStats = summary?.execution_usable_stats ?? null;
  const decisionStats = summary?.decision_usable_stats ?? null;
  const signalStats = executionStats
    ? executionStats.by_signal_kind_horizon_usable_stats?.stock_candidate?.return_5d ??
      executionStats.by_signal_kind_horizon_stats?.stock_candidate?.return_5d
    : decisionStats?.by_signal_kind_horizon_usable_stats?.stock_candidate?.return_5d ??
      summary?.by_signal_kind_horizon_usable_stats?.stock_candidate?.return_5d ??
      decisionStats?.by_signal_kind_horizon_stats?.stock_candidate?.return_5d ??
      summary?.by_signal_kind_horizon_stats?.stock_candidate?.return_5d;
  const primaryStats = executionStats
    ? executionStats.horizon_usable_stats?.return_5d ?? signalStats
    : decisionStats?.horizon_usable_stats?.return_5d ??
      summary?.horizon_usable_stats?.return_5d ??
      summary?.horizon_stats?.return_5d ??
      signalStats;
  const primaryAvailableCount = primaryStats?.available_count ?? 0;
  const trendT5 =
    signalStats != null && signalStats.available_count > 0
      ? formatBacktestHorizonStatsText(signalStats)
      : sourceGapDateCount > 0
        ? `历史源不足 · ${sourceGapDateCount}日`
        : pendingDateCount > 0
          ? `自然待成熟 · ${pendingDateCount}日`
          : unsupportedDateCount > 0
            ? `窗口不支持 · ${unsupportedDateCount}日`
            : topRow?.stats.return_5d ?? "接口未提供";
  const metricBasisLabel = resolveStrategyBacktestMetricBasisLabel(input.payload);

  const hasVisibleSamples = input.sampleCount > 0;
  const hasPrimarySamples = primaryAvailableCount > 0;
  const isSourceLimited = sourceGapDateCount > 0;
  const isWindowLimited = unsupportedDateCount > 0;
  const hasPendingMaturity = pendingDateCount > 0;
  const fullyReady = hasPrimarySamples && !isSourceLimited && !isWindowLimited && !hasPendingMaturity;
  return {
    headline: isSourceLimited
      ? hasVisibleSamples
        ? `可见收益样本 ${input.sampleCount} 条`
        : "历史样本源不足"
      : isWindowLimited
        ? hasVisibleSamples
          ? `可见短窗样本 ${input.sampleCount} 条`
          : "回放窗口不支持"
        : hasPrimarySamples
          ? `T+5 有效样本 ${primaryAvailableCount} 条`
          : hasVisibleSamples
            ? hasPendingMaturity
              ? "短窗可见，T+5 待成熟"
              : "短窗可见，T+5 无成熟样本"
            : hasPendingMaturity
              ? "T+5 收益待成熟"
              : "暂无回溯样本",
    detail: [input.dateRangeLabel, metricBasisLabel].filter(Boolean).join(" · "),
    badgeLabel: isSourceLimited
      ? "历史源不足"
      : isWindowLimited
        ? "窗口不支持"
        : fullyReady
          ? "已就绪"
          : hasVisibleSamples || hasPrimarySamples
            ? "部分成熟"
            : hasPendingMaturity
              ? "待成熟"
              : "暂无样本",
    stats: [
      {
        key: "trend",
        label: topRow?.label ?? "趋势",
        value: trendT5,
        tone: fullyReady ? "positive" : "warning",
      },
      ...(pendingDateCount > 0
        ? [
            {
              key: "pending",
              label: "待成熟",
              value: `${pendingDateCount} 日`,
              tone: "warning" as const,
            },
          ]
        : []),
      ...(sourceGapDateCount > 0
        ? [
            {
              key: "unsupported",
              label: "历史源不足",
              value: `${sourceGapDateCount} 日`,
              tone: "warning" as const,
            },
          ]
        : []),
      ...(unsupportedDateCount > 0
        ? [
            {
              key: "window",
              label: "窗口不支持",
              value: `${unsupportedDateCount} 日`,
              tone: "warning" as const,
            },
          ]
        : []),
      {
        key: "range",
        label: "区间",
        value: input.dateRangeLabel || "区间未提供",
        tone: "neutral",
      },
    ],
    tone: fullyReady ? "positive" : "warning",
  };
}

export function buildStrategyOptimizationPanelSummary(input: {
  payload: LivermoreStrategyOptimizationPayload | null;
  rows: LivermoreStrategyOptimizationPayload["strategy_summaries"];
  queryState: StockStrategyPanelQueryState;
  errorMessage?: string;
}): StockStrategyPanelResultSummary {
  if (input.queryState === "idle") {
    return {
      headline: "待触发",
      detail: "展开优化诊断复核区后读取证据。",
      badgeLabel: "待触发",
      stats: [],
      tone: "neutral",
    };
  }
  if (input.queryState === "loading") {
    return {
      headline: "加载中…",
      loading: true,
      badgeLabel: "加载中",
      stats: [],
      tone: "neutral",
    };
  }
  if (input.queryState === "error") {
    return {
      headline: "优化诊断暂不可用",
      detail: localizeStrategyPanelErrorDetail(input.errorMessage),
      badgeLabel: "读取失败",
      stats: [],
      tone: "warning",
    };
  }
  if (!input.payload) {
    return {
      headline: "优化接口未提供数据",
      detail: "接口未返回优化诊断载荷，当前不形成优化判断。",
      badgeLabel: "接口未提供",
      stats: [],
      tone: "warning",
    };
  }

  const promoteCount = input.payload.recommendations.filter(
    (item) => item.action === "promote" || item.priority_label === "优先复核",
  ).length;
  const downgradeCount = input.payload.recommendations.filter(
    (item) => item.action === "downgrade" || item.priority_label === "降权观察",
  ).length;
  const top = input.rows[0];
  const horizon = input.payload.primary_horizon;
  const primaryStats = top?.stats[horizon];
  const window = input.payload.backtest_window_summary;
  const sourceGapDateCount = backtestSourceGapDateCount(window);
  const unsupportedDateCount = Math.max(
    0,
    backtestUnsupportedDateCount(window) - sourceGapDateCount,
  );
  const pendingRows = input.payload.pending_summary.pending_rows;

  if (!top) {
    const headline =
      sourceGapDateCount > 0
        ? "历史样本源不足"
        : unsupportedDateCount > 0
          ? "回放窗口不支持"
          : "优化样本不足";
    return {
      headline,
      detail: input.payload.pending_summary.message
        ? localizeStockBackendText(input.payload.pending_summary.message)
        : undefined,
      badgeLabel:
        sourceGapDateCount > 0
          ? "历史源不足"
          : unsupportedDateCount > 0
            ? "窗口不支持"
            : pendingRows > 0
              ? "待成熟"
              : "样本不足",
      stats: [
        ...(sourceGapDateCount > 0
          ? [{ key: "unsupported", label: "历史源不足", value: `${sourceGapDateCount} 日`, tone: "warning" as const }]
          : []),
        ...(unsupportedDateCount > 0
          ? [{ key: "window", label: "窗口不支持", value: `${unsupportedDateCount} 日`, tone: "warning" as const }]
          : []),
        ...(pendingRows > 0
          ? [
              {
                key: "pending",
                label: "待成熟",
                value: `${pendingRows} 行`,
                tone: "warning" as const,
              },
            ]
          : []),
      ],
      tone: "warning",
    };
  }

  const status = strategyPrioritySummaryStatus(top.recommendation.priority_label);
  const coverageLimited = sourceGapDateCount > 0 || unsupportedDateCount > 0;
  const topSourceGapDateCount = backtestSourceGapDateCount(window, top.signal_kind);
  const topUnsupportedDateCount = Math.max(
    0,
    backtestUnsupportedDateCount(window, top.signal_kind) - topSourceGapDateCount,
  );
  const topPendingDateCount = backtestPendingDateCount(window, top.signal_kind);
  const primaryValue =
    primaryStats && primaryStats.available_count > 0
      ? formatBacktestHorizonStatsText(primaryStats)
      : top.sample_status === "insufficient" || top.recommendation.action === "pending_more_history"
        ? "样本不足"
        : topSourceGapDateCount > 0
          ? `历史源不足 · ${topSourceGapDateCount}日`
          : topPendingDateCount > 0
            ? `自然待成熟 · ${primaryStats?.missing_count || topPendingDateCount}条`
            : topUnsupportedDateCount > 0
              ? `窗口不支持 · ${topUnsupportedDateCount}日`
              : pendingRows > 0
                ? `全局待成熟 · ${pendingRows}条`
                : primaryStats
                  ? "成熟度未提供"
                  : "接口未提供";
  return {
    headline: `${status.label} · ${localizeStockStrategyLabel(top.strategy_label, top.signal_kind)}`,
    detail: [
      localizeStockBackendText(top.recommendation.reason, top.signal_kind),
      sourceGapDateCount > 0 ? `历史缺源 ${sourceGapDateCount} 日` : null,
      unsupportedDateCount > 0 ? `窗口不支持 ${unsupportedDateCount} 日` : null,
    ]
      .filter(Boolean)
      .join(" · "),
    badgeLabel:
      sourceGapDateCount > 0
        ? "部分缺源"
        : unsupportedDateCount > 0
          ? "窗口受限"
          : status.badgeLabel,
    stats: [
      {
        key: "promote",
        label: "上调",
        value: `${promoteCount}`,
        tone: promoteCount > 0 ? "positive" : "neutral",
      },
      {
        key: "downgrade",
        label: "降权",
        value: `${downgradeCount}`,
        tone: downgradeCount > 0 ? "warning" : "neutral",
      },
      {
        key: horizon,
        label: strategyHorizonShortLabel(horizon),
        value: primaryValue,
        tone: coverageLimited || !primaryStats || primaryStats.available_count <= 0 ? "warning" : "neutral",
      },
    ],
    tone: coverageLimited ? "warning" : status.tone,
  };
}

export function buildObservationPoolsPanelSummary(input: {
  gateState: string | null | undefined;
  meanReversionCount: number;
  factorScreenCount: number;
  hybridFusionCount: number;
  meanReversionActive: boolean;
}): StockStrategyPanelResultSummary {
  const total = input.meanReversionCount + input.factorScreenCount + input.hybridFusionCount;
  const primaryCount = input.factorScreenCount > 0 ? input.factorScreenCount : input.hybridFusionCount;
  const primaryLabel = input.factorScreenCount > 0 ? "多因子" : input.hybridFusionCount > 0 ? "融合" : "观察池";

  const headline =
    primaryCount > 0
      ? `${primaryLabel} ${primaryCount} 只待复核`
      : total > 0
        ? `观察池合计 ${total} 只`
        : "观察池暂无候选";

  return {
    headline,
    detail:
      input.meanReversionActive && input.gateState === "WARM"
        ? "条件触发超跌反弹；融合/超跌明细见展开区。"
        : "融合/超跌明细见展开区。",
    badgeLabel: total > 0 ? "已就绪" : "待补",
    stats: [
      {
        key: "factor",
        label: "多因子",
        value: `${input.factorScreenCount}`,
        tone: input.factorScreenCount > 0 ? "positive" : "neutral",
      },
      {
        key: "mean",
        label: "超跌",
        value: input.meanReversionActive ? `${input.meanReversionCount}` : "暂停",
        tone: input.meanReversionActive ? "warning" : "neutral",
      },
      {
        key: "hybrid",
        label: "融合",
        value: `${input.hybridFusionCount}`,
        tone: input.hybridFusionCount > 0 ? "positive" : "neutral",
      },
    ],
    tone: total > 0 ? "positive" : "neutral",
  };
}

export function buildEventsMonitoringPanelSummary(
  rows: StockAnalysisEventMonitorRow[],
): StockStrategyPanelResultSummary {
  if (rows.length === 0) {
    return {
      headline: "暂无待复核事件",
      detail: "诊断、缺口与风险触发均空。",
      badgeLabel: "已就绪",
      stats: [{ key: "count", label: "事件", value: "0", tone: "positive" }],
      tone: "positive",
    };
  }

  const errorCount = rows.filter((row) => row.level === "error").length;
  const warningCount = rows.filter((row) => row.level === "warning").length;
  const top = [...rows].sort((left, right) => eventMonitorPriority(right) - eventMonitorPriority(left))[0];

  return {
    headline: `${rows.length} 条待复核`,
    detail: `最高优先：${eventMonitorSourceLabel(top.source)} / ${localizeStockDataFamily(top.impact)}`,
    badgeLabel: errorCount > 0 ? "异常待核" : warningCount > 0 ? "待复核" : "已就绪",
    stats: [
      { key: "error", label: "错误", value: `${errorCount}`, tone: errorCount > 0 ? "negative" : "positive" },
      { key: "warn", label: "预警", value: `${warningCount}`, tone: warningCount > 0 ? "warning" : "neutral" },
      { key: "top", label: "来源", value: eventMonitorSourceLabel(top.source), tone: "neutral" },
    ],
    tone: errorCount > 0 ? "negative" : warningCount > 0 ? "warning" : "neutral",
  };
}
