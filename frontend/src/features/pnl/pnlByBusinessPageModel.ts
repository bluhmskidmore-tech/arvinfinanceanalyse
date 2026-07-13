import type {
  KpiCardProps,
} from "../../components/KpiCard";
import type {
  PnlByBusinessMonthlyBucket,
  PnlByBusinessMonthlyItem,
  PnlByBusinessMonthlyPayload,
  PnlByBusinessAnalysisRow,
  PnlByBusinessPayload,
  PnlByBusinessRow,
  PnlByBusinessYtdItem,
  PnlByBusinessYtdPayload,
  ResultMeta,
} from "../../api/contracts";
import { resolveAdbAvgYuan } from "./zqtzAdbAvgRollup";

export type PnlByBusinessViewMode = "monthly" | "ytd" | "formal";

export const VIEW_MODE_SUBTITLES: Record<PnlByBusinessViewMode, string> = {
  monthly: "按月报表口径查看当月业务种类损益；月报与累计均使用 ZQTZ 管理披露分类。",
  ytd: "按已发布月报累计业务种类损益；与月报同为 ZQTZ 管理披露分类。",
  formal: "按所选报表日读取 formal primary 对账明细（GET /api/pnl/by-business），用于源数据追溯；不与月报或累计混加。",
};

export const VIEW_MODE_STATUS_LABELS: Record<PnlByBusinessViewMode, string> = {
  monthly: "月报 ZQTZ",
  ytd: "年累计 YTD",
  formal: "formal primary",
};

/** 各视图首屏必须回答的首要业务问题（layout contract §2） */
export const VIEW_MODE_BUSINESS_QUESTIONS: Record<PnlByBusinessViewMode, string> = {
  monthly: "截至所选报表月，各 ZQTZ 业务种类损益贡献与收益率如何？",
  ytd: "年累计下哪类业务拉动或拖累组合损益，FTP 后是否仍为正？",
  formal: "所选报表日 formal primary 对账是否可追溯，未 join 损益有多少？",
};

export type PnlHeroModel = {
  businessQuestion: string;
  conclusionTitle: string;
  conclusionDetail: string;
  reportDateLabel: string;
  requestedReportDate: string;
  asOfDate: string;
  reportDateNote: string;
};

export type PnlStateSurfaceItem = {
  key: string;
  variant:
    | "neutral"
    | "loading"
    | "empty"
    | "error"
    | "stale"
    | "fallback-date"
    | "mock"
    | "definition-pending";
  title: string;
  description: string;
};

const YUAN_PER_YI = 100_000_000;
const YUAN_PER_WAN = 10_000;

type QueryState = {
  isLoading: boolean;
  isError: boolean;
};

type ZqtzBusinessDisplayRow = {
  row_key: string;
  business_type: string;
  source_note?: string | null;
};

export type PnlSummaryCard = Pick<
  KpiCardProps,
  "label" | "value" | "detail" | "tone" | "valueVariant"
>;

export type PnlByBusinessInsightConfidence =
  | "可分析"
  | "缺日均"
  | "日均为0"
  | "仅对账"
  | "预警/降级";

export type PnlByBusinessAdbEvidenceStatus = "comparison" | "loading" | "ytd_fallback";

export type PnlByBusinessDrilldownRecommendation = {
  targetBusinessLabel: string;
  priorityLabel: string;
  dimensionLabel: string;
  actionLabel: string;
  evidenceLabel: string;
  reasonLabel: string;
};

export type PnlByBusinessInsightModel = {
  confidenceLabel: PnlByBusinessInsightConfidence;
  totalPnlDisplay: string;
  topContributionLabel: string;
  topContributionDisplay: string;
  topDragLabel: string;
  topDragDisplay: string;
  topShareLabel: string;
  topShareDisplay: string;
  ftpAvailable: boolean;
  missingAdbCount: number;
  zeroAdbCount: number;
  missingFtpFieldCount: number;
  adbEvidenceStatus: PnlByBusinessAdbEvidenceStatus;
  manualAdjustmentCount: number;
  formalUntracedCount: number;
  formalUntracedValueDisplay: string;
  formalUntracedDisplay: string;
  formalTriageDisplay: string;
  nextStep: string;
  recommendedDrilldown: PnlByBusinessDrilldownRecommendation;
};

export type PnlDataStatusStripModel = {
  viewModeLabel: string;
  dataStatus: string;
  asOfDate: string;
  fallbackMode: string;
  vendorStatus: string;
  evidenceRows: string;
  generatedAt: string;
  traceId: string;
};

export type PnlByBusinessSelectionModel = {
  ytdRows: PnlByBusinessYtdItem[];
  parentYtdRows: PnlByBusinessYtdItem[];
  defaultBusinessRow: PnlByBusinessYtdItem | undefined;
  selectedBusinessRow: PnlByBusinessYtdItem | undefined;
};

export type PnlByBusinessSelectedDrilldownModel = {
  topContributionRows: PnlByBusinessAnalysisRow[];
  topDragRows: PnlByBusinessAnalysisRow[];
  negativeFtpRows: PnlByBusinessAnalysisRow[];
};

export type PnlByBusinessMonthlyAdjustmentBridgeModel = {
  monthKey: string;
  row: PnlByBusinessMonthlyItem;
  adjustedParentRowCount: number;
  preAdjustmentPnl: number | null;
  pnlReconciliationDelta: number | null;
  ftpReconciliationDelta: number | null;
  pnlReconciled: boolean;
  ftpReconciled: boolean;
};

type BuildPnlByBusinessPageModelInput = {
  viewMode: PnlByBusinessViewMode;
  selectedReportDate: string;
  selectedYear: number;
  selectedBusinessKey: string | null;
  clientMode?: "real" | "mock";
  datesState: QueryState;
  monthlyState: QueryState;
  ytdState: QueryState;
  formalState: QueryState;
  monthlyResult?: PnlByBusinessMonthlyPayload;
  monthlyMeta?: ResultMeta;
  ytdResult?: PnlByBusinessYtdPayload;
  ytdMeta?: ResultMeta;
  formalResult?: PnlByBusinessPayload;
  formalMeta?: ResultMeta;
  adbAvgByBusinessType?: Map<string, number>;
  adbEvidenceStatus?: PnlByBusinessAdbEvidenceStatus;
  manualAdjustmentCount?: number;
};

export type PnlByBusinessPageModel = PnlByBusinessSelectionModel & {
  monthlyBusinessMonths: PnlByBusinessMonthlyBucket[];
  activeMonthlyBucket: PnlByBusinessMonthlyBucket | undefined;
  parentMonthlyItems: PnlByBusinessMonthlyItem[];
  topMonthlyRow: PnlByBusinessMonthlyItem | undefined;
  formalRows: PnlByBusinessRow[];
  topFormalRow: PnlByBusinessRow | undefined;
  ytdAssetCount: number;
  loading: boolean;
  error: boolean;
  empty: boolean;
  activeResultMeta: ResultMeta | undefined;
  activeDataStatus: string;
  statusStrip: PnlDataStatusStripModel;
  summaryCards: PnlSummaryCard[];
  insight: PnlByBusinessInsightModel;
  hero: PnlHeroModel;
  stateSurfaces: PnlStateSurfaceItem[];
};

