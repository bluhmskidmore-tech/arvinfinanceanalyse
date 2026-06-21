import type { UseQueryResult } from "@tanstack/react-query";

import type { ApiClient } from "../../../api/client";
import type {
  MacroToolkitAnalysisPayload,
  MacroToolkitAShareRiskPayload,
  MacroToolkitHasonStrategy,
  MacroToolkitIndicator,
  MacroToolkitShadowPortfolioReport,
  MacroToolkitStrategySummariesPayload,
} from "../../../api/macroToolkitClient";
import { summarizeMacroNewsEvent } from "../dashboard-home/adapters/macroNewsPresentation";
import { formatChoiceMacroDelta, formatChoiceMacroValue } from "../../../utils/choiceMacroFormat";
import { choiceSeriesById, enrichMarketHomeRows } from "./marketHomeRowEnrichment";
import { formatMacroSignalEvidence } from "./marketEvidenceVisual";
import { formatRawAsNumeric } from "../../../utils/format";
import type {
  ApiEnvelope,
  AssetStructurePayload,
  BalanceAnalysisBasisBreakdownPayload,
  BalanceAnalysisDatesPayload,
  BalanceAnalysisOverviewPayload,
  BondAnalyticsDatesPayload,
  BondBusinessTypeMetricsPayload,
  BondDashboardHeadlinePayload,
  CashflowProjectionPayload,
  ChoiceMacroLatestPayload,
  ChoiceMacroLatestPoint,
  ChoiceNewsEventsPayload,
  CubeDimensionsPayload,
  HealthResponse,
  HealthStatusResponse,
  SourcePreviewSummary,
  IndustryDistPayload,
  KpiOwnerListResponse,
  KpiPeriodMetricSummary,
  KpiPeriodSummaryResponse,
  MacroVendorPayload,
  MacroVendorSeries,
  MaturityStructurePayload,
  Numeric,
  PnlAttributionAnalysisSummary,
  PnlByBusinessYtdItem,
  PnlByBusinessYtdPayload,
  PortfolioComparisonPayload,
  ResultMeta,
  RiskIndicatorsPayload,
  SpreadAnalysisPayload,
  YieldDistributionPayload,
  RiskTensorDatesPayload,
  RiskTensorPayload,
  RiskTensorScalar,
  SourcePreviewPayload,
} from "../../../api/contracts";
import {
  bondNumericDisplay,
  bondNumericRawOrNull,
} from "../../bond-analytics/adapters/bondAnalyticsAdapter";
import {
  formatDv01Wan,
  formatMomRatio,
  formatBp,
  formatRatePercent,
  formatYi,
  formatYears,
  nativeToNumber,
} from "../../bond-dashboard/utils/format";
import {
  buildMarketDataTerminalModel,
  type MarketDataMoneyMarketRow,
  type MarketDataRateQuoteRow,
} from "../../market-data/lib/marketDataTerminalModel";
import { formatRatioPct } from "../../pnl/pnlByBusinessPageModel";
import { moduleWorkbenchHomeConfigs, type ModuleWorkbenchHomeKind } from "./moduleHomeConfig";
import {
  buildPortfolioDecision,
  guardMockPortfolioHomeView,
  pnlDriverLabel,
  type PortfolioEvidenceState,
  type PortfolioPnlState,
  type PortfolioReadPathState,
} from "./portfolioDecisionModel";
import {
  buildPortfolioReadinessGate,
  type PortfolioEvidenceSource,
} from "./portfolioReadinessGate";
import {
  buildRiskKrdChart,
  dv01LimitStatusLabel,
  enrichRiskSectionsWithSparklines,
  riskKpiSparklineFromTensor,
} from "./riskHomeAdapter";

export type ModuleHomeTone = "ok" | "watch" | "error" | "muted";

export type ModuleHomeKpi = {
  key: string;
  label: string;
  value: string;
  detail: string;
  tone: ModuleHomeTone;
  /** 近两期读数，仅用于迷你走势展示（数据来自 API prev_kpis / recent_points） */
  sparkline?: readonly number[];
};

export type ModuleHomeStatus = {
  key: string;
  label: string;
  value: string;
  detail: string;
  tone: ModuleHomeTone;
};

export type ModuleHomeBriefing = {
  title: string;
  conclusion: string;
  evidence: string;
  tone: ModuleHomeTone;
};

export type ModuleHomeDataNote = {
  title: string;
  lines: string[];
  tone: ModuleHomeTone;
};

export type ModuleHomeDecision = {
  title: string;
  conclusion: string;
  detail: string;
  tone: ModuleHomeTone;
  facts: Array<{
    label: string;
    value: string;
    tone: ModuleHomeTone;
  }>;
  actions?: Array<{
    title: string;
    evidence: string;
    path: string;
    tone: ModuleHomeTone;
    label?: string;
  }>;
  readiness?: {
    decisionReady: boolean;
    riskClosureReady: boolean;
    blockingReasons: string[];
    warningReasons: string[];
    sourceFacts: string[];
    sourceDates: string;
    riskClosureFact: string;
  };
};

export type ModuleHomeDistributionRow = {
  key: string;
  label: string;
  marketValue: string;
  share: string;
  barPct: number;
  tone: ModuleHomeTone;
};

export type ModuleHomeDistributionPanel = {
  key: string;
  title: string;
  meta: string;
  stateLabel: string;
  stateDetail: string;
  rows: ModuleHomeDistributionRow[];
  tone: ModuleHomeTone;
  totalDisplay?: string;
  subtitle?: string;
  viewAllPath?: string;
};

export type ModuleHomeDetailRow = {
  key: string;
  label: string;
  value: string;
  tradeDate: string;
  source: string;
  tone: ModuleHomeTone;
  /** 日变动等补充说明，关键利率表单独占列展示 */
  detail?: string;
  /** 来自 recent_points 的迷你走势，仅展示用途 */
  sparkline?: readonly number[];
  /** portfolio-comparison 分列读数（仅展示，不补算） */
  scaleDisplay?: string;
  durationDisplay?: string;
  ytmDisplay?: string;
  dv01Display?: string;
  countDisplay?: string;
};

export type ModuleHomeDetailChart = {
  title: string;
  unit: string;
  orientation: "horizontal" | "vertical";
  categories: string[];
  values: number[];
};

export type ModuleHomeDetailSection = {
  key: string;
  title: string;
  subtitle?: string;
  rows: ModuleHomeDetailRow[];
  defaultExpanded?: boolean;
};

export type ModuleHomeDetailPanel = {
  key: string;
  title: string;
  meta: string;
  stateLabel: string;
  stateDetail: string;
  rows: ModuleHomeDetailRow[];
  sections?: ModuleHomeDetailSection[];
  tone: ModuleHomeTone;
  chart?: ModuleHomeDetailChart;
};

export type MarketCrisisExplainComponent = {
  key: string;
  label: string;
  zScore: number | null;
  weight: number | null;
  rawValue: number | null;
};

export type MarketCrisisHistoryPoint = {
  date: string;
  crisisScore: number;
  percentile: number | null;
};

export type MarketDeskIndicatorHighlight = {
  key: string;
  label: string;
  value: string;
  group: string;
  tone: ModuleHomeTone;
};

export type MarketDeskIntelView = {
  curveShape: string | null;
  curveShapeLabel: string | null;
  curveInterpretation: string | null;
  spread10y1yBp: number | null;
  curvePercentile1y: number | null;
  indicators: MarketDeskIndicatorHighlight[];
};

export type MarketCrisisExplainView = {
  crisisScore: number | null;
  regime: string | null;
  percentile: number | null;
  headline: string | null;
  recommendation: string | null;
  dataStatus: string | null;
  availableComponentCount: number | null;
  componentCount: number | null;
  scoreDelta: number | null;
  percentileDelta: number | null;
  components: MarketCrisisExplainComponent[];
  scoreHistory: MarketCrisisHistoryPoint[];
  warnings: string[];
  tone: ModuleHomeTone;
};

export type ModuleHomeView = {
  kind: ModuleWorkbenchHomeKind;
  title: string;
  question: string;
  summary: string;
  sourceScope: string;
  stateLabel: string;
  stateDetail: string;
  kpis: ModuleHomeKpi[];
  statuses: ModuleHomeStatus[];
  briefings: ModuleHomeBriefing[];
  decision?: ModuleHomeDecision;
  distributionPanels?: ModuleHomeDistributionPanel[];
  detailPanels?: ModuleHomeDetailPanel[];
  marketCrisisExplain?: MarketCrisisExplainView | null;
  marketDeskIntel?: MarketDeskIntelView | null;
  dataNote: ModuleHomeDataNote;
};

export type ModuleHomeViewBody = Omit<ModuleHomeView, "kind" | "title" | "question" | "summary" | "sourceScope">;

export type ModuleHomeSourceQueries = {
  balanceDates?: UseQueryResult<ApiEnvelope<BalanceAnalysisDatesPayload>>;
  balanceOverview?: UseQueryResult<ApiEnvelope<BalanceAnalysisOverviewPayload>>;
  bondDates?: UseQueryResult<ApiEnvelope<BondAnalyticsDatesPayload>>;
  bondHeadline?: UseQueryResult<ApiEnvelope<BondDashboardHeadlinePayload>>;
  bondRisk?: UseQueryResult<ApiEnvelope<RiskIndicatorsPayload>>;
  bondAssetType?: UseQueryResult<ApiEnvelope<AssetStructurePayload>>;
  bondAssetRating?: UseQueryResult<ApiEnvelope<AssetStructurePayload>>;
  bondMaturity?: UseQueryResult<ApiEnvelope<MaturityStructurePayload>>;
  bondIndustry?: UseQueryResult<ApiEnvelope<IndustryDistPayload>>;
  bondYield?: UseQueryResult<ApiEnvelope<YieldDistributionPayload>>;
  bondPortfolioComparison?: UseQueryResult<ApiEnvelope<PortfolioComparisonPayload>>;
  bondSpread?: UseQueryResult<ApiEnvelope<SpreadAnalysisPayload>>;
  bondBusinessType?: UseQueryResult<BondBusinessTypeMetricsPayload>;
  balanceBasis?: UseQueryResult<ApiEnvelope<BalanceAnalysisBasisBreakdownPayload>>;
  pnlSummary?: UseQueryResult<ApiEnvelope<PnlAttributionAnalysisSummary>>;
  choiceLatest?: UseQueryResult<ApiEnvelope<ChoiceMacroLatestPayload>>;
  marketRates?: UseQueryResult<ApiEnvelope<ChoiceMacroLatestPayload>>;
  marketCatalog?: UseQueryResult<ApiEnvelope<MacroVendorPayload>>;
  riskDates?: UseQueryResult<ApiEnvelope<RiskTensorDatesPayload>>;
  riskTensor?: UseQueryResult<ApiEnvelope<RiskTensorPayload>>;
  cashflow?: UseQueryResult<ApiEnvelope<CashflowProjectionPayload>>;
  kpiOwners?: UseQueryResult<KpiOwnerListResponse>;
  kpiSummary?: UseQueryResult<KpiPeriodSummaryResponse>;
  pnlYtd?: UseQueryResult<ApiEnvelope<PnlByBusinessYtdPayload>>;
  healthLive?: UseQueryResult<HealthStatusResponse>;
  healthSummary?: UseQueryResult<HealthStatusResponse>;
  sourceFoundation?: UseQueryResult<ApiEnvelope<SourcePreviewPayload>>;
  cubeDimensions?: UseQueryResult<CubeDimensionsPayload>;
  macroToolkitAnalysis?: UseQueryResult<ApiEnvelope<MacroToolkitAnalysisPayload>>;
  macroToolkitStrategySummaries?: UseQueryResult<ApiEnvelope<MacroToolkitStrategySummariesPayload>>;
  newsEvents?: UseQueryResult<ApiEnvelope<ChoiceNewsEventsPayload>>;
};

const YUAN_PER_YI = 100_000_000;

function decimalToNumber(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const parsed = typeof value === "number" ? value : Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatYiFromYuan(value: string | number | null | undefined) {
  const parsed = decimalToNumber(value);
  if (parsed === null) {
    return "-";
  }
  return `${(parsed / YUAN_PER_YI).toLocaleString("zh-CN", {
    maximumFractionDigits: 2,
  })} 亿元`;
}

function plain(value: unknown, fallback = "-") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  if (typeof value === "object" && "display" in value) {
    return String((value as { display?: unknown }).display ?? fallback);
  }
  return String(value);
}

function metaLabel(meta: ResultMeta | undefined) {
  if (!meta) {
    return "无元数据";
  }
  const date = meta.as_of_date ?? meta.resolved_report_date ?? meta.fallback_date ?? "";
  const parts = [meta.result_kind, meta.basis, date].filter(Boolean);
  return parts.join(" / ");
}

function queryIsInitialLoading(query: UseQueryResult<unknown> | undefined) {
  return Boolean(query?.isLoading);
}

function queryHasData(query: UseQueryResult<unknown> | undefined) {
  return Boolean(query?.data);
}

function queryStatus(
  key: string,
  label: string,
  query: UseQueryResult<unknown> | undefined,
  readyDetail: string,
): ModuleHomeStatus {
  if (!query) {
    return {
      key,
      label,
      value: "未接入",
      detail: "当前首页未触发该读链路。",
      tone: "muted",
    };
  }
  if (queryIsInitialLoading(query)) {
    return {
      key,
      label,
      value: "读取中",
      detail: "等待既有 API 返回。",
      tone: "muted",
    };
  }
  if (query.isError) {
    return {
      key,
      label,
      value: "读取失败",
      detail: "不使用前端补数，请进入下钻页或重试读链路。",
      tone: "error",
    };
  }
  if (!query.data) {
    return {
      key,
      label,
      value: "暂无数据",
      detail: "后端返回为空或该能力待接入。",
      tone: "watch",
    };
  }
  return {
    key,
    label,
    value: "已返回",
    detail: readyDetail,
    tone: "ok",
  };
}

function emptyRowsWatchStatus(
  status: ModuleHomeStatus,
  rows: readonly unknown[],
  emptyDetail: string,
): ModuleHomeStatus {
  if (status.tone !== "ok" || rows.length > 0) {
    return status;
  }
  return {
    ...status,
    value: "明细为空",
    detail: emptyDetail,
    tone: "watch",
  };
}

function hasError(queries: ModuleHomeSourceQueries) {
  return Object.values(queries).some((query) => query?.isError);
}

function hasLoading(queries: ModuleHomeSourceQueries) {
  return Object.values(queries).some((query) => queryIsInitialLoading(query));
}

function hasData(queries: ModuleHomeSourceQueries) {
  return Object.values(queries).some((query) => queryHasData(query));
}

function portfolioCoreReadQueries(queries: ModuleHomeSourceQueries): ModuleHomeSourceQueries {
  return {
    balanceDates: queries.balanceDates,
    balanceOverview: queries.balanceOverview,
    bondDates: queries.bondDates,
    bondHeadline: queries.bondHeadline,
    bondRisk: queries.bondRisk,
  };
}

function marketHomePrimaryQueries(queries: ModuleHomeSourceQueries): ModuleHomeSourceQueries {
  return {
    choiceLatest: queries.choiceLatest,
    marketRates: queries.marketRates,
    marketCatalog: queries.marketCatalog,
    macroToolkitAnalysis: queries.macroToolkitAnalysis,
  };
}

function envelopeMeta(query: UseQueryResult<ApiEnvelope<unknown>> | undefined) {
  return metaLabel(query?.data?.result_meta);
}

function metaIsFormalDecisionSource(meta: ResultMeta | undefined) {
  return Boolean(
    meta &&
      meta.basis === "formal" &&
      meta.formal_use_allowed &&
      meta.quality_flag === "ok" &&
      meta.fallback_mode === "none" &&
      !meta.fallback_date,
  );
}

function sourceUseStatus(
  status: ModuleHomeStatus,
  meta: ResultMeta | undefined,
  blockedDetail: string,
): ModuleHomeStatus {
  if (status.tone !== "ok" || metaIsFormalDecisionSource(meta)) {
    return status;
  }
  return {
    ...status,
    value: "分析口径",
    detail: blockedDetail,
    tone: "watch",
  };
}

function bondDashboardMeta(reportDate: string) {
  return `来源 bond-dashboard · ${reportDate || "-"}`;
}

function marketDataMeta(
  source: string,
  meta: ResultMeta | undefined,
  fallbackDate?: string,
) {
  const date =
    meta?.as_of_date ?? meta?.resolved_report_date ?? meta?.fallback_date ?? fallbackDate ?? "-";
  return `来源 ${source} · ${date}`;
}

/** Home depth zone: keep source labels, drop YYYY-MM-DD segments from panel meta. */
export function formatPanelMetaForHome(meta: string | undefined): string | undefined {
  if (!meta?.trim()) {
    return meta;
  }
  const parts = meta
    .split(/\s*·\s*/)
    .map((part) => part.trim())
    .filter((part) => part && !/^\d{4}-\d{2}-\d{2}$/.test(part));
  return parts.length > 0 ? parts.join(" · ") : undefined;
}

function combinedQueryStatus(
  key: string,
  label: string,
  queries: Array<UseQueryResult<unknown> | undefined>,
  readyDetail: string,
): ModuleHomeStatus {
  const active = queries.filter(Boolean);
  if (active.length === 0) {
    return queryStatus(key, label, undefined, readyDetail);
  }
  if (active.some((query) => query?.isError)) {
    return {
      key,
      label,
      value: "读取失败",
      detail: "不使用前端补数，请进入下钻页或重试读链路。",
      tone: "error",
    };
  }
  if (active.some((query) => queryIsInitialLoading(query))) {
    return {
      key,
      label,
      value: "读取中",
      detail: "等待既有 API 返回。",
      tone: "muted",
    };
  }
  if (active.every((query) => !query?.data)) {
    return {
      key,
      label,
      value: "暂无数据",
      detail: "后端返回为空或该能力待接入。",
      tone: "watch",
    };
  }
  return {
    key,
    label,
    value: "已返回",
    detail: readyDetail,
    tone: "ok",
  };
}

function buildDetailPanel(args: {
  key: string;
  title: string;
  meta: string;
  status: ModuleHomeStatus;
  rows: ModuleHomeDetailRow[];
  sections?: ModuleHomeDetailSection[];
  chart?: ModuleHomeDetailChart;
}): ModuleHomeDetailPanel {
  const ready = args.status.tone === "ok";
  const sections = ready ? args.sections : undefined;
  return {
    key: args.key,
    title: args.title,
    meta: args.meta,
    stateLabel: args.status.value,
    stateDetail: args.status.detail,
    rows: ready ? args.rows : [],
    sections,
    tone: args.status.tone,
    chart: ready ? args.chart : undefined,
  };
}

function flattenDetailSections(sections: ModuleHomeDetailSection[]): ModuleHomeDetailRow[] {
  return sections.flatMap((section) => section.rows);
}

function findMacroPoint(
  latestSeries: ChoiceMacroLatestPoint[],
  rateSeries: ChoiceMacroLatestPoint[],
  seriesIds: string[],
  nameIncludes?: string[],
): ChoiceMacroLatestPoint | undefined {
  const combined = [...rateSeries, ...latestSeries];
  for (const seriesId of seriesIds) {
    const found = combined.find((item) => item.series_id === seriesId);
    if (found) {
      return found;
    }
  }
  if (nameIncludes) {
    for (const token of nameIncludes) {
      const found = combined.find((item) => item.series_name.includes(token));
      if (found) {
        return found;
      }
    }
  }
  return undefined;
}

