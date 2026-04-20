import type { ApiEnvelope, ResultMeta } from "../../../api/contracts";
import type { PeriodType } from "../types";
import type { ActionAttributionResponse } from "../types";
import {
  BOND_ANALYTICS_FUTURE_MODULES,
  getBondAnalyticsModuleDefinition,
  type BondAnalyticsModuleKey,
} from "./bondAnalyticsModuleRegistry";
import {
  createDetailEntryReadiness,
  deriveActionAttributionReadiness,
  type BondAnalyticsModuleReadiness,
} from "./bondAnalyticsModuleReadiness";

export type BondAnalyticsPromotionDestination =
  | "headline"
  | "main-rail"
  | "readiness-only";

export type BondAnalyticsTruthTone =
  | "neutral"
  | "success"
  | "warning"
  | "danger";

export interface BondAnalyticsTruthStripItem {
  key: "basis" | "freshness" | "quality" | "coverage";
  label: string;
  value: string;
  tone: BondAnalyticsTruthTone;
}

export interface BondAnalyticsTruthStrip {
  title: string;
  items: BondAnalyticsTruthStripItem[];
}

export interface BondAnalyticsHeadlineTile {
  key: BondAnalyticsModuleKey;
  label: string;
  value: string;
  caption: string;
  detail: string;
}

export interface BondAnalyticsReadinessItem {
  key: BondAnalyticsModuleKey;
  label: string;
  description: string;
  detailHint: string;
  statusLabel: string;
  statusReason: string;
  promotionDestination: BondAnalyticsPromotionDestination;
  warnings: string[];
}

export interface BondAnalyticsFutureVisibilityItem {
  key: string;
  label: string;
  description: string;
  statusLabel: "future-visible";
  statusReason: string;
}

export interface BondAnalyticsActiveModuleContext {
  key: BondAnalyticsModuleKey;
  label: string;
  description: string;
  statusLabel: string;
  statusReason: string;
}

export interface BondAnalyticsOverviewModel {
  reportDate: string;
  periodType: PeriodType;
  truthStrip: BondAnalyticsTruthStrip;
  headlineTiles: BondAnalyticsHeadlineTile[];
  readinessItems: BondAnalyticsReadinessItem[];
  futureVisibilityItems: BondAnalyticsFutureVisibilityItem[];
  topAnomalies: string[];
  activeModuleContext: BondAnalyticsActiveModuleContext;
}

interface BuildBondAnalyticsOverviewModelInput {
  reportDate: string;
  periodType: PeriodType;
  activeModuleKey: BondAnalyticsModuleKey;
  actionAttributionEnvelope?: ApiEnvelope<ActionAttributionResponse> | null;
  actionAttributionLoading?: boolean;
  actionAttributionError?: string | null;
}

function formatBasis(meta: ResultMeta | null | undefined): string {
  if (!meta) {
    return "Unknown";
  }

  if (meta.basis === "formal") {
    return "Formal";
  }

  if (meta.basis === "analytical") {
    return "Analytical";
  }

  if (meta.basis === "scenario") {
    return "Scenario";
  }

  if (meta.basis === "mock") {
    return "演示口径";
  }

  return "其他口径";
}

