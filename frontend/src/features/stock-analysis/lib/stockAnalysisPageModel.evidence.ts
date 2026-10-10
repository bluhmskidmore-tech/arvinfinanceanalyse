// Data boundary, evidence status, endpoint evidence, observation closure and event monitor for the stock-analysis page model.
import type { LivermoreSignalConfluencePayload, LivermoreStrategyPayload } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import type {
  StockAnalysisEventMonitorRow,
  StockAnalysisEvidenceStatusItem,
  StockClosedLoopTone,
  StockCycleMacroLayerSummary,
  StockDataBoundarySummary,
  StockEndpointEvidenceInput,
  StockEndpointEvidenceItem,
  StockEndpointEvidenceMeta,
  StockObservationClosureReason,
  StockObservationClosureReasonInput,
  StockObservationClosureReasonKind,
  StockObservationClosureSummary,
  StockThemeTaxonomyGapSummary,
  StockViewModelMeta,
} from "./stockAnalysisPageModel.types";
import { formatNumber } from "./stockAnalysisPageModel.format";
import {
  localizeBasisLabel,
  localizeDataGapStatus,
  localizeFallbackMode,
  localizeMetaQualityFlag,
  localizeMetaVendorStatus,
  localizeStockBackendText,
  localizeStockDataFamily,
} from "./stockAnalysisPageModel.localize";
import {
  actionableDiagnostics,
  actionableUnsupportedOutputs,
  activeDataGaps,
  isActionableLivermoreUnsupportedOutput,
  normalizeEvidence,
} from "./stockAnalysisPageModel.shared";
import { buildRiskExitRows } from "./stockAnalysisPageModel.risk";

function formatFreshnessLabel(meta: StockViewModelMeta = {}): string {
  const quality = meta.quality_flag ?? "pending";
  const vendor = meta.vendor_status ?? "pending";
  const fallback = meta.fallback_mode && meta.fallback_mode !== "none" ? ` / ${localizeFallbackMode(meta.fallback_mode)}` : "";
  return `新鲜度 ${localizeMetaQualityFlag(quality)} / ${localizeMetaVendorStatus(vendor)}${fallback}`;
}

export function sectorRankFormulaGovernanceLabel(
  sectorRank: LivermoreStrategyPayload["sector_rank"] | null | undefined,
): string | undefined {
  if (!sectorRank) return undefined;
  const status = String(sectorRank.formula_status ?? "").trim().toLowerCase();
  const statusLabel =
    status === "signed_off"
      ? "规则已签核"
      : status === "review_pending" || sectorRank.is_provisional
        ? "规则待签核"
        : "规则待确认";
  const formulaVersion = sectorRank.formula_version || "公式版本待补";
  return `${statusLabel} / ${formulaVersion}`;
}

const MACRO_GAP_FAMILIES = new Set(["pmi", "credit_impulse", "macro_score", "price_spread"]);

function isMacroGapFamily(inputFamily: string): boolean {
  return MACRO_GAP_FAMILIES.has(inputFamily.trim().toLowerCase());
}

function macroGapLabels(payload: LivermoreStrategyPayload): string[] {
  return payload.data_gaps
    .filter((gap) => gap.status !== "ready" && isMacroGapFamily(gap.input_family))
    .map((gap) => `${localizeStockDataFamily(gap.input_family)} ${macroGapStatusLabel(gap.status)}`);
}

function macroGapStatusLabel(status: string | null | undefined): string {
  const normalized = (status ?? "").trim().toLowerCase();
  const labels: Record<string, string> = {
    blocked: "阻断",
    missing: "缺失",
    partial: "部分",
    stale: "陈旧",
  };
  return labels[normalized] ?? "状态待确认";
}

