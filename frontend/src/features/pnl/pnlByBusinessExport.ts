import writeExcelFile from "write-excel-file/browser";
import type { Sheet, SheetData } from "write-excel-file/browser";

import type {
  PnlByBusinessBalanceQualityIssue,
  PnlByBusinessMonthlyBucket,
  PnlByBusinessMonthlyItem,
  PnlByBusinessRow,
  PnlByBusinessYtdItem,
  PnlByBusinessYtdSummary,
  PnlByBusinessManualAdjustmentPayload,
  PnlByBusinessAnalysisRow,
  PnlByBusinessAnalysisDimension,
  PnlByBusinessAnalysisPayload,
  PnlByBusinessYtdUnallocatedBreakdownRow,
  PnlByBusinessYtdUnallocatedItem,
} from "../../api/contracts";
import type { PnlByBusinessSummary } from "../../api/pnlByBusinessContracts";
import { inclusiveCalendarDays } from "./pnlByBusinessAnnualizedYield";
import { buildNegativeFtpList } from "./pnlByBusinessPageModel";

type SheetAoA = SheetData;
export type PnlByBusinessExportSheet = Sheet<Blob>;

const YUAN_PER_WAN = 10_000;
const YUAN_PER_YI = 100_000_000;

function num(raw: string | number | null | undefined): number | null {
  if (raw === null || raw === undefined || raw === "") {
    return null;
  }
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

type ZqtzBusinessExportRow = {
  row_key: string;
  business_type: string;
  source_note?: string | null;
};

/** 排除「其中」细分行，与页面父级汇总一致 */
function isParentZqtzBusinessRow(row: ZqtzBusinessExportRow): boolean {
  if (row.row_key.includes("_detail_")) {
    return false;
  }
  if (row.business_type.startsWith("其中：")) {
    return false;
  }
  const note = String(row.source_note ?? "");
  return !note.includes("其中项");
}

function isDetailZqtzBusinessRow(row: ZqtzBusinessExportRow): boolean {
  return !isParentZqtzBusinessRow(row);
}

function wanFromYuan(raw: string | number | null | undefined): number | null {
  const v = num(raw);
  return v === null ? null : v / YUAN_PER_WAN;
}

function yiFromYuan(raw: string | number | null | undefined): number | null {
  const v = num(raw);
  return v === null ? null : v / YUAN_PER_YI;
}

/** Excel 工作表名最多 31 字符 */
function safeSheetName(name: string): string {
  const cleaned = name.replace(/[:\\/?*[\]]/g, "_").slice(0, 31);
  return cleaned || "Sheet1";
}

const ANALYSIS_DIM_LABELS: Record<PnlByBusinessAnalysisDimension, string> = {
  monthly: "月份",
  portfolio: "组合",
  accounting: "会计分类",
  currency: "原币种",
  cost_center: "成本中心",
  instrument: "资产明细",
  bond_bucket: "投资资产四类",
  bond_bucket_monthly: "四类月度",
};

export type PnlByBusinessExcelExportArgs = {
  viewMode: "monthly" | "ytd" | "formal";
  reportDate: string;
  year: number;
  periodStart?: string | null;
  periodEnd?: string | null;
  periodLabel?: string | null;
  balanceQualityIssues?: PnlByBusinessBalanceQualityIssue[];
  ytdQuality?: ExportBalanceQuality;
  bondBucketQuality?: ExportBalanceQuality;
  bondBucketMonthlyQuality?: ExportBalanceQuality;
  negativeFtpQuality?: ExportBalanceQuality;
  analysisQuality?: ExportBalanceQuality;
  /** YTD 主表（年累计视图） */
  ytdRows: PnlByBusinessYtdItem[];
  ytdSummary?: PnlByBusinessYtdSummary;
  unallocatedBreakdown?: PnlByBusinessYtdUnallocatedBreakdownRow[];
  unallocatedItems?: PnlByBusinessYtdUnallocatedItem[];
  adbAvgByBusinessType: Map<string, number>;
  /** formal 主表（primary 对账视图） */
  formalRows: PnlByBusinessRow[];
  /** formal 全表合计：与页面 tfoot 同源的后端 summary，导出不再逐行累加。 */
  formalSummary?: PnlByBusinessSummary;
  months: PnlByBusinessMonthlyBucket[];
  adjustments: PnlByBusinessManualAdjustmentPayload[];
  adjustmentEvents: PnlByBusinessManualAdjustmentPayload[];
  bondBucketRows: PnlByBusinessAnalysisRow[];
  bondBucketMonthlyRows: PnlByBusinessAnalysisRow[];
  negativeFtpRows: PnlByBusinessAnalysisRow[];
  analysisDimension?: PnlByBusinessAnalysisDimension;
  analysisRows: PnlByBusinessAnalysisRow[];
  selectedBusinessLabel?: string | null;
};

type ExportBalanceQuality = Pick<PnlByBusinessAnalysisPayload,
  "coverage_days" | "expected_days" | "sample_filled" | "balance_quality_issues">;

function balanceQualityNote(quality?: ExportBalanceQuality): string {
  const observed = quality?.coverage_days;
  const expected = quality?.expected_days;
  const coverage = `余额覆盖 ${observed ?? "未返回"}/${expected ?? "未返回"} 天`;
  const incomplete = typeof observed === "number" && typeof expected === "number" && observed < expected;
  const sourceIssues = quality?.balance_quality_issues ?? [];
  const pending = incomplete || sourceIssues.length > 0;
  return [
    coverage,
    incomplete ? "观测日均；年化收益率、FTP 成本及 FTP 后结果待核对，暂不作为汇报结论" : "",
    sourceIssues.length > 0 ? `余额来源待核实：${sourceIssues.map((issue) => `${issue.report_date} ${issue.reason}`).join("；")}；日均、收益率及 FTP 为暂列值` : "",
    quality?.sample_filled ? "样本填充" : "",
    !pending && (observed === undefined || expected === undefined) ? "覆盖状态未返回，完整性待核对" : "",
  ].filter(Boolean).join("；");
}

/** 将质量状态附在数值同行，单独复制明细也不会丢失覆盖限制。 */
function appendBalanceQuality(
  sheet: PnlByBusinessExportSheet,
  headerIndex: number,
  noteForRow: (row: SheetAoA[number], dataIndex: number) => string,
): void {
  sheet.data = sheet.data.map((row, index) => index < headerIndex ? row
    : [...row, index === headerIndex ? "余额及收益率质量" : noteForRow(row, index - headerIndex - 1)]);
}

const UNALLOCATED_REASON_LABELS = {
  no_business_rule_match: "未命中业务分类规则",
  detail_only_business_rule_match: "仅命中其中项，未命中父级分类",
} as const;

function appendSheet(sheets: PnlByBusinessExportSheet[], name: string, aoa: SheetAoA) {
  if (aoa.length === 0) {
    return;
  }
  sheets.push({ sheet: safeSheetName(name), data: aoa });
}

function buildYtdMainSheet(
  rows: PnlByBusinessYtdItem[],
  summary: PnlByBusinessYtdSummary | undefined,
  _adbMap: Map<string, number>,
  _ytdCalendarDays: number | null,
): SheetAoA {
  const header: SheetAoA[0] = [
    "业务种类",
    "日均(亿元)",
    "利息收入(万元)",
    "公允价值变动(万元)",
    "资本利得(万元)",
    "手工调整(万元)",
    "合计损益(万元)",
    "年化收益率(%)",
    "FTP后收益(万元)",
    "FTP后收益率(%)",
    "占比(0-1)",
    "资产数",
  ];
  const data: SheetAoA = [header];
  const parentRows = rows.filter(isParentZqtzBusinessRow);
  for (const row of parentRows) {
    data.push([
      row.business_type,
      yiFromYuan(row.avg_balance),
      wanFromYuan(row.interest_income),
      wanFromYuan(row.fair_value_change),
      wanFromYuan(row.capital_gain),
      wanFromYuan(row.manual_adjustment),
      wanFromYuan(row.total_pnl),
      num(row.annualized_yield_pct),
      wanFromYuan(row.ftp_net_pnl),
      num(row.ftp_net_annualized_yield_pct),
      num(row.proportion),
      row.assets_count,
    ]);
  }
  if (summary) {
    data.push([
      "父级汇总",
      yiFromYuan(summary.avg_balance),
      wanFromYuan(summary.interest_income),
      wanFromYuan(summary.fair_value_change),
      wanFromYuan(summary.capital_gain),
      wanFromYuan(summary.manual_adjustment),
      wanFromYuan(summary.total_pnl),
      num(summary.annualized_yield_pct),
      wanFromYuan(summary.ftp_net_pnl),
      num(summary.ftp_net_annualized_yield_pct),
      num(summary.proportion),
      summary.assets_count,
    ]);
  }
  return data;
}

function buildYtdUnallocatedBreakdownSheet(rows: PnlByBusinessYtdUnallocatedBreakdownRow[]): SheetAoA {
  const data: SheetAoA = [[
    "未命中原因",
    "来源",
    "原始类型",
    "会计分类",
    "组合",
    "成本中心",
    "条数",
    "净额(万元)",
    "绝对金额(万元)",
    "示例证券",
  ]];
  for (const row of rows) {
    data.push([
      UNALLOCATED_REASON_LABELS[row.reason_code],
      row.source_kind,
      row.invest_type_std,
      row.accounting_basis,
      row.portfolio_name,
      row.cost_center,
      row.pnl_row_count,
      wanFromYuan(row.total_pnl),
      wanFromYuan(row.abs_pnl),
      row.sample_instrument_codes.join("、"),
    ]);
  }
  return data;
}

function buildYtdUnallocatedItemsSheet(rows: PnlByBusinessYtdUnallocatedItem[]): SheetAoA {
  const data: SheetAoA = [[
    "报表日",
    "来源",
    "原始类型",
    "会计分类",
    "组合",
    "成本中心",
    "证券代码",
    "币种",
    "利息收入(万元)",
    "公允价值变动(万元)",
    "资本利得(万元)",
    "手工调整(万元)",
    "合计损益(万元)",
    "绝对金额(万元)",
    "未命中原因",
  ]];
  for (const row of rows) {
    data.push([
      row.report_date,
      row.source_kind,
      row.invest_type_std,
      row.accounting_basis,
      row.portfolio_name,
      row.cost_center,
      row.instrument_code,
      row.currency_basis,
      wanFromYuan(row.interest_income_514),
      wanFromYuan(row.fair_value_change_516),
      wanFromYuan(row.capital_gain_517),
      wanFromYuan(row.manual_adjustment),
      wanFromYuan(row.total_pnl),
      wanFromYuan(row.abs_pnl),
      UNALLOCATED_REASON_LABELS[row.reason_code],
    ]);
  }
  return data;
}

function buildMonthlyUnallocatedBreakdownSheet(months: PnlByBusinessMonthlyBucket[]): SheetAoA {
  const data: SheetAoA = [[
    "月份",
    "未命中原因",
    "来源",
    "原始类型",
    "会计分类",
    "组合",
    "成本中心",
    "条数",
    "净额(万元)",
    "绝对金额(万元)",
    "示例证券",
  ]];
  for (const month of months) {
    for (const row of month.unallocated_breakdown ?? []) {
      data.push([
        month.month_key,
        UNALLOCATED_REASON_LABELS[row.reason_code],
        row.source_kind,
        row.invest_type_std,
        row.accounting_basis,
        row.portfolio_name,
        row.cost_center,
        row.pnl_row_count,
        wanFromYuan(row.total_pnl),
        wanFromYuan(row.abs_pnl),
        row.sample_instrument_codes.join("、"),
      ]);
    }
  }
  return data;
}

function buildMonthlyUnallocatedItemsSheet(months: PnlByBusinessMonthlyBucket[]): SheetAoA {
  const data: SheetAoA = [[
    "月份",
    "报表日",
    "来源",
    "原始类型",
    "会计分类",
    "组合",
    "成本中心",
    "证券代码",
    "币种",
    "利息收入(万元)",
    "公允价值变动(万元)",
    "资本利得(万元)",
    "手工调整(万元)",
    "合计损益(万元)",
    "绝对金额(万元)",
    "未命中原因",
  ]];
  for (const month of months) {
    for (const row of month.unallocated_items ?? []) {
      data.push([
        month.month_key,
        row.report_date,
        row.source_kind,
        row.invest_type_std,
        row.accounting_basis,
        row.portfolio_name,
        row.cost_center,
        row.instrument_code,
        row.currency_basis,
        wanFromYuan(row.interest_income_514),
        wanFromYuan(row.fair_value_change_516),
        wanFromYuan(row.capital_gain_517),
        wanFromYuan(row.manual_adjustment),
        wanFromYuan(row.total_pnl),
        wanFromYuan(row.abs_pnl),
        UNALLOCATED_REASON_LABELS[row.reason_code],
      ]);
    }
  }
  return data;
}

/** 警示行 + 空行 + 表头，无明细数据行时的基线长度 */
const YTD_DETAIL_SHEET_EMPTY_LENGTH = 3;

function buildYtdDetailSheet(
  rows: PnlByBusinessYtdItem[],
  _adbMap: Map<string, number>,
  _ytdCalendarDays: number | null,
): SheetAoA {
  const header: SheetAoA[0] = [
    "业务种类",
    "日均(亿元)",
    "利息收入(万元)",
    "公允价值变动(万元)",
    "资本利得(万元)",
    "手工调整(万元)",
    "合计损益(万元)",
    "年化收益率(%)",
    "FTP后收益(万元)",
    "FTP后收益率(%)",
    "占比(0-1)",
    "资产数",
    "说明",
  ];
  const data: SheetAoA = [["⚠ 本表金额与父级表重叠展示，请勿相加或用于加总统计"], [], header];
  for (const row of rows.filter(isDetailZqtzBusinessRow)) {
    data.push([
      row.business_type,
      yiFromYuan(row.avg_balance),
      wanFromYuan(row.interest_income),
      wanFromYuan(row.fair_value_change),
      wanFromYuan(row.capital_gain),
      wanFromYuan(row.manual_adjustment),
      wanFromYuan(row.total_pnl),
      num(row.annualized_yield_pct),
      wanFromYuan(row.ftp_net_pnl),
      num(row.ftp_net_annualized_yield_pct),
      num(row.proportion),
      row.assets_count,
      "父级拆解项，不参与父级汇总",
    ]);
  }
  return data;
}

function buildFormalSheet(rows: PnlByBusinessRow[], summary: PnlByBusinessSummary | undefined): SheetAoA {
  const header: SheetAoA[0] = [
    "业务种类(primary)",
    "币种",
    "规模(亿元)",
    "利息收入(万元)",
    "公允价值变动(万元)",
    "资本利得(万元)",
    "手工调整(万元)",
    "合计损益(万元)",
    "表内收益率(%)",
    "损益行数",
  ];
  const data: SheetAoA = [header];
  for (const row of rows) {
    data.push([
      row.business_type_primary,
      row.currency_basis,
      yiFromYuan(row.scale_amount),
      wanFromYuan(row.interest_income_514),
      wanFromYuan(row.fair_value_change_516),
      wanFromYuan(row.capital_gain_517),
      wanFromYuan(row.manual_adjustment),
      wanFromYuan(row.total_pnl),
      num(row.yield_pct),
      row.pnl_row_count,
    ]);
  }
  if (rows.length === 0) {
    return data;
  }
  if (!summary) {
    data.push(["全表合计（不可用：后端未返回汇总）", null, null, null, null, null, null, null, null, null]);
    return data;
  }
  /** 全表合计直读后端 summary（与明细行同一批正式数值），导出不再逐行累加。 */
  data.push([
    "全表合计",
    null,
    yiFromYuan(summary.total_scale_amount),
    wanFromYuan(summary.interest_income_514),
    wanFromYuan(summary.fair_value_change_516),
    wanFromYuan(summary.capital_gain_517),
    wanFromYuan(summary.manual_adjustment),
    wanFromYuan(summary.total_pnl),
    null,
    summary.pnl_row_count,
  ]);
  return data;
}

/** 警示行 + 空行 + 表头，无明细数据行时的基线长度（月报/月度"其中项明细"sheet复用） */
const MONTHLY_DETAIL_SHEET_EMPTY_LENGTH = 3;

function withDetailSheetOverlapWarning(sheet: SheetAoA): SheetAoA {
  return [["⚠ 本表金额与父级表重叠展示，请勿相加或用于加总统计"], [], ...sheet];
}

function buildMonthlyFlatSheet(
  months: PnlByBusinessMonthlyBucket[],
  rowFilter: (row: PnlByBusinessMonthlyItem) => boolean = isParentZqtzBusinessRow,
): SheetAoA {
  const header: SheetAoA[0] = [
    "月份",
    "区间起",
    "区间止",
    "自然日数",
    "业务种类",
    "日均(亿元)",
    "期末余额(亿元)",
    "利息收入(万元)",
    "公允价值变动(万元)",
    "资本利得(万元)",
    "手工调整(万元)",
    "合计损益(万元)",
    "年化收益率(%)",
    "FTP后收益(万元)",
    "FTP后收益率(%)",
    "占比(0-1)",
    "资产数",
  ];
  const data: SheetAoA = [header];
  for (const m of months) {
    for (const row of m.items.filter(rowFilter)) {
      data.push([
        m.month_key,
        m.period_start_date,
        m.period_end_date,
        m.calendar_days,
        row.business_type,
        yiFromYuan(row.avg_balance),
        yiFromYuan(row.current_balance),
        wanFromYuan(row.interest_income),
        wanFromYuan(row.fair_value_change),
        wanFromYuan(row.capital_gain),
        wanFromYuan(row.manual_adjustment),
        wanFromYuan(row.total_pnl),
        num(row.annualized_yield_pct),
        wanFromYuan(row.ftp_net_pnl),
        num(row.ftp_net_annualized_yield_pct),
        num(row.proportion),
        row.asset_count,
      ]);
    }
    if (rowFilter === isParentZqtzBusinessRow) {
      const s = m.summary;
      data.push([
        m.month_key,
        m.period_start_date,
        m.period_end_date,
        m.calendar_days,
        "父级汇总",
        yiFromYuan(s.avg_balance),
        yiFromYuan(s.current_balance),
        wanFromYuan(s.interest_income),
        wanFromYuan(s.fair_value_change),
        wanFromYuan(s.capital_gain),
        wanFromYuan(s.manual_adjustment),
        wanFromYuan(s.total_pnl),
        num(s.annualized_yield_pct),
        wanFromYuan(s.ftp_net_pnl),
        num(s.ftp_net_annualized_yield_pct),
        null,
        s.asset_count,
      ]);
    }
  }
  return data;
}

function buildAdjustmentsSheet(
  title: string,
  rows: PnlByBusinessManualAdjustmentPayload[],
  mode: "current" | "events",
): SheetAoA {
  if (mode === "current") {
    const h: SheetAoA[0] = ["业务种类", "金额(万元)", "状态", "原因", "最近事件"];
    const data: SheetAoA = [[title], [], h];
    for (const r of rows) {
      data.push([r.business_type || r.row_key, wanFromYuan(r.manual_adjustment), r.approval_status, r.reason ?? "", r.event_type]);
    }
    return data;
  }
  const h: SheetAoA[0] = ["时间", "事件", "业务种类", "金额(万元)", "状态", "原因"];
  const data: SheetAoA = [[title], [], h];
  for (const r of rows) {
    data.push([
      r.created_at,
      r.event_type,
      r.business_type || r.row_key,
      wanFromYuan(r.manual_adjustment),
      r.approval_status,
      r.reason ?? "",
    ]);
  }
  return data;
}

function buildAnalysisSheet(title: string, dimensionLabel: string, rows: PnlByBusinessAnalysisRow[]): SheetAoA {
  const h: SheetAoA[0] = [
    dimensionLabel,
    "日均(亿元)",
    "期末余额(亿元)",
    "利息收入(万元)",
    "公允价值变动(万元)",
    "资本利得(万元)",
    "手工调整(万元)",
    "合计损益(万元)",
    "年化收益率(%)",
    "FTP成本(万元)",
    "FTP后收益(万元)",
    "FTP后收益率(%)",
    "资产数",
  ];
  const data: SheetAoA = [[title], [], h];
  for (const row of rows) {
    data.push([
      row.dimension_label,
      yiFromYuan(row.avg_balance),
      yiFromYuan(row.current_balance),
      wanFromYuan(row.interest_income),
      wanFromYuan(row.fair_value_change),
      wanFromYuan(row.capital_gain),
      wanFromYuan(row.manual_adjustment),
      wanFromYuan(row.total_pnl),
      num(row.annualized_yield_pct),
      wanFromYuan(row.ftp_cost),
      wanFromYuan(row.ftp_net_pnl),
      num(row.ftp_net_annualized_yield_pct),
      row.asset_count,
    ]);
  }
  return data;
}

function buildMetaRows(args: PnlByBusinessExcelExportArgs, ytdCalendarDays: number | null): SheetAoA {
  const lines: SheetAoA = [
    ["业务种类损益 — 导出说明"],
    ["报表截止日", args.reportDate],
    [
      "视图",
      args.viewMode === "monthly"
        ? "月报(ZQTZ)"
        : args.viewMode === "ytd"
          ? "月报累计(YTD)"
          : "primary 对账",
    ],
  ];
  if (args.viewMode === "monthly") {
    lines.push(["年度", args.year]);
    lines.push(["说明", "本导出为月报 ZQTZ 管理披露口径；同一月份可与年累计视图按父级行核对。"]);
  } else if (args.viewMode === "ytd") {
    lines.push(["年度", args.year]);
    if (args.periodLabel) {
      lines.push(["区间标签", args.periodLabel]);
    }
    if (args.periodStart && args.periodEnd) {
      lines.push(["区间起止", `${args.periodStart} ~ ${args.periodEnd}`]);
    }
    if (ytdCalendarDays !== null) {
      lines.push(["区间自然日数(含首尾)", ytdCalendarDays]);
    }
    lines.push([
      "说明",
      "数值列与页面一致：金额接口为元，表中为万元；收益率与页面同为百分点。未加载成功的分析区块不会出现在后续工作表。",
    ]);
  } else {
    lines.push(["说明", "本导出为 primary 对账明细；与月报或 YTD 的 ZQTZ 管理披露分类不可混加。"]);
  }
  if (args.viewMode !== "formal") {
    lines.push(["日均余额口径", "与期末一致：H 用摊余成本，A/T 用公允价值，凭证式国债用面值兜底，均加应计利息。"]);
    for (const issue of args.balanceQualityIssues ?? []) {
      lines.push(["余额来源待核实", issue.report_date, issue.reason,
        "受影响期间的日均、年化收益率和 FTP 为暂列值，取得正确源表后重算。"]);
    }
  }
  lines.push([]);
  return lines;
}

export function buildPnlByBusinessSheets(args: PnlByBusinessExcelExportArgs): PnlByBusinessExportSheet[] {
  const wb: PnlByBusinessExportSheet[] = [];
  const ytdCalendarDays =
    args.periodStart && args.periodEnd ? inclusiveCalendarDays(args.periodStart, args.periodEnd) : null;

  const meta = buildMetaRows(args, ytdCalendarDays);
  appendSheet(wb, "导出说明", meta);

  if (args.viewMode === "monthly" && args.months.length > 0) {
    appendSheet(wb, "月报业务种类", buildMonthlyFlatSheet(args.months));
    if (args.months.some((month) => (month.unallocated_breakdown?.length ?? 0) > 0)) {
      appendSheet(wb, "月报未分类汇总", buildMonthlyUnallocatedBreakdownSheet(args.months));
    }
    if (args.months.some((month) => (month.unallocated_items?.length ?? 0) > 0)) {
      appendSheet(wb, "月报未分类明细", buildMonthlyUnallocatedItemsSheet(args.months));
    }
    const detailSheet = withDetailSheetOverlapWarning(buildMonthlyFlatSheet(args.months, isDetailZqtzBusinessRow));
    if (detailSheet.length > MONTHLY_DETAIL_SHEET_EMPTY_LENGTH) {
      appendSheet(wb, "月报其中项明细", detailSheet);
    }
  }
  if (args.viewMode === "ytd" && args.ytdRows.length > 0) {
    appendSheet(
      wb,
      "YTD年累计明细",
      buildYtdMainSheet(args.ytdRows, args.ytdSummary, args.adbAvgByBusinessType, ytdCalendarDays),
    );
    if ((args.unallocatedBreakdown?.length ?? 0) > 0) {
      appendSheet(wb, "YTD未分类汇总", buildYtdUnallocatedBreakdownSheet(args.unallocatedBreakdown ?? []));
    }
    if ((args.unallocatedItems?.length ?? 0) > 0) {
      appendSheet(wb, "YTD未分类明细", buildYtdUnallocatedItemsSheet(args.unallocatedItems ?? []));
    }
    const detailSheet = buildYtdDetailSheet(args.ytdRows, args.adbAvgByBusinessType, ytdCalendarDays);
    if (detailSheet.length > YTD_DETAIL_SHEET_EMPTY_LENGTH) {
      appendSheet(wb, "YTD其中项明细", detailSheet);
    }
  }
  if (args.viewMode === "formal" && args.formalRows.length > 0) {
    appendSheet(wb, "Primary对账明细", buildFormalSheet(args.formalRows, args.formalSummary));
  }
  if (args.viewMode === "ytd" && args.months.length > 0) {
    appendSheet(wb, "月度业务种类", buildMonthlyFlatSheet(args.months));
    if (args.months.some((month) => (month.unallocated_breakdown?.length ?? 0) > 0)) {
      appendSheet(wb, "月度未分类汇总", buildMonthlyUnallocatedBreakdownSheet(args.months));
    }
    if (args.months.some((month) => (month.unallocated_items?.length ?? 0) > 0)) {
      appendSheet(wb, "月度未分类明细", buildMonthlyUnallocatedItemsSheet(args.months));
    }
    const detailSheet = withDetailSheetOverlapWarning(buildMonthlyFlatSheet(args.months, isDetailZqtzBusinessRow));
    if (detailSheet.length > MONTHLY_DETAIL_SHEET_EMPTY_LENGTH) {
      appendSheet(wb, "月度其中项明细", detailSheet);
    }
  }
  if (args.viewMode === "ytd" && args.adjustments.length > 0) {
    appendSheet(wb, "手工调整当前", buildAdjustmentsSheet(`报表日 ${args.reportDate}`, args.adjustments, "current"));
  }
  if (args.viewMode === "ytd" && args.adjustmentEvents.length > 0) {
    appendSheet(wb, "手工调整事件", buildAdjustmentsSheet(`报表日 ${args.reportDate}`, args.adjustmentEvents, "events"));
  }
  if (args.viewMode === "ytd" && args.bondBucketRows.length > 0) {
    appendSheet(
      wb,
      "投资资产四类",
      buildAnalysisSheet("投资资产四类统计", ANALYSIS_DIM_LABELS.bond_bucket, args.bondBucketRows),
    );
  }
  if (args.viewMode === "ytd" && args.bondBucketMonthlyRows.length > 0) {
    appendSheet(
      wb,
      "投资资产四类月度",
      buildAnalysisSheet("投资资产四类月度趋势", ANALYSIS_DIM_LABELS.bond_bucket_monthly, args.bondBucketMonthlyRows),
    );
  }
  if (args.viewMode === "ytd" && args.negativeFtpRows.length > 0) {
    const { topRows, calculatedCount, negativeCount, unavailableRows } = buildNegativeFtpList(args.negativeFtpRows);
    const coverage = `已计算 FTP ${calculatedCount} 笔，负收益 ${negativeCount} 笔，未计算 ${unavailableRows.length} 笔`;
    if (topRows.length > 0) {
      appendSheet(
        wb,
        "负FTP资产清单",
        buildAnalysisSheet(`负FTP后收益拖累前10项；${coverage}`, ANALYSIS_DIM_LABELS.instrument, topRows),
      );
    }
    if (unavailableRows.length > 0) {
      appendSheet(wb, "FTP未计算资产", buildAnalysisSheet(
        `FTP 未计算，保留扣 FTP 前损益；${coverage}`, ANALYSIS_DIM_LABELS.instrument, unavailableRows,
      ));
    }
  }
  if (args.viewMode === "ytd" && args.analysisRows.length > 0 && args.analysisDimension) {
    const dimLabel = ANALYSIS_DIM_LABELS[args.analysisDimension];
    const biz = args.selectedBusinessLabel ?? "";
    appendSheet(
      wb,
      "多维下钻",
      buildAnalysisSheet(`选中业务: ${biz} · 维度: ${dimLabel}`, dimLabel, args.analysisRows),
    );
  }

  if (args.viewMode !== "formal") {
    const monthlySheets = new Set(["月报业务种类", "月度业务种类", "月报其中项明细", "月度其中项明细"]);
    const qualityBySheet = new Map<string, ExportBalanceQuality | undefined>([
      ["YTD年累计明细", args.ytdQuality], ["YTD其中项明细", args.ytdQuality],
      ["投资资产四类", args.bondBucketQuality], ["投资资产四类月度", args.bondBucketMonthlyQuality],
      ["负FTP资产清单", args.negativeFtpQuality], ["FTP未计算资产", args.negativeFtpQuality],
      ["多维下钻", args.analysisQuality],
    ]);
    for (const sheet of wb) {
      const name = sheet.sheet ?? "";
      if (monthlySheets.has(name)) {
        appendBalanceQuality(sheet, name.includes("其中项") ? 2 : 0, (row) => {
          const month = args.months.find((item) => item.month_key === row[0]);
          return balanceQualityNote(month && { ...month, expected_days: month.expected_days ?? month.calendar_days });
        });
      } else if (qualityBySheet.has(name)) {
        const note = balanceQualityNote(qualityBySheet.get(name));
        const monthlyAnalysisRows = name === "投资资产四类月度" ? args.bondBucketMonthlyRows
          : name === "多维下钻" && (args.analysisDimension === "monthly" || args.analysisDimension === "bond_bucket_monthly")
            ? args.analysisRows : undefined;
        appendBalanceQuality(sheet, name === "YTD年累计明细" ? 0 : 2, (_row, dataIndex) => {
          if (!monthlyAnalysisRows) return note;
          const key = monthlyAnalysisRows[dataIndex]?.dimension_key ?? "";
          const monthKey = /^\d{4}-\d{2}(?=-|::|$)/.exec(key)?.[0];
          const month = args.months.find((item) => item.month_key === monthKey);
          return month ? balanceQualityNote({ ...month, expected_days: month.expected_days ?? month.calendar_days })
            : `${monthKey ?? "月份未识别"} 本月覆盖未返回，日均、收益率及 FTP 完整性待核对`;
        });
        meta.push([`${name}余额及收益率质量`, note]);
      }
    }
    for (const month of args.months) {
      meta.push([`${month.month_key}余额及收益率质量`, balanceQualityNote({
        ...month, expected_days: month.expected_days ?? month.calendar_days,
      })]);
    }
  }
  return wb;
}

export async function downloadPnlByBusinessExcel(args: PnlByBusinessExcelExportArgs): Promise<void> {
  const sheets = buildPnlByBusinessSheets(args);
  const filenameSuffix =
    args.viewMode === "monthly" ? "monthly" : args.viewMode === "ytd" ? "YTD" : "primary";
  const filename = `业务种类损益_${args.reportDate}_${filenameSuffix}.xlsx`;
  await writeExcelFile(sheets).toFile(filename);
}
