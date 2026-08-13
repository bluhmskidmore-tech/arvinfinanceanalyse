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
 * credit-spread-migration 契约中 hhi / top5_concentration / credit_weight /
 * rating_aa_and_below_weight 均为 unit="ratio" 的小数比率（占比 ∈ [0,1]，
 * 见 backend/app/schemas/bond_analytics.py 的 _NUMERIC_FIELDS），固定 ×100 展示，
 * 不再使用 ratio∈[0,1] 启发式。
 */
export function formatConcentrationPercent(value: string | Numeric | undefined): string {
  const ratio = parseRatio(value);
  if (ratio === null) {
    return displayStr(value);
  }
  return `${(ratio * 100).toFixed(2)}%`;
}