export function buildCycleMacroLayerSummary(
  payload: LivermoreStrategyPayload,
): StockCycleMacroLayerSummary | null {
  const macroLayer = payload.cycle_rotation_framework?.macro_layer;
  if (!macroLayer) {
    return null;
  }

  const hybridFormula = payload.hybrid_fusion_candidates?.formula_version?.trim() || "";
  const formulaVersionLabel =
    hybridFormula || "rv_hybrid_fusion_candidates_v6";
  const macroScoreLabel =
    macroLayer.macro_score == null ? "待补" : formatNumber(macroLayer.macro_score, 4);
  const availableInputs = macroLayer.available_inputs ?? [];
  const missingInputs = macroLayer.missing_inputs ?? [];
  const macroGapLabelsList = macroGapLabels(payload);
  const ready = macroLayer.ready === true;

  let statusLabel: StockCycleMacroLayerSummary["statusLabel"];
  let tone: StockClosedLoopTone;
  if (ready) {
    statusLabel = "已落地";
    tone = "positive";
  } else if (availableInputs.length > 0) {
    statusLabel = "部分就绪";
    tone = "warning";
  } else {
    statusLabel = "待补";
    tone = "negative";
  }

  const detailParts = [
    `可用 ${availableInputs.map(localizeStockDataFamily).join("、") || EM_DASH}`,
    `缺失 ${missingInputs.map(localizeStockDataFamily).join("、") || EM_DASH}`,
  ];
  if (macroGapLabelsList.length > 0) {
    detailParts.push(`缺口 ${macroGapLabelsList.join(" / ")}`);
  }

  return {
    statusLabel,
    tone,
    macroScoreLabel,
    formulaVersionLabel,
    evidence: macroLayer.evidence?.trim() || "宏观层证据待补",
    availableInputs,
    missingInputs,
    macroGapLabels: macroGapLabelsList,
    detailLabel: detailParts.join(" · "),
  };
}

export function buildDataBoundarySummary(
  payload: LivermoreStrategyPayload,
  meta: StockViewModelMeta = {},
): StockDataBoundarySummary {
  const diagnostics = actionableDiagnostics(payload);
  const dataGaps = activeDataGaps(payload);
  const unsupported = actionableUnsupportedOutputs(payload);
  const topMessages = [
    ...diagnostics.map((item) => localizeStockBackendText(item.message, item.input_family)),
    ...dataGaps.map(
      (gap) =>
        `${localizeStockDataFamily(gap.input_family)} ${localizeDataGapStatus(gap.status)}：${localizeStockBackendText(
          gap.evidence,
          gap.input_family,
        )}`,
    ),
    ...unsupported.map(
      (item) => `${localizeStockDataFamily(item.key)}：${localizeStockBackendText(item.reason, item.key)}`,
    ),
  ].slice(0, 4);
  const freshnessLabel = formatFreshnessLabel(meta);
  const boundaryCount = diagnostics.length + dataGaps.length + unsupported.length;

  return {
    boundaryCount,
    diagnosticsCount: diagnostics.length,
    dataGapCount: dataGaps.length,
    unsupportedCount: unsupported.length,
    freshnessLabel,
    summaryLabel: boundaryCount > 0 ? `${boundaryCount} 条边界` : "边界清晰",
    detailLabel: `诊断 ${diagnostics.length} / 缺口 ${dataGaps.length} / 阻断 ${unsupported.length} / ${freshnessLabel}`,
    topMessages,
  };
}

function isMetaBoundary(meta: StockViewModelMeta = {}): boolean {
  const quality = meta.quality_flag ?? "pending";
  const vendor = meta.vendor_status ?? "pending";
  const fallback = meta.fallback_mode ?? "none";
  return quality !== "ok" || vendor !== "ok" || fallback !== "none";
}

function evidenceToneForStatus(status: string): StockClosedLoopTone {
  const normalized = status.toLowerCase();
  if (normalized === "ok" || normalized === "complete" || normalized === "analytical") {
    return "positive";
  }
  if (normalized === "error" || normalized === "blocked") {
    return "negative";
  }
  if (
    normalized === "warning" ||
    normalized === "degraded" ||
    normalized === "stale" ||
    normalized === "pending" ||
    normalized === "missing" ||
    normalized === "fallback"
  ) {
    return "warning";
  }
  return "neutral";
}

