import * as XLSX from "xlsx";

import type {
  PnlByBusinessMonthlyBucket,
  PnlByBusinessRow,
  PnlByBusinessYtdItem,
  PnlByBusinessManualAdjustmentPayload,
  PnlByBusinessAnalysisRow,
  PnlByBusinessAnalysisDimension,
} from "../../api/contracts";
import { inclusiveCalendarDays } from "./pnlByBusinessAnnualizedYield";
import { resolveAdbAvgYuan } from "./zqtzAdbAvgRollup";

type SheetAoA = (string | number | null | undefined)[][];

const YUAN_PER_WAN = 10_000;
const YUAN_PER_YI = 100_000_000;
const FTP_RATE_RATIO = 0.016;

function num(raw: string | number | null | undefined): number | null {
  if (raw === null || raw === undefined || raw === "") {
    return null;
  }
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

/** 年化收益率百分点（损益/日均 × 365/天数 × 100） */
function annualizedYieldPctPoints(
  totalPnlYuan: string | number | null | undefined,
  avgBalanceYuan: number | undefined,
  calendarDays: number | null,
): number | null {
  const pnl = num(totalPnlYuan);
  if (pnl === null || avgBalanceYuan === undefined || avgBalanceYuan <= 0 || !calendarDays || calendarDays <= 0) {
    return null;
  }
  return (pnl / avgBalanceYuan) * (365 / calendarDays) * 100;
}

function ftpNetForYtdRow(
  totalPnlYuan: string | number | null | undefined,
  avgBalanceYuan: number | undefined,
  calendarDays: number | null,
): { ftpCost: number | null; ftpNet: number | null; ftpNetYieldPct: number | null } {
  const pnl = num(totalPnlYuan);
  const ann = annualizedYieldPctPoints(totalPnlYuan, avgBalanceYuan, calendarDays);
  if (
    pnl === null ||
    ann === null ||
    avgBalanceYuan === undefined ||
    avgBalanceYuan <= 0 ||
    !calendarDays ||
    calendarDays <= 0
  ) {
    return { ftpCost: null, ftpNet: null, ftpNetYieldPct: null };
  }
  const ftpCost = avgBalanceYuan * FTP_RATE_RATIO * (calendarDays / 365);
  return {
    ftpCost,
    ftpNet: pnl - ftpCost,
    ftpNetYieldPct: ann - 1.6,
  };
}

/** 排除「其中」细分行，与页面父级汇总一致 */
function isParentZqtzBusinessRow(row: PnlByBusinessYtdItem): boolean {
  if (row.business_type.startsWith("其中：")) {
    return false;
  }
  const note = String(row.source_note ?? "");
  return !note.includes("其中项");
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
  cost_center: "成本中心",
  instrument: "资产明细",
  bond_bucket: "债券四类",
  bond_bucket_monthly: "四类月度",
};

export type PnlByBusinessExcelExportArgs = {
  viewMode: "ytd" | "formal";
  reportDate: string;
  year: number;
  periodStart?: string | null;
  periodEnd?: string | null;
  periodLabel?: string | null;
  /** YTD 主表（年累计视图） */
  ytdRows: PnlByBusinessYtdItem[];
  adbAvgByBusinessType: Map<string, number>;
  /** formal 主表（单日视图） */
  formalRows: PnlByBusinessRow[];
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

function appendSheet(wb: XLSX.WorkBook, name: string, aoa: SheetAoA) {
  if (aoa.length === 0) {
    return;
  }
  const ws = XLSX.utils.aoa_to_sheet(aoa);
  XLSX.utils.book_append_sheet(wb, ws, safeSheetName(name));
}

function buildYtdMainSheet(
  rows: PnlByBusinessYtdItem[],
  adbMap: Map<string, number>,
  ytdCalendarDays: number | null,
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
  for (const row of rows) {
    const adb = resolveAdbAvgYuan(row.business_type, adbMap);
    const ftp = ftpNetForYtdRow(row.total_pnl, adb, ytdCalendarDays);
    data.push([
      row.business_type,
      adb !== undefined && adb > 0 ? adb / YUAN_PER_YI : null,
      wanFromYuan(row.interest_income),
      wanFromYuan(row.fair_value_change),
      wanFromYuan(row.capital_gain),
      wanFromYuan(row.manual_adjustment),
      wanFromYuan(row.total_pnl),
      annualizedYieldPctPoints(row.total_pnl, adb, ytdCalendarDays),
      wanFromYuan(ftp.ftpNet),
      ftp.ftpNetYieldPct,
      num(row.proportion),
      row.assets_count,
    ]);
  }
  const parentRows = rows.filter(isParentZqtzBusinessRow);
  if (parentRows.length > 0) {
    let interest = 0;
    let fairValue = 0;
    let capital = 0;
    let manual = 0;
    let totalPnl = 0;
    let assets = 0;
    let adbSum = 0;
    for (const row of parentRows) {
      interest += num(row.interest_income) ?? 0;
      fairValue += num(row.fair_value_change) ?? 0;
      capital += num(row.capital_gain) ?? 0;
      manual += num(row.manual_adjustment) ?? 0;
      totalPnl += num(row.total_pnl) ?? 0;
      assets += row.assets_count;
      const adb = resolveAdbAvgYuan(row.business_type, adbMap);
      if (adb !== undefined && adb > 0) {
        adbSum += adb;
      }
    }
    const ftp = ftpNetForYtdRow(totalPnl, adbSum > 0 ? adbSum : undefined, ytdCalendarDays);
    data.push([
      "父级汇总",
      adbSum > 0 ? adbSum / YUAN_PER_YI : null,
      interest / YUAN_PER_WAN,
      fairValue / YUAN_PER_WAN,
      capital / YUAN_PER_WAN,
      manual / YUAN_PER_WAN,
      totalPnl / YUAN_PER_WAN,
      null,
      wanFromYuan(ftp.ftpNet),
      ftp.ftpNetYieldPct,
      null,
      assets,
    ]);
  }
  return data;
}

function buildFormalSheet(rows: PnlByBusinessRow[]): SheetAoA {
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
  let interest = 0;
  let fairValue = 0;
  let capital = 0;
  let manual = 0;
  let totalPnl = 0;
  let scale = 0;
  let pnlRows = 0;
  for (const row of rows) {
    interest += num(row.interest_income_514) ?? 0;
    fairValue += num(row.fair_value_change_516) ?? 0;
    capital += num(row.capital_gain_517) ?? 0;
    manual += num(row.manual_adjustment) ?? 0;
    totalPnl += num(row.total_pnl) ?? 0;
    scale += num(row.scale_amount) ?? 0;
    pnlRows += row.pnl_row_count;
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
  if (rows.length > 0) {
    data.push([
      "全表合计",
      null,
      scale / YUAN_PER_YI,
      interest / YUAN_PER_WAN,
      fairValue / YUAN_PER_WAN,
      capital / YUAN_PER_WAN,
      manual / YUAN_PER_WAN,
      totalPnl / YUAN_PER_WAN,
      null,
      pnlRows,
    ]);
  }
  return data;
}

function buildMonthlyFlatSheet(months: PnlByBusinessMonthlyBucket[]): SheetAoA {
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
    for (const row of m.items) {
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
    ["视图", args.viewMode === "ytd" ? "年累计(YTD)" : "报表日 formal"],
  ];
  if (args.viewMode === "ytd") {
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
    lines.push(["说明", "本导出为 formal 单日明细；与 YTD 视图不可混加。"]);
  }
  lines.push([]);
  return lines;
}

export function buildPnlByBusinessWorkbook(args: PnlByBusinessExcelExportArgs): XLSX.WorkBook {
  const wb = XLSX.utils.book_new();
  const ytdCalendarDays =
    args.periodStart && args.periodEnd ? inclusiveCalendarDays(args.periodStart, args.periodEnd) : null;

  const meta = buildMetaRows(args, ytdCalendarDays);
  appendSheet(wb, "导出说明", meta);

  if (args.viewMode === "ytd" && args.ytdRows.length > 0) {
    appendSheet(wb, "YTD年累计明细", buildYtdMainSheet(args.ytdRows, args.adbAvgByBusinessType, ytdCalendarDays));
  }
  if (args.viewMode === "formal" && args.formalRows.length > 0) {
    appendSheet(wb, "Formal单日明细", buildFormalSheet(args.formalRows));
  }
  if (args.viewMode === "ytd" && args.months.length > 0) {
    appendSheet(wb, "月度业务种类", buildMonthlyFlatSheet(args.months));
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
      "债券四类",
      buildAnalysisSheet("债券四类统计", ANALYSIS_DIM_LABELS.bond_bucket, args.bondBucketRows),
    );
  }
  if (args.viewMode === "ytd" && args.bondBucketMonthlyRows.length > 0) {
    appendSheet(
      wb,
      "四类债券月度",
      buildAnalysisSheet("四类债券月度趋势", ANALYSIS_DIM_LABELS.bond_bucket_monthly, args.bondBucketMonthlyRows),
    );
  }
  if (args.viewMode === "ytd" && args.negativeFtpRows.length > 0) {
    const neg = args.negativeFtpRows
      .filter((row) => (num(row.ftp_net_pnl) ?? 0) < 0)
      .sort((a, b) => (num(a.ftp_net_pnl) ?? 0) - (num(b.ftp_net_pnl) ?? 0))
      .slice(0, 10);
    if (neg.length > 0) {
      appendSheet(
        wb,
        "负FTP资产清单",
        buildAnalysisSheet("负FTP后收益清单（与页面一致取前10笔）", ANALYSIS_DIM_LABELS.instrument, neg),
      );
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

  return wb;
}

export function downloadPnlByBusinessExcel(args: PnlByBusinessExcelExportArgs): void {
  const wb = buildPnlByBusinessWorkbook(args);
  const filename = `业务种类损益_${args.reportDate}_${args.viewMode === "ytd" ? "YTD" : "formal"}.xlsx`;
  const buf = XLSX.write(wb, { bookType: "xlsx", type: "array" });
  const blob = new Blob([buf], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}
