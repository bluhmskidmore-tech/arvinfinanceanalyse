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

/**
 * 仅用于瀑布图等需要累计求和的堆叠图表填充（如 `returnDecompositionWaterfallRawSteps`）。
 * 缺失/非有限值在这里退化为 0 只是为了让运行总和继续可算，绝不代表业务上的真实零值。
 * 禁止用于业务数值显示或聚合统计——那些路径必须保留 null 并走 EM_DASH / 排除缺失项语义。
 */
export function chartValueOrZero(value: number | null | undefined, fallback = 0): number {
  return value !== null && value !== undefined && Number.isFinite(value) ? value : fallback;
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

export function returnDecompositionWaterfallRawSteps(d: ReturnDecompositionPayload): number[] {
  const carry = chartValueOrZero(bondNumericRaw(d.carry));
  const rollDown = chartValueOrZero(bondNumericRaw(d.roll_down));
  const rateEffect = chartValueOrZero(bondNumericRaw(d.rate_effect));
  const spreadEffect = chartValueOrZero(bondNumericRaw(d.spread_effect));
  const trading = chartValueOrZero(bondNumericRaw(d.trading));
  const fxEffect = chartValueOrZero(bondNumericRaw(d.fx_effect));
  const convexityEffect = chartValueOrZero(bondNumericRaw(d.convexity_effect));
  const explained = chartValueOrZero(bondNumericRaw(d.explained_pnl));
  const stepValues = [carry, rollDown, rateEffect, spreadEffect, fxEffect, convexityEffect, trading].map((v) =>
    chartValueOrZero(v),
  );
  return [...stepValues, explained];
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
