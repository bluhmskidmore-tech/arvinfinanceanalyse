import { decimalToScaledBigInt } from "../../positions/utils/format";

/** 元（decimal string 或 V1 number）→ 亿元，用于图表数值轴。 */
export function yuanToYiNumber(v: string | number | null | undefined): number {
  if (v === null || v === undefined) {
    return 0;
  }
  if (typeof v === "number") {
    if (!Number.isFinite(v)) {
      return 0;
    }
    return v / 1e8;
  }
  const s = v.trim();
  if (!s) {
    return 0;
  }
  const bi = decimalToScaledBigInt(s, 4);
  return Number(bi) / 1e12;
}

export function nameAmountToYi(item: {
  amount?: number | string | null;
  amount_yi?: number | string | null;
}): number {
  if (item.amount_yi !== null && item.amount_yi !== undefined) {
    if (typeof item.amount_yi === "number") {
      return Number.isFinite(item.amount_yi) ? item.amount_yi : 0;
    }
    return yuanToYiNumber(item.amount_yi);
  }
  return yuanToYiNumber(item.amount ?? null);
}

export function bucketAmountToYi(item: {
  amount?: number | string | null;
  amount_yi?: number | string | null;
}): number {
  return nameAmountToYi(item);
}
