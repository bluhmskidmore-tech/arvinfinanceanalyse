import type {
  DecimalLike,
  ProductCategoryInterestSpreadPayload,
  ProductCategoryPnlRow,
  ResultMeta,
} from "../../../../api/contracts";

import { EM_DASH } from "../../../../utils/format";

const YUAN_PER_YI = 100_000_000;

export type ProductCategoryReportDateParts = {
  year: number;
  month: number;
};

export type ProductCategoryTrendReportPointLike = {
  reportDate: string;
  view?: string;
  label?: string;
};

export type ProductCategoryTrendSnapshotLike = {
  reportDate: string;
  label?: string;
  view?: string;
  meta?: ResultMeta;
  rows: ProductCategoryPnlRow[];
  assetTotal?: ProductCategoryPnlRow | null;
  liabilityTotal?: ProductCategoryPnlRow | null;
  grandTotal?: ProductCategoryPnlRow | null;
  interestSpread?: ProductCategoryInterestSpreadPayload | null;
  interestEarningSpread?: ProductCategoryInterestSpreadPayload | null;
};

export type ProductCategoryInterestSpreadBasisLike = "weighted" | "cny";

export function formatProductCategoryReportMonthLabelInternal(
  reportDate: string,
): string {
  const match = /^(\d{4})-(\d{2})-\d{2}$/.exec(reportDate);
  if (!match) {
    return reportDate;
  }
  return `${match[1]}\u5e74${match[2]}\u6708`;
}

