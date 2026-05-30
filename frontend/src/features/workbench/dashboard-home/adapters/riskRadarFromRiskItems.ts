import type { DashboardCockpitRiskItem } from "../../dashboard/dashboardCockpitModel";
import { DASHBOARD_RISK_RADAR_MOCK } from "../../dashboard/dashboardMockData";

export type HomeRiskRadarVM = {
  dimensions: readonly string[];
  values: readonly number[];
  pending?: boolean;
};

const RISK_RADAR_SPECS: ReadonlyArray<{ riskId: string; label: string }> = [
  { riskId: "dv01", label: "利率风险" },
  { riskId: "duration", label: "久期风险" },
  { riskId: "issuer-top5", label: "集中度风险" },
  { riskId: "credit-weight", label: "信用风险" },
];

export function buildRiskRadarFromRiskItems(
  riskItems: readonly DashboardCockpitRiskItem[],
  useMockFallback: boolean,
): { radar: HomeRiskRadarVM; usesMock: boolean } {
  if (useMockFallback) {
    return {
      radar: {
        dimensions: [...DASHBOARD_RISK_RADAR_MOCK.dimensions],
        values: [...DASHBOARD_RISK_RADAR_MOCK.values],
      },
      usesMock: true,
    };
  }

  const byId = new Map(riskItems.map((item) => [item.id, item]));
  const dimensions: string[] = [];
  const values: number[] = [];

  for (const spec of RISK_RADAR_SPECS) {
    const item = byId.get(spec.riskId);
    if (item && item.status !== "blocked" && item.level > 0) {
      dimensions.push(spec.label);
      values.push(item.level);
    }
  }

  if (dimensions.length >= 3) {
    return {
      radar: { dimensions, values, pending: false },
      usesMock: false,
    };
  }

  const usable = riskItems.filter((item) => item.status !== "blocked" && item.level > 0);
  if (usable.length >= 3) {
    return {
      radar: {
        dimensions: usable.map((item) => item.label),
        values: usable.map((item) => item.level),
        pending: false,
      },
      usesMock: false,
    };
  }

  return {
    radar: { dimensions: [], values: [], pending: true },
    usesMock: false,
  };
}
