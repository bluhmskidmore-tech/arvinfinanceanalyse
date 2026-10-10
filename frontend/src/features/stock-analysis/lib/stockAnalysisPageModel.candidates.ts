// Candidate evidence cards, review queue and pool selection for the stock-analysis page model.
import type {
  FreshTrendWatchlistCandidateItem,
  HybridFusionCandidateItem,
  LivermoreStockCandidateItem,
  LivermoreStrategyPayload,
} from "../../../api/contracts";
import { EM_DASH, formatYi } from "../../../utils/format";
import type {
  StockCandidateEvidenceBullet,
  StockCandidateEvidenceCard,
  StockCandidatePattern,
  StockCandidateReviewQueueItem,
  StockCandidateSourcePool,
  StockReviewQueueEmptyState,
  StockReviewQueueSectorFilterView,
  StockSectorFilterSummary,
} from "./stockAnalysisPageModel.types";
import { formatNumber, formatRatioAsPercent, numericRawField } from "./stockAnalysisPageModel.format";
import { localizeStockBackendText } from "./stockAnalysisPageModel.localize";
import {
  finiteNumber,
  sectorHeavyweightSourceLabel,
  stockModuleStates,
  strategyWalkForwardBadge,
} from "./stockAnalysisPageModel.shared";

function buildCandidateFundamentalEvidence(item: LivermoreStockCandidateItem): StockCandidateEvidenceBullet[] {
  const bullets: StockCandidateEvidenceBullet[] = [];
  const factorScore = finiteNumber(item.factor_score);
  const factorRank = finiteNumber(item.factor_overlay_rank);
  if (factorScore != null || factorRank != null) {
    bullets.push({
      key: "fundamental_overlay",
      label: "基本面因子",
      value: [
        factorScore != null ? `因子分 ${formatNumber(factorScore, 4)}` : null,
        factorRank != null ? `因子排名 #${factorRank.toFixed(0)}` : null,
      ]
        .filter((part): part is string => Boolean(part))
        .join(" / "),
    });
  }

  const valuationParts = [
    finiteNumber(item.pe) != null ? `PE ${formatNumber(item.pe, 2)}` : null,
    finiteNumber(item.pb) != null ? `PB ${formatNumber(item.pb, 2)}` : null,
    finiteNumber(item.ps) != null ? `PS ${formatNumber(item.ps, 2)}` : null,
  ].filter((part): part is string => Boolean(part));
  if (valuationParts.length > 0) {
    bullets.push({
      key: "valuation",
      label: "估值",
      value: valuationParts.join(" / "),
    });
  }

  const qualityParts = [
    finiteNumber(item.roe) != null ? `ROE ${formatRatioAsPercent(item.roe, 1)}` : null,
    finiteNumber(item.gross_margin) != null ? `毛利率 ${formatRatioAsPercent(item.gross_margin, 1)}` : null,
  ].filter((part): part is string => Boolean(part));
  if (qualityParts.length > 0) {
    bullets.push({
      key: "quality",
      label: "质量",
      value: qualityParts.join(" / "),
    });
  }

  const momentumParts = [
    finiteNumber(item.three_month_return) != null ? `3月 ${formatRatioAsPercent(item.three_month_return, 1)}` : null,
    finiteNumber(item.twelve_month_return) != null ? `12月 ${formatRatioAsPercent(item.twelve_month_return, 1)}` : null,
  ].filter((part): part is string => Boolean(part));
  if (momentumParts.length > 0) {
    bullets.push({
      key: "fundamental_momentum",
      label: "基本面动量",
      value: momentumParts.join(" / "),
    });
  }

  return bullets;
}

function candidateFundamentalCounterEvidence(item: LivermoreStockCandidateItem): string {
  const hasOverlay = finiteNumber(item.factor_score) != null || finiteNumber(item.factor_overlay_rank) != null;
  if (hasOverlay) {
    return "基本面因子已纳入候选排序，但财报口径、最新公告和一致预期仍需复核。";
  }
  return "基本面与估值证据未接入，不参与当前候选排序。";
}

export function isStockModulePrimaryExcluded(
  payload: LivermoreStrategyPayload | null | undefined,
  key: LivermoreStrategyPayload["supported_outputs"][number],
): boolean {
  if (!payload) {
    return true;
  }
  const states = stockModuleStates(payload);
  if (states.length === 0) {
    return true;
  }
  const state = states.find((item) => item.key === key);
  return !state || state.excludes_from_primary || state.render_mode !== "primary";
}

