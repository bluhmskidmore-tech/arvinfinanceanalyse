import type { Numeric, ReturnDecompositionPayload } from "../../../api/contracts";

/** Raw scalar for charts / sorting; governed Numeric or legacy string. */
export function bondNumericRaw(n: Numeric | string | null | undefined): number {
  if (n === null || n === undefined) {
    return 0;
  }
  if (typeof n === "string") {
    const v = Number.parseFloat(n);
    return Number.isFinite(v) ? v : 0;
  }
  if (n.raw === null || !Number.isFinite(n.raw)) {
    return 0;
  }
  return n.raw;
}

export function bondNumericRawOrNull(n: Numeric | string | null | undefined): number | null {
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

export function bondNumericDisplay(n: Numeric | string | null | undefined): string {
  if (n === null || n === undefined) {
    return "—";
  }
  if (typeof n === "string") {
    return n === "" ? "—" : n;
  }
  return n.display || "—";
}

/** ECharts / table magnitude from risk tensor string or bond-analytics Numeric. */
export function bondChartMagnitude(value: Numeric | string): number {
  return bondNumericRaw(value);
}

export function returnDecompositionWaterfallRawSteps(d: ReturnDecompositionPayload): number[] {
  const carry = bondNumericRaw(d.carry);
  const rollDown = bondNumericRaw(d.roll_down);
  const rateEffect = bondNumericRaw(d.rate_effect);
  const spreadEffect = bondNumericRaw(d.spread_effect);
  const trading = bondNumericRaw(d.trading);
  const fxEffect = bondNumericRaw(d.fx_effect);
  const convexityEffect = bondNumericRaw(d.convexity_effect);
  const explained = bondNumericRaw(d.explained_pnl);
  const stepValues = [carry, rollDown, rateEffect, spreadEffect, fxEffect, convexityEffect, trading].map((v) =>
    Number.isFinite(v) ? v : 0,
  );
  return [...stepValues, Number.isFinite(explained) ? explained : 0];
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
