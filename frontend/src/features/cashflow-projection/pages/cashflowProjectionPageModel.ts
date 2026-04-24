import type { Numeric } from "../../../api/contracts";
import type { CashflowProjectionVM } from "../adapters/cashflowProjectionAdapter";

export type CashflowMonthlyProjectionSeries = {
  categories: string[];
  assetInflow: number[];
  liabilityOutflow: number[];
  cumulativeNet: number[];
};

function numericRawOrZero(value: Numeric): number {
  return value.raw === null || !Number.isFinite(value.raw) ? 0 : value.raw;
}

export function selectCashflowMonthlyProjectionSeries(
  vm: CashflowProjectionVM | null,
): CashflowMonthlyProjectionSeries | null {
  const buckets = vm?.monthlyBuckets ?? [];
  if (buckets.length === 0) return null;

  return {
    categories: buckets.map((bucket) => bucket.yearMonth),
    assetInflow: buckets.map((bucket) => numericRawOrZero(bucket.assetInflow)),
    liabilityOutflow: buckets.map((bucket) => numericRawOrZero(bucket.liabilityOutflow)),
    cumulativeNet: buckets.map((bucket) => numericRawOrZero(bucket.cumulativeNet)),
  };
}