function sortedCandidateItems(payload: LivermoreStrategyPayload) {
  return [...(payload.stock_candidates?.items ?? [])].sort((left, right) => left.rank - right.rank);
}

function sortedHybridFusionItems(payload: LivermoreStrategyPayload) {
  return [...(payload.hybrid_fusion_candidates?.items ?? [])].sort((left, right) => left.rank - right.rank);
}

function sortedFreshTrendWatchlistItems(payload: LivermoreStrategyPayload): FreshTrendWatchlistCandidateItem[] {
  return [...(payload.fresh_trend_watchlist?.items ?? [])].sort((left, right) => left.rank - right.rank);
}

function formatCandidatePattern(item: LivermoreStockCandidateItem): StockCandidatePattern {
  const patternCode = item.pattern_code;
  if (
    patternCode !== "breakout" &&
    patternCode !== "pullback" &&
    patternCode !== "consolidation"
  ) {
    return EM_DASH;
  }
  const label = item.pattern?.trim();
  return label || EM_DASH;
}

function formatDistanceToBreakoutPct(item: LivermoreStockCandidateItem): string {
  const distance = item.distance_to_breakout_pct;
  return distance != null && Number.isFinite(distance)
    ? `${distance.toFixed(2)}%`
    : EM_DASH;
}

function fusionConfidenceLabel(value: string | null | undefined): string {
  const normalized = value?.trim().toLowerCase();
  if (!normalized) return "待补";
  if (normalized === "high") return "高";
  if (normalized === "medium") return "中";
  if (normalized === "low") return "低";
  return "置信度待确认";
}

function fusionActionLabel(value: string | null | undefined): string {
  const action = value?.trim();
  if (!action) return "待补";
  const normalized = action.toLowerCase().replace(/[\s-]+/g, "_");
  const labels: Record<string, string> = {
    observe: "观察",
    monitor: "观察",
    monitor_only: "观察",
    review: "复核",
    pending_review: "待复核",
    observation_only: "仅观察",
    core_plus_trading: "重点复核",
    core_reduce_trading: "降权观察",
    satellite_trial: "卫星观察",
  };
  if (labels[normalized]) return labels[normalized];
  const compact = normalized.replace(/_/g, "");
  if (
    normalized.includes("external_vendor") ||
    normalized.includes("vendor_") ||
    normalized.includes("source_table") ||
    compact.includes("externalvendor") ||
    compact.includes("vendor") ||
    compact.includes("sourcetable") ||
    compact.includes("choicestock")
  ) {
    return "裁决待确认";
  }
  if (/^[a-z0-9_]+$/i.test(normalized)) return "裁决待确认";
  return action;
}

export const CANDIDATE_SOURCE_POOL_LABELS: Record<StockCandidateSourcePool, string> = {
  theme_breakout: "题材突破",
  hybrid_fusion: "融合策略",
  stock_candidates: "趋势突破",
  fresh_trend_watchlist: "新趋势观察",
  factor_screen_candidates: "多因子",
  uptrend_momentum_candidates: "上升动量",
  mean_reversion_candidates: "超跌反弹",
  workbench_review_queue: "后端观察队列",
};

/** 题材内强势个股：strong 或涨停确认；题材按后端 rank、个股按涨幅降序。 */
function sortedThemeBreakoutStrongStocks(payload: LivermoreStrategyPayload) {
  const themes = [...(payload.theme_breakout?.items ?? [])].sort((left, right) => left.rank - right.rank);
  return themes.flatMap((theme) =>
    [...theme.items]
      .filter((stock) => stock.strong || stock.closed_up_limit)
      .sort((left, right) => (finiteNumber(right.pctchange) ?? 0) - (finiteNumber(left.pctchange) ?? 0))
      .map((stock) => ({ theme, stock })),
  );
}

