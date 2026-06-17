export function nullableNumber(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

/** Prefer backend share pct; fall back to balance / total only when it is missing. */
export function resolveBucketSharePct(
  backendPct: string | number | null | undefined,
  balance: string | number | null | undefined,
  total: string | number | null | undefined,
): number | null {
  const fromBackend = nullableNumber(backendPct);
  if (fromBackend !== null) {
    return fromBackend;
  }
  const balanceValue = nullableNumber(balance);
  const totalValue = nullableNumber(total);
  if (balanceValue === null || totalValue === null || totalValue <= 0) {
    return null;
  }
  return (balanceValue / totalValue) * 100;
}
