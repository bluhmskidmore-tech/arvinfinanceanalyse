import type { Numeric } from "../../../api/contracts";
import { formatRawAsNumeric } from "../../../utils/format";

export function numericRaw(value: Numeric | null | undefined): number | null {
  if (!value || value.raw === null || !Number.isFinite(value.raw)) {
    return null;
  }
  return value.raw;
}

export function numericYuanRaw(value: Numeric | null | undefined): number | null {
  const raw = numericRaw(value);
  if (raw === null) {
    return null;
  }
  if (value?.unit === "yuan") {
    return raw;
  }
  if (value?.unit === "yi") {
    return raw * 1e8;
  }
  return null;
}

export function numericPctRaw(value: Numeric | null | undefined): number | null {
  return numericRaw(value);
}

export function numericToYiNumeric(value: Numeric | null | undefined): Numeric | null {
  const raw = numericRaw(value);
  if (raw === null) {
    return null;
  }
  if (value?.unit === "yi") {
    return value;
  }
  if (value?.unit === "yuan") {
    return formatRawAsNumeric({
      raw: raw / 1e8,
      unit: "yi",
      sign_aware: value.sign_aware,
      precision: 2,
    });
  }
  return null;
}

export function ratioToPercentNumeric(raw: number | null | undefined, signAware = false): Numeric | null {
  if (raw === null || raw === undefined || !Number.isFinite(raw)) {
    return null;
  }
  return formatRawAsNumeric({ raw, unit: "pct", sign_aware: signAware, precision: 2 });
}

export function shareOfTotalNumeric(value: Numeric | null | undefined, total: Numeric | null | undefined): Numeric | null {
  const totalRaw = numericYuanRaw(total);
  const valueRaw = numericYuanRaw(value);
  if (totalRaw === null || valueRaw === null || totalRaw <= 0) {
    return null;
  }
  return ratioToPercentNumeric(valueRaw / totalRaw);
}

export function numericToYi(value: Numeric | null | undefined): number | null {
  return numericToYiNumeric(value)?.raw ?? null;
}

export function nameAmountToYi(item: {
  amount?: Numeric | null;
  amount_yi?: Numeric | null;
}): number | null {
  return nameAmountToYiNumeric(item)?.raw ?? null;
}

export function nameAmountToYiNumeric(item: {
  amount?: Numeric | null;
  amount_yi?: Numeric | null;
}): Numeric | null {
  if (item.amount_yi !== null && item.amount_yi !== undefined) {
    return numericToYiNumeric(item.amount_yi);
  }
  return numericToYiNumeric(item.amount ?? null);
}

export function bucketAmountToYi(item: {
  amount?: Numeric | null;
  amount_yi?: Numeric | null;
}): number | null {
  return bucketAmountToYiNumeric(item)?.raw ?? null;
}

export function bucketAmountToYiNumeric(item: {
  amount?: Numeric | null;
  amount_yi?: Numeric | null;
}): Numeric | null {
  return nameAmountToYiNumeric(item);
}

export function numericOrDash(value: Numeric | null | undefined): string {
  return value?.display ?? "—";
}