function buildThemeBreakoutEvidenceCards(
  payload: LivermoreStrategyPayload,
): StockCandidateEvidenceCard[] {
  const formula = payload.theme_breakout?.formula_version ?? "theme_breakout";
  const walkForward = strategyWalkForwardBadge(payload.theme_breakout?.walk_forward);
  return sortedThemeBreakoutStrongStocks(payload).map(({ theme, stock }, index) => {
    const evidenceBullets: StockCandidateEvidenceBullet[] = [
      {
        key: "theme_rank",
        label: "题材排名",
        value: `第 ${theme.rank} 名：${theme.theme_name}`,
      },
      {
        key: "advance_ratio",
        label: "题材上涨占比",
        value: `${formatRatioAsPercent(theme.advance_ratio, 1)}（${theme.advance_count}/${theme.member_count} 只）`,
      },
      {
        key: "theme_strength",
        label: "题材强度",
        value: `强势 ${theme.strong_stock_count} 只 · 涨停 ${theme.limit_stock_count} 只 · 均涨 ${formatNumber(theme.avg_pctchange, 2)}%`,
      },
      {
        key: "stock_move",
        label: "个股涨幅 / 换手",
        value: `${formatNumber(stock.pctchange, 2)}% · 换手 ${formatNumber(stock.turn, 2)}%`,
      },
      {
        key: "close_strength",
        label: "收盘强度",
        value: formatRatioAsPercent(stock.close_strength, 0),
      },
      {
        key: "limit_confirm",
        label: "涨停确认",
        value: stock.closed_up_limit ? "收盘涨停" : stock.strong ? "强势未涨停" : "待补",
      },
      {
        key: "parent_sector",
        label: "所属行业",
        value: `${theme.parent_sector_name}（行业排名第 ${theme.parent_sector_rank}）`,
      },
      { key: "formula_version", label: "公式版本", value: formula },
    ];
    const evidence = evidenceBullets.map((bullet) => `${bullet.label}：${bullet.value}`);
    const themeReason = theme.reason?.trim();

    return {
      rank: index + 1,
      stockCode: stock.stock_code,
      stockName: stock.stock_name,
      sectorCode: stock.sector_code,
      sectorName: stock.sector_name,
      headline: `题材突破 #${index + 1} · ${stock.stock_name}`,
      sourcePool: "theme_breakout" as const,
      sourcePoolLabel: CANDIDATE_SOURCE_POOL_LABELS.theme_breakout,
      walkForward,
      pattern: stock.closed_up_limit ? "涨停" : "强势",
      patternNote: "题材强势标签来自后端题材聚合口径，仅作观察辅助，不构成正式结论。",
      distanceToBreakoutPct: `题材第 ${theme.rank}`,
      evidenceBullets,
      evidence,
      counterEvidence: [
        theme.observation_only
          ? "题材池为只读观察输出，不构成交易指令。"
          : "题材证据仍需人工复核，不构成交易指令。",
        payload.theme_breakout?.is_proxy
          ? "当前题材为代理篮子（按行业/名称关键词构造），非真实概念成分。"
          : "概念成分表为时点数据，成分变更需复核。",
        "个股新闻、公告与盘中成交顺序未纳入本卡证据。",
      ],
      invalidationRules: [
        themeReason
          ? `题材入选理由失效即降级复核：${localizeStockBackendText(themeReason, "theme_breakout")}`
          : "题材入选理由失效即降级复核。",
        `题材跌出强势区间（上涨占比回落、强势股数 ${theme.strong_stock_count} 只收缩）时降级观察。`,
        "个股跌破当日收盘强度区间、涨停打开或停牌时，不得继续解释为有效观察。",
      ],
      rawFields: [
        { key: "theme_key", label: "题材键", value: theme.theme_key },
        numericRawField("theme_rank", "题材排名", theme.rank, String(theme.rank)),
        numericRawField("advance_ratio", "上涨占比", theme.advance_ratio, formatNumber(theme.advance_ratio, 6)),
        numericRawField("member_count", "题材成分数", theme.member_count, String(theme.member_count)),
        numericRawField("strong_stock_count", "强势股数", theme.strong_stock_count, String(theme.strong_stock_count)),
        numericRawField("limit_stock_count", "涨停股数", theme.limit_stock_count, String(theme.limit_stock_count)),
        numericRawField("avg_pctchange", "题材均涨", theme.avg_pctchange, formatNumber(theme.avg_pctchange, 4)),
        numericRawField("avg_turn", "题材均换手", theme.avg_turn, formatNumber(theme.avg_turn, 4)),
        numericRawField("close", "收盘", stock.close, formatNumber(stock.close, 4)),
        numericRawField("pctchange", "个股涨幅", stock.pctchange, formatNumber(stock.pctchange, 4)),
        numericRawField("turn", "个股换手", stock.turn, formatNumber(stock.turn, 4)),
        numericRawField("amplitude", "个股振幅", stock.amplitude, formatNumber(stock.amplitude, 4)),
        numericRawField("close_strength", "收盘强度", stock.close_strength, formatNumber(stock.close_strength, 4)),
      ],
    };
  });
}

