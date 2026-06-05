/**
 * 业务种类损益页「年化收益率」：用区间累计损益、与日均列同源的区间日均余额（元）、
 * 区间自然日数（含首尾）做简单年化：(损益/日均)×(365/天数)，结果以百分比字符串展示。
 */

export function inclusiveCalendarDays(startDate: string, endDate: string): number | null {
  const start = new Date(`${startDate}T12:00:00`);
  const end = new Date(`${endDate}T12:00:00`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end < start) {
    return null;
  }
  return Math.floor((end.getTime() - start.getTime()) / 86_400_000) + 1;
}

export function formatAnnualizedYieldPctDisplay(
  totalPnlYuan: number | null,
  adbAvgYuan: number | null | undefined,
  calendarDays: number | null,
): string {
  if (totalPnlYuan === null || !Number.isFinite(totalPnlYuan)) {
    return "-";
  }
  if (adbAvgYuan === undefined || adbAvgYuan === null || !Number.isFinite(adbAvgYuan) || adbAvgYuan <= 0) {
    return "-";
  }
  if (calendarDays === null || calendarDays < 1) {
    return "-";
  }
  const annualizedPct = (totalPnlYuan / adbAvgYuan) * (365 / calendarDays) * 100;
  if (!Number.isFinite(annualizedPct)) {
    return "-";
  }
  return `${annualizedPct.toFixed(2)}%`;
}
