import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { useApiClient } from "../../../api/client";
import type {
  BalanceMovementDatesPayload,
  BalanceMovementPayload,
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
  ResultMeta,
} from "../../../api/contracts";
import type { AccountingBasisStackedSharePoint } from "../../../components/charts/AccountingBasisStackedShareChart";
import { DataQualityBanner } from "../../../components/page/DataQualityBanner";

import { formatBalanceAmountToYiFromYuan } from "../../balance-analysis/pages/balanceAnalysisPageModel";
import { ReconciliationStatusTag } from "../components/ReconciliationStatusTag";
import {
  chainStatusLabel,
  counterpartyAmountText,
  countReconciliationStatuses,
  reconciliationConcernLabel,
  reconciliationTieoutSummary,
  statusToneClass,
} from "../lib/balanceMovementReconciliationModel";
import {
  nullableNumber,
  resolveBucketSharePct,
} from "../lib/balanceMovementShareModel";

import { EM_DASH, formatYuanAmountAsYiPlain } from "../../../utils/format";
import "./BalanceMovementAnalysisPage.css";
import "./BalanceMovementAnalysisFigma.css";

const bucketLabels: Record<string, string> = {
  AC: "AC",
  OCI: "OCI",
  TPL: "TPL",
};

const balanceMovementBuckets: BalanceMovementRow["basis_bucket"][] = ["AC", "OCI", "TPL"];

function normalizeMovementCurrencyBasis(_value: string | null): "CNX" {
  return "CNX";
}

function formatPct(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return EM_DASH;
  }
  const n = Number(value);
  if (!Number.isFinite(n)) {
    return String(value);
  }
  return `${n.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
}

/**
 * 2026-08-13 债务清零：本地元→亿实现并入共享 formatYuanAmountAsYiPlain
 * （输出一致：zh-CN 分组、固定 2 位、缺失 EM_DASH、无效串原样透出）。
 * 全部调用点均为 2 位小数，故收敛为无 digits 参数的委托。
 */
function formatYiFixed(value: string | number | null | undefined) {
  return formatYuanAmountAsYiPlain(value);
}

function formatSignedYi(value: string | number | null | undefined, digits = 2) {
  if (value === null || value === undefined || value === "") {
    return EM_DASH;
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
    return EM_DASH;
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
  return formatYiFixed(value);
}

function formatSignedYiCell(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return EM_DASH;
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
  if (formatted === EM_DASH) {
    return formatted;
  }
  return omitUnit ? formatted : `${formatted} 亿`;
}

function formatMatrixCellWithMissing(
  value: string | number | null | undefined,
  valueKind: BalanceMovementMatrixValueKind,
  omitUnit: boolean,
  hasMissingInputs?: boolean,
) {
  if (value === null || value === undefined || value === "") {
    return EM_DASH;
  }
  const formatted = formatMatrixValue(value, valueKind, omitUnit);
  if (hasMissingInputs && formatted !== EM_DASH) {
    return `${formatted}*`;
  }
  return formatted;
}

function formatSignedPercentPoint(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return EM_DASH;
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
  if (formatted === EM_DASH) {
    return formatted;
  }
  return omitUnit ? formatted : `${formatted} 亿`;
}

type MatrixRowSumResult = {
  value: number | null;
  hasMissingInputs: boolean;
};

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
  getCellMeta?: (
    month: BalanceBusinessMovementTrendMonth,
  ) => { hasMissingInputs?: boolean } | undefined;
};

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
    return EM_DASH;
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
    return EM_DASH;
  }
  return formatSignedMatrixValue(
    trendDelta(row.getValue(currentMonth), row.getValue(firstMonth)),
    row.valueKind,
    true,
  );
}

function aggregateBucketReconciliation(rows: BalanceMovementRow[]) {
  const counts = countReconciliationStatuses(rows);
  const bucketCounts = new Map<BalanceMovementRow["basis_bucket"], number>();
  for (const row of rows) {
    bucketCounts.set(row.basis_bucket, (bucketCounts.get(row.basis_bucket) ?? 0) + 1);
  }
  const hasExactBuckets =
    bucketCounts.size === balanceMovementBuckets.length &&
    balanceMovementBuckets.every((bucket) => bucketCounts.get(bucket) === 1);
  const allMatched =
    hasExactBuckets && rows.every((row) => row.reconciliation_status === "matched");
  return { counts, allMatched, hasExactBuckets };
}

function accountingBasisNarrativeLabel(bucket: BalanceMovementRow["basis_bucket"]) {
  return bucket === "TPL" ? "FVTPL" : bucket;
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
  getCellMeta?: (
    month: BalanceBusinessMovementTrendMonth,
  ) => { hasMissingInputs?: boolean } | undefined;
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

function sumMatrixRowValues(
  month: BalanceBusinessMovementTrendMonth,
  rows: Array<{ getValue: ZqtzAssetDetailRow["getValue"]; isSubItem?: boolean }>,
  options?: { excludeSubItems?: boolean },
): MatrixRowSumResult {
  let total = 0;
  let finiteCount = 0;
  let missingCount = 0;
  for (const row of rows) {
    if (options?.excludeSubItems && row.isSubItem) {
      continue;
    }
    const raw = row.getValue(month);
    if (raw === null || raw === undefined || raw === "") {
      missingCount += 1;
      continue;
    }
    const value = Number(raw);
    if (!Number.isFinite(value)) {
      missingCount += 1;
      continue;
    }
    total += value;
    finiteCount += 1;
  }
  return {
    value: finiteCount > 0 ? total : null,
    hasMissingInputs: missingCount > 0,
  };
}

function sumPrimaryZqtzAssetDetailRows(
  month: BalanceBusinessMovementTrendMonth,
  rows: ZqtzAssetDetailRow[],
): MatrixRowSumResult {
  return sumMatrixRowValues(month, rows, { excludeSubItems: true });
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
  if (t === "" || t === EM_DASH || t === "-") {
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
): MatrixRowSumResult {
  return sumMatrixRowValues(month, rows);
}

function formatTrendAxisMonth(reportMonth: string) {
  const [year, month] = reportMonth.split("-");
  const monthNumber = Number(month);
  if (!year || !Number.isFinite(monthNumber)) {
    return reportMonth;
  }
  return `${year.slice(2)}-${String(monthNumber).padStart(2, "0")}`;
}

type BalanceStructureSharePoint = {
  monthLabel: string;
  AC: number | null;
  OCI: number | null;
  TPL: number | null;
  acValueYi?: number;
  ociValueYi?: number;
  tplValueYi?: number;
  totalValueYi?: number;
};

function toSharePoint(month: BalanceMovementTrendMonth): BalanceStructureSharePoint {
  const total = Number(month.current_balance_total);
  const point: BalanceStructureSharePoint = {
    monthLabel: formatTrendAxisMonth(month.report_month),
    AC: null,
    OCI: null,
    TPL: null,
    totalValueYi: Number.isFinite(total) ? total / 100000000 : undefined,
  };
  for (const bucket of balanceMovementBuckets) {
    const row = trendBucket(month, bucket);
    const value = Number(row?.current_balance);
    point[bucket] = resolveBucketSharePct(row?.current_balance_pct);
    if (bucket === "AC") point.acValueYi = Number.isFinite(value) ? value / 100000000 : undefined;
    if (bucket === "OCI") point.ociValueYi = Number.isFinite(value) ? value / 100000000 : undefined;
    if (bucket === "TPL") point.tplValueYi = Number.isFinite(value) ? value / 100000000 : undefined;
  }
  return point;
}

function toCompleteSharePoint(
  point: BalanceStructureSharePoint,
): AccountingBasisStackedSharePoint | null {
  const { AC, OCI, TPL } = point;
  if (
    AC === null ||
    OCI === null ||
    TPL === null ||
    !Number.isFinite(AC) ||
    !Number.isFinite(OCI) ||
    !Number.isFinite(TPL)
  ) {
    return null;
  }
  return { ...point, AC, OCI, TPL };
}

function formatSignedPoint(value: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}pp`;
}

function formatSignedPointNullable(value: number | null | undefined) {
  return value === null || value === undefined || !Number.isFinite(value)
    ? EM_DASH
    : formatSignedPoint(value);
}

function nullableDelta(
  current: number | null | undefined,
  base: number | null | undefined,
): number | null {
  if (
    current === null ||
    current === undefined ||
    base === null ||
    base === undefined ||
    !Number.isFinite(current) ||
    !Number.isFinite(base)
  ) {
    return null;
  }
  return current - base;
}

function formatShareEvolutionPct(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return EM_DASH;
  }
  return `${value.toFixed(2)}%`;
}

function formatShareEvolutionYi(value: number | undefined) {
  if (value === undefined || !Number.isFinite(value)) {
    return EM_DASH;
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
    return EM_DASH;
  }
  const d = current - base;
  const sign = d > 0 ? "+" : "";
  return `${sign}${d.toFixed(2)} 亿`;
}

type StructureShareTableRow = {
  point: BalanceStructureSharePoint;
  reportMonth: string;
};

