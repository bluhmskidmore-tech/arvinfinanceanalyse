import type { ResultMeta } from "../../../api/contracts";
import { bondNumericRaw } from "../adapters/bondAnalyticsAdapter";
import type { ActionAttributionResponse } from "../types";

export type BondAnalyticsModuleTier = "summary" | "status" | "blocked";

export interface BondAnalyticsModuleSummary {
  primaryLabel: string;
  primaryValue: string;
  secondaryLabel: string;
  secondaryValue: string;
}

export interface BondAnalyticsModuleReadiness {
  tier: BondAnalyticsModuleTier;
  statusLabel: string;
  statusReason: string;
  warnings: string[];
  summary?: BondAnalyticsModuleSummary;
}

interface DeriveActionAttributionReadinessInput {
  actionAttribution?: ActionAttributionResponse | null;
  actionAttributionMeta?: ResultMeta | null;
  actionAttributionLoading?: boolean;
  actionAttributionError?: string | null;
}

const PLACEHOLDER_WARNING_PATTERNS = [
  /not yet populated/i,
  /returning empty/i,
  /placeholder/i,
] as const;

const PARTIAL_WARNING_PATTERNS = [
  /phase 3/i,
  /remain zero/i,
  /set to 0/i,
  /input unavailable/i,
] as const;

export function hasPlaceholderWarning(warnings: string[]): boolean {
  return warnings.some((warning) =>
    PLACEHOLDER_WARNING_PATTERNS.some((pattern) => pattern.test(warning)),
  );
}

export function classifyWarningSignals(warnings: string[]) {
  return {
    hasPlaceholderSignals: hasPlaceholderWarning(warnings),
    hasPartialSignals: warnings.some((warning) =>
      PARTIAL_WARNING_PATTERNS.some((pattern) => pattern.test(warning)),
    ),
    hasAnyWarnings: warnings.length > 0,
  };
}

function hasRealActionAttributionContent(
  actionAttribution: ActionAttributionResponse,
): boolean {
  return (
    actionAttribution.total_actions > 0 ||
    bondNumericRaw(actionAttribution.total_pnl_from_actions) !== 0 ||
    actionAttribution.by_action_type.length > 0 ||
    actionAttribution.action_details.length > 0
  );
}

function hasPromotionSafeProvenance(meta: ResultMeta | null | undefined): boolean {
  if (!meta) {
    return false;
  }

  return (
    meta.basis === "formal" &&
    meta.formal_use_allowed === true &&
    meta.scenario_flag === false &&
    meta.quality_flag === "ok" &&
    meta.vendor_status === "ok" &&
    meta.fallback_mode === "none"
  );
}

function formatBasis(value: ResultMeta["basis"]): string {
  if (value === "formal") return "正式口径";
  if (value === "scenario") return "情景口径";
  if (value === "analytical") return "分析口径";
  if (value === "mock") return "演示口径";
  return value;
}

function formatQuality(value: ResultMeta["quality_flag"]): string {
  if (value === "ok") return "正常";
  if (value === "warning") return "预警";
  if (value === "error") return "错误";
  if (value === "stale") return "陈旧";
  return value;
}

function formatFallback(value: ResultMeta["fallback_mode"]): string {
  if (value === "none") return "未降级";
  if (value === "latest_snapshot") return "最新快照降级";
  return value;
}

function formatVendorStatus(value: ResultMeta["vendor_status"]): string {
  if (value === "ok") return "正常";
  if (value === "vendor_stale") return "供应商数据陈旧";
  if (value === "vendor_unavailable") return "供应商不可用";
  return value;
}

function buildDegradedProvenanceReason(meta: ResultMeta | null | undefined): string {
  if (!meta) {
    return "尚未加载总览结果的证据信封。";
  }

  if (meta.fallback_mode !== "none") {
    return `总览结果正在使用${formatFallback(meta.fallback_mode)}。`;
  }

  if (meta.quality_flag !== "ok") {
    return `总览结果质量标记为${formatQuality(meta.quality_flag)}。`;
  }

  if (meta.vendor_status !== "ok") {
    return `供应商状态为${formatVendorStatus(meta.vendor_status)}。`;
  }

  if (meta.formal_use_allowed !== true) {
    return "该总览结果不允许正式使用。";
  }

  if (meta.scenario_flag) {
    return "情景结果不能提升到总览头条内容。";
  }

  if (meta.basis !== "formal") {
    return `总览结果口径为${formatBasis(meta.basis)}，因此仍阻止头条提升。`;
  }

  return "总览结果证据链强度不足，不能提升到头条。";
}

export function deriveActionAttributionReadiness(
  input: DeriveActionAttributionReadinessInput,
): BondAnalyticsModuleReadiness {
  if (input.actionAttributionLoading) {
    return {
      tier: "status",
      statusLabel: "loading",
      statusReason:
        "正在判断动作归因是否满足治理总览提升条件。",
      warnings: [],
    };
  }

  if (input.actionAttributionError) {
    return {
      tier: "status",
      statusLabel: "request-error",
      statusReason: input.actionAttributionError,
      warnings: [],
    };
  }

  if (!input.actionAttribution) {
    return {
      tier: "status",
      statusLabel: "pending",
      statusReason: "尚未加载总览动作归因结果。",
      warnings: [],
    };
  }

  const warnings = input.actionAttribution.warnings;
  const warningSignals = classifyWarningSignals(warnings);
  const hasCleanProvenance = hasPromotionSafeProvenance(input.actionAttributionMeta);
  const hasRealContent = hasRealActionAttributionContent(input.actionAttribution);

  if (
    hasCleanProvenance &&
    !warningSignals.hasAnyWarnings &&
    hasRealContent
  ) {
    return {
      tier: "summary",
      statusLabel: "eligible",
      statusReason:
        "动作归因已通过治理提升门槛，可以进入驾驶舱头条。",
      warnings,
      summary: {
        primaryLabel: "动作数量",
        primaryValue: String(input.actionAttribution.total_actions),
        secondaryLabel: "动作损益",
        secondaryValue: input.actionAttribution.total_pnl_from_actions.display,
      },
    };
  }

  if (warningSignals.hasPlaceholderSignals) {
    return {
      tier: "status",
      statusLabel: "placeholder-blocked",
      statusReason:
        "当前响应依赖占位内容，模块保持就绪/下钻模式。",
      warnings,
    };
  }

  if (warningSignals.hasPartialSignals || warningSignals.hasAnyWarnings) {
    return {
      tier: "status",
      statusLabel: "warning",
      statusReason:
        "总览结果仍带有预警信号，因此继续阻止提升。",
      warnings,
    };
  }

  if (!hasCleanProvenance) {
    return {
      tier: "status",
      statusLabel: "warning",
      statusReason: buildDegradedProvenanceReason(input.actionAttributionMeta),
      warnings,
    };
  }

  return {
    tier: "status",
    statusLabel: "detail-first",
    statusReason:
      "动作归因已加载，但尚无适合总览头条展示的内容。",
    warnings,
  };
}

export function createDetailEntryReadiness(): BondAnalyticsModuleReadiness {
  return {
    tier: "status",
    statusLabel: "detail-surface",
    statusReason:
      "该模块在下方明细区按当前筛选请求后端；概览层仅预取动作归因，不在此误报为占位或未实现。",
    warnings: [],
  };
}
