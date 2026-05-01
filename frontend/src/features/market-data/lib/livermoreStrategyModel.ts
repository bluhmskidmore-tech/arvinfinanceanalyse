import type {
  ApiEnvelope,
  LivermoreConditionStatus,
  LivermoreDiagnosticSeverity,
  LivermoreOutputKey,
  LivermoreRuleReadinessKey,
  LivermoreRuleReadinessStatus,
  LivermoreStrategyPayload,
  ResultMeta,
} from "../../../api/contracts";

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
    items: Array<{
      rank: number;
      stockCode: string;
      stockName: string;
      sectorName: string;
      sectorRank: number;
      breakoutLevel: string;
      closeStrength: string;
      gapNorm: string;
      abnormalTurnover: string;
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
  market_gate: "市场门控",
  sector_rank: "板块排序",
  stock_candidates: "个股候选",
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
  return notes;
}

function formatMetric(value: number, digits = 3) {
  return value.toFixed(digits);
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
      exposureDisplay: payload.market_gate.exposure.toFixed(1),
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
      ? {
          formulaVersion: payload.stock_candidates.formula_version,
          marketState: payload.stock_candidates.market_state,
          items: payload.stock_candidates.items.map((item) => ({
            rank: item.rank,
            stockCode: item.stock_code,
            stockName: item.stock_name,
            sectorName: item.sector_name,
            sectorRank: item.sector_rank,
            breakoutLevel: formatMetric(item.breakout_level),
            closeStrength: formatMetric(item.close_strength),
            gapNorm: formatMetric(item.gap_norm),
            abnormalTurnover: formatMetric(item.abnormal_turnover),
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
