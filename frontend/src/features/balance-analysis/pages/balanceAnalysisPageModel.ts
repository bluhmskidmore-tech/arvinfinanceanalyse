import type {
  BalanceAnalysisDecisionItemRow,
  BalanceAnalysisDecisionItemStatusRow,
  BalanceAnalysisEventCalendarRow,
  BalanceAnalysisOverviewPayload,
  BalanceAnalysisRiskAlertRow,
  BalanceAnalysisSummaryRow,
  BalanceAnalysisWorkbookPayload,
  BalanceAnalysisWorkbookTable,
  BalanceCurrencyBasis,
  BalancePositionScope,
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
