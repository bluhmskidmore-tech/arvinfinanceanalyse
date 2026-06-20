import type { LivermoreStrategyPayload, ResultMeta } from "../../../api/contracts";
import {
  localizeMarketDataStatus,
  localizeStockBackendText,
  localizeStockDataFamily,
} from "./stockAnalysisPageModel";
import {
  compactStockText,
  stockStatusLabel,
  stockSupplyBasisLabel,
  stockSupplyFallbackLabel,
  stockSupplyQualityLabel,
  stockSupplyVendorLabel,
} from "./stockAnalysisPageCopy";

export type StockTone = "positive" | "warning" | "negative" | "neutral";
export type CycleLayer = NonNullable<LivermoreStrategyPayload["cycle_rotation_framework"]>["layers"][number];
type CycleLayerView = Omit<CycleLayer, "available_inputs" | "missing_inputs"> & {
  available_inputs: readonly string[];
  missing_inputs: readonly string[];
};

export function eventSourceLabel(source: string) {
  const labels: Record<string, string> = {
    diagnostic: "诊断",
    data_gap: "缺口",
    unsupported: "阻断",
    signal_confluence: "联动",
    risk_exit: "风险",
  };
  return labels[source] ?? source;
}

export function eventLevelLabel(level: string) {
  if (level === "error") return "高";
  if (level === "warning") return "中";
  return "低";
}

export function eventImpactLabel(row: { source: string; impact: string }) {
  if (row.source === "data_gap") return row.impact;
  if (row.source === "unsupported" || row.source === "risk_exit") return outputKeyLabel(row.impact);
  if (row.source === "signal_confluence") return "联动观察";
  return localizeStockDataFamily(row.impact);
}

export function eventNameLabel(row: { source: string; event: string; impact: string }) {
  if (row.source === "data_gap") return stockStatusLabel(row.event);
  if (row.source === "unsupported") return compactStockText(row.event, 20);
  if (row.source === "risk_exit") return compactStockText(row.event, 18);
  if (row.source === "signal_confluence") return "联动诊断";
  if (row.source === "diagnostic") return `${eventImpactLabel(row)}诊断`;
  return compactStockText(row.event.replace(/_/g, " "), 20);
}

export function eventDetailLabel(row: { source: string; detail: string; impact: string }) {
  if (row.source === "diagnostic") return localizeStockBackendText(row.detail, row.impact);
  return row.detail;
}

export function formatSupplyPercent(value: number | null | undefined, digits = 0) {
  if (value == null || !Number.isFinite(value)) return "-";
  return `${(value * 100).toFixed(digits)}%`;
}

export function readinessTone(status: string): StockTone {
  if (status === "ready") return "positive";
  if (status === "partial" || status === "stale") return "warning";
  if (status === "missing" || status === "blocked") return "negative";
  return "neutral";
}

export function gapTone(status: string): StockTone {
  if (status === "ready") return "positive";
  if (status === "partial" || status === "stale") return "warning";
  return "negative";
}

export function buildStatusCounts(rows: Array<{ status: string }>) {
  return rows.reduce<Record<string, number>>((acc, row) => {
    acc[row.status] = (acc[row.status] ?? 0) + 1;
    return acc;
  }, {});
}

export function outputKeyLabel(key: string | null | undefined) {
  const labels: Record<string, string> = {
    market_gate: "市场门控",
    sector_rank: "板块排序",
    stock_candidates: "趋势候选",
    stock_candidate: "趋势候选",
    mean_reversion_candidates: "超跌池",
    factor_screen_candidates: "多因子",
    theme_breakout: "题材观察",
    hybrid_fusion: "融合池",
    risk_exit: "风险退出",
  };
  return key ? (labels[key] ?? "输出待确认") : "待补";
}

export function dataGapFamilyLabel(inputFamily: string | null | undefined) {
  return localizeStockDataFamily(inputFamily);
}

export function cycleInputLabel(input: string | null | undefined) {
  if (!input) return "待补";
  const normalized = input.trim().toLowerCase().replace(/[\s-]+/g, "_");
  const labels: Record<string, string> = {
    market_gate: "市场门控",
    sector_rank: "板块强弱",
    stock_candidates: "趋势候选",
    pmi: "PMI",
    credit_impulse: "信用脉冲",
    profit_cycle: "盈利周期",
    market_flow: "市场流动",
    valuation_support: "估值支撑",
    breadth: "市场宽度",
    limit_up_quality: "涨停质量",
    macro_score: "宏观分",
    price_spread: "价差",
    factor_screen: "多因子",
    factor_screen_candidates: "多因子",
    theme_breakout: "题材观察",
    stock_candidate: "趋势候选",
    hybrid_fusion: "融合池",
    social_text_raw: "社交文本",
    ocr_asr_pipeline: "图文识别",
    bot_spam_detection: "噪声过滤",
    industry_profit: "行业盈利",
    industry_profit_cycle: "行业盈利",
    industry_revenue_cycle: "行业收入",
    turnover_persistence: "换手持续",
    turnover_proxy: "换手代理",
    valuation_percentile_history: "估值分位",
    transaction_cost: "交易成本",
    disclosure_lag: "披露滞后",
    liquidity_floor: "流动性底线",
    risk_exit: "风险退出",
    margin_balance: "两融余额",
    unlock_event_panel: "解禁事件",
    sector_rank_for_regime: "板块强弱",
    fund_flow: "资金流",
    northbound_flow: "北向资金",
    earnings_revision: "业绩修正",
    external_vendor_cycle_feed: "输入待确认",
  };
  return labels[normalized] ?? "输入待确认";
}