function eventLevelFromSeverity(severity: string): StockAnalysisEventMonitorRow["level"] {
  return severity === "error" ? "error" : severity === "warning" ? "warning" : "info";
}

function eventToneLevel(tone: StockClosedLoopTone): StockAnalysisEventMonitorRow["level"] {
  return tone === "negative" ? "error" : tone === "positive" ? "info" : "warning";
}

function detailFromEventEvidence(evidence: string[] | string | null | undefined, fallback: string): string {
  return normalizeEvidence(evidence)[0] ?? fallback;
}

export function buildStockAnalysisEvidenceStatus(
  payload: LivermoreStrategyPayload,
  meta: StockViewModelMeta = {},
): StockAnalysisEvidenceStatusItem[] {
  const boundarySummary = buildDataBoundarySummary(payload, meta);
  const quality = meta.quality_flag ?? "pending";
  const vendor = meta.vendor_status ?? "pending";
  const fallback = meta.fallback_mode ?? "none";
  const qualityTone = isMetaBoundary(meta) ? "warning" : "positive";
  const lineageReady = Boolean(meta.source_version);
  const ruleReady = Boolean(meta.rule_version);
  const basisLabel = localizeBasisLabel(payload.basis);

  return [
    {
      key: "as-of-date",
      label: "数据日期",
      statusLabel: payload.as_of_date ?? "日期待补",
      tone: payload.as_of_date ? "positive" : "warning",
      detail: payload.requested_as_of_date ? `请求日期 ${payload.requested_as_of_date}` : "使用最新可用交易日",
    },
    {
      key: "lineage",
      label: "来源状态",
      statusLabel: lineageReady ? "可追踪" : "待确认",
      tone: lineageReady ? "positive" : "warning",
      detail: lineageReady ? "完整追踪见诊断" : "来源追踪待确认",
    },
    {
      key: "basis",
      label: "计算口径",
      statusLabel: basisLabel,
      tone: evidenceToneForStatus(payload.basis ?? "pending"),
      detail: basisLabel,
    },
    {
      key: "rule-version",
      label: "规则版本",
      statusLabel: ruleReady ? "规则已加载" : "规则待确认",
      tone: ruleReady ? "positive" : "warning",
      detail: `可用 ${payload.supported_outputs.length} / 阻断 ${payload.unsupported_outputs.length}`,
    },
    {
      key: "quality",
      label: "数据质量",
      statusLabel: qualityTone === "positive" ? "正常" : "需复核",
      tone: qualityTone,
      detail: stockEvidenceBusinessQualityLabel(quality, vendor, fallback),
    },
    {
      key: "exceptions",
      label: "例外状态",
      statusLabel: boundarySummary.boundaryCount > 0 ? `${boundarySummary.boundaryCount} 条边界` : "无边界",
      tone: boundarySummary.boundaryCount > 0 ? "warning" : "positive",
      detail: boundarySummary.detailLabel,
    },
  ];
}

function compactEndpointTrace(value: string | null | undefined): string {
  const trace = value?.trim();
  if (!trace) return "链路待补";
  if (trace.length <= 28) return `链路：${trace}`;
  return `链路：${trace.slice(0, 10)}...${trace.slice(-8)}`;
}

function stockEvidenceBusinessQualityLabel(
  quality: string | null | undefined,
  vendor: string | null | undefined,
  fallback: string | null | undefined,
): string {
  if (quality === "error" || vendor === "vendor_unavailable") return "不可用";
  if (fallback && fallback !== "none") return "数据延迟";
  if (quality === "stale" || vendor === "vendor_stale") return "数据延迟";
  if (quality === "ok" && vendor === "ok") return "数据正常";
  return "部分缺失";
}

function normalizeEndpointCount(value: number | null | undefined): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return Math.max(0, Math.trunc(value));
}

function firstNonEmptyText(...values: Array<string | null | undefined>): string | null {
  for (const value of values) {
    const normalized = value?.trim();
    if (normalized) return normalized;
  }
  return null;
}