export function parseProductCategoryReportDateInternal(
  reportDate: string,
): ProductCategoryReportDateParts | null {
  const match = /^(\d{4})-(\d{2})-\d{2}$/.exec(reportDate);
  if (!match) {
    return null;
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  if (
    !Number.isInteger(year) ||
    !Number.isInteger(month) ||
    month < 1 ||
    month > 12
  ) {
    return null;
  }
  return { year, month };
}

export function formatProductCategoryShortMonthLabelInternal(
  month: number,
): string {
  return `${month}\u6708`;
}

function productCategoryReportMonthPrefix(year: number, month: number): string {
  return `${year}-${String(month).padStart(2, "0")}-`;
}

export function findProductCategoryReportDateForMonthInternal(
  reportDates: string[],
  year: number,
  month: number,
  selectedDate: string,
): string | null {
  const prefix = productCategoryReportMonthPrefix(year, month);
  if (selectedDate.startsWith(prefix)) {
    return selectedDate;
  }
  return (
    reportDates.find((reportDate) => reportDate.startsWith(prefix)) ?? null
  );
}

export function pushUniqueProductCategoryTrendPointInternal(
  points: ProductCategoryTrendReportPointLike[],
  point: ProductCategoryTrendReportPointLike,
): void {
  if (
    points.some(
      (existing) =>
        existing.reportDate === point.reportDate &&
        existing.view === point.view,
    )
  ) {
    return;
  }
  points.push(point);
}

export function decimalNumberInternal(
  value: DecimalLike | null | undefined,
): number | null {
  if (value === null || value === undefined) {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function yiNumberInternal(
  value: DecimalLike | null | undefined,
): number | null {
  const parsed = decimalNumberInternal(value);
  if (parsed === null) {
    return null;
  }
  return Number((parsed / YUAN_PER_YI).toFixed(2));
}

export function percentNumberInternal(
  value: DecimalLike | null | undefined,
): number | null {
  const parsed = decimalNumberInternal(value);
  if (parsed === null) {
    return null;
  }
  return Number(parsed.toFixed(2));
}

export function buildSnapshotChartInternal<T>(
  snapshots: ProductCategoryTrendSnapshotLike[],
  project: (snapshot: ProductCategoryTrendSnapshotLike) => T | null,
): { labels: string[]; points: T[] } {
  const labels: string[] = [];
  const points: T[] = [];
  snapshots
    .slice()
    .sort((left, right) => left.reportDate.localeCompare(right.reportDate))
    .forEach((snapshot) => {
      const point = project(snapshot);
      if (point === null) {
        return;
      }
      labels.push(
        snapshot.label ??
          formatProductCategoryReportMonthLabelInternal(snapshot.reportDate),
      );
      points.push(point);
    });
  return { labels, points };
}

export function chronologicalProductCategorySnapshotsInternal(
  snapshots: ProductCategoryTrendSnapshotLike[],
): ProductCategoryTrendSnapshotLike[] {
  return snapshots
    .slice()
    .sort((left, right) => left.reportDate.localeCompare(right.reportDate));
}

export function findProductCategoryRowInternal(
  rows: ProductCategoryPnlRow[],
  categoryId: string,
): ProductCategoryPnlRow | undefined {
  return rows.find((row) => row.category_id === categoryId);
}

export function interestSpreadMetricNumberInternal(
  metric:
    | ProductCategoryInterestSpreadPayload[keyof ProductCategoryInterestSpreadPayload]
    | null
    | undefined,
): number | null {
  return decimalNumberInternal(metric?.raw);
}

export function productCategoryInterestSpreadForBasisInternal(
  snapshot: ProductCategoryTrendSnapshotLike,
  basis: ProductCategoryInterestSpreadBasisLike,
): number | null {
  return interestSpreadMetricNumberInternal(
    basis === "cny"
      ? snapshot.interestSpread?.cny_spread_pct
      : snapshot.interestSpread?.all_currency_spread_pct,
  );
}

export function productCategoryInterestEarningSpreadForBasisInternal(
  snapshot: ProductCategoryTrendSnapshotLike,
  basis: ProductCategoryInterestSpreadBasisLike,
): number | null {
  return interestSpreadMetricNumberInternal(
    basis === "cny"
      ? snapshot.interestEarningSpread?.cny_spread_pct
      : snapshot.interestEarningSpread?.all_currency_spread_pct,
  );
}

export type ProductCategoryCandidateMetricStatus = {
  status: "candidate";
  pendingConfirmation: true;
  formalUseAllowed: false;
  source: "frontend_derived";
  label: string;
  disclaimer: string;
};

export const PRODUCT_CATEGORY_CANDIDATE_METRIC_STATUS: ProductCategoryCandidateMetricStatus =
  {
    status: "candidate",
    pendingConfirmation: true,
    formalUseAllowed: false,
    source: "frontend_derived",
    label: "候选指标 · 非正式结论",
    disclaimer:
      "本区指标由前端基于后端 formal/scenario 字段进行排序、差额、阈值或诊断归类，仅供内部复核，不构成正式金融指标或业务结论。",
  };

export function rawYiNumberInternal(value: DecimalLike | null | undefined): number | null {
  const parsed = decimalNumberInternal(value);
  return parsed === null ? null : parsed / YUAN_PER_YI;
}

export function toneNameForValueInternal(
  value: DecimalLike | null | undefined,
): "neutral" | "positive" | "negative" {
  const parsed = decimalNumberInternal(value);
  if (parsed === null || parsed === 0) {
    return "neutral";
  }
  return parsed > 0 ? "positive" : "negative";
}

export function formatSignedProductCategoryYiInternal(value: number | null): string {
  return signedYiDeltaLabelInternal(value);
}

export function productCategoryPercentLabelInternal(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return EM_DASH;
  }
  return `${value.toFixed(1)}%`;
}

export function productCategoryYiNumberLabelInternal(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return EM_DASH;
  }
  return value.toFixed(2);
}

export function nonTotalProductCategoryRowsInternal(
  rows: ProductCategoryPnlRow[],
): ProductCategoryPnlRow[] {
  return rows.filter(
    (row) =>
      !row.is_total &&
      !row.category_id.endsWith("_total") &&
      row.category_id !== "grand_total" &&
      // This childless row overlaps product details despite is_total=false.
      row.category_id !== "interest_earning_assets",
  );
}

export function leafProductCategoryRowsInternal(
  rows: ProductCategoryPnlRow[],
): ProductCategoryPnlRow[] {
  return nonTotalProductCategoryRowsInternal(rows).filter(
    (row) => row.children.length === 0,
  );
}

export function parentProductCategoryIdsInternal(rows: ProductCategoryPnlRow[]): Set<string> {
  return new Set(
    nonTotalProductCategoryRowsInternal(rows)
      .filter((row) => row.children.length > 0)
      .map((row) => row.category_id),
  );
}

export function medianProductCategoryNumberInternal(values: number[]): number | null {
  const sorted = values
    .filter(Number.isFinite)
    .slice()
    .sort((left, right) => left - right);
  if (sorted.length === 0) {
    return null;
  }
  const midpoint = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 1) {
    return sorted[midpoint] ?? null;
  }
  const left = sorted[midpoint - 1];
  const right = sorted[midpoint];
  return left === undefined || right === undefined ? null : (left + right) / 2;
}

export function productCategoryDeltaToneInternal(
  value: number | null,
): "positive" | "negative" | "neutral" {
  if (value === null || value === 0) {
    return "neutral";
  }
  return value > 0 ? "positive" : "negative";
}

export function signedBpLabelInternal(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return EM_DASH;
  }
  if (value === 0) {
    return "0 bp";
  }
  return `${value > 0 ? "+" : "-"}${Math.abs(value).toFixed(1).replace(/\.0$/, "")} bp`;
}

export function bpLabelInternal(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return EM_DASH;
  }
  return `${value.toFixed(1).replace(/\.0$/, "")} bp`;
}

export function signedYiDeltaLabelInternal(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return EM_DASH;
  }
  if (value === 0) {
    return "0.00";
  }
  return `${value > 0 ? "+" : "-"}${Math.abs(value).toFixed(2)}`;
}

export function productCategorySideLabelInternal(side: string): string {
  if (side === "asset") {
    return "\u8d44\u4ea7";
  }
  if (side === "liability") {
    return "\u8d1f\u503a";
  }
  return side || EM_DASH;
}
