import type {
  BalanceAnalysisBasisBreakdownRow,
  BalanceAnalysisDecisionItemRow,
  BalanceAnalysisDecisionItemStatusRow,
  BalanceAnalysisDecisionItemsPayload,
  BalanceAnalysisEventCalendarRow,
  BalanceAnalysisOverviewPayload,
  BalanceAnalysisRiskAlertRow,
  BalanceAnalysisSummaryRow,
  BalanceAnalysisSummaryTablePayload,
  BalanceAnalysisWorkbookPayload,
  BalanceAnalysisWorkbookTable,
  BalanceCurrencyBasis,
  BalancePositionScope,
  BalanceMovementBucket,
  BalanceMovementPayload,
  ResultMeta,
} from "../../../api/contracts";

/** Minimum bar width (%) used by workbook distribution / gap panels (matches BalanceAnalysisPage). */
export const BALANCE_ANALYSIS_MIN_CHART_BAR_WIDTH_PCT = 14;

export type BalanceChartMagnitude =
  | { kind: "missing" }
  | { kind: "invalid"; raw: string }
  | { kind: "finite"; value: number };

function stripThousandsSeparators(raw: string): string {
  return raw.replace(/,/g, "").trim();
}

/** Full-string numeric match so `parseFloat("12abc") === 12` cannot slip through as valid. */
const STRICT_DISPLAY_FINITE_NUMBER = /^-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/;

function strictFiniteNumberFromDisplayText(text: string): number | null {
  if (text === "") {
    return null;
  }
  if (!STRICT_DISPLAY_FINITE_NUMBER.test(text)) {
    return null;
  }
  const n = Number(text);
  return Number.isFinite(n) ? n : null;
}

function finiteNumberFromOverviewInput(raw: string | number): number | null {
  if (typeof raw === "number") {
    return Number.isFinite(raw) ? raw : null;
  }
  const text = stripThousandsSeparators(raw);
  return strictFiniteNumberFromDisplayText(text);
}

export type BalanceScopeAmountKey =
  | "marketValueAmount"
  | "amortizedCostAmount"
  | "accruedInterestAmount";

export type BalanceScopeAmountTotals = {
  rowCount: number;
  hasRows: boolean;
  marketValueAmount: number | null;
  amortizedCostAmount: number | null;
  accruedInterestAmount: number | null;
};

type BalanceScopeSummaryInput = {
  position_scope?: unknown;
  row_count?: unknown;
  market_value_amount?: unknown;
  amortized_cost_amount?: unknown;
  accrued_interest_amount?: unknown;
};

function createEmptyScopeTotals(): BalanceScopeAmountTotals {
  return {
    rowCount: 0,
    hasRows: false,
    marketValueAmount: 0,
    amortizedCostAmount: 0,
    accruedInterestAmount: 0,
  };
}

function finiteNumberFromUnknown(value: unknown): number | null {
  if (typeof value !== "string" && typeof value !== "number") {
    return null;
  }
  return finiteNumberFromOverviewInput(value);
}

function addFiniteAmount(current: number | null, value: unknown): number | null {
  if (current === null) {
    return null;
  }
  const n = finiteNumberFromUnknown(value);
  return n === null ? null : current + n;
}

export function summarizeBalanceAmountsByPositionScope(
  rows: readonly BalanceScopeSummaryInput[],
): Record<"asset" | "liability", BalanceScopeAmountTotals> {
  const totals = {
    asset: createEmptyScopeTotals(),
    liability: createEmptyScopeTotals(),
  };

  for (const row of rows) {
    if (row.position_scope !== "asset" && row.position_scope !== "liability") {
      continue;
    }
    const bucket = totals[row.position_scope];
    bucket.hasRows = true;
    const rowCount = finiteNumberFromUnknown(row.row_count);
    bucket.rowCount += rowCount === null ? 0 : rowCount;
    bucket.marketValueAmount = addFiniteAmount(bucket.marketValueAmount, row.market_value_amount);
    bucket.amortizedCostAmount = addFiniteAmount(bucket.amortizedCostAmount, row.amortized_cost_amount);
    bucket.accruedInterestAmount = addFiniteAmount(bucket.accruedInterestAmount, row.accrued_interest_amount);
  }

  return totals;
}

export function formatBalanceScopeTotalAmountToYi(
  totals: BalanceScopeAmountTotals,
  amountKey: BalanceScopeAmountKey,
): string {
  if (!totals.hasRows) {
    return "—";
  }
  const value = totals[amountKey];
  return value === null ? "—" : formatBalanceAmountToYiFromYuan(value);
}

/**
 * Typed workbook/chart magnitude parse. Does not coerce invalid input to 0.
 * Missing: null, undefined, or whitespace-only string after comma strip.
 */
export function parseBalanceChartMagnitude(value: unknown): BalanceChartMagnitude {
  if (value === null || value === undefined) {
    return { kind: "missing" };
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? { kind: "finite", value } : { kind: "invalid", raw: String(value) };
  }
  const asString = String(value);
  const text = stripThousandsSeparators(asString);
  if (text === "") {
    return { kind: "missing" };
  }
  const parsed = strictFiniteNumberFromDisplayText(text);
  if (parsed === null) {
    return { kind: "invalid", raw: asString };
  }
  return { kind: "finite", value: parsed };
}

/**
 * Max scale for chart widths: largest absolute value among finite magnitudes, else 1.
 * Ignores missing/invalid so bad cells do not shrink the scale toward 0.
 */
export function maxAbsFiniteChartScale(values: readonly unknown[]): number {
  let maxAbs = 0;
  for (const v of values) {
    const m = parseBalanceChartMagnitude(v);
    if (m.kind === "finite") {
      const a = Math.abs(m.value);
      if (a > maxAbs) {
        maxAbs = a;
      }
    }
  }
  return maxAbs > 0 ? maxAbs : 1;
}

/**
 * Max positive scale for nonnegative workbook bars (distribution, rating blocks).
 */
export function maxFiniteChartScale(values: readonly unknown[]): number {
  let max = 0;
  for (const v of values) {
    const m = parseBalanceChartMagnitude(v);
    if (m.kind === "finite" && m.value > max) {
      max = m.value;
    }
  }
  return max > 0 ? max : 1;
}

/**
 * Bar width for distribution-style panels. Null when magnitude is missing/invalid (not a real zero bar).
 */
export function distributionChartBarWidthPercent(
  magnitude: BalanceChartMagnitude,
  maxAmongFinite: number,
): number | null {
  if (magnitude.kind !== "finite") {
    return null;
  }
  const denom = maxAmongFinite > 0 ? maxAmongFinite : 1;
  const pct = (magnitude.value / denom) * 100;
  return Math.max(BALANCE_ANALYSIS_MIN_CHART_BAR_WIDTH_PCT, pct);
}

/**
 * Maturity-gap style: width from absolute magnitude; null if missing/invalid.
 */
export function gapChartBarWidthPercent(
  magnitude: BalanceChartMagnitude,
  maxAbsAmongFinite: number,
): number | null {
  if (magnitude.kind !== "finite") {
    return null;
  }
  const denom = maxAbsAmongFinite > 0 ? maxAbsAmongFinite : 1;
  const pct = (Math.abs(magnitude.value) / denom) * 100;
  return Math.max(BALANCE_ANALYSIS_MIN_CHART_BAR_WIDTH_PCT, pct);
}

/** Workbook cell / label display: null, undefined, empty string → em dash. */
export function formatBalanceWorkbookCellDisplay(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  return String(value);
}

