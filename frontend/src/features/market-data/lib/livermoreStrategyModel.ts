import type {
  ApiEnvelope,
  ExternalDataFreshnessTier,
  LivermoreConditionStatus,
  LivermoreDiagnosticSeverity,
  LivermoreMarketGate,
  LivermoreOutputKey,
  LivermorePositionSizeHintItem,
  LivermoreRuleReadinessKey,
  LivermoreRuleReadinessStatus,
  LivermoreStrategyPayload,
  ResultMeta,
} from "../../../api/contracts";

export type MarketGateMacroDisclosure = {
  adjustmentLabel: string | null;
  cycleStateLabel: string | null;
  statusMarker: string | null;
  lagLabel: string | null;
};

const marketGateCycleStateLabels: Record<string, string> = {
  recession: "衰退",
  contraction: "收缩",
  neutral: "中性",
  expansion: "扩张",
};

const marketGateMacroStatusMarkers: Record<string, string> = {
  missing: "宏观背景缺失",
  expired: "宏观背景过期",
  look_ahead: "宏观背景前视",
};

export type MarketGateExposureFormat = "decimal" | "percent";

function formatMarketGateExposureRatio(
  value: number | null | undefined,
  format: MarketGateExposureFormat = "decimal",
): string {
  if (value == null || !Number.isFinite(value)) {
    return "—";
  }
  if (format === "percent") {
    return `${Math.round(value * 100)}%`;
  }
  return value.toFixed(2);
}

export function hasMarketGateMacroDisclosure(
  gate: Pick<LivermoreMarketGate, "macro_context" | "macro_overlay" | "exposure_raw" | "formula_version">,
): boolean {
  return (
    gate.macro_context != null ||
    gate.macro_overlay != null ||
    gate.exposure_raw != null ||
    gate.formula_version != null
  );
}

export function buildMarketGateMacroDisclosure(
  gate: LivermoreMarketGate,
  options?: { exposureFormat?: MarketGateExposureFormat },
): MarketGateMacroDisclosure | null {
  if (!hasMarketGateMacroDisclosure(gate)) {
    return null;
  }

  const exposureFormat = options?.exposureFormat ?? "decimal";
  const macroContext = gate.macro_context;
  const macroOverlay = gate.macro_overlay;
  const status = String(macroContext?.status ?? "").trim().toLowerCase();

  let adjustmentLabel: string | null = null;
  if (macroOverlay?.applied) {
    const raw = macroOverlay.exposure_raw ?? gate.exposure_raw ?? gate.exposure;
    const adjusted = macroOverlay.exposure_adjusted ?? gate.exposure;
    adjustmentLabel = `宏观调节 ${formatMarketGateExposureRatio(raw, exposureFormat)}→${formatMarketGateExposureRatio(adjusted, exposureFormat)}`;
  }

  let cycleStateLabel: string | null = null;
  if (macroOverlay?.applied && macroContext?.cycle_state) {
    const cycleKey = String(macroContext.cycle_state).trim().toLowerCase();
    cycleStateLabel = marketGateCycleStateLabels[cycleKey] ?? null;
  }

  let statusMarker: string | null = null;
  if (status === "missing" || status === "expired" || status === "look_ahead") {
    statusMarker = marketGateMacroStatusMarkers[status] ?? null;
  }

  let lagLabel: string | null = null;
  if (status === "ready" && typeof macroContext?.lag_days === "number" && Number.isFinite(macroContext.lag_days)) {
    lagLabel = `宏观数据滞后 ${macroContext.lag_days} 天`;
  }

  return {
    adjustmentLabel,
    cycleStateLabel,
    statusMarker,
    lagLabel,
  };
}

export function formatMarketGateMacroDisclosureDetail(
  disclosure: MarketGateMacroDisclosure | null | undefined,
): string | null {
  if (!disclosure) {
    return null;
  }
  const parts: string[] = [];
  if (disclosure.adjustmentLabel) {
    parts.push(
      disclosure.cycleStateLabel
        ? `${disclosure.adjustmentLabel} · ${disclosure.cycleStateLabel}`
        : disclosure.adjustmentLabel,
    );
  }
  if (disclosure.statusMarker) {
    parts.push(disclosure.statusMarker);
  }
  if (disclosure.lagLabel) {
    parts.push(disclosure.lagLabel);
  }
  return parts.length > 0 ? parts.join(" · ") : null;
}

