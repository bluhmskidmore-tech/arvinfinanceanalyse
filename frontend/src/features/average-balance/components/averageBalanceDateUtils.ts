/** 日历同比平移整年；2/29 等非法日自动夹到目标年对应月末同日序。 */
export function shiftIsoDateByYears(iso: string, deltaYears: number): string {
  const parts = iso.split("-");
  if (parts.length !== 3) return iso;
  const ys = Number(parts[0]);
  const ms = Number(parts[1]);
  const ds = Number(parts[2]);
  if (!Number.isFinite(ys) || !Number.isFinite(ms) || !Number.isFinite(ds)) return iso;
  const y = ys + deltaYears;
  const lastDay = new Date(y, ms, 0).getDate();
  const d = Math.min(ds, lastDay);
  return `${y}-${String(ms).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}