function formatIsoMoment(value: string | null | undefined): string {
  if (!value) {
    return "Unknown";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toISOString().slice(0, 16).replace("T", " ");
}

function buildTruthStrip(
  meta: ResultMeta | null | undefined,
  payload: ActionAttributionResponse | null | undefined,
  loading: boolean,
  error: string | null | undefined,
): BondAnalyticsTruthStrip {
  if (loading) {
    return {
      title: "Truth and provenance",
      items: [
        { key: "basis", label: "Basis", value: "Loading", tone: "neutral" },
        { key: "freshness", label: "Freshness", value: "Loading", tone: "neutral" },
        { key: "quality", label: "Quality", value: "Loading", tone: "neutral" },
        { key: "coverage", label: "Coverage", value: "Overview narrow", tone: "neutral" },
      ],
    };
  }

  if (error) {
    return {
      title: "Truth and provenance",
      items: [
        { key: "basis", label: "Basis", value: "Dashboard snapshot", tone: "warning" },
        {
          key: "freshness",
          label: "Freshness",
          value: "Action attribution unavailable",
          tone: "warning",
        },
        { key: "quality", label: "Quality", value: "Partial overview", tone: "warning" },
        { key: "coverage", label: "Coverage", value: "Dashboard snapshot only", tone: "neutral" },
      ],
    };
  }

  const generatedAt = meta?.generated_at ?? payload?.computed_at;
  const freshnessTone =
    meta?.quality_flag === "stale" ? "warning" : "neutral";
  const qualityTone =
    meta?.quality_flag === "ok" && meta?.fallback_mode === "none"
      ? "success"
      : meta
        ? "warning"
        : "danger";

  return {
    title: "Truth and provenance",
    items: [
      {
        key: "basis",
        label: "Basis",
        value: formatBasis(meta),
        tone: meta?.basis === "formal" ? "success" : "warning",
      },
      {
        key: "freshness",
        label: "Freshness",
        value: formatIsoMoment(generatedAt),
        tone: freshnessTone,
      },
      {
        key: "quality",
        label: "Quality",
        value: meta
          ? `${meta.quality_flag}${meta.fallback_mode !== "none" ? " / fallback" : ""}`
          : "Unknown",
        tone: qualityTone,
      },
      {
        key: "coverage",
        label: "Coverage",
        value: "Action attribution only",
        tone: "neutral",
      },
    ],
  };
}

function buildActionReadinessItem(
  readiness: BondAnalyticsModuleReadiness,
): BondAnalyticsReadinessItem {
  const definition = getBondAnalyticsModuleDefinition("action-attribution");

  return {
    key: definition.key,
    label: definition.label,
    description: definition.description,
    detailHint: definition.detailHint,
    statusLabel: readiness.statusLabel,
    statusReason: readiness.statusReason,
    promotionDestination:
      readiness.tier === "summary" ? "headline" : "readiness-only",
    warnings: readiness.warnings,
  };
}

function buildNonFetchedReadinessItem(
  key: Exclude<BondAnalyticsModuleKey, "action-attribution">,
): BondAnalyticsReadinessItem {
  const definition = getBondAnalyticsModuleDefinition(key);
  const readiness = createDetailEntryReadiness();

  return {
    key,
    label: definition.label,
    description: definition.description,
    detailHint: definition.detailHint,
    statusLabel: readiness.statusLabel,
    statusReason: readiness.statusReason,
    promotionDestination: "readiness-only",
    warnings: readiness.warnings,
  };
}

function buildTopAnomalies(
  meta: ResultMeta | null | undefined,
  warnings: string[],
  error: string | null | undefined,
): string[] {
  const anomalies = new Set<string>();

  if (error) {
    anomalies.add("Action attribution unavailable in homepage.");
  }

  if (meta?.fallback_mode && meta.fallback_mode !== "none") {
    anomalies.add(
      `Overview payload is using ${meta.fallback_mode.replace("_", " ")} fallback mode.`,
    );
  }

  if (meta?.quality_flag && meta.quality_flag !== "ok") {
    anomalies.add(`Overview payload quality is ${meta.quality_flag}.`);
  }

  if (meta?.vendor_status && meta.vendor_status !== "ok") {
    anomalies.add(
      `Vendor status is ${meta.vendor_status.replace("_", " ")}.`,
    );
  }

  warnings.forEach((warning) => anomalies.add(warning));

  return [...anomalies];
}

export function buildBondAnalyticsOverviewModel(
  input: BuildBondAnalyticsOverviewModelInput,
): BondAnalyticsOverviewModel {
  const actionAttributionMeta = input.actionAttributionEnvelope?.result_meta ?? null;
  const actionAttribution = input.actionAttributionEnvelope?.result ?? null;
  const actionReadiness = deriveActionAttributionReadiness({
    actionAttribution,
    actionAttributionMeta,
    actionAttributionLoading: input.actionAttributionLoading,
    actionAttributionError: input.actionAttributionError,
  });

  const readinessItems: BondAnalyticsReadinessItem[] = [
    buildActionReadinessItem(actionReadiness),
    buildNonFetchedReadinessItem("return-decomposition"),
    buildNonFetchedReadinessItem("benchmark-excess"),
    buildNonFetchedReadinessItem("krd-curve-risk"),
    buildNonFetchedReadinessItem("credit-spread"),
    buildNonFetchedReadinessItem("portfolio-headlines"),
    buildNonFetchedReadinessItem("top-holdings"),
    buildNonFetchedReadinessItem("accounting-audit"),
  ];

  const activeModuleDefinition = getBondAnalyticsModuleDefinition(input.activeModuleKey);
  const activeReadiness =
    readinessItems.find((item) => item.key === input.activeModuleKey) ??
    readinessItems[0];

  return {
    reportDate: input.reportDate,
    periodType: input.periodType,
    truthStrip: buildTruthStrip(
      actionAttributionMeta,
      actionAttribution,
      Boolean(input.actionAttributionLoading),
      input.actionAttributionError,
    ),
    headlineTiles:
      actionReadiness.tier === "summary" && actionReadiness.summary
        ? [
            {
              key: "action-attribution",
              label: getBondAnalyticsModuleDefinition("action-attribution").label,
              value: actionReadiness.summary.primaryValue,
              caption: actionReadiness.summary.primaryLabel,
              detail: `${actionReadiness.summary.secondaryLabel} ${actionReadiness.summary.secondaryValue}`,
            },
          ]
        : [],
    readinessItems,
    futureVisibilityItems: BOND_ANALYTICS_FUTURE_MODULES.map((module) => ({
      ...module,
      statusLabel: "future-visible",
      statusReason:
        "Kept visible in the top cockpit right rail while backend truth and promotion rules are still pending.",
    })),
    topAnomalies: buildTopAnomalies(
      actionAttributionMeta,
      actionReadiness.warnings,
      input.actionAttributionError,
    ),
    activeModuleContext: {
      key: activeModuleDefinition.key,
      label: activeModuleDefinition.label,
      description: activeModuleDefinition.description,
      statusLabel: activeReadiness.statusLabel,
      statusReason: activeReadiness.statusReason,
    },
  };
}
