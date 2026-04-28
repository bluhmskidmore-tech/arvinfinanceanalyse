import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type {
  BalanceBasisMovementDecomposition,
  BalanceDifferenceAttributionWaterfall,
  BalanceBusinessMovementTrendMonth,
  BalanceMovementRow,
  BalanceMovementDrilldownStatus,
  BalanceMovementTrendMonth,
  BalanceStructureMigrationAnalysis,
  BalanceZqtzConcentrationAnalysis,
  BalanceZqtzConcentrationDimensionKey,
  BalanceZqtzMaturityStructure,
} from "../../../api/contracts";
import AccountingBasisStackedShareChart, {
  type AccountingBasisStackedSharePoint,
} from "../../../components/charts/AccountingBasisStackedShareChart";
import { FilterBar } from "../../../components/FilterBar";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { formatBalanceAmountToYiFromYuan } from "../../balance-analysis/pages/balanceAnalysisPageModel";
import { designTokens } from "../../../theme/designSystem";
import { displayTokens } from "../../../theme/displayTokens";
import "./BalanceMovementAnalysisPage.css";

const pageHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: 16,
  padding: 20,
  borderRadius: 18,
  border: `1px solid ${designTokens.color.neutral[200]}`,
  background: designTokens.color.neutral[50],
  marginBottom: 18,
} as const;

const chipTypography = {
  display: "inline-flex",
  alignItems: "center",
  padding: "8px 12px",
  borderRadius: 999,
  fontSize: 12,
  fontWeight: 600,
  letterSpacing: "0.04em",
  textTransform: "uppercase" as const,
} as const;

const cardGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: 12,
  marginBottom: 18,
} as const;

const cardStyle = {
  display: "grid",
  gap: 6,
  padding: 16,
  borderRadius: 16,
  border: "1px solid #d7dfea",
  background: "#ffffff",
} as const;

const tableCellStyle = {
  padding: "12px 8px",
  borderBottom: "1px solid #edf1f6",
  textAlign: "right",
} as const;

const bucketLabels: Record<string, string> = {
  AC: "AC",
  OCI: "OCI",
  TPL: "TPL",
};
const bucketColors: Record<BalanceMovementRow["basis_bucket"], string> = {
  AC: "#10284a",
  OCI: "#33689a",
  TPL: "#d2a03f",
};
const balanceMovementBuckets: BalanceMovementRow["basis_bucket"][] = ["AC", "OCI", "TPL"];

function formatPct(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const n = Number(value);
  if (!Number.isFinite(n)) {
    return String(value);
  }
  return `${n.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
}

function formatYiFixed(value: string | number | null | undefined, digits = 2) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const n = Number(value) / 100000000;
  if (!Number.isFinite(n)) {
    return String(value);
  }
  return n.toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function formatSignedYi(value: string | number | null | undefined, digits = 2) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const n = Number(value) / 100000000;
  if (!Number.isFinite(n)) {
    return String(value);
  }
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })} 亿`;
}

function formatPlainNumber(value: string | number | null | undefined, digits = 2) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const n = Number(value);
  if (!Number.isFinite(n)) {
    return String(value);
  }
  return n.toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function trendBucket(
  month: BalanceMovementTrendMonth | undefined,
  bucket: BalanceMovementRow["basis_bucket"],
) {
  return month?.rows.find((row) => row.basis_bucket === bucket);
}

function basisBucketBalanceForBusiness(
  accountingByDate: Map<string, BalanceMovementTrendMonth>,
  businessMonth: BalanceBusinessMovementTrendMonth,
  bucket: BalanceMovementRow["basis_bucket"],
) {
  const am = accountingByDate.get(businessMonth.report_date);
  if (!am) {
    return undefined;
  }
  return trendBucket(am, bucket)?.current_balance;
}

function basisThreeBucketSum(
  accountingByDate: Map<string, BalanceMovementTrendMonth>,
  businessMonth: BalanceBusinessMovementTrendMonth,
) {
  const ac = basisBucketBalanceForBusiness(accountingByDate, businessMonth, "AC");
  const oci = basisBucketBalanceForBusiness(accountingByDate, businessMonth, "OCI");
  const tpl = basisBucketBalanceForBusiness(accountingByDate, businessMonth, "TPL");
  if (ac === undefined || oci === undefined || tpl === undefined) {
    return undefined;
  }
  const a = Number(ac);
  const o = Number(oci);
  const t = Number(tpl);
  if (!Number.isFinite(a) || !Number.isFinite(o) || !Number.isFinite(t)) {
    return undefined;
  }
  return a + o + t;
}

function trendDelta(
  current: string | number | null | undefined,
  previous: string | number | null | undefined,
) {
  const currentValue = Number(current);
  const previousValue = Number(previous);
  if (!Number.isFinite(currentValue) || !Number.isFinite(previousValue)) {
    return null;
  }
  return currentValue - previousValue;
}

function formatTrendMonthLabel(reportMonth: string) {
  const [year, month] = reportMonth.split("-");
  const monthNumber = Number(month);
  if (!year || !Number.isFinite(monthNumber)) {
    return reportMonth;
  }
  return `${year}年${monthNumber}月`;
}

function formatYiCell(value: string | number | null | undefined) {
  return formatYiFixed(value, 2);
}

