import type { Numeric } from "../../../api/contracts";
import type { LiabilityYieldKpi } from "../../../api/liabilityAdbContracts";

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
  const projected = yieldKpi?.nim_stress?.nim_stressed ?? null;
  const deltaBp = yieldKpi?.nim_stress?.delta_bp ?? null;
  const projectedRaw = pctDecimal(projected);
  const isCritical = projectedRaw !== null ? projectedRaw < NIM_CRITICAL_FLOOR - FLOAT_EPSILON : false;

  return {
    ay: yieldKpi?.asset_yield ?? null,
    mlc: yieldKpi?.market_liability_cost ?? null,
    nim: yieldKpi?.nim ?? null,
    projected,
    deltaBp,
    isCritical,
  };
}
