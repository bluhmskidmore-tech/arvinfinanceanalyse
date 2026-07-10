import type {
  RiskTensorPayload,
  RiskTensorScalar,
} from "../../../api/contracts";
import { bondNumericRawOrNull } from "../../bond-analytics/adapters/bondAnalyticsAdapter";
import type {
  ModuleHomeDetailChart,
} from "./moduleHomeModel";

const RISK_YUAN_PER_WAN = 10_000;

const RISK_KRD_FIELDS = [
  { key: "krd_1y", label: "KRD 1Y" },
  { key: "krd_3y", label: "KRD 3Y" },
  { key: "krd_5y", label: "KRD 5Y" },
  { key: "krd_7y", label: "KRD 7Y" },
  { key: "krd_10y", label: "KRD 10Y" },
  { key: "krd_30y", label: "KRD 30Y" },
] as const satisfies ReadonlyArray<{ key: keyof RiskTensorPayload; label: string }>;

function riskTensorRaw(value: RiskTensorScalar | null | undefined): number | null {
  return bondNumericRawOrNull(value);
}

export function buildRiskKrdChart(tensor: RiskTensorPayload): ModuleHomeDetailChart | undefined {
  const categories: string[] = [];
  const values: number[] = [];

  for (const field of RISK_KRD_FIELDS) {
    const raw = riskTensorRaw(tensor[field.key] as RiskTensorScalar | null | undefined);
    if (raw === null) {
      continue;
    }
    categories.push(field.label);
    values.push(Math.abs(raw) / RISK_YUAN_PER_WAN);
  }

  if (categories.length < 2) {
    return undefined;
  }

  return {
    title: "KRD 分布",
    unit: "万元",
    orientation: "horizontal",
    categories,
    values,
  };
}
