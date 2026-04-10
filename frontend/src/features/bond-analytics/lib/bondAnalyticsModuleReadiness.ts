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
  actionAttributionLoading?: boolean;
  actionAttributionError?: string | null;
}

const PLACEHOLDER_WARNING_PATTERNS = [
  /not yet populated/i,
  /returning empty/i,
  /placeholder/i,
];

export function hasPlaceholderWarning(warnings: string[]): boolean {
  return warnings.some((warning) =>
    PLACEHOLDER_WARNING_PATTERNS.some((pattern) => pattern.test(warning)),
  );
}

function hasRealActionAttributionContent(
  actionAttribution: ActionAttributionResponse,
): boolean {
  if (hasPlaceholderWarning(actionAttribution.warnings)) {
    return false;
  }

  return (
    actionAttribution.total_actions > 0 ||
    Number.parseFloat(actionAttribution.total_pnl_from_actions) !== 0 ||
    actionAttribution.by_action_type.length > 0 ||
    actionAttribution.action_details.length > 0
  );
}

export function deriveActionAttributionReadiness(
  input: DeriveActionAttributionReadinessInput,
): BondAnalyticsModuleReadiness {
  if (input.actionAttributionLoading) {
    return {
      tier: "status",
      statusLabel: "loading",
      statusReason:
        "Still evaluating whether action attribution is ready for summary mode.",
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
      statusReason: "No action attribution readiness payload has been loaded yet.",
      warnings: [],
    };
  }

  if (hasRealActionAttributionContent(input.actionAttribution)) {
    return {
      tier: "summary",
      statusLabel: "real-summary",
      statusReason:
        "The payload contains real action attribution content suitable for the overview.",
      warnings: input.actionAttribution.warnings,
      summary: {
        primaryLabel: "Action count",
        primaryValue: String(input.actionAttribution.total_actions),
        secondaryLabel: "Action PnL",
        secondaryValue: input.actionAttribution.total_pnl_from_actions,
      },
    };
  }

  return {
    tier: "status",
    statusLabel: "placeholder",
    statusReason:
      "Current response is placeholder-only; keep this module as a detail entry until stable homepage summary lands.",
    warnings: input.actionAttribution.warnings,
  };
}

export function createDetailEntryReadiness(): BondAnalyticsModuleReadiness {
  return {
    tier: "status",
    statusLabel: "detail-entry",
    statusReason:
      "Keep the detail entry available while the overview waits for stable backend truth.",
    warnings: [],
  };
}