export type LivermoreStrategyModel = {
  strategyName: string;
  asOfDate: string | null;
  requestedAsOfDate: string | null;
  statusNotes: string[];
  marketGate: {
    state: LivermoreStrategyPayload["market_gate"]["state"];
    exposure: number;
    exposureDisplay: string;
    passedConditions: number;
    availableConditions: number;
    requiredConditions: number;
    conditions: Array<{
      key: string;
      label: string;
      status: LivermoreConditionStatus;
      statusLabel: string;
      evidence: string;
      sourceSeriesId: string | null;
    }>;
    macroDisclosure: MarketGateMacroDisclosure | null;
  };
  ruleBlocks: Array<{
    key: LivermoreRuleReadinessKey;
    title: string;
    status: LivermoreRuleReadinessStatus;
    statusLabel: string;
    summary: string;
    requiredInputs: string[];
    missingInputs: string[];
  }>;
  diagnostics: Array<{
    severity: LivermoreDiagnosticSeverity;
    severityLabel: string;
    code: string;
    message: string;
    inputFamily: string | null;
  }>;
  dataGaps: Array<{
    inputFamily: string;
    status: LivermoreStrategyPayload["data_gaps"][number]["status"];
    statusLabel: string;
    evidence: string;
    input: string | null;
    businessDate: string | null;
    ageDays: number | null;
    tier: ExternalDataFreshnessTier | null;
    freshnessLabel: string | null;
  }>;
  supportedOutputs: Array<{
    key: LivermoreOutputKey;
    label: string;
  }>;
  sectorRank: null | {
    formulaVersion: string;
    isProvisional: boolean;
    items: Array<{
      rank: number;
      sectorCode: string;
      sectorName: string;
      score: string;
      constituentCount: number;
    }>;
  };
  stockCandidates: null | {
    formulaVersion: string;
    marketState: LivermoreStrategyPayload["market_gate"]["state"];
    factorMissingCount: number | null;
    positionSizeHint: null | {
      policyVersion: string;
      coverageDegraded: boolean;
      coverageWarning: string | null;
      gateExposureNote: string;
      shadowNote: string;
    };
    items: Array<{
      rank: number;
      stockCode: string;
      stockName: string;
      sectorName: string;
      sectorRank: number;
      close: string;
      breakoutLevel: string;
      ma20: string;
      ma60: string;
      ma120: string;
      entryTrigger: string;
      pullbackWatch: string;
      defenseLine: string;
      closeStrength: string;
      gapNorm: string;
      abnormalTurnover: string;
      sizeHint: string | null;
    }>;
  };
  meanReversionCandidates: null | {
    formulaVersion: string;
    marketState: LivermoreStrategyPayload["market_gate"]["state"];
    items: Array<{
      rank: number;
      stockCode: string;
      stockName: string;
      sectorName: string;
      close: string;
      score: string;
    }>;
  };
  factorScreenCandidates: null | {
    formulaVersion: string;
    marketState: LivermoreStrategyPayload["market_gate"]["state"];
    coverageNote: string;
    items: Array<{
      rank: number;
      stockCode: string;
      stockName: string;
      sectorName: string;
      score: string;
    }>;
  };
  themeBreakout: null | {
    formulaVersion: string;
    isProxy: boolean;
    items: Array<{
      rank: number;
      themeName: string;
      parentSectorName: string;
      reason: string;
    }>;
  };
  riskExit: null | {
    formulaVersion: string;
    positionCount: number;
    signalCount: number;
    items: Array<{
      stockCode: string;
      stockName: string;
      reason: string;
      entryCost: string;
      entryCostAvailable: boolean;
      barsSinceEntry: number;
      latestClose: string;
      latestEma10: string;
    }>;
  };
  unsupportedOutputs: Array<{
    key: LivermoreOutputKey;
    label: string;
    reason: string;
  }>;
};

const outputLabels: Record<LivermoreOutputKey, string> = {
  hybrid_fusion: "hybrid fusion",
  market_gate: "市场门控",
  sector_rank: "板块排序",
  stock_candidates: "个股候选",
  uptrend_momentum_candidates: "上升趋势",
  fresh_trend_watchlist: "新趋势观察",
  mean_reversion_candidates: "超跌反弹观察池",
  factor_screen_candidates: "多因子选股",
  theme_breakout: "题材突变",
  risk_exit: "风险退出",
};

const conditionStatusLabels: Record<LivermoreConditionStatus, string> = {
  pass: "通过",
  fail: "未通过",
  missing: "缺数据",
  stale: "已陈旧",
};

const readinessStatusLabels: Record<LivermoreRuleReadinessStatus, string> = {
  ready: "可用",
  partial: "部分",
  missing: "缺数据",
  blocked: "受阻",
  stale: "已陈旧",
};

const diagnosticSeverityLabels: Record<LivermoreDiagnosticSeverity, string> = {
  info: "提示",
  warning: "预警",
  error: "错误",
};

const gapStatusLabels: Record<LivermoreStrategyPayload["data_gaps"][number]["status"], string> = {
  missing: "缺失",
  partial: "部分",
  stale: "陈旧",
  ready: "就绪",
  look_ahead: "前视风险",
};

