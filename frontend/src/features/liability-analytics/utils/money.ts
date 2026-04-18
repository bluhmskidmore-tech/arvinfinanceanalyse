import type { Numeric } from "../../../api/contracts";

export function numericYuanRaw(n: Numeric | null | undefined): number {
  if (!n || n.raw === null || !Number.isFinite(n.raw)) {
    return 0;
  }
  return n.unit === "yuan" ? n.raw : 0;
}

export function numericPctRaw(n: Numeric | null | undefined): number | null {
  if (!n || n.raw === null || !Number.isFinite(n.raw)) {
    return null;
  }
  return n.raw;
}

export function numericToYi(n: Numeric | null | undefined): number {
  if (!n || n.raw === null || !Number.isFinite(n.raw)) {
    return 0;
  }
  if (n.unit === "yi") {
    return n.raw;
  }
  if (n.unit === "yuan") {
    return n.raw / 1e8;
  }
  return 0;
}

export function nameAmountToYi(item: {
  amount?: Numeric | null;
  amount_yi?: Numeric | null;
}): number {
  if (item.amount_yi !== null && item.amount_yi !== undefined) {
    return numericToYi(item.amount_yi);
  }
  return numericToYi(item.amount ?? null);
}

export function bucketAmountToYi(item: {
  amount?: Numeric | null;
  amount_yi?: Numeric | null;
}): number {
  return nameAmountToYi(item);
}
