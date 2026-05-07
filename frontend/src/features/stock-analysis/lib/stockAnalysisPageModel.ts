import type {
  LivermoreSignalConfluencePayload,
  LivermoreStrategyPayload,
} from "../../../api/contracts";

export type StockMarketConditionRow = {
  key: string;
  label: string;
  status: string;
  evidence: string;
};

export type StockMarketStateCard = {
  title: string;
  state: string;
  exposureLabel: string;
  passedLabel: string;
  basisLabel: string;
  warnings: string[];
  conditions: StockMarketConditionRow[];
};

export type StockSectorRow = {
  rank: number;
  sectorCode: string;
  sectorName: string;
  score: string;
  pctChange: string;
  turnover: string;
  amplitude: string;
  constituentCount: number;
};

export type StockCandidateEvidenceCard = {
  rank: number;
  stockCode: string;
  stockName: string;
  sectorName: string;
  headline: string;
  evidence: string[];
  counterEvidence: string[];
  invalidationRules: string[];
};

export type StockRiskExitRow = {
  stockCode: string;
  stockName: string;
  status: "triggered" | "watch";
  latestClose: string;
  exitWatchPrice: string;
  reason: string;
};

function formatNumber(value: number | null | undefined, digits = 2) {
  if (value == null || !Number.isFinite(value)) {
    return "待补";
  }
  return value.toFixed(digits);
}

function formatPercent(value: number | null | undefined, digits = 2) {
  if (value == null || !Number.isFinite(value)) {
    return "待补";
  }
  return `${value.toFixed(digits)}%`;
}

function formatRatioAsPercent(value: number | null | undefined, digits = 0) {
  if (value == null || !Number.isFinite(value)) {
    return "待补";
  }
  return `${(value * 100).toFixed(digits)}%`;
}

function normalizeEvidence(evidence: string[] | string | null | undefined): string[] {
  if (Array.isArray(evidence)) {
    return evidence.filter((item) => item.trim().length > 0);
  }
  if (typeof evidence === "string" && evidence.trim()) {
    return [evidence.trim()];
  }
  return [];
}

function sortedCandidateItems(payload: LivermoreStrategyPayload) {
  return [...(payload.stock_candidates?.items ?? [])].sort((left, right) => left.rank - right.rank);
}

export function buildMarketStateCard(
  payload: LivermoreStrategyPayload,
): StockMarketStateCard {
  const gate = payload.market_gate;
  const warnings = [
    ...payload.diagnostics
      .filter((item) => item.severity !== "info")
      .map((item) => item.message),
    ...payload.data_gaps
      .filter((gap) => gap.status !== "ready")
      .map((gap) => `${gap.input_family} ${gap.status}: ${gap.evidence}`),
  ];

  return {
    title: "市场状态",
    state: gate.state,
    exposureLabel: formatRatioAsPercent(gate.exposure),
    passedLabel: `${gate.passed_conditions} / ${gate.required_conditions} 条件通过`,
    basisLabel: `basis: ${payload.basis}`,
    warnings,
    conditions: gate.conditions.map((condition) => ({
      key: condition.key,
      label: condition.label,
      status: condition.status,
      evidence: condition.evidence,
    })),
  };
}

export function buildSectorRows(payload: LivermoreStrategyPayload): StockSectorRow[] {
  return [...(payload.sector_rank?.items ?? [])]
    .sort((left, right) => left.rank - right.rank)
    .map((item) => ({
      rank: item.rank,
      sectorCode: item.sector_code,
      sectorName: item.sector_name,
      score: formatNumber(item.score, 3),
      pctChange: formatPercent(item.avg_pctchange),
      turnover: formatNumber(item.avg_turn),
      amplitude: formatPercent(item.avg_amplitude),
      constituentCount: item.constituent_count,
    }));
}

