import type { Numeric, ReturnDecompositionPayload } from "../../../api/contracts";
import { EM_DASH, numericRaw } from "../../../pageModel";

/** Raw scalar for charts / sorting; governed Numeric or legacy string. */
export function bondNumericRaw(n: Numeric | string | null | undefined): number | null {
  if (n === null || n === undefined) {
    return null;
  }
  if (typeof n === "string") {
    const v = Number.parseFloat(n);
    return Number.isFinite(v) ? v : null;
  }
  return numericRaw(n);
}

export function bondNumericRawOrNull(n: Numeric | string | null | undefined): number | null {
  return bondNumericRaw(n);
}

export function bondNumericDisplay(n: Numeric | string | null | undefined): string {
  if (n === null || n === undefined) {
    return EM_DASH;
  }
  if (typeof n === "string") {
    return n === "" || n === "undefined" ? EM_DASH : n;
  }
  return !n.display || n.display === "undefined" ? EM_DASH : n.display;
}

/** ECharts / table magnitude from risk tensor string or bond-analytics Numeric. */
export function bondChartMagnitude(value: Numeric | string): number | null {
  return bondNumericRaw(value);
}

/** 非有限值（NaN/Infinity）与缺失统一收敛为 null：瀑布图按缺口断开，不再补 0 画假柱。 */
function finiteOrNull(value: number | null): number | null {
  return value !== null && Number.isFinite(value) ? value : null;
}

/**
 * 瀑布图原始步值：缺失/非有限效应保留 `null`（该柱断开、由消费方在区头披露 partial），
 * 不得补 0 —— 0 在归因语义里是「效应恰好为零」，与「未返回」是两回事。
 * 末位为合计（解释损益），同样可为 null。
 */
export function returnDecompositionWaterfallRawSteps(
  d: ReturnDecompositionPayload,
): Array<number | null> {
  const stepValues = [
    d.carry,
    d.roll_down,
    d.rate_effect,
    d.spread_effect,
    d.fx_effect,
    d.convexity_effect,
    d.trading,
  ].map((value) => finiteOrNull(bondNumericRaw(value)));
  return [...stepValues, finiteOrNull(bondNumericRaw(d.explained_pnl))];
}

export function returnDecompositionWaterfallDisplayStrings(d: ReturnDecompositionPayload): string[] {
  return [
    bondNumericDisplay(d.carry),
    bondNumericDisplay(d.roll_down),
    bondNumericDisplay(d.rate_effect),
    bondNumericDisplay(d.spread_effect),
    bondNumericDisplay(d.fx_effect),
    bondNumericDisplay(d.convexity_effect),
    bondNumericDisplay(d.trading),
    bondNumericDisplay(d.explained_pnl),
  ];
}
