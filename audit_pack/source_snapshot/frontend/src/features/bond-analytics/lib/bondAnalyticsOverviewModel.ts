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
    return "未知";
  }

  if (meta.basis === "formal") {
    return "正式口径";
  }

  if (meta.basis === "analytical") {
    return "分析口径";
  }

  if (meta.basis === "scenario") {
    return "情景口径";
  }

  if (meta.basis === "mock") {
    return "演示口径";
  }

  return "其他口径";
}

function formatQuality(value: ResultMeta["quality_flag"] | undefined): string {
  if (value === "ok") return "正常";
  if (value === "warning") return "预警";
  if (value === "error") return "错误";
  if (value === "stale") return "陈旧";
  return "未知";
}

function formatFallback(value: ResultMeta["fallback_mode"] | undefined): string {
  if (value === "none") return "未降级";
  if (value === "latest_snapshot") return "最新快照降级";
  return "未知";
}

function formatVendorStatus(value: ResultMeta["vendor_status"] | undefined): string {
  if (value === "ok") return "正常";
  if (value === "vendor_stale") return "供应商数据陈旧";
  if (value === "vendor_unavailable") return "供应商不可用";
  return "未知";
}

function formatIsoMoment(value: string | null | undefined): string {
  if (!value) {
    return "未知";
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
      title: "真值与证据",
      items: [
        { key: "basis", label: "口径", value: "加载中", tone: "neutral" },
        { key: "freshness", label: "新鲜度", value: "加载中", tone: "neutral" },
        { key: "quality", label: "质量", value: "加载中", tone: "neutral" },
        { key: "coverage", label: "覆盖", value: "总览收窄", tone: "neutral" },
      ],
    };
  }

  if (error) {
    return {
      title: "真值与证据",
      items: [
        { key: "basis", label: "口径", value: "驾驶舱快照", tone: "warning" },
        {
          key: "freshness",
          label: "新鲜度",
          value: "动作归因不可用",
          tone: "warning",
        },
        { key: "quality", label: "质量", value: "部分总览", tone: "warning" },
        { key: "coverage", label: "覆盖", value: "仅驾驶舱快照", tone: "neutral" },
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
    title: "真值与证据",
    items: [
      {
        key: "basis",
        label: "口径",
        value: formatBasis(meta),
        tone: meta?.basis === "formal" ? "success" : "warning",
      },
      {
        key: "freshness",
        label: "新鲜度",
        value: formatIsoMoment(generatedAt),
        tone: freshnessTone,
      },
      {
        key: "quality",
        label: "质量",
        value: meta
          ? `${formatQuality(meta.quality_flag)}${meta.fallback_mode !== "none" ? " / 降级" : ""}`
          : "未知",
        tone: qualityTone,
      },
      {
        key: "coverage",
        label: "覆盖",
        value: "仅动作归因",
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
    anomalies.add("首页动作归因不可用。");
  }

  if (meta?.fallback_mode && meta.fallback_mode !== "none") {
    anomalies.add(
      `总览结果正在使用${formatFallback(meta.fallback_mode)}。`,
    );
  }

  if (meta?.quality_flag && meta.quality_flag !== "ok") {
    anomalies.add(`总览结果质量标记为${formatQuality(meta.quality_flag)}。`);
  }

  if (meta?.vendor_status && meta.vendor_status !== "ok") {
    anomalies.add(
      `供应商状态为${formatVendorStatus(meta.vendor_status)}。`,
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
