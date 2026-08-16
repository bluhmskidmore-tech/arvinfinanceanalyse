import type {
  DecimalLike,
  ProductCategoryInterestSpreadPayload,
  ProductCategoryPnlRow,
  ResultMeta,
} from "../../../../api/contracts";

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