function buildHybridFusionEvidenceCards(
  payload: LivermoreStrategyPayload,
): StockCandidateEvidenceCard[] {
  const formula = payload.hybrid_fusion_candidates?.formula_version ?? "hybrid_fusion";
  const walkForward = strategyWalkForwardBadge(payload.hybrid_fusion_candidates?.walk_forward);
  return sortedHybridFusionItems(payload).map((item: HybridFusionCandidateItem) => {
    const evidenceBullets: StockCandidateEvidenceBullet[] = [
      { key: "fusion_score", label: "融合分", value: formatNumber(item.fusion_score, 4) },
      { key: "cycle_score", label: "景气周期", value: formatNumber(item.cycle_score, 4) },
      {
        key: "lifecourt_proxy_score",
        label: "生命法庭线索",
        value: formatNumber(item.lifecourt_proxy_score, 4),
      },
      { key: "attention_score", label: "关注线索", value: formatNumber(item.attention_score, 4) },
      { key: "price_confirm_score", label: "价格确认", value: formatNumber(item.price_confirm_score, 4) },
      { key: "crowding_penalty", label: "拥挤惩罚", value: formatNumber(item.crowding_penalty, 4) },
      // Only disclosed when the backend returns factor_rank_available (older payloads omit it).
      ...(item.factor_rank_available === undefined
        ? []
        : [
            {
              key: "factor_rank_available",
              label: "因子排名覆盖",
              value: item.factor_rank_available ? "已覆盖" : "缺失，景气周期权重已重归一",
            },
          ]),
      {
        key: "life_long_pass",
        label: "生命法庭长仓门槛",
        value: item.life_long_pass == null ? "待补" : item.life_long_pass ? "通过" : "未通过",
      },
      {
        key: "fusion_action",
        label: "融合裁决",
        value: fusionActionLabel(item.fusion_action),
      },
      { key: "confidence", label: "置信度", value: fusionConfidenceLabel(item.confidence) },
      { key: "formula_version", label: "公式版本", value: formula },
    ];
    const sourceKindValues = Array.isArray(item.evidence?.source_kinds)
      ? item.evidence.source_kinds
      : [];
    const hasProxySourceKind = sourceKindValues.some((sourceKind) => {
      const normalized = sourceKind.toLowerCase().replace(/[\s-]+/g, "_");
      const compact = normalized.replace(/_/g, "");
      return (
        normalized.includes("external_vendor") ||
        normalized.includes("vendor_") ||
        normalized.includes("source_table") ||
        normalized.includes("proxy") ||
        compact.includes("externalvendor") ||
        compact.includes("sourcetable")
      );
    });
    const proxyCounterEvidence = hasProxySourceKind
      ? ["代理信号仅作来源线索，仍需人工确认与正式数据校验。"]
      : [];
    const sourceKinds = sourceKindValues.length > 0
      ? sourceKindValues.map(sectorHeavyweightSourceLabel).join(" / ")
      : "待补";
    const evidence = evidenceBullets.map((bullet) => `${bullet.label}：${bullet.value}`);

    return {
      rank: item.rank,
      stockCode: item.stock_code,
      stockName: item.stock_name,
      sectorCode: item.sector_code,
      sectorName: item.sector_name,
      headline: `融合策略 #${item.rank} · ${item.stock_name}`,
      sourcePool: "hybrid_fusion" as const,
      sourcePoolLabel: CANDIDATE_SOURCE_POOL_LABELS.hybrid_fusion,
      walkForward,
      pattern: "待补",
      patternNote: "融合策略为研究只读候选，形态标签需回看趋势与题材证据",
      distanceToBreakoutPct: "融合优先",
      evidenceBullets,
      evidence,
      counterEvidence: [
        "生命法庭层仍是观察线索，真实大V文本、OCR/ASR和社交情绪生产线仍待补。",
        ...proxyCounterEvidence,
        "仅作观察与复核，不作为执行依据。",
        `来源命中：${sourceKinds}`,
      ],
      invalidationRules: [
        "市场门控转弱、题材/趋势/因子来源失效或拥挤惩罚上升时，需要降级复核。",
        "数据质量陈旧或缺失时，不得解释为有效观察。",
      ],
      rawFields: [
        numericRawField("fusion_score", "融合分", item.fusion_score, formatNumber(item.fusion_score, 6)),
        numericRawField("cycle_score", "景气周期", item.cycle_score, formatNumber(item.cycle_score, 6)),
        numericRawField(
          "lifecourt_proxy_score",
          "生命法庭线索",
          item.lifecourt_proxy_score,
          formatNumber(item.lifecourt_proxy_score, 6),
        ),
        numericRawField("attention_score", "关注线索", item.attention_score, formatNumber(item.attention_score, 6)),
        numericRawField(
          "price_confirm_score",
          "价格确认",
          item.price_confirm_score,
          formatNumber(item.price_confirm_score, 6),
        ),
        numericRawField("crowding_penalty", "拥挤惩罚", item.crowding_penalty, formatNumber(item.crowding_penalty, 6)),
        { key: "fusion_action", label: "融合裁决", value: fusionActionLabel(item.fusion_action) },
        { key: "confidence", label: "置信度", value: fusionConfidenceLabel(item.confidence) },
      ],
    };
  });
}

