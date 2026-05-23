import type { PnlByBusinessAnalysisPayload } from "../../../api/contracts";

import {
  DASHBOARD_PRODUCT_PNL_PENDING,
  type DashboardProductPnlTrendVM,
} from "./dashboardCockpitHomeModel";

const YUAN_PER_YI = 100_000_000;

const BOND_BUCKET_TREND_SPECS = [
  { id: "rate", bucketKey: "rate_bond", name: "利率债" },
  { id: "credit", bucketKey: "credit_bond", name: "信用债" },
  { id: "interbank", bucketKey: "financial_bond", name: "金融债" },
  { id: "other", bucketKey: "other_bond", name: "其它债券" },
] as const;

type TrendMonthPoint = {
  sortKey: string;
  label: string;
  valuesByBucket: Map<string, number>;
};

function parseBondBucketMonthlyKey(dimensionKey: string): { sortKey: string; label: string; bucketKey: string } | null {
  const [reportDatePart, bucketKey] = dimensionKey.split("::");
  if (!reportDatePart || !bucketKey) {
    return null;
  }
  const monthMatch = reportDatePart.match(/^(\d{4})-(\d{2})/);
  if (!monthMatch) {
    return null;
  }
  const year = monthMatch[1]!;
  const month = Number.parseInt(monthMatch[2]!, 10);
  if (!Number.isFinite(month) || month < 1 || month > 12) {
    return null;
  }
  return {
    sortKey: `${year}-${String(month).padStart(2, "0")}`,
    label: `${month}月`,
    bucketKey,
  };
}

function totalPnlYuanToYi(totalPnl: string): number | null {
  const parsed = Number.parseFloat(totalPnl.replace(/,/g, ""));
  if (!Number.isFinite(parsed)) {
    return null;
  }
  return Number((parsed / YUAN_PER_YI).toFixed(2));
}

function isSameReportDate(expected: string, actual: string | null | undefined): boolean {
  const expectedDate = expected.trim();
  const actualDate = actual?.trim() ?? "";
  return expectedDate.length > 0 && actualDate.length > 0 && expectedDate === actualDate;
}

/** 正式读面：pnl-by-business `bond_bucket_monthly` 四类债券月度 total_pnl（元 → 亿）。 */
export function buildDashboardProductPnlTrendFromBondBucketMonthly(
  payload: PnlByBusinessAnalysisPayload | null | undefined,
  reportDate: string,
): DashboardProductPnlTrendVM {
  if (
    !payload ||
    payload.dimension !== "bond_bucket_monthly" ||
    payload.rows.length === 0 ||
    !isSameReportDate(reportDate, payload.as_of_date)
  ) {
    return DASHBOARD_PRODUCT_PNL_PENDING;
  }

  const reportYearMonth = reportDate.slice(0, 7);
  const pointsByMonth = new Map<string, TrendMonthPoint>();

  for (const row of payload.rows) {
    const parsed = parseBondBucketMonthlyKey(row.dimension_key);
    const valueYi = totalPnlYuanToYi(row.total_pnl);
    if (!parsed || valueYi === null) {
      continue;
    }
    if (parsed.sortKey > reportYearMonth) {
      continue;
    }

    const existing =
      pointsByMonth.get(parsed.sortKey) ??
      ({
        sortKey: parsed.sortKey,
        label: parsed.label,
        valuesByBucket: new Map<string, number>(),
      } satisfies TrendMonthPoint);
    existing.valuesByBucket.set(parsed.bucketKey, valueYi);
    pointsByMonth.set(parsed.sortKey, existing);
  }

  const chronological = [...pointsByMonth.values()].sort((left, right) =>
    left.sortKey.localeCompare(right.sortKey),
  );
  const recentMonths = chronological.slice(-7);
  if (recentMonths.length === 0) {
    return DASHBOARD_PRODUCT_PNL_PENDING;
  }

  const series = BOND_BUCKET_TREND_SPECS.map((spec) => ({
    id: spec.id,
    name: spec.name,
    values: recentMonths.map((point) => point.valuesByBucket.get(spec.bucketKey) ?? 0),
  }));

  const totalValues = recentMonths.map((point) => {
    let sum = 0;
    for (const value of point.valuesByBucket.values()) {
      sum += value;
    }
    return Number(sum.toFixed(2));
  });

  const hasAnyNonZero = series.some((item) => item.values.some((value) => value !== 0));
  if (!hasAnyNonZero && totalValues.every((value) => value === 0)) {
    return DASHBOARD_PRODUCT_PNL_PENDING;
  }

  return {
    months: recentMonths.map((point) => point.label),
    series: [
      ...series,
      {
        id: "total",
        name: "合计",
        values: totalValues,
      },
    ],
    pending: false,
  };
}
