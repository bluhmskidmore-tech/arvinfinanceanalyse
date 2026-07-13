type AdbAvgByBusinessTypeSource = {
  category?: string | null;
  avg_balance?: number | null;
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