function buildFreshTrendEvidenceCards(
  payload: LivermoreStrategyPayload,
): StockCandidateEvidenceCard[] {
  const formula = payload.fresh_trend_watchlist?.formula_version ?? "fresh_trend_watchlist";
  const walkForward = strategyWalkForwardBadge(payload.fresh_trend_watchlist?.walk_forward);
  return sortedFreshTrendWatchlistItems(payload).map((item) => {
    const concepts = item.concepts.length > 0 ? item.concepts.slice(0, 3).join(" / ") : "题材待补";
    const evidenceBullets: StockCandidateEvidenceBullet[] = [
      { key: "return_20d", label: "20日动量", value: formatRatioAsPercent(item.return_20d, 1) },
      { key: "return_60d", label: "60日动量", value: formatRatioAsPercent(item.return_60d, 1) },
      { key: "return_120d", label: "120日动量", value: formatRatioAsPercent(item.return_120d, 1) },
      { key: "ma20_distance", label: "MA20距离", value: formatRatioAsPercent(item.close_to_ma20, 1) },
      { key: "amount_ratio", label: "量能", value: `${formatNumber(item.amount_ratio, 2)}x` },
      {
        key: "turn_amplitude",
        label: "换手/振幅",
        value: `换手 ${formatNumber(item.turn, 2)}% / 振幅 ${formatNumber(item.amplitude, 2)}%`,
      },
      { key: "concepts", label: "题材线索", value: concepts },
      { key: "formula_version", label: "公式版本", value: formula },
    ];
    const evidence = evidenceBullets.map((bullet) => `${bullet.label}：${bullet.value}`);

    return {
      rank: item.rank,
      stockCode: item.stock_code,
      stockName: item.stock_name,
      sectorCode: item.sector_code,
      sectorName: item.sector_name,
      headline: `新趋势观察 #${item.rank} · ${item.stock_name}`,
      sourcePool: "fresh_trend_watchlist" as const,
      sourcePoolLabel: CANDIDATE_SOURCE_POOL_LABELS.fresh_trend_watchlist,
      walkForward,
      pattern: "突破",
      patternNote: "新趋势观察池为只读候选，需人工复核行业、题材和风险退出证据。",
      distanceToBreakoutPct: `MA20 ${formatRatioAsPercent(item.close_to_ma20, 1)}`,
      evidenceBullets,
      evidence,
      counterEvidence: [
        "过热门控下仅作观察补充，不构成趋势突破交易指令。",
        "涨停连板、公告/新闻与盘中成交顺序仍需人工复核。",
      ],
      invalidationRules: [
        "回落至 MA20 下方或量能失真时降级观察。",
        "旧经济行业、ST/停牌或数据质量异常时不得继续解释为新趋势。",
      ],
      rawFields: [
        numericRawField("close", "收盘", item.close, formatNumber(item.close, 4)),
        numericRawField("ma20", "20日均线", item.ma20, formatNumber(item.ma20, 4)),
        numericRawField("ma60", "60日均线", item.ma60, formatNumber(item.ma60, 4)),
        numericRawField("ma120", "120日均线", item.ma120, formatNumber(item.ma120, 4)),
        numericRawField("return_20d", "20日收益", item.return_20d, formatNumber(item.return_20d, 6)),
        numericRawField("return_60d", "60日收益", item.return_60d, formatNumber(item.return_60d, 6)),
        numericRawField("return_120d", "120日收益", item.return_120d, formatNumber(item.return_120d, 6)),
        numericRawField("close_to_ma20", "MA20距离", item.close_to_ma20, formatNumber(item.close_to_ma20, 6)),
        numericRawField("amount_ratio", "量比", item.amount_ratio, formatNumber(item.amount_ratio, 6)),
        { key: "hlimitedays", label: "连板天数", value: item.hlimitedays == null ? "待补" : String(item.hlimitedays) },
        numericRawField("score", "观察分", item.score, formatNumber(item.score, 6)),
      ],
    };
  });
}

