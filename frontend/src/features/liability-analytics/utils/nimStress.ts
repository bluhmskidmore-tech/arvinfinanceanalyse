import type { LiabilityYieldKpi } from "../../../api/liabilityAdbContracts";

/** 与 V1 一致：负债成本 +50bps（0.005 小数）后的 NIM 与变动。 */
export function dailyNimStressFromKpi(yieldKpi: LiabilityYieldKpi | null) {
  const projected = yieldKpi?.nim_stress?.nim_stressed ?? null;
  const deltaBp = yieldKpi?.nim_stress?.delta_bp ?? null;

  return {
    ay: yieldKpi?.asset_yield ?? null,
    mlc: yieldKpi?.market_liability_cost ?? null,
    nim: yieldKpi?.nim ?? null,
    projected,
    deltaBp,
  };
}
