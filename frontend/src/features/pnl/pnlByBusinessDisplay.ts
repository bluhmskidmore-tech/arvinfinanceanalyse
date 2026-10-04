import { EM_DASH } from "../../utils/format";

export function numeric(raw: string | number | null | undefined): number | null {
  if (raw === null || raw === undefined || raw === "") {
    return null;
  }
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

/** 与日均分析页明细表「日均(亿元)」列一致：两位小数，单位写在表头 */
const YUAN_PER_YI = 100_000_000;
export function formatPnlWan(raw: string | number | null | undefined) {
  const value = numeric(raw);
  if (value === null) {
    return EM_DASH;
  }
  // 不做近零折叠：真实小值按两位小数如实四舍五入展示；仅规整 "-0" 符号噪声。
  const display = (value / 10_000).toLocaleString("zh-CN", { maximumFractionDigits: 2 });
  return display === "-0" ? "0" : display;
}

/** 月度表金额列的符号语义：负值统一 --dh-api-red（§4 色一致性锁，与 /pnl 汇总卡对齐）。 */
export function pnlWanCellTone(raw: string | number | null | undefined): "negative" | undefined {
  const value = numeric(raw);
  return value !== null && value < 0 ? "negative" : undefined;
}

export function formatAdbAvgYiCell(yuan: number): string {
  return (yuan / YUAN_PER_YI).toFixed(2);
}

export function formatYuanAsYiCell(raw: string | number | null | undefined): string {
  const value = numeric(raw);
  if (value === null) {
    return EM_DASH;
  }
  return (value / YUAN_PER_YI).toFixed(2);
}

/** 单日 formal 接口 `yield_pct`：与后端 SQL 一致，为百分数点（如 10.14 表示 10.14%），非 0–1 占比 */
export function formatFormalYieldPctPoints(raw: string | number | null | undefined) {
  const value = numeric(raw);
  if (value === null) {
    return EM_DASH;
  }
  return `${value.toFixed(2)}%`;
}

export function formatFtpRatePct(raw: string | number | null | undefined): string {
  const value = numeric(raw);
  if (value === null) {
    return EM_DASH;
  }
  return `${value.toFixed(2)}%`;
}