export function buildReviewQueueEmptyState(payload: LivermoreStrategyPayload): StockReviewQueueEmptyState {
  const factorCount = isStockModulePrimaryExcluded(payload, "factor_screen_candidates")
    ? 0
    : (payload.factor_screen_candidates?.candidate_count ?? 0);
  const hybridCount = isStockModulePrimaryExcluded(payload, "hybrid_fusion")
    ? 0
    : (payload.hybrid_fusion_candidates?.candidate_count ?? 0);
  const nextParts: string[] = [];
  if (factorCount > 0) {
    nextParts.push(`可先看多因子池 ${factorCount} 只`);
  } else if (hybridCount > 0) {
    nextParts.push(`可先看融合策略池 ${hybridCount} 只`);
  } else {
    nextParts.push("可下翻「深度分析」查看各观察池");
  }
  return {
    headline: "今天没有进入复核队列的候选",
    detail: `${nextParts.join("；")}；请先看下方「策略共振」与「多策略观察池」。`,
  };
}

export function buildSectorFilterSummary(
  payload: LivermoreStrategyPayload,
  sectorFilterSectorCode: string | null,
): StockSectorFilterSummary {
  const queue = buildCandidateReviewQueue(payload);
  const totalCount = queue.length;
  if (!sectorFilterSectorCode) {
    return {
      sectorCode: null,
      sectorLabel: "全部行业",
      isFiltered: false,
      visibleCount: totalCount,
      totalCount,
      summaryLabel: `行业 全部 / 显示 ${totalCount} / ${totalCount} 个候选`,
    };
  }

  const sectorName =
    queue.find((item) => item.sectorCode === sectorFilterSectorCode)?.sectorName ??
    payload.sector_rank?.items?.find((item) => item.sector_code === sectorFilterSectorCode)?.sector_name ??
    sectorFilterSectorCode;
  const visibleCount = queue.filter((item) => item.sectorCode === sectorFilterSectorCode).length;

  return {
    sectorCode: sectorFilterSectorCode,
    sectorLabel: sectorName,
    isFiltered: true,
    visibleCount,
    totalCount,
    summaryLabel: `行业 ${sectorName} (${sectorFilterSectorCode}) / 显示 ${visibleCount} / ${totalCount} 个候选`,
  };
}

export function buildReviewQueueSectorFilterView({
  reviewQueue,
  sectorFilterSectorCode,
  selectedSectorLabel,
}: {
  reviewQueue: StockCandidateReviewQueueItem[];
  sectorFilterSectorCode: string | null;
  selectedSectorLabel?: string | null;
}): StockReviewQueueSectorFilterView {
  const sectorMap = new Map<string, string>();
  for (const card of reviewQueue) {
    sectorMap.set(card.sectorCode, card.sectorName || card.sectorCode);
  }
  const sectorOptions: [string, string][] = [...sectorMap.entries()].sort(([a], [b]) =>
    a.localeCompare(b, "zh-Hans-CN"),
  );
  const filteredCandidates = sectorFilterSectorCode
    ? reviewQueue.filter((candidate) => candidate.sectorCode === sectorFilterSectorCode)
    : reviewQueue;
  const selectedSectorLeadCandidate = filteredCandidates[0] ?? null;
  const sectorLabel = selectedSectorLabel ?? sectorFilterSectorCode;
  const sectorLinkTone = sectorFilterSectorCode
    ? filteredCandidates.length > 0
      ? "active"
      : "empty"
    : "all";
  const sectorLinkSummary = sectorFilterSectorCode
    ? filteredCandidates.length > 0
      ? `${sectorLabel} · ${filteredCandidates.length} 个候选`
      : `${sectorLabel} · 无候选`
    : `全部行业 · ${reviewQueue.length} 个候选`;
  const sectorLinkFocus = selectedSectorLeadCandidate
    ? `首位 ${selectedSectorLeadCandidate.stockName} · 距观察 ${selectedSectorLeadCandidate.distanceToBreakoutPct}`
    : sectorFilterSectorCode
      ? "该行业暂无线索"
      : "按板块收敛";

  return {
    sectorOptions,
    filteredCandidates,
    selectedSectorLeadCandidate,
    sectorLinkTone,
    sectorLinkSummary,
    sectorLinkFocus,
  };
}

