import type { Numeric, ReturnDecompositionPayload } from "../../../api/contracts";

/** Raw scalar for charts / sorting; governed Numeric or legacy string. */
export function bondNumericRaw(n: Numeric | string | null | undefined): number | null {
  if (n === null || n === undefined) {
    return null;
  }
  if (typeof n === "string") {
    const v = Number.parseFloat(n);
    return Number.isFinite(v) ? v : null;
  }
  if (n.raw === null || !Number.isFinite(n.raw)) {
    return null;
  }
  return n.raw;
}

export function bondNumericRawOrNull(n: Numeric | string | null | undefined): number | null {
  return bondNumericRaw(n);
}

export function finiteNumberOr(value: number | null | undefined, fallback = 0): number {
  return value !== null && value !== undefined && Number.isFinite(value) ? value : fallback;
}

export function bondNumericDisplay(n: Numeric | string | null | undefined): string {
  if (n === null || n === undefined) {
    return "—";
  }
  if (typeof n === "string") {
    return n === "" || n === "undefined" ? "—" : n;
  }
  return !n.display || n.display === "undefined" ? "—" : n.display;
}

/** ECharts / table magnitude from risk tensor string or bond-analytics Numeric. */
export function bondChartMagnitude(value: Numeric | string): number | null {
  return bondNumericRaw(value);
}

export function returnDecompositionWaterfallRawSteps(d: ReturnDecompositionPayload): number[] {
  const carry = finiteNumberOr(bondNumericRaw(d.carry));
  const rollDown = finiteNumberOr(bondNumericRaw(d.roll_down));
  const rateEffect = finiteNumberOr(bondNumericRaw(d.rate_effect));
  const spreadEffect = finiteNumberOr(bondNumericRaw(d.spread_effect));
  const trading = finiteNumberOr(bondNumericRaw(d.trading));
  const fxEffect = finiteNumberOr(bondNumericRaw(d.fx_effect));
  const convexityEffect = finiteNumberOr(bondNumericRaw(d.convexity_effect));
  const explained = finiteNumberOr(bondNumericRaw(d.explained_pnl));
  const stepValues = [carry, rollDown, rateEffect, spreadEffect, fxEffect, convexityEffect, trading].map((v) =>
    finiteNumberOr(v),
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
