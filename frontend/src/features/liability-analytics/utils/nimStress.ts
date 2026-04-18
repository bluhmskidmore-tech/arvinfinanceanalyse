import type { LiabilityYieldKpi } from "../../../api/contracts";

function pctDecimal(n: Numeric | null | undefined): number | null {
  if (!n || n.raw === null || !Number.isFinite(n.raw)) {
    return null;
  }
  return n.raw;
}

/** 与 V1 一致：负债成本 +50bps（+0.005 小数）后的 NIM 与变动。 */
export function dailyNimStressFromKpi(yieldKpi: LiabilityYieldKpi | null) {
  const ay = pctDecimal(yieldKpi?.asset_yield ?? null);
  const mlc = pctDecimal(yieldKpi?.market_liability_cost ?? null);
  const nimExplicit = pctDecimal(yieldKpi?.nim ?? null);
  const nim =
    nimExplicit !== null
      ? nimExplicit
      : ay !== null && mlc !== null && Number.isFinite(ay) && Number.isFinite(mlc)
        ? ay - mlc
        : null;
  const projected =
    ay !== null && mlc !== null && Number.isFinite(ay) && Number.isFinite(mlc) ? ay - (mlc + 0.005) : null;
  const delta = projected !== null && nim !== null ? projected - nim : null;
  const isCritical = projected !== null ? projected < 0.005 : false;
  return { ay, mlc, nim, projected, delta, isCritical };
}

export function fmtDecimalRatePct(v: number | null): string {
  if (v === null || !Number.isFinite(v)) {
    return "—";
  }
  return `${(v * 100).toFixed(2)}%`;
}