export function buildCandidateReviewQueue(
  payload: LivermoreStrategyPayload,
): StockCandidateReviewQueueItem[] {
  return buildCandidateEvidenceCards(payload).map((card) => ({
    rank: card.rank,
    stockCode: card.stockCode,
    stockName: card.stockName,
    sectorCode: card.sectorCode,
    sectorName: card.sectorName,
    headline: card.headline,
    sourcePool: card.sourcePool,
    sourcePoolLabel: card.sourcePoolLabel,
    walkForward: card.walkForward,
    pattern: card.pattern,
    patternNote: card.patternNote,
    distanceToBreakoutPct: card.distanceToBreakoutPct,
    reviewFocus: `${card.stockName} · ${card.sectorName} · 距观察位 ${card.distanceToBreakoutPct}`,
    primaryEvidence: card.evidenceBullets.slice(0, 3),
    supportingEvidence: card.evidenceBullets.slice(3),
    boundaryEvidence: card.counterEvidence,
    invalidationFocus: card.invalidationRules[0] ?? "失效条件待补。",
    invalidationRules: card.invalidationRules,
    rawFields: card.rawFields,
    liquidityFloorPass: card.liquidityFloorPass ?? null,
    dailyAmountLabel: card.dailyAmountLabel ?? null,
  }));
}