function macroPointToDetailRow(
  point: ChoiceMacroLatestPoint,
  label: string,
  source: string,
): ModuleHomeDetailRow {
  const change = formatChoiceMacroDelta(point, { spaceBeforeUnit: false, emptyDisplay: "" });
  return {
    key: point.series_id,
    label,
    value: formatChoiceMacroValue(point, { spaceBeforeUnit: false }),
    tradeDate: point.trade_date,
    source,
    tone: "ok",
    detail: change || undefined,
  };
}

function rateSnapshotChange(deltaText: string | undefined): string | undefined {
  if (!deltaText || deltaText === "-" || deltaText === "无变动") {
    return undefined;
  }
  return deltaText;
}

function pushRateQuoteRow(
  rows: ModuleHomeDetailRow[],
  seen: Set<string>,
  matched: MarketDataRateQuoteRow,
  label: string,
  key: string,
) {
  if (seen.has(matched.key)) {
    return;
  }
  seen.add(matched.key);
  rows.push({
    key,
    label,
    value: matched.rateText,
    tradeDate: matched.tradeDate,
    source: matched.seriesId,
    tone: "ok",
    detail: rateSnapshotChange(matched.deltaText),
  });
}

function pushMoneyMarketRow(
  rows: ModuleHomeDetailRow[],
  seen: Set<string>,
  matched: MarketDataMoneyMarketRow,
  label: string,
  key: string,
) {
  if (seen.has(matched.key)) {
    return;
  }
  seen.add(matched.key);
  rows.push({
    key,
    label,
    value: matched.rateText,
    tradeDate: matched.tradeDate,
    source: matched.seriesId,
    tone: "ok",
    detail: rateSnapshotChange(matched.deltaText),
  });
}

type HomeKeyRatePick =
  | {
      key: string;
      label: string;
      kind: "rate";
      match: (row: MarketDataRateQuoteRow) => boolean;
    }
  | {
      key: string;
      label: string;
      kind: "money";
      match: (row: MarketDataMoneyMarketRow) => boolean;
    }
  | {
      key: string;
      label: string;
      kind: "macro";
      seriesIds: string[];
      nameIncludes?: string[];
    };

const HOME_KEY_RATE_PICKS: HomeKeyRatePick[] = [
  {
    key: "gov-10y",
    label: "10Y 国债",
    kind: "rate",
    match: (row) => row.variety === "国债" && row.tenor === "10Y",
  },
  {
    key: "gov-2y",
    label: "2Y 国债",
    kind: "rate",
    match: (row) => row.variety === "国债" && row.tenor === "2Y",
  },
  {
    key: "gov-1y",
    label: "1Y 国债",
    kind: "rate",
    match: (row) => row.variety === "国债" && row.tenor === "1Y",
  },
  {
    key: "gov-3y",
    label: "3Y 国债",
    kind: "rate",
    match: (row) => row.variety === "国债" && row.tenor === "3Y",
  },
  {
    key: "gov-5y",
    label: "5Y 国债",
    kind: "rate",
    match: (row) => row.variety === "国债" && row.tenor === "5Y",
  },
  {
    key: "gov-30y",
    label: "30Y 国债",
    kind: "rate",
    match: (row) => row.variety === "国债" && row.tenor === "30Y",
  },
  {
    key: "gov-7y",
    label: "7Y 国债",
    kind: "rate",
    match: (row) => row.variety === "国债" && row.tenor === "7Y",
  },
  {
    key: "cdb-10y",
    label: "10Y 国开",
    kind: "rate",
    match: (row) => row.variety === "国开" && row.tenor === "10Y",
  },
  {
    key: "cdb-5y",
    label: "5Y 国开",
    kind: "rate",
    match: (row) => row.variety === "国开" && row.tenor === "5Y",
  },
  {
    key: "cdb-3y",
    label: "3Y 国开",
    kind: "rate",
    match: (row) => row.variety === "国开" && row.tenor === "3Y",
  },
  {
    key: "cdb-1y",
    label: "1Y 国开",
    kind: "rate",
    match: (row) => row.variety === "国开" && row.tenor === "1Y",
  },
  {
    key: "dr007",
    label: "DR007",
    kind: "money",
    match: (row) => row.name === "DR007",
  },
  {
    key: "r007",
    label: "R007",
    kind: "macro",
    seriesIds: ["CA.R007", "M003", "EMM00167614"],
    nameIncludes: ["R007", "R-007", "质押式回购加权利率:R007"],
  },
  {
    key: "omo-7d",
    label: "7天逆回购",
    kind: "macro",
    seriesIds: ["M001"],
    nameIncludes: ["7天逆回购", "公开市场7天"],
  },
  {
    key: "ncd-3m",
    label: "3M NCD",
    kind: "macro",
    seriesIds: ["NCD.SHIBOR.3M", "M0041813"],
    nameIncludes: ["3M NCD", "NCD"],
  },
  {
    key: "aa-5y",
    label: "5Y AA信用",
    kind: "macro",
    seriesIds: ["EMM00166683", "legacy.yield.choice.aa_credit.5Y"],
    nameIncludes: ["5Y AA", "AA 信用", "AA信用"],
  },
  {
    key: "shibor-on",
    label: "SHIBOR 隔夜",
    kind: "macro",
    seriesIds: ["EMM00166252"],
    nameIncludes: ["SHIBOR 隔夜", "Shibor 隔夜", "SHIBOR隔夜"],
  },
];

function mergeDerivedSpreads(
  formal: Partial<Record<string, number | null>> | undefined,
  latest: Partial<Record<string, number | null>> | undefined,
): Partial<Record<string, number | null>> | undefined {
  if (!formal && !latest) {
    return undefined;
  }
  const keys = new Set([...Object.keys(formal ?? {}), ...Object.keys(latest ?? {})]);
  const merged: Partial<Record<string, number | null>> = {};
  for (const key of keys) {
    const formalValue = formal?.[key];
    if (formalValue !== null && formalValue !== undefined && Number.isFinite(formalValue)) {
      merged[key] = formalValue;
      continue;
    }
    const latestValue = latest?.[key];
    if (latestValue !== null && latestValue !== undefined && Number.isFinite(latestValue)) {
      merged[key] = latestValue;
    }
  }
  return Object.keys(merged).length > 0 ? merged : undefined;
}

function buildDerivedSpreadRows(
  derivedSpreads: Partial<Record<string, number | null>> | undefined,
  tradeDate: string,
): ModuleHomeDetailRow[] {
  if (!derivedSpreads) {
    return [];
  }
  const rows: ModuleHomeDetailRow[] = [];
  const spreadSpecs: Array<{ key: string; label: string; field: string }> = [
    { key: "term-spread-10y-2y", label: "10Y-2Y 利差", field: "term_spread_10y_2y" },
    { key: "term-spread-10y-1y", label: "10Y-1Y 利差", field: "term_spread_10y_1y" },
    { key: "term-spread-10y-5y", label: "10Y-5Y 利差", field: "term_spread_10y_5y" },
    { key: "credit-spread-aa-3y", label: "AA-3Y 信用利差", field: "credit_spread_aa_3y" },
  ];
  for (const spec of spreadSpecs) {
    const value = derivedSpreads[spec.field];
    if (value === null || value === undefined || !Number.isFinite(value)) {
      continue;
    }
    rows.push({
      key: spec.key,
      label: spec.label,
      value: `${value.toFixed(1)} bp`,
      tradeDate,
      source: "market_derived",
      tone: "ok",
    });
  }
  return rows;
}

function buildMarketKeyRateRows(
  latestSeries: ChoiceMacroLatestPoint[],
  rateSeries: ChoiceMacroLatestPoint[],
  terminalModel: ReturnType<typeof buildMarketDataTerminalModel>,
): ModuleHomeDetailRow[] {
  const rows: ModuleHomeDetailRow[] = [];
  const seen = new Set<string>();

  for (const pick of HOME_KEY_RATE_PICKS) {
    if (pick.kind === "rate") {
      const matched = terminalModel.rateQuotes.rows.find(pick.match);
      if (!matched) {
        continue;
      }
      pushRateQuoteRow(rows, seen, matched, pick.label, pick.key);
      continue;
    }
    if (pick.kind === "money") {
      const matched = terminalModel.moneyMarket.rows.find(pick.match);
      if (!matched) {
        continue;
      }
      pushMoneyMarketRow(rows, seen, matched, pick.label, pick.key);
      continue;
    }
    const point = findMacroPoint(latestSeries, rateSeries, pick.seriesIds, pick.nameIncludes);
    if (!point || seen.has(point.series_id)) {
      continue;
    }
    seen.add(point.series_id);
    rows.push(macroPointToDetailRow(point, pick.label, point.series_id));
  }

  for (const matched of terminalModel.rateQuotes.rows) {
    if (rows.length >= 14) {
      break;
    }
    pushRateQuoteRow(rows, seen, matched, `${matched.variety} ${matched.tenor}`, matched.key);
  }

  for (const matched of terminalModel.moneyMarket.rows) {
    if (rows.length >= 14) {
      break;
    }
    pushMoneyMarketRow(rows, seen, matched, matched.name, matched.key);
  }

  return rows.slice(0, 14);
}

function catalogTierCounts(series: MacroVendorSeries[]) {
  const tiers: Record<string, number> = {
    stable: 0,
    fallback: 0,
    isolated: 0,
    other: 0,
  };
  for (const item of series) {
    const tier = item.refresh_tier ?? "other";
    if (tier in tiers) {
      tiers[tier] += 1;
    } else {
      tiers.other += 1;
    }
  }
  return tiers;
}

function portfolioKpiSparkline(
  current: Numeric | number | null | undefined,
  previous: Numeric | number | null | undefined,
): readonly number[] | undefined {
  const currentRaw =
    typeof current === "number"
      ? current
      : current === null || current === undefined
        ? null
        : nativeToNumber(current);
  const previousRaw =
    typeof previous === "number"
      ? previous
      : previous === null || previous === undefined
        ? null
        : nativeToNumber(previous);
  if (currentRaw === null || previousRaw === null) {
    return undefined;
  }
  return [previousRaw, currentRaw];
}

function portfolioKpiMomDetail(
  field: keyof BondDashboardHeadlinePayload["kpis"],
  current: Numeric | number | null | undefined,
  previous: Numeric | number | null | undefined,
): string | null {
  if (field === "bond_count") {
    const currentCount = typeof current === "number" ? current : null;
    const previousCount = typeof previous === "number" ? previous : null;
    if (currentCount === null || previousCount === null) {
      return null;
    }
    const diff = currentCount - previousCount;
    return `较前日 ${diff >= 0 ? "+" : ""}${diff} 只`;
  }
  if (typeof current !== "object" || current === null || typeof previous !== "object" || previous === null) {
    return null;
  }
  const mom = formatMomRatio(current, previous);
  return mom ? `环比 ${mom}` : null;
}

function enrichPortfolioKpis(
  kpis: ModuleHomeKpi[],
  bondHeadline: BondDashboardHeadlinePayload | undefined,
  bondKpiDefs: Array<{
    key: string;
    field?: keyof BondDashboardHeadlinePayload["kpis"];
  }>,
): ModuleHomeKpi[] {
  const bondKpis = bondHeadline?.kpis;
  const prevKpis = bondHeadline?.prev_kpis;
  if (!bondKpis || !prevKpis) {
    return kpis;
  }

  return kpis.map((kpi) => {
    const def = bondKpiDefs.find((item) => item.key === kpi.key);
    if (!def?.field) {
      return kpi;
    }
    const field = def.field;
    const sparkline = portfolioKpiSparkline(bondKpis[field], prevKpis[field]);
    const momDetail = portfolioKpiMomDetail(field, bondKpis[field], prevKpis[field]);
    if (!sparkline && !momDetail) {
      return kpi;
    }
    return {
      ...kpi,
      sparkline,
      detail: momDetail ? `${kpi.detail} · ${momDetail}` : kpi.detail,
    };
  });
}

function formatBondHeadlineKpi(
  key: keyof BondDashboardHeadlinePayload["kpis"],
  value: Numeric | number | null | undefined,
) {
  if (value === null || value === undefined) {
    return "-";
  }
  if (key === "bond_count") {
    const count = typeof value === "number" ? value : nativeToNumber(value);
    if (count === null) {
      return "-";
    }
    return `${count.toLocaleString("zh-CN", { maximumFractionDigits: 0 })} 只`;
  }
  if (typeof value !== "object" || !("raw" in value)) {
    return "-";
  }
  if (key === "total_market_value" || key === "unrealized_pnl") {
    return `${formatYi(value)} 亿元`;
  }
  if (key === "weighted_ytm" || key === "weighted_coupon") {
    return `${formatRatePercent(value)}%`;
  }
  if (key === "credit_spread_median") {
    return value.unit === "bp" ? `${formatBp(value)} bp` : `${formatRatePercent(value)}%`;
  }
  if (key === "weighted_duration") {
    return `${formatYears(value)} 年`;
  }
  if (key === "total_dv01") {
    return `${formatDv01Wan(value)} 万元`;
  }
  return plain(value);
}

function distributionRows(
  items: Array<{ key: string; label: string; marketValue: Numeric; percentage: Numeric | null }>,
  totalMarketValue?: Numeric,
  options: { emptyLabel?: string } = {},
): ModuleHomeDistributionRow[] {
  const totalRaw =
    totalMarketValue !== undefined
      ? (nativeToNumber(totalMarketValue) ?? 0)
      : items.reduce((sum, item) => sum + (nativeToNumber(item.marketValue) ?? 0), 0);

  return items.map((item) => {
    const mvRaw = nativeToNumber(item.marketValue);
    const barPct = totalRaw > 0 && mvRaw !== null ? (mvRaw / totalRaw) * 100 : 0;
    const share = item.percentage ? plain(item.percentage) : "-";
    return {
      key: item.key,
      label: item.label?.trim() || options.emptyLabel || "未分类",
      marketValue: `${formatYi(item.marketValue)} 亿元`,
      share,
      barPct: Math.min(100, Math.max(0, barPct)),
      tone: mvRaw !== null && mvRaw > 0 ? "ok" : "muted",
    };
  });
}

function zqtzAssetCnyMarketValue(balanceBasis: BalanceAnalysisBasisBreakdownPayload | undefined) {
  if (!balanceBasis) {
    return null;
  }
  const rows = balanceBasis.rows.filter(
    (row) =>
      row.source_family === "zqtz" &&
      row.position_scope === "asset" &&
      row.currency_basis === "CNY",
  );
  if (rows.length === 0) {
    return null;
  }
  return rows.reduce((sum, row) => sum + (decimalToNumber(row.market_value_amount) ?? 0), 0);
}

function ratingTieOutSubtitle(
  assetRating: AssetStructurePayload | undefined,
  balanceBasis: BalanceAnalysisBasisBreakdownPayload | undefined,
) {
  if (!assetRating) {
    return undefined;
  }
  const ratingTotal = nativeToNumber(assetRating.total_market_value);
  const basisTotal = zqtzAssetCnyMarketValue(balanceBasis);
  const tieOut =
    ratingTotal !== null && basisTotal !== null
      ? `正式余额核对差异 ${((ratingTotal - basisTotal) / YUAN_PER_YI).toLocaleString("zh-CN", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        })} 亿`
      : "正式余额核对待 basis 分解返回";
  return `ZQTZ 资产端 CNY；${tieOut}；无评级含利率债或未填评级。`;
}

function buildDistributionPanel(args: {
  key: string;
  title: string;
  reportDate: string;
  query: UseQueryResult<unknown> | undefined;
  rows: ModuleHomeDistributionRow[];
  readyDetail: string;
  totalMarketValue?: Numeric;
  subtitle?: string;
  viewAllPath?: string;
}): ModuleHomeDistributionPanel {
  const status = queryStatus(args.key, args.title, args.query, args.readyDetail);
  const emptyReadyStatus: ModuleHomeStatus | null =
    status.tone === "ok" && args.rows.length === 0
      ? {
          key: args.key,
          label: args.title,
          value: "明细为空",
          detail: `${args.title}明细为空；正式读链路已返回但无分组行，请复核源表过滤条件。`,
          tone: "watch",
        }
      : null;
  const panelStatus = emptyReadyStatus ?? status;
  return {
    key: args.key,
    title: args.title,
    meta: bondDashboardMeta(args.reportDate),
    stateLabel: panelStatus.value,
    stateDetail: panelStatus.detail,
    rows: panelStatus.tone === "ok" ? args.rows : [],
    tone: panelStatus.tone,
    totalDisplay:
      panelStatus.tone === "ok" && args.totalMarketValue !== undefined
        ? `${formatYi(args.totalMarketValue)} 亿`
        : undefined,
    subtitle: panelStatus.tone === "ok" ? args.subtitle : undefined,
    viewAllPath: args.viewAllPath,
  };
}

function baseDataNote(
  kind: ModuleWorkbenchHomeKind,
  queries: ModuleHomeSourceQueries,
): ModuleHomeDataNote {
  const config = moduleWorkbenchHomeConfigs[kind];
  const errorLines = Object.values(queries)
    .filter((query) => query?.isError)
    .map(() => "读取失败：不使用前端补数。");
  return {
    title: "数据说明",
    lines: [...config.dataNotes, ...errorLines],
    tone: errorLines.length > 0 ? "error" : "ok",
  };
}

function metaEvidenceLine(label: string, meta: ResultMeta | undefined): string | null {
  if (!meta) {
    return null;
  }
  const reportDate =
    meta.resolved_report_date ??
    meta.as_of_date ??
    meta.requested_report_date ??
    meta.fallback_date ??
    "-";
  const table = meta.tables_used?.length ? meta.tables_used.join(" / ") : "未披露";
  const rows =
    typeof meta.evidence_rows === "number" ? `${meta.evidence_rows} 行` : "未披露";
  const fallback =
    meta.fallback_mode === "none" && !meta.fallback_date
      ? "none"
      : `${meta.fallback_mode}${meta.fallback_date ? `/${meta.fallback_date}` : ""}`;
  return `${label}证据：report_date=${reportDate}；basis=${meta.basis}；formal_use_allowed=${String(
    meta.formal_use_allowed,
  )}；quality=${meta.quality_flag}；result_kind=${meta.result_kind}；tables=${table}；evidence_rows=${rows}；fallback=${fallback}。`;
}

function portfolioDataNote(queries: ModuleHomeSourceQueries): ModuleHomeDataNote {
  const base = baseDataNote("portfolio", queries);
  const evidenceLines = [
    metaEvidenceLine("债券总览", queries.bondHeadline?.data?.result_meta),
    metaEvidenceLine("资产负债", queries.balanceOverview?.data?.result_meta),
    metaEvidenceLine("损益归因", queries.pnlSummary?.data?.result_meta),
  ].filter((line): line is string => Boolean(line));

  return {
    ...base,
    lines: [...base.lines, ...evidenceLines],
  };
}

function balanceSourceMeta(reportDate: string) {
  return `来源 balance-analysis · ${reportDate || "-"}`;
}

