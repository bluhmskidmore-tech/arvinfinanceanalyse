import type {
  KpiCardProps,
} from "../../components/KpiCard";
import type {
  PnlByBusinessMonthlyBucket,
  PnlByBusinessMonthlyItem,
  PnlByBusinessMonthlyPayload,
  PnlByBusinessPayload,
  PnlByBusinessRow,
  PnlByBusinessYtdItem,
  PnlByBusinessYtdPayload,
  ResultMeta,
} from "../../api/contracts";

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

type BuildPnlByBusinessPageModelInput = {
  viewMode: PnlByBusinessViewMode;
  selectedReportDate: string;
  selectedYear: number;
  selectedBusinessKey: string | null;
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
};

function numeric(raw: string | number | null | undefined): number | null {
  if (raw === null || raw === undefined || raw === "") {
    return null;
  }
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
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
    asOfDate: meta?.as_of_date ?? input.selectedReportDate ?? "待返回",
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
  return [
    {
      label: "月报累计损益",
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
      value: formatRatioPct(topYtdRow?.proportion),
      detail: topYtdRow?.business_type ?? "无明细",
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

export function buildPnlByBusinessPageModel(
  input: BuildPnlByBusinessPageModelInput,
): PnlByBusinessPageModel {
  const selection = buildPnlByBusinessSelectionModel({
    ytdResult: input.ytdResult,
    selectedBusinessKey: input.selectedBusinessKey,
  });
  const monthlyBusinessMonths = input.monthlyResult?.months ?? [];
  const activeMonthlyBucket =
    monthlyBusinessMonths.find((month) => month.period_end_date === input.selectedReportDate) ??
    monthlyBusinessMonths[0];
  const parentMonthlyItems = activeMonthlyBucket?.items.filter(isParentZqtzBusinessRow) ?? [];
  const topMonthlyRow = pickTopMonthlyBusinessRow(parentMonthlyItems);
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
  };
}