export function buildCandidateEvidenceCards(
  payload: LivermoreStrategyPayload,
): StockCandidateEvidenceCard[] {
  // 择池顺序按 walk-forward 样本外证据强度排列（docs/strategy-reports/walk-forward-rerun-20260813.md §0.1）：
  // theme_breakout 是唯一被样本外支持的池（5/5 正超额窗），优先进入复核队列；
  // hybrid/stock 的样本外证据为零验证或削弱，仅在题材池无输出时兜底。
  const themeCards = isStockModulePrimaryExcluded(payload, "theme_breakout")
    ? []
    : buildThemeBreakoutEvidenceCards(payload);
  if (themeCards.length > 0) return themeCards;
  const hybridCards = isStockModulePrimaryExcluded(payload, "hybrid_fusion")
    ? []
    : buildHybridFusionEvidenceCards(payload);
  if (hybridCards.length > 0) return hybridCards;
  const stockWalkForward = strategyWalkForwardBadge(payload.stock_candidates?.walk_forward);
  const stockCards = isStockModulePrimaryExcluded(payload, "stock_candidates")
    ? []
    : sortedCandidateItems(payload).map((item) => {
      const pattern = formatCandidatePattern(item);
      const patternNote =
        pattern === EM_DASH
          ? "接口未提供后端统一形态字段，页面不做本地重算。"
          : "观察提示（后端统一几何口径）：形态标签仅作观察辅助，不构成正式结论。";
      const distanceToBreakoutPct = formatDistanceToBreakoutPct(item);

    const evidenceBullets: StockCandidateEvidenceBullet[] = [
      {
        key: "sector_rank",
        label: "行业排名",
        value: `行业排名第 ${item.sector_rank}：${item.sector_name}`,
      },
      {
        key: "close_vs_break",
        label: "收盘 vs 观察位",
        value: `收盘价 ${formatNumber(item.close)} · 观察位 ${formatNumber(item.breakout_level)}`,
      },
      {
        key: "ma_curve",
        label: "均线结构",
        value: `MA20 ${formatNumber(item.ma20)} · MA60 ${formatNumber(item.ma60)} · MA120 ${formatNumber(item.ma120)}`,
      },
      {
        key: "strength_turnover",
        label: "强度 / 换手观察",
        value: `收盘强度 ${formatRatioAsPercent(item.close_strength, 2)} · 换手观察值 ${formatNumber(item.abnormal_turnover, 3)}`,
      },
      ...buildCandidateFundamentalEvidence(item),
      {
        key: "gap_norm",
        label: "跳空归一观察",
        value:
          item.gap_norm != null && Number.isFinite(item.gap_norm)
            ? `${item.gap_norm.toFixed(4)}`
            : "待补",
      },
      {
        key: "breakout_extension_norm",
        label: "突破延展观察",
        value:
          item.breakout_extension_norm != null && Number.isFinite(item.breakout_extension_norm)
            ? `${item.breakout_extension_norm.toFixed(4)}`
            : "待补",
      },
      {
        key: "ema10_watch",
        label: "10EMA 失效观察",
        value: `当前 10EMA ${formatNumber(item.ema10)}，用于复核是否降级观察。`,
      },
    ];

    const evidence = evidenceBullets.map((bullet) => `${bullet.label}：${bullet.value}`);

    return {
      rank: item.rank,
      stockCode: item.stock_code,
      stockName: item.stock_name,
      sectorCode: item.sector_code,
      sectorName: item.sector_name,
      headline: `观察候选 #${item.rank} · ${item.stock_name}`,
      sourcePool: "stock_candidates" as const,
      sourcePoolLabel: CANDIDATE_SOURCE_POOL_LABELS.stock_candidates,
      walkForward: stockWalkForward,
      pattern,
      patternNote,
      distanceToBreakoutPct,
      evidenceBullets,
      evidence,
      counterEvidence: [
        candidateFundamentalCounterEvidence(item),
        "新闻、公告、财报事件尚未进入候选卡。",
        // 措辞避开"实盘"子串：合规测试禁止页面出现任何交易执行类用语。
        "ATR、盘中真实成交顺序和精确涨跌停状态未在当前只读卡片中完整验证。",
      ],
      invalidationRules: [
        `收盘跌破 10EMA ${formatNumber(item.ema10)} 或突破观察位 ${formatNumber(item.breakout_level)} 后需要降级复核。`,
        "所属行业强度跌出前列需要重新复核。",
        "涨跌停状态、停牌状态或数据质量陈旧/缺失时，不得继续解释为有效观察。",
      ],
      liquidityFloorPass: item.liquidity_floor_pass ?? null,
      dailyAmountLabel:
        item.daily_amount != null && Number.isFinite(item.daily_amount)
          ? `日成交 ${formatYi(item.daily_amount, false)}`
          : null,
      rawFields: [
        numericRawField("ema10", "10日均线", item.ema10, formatNumber(item.ema10)),
        numericRawField("ma20", "20日均线", item.ma20, formatNumber(item.ma20)),
        numericRawField("ma60", "60日均线", item.ma60, formatNumber(item.ma60)),
        numericRawField("ma120", "120日均线", item.ma120, formatNumber(item.ma120)),
        numericRawField("abnormal_turnover", "换手观察", item.abnormal_turnover, formatNumber(item.abnormal_turnover, 4)),
        numericRawField("gap_norm", "跳空观察", item.gap_norm, formatNumber(item.gap_norm, 4)),
        numericRawField(
          "breakout_extension_norm",
          "突破延展",
          item.breakout_extension_norm,
          formatNumber(item.breakout_extension_norm, 4),
        ),
        numericRawField("close_strength", "收盘强度", item.close_strength, formatNumber(item.close_strength, 4)),
        numericRawField("factor_score", "因子分", item.factor_score, formatNumber(item.factor_score, 4)),
        numericRawField(
          "factor_overlay_rank",
          "因子叠加排名",
          item.factor_overlay_rank,
          formatNumber(item.factor_overlay_rank, 0),
        ),
        numericRawField("pe", "PE", item.pe, formatNumber(item.pe, 4)),
        numericRawField("pb", "PB", item.pb, formatNumber(item.pb, 4)),
        numericRawField("ps", "PS", item.ps, formatNumber(item.ps, 4)),
        numericRawField("roe", "ROE", item.roe, formatNumber(item.roe, 4)),
        numericRawField("gross_margin", "毛利率", item.gross_margin, formatNumber(item.gross_margin, 4)),
      ],
    };
  });
  if (stockCards.length > 0) return stockCards;
  const freshCards = isStockModulePrimaryExcluded(payload, "fresh_trend_watchlist")
    ? []
    : buildFreshTrendEvidenceCards(payload);
  return freshCards;
}