function formatSignedYiCell(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const n = Number(value) / 100000000;
  if (!Number.isFinite(n)) {
    return String(value);
  }
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

type BalanceMovementMatrixValueKind = "amount" | "percent";

function formatMatrixValue(
  value: string | number | null | undefined,
  valueKind: BalanceMovementMatrixValueKind,
  omitUnit = false,
) {
  if (valueKind === "percent") {
    return formatPct(value);
  }
  const formatted = formatYiCell(value);
  if (formatted === "-") {
    return formatted;
  }
  return omitUnit ? formatted : `${formatted} 亿`;
}

function formatSignedPercentPoint(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const n = Number(value);
  if (!Number.isFinite(n)) {
    return String(value);
  }
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}pp`;
}

function drilldownStatusLabel(status: BalanceMovementDrilldownStatus | undefined) {
  switch (status) {
    case "supported":
      return "已支持";
    case "unsupported_missing_columns":
      return "字段不足";
    case "unsupported_low_coverage":
      return "覆盖率不足";
    case "no_data":
      return "无数据";
    default:
      return "未确认";
  }
}

function concentrationDimensionLabel(dimension: BalanceZqtzConcentrationDimensionKey) {
  switch (dimension) {
    case "issuer_name":
      return "主体";
    case "rating":
      return "评级";
    case "industry_name":
      return "行业";
    default:
      return dimension;
  }
}

function formatSignedMatrixValue(
  value: string | number | null | undefined,
  valueKind: BalanceMovementMatrixValueKind,
  omitUnit = false,
) {
  if (valueKind === "percent") {
    return formatSignedPercentPoint(value);
  }
  const formatted = formatSignedYiCell(value);
  if (formatted === "-") {
    return formatted;
  }
  return omitUnit ? formatted : `${formatted} 亿`;
}

type BusinessMovementMatrixRow = {
  key: string;
  label: string;
  side: "asset" | "liability" | "total";
  sourceKind?: "ledger" | "zqtz";
  sourceNote?: string;
  /** 三桶分类行：整行加粗 */
  emphasis?: boolean;
  valueKind: BalanceMovementMatrixValueKind;
  getValue: (month: BalanceBusinessMovementTrendMonth) => string | number | null | undefined;
};

function buildAccountingBasisMatrixRows(
  accountingByDate: Map<string, BalanceMovementTrendMonth>,
  options?: { keyPrefix?: string },
): BusinessMovementMatrixRow[] {
  const keyPrefix = options?.keyPrefix ?? "basis";
  return [
    {
      key: `${keyPrefix}-ac`,
      label: "AC",
      side: "asset",
      emphasis: true,
      sourceKind: "ledger",
      sourceNote: "总账控制数：以摊余成本计量（AC）",
      valueKind: "amount",
      getValue: (bm) => basisBucketBalanceForBusiness(accountingByDate, bm, "AC"),
    },
    {
      key: `${keyPrefix}-oci`,
      label: "OCI",
      side: "asset",
      emphasis: true,
      sourceKind: "ledger",
      sourceNote: "总账控制数：以公允价值计量且其变动计入其他综合收益（OCI）",
      valueKind: "amount",
      getValue: (bm) => basisBucketBalanceForBusiness(accountingByDate, bm, "OCI"),
    },
    {
      key: `${keyPrefix}-fvtpl`,
      label: "FVTPL",
      side: "asset",
      emphasis: true,
      sourceKind: "ledger",
      sourceNote: "总账 TPL 桶，与以公允价值计量且其变动计入当期损益（FVTPL）一致",
      valueKind: "amount",
      getValue: (bm) => basisBucketBalanceForBusiness(accountingByDate, bm, "TPL"),
    },
    {
      key: `${keyPrefix}-ac-oci-fvtpl-total`,
      label: "AC/OCI/FVTPL 合计",
      side: "asset",
      emphasis: true,
      sourceKind: "ledger",
      sourceNote: "AC+OCI+TPL 分类余额加总，与上三行同口径",
      valueKind: "amount",
      getValue: (bm) => basisThreeBucketSum(accountingByDate, bm),
    },
  ];
}

function businessTrendRow(month: BalanceBusinessMovementTrendMonth, rowKey: string) {
  return month.rows.find((row) => row.row_key === rowKey);
}

function compareBusinessMatrixCell(
  months: BalanceBusinessMovementTrendMonth[],
  row: Pick<BusinessMovementMatrixRow, "getValue" | "valueKind">,
  baselineOffset: number,
) {
  const currentMonth = months[months.length - 1];
  const baselineMonth = months[months.length - 1 - baselineOffset];
  if (!currentMonth || !baselineMonth) {
    return "-";
  }
  return formatSignedMatrixValue(
    trendDelta(row.getValue(currentMonth), row.getValue(baselineMonth)),
    row.valueKind,
    true,
  );
}

function compareBusinessMatrixCellToFirst(
  months: BalanceBusinessMovementTrendMonth[],
  row: Pick<BusinessMovementMatrixRow, "getValue" | "valueKind">,
) {
  const currentMonth = months[months.length - 1];
  const firstMonth = months[0];
  if (!currentMonth || !firstMonth || currentMonth.report_date === firstMonth.report_date) {
    return "-";
  }
  return formatSignedMatrixValue(
    trendDelta(row.getValue(currentMonth), row.getValue(firstMonth)),
    row.valueKind,
    true,
  );
}

const reconciliationStatusLabels: Record<BalanceMovementRow["reconciliation_status"], string> = {
  matched: "一致",
  mismatch: "不一致",
  gl_only: "仅总账",
  zqtz_only: "仅辅助",
};

function aggregateBucketReconciliation(rows: BalanceMovementRow[]) {
  const counts: Record<BalanceMovementRow["reconciliation_status"], number> = {
    matched: 0,
    mismatch: 0,
    gl_only: 0,
    zqtz_only: 0,
  };
  for (const row of rows) {
    counts[row.reconciliation_status] += 1;
  }
  const allMatched = rows.length === 0 || rows.every((row) => row.reconciliation_status === "matched");
  return { counts, allMatched };
}

type BusinessMomMove = {
  label: string;
  deltaYuan: number;
  side: "asset" | "liability";
  rowKey: string;
  sourceKind?: "ledger" | "zqtz";
  sourceNote?: string;
  currentYuan: number;
  previousYuan: number;
};

type ZqtzAssetDetailRow = {
  key: string;
  label: string;
  sourceNote: string;
  isSubItem: boolean;
  valueKind: BalanceMovementMatrixValueKind;
  getValue: (month: BalanceBusinessMovementTrendMonth) => string | number | null | undefined;
};

function buildZqtzAssetDetailRows(
  months: BalanceBusinessMovementTrendMonth[],
): ZqtzAssetDetailRow[] {
  const latestMonth = months[months.length - 1];
  const sourceRows = latestMonth?.rows ?? months.flatMap((month) => month.rows);
  return sourceRows
    .filter(
      (row) =>
        row.side === "asset" &&
        (row.source_kind === "zqtz" || row.row_key === "asset_long_term_equity_investment"),
    )
    .filter(
      (row, index, allRows) =>
        allRows.findIndex((candidate) => candidate.row_key === row.row_key) === index,
    )
    .sort((left, right) => left.sort_order - right.sort_order)
    .map((row) => ({
      key: row.row_key,
      label: row.row_label,
      sourceNote: row.source_note,
      isSubItem: row.row_label.startsWith("其中：") || row.row_key.startsWith("asset_zqtz_detail_"),
      valueKind: "amount",
      getValue: (month) => businessTrendRow(month, row.row_key)?.current_balance ?? "0",
    }));
}

function sumPrimaryZqtzAssetDetailRows(
  month: BalanceBusinessMovementTrendMonth,
  rows: ZqtzAssetDetailRow[],
) {
  return rows.reduce((total, row) => {
    if (row.isSubItem) {
      return total;
    }
    const value = Number(row.getValue(month));
    return Number.isFinite(value) ? total + value : total;
  }, 0);
}

function topBusinessLineMovesByMomAbs(
  months: BalanceBusinessMovementTrendMonth[],
  matrixRows: ReturnType<typeof buildBusinessCategoryMatrixRows>,
  limit: number,
): BusinessMomMove[] {
  if (months.length < 2) {
    return [];
  }
  const currentMonth = months[months.length - 1];
  const previousMonth = months[months.length - 2];
  const scored: BusinessMomMove[] = [];
  for (const row of matrixRows) {
    if (row.side !== "asset" && row.side !== "liability") {
      continue;
    }
    const current = row.getValue(currentMonth);
    const previous = row.getValue(previousMonth);
    const delta = trendDelta(current, previous);
    if (delta === null) {
      continue;
    }
    scored.push({
      label: row.label,
      rowKey: row.key,
      sourceKind: row.sourceKind ?? "ledger",
      sourceNote: row.sourceNote,
      deltaYuan: delta,
      side: row.side,
      currentYuan: Number(current),
      previousYuan: Number(previous),
    });
  }
  scored.sort((left, right) => Math.abs(right.deltaYuan) - Math.abs(left.deltaYuan));
  return scored.slice(0, limit);
}

function topBusinessLineMovesByWindowAbs(
  months: BalanceBusinessMovementTrendMonth[],
  matrixRows: ReturnType<typeof buildBusinessCategoryMatrixRows>,
  limit: number,
  baselineOffsetFromLatest: number,
): BusinessMomMove[] {
  if (months.length <= baselineOffsetFromLatest) {
    return [];
  }
  const currentMonth = months[months.length - 1];
  const previousMonth = months[months.length - 1 - baselineOffsetFromLatest];
  if (!currentMonth || !previousMonth) {
    return [];
  }
  const scored: BusinessMomMove[] = [];
  for (const row of matrixRows) {
    if (row.side !== "asset" && row.side !== "liability") {
      continue;
    }
    const current = row.getValue(currentMonth);
    const previous = row.getValue(previousMonth);
    const delta = trendDelta(current, previous);
    if (delta === null) {
      continue;
    }
    scored.push({
      label: row.label,
      rowKey: row.key,
      sourceKind: row.sourceKind ?? "ledger",
      sourceNote: row.sourceNote,
      deltaYuan: delta,
      side: row.side,
      currentYuan: Number(current),
      previousYuan: Number(previous),
    });
  }
  scored.sort((left, right) => Math.abs(right.deltaYuan) - Math.abs(left.deltaYuan));
  return scored.slice(0, limit);
}

function uniqueNonEmptyStrings(values: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const value of values) {
    const trimmed = value.trim();
    if (!trimmed || seen.has(trimmed)) {
      continue;
    }
    seen.add(trimmed);
    out.push(trimmed);
  }
  return out;
}

function matrixDeltaTone(formatted: string): string {
  const t = formatted.trim();
  if (t === "" || t === "-") {
    return "balance-movement-matrix__delta balance-movement-matrix__delta--neutral";
  }
  if (t.startsWith("+") || t.startsWith("＋")) {
    return "balance-movement-matrix__delta balance-movement-matrix__delta--up";
  }
  if (t.startsWith("-") || t.startsWith("−")) {
    return "balance-movement-matrix__delta balance-movement-matrix__delta--down";
  }
  return "balance-movement-matrix__delta balance-movement-matrix__delta--neutral";
}

function buildBusinessCategoryMatrixRows(
  months: BalanceBusinessMovementTrendMonth[],
): BusinessMovementMatrixRow[] {
  const latestMonth = months[months.length - 1];
  const rowDefs = new Map<
    string,
    {
      label: string;
      side: "asset" | "liability";
      sourceKind: "ledger" | "zqtz";
      sourceNote?: string;
      sortOrder: number;
    }
  >();
  for (const month of months) {
    for (const row of month.rows) {
      if (!rowDefs.has(row.row_key)) {
        rowDefs.set(row.row_key, {
          label: row.row_label,
          side: row.side,
          sourceKind: row.source_kind,
          sourceNote: row.source_note,
          sortOrder: row.sort_order,
        });
      }
    }
  }
  if (latestMonth) {
    for (const row of latestMonth.rows) {
      rowDefs.set(row.row_key, {
        label: row.row_label,
        side: row.side,
        sourceKind: row.source_kind,
        sourceNote: row.source_note,
        sortOrder: row.sort_order,
      });
    }
  }
  return Array.from(rowDefs.entries())
    .sort(([, left], [, right]) => left.sortOrder - right.sortOrder)
    .map(([rowKey, row]) => ({
      key: rowKey,
      label: row.label,
      side: row.side,
      sourceKind: row.sourceKind,
      sourceNote: row.sourceNote,
      valueKind: "amount" as const,
      getValue: (month: BalanceBusinessMovementTrendMonth) =>
        businessTrendRow(month, rowKey)?.current_balance,
    }));
}

function sumBusinessMatrixRowValues(
  month: BalanceBusinessMovementTrendMonth,
  rows: Pick<BusinessMovementMatrixRow, "getValue">[],
) {
  return rows.reduce((total, row) => {
    const value = Number(row.getValue(month));
    return Number.isFinite(value) ? total + value : total;
  }, 0);
}

function formatTrendAxisMonth(reportMonth: string) {
  const [year, month] = reportMonth.split("-");
  const monthNumber = Number(month);
  if (!year || !Number.isFinite(monthNumber)) {
    return reportMonth;
  }
  return `${year.slice(2)}-${String(monthNumber).padStart(2, "0")}`;
}

function toSharePoint(month: BalanceMovementTrendMonth): AccountingBasisStackedSharePoint {
  const total = Number(month.current_balance_total);
  const point: AccountingBasisStackedSharePoint = {
    monthLabel: formatTrendAxisMonth(month.report_month),
    AC: 0,
    OCI: 0,
    TPL: 0,
    totalValueYi: Number.isFinite(total) ? total / 100000000 : undefined,
  };
  for (const bucket of balanceMovementBuckets) {
    const row = trendBucket(month, bucket);
    const value = Number(row?.current_balance);
    const share = total > 0 && Number.isFinite(value) ? (value / total) * 100 : Number(row?.current_balance_pct);
    point[bucket] = Number.isFinite(share) ? share : 0;
    if (bucket === "AC") point.acValueYi = Number.isFinite(value) ? value / 100000000 : undefined;
    if (bucket === "OCI") point.ociValueYi = Number.isFinite(value) ? value / 100000000 : undefined;
    if (bucket === "TPL") point.tplValueYi = Number.isFinite(value) ? value / 100000000 : undefined;
  }
  return point;
}

function formatSignedPoint(value: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}pp`;
}

function formatShareEvolutionPct(value: number) {
  return `${value.toFixed(2)}%`;
}

function formatShareEvolutionYi(value: number | undefined) {
  if (value === undefined || !Number.isFinite(value)) {
    return "—";
  }
  return `${value.toFixed(2)} 亿`;
}

/** 用于同比：返回 report_month 的上年同月 `YYYY-MM` */
function priorYearSameMonth(reportMonth: string): string {
  const [y, m] = reportMonth.split("-").map(Number);
  if (!Number.isFinite(y) || !Number.isFinite(m)) {
    return "";
  }
  return `${y - 1}-${String(m).padStart(2, "0")}`;
}

