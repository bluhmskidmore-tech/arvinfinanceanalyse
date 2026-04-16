import type { ResultMeta } from "../../../api/contracts";
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
    Number.parseFloat(actionAttribution.total_pnl_from_actions) !== 0 ||
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

function buildDegradedProvenanceReason(meta: ResultMeta | null | undefined): string {
  if (!meta) {
    return "No provenance envelope has been loaded for the overview payload yet.";
  }

  if (meta.fallback_mode !== "none") {
    return `Overview payload is using ${meta.fallback_mode.replace("_", " ")} fallback mode.`;
  }

  if (meta.quality_flag !== "ok") {
    return `Overview payload quality is ${meta.quality_flag}.`;
  }

  if (meta.vendor_status !== "ok") {
    return `Vendor status is ${meta.vendor_status.replace("_", " ")}.`;
  }

  if (meta.formal_use_allowed !== true) {
    return "Formal use is not allowed for this overview payload.";
  }

  if (meta.scenario_flag) {
    return "Scenario payloads cannot be promoted into overview headline content.";
  }

  if (meta.basis !== "formal") {
    return `Overview payload basis is ${meta.basis}, so headline promotion stays blocked.`;
  }

  return "Overview payload provenance is not strong enough for headline promotion.";
}

export function deriveActionAttributionReadiness(
  input: DeriveActionAttributionReadinessInput,
): BondAnalyticsModuleReadiness {
  if (input.actionAttributionLoading) {
    return {
      tier: "status",
      statusLabel: "loading",
      statusReason:
        "Still evaluating whether action attribution is eligible for governed overview promotion.",
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
      statusReason: "No overview action-attribution envelope has been loaded yet.",
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
        "Action attribution passed the governed promotion gate and can lead the cockpit.",
      warnings,
      summary: {
        primaryLabel: "Action count",
        primaryValue: String(input.actionAttribution.total_actions),
        secondaryLabel: "Action PnL",
        secondaryValue: input.actionAttribution.total_pnl_from_actions,
      },
    };
  }

  if (warningSignals.hasPlaceholderSignals) {
    return {
      tier: "status",
      statusLabel: "placeholder-blocked",
      statusReason:
        "Current response is placeholder-backed, so the module stays in readiness/drill mode.",
      warnings,
    };
  }

  if (warningSignals.hasPartialSignals || warningSignals.hasAnyWarnings) {
    return {
      tier: "status",
      statusLabel: "warning",
      statusReason:
        "Overview payload still carries warning signals, so promotion remains blocked.",
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
      "Action attribution is loaded, but overview-safe headline content is not available yet.",
    warnings,
  };
}

export function createDetailEntryReadiness(): BondAnalyticsModuleReadiness {
  return {
    tier: "status",
    statusLabel: "not-fetched-in-overview",
    statusReason:
      "This module remains a governed detail-first surface while overview fetching stays narrow.",
    warnings: [],
  };
}