function fallbackLabel(value: ResultMeta["fallback_mode"]) {
  if (value === "latest_snapshot") {
    return "最新快照降级";
  }
  return value;
}

function buildStatusNotes(
  payload: LivermoreStrategyPayload,
  meta: ResultMeta,
): string[] {
  const notes: string[] = [];
  if (
    payload.requested_as_of_date &&
    payload.as_of_date &&
    payload.requested_as_of_date !== payload.as_of_date
  ) {
    notes.push(
      `请求日期 ${payload.requested_as_of_date}，解析结果日期 ${payload.as_of_date}。`,
    );
  }
  if (payload.market_gate.state === "STALE" || meta.quality_flag === "stale") {
    notes.push("当前结果带有陈旧数据标记。");
  }
  if (meta.fallback_mode !== "none") {
    notes.push(`当前结果使用${fallbackLabel(meta.fallback_mode)}。`);
  }
  if (meta.quality_flag !== "ok") {
    for (const diagnostic of payload.diagnostics) {
      if (
        diagnostic.code === "LIVERMORE_INPUT_FRESHNESS_DEGRADED" &&
        diagnostic.message &&
        !notes.includes(diagnostic.message)
      ) {
        notes.push(diagnostic.message);
      }
    }
  }
  return notes;
}

function formatMetric(value: number | null | undefined, digits = 3) {
  return value == null ? "—" : value.toFixed(digits);
}

function formatPositionSizeHintLabel(
  hint: LivermorePositionSizeHintItem | undefined,
): string | null {
  if (!hint || typeof hint.raw_weight !== "number" || !Number.isFinite(hint.raw_weight)) {
    return null;
  }
  const parts = [`≤ ${(hint.raw_weight * 100).toFixed(1)}%`];
  parts.push(hint.stop_basis === "fallback" ? "fallback止损" : "EMA10止损");
  if (hint.capped) {
    parts.push("已触单票上限");
  }
  return parts.join(" · ");
}

function formatFreshnessLabel(gap: LivermoreStrategyPayload["data_gaps"][number]) {
  const hasFreshness =
    gap.input != null ||
    gap.business_date != null ||
    gap.age_days != null ||
    gap.tier != null;
  if (!hasFreshness) {
    return null;
  }
  const input = gap.input ?? gap.input_family;
  const businessDate = gap.business_date ?? "未知";
  const age = typeof gap.age_days === "number" ? `T+${gap.age_days}` : "T+未知";
  const tier = gap.tier ?? "unknown";
  return `输入 ${input} · 日期 ${businessDate} · ${age} · ${tier}`;
}