function formatSignedYiDelta(
  current: number | undefined,
  base: number | undefined,
): string {
  if (
    current === undefined ||
    base === undefined ||
    !Number.isFinite(current) ||
    !Number.isFinite(base)
  ) {
    return "—";
  }
  const d = current - base;
  const sign = d > 0 ? "+" : "";
  return `${sign}${d.toFixed(2)} 亿`;
}

type StructureShareTableRow = {
  point: AccountingBasisStackedSharePoint;
  reportMonth: string;
};

function numericValue(value: string | number | null | undefined) {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function shareDeltaPp(row: BalanceMovementRow): number {
  return numericValue(row.current_balance_pct) - numericValue(row.previous_balance_pct);
}

function isPreviousCalendarMonth(currentReportDate: string, previousReportDate: string) {
  const currentParts = currentReportDate.split("-").map(Number);
  const previousParts = previousReportDate.split("-").map(Number);
  const [currentYear, currentMonth] = currentParts;
  const [previousYear, previousMonth] = previousParts;
  if (
    !Number.isInteger(currentYear) ||
    !Number.isInteger(currentMonth) ||
    !Number.isInteger(previousYear) ||
    !Number.isInteger(previousMonth)
  ) {
    return false;
  }
  return previousYear * 12 + previousMonth === currentYear * 12 + currentMonth - 1;
}

function statusTone(status: BalanceMovementRow["reconciliation_status"]) {
  return status === "matched" ? "#027a48" : "#b54708";
}

type BalanceMovementDriver = {
  bucket: BalanceMovementRow["basis_bucket"];
  balanceChange: number;
  balanceChangeYi: number;
  contributionPct: number;
  currentBalancePct: number;
  previousBalancePct: number;
  shareDelta: number;
};

function toMovementDriver(row: BalanceMovementRow): BalanceMovementDriver {
  const balanceChange = numericValue(row.balance_change);
  const currentBalancePct = numericValue(row.current_balance_pct);
  const previousBalancePct = numericValue(row.previous_balance_pct);
  return {
    bucket: row.basis_bucket,
    balanceChange,
    balanceChangeYi: balanceChange / 100000000,
    contributionPct: numericValue(row.contribution_pct),
    currentBalancePct,
    previousBalancePct,
    shareDelta: currentBalancePct - previousBalancePct,
  };
}

function formatSignedYiNumber(value: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function movementDirection(value: string | number | null | undefined) {
  const n = numericValue(value);
  if (n > 0) return "增加";
  if (n < 0) return "减少";
  return "持平";
}

function dataIndexFromTooltip(params: unknown) {
  const first = Array.isArray(params) ? params[0] : params;
  if (!first || typeof first !== "object" || !("dataIndex" in first)) {
    return 0;
  }
  const dataIndex = Number((first as { dataIndex?: unknown }).dataIndex);
  return Number.isFinite(dataIndex) ? dataIndex : 0;
}

function buildDriverChartOption(drivers: BalanceMovementDriver[]): EChartsOption {
  return {
    grid: { left: 44, right: 72, top: 20, bottom: 34 },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params: unknown) => {
        const driver = drivers[dataIndexFromTooltip(params)];
        if (!driver) return "";
        return [
          driver.bucket,
          `变动：${formatSignedYiNumber(driver.balanceChangeYi)} 亿`,
          `贡献：${formatPct(driver.contributionPct)}`,
          `占比变化：${formatSignedPoint(driver.shareDelta)}`,
        ].join("<br/>");
      },
    },
    xAxis: {
      type: "value",
      axisLabel: { formatter: (value: number) => `${value.toFixed(0)}亿` },
      splitLine: { lineStyle: { color: "#edf1f6" } },
    },
    yAxis: {
      type: "category",
      data: drivers.map((driver) => driver.bucket),
      axisTick: { show: false },
      axisLabel: { color: "#26364a", fontWeight: 700 },
    },
    series: [
      {
        name: "余额变动",
        type: "bar",
        barWidth: 28,
        data: drivers.map((driver) => driver.balanceChangeYi),
        itemStyle: {
          color: (params: { dataIndex: number }) =>
            bucketColors[drivers[params.dataIndex]?.bucket ?? "AC"],
          borderRadius: [0, 4, 4, 0],
        },
        label: {
          show: true,
          position: "right",
          color: "#26364a",
          fontWeight: 700,
          formatter: (params: { dataIndex: number }) => {
            const driver = drivers[params.dataIndex];
            return driver ? `${formatSignedYiNumber(driver.balanceChangeYi)} 亿` : "";
          },
        },
      },
    ],
  };
}

function StructureMigrationPanel({
  analysis,
}: {
  analysis: BalanceStructureMigrationAnalysis;
}) {
  const latestPair = analysis.pairs[analysis.pairs.length - 1];
  return (
    <section
      className="balance-movement-derived-panel"
      data-testid="balance-movement-analysis-structure-migration"
    >
      <div className="balance-movement-derived-panel__header">
        <div>
          <span>结构迁移信号</span>
          <h2>AC / OCI / FVTPL 占比变化</h2>
        </div>
        {latestPair?.dominant_share_increase_bucket ? (
          <strong>{latestPair.dominant_share_increase_bucket}</strong>
        ) : null}
      </div>
      <p className="balance-movement-derived-panel__summary">{analysis.summary}</p>
      <p className="balance-movement-derived-panel__caveat">{analysis.caveat}</p>
      {latestPair ? (
        <div className="balance-movement-derived-grid">
          {latestPair.buckets.map((bucket) => (
            <div key={bucket.basis_bucket} className="balance-movement-derived-card">
              <span>{bucket.basis_bucket}</span>
              <strong>{formatSignedYiCell(bucket.balance_delta)} 亿</strong>
              <p>
                占比 {formatPct(bucket.current_share_pct)}，
                较上期 {formatSignedPercentPoint(bucket.share_delta_pp)}
              </p>
            </div>
          ))}
        </div>
      ) : null}
      {latestPair ? (
        <div className="balance-movement-derived-notes">
          <p>{latestPair.fvtpl_volatility_signal}</p>
          <p>{latestPair.oci_valuation_signal}</p>
        </div>
      ) : null}
    </section>
  );
}

function DifferenceAttributionWaterfallPanel({
  waterfall,
}: {
  waterfall: BalanceDifferenceAttributionWaterfall;
}) {
  return (
    <section
      className="balance-movement-derived-panel"
      data-testid="balance-movement-analysis-difference-waterfall"
    >
      <div className="balance-movement-derived-panel__header">
        <div>
          <span>差异归因瀑布</span>
          <h2>ZQTZ 明细汇总 vs AC/OCI/FVTPL</h2>
        </div>
        <strong>{formatSignedYiCell(waterfall.net_difference)} 亿</strong>
      </div>
      <p className="balance-movement-derived-panel__summary">{waterfall.caveat}</p>
      <div className="balance-movement-waterfall">
        <div className="balance-movement-waterfall__endpoint">
          <span>{waterfall.reference_label}</span>
          <strong>{formatYiCell(waterfall.reference_total)} 亿</strong>
        </div>
        {waterfall.components.map((component) => {
          const isUnsupported = component.is_supported === false;
          const className = [
            "balance-movement-waterfall__component",
            component.is_residual ? "balance-movement-waterfall__component--residual" : "",
            isUnsupported ? "balance-movement-waterfall__component--unsupported" : "",
          ]
            .filter(Boolean)
            .join(" ");
          return (
            <div key={component.component_key} className={className}>
              <div>
                <span>{component.component_label}</span>
                <p>{component.evidence_note}</p>
              </div>
              {isUnsupported ? (
                <strong>待拆分</strong>
              ) : (
                <strong>{formatSignedYiCell(component.amount)} 亿</strong>
              )}
            </div>
          );
        })}
        <div className="balance-movement-waterfall__endpoint">
          <span>{waterfall.target_label}</span>
          <strong>{formatYiCell(waterfall.target_total)} 亿</strong>
        </div>
      </div>
      <p className="balance-movement-derived-panel__caveat">
        闭合校验：{formatSignedYiCell(waterfall.closing_check)} 亿
      </p>
    </section>
  );
}