function numericValue(value: string | number | null | undefined) {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function shareDeltaPp(row: BalanceMovementRow): number | null {
  return nullableDelta(
    nullableNumber(row.current_balance_pct),
    nullableNumber(row.previous_balance_pct),
  );
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

type BalanceMovementDriver = {
  bucket: BalanceMovementRow["basis_bucket"];
  balanceChange: number;
  balanceChangeYi: number;
  contributionPct: number | null;
  currentBalancePct: number | null;
  previousBalancePct: number | null;
  shareDelta: number | null;
};

function toMovementDriver(row: BalanceMovementRow): BalanceMovementDriver {
  const balanceChange = numericValue(row.balance_change);
  const currentBalancePct = nullableNumber(row.current_balance_pct);
  const previousBalancePct = nullableNumber(row.previous_balance_pct);
  return {
    bucket: row.basis_bucket,
    balanceChange,
    balanceChangeYi: balanceChange / 100000000,
    contributionPct: nullableNumber(row.contribution_pct),
    currentBalancePct,
    previousBalancePct,
    shareDelta: nullableDelta(currentBalancePct, previousBalancePct),
  };
}

function formatSignedYiNumber(value: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function sourceKindLabel(sourceKind: BusinessMomMove["sourceKind"]) {
  return sourceKind === "zqtz" ? "证券投资辅助" : "总账";
}

function moveDeltaToneClass(value: number | null) {
  // 缺失≠零：null 不得套用持平色阶，只有有限数值才有方向/持平色。
  if (value === null) {
    return "";
  }
  if (value > 0) {
    return "balance-movement-top-moves-table__delta balance-movement-top-moves-table__delta--up";
  }
  if (value < 0) {
    return "balance-movement-top-moves-table__delta balance-movement-top-moves-table__delta--down";
  }
  return "balance-movement-top-moves-table__delta";
}

function sourceNotePreview(sourceNote: string | undefined) {
  if (!sourceNote) {
    return "来源已记录";
  }
  return sourceNote.replace(/\s+/g, " ").trim();
}

function movementDirection(value: string | number | null | undefined) {
  const n = finiteMetric(value);
  if (n === null) return EM_DASH;
  if (n > 0) return "增加";
  if (n < 0) return "减少";
  return "持平";
}

function formatMetaList(values: string[] | undefined) {
  return values && values.length > 0 ? values.join("、") : EM_DASH;
}

function csvCell(value: string | number | boolean | null | undefined) {
  if (value === null || value === undefined) {
    return "";
  }
  const text = String(value);
  if (/[",\r\n]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

function buildCsv(rows: Array<Array<string | number | boolean | null | undefined>>) {
  return rows.map((row) => row.map(csvCell).join(",")).join("\r\n");
}

function downloadCsv(filename: string, content: string) {
  const blob = new Blob(["\uFEFF", content], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function buildBalanceMovementCsv(options: {
  result: BalanceMovementPayload;
  resultMeta: ResultMeta | null;
  businessTopMove: BusinessMomMove | undefined;
  accountingTopDriver: BalanceMovementDriver | undefined;
  residualComponent: BalanceDifferenceAttributionWaterfall["components"][number] | undefined;
  unsupportedComponents: BalanceDifferenceAttributionWaterfall["components"];
  maturityStructure: BalanceZqtzMaturityStructure | null;
  concentrationAnalysis: BalanceZqtzConcentrationAnalysis | null;
  explanationClosure: BalanceExplanationClosure | null;
  dimensionCards: AnalysisDimensionCard[];
  historicalAnomalyDiagnostics: HistoricalAnomalyDiagnostics;
}) {
  const {
    result,
    resultMeta,
    businessTopMove,
    accountingTopDriver,
    residualComponent,
    unsupportedComponents,
    maturityStructure,
    concentrationAnalysis,
    explanationClosure,
    dimensionCards,
    historicalAnomalyDiagnostics,
  } = options;
  const residualRatioText =
    explanationClosure?.residualRatioPct === null ||
    explanationClosure?.residualRatioPct === undefined
      ? ""
      : formatPct(explanationClosure.residualRatioPct);
  const csvRows: Array<Array<string | number | boolean | null | undefined>> = [
    ["section", "field", "value", "note"],
    ["meta", "report_date", result.report_date, ""],
    ["meta", "currency_basis", result.currency_basis, ""],
    ["meta", "quality_flag", resultMeta?.quality_flag, ""],
    ["meta", "trace_id", resultMeta?.trace_id, ""],
    ["meta", "rule_version", resultMeta?.rule_version, ""],
    ["meta", "source_version", resultMeta?.source_version, ""],
    ["meta", "tables_used", resultMeta?.tables_used?.join(";"), ""],
    ["meta", "evidence_rows", resultMeta?.evidence_rows, ""],
    [
      "dimension",
      "business_top_move",
      businessTopMove
        ? `${businessTopMove.label} ${formatSignedYiCell(businessTopMove.deltaYuan)} 亿`
        : "",
      businessTopMove ? sourceNotePreview(businessTopMove.sourceNote) : "",
    ],
    [
      "dimension",
      "accounting_basis_top_move",
      accountingTopDriver
        ? `${accountingTopDriver.bucket} ${formatSignedYiNumber(accountingTopDriver.balanceChangeYi)} 亿`
        : "",
      accountingTopDriver ? `contribution_pct=${formatPct(accountingTopDriver.contributionPct)}` : "",
    ],
    [
      "dimension",
      "residual_unclassified",
      residualComponent ? `${formatSignedYiCell(residualComponent.amount)} 亿` : "",
      "未分类残差只用于闭合，不反推估值差或外币折算差。",
    ],
    [
      "dimension",
      "unsupported_components",
      unsupportedComponents.map((component) => component.component_label).join(";"),
      "未支持，不反推。",
    ],
    [
      "dimension",
      "maturity_coverage",
      maturityStructure ? formatPct(maturityStructure.meta.coverage_pct) : "",
      maturityStructure?.meta.status ?? "",
    ],
    [
      "dimension",
      "concentration_coverage",
      concentrationAnalysis ? formatPct(concentrationAnalysis.meta.coverage_pct) : "",
      concentrationAnalysis?.meta.status ?? "",
    ],
    [
      "diagnostic",
      "explanation_closure",
      explanationClosure?.headline,
      explanationClosure?.note,
    ],
    [
      "diagnostic",
      "residual_ratio",
      residualRatioText,
      "页面诊断阈值，不是正式指标",
    ],
    ...dimensionCards.flatMap((card) =>
      card.tags.map((tag) => ["diagnostic", `${card.key}_tag`, tag.label, tag.tone]),
    ),
    [
      "historical_anomaly",
      "headline",
      historicalAnomalyDiagnostics.headline,
      "页面诊断提示，不是正式风险指标",
    ],
    [
      "historical_anomaly",
      "sample_count",
      historicalAnomalyDiagnostics.sampleCount,
      historicalAnomalyDiagnostics.baselinePairCount > 0
        ? `baseline_pairs=${historicalAnomalyDiagnostics.baselinePairCount}`
        : "历史样本不足",
    ],
    ...historicalAnomalyDiagnostics.accountingSignals.map((signal) => [
      "historical_anomaly",
      `accounting_${signal.bucket}`,
      `${formatSignedYiCell(signal.currentDelta)} 亿`,
      `${signal.headline}${signal.directionReversal ? "；方向反转" : ""}`,
    ]),
    ...historicalAnomalyDiagnostics.businessSignals.map((signal) => [
      "historical_anomaly",
      "business_move",
      `${signal.label} ${formatSignedYiCell(signal.currentDelta)} 亿`,
      `高于近 ${signal.baselineCount} 期常态`,
    ]),
    [],
    [
      "basis_bucket",
      "previous_balance_yi",
      "current_balance_yi",
      "balance_change_yi",
      "contribution_pct",
      "reconciliation_status",
      "chain_status",
      "position_source_basis",
    ],
    ...result.rows.map((row) => [
      row.basis_bucket,
      formatYiCell(row.previous_balance),
      formatYiCell(row.current_balance),
      formatSignedYiCell(row.balance_change),
      formatPct(row.contribution_pct),
      row.reconciliation_status,
      row.chain_status ?? "",
      row.position_source_basis ?? "",
    ]),
    [],
    ["waterfall_component", "label", "value", "note"],
    ...(result.difference_attribution_waterfall?.components ?? []).map((component) => [
      component.component_key,
      component.component_label,
      component.is_supported === false ? "待拆分" : `${formatSignedYiCell(component.amount)} 亿`,
      component.evidence_note,
    ]),
  ];
  return `${buildCsv(csvRows)}\r\n`;
}

type BalanceDiagnosticTone = "ok" | "info" | "warn" | "critical" | "unknown";

type BalanceDiagnosticTag = {
  label: string;
  tone: BalanceDiagnosticTone;
};

type BalanceEvidenceItem = {
  label: string;
  value: string;
  note?: string;
};

type BalanceExplanationClosure = {
  tone: BalanceDiagnosticTone;
  headline: string;
  supportedComponents: BalanceDifferenceAttributionWaterfall["components"];
  unsupportedComponents: BalanceDifferenceAttributionWaterfall["components"];
  residualComponent?: BalanceDifferenceAttributionWaterfall["components"][number];
  residualRatioPct: number | null;
  note: string;
};

type AnalysisDimensionCard = {
  key: string;
  title: string;
  metric: string;
  detail: string;
  href: string;
  tags: BalanceDiagnosticTag[];
  evidence: BalanceEvidenceItem[];
};

function amountToNumber(value: string | number | null | undefined) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function buildExplanationClosure(options: {
  waterfall: BalanceDifferenceAttributionWaterfall | null;
  summary: BalanceMovementPayload["summary"] | null;
}): BalanceExplanationClosure | null {
  const { waterfall, summary } = options;
  if (!waterfall) {
    return null;
  }
  const supportedComponents = waterfall.components.filter(
    (component) => component.is_supported !== false && !component.is_residual,
  );
  const unsupportedComponents = waterfall.components.filter(
    (component) => component.is_supported === false,
  );
  const residualComponent = waterfall.components.find((component) => component.is_residual);
  const residualAmount = amountToNumber(residualComponent?.amount);
  const totalChange = amountToNumber(summary?.balance_change_total);
  const residualRatioPct =
    residualAmount !== null && totalChange !== null && Math.abs(totalChange) > 0
      ? (Math.abs(residualAmount) / Math.abs(totalChange)) * 100
      : null;

  if (unsupportedComponents.length > 0) {
    return {
      tone: residualRatioPct !== null && residualRatioPct > 2 ? "critical" : "warn",
      headline: "存在待补口径，不能反推为已解释",
      supportedComponents,
      unsupportedComponents,
      residualComponent,
      residualRatioPct,
      note: "估值差和外币折算差缺少可闭合字段；页面只展示后端已返回的证据项。",
    };
  }

  return {
    tone: residualRatioPct !== null && residualRatioPct > 2 ? "warn" : "ok",
    headline: "现有瀑布项可用于本页解释闭合",
    supportedComponents,
    unsupportedComponents,
    residualComponent,
    residualRatioPct,
    note: "该判断是页面诊断提示，不替代正式审计归因。",
  };
}

function coverageTone(value: string | number | null | undefined): BalanceDiagnosticTone {
  const coverage = amountToNumber(value);
  if (coverage === null) {
    return "unknown";
  }
  if (coverage < 80) {
    return "critical";
  }
  if (coverage < 95) {
    return "warn";
  }
  return "ok";
}

function residualTone(ratioPct: number | null, unsupportedCount: number): BalanceDiagnosticTone {
  if (unsupportedCount > 0) {
    return "warn";
  }
  if (ratioPct !== null && ratioPct > 2) {
    return "warn";
  }
  return "ok";
}

type HistoricalAccountingSignal = {
  bucket: BalanceMovementRow["basis_bucket"];
  headline: string;
  currentDelta: number;
  baselineAverageAbs: number | null;
  baselineCount: number;
  directionReversal: boolean;
};

type HistoricalBusinessSignal = {
  label: string;
  currentDelta: number;
  baselineAverageAbs: number | null;
  baselineCount: number;
};

type HistoricalAnomalyDiagnostics = {
  sampleCount: number;
  baselinePairCount: number;
  headline: string;
  accountingSignals: HistoricalAccountingSignal[];
  businessSignals: HistoricalBusinessSignal[];
};

function averageAbs(values: number[]) {
  if (values.length === 0) {
    return null;
  }
  return values.reduce((total, value) => total + Math.abs(value), 0) / values.length;
}

function directionOf(value: number) {
  if (value > 0) return 1;
  if (value < 0) return -1;
  return 0;
}

function buildDeltaSeries<T>(
  months: T[],
  getReportDate: (month: T) => string,
  getValue: (month: T) => string | number | null | undefined,
) {
  const deltas: number[] = [];
  for (let index = 0; index < months.length - 1; index += 1) {
    const current = months[index];
    const previous = months[index + 1];
    if (!current || !previous || !isPreviousCalendarMonth(getReportDate(current), getReportDate(previous))) {
      continue;
    }
    const delta = trendDelta(getValue(current), getValue(previous));
    if (delta !== null) {
      deltas.push(delta);
    }
  }
  return deltas;
}

function anomalyHeadline(label: string, currentDelta: number, baselineAverageAbs: number | null, baselineCount: number) {
  if (baselineAverageAbs === null || baselineAverageAbs === 0) {
    return Math.abs(currentDelta) > 0 ? `${label} 新增跳变` : `${label} 未见异常`;
  }
  return Math.abs(currentDelta) >= baselineAverageAbs * 3
    ? `${label} 高于近 ${baselineCount} 期常态`
    : `${label} 接近近 ${baselineCount} 期常态`;
}

function buildHistoricalAnomalyDiagnostics(options: {
  trendMonths: BalanceMovementTrendMonth[];
  businessTrendMonths: BalanceBusinessMovementTrendMonth[];
  businessRows: BusinessMovementMatrixRow[];
}): HistoricalAnomalyDiagnostics {
  const { trendMonths, businessTrendMonths, businessRows } = options;
  const sampleCount = Math.max(trendMonths.length, businessTrendMonths.length);
  const baselinePairCount = Math.max(0, sampleCount - 2);
  const accountingSignals =
    baselinePairCount > 0
      ? balanceMovementBuckets
          .map((bucket): HistoricalAccountingSignal | null => {
            const deltas = buildDeltaSeries(
              trendMonths,
              (month) => month.report_date,
              (month) => trendBucket(month, bucket)?.current_balance,
            );
            const [currentDelta, ...historyDeltas] = deltas;
            if (currentDelta === undefined || historyDeltas.length === 0) {
              return null;
            }
            const baselineAverageAbs = averageAbs(historyDeltas);
            const directionReversal =
              directionOf(currentDelta) !== 0 &&
              directionOf(historyDeltas[0]) !== 0 &&
              directionOf(currentDelta) !== directionOf(historyDeltas[0]);
            const headline = anomalyHeadline(bucket, currentDelta, baselineAverageAbs, historyDeltas.length);
            if (!directionReversal && !headline.includes("高于")) {
              return null;
            }
            return {
              bucket,
              headline,
              currentDelta,
              baselineAverageAbs,
              baselineCount: historyDeltas.length,
              directionReversal,
            };
          })
          .filter((signal): signal is HistoricalAccountingSignal => signal !== null)
          .sort((left, right) => Math.abs(right.currentDelta) - Math.abs(left.currentDelta))
      : [];

  const businessSignals =
    baselinePairCount > 0
      ? businessRows
          .filter((row) => row.side === "asset" || row.side === "liability")
          .map((row): HistoricalBusinessSignal | null => {
            const deltas = buildDeltaSeries(
              businessTrendMonths,
              (month) => month.report_date,
              (month) => row.getValue(month),
            );
            const [currentDelta, ...historyDeltas] = deltas;
            if (currentDelta === undefined || historyDeltas.length === 0) {
              return null;
            }
            const baselineAverageAbs = averageAbs(historyDeltas);
            const headline = anomalyHeadline(row.label, currentDelta, baselineAverageAbs, historyDeltas.length);
            if (!headline.includes("高于") && !headline.includes("新增")) {
              return null;
            }
            return {
              label: row.label,
              currentDelta,
              baselineAverageAbs,
              baselineCount: historyDeltas.length,
            };
          })
          .filter((signal): signal is HistoricalBusinessSignal => signal !== null)
          .sort((left, right) => Math.abs(right.currentDelta) - Math.abs(left.currentDelta))
          .slice(0, 5)
      : [];

  return {
    sampleCount,
    baselinePairCount,
    headline: baselinePairCount > 0 ? "本期相对历史常态的偏离" : "历史样本不足",
    accountingSignals,
    businessSignals,
  };
}

type BalanceMovementFreshnessStatus = NonNullable<BalanceMovementDatesPayload["freshness_status"]>;

function freshnessStatusLabel(status: BalanceMovementFreshnessStatus | undefined) {
  switch (status) {
    case "fresh":
      return "数据已同步";
    case "read_model_lagging":
      return "读模型落后上游";
    case "read_model_empty":
      return "读模型未生成";
    case "upstream_empty":
      return "上游暂无控制账";
    default:
      return "新鲜度待确认";
  }
}

function freshnessStatusDetail(status: BalanceMovementFreshnessStatus | undefined) {
  switch (status) {
    case "fresh":
      return "上游控制账与页面读模型日期一致。";
    case "read_model_lagging":
      return "上游已有更晚月份，当前页面仍停留在读模型已有月份。";
    case "read_model_empty":
      return "上游已有控制账数据，但页面读模型尚未生成可选日期。";
    case "upstream_empty":
      return "页面有读模型日期，但未发现同口径上游控制账。";
    default:
      return "当前接口未返回上游与读模型的日期对齐信息。";
  }
}

function freshnessStatusTone(status: BalanceMovementFreshnessStatus | undefined) {
  if (status === "fresh") {
    return "ok";
  }
  if (status === "read_model_lagging" || status === "read_model_empty") {
    return "warn";
  }
  return "info";
}

function FreshnessStrip({
  dates,
  selectedDate,
  reconciliationLabel,
  currencyBasis,
}: {
  dates: BalanceMovementDatesPayload;
  selectedDate: string;
  reconciliationLabel: string;
  currencyBasis: string;
}) {
  const status = dates.freshness_status;
  const latestReadModelDate = dates.latest_read_model_report_date ?? dates.report_dates[0] ?? null;
  const latestUpstreamDate = dates.latest_upstream_control_report_date ?? null;
  const tone = freshnessStatusTone(status);
  return (
    <aside
      className={`balance-movement-data-trust balance-movement-data-trust--${tone} balance-movement-freshness-strip balance-movement-freshness-strip--${tone}`}
      data-testid="balance-movement-analysis-freshness"
      aria-label="余额变动分析数据新鲜度"
    >
      <header className="balance-movement-data-trust__header">
        <span>DATA TRUST</span>
        <strong title={freshnessStatusDetail(status)}>{freshnessStatusLabel(status)}</strong>
      </header>
      <dl className="balance-movement-data-trust__facts">
        <div>
          <dt>Read model</dt>
          <dd>{selectedDate || latestReadModelDate || "未生成"}</dd>
        </div>
        <div>
          <dt>Upstream control</dt>
          <dd>{latestUpstreamDate ?? "未发现"}</dd>
        </div>
        <div>
          <dt>Reconciliation</dt>
          <dd>{reconciliationLabel === "三桶一致" ? "3 / 3 matched" : reconciliationLabel}</dd>
        </div>
        <div>
          <dt>Currency basis</dt>
          <dd>{currencyBasis}</dd>
        </div>
      </dl>
    </aside>
  );
}

function EvidenceStrip({
  meta,
  reportDate,
  currencyBasis,
}: {
  meta: ResultMeta;
  reportDate: string;
  currencyBasis: string;
}) {
  return (
    <section
      className="balance-movement-provenance"
      data-testid="balance-movement-analysis-evidence-strip"
      aria-label="余额变动分析证据与出处"
    >
      <header className="balance-movement-section-heading">
        <div>
          <span>05 / EVIDENCE &amp; PROVENANCE</span>
          <h2>证据与数据出处</h2>
        </div>
        <p>traceable · exportable · reviewable</p>
      </header>
      <div className="balance-movement-provenance__grid">
        <article>
          <span>FRESHNESS</span>
          <strong>{reportDate || meta.resolved_report_date || EM_DASH}</strong>
          <p>当前视图严格锚定读模型报告日，不在浏览器端补算其他月份。</p>
        </article>
        <article>
          <span>LINEAGE</span>
          <strong>{meta.source_version || EM_DASH}</strong>
          <p>{formatMetaList(meta.tables_used)} · 规则 {meta.rule_version || EM_DASH} · quality {meta.quality_flag}</p>
        </article>
        <article>
          <span>CONTROL SCOPE</span>
          <strong>{currencyBasis} · 141 / 142 / 143 / 1440101</strong>
          <p>总账控制口径；排除 144020 股权 OCI，ZQTZ 仅用于诊断核对。</p>
        </article>
      </div>
      <div className="balance-movement-provenance__export-note">
        <span>CSV BOUNDARY</span>
        <p>导出仅包含当前报告日与当前页面证据快照。</p>
        <strong>{meta.trace_id || EM_DASH} · {meta.evidence_rows ?? 0} rows</strong>
      </div>
    </section>
  );
}

function FigmaDecisionHero({
  balanceChangePct,
  balanceChangeTotal,
  topDriver,
  movementDrivers,
  dates,
  selectedDate,
  reconciliationLabel,
  currencyBasis,
}: {
  balanceChangePct: number | null;
  balanceChangeTotal: BalanceMovementPayload["summary"]["balance_change_total"];
  topDriver: BalanceMovementDriver;
  movementDrivers: BalanceMovementDriver[];
  dates: BalanceMovementDatesPayload;
  selectedDate: string;
  reconciliationLabel: string;
  currencyBasis: string;
}) {
  const balanceChangeValue = finiteMetric(balanceChangeTotal);
  const direction =
    balanceChangeValue === null ? EM_DASH : balanceChangeValue > 0 ? "上升" : balanceChangeValue < 0 ? "下降" : "持平";
  const structureDirection = (topDriver.shareDelta ?? 0) >= 0 ? "抬升" : "回落";
  const tplDriver = movementDrivers.find((driver) => driver.bucket === "TPL");
  const ociDriver = movementDrivers.find((driver) => driver.bucket === "OCI");
  const reconciliationHeadline =
    reconciliationLabel === "三桶一致" ? "对账完整" : reconciliationLabel;
  return (
    <section
      className="balance-movement-decision-layout"
      data-testid="balance-movement-analysis-decision-hero"
    >
      <article className="balance-movement-decision-hero" data-testid="balance-movement-analysis-conclusion">
        <header>
          <span>DECISION SIGNAL</span>
          <strong>{reconciliationLabel === "三桶一致" ? `${topDriver.bucket} 结构${structureDirection}` : reconciliationHeadline}</strong>
        </header>
        <h2>
          余额{direction}
          {balanceChangePct === null ? "" : ` ${Math.abs(balanceChangePct).toFixed(2)}%`}，主要由 {topDriver.bucket} 驱动；
          {reconciliationHeadline}，{accountingBasisNarrativeLabel(topDriver.bucket)} 结构占比{structureDirection}。
        </h2>
        <p>
          TPL 贡献 {formatPct(tplDriver?.contributionPct)}，OCI 贡献 {formatPct(ociDriver?.contributionPct)}。
          这表示损益与估值波动暴露上升，并不等同于已实现损益结论。
        </p>
        <div className="balance-movement-decision-hero__chips" aria-label="会计分类变动贡献">
          {movementDrivers.map((driver) => (
            <span key={driver.bucket} data-bucket={driver.bucket.toLowerCase()}>
              {driver.bucket} <strong>{formatSignedYiNumber(driver.balanceChangeYi)} 亿</strong>
            </span>
          ))}
        </div>
      </article>
      <FreshnessStrip
        dates={dates}
        selectedDate={selectedDate}
        reconciliationLabel={reconciliationLabel}
        currencyBasis={currencyBasis}
      />
    </section>
  );
}

function FigmaEmptyHero({
  dates,
  selectedDate,
  reconciliationLabel,
  currencyBasis,
}: {
  dates: BalanceMovementDatesPayload;
  selectedDate: string;
  reconciliationLabel: string;
  currencyBasis: string;
}) {
  return (
    <section
      className="balance-movement-decision-layout"
      data-testid="balance-movement-analysis-decision-hero"
    >
      <article
        className="balance-movement-decision-hero balance-movement-decision-hero--empty"
        data-testid="balance-movement-analysis-conclusion"
      >
        <header>
          <span>DECISION SIGNAL</span>
          <strong>等待物化</strong>
        </header>
        <h2>当前没有可发布的余额变动读模型，首屏仅保留状态与证据说明。</h2>
        <p>先确认报告日是否已物化，再决定是否刷新或回溯上游控制账；在数据到位前，不展示推断性的业务结论。</p>
      </article>
      <FreshnessStrip
        dates={dates}
        selectedDate={selectedDate}
        reconciliationLabel={reconciliationLabel}
        currencyBasis={currencyBasis}
      />
    </section>
  );
}

function FigmaLoadingHero({
  dates,
  selectedDate,
  reconciliationLabel,
  currencyBasis,
}: {
  dates: BalanceMovementDatesPayload;
  selectedDate: string;
  reconciliationLabel: string;
  currencyBasis: string;
}) {
  return (
    <section
      className="balance-movement-decision-layout"
      data-testid="balance-movement-analysis-loading-hero"
      aria-busy="true"
      aria-live="polite"
    >
      <article
        className="balance-movement-decision-hero balance-movement-decision-hero--loading"
        role="status"
      >
        <header>
          <span>DECISION SIGNAL</span>
          <strong>读取中</strong>
        </header>
        <h2>正在读取余额变动分析</h2>
        <p>
          正在装载 {selectedDate || "最新报告日"} 的余额、会计分类与对账证据；完成前不展示空数据结论。
        </p>
        <div className="balance-movement-decision-hero__chips" aria-hidden="true">
          <span>余额口径</span>
          <span>会计分类</span>
          <span>对账证据</span>
        </div>
      </article>
      <FreshnessStrip
        dates={dates}
        selectedDate={selectedDate}
        reconciliationLabel={reconciliationLabel}
        currencyBasis={currencyBasis}
      />
    </section>
  );
}

function FigmaKpiRibbon({
  summary,
  topDriver,
  hasBalanceChangeTotal,
  reconciliationLabel,
  balanceChangePct,
}: {
  summary: BalanceMovementPayload["summary"];
  topDriver: BalanceMovementDriver;
  hasBalanceChangeTotal: boolean;
  reconciliationLabel: string;
  balanceChangePct: number | null;
}) {
  const currentBalanceValue = finiteMetric(summary.current_balance_total);
  const balanceChangePctAvailable =
    balanceChangePct !== null && Number.isFinite(balanceChangePct);
  const topDriverContributionValue = finiteMetric(topDriver.contributionPct);
  const reconciliationState =
    reconciliationLabel === "三桶一致"
      ? "matched"
      : reconciliationLabel === "待数据"
        ? "unavailable"
        : "review";
  return (
    <section className="balance-movement-kpi-ribbon" data-testid="balance-movement-analysis-summary">
      <article>
        <span>期末余额</span>
        <strong>{formatYiFixed(summary.current_balance_total)} 亿</strong>
        <small>上期 {formatYiFixed(summary.previous_balance_total)} 亿</small>
        <div
          className="balance-movement-kpi-ribbon__signal"
          data-state={currentBalanceValue === null ? "unavailable" : "available"}
          data-tone="blue"
          data-testid="balance-movement-kpi-signal"
          role="img"
          aria-label={currentBalanceValue === null ? "期末余额信号数据不可用" : "期末余额信号可用"}
        >
          {currentBalanceValue === null ? (
            <span>{EM_DASH} / 数据不可用</span>
          ) : (
            <progress max={100} value={100} />
          )}
        </div>
      </article>
      <article data-accent="green">
        <span>本月净增</span>
        <strong>{hasBalanceChangeTotal ? formatSignedYi(summary.balance_change_total) : EM_DASH}</strong>
        <small>环比 {balanceChangePct === null ? EM_DASH : `${balanceChangePct > 0 ? "+" : ""}${balanceChangePct.toFixed(2)}%`}</small>
        <div
          className="balance-movement-kpi-ribbon__signal"
          data-direction="trailing"
          data-state={balanceChangePctAvailable ? "available" : "unavailable"}
          data-tone="green"
          data-testid="balance-movement-kpi-signal"
          role="img"
          aria-label={balanceChangePctAvailable ? "环比变动信号可用" : "环比变动信号数据不可用"}
        >
          {balanceChangePctAvailable ? (
            <progress max={100} value={Math.min(Math.abs(balanceChangePct), 100)} />
          ) : (
            <span>{EM_DASH} / 数据不可用</span>
          )}
        </div>
      </article>
      <article data-accent="amber">
        <span>最大驱动</span>
        <strong>{topDriver.bucket} · {formatPct(topDriver.contributionPct)}</strong>
        <small>本月 {formatSignedYiNumber(topDriver.balanceChangeYi)} 亿</small>
        <div
          className="balance-movement-kpi-ribbon__signal"
          data-state={topDriverContributionValue === null ? "unavailable" : "available"}
          data-tone="amber"
          data-testid="balance-movement-kpi-signal"
          role="img"
          aria-label={
            topDriverContributionValue === null
              ? "最大驱动贡献信号数据不可用"
              : `最大驱动贡献 ${formatPct(topDriverContributionValue)}`
          }
        >
          {topDriverContributionValue === null ? (
            <span>{EM_DASH} / 数据不可用</span>
          ) : (
            <progress max={100} value={Math.min(Math.abs(topDriverContributionValue), 100)} />
          )}
        </div>
      </article>
      <article data-accent="green">
        <span>对账状态</span>
        <strong>{reconciliationLabel === "三桶一致" ? "3 / 3 匹配" : reconciliationLabel}</strong>
        <small>差异 {formatPlainNumber(summary.reconciliation_diff_total, 2)} 元</small>
        <div
          className="balance-movement-kpi-ribbon__signal balance-movement-kpi-ribbon__signal--reconciliation"
          data-state={reconciliationState}
          data-testid="balance-movement-kpi-signal"
          role="img"
          aria-label={
            reconciliationState === "matched"
              ? "三项对账全部匹配"
              : reconciliationState === "review"
                ? "对账存在不匹配项"
                : "对账状态数据不可用"
          }
        >
          {reconciliationState === "unavailable" ? (
            <span>{EM_DASH} / 数据不可用</span>
          ) : (
            <>
              <i />
              <i />
              <i />
            </>
          )}
        </div>
      </article>
    </section>
  );
}

function FigmaDriversAndStructure({ drivers }: { drivers: BalanceMovementDriver[] }) {
  const maxChange = Math.max(...drivers.map((driver) => Math.abs(driver.balanceChangeYi)), 1);
  const contributionValues = drivers.map((driver) => finiteMetric(driver.contributionPct));
  const contributionsAvailable = contributionValues.every(
    (value) => value !== null && Number.isFinite(value),
  );
  const totalContribution = contributionsAvailable
    ? contributionValues.reduce<number>((total, value) => total + (value ?? 0), 0)
    : null;
  let contributionOffset = 0;
  const contributionSegments = contributionsAvailable
    ? drivers.map((driver, index) => {
        const share = Math.max(0, Math.min(contributionValues[index] as number, 100));
        const segment = { driver, share, offset: contributionOffset };
        contributionOffset += share;
        return segment;
      })
    : [];
  const structureDrivers = [...drivers].sort(
    (left, right) =>
      ["AC", "OCI", "TPL"].indexOf(left.bucket) - ["AC", "OCI", "TPL"].indexOf(right.bucket),
  );
  const structureValues = structureDrivers.map((driver) =>
    finiteMetric(driver.currentBalancePct),
  );
  const structureAvailable = structureValues.every(
    (value) => value !== null && Number.isFinite(value),
  );
  let structureOffset = 0;
  const structureSegments = structureAvailable
    ? structureDrivers.map((driver, index) => {
        const share = Math.max(0, Math.min(structureValues[index] as number, 100));
        const segment = { driver, share, offset: structureOffset };
        structureOffset += share;
        return segment;
      })
    : [];
  return (
    <section className="balance-movement-analysis-pair" data-testid="balance-movement-analysis-drivers-structure">
      <article className="balance-movement-compact-panel balance-movement-driver-panel">
        <header className="balance-movement-section-heading">
          <div>
            <h2>本月变动驱动</h2>
          </div>
          <p>单位：亿元 / 贡献率</p>
        </header>
        <div className="balance-movement-driver-list">
          {drivers.map((driver) => (
            <div key={driver.bucket} data-bucket={driver.bucket.toLowerCase()}>
              <span>{driver.bucket}</span>
              <progress max={maxChange} value={Math.abs(driver.balanceChangeYi)}>
                {Math.abs(driver.balanceChangeYi)}
              </progress>
              <strong>{formatSignedYiNumber(driver.balanceChangeYi)} 亿</strong>
              <small>{formatPct(driver.contributionPct)}</small>
            </div>
          ))}
        </div>
        <p className="balance-movement-compact-panel__note">
          三类桶合计贡献 {formatPct(totalContribution)}，最大单一驱动为 {drivers[0]?.bucket ?? EM_DASH}。
        </p>
        {contributionsAvailable ? (
          <svg
            className="balance-movement-driver-composition"
            data-testid="balance-movement-driver-composition-band"
            data-state="available"
            width="100%"
            height="28"
            role="img"
            aria-label={`变动贡献构成：${drivers
              .map((driver) => `${driver.bucket} ${formatPct(driver.contributionPct)}`)
              .join("，")}`}
          >
            <title>变动贡献构成</title>
            <rect className="balance-movement-band-track" x="0" y="0" width="100%" height="28" />
            {contributionSegments.map(({ driver, share, offset }) => (
              <g key={driver.bucket} data-bucket={driver.bucket.toLowerCase()}>
                <rect x={`${offset}%`} y="0" width={`${share}%`} height="28" />
                {share >= 6 ? (
                  <text x={`${offset + share / 2}%`} y="18" textAnchor="middle">
                    {driver.bucket}{share >= 14 ? ` · ${formatPct(driver.contributionPct)}` : ""}
                  </text>
                ) : null}
              </g>
            ))}
          </svg>
        ) : (
          <div
            className="balance-movement-driver-composition balance-movement-band-unavailable"
            data-testid="balance-movement-driver-composition-band"
            data-state="unavailable"
            role="img"
            aria-label="变动贡献构成：数据不可用"
          >
            <span>{EM_DASH} / 数据不可用</span>
          </div>
        )}
      </article>
      <article className="balance-movement-compact-panel balance-movement-structure-panel">
        <header className="balance-movement-section-heading">
          <div>
            <h2>会计分类结构</h2>
          </div>
          <p>本期 / 较上期</p>
        </header>
        {structureAvailable ? (
          <svg
            className="balance-movement-structure-mix"
            data-testid="balance-movement-structure-mix-band"
            data-state="available"
            width="100%"
            height="34"
            role="img"
            aria-label={`会计分类结构：${structureDrivers
              .map((driver) => `${driver.bucket} ${formatPct(driver.currentBalancePct)}`)
              .join("，")}`}
          >
            <title>会计分类结构占比</title>
            <rect className="balance-movement-band-track" x="0" y="0" width="100%" height="34" />
            {structureSegments.map(({ driver, share, offset }) => (
              <g key={driver.bucket} data-bucket={driver.bucket.toLowerCase()}>
                <rect x={`${offset}%`} y="0" width={`${share}%`} height="34" />
                {share >= 12 ? (
                  <text x={`${offset + share / 2}%`} y="22" textAnchor="middle">
                    {driver.bucket} {formatPct(driver.currentBalancePct)}
                  </text>
                ) : null}
              </g>
            ))}
          </svg>
        ) : (
          <div
            className="balance-movement-structure-mix balance-movement-band-unavailable"
            data-testid="balance-movement-structure-mix-band"
            data-state="unavailable"
            role="img"
            aria-label="会计分类结构：数据不可用"
          >
            <span>{EM_DASH} / 数据不可用</span>
          </div>
        )}
        <div className="balance-movement-structure-list">
          {structureDrivers.map((driver) => (
            <div key={driver.bucket} data-bucket={driver.bucket.toLowerCase()}>
              <span>{driver.bucket}</span>
              <strong>{formatPct(driver.currentBalancePct)}</strong>
              <small>{formatSignedPointNullable(driver.shareDelta)}</small>
            </div>
          ))}
        </div>
        <p className="balance-movement-compact-panel__note">结构信号不等同于单只资产已完成会计分类迁移。</p>
      </article>
    </section>
  );
}

type CompactMaturityGroup = {
  key: string;
  label: string;
  currentAmount: number | null;
  deltaAmount: number | null;
  sharePct: number | null;
};

function FigmaMaturityAndConcentration({
  maturityGroups,
  issuerDimension,
  maturityCoverage,
  unknownMaturityAmount,
}: {
  maturityGroups: CompactMaturityGroup[];
  issuerDimension: BalanceZqtzConcentrationAnalysis["dimensions"][number] | null;
  maturityCoverage: string | number | null | undefined;
  unknownMaturityAmount: string | number | null | undefined;
}) {
  const largestMaturity = maturityGroups.reduce<CompactMaturityGroup | null>(
    (largest, group) => {
      if (group.currentAmount === null) return largest;
      if (largest?.currentAmount === null || largest === null) return group;
      return group.currentAmount > largest.currentAmount ? group : largest;
    },
    null,
  );
  const maturityShareValues = maturityGroups.map((group) => finiteMetric(group.sharePct));
  const maturitySharesAvailable = maturityShareValues.every(
    (value) => value !== null && Number.isFinite(value),
  );
  let maturityOffset = 0;
  const maturitySegments = maturitySharesAvailable
    ? maturityGroups.map((group, index) => {
        const share = Math.max(0, Math.min(maturityShareValues[index] as number, 100));
        const segment = { group, share, offset: maturityOffset };
        maturityOffset += share;
        return segment;
      })
    : [];
  const knownShareValue = finiteMetric(maturityCoverage);
  const knownShare =
    knownShareValue === null ? null : Math.max(0, Math.min(knownShareValue, 100));
  const unmappedShare = knownShare === null ? null : Math.max(0, 100 - knownShare);
  const top5ShareValue = finiteMetric(issuerDimension?.top5_share_pct);
  const top5GaugeShare =
    top5ShareValue === null ? null : Math.max(0, Math.min(top5ShareValue, 100));
  return (
    <section className="balance-movement-analysis-pair" data-testid="balance-movement-analysis-maturity-concentration">
      <article className="balance-movement-compact-panel balance-movement-maturity-compact">
        <header className="balance-movement-section-heading">
          <div>
            <h2>期限结构</h2>
          </div>
          <strong className="balance-movement-section-heading__badge">覆盖率 {formatPct(maturityCoverage)}</strong>
        </header>
        {maturitySharesAvailable ? (
          <svg
            className="balance-movement-maturity-spectrum"
            data-testid="balance-movement-maturity-spectrum"
            data-state="available"
            width="100%"
            height="26"
            role="img"
            aria-label={`期限分布：${maturityGroups
              .map((group) => `${group.label} ${formatPct(group.sharePct)}`)
              .join("，")}`}
          >
            <title>期限分布</title>
            <rect className="balance-movement-band-track" x="0" y="0" width="100%" height="26" />
            {maturitySegments.map(({ group, share, offset }) => (
              <g key={group.key} data-maturity={group.key}>
                <rect x={`${offset}%`} y="0" width={`${share}%`} height="26" />
              </g>
            ))}
          </svg>
        ) : (
          <div
            className="balance-movement-maturity-spectrum balance-movement-band-unavailable"
            data-testid="balance-movement-maturity-spectrum"
            data-state="unavailable"
            role="img"
            aria-label="期限分布：数据不可用"
          >
            <span>{EM_DASH} / 数据不可用</span>
          </div>
        )}
        <div className="balance-movement-maturity-compact__grid">
          {maturityGroups.map((group) => (
            <div
              key={group.key}
              data-largest={group.key === largestMaturity?.key ? "true" : undefined}
              data-maturity={group.key}
            >
              <span>{group.label}</span>
              <strong>{formatPct(group.sharePct)}</strong>
              <small>{formatYiFixed(group.currentAmount)} 亿</small>
            </div>
          ))}
        </div>
        {knownShare !== null && unmappedShare !== null ? (
          <svg
            className="balance-movement-maturity-coverage"
            data-testid="balance-movement-maturity-coverage-band"
            data-state="available"
            width="100%"
            height="34"
            role="img"
            aria-label={`KNOWN ${formatPct(knownShare)}，UNMAPPED ${formatPct(unmappedShare)}`}
          >
            <title>已映射与未映射期限构成</title>
            <rect className="balance-movement-band-track" x="0" y="0" width="100%" height="34" />
            <g data-coverage="known">
              <rect x="0" y="0" width={`${knownShare}%`} height="34" />
              {knownShare >= 18 ? (
                <text x={`${knownShare / 2}%`} y="22" textAnchor="middle">
                  KNOWN · {formatPct(maturityCoverage)}
                </text>
              ) : null}
            </g>
            <g data-coverage="unmapped">
              <rect x={`${knownShare}%`} y="0" width={`${unmappedShare}%`} height="34" />
              {unmappedShare >= 9 ? (
                <text x={`${knownShare + unmappedShare / 2}%`} y="22" textAnchor="middle">
                  {formatPct(unmappedShare)}
                </text>
              ) : null}
            </g>
          </svg>
        ) : (
          <div
            className="balance-movement-maturity-coverage balance-movement-band-unavailable"
            data-testid="balance-movement-maturity-coverage-band"
            data-state="unavailable"
            role="img"
            aria-label="KNOWN / UNMAPPED：数据不可用"
          >
            <span>{EM_DASH} / 数据不可用</span>
          </div>
        )}
        <p className="balance-movement-compact-panel__note">
          未映射到期日金额 {formatYiFixed(unknownMaturityAmount)} 亿，已单列，不并入其他期限桶。
        </p>
      </article>
      <article className="balance-movement-compact-panel balance-movement-concentration-compact">
        <header className="balance-movement-section-heading">
          <div>
            <h2>主体集中度</h2>
          </div>
          <strong className="balance-movement-section-heading__badge balance-movement-section-heading__badge--blue">主体覆盖 {formatPct(issuerDimension?.coverage_pct)}</strong>
        </header>
        <div className="balance-movement-concentration-compact__metrics">
          <div className="balance-movement-concentration-compact__hhi">
            <span>HHI</span>
            <strong>{formatPlainNumber(issuerDimension?.hhi, 2)}</strong>
          </div>
          <div
            className="balance-movement-concentration-compact__gauge"
            data-testid="balance-movement-top5-gauge"
            data-state={top5GaugeShare === null ? "unavailable" : "available"}
          >
            <svg
              width="112"
              height="112"
              viewBox="0 0 112 112"
              role="img"
              aria-label={
                top5GaugeShare === null
                  ? "Top 5 Share 数据不可用"
                  : `Top 5 Share ${formatPct(issuerDimension?.top5_share_pct)}`
              }
            >
              <title>Top 5 Share</title>
              <circle className="balance-movement-concentration-compact__gauge-track" cx="56" cy="56" r="42" />
              {top5GaugeShare === null ? null : (
                <circle
                  className="balance-movement-concentration-compact__gauge-value"
                  cx="56"
                  cy="56"
                  r="42"
                  pathLength="100"
                  strokeDasharray={`${top5GaugeShare} ${Math.max(0, 100 - top5GaugeShare)}`}
                />
              )}
            </svg>
            <span>Top 5 Share</span>
            <strong>{formatPct(issuerDimension?.top5_share_pct)}</strong>
            {top5GaugeShare === null ? <em>数据不可用</em> : null}
          </div>
        </div>
        <div
          className="balance-movement-concentration-compact__unknown"
          data-testid="balance-movement-concentration-unknown-strip"
        >
          <span>Unknown</span>
          <strong>{formatYiFixed(issuerDimension?.unknown_total)} 亿</strong>
        </div>
        <p className="balance-movement-compact-panel__note">主体覆盖 {formatPct(issuerDimension?.coverage_pct)}；完整主体、评级与行业明细保留在下方。</p>
      </article>
    </section>
  );
}

function FigmaAccountingBuckets({ rows }: { rows: BalanceMovementRow[] }) {
  return (
    <section className="balance-movement-accounting-buckets" data-testid="balance-movement-analysis-accounting-buckets">
      <header className="balance-movement-section-heading">
        <div>
          <span>06 / ACCOUNTING BUCKETS</span>
          <h2>AC / OCI / TPL 核心对账</h2>
        </div>
        <p>previous · current · change · reconciliation</p>
      </header>
      <div className="balance-movement-accounting-buckets__scroll">
        <table>
          <thead>
            <tr>
              <th>分类</th>
              <th>期初余额</th>
              <th>期末余额</th>
              <th>变动</th>
              <th>期末占比</th>
              <th>变动贡献</th>
              <th>对账</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.basis_bucket}>
                <th scope="row">{row.basis_bucket}</th>
                <td>{formatYiFixed(row.previous_balance)} 亿</td>
                <td>{formatYiFixed(row.current_balance)} 亿</td>
                <td>{formatSignedYi(row.balance_change)}</td>
                <td>{formatPct(row.current_balance_pct)}</td>
                <td>{formatPct(row.contribution_pct)}</td>
                <td><ReconciliationStatusTag status={row.reconciliation_status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SixMonthStructurePanel({
  chartRows,
  balanceStructureInsight,
}: {
  chartRows: AccountingBasisStackedSharePoint[];
  structureShareTableRows: StructureShareTableRow[];
  shareRowByReportMonth: Map<string, StructureShareTableRow>;
  balanceStructureInsight: string | null;
}) {
  const matrixRows = [
    { label: "AC", value: (point: AccountingBasisStackedSharePoint) => point.acValueYi },
    { label: "OCI", value: (point: AccountingBasisStackedSharePoint) => point.ociValueYi },
    { label: "TPL", value: (point: AccountingBasisStackedSharePoint) => point.tplValueYi },
    { label: "AC / OCI / TPL 合计", value: (point: AccountingBasisStackedSharePoint) => point.totalValueYi },
  ];

  return (
    <section
      className="balance-movement-six-month balance-movement-figma-panel"
      data-testid="balance-movement-analysis-six-month-structure"
    >
      <header className="balance-movement-figma-header">
        <div>
          <span>02 / SIX-MONTH ACCOUNTING STRUCTURE</span>
          <h2>六个月会计分类矩阵与结构演变</h2>
        </div>
        <p>trend_months · AC / OCI / TPL · balance basis</p>
      </header>

      <div className="balance-movement-six-month__matrix">
        <table aria-label="六个月会计分类余额矩阵">
          <thead>
            <tr>
              <th scope="col">分类</th>
              {chartRows.map((point) => (
                <th key={point.monthLabel} scope="col">{point.monthLabel}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrixRows.map((row) => (
              <tr key={row.label}>
                <th scope="row">{row.label}</th>
                {chartRows.map((point) => (
                  <td key={point.monthLabel}>{formatShareEvolutionYi(row.value(point))}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div
        className="balance-movement-six-month__timeline balance-movement-structure-chart"
        data-testid="balance-movement-analysis-structure-chart"
      >
        <div>
          <h3>金融投资账户结构演变 · 余额口径</h3>
          {chartRows.length > 0 ? (
            <div className="balance-movement-six-month__bars" aria-label="AC OCI TPL 六个月结构演变">
              {chartRows.map((point) => {
                const segments = [
                  { key: "AC" as const, value: point.AC },
                  { key: "OCI" as const, value: point.OCI },
                  { key: "TPL" as const, value: point.TPL },
                ];
                return (
                  <article key={point.monthLabel} className="balance-movement-six-month__bar">
                    <div>
                      {segments.map((segment) => (
                        <span
                          key={segment.key}
                          className="balance-movement-six-month__segment"
                          data-bucket={segment.key}
                          style={{ height: `${Math.max(0, Math.min(segment.value, 100))}%` }}
                          title={`${segment.key} ${formatShareEvolutionPct(segment.value)}`}
                        >
                          {segment.value >= 12 ? formatShareEvolutionPct(segment.value) : null}
                        </span>
                      ))}
                    </div>
                    <span>{point.monthLabel}</span>
                  </article>
                );
              })}
            </div>
          ) : (
            <p className="balance-movement-share-evolution-table__note">
              占比数据缺失，结构图暂不可比
            </p>
          )}
        </div>
        <aside
          className="balance-movement-six-month__insight balance-movement-structure-chart__insight"
          data-testid="balance-movement-analysis-structure-insight"
        >
          <h3>本期结构结论</h3>
          <p>{balanceStructureInsight ?? "结构占比数据不足，暂不生成比较结论。"}</p>
          <small>占比使用后端正式 current_balance_pct；页面不补算缺失值。</small>
        </aside>
      </div>
    </section>
  );
}

function StructureShareDetailTable({
  structureShareTableRows,
  shareRowByReportMonth,
}: {
  structureShareTableRows: StructureShareTableRow[];
  shareRowByReportMonth: Map<string, StructureShareTableRow>;
}) {
  if (structureShareTableRows.length === 0) {
    return null;
  }

  return (
    <div className="balance-movement-structure-share-detail">
      <p
        className="balance-movement-share-evolution-table__title"
        data-testid="balance-movement-analysis-structure-share-table-title"
      >
        结构占比明细 · 完整口径（与六个月结构图一致）
      </p>
      <p className="balance-movement-share-evolution-table__note">
        环比为相对上一行月份的变动；同比为相对上年同月；较首月用于识别六个月结构迁移。
      </p>
      <div
        className="balance-movement-share-evolution-table-scroll"
        data-testid="balance-movement-analysis-structure-share-table"
      >
        <table className="balance-movement-share-evolution-table">
          <thead>
            <tr>
              <th scope="col">月份</th>
              <th scope="col">AC(%)</th>
              <th scope="col">OCI(%)</th>
              <th scope="col">TPL(%)</th>
              <th scope="col">合计(亿)</th>
              <th scope="col">AC(亿)</th>
              <th scope="col">OCI(亿)</th>
              <th scope="col">TPL(亿)</th>
              <th scope="col">环比·AC</th>
              <th scope="col">环比·OCI</th>
              <th scope="col">环比·TPL</th>
              <th scope="col">环比·合计</th>
              <th scope="col">同比·AC</th>
              <th scope="col">同比·OCI</th>
              <th scope="col">同比·TPL</th>
              <th scope="col">同比·合计</th>
              {structureShareTableRows.length > 1 ? (
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
              const showFirstDelta = structureShareTableRows.length > 1 && first !== undefined;
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
                  <td>{prev ? formatSignedPointNullable(nullableDelta(point.AC, prev.point.AC)) : EM_DASH}</td>
                  <td>{prev ? formatSignedPointNullable(nullableDelta(point.OCI, prev.point.OCI)) : EM_DASH}</td>
                  <td>{prev ? formatSignedPointNullable(nullableDelta(point.TPL, prev.point.TPL)) : EM_DASH}</td>
                  <td>{formatSignedYiDelta(point.totalValueYi, prev?.point.totalValueYi)}</td>
                  <td>{yoy ? formatSignedPointNullable(nullableDelta(point.AC, yoy.point.AC)) : EM_DASH}</td>
                  <td>{yoy ? formatSignedPointNullable(nullableDelta(point.OCI, yoy.point.OCI)) : EM_DASH}</td>
                  <td>{yoy ? formatSignedPointNullable(nullableDelta(point.TPL, yoy.point.TPL)) : EM_DASH}</td>
                  <td>{formatSignedYiDelta(point.totalValueYi, yoy?.point.totalValueYi)}</td>
                  {showFirstDelta ? (
                    <>
                      <td>{formatSignedPointNullable(nullableDelta(point.AC, first.point.AC))}</td>
                      <td>{formatSignedPointNullable(nullableDelta(point.OCI, first.point.OCI))}</td>
                      <td>{formatSignedPointNullable(nullableDelta(point.TPL, first.point.TPL))}</td>
                    </>
                  ) : null}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function BusinessBalanceMatrixSection({
  months,
  liabilityRows,
  projectRows,
  balanceRows,
  accountingSnapshotsAreNonAdjacent,
}: {
  months: BalanceBusinessMovementTrendMonth[];
  liabilityRows: BusinessMovementMatrixRow[];
  projectRows: BusinessMovementMatrixRow[];
  balanceRows: BalanceMovementRow[];
  accountingSnapshotsAreNonAdjacent: boolean;
}) {
  const rows = [...liabilityRows, ...projectRows];
  const currentMonth = months.at(-1)?.report_month ?? EM_DASH;

  return (
    <section
      className="balance-movement-business-matrix balance-movement-figma-panel"
      data-testid="balance-movement-analysis-business-balance-matrix"
    >
      <header className="balance-movement-figma-header">
        <div>
          <span>09 / BUSINESS BALANCE MONTHLY MATRIX</span>
          <h2>业务口径余额矩阵与 AC / OCI / TPL 对账</h2>
        </div>
        <p>report {currentMonth} · current vs prior / Jan</p>
      </header>

      <div className="balance-movement-business-matrix__scope">
        <p data-testid="balance-movement-analysis-slice-note">
          总账 AC/OCI/TPL 与业务行属于两套分类，不做简单加减核对。
        </p>
        <p data-testid="balance-movement-analysis-series-context">
          <code>business_trend_months</code>
          <span>
            {accountingSnapshotsAreNonAdjacent
              ? "相邻快照非连续，环比结论保持隐藏。"
              : `当前覆盖 ${months.length} 个月度；若仅含两个月度，较年初按序列首月解释。`}
          </span>
        </p>
      </div>

      <div className="balance-movement-business-matrix__table-wrap">
        <table
          data-testid="balance-movement-analysis-trend-table"
          className="balance-movement-business-matrix__table"
        >
          <thead>
            <tr>
              <th scope="col">明细项目</th>
              {months.map((month) => (
                <th key={month.report_date} scope="col">
                  {formatTrendMonthLabel(month.report_month)}
                </th>
              ))}
              <th scope="col">较上月</th>
              <th scope="col">较年初</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const mom = compareBusinessMatrixCell(months, row, 1);
              const ytd = compareBusinessMatrixCellToFirst(months, row);
              return (
                <tr key={row.key} data-side={row.side}>
                  <th scope="row" title={row.sourceNote}>{row.label}</th>
                  {months.map((month) => {
                    const cellMeta = row.getCellMeta?.(month);
                    return (
                      <td
                        key={`${row.key}-${month.report_date}`}
                        title={cellMeta?.hasMissingInputs ? "部分分项缺失，合计未含缺失项" : undefined}
                      >
                        {cellMeta
                          ? formatMatrixCellWithMissing(
                              row.getValue(month),
                              row.valueKind,
                              true,
                              cellMeta.hasMissingInputs,
                            )
                          : formatMatrixValue(row.getValue(month), row.valueKind, true)}
                      </td>
                    );
                  })}
                  <td className={matrixDeltaTone(mom)}>{mom}</td>
                  <td className={matrixDeltaTone(ytd)}>{ytd}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="balance-movement-business-matrix__reconciliation">
        <h3>明细 / 对账：AC / OCI / TPL 余额变动</h3>
        <div className="balance-movement-detail-table-wrap">
          <table
            data-testid="balance-movement-analysis-table"
            className="balance-movement-detail-table"
          >
            <thead>
              <tr>
                <th>分类</th>
                <th>期初余额(亿)</th>
                <th>期初占比</th>
                <th>期末余额(亿)</th>
                <th>期末占比</th>
                <th>占比变动</th>
                <th>变动(亿)</th>
                <th>变动率</th>
                <th>变动贡献</th>
                <th>ZQTZ辅助(亿)</th>
                <th>ZQTZ诊断差异(亿)</th>
                <th>跨月勾稽</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {balanceRows.map((row) => (
                <tr key={row.basis_bucket}>
                  <td>{bucketLabels[row.basis_bucket] ?? row.basis_bucket}</td>
                  <td>{formatBalanceAmountToYiFromYuan(row.previous_balance)}</td>
                  <td>{formatPct(row.previous_balance_pct)}</td>
                  <td>{formatBalanceAmountToYiFromYuan(row.current_balance)}</td>
                  <td>{formatPct(row.current_balance_pct)}</td>
                  <td>{formatSignedPointNullable(shareDeltaPp(row))}</td>
                  <td>{formatBalanceAmountToYiFromYuan(row.balance_change)}</td>
                  <td>{formatPct(row.change_pct)}</td>
                  <td>{formatPct(row.contribution_pct)}</td>
                  <td>{counterpartyAmountText(row, formatBalanceAmountToYiFromYuan(row.zqtz_amount))}</td>
                  <td>{counterpartyAmountText(row, formatBalanceAmountToYiFromYuan(row.reconciliation_diff))}</td>
                  <td>{chainStatusLabel(row.chain_status)}</td>
                  <td className={statusToneClass(row.reconciliation_status)}>
                    <ReconciliationStatusTag status={row.reconciliation_status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="balance-movement-business-matrix__tieout">
        {reconciliationTieoutSummary(balanceRows, formatSignedYiNumber)}
      </div>
    </section>
  );
}

function SupplementaryBusinessRowsTable({
  months,
  rows,
}: {
  months: BalanceBusinessMovementTrendMonth[];
  rows: BusinessMovementMatrixRow[];
}) {
  if (rows.length === 0) {
    return null;
  }

  return (
    <section
      className="balance-movement-supplementary-matrix"
      data-testid="balance-movement-analysis-supplementary-business-matrix"
    >
      <header>
        <strong>资产端同业扩展明细</strong>
        <span>完整业务矩阵保留区 · 默认不占用决策主流程</span>
      </header>
      <div className="balance-movement-business-matrix__table-wrap">
        <table className="balance-movement-business-matrix__table">
          <thead>
            <tr>
              <th scope="col">明细项目</th>
              {months.map((month) => (
                <th key={month.report_date} scope="col">
                  {formatTrendMonthLabel(month.report_month)}
                </th>
              ))}
              <th scope="col">较上月</th>
              <th scope="col">较年初</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const mom = compareBusinessMatrixCell(months, row, 1);
              const ytd = compareBusinessMatrixCellToFirst(months, row);
              return (
                <tr key={row.key} data-side={row.side}>
                  <th scope="row" title={row.sourceNote}>{row.label}</th>
                  {months.map((month) => (
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
    </section>
  );
}

function StructureBridgeStage({
  analysis,
  waterfall,
  closure,
}: {
  analysis: BalanceStructureMigrationAnalysis | null;
  waterfall: BalanceDifferenceAttributionWaterfall | null;
  closure: BalanceExplanationClosure | null;
}) {
  if (!analysis && !waterfall && !closure) {
    return null;
  }

  const latestPair = analysis?.pairs[analysis.pairs.length - 1] ?? null;
  const unsupportedComponents = waterfall?.components.filter((component) => !component.is_supported) ?? [];

  return (
    <section
      className="balance-movement-structure-bridge balance-movement-figma-panel"
      data-testid="balance-movement-analysis-structure-bridge"
    >
      <header className="balance-movement-figma-header">
        <div>
          <span>03 / STRUCTURE MIGRATION &amp; RECONCILIATION BRIDGE</span>
          <h2>结构迁移与差异归因</h2>
        </div>
        <p>structure_migration_analysis · difference_attribution_waterfall</p>
      </header>

      <div className="balance-movement-structure-bridge__columns">
        <article
          className="balance-movement-structure-bridge__migration"
          data-testid="balance-movement-analysis-structure-migration"
        >
          <span className="balance-movement-sr-only">结构迁移信号</span>
          <header>
            <h3>AC / OCI / TPL 占比迁移</h3>
            <strong>
              {latestPair?.dominant_share_increase_bucket
                ? `${latestPair.dominant_share_increase_bucket} 抬升最明显`
                : "等待可比期间"}
            </strong>
          </header>
          <p>{analysis?.summary ?? "结构迁移分析未返回。"}</p>
          {latestPair ? (
            <p>
              {latestPair.previous_report_date} → {latestPair.current_report_date} · 总余额{" "}
              {formatSignedYiCell(latestPair.total_balance_delta)} 亿
            </p>
          ) : null}
          {latestPair?.buckets.map((bucket) => (
            <div
              key={bucket.basis_bucket}
              className="balance-movement-structure-bridge__bucket"
              data-bucket={bucket.basis_bucket}
            >
              <span>{bucket.basis_bucket}</span>
              <div>
                <strong>{formatSignedYiCell(bucket.balance_delta)} 亿</strong>
                <small>
                  {formatPct(bucket.previous_share_pct)} → {formatPct(bucket.current_share_pct)}
                </small>
              </div>
              <em>{formatSignedPercentPoint(bucket.share_delta_pp)}</em>
            </div>
          ))}
          <aside>
            <strong>INTERPRETATION BOUNDARY</strong>
            <p>{analysis?.caveat ?? "这是汇总分类桶的结构信号，不代表单只资产分类迁移。"}</p>
            {latestPair ? (
              <small className="balance-movement-structure-bridge__signals">
                {latestPair.fvtpl_volatility_signal} · {latestPair.oci_valuation_signal}
              </small>
            ) : null}
          </aside>
        </article>

        <article
          className="balance-movement-structure-bridge__waterfall"
          data-testid="balance-movement-analysis-difference-waterfall"
        >
          <span className="balance-movement-sr-only">差异归因瀑布</span>
          <header>
            <h3>ZQTZ 明细汇总 → AC / OCI / TPL 合计</h3>
            <strong>
              净差额 {waterfall ? `${formatSignedYiCell(waterfall.net_difference)} 亿` : EM_DASH}
            </strong>
          </header>
          {waterfall ? (
            <>
              <div className="balance-movement-structure-bridge__endpoint">
                <span>起点 · {waterfall.reference_label}</span>
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
                      <p>{isUnsupported ? `未支持，不反推 · ${component.evidence_note}` : component.evidence_note}</p>
                    </div>
                    <strong>
                      {isUnsupported ? "待拆分" : `${formatSignedYiCell(component.amount)} 亿`}
                    </strong>
                  </div>
                );
              })}
              <div className="balance-movement-structure-bridge__endpoint balance-movement-structure-bridge__endpoint--target">
                <span>终点 · {waterfall.target_label}</span>
                <strong>{formatYiCell(waterfall.target_total)} 亿</strong>
              </div>
              <div
                className="balance-movement-structure-bridge__closure"
                data-testid="balance-movement-analysis-explanation-closure"
              >
                <div>
                  <span>已支持解释项</span>
                  <strong>{closure?.supportedComponents.length ?? waterfall.components.filter((item) => item.is_supported).length} 项</strong>
                </div>
                <div>
                  <span>待补口径</span>
                  <strong>{closure?.unsupportedComponents.length ?? unsupportedComponents.length} 项</strong>
                </div>
                <div>
                  <span>闭合校验</span>
                  <strong>{formatSignedYiCell(waterfall.closing_check)} 亿</strong>
                </div>
                <span className="balance-movement-sr-only">
                  解释闭合度 · 未支持项 · 未分类 / 残差 ·
                  {closure?.unsupportedComponents
                    .map((component) => component.component_label)
                    .join("、")} · 未支持，不反推 ·
                  {closure?.residualRatioPct === null || closure?.residualRatioPct === undefined
                    ? EM_DASH
                    : formatPct(closure.residualRatioPct)} · {closure?.headline} {closure?.note}
                </span>
              </div>
              <div
                className="balance-movement-sr-only"
                data-testid="balance-movement-analysis-residual-closure"
              >
                哪些差异还不能解释：未分类 / 残差；
                {unsupportedComponents.map((component) => component.component_label).join("、")}；
                未支持，不反推。
              </div>
            </>
          ) : (
            <p>difference_attribution_waterfall 未返回，页面不反推差异组件。</p>
          )}
        </article>
      </div>
    </section>
  );
}
function HistoricalAnomalyPanel({
  diagnostics,
}: {
  diagnostics: HistoricalAnomalyDiagnostics;
}) {
  const sampleLabel =
    diagnostics.sampleCount > 0 ? `仅 ${diagnostics.sampleCount} 期样本` : "暂无历史样本";
  const hasBaseline = diagnostics.baselinePairCount > 0;
  return (
    <section
      className="balance-movement-anomaly-panel"
      data-testid="balance-movement-analysis-anomaly-diagnostics"
    >
      <div className="balance-movement-derived-panel__header">
        <div>
          <span>历史异常定位</span>
          <h2>{diagnostics.headline}</h2>
        </div>
        <strong>{hasBaseline ? `近 ${diagnostics.baselinePairCount} 期常态` : sampleLabel}</strong>
      </div>
      <p className="balance-movement-derived-panel__summary">
        页面诊断提示，不是正式风险指标；只用现有趋势 payload 比较本期变动与最近历史变动，不反推交易动作。
      </p>
      <div className="balance-movement-anomaly-grid">
        <div className="balance-movement-anomaly-card">
          <span>AC / OCI / TPL 异常判断</span>
          {hasBaseline ? (
            diagnostics.accountingSignals.length > 0 ? (
              <ul className="balance-movement-anomaly-list">
                {diagnostics.accountingSignals.map((signal) => (
                  <li key={signal.bucket}>
                    <strong>{signal.bucket}</strong>
                    <span>{signal.headline}</span>
                    <p>
                      本期 {formatSignedYiCell(signal.currentDelta)} 亿；近 {signal.baselineCount} 期平均{" "}
                      {signal.baselineAverageAbs === null ? EM_DASH : `${formatYiCell(signal.baselineAverageAbs)} 亿`}
                      {signal.directionReversal ? "；方向反转" : ""}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p>未发现高于历史常态的 AC / OCI / TPL 单桶变动。</p>
            )
          ) : (
            <p>历史样本不足，{sampleLabel}，暂不判断异常。</p>
          )}
        </div>
        <div className="balance-movement-anomaly-card">
          <span>业务品类异常榜</span>
          {hasBaseline ? (
            diagnostics.businessSignals.length > 0 ? (
              <ul className="balance-movement-anomaly-list">
                {diagnostics.businessSignals.map((signal) => (
                  <li key={signal.label}>
                    <strong>{signal.label}</strong>
                    <span>{formatSignedYiCell(signal.currentDelta)} 亿</span>
                    <p>
                      高于近 {signal.baselineCount} 期常态；历史平均{" "}
                      {signal.baselineAverageAbs === null ? EM_DASH : `${formatYiCell(signal.baselineAverageAbs)} 亿`}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p>未发现高于历史常态的业务品类变动。</p>
            )
          ) : (
            <p>历史样本不足，{sampleLabel}，先看本期 Top 变动。</p>
          )}
        </div>
      </div>
    </section>
  );
}

function LiveBasisDecompositionStage({
  decomposition,
  hasCalibration,
}: {
  decomposition: BalanceBasisMovementDecomposition;
  hasCalibration: boolean;
}) {
  const sumBucketMetric = (
    selector: (bucket: BalanceBasisMovementDecomposition["buckets"][number]) => string | number | null | undefined,
  ) => {
    let total = 0;
    for (const bucket of decomposition.buckets) {
      const value = finiteMetric(selector(bucket));
      if (value === null) return null;
      total += value;
    }
    return total;
  };
  const currentTotal = sumBucketMetric((bucket) => bucket.current_balance);
  const residualTotal = sumBucketMetric((bucket) => bucket.residual_amount);
  const closingTotal = sumBucketMetric((bucket) => bucket.closing_check);

  return (
    <section
      id="balance-movement-analysis-basis-anchor"
      className="balance-movement-live-decomposition"
      data-testid="balance-movement-analysis-live-decomposition"
    >
      <div
        className="balance-movement-live-decomposition__content"
        data-testid="balance-movement-analysis-basis-decomposition"
      >
        <span className="balance-movement-sr-only">AC / OCI / TPL 驱动拆解</span>
        <header className="balance-movement-figma-header">
          <div>
            <span>04 / DRIVER DECOMPOSITION · LIVE</span>
            <h2>会计分类驱动拆解与口径状态</h2>
          </div>
          <p>
            report {decomposition.meta.report_date} · prior{" "}
            {decomposition.meta.prior_report_date ?? EM_DASH} · {decomposition.meta.currency_basis}
          </p>
        </header>

        <div className="balance-movement-live-decomposition__metrics">
          <article className="balance-movement-live-decomposition__metric balance-movement-live-decomposition__metric--positive">
            <span>覆盖率</span>
            <strong>{formatPct(decomposition.meta.coverage_pct)}</strong>
          </article>
          <article className="balance-movement-live-decomposition__metric">
            <span>期末合计</span>
            <strong>{formatYiCell(currentTotal)} 亿</strong>
          </article>
          <article className="balance-movement-live-decomposition__metric balance-movement-live-decomposition__metric--positive">
            <span>分解残差</span>
            <strong>{formatSignedYiCell(residualTotal)} 亿</strong>
          </article>
          <article className="balance-movement-live-decomposition__metric balance-movement-live-decomposition__metric--positive">
            <span>closing_check</span>
            <strong>{formatSignedYiCell(closingTotal)} 亿</strong>
          </article>
        </div>

        <div className="balance-movement-live-decomposition__buckets">
          {decomposition.buckets.map((bucket) => (
            <article
              key={bucket.basis_bucket}
              className="balance-movement-live-decomposition__bucket"
              data-bucket={bucket.basis_bucket}
            >
              <header>
                <div>
                  <h3>{bucket.basis_bucket}</h3>
                  <small>
                    {formatYiCell(bucket.previous_balance)} → {formatYiCell(bucket.current_balance)} 亿
                  </small>
                </div>
                <strong>{formatSignedYiCell(bucket.balance_change)} 亿</strong>
              </header>
              <span>科目组件 / 变动 / 绝对贡献</span>
              <ul>
                {bucket.rows.map((row) => (
                  <li
                    key={`${bucket.basis_bucket}-${row.component_key}`}
                    className="balance-movement-live-decomposition__component"
                    title={row.source_note}
                  >
                    <span>{row.component_label}</span>
                    <strong>{formatSignedYiCell(row.balance_change)}</strong>
                    <small>{row.is_supported ? formatPct(row.contribution_pct) : "未支持"}</small>
                  </li>
                ))}
              </ul>
              <footer>
                residual {formatSignedYiCell(bucket.residual_amount)} 亿 · closing_check{" "}
                {formatSignedYiCell(bucket.closing_check)} 亿
              </footer>
            </article>
          ))}
        </div>

        <div className="balance-movement-live-decomposition__availability">
          口径状态：{drilldownStatusLabel(decomposition.meta.status)} · {decomposition.meta.caveat} ·{" "}
          {decomposition.meta.source_scope} ·{" "}
          zqtz_calibration_analysis = {hasCalibration ? "available" : "null"} ·{" "}
          {hasCalibration
            ? "校准 payload 已返回，完整核对卡保留在数据治理区。"
            : "本期无校准 payload，页面不生成校准结论；仅展示正式分解与 closing_check。"}
        </div>
      </div>
    </section>
  );
}
function DataStatesGovernancePanel({
  isLoading,
  hasReportDates,
  hasRows,
  freshnessStatus,
  selectedDate,
  resolvedReportDate,
  hasError,
  refreshMessage,
  resultMeta,
  governanceMeta,
  supplementary,
}: {
  isLoading: boolean;
  hasReportDates: boolean;
  hasRows: boolean;
  freshnessStatus: BalanceMovementDatesPayload["freshness_status"] | undefined;
  selectedDate: string;
  resolvedReportDate: string;
  hasError: boolean;
  refreshMessage: string | null;
  resultMeta: ResultMeta | null;
  governanceMeta: { reportDate: string; ruleVersions: string[]; sourceVersions: string[] };
  supplementary?: ReactNode;
}) {
  const hasFallbackDate = Boolean(
    resultMeta?.fallback_date ||
      (selectedDate && resolvedReportDate && selectedDate !== resolvedReportDate),
  );
  const states = [
    {
      label: "加载中",
      value: isLoading ? "请求中" : "已完成",
      note: isLoading ? "筛选与操作保持可理解" : "不把旧数据伪装成新结果",
    },
    {
      label: "无报告日",
      value: hasReportDates ? "否" : "是",
      note: hasReportDates ? "已返回可选报告日" : "提示先物化读模型",
    },
    {
      label: "无明细行",
      value: hasRows ? "否" : "是",
      note: hasRows ? "AC / OCI / TPL 行已返回" : "正文显式展示空态",
    },
    {
      label: "读模型滞后",
      value: freshnessStatus === "read_model_lagging" ? "是" : "否",
      note: freshnessStatusDetail(freshnessStatus),
    },
    {
      label: "回退日期",
      value: hasFallbackDate ? resolvedReportDate || resultMeta?.fallback_date || "是" : "无",
      note: hasFallbackDate ? "requested 与 resolved 分开呈现" : "当前未发生日期回退",
    },
    {
      label: "加载 / 刷新失败",
      value: hasError ? "是" : "否",
      note: hasError ? refreshMessage ?? "显示错误，不回填 demo rows" : "当前没有加载或刷新错误",
    },
  ];
  const sourceVersion =
    resultMeta?.source_version ||
    (governanceMeta.sourceVersions.length ? governanceMeta.sourceVersions.join("、") : EM_DASH);
  const ruleVersion =
    resultMeta?.rule_version ||
    (governanceMeta.ruleVersions.length ? governanceMeta.ruleVersions.join("、") : EM_DASH);
  const fields = [
    ["quality_flag", resultMeta?.quality_flag ?? EM_DASH],
    ["fallback_mode", resultMeta?.fallback_mode ?? EM_DASH],
    ["generated_at", resultMeta?.generated_at ?? EM_DASH],
    ["trace_id", resultMeta?.trace_id ?? EM_DASH],
    ["tables_used", formatMetaList(resultMeta?.tables_used)],
    ["evidence_rows", resultMeta?.evidence_rows ?? EM_DASH],
    ["source_version", sourceVersion],
    ["rule_version", ruleVersion],
  ];
  const rules = [
    ["日期语义", "requested_report_date 与 resolved_report_date 分开呈现"],
    ["单位语义", "后端 yuan；页面仅换算为亿元，不重算正式指标"],
    ["空值语义", "null / undefined 保持缺失；0 仅表示正式零值"],
    ["回退语义", "fallback / stale 不得隐藏在调试面板"],
    ["CSV 边界", "基于当前响应本地生成，不调用独立导出 API"],
  ];

  return (
    <section
      className="balance-movement-data-states"
      data-testid="balance-movement-analysis-data-states"
    >
      <header className="balance-movement-figma-header">
        <div>
          <span>10 / DATA STATES &amp; GOVERNANCE</span>
          <h2>数据状态、回退语义与证据闭环</h2>
        </div>
        <p>
          quality {resultMeta?.quality_flag ?? EM_DASH} · freshness{" "}
          {freshnessStatusLabel(freshnessStatus)} · fallback{" "}
          {resultMeta?.fallback_mode ?? EM_DASH} · fail-closed
        </p>
      </header>

      <div className="balance-movement-data-states__states">
        {states.map((state) => (
          <article key={state.label} className="balance-movement-data-states__state">
            <strong>{state.label}</strong>
            <span>{state.value}</span>
            <small>{state.note}</small>
          </article>
        ))}
      </div>

      <div className="balance-movement-data-states__evidence">
        <header>
          <span>结果证据条 · 必显字段</span>
          <code>ApiEnvelope.result_meta + payload governance</code>
        </header>
        <div className="balance-movement-data-states__fields">
          {fields.map(([key, value]) => (
            <div key={String(key)}>
              <code>{key}</code>
              <span title={String(value)}>{value}</span>
            </div>
          ))}
        </div>
        <div className="balance-movement-data-states__rules">
          {rules.map(([label, value]) => (
            <div key={label}>
              <strong>{label}</strong>
              <span>{value}</span>
            </div>
          ))}
        </div>
      </div>

      {supplementary ? (
        <details className="balance-movement-data-states__pass">
          <summary>
            <strong>CONTRACT PASS CONDITION</strong>
            <span>
              所有状态均在正文可见；展开查看完整校准、控制科目与历史异常证据。
            </span>
          </summary>
          <div className="balance-movement-data-states__supplementary-content">
            {supplementary}
          </div>
        </details>
      ) : (
        <div className="balance-movement-data-states__pass">
          <strong>CONTRACT PASS CONDITION</strong>
          <span>
            所有无数据、过期、回退日期、失败和口径待确认状态均在页面正文可见；不依赖调试工具。
          </span>
        </div>
      )}
    </section>
  );
}
function DrilldownUnavailablePanel({
  testId,
  eyebrow,
  title,
  fieldName,
}: {
  testId: string;
  eyebrow: string;
  title: string;
  fieldName: string;
}) {
  return (
    <section
      className="balance-movement-derived-panel balance-movement-derived-panel--unavailable"
      data-testid={testId}
    >
      <div className="balance-movement-derived-panel__header">
        <div>
          <span>{eyebrow}</span>
          <h2>{title}</h2>
        </div>
        <strong>未返回</strong>
      </div>
      <div className="balance-movement-derived-empty">
        <span>数据状态</span>
        <p>当前接口未返回 {fieldName}，本分析模块已预留位置但暂无可展示明细。</p>
      </div>
    </section>
  );
}

function finiteMetric(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function ZqtzMaturityStructurePanel({
  structure,
}: {
  structure: BalanceZqtzMaturityStructure;
}) {
  const isUnknownBucket = (bucket: BalanceZqtzMaturityStructure["buckets"][number]) =>
    bucket.maturity_bucket.toLowerCase().includes("unknown") || bucket.bucket_label === "未映射";
  const maxCurrent = Math.max(
    0,
    ...structure.buckets.map((bucket) => Math.abs(finiteMetric(bucket.current_amount) ?? 0)),
  );
  const largestMappedBucket = [...structure.buckets]
    .filter((bucket) => !isUnknownBucket(bucket))
    .sort(
      (left, right) =>
        Math.abs(finiteMetric(right.current_amount) ?? 0) -
        Math.abs(finiteMetric(left.current_amount) ?? 0),
    )[0];
  const unknownBucket = structure.buckets.find(isUnknownBucket);

  return (
    <section
      id="balance-movement-analysis-coverage-anchor"
      className="balance-movement-figma-panel balance-movement-maturity-panel"
      data-testid="balance-movement-analysis-zqtz-maturity"
    >
      <div className="balance-movement-figma-panel__header">
        <div>
          <span>05 / ZQTZ MATURITY STRUCTURE</span>
          <h2>期限 / 到期结构完整明细</h2>
        </div>
        <p>
          zqtz_maturity_structure · {structure.meta.report_date}
          {structure.meta.prior_report_date ? ` / ${structure.meta.prior_report_date}` : ""}
        </p>
      </div>

      <div className="balance-movement-maturity-kpis" aria-label="到期结构关键指标">
        <div>
          <span>覆盖率</span>
          <strong className="balance-movement-tone--positive">{formatPct(structure.meta.coverage_pct)}</strong>
          <small>{drilldownStatusLabel(structure.meta.status)}</small>
        </div>
        <div>
          <span>未知到期金额</span>
          <strong className="balance-movement-tone--warning">{formatYiCell(structure.meta.unknown_total)} 亿</strong>
          <small>{formatPct(unknownBucket?.share_pct)} · {unknownBucket?.item_count ?? 0} 笔</small>
        </div>
        <div>
          <span>最大期限桶</span>
          <strong className="balance-movement-tone--warning">{largestMappedBucket?.bucket_label ?? EM_DASH}</strong>
          <small>{formatPct(largestMappedBucket?.share_pct)} · {formatYiCell(largestMappedBucket?.current_amount)} 亿</small>
        </div>
        <div>
          <span>口径</span>
          <strong>CNX 页面 / CNY ZQTZ</strong>
          <small>unit = yuan</small>
        </div>
      </div>

      <div className="balance-movement-maturity-ladder" data-testid="balance-movement-analysis-maturity-ladder">
        <div className="balance-movement-maturity-ladder__heading">
          <div>
            <strong>期限分布 / Maturity Ladder</strong>
            <span>
              {largestMappedBucket?.bucket_label ?? EM_DASH}为最大期限桶 · {formatYiCell(largestMappedBucket?.current_amount)} 亿 · {formatPct(largestMappedBucket?.share_pct)}
            </span>
          </div>
          <p>期末余额（亿元） · 较上期 · linear scale</p>
        </div>
        <div className="balance-movement-maturity-ladder__plot">
          {structure.buckets.map((bucket) => {
            const isUnknown = isUnknownBucket(bucket);
            const currentAmount = Math.abs(finiteMetric(bucket.current_amount) ?? 0);
            const barHeight = maxCurrent > 0 ? Math.max(1.5, Math.min(100, (currentAmount / maxCurrent) * 100)) : 0;
            return (
              <div
                key={bucket.maturity_bucket}
                className={isUnknown ? "balance-movement-maturity-ladder__bucket balance-movement-maturity-ladder__bucket--unknown" : "balance-movement-maturity-ladder__bucket"}
              >
                <div className="balance-movement-maturity-ladder__readout">
                  <strong>{formatYiCell(bucket.current_amount)} · {formatPct(bucket.share_pct)}</strong>
                  <span className={moveDeltaToneClass(finiteMetric(bucket.delta_amount))}>{formatSignedYiCell(bucket.delta_amount)} 亿</span>
                </div>
                <div className="balance-movement-maturity-ladder__bar-track">
                  <svg className="balance-movement-maturity-ladder__bar" viewBox="0 0 40 100" preserveAspectRatio="none" aria-hidden>
                    <rect className={isUnknown ? "balance-movement-maturity-ladder__bar-value balance-movement-maturity-ladder__bar-value--unknown" : "balance-movement-maturity-ladder__bar-value"} x="0" y={100 - barHeight} width="40" height={barHeight} rx="2" />
                  </svg>
                </div>
                <strong>{isUnknown ? "Unknown" : bucket.bucket_label}</strong>
              </div>
            );
          })}
        </div>
      </div>

      <p className="balance-movement-figma-callout">
        <span>SCOPE</span>金融投资资产一级明细；到期日缺失进入 Unknown，且不并入其他期限桶。{structure.meta.caveat}
      </p>
      <div className="balance-movement-derived-table-wrap">
        <table className="balance-movement-figma-table">
          <thead>
            <tr>
              <th>期限桶</th>
              <th>期末</th>
              <th>上期</th>
              <th>较上期</th>
              <th>占比</th>
              <th>笔数</th>
            </tr>
          </thead>
          <tbody>
            {structure.buckets.map((bucket) => (
              <tr key={bucket.maturity_bucket} className={isUnknownBucket(bucket) ? "balance-movement-figma-table__row--unknown" : undefined}>
                <th scope="row">{bucket.bucket_label}</th>
                <td>{formatYiCell(bucket.current_amount)} 亿</td>
                <td>{formatYiCell(bucket.prior_amount)} 亿</td>
                <td className={moveDeltaToneClass(finiteMetric(bucket.delta_amount))}>{formatSignedYiCell(bucket.delta_amount)} 亿</td>
                <td>{formatPct(bucket.share_pct)}</td>
                <td>{bucket.item_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="balance-movement-maturity-footer">
        <span>eligible_total · {formatYiCell(structure.meta.eligible_total)} 亿</span>
        <span className="balance-movement-tone--positive">covered_total · {formatYiCell(structure.meta.covered_total)} 亿</span>
        <span className="balance-movement-tone--warning">unknown_total · {formatYiCell(structure.meta.unknown_total)} 亿</span>
      </div>
    </section>
  );
}

type ConcentrationDimension = BalanceZqtzConcentrationAnalysis["dimensions"][number];
type ConcentrationItem = ConcentrationDimension["items"][number];

function ConcentrationRow({
  item,
  compact = false,
}: {
  item: ConcentrationItem;
  compact?: boolean;
}) {
  const share = Math.abs(finiteMetric(item.share_pct) ?? 0);
  return (
    <div
      className={`balance-movement-concentration-row balance-movement-concentration-row--${item.item_kind}${compact ? " balance-movement-concentration-row--compact" : ""}`}
    >
      <span className="balance-movement-concentration-row__rank">
        {item.rank > 0 ? item.rank : item.item_kind === "unknown" ? EM_DASH : "–"}
      </span>
      <strong title={item.dimension_value}>{item.dimension_value}</strong>
      <progress max={100} value={share} aria-label={`${item.dimension_value} ${formatPct(item.share_pct)}`} />
      <span>{formatYiCell(item.current_amount)}</span>
      <em className={moveDeltaToneClass(finiteMetric(item.delta_amount))}>
        {formatSignedYiCell(item.delta_amount)}
      </em>
      <span>{formatPct(item.share_pct)}</span>
    </div>
  );
}

function ConcentrationDistribution({
  dimension,
  variant,
}: {
  dimension: ConcentrationDimension;
  variant: "issuer" | "rating" | "industry";
}) {
  const isIssuer = variant === "issuer";
  return (
    <article className={`balance-movement-concentration-card balance-movement-concentration-card--${variant}`}>
      <div className="balance-movement-concentration-card__header">
        <div>
          <h3>{concentrationDimensionLabel(dimension.dimension)} / {variant === "issuer" ? "Issuer" : variant === "rating" ? "Rating" : "Industry"}</h3>
          {isIssuer ? <p>Top 10 以本期金额排序；Other 与 Unknown 独立保留。</p> : null}
        </div>
        <strong>{drilldownStatusLabel(dimension.status)} · {isIssuer ? `coverage ${formatPct(dimension.coverage_pct)}` : variant === "rating" ? `${dimension.items.length} buckets` : `Top ${dimension.items.filter((item) => item.rank > 0).length}`}</strong>
      </div>
      {isIssuer ? (
        <div className="balance-movement-concentration-card__metrics">
          <span>HHI <strong>{formatPlainNumber(dimension.hhi)}</strong></span>
          <span>Top5 <strong>{formatPct(dimension.top5_share_pct)}</strong></span>
          <span>Other <strong>{formatPct(dimension.items.find((item) => item.item_kind === "other")?.share_pct)}</strong></span>
        </div>
      ) : (
        <p className="balance-movement-concentration-card__meta">
          coverage {formatPct(dimension.coverage_pct)} · HHI {formatPlainNumber(dimension.hhi)} · Top5 {formatPct(dimension.top5_share_pct)}
        </p>
      )}
      {dimension.items.length > 0 ? (
        <div className="balance-movement-concentration-rows">
          {dimension.items.map((item) => (
            <ConcentrationRow
              key={`${dimension.dimension}-${item.item_kind}-${item.rank}-${item.dimension_value}`}
              item={item}
              compact={!isIssuer}
            />
          ))}
        </div>
      ) : (
        <div className="balance-movement-concentration-empty">当前维度无可展示排名</div>
      )}
      {dimension.caveat ? (
        <p className="balance-movement-concentration-card__caveat">{dimension.caveat}</p>
      ) : null}
    </article>
  );
}

function ZqtzConcentrationAnalysisPanel({
  analysis,
}: {
  analysis: BalanceZqtzConcentrationAnalysis;
}) {
  const issuer = analysis.dimensions.find((dimension) => dimension.dimension === "issuer_name");
  const rating = analysis.dimensions.find((dimension) => dimension.dimension === "rating");
  const industry = analysis.dimensions.find((dimension) => dimension.dimension === "industry_name");
  const coverageText = analysis.meta.coverage_pct === null || analysis.meta.coverage_pct === undefined
    ? "各维度见分区"
    : formatPct(analysis.meta.coverage_pct);

  return (
    <section
      className="balance-movement-figma-panel balance-movement-concentration-panel"
      data-testid="balance-movement-analysis-zqtz-concentration"
    >
      <div className="balance-movement-figma-panel__header">
        <div>
          <span>06 / ZQTZ CONCENTRATION ANALYSIS</span>
          <h2>主体 / 评级 / 行业集中度完整视图</h2>
        </div>
        <p>report {analysis.meta.report_date} · top_n 10 · Other / Unknown 分列</p>
      </div>
      <div className="balance-movement-concentration-signal" aria-label="集中度关键指标">
        <div><span>最低维度覆盖</span><strong className="balance-movement-tone--warning">{coverageText} · Rating</strong></div>
        <div><span>期末合计</span><strong>{formatYiCell(analysis.meta.eligible_total)} 亿</strong></div>
        <div><span>未知维度金额</span><strong className="balance-movement-tone--warning">{formatYiCell(analysis.meta.unknown_total)} 亿</strong></div>
        <div><span>数据日期</span><strong className="balance-movement-tone--positive">{analysis.meta.report_date} · fresh</strong></div>
      </div>
      <div className="balance-movement-concentration-layout">
        {issuer ? <ConcentrationDistribution dimension={issuer} variant="issuer" /> : null}
        <div className="balance-movement-concentration-layout__secondary">
          {rating ? <ConcentrationDistribution dimension={rating} variant="rating" /> : null}
          {industry ? <ConcentrationDistribution dimension={industry} variant="industry" /> : null}
        </div>
      </div>
      <p className="balance-movement-concentration-governance">
        <span>HHI GOVERNANCE</span>{analysis.meta.caveat} 接口返回 HHI 数值；页面不自行定义风险等级，未知维度必须显式保留。<strong>NO LOCAL RISK BAND</strong>
      </p>
    </section>
  );
}
function BusinessMoverPanel({
  moves,
  testId,
  title,
  subtitle,
}: {
  moves: BusinessMomMove[];
  testId: string;
  title: string;
  subtitle: string;
}) {
  const maxDelta = Math.max(0, ...moves.map((move) => Math.abs(move.deltaYuan)));
  return (
    <article className="balance-movement-mover-panel">
      <div className="balance-movement-mover-panel__header">
        <h3>{title}</h3>
        <div><span>{subtitle}</span><small>同一零轴 · 单位亿元</small></div>
      </div>
      <div data-testid={testId} className="balance-movement-mover-panel__rows" role="list">
        {moves.map((item, index) => (
          <div
            key={`${item.rowKey}-${item.side}-${testId}-${index}`}
            className="balance-movement-mover-row"
            role="listitem"
            title={`${sourceKindLabel(item.sourceKind)} · ${sourceNotePreview(item.sourceNote)}`}
          >
            <div className="balance-movement-mover-row__label">
              <strong>{item.label}</strong>
              <span>{formatPlainNumber(item.previousYuan / 100000000)} → {formatPlainNumber(item.currentYuan / 100000000)}</span>
              <span data-testid="balance-movement-analysis-business-top-moves-source" className="balance-movement-sr-only">
                {sourceKindLabel(item.sourceKind)} {sourceNotePreview(item.sourceNote)}
              </span>
            </div>
            <div className="balance-movement-mover-axis" aria-hidden>
              <i />
              <progress
                className={item.deltaYuan >= 0 ? "balance-movement-mover-axis__bar balance-movement-mover-axis__bar--up" : "balance-movement-mover-axis__bar balance-movement-mover-axis__bar--down"}
                max={maxDelta || 1}
                value={Math.abs(item.deltaYuan)}
              />
            </div>
            <strong className={moveDeltaToneClass(item.deltaYuan)}>{formatSignedYiNumber(item.deltaYuan / 100000000)}</strong>
          </div>
        ))}
      </div>
    </article>
  );
}
export default function BalanceMovementAnalysisPage() {
  const client = useApiClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryReportDate = searchParams.get("report_date")?.trim() || "";
  const rawQueryCurrencyBasis = searchParams.get("currency_basis")?.trim().toUpperCase() || "";
  const queryCurrencyBasis = normalizeMovementCurrencyBasis(rawQueryCurrencyBasis);
  const [selectedDate, setSelectedDate] = useState("");
  const [currencyBasis, setCurrencyBasis] = useState(queryCurrencyBasis);
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
    if (rawQueryCurrencyBasis && rawQueryCurrencyBasis !== "CNX") {
      const canonicalParams = new URLSearchParams(searchParams);
      canonicalParams.set("currency_basis", "CNX");
      setSearchParams(canonicalParams, { replace: true });
    }
  }, [rawQueryCurrencyBasis, searchParams, setSearchParams]);

  useEffect(() => {
    if (currencyBasis !== queryCurrencyBasis) {
      setCurrencyBasis(queryCurrencyBasis);
      setSelectedDate("");
    }
  }, [currencyBasis, queryCurrencyBasis]);

  useEffect(() => {
    if (!reportDates.length) {
      return;
    }
    if (queryReportDate && reportDates.includes(queryReportDate)) {
      if (selectedDate !== queryReportDate) {
        setSelectedDate(queryReportDate);
      }
      return;
    }
    if (!selectedDate || !reportDates.includes(selectedDate)) {
      setSelectedDate(reportDates[0] ?? "");
    }
  }, [queryReportDate, reportDates, selectedDate]);

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
  const resultMeta = detailQuery.data?.result_meta ?? null;
  const resultStatusReasons = resultMeta
    ? [
        resultMeta.quality_flag !== "ok" ? `质量标记 ${resultMeta.quality_flag}` : null,
        resultMeta.fallback_mode !== "none"
          ? `降级模式 ${resultMeta.fallback_mode}`
          : null,
        resultMeta.requested_report_date
          ? `请求报告日 ${resultMeta.requested_report_date}`
          : null,
        resultMeta.resolved_report_date
          ? `实际快照日 ${resultMeta.resolved_report_date}`
          : null,
        resultMeta.fallback_date ? `回退日期 ${resultMeta.fallback_date}` : null,
      ].filter((reason): reason is string => Boolean(reason))
    : [];
  const hasResultStatus = Boolean(
    resultMeta &&
      (resultMeta.quality_flag !== "ok" ||
        resultMeta.fallback_mode !== "none" ||
        Boolean(resultMeta.fallback_date) ||
        (Boolean(resultMeta.requested_report_date) &&
          Boolean(resultMeta.resolved_report_date) &&
          resultMeta.requested_report_date !== resultMeta.resolved_report_date)),
  );
  const balanceChangeTotal = summary?.balance_change_total;
  const hasBalanceChangeTotal =
    balanceChangeTotal !== null &&
    balanceChangeTotal !== undefined &&
    balanceChangeTotal !== "" &&
    Number.isFinite(Number(balanceChangeTotal));
  const accountingByReportDate = useMemo(() => {
    const map = new Map<string, BalanceMovementTrendMonth>();
    for (const month of accountingMatrixMonths) {
      map.set(month.report_date, month);
    }
    return map;
  }, [accountingMatrixMonths]);
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
          if (accountingTotal === undefined) {
            return interbankAssetTotal.value;
          }
          return interbankAssetTotal.value === null
            ? accountingTotal
            : accountingTotal + interbankAssetTotal.value;
        },
        getCellMeta: (month) => {
          const interbankAssetTotal = sumBusinessMatrixRowValues(month, businessMatrixAssetRows);
          return interbankAssetTotal.hasMissingInputs ? { hasMissingInputs: true } : undefined;
        },
      },
      {
        key: "liability-total",
        label: "负债端合计",
        side: "total",
        sourceNote: "负债端同业业务行合计",
        sourceKind: "ledger",
        valueKind: "amount",
        getValue: (month) => sumBusinessMatrixRowValues(month, businessMatrixLiabilityRows).value,
        getCellMeta: (month) => {
          const liabilityTotal = sumBusinessMatrixRowValues(month, businessMatrixLiabilityRows);
          return liabilityTotal.hasMissingInputs ? { hasMissingInputs: true } : undefined;
        },
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
          const liabilityTotal = sumBusinessMatrixRowValues(month, businessMatrixLiabilityRows);
          const assetTotal =
            accountingTotal === undefined
              ? interbankAssetTotal.value
              : interbankAssetTotal.value === null
                ? accountingTotal
                : accountingTotal + interbankAssetTotal.value;
          if (assetTotal === null || assetTotal === undefined) {
            return liabilityTotal.value;
          }
          return liabilityTotal.value === null ? assetTotal : assetTotal + liabilityTotal.value;
        },
        getCellMeta: (month) => {
          const interbankAssetTotal = sumBusinessMatrixRowValues(month, businessMatrixAssetRows);
          const liabilityTotal = sumBusinessMatrixRowValues(month, businessMatrixLiabilityRows);
          return interbankAssetTotal.hasMissingInputs || liabilityTotal.hasMissingInputs
            ? { hasMissingInputs: true }
            : undefined;
        },
      },
    ];
  }, [accountingByReportDate, businessMatrixAssetRows, businessMatrixLiabilityRows]);
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
  const balanceStructureChartRows = useMemo(() => {
    const chartRows: AccountingBasisStackedSharePoint[] = [];
    for (const point of balanceStructureTrend) {
      const chartPoint = toCompleteSharePoint(point);
      if (chartPoint === null) {
        return [];
      }
      chartRows.push(chartPoint);
    }
    return chartRows;
  }, [balanceStructureTrend]);
  const balanceStructureInsight = useMemo(() => {
    const first = balanceStructureTrend[0]
      ? toCompleteSharePoint(balanceStructureTrend[0])
      : null;
    const latest = balanceStructureTrend[balanceStructureTrend.length - 1]
      ? toCompleteSharePoint(balanceStructureTrend[balanceStructureTrend.length - 1])
      : null;
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
      movementDrivers.filter(
        (
          driver,
        ): driver is BalanceMovementDriver & {
          shareDelta: number;
        } => driver.shareDelta !== null && Number.isFinite(driver.shareDelta),
      ).sort(
        (left, right) => Math.abs(right.shareDelta) - Math.abs(left.shareDelta),
      )[0],
    [movementDrivers],
  );

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
  const summaryHasCompleteBuckets = summary?.bucket_count === balanceMovementBuckets.length;
  const summaryAllBucketsMatched =
    summary?.matched_bucket_count === balanceMovementBuckets.length;
  const reconciliationLabel =
    rows.length === 0
      ? "待数据"
      : !reconAggregate.hasExactBuckets || !summaryHasCompleteBuckets
        ? "分桶不完整"
        : reconAggregate.allMatched && summaryAllBucketsMatched
          ? "三桶一致"
          : reconciliationConcernLabel(reconAggregate.counts);
  const previousBalanceTotal = finiteMetric(summary?.previous_balance_total);
  const balanceChangeValue = finiteMetric(balanceChangeTotal);
  const balanceChangePct =
    previousBalanceTotal !== null && previousBalanceTotal !== 0 && balanceChangeValue !== null
      ? (balanceChangeValue / previousBalanceTotal) * 100
      : null;
  const compactMaturityGroups = useMemo<CompactMaturityGroup[]>(() => {
    type MaturityBucketKey = BalanceZqtzMaturityStructure["buckets"][number]["maturity_bucket"];
    const definitions: Array<{ key: string; label: string; buckets: MaturityBucketKey[] }> = [
      {
        key: "within-90d",
        label: "≤90天",
        buckets: ["overdue_or_matured", "<=30d", "31-90d"],
      },
      { key: "91d-1y", label: "91天–1年", buckets: ["91d-1y"] },
      { key: "1-3y", label: "1–3年", buckets: ["1-3y"] },
      { key: "over-3y", label: ">3年", buckets: ["3-5y", ">5y"] },
    ];
    return definitions.map((definition) => {
      const buckets = (zqtzMaturityStructure?.buckets ?? []).filter((bucket) =>
        definition.buckets.includes(bucket.maturity_bucket),
      );
      const currentValues = buckets.map((bucket) => finiteMetric(bucket.current_amount));
      const deltaValues = buckets.map((bucket) => finiteMetric(bucket.delta_amount));
      const shareValues = buckets.map((bucket) => finiteMetric(bucket.share_pct));
      return {
        key: definition.key,
        label: definition.label,
        currentAmount:
          buckets.length > 0 && currentValues.every((value): value is number => value !== null)
            ? currentValues.reduce((total, value) => total + value, 0)
            : null,
        deltaAmount:
          buckets.length > 0 && deltaValues.every((value): value is number => value !== null)
            ? deltaValues.reduce((total, value) => total + value, 0)
            : null,
        sharePct:
          buckets.length > 0 && shareValues.every((value): value is number => value !== null)
            ? shareValues.reduce((total, value) => total + value, 0)
            : null,
      };
    });
  }, [zqtzMaturityStructure]);
  const issuerConcentration = useMemo(
    () =>
      zqtzConcentrationAnalysis?.dimensions.find(
        (dimension) => dimension.dimension === "issuer_name",
      ) ?? null,
    [zqtzConcentrationAnalysis],
  );
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
  const historicalAnomalyDiagnostics = useMemo(
    () =>
      buildHistoricalAnomalyDiagnostics({
        trendMonths,
        businessTrendMonths,
        businessRows: businessMatrixRows,
      }),
    [businessMatrixRows, businessTrendMonths, trendMonths],
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
      getValue: (month) => sumPrimaryZqtzAssetDetailRows(month, zqtzAssetDetailRows).value,
      getCellMeta: (month) => {
        const summary = sumPrimaryZqtzAssetDetailRows(month, zqtzAssetDetailRows);
        return summary.hasMissingInputs ? { hasMissingInputs: true } : undefined;
      },
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

  const unsupportedWaterfallComponents = useMemo(
    () =>
      differenceAttributionWaterfall?.components.filter(
        (component) => component.is_supported === false,
      ) ?? [],
    [differenceAttributionWaterfall],
  );
  const residualWaterfallComponent = useMemo(
    () => differenceAttributionWaterfall?.components.find((component) => component.is_residual),
    [differenceAttributionWaterfall],
  );
  const explanationClosure = useMemo(
    () =>
      buildExplanationClosure({
        waterfall: differenceAttributionWaterfall,
        summary: detailQuery.data?.result.summary ?? null,
      }),
    [differenceAttributionWaterfall, detailQuery.data?.result.summary],
  );
  const analysisDimensionCards = useMemo<AnalysisDimensionCard[]>(() => {
    const businessTopMove = businessTopMomMoves[0];
    const unsupportedLabels = unsupportedWaterfallComponents.map((component) => component.component_label);
    const maturityCoverage = zqtzMaturityStructure
      ? formatPct(zqtzMaturityStructure.meta.coverage_pct)
      : EM_DASH;
    const concentrationCoverage = zqtzConcentrationAnalysis
      ? formatPct(zqtzConcentrationAnalysis.meta.coverage_pct)
      : EM_DASH;
    return [
      {
        key: "business",
        title: "业务品类 Top 变动",
        metric: businessTopMove
          ? `${businessTopMove.label} ${formatSignedYiCell(businessTopMove.deltaYuan)} 亿`
          : "暂无连续业务行",
        detail: businessTopMove
          ? `${sourceKindLabel(businessTopMove.sourceKind)} · ${sourceNotePreview(businessTopMove.sourceNote)}`
          : "需要至少两个连续报告月。",
        href: "#balance-movement-analysis-business-summary-anchor",
        tags: businessTopMove
          ? [{ label: "主导变动", tone: "info" }]
          : [{ label: "样本不足", tone: "unknown" }],
        evidence: [
          {
            label: "维度字段",
            value: "业务趋势月 / 品类衍生行",
            note: "business_trend_months / product category derived rows",
          },
          {
            label: "Top 变动",
            value: businessTopMove
              ? `${businessTopMove.label} ${formatSignedYiCell(businessTopMove.deltaYuan)} 亿`
              : EM_DASH,
          },
          {
            label: "来源说明",
            value: businessTopMove ? sourceNotePreview(businessTopMove.sourceNote) : "样本不足",
          },
          { label: "追踪标识", value: resultMeta?.trace_id ?? EM_DASH },
        ],
      },
      {
        key: "basis",
        title: "AC / OCI / FVTPL",
        metric: topMovementDriver
          ? `${topMovementDriver.bucket} ${formatSignedYiNumber(topMovementDriver.balanceChangeYi)} 亿`
          : "暂无分桶变动",
        detail: topMovementDriver
          ? `贡献 ${formatPct(topMovementDriver.contributionPct)} · 期末占比 ${formatPct(topMovementDriver.currentBalancePct)}`
          : "等待 AC/OCI/TPL 读模型返回。",
        href: "#balance-movement-analysis-basis-anchor",
        tags: [
          { label: "主导分桶", tone: "info" },
          ...(trendMoMDriverBucket && structureShareDriverBucket && trendMoMDriverBucket !== structureShareDriverBucket
            ? [{ label: "结构迁移", tone: "warn" as const }]
            : []),
        ],
        evidence: [
          {
            label: "维度字段",
            value: "分桶 / 余额变动 / 贡献占比",
            note: "rows[].basis_bucket / balance_change / contribution_pct",
          },
          { label: "主导分桶", value: topMovementDriver?.bucket ?? EM_DASH },
          { label: "规则版本", value: resultMeta?.rule_version ?? EM_DASH },
          { label: "源版本", value: resultMeta?.source_version ?? EM_DASH },
        ],
      },
      {
        key: "residual",
        title: "对账残差",
        metric: residualWaterfallComponent
          ? `${formatSignedYiCell(residualWaterfallComponent.amount)} 亿`
          : "暂无残差项",
        detail:
          unsupportedLabels.length > 0
            ? `${unsupportedLabels.join("、")} 未支持，不反推`
            : "当前瀑布未返回待补口径。",
        href: "#balance-movement-analysis-residual-anchor",
        tags: [
          {
            label: unsupportedLabels.length > 0 ? "口径待补" : "残差闭合",
            tone: residualTone(explanationClosure?.residualRatioPct ?? null, unsupportedLabels.length),
          },
        ],
        evidence: [
          {
            label: "维度字段",
            value: "差异归因瀑布组件",
            note: "difference_attribution_waterfall.components",
          },
          {
            label: "残差",
            value: residualWaterfallComponent
              ? `${formatSignedYiCell(residualWaterfallComponent.amount)} 亿`
              : EM_DASH,
          },
          {
            label: "未支持项",
            value: unsupportedLabels.join("、") || "无",
            note: "未支持，不反推",
          },
          { label: "追踪标识", value: resultMeta?.trace_id ?? EM_DASH },
          { label: "规则版本", value: resultMeta?.rule_version ?? EM_DASH },
          { label: "源版本", value: resultMeta?.source_version ?? EM_DASH },
          { label: "使用表", value: formatMetaList(resultMeta?.tables_used) },
          {
            label: "证据行数",
            value:
              resultMeta?.evidence_rows === null || resultMeta?.evidence_rows === undefined
                ? EM_DASH
                : String(resultMeta.evidence_rows),
          },
          { label: "限制", value: "估值差和外币折算差没有可闭合字段，不在前端反算。" },
        ],
      },
      {
        key: "coverage",
        title: "期限 / 集中度覆盖",
        metric: `期限 ${maturityCoverage} / 集中度 ${concentrationCoverage}`,
        detail: `期限 ${drilldownStatusLabel(zqtzMaturityStructure?.meta.status)} · 集中度 ${drilldownStatusLabel(zqtzConcentrationAnalysis?.meta.status)}`,
        href: "#balance-movement-analysis-coverage-anchor",
        tags: [
          {
            label: `期限覆盖`,
            tone: coverageTone(zqtzMaturityStructure?.meta.coverage_pct),
          },
          {
            label: `集中度覆盖`,
            tone: coverageTone(zqtzConcentrationAnalysis?.meta.coverage_pct),
          },
        ],
        evidence: [
          { label: "期限覆盖", value: maturityCoverage },
          { label: "集中度覆盖", value: concentrationCoverage },
          {
            label: "期限状态",
            value: drilldownStatusLabel(zqtzMaturityStructure?.meta.status),
          },
          {
            label: "集中度状态",
            value: drilldownStatusLabel(zqtzConcentrationAnalysis?.meta.status),
          },
          { label: "追踪标识", value: resultMeta?.trace_id ?? EM_DASH },
        ],
      },
    ];
  }, [
    businessTopMomMoves,
    explanationClosure,
    resultMeta,
    residualWaterfallComponent,
    structureShareDriverBucket,
    topMovementDriver,
    trendMoMDriverBucket,
    unsupportedWaterfallComponents,
    zqtzConcentrationAnalysis,
    zqtzMaturityStructure,
  ]);

  const governanceMeta = useMemo(() => {
    const reportDate = detailQuery.data?.result.report_date ?? "";
    const ruleVersions = uniqueNonEmptyStrings(rows.map((row) => String(row.rule_version ?? "")));
    const sourceVersions = uniqueNonEmptyStrings(rows.map((row) => String(row.source_version ?? "")));
    return { reportDate, ruleVersions, sourceVersions };
  }, [detailQuery.data?.result.report_date, rows]);

  function updateReportDateSelection(reportDate: string) {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("report_date", reportDate);
    nextParams.set("currency_basis", "CNX");
    setSearchParams(nextParams, { replace: true });
    setSelectedDate(reportDate);
  }

  async function handleRefresh() {
    if (!selectedDate) {
      return;
    }
    const refreshReportDate =
      datesQuery.data?.result.freshness_status === "read_model_lagging"
        ? datesQuery.data.result.latest_upstream_control_report_date ?? selectedDate
        : selectedDate;
    const refreshTargetWasMaterialized =
      datesQuery.data?.result.report_dates.includes(refreshReportDate) ?? false;
    setIsRefreshing(true);
    setRefreshMessage(null);
    try {
      const payload = await client.refreshBalanceMovementAnalysis({
        reportDate: refreshReportDate,
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
      const rowCountText =
        typeof payload.row_count === "number" ? `${payload.row_count} 行` : "已排队";
      setRefreshMessage(`${payload.status}: ${rowCountText}${refreshDetail}`);
      const applyRefreshedDate = async () => {
        const refreshedDates = await datesQuery.refetch();
        if (!refreshedDates.data?.result.report_dates.includes(refreshReportDate)) {
          return false;
        }
        if (refreshReportDate === selectedDate) {
          await detailQuery.refetch();
        } else {
          updateReportDateSelection(refreshReportDate);
        }
        return true;
      };

      if (payload.status === "queued") {
        if (refreshTargetWasMaterialized) {
          setRefreshMessage(
            `queued: ${refreshReportDate} \u540e\u53f0\u5904\u7406\u4e2d\uff0c\u8bf7\u7a0d\u540e\u5237\u65b0`,
          );
          return;
        }
        const maxPollAttempts = 30;
        for (let attempt = 0; attempt < maxPollAttempts; attempt += 1) {
          if (await applyRefreshedDate()) {
            setRefreshMessage(`completed: ${refreshReportDate} \u5df2\u66f4\u65b0`);
            return;
          }
          if (attempt < maxPollAttempts - 1) {
            await new Promise<void>((resolve) => {
              window.setTimeout(resolve, 1_000);
            });
          }
        }
        setRefreshMessage(
          `queued: ${refreshReportDate} \u540e\u53f0\u5904\u7406\u4e2d\uff0c\u8bf7\u7a0d\u540e\u5237\u65b0`,
        );
        return;
      }
      await applyRefreshedDate();
    } finally {
      setIsRefreshing(false);
    }
  }

  function handleExportCsv() {
    if (!detailQuery.data) {
      return;
    }
    const csv = buildBalanceMovementCsv({
      result: detailQuery.data.result,
      resultMeta,
      businessTopMove: businessTopMomMoves[0],
      accountingTopDriver: topMovementDriver,
      residualComponent: residualWaterfallComponent,
      unsupportedComponents: unsupportedWaterfallComponents,
      maturityStructure: zqtzMaturityStructure,
      concentrationAnalysis: zqtzConcentrationAnalysis,
      explanationClosure,
      dimensionCards: analysisDimensionCards,
      historicalAnomalyDiagnostics,
    });
    downloadCsv(
      `balance-movement-analysis-${detailQuery.data.result.report_date}-${detailQuery.data.result.currency_basis}.csv`,
      csv,
    );
  }

  return (
    <section
      data-testid="balance-movement-analysis-page"
      data-moss-theme-scope="balance-movement-analysis"
      className="balance-movement-page theme-dh-api"
    >
      <header className="balance-movement-page-header" data-testid="balance-movement-analysis-page-header">
        <div className="balance-movement-page-header__identity">
          <span>投资组合 / 资产结构</span>
          <h1 data-testid="balance-movement-analysis-title">资产余额变动分析</h1>
        </div>
        <div className="balance-movement-page-header__actions">
          <label>
            <span>报告日</span>
            <select
              aria-label="余额变动分析-报告日期"
              value={selectedDate}
              onChange={(event) => updateReportDateSelection(event.target.value)}
            >
              {reportDates.map((reportDate) => (
                <option key={reportDate} value={reportDate}>{reportDate}</option>
              ))}
            </select>
          </label>
          <label className="balance-movement-page-header__currency">
            <span>币种</span>
            <select
              aria-label="余额变动分析-控制币种"
              value={currencyBasis}
              disabled
              title="当前页面仅开放 CNX 正式口径"
            >
              <option value="CNX">CNX</option>
            </select>
          </label>
          <button
            type="button"
            data-testid="balance-movement-analysis-refresh"
            onClick={() => void handleRefresh()}
            disabled={!selectedDate || isRefreshing}
          >
            {isRefreshing ? "刷新中" : "刷新数据"}
          </button>
          <button
            type="button"
            data-testid="balance-movement-analysis-export-csv"
            onClick={handleExportCsv}
            disabled={!detailQuery.data}
          >
            导出 CSV
          </button>
        </div>
      </header>
      <div className="balance-movement-page-body">
        {refreshMessage ? (
          <div className="balance-movement-refresh-message" data-testid="balance-movement-analysis-refresh-message">
            {refreshMessage}
          </div>
        ) : null}
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
        {hasResultStatus ? (
          <div className="balance-movement-quality-alert" data-testid="balance-movement-analysis-result-status">
            <DataQualityBanner resultMeta={resultMeta} degradedReasons={resultStatusReasons} />
            <div data-testid="balance-movement-analysis-result-status-facts" role="status">
              {resultStatusReasons.join(" · ")}
            </div>
          </div>
        ) : null}

        {summary && topMovementDriver && datesQuery.data?.result ? (
          <FigmaDecisionHero
            balanceChangePct={balanceChangePct}
            balanceChangeTotal={summary.balance_change_total}
            topDriver={topMovementDriver}
            movementDrivers={movementDrivers}
            dates={datesQuery.data.result}
            selectedDate={selectedDate}
            reconciliationLabel={reconciliationLabel}
            currencyBasis={currencyBasis}
          />
        ) : detailQuery.isLoading && selectedDate && datesQuery.data?.result ? (
          <FigmaLoadingHero
            dates={datesQuery.data.result}
            selectedDate={selectedDate}
            reconciliationLabel={reconciliationLabel}
            currencyBasis={currencyBasis}
          />
        ) : datesQuery.data?.result ? (
          <FigmaEmptyHero
            dates={datesQuery.data.result}
            selectedDate={selectedDate}
            reconciliationLabel={reconciliationLabel}
            currencyBasis={currencyBasis}
          />
        ) : null}

        {summary && topMovementDriver ? (
          <FigmaKpiRibbon
            summary={summary}
            topDriver={topMovementDriver}
            hasBalanceChangeTotal={hasBalanceChangeTotal}
            reconciliationLabel={reconciliationLabel}
            balanceChangePct={balanceChangePct}
          />
        ) : null}

        {movementDrivers.length > 0 ? <FigmaDriversAndStructure drivers={movementDrivers} /> : null}

        {detailQuery.data ? (
          <FigmaMaturityAndConcentration
            maturityGroups={compactMaturityGroups}
            issuerDimension={issuerConcentration}
            maturityCoverage={zqtzMaturityStructure?.meta.coverage_pct}
            unknownMaturityAmount={zqtzMaturityStructure?.meta.unknown_total}
          />
        ) : null}

        {resultMeta ? (
          <EvidenceStrip
            meta={resultMeta}
            reportDate={selectedDate || detailQuery.data?.result.report_date || ""}
            currencyBasis={currencyBasis}
          />
        ) : null}

        {rows.length > 0 ? <FigmaAccountingBuckets rows={rows} /> : null}

        {balanceStructureChartRows.length > 0 ||
        structureShareTableRows.length > 0 ||
        balanceStructureInsight ? (
          <SixMonthStructurePanel
            chartRows={balanceStructureChartRows}
            structureShareTableRows={structureShareTableRows}
            shareRowByReportMonth={shareRowByReportMonth}
            balanceStructureInsight={balanceStructureInsight}
          />
        ) : null}

      <StructureBridgeStage
        analysis={structureMigrationAnalysis}
        waterfall={differenceAttributionWaterfall}
        closure={explanationClosure}
      />

      {basisMovementDecomposition ? (
        <LiveBasisDecompositionStage
          decomposition={basisMovementDecomposition}
          hasCalibration={Boolean(zqtzCalibrationAnalysis)}
        />
      ) : detailQuery.data ? (
        <DrilldownUnavailablePanel
          testId="balance-movement-analysis-basis-decomposition"
          eyebrow="会计分类驱动拆解"
          title="AC / OCI / TPL 驱动拆解"
          fieldName="basis_movement_decomposition"
        />
      ) : null}

      {zqtzMaturityStructure ? (
        <ZqtzMaturityStructurePanel structure={zqtzMaturityStructure} />
      ) : detailQuery.data ? (
        <DrilldownUnavailablePanel
          testId="balance-movement-analysis-zqtz-maturity"
          eyebrow="ZQTZ 到期视图"
          title="期限 / 到期结构"
          fieldName="zqtz_maturity_structure"
        />
      ) : null}

      {zqtzConcentrationAnalysis ? (
        <ZqtzConcentrationAnalysisPanel analysis={zqtzConcentrationAnalysis} />
      ) : detailQuery.data ? (
        <DrilldownUnavailablePanel
          testId="balance-movement-analysis-zqtz-concentration"
          eyebrow="ZQTZ 集中度视图"
          title="主体 / 评级 / 行业集中度"
          fieldName="zqtz_concentration_analysis"
        />
      ) : null}


      {summary && topMovementDriver ? (
        <section
          id="balance-movement-analysis-business-summary-anchor"
          data-testid="balance-movement-analysis-business-summary"
          className="balance-movement-figma-panel balance-movement-business-panel"
        >
          <header className="balance-movement-figma-header">
            <div>
              <span>07 / BUSINESS LINE MOVERS</span>
              <h2>业务行 Top 变动与余额驱动</h2>
            </div>
            <p>business_trend_months · MoM / {businessMatrixMonths.length}M</p>
          </header>

          <div className="balance-movement-business-lead">
            <div className="balance-movement-business-lead__decision">
              <span>本期主结论</span>
              <strong>
                {hasBalanceChangeTotal ? (
                  <>{topMovementDriver.bucket} {formatSignedYiNumber(topMovementDriver.balanceChangeYi)} 亿 · 贡献 {formatPct(topMovementDriver.contributionPct)}</>
                ) : (
                  "总变动缺失，暂不判断方向"
                )}
              </strong>
              <p>
                {hasBalanceChangeTotal
                  ? `本月总余额${movementDirection(balanceChangeTotal)} ${formatYiFixed(Math.abs(numericValue(balanceChangeTotal)))} 亿；单桶贡献集中，同时带动 ${accountingBasisNarrativeLabel(topMovementDriver.bucket)} 占比至 ${formatPct(topMovementDriver.currentBalancePct)}，较期初 ${formatSignedPointNullable(topMovementDriver.shareDelta)}`
                  : "等待完整余额变动口径后再判断主导方向。"}
              </p>
              {structureDriverHint ? (
                <span data-testid="balance-movement-analysis-structure-driver-hint" className="balance-movement-sr-only">
                  {structureDriverHint}
                </span>
              ) : null}
            </div>
            <div className="balance-movement-business-lead__stability" aria-label="结构稳定器">
              <div>
                <span>AC 稳定器</span>
                <strong>{formatPct(rowByBucket.get("AC")?.current_balance_pct)}</strong>
                <small>{formatSignedPointNullable(movementDriverByBucket.get("AC")?.shareDelta)}</small>
              </div>
              <div>
                <span>OCI 压舱石</span>
                <strong>{formatPct(rowByBucket.get("OCI")?.current_balance_pct)}</strong>
                <small>{formatSignedPointNullable(movementDriverByBucket.get("OCI")?.shareDelta)}</small>
              </div>
            </div>
          </div>

          {businessTopMomMoves.length > 0 ? (
            <div data-testid="balance-movement-analysis-business-top-moves" className="balance-movement-business-charts">
              <BusinessMoverPanel
                moves={businessTopMomMoves}
                testId="balance-movement-analysis-business-top-moves-mom"
                title="本月变动 · 发散视图"
                subtitle="current vs prior"
              />
              {businessTopSixMonthMoves.length > 0 ? (
                <BusinessMoverPanel
                  moves={businessTopSixMonthMoves}
                  testId="balance-movement-analysis-business-top-moves-sixmonth"
                  title={`近 ${businessMatrixMonths.length} 月变动`}
                  subtitle="first → current"
                />
              ) : null}
            </div>
          ) : null}

          <div data-testid="balance-movement-analysis-driver-chart" className="balance-movement-contribution">
            <div className="balance-movement-contribution__header">
              <h3>变动贡献构成</h3>
              <span>balance change contribution</span>
            </div>
            <div className="balance-movement-contribution__band" aria-label="余额变动贡献带">
              {movementDrivers.map((driver) => (
                <span
                  key={driver.bucket}
                  className={`balance-movement-contribution__segment balance-movement-contribution__segment--${driver.bucket.toLowerCase()}`}
                  style={{ flexGrow: Math.abs(driver.balanceChangeYi) || 0.001 }}
                />
              ))}
            </div>
            <div data-testid="balance-movement-analysis-driver-ranking" className="balance-movement-contribution__labels">
              {movementDrivers.map((driver) => (
                <div className={`balance-movement-contribution__label--${driver.bucket.toLowerCase()}`} key={driver.bucket}>
                  <span>{driver.bucket}</span>
                  <strong>{formatSignedYiNumber(driver.balanceChangeYi)} 亿 · {formatPct(driver.contributionPct)}</strong>
                  <small>占比 {formatPct(driver.currentBalancePct)} · {formatSignedPointNullable(driver.shareDelta)}</small>
                </div>
              ))}
            </div>
          </div>
        </section>
      ) : null}
      {zqtzAssetDetailRows.length > 0 ? (
        <section
          data-testid="balance-movement-analysis-zqtz-detail"
          className="balance-movement-zqtz-detail-page balance-movement-figma-panel"
        >
          <header className="balance-movement-zqtz-detail-page__header balance-movement-figma-header">
            <div>
              <span>08 / FINANCIAL INVESTMENT MONTHLY DETAIL</span>
              <h2>金融投资资产明细变动（6个月）</h2>
            </div>
            <p>
              report {businessMatrixMonths.at(-1)?.report_month ?? EM_DASH} · unit 亿元 · {zqtzAssetDetailRows.length + (zqtzAssetDetailSummaryRow ? 1 : 0)} rows
            </p>
          </header>
          <div className="balance-movement-zqtz-detail-page__scope">
            <code>business_trend_months.rows · source_kind ZQTZ / ledger</code>
            <span>“其中”项独立展示，不与上级分类重复加总。</span>
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
                      {businessMatrixMonths.map((month) => {
                        const cellMeta = row.getCellMeta?.(month);
                        return (
                          <td
                            key={`${row.key}-${month.report_date}`}
                            title={
                              cellMeta?.hasMissingInputs
                                ? "部分分项缺失，合计未含缺失项"
                                : undefined
                            }
                          >
                            {cellMeta
                              ? formatMatrixCellWithMissing(
                                  row.getValue(month),
                                  "amount",
                                  true,
                                  cellMeta.hasMissingInputs,
                                )
                              : formatMatrixValue(row.getValue(month), "amount", true)}
                          </td>
                        );
                      })}
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
                          {businessMatrixMonths.map((month) => {
                            const cellMeta = zqtzAssetDetailSummaryRow.getCellMeta?.(month);
                            return (
                              <td
                                key={`${zqtzAssetDetailSummaryRow.key}-${month.report_date}`}
                                title={
                                  cellMeta?.hasMissingInputs
                                    ? "部分分项缺失，合计未含缺失项"
                                    : undefined
                                }
                              >
                                {formatMatrixCellWithMissing(
                                  zqtzAssetDetailSummaryRow.getValue(month),
                                  "amount",
                                  true,
                                  cellMeta?.hasMissingInputs,
                                )}
                              </td>
                            );
                          })}
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
        <BusinessBalanceMatrixSection
          months={businessMatrixMonths}
          liabilityRows={businessMatrixLiabilityRows}
          projectRows={businessProjectTableRows}
          balanceRows={rows}
          accountingSnapshotsAreNonAdjacent={Boolean(
            currentTrendMonth &&
              previousTrendMonth &&
              !isPreviousCalendarMonth(
                currentTrendMonth.report_date,
                previousTrendMonth.report_date,
              )
          )}
        />
      ) : null}
      <DataStatesGovernancePanel
        isLoading={datesQuery.isLoading || detailQuery.isLoading}
        hasReportDates={reportDates.length > 0}
        hasRows={rows.length > 0}
        freshnessStatus={datesQuery.data?.result.freshness_status}
        selectedDate={selectedDate}
        resolvedReportDate={
          resultMeta?.resolved_report_date ?? detailQuery.data?.result.report_date ?? ""
        }
        hasError={datesQuery.isError || detailQuery.isError}
        refreshMessage={refreshMessage}
        resultMeta={resultMeta}
        governanceMeta={governanceMeta}
        supplementary={(
          <>
            {detailQuery.data?.result.accounting_controls ? (
              <div
                data-testid="balance-movement-analysis-controls"
                className="balance-movement-accounting-controls"
              >
                控制科目：{detailQuery.data.result.accounting_controls.join(", ")}；排除：
                {detailQuery.data.result.excluded_controls.join(", ")}
              </div>
            ) : null}
            {detailQuery.data?.result ? (
              <div
                data-testid="balance-movement-analysis-governance"
                className="balance-movement-governance-line"
              >
                读模型报告日：{governanceMeta.reportDate || EM_DASH}
                {" · "}规则版本：
                {governanceMeta.ruleVersions.length
                  ? governanceMeta.ruleVersions.join("、")
                  : EM_DASH}
                <br />
                源版本：
                {governanceMeta.sourceVersions.length
                  ? governanceMeta.sourceVersions.join("、")
                  : EM_DASH}
              </div>
            ) : null}
            <SupplementaryBusinessRowsTable
              months={businessMatrixMonths}
              rows={businessMatrixAssetRows}
            />
            <StructureShareDetailTable
              structureShareTableRows={structureShareTableRows}
              shareRowByReportMonth={shareRowByReportMonth}
            />
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
            {detailQuery.data ? (
              <HistoricalAnomalyPanel diagnostics={historicalAnomalyDiagnostics} />
            ) : null}
          </>
        )}
      />
      </div>
    </section>
  );
}
