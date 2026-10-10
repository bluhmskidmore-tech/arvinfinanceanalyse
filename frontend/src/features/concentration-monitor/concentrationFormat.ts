import type { Numeric } from "../../api/contracts";
import { numericRaw } from "../../pageModel";
import { EM_DASH } from "../../utils/format";

export function displayStr(value: string | Numeric | undefined) {
  if (value === undefined || value === "") {
    return EM_DASH;
  }
  if (typeof value === "object" && value !== null && "display" in value) {
    return value.display || EM_DASH;
  }
  return String(value);
}

/** 仅用于与展示限额比较，不参与组合指标重算。 */
export function parseRatio(value: string | Numeric | undefined): number | null {
  if (value === undefined || value === "") {
    return null;
  }
  if (typeof value === "object" && value !== null && "raw" in value) {
    return numericRaw(value);
  }
  const n = Number.parseFloat(value);
  return Number.isFinite(n) ? n : null;
}

/**
 * top5_concentration / credit_weight / rating_aa_and_below_weight / weight
 * 为占比（unit="ratio"，∈ [0,1]），固定 ×100 加 % 展示。
 * HHI 是集中度指数，不是占比，必须走 formatConcentrationIndex，禁止套用本函数。
 */
export function formatConcentrationPercent(value: string | Numeric | undefined): string {
  const ratio = parseRatio(value);
  if (ratio === null) {
    return displayStr(value);
  }
  return `${(ratio * 100).toFixed(2)}%`;
}

/**
 * HHI 指数展示：从 raw 按 4 位小数输出（如 0.1200），不加 %。
 * 精度对齐债券分析页 formatHhi / AdbDeepAnalysis 的 4 位惯例；缺值统一 EM_DASH。
 * 亦用于 HHI 展示限额阈值（后端下发的比率小数，语义仍是指数而非占比）。
 */
export function formatConcentrationIndex(
  value: string | Numeric | number | undefined,
): string {
  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      return EM_DASH;
    }
    return value.toFixed(4);
  }
  const ratio = parseRatio(value);
  if (ratio === null) {
    return displayStr(value);
  }
  return ratio.toFixed(4);
}

/** 展示限额阈值（后端下发 ratio 小数）与当前值列同制：两位小数百分比。HHI 阈值走 formatConcentrationIndex。 */
export function formatLimitThresholdPercent(limit: number): string {
  if (!Number.isFinite(limit)) {
    return EM_DASH;
  }
  return `${(limit * 100).toFixed(2)}%`;
}

/**
 * 限额使用率 = 当前值 / 限额（两者均为 ratio 小数，仅展示对照，不参与重算）；
 * 缺当前值或限额非正时返回 EM_DASH。
 */
export function formatLimitUsagePercent(value: number | null, limit: number): string {
  if (value === null || !Number.isFinite(limit) || limit <= 0) {
    return EM_DASH;
  }
  return `${((value / limit) * 100).toFixed(1)}%`;
}