function BasisMovementDecompositionPanel({
  decomposition,
}: {
  decomposition: BalanceBasisMovementDecomposition;
}) {
  return (
    <section
      className="balance-movement-derived-panel"
      data-testid="balance-movement-analysis-basis-decomposition"
    >
      <div className="balance-movement-derived-panel__header">
        <div>
          <span>会计分类驱动拆解</span>
          <h2>AC / OCI / TPL 驱动拆解</h2>
        </div>
        <strong>{drilldownStatusLabel(decomposition.meta.status)}</strong>
      </div>
      <p className="balance-movement-derived-panel__summary">
        {decomposition.meta.report_date}
        {decomposition.meta.prior_report_date ? ` 较 ${decomposition.meta.prior_report_date}` : ""}：
        覆盖 {formatPct(decomposition.meta.coverage_pct)}，按总账科目归集到 AC / OCI / TPL。
      </p>
      <p className="balance-movement-derived-panel__caveat">{decomposition.meta.caveat}</p>
      <p className="balance-movement-derived-panel__caveat">
        口径：{decomposition.meta.source_scope}
      </p>
      <div className="balance-movement-derived-grid">
        {decomposition.buckets.map((bucket) => (
          <div key={bucket.basis_bucket} className="balance-movement-derived-card">
            <span>{bucket.basis_bucket}</span>
            <strong>{formatSignedYiCell(bucket.balance_change)} 亿</strong>
            <p>
              期末 {formatYiCell(bucket.current_balance)} 亿 · 残差{" "}
              {formatSignedYiCell(bucket.residual_amount)} 亿
            </p>
            <ul className="balance-movement-derived-list">
              {bucket.rows.slice(0, 3).map((row) => (
                <li key={`${bucket.basis_bucket}-${row.component_key}`}>
                  <span>{row.component_label}</span>
                  <strong>{formatSignedYiCell(row.balance_change)} 亿</strong>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}

function ZqtzMaturityStructurePanel({
  structure,
}: {
  structure: BalanceZqtzMaturityStructure;
}) {
  return (
    <section
      className="balance-movement-derived-panel"
      data-testid="balance-movement-analysis-zqtz-maturity"
    >
      <div className="balance-movement-derived-panel__header">
        <div>
          <span>ZQTZ 到期视图</span>
          <h2>期限 / 到期结构</h2>
        </div>
        <strong>{drilldownStatusLabel(structure.meta.status)}</strong>
      </div>
      <p className="balance-movement-derived-panel__summary">
        {structure.meta.report_date}
        {structure.meta.prior_report_date ? ` 较 ${structure.meta.prior_report_date}` : ""}：
        覆盖 {formatPct(structure.meta.coverage_pct)}，未知到期金额{" "}
        {formatYiCell(structure.meta.unknown_total)} 亿。
      </p>
      <p className="balance-movement-derived-panel__caveat">{structure.meta.caveat}</p>
      <div className="balance-movement-derived-table-wrap">
        <table className="balance-movement-derived-table">
          <thead>
            <tr>
              <th>期限桶</th>
              <th>期末</th>
              <th>较上期</th>
              <th>占比</th>
              <th>笔数</th>
            </tr>
          </thead>
          <tbody>
            {structure.buckets.map((bucket) => (
              <tr key={bucket.maturity_bucket}>
                <th scope="row">{bucket.bucket_label}</th>
                <td>{formatYiCell(bucket.current_amount)} 亿</td>
                <td>{formatSignedYiCell(bucket.delta_amount)} 亿</td>
                <td>{formatPct(bucket.share_pct)}</td>
                <td>{bucket.item_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ZqtzConcentrationAnalysisPanel({
  analysis,
}: {
  analysis: BalanceZqtzConcentrationAnalysis;
}) {
  const coverageText =
    analysis.meta.coverage_pct === null || analysis.meta.coverage_pct === undefined
      ? "各维度覆盖见下方"
      : `最低维度覆盖 ${formatPct(analysis.meta.coverage_pct)}`;
  const unknownText =
    analysis.meta.unknown_total === null || analysis.meta.unknown_total === undefined
      ? "未知维度金额见各维度"
      : `未知维度金额 ${formatYiCell(analysis.meta.unknown_total)} 亿`;
  return (
    <section
      className="balance-movement-derived-panel"
      data-testid="balance-movement-analysis-zqtz-concentration"
    >
      <div className="balance-movement-derived-panel__header">
        <div>
          <span>ZQTZ 集中度视图</span>
          <h2>主体 / 评级 / 行业集中度</h2>
        </div>
        <strong>{drilldownStatusLabel(analysis.meta.status)}</strong>
      </div>
      <p className="balance-movement-derived-panel__summary">
        {analysis.meta.report_date}
        {analysis.meta.prior_report_date ? ` 较 ${analysis.meta.prior_report_date}` : ""}：{coverageText}，
        {unknownText}。
      </p>
      <p className="balance-movement-derived-panel__caveat">{analysis.meta.caveat}</p>
      <div className="balance-movement-concentration-grid">
        {analysis.dimensions.map((dimension) => (
          <div key={dimension.dimension} className="balance-movement-concentration-card">
            <div className="balance-movement-concentration-card__header">
              <h3>{concentrationDimensionLabel(dimension.dimension)}</h3>
              <span>{drilldownStatusLabel(dimension.status)}</span>
            </div>
            <p>
              覆盖 {formatPct(dimension.coverage_pct)} · Top5 {formatPct(dimension.top5_share_pct)} ·
              HHI {formatPlainNumber(dimension.hhi)}
            </p>
            <table className="balance-movement-derived-table">
              <thead>
                <tr>
                  <th>项目</th>
                  <th>期末</th>
                  <th>较上期</th>
                  <th>占比</th>
                </tr>
              </thead>
              <tbody>
                {dimension.items.map((item) => (
                  <tr key={`${dimension.dimension}-${item.item_kind}-${item.rank}-${item.dimension_value}`}>
                    <th scope="row">
                      {item.rank > 0 ? `${item.rank}. ` : ""}
                      {item.dimension_value}
                    </th>
                    <td>{formatYiCell(item.current_amount)} 亿</td>
                    <td>{formatSignedYiCell(item.delta_amount)} 亿</td>
                    <td>{formatPct(item.share_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="balance-movement-derived-panel__caveat">{dimension.caveat}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function BalanceMovementAnalysisPage() {
  const client = useApiClient();
  const [selectedDate, setSelectedDate] = useState("");
  const [currencyBasis, setCurrencyBasis] = useState("CNX");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshMessage, setRefreshMessage] = useState<string | null>(null);

  const datesQuery = useQuery({
    queryKey: ["balance-movement-analysis", "dates", client.mode, currencyBasis],
    queryFn: () => client.getBalanceMovementDates(currencyBasis),
    retry: false,
  });
  const reportDates = useMemo(
    () => datesQuery.data?.result.report_dates ?? [],
    [datesQuery.data?.result.report_dates],
  );
  const dateStatus = datesQuery.isError
    ? {
        tone: "error" as const,
        title: "报告日期加载失败",
        detail: "请确认后端 7888 服务与余额变动读模型可用。",
      }
    : !datesQuery.isLoading && reportDates.length === 0
      ? {
          tone: "empty" as const,
          title: "暂无已物化报告日期",
          detail: `${currencyBasis} 口径下没有可选日期；请先物化余额变动读模型。`,
        }
      : null;

  useEffect(() => {
    if (!selectedDate && reportDates.length) {
      setSelectedDate(reportDates[0] ?? "");
    }
  }, [reportDates, selectedDate]);

  const detailQuery = useQuery({
    queryKey: ["balance-movement-analysis", "detail", client.mode, selectedDate, currencyBasis],
    queryFn: () =>
      client.getBalanceMovementAnalysis({
        reportDate: selectedDate,
        currencyBasis,
      }),
    enabled: Boolean(selectedDate),
    retry: false,
  });

  const rows = useMemo(
    () => detailQuery.data?.result.rows ?? [],
    [detailQuery.data?.result.rows],
  );
  const summary = detailQuery.data?.result.summary;
  const trendMonths = useMemo(
    () => detailQuery.data?.result.trend_months ?? [],
    [detailQuery.data?.result.trend_months],
  );
  const businessTrendMonths = useMemo(
    () => detailQuery.data?.result.business_trend_months ?? [],
    [detailQuery.data?.result.business_trend_months],
  );
  const accountingMatrixMonths = useMemo(() => [...trendMonths].reverse(), [trendMonths]);
  const businessMatrixMonths = useMemo(
    () => [...businessTrendMonths].reverse(),
    [businessTrendMonths],
  );
  const businessMatrixRows = useMemo(
    () => buildBusinessCategoryMatrixRows(businessMatrixMonths),
    [businessMatrixMonths],
  );
  const zqtzCalibrationAnalysis = detailQuery.data?.result.zqtz_calibration_analysis ?? null;
  const structureMigrationAnalysis =
    detailQuery.data?.result.structure_migration_analysis ?? null;
  const differenceAttributionWaterfall =
    detailQuery.data?.result.difference_attribution_waterfall ?? null;
  const basisMovementDecomposition =
    detailQuery.data?.result.basis_movement_decomposition ?? null;
  const zqtzMaturityStructure =
    detailQuery.data?.result.zqtz_maturity_structure ?? null;
  const zqtzConcentrationAnalysis =
    detailQuery.data?.result.zqtz_concentration_analysis ?? null;
  const accountingByReportDate = useMemo(() => {
    const map = new Map<string, BalanceMovementTrendMonth>();
    for (const month of accountingMatrixMonths) {
      map.set(month.report_date, month);
    }
    return map;
  }, [accountingMatrixMonths]);
  const accountingBasisMatrixRows = useMemo(
    () => buildAccountingBasisMatrixRows(accountingByReportDate),
    [accountingByReportDate],
  );
  const businessMatrixAssetRows = useMemo(
    () =>
      businessMatrixRows.filter(
        (row) =>
          row.side === "asset" &&
          !row.key.startsWith("asset_zqtz_") &&
          row.key !== "asset_long_term_equity_investment",
      ),
    [businessMatrixRows],
  );
  const businessMatrixLiabilityRows = useMemo(
    () => businessMatrixRows.filter((row) => row.side === "liability"),
    [businessMatrixRows],
  );
  const businessProjectTableRows = useMemo((): BusinessMovementMatrixRow[] => {
    return [
      {
        key: "asset-total",
        label: "资产端合计",
        side: "total",
        sourceNote: "资产端合计 = AC + OCI + TPL + 同业资产；金融投资明细在上方单独页展示。",
        sourceKind: "ledger",
        valueKind: "amount",
        getValue: (month) => {
          const accountingTotal = basisThreeBucketSum(accountingByReportDate, month);
          const interbankAssetTotal = sumBusinessMatrixRowValues(month, businessMatrixAssetRows);
          return accountingTotal === undefined ? interbankAssetTotal : accountingTotal + interbankAssetTotal;
        },
      },
      {
        key: "liability-total",
        label: "负债端合计",
        side: "total",
        sourceNote: "负债端同业业务行合计",
        sourceKind: "ledger",
        valueKind: "amount",
        getValue: (month) => sumBusinessMatrixRowValues(month, businessMatrixLiabilityRows),
      },
      {
        key: "net-total",
        label: "资产负债净额",
        side: "total",
        sourceNote: "资产端合计 + 负债端合计。",
        sourceKind: "ledger",
        valueKind: "amount",
        getValue: (month) => {
          const accountingTotal = basisThreeBucketSum(accountingByReportDate, month);
          const interbankAssetTotal = sumBusinessMatrixRowValues(month, businessMatrixAssetRows);
          const assetTotal =
            accountingTotal === undefined ? interbankAssetTotal : accountingTotal + interbankAssetTotal;
          return assetTotal + sumBusinessMatrixRowValues(month, businessMatrixLiabilityRows);
        },
      },
    ];
  }, [accountingByReportDate, businessMatrixAssetRows, businessMatrixLiabilityRows]);
  const monthlyMatrixCategoryRows = useMemo(
    () => [
      ...businessMatrixAssetRows,
      ...accountingBasisMatrixRows,
      ...businessMatrixLiabilityRows,
    ],
    [businessMatrixAssetRows, accountingBasisMatrixRows, businessMatrixLiabilityRows],
  );
  const structureShareTableRows = useMemo((): StructureShareTableRow[] => {
    return accountingMatrixMonths.map((month) => ({
      point: toSharePoint(month),
      reportMonth: month.report_month,
    }));
  }, [accountingMatrixMonths]);
  const shareRowByReportMonth = useMemo(() => {
    const map = new Map<string, StructureShareTableRow>();
    for (const row of structureShareTableRows) {
      map.set(row.reportMonth, row);
    }
    return map;
  }, [structureShareTableRows]);
  const balanceStructureTrend = useMemo(
    () => structureShareTableRows.map((row) => row.point),
    [structureShareTableRows],
  );
  const balanceStructureInsight = useMemo(() => {
    const first = balanceStructureTrend[0];
    const latest = balanceStructureTrend[balanceStructureTrend.length - 1];
    if (!first || !latest || first.monthLabel === latest.monthLabel) {
      return null;
    }
    return `AC占比较首月 ${formatSignedPoint(latest.AC - first.AC)}，OCI ${formatSignedPoint(
      latest.OCI - first.OCI,
    )}，TPL ${formatSignedPoint(latest.TPL - first.TPL)}。`;
  }, [balanceStructureTrend]);
  const currentTrendMonth = trendMonths[0];
  const previousTrendMonth = trendMonths[1];
  const rowByBucket = useMemo(
    () => new Map(rows.map((row) => [row.basis_bucket, row])),
    [rows],
  );
  const movementDrivers = useMemo(
    () =>
      rows
        .map(toMovementDriver)
        .sort((left, right) => Math.abs(right.balanceChange) - Math.abs(left.balanceChange)),
    [rows],
  );
  const movementDriverByBucket = useMemo(
    () => new Map(movementDrivers.map((driver) => [driver.bucket, driver])),
    [movementDrivers],
  );
  const topMovementDriver = movementDrivers[0];
  const maxShareShiftDriver = useMemo(
    () =>
      [...movementDrivers].sort(
        (left, right) => Math.abs(right.shareDelta) - Math.abs(left.shareDelta),
      )[0],
    [movementDrivers],
  );
  const driverChartOption = useMemo(
    () => buildDriverChartOption(movementDrivers),
    [movementDrivers],
  );
  const structureStatus =
    maxShareShiftDriver && Math.abs(maxShareShiftDriver.shareDelta) <= 1
      ? "结构整体稳定"
      : "结构变化明显";
  const trendComparison = useMemo(() => {
    if (!currentTrendMonth || !previousTrendMonth) {
      return null;
    }
    if (
      !isPreviousCalendarMonth(
        currentTrendMonth.report_date,
        previousTrendMonth.report_date,
      )
    ) {
      return null;
    }
    const totalDelta = trendDelta(
      currentTrendMonth.current_balance_total,
      previousTrendMonth.current_balance_total,
    );
    if (totalDelta === null) {
      return null;
    }
    const drivers = balanceMovementBuckets
      .map((bucket) => {
        const delta = trendDelta(
          trendBucket(currentTrendMonth, bucket)?.current_balance,
          trendBucket(previousTrendMonth, bucket)?.current_balance,
        );
        return delta === null ? null : { bucket, delta };
      })
      .filter((driver): driver is { bucket: BalanceMovementRow["basis_bucket"]; delta: number } =>
        driver !== null,
      )
      .sort((left, right) => Math.abs(right.delta) - Math.abs(left.delta));
    return {
      drivers,
      previousReportDate: previousTrendMonth.report_date,
      totalDelta,
    };
  }, [currentTrendMonth, previousTrendMonth]);

  const reconAggregate = useMemo(() => aggregateBucketReconciliation(rows), [rows]);
  const businessTopMomMoves = useMemo(
    () => topBusinessLineMovesByMomAbs(businessMatrixMonths, businessMatrixRows, 5),
    [businessMatrixMonths, businessMatrixRows],
  );
  const businessTopSixMonthMoves = useMemo(
    () =>
      topBusinessLineMovesByWindowAbs(
        businessMatrixMonths,
        businessMatrixRows,
        5,
        Math.max(1, businessMatrixMonths.length - 1),
      ),
    [businessMatrixMonths, businessMatrixRows],
  );
  const zqtzAssetDetailRows = useMemo(
    () => buildZqtzAssetDetailRows(businessMatrixMonths),
    [businessMatrixMonths],
  );
  const zqtzAssetDetailSummaryRow = useMemo<ZqtzAssetDetailRow | null>(() => {
    if (zqtzAssetDetailRows.length === 0) {
      return null;
    }
    return {
      key: "zqtz-detail-summary",
      label: "汇总",
      sourceNote: "按本表非“其中”明细加总，避免重复计算下级项目。",
      isSubItem: false,
      valueKind: "amount",
      getValue: (month) => sumPrimaryZqtzAssetDetailRows(month, zqtzAssetDetailRows),
    };
  }, [zqtzAssetDetailRows]);
  const trendMoMDriverBucket = trendComparison?.drivers[0]?.bucket;
  const structureShareDriverBucket = maxShareShiftDriver?.bucket;
  const structureDriverHint = useMemo(() => {
    if (!trendMoMDriverBucket || !structureShareDriverBucket) {
      return null;
    }
    if (trendMoMDriverBucket === structureShareDriverBucket) {
      return null;
    }
    return `「变动额」环比主导为 ${trendMoMDriverBucket}，「占比变化（pp）」主导为 ${structureShareDriverBucket}；二者可同时成立。`;
  }, [trendMoMDriverBucket, structureShareDriverBucket]);

  const seriesContextSegments = useMemo(() => {
    const segments: string[] = [];
    if (businessMatrixMonths.length === 2) {
      segments.push(
        "「月度余额分析矩阵」当前仅含两个月度：「较年初」列 = 相对本序列首月变动，不一定等同于自然年 1 月末基期。",
      );
    }
    if (
      currentTrendMonth &&
      previousTrendMonth &&
      !isPreviousCalendarMonth(currentTrendMonth.report_date, previousTrendMonth.report_date)
    ) {
      segments.push("上方总账「较上月」结论文案已隐藏：相邻两期在日历上非连续月和月。");
    }
    return segments;
  }, [businessMatrixMonths.length, currentTrendMonth, previousTrendMonth]);

  const governanceMeta = useMemo(() => {
    const reportDate = detailQuery.data?.result.report_date ?? "";
    const ruleVersions = uniqueNonEmptyStrings(rows.map((row) => String(row.rule_version ?? "")));
    const sourceVersions = uniqueNonEmptyStrings(rows.map((row) => String(row.source_version ?? "")));
    return { reportDate, ruleVersions, sourceVersions };
  }, [detailQuery.data?.result.report_date, rows]);

  async function handleRefresh() {
    if (!selectedDate) {
      return;
    }
    setIsRefreshing(true);
    setRefreshMessage(null);
    try {
      const payload = await client.refreshBalanceMovementAnalysis({
        reportDate: selectedDate,
        currencyBasis,
      });
      const upstreamRefreshCount =
        (payload.product_category_refreshed_dates?.length ?? 0) +
        (payload.formal_balance_refreshed_dates?.length ?? 0);
      const movementRefreshCount = payload.movement_refreshed_dates?.length ?? 0;
      const refreshDetail =
        upstreamRefreshCount > 0
          ? `，补刷新上游 ${upstreamRefreshCount} 月 / 读模型 ${movementRefreshCount} 月`
          : movementRefreshCount > 1
            ? `，读模型 ${movementRefreshCount} 月`
            : "";
      setRefreshMessage(`${payload.status}: ${payload.row_count} 行${refreshDetail}`);
      await detailQuery.refetch();
      await datesQuery.refetch();
    } finally {
      setIsRefreshing(false);
    }
  }

  return (
    <section data-testid="balance-movement-analysis-page">
      <div style={pageHeaderStyle}>
        <div>
          <h1
            data-testid="balance-movement-analysis-title"
            style={{ margin: 0, fontSize: 28, fontWeight: 700 }}
          >
            余额变动分析
          </h1>
          <p
            data-testid="balance-movement-analysis-subtitle"
            style={{ marginTop: 8, marginBottom: 0, color: designTokens.color.neutral[600], fontSize: 14 }}
          >
            AC / OCI / TPL 月末余额、月度变动与总账控制数对账。
          </p>
        </div>
        <div style={{ display: "grid", gap: 10, justifyItems: "end" }}>
          <span
            style={{
              ...chipTypography,
              background: designTokens.color.primary[50],
              color: designTokens.color.primary[600],
            }}
          >
            正式总账控制
          </span>
          <span
            style={{
              ...chipTypography,
              background:
                client.mode === "real" ? designTokens.color.success[50] : designTokens.color.primary[50],
              color:
                client.mode === "real"
                  ? displayTokens.apiMode.realForeground
                  : displayTokens.apiMode.mockForeground,
            }}
          >
            {client.mode === "real" ? "正式接口" : "本地模拟"}
          </span>
        </div>
      </div>

      <FilterBar style={{ marginBottom: 16 }}>
        <label style={{ display: "grid", gap: 6 }}>
          报告日期
          <select
            aria-label="余额变动分析-报告日期"
            value={selectedDate}
            onChange={(event) => setSelectedDate(event.target.value)}
          >
            {reportDates.map((reportDate) => (
              <option key={reportDate} value={reportDate}>
                {reportDate}
              </option>
            ))}
          </select>
        </label>
        <label style={{ display: "grid", gap: 6 }}>
          控制币种
          <select
            aria-label="余额变动分析-控制币种"
            value={currencyBasis}
            onChange={(event) => {
              setCurrencyBasis(event.target.value);
              setSelectedDate("");
            }}
          >
            <option value="CNX">CNX</option>
            <option value="CNY">CNY</option>
          </select>
        </label>
        <button
          type="button"
          data-testid="balance-movement-analysis-refresh"
          onClick={() => void handleRefresh()}
          disabled={!selectedDate || isRefreshing}
        >
          {isRefreshing ? "刷新中..." : "刷新余额变动"}
        </button>
        {refreshMessage ? (
          <span data-testid="balance-movement-analysis-refresh-message">{refreshMessage}</span>
        ) : null}
      </FilterBar>
      {dateStatus ? (
        <div
          data-testid="balance-movement-analysis-date-status"
          className={`balance-movement-date-status balance-movement-date-status--${dateStatus.tone}`}
          role={dateStatus.tone === "error" ? "alert" : "status"}
        >
          <strong>{dateStatus.title}</strong>
          <span>{dateStatus.detail}</span>
        </div>
      ) : null}

      {summary ? (
        <section
          data-testid="balance-movement-analysis-conclusion"
          className="balance-movement-conclusion"
        >
          <div className="balance-movement-conclusion__top">
            <div>
              <div
                className={`balance-movement-conclusion__status${
                  rows.length > 0 && !reconAggregate.allMatched
                    ? " balance-movement-conclusion__status--warn"
                    : ""
                }`}
              >
                {rows.length > 0 && !reconAggregate.allMatched
                  ? "ZQTZ 分桶对账需关注"
                  : "总账控制核对通过"}
              </div>
              <strong className="balance-movement-conclusion__headline">
                {selectedDate || detailQuery.data?.result.report_date} 合计{" "}
                {formatYiFixed(summary.current_balance_total)} 亿
              </strong>
              <div
                data-testid="balance-movement-analysis-recon-summary"
                className={`balance-movement-conclusion__recon-summary${
                  rows.length > 0 && !reconAggregate.allMatched
                    ? " balance-movement-conclusion__recon-summary--warn"
                    : ""
                }`}
              >
                {rows.length === 0 ? (
                  <span>暂无 AC/OCI/TPL 分桶明细行；对账摘要待数据返回后展示。</span>
                ) : reconAggregate.allMatched ? (
                  <span>
                    ZQTZ 分桶对账：三桶均为「{reconciliationStatusLabels.matched}」；明细见下方「明细 /
                    对账」表。
                  </span>
                ) : (
                  <span>
                    分桶状态：
                    {(
                      Object.entries(reconAggregate.counts) as [
                        BalanceMovementRow["reconciliation_status"],
                        number,
                      ][]
                    )
                      .filter(([, count]) => count > 0)
                      .map(([status, count]) => `${reconciliationStatusLabels[status]} ${count} 条`)
                      .join("；")}
                    。请核对{" "}
                    <a href="#balance-movement-analysis-detail-anchor" className="balance-movement-inline-anchor">
                      明细 / 对账表
                    </a>
                    。
                  </span>
                )}
              </div>
            </div>
            <div className="balance-movement-conclusion__controls">
              控制科目 141 / 142 / 143 / 1440101；排除 144020 股权 OCI
            </div>
          </div>
          <div className="balance-movement-conclusion__shares">
            <span>AC {formatPct(rowByBucket.get("AC")?.current_balance_pct)}</span>
            <span>OCI {formatPct(rowByBucket.get("OCI")?.current_balance_pct)}</span>
            <span>TPL {formatPct(rowByBucket.get("TPL")?.current_balance_pct)}</span>
          </div>
          <div className="balance-movement-conclusion__note">
            本页以 CNX 总账控制数为正式口径；ZQTZ 诊断同步读取 CNX 余额表，不再回退到 CNY 辅助口径。
          </div>
          <div
            data-testid="balance-movement-analysis-diagnostic-reason"
            className="balance-movement-conclusion__note"
          >
            口径差异原因：昨晚定位的是 ZQTZ 诊断应使用 CNX 表；若误读 CNY
            辅助口径，会把综合本位币核对数和人民币辅助数相减，形成 AC / OCI / TPL 的假差异。
          </div>
          {trendComparison ? (
            <div
              data-testid="balance-movement-analysis-trend-conclusion"
              className="balance-movement-conclusion__trend"
            >
              较 {trendComparison.previousReportDate} {formatSignedYi(trendComparison.totalDelta)}
              ，主要来自{" "}
              {trendComparison.drivers
                .map((driver) => `${driver.bucket} ${formatSignedYi(driver.delta)}`)
                .join("、")}。
            </div>
          ) : null}
        </section>
      ) : null}

      {summary ? (
        <div data-testid="balance-movement-analysis-summary" style={cardGridStyle}>
          <div style={cardStyle}>
            <span style={{ color: "#5c6b82", fontSize: 12 }}>期末余额</span>
            <strong>{formatBalanceAmountToYiFromYuan(summary.current_balance_total)} 亿</strong>
          </div>
          <div style={cardStyle}>
            <span style={{ color: "#5c6b82", fontSize: 12 }}>期初余额</span>
            <strong>{formatBalanceAmountToYiFromYuan(summary.previous_balance_total)} 亿</strong>
          </div>
          <div style={cardStyle}>
            <span style={{ color: "#5c6b82", fontSize: 12 }}>余额变动</span>
            <strong>{formatBalanceAmountToYiFromYuan(summary.balance_change_total)} 亿</strong>
          </div>
          <div style={cardStyle}>
            <span style={{ color: "#5c6b82", fontSize: 12 }}>ZQTZ诊断差异</span>
            <strong>{formatBalanceAmountToYiFromYuan(summary.reconciliation_diff_total)} 亿</strong>
          </div>
        </div>
      ) : null}

      {structureMigrationAnalysis ? (
        <StructureMigrationPanel analysis={structureMigrationAnalysis} />
      ) : null}

      {differenceAttributionWaterfall ? (
        <DifferenceAttributionWaterfallPanel waterfall={differenceAttributionWaterfall} />
      ) : null}

      {basisMovementDecomposition ? (
        <BasisMovementDecompositionPanel decomposition={basisMovementDecomposition} />
      ) : null}

      {zqtzMaturityStructure ? (
        <ZqtzMaturityStructurePanel structure={zqtzMaturityStructure} />
      ) : null}

      {zqtzConcentrationAnalysis ? (
        <ZqtzConcentrationAnalysisPanel analysis={zqtzConcentrationAnalysis} />
      ) : null}

      {zqtzCalibrationAnalysis ? (
        <section
          data-testid="balance-movement-analysis-zqtz-calibration"
          className="balance-movement-zqtz-calibration"
        >
          <div className="balance-movement-zqtz-calibration__header">
            <div>
              <span>ZQTZ228 口径核对</span>
              <strong>{zqtzCalibrationAnalysis.source_file}</strong>
            </div>
            <p>{zqtzCalibrationAnalysis.conclusion}</p>
          </div>
          <div className="balance-movement-zqtz-calibration__diagnosis">
            <div>
              <span>差异定位</span>
              <p>{zqtzCalibrationAnalysis.root_cause}</p>
            </div>
            <div>
              <span>系统处理</span>
              <p>{zqtzCalibrationAnalysis.remediation}</p>
            </div>
          </div>
          <div className="balance-movement-zqtz-calibration__table-wrap">
            <table className="balance-movement-zqtz-calibration__table">
              <thead>
                <tr>
                  <th>项目</th>
                  <th>系统数（亿元）</th>
                  <th>核对表（亿元）</th>
                  <th>差异（亿元）</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                {zqtzCalibrationAnalysis.items.map((item) => (
                  <tr key={item.row_key}>
                    <td>
                      <strong>{item.row_label}</strong>
                      <span>{item.note}</span>
                    </td>
                    <td>{formatYiFixed(item.system_amount)}</td>
                    <td>{formatYiFixed(item.reference_amount)}</td>
                    <td>{formatSignedYiNumber(Number(item.diff_amount) / 100000000)}</td>
                    <td>
                      <span
                        className={`balance-movement-zqtz-calibration__status balance-movement-zqtz-calibration__status--${item.status}`}
                      >
                        {item.status === "matched" ? "一致" : "观察"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="balance-movement-zqtz-calibration__risks">
            {zqtzCalibrationAnalysis.residual_risks.map((risk) => (
              <li key={risk}>{risk}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {summary && topMovementDriver && maxShareShiftDriver ? (
        <section
          data-testid="balance-movement-analysis-business-summary"
          className="balance-movement-business-summary"
        >
          <div className="balance-movement-business-summary__headline">
            <span>分析结论</span>
            <strong>
              本月余额{movementDirection(summary.balance_change_total)}{" "}
              {formatYiFixed(Math.abs(numericValue(summary.balance_change_total)))} 亿，最大驱动是{" "}
              {topMovementDriver.bucket}
            </strong>
            <p>
              {structureStatus}，最大占比变化为 {maxShareShiftDriver.bucket}{" "}
              {formatSignedPoint(maxShareShiftDriver.shareDelta)}
            </p>
            {structureDriverHint ? (
              <p
                data-testid="balance-movement-analysis-structure-driver-hint"
                className="balance-movement-business-summary__driver-hint"
              >
                {structureDriverHint}
              </p>
            ) : null}
          </div>

          <div className="balance-movement-business-summary__facts">
            <div>
              <span>最大驱动</span>
              <p>
                {topMovementDriver.bucket} 增量最大：
                {formatSignedYiNumber(topMovementDriver.balanceChangeYi)} 亿，贡献{" "}
                {formatPct(topMovementDriver.contributionPct)}
              </p>
            </div>
            <div>
              <span>压舱石</span>
              <p>
                AC 压舱石占比{" "}
                {formatPct(rowByBucket.get("AC")?.current_balance_pct)}，较期初{" "}
                {formatSignedPoint(movementDriverByBucket.get("AC")?.shareDelta ?? 0)}
              </p>
            </div>
            <div>
              <span>配置变化</span>
              <p>
                OCI 配置占比{" "}
                {formatPct(rowByBucket.get("OCI")?.current_balance_pct)}，较期初{" "}
                {formatSignedPoint(movementDriverByBucket.get("OCI")?.shareDelta ?? 0)}
              </p>
            </div>
          </div>

          {businessTopMomMoves.length > 0 ? (
            <div
              data-testid="balance-movement-analysis-business-top-moves"
              className="balance-movement-business-summary__top-moves"
            >
              <h2>业务行Top变动（Top 5）</h2>
              <div>
                <h3>MoM Top 5</h3>
                <ol
                  data-testid="balance-movement-analysis-business-top-moves-mom"
                  className="balance-movement-business-summary__top-moves-list"
                >
                  {businessTopMomMoves.map((item, index) => (
                    <li key={`${item.rowKey}-${item.side}-${index}`}>
                      <span className="balance-movement-business-summary__top-moves-rank">{index + 1}</span>
                      <span className="balance-movement-business-summary__top-moves-label">{item.label}</span>
                      <strong className="balance-movement-business-summary__top-moves-delta">
                        {formatSignedYiNumber(item.deltaYuan / 100000000)} 亿
                      </strong>
                      <span className="balance-movement-business-summary__top-moves-side">
                        {item.side === "asset" ? "资产" : "负债"}
                      </span>
                      <span
                        data-testid="balance-movement-analysis-business-top-moves-source"
                        className="balance-movement-business-summary__top-moves-source"
                        title={item.sourceNote ?? `${item.sourceKind ?? "ledger"} source`}
                      >
                        {item.sourceKind ?? "ledger"} · {item.sourceNote ? item.sourceNote : "来源已记录"}
                      </span>
                    </li>
                  ))}
                </ol>
              </div>
              {businessTopSixMonthMoves.length > 0 ? (
                <div>
                  <h3>近{businessMatrixMonths.length}月 Top 5</h3>
                  <ol
                    data-testid="balance-movement-analysis-business-top-moves-sixmonth"
                    className="balance-movement-business-summary__top-moves-list"
                  >
                    {businessTopSixMonthMoves.map((item, index) => (
                      <li key={`${item.rowKey}-${item.side}-6m-${index}`}>
                        <span className="balance-movement-business-summary__top-moves-rank">{index + 1}</span>
                        <span className="balance-movement-business-summary__top-moves-label">{item.label}</span>
                        <strong className="balance-movement-business-summary__top-moves-delta">
                          {formatSignedYiNumber(item.deltaYuan / 100000000)} 亿
                        </strong>
                        <span className="balance-movement-business-summary__top-moves-side">
                          {item.side === "asset" ? "资产" : "负债"}
                        </span>
                        <span className="balance-movement-business-summary__top-moves-source">
                          首期 {formatSignedYiNumber(item.previousYuan / 100000000)} 亿 · 末期 {formatSignedYiNumber(item.currentYuan / 100000000)}
                        </span>
                      </li>
                    ))}
                  </ol>
                </div>
              ) : null}
            </div>
          ) : null}

          <div className="balance-movement-business-summary__body">
            <div
              data-testid="balance-movement-analysis-driver-chart"
              className="balance-movement-driver-chart"
            >
              <h2>余额变动驱动</h2>
              <ReactECharts
                option={driverChartOption}
                style={{ height: 240, width: "100%" }}
                notMerge
                lazyUpdate
              />
            </div>

            <div
              data-testid="balance-movement-analysis-driver-ranking"
              className="balance-movement-driver-ranking"
            >
              <h2>贡献排序</h2>
              {movementDrivers.map((driver, index) => (
                <div key={driver.bucket} className="balance-movement-driver-ranking__row">
                  <span>{index + 1}</span>
                  <strong>
                    {driver.bucket} {formatSignedYiNumber(driver.balanceChangeYi)} 亿{" "}
                    {formatPct(driver.contributionPct)}
                  </strong>
                </div>
              ))}
            </div>

            <div
              data-testid="balance-movement-analysis-structure-shift"
              className="balance-movement-structure-shift"
            >
              <h2>期初到期末结构变化</h2>
              {balanceMovementBuckets.map((bucket) => {
                const driver = movementDrivers.find((item) => item.bucket === bucket);
                if (!driver) return null;
                return (
                  <div key={bucket} className="balance-movement-structure-shift__row">
                    <div>
                      <strong>{bucket}</strong>
                      <span>
                        期初 {formatPct(driver.previousBalancePct)} 期末{" "}
                        {formatPct(driver.currentBalancePct)}
                      </span>
                    </div>
                    <div className="balance-movement-structure-shift__track">
                      <span
                        className="balance-movement-structure-shift__previous"
                        style={{
                          width: `${Math.min(Math.max(driver.previousBalancePct, 1), 100)}%`,
                        }}
                      />
                      <span
                        className="balance-movement-structure-shift__current"
                        style={{
                          width: `${Math.min(Math.max(driver.currentBalancePct, 1), 100)}%`,
                        }}
                      />
                    </div>
                    <em>{formatSignedPoint(driver.shareDelta)}</em>
                  </div>
                );
              })}
            </div>
          </div>
        </section>
      ) : null}

      {zqtzAssetDetailRows.length > 0 ? (
        <section
          data-testid="balance-movement-analysis-zqtz-detail"
          className="balance-movement-zqtz-detail-page"
        >
          <div className="balance-movement-zqtz-detail-page__header">
            <div>
              <span>单独页</span>
              <strong>金融投资资产明细变动</strong>
            </div>
            <p>
              对应 ZQTZSHOW 资产项目和长期股权投资明细，按月份展开；“其中”项单独列示，不与上级分类重复加总。
            </p>
          </div>
          <div className="balance-movement-zqtz-detail-page__table-wrap">
            <table className="balance-movement-zqtz-detail-page__table">
              <thead>
                <tr>
                  <th scope="col">明细项目</th>
                  {businessMatrixMonths.map((month) => (
                    <th key={month.report_date} scope="col">
                      {formatTrendMonthLabel(month.report_month)}
                    </th>
                  ))}
                  <th scope="col">较上月</th>
                  <th scope="col">较年初</th>
                </tr>
              </thead>
              <tbody>
                {zqtzAssetDetailRows.map((row) => {
                  const mom = compareBusinessMatrixCell(businessMatrixMonths, row, 1);
                  const ytd = compareBusinessMatrixCellToFirst(businessMatrixMonths, row);
                  return (
                    <tr
                      key={row.key}
                      className={row.isSubItem ? "balance-movement-zqtz-detail-page__row--subitem" : undefined}
                    >
                      <th scope="row" title={row.sourceNote}>
                        {row.label}
                      </th>
                      {businessMatrixMonths.map((month) => (
                        <td key={`${row.key}-${month.report_date}`}>
                          {formatMatrixValue(row.getValue(month), "amount", true)}
                        </td>
                      ))}
                      <td className={matrixDeltaTone(mom)}>{mom}</td>
                      <td className={matrixDeltaTone(ytd)}>{ytd}</td>
                    </tr>
                  );
                })}
                {zqtzAssetDetailSummaryRow
                  ? (() => {
                      const mom = compareBusinessMatrixCell(businessMatrixMonths, zqtzAssetDetailSummaryRow, 1);
                      const ytd = compareBusinessMatrixCellToFirst(
                        businessMatrixMonths,
                        zqtzAssetDetailSummaryRow,
                      );
                      return (
                        <tr
                          key={zqtzAssetDetailSummaryRow.key}
                          className="balance-movement-zqtz-detail-page__row--summary"
                        >
                          <th scope="row" title={zqtzAssetDetailSummaryRow.sourceNote}>
                            {zqtzAssetDetailSummaryRow.label}
                          </th>
                          {businessMatrixMonths.map((month) => (
                            <td key={`${zqtzAssetDetailSummaryRow.key}-${month.report_date}`}>
                              {formatMatrixValue(zqtzAssetDetailSummaryRow.getValue(month), "amount", true)}
                            </td>
                          ))}
                          <td className={matrixDeltaTone(mom)}>{mom}</td>
                          <td className={matrixDeltaTone(ytd)}>{ytd}</td>
                        </tr>
                      );
                    })()
                  : null}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {businessTrendMonths.length > 0 ? (
        <AsyncSection
          title="月度余额分析矩阵"
          extra={
            <span className="balance-movement-matrix-unit-hint">
              各月末为账面余额；「较上月」「较年初」为变动额。单位：亿元
            </span>
          }
          isLoading={detailQuery.isLoading}
          isError={detailQuery.isError}
          isEmpty={businessTrendMonths.length === 0}
          onRetry={() => void detailQuery.refetch()}
        >
          <div
            className="balance-movement-pre-matrix-notes"
            data-testid="balance-movement-analysis-pre-matrix-notes"
          >
            <p
              data-testid="balance-movement-analysis-slice-note"
              className="balance-movement-pre-matrix-notes__slice"
            >
              口径说明：上方总账 AC/OCI/TPL 来自控制科目切片；下方「月度余额分析矩阵」中业务行与同业合计为另一套分类，数值不应与三桶简单加减比对是否相等。
            </p>
            <div
              data-testid="balance-movement-analysis-series-context"
              className="balance-movement-pre-matrix-notes__series"
            >
              {seriesContextSegments.map((text, index) => (
                <p key={index}>{text}</p>
              ))}
              <p className="balance-movement-pre-matrix-notes__footer">
                自然年首月基期、业务矩阵同比、分桶 ZQTZ 差异历史走势等依赖更长期物化或专用接口；当前页仅展示既有读模型，不在浏览器端补算正式口径。
              </p>
            </div>
          </div>
          <div className="balance-movement-matrix-scroll">
            <table
              data-testid="balance-movement-analysis-trend-table"
              className="balance-movement-report-matrix balance-movement-report-matrix--monthly"
            >
              <thead>
                <tr>
                  <th scope="col">分类</th>
                  {businessMatrixMonths.map((month) => (
                    <th key={month.report_date} scope="col">
                      {formatTrendMonthLabel(month.report_month)}
                    </th>
                  ))}
                  <th scope="col">较上月</th>
                  <th scope="col">较年初</th>
                </tr>
              </thead>
              <tbody>
                {monthlyMatrixCategoryRows.map((row) => {
                  const mom = compareBusinessMatrixCell(businessMatrixMonths, row, 1);
                  const ytd = compareBusinessMatrixCellToFirst(businessMatrixMonths, row);
                  return (
                    <tr
                      key={row.key}
                      data-side={row.side}
                      className={row.emphasis ? "balance-movement-report-matrix__row--emphasis" : undefined}
                    >
                      <th scope="row" title={row.sourceNote}>
                        {row.label}
                      </th>
                      {businessMatrixMonths.map((month) => (
                        <td key={`${row.key}-${month.report_date}`}>
                          {formatMatrixValue(row.getValue(month), row.valueKind, true)}
                        </td>
                      ))}
                      <td className={matrixDeltaTone(mom)}>{mom}</td>
                      <td className={matrixDeltaTone(ytd)}>{ytd}</td>
                    </tr>
                  );
                })}
                <tr className="balance-movement-report-matrix__gap" aria-hidden>
                  <td colSpan={businessMatrixMonths.length + 3} />
                </tr>
                <tr className="balance-movement-report-matrix__section-cap">
                  <td colSpan={businessMatrixMonths.length + 3}>合计与净额</td>
                </tr>
                <tr className="balance-movement-report-matrix__subhead">
                  <th scope="col">项目</th>
                  {businessMatrixMonths.map((month) => (
                    <th key={`project-${month.report_date}`} scope="col">
                      {formatTrendMonthLabel(month.report_month)}
                    </th>
                  ))}
                  <th scope="col">较上月</th>
                  <th scope="col">较年初</th>
                </tr>
                {businessProjectTableRows.map((row) => {
                  const mom = compareBusinessMatrixCell(businessMatrixMonths, row, 1);
                  const ytd = compareBusinessMatrixCellToFirst(businessMatrixMonths, row);
                  return (
                    <tr
                      key={row.key}
                      data-side={row.side}
                      className={row.emphasis ? "balance-movement-report-matrix__row--emphasis" : undefined}
                    >
                      <th scope="row" title={row.sourceNote}>
                        {row.label}
                      </th>
                      {businessMatrixMonths.map((month) => (
                        <td key={`${row.key}-${month.report_date}`}>
                          {formatMatrixValue(row.getValue(month), row.valueKind, true)}
                        </td>
                      ))}
                      <td className={matrixDeltaTone(mom)}>{mom}</td>
                      <td className={matrixDeltaTone(ytd)}>{ytd}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div
            className="balance-movement-structure-chart"
            data-testid="balance-movement-analysis-structure-chart"
          >
            <AccountingBasisStackedShareChart
              rows={balanceStructureTrend}
              title="金融投资账户结构演变：余额口径"
            />
            {balanceStructureTrend.length > 0 ? (
              <>
                <p
                  className="balance-movement-share-evolution-table__title"
                  data-testid="balance-movement-analysis-structure-share-table-title"
                >
                  结构占比明细（与上图一致，余额口径）
                </p>
                <p className="balance-movement-share-evolution-table__note">
                  环比为时间序列中相对<strong>上一行月份</strong>的变动；同比为相对<strong>上年同月</strong>（近 6
                  个月趋势中含该月时显示，否则为 —）。
                </p>
                <div
                  className="balance-movement-share-evolution-table-scroll"
                  data-testid="balance-movement-analysis-structure-share-table"
                >
                  <table className="balance-movement-share-evolution-table">
                    <thead>
                      <tr>
                        <th scope="col">月份</th>
                        <th scope="col">AC（%）</th>
                        <th scope="col">OCI（%）</th>
                        <th scope="col">TPL（%）</th>
                        <th scope="col">合计（亿）</th>
                        <th scope="col">AC（亿）</th>
                        <th scope="col">OCI（亿）</th>
                        <th scope="col">TPL（亿）</th>
                        <th scope="col">环比·AC</th>
                        <th scope="col">环比·OCI</th>
                        <th scope="col">环比·TPL</th>
                        <th scope="col">环比·合计</th>
                        <th scope="col">同比·AC</th>
                        <th scope="col">同比·OCI</th>
                        <th scope="col">同比·TPL</th>
                        <th scope="col">同比·合计</th>
                        {balanceStructureTrend.length > 1 ? (
                          <>
                            <th scope="col">较首月·AC</th>
                            <th scope="col">较首月·OCI</th>
                            <th scope="col">较首月·TPL</th>
                          </>
                        ) : null}
                      </tr>
                    </thead>
                    <tbody>
                      {structureShareTableRows.map((item, index) => {
                        const { point, reportMonth } = item;
                        const first = structureShareTableRows[0];
                        const prev = index > 0 ? structureShareTableRows[index - 1] : null;
                        const yoyKey = priorYearSameMonth(reportMonth);
                        const yoy = yoyKey ? shareRowByReportMonth.get(yoyKey) : undefined;
                        const showFirstDelta = balanceStructureTrend.length > 1 && first !== undefined;
                        return (
                          <tr key={point.monthLabel}>
                            <th scope="row">{point.monthLabel}</th>
                            <td>{formatShareEvolutionPct(point.AC)}</td>
                            <td>{formatShareEvolutionPct(point.OCI)}</td>
                            <td>{formatShareEvolutionPct(point.TPL)}</td>
                            <td>{formatShareEvolutionYi(point.totalValueYi)}</td>
                            <td>{formatShareEvolutionYi(point.acValueYi)}</td>
                            <td>{formatShareEvolutionYi(point.ociValueYi)}</td>
                            <td>{formatShareEvolutionYi(point.tplValueYi)}</td>
                            <td>
                              {prev
                                ? formatSignedPoint(point.AC - prev.point.AC)
                                : "—"}
                            </td>
                            <td>
                              {prev
                                ? formatSignedPoint(point.OCI - prev.point.OCI)
                                : "—"}
                            </td>
                            <td>
                              {prev
                                ? formatSignedPoint(point.TPL - prev.point.TPL)
                                : "—"}
                            </td>
                            <td>
                              {formatSignedYiDelta(
                                point.totalValueYi,
                                prev?.point.totalValueYi,
                              )}
                            </td>
                            <td>
                              {yoy
                                ? formatSignedPoint(point.AC - yoy.point.AC)
                                : "—"}
                            </td>
                            <td>
                              {yoy
                                ? formatSignedPoint(point.OCI - yoy.point.OCI)
                                : "—"}
                            </td>
                            <td>
                              {yoy
                                ? formatSignedPoint(point.TPL - yoy.point.TPL)
                                : "—"}
                            </td>
                            <td>
                              {formatSignedYiDelta(
                                point.totalValueYi,
                                yoy?.point.totalValueYi,
                              )}
                            </td>
                            {showFirstDelta ? (
                              <>
                                <td>{formatSignedPoint(point.AC - first.point.AC)}</td>
                                <td>{formatSignedPoint(point.OCI - first.point.OCI)}</td>
                                <td>{formatSignedPoint(point.TPL - first.point.TPL)}</td>
                              </>
                            ) : null}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </>
            ) : null}
            {balanceStructureInsight ? (
              <div
                className="balance-movement-structure-chart__insight"
                data-testid="balance-movement-analysis-structure-insight"
              >
                {balanceStructureInsight}
              </div>
            ) : null}
          </div>
        </AsyncSection>
      ) : null}

      <div id="balance-movement-analysis-detail-anchor">
        <AsyncSection
          title="明细 / 对账：AC / OCI / TPL 余额变动"
          isLoading={detailQuery.isLoading}
          isError={detailQuery.isError}
          isEmpty={!detailQuery.isLoading && !detailQuery.isError && rows.length === 0}
          onRetry={() => void detailQuery.refetch()}
        >
          <div style={{ overflowX: "auto" }}>
            <table
              data-testid="balance-movement-analysis-table"
              style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}
            >
            <thead>
              <tr style={{ textAlign: "left", borderBottom: "1px solid #d7dfea" }}>
                <th style={{ padding: "12px 8px" }}>分类</th>
                <th style={tableCellStyle}>期初余额(亿)</th>
                <th style={tableCellStyle}>期初占比</th>
                <th style={tableCellStyle}>期末余额(亿)</th>
                <th style={tableCellStyle}>期末占比</th>
                <th className="balance-movement-detail-table__num">占比变动</th>
                <th style={tableCellStyle}>变动(亿)</th>
                <th style={tableCellStyle}>变动率</th>
                <th style={tableCellStyle}>变动贡献</th>
                <th style={tableCellStyle}>ZQTZ辅助(亿)</th>
                <th style={tableCellStyle}>ZQTZ诊断差异(亿)</th>
                <th style={tableCellStyle}>状态</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.basis_bucket}>
                  <td style={{ ...tableCellStyle, textAlign: "left", fontWeight: 700 }}>
                    {bucketLabels[row.basis_bucket] ?? row.basis_bucket}
                  </td>
                  <td style={tableCellStyle}>
                    {formatBalanceAmountToYiFromYuan(row.previous_balance)}
                  </td>
                  <td style={tableCellStyle}>{formatPct(row.previous_balance_pct)}</td>
                  <td style={tableCellStyle}>
                    {formatBalanceAmountToYiFromYuan(row.current_balance)}
                  </td>
                  <td style={tableCellStyle}>{formatPct(row.current_balance_pct)}</td>
                  <td className="balance-movement-detail-table__num">
                    {formatSignedPoint(shareDeltaPp(row))}
                  </td>
                  <td style={tableCellStyle}>
                    {formatBalanceAmountToYiFromYuan(row.balance_change)}
                  </td>
                  <td style={tableCellStyle}>{formatPct(row.change_pct)}</td>
                  <td style={tableCellStyle}>{formatPct(row.contribution_pct)}</td>
                  <td style={tableCellStyle}>{formatBalanceAmountToYiFromYuan(row.zqtz_amount)}</td>
                  <td style={tableCellStyle}>
                    {formatBalanceAmountToYiFromYuan(row.reconciliation_diff)}
                  </td>
                  <td style={{ ...tableCellStyle, color: statusTone(row.reconciliation_status) }}>
                    {row.reconciliation_status}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </AsyncSection>
      </div>

      {detailQuery.data?.result.accounting_controls ? (
        <div
          data-testid="balance-movement-analysis-controls"
          style={{ marginTop: 14, color: "#5c6b82", fontSize: 12 }}
        >
          控制科目：{detailQuery.data.result.accounting_controls.join(", ")}；排除：
          {detailQuery.data.result.excluded_controls.join(", ")}
        </div>
      ) : null}

      {detailQuery.data?.result ? (
        <div data-testid="balance-movement-analysis-governance" className="balance-movement-governance-line">
          读模型报告日：{governanceMeta.reportDate || "—"}
          {" · "}
          rule_version：{governanceMeta.ruleVersions.length ? governanceMeta.ruleVersions.join("、") : "—"}
          {" · "}
          source_version：
          {governanceMeta.sourceVersions.length ? governanceMeta.sourceVersions.join("、") : "—"}
        </div>
      ) : null}
    </section>
  );
}