export function buildCandidateEvidenceCards(
  payload: LivermoreStrategyPayload,
): StockCandidateEvidenceCard[] {
  return sortedCandidateItems(payload).map((item) => ({
    rank: item.rank,
    stockCode: item.stock_code,
    stockName: item.stock_name,
    sectorName: item.sector_name,
    headline: `观察候选 #${item.rank} · ${item.stock_name}`,
    evidence: [
      `行业排名第 ${item.sector_rank}：${item.sector_name}`,
      `收盘价 ${formatNumber(item.close)}，突破观察位 ${formatNumber(item.breakout_level)}。`,
      `均线结构：MA20 ${formatNumber(item.ma20)} / MA60 ${formatNumber(item.ma60)} / MA120 ${formatNumber(item.ma120)}。`,
      `收盘强度 ${formatRatioAsPercent(item.close_strength, 2)}，换手放大观察值 ${formatNumber(item.abnormal_turnover, 3)}。`,
      `10EMA 失效观察：当前 10EMA ${formatNumber(item.ema10)}，用于复核是否降级观察。`,
    ],
    counterEvidence: [
      "基本面与估值证据未接入，不参与当前候选排序。",
      "新闻、公告、财报事件尚未进入候选卡。",
      "ATR、真实盘中成交顺序和精确涨跌停状态未在当前只读卡片中完整验证。",
    ],
    invalidationRules: [
      `收盘跌破 10EMA ${formatNumber(item.ema10)} 或突破观察位 ${formatNumber(item.breakout_level)} 后需要降级复核。`,
      "所属行业强度跌出前列需要重新复核。",
      "涨跌停状态、停牌状态或数据质量为 stale / missing 时，不得继续解释为有效观察。",
    ],
  }));
}

export function buildRiskExitRows(
  payload: LivermoreStrategyPayload,
  confluence?: LivermoreSignalConfluencePayload | null,
): StockRiskExitRow[] {
  const rows: StockRiskExitRow[] = [];
  const seen = new Set<string>();

  for (const item of payload.risk_exit?.items ?? []) {
    const key = `${item.stock_code}:triggered`;
    seen.add(key);
    rows.push({
      stockCode: item.stock_code,
      stockName: item.stock_name,
      status: "triggered",
      latestClose: formatNumber(item.latest_close),
      exitWatchPrice: formatNumber(item.latest_ema10),
      reason: `触发复核：${item.reason}`,
    });
  }

  for (const item of payload.risk_exit?.watch_items ?? []) {
    const status = item.triggered ? "triggered" : "watch";
    const key = `${item.stock_code}:${status}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    rows.push({
      stockCode: item.stock_code,
      stockName: item.stock_name,
      status,
      latestClose: formatNumber(item.latest_close),
      exitWatchPrice: formatNumber(item.exit_watch_price),
      reason: status === "triggered" ? "触发复核：跌破退出观察价" : "观察中：接近退出观察价",
    });
  }

  for (const item of confluence?.exit_observations ?? []) {
    if (!item.stock_code) {
      continue;
    }
    const status = item.action === "exit_triggered" || item.triggered ? "triggered" : "watch";
    const key = `${item.stock_code}:${status}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    rows.push({
      stockCode: item.stock_code,
      stockName: item.stock_name ?? item.stock_code,
      status,
      latestClose: formatNumber(item.current_price),
      exitWatchPrice: formatNumber(item.exit_watch_price),
      reason:
        normalizeEvidence(item.evidence)[0] ??
        (status === "triggered" ? "触发复核：联动观察命中" : "观察中：联动观察"),
    });
  }

  return rows;
}

export function buildDataBoundaryNotes(payload: LivermoreStrategyPayload): string[] {
  const notes = [
    `basis: ${payload.basis}`,
    `strategy: ${payload.strategy_name}`,
  ];
  for (const diag of payload.diagnostics) {
    notes.push(`${diag.severity} [${diag.code}]: ${diag.message}`);
  }

  if (payload.as_of_date) {
    notes.push(`as_of_date: ${payload.as_of_date}`);
  }
  if (payload.sector_rank?.formula_version) {
    notes.push(`sector_rank formula: ${payload.sector_rank.formula_version}`);
  }
  if (payload.stock_candidates?.formula_version) {
    notes.push(`stock_candidates formula: ${payload.stock_candidates.formula_version}`);
  }
  if (payload.risk_exit?.formula_version) {
    notes.push(`risk_exit formula: ${payload.risk_exit.formula_version}`);
  }
  for (const gap of payload.data_gaps) {
    notes.push(`${gap.input_family} ${gap.status}: ${gap.evidence}`);
  }
  for (const output of payload.unsupported_outputs) {
    notes.push(`${output.key} unsupported: ${output.reason}`);
  }
  notes.push(`supported_outputs: ${payload.supported_outputs.join(", ") || "none"}`);

  return notes;
}