export function compactCycleInputs(inputs: readonly string[]) {
  return inputs.map(cycleInputLabel).slice(0, 3).join("、") || "无";
}

export function cycleInputSummary(availableInputs: readonly string[], missingInputs: readonly string[]) {
  const parts = [];
  if (availableInputs.length > 0) {
    parts.push(`已有证据 ${compactCycleInputs(availableInputs)}`);
  }
  if (missingInputs.length > 0) {
    parts.push(`待补 ${compactCycleInputs(missingInputs)}`);
  }
  return parts.join(" · ") || "输入待补";
}

export function cycleLayerTitleLabel(layer: Pick<CycleLayerView, "key" | "title">) {
  const labels: Record<CycleLayer["key"], string> = {
    macro_direction: "宏观方向",
    industry_cycle: "行业景气",
    market_flow: "市场流动",
    valuation_support: "估值支撑",
    execution_constraints: "执行边界",
  };
  return labels[layer.key] ?? layer.title;
}

export function cycleLayerWeightLabel(layer: Pick<CycleLayerView, "weight">) {
  return layer.weight == null ? "边界" : `${Math.round(layer.weight * 100)}%`;
}

export function cycleRuleSummary(layers: readonly CycleLayerView[]) {
  const weighted = layers.filter((layer) => layer.weight != null);
  if (weighted.length === 0) return "权重待补";
  return weighted.map((layer) => `${cycleLayerTitleLabel(layer)} ${cycleLayerWeightLabel(layer)}`).join(" · ");
}

export function cycleCadenceLabel(cadence: string | null | undefined) {
  const value = cadence?.trim();
  if (!value) return "节奏待补";
  const normalized = value.toLowerCase();
  if (normalized.includes("external_vendor") || normalized.includes("external vendor")) return "节奏待确认";
  if (normalized.includes("monthly") && normalized.includes("weekly")) {
    return "月度核心复核 · 周度跟踪";
  }
  if (normalized.includes("monthly")) return "月度复核";
  if (normalized.includes("weekly")) return "周度复核";
  return "节奏待确认";
}

export function cycleGapLabel(gap: string) {
  const [input, rawStatus] = gap.split("(");
  const status = rawStatus?.replace(")", "").trim();
  return `${cycleInputLabel(input)} ${stockStatusLabel(status || "missing")}`;
}

export function cycleConstraintLabel(constraint: string) {
  const industryCap = constraint.match(/industry cap\s+(\d+%)/i);
  if (industryCap) return `行业上限 ${industryCap[1]}`;
  const stockCap = constraint.match(/(?:single\s+)?stock cap\s+(\d+%)/i);
  if (stockCap) return `个股上限 ${stockCap[1]}`;
  if (/exclude st and suspended stocks/i.test(constraint)) return "排除 ST / 停牌";
  if (/monthly core review.*weekly satellite monitoring/i.test(constraint)) return "月度核心复核 · 周度跟踪";
  if (/exclude bottom\s+(\d+%).*liquidity/i.test(constraint)) {
    return `排除低流动性后 ${constraint.match(/bottom\s+(\d+%)/i)?.[1] ?? ""}`.trim();
  }
  if (/require\s+(\d+)\s+trading-day history/i.test(constraint)) {
    return `历史样本不少于 ${constraint.match(/require\s+(\d+)/i)?.[1] ?? "250"} 日`;
  }
  if (/lifecourtscore.*top\s+(\d+%)/i.test(constraint)) {
    return `生命法庭分位前 ${constraint.match(/top\s+(\d+%)/i)?.[1] ?? ""}`.trim();
  }
  if (/pconf.*top\s+(\d+%)/i.test(constraint)) {
    return `价格确认前 ${constraint.match(/top\s+(\d+%)/i)?.[1] ?? ""}`.trim();
  }
  if (/crowd.*below\s+(\d+)/i.test(constraint)) {
    const percentile = constraint.match(/below\s+(\d+)/i)?.[1] ?? "阈值";
    return percentile === "阈值" ? "拥挤度低于阈值" : `拥挤度低于 ${percentile} 分位`;
  }
  if (/hygiene\s*>\s*0/i.test(constraint)) return "数据卫生通过";
  return "约束待确认";
}

