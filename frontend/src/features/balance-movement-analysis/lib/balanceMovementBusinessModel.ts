import type {
  BalanceMovementRow,
  BalanceMovementTrendMonth,
  BalanceBusinessMovementTrendMonth,
} from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import { countReconciliationStatuses } from "./balanceMovementReconciliationModel";
import { nullableDelta, nullableNumber } from "./balanceMovementShareModel";
import { type BalanceMovementMatrixValueKind, formatSignedMatrixValue } from "./balanceMovementPresentation";

export const balanceMovementBuckets: BalanceMovementRow["basis_bucket"][] = ["AC", "OCI", "TPL"];

export function trendBucket(
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

export function basisThreeBucketSum(
  accountingByDate: Map<string, BalanceMovementTrendMonth>,
  businessMonth: BalanceBusinessMovementTrendMonth,
) {
  const ac = basisBucketBalanceForBusiness(accountingByDate, businessMonth, "AC");
  const oci = basisBucketBalanceForBusiness(accountingByDate, businessMonth, "OCI");
  const tpl = basisBucketBalanceForBusiness(accountingByDate, businessMonth, "TPL");
  if (ac === undefined || oci === undefined || tpl === undefined) {
    return undefined;
  }
  const a = nullableNumber(ac);
  const o = nullableNumber(oci);
  const t = nullableNumber(tpl);
  if (a === null || o === null || t === null) {
    return undefined;
  }
  return a + o + t;
}

export function trendDelta(
  current: string | number | null | undefined,
  previous: string | number | null | undefined,
) {
  const currentValue = nullableNumber(current);
  const previousValue = nullableNumber(previous);
  if (currentValue === null || previousValue === null) {
    return null;
  }
  return currentValue - previousValue;
}

type MatrixRowSumResult = {
  value: number | null;
  hasMissingInputs: boolean;
};

export type BusinessMovementMatrixRow = {
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

export function compareBusinessMatrixCell(
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

export function compareBusinessMatrixCellToFirst(
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

export function aggregateBucketReconciliation(rows: BalanceMovementRow[]) {
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

export function accountingBasisNarrativeLabel(bucket: BalanceMovementRow["basis_bucket"]) {
  return bucket === "TPL" ? "FVTPL" : bucket;
}

export type BusinessMomMove = {
  label: string;
  deltaYuan: number;
  side: "asset" | "liability";
  rowKey: string;
  sourceKind?: "ledger" | "zqtz";
  sourceNote?: string;
  currentYuan: number;
  previousYuan: number;
};

export type ZqtzAssetDetailRow = {
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

export function buildZqtzAssetDetailRows(
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

export function sumPrimaryZqtzAssetDetailRows(
  month: BalanceBusinessMovementTrendMonth,
  rows: ZqtzAssetDetailRow[],
): MatrixRowSumResult {
  return sumMatrixRowValues(month, rows, { excludeSubItems: true });
}

export function topBusinessLineMovesByMomAbs(
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

export function topBusinessLineMovesByWindowAbs(
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

export function uniqueNonEmptyStrings(values: string[]): string[] {
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

export function buildBusinessCategoryMatrixRows(
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

export function sumBusinessMatrixRowValues(
  month: BalanceBusinessMovementTrendMonth,
  rows: Pick<BusinessMovementMatrixRow, "getValue">[],
): MatrixRowSumResult {
  return sumMatrixRowValues(month, rows);
}

export function numericValue(value: string | number | null | undefined) {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

export function shareDeltaPp(row: BalanceMovementRow): number | null {
  return nullableDelta(
    nullableNumber(row.current_balance_pct),
    nullableNumber(row.previous_balance_pct),
  );
}

export function isPreviousCalendarMonth(currentReportDate: string, previousReportDate: string) {
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

export type BalanceMovementDriver = {
  bucket: BalanceMovementRow["basis_bucket"];
  balanceChange: number;
  balanceChangeYi: number;
  contributionPct: number | null;
  currentBalancePct: number | null;
  previousBalancePct: number | null;
  shareDelta: number | null;
};

export function toMovementDriver(row: BalanceMovementRow): BalanceMovementDriver {
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
