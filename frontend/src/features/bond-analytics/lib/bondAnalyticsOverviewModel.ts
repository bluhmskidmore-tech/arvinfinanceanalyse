import type { PeriodType } from "../types";
import {
  BOND_ANALYTICS_CURRENT_MODULES,
  BOND_ANALYTICS_FUTURE_MODULES,
  type BondAnalyticsModuleKey,
} from "./bondAnalyticsModuleRegistry";
import {
  createDetailEntryReadiness,
  deriveActionAttributionReadiness,
  type BondAnalyticsModuleReadiness,
  type BondAnalyticsModuleSummary,
  type BondAnalyticsModuleTier,
} from "./bondAnalyticsModuleReadiness";

export interface BondAnalyticsOverviewModule {
  key: BondAnalyticsModuleKey;
  label: string;
  description: string;
  detailHint: string;
  tier: BondAnalyticsModuleTier;
  statusLabel: string;
  statusReason: string;
  warnings: string[];
  summary?: BondAnalyticsModuleSummary;
}

export interface BondAnalyticsFutureModule {
  key: string;
  label: string;
  description: string;
  tier: "blocked";
  statusLabel: string;
  statusReason: string;
}

export interface BondAnalyticsOverviewModel {
  reportDate: string;
  periodType: PeriodType;
  summaryModules: BondAnalyticsOverviewModule[];
  currentModules: BondAnalyticsOverviewModule[];
  futureModules: BondAnalyticsFutureModule[];
  topWarnings: string[];
}

interface BuildBondAnalyticsOverviewModelInput {
  reportDate: string;
  periodType: PeriodType;
  actionAttribution?: import("../types").ActionAttributionResponse | null;
  actionAttributionLoading?: boolean;
  actionAttributionError?: string | null;
}

function applyReadiness(
  key: BondAnalyticsModuleKey,
  readiness: BondAnalyticsModuleReadiness,
): BondAnalyticsOverviewModule {
  const base = BOND_ANALYTICS_CURRENT_MODULES.find((module) => module.key === key)!;

  return {
    ...base,
    ...readiness,
  };
}

function buildDetailOnlyModule(
  key: Exclude<BondAnalyticsModuleKey, "action-attribution">,
): BondAnalyticsOverviewModule {
  return applyReadiness(key, createDetailEntryReadiness());
}

export function buildBondAnalyticsOverviewModel(
  input: BuildBondAnalyticsOverviewModelInput,
): BondAnalyticsOverviewModel {
  const currentModules: BondAnalyticsOverviewModule[] = [
    applyReadiness(
      "action-attribution",
      deriveActionAttributionReadiness({
        actionAttribution: input.actionAttribution,
        actionAttributionLoading: input.actionAttributionLoading,
        actionAttributionError: input.actionAttributionError,
      }),
    ),
    buildDetailOnlyModule("return-decomposition"),
    buildDetailOnlyModule("benchmark-excess"),
    buildDetailOnlyModule("krd-curve-risk"),
    buildDetailOnlyModule("credit-spread"),
    buildDetailOnlyModule("accounting-audit"),
  ];

  return {
    reportDate: input.reportDate,
    periodType: input.periodType,
    summaryModules: currentModules.filter((module) => module.tier === "summary"),
    currentModules,
    futureModules: BOND_ANALYTICS_FUTURE_MODULES.map((module) => ({
      ...module,
      tier: "blocked",
      statusLabel: "blocked",
      statusReason: "Wait for stable backend truth before promoting this module.",
    })),
    topWarnings: currentModules.flatMap((module) => module.warnings),
  };
}
