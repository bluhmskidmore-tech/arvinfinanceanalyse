/** 业务种类损益页「年化收益率」：后端返回百分点，本文件只负责展示格式化。 */
import { EM_DASH } from "../../utils/format";

export function inclusiveCalendarDays(startDate: string, endDate: string): number | null {
  const start = new Date(`${startDate}T12:00:00`);
  const end = new Date(`${endDate}T12:00:00`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end < start) {
    return null;
  }
  return Math.floor((end.getTime() - start.getTime()) / 86_400_000) + 1;
}

export function formatAnnualizedYieldPctDisplay(
  annualizedYieldPct: string | number | null | undefined,
): string {
  if (annualizedYieldPct === null || annualizedYieldPct === undefined || annualizedYieldPct === "") {
    return EM_DASH;
  }
  const annualizedPct = Number(annualizedYieldPct);
  if (!Number.isFinite(annualizedPct)) {
    return EM_DASH;
  }
  return `${annualizedPct.toFixed(2)}%`;
}
