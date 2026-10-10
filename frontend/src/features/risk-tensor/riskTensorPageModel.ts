import Decimal from "decimal.js";

import type { RiskScenarioStressRow, RiskTensorPayload } from "../../api/contracts";
import { numericChartNumberOrNull, numericDecimalOrNull } from "../../api/numeric";

/**
 * Formal page decisions prefer governed raw_text. Older raw-only payloads keep
 * their approximate-number behavior; chart conversion remains a separate path.
 */
export function riskTensorDecisionDecimalOrNull(value: unknown): Decimal | null {
  const exact = numericDecimalOrNull(value);
  if (exact !== null) return exact;

  const raw = numericChartNumberOrNull(value);
  return raw === null ? null : new Decimal(raw);
}

function groupFixedTwoDecimal(value: Decimal): string {
  const [integerPart, fractionalPart] = value
    .toFixed(2, Decimal.ROUND_HALF_UP)
    .split(".");
  return `${integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}.${fractionalPart}`;
}

/**
 * Exact formal-text scaling. Returning null deliberately leaves raw-only
 * payloads to the page's legacy number formatter; chart conversion is separate.
 */
export function riskTensorExactScaledAmountDisplayOrNull(
  value: unknown,
  divisor: number,
  prefixPositive = false,
): string | null {
  const exact = numericDecimalOrNull(value);
  if (exact === null) return null;

  const scaled = exact.div(divisor);
  const formatted = groupFixedTwoDecimal(scaled.abs());
  if (scaled.isNegative() && !scaled.isZero()) return `-${formatted}`;
  return `${prefixPositive && scaled.isPositive() ? "+" : ""}${formatted}`;
}

export function liquidityGapLabel(value: unknown): string {
  const amount = riskTensorDecisionDecimalOrNull(value);
  if (amount === null) return "30 日缺口待确认";
  if (amount.lessThan(0)) return "30 日缺口为负";
  if (amount.greaterThan(0)) return "30 日缺口为正";
  return "30 日缺口持平";
}

export function liquidityGapTone(value: unknown): "neutral" | "danger" | "ok" {
  const amount = riskTensorDecisionDecimalOrNull(value);
  if (amount === null) return "neutral";
  return amount.lessThan(0) ? "danger" : "ok";
}

export function projectionQualityTone(
  value: unknown,
  count: number | null | undefined,
  status: RiskTensorPayload["projection_quality_status"],
): "default" | "warning" {
  if (status !== "available") return "default";

  const amount = riskTensorDecisionDecimalOrNull(value);
  if (amount?.greaterThan(0) || (typeof count === "number" && Number.isFinite(count) && count > 0)) {
    return "warning";
  }
  return "default";
}

export function durationExclusionTone(
  result: Pick<RiskTensorPayload, "duration_excluded_count" | "duration_excluded_market_value">,
): "default" | "warning" {
  const amount = riskTensorDecisionDecimalOrNull(result.duration_excluded_market_value);
  if ((result.duration_excluded_count ?? 0) > 0 || amount?.greaterThan(0)) return "warning";
  return "default";
}

export function scenarioStressTone(
  row: Pick<RiskScenarioStressRow, "data_status" | "estimated_impact">,
): "warning" | "danger" | "ok" {
  if (row.data_status !== "available") return "warning";

  const impact = riskTensorDecisionDecimalOrNull(row.estimated_impact);
  if (impact === null) return "warning";
  return impact.lessThan(0) ? "danger" : "ok";
}

/** Select by exact absolute magnitude and keep the first row on an exact tie. */
export function selectDominantRiskTensorRow<T extends { value: unknown }>(rows: readonly T[]): T | undefined {
  let best: { row: T; magnitude: Decimal } | undefined;
  for (const row of rows) {
    const value = riskTensorDecisionDecimalOrNull(row.value);
    if (value === null) continue;
    const magnitude = value.abs();
    if (!best || magnitude.greaterThan(best.magnitude)) best = { row, magnitude };
  }
  return best?.row;
}
