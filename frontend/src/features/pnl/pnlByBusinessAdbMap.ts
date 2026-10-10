type AdbAvgByBusinessTypeSource = {
  category?: string | null;
  avg_balance?: number | null;
};

type YtdAvgByBusinessTypeSource = {
  business_type?: string | null;
  avg_balance?: string | number | null;
};

export function buildAdbAvgByBusinessTypeMap(
  items: readonly AdbAvgByBusinessTypeSource[] | null | undefined,
): Map<string, number> {
  const map = new Map<string, number>();
  for (const item of items ?? []) {
    const label = item.category?.trim();
    if (!label || item.avg_balance === null || item.avg_balance === undefined) continue;
    if (!Number.isFinite(item.avg_balance)) continue;
    map.set(label, item.avg_balance);
  }
  return map;
}

export function buildYtdAvgByBusinessTypeMap(
  items: readonly YtdAvgByBusinessTypeSource[] | null | undefined,
): Map<string, number> {
  const map = new Map<string, number>();
  for (const item of items ?? []) {
    const label = item.business_type?.trim();
    const rawBalance = item.avg_balance;
    if (!label || rawBalance === null || rawBalance === undefined || rawBalance === "") continue;
    const avgBalance = typeof rawBalance === "number" ? rawBalance : Number(rawBalance);
    if (!Number.isFinite(avgBalance)) continue;
    map.set(label, avgBalance);
  }
  return map;
}