function buildRiskIndicatorDetailRows(risk: RiskIndicatorsPayload): ModuleHomeDetailRow[] {
  const reportDate = risk.report_date;
  return [
    {
      key: "risk-total-market-value",
      label: "组合市值",
      value: `${formatYi(risk.total_market_value)} 亿元`,
      tradeDate: reportDate,
      source: "total_market_value",
      tone: "ok",
    },
    {
      key: "risk-total-dv01",
      label: "DV01",
      value: `${formatDv01Wan(risk.total_dv01)} 万元`,
      tradeDate: reportDate,
      source: "total_dv01",
      tone: "ok",
    },
    {
      key: "risk-weighted-duration",
      label: "加权久期",
      value: `${formatYears(risk.weighted_duration)} 年`,
      tradeDate: reportDate,
      source: "weighted_duration",
      tone: "ok",
    },
    {
      key: "risk-credit-ratio",
      label: "信用占比",
      value: `${formatRatePercent(risk.credit_ratio)}%`,
      tradeDate: reportDate,
      source: "credit_ratio",
      tone: "ok",
    },
    {
      key: "risk-weighted-convexity",
      label: "凸性(加权)",
      value: (() => {
        const raw = nativeToNumber(risk.weighted_convexity);
        return raw === null ? "-" : raw.toFixed(4);
      })(),
      tradeDate: reportDate,
      source: "weighted_convexity",
      tone: "ok",
    },
    {
      key: "risk-spread-dv01",
      label: "利差 DV01",
      value: `${formatDv01Wan(risk.total_spread_dv01)} 万元`,
      tradeDate: reportDate,
      source: "total_spread_dv01",
      tone: "ok",
    },
    {
      key: "risk-reinvestment-ratio",
      label: "1年内再投资占比",
      value: `${formatRatePercent(risk.reinvestment_ratio_1y)}%`,
      tradeDate: reportDate,
      source: "reinvestment_ratio_1y",
      tone: "ok",
    },
  ];
}

function buildPortfolioComparisonRows(
  payload: PortfolioComparisonPayload,
): ModuleHomeDetailRow[] {
  return payload.items
    .slice(0, 8)
    .map((item, index) => {
      const portfolioLabel = item.portfolio_name.trim() || `未命名组合 ${index + 1}`;
      return {
        key: `portfolio-${portfolioLabel}`,
        label: portfolioLabel,
        value: `${formatYi(item.total_market_value)} 亿`,
        tradeDate: payload.report_date,
        source: `DV01 ${formatDv01Wan(item.total_dv01)} 万 · ${item.bond_count} 只`,
        tone: "ok",
        scaleDisplay: `${formatYi(item.total_market_value)} 亿`,
        durationDisplay: `${formatYears(item.weighted_duration)} 年`,
        ytmDisplay: `${formatRatePercent(item.weighted_ytm)}%`,
        dv01Display: `${formatDv01Wan(item.total_dv01)} 万`,
        countDisplay: item.bond_count.toLocaleString("zh-CN"),
      };
    });
}

function parseRatePercent(value: string): number | null {
  const match = value.match(/([\d.]+)/);
  if (!match) {
    return null;
  }
  const parsed = Number.parseFloat(match[1]);
  return Number.isFinite(parsed) ? parsed : null;
}

function isPercentRateRow(row: ModuleHomeDetailRow): boolean {
  if (!row.value.includes("%")) {
    return false;
  }
  const parsed = parseRatePercent(row.value);
  return parsed !== null && parsed >= 0 && parsed <= 20;
}

function buildPercentRateChart(
  rows: ModuleHomeDetailRow[],
  title: string,
): ModuleHomeDetailChart | undefined {
  const parsed = rows
    .filter(isPercentRateRow)
    .map((row) => ({ label: row.label, value: parseRatePercent(row.value)! }));
  if (parsed.length < 2) {
    return undefined;
  }
  return {
    title,
    unit: "%",
    orientation: "horizontal",
    categories: parsed.map((item) => item.label),
    values: parsed.map((item) => item.value),
  };
}

const MACRO_SNAPSHOT_PRIORITY_IDS = [
  "CA.CSI300",
  "CA.CSI300_PCT_CHG",
  "CA.CSI300_PE",
  "CA.BRENT",
  "CA.COPPER",
  "CA.ALUMINUM",
  "CA.USD_CNY",
  "CA.USDCNY",
  "CA.HSI",
  "CA.SPX",
] as const;

function buildYieldCurveQuoteRows(
  terminalModel: ReturnType<typeof buildMarketDataTerminalModel>,
): ModuleHomeDetailRow[] {
  return terminalModel.rateQuotes.rows.map((row) => ({
    key: row.key,
    label: `${row.variety} ${row.tenor}`,
    value: row.deltaText && row.deltaText !== "-" ? `${row.rateText} · ${row.deltaText}` : row.rateText,
    tradeDate: row.tradeDate,
    source: row.seriesId,
    tone: "ok" as ModuleHomeTone,
  }));
}

function buildLatestMacroSnapshotRows(
  latestSeries: ChoiceMacroLatestPoint[],
  excludeSeriesIds: Set<string>,
): ModuleHomeDetailRow[] {
  const byId = new Map(latestSeries.map((point) => [point.series_id, point]));
  const rows: ModuleHomeDetailRow[] = [];
  const seen = new Set<string>();

  for (const seriesId of MACRO_SNAPSHOT_PRIORITY_IDS) {
    const point = byId.get(seriesId);
    if (!point || seen.has(point.series_id) || excludeSeriesIds.has(point.series_id)) {
      continue;
    }
    seen.add(point.series_id);
    rows.push(macroPointToDetailRow(point, point.series_name, point.series_id));
  }

  for (const point of latestSeries) {
    if (rows.length >= 24) {
      break;
    }
    if (seen.has(point.series_id) || excludeSeriesIds.has(point.series_id)) {
      continue;
    }
    if (point.series_id.startsWith("CA.") || /指数|期货|Brent|原油|铜|铝|汇率/.test(point.series_name)) {
      seen.add(point.series_id);
      rows.push(macroPointToDetailRow(point, point.series_name, point.series_id));
    }
  }

  return rows;
}

function buildNewsEventsSnapshotRows(
  payload: ChoiceNewsEventsPayload | undefined,
): ModuleHomeDetailRow[] {
  if (!payload || payload.events.length === 0) {
    return [];
  }
  const rows: ModuleHomeDetailRow[] = [
    {
      key: "news-events-total",
      label: "事件总数",
      value: `${payload.total_rows} 条`,
      tradeDate: "-",
      source: "choice-events",
      tone: payload.total_rows > 0 ? "ok" : "muted",
    },
  ];
  for (const [index, event] of payload.events.slice(0, 5).entries()) {
    const headline = summarizeMacroNewsEvent(event);
    rows.push({
      key: `news-event-${event.event_key || index}`,
      label: event.topic_code || "新闻事件",
      value: headline || event.payload_text?.trim() || "待解析标题",
      detail: event.received_at?.slice(0, 10) ?? undefined,
      tradeDate: event.received_at?.slice(0, 10) ?? "-",
      source: event.content_type || "choice-events",
      tone: event.error_code === 0 ? "ok" : "watch",
    });
  }
  return rows;
}

function macroToolkitModuleTone(tone: string): ModuleHomeTone {
  if (tone === "positive" || tone === "complete") {
    return "ok";
  }
  if (tone === "negative" || tone === "unavailable") {
    return "error";
  }
  if (tone === "degraded" || tone === "neutral") {
    return "watch";
  }
  return "muted";
}

function formatMacroToolkitPrimaryMetric(
  metric: { label: string; value: string | number; unit: string } | null,
): string {
  if (!metric) {
    return "-";
  }
  const unit = metric.unit ? ` ${metric.unit}` : "";
  return `${metric.value}${unit}`;
}

function pickMacroSignalChangeDetail(evidence: string[]): string | undefined {
  return evidence.find((line) => {
    const trimmed = line.trim();
    if (/^(?:score|regime|percentile)=/i.test(trimmed)) {
      return false;
    }
    return /bp|日变动|[+-]\d/.test(trimmed);
  });
}

export const MARKET_HOME_MACRO_SIGNAL_ORDER = [
  "crisis_score_cn",
  "liquidity",
  "credit",
  "risk_appetite",
  "a_share_stampede_risk",
] as const;

function marketHomeMacroSignalSortIndex(key: string): number {
  const index = MARKET_HOME_MACRO_SIGNAL_ORDER.indexOf(key as (typeof MARKET_HOME_MACRO_SIGNAL_ORDER)[number]);
  return index === -1 ? MARKET_HOME_MACRO_SIGNAL_ORDER.length : index;
}

export const MARKET_CURVE_TERM_SPREAD_KEYS = [
  "term-spread-10y-2y",
  "term-spread-10y-5y",
  "term-spread-10y-1y",
] as const;

const MARKET_CURVE_CREDIT_SPREAD_MATCHERS = [
  "credit-spread",
  "credit_spread",
  "信用利差",
  "aa-国债",
  "aa5y",
] as const;

export function findMarketCreditSpreadRow(rows: ModuleHomeDetailRow[]): ModuleHomeDetailRow | undefined {
  return rows.find((row) => {
    if (row.key.startsWith("term-spread-")) {
      return false;
    }
    const haystack = `${row.key} ${row.label}`.toLowerCase();
    return MARKET_CURVE_CREDIT_SPREAD_MATCHERS.some((token) => haystack.includes(token.toLowerCase()));
  });
}

export function buildMarketCurveSpreadRows(keyRatePanel?: ModuleHomeDetailPanel): {
  termSpreadRows: ModuleHomeDetailRow[];
  creditSpreadRow?: ModuleHomeDetailRow;
} {
  const rows = keyRatePanel?.rows ?? [];
  const termSpreadRows = MARKET_CURVE_TERM_SPREAD_KEYS.map((key) => rows.find((row) => row.key === key)).filter(
    (row): row is ModuleHomeDetailRow => Boolean(row),
  );
  const creditSpreadRow = findMarketCreditSpreadRow(rows);
  return { termSpreadRows, creditSpreadRow };
}

const MARKET_CURVE_SHAPE_LABELS: Record<string, string> = {
  Inverted: "倒挂",
  Flat: "平坦",
  Hump: "驼峰",
  ModerateSteep: "中度陡峭",
  NormalSteep: "偏陡",
  Unavailable: "不可用",
};

const MARKET_DESK_INTEL_INDICATOR_LIMIT = 6;

function crisisHistoryDelta(history: MarketCrisisHistoryPoint[]): {
  scoreDelta: number | null;
  percentileDelta: number | null;
} {
  if (history.length < 2) {
    return { scoreDelta: null, percentileDelta: null };
  }
  const first = history[0];
  const last = history[history.length - 1];
  const scoreDelta =
    first && last && Number.isFinite(first.crisisScore) && Number.isFinite(last.crisisScore)
      ? Number((last.crisisScore - first.crisisScore).toFixed(4))
      : null;
  const percentileDelta =
    first?.percentile !== null &&
    first?.percentile !== undefined &&
    last?.percentile !== null &&
    last?.percentile !== undefined
      ? Number((last.percentile - first.percentile).toFixed(2))
      : null;
  return { scoreDelta, percentileDelta };
}

function readCrisisResultNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function buildMarketDeskIntel(
  analysis: MacroToolkitAnalysisPayload | null | undefined,
): MarketDeskIntelView | null {
  if (!analysis) {
    return null;
  }

  const curveCapability = analysis.capability_results.find((item) => item.key === "yield_curve_shape");
  const curveResult = curveCapability?.result ?? {};
  const curveShape = readCrisisResultString(curveResult.shape);
  const spreads =
    curveResult.spreads && typeof curveResult.spreads === "object"
      ? (curveResult.spreads as Record<string, unknown>)
      : {};
  const spread10y1yRaw = spreads["10Y-1Y"];
  const spread10y1yBp =
    typeof spread10y1yRaw === "number"
      ? spread10y1yRaw
      : typeof spread10y1yRaw === "string"
        ? readCrisisResultNumber(Number.parseFloat(spread10y1yRaw))
        : readCrisisResultNumber(spread10y1yRaw);

  const indicators = analysis.indicators
    .filter((indicator) => indicator.latest_value !== null && indicator.latest_value !== undefined)
    .slice(0, MARKET_DESK_INTEL_INDICATOR_LIMIT)
    .map((indicator) => {
      const changeText =
        indicator.change_pct !== null && indicator.change_pct !== undefined
          ? ` · ${indicator.change_pct >= 0 ? "+" : ""}${indicator.change_pct.toFixed(2)}%`
          : "";
      return {
        key: indicator.key,
        label: indicator.label,
        value: `${indicator.latest_value}${indicator.unit ?? ""}${changeText}`,
        group: indicator.group,
        tone: (indicator.quality === "ok" ? "ok" : "watch") as ModuleHomeTone,
      };
    });

  if (!curveShape && indicators.length === 0) {
    return null;
  }

  return {
    curveShape,
    curveShapeLabel: curveShape ? MARKET_CURVE_SHAPE_LABELS[curveShape] ?? curveShape : null,
    curveInterpretation: readCrisisResultString(curveResult.interpretation),
    spread10y1yBp,
    curvePercentile1y: readCrisisResultNumber(curveResult.percentile_1y),
    indicators,
  };
}