export function buildLivermoreStrategyModel(input: {
  envelope: ApiEnvelope<LivermoreStrategyPayload>;
}): LivermoreStrategyModel {
  const payload = input.envelope.result;
  const meta = input.envelope.result_meta;

  return {
    strategyName: payload.strategy_name,
    asOfDate: payload.as_of_date,
    requestedAsOfDate: payload.requested_as_of_date,
    statusNotes: buildStatusNotes(payload, meta),
    marketGate: {
      state: payload.market_gate.state,
      exposure: payload.market_gate.exposure,
      // Align with stock-analysis: exposure is a 0–1 ratio (passed/4).
      exposureDisplay: formatMarketGateExposureRatio(payload.market_gate.exposure, "percent"),
      passedConditions: payload.market_gate.passed_conditions,
      availableConditions: payload.market_gate.available_conditions,
      requiredConditions: payload.market_gate.required_conditions,
      conditions: payload.market_gate.conditions.map((condition) => ({
        key: condition.key,
        label: condition.label,
        status: condition.status,
        statusLabel: conditionStatusLabels[condition.status],
        evidence: condition.evidence,
        sourceSeriesId: condition.source_series_id ?? null,
      })),
      macroDisclosure: buildMarketGateMacroDisclosure(payload.market_gate, {
        exposureFormat: "percent",
      }),
    },
    ruleBlocks: payload.rule_readiness.map((block) => ({
      key: block.key,
      title: block.title,
      status: block.status,
      statusLabel: readinessStatusLabels[block.status],
      summary: block.summary,
      requiredInputs: block.required_inputs,
      missingInputs: block.missing_inputs,
    })),
    diagnostics: payload.diagnostics.map((item) => ({
      severity: item.severity,
      severityLabel: diagnosticSeverityLabels[item.severity],
      code: item.code,
      message: item.message,
      inputFamily: item.input_family ?? null,
    })),
    dataGaps: payload.data_gaps.map((gap) => ({
      inputFamily: gap.input_family,
      status: gap.status,
      statusLabel: gapStatusLabels[gap.status],
      evidence: gap.evidence,
      input: gap.input ?? null,
      businessDate: gap.business_date ?? null,
      ageDays: gap.age_days ?? null,
      tier: gap.tier ?? null,
      freshnessLabel: formatFreshnessLabel(gap),
    })),
    supportedOutputs: payload.supported_outputs.map((key) => ({
      key,
      label: outputLabels[key],
    })),
    sectorRank: payload.sector_rank
      ? {
          formulaVersion: payload.sector_rank.formula_version,
          isProvisional: payload.sector_rank.is_provisional,
          items: payload.sector_rank.items.map((item) => ({
            rank: item.rank,
            sectorCode: item.sector_code,
            sectorName: item.sector_name,
            score: formatMetric(item.score),
            constituentCount: item.constituent_count,
          })),
        }
      : null,
    stockCandidates: payload.stock_candidates
      ? (() => {
          const rawHint = payload.stock_candidates.position_size_hint ?? null;
          const hintByStockCode = new Map(
            (rawHint?.items ?? []).map((item) => [item.stock_code, item]),
          );
          return {
            formulaVersion: payload.stock_candidates.formula_version,
            marketState: payload.stock_candidates.market_state,
            factorMissingCount:
              payload.stock_candidates.fundamental_overlay?.factor_missing_count ?? null,
            positionSizeHint: rawHint
              ? {
                  policyVersion: rawHint.policy_version,
                  coverageDegraded: rawHint.coverage_degraded === true,
                  coverageWarning: rawHint.coverage_warning ?? null,
                  gateExposureNote: rawHint.gate_exposure_note,
                  shadowNote: rawHint.equal_weight_shadow_note,
                }
              : null,
            items: payload.stock_candidates.items.map((item) => ({
              rank: item.rank,
              stockCode: item.stock_code,
              stockName: item.stock_name,
              sectorName: item.sector_name,
              sectorRank: item.sector_rank,
              close: formatMetric(item.close),
              breakoutLevel: formatMetric(item.breakout_level),
              ma20: formatMetric(item.ma20),
              ma60: formatMetric(item.ma60),
              ma120: formatMetric(item.ma120),
              entryTrigger: formatMetric(item.breakout_level),
              pullbackWatch: formatMetric(item.ma20),
              defenseLine: formatMetric(item.ma60),
              closeStrength: formatMetric(item.close_strength),
              gapNorm: formatMetric(item.gap_norm),
              abnormalTurnover: formatMetric(item.abnormal_turnover),
              sizeHint: formatPositionSizeHintLabel(hintByStockCode.get(item.stock_code)),
            })),
          };
        })()
      : null,
    meanReversionCandidates: payload.mean_reversion_candidates
      ? {
          formulaVersion: payload.mean_reversion_candidates.formula_version,
          marketState: payload.mean_reversion_candidates.market_state,
          items: payload.mean_reversion_candidates.items.map((item) => ({
            rank: item.rank,
            stockCode: item.stock_code,
            stockName: item.stock_name,
            sectorName: item.sector_name,
            close: formatMetric(item.close),
            score: formatMetric(item.score),
          })),
        }
      : null,
    factorScreenCandidates: payload.factor_screen_candidates
      ? {
          formulaVersion: payload.factor_screen_candidates.formula_version,
          marketState: payload.factor_screen_candidates.market_state,
          coverageNote: payload.factor_screen_candidates.coverage_note,
          items: payload.factor_screen_candidates.items.map((item) => ({
            rank: item.rank,
            stockCode: item.stock_code,
            stockName: item.stock_name,
            sectorName: item.sector_name,
            score: formatMetric(item.score),
          })),
        }
      : null,
    themeBreakout: payload.theme_breakout
      ? {
          formulaVersion: payload.theme_breakout.formula_version,
          isProxy: payload.theme_breakout.is_proxy,
          items: payload.theme_breakout.items.map((item) => ({
            rank: item.rank,
            themeName: item.theme_name,
            parentSectorName: item.parent_sector_name,
            reason: item.reason,
          })),
        }
      : null,
    riskExit: payload.risk_exit
      ? {
          formulaVersion: payload.risk_exit.formula_version,
          positionCount: payload.risk_exit.position_count,
          signalCount: payload.risk_exit.signal_count,
          items: payload.risk_exit.items.map((item) => ({
            stockCode: item.stock_code,
            stockName: item.stock_name,
            reason: item.reason,
            entryCost: formatMetric(item.entry_cost),
            entryCostAvailable: item.entry_cost_available ?? item.entry_cost != null,
            barsSinceEntry: item.bars_since_entry,
            latestClose: formatMetric(item.latest_close),
            latestEma10: formatMetric(item.latest_ema10),
          })),
        }
      : null,
    unsupportedOutputs: payload.unsupported_outputs.map((item) => ({
      key: item.key,
      label: outputLabels[item.key],
      reason: item.reason,
    })),
  };
}