export function cycleEvidenceLabel(text: string | null | undefined) {
  const value = text?.trim();
  if (!value) return "证据待补";
  const lower = value.toLowerCase();
  if (lower.includes("external_vendor") || lower.includes("external vendor")) return "证据待确认";
  if (lower.includes("market gate") && lower.includes("pmi") && lower.includes("credit impulse")) {
    return "市场门控已有可用证据；PMI 与信用脉冲待补。";
  }
  if (lower.includes("sector_rank")) return "板块强弱已有可用证据。";
  if (lower.includes("pricespread") || lower.includes("price_spread") || lower.includes("macroscore")) {
    return "价差与宏观分已接入。";
  }
  if (lower.includes("stock candidate review") || lower.includes("choice stock daily observation")) {
    return "候选复核与换手观察已接入。";
  }
  if (lower.includes("factor_screen_candidates") || lower.includes("valuation")) {
    return "多因子与估值支撑已接入。";
  }
  if (lower.includes("risk-exit evidence") || lower.includes("sizing") || lower.includes("liquidity controls")) {
    return "风险退出证据已接入；仓位、成本与流动性回放待补。";
  }
  if (lower.includes("not landed") || lower.includes("missing")) return "证据待确认。";
  if (lower.includes("available")) return "证据已接入。";
  return "证据待确认";
}

export function cycleBoundaryLabel(text: string | null | undefined) {
  const value = text?.trim();
  if (!value) return "边界待补";
  const lower = value.toLowerCase();
  if (lower.includes("lifecourt") || lower.includes("proxy-reconstructed") || lower.includes("influencer")) {
    return "生命法庭层为量化重建口径，原始文本规则尚未完整接入。";
  }
  if (lower.includes("proxy")) return "当前为代理观察口径，需复核后使用。";
  return "边界待确认";
}

export function buildBackendSupplyOverview(
  payload: LivermoreStrategyPayload,
  meta: Partial<ResultMeta> = {},
) {
  const gate = payload.market_gate;
  const readinessRows = payload.rule_readiness ?? [];
  const dataGaps = payload.data_gaps ?? [];
  const unsupportedOutputs = payload.unsupported_outputs ?? [];
  const supportedOutputs = payload.supported_outputs ?? [];
  const readyRuleCount = readinessRows.filter((row) => row.status === "ready").length;
  const notReadyGaps = dataGaps.filter((row) => row.status !== "ready");
  const risk = payload.risk_exit;
  const candidateCount =
    payload.stock_candidates?.candidate_count ??
    payload.hybrid_fusion_candidates?.candidate_count ??
    0;
  const sectorCount = payload.sector_rank?.sector_count ?? payload.sector_rank?.items.length ?? 0;
  const watchCount = risk?.watch_items?.length ?? 0;

  return {
    asOfLabel: payload.as_of_date ?? "日期待补",
    requestedAsOfLabel: payload.requested_as_of_date ?? "默认",
    gateLabel: `门控 ${localizeMarketDataStatus(gate.state)}`,
    exposureLabel: `暴露 ${formatSupplyPercent(gate.exposure)}`,
    conditionLabel: `条件 ${gate.passed_conditions}/${gate.required_conditions}`,
    availableConditionLabel: `可评估 ${gate.available_conditions}`,
    readinessLabel: `就绪 ${readyRuleCount}/${readinessRows.length}`,
    readinessValueLabel: `${readyRuleCount}/${readinessRows.length}`,
    dataGapLabel: `缺口 ${notReadyGaps.length}`,
    dataGapValueLabel: `${notReadyGaps.length}`,
    supportedLabel: `可用 ${supportedOutputs.length}`,
    supportedValueLabel: `${supportedOutputs.length}`,
    unsupportedLabel: `阻断 ${unsupportedOutputs.length}`,
    unsupportedValueLabel: `${unsupportedOutputs.length}`,
    sectorSupplyLabel: `板块 ${sectorCount}`,
    sectorSupplyValueLabel: `${sectorCount}`,
    candidateSupplyLabel: `候选 ${candidateCount}`,
    candidateSupplyValueLabel: `${candidateCount}`,
    riskSupplyLabel: `风险 ${risk?.signal_count ?? 0}`,
    riskSupplyValueLabel: `${risk?.signal_count ?? 0}`,
    riskDetailLabel: `持仓 ${risk?.position_count ?? 0} / 触发 ${risk?.signal_count ?? 0} / 观察 ${watchCount}`,
    qualityLabel: `质量 ${stockSupplyQualityLabel(meta.quality_flag)}`,
    vendorLabel: `通道 ${stockSupplyVendorLabel(meta.vendor_status)}`,
    fallbackLabel: stockSupplyFallbackLabel(meta.fallback_mode),
    basisLabel: stockSupplyBasisLabel(payload.basis),
    strategyName: payload.strategy_name,
    readinessRows,
    dataGapRows: dataGaps,
    supportedOutputs,
    unsupportedOutputs,
    risk,
  };
}