/** Workbook numeric metric (e.g. 加权利率%、加权期限年): zh-CN, 2 fraction digits; missing → em dash; invalid → original string. */
export function formatBalanceWorkbookMetricTwoDecimals(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  const n = finiteNumberFromUnknown(value);
  if (n === null) {
    return String(value);
  }
  return n.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/** Workbook operational section keys (e.g. maturity_gap) → panel title for UI copy. */
const WORKBOOK_OPERATIONAL_SECTION_KEY_LABELS: Record<string, string> = {
  maturity_gap: "期限缺口分析",
  rating_analysis: "信用评级分析",
  issuance_business_types: "发行类分析",
};

export function formatBalanceWorkbookOperationalSectionKeyDisplay(value: unknown): string {
  const raw = formatBalanceWorkbookCellDisplay(value);
  if (raw === "—") {
    return raw;
  }
  return WORKBOOK_OPERATIONAL_SECTION_KEY_LABELS[raw] ?? raw;
}

/** Severity enums from governed payloads → short Chinese labels for operators. */
export function formatBalanceGovernedSeverityDisplay(value: unknown): string {
  const key = String(value ?? "").trim().toLowerCase();
  if (key === "high") {
    return "高";
  }
  if (key === "medium") {
    return "中";
  }
  if (key === "low") {
    return "低";
  }
  return formatBalanceWorkbookCellDisplay(value);
}

/** Decision workflow status from API → Chinese operator-facing label. */
export function formatBalanceDecisionWorkflowStatusDisplay(value: unknown): string {
  const key = String(value ?? "").trim().toLowerCase();
  if (key === "pending") {
    return "待处理";
  }
  if (key === "confirmed") {
    return "已确认";
  }
  if (key === "dismissed") {
    return "已忽略";
  }
  return formatBalanceWorkbookCellDisplay(value);
}

/** Overview-style integer grouping; missing → "—"; invalid → original string. */
export function formatBalanceOverviewNumber(raw: string | number | null | undefined): string {
  if (raw === null || raw === undefined || raw === "") {
    return "—";
  }
  const n = finiteNumberFromOverviewInput(raw);
  if (n === null) {
    return String(raw);
  }
  return n.toLocaleString("zh-CN");
}

/** Yuan → 亿元 display (2 decimals, zh-CN). */
export function formatBalanceAmountToYiFromYuan(raw: string | number | null | undefined): string {
  if (raw === null || raw === undefined || raw === "") {
    return "—";
  }
  const n = finiteNumberFromOverviewInput(raw);
  if (n === null) {
    return String(raw);
  }
  return (n / 100_000_000).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/** 万元 → 亿元 display (2 decimals, zh-CN). */
export function formatBalanceAmountToYiFromWan(raw: string | number | null | undefined): string {
  if (raw === null || raw === undefined || raw === "") {
    return "—";
  }
  const n = finiteNumberFromOverviewInput(raw);
  if (n === null) {
    return String(raw);
  }
  return (n / 10_000).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/** Workbook wan-yuan amount cell display with unit, preserving invalid source text. */
export function formatBalanceWorkbookWanAmountDisplay(raw: unknown): string {
  if (raw === null || raw === undefined || raw === "") {
    return "—";
  }
  if (typeof raw !== "string" && typeof raw !== "number") {
    return String(raw);
  }
  const n = finiteNumberFromOverviewInput(raw);
  if (n === null) {
    return String(raw);
  }
  return `${formatBalanceAmountToYiFromWan(raw)} 亿元`;
}

const WORKBOOK_WAN_YUAN_TEXT_PATTERN = /(-?(?:\d[\d,]*(?:\.\d*)?|\.\d+))\s*(?:wan yuan|万元)/gi;

/** Workbook governed prose display: replace embedded wan-yuan amounts with yi-yuan amounts. */
export function formatBalanceWorkbookWanTextDisplay(value: unknown): string {
  const text = formatBalanceWorkbookCellDisplay(value);
  if (text === "—") {
    return text;
  }
  return text.replace(WORKBOOK_WAN_YUAN_TEXT_PATTERN, (_match, rawAmount: string) =>
    formatBalanceWorkbookWanAmountDisplay(rawAmount),
  );
}

/**
 * Core AG Grid value formatter: null/undefined/"" → "—"; invalid → original string; else zh-CN grouped.
 */
export function formatBalanceGridThousandsValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? value.toLocaleString("zh-CN") : String(value);
  }
  const text = stripThousandsSeparators(String(value));
  const n = strictFiniteNumberFromDisplayText(text);
  if (n === null) {
    return String(value);
  }
  return n.toLocaleString("zh-CN");
}

export type BalanceHeadlineMetricState = "missing" | "zero" | "invalid" | "value";

export type BalanceHeadlineCard = {
  key: string;
  label: string;
  value: string;
  unit?: string;
  detail: string;
  valueVariant: "text";
  state: BalanceHeadlineMetricState;
};

function classifyBalanceHeadlineValue(raw: unknown): BalanceHeadlineMetricState {
  if (raw === null || raw === undefined || raw === "") {
    return "missing";
  }
  const n = finiteNumberFromUnknown(raw);
  if (n === null) {
    return "invalid";
  }
  return n === 0 ? "zero" : "value";
}

function buildBalanceHeadlineAmountCard({
  key,
  label,
  raw,
  detail,
}: {
  key: string;
  label: string;
  raw: unknown;
  detail: string;
}): BalanceHeadlineCard {
  return {
    key,
    label,
    value: formatBalanceAmountToYiFromYuan(raw as string | number | null | undefined),
    unit: "亿元",
    detail,
    valueVariant: "text",
    state: classifyBalanceHeadlineValue(raw),
  };
}

function buildBalanceHeadlineCountCard({
  key,
  label,
  raw,
  detail,
}: {
  key: string;
  label: string;
  raw: unknown;
  detail: string;
}): BalanceHeadlineCard {
  return {
    key,
    label,
    value: formatBalanceOverviewNumber(raw as string | number | null | undefined),
    detail,
    valueVariant: "text",
    state: classifyBalanceHeadlineValue(raw),
  };
}

export function buildBalanceHeadlineCards({
  overview,
  positionScope,
}: {
  overview?: BalanceAnalysisOverviewPayload | null;
  positionScope: BalancePositionScope;
}): BalanceHeadlineCard[] {
  const scopeLabel = positionScope === "asset" ? "资产" : "负债";
  const amountCards =
    positionScope === "all"
      ? [
          buildBalanceHeadlineAmountCard({
            key: "asset-market-value",
            label: "资产市值合计",
            raw: overview?.asset_total_market_value_amount,
            detail: "正式总览 · 资产口径",
          }),
          buildBalanceHeadlineAmountCard({
            key: "asset-amortized-cost",
            label: "资产摊余成本合计",
            raw: overview?.asset_total_amortized_cost_amount,
            detail: "正式总览 · 资产口径",
          }),
          buildBalanceHeadlineAmountCard({
            key: "asset-accrued-interest",
            label: "资产应计利息合计",
            raw: overview?.asset_total_accrued_interest_amount,
            detail: "正式总览 · 资产口径",
          }),
          buildBalanceHeadlineAmountCard({
            key: "liability-market-value",
            label: "负债市值合计",
            raw: overview?.liability_total_market_value_amount,
            detail: "正式总览 · 负债口径",
          }),
          buildBalanceHeadlineAmountCard({
            key: "liability-amortized-cost",
            label: "负债摊余成本合计",
            raw: overview?.liability_total_amortized_cost_amount,
            detail: "正式总览 · 负债口径",
          }),
          buildBalanceHeadlineAmountCard({
            key: "liability-accrued-interest",
            label: "负债应计利息合计",
            raw: overview?.liability_total_accrued_interest_amount,
            detail: "正式总览 · 负债口径",
          }),
        ]
      : [
          buildBalanceHeadlineAmountCard({
            key: `${positionScope}-market-value`,
            label: `${scopeLabel}市值合计`,
            raw: overview?.total_market_value_amount,
            detail: `正式总览 · ${scopeLabel}口径`,
          }),
          buildBalanceHeadlineAmountCard({
            key: `${positionScope}-amortized-cost`,
            label: `${scopeLabel}摊余成本合计`,
            raw: overview?.total_amortized_cost_amount,
            detail: `正式总览 · ${scopeLabel}口径`,
          }),
          buildBalanceHeadlineAmountCard({
            key: `${positionScope}-accrued-interest`,
            label: `${scopeLabel}应计利息合计`,
            raw: overview?.total_accrued_interest_amount,
            detail: `正式总览 · ${scopeLabel}口径`,
          }),
        ];

  return [
    ...amountCards,
    buildBalanceHeadlineCountCard({
      key: "summary-rows",
      label: "汇总行数",
      raw: overview?.summary_row_count,
      detail: "正式总览 · 汇总行数",
    }),
    buildBalanceHeadlineCountCard({
      key: "detail-rows",
      label: "明细行数",
      raw: overview?.detail_row_count,
      detail: "正式总览 · 明细行数",
    }),
  ];
}

export type BalanceAnalysisPageSourceMode = "real" | "mock";

export type BalanceAnalysisPageReadModelMetaInput = {
  key: string;
  title: string;
  meta?: ResultMeta | null;
};

export type BalanceAnalysisPageReadModelInput = {
  clientMode: BalanceAnalysisPageSourceMode;
  requestedReportDate: string;
  selectedPositionScope: BalancePositionScope;
  selectedCurrencyBasis: BalanceCurrencyBasis;
  overview?: BalanceAnalysisOverviewPayload | null;
  summary?: Pick<BalanceAnalysisSummaryTablePayload, "total_rows"> | null;
  decisionItems?: Pick<BalanceAnalysisDecisionItemsPayload, "rows"> | null;
  metaSections: BalanceAnalysisPageReadModelMetaInput[];
};

export type BalanceAnalysisPageStatusBadge = {
  key: string;
  label: string;
  tone: "success" | "warning" | "danger" | "info" | "neutral" | "mock";
};

export type BalanceAnalysisPageStateSurface = {
  key: string;
  variant: "neutral" | "loading" | "empty" | "error" | "stale" | "fallback-date" | "mock";
  title: string;
  description: string;
};

export type BalanceAnalysisPageEvidenceCard = {
  key: string;
  title: string;
  resultKind: string;
  basisLabel: string;
  qualityLabel: string;
  fallbackLabel: string;
  asOfDate: string;
  traceId: string;
};

export type BalanceAnalysisPageReadModel = {
  requestedReportDate: string;
  resolvedReportDate: string;
  dateStatus: "pending" | "matched" | "mismatch";
  filterLine: string;
  sourceBadge: BalanceAnalysisPageStatusBadge;
  statusBadges: BalanceAnalysisPageStatusBadge[];
  stateSurfaces: BalanceAnalysisPageStateSurface[];
  conclusionTitle: string;
  conclusionDetail: string;
  kpis: BalanceHeadlineCard[];
  evidenceCards: BalanceAnalysisPageEvidenceCard[];
};

export type BalanceAnalysisPageModelInput = {
  clientMode: BalanceAnalysisPageSourceMode;
  selectedReportDate: string;
  positionScope: BalancePositionScope;
  currencyBasis: BalanceCurrencyBasis;
  overview?: BalanceAnalysisOverviewPayload | null;
  summary?: Pick<BalanceAnalysisSummaryTablePayload, "total_rows"> | null;
  decisionItems?: Pick<BalanceAnalysisDecisionItemsPayload, "rows"> | null;
  workbook?: BalanceAnalysisWorkbookPayload | null;
  summaryRows?: readonly BalanceAnalysisSummaryRow[];
  decisionRows?: readonly BalanceAnalysisDecisionItemStatusRow[];
  workbookDecisionRows?: readonly BalanceAnalysisDecisionItemRow[];
  eventCalendarRows?: readonly BalanceAnalysisEventCalendarRow[];
  riskAlertRows?: readonly BalanceAnalysisRiskAlertRow[];
  metaSections: BalanceAnalysisPageReadModelMetaInput[];
};

export type BalanceAnalysisPageModel = {
  readModel: BalanceAnalysisPageReadModel;
  headlineAmountCards: BalanceHeadlineCard[];
  balanceWorkbenchMetrics: BalanceAnalysisWorkbenchMetric[];
  stageModel: BalanceStageRealDataModel;
};

export type BalanceAnalysisWorkbenchMetric = {
  key: string;
  label: string;
  value: string;
  unit?: string;
  detail?: string;
};

function balancePositionScopeLabel(value: BalancePositionScope): string {
  if (value === "asset") return "资产端";
  if (value === "liability") return "负债端";
  return "全头寸";
}

function balanceCurrencyBasisLabel(value: BalanceCurrencyBasis): string {
  return value === "native" ? "原币" : "CNY";
}

function metaBasisLabel(value: ResultMeta["basis"] | undefined): string {
  if (value === "formal") return "正式口径";
  if (value === "analytical") return "分析口径";
  if (value === "scenario") return "情景口径";
  if (value === "mock") return "模拟口径";
  return "未提供";
}

function metaQualityLabel(value: ResultMeta["quality_flag"] | undefined): string {
  if (value === "ok") return "正常";
  if (value === "warning") return "预警";
  if (value === "error") return "错误";
  if (value === "stale") return "陈旧";
  if (value === "missing") return "缺失";
  return "未提供";
}

function metaFallbackLabel(value: ResultMeta["fallback_mode"] | undefined): string {
  if (value === "none") return "未降级";
  if (value === "latest_snapshot") return "最新快照降级";
  return "未提供";
}

function countDisplay(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return Number.isFinite(value) ? value.toLocaleString("zh-CN") : String(value);
}

function buildReadModelAmountKpi(
  key: string,
  label: string,
  raw: unknown,
  detail: string,
): BalanceHeadlineCard {
  return buildBalanceHeadlineAmountCard({ key, label, raw, detail });
}

function buildReadModelCountKpi(
  key: string,
  label: string,
  raw: number | null | undefined,
  detail: string,
): BalanceHeadlineCard {
  return {
    key,
    label,
    value: countDisplay(raw),
    unit: key === "decision-item-count" ? "项" : "行",
    detail,
    valueVariant: "text",
    state: raw === null || raw === undefined ? "missing" : raw === 0 ? "zero" : "value",
  };
}

function buildBalancePageKpis(input: BalanceAnalysisPageReadModelInput): BalanceHeadlineCard[] {
  const overview = input.overview;
  return [
    buildReadModelAmountKpi(
      "total-market-value",
      "总市值",
      overview?.total_market_value_amount,
      "MTR-BAL-001 · overview.total_market_value_amount",
    ),
    buildReadModelAmountKpi(
      "total-amortized-cost",
      "总摊余成本",
      overview?.total_amortized_cost_amount,
      "MTR-BAL-002 · overview.total_amortized_cost_amount",
    ),
    buildReadModelAmountKpi(
      "total-accrued-interest",
      "总应计利息",
      overview?.total_accrued_interest_amount,
      "MTR-BAL-003 · overview.total_accrued_interest_amount",
    ),
    buildReadModelCountKpi(
      "detail-row-count",
      "明细行数",
      overview?.detail_row_count,
      "MTR-BAL-101 · overview.detail_row_count",
    ),
    buildReadModelCountKpi(
      "summary-row-count",
      "汇总行数",
      overview?.summary_row_count ?? input.summary?.total_rows,
      "MTR-BAL-102/103 · overview.summary_row_count / summary.total_rows",
    ),
    buildReadModelCountKpi(
      "decision-item-count",
      "治理动作",
      input.decisionItems?.rows.length,
      "decision-items.rows.length · 运营治理",
    ),
  ];
}

function buildBalanceEvidenceCards(
  sections: BalanceAnalysisPageReadModelMetaInput[],
): BalanceAnalysisPageEvidenceCard[] {
  return sections.flatMap((section) => {
    if (!section.meta) return [];
    return [
      {
        key: section.key,
        title: section.title,
        resultKind: section.meta.result_kind,
        basisLabel: metaBasisLabel(section.meta.basis),
        qualityLabel: metaQualityLabel(section.meta.quality_flag),
        fallbackLabel: metaFallbackLabel(section.meta.fallback_mode),
        asOfDate: section.meta.as_of_date || "未提供",
        traceId: section.meta.trace_id || "未提供",
      },
    ];
  });
}

export function buildBalanceAnalysisPageReadModel(
  input: BalanceAnalysisPageReadModelInput,
): BalanceAnalysisPageReadModel {
  const requestedReportDate = input.requestedReportDate || "—";
  const resolvedReportDate = input.overview?.report_date || requestedReportDate;
  const dateStatus =
    requestedReportDate === "—" || resolvedReportDate === "—"
      ? "pending"
      : requestedReportDate === resolvedReportDate
        ? "matched"
        : "mismatch";
  const positionScope = input.overview?.position_scope ?? input.selectedPositionScope;
  const currencyBasis = input.overview?.currency_basis ?? input.selectedCurrencyBasis;
  const filterLine = `头寸范围 ${balancePositionScopeLabel(positionScope)} · 币种口径 ${balanceCurrencyBasisLabel(currencyBasis)}`;
  const metas = input.metaSections.map((section) => section.meta).filter(Boolean) as ResultMeta[];
  const hasFallback = metas.some((meta) => meta.fallback_mode === "latest_snapshot");
  const hasStale = metas.some((meta) => meta.quality_flag === "stale");
  const hasQualityError = metas.some((meta) => meta.quality_flag === "error" || meta.quality_flag === "missing");
  const sourceBadge: BalanceAnalysisPageStatusBadge =
    input.clientMode === "real"
      ? { key: "source-real", label: "正式只读链路", tone: "success" }
      : { key: "source-mock", label: "本地演示数据", tone: "mock" };

  const statusBadges: BalanceAnalysisPageStatusBadge[] = [
    sourceBadge,
    {
      key: "date",
      label:
        dateStatus === "matched"
          ? `报告日 ${resolvedReportDate}`
          : dateStatus === "mismatch"
            ? `请求 ${requestedReportDate} / 返回 ${resolvedReportDate}`
            : "报告日待定",
      tone: dateStatus === "matched" ? "neutral" : "warning",
    },
    {
      key: "basis",
      label: "formal",
      tone: "info",
    },
  ];

  if (hasFallback) {
    statusBadges.push({ key: "fallback", label: "fallback date", tone: "warning" });
  }
  if (hasStale) {
    statusBadges.push({ key: "stale", label: "stale", tone: "warning" });
  }
  if (hasQualityError) {
    statusBadges.push({ key: "quality-error", label: "quality error", tone: "danger" });
  }

  const stateSurfaces: BalanceAnalysisPageStateSurface[] = [];
  if (input.clientMode === "mock") {
    stateSurfaces.push({
      key: "mock",
      variant: "mock",
      title: "当前为演示数据",
      description: "页面可验证交互与布局，但不得把 mock 数值当成正式口径。",
    });
  }
  if (dateStatus === "matched") {
    stateSurfaces.push({
      key: "date-matched",
      variant: "neutral",
      title: "报告日已匹配",
      description: `请求报告日与后端返回报告日一致：${resolvedReportDate}。`,
    });
  } else if (dateStatus === "mismatch") {
    stateSurfaces.push({
      key: "date-mismatch",
      variant: "fallback-date",
      title: "报告日不一致",
      description: `请求 ${requestedReportDate}，后端返回 ${resolvedReportDate}，不得静默当作同一报告日。`,
    });
  }
  if (hasStale) {
    stateSurfaces.push({
      key: "stale",
      variant: "stale",
      title: "存在陈旧数据标记",
      description: "至少一个正式读面返回 stale，需要在结论旁显式提醒。",
    });
  }
  if (hasFallback) {
    stateSurfaces.push({
      key: "fallback",
      variant: "fallback-date",
      title: "存在 fallback 日期",
      description: "至少一个正式读面使用 latest_snapshot 降级，需查看证据账本确认 as-of。",
    });
  }
  if (hasQualityError) {
    stateSurfaces.push({
      key: "quality-error",
      variant: "error",
      title: "存在质量错误",
      description: "至少一个正式读面返回 error/missing，不应渲染为正常结论。",
    });
  }

  return {
    requestedReportDate,
    resolvedReportDate,
    dateStatus,
    filterLine,
    sourceBadge,
    statusBadges,
    stateSurfaces,
    conclusionTitle: "正式状态判断",
    conclusionDetail:
      "先看正式资产、负债和治理动作；净头寸、期限缺口与解释项进入 governed workbook 与证据账本下钻，不在前端补算正式口径。",
    kpis: buildBalancePageKpis(input),
    evidenceCards: buildBalanceEvidenceCards(input.metaSections),
  };
}

export function buildBalanceAnalysisPageModel(
  input: BalanceAnalysisPageModelInput,
): BalanceAnalysisPageModel {
  const overviewCards = buildBalanceHeadlineCards({
    overview: input.overview ?? undefined,
    positionScope: input.positionScope,
  });
  const stageDecisionRows =
    (input.decisionRows ?? []).length > 0 ? input.decisionRows ?? [] : input.workbookDecisionRows ?? [];

  return {
    readModel: buildBalanceAnalysisPageReadModel({
      clientMode: input.clientMode,
      requestedReportDate: input.selectedReportDate,
      selectedPositionScope: input.positionScope,
      selectedCurrencyBasis: input.currencyBasis,
      overview: input.overview,
      summary: input.summary,
      decisionItems: input.decisionItems,
      metaSections: input.metaSections,
    }),
    headlineAmountCards: overviewCards.filter((card) => card.unit === "亿元"),
    balanceWorkbenchMetrics: overviewCards.map(({ key, label, value, unit, detail }) => ({
      key,
      label,
      value,
      unit,
      detail,
    })),
    stageModel: buildBalanceStageRealDataModel({
      overview: input.overview ?? undefined,
      summaryRows: input.summaryRows ?? [],
      workbook: input.workbook ?? undefined,
      decisionRows: stageDecisionRows,
      eventCalendarRows: input.eventCalendarRows ?? [],
      riskAlertRows: input.riskAlertRows ?? [],
    }),
  };
}

export type BalanceStageAlertLevel = "danger" | "warning" | "caution" | "info";
export type BalanceStageCalendarLevel = "high" | "medium" | "low";
export type BalanceStageRiskLevel = "low" | "mid" | "high";

export type BalanceStageAllocationItem = {
  label: string;
  value: number;
  color: string;
};

export type BalanceStageRiskRow = {
  dim: string;
  current: string;
  stress: string;
  scenario: string;
  level: BalanceStageRiskLevel;
};

export type BalanceStageContributionRow = {
  item: string;
  assetBal: string;
  assetPct: string;
  liabBal: string;
  liabPct: string;
  netGap: string;
  rowKind: "body" | "gap" | "empty";
};

export type BalanceStageAlertItem = {
  level: BalanceStageAlertLevel;
  title: string;
  detail?: string;
  time?: string;
};

export type BalanceStageRiskMetric = {
  label: string;
  value: string;
};

export type BalanceStageCalendarItem = {
  date: string;
  event: string;
  issuerLabel?: string;
  amount?: string;
  level: BalanceStageCalendarLevel;
  note?: string;
};

export type BalanceStageSummaryModel = {
  content: string;
  tags: { label: string; color?: string }[];
  allocationItems: BalanceStageAllocationItem[];
  allocationNetValue: string;
  riskRows: BalanceStageRiskRow[];
};

export type BalanceStageContributionModel = {
  rows: BalanceStageContributionRow[];
  watchItems: BalanceStageAlertItem[];
  alertItems: BalanceStageAlertItem[];
};

export type BalanceStageBottomModel = {
  maturityCategories: string[];
  assetSeries: number[];
  liabilitySeries: number[];
  gapSeries: number[];
  riskMetrics: BalanceStageRiskMetric[];
  calendarItems: BalanceStageCalendarItem[];
};

export type BalanceStageRealDataModel = {
  summary: BalanceStageSummaryModel;
  contribution: BalanceStageContributionModel;
  bottom: BalanceStageBottomModel;
  hasRealData: boolean;
};

type StageDecisionRow = BalanceAnalysisDecisionItemStatusRow | BalanceAnalysisDecisionItemRow;

export type BalanceStageRealDataInput = {
  overview?: BalanceAnalysisOverviewPayload | null;
  summaryRows?: readonly BalanceAnalysisSummaryRow[];
  workbook?: BalanceAnalysisWorkbookPayload | null;
  decisionRows?: readonly StageDecisionRow[];
  eventCalendarRows?: readonly BalanceAnalysisEventCalendarRow[];
  riskAlertRows?: readonly BalanceAnalysisRiskAlertRow[];
};

const BALANCE_STAGE_SHORT_BUCKETS = new Set([
  "已到期/逾期",
  "3个月以内",
  "3-6个月",
  "6-12个月",
]);

function tableByKey(
  workbook: BalanceAnalysisWorkbookPayload | null | undefined,
  key: string,
): BalanceAnalysisWorkbookTable | undefined {
  return workbook?.tables.find((table) => table.key === key);
}

function workbookCardValue(
  workbook: BalanceAnalysisWorkbookPayload | null | undefined,
  key: string,
): unknown {
  return workbook?.cards.find((card) => card.key === key)?.value;
}

function finiteNumberFromStageValue(value: unknown): number | null {
  const magnitude = parseBalanceChartMagnitude(value);
  return magnitude.kind === "finite" ? magnitude.value : null;
}

function finiteWanValue(value: unknown): number | null {
  return finiteNumberFromStageValue(value);
}

function sumFinite(values: readonly (number | null)[]): number | null {
  let total = 0;
  let hasAny = false;
  for (const value of values) {
    if (value === null) {
      continue;
    }
    total += value;
    hasAny = true;
  }
  return hasAny ? total : null;
}

const BALANCE_RECONCILIATION_WAN_TOLERANCE = 0.01;
const BALANCE_RECONCILIATION_YUAN_TOLERANCE = 100_000_000;
const BALANCE_RECONCILIATION_RATIO_TOLERANCE = 0.0005;

export type BalanceReconciliationLinkStatus = "pending" | "unavailable" | "aligned" | "watch";

export type BalanceReconciliationInternalCheck = {
  key: string;
  label: string;
  leftLabel: string;
  rightLabel: string;
  leftWan: number | null;
  rightWan: number | null;
  deltaWan: number | null;
  aligned: boolean;
};

export type BalanceReconciliationBridgeComponent = {
  bucket: BalanceMovementBucket;
  label: string;
  amountYuan: number | null;
};

export type BalanceReconciliationLinkModel = {
  reportDate: string;
  movementHref: string;
  status: BalanceReconciliationLinkStatus;
  statusLabel: string;
  statusDetail: string;
  workbookBondWan: number | null;
  workbookAssetTotalWan: number | null;
  workbookLiabilityTotalWan: number | null;
  workbookGapWan: number | null;
  workbookFullScopeGapWan: number | null;
  allInternalChecksAligned: boolean;
  internalChecks: BalanceReconciliationInternalCheck[];
  bridgeComponents: BalanceReconciliationBridgeComponent[];
  formalBridgeYuan: number | null;
  movementControlYuan: number | null;
  residualYuan: number | null;
  residualRatio: number | null;
};

export type BalanceReconciliationLinkInput = {
  reportDate: string;
  workbook?: BalanceAnalysisWorkbookPayload | null;
  basisRows?: readonly BalanceAnalysisBasisBreakdownRow[];
  movement?: BalanceMovementPayload | null;
  movementAvailableForDate?: boolean;
  isPending?: boolean;
};

function sumWorkbookTableWan(
  workbook: BalanceAnalysisWorkbookPayload | null | undefined,
  tableKey: string,
  valueKey: string,
): number | null {
  return sumFinite(
    (tableByKey(workbook, tableKey)?.rows ?? []).map((row) => finiteWanValue(row[valueKey])),
  );
}

function buildInternalCheck(
  key: string,
  label: string,
  leftLabel: string,
  rightLabel: string,
  leftWan: number | null,
  rightWan: number | null,
): BalanceReconciliationInternalCheck {
  const deltaWan = leftWan === null || rightWan === null ? null : rightWan - leftWan;
  return {
    key,
    label,
    leftLabel,
    rightLabel,
    leftWan,
    rightWan,
    deltaWan,
    aligned: deltaWan !== null && Math.abs(deltaWan) <= BALANCE_RECONCILIATION_WAN_TOLERANCE,
  };
}

function movementBucketForAccountingBasis(accountingBasis: string): BalanceMovementBucket | null {
  const normalized = accountingBasis.trim().toUpperCase();
  if (normalized === "AC") {
    return "AC";
  }
  if (normalized === "FVOCI" || normalized === "OCI") {
    return "OCI";
  }
  if (normalized === "FVTPL" || normalized === "TPL") {
    return "TPL";
  }
  return null;
}

function movementLikeAmountForBasisRow(row: BalanceAnalysisBasisBreakdownRow): number | null {
  const bucket = movementBucketForAccountingBasis(row.accounting_basis);
  if (bucket === "AC") {
    return finiteNumberFromUnknown(row.amortized_cost_amount);
  }
  if (bucket === "OCI" || bucket === "TPL") {
    return finiteNumberFromUnknown(row.market_value_amount);
  }
  return null;
}

function buildBridgeComponents(
  basisRows: readonly BalanceAnalysisBasisBreakdownRow[],
): BalanceReconciliationBridgeComponent[] {
  const totals: Record<BalanceMovementBucket, number | null> = {
    AC: null,
    OCI: null,
    TPL: null,
  };

  for (const row of basisRows) {
    if (row.source_family !== "zqtz" || row.position_scope !== "asset") {
      continue;
    }
    const bucket = movementBucketForAccountingBasis(row.accounting_basis);
    const amount = movementLikeAmountForBasisRow(row);
    if (bucket === null || amount === null) {
      continue;
    }
    totals[bucket] = (totals[bucket] ?? 0) + amount;
  }

  return [
    { bucket: "AC", label: "AC 摊余", amountYuan: totals.AC },
    { bucket: "OCI", label: "OCI 市值", amountYuan: totals.OCI },
    { bucket: "TPL", label: "TPL 市值", amountYuan: totals.TPL },
  ];
}

function statusForReconciliationLink({
  isPending,
  movementAvailableForDate,
  formalBridgeYuan,
  movementControlYuan,
  residualYuan,
  residualRatio,
}: {
  isPending: boolean;
  movementAvailableForDate: boolean;
  formalBridgeYuan: number | null;
  movementControlYuan: number | null;
  residualYuan: number | null;
  residualRatio: number | null;
}): Pick<BalanceReconciliationLinkModel, "status" | "statusLabel" | "statusDetail"> {
  if (isPending || formalBridgeYuan === null) {
    return {
      status: "pending",
      statusLabel: "待联动数据",
      statusDetail: "正在等待 summary-by-basis 或工作簿数据返回。",
    };
  }
  if (!movementAvailableForDate || movementControlYuan === null) {
    return {
      status: "unavailable",
      statusLabel: "无余额变动日期",
      statusDetail: "当前报告日未出现在余额变动 CNX 月末读模型中。",
    };
  }
  if (residualYuan === null || residualRatio === null) {
    return {
      status: "pending",
      statusLabel: "待联动数据",
      statusDetail: "余额变动控制数尚未返回。",
    };
  }
  if (
    Math.abs(residualYuan) <= BALANCE_RECONCILIATION_YUAN_TOLERANCE ||
    residualRatio <= BALANCE_RECONCILIATION_RATIO_TOLERANCE
  ) {
    return {
      status: "aligned",
      statusLabel: "可核对",
      statusDetail: "AC 摊余 + OCI/TPL 市值与 CNX 控制数在容忍阈值内。",
    };
  }
  return {
    status: "watch",
    statusLabel: "需复核",
    statusDetail: "桥接口径与 CNX 控制数存在超阈值差异。",
  };
}

export function buildBalanceReconciliationLinkModel({
  reportDate,
  workbook,
  basisRows = [],
  movement,
  movementAvailableForDate = false,
  isPending = false,
}: BalanceReconciliationLinkInput): BalanceReconciliationLinkModel {
  const bondWan = finiteWanValue(workbookCardValue(workbook, "bond_assets_excluding_issue"));
  const interbankAssetWan = finiteWanValue(workbookCardValue(workbook, "interbank_assets"));
  const interbankLiabilityWan = finiteWanValue(workbookCardValue(workbook, "interbank_liabilities"));
  const issuanceWan = finiteWanValue(workbookCardValue(workbook, "issuance_liabilities"));
  const netPositionWan = finiteWanValue(workbookCardValue(workbook, "net_position"));

  const maturityBondWan = sumWorkbookTableWan(workbook, "maturity_gap", "bond_assets_amount");
  const maturityInterbankAssetWan = sumWorkbookTableWan(workbook, "maturity_gap", "interbank_assets_amount");
  const maturityIssuanceWan = sumWorkbookTableWan(workbook, "maturity_gap", "issuance_amount");
  const maturityInterbankLiabilityWan = sumWorkbookTableWan(
    workbook,
    "maturity_gap",
    "interbank_liabilities_amount",
  );
  const maturityGapWan = sumWorkbookTableWan(workbook, "maturity_gap", "gap_amount");
  const maturityFullScopeGapWan = sumWorkbookTableWan(workbook, "maturity_gap", "full_scope_gap_amount");

  const internalChecks = [
    buildInternalCheck(
      "bond-business",
      "债券业务",
      "卡片债券资产",
      "业务种类合计",
      bondWan,
      sumWorkbookTableWan(workbook, "bond_business_types", "balance_amount"),
    ),
    buildInternalCheck(
      "rating",
      "信用评级",
      "卡片债券资产",
      "评级合计",
      bondWan,
      sumWorkbookTableWan(workbook, "rating_analysis", "balance_amount"),
    ),
    buildInternalCheck(
      "maturity-bond",
      "期限债券",
      "卡片债券资产",
      "期限债券合计",
      bondWan,
      maturityBondWan,
    ),
    buildInternalCheck(
      "issuance",
      "发行类",
      "发行类卡片",
      "发行类合计",
      issuanceWan,
      sumWorkbookTableWan(workbook, "issuance_business_types", "balance_amount"),
    ),
    buildInternalCheck(
      "maturity-issuance",
      "期限发行类",
      "发行类卡片",
      "期限发行类合计",
      issuanceWan,
      maturityIssuanceWan,
    ),
    buildInternalCheck(
      "maturity-interbank-asset",
      "期限同业资产",
      "同业资产卡片",
      "期限同业资产合计",
      interbankAssetWan,
      maturityInterbankAssetWan,
    ),
    buildInternalCheck(
      "maturity-interbank-liability",
      "期限同业负债",
      "同业负债卡片",
      "期限同业负债合计",
      interbankLiabilityWan,
      maturityInterbankLiabilityWan,
    ),
    buildInternalCheck(
      "gap",
      "期限缺口",
      "净头寸卡片",
      "期限缺口合计",
      netPositionWan,
      maturityGapWan,
    ),
  ];
  const allInternalChecksAligned =
    internalChecks.length > 0 && internalChecks.every((check) => check.aligned);

  const bridgeComponents = buildBridgeComponents(basisRows);
  const formalBridgeYuan = sumFinite(bridgeComponents.map((component) => component.amountYuan));
  const movementControlYuan = finiteNumberFromUnknown(movement?.summary.current_balance_total);
  const residualYuan =
    formalBridgeYuan === null || movementControlYuan === null
      ? null
      : movementControlYuan - formalBridgeYuan;
  const residualRatio =
    residualYuan === null || movementControlYuan === null || movementControlYuan === 0
      ? null
      : Math.abs(residualYuan) / Math.abs(movementControlYuan);

  const status = statusForReconciliationLink({
    isPending,
    movementAvailableForDate,
    formalBridgeYuan,
    movementControlYuan,
    residualYuan,
    residualRatio,
  });

  return {
    reportDate,
    movementHref: reportDate
      ? `/balance-movement-analysis?report_date=${encodeURIComponent(reportDate)}&currency_basis=CNX`
      : "/balance-movement-analysis",
    ...status,
    workbookBondWan: bondWan,
    workbookAssetTotalWan: sumFinite([bondWan, interbankAssetWan]),
    workbookLiabilityTotalWan: sumFinite([issuanceWan, interbankLiabilityWan]),
    workbookGapWan: maturityGapWan,
    workbookFullScopeGapWan: maturityFullScopeGapWan,
    allInternalChecksAligned,
    internalChecks,
    bridgeComponents,
    formalBridgeYuan,
    movementControlYuan,
    residualYuan,
    residualRatio,
  };
}

function formatWanAsYiPlain(value: unknown): string {
  return formatBalanceAmountToYiFromWan(
    typeof value === "number" || typeof value === "string" ? value : null,
  );
}

function formatSignedWanAsYiPlain(value: unknown): string {
  const n = finiteWanValue(value);
  if (n === null) {
    return formatWanAsYiPlain(value);
  }
  const formatted = formatBalanceAmountToYiFromWan(n);
  return n > 0 ? `+${formatted}` : formatted;
}

function formatRatioPercent(numerator: number | null, denominator: number | null): string {
  if (numerator === null || denominator === null || denominator === 0) {
    return "—";
  }
  return `${((numerator / denominator) * 100).toLocaleString("zh-CN", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}%`;
}

function formatSharePercent(value: unknown): string {
  const n = finiteNumberFromStageValue(value);
  if (n === null) {
    return "—";
  }
  return `${(n * 100).toLocaleString("zh-CN", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}%`;
}

function alertLevelFromSeverity(severity: string | undefined): BalanceStageAlertLevel {
  if (severity === "high") {
    return "danger";
  }
  if (severity === "medium") {
    return "warning";
  }
  if (severity === "low") {
    return "info";
  }
  return "caution";
}

function riskLevelFromSeverity(severity: string | undefined): BalanceStageRiskLevel {
  if (severity === "high") {
    return "high";
  }
  if (severity === "low") {
    return "low";
  }
  return "mid";
}

function calendarLevelFromEventType(eventType: string): BalanceStageCalendarLevel {
  if (/issuance|funding|rollover|liability/i.test(eventType)) {
    return "high";
  }
  if (/asset|bond/i.test(eventType)) {
    return "medium";
  }
  return "low";
}

function displayDecisionStatus(row: StageDecisionRow): string | null {
  return "latest_status" in row && row.latest_status ? row.latest_status.status : null;
}

function stageNoDataRow(): BalanceStageContributionRow {
  return {
    item: "暂无真实数据",
    assetBal: "—",
    assetPct: "—",
    liabBal: "—",
    liabPct: "—",
    netGap: "—",
    rowKind: "empty",
  };
}

function sortedByAbsWanAmount(
  rows: readonly Record<string, unknown>[],
  key: string,
): Record<string, unknown>[] {
  return [...rows].sort((a, b) => {
    const aValue = Math.abs(finiteWanValue(a[key]) ?? 0);
    const bValue = Math.abs(finiteWanValue(b[key]) ?? 0);
    return bValue - aValue;
  });
}

function buildStageContributionRows(
  workbook: BalanceAnalysisWorkbookPayload | null | undefined,
): BalanceStageContributionRow[] {
  const bondAssets = finiteWanValue(workbookCardValue(workbook, "bond_assets_excluding_issue"));
  const interbankAssets = finiteWanValue(workbookCardValue(workbook, "interbank_assets"));
  const issuanceLiabilities = finiteWanValue(workbookCardValue(workbook, "issuance_liabilities"));
  const interbankLiabilities = finiteWanValue(workbookCardValue(workbook, "interbank_liabilities"));
  const assetTotal = sumFinite([bondAssets, interbankAssets]);
  const liabilityTotal = sumFinite([issuanceLiabilities, interbankLiabilities]);
  const rows: BalanceStageContributionRow[] = [];

  const pushAssetRow = (item: string, value: number | null) => {
    if (value === null) {
      return;
    }
    rows.push({
      item,
      assetBal: formatWanAsYiPlain(value),
      assetPct: formatRatioPercent(value, assetTotal),
      liabBal: "—",
      liabPct: "—",
      netGap: formatSignedWanAsYiPlain(value),
      rowKind: "body",
    });
  };

  const pushLiabilityRow = (item: string, value: number | null) => {
    if (value === null) {
      return;
    }
    rows.push({
      item,
      assetBal: "—",
      assetPct: "—",
      liabBal: formatWanAsYiPlain(value),
      liabPct: formatRatioPercent(value, liabilityTotal),
      netGap: formatSignedWanAsYiPlain(-value),
      rowKind: "body",
    });
  };

  pushAssetRow("债券资产", bondAssets);
  pushAssetRow("同业资产", interbankAssets);
  pushLiabilityRow("发行类负债", issuanceLiabilities);
  pushLiabilityRow("同业负债", interbankLiabilities);

  if (assetTotal !== null || liabilityTotal !== null) {
    rows.push({
      item: "合计",
      assetBal: assetTotal === null ? "—" : formatWanAsYiPlain(assetTotal),
      assetPct: assetTotal === null ? "—" : "100.0%",
      liabBal: liabilityTotal === null ? "—" : formatWanAsYiPlain(liabilityTotal),
      liabPct: liabilityTotal === null ? "—" : "100.0%",
      netGap:
        assetTotal === null && liabilityTotal === null
          ? "—"
          : formatSignedWanAsYiPlain((assetTotal ?? 0) - (liabilityTotal ?? 0)),
      rowKind: "body",
    });
  }

  const maturityRows = tableByKey(workbook, "maturity_gap")?.rows ?? [];
  for (const row of sortedByAbsWanAmount(maturityRows, "full_scope_gap_amount").slice(0, 3)) {
    const gap = finiteWanValue(row.full_scope_gap_amount ?? row.gap_amount);
    if (gap === null || gap === 0) {
      continue;
    }
    rows.push({
      item: `${formatBalanceWorkbookCellDisplay(row.bucket)}全口径缺口`,
      assetBal: "—",
      assetPct: "—",
      liabBal: "—",
      liabPct: "—",
      netGap: formatSignedWanAsYiPlain(gap),
      rowKind: "gap",
    });
  }

  return rows.length > 0 ? rows : [stageNoDataRow()];
}

function buildWatchItems(rows: readonly StageDecisionRow[]): BalanceStageAlertItem[] {
  const items = rows.slice(0, 4).map((row) => {
    const status = displayDecisionStatus(row);
    return {
      level: alertLevelFromSeverity(row.severity),
      title: row.title,
      detail: [
        formatBalanceWorkbookWanTextDisplay(row.reason),
        row.source_section,
        status ? `状态 ${status}` : null,
      ]
        .filter(Boolean)
        .join(" · "),
    };
  });
  return items.length > 0
    ? items
    : [{ level: "info", title: "当前报告日未返回治理事项", detail: "decision_items 为空，未补造静态事项。" }];
}

function buildAlertItems(
  riskAlertRows: readonly BalanceAnalysisRiskAlertRow[],
  eventCalendarRows: readonly BalanceAnalysisEventCalendarRow[],
): BalanceStageAlertItem[] {
  const riskItems = riskAlertRows.slice(0, 3).map((row) => ({
    level: alertLevelFromSeverity(row.severity),
    title: row.title,
    detail: `${formatBalanceWorkbookWanTextDisplay(row.reason)} · ${row.source_section}`,
  }));
  const eventItems = eventCalendarRows.slice(0, Math.max(0, 4 - riskItems.length)).map((row) => ({
    level: "info" as const,
    title: row.title,
    detail: `${row.event_type} · ${row.impact_hint}`,
    time: row.event_date,
  }));
  const items = [...riskItems, ...eventItems];
  return items.length > 0
    ? items
    : [{ level: "info", title: "当前报告日未返回预警或事件", detail: "risk_alerts/event_calendar 为空。" }];
}

function buildStageCalendarItems(
  eventCalendarRows: readonly BalanceAnalysisEventCalendarRow[],
): BalanceStageCalendarItem[] {
  const items = eventCalendarRows.slice(0, 6).map((row) => ({
    date: row.event_date,
    event: row.title,
    issuerLabel: row.event_type,
    amount: row.source_section,
    level: calendarLevelFromEventType(row.event_type),
    note: row.impact_hint,
  }));
  return items.length > 0
    ? items
    : [
        {
          date: "—",
          event: "当前报告日未返回事件日历",
          amount: "—",
          level: "low",
          note: "event_calendar 为空，未使用静态日历。",
        },
      ];
}

function buildStageRiskRows({
  workbook,
  overview,
  decisionRows,
  eventCalendarRows,
  riskAlertRows,
}: {
  workbook?: BalanceAnalysisWorkbookPayload | null;
  overview?: BalanceAnalysisOverviewPayload | null;
  decisionRows: readonly StageDecisionRow[];
  eventCalendarRows: readonly BalanceAnalysisEventCalendarRow[];
  riskAlertRows: readonly BalanceAnalysisRiskAlertRow[];
}): BalanceStageRiskRow[] {
  const maturityRows = tableByKey(workbook, "maturity_gap")?.rows ?? [];
  const largestGap = sortedByAbsWanAmount(maturityRows, "full_scope_gap_amount")[0];
  const largestGapValue = finiteWanValue(largestGap?.full_scope_gap_amount ?? largestGap?.gap_amount);
  const topRisk = riskAlertRows[0];
  const topDecision = decisionRows[0];
  const reportDate = overview?.report_date ?? workbook?.report_date ?? "—";
  const scope = overview?.position_scope ?? workbook?.position_scope ?? "—";
  const currency = overview?.currency_basis ?? workbook?.currency_basis ?? "—";

  return [
    {
      dim: "期限缺口",
      current: largestGapValue === null ? "无切片" : largestGapValue < 0 ? "负缺口" : "非负",
      stress: largestGapValue === null ? "—" : `${formatSignedWanAsYiPlain(largestGapValue)} 亿元`,
      scenario: formatBalanceWorkbookCellDisplay(largestGap?.bucket ?? "maturity_gap"),
      level: largestGapValue === null ? "mid" : largestGapValue < 0 ? "high" : "low",
    },
    {
      dim: "风险预警",
      current: `${riskAlertRows.length} 条`,
      stress: topRisk?.severity ?? "—",
      scenario: topRisk?.source_section ?? "risk_alerts",
      level: riskLevelFromSeverity(topRisk?.severity),
    },
    {
      dim: "治理事项",
      current: `${decisionRows.length} 项`,
      stress: topDecision?.severity ?? "—",
      scenario: topDecision?.source_section ?? "decision_items",
      level: riskLevelFromSeverity(topDecision?.severity),
    },
    {
      dim: "事件日历",
      current: `${eventCalendarRows.length} 个`,
      stress: eventCalendarRows[0]?.event_date ?? "—",
      scenario: eventCalendarRows[0]?.event_type ?? "event_calendar",
      level: eventCalendarRows.length > 0 ? "mid" : "low",
    },
    {
      dim: "数据口径",
      current: String(scope),
      stress: String(currency),
      scenario: reportDate,
      level: "low",
    },
  ];
}

function buildStageRiskMetrics({
  workbook,
  decisionRows,
  riskAlertRows,
}: {
  workbook?: BalanceAnalysisWorkbookPayload | null;
  decisionRows: readonly StageDecisionRow[];
  riskAlertRows: readonly BalanceAnalysisRiskAlertRow[];
}): BalanceStageRiskMetric[] {
  const bondAssets = finiteWanValue(workbookCardValue(workbook, "bond_assets_excluding_issue"));
  const interbankAssets = finiteWanValue(workbookCardValue(workbook, "interbank_assets"));
  const issuanceLiabilities = finiteWanValue(workbookCardValue(workbook, "issuance_liabilities"));
  const interbankLiabilities = finiteWanValue(workbookCardValue(workbook, "interbank_liabilities"));
  const assetTotal = sumFinite([bondAssets, interbankAssets]);
  const liabilityTotal = sumFinite([issuanceLiabilities, interbankLiabilities]);
  const maturityRows = tableByKey(workbook, "maturity_gap")?.rows ?? [];
  const shortGap = sumFinite(
    maturityRows
      .filter((row) => BALANCE_STAGE_SHORT_BUCKETS.has(String(row.bucket)))
      .map((row) => finiteWanValue(row.full_scope_gap_amount ?? row.gap_amount)),
  );

  return [
    {
      label: "资产/全口径负债比",
      value:
        assetTotal !== null && liabilityTotal !== null && liabilityTotal !== 0
          ? `${(assetTotal / liabilityTotal).toLocaleString("zh-CN", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}x`
          : "—",
    },
    {
      label: "1年内全口径缺口",
      value: shortGap === null ? "—" : `${formatSignedWanAsYiPlain(shortGap)} 亿`,
    },
    {
      label: "发行类负债",
      value: issuanceLiabilities === null ? "—" : `${formatWanAsYiPlain(issuanceLiabilities)} 亿`,
    },
    {
      label: "风险预警条数",
      value: `${riskAlertRows.length}`,
    },
    {
      label: "治理事项条数",
      value: `${decisionRows.length}`,
    },
  ];
}

function buildStageSummaryContent({
  workbook,
  decisionRows,
  riskAlertRows,
  fallbackAssetWan,
  fallbackLiabilityWan,
}: {
  workbook?: BalanceAnalysisWorkbookPayload | null;
  decisionRows: readonly StageDecisionRow[];
  riskAlertRows: readonly BalanceAnalysisRiskAlertRow[];
  fallbackAssetWan: number | null;
  fallbackLiabilityWan: number | null;
}): string {
  const bondAssets = finiteWanValue(workbookCardValue(workbook, "bond_assets_excluding_issue"));
  const interbankAssets = finiteWanValue(workbookCardValue(workbook, "interbank_assets"));
  const issuanceLiabilities = finiteWanValue(workbookCardValue(workbook, "issuance_liabilities"));
  const interbankLiabilities = finiteWanValue(workbookCardValue(workbook, "interbank_liabilities"));
  const assetTotal = sumFinite([bondAssets, interbankAssets]);
  const liabilityTotal = sumFinite([issuanceLiabilities, interbankLiabilities]);
  const bondRows = tableByKey(workbook, "bond_business_types")?.rows ?? [];
  const issuanceRows = tableByKey(workbook, "issuance_business_types")?.rows ?? [];
  const topBond = sortedByAbsWanAmount(bondRows, "balance_amount")[0];
  const topIssuance = sortedByAbsWanAmount(issuanceRows, "balance_amount")[0];
  const maturityRows = tableByKey(workbook, "maturity_gap")?.rows ?? [];
  const largestGap = sortedByAbsWanAmount(maturityRows, "full_scope_gap_amount")[0];
  const gapValue = finiteWanValue(largestGap?.full_scope_gap_amount ?? largestGap?.gap_amount);

  if (
    assetTotal === null &&
    liabilityTotal === null &&
    (fallbackAssetWan !== null || fallbackLiabilityWan !== null) &&
    !topBond &&
    !topIssuance &&
    gapValue === null
  ) {
    return [
      fallbackAssetWan === null
        ? "资产端真实合计暂不可用。"
        : `资产端合计 ${formatWanAsYiPlain(fallbackAssetWan)} 亿元，来自 detail summary。`,
      fallbackLiabilityWan === null
        ? "负债端真实合计暂不可用。"
        : `负债端合计 ${formatWanAsYiPlain(fallbackLiabilityWan)} 亿元，来自 detail summary。`,
      `治理事项 ${decisionRows.length} 项、风险预警 ${riskAlertRows.length} 条。`,
    ].join("\n");
  }

  if (
    assetTotal === null &&
    liabilityTotal === null &&
    !topBond &&
    !topIssuance &&
    gapValue === null
  ) {
    return "当前报告日未返回可用于 stage 的真实 workbook 切片；页面不会继续展示静态演示数字。";
  }

  return [
    assetTotal === null
      ? "资产端真实合计暂不可用。"
      : `资产端合计 ${formatWanAsYiPlain(assetTotal)} 亿元，其中债券资产 ${formatWanAsYiPlain(
          bondAssets,
        )} 亿元、同业资产 ${formatWanAsYiPlain(interbankAssets)} 亿元。`,
    liabilityTotal === null
      ? "负债端真实合计暂不可用。"
      : `负债端合计 ${formatWanAsYiPlain(liabilityTotal)} 亿元，发行类 ${formatWanAsYiPlain(
          issuanceLiabilities,
        )} 亿元、同业负债 ${formatWanAsYiPlain(interbankLiabilities)} 亿元。`,
    [
      topBond
        ? `债券首位分布为 ${formatBalanceWorkbookCellDisplay(topBond.bond_type)}，占比 ${formatSharePercent(
            topBond.share,
          )}`
        : null,
      topIssuance
        ? `发行类首位为 ${formatBalanceWorkbookCellDisplay(topIssuance.bond_type)}，占比 ${formatSharePercent(
            topIssuance.share,
          )}`
        : null,
      gapValue !== null
        ? `${formatBalanceWorkbookCellDisplay(largestGap?.bucket)}全口径缺口 ${formatSignedWanAsYiPlain(
            gapValue,
          )} 亿元`
        : null,
      `治理事项 ${decisionRows.length} 项、风险预警 ${riskAlertRows.length} 条`,
    ]
      .filter(Boolean)
      .join("；") + "。",
  ].join("\n");
}

function buildStageAllocationItems(
  workbook: BalanceAnalysisWorkbookPayload | null | undefined,
): BalanceStageAllocationItem[] {
  const sourceRows = [
    { label: "债券资产", value: workbookCardValue(workbook, "bond_assets_excluding_issue"), color: "#2563eb", sign: 1 },
    { label: "同业资产", value: workbookCardValue(workbook, "interbank_assets"), color: "#3b82f6", sign: 1 },
    { label: "发行类负债", value: workbookCardValue(workbook, "issuance_liabilities"), color: "#dc2626", sign: -1 },
    { label: "同业负债", value: workbookCardValue(workbook, "interbank_liabilities"), color: "#f97316", sign: -1 },
  ];
  return sourceRows
    .map((row) => {
      const value = finiteWanValue(row.value);
      return value === null
        ? null
        : {
            label: row.label,
            value: row.sign * (value / 10_000),
            color: row.color,
          };
    })
    .filter((row): row is BalanceStageAllocationItem => row !== null);
}

function buildStageMaturitySeries(
  workbook: BalanceAnalysisWorkbookPayload | null | undefined,
): Pick<BalanceStageBottomModel, "maturityCategories" | "assetSeries" | "liabilitySeries" | "gapSeries"> {
  const rows = tableByKey(workbook, "maturity_gap")?.rows ?? [];
  return {
    maturityCategories: rows.map((row) => formatBalanceWorkbookCellDisplay(row.bucket)),
    assetSeries: rows.map((row) => (finiteWanValue(row.asset_total_amount) ?? 0) / 10_000),
    liabilitySeries: rows.map((row) => (finiteWanValue(row.full_scope_liability_amount) ?? 0) / 10_000),
    gapSeries: rows.map((row) => (finiteWanValue(row.full_scope_gap_amount ?? row.gap_amount) ?? 0) / 10_000),
  };
}

export function buildBalanceStageRealDataModel({
  overview,
  summaryRows = [],
  workbook,
  decisionRows = [],
  eventCalendarRows = [],
  riskAlertRows = [],
}: BalanceStageRealDataInput): BalanceStageRealDataModel {
  const detailsTotals = summarizeBalanceAmountsByPositionScope(summaryRows);
  const fallbackAssetValue =
    detailsTotals.asset.hasRows && detailsTotals.asset.marketValueAmount !== null
      ? detailsTotals.asset.marketValueAmount / 10_000
      : null;
  const fallbackLiabilityValue =
    detailsTotals.liability.hasRows && detailsTotals.liability.marketValueAmount !== null
      ? detailsTotals.liability.marketValueAmount / 10_000
      : null;
  const allocationItems = buildStageAllocationItems(workbook);
  const allocationItemsWithFallback =
    allocationItems.length > 0
      ? allocationItems
      : [
          fallbackAssetValue === null
            ? null
            : { label: "资产端", value: fallbackAssetValue / 10_000, color: "#2563eb" },
          fallbackLiabilityValue === null
            ? null
            : { label: "负债端", value: -(fallbackLiabilityValue / 10_000), color: "#dc2626" },
        ].filter((row): row is BalanceStageAllocationItem => row !== null);
  const allocationNet = allocationItemsWithFallback.reduce((total, row) => total + row.value, 0);
  const maturitySeries = buildStageMaturitySeries(workbook);
  const reportDate = overview?.report_date ?? workbook?.report_date ?? "报告日未定";
  const positionScope = overview?.position_scope ?? workbook?.position_scope ?? "all";
  const currencyBasis = overview?.currency_basis ?? workbook?.currency_basis ?? "CNY";
  const hasRealData =
    allocationItemsWithFallback.length > 0 ||
    maturitySeries.maturityCategories.length > 0 ||
    decisionRows.length > 0 ||
    eventCalendarRows.length > 0 ||
    riskAlertRows.length > 0;

  return {
    hasRealData,
    summary: {
      content: buildStageSummaryContent({
        workbook,
        decisionRows,
        riskAlertRows,
        fallbackAssetWan: fallbackAssetValue,
        fallbackLiabilityWan: fallbackLiabilityValue,
      }),
      tags: [
        { label: String(reportDate), color: "blue" },
        { label: formatStagePositionScope(positionScope), color: "geekblue" },
        { label: formatStageCurrencyBasis(currencyBasis), color: "cyan" },
      ],
      allocationItems: allocationItemsWithFallback,
      allocationNetValue: allocationItemsWithFallback.length > 0 ? allocationNet.toFixed(2) : "—",
      riskRows: buildStageRiskRows({
        workbook,
        overview,
        decisionRows,
        eventCalendarRows,
        riskAlertRows,
      }),
    },
    contribution: {
      rows: buildStageContributionRows(workbook),
      watchItems: buildWatchItems(decisionRows),
      alertItems: buildAlertItems(riskAlertRows, eventCalendarRows),
    },
    bottom: {
      ...maturitySeries,
      riskMetrics: buildStageRiskMetrics({ workbook, decisionRows, riskAlertRows }),
      calendarItems: buildStageCalendarItems(eventCalendarRows),
    },
  };
}

function formatStagePositionScope(scope: BalancePositionScope | string): string {
  if (scope === "asset") {
    return "资产端";
  }
  if (scope === "liability") {
    return "负债端";
  }
  return "全头寸";
}

function formatStageCurrencyBasis(currencyBasis: BalanceCurrencyBasis | string): string {
  return currencyBasis === "native" ? "原币" : String(currencyBasis);
}