function endpointDateLabel(input: StockEndpointEvidenceInput): string {
  const asOfDate = firstNonEmptyText(
    input.asOfDate,
    input.meta?.as_of_date,
    input.meta?.resolved_report_date,
  );
  if (asOfDate) return `日期：${asOfDate}`;

  const snapshotFrom = firstNonEmptyText(input.snapshotFrom, input.meta?.requested_report_date);
  const snapshotTo = firstNonEmptyText(input.snapshotTo, input.meta?.resolved_report_date);
  if (snapshotFrom && snapshotTo) return `窗口：${snapshotFrom} 至 ${snapshotTo}`;
  if (snapshotTo) return `截至：${snapshotTo}`;
  if (snapshotFrom) return `起始：${snapshotFrom}`;
  return "日期待补";
}

function endpointIssueLabel(input: StockEndpointEvidenceInput): string {
  const warningCount = normalizeEndpointCount(input.warningCount);
  const unsupportedCount = normalizeEndpointCount(input.unsupportedCount);
  const missingInputCount = normalizeEndpointCount(input.missingInputCount);
  const counts = [warningCount, unsupportedCount, missingInputCount].filter(
    (value): value is number => value !== null,
  );
  if (counts.length === 0) return "提示待补";
  const parts: string[] = [];
  if ((warningCount ?? 0) > 0) parts.push(`提示 ${warningCount}`);
  if ((unsupportedCount ?? 0) > 0) parts.push(`阻断 ${unsupportedCount}`);
  if ((missingInputCount ?? 0) > 0) parts.push(`缺输入 ${missingInputCount}`);
  return parts.length > 0 ? parts.join(" / ") : "无新增提示";
}

function endpointIssueCount(input: StockEndpointEvidenceInput): number {
  return (
    (normalizeEndpointCount(input.warningCount) ?? 0) +
    (normalizeEndpointCount(input.unsupportedCount) ?? 0) +
    (normalizeEndpointCount(input.missingInputCount) ?? 0)
  );
}

function endpointMetaNeedsReview(meta: StockEndpointEvidenceMeta): boolean {
  const quality = meta.quality_flag ?? "pending";
  const vendor = meta.vendor_status ?? "pending";
  const fallback = meta.fallback_mode ?? "pending";
  return quality !== "ok" || vendor !== "ok" || fallback !== "none";
}

function endpointMetaLabel(meta: StockEndpointEvidenceMeta | null | undefined): string {
  if (!meta) return "证据待补";
  const quality = meta.quality_flag ?? "pending";
  const vendor = meta.vendor_status ?? "pending";
  const fallback = meta.fallback_mode ?? "pending";
  return stockEvidenceBusinessQualityLabel(quality, vendor, fallback);
}

export function buildStockEndpointEvidenceItems(
  inputs: StockEndpointEvidenceInput[],
): StockEndpointEvidenceItem[] {
  return inputs.map((input) => {
    const base = {
      key: input.key,
      label: input.label,
      dateLabel: endpointDateLabel(input),
      traceLabel: compactEndpointTrace(input.meta?.trace_id),
      issueLabel: endpointIssueLabel(input),
      metaLabel: endpointMetaLabel(input.meta),
    };

    if (input.queryState === "loading") {
      return {
        ...base,
        dateLabel: "",
        traceLabel: "",
        issueLabel: "",
        metaLabel: "",
        statusLabel: "读取中",
        tone: "neutral",
        detail: "正在读取证据链，暂不纳入复核判断",
      };
    }

    if (input.queryState === "error") {
      return {
        ...base,
        dateLabel: "",
        traceLabel: "",
        issueLabel: "",
        metaLabel: "",
        statusLabel: "读取失败",
        tone: "negative",
        detail: "证据读取失败，当前结论不使用该扩展证据",
      };
    }

    if (input.queryState === "idle") {
      return {
        ...base,
        dateLabel: "",
        traceLabel: "",
        issueLabel: "",
        metaLabel: "",
        statusLabel: "待触发",
        tone: "neutral",
        detail: "证据链尚未触发，展开相关复核区后读取",
      };
    }

    if (!input.meta) {
      return {
        ...base,
        statusLabel: "证据待补",
        tone: "warning",
        detail: "证据已返回，但质量状态待补",
      };
    }

    const needsReview = endpointMetaNeedsReview(input.meta) || endpointIssueCount(input) > 0;
    return {
      ...base,
      statusLabel: needsReview ? "需复核" : "接通",
      tone: needsReview ? "warning" : "positive",
      detail: needsReview ? "证据已返回，业务提示需复核" : "证据链已返回，质量可核验",
    };
  });
}