function numeric(raw: string | number | null | undefined): number | null {
  if (raw === null || raw === undefined || raw === "") {
    return null;
  }
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

export function formatPnlByBusinessFtpStatus(
  totalPnlRaw: string | number | null | undefined,
  ftpNetPnlRaw: string | number | null | undefined,
): string {
  const totalPnl = numeric(totalPnlRaw);
  const ftpNetPnl = numeric(ftpNetPnlRaw);
  if (ftpNetPnl === null) {
    return "FTP 后不可算";
  }
  if (ftpNetPnl === 0) {
    return "FTP 后为零";
  }
  if (ftpNetPnl > 0) {
    if (totalPnl === null) {
      return "FTP 后为正（扣前损益待返回）";
    }
    return totalPnl <= 0 ? "FTP 后转正" : "FTP 后仍为正";
  }
  if (totalPnl === null) {
    return "FTP 后为负（扣前损益待返回）";
  }
  return totalPnl >= 0 ? "FTP 后转负" : "FTP 后为负";
}

export function buildPnlByBusinessSelectedDrilldownModel(
  rows: PnlByBusinessAnalysisRow[],
  limit = 3,
): PnlByBusinessSelectedDrilldownModel {
  const byInputOrder = rows.map((row, index) => ({ row, index }));
  const compareNumberDesc = (
    left: { row: PnlByBusinessAnalysisRow; index: number },
    right: { row: PnlByBusinessAnalysisRow; index: number },
    field: keyof Pick<PnlByBusinessAnalysisRow, "total_pnl" | "ftp_net_pnl">,
  ) => {
    const leftValue = numeric(left.row[field]) ?? Number.NEGATIVE_INFINITY;
    const rightValue = numeric(right.row[field]) ?? Number.NEGATIVE_INFINITY;
    return rightValue - leftValue || left.index - right.index;
  };
  const compareNumberAsc = (
    left: { row: PnlByBusinessAnalysisRow; index: number },
    right: { row: PnlByBusinessAnalysisRow; index: number },
    field: keyof Pick<PnlByBusinessAnalysisRow, "total_pnl" | "ftp_net_pnl">,
  ) => {
    const leftValue = numeric(left.row[field]) ?? Number.POSITIVE_INFINITY;
    const rightValue = numeric(right.row[field]) ?? Number.POSITIVE_INFINITY;
    return leftValue - rightValue || left.index - right.index;
  };

  return {
    topContributionRows: [...byInputOrder]
      .sort((left, right) => compareNumberDesc(left, right, "total_pnl"))
      .slice(0, limit)
      .map((item) => item.row),
    topDragRows: [...byInputOrder]
      .filter((item) => (numeric(item.row.total_pnl) ?? 0) < 0)
      .sort((left, right) => compareNumberAsc(left, right, "total_pnl"))
      .slice(0, limit)
      .map((item) => item.row),
    negativeFtpRows: [...byInputOrder]
      .filter((item) => (numeric(item.row.ftp_net_pnl) ?? 0) < 0)
      .sort((left, right) => compareNumberAsc(left, right, "ftp_net_pnl"))
      .slice(0, limit)
      .map((item) => item.row),
  };
}

function formatPnlWan(raw: string | number | null | undefined) {
  const value = numeric(raw);
  if (value === null) {
    return "-";
  }
  return (value / YUAN_PER_WAN).toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}

export function formatYuanAsWanUnit(raw: string | number | null | undefined) {
  const value = numeric(raw);
  if (value === null) {
    return "-";
  }
  return `${formatPnlWan(value)} 万元`;
}

function formatYuanAsYiCell(raw: string | number | null | undefined): string {
  const value = numeric(raw);
  if (value === null) {
    return "-";
  }
  return (value / YUAN_PER_YI).toFixed(2);
}

export function formatAvgBalanceYi(raw: string | number | null | undefined): string {
  const value = numeric(raw);
  if (value === null) {
    return "日均缺失";
  }
  return formatYuanAsYiCell(value);
}

export function formatAvgBalanceYiMetric(raw: string | number | null | undefined): string {
  const display = formatAvgBalanceYi(raw);
  return display === "日均缺失" ? display : `${display} 亿元`;
}

export function formatAnalysisYieldPct(raw: string | number | null | undefined): string {
  const value = numeric(raw);
  if (value === null) {
    return "-";
  }
  return `${value.toFixed(2)}%`;
}

export function formatRatioPct(raw: string | number | null | undefined) {
  const value = numeric(raw);
  if (value === null) {
    return "-";
  }
  return `${(value * 100).toFixed(2)}%`;
}

export function toneFromSigned(raw: string | number | null | undefined): "default" | "positive" | "negative" {
  const value = numeric(raw);
  if (value === null || value === 0) {
    return "default";
  }
  return value > 0 ? "positive" : "negative";
}

export function isParentZqtzBusinessRow(row: ZqtzBusinessDisplayRow): boolean {
  if (row.row_key.includes("_detail_")) {
    return false;
  }
  if (row.business_type.startsWith("其中：")) {
    return false;
  }
  const note = String(row.source_note ?? "");
  return !note.includes("其中项");
}

export function isDetailZqtzBusinessRow(row: ZqtzBusinessDisplayRow): boolean {
  return !isParentZqtzBusinessRow(row);
}

/**
 * Builds a display-only reconciliation bridge from governed monthly fields.
 * `preAdjustmentPnl` is explicitly a tie-out value (interest + FV + capital),
 * not a new formal metric; FTP cost and FTP net PnL are never recomputed here.
 */
export function buildPnlByBusinessMonthlyAdjustmentBridge(
  month: PnlByBusinessMonthlyBucket | undefined,
): PnlByBusinessMonthlyAdjustmentBridgeModel | undefined {
  const adjustedParentRows = month?.items
    .filter(isParentZqtzBusinessRow)
    .filter((item) => (numeric(item.manual_adjustment) ?? 0) !== 0)
    .sort(
      (left, right) =>
        Math.abs(numeric(right.manual_adjustment) ?? 0) - Math.abs(numeric(left.manual_adjustment) ?? 0) ||
        left.sort_order - right.sort_order,
    );
  const row = adjustedParentRows?.[0];
  if (!month || !row) {
    return undefined;
  }

  const interestIncome = numeric(row.interest_income);
  const fairValueChange = numeric(row.fair_value_change);
  const capitalGain = numeric(row.capital_gain);
  const manualAdjustment = numeric(row.manual_adjustment);
  const totalPnl = numeric(row.total_pnl);
  const ftpCost = numeric(row.ftp_cost);
  const ftpNetPnl = numeric(row.ftp_net_pnl);
  const preAdjustmentPnl =
    interestIncome !== null && fairValueChange !== null && capitalGain !== null
      ? interestIncome + fairValueChange + capitalGain
      : null;
  const pnlReconciliationDelta =
    preAdjustmentPnl !== null && manualAdjustment !== null && totalPnl !== null
      ? totalPnl - (preAdjustmentPnl + manualAdjustment)
      : null;
  const ftpReconciliationDelta =
    totalPnl !== null && ftpCost !== null && ftpNetPnl !== null ? ftpNetPnl - (totalPnl - ftpCost) : null;
  const toleranceYuan = 0.01;

  return {
    monthKey: month.month_key,
    row,
    adjustedParentRowCount: adjustedParentRows.length,
    preAdjustmentPnl,
    pnlReconciliationDelta,
    ftpReconciliationDelta,
    pnlReconciled:
      pnlReconciliationDelta !== null && Math.abs(pnlReconciliationDelta) <= toleranceYuan,
    ftpReconciled: ftpReconciliationDelta !== null && Math.abs(ftpReconciliationDelta) <= toleranceYuan,
  };
}

export function resolvePnlByBusinessActiveMonthlyBucket(
  months: PnlByBusinessMonthlyBucket[],
  selectedReportDate: string,
  resolvedReportDate?: string,
): PnlByBusinessMonthlyBucket | undefined {
  const preferredReportDate =
    resolvedReportDate && (!selectedReportDate || resolvedReportDate <= selectedReportDate)
      ? resolvedReportDate
      : selectedReportDate;
  const exactBucket = months.find((month) => month.period_end_date === preferredReportDate);
  if (exactBucket) {
    return exactBucket;
  }
  return months.reduce<PnlByBusinessMonthlyBucket | undefined>((latest, month) => {
    if (!preferredReportDate || month.period_end_date > preferredReportDate) {
      return latest;
    }
    return !latest || month.period_end_date > latest.period_end_date ? month : latest;
  }, undefined);
}

export function pickDefaultBusinessRow(rows: PnlByBusinessYtdItem[]): PnlByBusinessYtdItem | undefined {
  return rows.reduce<PnlByBusinessYtdItem | undefined>((current, row) => {
    if (!current) {
      return row;
    }
    return Math.abs(numeric(row.total_pnl) ?? 0) > Math.abs(numeric(current.total_pnl) ?? 0)
      ? row
      : current;
  }, undefined);
}

export function pickTopMonthlyBusinessRow(rows: PnlByBusinessMonthlyItem[]): PnlByBusinessMonthlyItem | undefined {
  return rows.reduce<PnlByBusinessMonthlyItem | undefined>((current, row) => {
    if (!current) {
      return row;
    }
    return Math.abs(numeric(row.total_pnl) ?? 0) > Math.abs(numeric(current.total_pnl) ?? 0)
      ? row
      : current;
  }, undefined);
}

function pickTopNegativeMonthlyBusinessRow(rows: PnlByBusinessMonthlyItem[]): PnlByBusinessMonthlyItem | undefined {
  return rows.reduce<PnlByBusinessMonthlyItem | undefined>((current, row) => {
    const value = numeric(row.total_pnl) ?? 0;
    if (value >= 0) {
      return current;
    }
    if (!current) {
      return row;
    }
    return value < (numeric(current.total_pnl) ?? 0) ? row : current;
  }, undefined);
}

function pickTopFormalRow(rows: PnlByBusinessRow[]): PnlByBusinessRow | undefined {
  return rows.reduce<PnlByBusinessRow | undefined>((current, row) => {
    if (!current) {
      return row;
    }
    return Math.abs(numeric(row.total_pnl) ?? 0) > Math.abs(numeric(current.total_pnl) ?? 0)
      ? row
      : current;
  }, undefined);
}

function pickTopPositiveYtdRow(rows: PnlByBusinessYtdItem[]): PnlByBusinessYtdItem | undefined {
  return rows.reduce<PnlByBusinessYtdItem | undefined>((current, row) => {
    const value = numeric(row.total_pnl) ?? 0;
    if (value <= 0) {
      return current;
    }
    if (!current) {
      return row;
    }
    return value > (numeric(current.total_pnl) ?? 0) ? row : current;
  }, undefined);
}

function pickTopNegativeYtdRow(rows: PnlByBusinessYtdItem[]): PnlByBusinessYtdItem | undefined {
  return rows.reduce<PnlByBusinessYtdItem | undefined>((current, row) => {
    const value = numeric(row.total_pnl) ?? 0;
    if (value >= 0) {
      return current;
    }
    if (!current) {
      return row;
    }
    return value < (numeric(current.total_pnl) ?? 0) ? row : current;
  }, undefined);
}

function pickTopShareYtdRow(rows: PnlByBusinessYtdItem[]): PnlByBusinessYtdItem | undefined {
  let selected: PnlByBusinessYtdItem | undefined;
  let selectedShare = Number.NEGATIVE_INFINITY;
  for (const row of rows) {
    const proportion = numeric(row.proportion);
    if (proportion === null) {
      continue;
    }
    const absoluteShare = Math.abs(proportion);
    if (!selected || absoluteShare > selectedShare) {
      selected = row;
      selectedShare = absoluteShare;
    }
  }
  return selected;
}

function hasAnalysisWarning(meta: ResultMeta | undefined): boolean {
  return (
    meta?.quality_flag === "warning" ||
    meta?.quality_flag === "error" ||
    meta?.quality_flag === "stale" ||
    meta?.quality_flag === "missing" ||
    meta?.fallback_mode === "latest_snapshot" ||
    meta?.vendor_status === "vendor_stale" ||
    meta?.vendor_status === "vendor_unavailable"
  );
}

function hasYtdBusinessActivity(row: PnlByBusinessYtdItem): boolean {
  return (
    row.assets_count > 0 ||
    (numeric(row.current_balance) ?? 0) !== 0 ||
    (numeric(row.total_pnl) ?? 0) !== 0 ||
    (numeric(row.interest_income) ?? 0) !== 0 ||
    (numeric(row.fair_value_change) ?? 0) !== 0 ||
    (numeric(row.capital_gain) ?? 0) !== 0 ||
    (numeric(row.manual_adjustment) ?? 0) !== 0
  );
}

function buildFormalUntracedDisplay(formalResult: PnlByBusinessPayload | undefined): string {
  const untracedCount = formalResult?.summary.untraced_pnl_row_count ?? 0;
  if (untracedCount <= 0) {
    return "0 条未追溯";
  }
  const untracedRows = (formalResult?.rows ?? [])
    .filter((row) => row.balance_row_count <= 0 && row.pnl_row_count > 0)
    .sort((a, b) => b.pnl_row_count - a.pnl_row_count)
    .slice(0, 3);
  if (!untracedRows.length) {
    return `${untracedCount} 条未追溯`;
  }
  return untracedRows.map((row) => `${row.business_type_primary} ${row.pnl_row_count} 条`).join(" / ");
}

function buildFormalTriageDisplay(
  formalResult: PnlByBusinessPayload | undefined,
  formalUntracedDisplay: string,
): string {
  const untracedCount = formalResult?.summary.untraced_pnl_row_count ?? 0;
  if (untracedCount <= 0) {
    return "";
  }
  const breakdown = formalResult?.summary.untraced_breakdown ?? [];
  if (breakdown.length) {
    const topBuckets = breakdown
      .slice()
      .sort((a, b) => (numeric(b.abs_pnl) ?? 0) - (numeric(a.abs_pnl) ?? 0))
      .slice(0, 3)
      .map((row) => `${formalUntracedReasonLabel(row.reason_code)} · ${row.invest_type_std} ${row.pnl_row_count} 条`)
      .join(" / ");
    return `排查顺序：cost_center 已授权放宽；剩余未追溯按余额证据分类（${topBuckets}），不作为业务贡献结论。`;
  }
  return `排查顺序：cost_center 已授权放宽；剩余未追溯先做无余额/无持仓排查（${formalUntracedDisplay}）。`;
}

function formalUntracedReasonLabel(reasonCode: string): string {
  const labels: Record<string, string> = {
    position_absent_before_maturity: "未到期但报表日无持仓",
    matured_before_or_on_report_date: "到期后无持仓",
    never_seen_in_zqtz_asset_balance: "从未见同券资产余额",
    same_day_balance_without_primary_type: "同日余额缺业务分类",
    same_day_balance_multiple_primary_types: "同日余额多业务分类",
    unexpected_untraced: "待复核",
  };
  return labels[reasonCode] ?? "待复核";
}

export function formatPnlQualityStatus(
  quality: ResultMeta["quality_flag"] | undefined,
  state: { isLoading: boolean; isError: boolean; isEmpty: boolean },
) {
  if (state.isLoading) return "读取中";
  if (state.isError) return "读取失败";
  if (state.isEmpty) return "无数据";
  if (!quality) return "待返回";
  const labels: Record<ResultMeta["quality_flag"], string> = {
    ok: "正常",
    warning: "预警",
    error: "错误",
    stale: "陈旧",
    missing: "缺失",
  };
  return labels[quality];
}

export function formatPnlVendorStatus(status: ResultMeta["vendor_status"] | undefined) {
  if (!status) return "待返回";
  if (status === "vendor_stale") return "供应商陈旧";
  if (status === "vendor_unavailable") return "供应商不可用";
  return "正常";
}

export function formatPnlFallbackMode(mode: ResultMeta["fallback_mode"] | undefined) {
  if (!mode) return "待返回";
  return mode === "latest_snapshot" ? "最新快照降级" : "未降级";
}

export function formatPnlEvidenceRows(rows: ResultMeta["evidence_rows"] | undefined) {
  return typeof rows === "number" ? `${rows.toLocaleString("zh-CN")} 行` : "待返回";
}

export function buildPnlByBusinessSelectionModel(input: {
  ytdResult?: PnlByBusinessYtdPayload;
  selectedBusinessKey: string | null;
}): PnlByBusinessSelectionModel {
  const ytdRows = input.ytdResult?.items ?? [];
  const parentYtdRows = ytdRows.filter(isParentZqtzBusinessRow);
  const defaultBusinessRow = pickDefaultBusinessRow(parentYtdRows);
  const selectedBusinessRow =
    ytdRows.find((row) => row.row_key === input.selectedBusinessKey) ?? defaultBusinessRow;
  return {
    ytdRows,
    parentYtdRows,
    defaultBusinessRow,
    selectedBusinessRow,
  };
}

function buildHeroReportDateFields(input: {
  viewMode: PnlByBusinessViewMode;
  selectedReportDate: string;
  activeResultMeta?: ResultMeta;
}): Pick<PnlHeroModel, "reportDateLabel" | "requestedReportDate" | "asOfDate" | "reportDateNote"> {
  const requestedReportDate = input.selectedReportDate || "待选择";
  const asOfDate = input.activeResultMeta?.as_of_date ?? input.activeResultMeta?.resolved_report_date ?? "待返回";
  const reportDateLabel = input.viewMode === "monthly" ? "请求报表日" : "分析截止日";
  const isFallback = input.activeResultMeta?.fallback_mode === "latest_snapshot";
  const datesAligned =
    requestedReportDate !== "待选择" &&
    asOfDate !== "待返回" &&
    requestedReportDate === asOfDate;

  let reportDateNote: string;
  if (isFallback) {
    reportDateNote = `实际 as_of ${asOfDate}；请求 ${requestedReportDate}，已启用 fallback 快照。`;
  } else if (datesAligned) {
    reportDateNote = `实际 as_of ${asOfDate}；与请求日一致。`;
  } else if (requestedReportDate !== "待选择" && asOfDate !== "待返回") {
    reportDateNote = `实际 as_of ${asOfDate}；与请求 ${requestedReportDate} 不一致。`;
  } else {
    reportDateNote = `实际 as_of ${asOfDate}。`;
  }

  return {
    reportDateLabel,
    requestedReportDate,
    asOfDate,
    reportDateNote,
  };
}

function buildHeroConclusion(input: {
  viewMode: PnlByBusinessViewMode;
  selectedReportDate: string;
  selectedYear: number;
  activeResultMeta?: ResultMeta;
  ytdResult?: PnlByBusinessYtdPayload;
  activeMonthlyBucket?: PnlByBusinessMonthlyBucket;
  formalResult?: PnlByBusinessPayload;
  topMonthlyRow?: PnlByBusinessMonthlyItem;
  topYtdRow?: PnlByBusinessYtdItem;
  topFormalRow?: PnlByBusinessRow;
}): PnlHeroModel {
  const reportDateFields = buildHeroReportDateFields({
    viewMode: input.viewMode,
    selectedReportDate: input.selectedReportDate,
    activeResultMeta: input.activeResultMeta,
  });

  if (input.viewMode === "monthly") {
    const monthKey = input.activeMonthlyBucket?.month_key ?? input.selectedReportDate.slice(0, 7);
    const total = formatYuanAsWanUnit(input.activeMonthlyBucket?.summary.total_pnl);
    const topBusiness = input.topMonthlyRow?.business_type ?? "暂无明细";
    return {
      ...reportDateFields,
      businessQuestion: VIEW_MODE_BUSINESS_QUESTIONS.monthly,
      conclusionTitle: `${monthKey} 月报合计 ${total}`,
      conclusionDetail: `最大损益业务：${topBusiness}；口径与月报 ZQTZ 管理披露分类一致。`,
    };
  }

  if (input.viewMode === "ytd") {
    const total = formatYuanAsWanUnit(input.ytdResult?.total_pnl);
    const topBusiness = input.topYtdRow?.business_type ?? "暂无明细";
    return {
      ...reportDateFields,
      businessQuestion: VIEW_MODE_BUSINESS_QUESTIONS.ytd,
      conclusionTitle: `${input.ytdResult?.period_label ?? `${input.selectedYear} 年累计`} ${total}`,
      conclusionDetail: `最大损益业务：${topBusiness}；父级汇总不含「其中」细分行。`,
    };
  }

  const total = formatYuanAsWanUnit(input.formalResult?.summary.total_pnl);
  const topBusiness = input.topFormalRow?.business_type_primary ?? "暂无明细";
  return {
    ...reportDateFields,
    businessQuestion: VIEW_MODE_BUSINESS_QUESTIONS.formal,
    conclusionTitle: `${input.formalResult?.report_date ?? input.selectedReportDate} formal 合计 ${total}`,
    conclusionDetail: `最大 primary 行：${topBusiness}；未追溯 PnL 行 ${input.formalResult?.summary.untraced_pnl_row_count ?? 0} 条。`,
  };
}

function buildStateSurfaces(input: {
  activeDataStatus: string;
  activeResultMeta?: ResultMeta;
  activeDiagnostics?: {
    coverage_days?: number;
    expected_days?: number;
    sample_filled?: boolean;
    sample_fill_method?: string | null;
    unallocated_pnl?: string;
    unallocated_row_count?: number;
    reconciliation_delta?: string;
  };
  clientMode?: "real" | "mock";
}): PnlStateSurfaceItem[] {
  const surfaces: PnlStateSurfaceItem[] = [];

  if (input.clientMode === "mock") {
    surfaces.push({
      key: "mock-mode",
      variant: "mock",
      title: "演示 / Mock 读路径",
      description: "当前为本地契约回放，不代表正式 DuckDB 读面。",
    });
  }

  const meta = input.activeResultMeta;
  if (meta?.formal_use_allowed === false) {
    surfaces.push({
      key: "definition-pending",
      variant: "definition-pending",
      title: "指标口径待正式确认",
      description: "当前为分析候选口径，仅用于经营分析与对账，不作为正式报表口径。",
    });
  }

  const diagnostics = input.activeDiagnostics;
  const coverageDays = diagnostics?.coverage_days;
  const expectedDays = diagnostics?.expected_days;
  if (
    typeof coverageDays === "number" &&
    typeof expectedDays === "number" &&
    expectedDays > 0 &&
    coverageDays < expectedDays
  ) {
    surfaces.push({
      key: "coverage-partial",
      variant: "stale",
      title: "日均余额样本覆盖不足",
      description: `余额观测覆盖 ${coverageDays}/${expectedDays} 天；sample_filled=${String(
        diagnostics?.sample_filled ?? false,
      )}，method=${diagnostics?.sample_fill_method ?? "none"}。收益率与 FTP 结果需结合覆盖率使用。`,
    });
  }

  const unallocatedPnl = numeric(diagnostics?.unallocated_pnl);
  const unallocatedRowCount = diagnostics?.unallocated_row_count ?? 0;
  if (unallocatedRowCount > 0 || (unallocatedPnl !== null && unallocatedPnl !== 0)) {
    surfaces.push({
      key: "unallocated",
      variant: "definition-pending",
      title: "存在未分类损益",
      description: `${unallocatedRowCount} 条损益未命中父级业务分类，金额 ${formatYuanAsWanUnit(
        diagnostics?.unallocated_pnl,
      )}；未对 A/T 口径做推测映射。`,
    });
  }

  const reconciliationDelta = numeric(diagnostics?.reconciliation_delta);
  if (reconciliationDelta !== null && reconciliationDelta !== 0) {
    surfaces.push({
      key: "reconciliation-break",
      variant: "error",
      title: "分类损益未闭合",
      description: `源损益、父级分类与未分类差额仍有 ${formatYuanAsWanUnit(
        diagnostics?.reconciliation_delta,
      )}，请先核对规则与手工调整。`,
    });
  }
  if (meta?.quality_flag === "error" || input.activeDataStatus === "错误") {
    surfaces.push({
      key: "quality-error",
      variant: "error",
      title: "结果质量错误",
      description: `quality_flag=error；as_of ${meta?.as_of_date ?? "待返回"}。请勿据此做正式经营结论。`,
    });
  }

  if (meta?.quality_flag === "missing" || input.activeDataStatus === "缺失") {
    surfaces.push({
      key: "quality-missing",
      variant: "empty",
      title: "结果数据缺失",
      description: "quality_flag=missing；当前读面未返回完整 formal 结果，需核对报表日与数据源。",
    });
  }

  if (meta?.quality_flag === "stale" || input.activeDataStatus === "陈旧") {
    surfaces.push({
      key: "stale",
      variant: "stale",
      title: "结果可能陈旧",
      description: `as_of ${meta?.as_of_date ?? "待返回"}；请结合生成时间与 trace 核对是否仍适用。`,
    });
  }

  if (meta?.quality_flag === "warning" || input.activeDataStatus === "预警") {
    surfaces.push({
      key: "warning",
      variant: "stale",
      title: "质量预警",
      description: "结果 meta 标记为预警，下钻前请核对 vendor 与 fallback 状态。",
    });
  }

  if (meta?.fallback_mode === "latest_snapshot") {
    surfaces.push({
      key: "fallback-date",
      variant: "fallback-date",
      title: "已启用 fallback 快照",
      description: `展示 as_of ${meta.as_of_date ?? "待返回"}；非请求报表日的最新可用快照。`,
    });
  }

  if (meta?.vendor_status === "vendor_stale") {
    surfaces.push({
      key: "vendor-stale",
      variant: "stale",
      title: "供应商数据陈旧",
      description: "上游 vendor 标记为 stale，指标仍来自已返回 formal 结果。",
    });
  }

  if (meta?.vendor_status === "vendor_unavailable") {
    surfaces.push({
      key: "vendor-unavailable",
      variant: "error",
      title: "供应商不可用",
      description: "上游 vendor 不可用；请结合降级模式与 trace 判断是否可决策。",
    });
  }

  return surfaces;
}

function buildStatusStrip(input: {
  viewMode: PnlByBusinessViewMode;
  activeDataStatus: string;
  activeResultMeta?: ResultMeta;
  selectedReportDate: string;
}): PnlDataStatusStripModel {
  const meta = input.activeResultMeta;
  return {
    viewModeLabel: VIEW_MODE_STATUS_LABELS[input.viewMode],
    dataStatus: input.activeDataStatus,
    asOfDate: meta?.as_of_date ?? meta?.resolved_report_date ?? "待返回",
    fallbackMode: formatPnlFallbackMode(meta?.fallback_mode),
    vendorStatus: formatPnlVendorStatus(meta?.vendor_status),
    evidenceRows: formatPnlEvidenceRows(meta?.evidence_rows),
    generatedAt: meta?.generated_at ?? "待返回",
    traceId: meta?.trace_id ?? "待返回",
  };
}

function buildMonthlySummaryCards(input: {
  activeMonthlyBucket?: PnlByBusinessMonthlyBucket;
  selectedReportDate: string;
  parentMonthlyItems: PnlByBusinessMonthlyItem[];
  topMonthlyRow?: PnlByBusinessMonthlyItem;
}): PnlSummaryCard[] {
  const { activeMonthlyBucket, topMonthlyRow } = input;
  return [
    {
      label: "月报合计损益",
      value: formatYuanAsWanUnit(activeMonthlyBucket?.summary.total_pnl),
      detail: activeMonthlyBucket?.month_key ?? input.selectedReportDate,
      tone: toneFromSigned(activeMonthlyBucket?.summary.total_pnl),
    },
    {
      label: "业务种类",
      value: `${input.parentMonthlyItems.length}`,
      detail: "父级 ZQTZ 分类",
    },
    {
      label: "最大损益业务",
      value: topMonthlyRow?.business_type ?? "-",
      detail: topMonthlyRow ? formatYuanAsWanUnit(topMonthlyRow.total_pnl) : "无明细",
      valueVariant: "text",
      tone: toneFromSigned(topMonthlyRow?.total_pnl),
    },
    {
      label: "月报收益率",
      value: formatAnalysisYieldPct(activeMonthlyBucket?.summary.annualized_yield_pct),
      detail: "月度日均分母",
      tone: toneFromSigned(activeMonthlyBucket?.summary.annualized_yield_pct),
    },
  ];
}

function buildYtdSummaryCards(input: {
  ytdResult?: PnlByBusinessYtdPayload;
  selectedYear: number;
  parentYtdRows: PnlByBusinessYtdItem[];
  ytdAssetCount: number;
  topYtdRow?: PnlByBusinessYtdItem;
}): PnlSummaryCard[] {
  const { ytdResult, topYtdRow } = input;
  const topShareRow = pickTopShareYtdRow(input.parentYtdRows);
  return [
    {
      label: "年累计损益",
      value: formatYuanAsWanUnit(ytdResult?.total_pnl),
      detail: ytdResult?.period_label ?? `${input.selectedYear} 年累计`,
      tone: toneFromSigned(ytdResult?.total_pnl),
    },
    {
      label: "业务种类",
      value: `${input.parentYtdRows.length}`,
      detail: `${input.ytdAssetCount} 个父级归类命中`,
    },
    {
      label: "最大损益业务",
      value: topYtdRow?.business_type ?? "-",
      detail: topYtdRow ? formatYuanAsWanUnit(topYtdRow.total_pnl) : "无明细",
      valueVariant: "text",
      tone: toneFromSigned(topYtdRow?.total_pnl),
    },
    {
      label: "最大占比",
      value: formatRatioPct(topShareRow?.proportion),
      detail: topShareRow?.business_type ?? "无明细",
    },
  ];
}

function buildFormalSummaryCards(input: {
  formalResult?: PnlByBusinessPayload;
  formalRows: PnlByBusinessRow[];
  selectedReportDate: string;
  topFormalRow?: PnlByBusinessRow;
}): PnlSummaryCard[] {
  const { formalResult, topFormalRow } = input;
  return [
    {
      label: "报表日合计损益",
      value: formatYuanAsWanUnit(formalResult?.summary.total_pnl),
      detail: `${formalResult?.report_date ?? input.selectedReportDate} · formal`,
      tone: toneFromSigned(formalResult?.summary.total_pnl),
    },
    {
      label: "业务种类行数",
      value: `${input.formalRows.length}`,
      detail: `已追溯损益行 ${formalResult?.summary.traced_pnl_row_count ?? 0}`,
    },
    {
      label: "最大损益（行）",
      value: topFormalRow?.business_type_primary ?? "-",
      detail: topFormalRow ? formatYuanAsWanUnit(topFormalRow.total_pnl) : "无明细",
      valueVariant: "text",
      tone: toneFromSigned(topFormalRow?.total_pnl),
    },
    {
      label: "未追溯 PnL 行",
      value: `${formalResult?.summary.untraced_pnl_row_count ?? 0}`,
      detail: "与余额 join 未命中时计数",
    },
  ];
}

function buildYtdDrilldownRecommendation(input: {
  isWarning: boolean;
  topContribution?: PnlByBusinessYtdItem;
  topDrag?: PnlByBusinessYtdItem;
  topShare?: PnlByBusinessYtdItem;
  missingAdbCount: number;
  zeroAdbCount: number;
  missingFtpFieldCount: number;
  ftpAvailable: boolean;
  adbEvidenceStatus: PnlByBusinessAdbEvidenceStatus;
}): PnlByBusinessDrilldownRecommendation {
  const targetBusinessLabel =
    input.topContribution?.business_type ??
    input.topDrag?.business_type ??
    input.topShare?.business_type ??
    "暂无明细";

  if (input.isWarning) {
    return {
      targetBusinessLabel,
      priorityLabel: "预警/降级",
      dimensionLabel: "证据状态",
      actionLabel: "先核对质量、fallback、trace 后再下钻",
      evidenceLabel: "结果质量待复核",
      reasonLabel: "当前 meta 存在 warning/stale/fallback/vendor 降级信号，业务结论先降级为证据复核。",
    };
  }

  if (input.missingAdbCount > 0) {
    return {
      targetBusinessLabel,
      priorityLabel: "补日均",
      dimensionLabel: "日均映射",
      actionLabel: "先补齐 ADB 再判断 FTP 后收益",
      evidenceLabel: `缺日均 ${input.missingAdbCount} 项`,
      reasonLabel: "父级业务仍有损益或余额活动，但 ADB 未全覆盖；年化收益率和 FTP 后收益先不作为决策结论。",
    };
  }

  if (input.zeroAdbCount > 0) {
    return {
      targetBusinessLabel,
      priorityLabel: "日均为0",
      dimensionLabel: "日均分母",
      actionLabel:
        input.adbEvidenceStatus === "ytd_fallback"
          ? "ADB 对照不可用，先确认 YTD 零值；收益率/FTP 暂不计算"
          : "先确认 ADB 为真实零，再查看损益贡献；收益率/FTP 暂不计算",
      evidenceLabel:
        input.adbEvidenceStatus === "ytd_fallback"
          ? `YTD 日均为0 ${input.zeroAdbCount} 项（待复核）`
          : `日均为0 ${input.zeroAdbCount} 项`,
      reasonLabel:
        input.adbEvidenceStatus === "ytd_fallback"
          ? "YTD 主端点返回零分母，但 ADB comparison 不可用，当前无法独立区分真实零与未映射；年化收益率和 FTP 后收益不作为决策结论。"
          : "ADB 已返回但存在零分母；可展示真实日均为 0，但年化收益率和 FTP 后收益不作为决策结论。",
    };
  }

  if (input.missingFtpFieldCount > 0) {
    return {
      targetBusinessLabel,
      priorityLabel: "FTP 字段待核对",
      dimensionLabel: "FTP 返回字段",
      actionLabel: "先核对 YTD FTP 成本与 FTP 后损益字段",
      evidenceLabel: `FTP 字段缺失 ${input.missingFtpFieldCount} 项`,
      reasonLabel: "日均已覆盖，但部分活跃父级未同时返回 FTP 成本和 FTP 后损益，暂不标记为 FTP 可分析。",
    };
  }

  if (input.adbEvidenceStatus === "ytd_fallback") {
    return {
      targetBusinessLabel,
      priorityLabel: "预警/降级",
      dimensionLabel: "ADB 补充复核",
      actionLabel: "保留 YTD 分析，暂缓跨源 ADB 覆盖结论",
      evidenceLabel: "YTD 日均回退",
      reasonLabel: "本页使用 YTD 主端点返回的同区间日均与 FTP 字段；ADB comparison 补充复核当前不可用。",
    };
  }

  if (input.adbEvidenceStatus === "loading") {
    return {
      targetBusinessLabel,
      priorityLabel: input.topDrag ? "先看拖累" : "FTP 后仍有效",
      dimensionLabel: "证券级下钻",
      actionLabel: "先看 YTD 贡献与 FTP，等待 ADB 补充复核",
      evidenceLabel: "ADB 补充复核中",
      reasonLabel: "YTD 主端点日均与 FTP 字段已返回；ADB comparison 尚在读取，不据此判定覆盖缺口。",
    };
  }

  return {
    targetBusinessLabel,
    priorityLabel: input.topDrag ? "先看拖累" : "FTP 后仍有效",
    dimensionLabel: "证券级下钻",
    actionLabel: "看 Top 贡献券、Top 拖累券、FTP 后为负",
    evidenceLabel: "ADB 已覆盖",
    reasonLabel: input.topDrag
      ? `贡献来自 ${input.topContribution?.business_type ?? "暂无正贡献"}，拖累来自 ${input.topDrag.business_type}；先用证券级明细确认是否为个券或 FTP 后转负。`
      : `贡献集中在 ${targetBusinessLabel}；ADB 已覆盖，可继续检查证券级贡献、拖累和 FTP 后为负资产。`,
  };
}

function buildPnlByBusinessInsight(input: {
  viewMode: PnlByBusinessViewMode;
  activeResultMeta?: ResultMeta;
  ytdResult?: PnlByBusinessYtdPayload;
  parentYtdRows: PnlByBusinessYtdItem[];
  topFormalRow?: PnlByBusinessRow;
  formalResult?: PnlByBusinessPayload;
  activeMonthlyBucket?: PnlByBusinessMonthlyBucket;
  topMonthlyRow?: PnlByBusinessMonthlyItem;
  topMonthlyDragRow?: PnlByBusinessMonthlyItem;
  adbAvgByBusinessType?: Map<string, number>;
  adbEvidenceStatus?: PnlByBusinessAdbEvidenceStatus;
  manualAdjustmentCount?: number;
}): PnlByBusinessInsightModel {
  const isWarning = hasAnalysisWarning(input.activeResultMeta);
  const adbEvidenceStatus = input.adbEvidenceStatus ?? "comparison";

  if (input.viewMode === "formal") {
    const topFormalValue = input.topFormalRow?.total_pnl;
    const formalUntracedCount = input.formalResult?.summary.untraced_pnl_row_count ?? 0;
    const formalUntracedDisplay = buildFormalUntracedDisplay(input.formalResult);
    const formalTriageDisplay = buildFormalTriageDisplay(input.formalResult, formalUntracedDisplay);
    return {
      confidenceLabel: isWarning ? "预警/降级" : "仅对账",
      totalPnlDisplay: formatYuanAsWanUnit(input.formalResult?.summary.total_pnl),
      topContributionLabel: input.topFormalRow?.business_type_primary ?? "暂无明细",
      topContributionDisplay: formatYuanAsWanUnit(topFormalValue),
      topDragLabel: (numeric(topFormalValue) ?? 0) < 0 ? (input.topFormalRow?.business_type_primary ?? "暂无明细") : "无拖累",
      topDragDisplay: (numeric(topFormalValue) ?? 0) < 0 ? formatYuanAsWanUnit(topFormalValue) : "-",
      topShareLabel: "仅对账",
      topShareDisplay: "不与月报/YTD 混加",
      ftpAvailable: false,
      missingAdbCount: 0,
      zeroAdbCount: 0,
      missingFtpFieldCount: 0,
      adbEvidenceStatus,
      manualAdjustmentCount: 0,
      formalUntracedCount,
      formalUntracedValueDisplay: `${formalUntracedCount} 条未追溯`,
      formalUntracedDisplay,
      formalTriageDisplay,
      nextStep:
        formalUntracedCount > 0
          ? `用于对账证据和未追溯行排查，不作为业务贡献主分析。优先核对：${formalUntracedDisplay}。`
          : "用于对账证据，不作为业务贡献主分析；当前无未追溯行。",
      recommendedDrilldown: {
        targetBusinessLabel: input.topFormalRow?.business_type_primary ?? "formal primary",
        priorityLabel: "仅对账",
        dimensionLabel: "未追溯对账",
        actionLabel: formalUntracedCount > 0 ? "核对未追溯行和 breakdown" : "保留为 formal 对账证据",
        evidenceLabel: `${formalUntracedCount} 条未追溯`,
        reasonLabel: "formal primary 只用于追溯 fact_formal_pnl_fi / bridge / balance join，不与月报或 YTD 结论混加。",
      },
    };
  }

  if (input.viewMode === "monthly") {
    const total = input.activeMonthlyBucket?.summary.total_pnl;
    return {
      confidenceLabel: isWarning ? "预警/降级" : "可分析",
      totalPnlDisplay: formatYuanAsWanUnit(total),
      topContributionLabel: input.topMonthlyRow?.business_type ?? "暂无明细",
      topContributionDisplay: formatYuanAsWanUnit(input.topMonthlyRow?.total_pnl),
      topDragLabel: input.topMonthlyDragRow?.business_type ?? "无拖累",
      topDragDisplay: input.topMonthlyDragRow ? formatYuanAsWanUnit(input.topMonthlyDragRow.total_pnl) : "-",
      topShareLabel: input.topMonthlyRow?.business_type ?? "暂无明细",
      topShareDisplay: formatRatioPct(input.topMonthlyRow?.proportion),
      ftpAvailable: numeric(input.activeMonthlyBucket?.summary.ftp_net_pnl) !== null,
      missingAdbCount: 0,
      zeroAdbCount: 0,
      missingFtpFieldCount: 0,
      adbEvidenceStatus,
      manualAdjustmentCount: input.manualAdjustmentCount ?? 0,
      formalUntracedCount: 0,
      formalUntracedValueDisplay: "未读取",
      formalUntracedDisplay: "切到 primary 对账查看；不与月报/YTD 混加",
      formalTriageDisplay: "",
      nextStep: "先看当月贡献，再切到年累计核对趋势与 FTP 后收益。",
      recommendedDrilldown: {
        targetBusinessLabel: input.topMonthlyRow?.business_type ?? "暂无明细",
        priorityLabel: input.topMonthlyDragRow ? "月度拖累" : "月度贡献",
        dimensionLabel: "月度明细",
        actionLabel: "先看当月贡献/拖累，再切 YTD 验证趋势",
        evidenceLabel: numeric(input.activeMonthlyBucket?.summary.ftp_net_pnl) !== null ? "月度 FTP 已返回" : "月度 FTP 未返回",
        reasonLabel: "月报视图只回答当月口径；需要判断持续性时，应切到 YTD 并结合 FTP/ADB。",
      },
    };
  }

  const topContribution = pickTopPositiveYtdRow(input.parentYtdRows);
  const topDrag = pickTopNegativeYtdRow(input.parentYtdRows);
  const topShare = pickTopShareYtdRow(input.parentYtdRows);
  const activeYtdRows = input.parentYtdRows.filter(hasYtdBusinessActivity);
  const resolvedAdbValues = activeYtdRows.map((row) =>
      input.adbAvgByBusinessType
        ? resolveAdbAvgYuan(row.business_type, input.adbAvgByBusinessType)
        : undefined,
    );
  const missingAdbCount = resolvedAdbValues.filter((adb) => adb === undefined).length;
  const zeroAdbCount = resolvedAdbValues.filter((adb) => adb === 0).length;
  const missingFtpFieldCount = activeYtdRows.filter(
    (row) => numeric(row.ftp_cost) === null || numeric(row.ftp_net_pnl) === null,
  ).length;
  const ftpAvailable =
    missingAdbCount === 0 &&
    zeroAdbCount === 0 &&
    missingFtpFieldCount === 0 &&
    activeYtdRows.length > 0;
  const confidenceLabel: PnlByBusinessInsightConfidence = isWarning
    ? "预警/降级"
    : missingAdbCount > 0
      ? "缺日均"
      : zeroAdbCount > 0
        ? "日均为0"
        : missingFtpFieldCount > 0 || adbEvidenceStatus === "ytd_fallback"
          ? "预警/降级"
          : ftpAvailable
            ? "可分析"
            : "缺日均";

  return {
    confidenceLabel,
    totalPnlDisplay: formatYuanAsWanUnit(input.ytdResult?.total_pnl),
    topContributionLabel: topContribution?.business_type ?? "暂无正贡献",
    topContributionDisplay: formatYuanAsWanUnit(topContribution?.total_pnl),
    topDragLabel: topDrag?.business_type ?? "无拖累",
    topDragDisplay: topDrag ? formatYuanAsWanUnit(topDrag.total_pnl) : "-",
    topShareLabel: topShare?.business_type ?? "暂无占比",
    topShareDisplay: formatRatioPct(topShare?.proportion),
    ftpAvailable,
    missingAdbCount,
    zeroAdbCount,
    missingFtpFieldCount,
    adbEvidenceStatus,
    manualAdjustmentCount: input.manualAdjustmentCount ?? 0,
    formalUntracedCount: 0,
    formalUntracedValueDisplay: "未读取",
    formalUntracedDisplay: "切到 primary 对账查看；不与月报/YTD 混加",
    formalTriageDisplay: "",
    nextStep:
      missingAdbCount > 0
        ? "先补齐日均映射，再判断年化收益率和 FTP 后收益。"
        : zeroAdbCount > 0
          ? adbEvidenceStatus === "ytd_fallback"
            ? "ADB 补充复核不可用，先确认 YTD 日均零值是否为真实零，再判断收益率和 FTP。"
            : "先确认日均为真实零，再判断该业务的收益率和 FTP 结论。"
          : missingFtpFieldCount > 0
            ? "先核对 YTD FTP 成本与 FTP 后损益返回字段，再进入收益归因。"
            : adbEvidenceStatus === "ytd_fallback"
              ? "YTD 日均与 FTP 字段可用于本页分析；ADB 补充复核不可用，跨源覆盖结论暂缓。"
              : ftpAvailable
                ? "先核对 FTP 后收益，再进入多维下钻定位组合、会计分类或资产明细。"
                : "先核对日均与 FTP 返回字段，再判断年化收益率和 FTP 后收益。",
    recommendedDrilldown: buildYtdDrilldownRecommendation({
      isWarning,
      topContribution,
      topDrag,
      topShare,
      missingAdbCount,
      zeroAdbCount,
      missingFtpFieldCount,
      ftpAvailable,
      adbEvidenceStatus,
    }),
  };
}

export function buildPnlByBusinessPageModel(
  input: BuildPnlByBusinessPageModelInput,
): PnlByBusinessPageModel {
  const selection = buildPnlByBusinessSelectionModel({
    ytdResult: input.ytdResult,
    selectedBusinessKey: input.selectedBusinessKey,
  });
  const monthlyBusinessMonths = input.monthlyResult?.months ?? [];
  const activeMonthlyBucket = resolvePnlByBusinessActiveMonthlyBucket(
    monthlyBusinessMonths,
    input.selectedReportDate,
    input.monthlyResult?.as_of_date,
  );
  const parentMonthlyItems = activeMonthlyBucket?.items.filter(isParentZqtzBusinessRow) ?? [];
  const topMonthlyRow = pickTopMonthlyBusinessRow(parentMonthlyItems);
  const topMonthlyDragRow = pickTopNegativeMonthlyBusinessRow(parentMonthlyItems);
  const formalRows = input.formalResult?.rows ?? [];
  const topFormalRow = pickTopFormalRow(formalRows);
  const topYtdRow = selection.defaultBusinessRow;
  const ytdAssetCount = selection.parentYtdRows.reduce((total, row) => total + row.assets_count, 0);
  const loading =
    input.datesState.isLoading ||
    (input.viewMode === "monthly" && input.monthlyState.isLoading) ||
    (input.viewMode === "ytd" && input.ytdState.isLoading) ||
    (input.viewMode === "formal" && input.formalState.isLoading);
  const error =
    input.datesState.isError ||
    (input.viewMode === "monthly" && input.monthlyState.isError) ||
    (input.viewMode === "ytd" && input.ytdState.isError) ||
    (input.viewMode === "formal" && input.formalState.isError);
  const empty =
    !loading &&
    !error &&
    (!input.selectedReportDate ||
      (input.viewMode === "monthly" && monthlyBusinessMonths.length === 0) ||
      (input.viewMode === "ytd" && selection.ytdRows.length === 0) ||
      (input.viewMode === "formal" && formalRows.length === 0));
  const activeResultMeta =
    input.viewMode === "monthly"
      ? input.monthlyMeta
      : input.viewMode === "ytd"
        ? input.ytdMeta
        : input.formalMeta;
  const activeDiagnostics =
    input.viewMode === "monthly" ? activeMonthlyBucket : input.viewMode === "ytd" ? input.ytdResult : undefined;
  const activeDataStatus = formatPnlQualityStatus(activeResultMeta?.quality_flag, {
    isLoading: loading,
    isError: error,
    isEmpty: empty,
  });
  const summaryCards =
    input.viewMode === "monthly"
      ? buildMonthlySummaryCards({
          activeMonthlyBucket,
          selectedReportDate: input.selectedReportDate,
          parentMonthlyItems,
          topMonthlyRow,
        })
      : input.viewMode === "ytd"
        ? buildYtdSummaryCards({
            ytdResult: input.ytdResult,
            selectedYear: input.selectedYear,
            parentYtdRows: selection.parentYtdRows,
            ytdAssetCount,
            topYtdRow,
          })
        : buildFormalSummaryCards({
            formalResult: input.formalResult,
            formalRows,
            selectedReportDate: input.selectedReportDate,
            topFormalRow,
          });

  return {
    ...selection,
    monthlyBusinessMonths,
    activeMonthlyBucket,
    parentMonthlyItems,
    topMonthlyRow,
    formalRows,
    topFormalRow,
    ytdAssetCount,
    loading,
    error,
    empty,
    activeResultMeta,
    activeDataStatus,
    statusStrip: buildStatusStrip({
      viewMode: input.viewMode,
      activeDataStatus,
      activeResultMeta,
      selectedReportDate: input.selectedReportDate,
    }),
    summaryCards,
    insight: buildPnlByBusinessInsight({
      viewMode: input.viewMode,
      activeResultMeta,
      ytdResult: input.ytdResult,
      parentYtdRows: selection.parentYtdRows,
      topFormalRow,
      formalResult: input.formalResult,
      activeMonthlyBucket,
      topMonthlyRow,
      topMonthlyDragRow,
      adbAvgByBusinessType: input.adbAvgByBusinessType,
      adbEvidenceStatus: input.adbEvidenceStatus,
      manualAdjustmentCount: input.manualAdjustmentCount,
    }),
    hero: buildHeroConclusion({
      viewMode: input.viewMode,
      selectedReportDate: input.selectedReportDate,
      selectedYear: input.selectedYear,
      activeResultMeta,
      ytdResult: input.ytdResult,
      activeMonthlyBucket,
      formalResult: input.formalResult,
      topMonthlyRow,
      topYtdRow,
      topFormalRow,
    }),
    stateSurfaces: buildStateSurfaces({
      activeDataStatus,
      activeResultMeta,
      activeDiagnostics,
      clientMode: input.clientMode,
    }),
  };
}