function readCrisisResultString(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function readMarketCrisisScoreHistory(raw: unknown): MarketCrisisHistoryPoint[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw
    .map((item) => {
      if (!item || typeof item !== "object") {
        return null;
      }
      const point = item as Record<string, unknown>;
      const crisisScore = readCrisisResultNumber(point.crisis_score);
      const date = readCrisisResultString(point.date);
      if (crisisScore === null || !date) {
        return null;
      }
      return {
        date,
        crisisScore,
        percentile: readCrisisResultNumber(point.percentile),
      };
    })
    .filter((item): item is MarketCrisisHistoryPoint => Boolean(item));
}

export function buildMarketCrisisExplain(
  analysis: MacroToolkitAnalysisPayload | null | undefined,
): MarketCrisisExplainView | null {
  if (!analysis) {
    return null;
  }
  const capability = analysis.capability_results.find((item) => item.key === "crisis_score_cn");
  if (!capability) {
    return null;
  }
  const result = capability.result ?? {};
  const rawComponents = Array.isArray(result.components) ? result.components : [];
  const components: MarketCrisisExplainComponent[] = rawComponents
    .map((item) => {
      if (!item || typeof item !== "object") {
        return null;
      }
      const component = item as Record<string, unknown>;
      const key = readCrisisResultString(component.key) ?? "";
      if (!key) {
        return null;
      }
      return {
        key,
        label: readCrisisResultString(component.label) ?? key,
        zScore: readCrisisResultNumber(component.z_score),
        weight: readCrisisResultNumber(component.weight),
        rawValue: readCrisisResultNumber(component.raw_value),
      };
    })
    .filter((item): item is MarketCrisisExplainComponent => Boolean(item));
  const warnings = Array.isArray(result.warnings)
    ? result.warnings.map((item) => String(item).trim()).filter(Boolean)
    : capability.warnings ?? [];
  const scoreHistory = readMarketCrisisScoreHistory(result.score_history);
  const { scoreDelta, percentileDelta } = crisisHistoryDelta(scoreHistory);

  return {
    crisisScore: readCrisisResultNumber(result.crisis_score) ?? capability.score,
    regime: readCrisisResultString(result.regime),
    percentile: readCrisisResultNumber(result.percentile),
    headline: readCrisisResultString(result.headline) ?? capability.headline ?? null,
    recommendation: readCrisisResultString(result.recommendation),
    dataStatus: readCrisisResultString(result.data_status) ?? capability.status,
    availableComponentCount: readCrisisResultNumber(result.available_component_count),
    componentCount: readCrisisResultNumber(result.component_count),
    scoreDelta,
    percentileDelta,
    components,
    scoreHistory,
    warnings,
    tone: macroToolkitModuleTone(capability.status),
  };
}

function buildMacroToolkitSignalRows(analysis: MacroToolkitAnalysisPayload): ModuleHomeDetailRow[] {
  return analysis.signal_cards
    .map((card) => {
      const evidenceLines = card.evidence
        .map((line) => line.trim())
        .filter((line) => line.length > 0 && !/^(?:score|regime|percentile)=/i.test(line));
      const detail = evidenceLines.slice(0, 2).join(" · ") || pickMacroSignalChangeDetail(card.evidence);

      return {
        key: card.key,
        label: card.title,
        value: card.score !== null ? `${card.stance} · ${card.score}` : card.stance,
        detail,
        tradeDate: analysis.as_of_date ?? "-",
        source: formatMacroSignalEvidence(card.evidence) || "macro-toolkit",
        tone: macroToolkitModuleTone(card.tone),
      };
    })
    .sort((left, right) => marketHomeMacroSignalSortIndex(left.key) - marketHomeMacroSignalSortIndex(right.key));
}

function buildMacroToolkitCapabilityRows(analysis: MacroToolkitAnalysisPayload): ModuleHomeDetailRow[] {
  return analysis.capability_results.map((capability) => ({
    key: capability.key,
    label: capability.label,
    value: capability.headline || formatMacroToolkitPrimaryMetric(capability.primary_metric),
    tradeDate: analysis.as_of_date ?? "-",
    source: [capability.group, capability.evidence.join(" · ")].filter(Boolean).join(" · "),
    tone: macroToolkitModuleTone(capability.status),
  }));
}

function buildMacroToolkitIndicatorRows(indicators: MacroToolkitIndicator[]): ModuleHomeDetailRow[] {
  return indicators.map((indicator) => {
    const changeText =
      indicator.change_pct !== null && indicator.change_pct !== undefined
        ? ` · ${indicator.change_pct >= 0 ? "+" : ""}${indicator.change_pct.toFixed(2)}%`
        : "";
    const value =
      indicator.latest_value !== null
        ? `${indicator.latest_value}${indicator.unit ? indicator.unit : ""}${changeText}`
        : "-";
    return {
      key: indicator.key,
      label: indicator.label,
      value,
      tradeDate: indicator.latest_date ?? "-",
      source: [indicator.group, indicator.series_id ?? indicator.source].filter(Boolean).join(" · "),
      tone: indicator.quality === "ok" ? "ok" : "watch",
    };
  });
}

const A_SHARE_RISK_METRIC_ROWS: Array<{
  key: string;
  label: string;
  format?: "percent" | "ratio";
}> = [
  { key: "up_count", label: "上涨家数" },
  { key: "up_ratio", label: "上涨比例", format: "percent" },
  { key: "drop_3_count", label: "跌超3%家数" },
  { key: "drop_5_count", label: "跌超5%家数" },
  { key: "limit_down_count", label: "跌停家数" },
  { key: "near_down_count", label: "近跌停" },
  { key: "turnover_ratio_ma20", label: "成交额/20日", format: "ratio" },
  { key: "index_drawdown_from_high", label: "回落幅度", format: "percent" },
];

function formatMacroRiskMetric(value: number | null | undefined, format?: "percent" | "ratio"): string {
  if (value == null) {
    return "缺失";
  }
  if (format === "percent") {
    return `${(value * 100).toFixed(1)}%`;
  }
  if (format === "ratio") {
    return `${value.toFixed(2)}x`;
  }
  return String(value);
}

function aShareRiskModuleTone(risk: MacroToolkitAShareRiskPayload): ModuleHomeTone {
  if (risk.risk_level === "green") {
    return "ok";
  }
  if (risk.risk_level === "yellow") {
    return "watch";
  }
  if (risk.risk_level === "unknown") {
    return "muted";
  }
  return "error";
}

function buildMacroToolkitAShareRiskRows(risk: MacroToolkitAShareRiskPayload): ModuleHomeDetailRow[] {
  const tone = aShareRiskModuleTone(risk);
  const rows: ModuleHomeDetailRow[] = [
    {
      key: "a-share-score",
      label: "风险评分",
      value: risk.risk_score !== null ? String(risk.risk_score) : "缺失",
      tradeDate: risk.trade_date ?? "-",
      source: risk.risk_name,
      tone,
    },
    {
      key: "a-share-summary",
      label: "风险摘要",
      value: risk.summary,
      tradeDate: risk.trade_date ?? "-",
      source: risk.status,
      tone,
    },
    {
      key: "a-share-position",
      label: "仓位规则",
      value: risk.position_rule,
      tradeDate: "-",
      source: "position_rule",
      tone: "muted",
    },
  ];

  for (const metric of A_SHARE_RISK_METRIC_ROWS) {
    rows.push({
      key: `a-share-${metric.key}`,
      label: metric.label,
      value: formatMacroRiskMetric(risk.metrics[metric.key], metric.format),
      tradeDate: risk.trade_date ?? "-",
      source: "metrics",
      tone: "ok",
    });
  }

  for (const [index, rule] of risk.triggered_rules.entries()) {
    rows.push({
      key: `a-share-trigger-${index}`,
      label: "触发规则",
      value: rule,
      tradeDate: risk.trade_date ?? "-",
      source: "triggered_rules",
      tone: "watch",
    });
  }

  for (const [index, item] of risk.watch_next.entries()) {
    rows.push({
      key: `a-share-watch-${index}`,
      label: "观察条件",
      value: item,
      tradeDate: "-",
      source: "watch_next",
      tone: "muted",
    });
  }

  return rows;
}

function buildMacroToolkitHasonRows(strategy: MacroToolkitHasonStrategy): ModuleHomeDetailRow[] {
  const rows: ModuleHomeDetailRow[] = [
    {
      key: "hason-framework",
      label: "策略框架",
      value: strategy.framework_name,
      tradeDate: "-",
      source: strategy.boundary,
      tone: macroToolkitModuleTone(strategy.status),
    },
    {
      key: "hason-readiness",
      label: "模块就绪",
      value: `${strategy.readiness.ready_modules}/${strategy.readiness.total_modules} · ${(strategy.readiness.ratio * 100).toFixed(0)}%`,
      tradeDate: "-",
      source: `${strategy.readiness.partial_modules} 部分 / ${strategy.readiness.missing_modules} 缺失`,
      tone: strategy.readiness.ratio >= 0.7 ? "ok" : "watch",
    },
    {
      key: "hason-runtime",
      label: "运行时产物",
      value: strategy.runtime_output_status,
      tradeDate: "-",
      source: strategy.runtime_output_gaps.join(" / ") || strategy.required_runtime_outputs.join(" / ") || "-",
      tone: strategy.runtime_output_status === "current" ? "ok" : "watch",
    },
  ];

  for (const module of strategy.modules) {
    rows.push({
      key: `hason-${module.key}`,
      label: module.label,
      value: module.status,
      tradeDate: "-",
      source: module.available_scripts.join(" / ") || "无可用脚本",
      tone: module.missing_scripts.length > 0 ? "watch" : "ok",
    });
  }

  return rows;
}

function buildMacroToolkitShadowRows(report: MacroToolkitShadowPortfolioReport): ModuleHomeDetailRow[] {
  const rows: ModuleHomeDetailRow[] = [
    {
      key: "shadow-status",
      label: "报告状态",
      value: report.status,
      tradeDate: report.as_of_date ?? "-",
      source: report.basis,
      tone: report.status === "complete" ? "ok" : "watch",
    },
    {
      key: "shadow-periods",
      label: "完成周期",
      value: `${report.completed_periods} 期`,
      tradeDate: report.as_of_date ?? "-",
      source: report.rule_version,
      tone: report.completed_periods >= 12 ? "ok" : "watch",
    },
  ];

  if (report.benchmark) {
    rows.push({
      key: "shadow-benchmark",
      label: report.benchmark.label,
      value: `累计 ${(report.benchmark.total_return * 100).toFixed(2)}% · 回撤 ${(report.benchmark.max_drawdown * 100).toFixed(2)}%`,
      tradeDate: report.as_of_date ?? "-",
      source: report.benchmark.key,
      tone: "muted",
    });
  }

  for (const portfolio of report.portfolios) {
    const admission = portfolio.admission?.label ? ` · ${portfolio.admission.label}` : "";
    rows.push({
      key: `shadow-${portfolio.key}`,
      label: portfolio.label,
      value: `累计 ${(portfolio.total_return * 100).toFixed(2)}% · 超额 ${(portfolio.excess_return * 100).toFixed(2)}%${admission}`,
      tradeDate: report.as_of_date ?? "-",
      source: portfolio.role,
      tone: portfolio.total_return >= 0 ? "ok" : "watch",
    });
  }

  return rows;
}

function buildMacroToolkitRuntimeRows(analysis: MacroToolkitAnalysisPayload): ModuleHomeDetailRow[] {
  const rows: ModuleHomeDetailRow[] = [];

  if (analysis.cffex_member_rank) {
    const rank = analysis.cffex_member_rank;
    rows.push({
      key: "cffex-member-rank",
      label: "中金所会员排名",
      value: `${rank.status} · ${rank.row_count} 行`,
      tradeDate: rank.latest_trade_date ?? "-",
      source: `${rank.freshness_status} · ${rank.source_vendors?.join("/") ?? "-"}`,
      tone: rank.freshness_status === "current" ? "ok" : "watch",
    });
  }

  const refresh = analysis.choice_stock_refresh;
  if (refresh?.daily_observation) {
    const daily = refresh.daily_observation;
    rows.push({
      key: "choice-daily-observation",
      label: "Choice 日频观测",
      value: `${daily.status} · ${daily.stock_count ?? "-"} 只`,
      tradeDate: daily.latest_trade_date ?? "-",
      source: daily.freshness_status ?? "-",
      tone: daily.freshness_status === "current" ? "ok" : "watch",
    });
  }
  if (refresh?.factor_snapshot) {
    const factor = refresh.factor_snapshot;
    rows.push({
      key: "choice-factor-snapshot",
      label: "Choice 因子快照",
      value: `${factor.status} · ${factor.stock_count ?? "-"} 只`,
      tradeDate: factor.as_of_date ?? "-",
      source: factor.freshness_status ?? "-",
      tone: factor.freshness_status === "current" ? "ok" : "watch",
    });
  }

  for (const check of analysis.source_checks) {
    rows.push({
      key: `source-${check.alias}`,
      label: check.alias,
      value: check.latest
        ? `${check.latest.value} · ${check.latest.series_id}`
        : "未命中",
      tradeDate: check.latest?.date ?? "-",
      source: check.latest?.vendor_name ?? "-",
      tone: check.latest ? "ok" : "watch",
    });
  }

  for (const [index, warning] of analysis.warnings.entries()) {
    rows.push({
      key: `macro-warning-${index}`,
      label: "数据提示",
      value: warning,
      tradeDate: "-",
      source: "warnings",
      tone: "watch",
    });
  }

  return rows;
}

function buildMacroToolkitOverviewRows(analysis: MacroToolkitAnalysisPayload): ModuleHomeDetailRow[] {
  return [
    {
      key: "macro-summary",
      label: "结论摘要",
      value: analysis.conclusion.summary,
      tradeDate: analysis.as_of_date ?? "-",
      source: "conclusion",
      tone: macroToolkitModuleTone(analysis.conclusion.tone),
    },
    {
      key: "macro-stance",
      label: "工具立场",
      value: analysis.conclusion.stance,
      tradeDate: analysis.as_of_date ?? "-",
      source: "conclusion",
      tone: macroToolkitModuleTone(analysis.conclusion.tone),
    },
    {
      key: "macro-hit-rate",
      label: "指标命中率",
      value: `${analysis.coverage.hit_count}/${analysis.coverage.indicator_count} · ${(analysis.coverage.hit_rate * 100).toFixed(1)}%`,
      tradeDate: analysis.as_of_date ?? "-",
      source: "coverage",
      tone: analysis.coverage.hit_rate >= 0.7 ? "ok" : "watch",
    },
    {
      key: "macro-scripts",
      label: "注册脚本",
      value: `${analysis.coverage.script_count} 个 · 产物 ${analysis.coverage.output_file_count} 个`,
      tradeDate: analysis.as_of_date ?? "-",
      source: "toolkit",
      tone: analysis.coverage.script_count > 0 ? "ok" : "muted",
    },
    {
      key: "macro-action",
      label: "建议动作",
      value: analysis.conclusion.recommended_action,
      tradeDate: "-",
      source: "conclusion",
      tone: "muted",
    },
  ];
}

function mergeMacroToolkitAnalysis(
  analysis: MacroToolkitAnalysisPayload | undefined,
  strategyPayload: MacroToolkitStrategySummariesPayload | undefined,
): MacroToolkitAnalysisPayload | undefined {
  if (!analysis) {
    return undefined;
  }
  if (!strategyPayload) {
    return analysis;
  }
  return {
    ...analysis,
    strategy_summaries: analysis.strategy_summaries.length
      ? analysis.strategy_summaries
      : strategyPayload.strategy_summaries,
    shadow_portfolio_report:
      analysis.shadow_portfolio_report ?? strategyPayload.shadow_portfolio_report,
  };
}

function buildMacroToolkitStrategyRows(analysis: MacroToolkitAnalysisPayload): ModuleHomeDetailRow[] {
  return analysis.strategy_summaries.map((strategy) => ({
    key: strategy.key,
    label: strategy.label,
    value: formatMacroToolkitPrimaryMetric(strategy.primary_metric) || strategy.status,
    tradeDate: analysis.as_of_date ?? "-",
    source: [strategy.group, strategy.evidence.join(" · ")].filter(Boolean).join(" · "),
    tone: macroToolkitModuleTone(strategy.status),
  }));
}

function buildPortfolioComparisonChart(
  payload: PortfolioComparisonPayload,
): ModuleHomeDetailChart {
  const items = payload.items.slice(0, 8);
  return {
    title: "子组合市值规模",
    unit: "亿元",
    orientation: "horizontal",
    categories: items.map((item, index) => item.portfolio_name.trim() || `未命名组合 ${index + 1}`),
    values: items.map((item) => (nativeToNumber(item.total_market_value) ?? 0) / 1e8),
  };
}

function buildYieldDistributionChart(payload: YieldDistributionPayload): ModuleHomeDetailChart {
  const items = payload.items.slice(0, 8);
  return {
    title: "收益率桶市值分布",
    unit: "亿元",
    orientation: "vertical",
    categories: items.map((item) => item.yield_bucket),
    values: items.map((item) => (nativeToNumber(item.total_market_value) ?? 0) / 1e8),
  };
}

function buildSpreadAnalysisChart(payload: SpreadAnalysisPayload): ModuleHomeDetailChart {
  const items = payload.items.slice(0, 8);
  return {
    title: "券种规模分布",
    unit: "亿元",
    orientation: "horizontal",
    categories: items.map((item) => item.bond_type),
    values: items.map((item) => (nativeToNumber(item.total_market_value) ?? 0) / 1e8),
  };
}

function buildBusinessTypeChart(
  payload: BondBusinessTypeMetricsPayload["result"],
): ModuleHomeDetailChart {
  const items = payload.items.slice(0, 8);
  return {
    title: "业务类型市值分布",
    unit: "亿元",
    orientation: "horizontal",
    categories: items.map((item) => item.name),
    values: items.map((item) => Number(item.market_value) / 1e8),
  };
}

function buildYieldDistributionRows(payload: YieldDistributionPayload): ModuleHomeDetailRow[] {
  const rows = payload.items.slice(0, 8).map((item) => ({
    key: `yield-${item.yield_bucket}`,
    label: item.yield_bucket,
    value: `${formatYi(item.total_market_value)} 亿元`,
    tradeDate: payload.report_date,
    source: `${item.bond_count} 只`,
    tone: "ok" as ModuleHomeTone,
  }));
  if (rows.length > 0) {
    rows.unshift({
      key: "yield-weighted-ytm",
      label: "组合加权 YTM",
      value: `${formatRatePercent(payload.weighted_ytm)}%`,
      tradeDate: payload.report_date,
      source: "weighted_ytm",
      tone: "ok",
    });
  }
  return rows;
}

function buildSpreadAnalysisRows(payload: SpreadAnalysisPayload): ModuleHomeDetailRow[] {
  return payload.items.slice(0, 8).map((item) => ({
    key: `spread-${item.bond_type}`,
    label: item.bond_type,
    value: item.median_yield ? `${formatRatePercent(item.median_yield)}%` : "-",
    tradeDate: payload.report_date,
    source: `${formatYi(item.total_market_value)} 亿 · ${item.bond_count} 只`,
    tone: "ok",
  }));
}

function buildBusinessTypeRows(
  payload: BondBusinessTypeMetricsPayload["result"],
): ModuleHomeDetailRow[] {
  return payload.items.slice(0, 8).map((item) => ({
    key: `business-type-${item.name}`,
    label: item.name,
    value: `YTM ${item.weighted_avg_ytm_pct}% · 久期 ${item.weighted_avg_duration}`,
    tradeDate: payload.report_date,
    source: ["市值 " + formatYiFromYuan(item.market_value), item.duration_source]
      .filter((part) => part.trim().length > 0)
      .join(" · "),
    tone: "ok",
  }));
}

function buildBalanceBasisRows(
  payload: BalanceAnalysisBasisBreakdownPayload,
): ModuleHomeDetailRow[] {
  return payload.rows.slice(0, 10).map((row, index) => ({
    key: `basis-${row.source_family}-${row.accounting_basis}-${index}`,
    label: `${row.source_family.toUpperCase()} · ${row.invest_type_std} · ${row.accounting_basis}`,
    value: formatYiFromYuan(row.market_value_amount),
    tradeDate: payload.report_date,
    source: `摊余 ${formatYiFromYuan(row.amortized_cost_amount)} · 应计 ${formatYiFromYuan(row.accrued_interest_amount)}`,
    tone: "ok",
  }));
}

function buildPnlSummaryRows(summary: PnlAttributionAnalysisSummary): ModuleHomeDetailRow[] {
  const rows: ModuleHomeDetailRow[] = [
    {
      key: "pnl-primary-driver",
      label: "主驱动",
      value: `${pnlDriverLabel(summary.primary_driver)} · ${bondNumericDisplay(summary.primary_driver_pct)}`,
      tradeDate: summary.report_date,
      source: "primary_driver",
      tone: "ok",
    },
    {
      key: "pnl-tpl-alignment",
      label: "TPL 与市场",
      value: summary.tpl_market_aligned ? "方向一致" : "待核验",
      tradeDate: summary.report_date,
      source: summary.tpl_market_note,
      tone: summary.tpl_market_aligned ? "ok" : "watch",
    },
  ];
  for (const [index, finding] of summary.key_findings.slice(0, 4).entries()) {
    rows.push({
      key: `pnl-finding-${index}`,
      label: `发现 ${index + 1}`,
      value: finding,
      tradeDate: summary.report_date,
      source: "key_findings",
      tone: "ok",
    });
  }
  return rows;
}

function portfolioReadPathState(queries: ModuleHomeSourceQueries): PortfolioReadPathState {
  const coreQueries = portfolioCoreReadQueries(queries);
  if (hasError(coreQueries)) {
    return { label: "读取失败", tone: "error" };
  }
  if (hasLoading(coreQueries)) {
    if (hasData(coreQueries)) {
      return { label: "部分接入", tone: "watch" };
    }
    return { label: "读取中", tone: "muted" };
  }
  return { label: "已接入", tone: "ok" };
}

function portfolioPnlState(
  queries: ModuleHomeSourceQueries,
  summary: PnlAttributionAnalysisSummary | undefined,
): PortfolioPnlState {
  if (queries.pnlSummary?.isError) {
    return { label: "读取失败", tone: "error" };
  }
  if (queryIsInitialLoading(queries.pnlSummary)) {
    return { label: "读取中", tone: "muted" };
  }
  if (summary) {
    return { label: "已返回", tone: "ok" };
  }
  return { label: "待读", tone: "watch" };
}

function portfolioEvidenceState(queries: ModuleHomeSourceQueries): PortfolioEvidenceState {
  const meta =
    queries.bondHeadline?.data?.result_meta ??
    queries.bondRisk?.data?.result_meta ??
    queries.bondPortfolioComparison?.data?.result_meta;
  if (!meta) {
    return {
      factValue: "待返回",
      detail: "证据元数据待返回",
      tone: "muted",
    };
  }

  const rows =
    typeof meta.evidence_rows === "number" ? `${meta.evidence_rows} 行` : "行数未披露";
  const table = meta.tables_used?.[0] ?? "来源表未披露";
  const fallback =
    meta.fallback_mode === "none" && !meta.fallback_date
      ? "无回退"
      : `${meta.fallback_mode}${meta.fallback_date ? ` / ${meta.fallback_date}` : ""}`;
  return {
    factValue: rows,
    detail: `${meta.result_kind} / ${rows} / ${table} / ${fallback}`,
    tone: meta.quality_flag === "ok" ? "ok" : "watch",
  };
}

function portfolioDecisionAnchorDate(queries: ModuleHomeSourceQueries) {
  return (
    queries.bondHeadline?.data?.result.report_date ??
    queries.bondDates?.data?.result.report_dates[0] ??
    ""
  );
}

function portfolioEvidenceSources(queries: ModuleHomeSourceQueries): PortfolioEvidenceSource[] {
  return [
    {
      label: "债券总览",
      hasData: Boolean(queries.bondHeadline?.data),
      isError: queries.bondHeadline?.isError,
      isLoading: queryIsInitialLoading(queries.bondHeadline),
      meta: queries.bondHeadline?.data?.result_meta,
      reportDate: queries.bondHeadline?.data?.result.report_date ?? "",
    },
    {
      label: "风险指标",
      hasData: Boolean(queries.bondRisk?.data),
      isError: queries.bondRisk?.isError,
      isLoading: queryIsInitialLoading(queries.bondRisk),
      meta: queries.bondRisk?.data?.result_meta,
      reportDate: queries.bondRisk?.data?.result.report_date ?? "",
    },
    {
      label: "资产负债",
      hasData: Boolean(queries.balanceOverview?.data),
      isError: queries.balanceOverview?.isError,
      isLoading: queryIsInitialLoading(queries.balanceOverview),
      meta: queries.balanceOverview?.data?.result_meta,
      reportDate: queries.balanceOverview?.data?.result.report_date ?? "",
    },
    {
      label: "损益归因",
      hasData: Boolean(queries.pnlSummary?.data),
      isError: queries.pnlSummary?.isError,
      isLoading: queryIsInitialLoading(queries.pnlSummary),
      meta: queries.pnlSummary?.data?.result_meta,
      reportDate: queries.pnlSummary?.data?.result.report_date ?? "",
    },
  ];
}

function portfolioRiskDatesEvidence(queries: ModuleHomeSourceQueries) {
  return {
    hasData: Boolean(queries.riskDates?.data),
    isError: queries.riskDates?.isError,
    isLoading: queryIsInitialLoading(queries.riskDates),
    dates: queries.riskDates?.data?.result.report_dates ?? [],
    meta: queries.riskDates?.data?.result_meta,
  };
}

function portfolioView(
  queries: ModuleHomeSourceQueries,
): ModuleHomeViewBody {
  const balance = queries.balanceOverview?.data?.result;
  const bond = queries.bondHeadline?.data?.result;
  const risk = queries.bondRisk?.data?.result;
  const balanceDate = queries.balanceDates?.data?.result.report_dates[0] ?? "-";
  const bondDate = queries.bondDates?.data?.result.report_dates[0] ?? bond?.report_date ?? "-";
  const bondKpis = bond?.kpis;
  const assetType = queries.bondAssetType?.data?.result;
  const assetRating = queries.bondAssetRating?.data?.result;
  const maturity = queries.bondMaturity?.data?.result;
  const industry = queries.bondIndustry?.data?.result;
  const yieldDist = queries.bondYield?.data?.result;
  const portfolioComparison = queries.bondPortfolioComparison?.data?.result;
  const spread = queries.bondSpread?.data?.result;
  const businessType = queries.bondBusinessType?.data?.result;
  const balanceBasis = queries.balanceBasis?.data?.result;
  const pnlSummary = queries.pnlSummary?.data?.result;
  const industryTotalMarketValue = sumIndustryMarketValue(industry);
  const bondMeta = queries.bondHeadline?.data?.result_meta;
  const riskMeta = queries.bondRisk?.data?.result_meta;
  const formalBond = metaIsFormalDecisionSource(bondMeta) ? bond : undefined;
  const formalRisk = metaIsFormalDecisionSource(riskMeta) ? risk : undefined;
  const formalBondKpis = formalBond?.kpis;

  const creditRatio = risk ? nativeToNumber(risk.credit_ratio) : null;
  const creditTone =
    creditRatio === null
      ? "待确认信用结构"
      : creditRatio >= 0.5
        ? "信用仓位偏高"
        : creditRatio >= 0.3
          ? "信用仓位适中"
          : "利率债占比更高";

  const bondKpiDefs: Array<{
    key: string;
    label: string;
    field?: keyof NonNullable<typeof bondKpis>;
    detail: string;
    customValue?: string;
    tone?: ModuleHomeTone;
  }> = [
    {
      key: "bond-market",
      label: "债券组合市值",
      field: "total_market_value",
      detail: "债券总览口径，按亿元展示。",
    },
    {
      key: "asset-market",
      label: "资产侧市值",
      customValue: formatYiFromYuan(balance?.asset_total_market_value_amount),
      detail: `资产负债口径，${envelopeMeta(queries.balanceOverview)}`,
      tone: balance ? "ok" : "watch",
    },
    {
      key: "liability-market",
      label: "负债侧市值",
      customValue: formatYiFromYuan(balance?.liability_total_market_value_amount),
      detail: `资产负债口径，${envelopeMeta(queries.balanceOverview)}`,
      tone: balance ? "ok" : "watch",
    },
    {
      key: "bond-duration",
      label: "加权久期",
      field: "weighted_duration",
      detail: "债券总览久期读数。",
    },
    {
      key: "bond-ytm",
      label: "加权 YTM",
      field: "weighted_ytm",
      detail: "债券总览收益率读数。",
    },
    {
      key: "bond-credit-spread",
      label: "信用利差中位数",
      field: "credit_spread_median",
      detail: "债券总览信用利差读数。",
    },
    {
      key: "bond-dv01",
      label: "DV01 合计",
      field: "total_dv01",
      detail: "债券总览口径，按万元展示。",
    },
    {
      key: "bond-credit-ratio",
      label: "信用占比",
      customValue: formalRisk ? `${formatRatePercent(formalRisk.credit_ratio)}%` : "-",
      detail: formalRisk ? "风险指标口径。" : "风险指标未达到正式决策口径，未纳入 KPI。",
      tone: formalRisk ? "ok" : "watch",
    },
    {
      key: "bond-pnl",
      label: "未实现损益",
      field: "unrealized_pnl",
      detail: "债券总览损益读数，按亿元展示。",
    },
    {
      key: "bond-count",
      label: "持仓只数",
      field: "bond_count",
      detail: "债券总览逐券行数。",
    },
  ];

  const kpis: ModuleHomeKpi[] = enrichPortfolioKpis(
    bondKpiDefs.map((def) => {
      if (def.customValue !== undefined) {
        return {
          key: def.key,
          label: def.label,
          value: def.customValue,
          detail: def.detail,
          tone: def.tone ?? (def.customValue === "-" ? "watch" : "ok"),
        };
      }
      const raw = formalBondKpis?.[def.field!];
      return {
        key: def.key,
        label: def.label,
        value: formalBondKpis ? formatBondHeadlineKpi(def.field!, raw) : "-",
        detail: formalBondKpis ? def.detail : "债券总览未达到正式决策口径，未纳入 KPI。",
        tone: formalBondKpis ? "ok" : "watch",
      };
    }),
    formalBond,
    bondKpiDefs,
  );

  const distributionPanels: ModuleHomeDistributionPanel[] = [
    buildDistributionPanel({
      key: "asset-type",
      title: "券种分布",
      reportDate: assetType?.report_date ?? bondDate,
      query: queries.bondAssetType,
      readyDetail: "asset-structure / bond_type 已返回。",
      viewAllPath: "/bond-dashboard",
      rows: distributionRows(
        (assetType?.items ?? []).map((item) => ({
          key: item.category,
          label: item.category,
          marketValue: item.total_market_value,
          percentage: item.percentage,
        })),
        assetType?.total_market_value,
      ),
      totalMarketValue: assetType?.total_market_value,
    }),
    buildDistributionPanel({
      key: "rating",
      title: "评级分布",
      reportDate: assetRating?.report_date ?? bondDate,
      query: queries.bondAssetRating,
      readyDetail: "asset-structure / rating 已返回。",
      viewAllPath: "/bond-dashboard",
      rows: distributionRows(
        (assetRating?.items ?? []).map((item) => ({
          key: item.category,
          label: item.category,
          marketValue: item.total_market_value,
          percentage: item.percentage,
        })),
        assetRating?.total_market_value,
        { emptyLabel: "未填评级 / 不适用评级" },
      ),
      totalMarketValue: assetRating?.total_market_value,
      subtitle: ratingTieOutSubtitle(assetRating, balanceBasis),
    }),
    buildDistributionPanel({
      key: "maturity",
      title: "期限分布",
      reportDate: maturity?.report_date ?? bondDate,
      query: queries.bondMaturity,
      readyDetail: "maturity-structure 已返回。",
      viewAllPath: "/bond-dashboard",
      rows: distributionRows(
        (maturity?.items ?? []).map((item) => ({
          key: item.maturity_bucket,
          label: item.maturity_bucket,
          marketValue: item.total_market_value,
          percentage: item.percentage,
        })),
        maturity?.total_market_value,
      ),
      totalMarketValue: maturity?.total_market_value,
    }),
    buildDistributionPanel({
      key: "industry",
      title: "行业分布",
      reportDate: industry?.report_date ?? bondDate,
      query: queries.bondIndustry,
      readyDetail: "industry-distribution 已返回。",
      viewAllPath: "/bond-dashboard",
      rows: distributionRows(
        (industry?.items ?? []).map((item) => ({
          key: item.industry_name,
          label: item.industry_name,
          marketValue: item.total_market_value,
          percentage: item.percentage,
        })),
        industryTotalMarketValue,
      ),
      totalMarketValue: industryTotalMarketValue,
    }),
    buildDistributionPanel({
      key: "yield",
      title: "收益率分布",
      reportDate: yieldDist?.report_date ?? bondDate,
      query: queries.bondYield,
      readyDetail: "yield-distribution 已返回。",
      viewAllPath: "/bond-dashboard",
      subtitle: yieldDist
        ? `组合加权 YTM ${formatRatePercent(yieldDist.weighted_ytm)}%`
        : undefined,
      rows: distributionRows(
        (yieldDist?.items ?? []).map((item) => ({
          key: item.yield_bucket,
          label: item.yield_bucket,
          marketValue: item.total_market_value,
          percentage: null,
        })),
      ),
    }),
  ];

  const riskRows = risk ? buildRiskIndicatorDetailRows(risk) : [];
  const riskStatus = sourceUseStatus(
    queryStatus(
      "risk-indicators-detail",
      "风险指标",
      queries.bondRisk,
      riskRows.length > 0 ? `risk-indicators 已返回 ${riskRows.length} 项。` : "风险指标为空。",
    ),
    riskMeta,
    "risk-indicators 为分析口径或未允许正式使用，仅保留为明细复核，不参与风险 ticker 或闭合判断。",
  );

  const portfolioRows = portfolioComparison ? buildPortfolioComparisonRows(portfolioComparison) : [];
  const readPath = portfolioReadPathState(queries);
  const pnlState = portfolioPnlState(queries, pnlSummary);
  const evidenceState = portfolioEvidenceState(queries);
  const readiness = buildPortfolioReadinessGate({
    decisionAnchorDate: portfolioDecisionAnchorDate(queries),
    readPathTone: readPath.tone,
    hasCoreReads: Boolean(bondKpis || risk),
    evidenceSources: portfolioEvidenceSources(queries),
    riskDatesEvidence: portfolioRiskDatesEvidence(queries),
  });
  const decision = buildPortfolioDecision({
    bondKpis: formalBondKpis,
    risk: formalRisk,
    pnlSummary,
    bondDate,
    portfolioRows,
    readPath,
    pnlState,
    evidenceState,
    readiness,
  });
  const portfolioStatus = emptyRowsWatchStatus(
    queryStatus(
      "portfolio-comparison",
      "子组合对比",
      queries.bondPortfolioComparison,
      portfolioRows.length > 0
        ? `portfolio-comparison 已返回 ${portfolioRows.length} 个子组合。`
        : "子组合对比为空。",
    ),
    portfolioRows,
    "子组合对比为空；正式读链路已返回但无子组合明细，请复核组合分层读链路。",
  );

  const yieldRows = yieldDist ? buildYieldDistributionRows(yieldDist) : [];
  const yieldStatus = emptyRowsWatchStatus(
    queryStatus(
      "yield-distribution",
      "收益率分布",
      queries.bondYield,
      yieldRows.length > 0 ? `yield-distribution 已返回 ${yieldRows.length} 项。` : "收益率分布为空。",
    ),
    yieldRows,
    "收益率分布为空；正式读链路已返回但无收益率桶明细，请复核源表过滤条件。",
  );

  const spreadRows = spread ? buildSpreadAnalysisRows(spread) : [];
  const spreadStatus = emptyRowsWatchStatus(
    queryStatus(
      "spread-analysis",
      "利差结构",
      queries.bondSpread,
      spreadRows.length > 0 ? `spread-analysis 已返回 ${spreadRows.length} 项。` : "利差结构为空。",
    ),
    spreadRows,
    "利差结构为空；正式读链路已返回但无券种利差明细，请复核源表过滤条件。",
  );

  const businessTypeRows = businessType ? buildBusinessTypeRows(businessType) : [];
  const businessTypeStatus = emptyRowsWatchStatus(
    queryStatus(
      "business-type-metrics",
      "业务类型指标",
      queries.bondBusinessType,
      businessTypeRows.length > 0
        ? `business-type-metrics 已返回 ${businessTypeRows.length} 项。`
        : "业务类型指标为空。",
    ),
    businessTypeRows,
    "业务类型指标为空；正式读链路已返回但无业务类型明细，请复核源表过滤条件。",
  );

  const basisRows = balanceBasis ? buildBalanceBasisRows(balanceBasis) : [];
  const basisStatus = queryStatus(
    "balance-basis",
    "Basis 分解",
    queries.balanceBasis,
    basisRows.length > 0 ? `summary-by-basis 已返回 ${basisRows.length} 行。` : "Basis 分解为空。",
  );

  const pnlRows = pnlSummary ? buildPnlSummaryRows(pnlSummary) : [];
  const pnlStatus = queryStatus(
    "pnl-attribution-summary",
    "损益归因摘要",
    queries.pnlSummary,
    pnlRows.length > 0 ? "pnl-attribution summary 已返回。" : "损益归因摘要为空。",
  );

  const detailPanels: ModuleHomeDetailPanel[] = [
    buildDetailPanel({
      key: "risk-indicators-detail",
      title: "风险指标",
      meta: bondDashboardMeta(risk?.report_date ?? bondDate),
      status: riskStatus,
      rows: riskRows,
    }),
    buildDetailPanel({
      key: "portfolio-comparison",
      title: "子组合对比",
      meta: bondDashboardMeta(portfolioComparison?.report_date ?? bondDate),
      status: portfolioStatus,
      rows: portfolioRows,
      chart: portfolioComparison ? buildPortfolioComparisonChart(portfolioComparison) : undefined,
    }),
    buildDetailPanel({
      key: "yield-distribution",
      title: "收益率分布",
      meta: bondDashboardMeta(yieldDist?.report_date ?? bondDate),
      status: yieldStatus,
      rows: yieldRows,
      chart: yieldDist ? buildYieldDistributionChart(yieldDist) : undefined,
    }),
    buildDetailPanel({
      key: "spread-analysis",
      title: "利差结构",
      meta: bondDashboardMeta(spread?.report_date ?? bondDate),
      status: spreadStatus,
      rows: spreadRows,
      chart: spread ? buildSpreadAnalysisChart(spread) : undefined,
    }),
    buildDetailPanel({
      key: "business-type-metrics",
      title: "业务类型加权指标",
      meta: bondDashboardMeta(businessType?.report_date ?? bondDate),
      status: businessTypeStatus,
      rows: businessTypeRows,
      chart: businessType ? buildBusinessTypeChart(businessType) : undefined,
    }),
    buildDetailPanel({
      key: "balance-basis",
      title: "资产负债 Basis 分解",
      meta: balanceSourceMeta(balanceBasis?.report_date ?? balanceDate),
      status: basisStatus,
      rows: basisRows,
    }),
    buildDetailPanel({
      key: "pnl-attribution-summary",
      title: "损益归因摘要",
      meta: `来源 pnl-attribution · ${pnlSummary?.report_date ?? bondDate}`,
      status: pnlStatus,
      rows: pnlRows,
    }),
  ];

  const hasCoreReadError = hasError(portfolioCoreReadQueries(queries));

  return {
    stateLabel: readPath.label,
    stateDetail: hasCoreReadError
      ? "部分组合读链路失败，不使用前端补数。"
      : `资产负债 ${balanceDate}，债券总览 ${bondDate}，子组合 ${portfolioRows.length} 个，归因摘要 ${pnlSummary ? "已返回" : "待读"}。`,
    kpis,
    statuses: [
      queryStatus("balance", "资产负债", queries.balanceOverview, "正式 overview 已返回。"),
      sourceUseStatus(
        queryStatus("bond", "债券总览", queries.bondHeadline, "headline kpis 已返回。"),
        bondMeta,
        "bond.home_summary 为分析口径或未允许正式使用，不参与首屏决策 KPI。",
      ),
      sourceUseStatus(
        queryStatus("bond-risk", "风险指标", queries.bondRisk, "risk-indicators 已返回。"),
        riskMeta,
        "bond.risk_indicators 为分析口径或未允许正式使用，不参与风险 ticker 或闭合判断。",
      ),
      queryStatus("bond-structure", "持仓结构", queries.bondAssetType, "券种/评级/期限/行业分布已挂接。"),
      combinedQueryStatus(
        "bond-depth",
        "深度读链路",
        [
          queries.bondYield,
          queries.bondPortfolioComparison,
          queries.bondSpread,
          queries.bondBusinessType,
        ],
        "深度读链路至少一个子读面已返回；收益率/子组合/利差/业务类型分别在明细面板披露。",
      ),
      queryStatus("balance-basis", "Basis 分解", queries.balanceBasis, "summary-by-basis 已返回。"),
      queryStatus("pnl-summary", "损益归因", queries.pnlSummary, "summary 已返回。"),
      {
        key: "positions",
        label: "持仓明细",
        value: "下钻页",
        detail: "逐券明细仍在 /positions 展开。",
        tone: "muted",
      },
    ],
    decision,
    briefings: [
      {
        title: "规模与错配",
        conclusion:
          formalBondKpis && balance
            ? `债券组合 ${formatBondHeadlineKpi("total_market_value", formalBondKpis.total_market_value)}，资产侧 ${formatYiFromYuan(
                balance.asset_total_market_value_amount,
              )}，负债侧 ${formatYiFromYuan(balance.liability_total_market_value_amount)}。`
            : balance
              ? `资产侧 ${formatYiFromYuan(balance.asset_total_market_value_amount)}，负债侧 ${formatYiFromYuan(
                  balance.liability_total_market_value_amount,
                )}。`
              : "资产负债 overview 暂无可用数据。",
        evidence: basisRows.length
          ? `已挂接 basis 分解 ${basisRows.length} 行；不做净额补算。`
          : "使用 balance-analysis overview 字段展示，不做净额补算。",
        tone: balance || bondKpis ? "ok" : "watch",
      },
      {
        title: "风险敏感度",
        conclusion:
          formalBondKpis && formalRisk
            ? `久期 ${formatBondHeadlineKpi("weighted_duration", formalBondKpis.weighted_duration)}，DV01 ${formatBondHeadlineKpi(
                "total_dv01",
                formalBondKpis.total_dv01,
              )}，${creditTone}（信用占比 ${formatRatePercent(formalRisk.credit_ratio)}%）。`
            : formalRisk
              ? `久期 ${formatYears(formalRisk.weighted_duration)} 年，DV01 ${formatDv01Wan(formalRisk.total_dv01)} 万元，${creditTone}。`
              : "正式风险读数暂未返回或未允许正式使用。",
        evidence: "直接展示 headline / risk-indicators 字段，不以前端估算监管 DV01。",
        tone: formalBondKpis || formalRisk ? "ok" : "watch",
      },
      {
        title: "收益解释",
        conclusion: pnlSummary
          ? `主驱动 ${pnlDriverLabel(pnlSummary.primary_driver)}（${bondNumericDisplay(
              pnlSummary.primary_driver_pct,
            )}）；${pnlSummary.key_findings[0] ?? "详见归因摘要。"}`
          : formalBondKpis
            ? `未实现损益 ${formatBondHeadlineKpi("unrealized_pnl", formalBondKpis.unrealized_pnl)}，加权 YTM ${formatBondHeadlineKpi(
                "weighted_ytm",
                formalBondKpis.weighted_ytm,
              )}。`
            : "收益解释需要进入损益归因下钻页。",
        evidence: pnlSummary
          ? "使用 pnl-attribution summary；完整瀑布图在 /pnl-attribution。"
          : "首页只做摘要，不替代正式归因页面。",
        tone: pnlSummary || bondKpis ? "ok" : "muted",
      },
    ],
    distributionPanels,
    detailPanels,
    dataNote: portfolioDataNote(queries),
  };
}

function marketView(
  queries: ModuleHomeSourceQueries,
): Omit<ModuleHomeView, "kind" | "title" | "question" | "summary" | "sourceScope"> {
  const latestSeries = queries.choiceLatest?.data?.result.series ?? [];
  const rateSeries = queries.marketRates?.data?.result.series ?? [];
  const catalogSeries = queries.marketCatalog?.data?.result.series ?? [];
  const ratesMeta = queries.marketRates?.data?.result_meta;
  const latestMeta = queries.choiceLatest?.data?.result_meta;
  const catalogMeta = queries.marketCatalog?.data?.result_meta;
  const terminalModel = buildMarketDataTerminalModel({
    ratesEnvelope: queries.marketRates?.data,
    latestEnvelope: queries.choiceLatest?.data,
  });
  const tenYear =
    latestSeries.find((item) => ["CA.CN_GOV_10Y", "E1000180", "EMM00166466"].includes(item.series_id)) ??
    latestSeries.find((item) => item.series_name.includes("10年")) ??
    rateSeries.find((item) => ["CA.CN_GOV_10Y", "E1000180", "EMM00166466"].includes(item.series_id)) ??
    rateSeries.find((item) => item.series_name.includes("10年"));

  const seriesById = choiceSeriesById(latestSeries, rateSeries);
  const baseKeyRateRows = buildMarketKeyRateRows(latestSeries, rateSeries, terminalModel);
  const spreadTradeDate =
    baseKeyRateRows[0]?.tradeDate ?? latestSeries[0]?.trade_date ?? rateSeries[0]?.trade_date ?? "-";
  const keyRateRows = enrichMarketHomeRows(
    [
      ...baseKeyRateRows,
      ...buildDerivedSpreadRows(
        mergeDerivedSpreads(
          queries.marketRates?.data?.result.derived_spreads,
          queries.choiceLatest?.data?.result.derived_spreads,
        ),
        spreadTradeDate,
      ),
    ],
    seriesById,
  );
  const keyRateStatus = combinedQueryStatus(
    "key-rates",
    "关键利率快照",
    [queries.choiceLatest, queries.marketRates],
    keyRateRows.length > 0
      ? `已匹配 ${keyRateRows.length} 条关键利率点。`
      : "未匹配到关键利率点，前端不补数。",
  );
  const keyRateSnapshotPanel = buildDetailPanel({
    key: "key-rate-snapshot",
    title: "关键利率快照",
    meta: marketDataMeta(
      "choice-latest / market-data",
      ratesMeta ?? latestMeta,
      keyRateRows[0]?.tradeDate,
    ),
    status: keyRateStatus,
    rows: keyRateRows,
  });

  const formalRateRows: ModuleHomeDetailRow[] = rateSeries.slice(0, 24).map((point) =>
    macroPointToDetailRow(point, point.series_name, point.series_id),
  );
  const formalRateStatus = queryStatus(
    "formal-rates",
    "正式利率序列",
    queries.marketRates,
    formalRateRows.length > 0
      ? `market-data rates 已返回 ${rateSeries.length} 条。`
      : "正式利率序列为空。",
  );
  const formalRatePanel = buildDetailPanel({
    key: "formal-rate-series",
    title: "正式利率序列",
    meta: marketDataMeta("market-data", ratesMeta),
    status: formalRateStatus,
    rows: formalRateRows,
    chart: buildPercentRateChart(formalRateRows, "正式利率对比"),
  });

  const keyRateSeriesIds = new Set(keyRateRows.map((row) => row.source).filter((source) => source !== "-"));
  const macroSnapshotRows = enrichMarketHomeRows(
    buildLatestMacroSnapshotRows(latestSeries, keyRateSeriesIds),
    seriesById,
  );
  const macroSnapshotStatus = queryStatus(
    "macro-snapshot",
    "跨资产快讯",
    queries.choiceLatest,
    macroSnapshotRows.length > 0
      ? `Choice latest 已匹配 ${macroSnapshotRows.length} 条跨资产观察点。`
      : "未匹配到跨资产快讯，前端不补数。",
  );
  const macroSnapshotPanel = buildDetailPanel({
    key: "latest-macro-snapshot",
    title: "跨资产快讯",
    meta: marketDataMeta("choice-latest", latestMeta, macroSnapshotRows[0]?.tradeDate),
    status: macroSnapshotStatus,
    rows: macroSnapshotRows,
  });

  const curveQuoteRows = buildYieldCurveQuoteRows(terminalModel);
  const curveQuoteStatus = combinedQueryStatus(
    "yield-curve",
    "收益率曲线",
    [queries.choiceLatest, queries.marketRates],
    curveQuoteRows.length > 0
      ? `已匹配 ${curveQuoteRows.length} 条国债/国开曲线点。`
      : "曲线报价为空。",
  );
  const yieldCurvePanel = buildDetailPanel({
    key: "yield-curve-quotes",
    title: "国债与国开曲线",
    meta: marketDataMeta("market-data terminal", ratesMeta ?? latestMeta, curveQuoteRows[0]?.tradeDate),
    status: curveQuoteStatus,
    rows: curveQuoteRows,
    chart: buildPercentRateChart(curveQuoteRows, "收益率对比"),
  });

  const tierCounts = catalogTierCounts(catalogSeries);
  const catalogSummaryRows: ModuleHomeDetailRow[] = [
    {
      key: "catalog-total",
      label: "已注册序列",
      value: `${catalogSeries.length} 条`,
      tradeDate: "-",
      source: "catalog",
      tone: catalogSeries.length > 0 ? "ok" : "watch",
    },
    {
      key: "catalog-stable",
      label: "stable 序列",
      value: `${tierCounts.stable} 条`,
      tradeDate: "-",
      source: "refresh_tier",
      tone: tierCounts.stable > 0 ? "ok" : "muted",
    },
    {
      key: "catalog-fallback",
      label: "fallback 序列",
      value: `${tierCounts.fallback} 条`,
      tradeDate: "-",
      source: "refresh_tier",
      tone: tierCounts.fallback > 0 ? "watch" : "muted",
    },
    ...catalogSeries.slice(0, 8).map((item) => ({
      key: `catalog-${item.series_id}`,
      label: item.series_name,
      value: item.unit ? `${item.unit}` : "-",
      tradeDate: item.frequency ?? "-",
      source: item.series_id,
      tone: "muted" as ModuleHomeTone,
    })),
  ];
  const catalogStatus = queryStatus(
    "catalog-overview",
    "数据目录",
    queries.marketCatalog,
    catalogSeries.length > 0 ? `catalog 已注册 ${catalogSeries.length} 条序列。` : "目录为空。",
  );
  const catalogPanel = buildDetailPanel({
    key: "catalog-overview",
    title: "数据目录概览",
    meta: marketDataMeta("market-data catalog", catalogMeta),
    status: catalogStatus,
    rows: catalogSummaryRows,
  });

  const macroAnalysis = mergeMacroToolkitAnalysis(
    queries.macroToolkitAnalysis?.data?.result,
    queries.macroToolkitStrategySummaries?.data?.result,
  );
  const newsEventsPayload = queries.newsEvents?.data?.result;
  const newsEventsStatus = queryStatus(
    "news-events",
    "新闻事件",
    queries.newsEvents,
    newsEventsPayload
      ? `choice-events 已返回 ${newsEventsPayload.total_rows} 条事件摘要。`
      : "新闻事件摘要待读取。",
  );
  const macroToolkitMeta = queries.macroToolkitAnalysis?.data?.result_meta;
  const macroToolkitStatus = queryStatus(
    "macro-toolkit",
    "宏观工具",
    queries.macroToolkitAnalysis,
    macroAnalysis
      ? `${macroAnalysis.conclusion.stance} · 命中 ${macroAnalysis.coverage.hit_count}/${macroAnalysis.coverage.indicator_count}`
      : "宏观工具分析待接入或读取失败。",
  );
  const macroOverviewPanel = buildDetailPanel({
    key: "macro-toolkit-overview",
    title: "宏观工具结论",
    meta: marketDataMeta("macro-toolkit / analysis", macroToolkitMeta, macroAnalysis?.as_of_date ?? undefined),
    status: macroToolkitStatus,
    rows: macroAnalysis ? buildMacroToolkitOverviewRows(macroAnalysis) : [],
  });
  const macroSignalPanel = buildDetailPanel({
    key: "macro-toolkit-signals",
    title: "宏观信号卡片",
    meta: marketDataMeta("macro-toolkit / signal_cards", macroToolkitMeta, macroAnalysis?.as_of_date ?? undefined),
    status: macroToolkitStatus,
    rows: macroAnalysis ? buildMacroToolkitSignalRows(macroAnalysis) : [],
  });
  const macroCapabilityPanel = buildDetailPanel({
    key: "macro-toolkit-capabilities",
    title: "能力模块",
    meta: marketDataMeta("macro-toolkit / capabilities", macroToolkitMeta, macroAnalysis?.as_of_date ?? undefined),
    status: macroToolkitStatus,
    rows: macroAnalysis ? buildMacroToolkitCapabilityRows(macroAnalysis) : [],
  });
  const macroIndicatorPanel = buildDetailPanel({
    key: "macro-toolkit-indicators",
    title: "工具指标",
    meta: marketDataMeta("macro-toolkit / indicators", macroToolkitMeta, macroAnalysis?.as_of_date ?? undefined),
    status: macroToolkitStatus,
    rows: macroAnalysis ? buildMacroToolkitIndicatorRows(macroAnalysis.indicators) : [],
  });
  const macroStrategyPanel = buildDetailPanel({
    key: "macro-toolkit-strategies",
    title: "策略摘要",
    meta: marketDataMeta("macro-toolkit / strategies", macroToolkitMeta, macroAnalysis?.as_of_date ?? undefined),
    status: macroToolkitStatus,
    rows: macroAnalysis ? buildMacroToolkitStrategyRows(macroAnalysis) : [],
  });
  const macroAShareRiskPanel = buildDetailPanel({
    key: "macro-toolkit-a-share-risk",
    title: "A股踩踏风险",
    meta: marketDataMeta("macro-toolkit / a_share_risk", macroToolkitMeta, macroAnalysis?.a_share_risk?.trade_date ?? undefined),
    status: macroToolkitStatus,
    rows: macroAnalysis?.a_share_risk ? buildMacroToolkitAShareRiskRows(macroAnalysis.a_share_risk) : [],
  });
  const macroHasonPanel = buildDetailPanel({
    key: "macro-toolkit-hason",
    title: "Hason 宏观策略",
    meta: marketDataMeta("macro-toolkit / hason_strategy", macroToolkitMeta, macroAnalysis?.as_of_date ?? undefined),
    status: macroToolkitStatus,
    rows: macroAnalysis?.hason_strategy ? buildMacroToolkitHasonRows(macroAnalysis.hason_strategy) : [],
  });
  const macroShadowPanel = buildDetailPanel({
    key: "macro-toolkit-shadow",
    title: "影子组合报告",
    meta: marketDataMeta(
      "macro-toolkit / shadow_portfolio",
      macroToolkitMeta,
      macroAnalysis?.shadow_portfolio_report?.as_of_date ?? undefined,
    ),
    status: macroToolkitStatus,
    rows: macroAnalysis?.shadow_portfolio_report
      ? buildMacroToolkitShadowRows(macroAnalysis.shadow_portfolio_report)
      : [],
  });
  const macroRuntimePanel = buildDetailPanel({
    key: "macro-toolkit-runtime",
    title: "数据运行时",
    meta: marketDataMeta("macro-toolkit / runtime", macroToolkitMeta, macroAnalysis?.as_of_date ?? undefined),
    status: macroToolkitStatus,
    rows: macroAnalysis ? buildMacroToolkitRuntimeRows(macroAnalysis) : [],
  });
  const newsEventsSnapshotRows = buildNewsEventsSnapshotRows(newsEventsPayload);
  const newsEventsPanel = buildDetailPanel({
    key: "news-events-snapshot",
    title: "新闻事件",
    meta: marketDataMeta("choice-events", queries.newsEvents?.data?.result_meta),
    status: newsEventsStatus,
    rows: newsEventsSnapshotRows,
  });

  return {
    stateLabel: hasError(queries)
      ? "读取失败"
      : hasLoading(marketHomePrimaryQueries(queries))
        ? "读取中"
        : "已接入",
    stateDetail: hasError(queries)
      ? "部分市场读链路失败，不使用前端补数。"
      : `最新行情 ${latestSeries.length} 条，正式利率序列 ${rateSeries.length} 条。`,
    kpis: [
      {
        key: "macro-series",
        label: "最新行情",
        value: `${latestSeries.length}`,
        detail: "Choice latest series 数量。",
        tone: latestSeries.length > 0 ? "ok" : "watch",
      },
      {
        key: "ten-year-rate",
        label: "10年利率",
        value: tenYear ? formatChoiceMacroValue(tenYear, { spaceBeforeUnit: false }) : "-",
        detail: tenYear ? `${tenYear.series_name} / ${tenYear.trade_date}` : "未返回 10 年利率点。",
        tone: tenYear ? "ok" : "watch",
      },
      {
        key: "rate-series",
        label: "正式利率",
        value: `${rateSeries.length}`,
        detail: `market-data rates，${envelopeMeta(queries.marketRates)}`,
        tone: rateSeries.length > 0 ? "ok" : "watch",
      },
      {
        key: "catalog-series",
        label: "目录序列",
        value: `${catalogSeries.length}`,
        detail: "market data catalog 已注册序列数。",
        tone: catalogSeries.length > 0 ? "ok" : "watch",
      },
      ...(macroAnalysis
        ? [
            {
              key: "macro-toolkit-hit",
              label: "工具命中率",
              value: `${(macroAnalysis.coverage.hit_rate * 100).toFixed(1)}%`,
              detail: `${macroAnalysis.coverage.hit_count}/${macroAnalysis.coverage.indicator_count} 指标 · ${macroAnalysis.coverage.script_count} 脚本`,
              tone: (macroAnalysis.coverage.hit_rate >= 0.7 ? "ok" : "watch") as ModuleHomeTone,
            },
          ]
        : []),
    ],
    statuses: [
      queryStatus("choice", "最新行情", queries.choiceLatest, "Choice latest 已返回。"),
      queryStatus("rates", "市场数据", queries.marketRates, "market-data rates 已返回。"),
      queryStatus("catalog", "数据目录", queries.marketCatalog, "catalog 已返回。"),
      macroToolkitStatus,
      newsEventsStatus,
      {
        key: "cross-asset",
        label: "跨资产",
        value: "下钻页",
        detail: "跨资产传导解释以 /cross-asset 为准。",
        tone: "muted" as ModuleHomeTone,
      },
      ...(macroAnalysis?.a_share_risk
        ? [
            {
              key: "a-share-risk",
              label: "A股踩踏风险",
              value: macroAnalysis.a_share_risk.risk_name,
              detail: macroAnalysis.a_share_risk.summary,
              tone: aShareRiskModuleTone(macroAnalysis.a_share_risk),
            },
          ]
        : []),
    ],
    briefings: (() => {
      const csi300 = findMacroPoint(latestSeries, rateSeries, ["CA.CSI300"], ["沪深300"]);
      const csiChg = findMacroPoint(latestSeries, rateSeries, ["CA.CSI300_PCT_CHG"], ["沪深300", "涨跌幅"]);
      const brent = findMacroPoint(latestSeries, rateSeries, ["CA.BRENT"], ["Brent", "布伦特"]);
      const dr007 = keyRateRows.find((row) => row.key === "dr007");

      return [
        {
          title: "利率快照",
          conclusion: tenYear
            ? `${tenYear.series_name} 最新值 ${formatChoiceMacroValue(tenYear, { spaceBeforeUnit: false })}${
                dr007 ? `；${dr007.label} ${dr007.value}` : ""
              }。`
            : keyRateRows.length > 0
              ? `已返回 ${keyRateRows.length} 条关键利率点，10Y 国债待下钻页核验。`
              : "未返回可用 10 年利率点。",
          evidence: "稳定 series_id 优先，名称匹配兜底；完整曲线见下方国债/国开区。",
          tone: tenYear || keyRateRows.length > 0 ? "ok" : "watch",
        },
        {
          title: "跨资产传导",
          conclusion:
            csi300 && csiChg
              ? `沪深300 ${formatChoiceMacroValue(csi300, { spaceBeforeUnit: false })}，日变动 ${formatChoiceMacroValue(
                  csiChg,
                  { spaceBeforeUnit: false },
                )}。`
              : csi300
                ? `沪深300 ${formatChoiceMacroValue(csi300, { spaceBeforeUnit: false })}，完整传导见跨资产页。`
                : brent
                  ? `${brent.series_name} ${formatChoiceMacroValue(brent, { spaceBeforeUnit: false })}，跨资产解释进入 /cross-asset。`
                  : macroSnapshotRows.length > 0
                    ? `已返回 ${macroSnapshotRows.length} 条跨资产观察点，完整传导见 /cross-asset。`
                    : "跨资产解释仍进入 /cross-asset 阅读。",
          evidence: "首页仅展示 Choice latest 已返回的观察点，不把观察口径提升为正式结论。",
          tone: csi300 || brent || macroSnapshotRows.length > 0 ? "ok" : "muted",
        },
        {
          title: "事件状态",
          conclusion: newsEventsPayload
            ? newsEventsSnapshotRows.length > 1
              ? `choice-events 已返回 ${newsEventsPayload.total_rows} 条；最新 ${newsEventsSnapshotRows[1]?.value ?? "待解析"}。`
              : `choice-events 已注册 ${newsEventsPayload.total_rows} 条事件摘要。`
            : "新闻事件摘要待读取。",
          evidence: newsEventsSnapshotRows.length > 1
            ? `最近收到 ${newsEventsSnapshotRows[1]?.tradeDate ?? "—"} · 进入 /news-events 查看全文。`
            : "首页仅展示事件计数与最新标题，完整列表见新闻事件页。",
          tone: newsEventsPayload && newsEventsPayload.total_rows > 0 ? "ok" : "muted",
        },
        {
          title: "宏观工具",
          conclusion: macroAnalysis
            ? `${macroAnalysis.conclusion.stance}：${macroAnalysis.conclusion.summary}`
            : `正式利率序列 ${rateSeries.length} 条，目录序列 ${catalogSeries.length} 条；宏观工具分析待读取。`,
          evidence: macroAnalysis
            ? `${macroAnalysis.conclusion.recommended_action}（工具口径，非正式经营结论）。`
            : "脚本注册表、信号卡片与能力模块由 /macro-toolkit 呈现。",
          tone: macroAnalysis ? macroToolkitModuleTone(macroAnalysis.conclusion.tone) : "muted",
        },
      ];
    })(),
    detailPanels: [
      keyRateSnapshotPanel,
      formalRatePanel,
      catalogPanel,
      macroSnapshotPanel,
      yieldCurvePanel,
      macroOverviewPanel,
      macroSignalPanel,
      macroCapabilityPanel,
      macroIndicatorPanel,
      macroStrategyPanel,
      macroAShareRiskPanel,
      macroHasonPanel,
      macroShadowPanel,
      macroRuntimePanel,
      newsEventsPanel,
    ],
    marketCrisisExplain: buildMarketCrisisExplain(macroAnalysis),
    marketDeskIntel: buildMarketDeskIntel(macroAnalysis),
    dataNote: baseDataNote("market", queries),
  };
}

type RiskTensorDisplayValue = RiskTensorScalar | null | undefined;

function sumIndustryMarketValue(payload: IndustryDistPayload | undefined): Numeric | undefined {
  if (!payload || payload.items.length === 0) {
    return undefined;
  }
  const values = payload.items
    .map((item) => bondNumericRawOrNull(item.total_market_value))
    .filter((value): value is number => value !== null);
  if (values.length === 0) {
    return undefined;
  }
  const raw = values.reduce((sum, value) => sum + value, 0);
  return formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
}

const RISK_YUAN_PER_WAN = 10_000;
const RISK_YUAN_PER_YI = 100_000_000;

const RISK_KRD_FIELDS: ReadonlyArray<{ key: keyof RiskTensorPayload; label: string }> = [
  { key: "krd_1y", label: "KRD 1Y" },
  { key: "krd_3y", label: "KRD 3Y" },
  { key: "krd_5y", label: "KRD 5Y" },
  { key: "krd_7y", label: "KRD 7Y" },
  { key: "krd_10y", label: "KRD 10Y" },
  { key: "krd_30y", label: "KRD 30Y" },
];

type RiskAccountingDv01FieldKey = "ac_dv01" | "oci_dv01" | "tpl_dv01" | "other_dv01";

const RISK_ACCOUNTING_DV01_FIELDS: ReadonlyArray<{ key: RiskAccountingDv01FieldKey; label: string }> = [
  { key: "ac_dv01", label: "AC DV01（摊余成本）" },
  { key: "oci_dv01", label: "OCI DV01（其他综合收益）" },
  { key: "tpl_dv01", label: "TPL DV01（交易性）" },
  { key: "other_dv01", label: "未分类 DV01" },
];

function riskTensorRawOrNull(value: RiskTensorDisplayValue): number | null {
  return bondNumericRawOrNull(value);
}

function shouldShowAccountingDv01Split(value: RiskTensorDisplayValue): boolean {
  if (!hasRiskTensorValue(value)) {
    return false;
  }
  const raw = riskTensorRawOrNull(value);
  return raw === null || raw !== 0;
}

function riskTensorDisplay(value: RiskTensorDisplayValue): string {
  return bondNumericDisplay(value);
}

function formatRiskTensorYuanAmount(value: RiskTensorDisplayValue, divisor: number): string {
  const raw = riskTensorRawOrNull(value);
  if (raw === null) {
    return riskTensorDisplay(value);
  }
  // 保留正负号：负缺口/空头 KRD 的方向有业务含义，与风险张量页保持一致。
  return (raw / divisor).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function riskTensorWanWithUnit(value: RiskTensorDisplayValue): string {
  const raw = riskTensorRawOrNull(value);
  const display = formatRiskTensorYuanAmount(value, RISK_YUAN_PER_WAN);
  return raw === null ? display : `${display} 万元`;
}

function riskTensorYiWithUnit(value: RiskTensorDisplayValue): string {
  const raw = riskTensorRawOrNull(value);
  const display = formatRiskTensorYuanAmount(value, RISK_YUAN_PER_YI);
  return raw === null ? display : `${display} 亿元`;
}

function riskTensorRatioPercent(value: RiskTensorDisplayValue): string {
  const display = riskTensorDisplay(value);
  if (display.includes("%")) {
    return display;
  }
  const raw = riskTensorRawOrNull(value);
  if (raw === null) {
    return display;
  }
  const abs = Math.abs(raw);
  if (abs <= 1) {
    return `${(raw * 100).toFixed(1)}%`;
  }
  if (abs <= 100) {
    return `${raw.toFixed(1)}%`;
  }
  return display;
}

function riskTensorValueTone(value: RiskTensorDisplayValue): ModuleHomeTone {
  const raw = riskTensorRawOrNull(value);
  if (raw === null) {
    return "watch";
  }
  return "ok";
}

function riskTensorPendingOrWan(value: RiskTensorDisplayValue): string {
  return hasRiskTensorValue(value) ? riskTensorWanWithUnit(value) : "待接入";
}

function hasRiskTensorValue(value: RiskTensorDisplayValue): boolean {
  return value !== null && value !== undefined;
}

function riskSourceMeta(source: string, reportDate: string): string {
  return `来源 ${source} · ${reportDate}`;
}

function pushRiskTensorDetailRow(
  rows: ModuleHomeDetailRow[],
  key: string,
  label: string,
  value: RiskTensorDisplayValue,
  format: "wan" | "yi" | "display" | "ratio",
  reportDate: string,
) {
  if (!hasRiskTensorValue(value)) {
    return;
  }
  const formatted =
    format === "wan"
      ? riskTensorWanWithUnit(value)
      : format === "yi"
        ? riskTensorYiWithUnit(value)
        : format === "ratio"
          ? riskTensorRatioPercent(value)
          : riskTensorDisplay(value);
  rows.push({
    key,
    label,
    value: formatted,
    tradeDate: reportDate,
    source: key,
    tone: "ok",
  });
}

function buildRiskTensorDetailSections(tensor: RiskTensorPayload): ModuleHomeDetailSection[] {
  const reportDate = tensor.report_date;

  const rateRows: ModuleHomeDetailRow[] = [];
  pushRiskTensorDetailRow(
    rateRows,
    "regulatory_dv01",
    "监管口径 DV01",
    tensor.regulatory_dv01,
    "wan",
    reportDate,
  );
  pushRiskTensorDetailRow(
    rateRows,
    "portfolio_dv01",
    "估值 DV01",
    tensor.portfolio_dv01,
    "wan",
    reportDate,
  );
  pushRiskTensorDetailRow(
    rateRows,
    "rate_risk_dv01",
    "利率风险 DV01",
    tensor.rate_risk_dv01,
    "wan",
    reportDate,
  );
  pushRiskTensorDetailRow(rateRows, "cs01", "CS01", tensor.cs01, "wan", reportDate);
  pushRiskTensorDetailRow(
    rateRows,
    "portfolio_convexity",
    "组合凸性",
    tensor.portfolio_convexity,
    "display",
    reportDate,
  );

  const accountingRows: ModuleHomeDetailRow[] = [];
  const accountingDv01 = tensor as Partial<Record<RiskAccountingDv01FieldKey, RiskTensorDisplayValue>>;
  for (const field of RISK_ACCOUNTING_DV01_FIELDS) {
    const value = accountingDv01[field.key];
    if (!shouldShowAccountingDv01Split(value)) {
      continue;
    }
    pushRiskTensorDetailRow(accountingRows, field.key, field.label, value, "wan", reportDate);
  }

  const krdRows: ModuleHomeDetailRow[] = [];
  for (const field of RISK_KRD_FIELDS) {
    pushRiskTensorDetailRow(
      krdRows,
      field.key,
      field.label,
      tensor[field.key] as RiskTensorDisplayValue,
      "wan",
      reportDate,
    );
  }

  const concentrationRows: ModuleHomeDetailRow[] = [];
  pushRiskTensorDetailRow(
    concentrationRows,
    "issuer_concentration_hhi",
    "发行人 HHI",
    tensor.issuer_concentration_hhi,
    "display",
    reportDate,
  );
  pushRiskTensorDetailRow(
    concentrationRows,
    "issuer_top5_weight",
    "前五大发行人权重",
    tensor.issuer_top5_weight,
    "ratio",
    reportDate,
  );

  const liquidityRows: ModuleHomeDetailRow[] = [];
  pushRiskTensorDetailRow(
    liquidityRows,
    "liquidity_gap_30d",
    "30 日流动性缺口",
    tensor.liquidity_gap_30d,
    "yi",
    reportDate,
  );
  pushRiskTensorDetailRow(
    liquidityRows,
    "liquidity_gap_90d",
    "90 日流动性缺口",
    tensor.liquidity_gap_90d,
    "yi",
    reportDate,
  );
  pushRiskTensorDetailRow(
    liquidityRows,
    "liquidity_gap_30d_ratio",
    "30 日缺口比例",
    tensor.liquidity_gap_30d_ratio,
    "ratio",
    reportDate,
  );
  pushRiskTensorDetailRow(
    liquidityRows,
    "asset_cashflow_30d",
    "30 日资产现金流",
    tensor.asset_cashflow_30d,
    "yi",
    reportDate,
  );
  pushRiskTensorDetailRow(
    liquidityRows,
    "asset_cashflow_90d",
    "90 日资产现金流",
    tensor.asset_cashflow_90d,
    "yi",
    reportDate,
  );
  pushRiskTensorDetailRow(
    liquidityRows,
    "liability_cashflow_30d",
    "30 日负债现金流",
    tensor.liability_cashflow_30d,
    "yi",
    reportDate,
  );
  pushRiskTensorDetailRow(
    liquidityRows,
    "liability_cashflow_90d",
    "90 日负债现金流",
    tensor.liability_cashflow_90d,
    "yi",
    reportDate,
  );

  const sections: ModuleHomeDetailSection[] = [];
  if (rateRows.length > 0) {
    sections.push({
      key: "rate-sensitivity",
      title: "利率敏感度",
      subtitle: "监管 / 估值 / 利率风险 / CS01 / 凸性",
      rows: rateRows,
      defaultExpanded: true,
    });
  }
  if (accountingRows.length > 0) {
    sections.push({
      key: "accounting-dv01",
      title: "会计分类 DV01",
      subtitle: "AC / OCI / TPL 拆分",
      rows: accountingRows,
      defaultExpanded: true,
    });
  }
  if (krdRows.length > 0) {
    sections.push({
      key: "krd-detail",
      title: "KRD 明细",
      subtitle: "上方图表已展示分布，展开查看数值",
      rows: krdRows,
      defaultExpanded: false,
    });
  }
  if (concentrationRows.length > 0) {
    sections.push({
      key: "concentration",
      title: "集中度",
      rows: concentrationRows,
      defaultExpanded: false,
    });
  }
  if (liquidityRows.length > 0) {
    sections.push({
      key: "liquidity-detail",
      title: "流动性明细",
      rows: liquidityRows,
      defaultExpanded: false,
    });
  }

  return sections;
}

function numericDetailRow(
  key: string,
  label: string,
  value: Numeric,
  reportDate: string,
  source: string,
): ModuleHomeDetailRow {
  return {
    key,
    label,
    value: bondNumericDisplay(value),
    tradeDate: reportDate,
    source,
    tone: "ok",
  };
}

function buildCashflowDetailSections(cashflow: CashflowProjectionPayload): ModuleHomeDetailSection[] {
  const reportDate = cashflow.report_date;
  const forecastRows: ModuleHomeDetailRow[] = [
    numericDetailRow("duration_gap", "久期缺口", cashflow.duration_gap, reportDate, "duration_gap"),
    numericDetailRow(
      "asset_duration",
      "资产久期",
      cashflow.asset_duration,
      reportDate,
      "asset_duration",
    ),
    numericDetailRow(
      "liability_duration",
      "负债久期",
      cashflow.liability_duration,
      reportDate,
      "liability_duration",
    ),
    numericDetailRow(
      "equity_duration",
      "权益久期",
      cashflow.equity_duration,
      reportDate,
      "equity_duration",
    ),
    {
      key: "rate_sensitivity_1bp",
      label: "1bp 敏感度",
      value: `${formatDv01Wan(cashflow.rate_sensitivity_1bp)} 万元`,
      tradeDate: reportDate,
      source: "rate_sensitivity_1bp",
      tone: "ok",
    },
    numericDetailRow(
      "reinvestment_risk_12m",
      "12M 再投资风险",
      cashflow.reinvestment_risk_12m,
      reportDate,
      "reinvestment_risk_12m",
    ),
  ];

  const monthlyRows: ModuleHomeDetailRow[] = [];
  for (const bucket of cashflow.monthly_buckets.slice(0, 6)) {
    monthlyRows.push({
      key: `bucket-${bucket.year_month}`,
      label: `${bucket.year_month} 净现金流`,
      value: `${formatYi(bucket.net_cashflow)} 亿元`,
      tradeDate: bucket.year_month,
      source: "net_cashflow",
      tone: "ok",
    });
    monthlyRows.push({
      key: `bucket-cum-${bucket.year_month}`,
      label: `${bucket.year_month} 累计净现金流`,
      value: `${formatYi(bucket.cumulative_net)} 亿元`,
      tradeDate: bucket.year_month,
      source: "cumulative_net",
      tone: "ok",
    });
  }

  const sections: ModuleHomeDetailSection[] = [
    {
      key: "cashflow-forecast",
      title: "现金流预测",
      subtitle: "久期四要素 / 1bp / 12M 再投资",
      rows: forecastRows,
      defaultExpanded: true,
    },
  ];
  if (monthlyRows.length > 0) {
    sections.push({
      key: "monthly-buckets",
      title: "月度净现金流",
      subtitle: "近 6 个月 bucket",
      rows: monthlyRows,
      defaultExpanded: false,
    });
  }
  return sections;
}

function riskView(
  queries: ModuleHomeSourceQueries,
): Omit<ModuleHomeView, "kind" | "title" | "question" | "summary" | "sourceScope"> {
  const dates = queries.riskDates?.data?.result.report_dates ?? [];
  const tensor = queries.riskTensor?.data?.result;
  const cashflow = queries.cashflow?.data?.result;
  const reportDate = tensor?.report_date ?? cashflow?.report_date ?? dates[0] ?? "-";
  const cashflowReportDate = cashflow?.report_date ?? reportDate;
  const tensorWarnings = tensor?.warnings ?? [];
  const hasRiskPartialError = Boolean(queries.riskDates?.isError || queries.riskTensor?.isError || queries.cashflow?.isError);
  const hasRiskPrimaryError = Boolean(queries.riskDates?.isError || queries.riskTensor?.isError);
  const riskStateLabel = hasRiskPrimaryError
    ? "读取失败"
    : hasRiskPartialError
      ? "部分失败"
      : hasLoading(queries)
        ? "读取中"
        : "已接入";
  const decisionTone: ModuleHomeTone = hasRiskPrimaryError
    ? "error"
    : hasLoading(queries)
      ? "muted"
      : hasRiskPartialError || !tensor || tensorWarnings.length > 0 || !hasRiskTensorValue(tensor.regulatory_dv01)
        ? "watch"
        : "ok";
  const decisionConclusion = hasRiskPrimaryError
    ? "风险读链路失败，当前不能形成处置判断。"
    : hasLoading(queries)
      ? "风险链路读取中，等待正式接口返回。"
      : !tensor
        ? "风险张量未返回，先补齐主链数据。"
        : hasRiskPartialError
          ? "风险张量已返回，现金流等辅助链路需单独复核。"
        : tensorWarnings.length > 0
          ? `存在 ${tensorWarnings.length} 条风险数据提示，优先核对张量质量。`
          : !hasRiskTensorValue(tensor.regulatory_dv01)
            ? "监管 DV01 待接入，不能判定限额状态。"
            : "主链已返回，按后端字段做截面风险复核。";
  const decisionDetail =
    tensor?.dv01_controls?.control_message ??
    tensor?.prior_period_change?.summary ??
    "下方保留字段级证据；正式处置进入风险张量、集中度和现金流页面。";

  const riskTensorSections = tensor
    ? enrichRiskSectionsWithSparklines(buildRiskTensorDetailSections(tensor), tensor)
    : [];
  const riskTensorRows = flattenDetailSections(riskTensorSections);
  const riskTensorStatus = queryStatus(
    "risk-tensor-detail",
    "风险张量明细",
    queries.riskTensor,
    riskTensorRows.length > 0
      ? `风险张量已返回 ${riskTensorRows.length} 条明细。`
      : "风险张量明细为空。",
  );
  const riskTensorPanel = buildDetailPanel({
    key: "risk-tensor-detail",
    title: "风险张量明细",
    meta: riskSourceMeta("risk-tensor", reportDate),
    status: riskTensorStatus,
    rows: riskTensorRows,
    sections: riskTensorSections,
    chart: tensor ? buildRiskKrdChart(tensor) : undefined,
  });

  const cashflowSections = cashflow ? buildCashflowDetailSections(cashflow) : [];
  const cashflowRows = flattenDetailSections(cashflowSections);
  const cashflowStatus = queryStatus(
    "cashflow-projection-detail",
    "现金流与缺口",
    queries.cashflow,
    cashflowRows.length > 0
      ? `现金流预测已返回 ${cashflowRows.length} 条明细。`
      : "现金流预测明细为空。",
  );
  const cashflowPanel = buildDetailPanel({
    key: "cashflow-projection-detail",
    title: "现金流与缺口",
    meta: riskSourceMeta("cashflow-projection", cashflowReportDate),
    status: cashflowStatus,
    rows: cashflowRows,
    sections: cashflowSections,
  });

  const durationGapKpi = cashflow
    ? {
        label: "久期缺口",
        value: bondNumericDisplay(cashflow.duration_gap),
        detail: "来自现金流预测 duration_gap。",
      }
    : {
        label: "30日缺口",
        value: riskTensorYiWithUnit(tensor?.liquidity_gap_30d),
        detail: "来自风险张量 liquidity_gap_30d。",
      };

  return {
    stateLabel: riskStateLabel,
    stateDetail: hasRiskPrimaryError
      ? "风险主链路失败，不使用前端补数。"
      : hasRiskPartialError
        ? `风险报告日 ${reportDate}，主链已返回；辅助链路存在失败。`
      : `风险报告日 ${reportDate}，可用日期 ${dates.length} 个。`,
    kpis: [
      {
        key: "regulatory-dv01",
        label: "监管 DV01",
        value: tensor ? riskTensorPendingOrWan(tensor.regulatory_dv01) : "-",
        detail: "来自 regulatory_dv01；缺失时不使用估值 DV01 替代。",
        tone: tensor ? riskTensorValueTone(tensor.regulatory_dv01) : "watch",
        sparkline: tensor ? riskKpiSparklineFromTensor(tensor, "regulatory_dv01") : undefined,
      },
      {
        key: "portfolio-dv01",
        label: "估值 DV01",
        value: tensor ? riskTensorWanWithUnit(tensor.portfolio_dv01) : "-",
        detail: "portfolio_dv01，只作估值敏感度读数。",
        tone: tensor ? "ok" : "watch",
      },
      {
        key: "modified-duration",
        label: "修正久期",
        value: tensor ? riskTensorDisplay(tensor.portfolio_modified_duration) : "-",
        detail: "portfolio_modified_duration。",
        tone: tensor ? "ok" : "watch",
        sparkline: tensor ? riskKpiSparklineFromTensor(tensor, "portfolio_modified_duration") : undefined,
      },
      {
        key: "liquidity-gap",
        label: durationGapKpi.label,
        value: cashflow || tensor ? durationGapKpi.value : "-",
        detail: durationGapKpi.detail,
        tone: cashflow || tensor ? "ok" : "watch",
        sparkline: tensor ? riskKpiSparklineFromTensor(tensor, "liquidity_gap_30d_ratio") : undefined,
      },
    ],
    statuses: [
      queryStatus("dates", "风险报告日", queries.riskDates, "风险日期列表已返回。"),
      queryStatus("tensor", "风险张量", queries.riskTensor, "风险张量已返回。"),
      queryStatus("cashflow", "现金流预测", queries.cashflow, "现金流预测已返回。"),
      {
        key: "concentration",
        label: "集中度",
        value: "下钻页",
        detail: "集中度监控入口保留到 /concentration-monitor。",
        tone: "muted",
      },
    ],
    decision: {
      title: "风险处置判断",
      conclusion: decisionConclusion,
      detail: decisionDetail,
      tone: decisionTone,
      facts: [
        { label: "报告日", value: reportDate, tone: reportDate === "-" ? "watch" : "ok" },
        {
          label: "质量标记",
          value: tensor?.quality_flag ?? "-",
          tone: tensor?.quality_flag === "ok" ? "ok" : tensor ? "watch" : "muted",
        },
        {
          label: "限额状态",
          value: tensor?.dv01_controls?.limit_status
            ? dv01LimitStatusLabel(tensor.dv01_controls.limit_status)
            : "未返回",
          tone:
            tensor?.dv01_controls?.limit_status === "ok"
              ? "ok"
              : tensor?.dv01_controls?.limit_status === "breach"
                ? "error"
                : "watch",
        },
        {
          label: "数据提示",
          value: `${tensorWarnings.length} 条`,
          tone: tensorWarnings.length > 0 ? "watch" : "ok",
        },
      ],
    },
    briefings: [
      {
        title: "久期与 DV01",
        conclusion: tensor
          ? `DV01 ${riskTensorWanWithUnit(tensor.portfolio_dv01)}，修正久期 ${riskTensorDisplay(tensor.portfolio_modified_duration)}。`
          : "风险张量暂未返回。",
        evidence: "直接展示 risk tensor 字段，不以前端计算监管 DV01。",
        tone: tensor ? "ok" : "watch",
      },
      {
        title: "信用与集中度",
        conclusion: tensor
          ? `CS01 ${riskTensorWanWithUnit(tensor.cs01)}，前五大权重 ${riskTensorRatioPercent(tensor.issuer_top5_weight)}。`
          : "集中度需要进入下钻页核验。",
        evidence: "首页只提供摘要状态。",
        tone: tensor ? "ok" : "muted",
      },
      {
        title: "现金流压力",
        conclusion: cashflow
          ? `久期缺口 ${bondNumericDisplay(cashflow.duration_gap)}，12M 再投资风险 ${bondNumericDisplay(
              cashflow.reinvestment_risk_12m,
            )}。`
          : "现金流预测未返回或待接入。",
        evidence: "现金流压力以 /cashflow-projection 正式展示为准。",
        tone: cashflow ? "ok" : "watch",
      },
    ],
    detailPanels: [riskTensorPanel, cashflowPanel],
    dataNote: baseDataNote("risk", queries),
  };
}

function formatKpiDecimal(value: string | null | undefined, decimals = 2): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const num = Number.parseFloat(value);
  if (Number.isNaN(num)) {
    return String(value);
  }
  return num.toLocaleString("zh-CN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function formatKpiMetricDetailValue(metric: KpiPeriodMetricSummary): string {
  const score = formatKpiDecimal(metric.period_score_value, 2);
  const actual = formatKpiDecimal(metric.period_actual_value, 2);
  const target = formatKpiDecimal(metric.target_value, 2);
  const unit = metric.unit ? ` ${metric.unit}` : "";
  return `得分 ${score} · 实际 ${actual}${unit} / 目标 ${target}${unit}`;
}

function buildPerformanceKpiDetailRows(kpi: KpiPeriodSummaryResponse): ModuleHomeDetailRow[] {
  return kpi.metrics.slice(0, 10).map((metric) => ({
    key: `kpi-metric-${metric.metric_id}`,
    label: metric.metric_name,
    value: formatKpiMetricDetailValue(metric),
    tradeDate: metric.data_date ?? metric.period_end_date,
    source: metric.metric_code,
    tone: "ok",
  }));
}

function buildPerformanceBusinessPnlRows(
  items: PnlByBusinessYtdItem[],
  periodEndDate: string,
): ModuleHomeDetailRow[] {
  const sorted = [...items].sort((left, right) => left.sort_order - right.sort_order);
  return sorted.slice(0, 10).map((item) => {
    const proportion =
      item.proportion !== null && item.proportion !== undefined && item.proportion !== ""
        ? formatRatioPct(item.proportion)
        : null;
    const balance = formatYiFromYuan(item.current_balance);
    const pnlValue = formatYiFromYuan(item.total_pnl);
    const valueParts = [pnlValue];
    if (proportion && proportion !== "-") {
      valueParts.push(`占比 ${proportion}`);
    }
    const sourceParts = [item.row_key];
    if (balance !== "-") {
      sourceParts.push(`规模 ${balance}`);
    }
    return {
      key: `pnl-business-${item.row_key}`,
      label: item.business_type,
      value: valueParts.join(" · "),
      tradeDate: periodEndDate,
      source: sourceParts.join(" · "),
      tone: "ok",
    };
  });
}

function performanceSourceMeta(source: string, periodLabel: string): string {
  return `来源 ${source} · ${periodLabel || "-"}`;
}

function performanceView(
  queries: ModuleHomeSourceQueries,
): Omit<ModuleHomeView, "kind" | "title" | "question" | "summary" | "sourceScope"> {
  const owners = queries.kpiOwners?.data;
  const kpi = queries.kpiSummary?.data;
  const pnl = queries.pnlYtd?.data?.result;

  const kpiDetailRows = kpi ? buildPerformanceKpiDetailRows(kpi) : [];
  const kpiDetailStatus = queryStatus(
    "kpi-metric-detail",
    "KPI 指标明细",
    queries.kpiSummary,
    kpiDetailRows.length > 0
      ? `KPI summary 已返回 ${kpiDetailRows.length} 条指标。`
      : "KPI 指标明细为空。",
  );
  const kpiDetailPanel = buildDetailPanel({
    key: "kpi-metric-detail",
    title: "KPI 指标明细",
    meta: performanceSourceMeta("kpi", kpi?.period_label ?? String(kpi?.year ?? "-")),
    status: kpiDetailStatus,
    rows: kpiDetailRows,
  });

  const businessPnlRows = pnl
    ? buildPerformanceBusinessPnlRows(pnl.items, pnl.period_end_date)
    : [];
  const businessPnlStatus = queryStatus(
    "business-pnl-detail",
    "业务种类损益",
    queries.pnlYtd,
    businessPnlRows.length > 0
      ? `YTD 业务损益已返回 ${businessPnlRows.length} 条。`
      : "业务种类损益明细为空。",
  );
  const businessPnlPanel = buildDetailPanel({
    key: "business-pnl-detail",
    title: "业务种类损益",
    meta: performanceSourceMeta("pnl/by-business", pnl?.period_label ?? String(pnl?.year ?? "-")),
    status: businessPnlStatus,
    rows: businessPnlRows,
  });

  return {
    stateLabel: hasError(queries) ? "读取失败" : hasLoading(queries) ? "读取中" : "已接入",
    stateDetail: hasError(queries)
      ? "绩效读链路失败，不使用前端补数。"
      : `KPI owner ${owners?.total ?? 0} 个，业务损益项目 ${pnl?.items.length ?? 0} 条。`,
    kpis: [
      {
        key: "owner-count",
        label: "KPI Owner",
        value: String(owners?.total ?? "-"),
        detail: "来自 getKpiOwners。",
        tone: owners && owners.total > 0 ? "ok" : "watch",
      },
      {
        key: "kpi-score",
        label: "本期得分",
        value: kpi?.total_score ? `${kpi.total_score} 分` : "-",
        detail: kpi ? `${kpi.period_label} / owner ${kpi.owner_name}` : "KPI summary 未返回。",
        tone: kpi ? "ok" : "watch",
      },
      {
        key: "metric-count",
        label: "指标数",
        value: String(kpi?.total ?? "-"),
        detail: "KPI summary total。",
        tone: kpi ? "ok" : "watch",
      },
      {
        key: "business-pnl",
        label: "YTD 业务损益",
        value: formatYiFromYuan(pnl?.total_pnl),
        detail: pnl ? `${pnl.period_label}，${pnl.source_tables.join(" / ")}` : "业务损益 YTD 未返回。",
        tone: pnl ? "ok" : "watch",
      },
    ],
    statuses: [
      queryStatus("owners", "KPI Owner", queries.kpiOwners, "owners 已返回。"),
      queryStatus("summary", "KPI 汇总", queries.kpiSummary, "summary 已返回。"),
      queryStatus("pnl", "业务损益", queries.pnlYtd, "YTD 损益已返回。"),
      {
        key: "team",
        label: "团队绩效",
        value: "下钻页",
        detail: "团队映射和复盘规则在 /team-performance 展示。",
        tone: "muted",
      },
    ],
    briefings: [
      {
        title: "KPI 完成",
        conclusion: kpi
          ? `${kpi.period_label} 指标 ${kpi.total} 个，总分 ${kpi.total_score}。`
          : "KPI 汇总暂无可用数据。",
        evidence: "只展示 getKpiValuesSummary 返回值。",
        tone: kpi ? "ok" : "watch",
      },
      {
        title: "团队贡献",
        conclusion: owners ? `当前活跃 owner ${owners.total} 个。` : "团队 owner 未返回。",
        evidence: "团队贡献明细进入团队绩效页。",
        tone: owners ? "ok" : "watch",
      },
      {
        title: "损益复盘",
        conclusion: pnl ? `YTD total_pnl ${formatYiFromYuan(pnl.total_pnl)}。` : "业务损益摘要未返回。",
        evidence: "使用 /pnl/by-business YTD 字段，不在首页重算 FTP 或收益率。",
        tone: pnl ? "ok" : "watch",
      },
    ],
    detailPanels: [kpiDetailPanel, businessPnlPanel],
    dataNote: baseDataNote("performance", queries),
  };
}

function governanceSourceMeta(meta: ResultMeta | undefined): string {
  return `来源 source-foundation · ${metaLabel(meta)}`;
}

function governanceCubeMeta(factTable: string): string {
  return `来源 cube / ${factTable}`;
}

function governanceSourceRowOk(summary: SourcePreviewSummary): boolean {
  return summary.total_rows > 0 && summary.manual_review_count === 0;
}

function governanceSourceStatus(summary: SourcePreviewSummary): {
  label: string;
  tone: ModuleHomeTone;
} {
  if (governanceSourceRowOk(summary)) {
    return { label: "正常", tone: "ok" };
  }
  if (summary.manual_review_count > 0) {
    return { label: `待复核 ${summary.manual_review_count}`, tone: "watch" };
  }
  if (summary.total_rows === 0) {
    return { label: "无数据", tone: "watch" };
  }
  return { label: "需关注", tone: "watch" };
}

function buildGovernanceSourceRows(sources: SourcePreviewSummary[]): ModuleHomeDetailRow[] {
  return sources.slice(0, 10).map((summary, index) => {
    const status = governanceSourceStatus(summary);
    const versionParts = [summary.source_version, summary.rule_version].filter(Boolean);
    return {
      key: `source-${summary.source_family}-${index}`,
      label: summary.source_family.toUpperCase(),
      value: status.label,
      tradeDate: summary.report_date ?? summary.batch_created_at ?? "-",
      source:
        versionParts.length > 0
          ? `版本 ${versionParts.join(" / ")} · 行数 ${summary.total_rows}`
          : `行数 ${summary.total_rows}`,
      tone: status.tone,
    };
  });
}

function buildGovernanceCubeRows(dims: CubeDimensionsPayload): ModuleHomeDetailRow[] {
  const rows: ModuleHomeDetailRow[] = [
    {
      key: "cube-fact-table",
      label: "事实表",
      value: dims.fact_table,
      tradeDate: "-",
      source: "fact_table",
      tone: "ok",
    },
  ];

  for (const dimension of dims.dimensions) {
    if (rows.length >= 10) {
      break;
    }
    rows.push({
      key: `cube-dim-${dimension}`,
      label: dimension,
      value: "维度",
      tradeDate: "-",
      source: "dimensions",
      tone: "muted",
    });
  }

  for (const measure of dims.measures) {
    if (rows.length >= 10) {
      break;
    }
    rows.push({
      key: `cube-measure-${measure}`,
      label: measure,
      value: "聚合",
      tradeDate: "-",
      source: "measures",
      tone: "muted",
    });
  }

  for (const field of dims.measure_fields) {
    if (rows.length >= 10) {
      break;
    }
    rows.push({
      key: `cube-field-${field}`,
      label: field,
      value: "度量字段",
      tradeDate: "-",
      source: "measure_fields",
      tone: "muted",
    });
  }

  return rows;
}

function extractHealthCheckRows(healthData: unknown): ModuleHomeDetailRow[] {
  if (!healthData || typeof healthData !== "object") {
    return [];
  }
  const checks = (healthData as HealthResponse).checks;
  if (!checks || typeof checks !== "object") {
    return [];
  }
  return Object.entries(checks)
    .slice(0, 10)
    .map(([name, check]) => ({
      key: `health-check-${name}`,
      label: name,
      value: check.ok ? "ok" : "异常",
      tradeDate: "-",
      source: check.detail || name,
      tone: check.ok ? "ok" : "watch",
    }));
}

function governanceView(
  queries: ModuleHomeSourceQueries,
): Omit<ModuleHomeView, "kind" | "title" | "question" | "summary" | "sourceScope"> {
  const live = queries.healthLive?.data?.status;
  const summary = queries.healthSummary?.data?.status;
  const sources = queries.sourceFoundation?.data?.result.sources ?? [];
  const dims = queries.cubeDimensions?.data;
  const cubeFactTable = dims?.fact_table ?? "bond_analytics";

  const sourceRows = buildGovernanceSourceRows(sources);
  const sourceStatus = queryStatus(
    "source-status-detail",
    "数据源状态",
    queries.sourceFoundation,
    sourceRows.length > 0
      ? `source foundation 已返回 ${sources.length} 个 source family。`
      : "source foundation 列表为空。",
  );
  const sourcePanel = buildDetailPanel({
    key: "source-status",
    title: "数据源状态",
    meta: governanceSourceMeta(queries.sourceFoundation?.data?.result_meta),
    status: sourceStatus,
    rows: sourceRows,
  });

  const cubeRows = dims ? buildGovernanceCubeRows(dims) : [];
  const cubeStatus = queryStatus(
    "cube-dimensions-detail",
    "Cube 维度与度量",
    queries.cubeDimensions,
    cubeRows.length > 0
      ? `cube dimensions 已返回 ${dims?.dimensions.length ?? 0} 个维度。`
      : "cube dimensions 为空。",
  );
  const cubePanel = buildDetailPanel({
    key: "cube-dimensions",
    title: "Cube 维度与度量",
    meta: governanceCubeMeta(cubeFactTable),
    status: cubeStatus,
    rows: cubeRows,
  });

  const healthCheckRows = [
    ...extractHealthCheckRows(queries.healthLive?.data),
    ...extractHealthCheckRows(queries.healthSummary?.data),
  ].filter((row, index, allRows) => allRows.findIndex((item) => item.key === row.key) === index);

  const detailPanels: ModuleHomeDetailPanel[] = [sourcePanel, cubePanel];

  if (healthCheckRows.length > 0) {
    const healthCheckStatus = combinedQueryStatus(
      "health-checks-detail",
      "健康检查明细",
      [queries.healthLive, queries.healthSummary],
      `已返回 ${healthCheckRows.length} 项健康检查。`,
    );
    detailPanels.push(
      buildDetailPanel({
        key: "health-checks",
        title: "健康检查明细",
        meta: "来源 health / health/live",
        status: healthCheckStatus,
        rows: healthCheckRows,
      }),
    );
  }

  return {
    stateLabel: hasError(queries) ? "读取失败" : hasLoading(queries) ? "读取中" : "已接入",
    stateDetail: hasError(queries)
      ? "数据中心读链路失败，不使用前端补数。"
      : `live=${live ?? "-"}，health=${summary ?? "-"}，source=${sources.length}。`,
    kpis: [
      {
        key: "health-live",
        label: "Live",
        value: live ?? "-",
        detail: "GET /health/live。",
        tone: live === "ok" ? "ok" : live ? "watch" : "muted",
      },
      {
        key: "health-summary",
        label: "Health",
        value: summary ?? "-",
        detail: "GET /health。",
        tone: summary === "ok" ? "ok" : summary ? "watch" : "muted",
      },
      {
        key: "source-count",
        label: "数据源",
        value: `${sources.length}`,
        detail: "source foundation sources。",
        tone: sources.length > 0 ? "ok" : "watch",
      },
      {
        key: "cube-dimensions",
        label: "Cube 维度",
        value: `${dims?.dimensions.length ?? 0}`,
        detail: dims ? `${dims.fact_table} / measures ${dims.measures.length}` : "cube dimensions 未返回。",
        tone: dims ? "ok" : "watch",
      },
    ],
    statuses: [
      queryStatus("health-live", "实时健康", queries.healthLive, "live probe 已返回。"),
      queryStatus("source", "数据源状态", queries.sourceFoundation, "source foundation 已返回。"),
      queryStatus("cube", "自助查询", queries.cubeDimensions, "cube dimensions 已返回。"),
      {
        key: "reports",
        label: "报表中心",
        value: "规划中",
        detail: "未接入统一报表后端接口，不伪造报表数据。",
        tone: "watch",
      },
    ],
    briefings: [
      {
        title: "系统健康",
        conclusion: `live=${live ?? "-"}，summary=${summary ?? "-"}。`,
        evidence: "来自既有 health endpoints。",
        tone: live === "ok" && summary === "ok" ? "ok" : "watch",
      },
      {
        title: "数据源状态",
        conclusion: sources.length > 0 ? `已返回 ${sources.length} 个 source family。` : "暂无 source 列表。",
        evidence: "使用 source foundation，不在首页扫描数据库。",
        tone: sources.length > 0 ? "ok" : "watch",
      },
      {
        title: "报表规划",
        conclusion: "统一报表中心仍显示规划/待接入状态。",
        evidence: "当前只保留下钻和数据说明，不构造报表 payload。",
        tone: "watch",
      },
    ],
    detailPanels,
    dataNote: baseDataNote("governance", queries),
  };
}

export function buildModuleHomeView(
  kind: ModuleWorkbenchHomeKind,
  client: Pick<ApiClient, "mode">,
  queries: ModuleHomeSourceQueries,
): ModuleHomeView {
  const config = moduleWorkbenchHomeConfigs[kind];
  const view =
    kind === "portfolio"
      ? client.mode === "mock"
        ? guardMockPortfolioHomeView(portfolioView(queries))
        : portfolioView(queries)
      : kind === "market"
        ? marketView(queries)
        : kind === "risk"
          ? riskView(queries)
          : kind === "performance"
            ? performanceView(queries)
            : governanceView(queries);

  return {
    kind,
    title: config.title,
    question: config.question,
    summary: config.summary,
    sourceScope: `${config.sourceScope} / ${client.mode === "real" ? "real" : "mock"}`,
    ...view,
  };
}