function closureReasonTone(kind: StockObservationClosureReasonKind): StockClosedLoopTone {
  if (kind === "query-error") return "negative";
  if (kind === "no-data" || kind === "meta-missing") return "neutral";
  return "warning";
}

function closureActionText(reason: StockObservationClosureReason): string {
  const source = reason.endpointLabel;
  switch (reason.kind) {
    case "query-error":
      return `修复${source}证据读取失败`;
    case "meta-missing":
      return `补齐${source}证据状态`;
    case "fallback":
      return `核对${source}回退状态与供数状态`;
    case "warning":
      return `复核${source}服务端 warning`;
    case "unsupported":
      return `确认${source}支持边界`;
    case "missing-input":
      return `补${source}完整策略输入证据`;
    case "data-gap":
      return `补${source}数据缺口证据`;
    case "diagnostic":
      return `复核${source}诊断项`;
    case "no-data":
      return `确认${source}无记录状态`;
    default:
      return `复核${source}证据`;
  }
}

function endpointLoaded(item: StockEndpointEvidenceItem): boolean {
  return !["待读取", "待读取中", "待触发", "读取中", "读取失败"].includes(item.statusLabel);
}

export function buildObservationClosureSummary({
  endpointItems,
  reasonInputs = [],
  formalUseAllowed = false,
  approvalStatus = "gap_or_observational",
}: {
  endpointItems: StockEndpointEvidenceItem[];
  reasonInputs?: StockObservationClosureReasonInput[];
  formalUseAllowed?: boolean | null;
  approvalStatus?: string | null;
}): StockObservationClosureSummary {
  const endpointReasons: StockObservationClosureReasonInput[] = endpointItems.flatMap((item): StockObservationClosureReasonInput[] => {
    if (item.statusLabel === "读取失败") {
      return [
        {
          endpointId: item.key,
          endpointLabel: item.label,
          kind: "query-error",
          fieldPath: `${item.key}.queryState`,
          displayText: `${item.label}读取失败`,
        },
      ];
    }
    if (item.statusLabel === "证据待补") {
      return [
        {
          endpointId: item.key,
          endpointLabel: item.label,
          kind: "meta-missing",
          fieldPath: `${item.key}.result_meta`,
          displayText: `${item.label}证据状态待补`,
        },
      ];
    }
    return [];
  });
  const seen = new Set<string>();
  const unresolvedReasons = [...endpointReasons, ...reasonInputs].flatMap((input, index) => {
    const key = input.key ?? `${input.endpointId}:${input.kind}:${input.fieldPath}:${index}`;
    if (seen.has(key)) return [];
    seen.add(key);
    return [
      {
        ...input,
        key,
        tone: closureReasonTone(input.kind),
      },
    ];
  });
  const endpointLoadedCount = endpointItems.filter(endpointLoaded).length;
  const endpointErrorCount = endpointItems.filter((item) => item.statusLabel === "读取失败").length;
  const metaMissingCount = endpointItems.filter((item) => item.statusLabel === "证据待补").length;
  const formalUse = formalUseAllowed === true;
  const approval = approvalStatus?.trim() || "gap_or_observational";
  const nextEvidenceActions = unresolvedReasons.slice(0, 6).map((reason) => ({
    key: `action:${reason.key}`,
    source: reason.endpointLabel,
    actionText: closureActionText(reason),
    fieldPath: reason.fieldPath,
  }));
  const tone: StockClosedLoopTone =
    endpointErrorCount > 0 ? "negative" : unresolvedReasons.length > 0 || !formalUse ? "warning" : "positive";

  return {
    formalUseAllowed: formalUse,
    approvalStatus: approval,
    approvalLabel: approval === "gap_or_observational" ? "观测缺口页" : approval,
    endpointTotal: endpointItems.length,
    endpointLoadedCount,
    endpointErrorCount,
    metaMissingCount,
    unresolvedReasons,
    nextEvidenceActions,
    headline: `证据读取覆盖 ${endpointLoadedCount}/${endpointItems.length}`,
    detail: formalUse
      ? `治理状态：${approval}`
      : `正式用途：否 · 治理状态：${approval} · 待复核项 ${unresolvedReasons.length}`,
    tone,
  };
}

