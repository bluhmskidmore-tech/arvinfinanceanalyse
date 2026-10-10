import type { BalanceMovementRow, BalanceMovementTrendMonth } from "../../../api/contracts";
import type { AccountingBasisStackedSharePoint } from "../../../components/charts/AccountingBasisStackedShareChart";
import { EM_DASH } from "../../../utils/format";

const balanceMovementBuckets: BalanceMovementRow["basis_bucket"][] = ["AC", "OCI", "TPL"];

export function nullableNumber(value: string | number | null | undefined): number | null {
  if (
    value === null
    || value === undefined
    || (typeof value === "string" && value.trim() === "")
  ) {
    return null;
  }
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

/** The governed backend share is authoritative; missing stays missing. */
export function resolveBucketSharePct(
  backendPct: string | number | null | undefined,
): number | null {
  return nullableNumber(backendPct);
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
  const rowByBucket = new Map<BalanceMovementRow["basis_bucket"], BalanceMovementRow>();
  for (const row of month.rows) {
    if (!rowByBucket.has(row.basis_bucket)) rowByBucket.set(row.basis_bucket, row);
  }
  for (const bucket of balanceMovementBuckets) {
    const row = rowByBucket.get(bucket);
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

export function formatSignedPointNullable(value: number | null | undefined) {
  return value === null || value === undefined || !Number.isFinite(value)
    ? EM_DASH
    : formatSignedPoint(value);
}

export function nullableDelta(
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

type StructureShareTableRow = {
  point: BalanceStructureSharePoint;
  reportMonth: string;
};

export type BalanceStructureEvolutionModel = {
  structureShareTableRows: StructureShareTableRow[];
  shareRowByReportMonth: Map<string, StructureShareTableRow>;
  chartRows: AccountingBasisStackedSharePoint[];
  balanceStructureInsight: string | null;
};

/** Build the matrix, chart and detail table from the same chronological snapshots. */
export function buildBalanceStructureEvolution(
  months: BalanceMovementTrendMonth[],
): BalanceStructureEvolutionModel {
  const structureShareTableRows: StructureShareTableRow[] = [];
  const shareRowByReportMonth = new Map<string, StructureShareTableRow>();
  const chartRows: AccountingBasisStackedSharePoint[] = [];
  let hasIncompleteShare = false;
  let firstCompletePoint: AccountingBasisStackedSharePoint | null = null;
  let latestCompletePoint: AccountingBasisStackedSharePoint | null = null;

  for (const month of months) {
    const point = toSharePoint(month);
    const row = { point, reportMonth: month.report_month };
    structureShareTableRows.push(row);
    shareRowByReportMonth.set(row.reportMonth, row);
    const chartPoint = toCompleteSharePoint(point);
    if (structureShareTableRows.length === 1) firstCompletePoint = chartPoint;
    latestCompletePoint = chartPoint;
    if (chartPoint === null) {
      hasIncompleteShare = true;
    } else {
      chartRows.push(chartPoint);
    }
  }

  const first = firstCompletePoint;
  const latest = latestCompletePoint;
  const balanceStructureInsight =
    first && latest && first.monthLabel !== latest.monthLabel
      ? `AC占比较首月 ${formatSignedPoint(latest.AC - first.AC)}，OCI ${formatSignedPoint(
          latest.OCI - first.OCI,
        )}，TPL ${formatSignedPoint(latest.TPL - first.TPL)}。`
      : null;

  return {
    structureShareTableRows,
    shareRowByReportMonth,
    chartRows: hasIncompleteShare ? [] : chartRows,
    balanceStructureInsight,
  };
}
