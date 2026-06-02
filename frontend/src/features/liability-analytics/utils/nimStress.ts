import type { LiabilityYieldKpi, Numeric } from "../../../api/contracts";
import { formatRawAsNumeric } from "../../../utils/format";

function pctDecimal(n: Numeric | null | undefined): number | null {
  if (!n || n.raw === null || !Number.isFinite(n.raw)) {
    return null;
  }
  return n.raw;
}

const NIM_CRITICAL_FLOOR = 0.005;
const FLOAT_EPSILON = 1e-9;

/** 与 V1 一致：负债成本 +50bps（0.005 小数）后的 NIM 与变动。 */
export function dailyNimStressFromKpi(yieldKpi: LiabilityYieldKpi | null) {
  const ayRaw = pctDecimal(yieldKpi?.asset_yield ?? null);
  const mlcRaw = pctDecimal(yieldKpi?.market_liability_cost ?? null);
  const nimExplicitRaw = pctDecimal(yieldKpi?.nim ?? null);
  const nimRaw =
    nimExplicitRaw !== null
      ? nimExplicitRaw
      : ayRaw !== null && mlcRaw !== null && Number.isFinite(ayRaw) && Number.isFinite(mlcRaw)
        ? ayRaw - mlcRaw
        : null;
  const projectedRaw =
    ayRaw !== null && mlcRaw !== null && Number.isFinite(ayRaw) && Number.isFinite(mlcRaw)
      ? ayRaw - (mlcRaw + 0.005)
      : null;
  const deltaBpRaw = projectedRaw !== null && nimRaw !== null ? (projectedRaw - nimRaw) * 10000 : null;
  const isCritical = projectedRaw !== null ? projectedRaw < NIM_CRITICAL_FLOOR - FLOAT_EPSILON : false;

  return {
    ay: yieldKpi?.asset_yield ?? null,
    mlc: yieldKpi?.market_liability_cost ?? null,
    nim:
      yieldKpi?.nim ??
      (nimRaw === null ? null : formatRawAsNumeric({ raw: nimRaw, unit: "pct", sign_aware: true, precision: 2 })),
    projected:
      projectedRaw === null
        ? null
        : formatRawAsNumeric({ raw: projectedRaw, unit: "pct", sign_aware: true, precision: 2 }),
    deltaBp:
      deltaBpRaw === null
        ? null
        : formatRawAsNumeric({ raw: deltaBpRaw, unit: "bp", sign_aware: true, precision: 1 }),
    isCritical,
  };
}