export function buildStockAnalysisEventMonitorRows(
  payload: LivermoreStrategyPayload,
  confluence: LivermoreSignalConfluencePayload | null,
): StockAnalysisEventMonitorRow[] {
  const rows: StockAnalysisEventMonitorRow[] = [];

  for (const [index, item] of payload.diagnostics.entries()) {
    rows.push({
      key: `diagnostic:${item.code}:${item.input_family ?? "strategy"}:${index}`,
      source: "diagnostic",
      level: eventLevelFromSeverity(item.severity),
      event: item.code,
      impact: item.input_family ?? "strategy",
      detail: localizeStockBackendText(item.message, item.input_family),
    });
  }

  for (const gap of payload.data_gaps.filter((item) => item.status !== "ready")) {
    rows.push({
      key: `data_gap:${gap.input_family}:${gap.status}`,
      source: "data_gap",
      level: gap.status === "stale" ? "warning" : "error",
      event: localizeDataGapStatus(gap.status),
      impact: localizeStockDataFamily(gap.input_family),
      detail: localizeStockBackendText(gap.evidence, gap.input_family),
    });
  }

  for (const item of payload.unsupported_outputs) {
    rows.push({
      key: `unsupported:${item.key}`,
      source: "unsupported",
      level: isActionableLivermoreUnsupportedOutput(item) ? "warning" : "info",
      event: `${localizeStockDataFamily(item.key)}阻断`,
      impact: item.key,
      detail: localizeStockBackendText(item.reason, item.key),
    });
  }

  for (const item of confluence?.diagnostics ?? []) {
    const row =
      typeof item === "string"
        ? { severity: "warning", code: item, message: item }
        : {
            severity: item.severity ?? "warning",
            code: item.code ?? item.message ?? "signal_confluence",
            message: item.message ?? item.code ?? "Signal confluence diagnostic pending detail.",
          };
    rows.push({
      key: `signal_confluence:${row.code}`,
      source: "signal_confluence",
      level: eventLevelFromSeverity(row.severity),
      event: row.code,
      impact: "signal_confluence",
      detail: localizeStockBackendText(row.message, "signal_confluence"),
    });
  }

  for (const row of buildRiskExitRows(payload, confluence).filter((item) => item.status === "triggered")) {
    rows.push({
      key: `risk_exit:${row.stockCode}`,
      source: "risk_exit",
      level: eventToneLevel("negative"),
      event: `${row.stockCode} ${row.stockName}`,
      impact: "risk_exit",
      detail: detailFromEventEvidence(row.reason, "风险退出观察触发复核"),
    });
  }

  return rows;
}

export function buildThemeTaxonomyGapSummary(
  dataGaps: readonly Pick<LivermoreStrategyPayload["data_gaps"][number], "input_family" | "status">[],
): StockThemeTaxonomyGapSummary {
  const themeGap = dataGaps.find(
    (gap) => gap.input_family.trim().toLowerCase().replace(/[\s-]+/g, "_") === "theme_taxonomy",
  );
  const status = themeGap?.status.trim().toLowerCase();
  if (!status || status === "ready") {
    return { state: "ready", detail: "目录状态随主包返回" };
  }
  if (status === "partial") {
    return {
      state: "partial",
      detail: "题材分类部分覆盖；证据受限，不阻断只读复核",
    };
  }
  return {
    state: "unavailable",
    detail: "题材分类证据不可用；保持只读并等待补证",
  };
}
